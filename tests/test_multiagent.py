import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from agen3d.multiagent.contracts import Decision, Evidence, Task
from agen3d.multiagent.engine import Runner, load_config, validate_plan
from agen3d.multiagent.providers import Reply
from agen3d.multiagent.store import BudgetExceeded, Ledger

ROOT = Path(__file__).resolve().parents[1]


def config(tmp_path, variant="v1"):
    c = load_config(ROOT / "tests/fixtures/multiagent/offline.json")
    c.output = str(tmp_path / "run")
    c.variant = variant
    if variant == "v3":
        c.models["medium"] = c.models["cheap"].model_copy()
    return c


def test_capabilities_and_scope(tmp_path):
    runner = Runner(config(tmp_path))
    task = Task(task_id="critic", role="critic", instruction="inspect", object_ids=["box_01"])
    with pytest.raises(PermissionError):
        runner.registry.dispatch(task, "make_primitive", {"object_id": "box_01"})
    with pytest.raises(PermissionError):
        runner.registry.dispatch(task, "summarize_geometry", {"object_id": "table_01"})
    with pytest.raises(ValueError):
        runner.registry.dispatch(task, "read_scene", {"unexpected": True})
    assert "request_sam3d" not in runner.registry.tools


def test_evidence_hash_and_escape(tmp_path):
    c = config(tmp_path)
    root = tmp_path / "evidence"
    root.mkdir()
    file = root / "note.json"
    file.write_text('{}')
    c.evidence_root = str(root)
    c.evidence["note"] = Evidence(path="note.json", sha256=hashlib.sha256(b'{}').hexdigest(),
                                   kind="json", description="note")
    runner = Runner(c)
    assert runner.context.evidence("note") == file
    file.write_text('{"changed":true}')
    with pytest.raises(ValueError, match="changed"):
        runner.context.evidence("note")
    c.evidence["note"].path = "../outside.json"
    (tmp_path / "outside.json").write_text('{}')
    with pytest.raises(PermissionError):
        runner.context.evidence("note")


def test_budget_concurrency_and_unknown(tmp_path):
    ledger = Ledger(tmp_path / "ledger.sqlite", 1)

    def reserve(_):
        try:
            return ledger.reserve("call", .3, .3)
        except BudgetExceeded:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        keys = [k for k in pool.map(reserve, range(8)) if k]
    assert len(keys) == 2
    ledger.settle(keys[0], None, {"failed": True})
    assert ledger.summary()["accounted_usd"] == pytest.approx(.6)
    with pytest.raises(ValueError):
        ledger.settle(keys[0], 0, {})
    # Actual overages are recorded, not clipped to the reservation.
    ledger.settle(keys[1], .8, {})
    assert ledger.summary()["accounted_usd"] == pytest.approx(1.1)


def test_plan_cycles_and_privilege():
    with pytest.raises(ValueError):
        validate_plan([Task(task_id="a", role="asset", instruction="x", depends_on=["a"])], 5)
    with pytest.raises(ValueError):
        validate_plan([Task(task_id="a", role="judge", instruction="x")], 5)


@pytest.mark.parametrize("variant", ["v1", "v2", "v3"])
def test_offline_run_is_not_claimed_as_reconstruction(tmp_path, variant):
    c = config(tmp_path, variant)
    report = Runner(c).run()
    assert report["status"] == "incomplete"
    assert not report["scene_changed"]
    assert "_judge" in report["results"]
    assert (Path(c.output) / "ledger.sqlite").exists()
    with pytest.raises(FileExistsError):
        Runner(c)


class CascadeProvider:
    def __init__(self):
        self.models = []

    def complete(self, spec, system, packet, images, workdir):
        self.models.append(spec.model)
        return Reply(Decision(status="abstain" if spec.model == "small" else "done",
                              summary="test").model_dump_json(), 0)


def test_v3_escalates_only_after_abstention(tmp_path):
    c = config(tmp_path, "v3")
    c.models["cheap"].model = "small"
    c.models["medium"].model = "medium"
    provider = CascadeProvider()
    runner = Runner(c, provider)
    result = runner.task(Task(task_id="x", role="critic", instruction="inspect"))
    assert result.status == "done"
    assert provider.models == ["small", "medium"]


def test_invalid_protocol_retries_are_bounded_and_charged(tmp_path):
    class BrokenProvider:
        def complete(self, *args):
            return Reply("not JSON", .02)
    runner = Runner(config(tmp_path), BrokenProvider())
    result = runner.task(Task(task_id="x", role="asset", instruction="inspect", max_turns=2))
    assert result.status == "abstain"
    assert runner.ledger.summary()["known_actual_usd"] == pytest.approx(.04)


def test_worker_cannot_delegate(tmp_path):
    class BadWorker:
        def complete(self, *args):
            return Reply(Decision(status="done", summary="delegate", tasks=[
                Task(task_id="evil", role="judge", instruction="override")]).model_dump_json(), 0)
    runner = Runner(config(tmp_path), BadWorker())
    result = runner.task(Task(task_id="x", role="asset", instruction="inspect", max_turns=1))
    assert result.status == "abstain"


def test_transform_is_proposal_only(tmp_path):
    c = config(tmp_path)
    c.evidence_root = str(tmp_path)
    (tmp_path / "e.json").write_text('{}')
    c.evidence["e"] = Evidence(path="e.json", sha256=hashlib.sha256(b'{}').hexdigest(),
                                kind="json", description="e")
    runner = Runner(c)
    before = runner.context.object("box_01").box.model_dump()
    after = {**before, "center": [0, 0, .9]}
    result = runner.registry.dispatch(Task(task_id="x", role="geometry", instruction="fit"),
        "propose_transform", {"object_id":"box_01", "box":after, "reason":"support",
                              "evidence_ids":["e"]})
    assert result["status"] == "unverified_proposal"
    assert runner.context.object("box_01").box.model_dump() == before
