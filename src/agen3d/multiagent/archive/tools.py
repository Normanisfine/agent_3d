"""Concrete, path-contained tools. Models receive IDs, never arbitrary host paths."""
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
from PIL import Image
from pydantic import Field

from agen3d.geometry import corners
from agen3d.schema import Box, ObjectState, Record, SceneState
from agen3d.verification import Verifier

from .protocol import Registry
from agen3d.multiagent.process import run_process
from agen3d.multiagent.models import ModelRegistry
from agen3d.multiagent.archive.contracts import Evidence
from agen3d.multiagent.store import save

ALL_ROLES = {"planner", "inventory", "geometry", "asset", "critic", "judge", "physics"}


class Empty(Record):
    pass


class EvidenceArgs(Record):
    evidence_id: str


class ObjectArgs(Record):
    object_id: str


class TransformArgs(ObjectArgs):
    box: Box
    reason: str
    evidence_ids: list[str] = Field(min_length=1)


class ObjectProposalArgs(Record):
    object: ObjectState
    evidence_ids: list[str] = Field(min_length=1)


class SupportFitArgs(ObjectArgs):
    evidence_ids: list[str] = Field(min_length=1)


class CompareMasks(Record):
    source_mask: str
    rendered_mask: str


class SpatialArgs(Record):
    image_id: str
    question: str = Field(min_length=1, max_length=2000)


class SegmentArgs(Record):
    image_id: str
    prompt: str = Field(min_length=1, max_length=300)


class Pi3xArgs(Record):
    image_ids: list[str] = Field(min_length=2, max_length=64)


class GenerateArgs(ObjectArgs):
    image_id: str
    mask_id: str | None = None
    seed: int = Field(default=42, ge=0, le=2147483647)


class IssueArgs(ObjectArgs):
    issue_type: str
    severity: str = Field(pattern="^(low|medium|high)$")
    evidence_ids: list[str] = Field(min_length=1)
    suggested_action: str


class AssetQuery(Record):
    query: str = Field(min_length=1, max_length=200)


class ToolContext:
    def __init__(self, config, scene: SceneState, output: Path, ledger):
        self.config, self.scene, self.output, self.ledger = config, scene, output, ledger
        self.root = Path(config.evidence_root).resolve()
        self.version = 0
        self.issues = []
        self.proposals = []
        self.object_proposals = []
        self.requested_images: list[Path] = []
        self.generations = 0
        self.service_cache = {}
        self.generated_ids = set()

    def evidence(self, evidence_id, kinds=None):
        """Resolve only approved or runtime-produced evidence and recheck its identity."""
        record = self.config.evidence.get(evidence_id)
        if record is None or (kinds and record.kind not in kinds):
            raise ValueError(f"Unknown or incompatible evidence: {evidence_id}")
        path = (self.root / record.path).resolve()
        approved_root = self.output if evidence_id in self.generated_ids else self.root
        if not path.is_relative_to(approved_root) or not path.is_file():
            raise PermissionError("Evidence must be a file inside the approved evidence root")
        if hashlib.sha256(path.read_bytes()).hexdigest() != record.sha256:
            raise ValueError(f"Evidence changed: {evidence_id}")
        return path

    def get_evidence(self, args):
        path = self.evidence(args.evidence_id)
        record = self.config.evidence[args.evidence_id]
        if record.kind in {"image", "mask"}:
            if path not in self.requested_images:
                if len(self.requested_images) >= 12:
                    raise ValueError("Task image limit reached")
                self.requested_images.append(path)
            return {"evidence_id": args.evidence_id, "attached_next_turn": True,
                    "description": record.description}
        if record.kind == "json":
            if path.stat().st_size > 64000:
                raise ValueError("JSON evidence exceeds 64KB; prepare a summary")
            return json.loads(path.read_text())
        return {"evidence_id": args.evidence_id, "kind": record.kind,
                "description": record.description, "bytes": path.stat().st_size}

    def object(self, object_id):
        for obj in self.scene.objects:
            if obj.object_id == object_id:
                return obj
        raise ValueError(f"Unknown object {object_id}")

    def summarize(self, args):
        obj = self.object(args.object_id)
        points = corners(obj.box)
        return {"object": obj.model_dump(mode="json"),
                "aabb_min_m": points.min(0).tolist(), "aabb_max_m": points.max(0).tolist(),
                "box_volume_m3": float(np.prod(obj.box.extent)),
                "warning": "box volume is not solid material volume"}

    def propose_transform(self, args):
        obj = self.object(args.object_id)
        for ref in args.evidence_ids:
            self.evidence(ref)
        displacement = np.linalg.norm(np.array(args.box.center) - obj.box.center)
        if displacement > 0.1 + 1e-9:
            raise ValueError("Local transform exceeds 0.10m bound; needs a separate global plan")
        proposal = {"id": len(self.proposals), "scene_version": self.version,
                    "object_id": obj.object_id, "before": obj.box.model_dump(),
                    "after": args.box.model_dump(), "reason": args.reason,
                    "evidence_ids": args.evidence_ids, "status": "unverified_proposal"}
        self.proposals.append(proposal)
        save(self.output / "proposals.json", self.proposals)
        return proposal

    def compare_masks(self, args):
        a = np.asarray(Image.open(self.evidence(args.source_mask, {"mask"})).convert("L")) > 127
        b = np.asarray(Image.open(self.evidence(args.rendered_mask, {"mask"})).convert("L")) > 127
        if a.shape != b.shape:
            raise ValueError("Source/render masks must share raster and camera")
        union = int(np.logical_or(a, b).sum())
        return {"iou": float(np.logical_and(a, b).sum() / union) if union else None,
                "source_pixels": int(a.sum()), "render_pixels": int(b.sum()),
                "warning": "Caller must supply matched camera/view; IoU alone is not acceptance"}

    def propose_object(self, args):
        if args.object.object_id in {o.object_id for o in self.scene.objects}:
            raise ValueError("Object ID already exists")
        for ref in args.evidence_ids:
            self.evidence(ref)
        proposal = {"kind": "add_object", "object": args.object.model_dump(mode="json"),
                    "evidence_ids": args.evidence_ids, "status": "unverified_proposal"}
        self.object_proposals.append(proposal)
        save(self.output / "object_proposals.json", self.object_proposals)
        return proposal

    def fit_support(self, args):
        obj = self.object(args.object_id)
        issues = [i for i in Verifier().check(self.scene)
                  if i.object_id == obj.object_id and i.issue_type == "support_gap"]
        if len(issues) != 1:
            raise ValueError("No unique supported axis-aligned support-gap correction")
        box = obj.box.model_copy(deep=True)
        x, y, z = box.center
        box.center = (x, y, z - issues[0].evidence["gap_m"])
        return self.propose_transform(TransformArgs(object_id=obj.object_id, box=box,
            reason="Numerical support snap; needs rendered-source validation", evidence_ids=args.evidence_ids))

    def emit_issue(self, args):
        self.object(args.object_id)
        for ref in args.evidence_ids:
            self.evidence(ref)
        self.issues.append(args.model_dump())
        save(self.output / "semantic_issues.json", self.issues)
        return {"recorded": True, "issue_index": len(self.issues) - 1}

    def primitive(self, args):
        obj = self.object(args.object_id)
        # OBJ in local object coordinates. Pose remains a separate scene transform.
        box = obj.box.model_copy(update={"center": (0., 0., 0.),
                                       "rotation": ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))})
        points = corners(box)
        from scipy.spatial import ConvexHull
        hull = ConvexHull(points)
        asset_id = hashlib.sha256(args.object_id.encode()).hexdigest()[:16]
        path = self.output / "assets" / f"{asset_id}-box.obj"
        path.parent.mkdir(exist_ok=True)
        lines = ["v " + " ".join(map(str, p)) for p in points]
        for face, equation in zip(hull.simplices, hull.equations):
            face = face.copy()
            p, q, r = points[face]
            if np.dot(np.cross(q - p, r - p), equation[:3]) < 0:
                face[[1, 2]] = face[[2, 1]]
            lines.append("f " + " ".join(str(int(i) + 1) for i in face))
        path.write_text("\n".join(lines) + "\n")
        return {"artifact": str(path.relative_to(self.output)), "status": "candidate",
                "units": "metres", "object_id": args.object_id}

    def service(self, name, args):
        """Run a pinned specialist with a lease, or reuse this run's exact result.

        Result paths are never trusted just because a subprocess exited zero.
        Artifacts must remain under its job directory before they become evidence.
        """
        spec = self.config.services[name]
        model_registry = ModelRegistry()
        if not spec.checkpoint or not spec.checkpoint.startswith("model:"):
            raise ValueError("Specialists require a pinned model:alias checkpoint reference")
        image_ids = args.image_ids if name == "pi3x" else [args.image_id]
        images = [self.evidence(ref, {"image"}) for ref in image_ids]
        image = images[0]
        mask = self.evidence(args.mask_id, {"mask"}) if getattr(args, "mask_id", None) else None
        if name == "sam3d" and mask is None:
            raise ValueError("SAM 3D requires an object mask")
        if name in {"sam3d", "hunyuan"}:
            self.object(args.object_id)
        signature = json.dumps({"service": name, "spec": spec.model_dump(),
                                "args": args.model_dump(),
                                "images": [self.config.evidence[ref].sha256 for ref in image_ids],
                                "model_lock": hashlib.sha256(model_registry.lock_path.read_bytes()).hexdigest(),
                                "mask": self.config.evidence[args.mask_id].sha256 if mask else None},
                               sort_keys=True)
        cache_key = hashlib.sha256(signature.encode()).hexdigest()
        if cache_key in self.service_cache:
            return {**self.service_cache[cache_key], "cache_hit": True}
        if name in {"sam3d", "hunyuan"} and self.generations >= self.config.max_generations:
            raise ValueError("Scene generation cap reached")
        checkpoint = model_registry.resolve(spec.checkpoint)
        moge = model_registry.resolve("model:moge") if name == "hispatial" else None
        key = self.ledger.reserve(f"service:{name}", spec.reservation_usd,
                                  self.config.judge_reserve_usd)
        folder = self.output / "jobs" / key
        folder.mkdir(parents=True)
        request = {"service": name, "repo": spec.repo, "checkpoint": str(checkpoint),
                   "model_reference": spec.checkpoint,
                   "model_revision": model_registry.specs[spec.checkpoint.split(":", 1)[1]]["revision"],
                   "image": str(image), "mask": str(mask) if mask else None,
                   "images": [str(p) for p in images],
                   "output": str(folder), "seed": getattr(args, "seed", 42),
                   "question": getattr(args, "question", None),
                   "prompt": getattr(args, "prompt", None), "moge": str(moge) if moge else None}
        save(folder / "request.json", request)
        worker = Path(__file__).resolve().parents[1] / "specialist_worker.py"
        start = time.monotonic()
        if name in {"sam3d", "hunyuan"}:
            self.generations += 1
        try:
            # fcntl serializes GPU work across runs of this runtime on the host.
            import fcntl
            with (self.output.parent / ".agen3d-gpu.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with (folder / "stdout.log").open("w") as stdout, (folder / "stderr.log").open("w") as stderr:
                    completed = run_process([spec.python, str(worker), str(folder / "request.json")],
                                            cwd=spec.repo, stdout=stdout, stderr=stderr,
                                            timeout=spec.timeout_s,
                                            env={**os.environ, "AGEN3D_MODEL_ROOT": str(model_registry.root),
                                                 "HF_HUB_CACHE": str(model_registry.root / "hub"),
                                                 "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
                    completed.check_returncode()
            result = json.loads((folder / "result.json").read_text())
        finally:
            self.ledger.settle(key, None, {"wall_seconds": time.monotonic() - start,
                                          "note": "GPU monetary cost not measured"})
        generated = []
        artifacts = [(p, "mask") for p in result.get("masks", [])]
        artifacts += [(result[k], kind) for k, kind in [("mesh", "mesh"), ("geometry", "depth")]
                      if k in result]
        for index, (filename, kind) in enumerate(artifacts):
            path = Path(filename).resolve()
            if not path.is_relative_to(folder) or not path.is_file():
                raise ValueError("Specialist returned invalid artifact path")
            ref = f"generated_{key}_{index}"
            self.config.evidence[ref] = Evidence(path=str(path), kind=kind,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), description=f"{name} predicted {kind}")
            self.generated_ids.add(ref)
            generated.append(ref)
        result["evidence_ids"] = generated
        self.service_cache[cache_key] = result
        save(self.output / "generated_evidence.json",
             {ref: self.config.evidence[ref].model_dump() for ref in self.generated_ids})
        return {**result, "cache_hit": False}

    def registry(self):
        r = Registry()
        r.add("read_scene", "Read canonical scene, version and open issues.", ALL_ROLES, Empty,
              lambda a: {"scene_version": self.version, "scene": self.scene.model_dump(mode="json"),
                         "issues": self.issues})
        r.add("read_budget", "Read measured/unknown charges and reservations.", ALL_ROLES,
              Empty, lambda a: self.ledger.summary())
        r.add("get_evidence", "Read registered JSON or attach a registered image next turn.",
              ALL_ROLES, EvidenceArgs, self.get_evidence)
        r.add("summarize_geometry", "Read object box, bounds and uncertainty; no inferred mass.",
              ALL_ROLES, ObjectArgs, self.summarize)
        r.add("check_geometry", "Check declared support gaps and duplicate tracks (box checks only).",
              ALL_ROLES, Empty, lambda a: {"issues": [i.model_dump() for i in Verifier().check(self.scene)]})
        r.add("compare_masks", "Compute source/render binary mask IoU at equal resolution.",
              {"geometry", "critic", "judge"}, CompareMasks, self.compare_masks)
        r.add("propose_transform", "Save bounded object transform proposal; never commits it.",
              {"geometry"}, TransformArgs, self.propose_transform)
        r.add("propose_object", "Save new object hypothesis with observed evidence; not a scene commit.",
              {"inventory"}, ObjectProposalArgs, self.propose_object)
        r.add("fit_support", "Compute a bounded axis-aligned support correction and save proposal.",
              {"geometry"}, SupportFitArgs, self.fit_support)
        r.add("make_primitive", "Write a fitted local box OBJ candidate, not an accepted asset.",
              {"asset"}, ObjectArgs, self.primitive)
        r.add("emit_issue", "Record an evidence-backed issue for review.",
              {"inventory", "geometry", "asset", "critic", "judge", "physics"}, IssueArgs,
              self.emit_issue)
        r.add("search_assets", "Search approved mesh evidence descriptions.", {"asset"}, AssetQuery,
              lambda a: {"matches": [{"id": k, "description": v.description}
                                      for k, v in self.config.evidence.items()
                                      if v.kind == "mesh" and a.query.lower() in v.description.lower()]})
        for name in ("pi3x", "sam3", "sam3d", "hunyuan", "hispatial"):
            if name not in self.config.services:
                continue
            if name == "hispatial" and self.config.variant == "v1":
                continue
            r.add("request_" + name, f"Run configured {name} specialist under GPU/budget lease.",
                  ({"geometry", "critic"} if name == "hispatial" else {"geometry"} if name == "pi3x" else
                   {"inventory"} if name == "sam3" else {"asset"}),
                  Pi3xArgs if name == "pi3x" else SpatialArgs if name == "hispatial" else
                  SegmentArgs if name == "sam3" else GenerateArgs,
                  lambda a, backend=name: self.service(backend, a))
        return r
