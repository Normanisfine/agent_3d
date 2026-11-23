"""Read-only command construction for existing AHa-3D; never executes subprocesses."""
from pathlib import Path
import shlex


DEFAULT_AHA_REPO = Path(__file__).resolve().parents[3] / "external" / "aha-3d"


def reference_command(repo: Path, video: Path, output: Path, python: Path,
                      checkpoint: Path, mesh_python: Path, frames=32):
    if frames not in (32, 64):
        raise ValueError("AHa reference tier must be 32 or 64 frames")
    if not (repo / "tools/layout_inspection/build_reference.py").is_file():
        raise FileNotFoundError(
            f"AHa reference builder not found in {repo}. "
            "Run python scripts/setup_external.py or pass --repo."
        )
    if output.exists():
        raise FileExistsError("Reference output must be new")
    argv = [str(python.resolve()), "-m", "tools.layout_inspection.build_reference",
            "--video", str(video.resolve()), "--checkpoint", str(checkpoint.resolve()),
            "--mesh-python", str(mesh_python.resolve()), "--num-frames", str(frames),
            "--out", str(output.resolve())]
    return {"cwd": str(repo.resolve()), "argv": argv, "display": shlex.join(argv),
            "status": "planned_only", "scope": "geometry reference, not authored scene"}
