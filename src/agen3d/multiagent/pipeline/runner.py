"""One measured raw-input pipeline; variant policies only change model routing.

Every expensive stage starts after the run clock. Reconstruction never reads the
evaluation dataset; its separate subprocess starts only after the last agent call.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from pydantic import Field

from agen3d.io import digest
from agen3d.schema import Record, SceneState
from agen3d.verification import Verifier
from ..contracts import Evidence, RunConfig, Task
from ..engine import Runner
from ..models import ModelRegistry
from ..process import run_process
from ..store import save
from .accounting import Timings, usage_summary, complete_costs
from .geometry import reconstruct
from .inputs import prepare
from .rendering import accept_repair, object_focus, overview_pairs, source_fit


class Category(Record):
    category: str = Field(min_length=1, max_length=60)
    prompt: str = Field(min_length=1, max_length=120)


class Inventory(Record):
    categories: list[Category] = Field(min_length=1, max_length=40)


class AssetChoice(Record):
    object_id: str
    asset_id: str | None
    reason: str


class AssetChoices(Record):
    choices: list[AssetChoice] = Field(min_length=1, max_length=20)


class Pipeline:
    def __init__(self, config):
        self.config = config
        self.output = Path(config.output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.timing = Timings(self.output)
        self.agent = None
        self.categories = {}
        self.assets = {}
        self.catalog = {}
        self.final_dir = None
        self.failure = None
        self.gpu_wall_seconds = 0.
        self.cpu_render_seconds = 0.
        save(self.output / "pipeline.config.json", config.model_dump(mode="json"))

    def register(self, key, path, kind="image", description=""):
        path = Path(path).resolve()
        context = self.agent.context
        if not path.is_relative_to(self.output):
            raise ValueError("Pipeline may register only its own artifacts")
        context.config.evidence[key] = Evidence(path=str(path), sha256=digest(path), kind=kind,
                                               description=description or key)
        context.generated_ids.add(key)
        return key

    def record_categories(self, args):
        for item in args.categories:
            key = item.category.lower().replace(" ", "")
            if key not in self.categories and len(self.categories) >= self.config.max_categories:
                raise ValueError("Category budget reached; keep omissions explicit")
            self.categories[key] = item.model_dump()
        save(self.output / "inventory.json", list(self.categories.values()))
        return {"categories_recorded": len(self.categories)}

    def choose_assets(self, args):
        for choice in args.choices:
            if choice.object_id not in self.assets:
                raise ValueError("Unknown object")
            if choice.asset_id is not None and choice.asset_id not in self.catalog:
                raise ValueError("Choose a registered collection ID from the provided catalog")
            self.assets[choice.object_id]["asset_id"] = choice.asset_id
            self.assets[choice.object_id]["choice_reason"] = choice.reason
        save(self.output / "reconstruction/assets.json", self.assets)
        return {"recorded": len(args.choices)}

    def gpu(self, backend, service_name, request):
        """Charge loading/inference/export wall time; no hidden preparation outside the run."""
        spec = self.config.services[service_name]
        registry = ModelRegistry()
        checkpoint = registry.resolve(spec.checkpoint)
        key = self.agent.ledger.reserve("gpu:" + backend, spec.reservation_usd,
                                        self.config.judge_reserve_usd)
        folder = self.output / "jobs" / key
        folder.mkdir(parents=True)
        request.update(service=backend, repo=spec.repo, checkpoint=str(checkpoint), output=str(folder),
                       model_reference=spec.checkpoint,
                       model_revision=registry.specs[spec.checkpoint.split(":")[1]]["revision"])
        save(folder / "request.json", request)
        worker = Path(__file__).resolve().parents[1] / "specialist_worker.py"
        start = time.monotonic()
        try:
            import fcntl
            with (self.output.parent / ".agen3d-gpu.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with (folder / "stdout.log").open("w") as stdout, (folder / "stderr.log").open("w") as stderr:
                    result = run_process([spec.python, str(worker), str(folder / "request.json")],
                        cwd=spec.repo, stdout=stdout, stderr=stderr, timeout=spec.timeout_s,
                        env={**os.environ, "AGEN3D_MODEL_ROOT": str(registry.root),
                             "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                             "HF_HUB_CACHE": str(registry.root / "hub")})
                    result.check_returncode()
            return json.loads((folder / "result.json").read_text())
        finally:
            elapsed = time.monotonic() - start
            self.gpu_wall_seconds += elapsed
            actual = elapsed/3600*self.config.gpu_hourly_usd if self.config.gpu_hourly_usd is not None else None
            self.agent.ledger.settle(key, actual, {"wall_seconds": elapsed, "resource": "GPU job wall time",
                "pricing": "configured hourly rate" if actual is not None else "unknown",
                "service": backend, "request": str(folder / "request.json")})

    def render(self, scene, name):
        folder = self.output / "renders" / name
        request_path = self.output / "reconstruction" / f"render_{name}.json"
        scene_path = self.output / "reconstruction" / f"scene.{name}.json"
        save(scene_path, scene.model_dump(mode="json"))
        save(request_path, {"scene": str(scene_path), "assets": str(self.output / "reconstruction/assets.json"),
            "cameras": str(self.output / "reconstruction/cameras.predicted.json"),
            "view_indices": self.views, "aha_repo": self.config.aha_repo, "output": str(folder)})
        key = self.agent.ledger.reserve("cpu:render", .05, self.config.judge_reserve_usd)
        start = time.monotonic()
        try:
            script = Path(__file__).with_name("blender_scene.py")
            with (request_path.with_suffix(".log")).open("w") as log:
                result = run_process([self.config.blender, "-b", "-t", "8", "--python-exit-code", "1",
                    "-P", str(script), "--", str(request_path)], stdout=log, stderr=subprocess.STDOUT, timeout=1200)
                result.check_returncode()
            if not (folder / "scene.blend").is_file():
                raise RuntimeError("Blender did not save the authored scene")
            scores = source_fit(folder, self.associations, self.cameras)
            comparisons = overview_pairs(folder, self.manifest, self.output / "inputs", self.views)
            focus = object_focus(folder, self.manifest, self.output / "inputs", self.associations, self.cameras)
            return folder, scores, comparisons, focus
        finally:
            elapsed = time.monotonic()-start
            self.cpu_render_seconds += elapsed
            actual = elapsed/3600*self.config.cpu_hourly_usd if self.config.cpu_hourly_usd is not None else None
            self.agent.ledger.settle(key, actual, {"wall_seconds": elapsed, "resource": "CPU Blender rendering"})

    def ask(self, task_id, role, instruction, evidence_ids=(), object_ids=(), max_turns=3):
        decision = self.agent.task(Task(task_id=task_id, role=role, instruction=instruction,
            evidence_ids=list(evidence_ids), object_ids=list(object_ids), max_turns=max_turns))
        if decision.status == "abstain" and decision.summary.startswith("Provider failed:"):
            raise RuntimeError(f"{task_id}: {decision.summary}")
        return decision

    def run(self):
        evaluation_status = "not_run"
        judge_status = "not_run"
        try:
            with self.timing.stage("decode_select_copy_hash_inputs"):
                self.manifest = prepare(Path(self.config.input), self.output, self.config.frames,
                                        self.config.scene_id, self.config.dataset_kind)
            self.views = np.linspace(0, self.config.frames-1, self.config.segmentation_views).round().astype(int).tolist()
            with self.timing.stage("initialize_models_and_protocol"):
                empty = SceneState(scene_id=self.config.scene_id, alignment_id="pi3x-predicted-world", objects=[])
                save(self.output / "inputs/scene.empty.json", empty.model_dump())
                run_config = RunConfig(variant=self.config.variant, scene=str(self.output / "inputs/scene.empty.json"),
                    evidence_root=str(self.output / "inputs"), output=str(self.output / "agents"),
                    models=self.config.models, services={}, budget_usd=self.config.budget_usd,
                    judge_reserve_usd=self.config.judge_reserve_usd)
                self.agent = Runner(run_config)
                # Agent-written artifacts and pipeline-produced evidence share this run root.
                self.agent.context.output = self.output
                self.agent.registry.add("record_categories", "Record visually observed object categories and SAM prompts. "
                    "Do not infer object coordinates or use labels.", {"inventory"}, Inventory, self.record_categories)
                self.agent.registry.add("choose_assets", "Choose registered reusable collection assets for tracked objects; "
                    "null keeps an explicitly labeled observed-point hull.", {"asset"}, AssetChoices, self.choose_assets)
                overviews = [self.register(p.stem, p) for p in sorted((self.output / "inputs").glob("overview_*.jpg"))]
                rgb = [self.register("rgb_"+f.frame_id, self.output / "inputs" / f.path,
                                     description=f"Selected input RGB frame {f.frame_id}") for f in self.manifest.frames]
                # No dataset path, GT metadata, camera truth or evaluator artifact enters a task.
            with self.timing.stage("strong_planning"):
                self.ask("plan", "planner", "Plan priorities and failure checks for rebuilding this room. "
                    "The fixed measured stages are inventory, Pi3X, SAM3, object association, RoomKit asset "
                    "selection, rendering, one bounded repair and independent review. Use only source images. "
                    "Return a concise plan in summary; the scheduler owns stage order.", overviews[:12], max_turns=2)
            with self.timing.stage("cheap_visual_inventory"):
                for start in range(0, len(rgb), 4):
                    self.ask(f"inventory_{start:03d}", "inventory", "Inspect these four selected frames carefully, "
                        "including small tabletop objects. Call record_categories with observed categories and "
                        "short SAM3 text prompts. Use common AI2-THOR category names when known (Sofa, ArmChair, "
                        "CoffeeTable, Laptop, Vase, Pillow, FloorLamp, Painting, HousePlant, RemoteControl, etc.); "
                        "do not treat repeated views as new categories. Do not invent invisible objects. "
                        "Finish only after recording categories. Coordinates will come from predicted geometry.",
                        rgb[start:start+4], max_turns=3)
                if not self.categories:
                    raise RuntimeError("Inventory produced no usable categories; refusing a fabricated reconstruction")
            with self.timing.stage("pi3x_loading_inference_export"):
                geometry = self.gpu("pi3x", "pi3x", {"images": [str(self.output / "inputs" / f.path) for f in self.manifest.frames]})
            with self.timing.stage("sam3_loading_segmentation_export"):
                categories = list(self.categories.values())
                if not any(c["category"].lower() == "floor" for c in categories):
                    categories.append({"category": "Floor", "prompt": "floor"})
                masks = self.gpu("sam3_batch", "sam3", {"categories": categories,
                    "frames": [{"index": i, "path": str(self.output / "inputs" / self.manifest.frames[i].path)} for i in self.views]})
            with self.timing.stage("coordinate_frame_tracking_and_geometry"):
                reconstruction = self.output / "reconstruction"
                reconstruction.mkdir()
                scene, self.assets, self.associations = reconstruct(geometry["geometry"], masks["masks_manifest"],
                    self.manifest, self.output / "inputs", reconstruction, self.config.max_objects)
                if not scene.objects:
                    raise RuntimeError("No valid tracked objects from predicted masks/geometry")
                for obj in scene.objects:
                    self.assets[obj.object_id]["initial_extent"] = list(obj.box.extent)
                save(reconstruction / "assets.json", self.assets)
                self.cameras = json.loads((reconstruction / "cameras.predicted.json").read_text())
                self.agent.context.scene = scene
                self.agent.context.version += 1
            with self.timing.stage("cheap_asset_selection"):
                entries = json.loads((Path(self.config.aha_repo) / "assets/index.json").read_text())["entries"]
                self.catalog = {e["id"]: e for e in entries if e.get("status") == "registered" and e.get("kind") == "collection"}
                cards = [{"id": k, "name": v["name"], "dimensions_m": v.get("dimensions_m"),
                          "category": v.get("category")} for k, v in self.catalog.items()]
                save(reconstruction / "asset_catalog.used.json", cards)
                for start in range(0, len(scene.objects), 12):
                    objects = scene.objects[start:start+12]
                    self.ask(f"assets_{start:03d}", "asset", "Choose appropriate reusable assets for these object IDs "
                        "using their categories/extents and source images. Call choose_assets. Use null for objects "
                        "with no appropriate catalog asset; their fallback is an explicitly approximate point hull. "
                        "Do not select unrelated furniture just to avoid null. Catalog: " + json.dumps(cards),
                        overviews[:4], [o.object_id for o in objects], max_turns=3)
            with self.timing.stage("initial_assembly_render_and_source_checks"):
                current_dir, scores, comparisons, focus = self.render(scene, "initial")
                self.final_dir = current_dir
            for round_index in range(self.config.repair_rounds + 1):
                with self.timing.stage(f"cheap_per_object_review_{round_index}"):
                    focus_ids = {oid: self.register(f"focus_{round_index}_{oid}", path) for oid, path in focus.items()}
                    ids = list(focus_ids)
                    for start in range(0, len(ids), 4):
                        group = ids[start:start+4]
                        self.ask(f"critic_{round_index}_{start:03d}", "critic", "Review each supplied object source/render "
                            "focus. Identify wrong identity, extent, orientation, placement or missing geometry. "
                            "Use emit_issue for actionable failures; do not call a good-looking picture an evaluation "
                            "score. Mask IoUs: " + json.dumps({oid:scores[oid] for oid in group}),
                            [focus_ids[oid] for oid in group], group, max_turns=2)
                if round_index >= self.config.repair_rounds:
                    break
                with self.timing.stage(f"bounded_repair_{round_index}"):
                    before_count = len(self.agent.context.proposals)
                    worst = sorted(scores, key=lambda oid: scores[oid]["mean_mask_iou"] or 0)[:4]
                    self.ask(f"repair_{round_index}", "geometry", "Use source/render focus and recorded critic issues "
                        "to propose at most three small transform corrections. Use propose_transform or fit_support "
                        "only with registered visual evidence. Never change scene scale/cameras. Abstain if geometry "
                        "cannot justify an edit. The scheduler will reject source-fit regressions.",
                        [focus_ids[oid] for oid in worst if oid in focus_ids], worst, max_turns=3)
                    proposals = self.agent.context.proposals[before_count:][:3]
                    candidate = scene.model_copy(deep=True)
                    changed = set()
                    for proposal in proposals:
                        if proposal["object_id"] in changed:
                            continue
                        obj = next(o for o in candidate.objects if o.object_id == proposal["object_id"])
                        from agen3d.schema import Box
                        obj.box = Box.model_validate(proposal["after"])
                        changed.add(obj.object_id)
                    if changed:
                        candidate_dir, candidate_scores, candidate_pairs, candidate_focus = self.render(candidate, f"repair_{round_index}")
                        accepted = accept_repair(scores, candidate_scores, changed,
                                                len(Verifier().check(scene)), len(Verifier().check(candidate)))
                        save(candidate_dir / "acceptance.json", {"accepted": accepted, "changed_ids": sorted(changed),
                            "criterion": "source-mask improvement, no material regression, no added box issues"})
                        if accepted:
                            scene, scores, comparisons, focus = candidate, candidate_scores, candidate_pairs, candidate_focus
                            self.final_dir = candidate_dir
                            self.agent.context.scene = scene
                            self.agent.context.version += 1
            with self.timing.stage("save_selected_scene_and_strong_final_review"):
                save(self.output / "scene.final.json", scene.model_dump(mode="json"))
                save(self.output / "selected.json", {"scene": str(self.output / "scene.final.json"),
                    "blend": str(self.final_dir / "scene.blend"), "renders": str(self.final_dir),
                    "asset_representations": json.loads((self.final_dir / "manifest.json").read_text())["objects"]})
                ids = [self.register(f"final_comparison_{i}", path) for i, path in enumerate(comparisons)]
                judge = self.ask("final_judge", "judge", "Independently review the saved reconstruction against the "
                    "source/render comparisons and per-object critic findings. The scene contains reusable RoomKit "
                    "assets plus explicit observed-point hull approximations. State remaining defects and accept "
                    "only if evidence supports it. No benchmark scores or GT are available. Repairs were accepted "
                    "only on input-derived checks. Return pass, repair, or abstain.", ids[:12], max_turns=3)
                judge_status = judge.status
            # Ground truth is opened only in this separate process after all model work.
            if self.config.evaluation_dataset:
                if self.config.dataset_kind != "ai2thor":
                    raise ValueError("This automatic evaluator currently supports AI2-THOR only")
                with self.timing.stage("offline_ground_truth_evaluation"):
                    evaluation_dir = self.output / "evaluation"
                    with (self.output / "evaluation.log").open("w") as log:
                        result = run_process([sys.executable, "-m", "agen3d.multiagent.pipeline.evaluate_run",
                            "--dataset", self.config.evaluation_dataset, "--manifest", str(self.output / "inputs/manifest.json"),
                            "--scene", str(self.output / "scene.final.json"), "--cameras", str(self.output / "reconstruction/cameras.predicted.json"),
                            "--output", str(evaluation_dir)], stdout=log, stderr=subprocess.STDOUT, timeout=600)
                        result.check_returncode()
                    evaluation_status = "completed"
            else:
                evaluation_status = "unavailable_no_labels"
        except Exception as exc:
            self.failure = f"{type(exc).__name__}: {exc}"
        finally:
            timing = self.timing.flush()
            report = {"status": "failed" if self.failure else "completed" if judge_status == "pass" else "completed_with_unresolved",
                "error": self.failure, "variant": self.config.variant, "input": self.config.input,
                "preprocessing_included": True, "cache_mode": "fresh_inference_no_cross_run_cache",
                "timing": timing, "gpu_job_wall_seconds": self.gpu_wall_seconds,
                "cpu_render_wall_seconds": self.cpu_render_seconds,
                "tokens_and_calls": usage_summary(self.agent.ledger) if self.agent else {},
                "cost": complete_costs(self.agent.ledger if self.agent else None, timing,
                    self.gpu_wall_seconds, self.cpu_render_seconds, self.config.cpu_hourly_usd),
                "local_compute_cost_complete": self.config.gpu_hourly_usd is not None and self.config.cpu_hourly_usd is not None,
                "evaluation": evaluation_status, "judge_status": judge_status,
                "selected": str(self.output / "selected.json") if self.final_dir else None,
                "quality_claim": "pilot reconstruction; hull fallback and unobserved geometry remain approximate"}
            save(self.output / "report.json", report)
        return report
