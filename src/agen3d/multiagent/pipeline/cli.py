"""Measured raw RGB/video reconstruction, shared by V1/V2/V3."""
import argparse
import json
import os
import shutil
from pathlib import Path

from ..cli import doctor as agent_doctor
from .config import load, load_env


def doctor(config):
    # Reuse provider/service checks without requiring an exported input scene.
    from types import SimpleNamespace
    checks = agent_doctor(SimpleNamespace(models=config.models, services=config.services, scene=None))
    checks += [
        {"component": "raw_input", "ok": Path(config.input).exists()},
        {"component": "fresh_output", "ok": not Path(config.output).exists()},
        {"component": "blender", "ok": os.access(config.blender, os.X_OK)},
        {"component": "asset_catalog", "ok": (Path(config.aha_repo) / "assets/index.json").is_file()},
    ]
    if Path(config.input).is_file():
        checks.extend({"component": name, "ok": bool(shutil.which(name))} for name in ("ffmpeg", "ffprobe"))
    if config.evaluation_dataset:
        checks.append({"component": "evaluation_dataset", "ok": Path(config.evaluation_dataset).is_dir()})
    missing = [c["component"] for c in checks if c.get("ok") is False or
               c.get("key_present") is False or ("executable" in c and not c["executable"]) or
               c.get("python_exists") is False or c.get("repo_exists") is False or
               c.get("checkpoint_ready") is False]
    return {"ready": not missing, "missing": missing, "checks": checks,
            "note": "Readiness checks only; no model calls or CUDA inference performed."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["doctor", "run"])
    parser.add_argument("config", type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--input", type=Path, help="Override with a room video or RGB folder")
    parser.add_argument("--output", type=Path, help="New run directory")
    args = parser.parse_args()
    if args.env_file:
        load_env(args.env_file)
    config = load(args.config)
    for name in ("input", "output"):
        if getattr(args, name):
            setattr(config, name, str(getattr(args, name).resolve()))
    if args.input:
        # An arbitrary new room must never be scored against the example room labels.
        config.evaluation_dataset = None
        config.dataset_kind = "generic"
        config.scene_id = args.input.stem
    result = doctor(config)
    if args.command == "run" and result["ready"]:
        from .runner import Pipeline
        result = Pipeline(config).run()
    print(json.dumps(result, indent=2))
    if result.get("ready") is False or result.get("error"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
