"""Raw-input selection and full-cost regression checks, without paid inference."""
import shutil
import subprocess

import pytest
from PIL import Image

from agen3d.multiagent.pipeline.accounting import complete_costs
from agen3d.multiagent.pipeline.inputs import prepare
from agen3d.multiagent.pipeline.config import PipelineConfig
from agen3d.multiagent.pipeline.runner import Pipeline


def images(folder):
    folder.mkdir()
    for i in range(8):
        Image.new("RGB", (32, 32), (i * 25, 0, 0)).save(folder / f"{i:06d}.png")


def test_rgb_selection(tmp_path):
    source = tmp_path / "source"
    images(source)
    manifest = prepare(source, tmp_path / "out", 4, "room")
    assert [f.frame_id for f in manifest.frames] == ["000000", "000002", "000005", "000007"]
    assert len({f.sha256 for f in manifest.frames}) == 4
    assert manifest.dataset == "generic"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg unavailable")
def test_video_selection(tmp_path):
    source = tmp_path / "source"
    images(source)
    video = tmp_path / "room.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-framerate", "4", "-i",
                    str(source / "%06d.png"), "-pix_fmt", "yuv420p", str(video)], check=True)
    manifest = prepare(video, tmp_path / "out", 4, "room")
    assert [f.frame_id for f in manifest.frames] == ["000000", "000002", "000005", "000007"]
    assert manifest.frames[-1].timestamp_s == 1.75


def test_preprocessing_cost_even_without_agent():
    known = complete_costs(None, {"wall_seconds": 3600}, 0, 0, 2)
    assert known["total_actual_usd"] == 2
    unknown = complete_costs(None, {"wall_seconds": 3600}, 0, 0, None)
    assert unknown["total_actual_usd"] is None
    assert unknown["unknown_cost_items"] == 1


@pytest.mark.parametrize("variant", ["v1", "v2", "v3"])
def test_failed_preprocessing_is_reported(tmp_path, variant):
    source = tmp_path / "empty"
    source.mkdir()
    config = PipelineConfig(variant=variant, input=str(source), output=str(tmp_path / "run"),
        scene_id="room", aha_repo="unused", blender="unused", frames=4, segmentation_views=2,
        models={key: {"backend": "mock"} for key in ("planner", "judge", "cheap")},
        services={key: {"python": "unused", "repo": "unused", "checkpoint": f"model:{key}", "reservation_usd": .1}
                  for key in ("pi3x", "sam3")})
    report = Pipeline(config).run()
    assert report["status"] == "failed"
    assert report["timing"]["stages"][0]["status"] == "failed"
    assert report["timing"]["wall_seconds"] > 0
    assert report["cost"]["total_actual_usd"] is None


def test_runtime_paths_preserve_virtualenv_symlink(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from agen3d.multiagent.pipeline.config import load
    from agen3d.multiagent.resources import resolve_resource
    from agen3d.multiagent.engine import load_config

    root = Path(__file__).resolve().parents[1]
    executable = tmp_path / "base-python"
    executable.touch()
    venv = tmp_path / "venv/bin/python"
    venv.parent.mkdir(parents=True)
    venv.symlink_to(executable)
    registry = tmp_path / "resources.json"
    registry.write_text(json.dumps({"schema_version": 1, "runtimes": {"test": "venv/bin/python"}}))
    monkeypatch.setenv("AGEN3D_RESOURCES", str(registry))
    assert resolve_resource("runtime:test", "runtimes") == str(venv)
    for loader, template in (
        (load, root / "configs/multiagent/example.json"),
        (load_config, root / "tests/fixtures/multiagent/offline.json"),
    ):
        config = json.loads(template.read_text())
        config["services"] = {"pi3x": {"python": "venv/bin/python", "repo": ".",
            "checkpoint": "model:pi3x", "reservation_usd": .1},
            "sam3": {"python": "runtime:test", "repo": ".",
            "checkpoint": "model:sam3", "reservation_usd": .1}}
        path = tmp_path / "config.json"
        path.write_text(json.dumps(config))
        loaded = loader(path)
        assert loaded.services["pi3x"].python == str(venv)
        assert loaded.services["sam3"].python == str(venv)


def test_pipeline_stops_on_provider_failure():
    from types import SimpleNamespace
    from agen3d.multiagent.contracts import Decision

    pipeline = Pipeline.__new__(Pipeline)
    pipeline.agent = SimpleNamespace(task=lambda task: Decision(
        status="abstain", summary="Provider failed: HTTP 429: Provider returned error"))
    with pytest.raises(RuntimeError, match="inventory_000: Provider failed: HTTP 429"):
        pipeline.ask("inventory_000", "inventory", "Inspect images")
