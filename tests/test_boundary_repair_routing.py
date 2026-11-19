import pytest

from agen3d.datasets import ReconstructionContext
from agen3d.io import write_new
from agen3d.routing import CostTracker, Usage, route
from agen3d.schema import Box, Frame, InputManifest, ObjectState, SceneState
from agen3d.verification import Verifier, repair


def test_reader_rejects_gt_and_symlink_escape(tmp_path):
    root = tmp_path / "rgb_only"
    root.mkdir()
    secret = tmp_path / "labels.png"
    secret.write_bytes(b"privileged")
    (root / "escape.png").symlink_to(secret)
    manifest = InputManifest(dataset="ai2thor", dataset_version="synthetic", scene_id="s",
                             split="val", frames=[Frame(frame_id="0", timestamp_s=0,
                             path="escape.png", sha256="wrong")])
    path = root / "manifest.json"
    write_new(path, manifest)
    ctx = ReconstructionContext(path)
    with pytest.raises(PermissionError):
        ctx.read_frame("../labels.png")
    with pytest.raises(PermissionError):
        ctx.read_frame("0")
    assert len(ctx.denied) == 2


def support_scene(gap):
    return SceneState(scene_id="s", alignment_id="predicted", objects=[
        ObjectState(object_id="table", box=Box(center=(0, 0, .5), extent=(2, 2, 1))),
        ObjectState(object_id="cup", support_id="table",
                    box=Box(center=(0, 0, 1.1 + gap), extent=(.2, .2, .2)))])


def test_repair_is_bounded_and_preserves_original():
    original = support_scene(.05)
    fixed, trace, remaining = repair(original, Verifier())
    assert len(trace) == 1 and trace[0]["accepted"]
    assert not remaining
    assert original.objects[1].box.center[2] == pytest.approx(1.15)
    assert fixed.objects[1].box.center[2] == pytest.approx(1.1)
    _, trace, remaining = repair(support_scene(.2), Verifier())
    assert trace == [] and remaining


def test_rollback_when_new_issue_cancels_improvement():
    class RejectingVerifier:
        def check(self, state):
            # Stable issue count forces rejection of the proposed change.
            return Verifier().check(support_scene(.05))
    original = support_scene(.05)
    fixed, trace, _ = repair(original, RejectingVerifier())
    assert not trace[0]["accepted"]
    assert fixed == original


def test_cost_limits_include_retries():
    tracker = CostTracker(1)
    assert route(.2, 2, tracker, .1, .8) == "strong"
    tracker.record(Usage("retry", "open", 10, 20, 2, 3, .3, "2026-11-15", True))
    assert route(.2, 2, tracker, .1, .8) == "stop"
    assert route(.6, 0, tracker, .1, .8) == "open"
    assert route(.9, 0, tracker, .1, .8) == "deterministic"
    with pytest.raises(ValueError):
        CostTracker(float("nan"))
