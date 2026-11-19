import json
import sys

from smallobj import cli, gen3d

from test_gen3d import FAKE, scene  # noqa: F401  复用假场景和假后端


def test_cli_job_file_schema(scene, capsys):  # noqa: F811
    root, calls = scene
    cli.main(["gen3d-request", "--scene", "S", "--items", "big,tiny", "--backend", "fake", "--root", str(root), "--sync"])
    job_id = capsys.readouterr().out.strip().splitlines()[-1]
    job = json.loads((root / "gen" / "S" / "jobs" / f"{job_id}.json").read_text())
    assert job["status"] == "done" and job["items"] == ["big", "tiny"]
    assert [r["status"] for r in job["results"]] == ["ok", "ok", "too_small"]  # big 两个候选，tiny 太小
    cli.main(["gen3d-status", job_id, "--scene", "S", "--root", str(root)])
    assert json.loads(capsys.readouterr().out)["status"] == "done"
