"""Serial, auditable task-DAG execution with bounded model cascades."""
import importlib
import time
from pathlib import Path

from agen3d.schema import SceneState
from agen3d.verification import Verifier

from .contracts import Decision, RunConfig, Task
from .providers import Provider, ProviderHTTPError
from .store import BudgetExceeded, Ledger, save
from .tools import ToolContext
from .resources import resolve_resource, interpreter_path


def validate_plan(tasks, limit):
    """Topologically order a bounded plan without allowing privileged subtasks."""
    if len(tasks) > limit:
        raise ValueError("Plan exceeds task cap")
    ids = [t.task_id for t in tasks]
    if len(set(ids)) != len(ids) or {"_planner", "_critic", "_judge"} & set(ids):
        raise ValueError("Duplicate/reserved task IDs")
    if any(t.role in {"planner", "judge"} for t in tasks):
        raise ValueError("Only runtime can schedule strong leader/judge")
    known, ordered, remaining = set(), [], list(tasks)
    while remaining:
        ready = [t for t in remaining if set(t.depends_on) <= known]
        if not ready:
            raise ValueError("Missing or cyclic task dependencies")
        for task in ready:
            known.add(task.task_id)
            ordered.append(task)
            remaining.remove(task)
    return ordered


class Runner:
    def __init__(self, config: RunConfig, provider=None):
        self.config = config
        self.output = Path(config.output).resolve()
        # Existing output means possible billed work; never silently replay it.
        self.output.mkdir(parents=True, exist_ok=False)
        self.ledger = Ledger(self.output / "ledger.sqlite", config.budget_usd)
        scene = SceneState.model_validate_json(Path(config.scene).read_text())
        self.context = ToolContext(config, scene, self.output, self.ledger)
        self.registry = self.context.registry()
        self.provider = provider or Provider()
        package = {"v1": "v1_shared", "v2": "v2_specialists", "v3": "v3_adaptive"}[config.variant]
        self.policy = importlib.import_module(f"agen3d.multiagent.{package}")
        self.results = {}
        self.escalations = 0
        save(self.output / "config.json", config.model_dump(mode="json"))
        save(self.output / "scene.input.json", scene.model_dump(mode="json"))

    def task(self, task):
        """Execute one role-scoped task; every retry/tier incurs its own reservation.

        A transport error can occur after billing, so there is no automatic HTTP
        retry or free refund. Strong escalation changes model, not role privileges.
        """
        self.context.requested_images = []
        for ref in task.evidence_ids:
            path = self.context.evidence(ref)
            if self.config.evidence[ref].kind in {"image", "mask"}:
                self.context.requested_images.append(path)
        history = []
        aliases = self.policy.candidates(task.role, self.config.models)
        last = Decision(status="abstain", summary="Task did not complete")
        for tier, alias in enumerate(aliases):
            if alias == "planner" and task.role not in {"planner", "judge"}:
                if self.escalations >= self.config.max_strong_escalations:
                    break
                self.escalations += 1
            spec = self.config.models[alias]
            for turn in range(task.max_turns):
                label = f"{task.task_id}/{tier}/{turn}/{alias}"
                holdback = 0 if task.role == "judge" else self.config.judge_reserve_usd
                try:
                    reservation = self.ledger.reserve(label, spec.call_reservation_usd, holdback)
                except BudgetExceeded as exc:
                    last = Decision(status="abstain", summary=str(exc))
                    break
                packet = {"task": task.model_dump(mode="json"),
                          "scene_version": self.context.version,
                          "evidence_catalog": {k: {"kind": v.kind, "description": v.description}
                                               for k, v in self.config.evidence.items()},
                          "scene": self.context.scene.model_dump(mode="json"),
                          "completed_tasks": self.results, "history": history,
                          "image_evidence_order": [next(k for k, v in self.config.evidence.items()
                                                         if (self.context.root / v.path).resolve() == p)
                                                   for p in self.context.requested_images],
                          "open_numeric_issues": [i.model_dump() for i in Verifier().check(self.context.scene)],
                          "open_semantic_issues": self.context.issues,
                          "unapplied_proposals": self.context.proposals + self.context.object_proposals}
                self.ledger.event("call_started", {"task": task.task_id, "alias": alias,
                                                    "reservation": reservation})
                start = time.monotonic()
                reply = None
                try:
                    reply = self.provider.complete(spec, self.registry.prompt(task.role), packet,
                                                   list(self.context.requested_images), self.output)
                except Exception as exc:
                    detail = str(exc) if isinstance(exc, ProviderHTTPError) else type(exc).__name__
                    self.ledger.event("provider_failed", {"task": task.task_id,
                        "error_type": type(exc).__name__, "error": detail})
                    last = Decision(status="abstain", summary=f"Provider failed: {detail}")
                    # Transport failures may be charged: reservation remains accounted.
                    break
                finally:
                    self.ledger.settle(reservation, reply.actual_usd if reply else None,
                                       {"wall_seconds": time.monotonic() - start,
                                        "usage": reply.usage if reply else {}, "alias": alias})
                save(self.output / "responses" / f"{reservation}.json",
                     {"text": reply.text, "usage": reply.usage, "alias": alias})
                try:
                    decision = Decision.model_validate_json(reply.text)
                    if decision.tasks and task.role != "planner":
                        raise ValueError("Workers cannot create tasks")
                    if not set(decision.evidence_used) <= self.config.evidence.keys():
                        raise ValueError("Decision cites unknown evidence")
                except ValueError as exc:
                    history.append({"protocol_error": str(exc)[:1200]})
                    last = Decision(status="abstain", summary="Invalid structured model decision")
                    continue
                last = decision
                if decision.status != "tool":
                    break
                outputs = []
                for call in decision.calls:
                    try:
                        result = self.registry.dispatch(task, call.name, call.arguments)
                        outputs.append({"name": call.name, "result": result})
                    except Exception as exc:
                        outputs.append({"name": call.name, "error": str(exc)[:1200]})
                    self.ledger.event("tool_result", {"task": task.task_id, **outputs[-1]})
                history.append({"decision": decision.model_dump(mode="json"), "tools": outputs})
            if last.status not in {"abstain", "tool"}:
                break
            if tier + 1 < len(aliases):
                self.ledger.event("escalation", {"task": task.task_id, "from": alias,
                                                 "to": aliases[tier + 1]})
        if last.status == "tool":
            last = Decision(status="abstain", summary="Turn budget exhausted before final answer")
        self.results[task.task_id] = last.model_dump(mode="json")
        save(self.output / "tasks" / f"{task.task_id}.json", self.results[task.task_id])
        return last

    def run(self):
        """Execute planning/work/review, preserving incomplete outcomes in the report."""
        status, failure = "incomplete", None
        try:
            plan = self.task(Task(task_id="_planner", role="planner", instruction=self.config.source))
            tasks = validate_plan(self.config.tasks or plan.tasks, self.config.max_tasks)
            for task in tasks:
                failed_dependencies = [dep for dep in task.depends_on
                                       if self.results[dep]["status"] not in {"done", "pass"}]
                if failed_dependencies:
                    self.results[task.task_id] = Decision(
                        status="abstain", summary=f"Unresolved dependencies: {failed_dependencies}").model_dump()
                    continue
                self.task(task)
            self.task(Task(task_id="_critic", role="critic", max_turns=3,
                           instruction="Inspect current scene and source evidence; enumerate defects. "
                                       "Proposals are not applied. Do not judge them as completed repairs."))
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"
            self.ledger.event("run_failed", {"error": failure})
        # Judge is attempted even when a worker/plan failed; its reserve was protected.
        try:
            judge = self.task(Task(task_id="_judge", role="judge", max_turns=3,
                                  instruction="Final independent review. Inspect actual source/render "
                                              "evidence. Report unresolved work and unapplied proposals. "
                                              "A run with failures cannot be accepted."))
            unresolved = any(r["status"] not in {"done", "pass"}
                             for name, r in self.results.items() if name != "_judge")
            if (judge.status == "pass" and not failure and not unresolved
                    and not self.context.proposals and not self.context.object_proposals):
                status = "review_passed_unvalidated"
        except Exception as exc:
            failure = failure or f"Judge failed: {type(exc).__name__}"
        # Current bridge is proposals-only; never certify a reconstructed Blender scene.
        report = {"status": status, "variant": self.config.variant, "error": failure,
                  "scene_changed": False,
                  "unapplied_proposals": len(self.context.proposals) + len(self.context.object_proposals),
                  "limitations": ["No automatic Blender commit/source-render acceptance bridge",
                                  "CLI model charges may be unknown; reservations are estimates",
                                  "Task capability checks are not OS filesystem isolation"],
                  "results": self.results, "cost": self.ledger.summary()}
        save(self.output / "report.json", report)
        return report


def load_config(path):
    path = Path(path).resolve()
    config = RunConfig.model_validate_json(path.read_text())
    for name in ("scene", "evidence_root", "output"):
        setattr(config, name, str((path.parent / getattr(config, name)).resolve()))
    for service in config.services.values():
        service.python = resolve_resource(service.python, "runtimes") or interpreter_path(path.parent, service.python)
        service.repo = resolve_resource(service.repo, "repos") or str((path.parent / service.repo).resolve())
        if service.checkpoint and service.checkpoint.startswith("."):
            service.checkpoint = str((path.parent / service.checkpoint).resolve())
    return config
