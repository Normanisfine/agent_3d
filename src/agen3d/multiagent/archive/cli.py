"""agen3d-multi: inspect protocol, diagnose setup, execute bounded runs."""
import argparse
import json
import os
import shutil
from pathlib import Path

from agen3d.schema import SceneState

from .engine import Runner, load_config, validate_plan
from .tools import ALL_ROLES, ToolContext
from agen3d.multiagent.models import ModelRegistry


def doctor(config):
    checks = []
    for alias, model in config.models.items():
        if model.backend in {"codex", "claude"}:
            checks.append({"component": alias, "backend": model.backend,
                           "executable": shutil.which(model.backend),
                           "authentication": "not probed (no model call)"})
        elif model.backend != "mock":
            checks.append({"component": alias, "backend": model.backend,
                           "key_present": bool(os.environ.get(model.api_key_env)),
                           "model": model.model, "provider": model.provider})
    for name, service in config.services.items():
        checkpoint = None
        if service.checkpoint and service.checkpoint.startswith("model:"):
            checkpoint = ModelRegistry().verify(service.checkpoint.split(":", 1)[1], full=False)
        checks.append({"component": name, "python_exists": Path(service.python).is_file(),
                       "repo_exists": Path(service.repo).is_dir(),
                       "checkpoint": service.checkpoint, "checkpoint_state": checkpoint,
                       "checkpoint_ready": bool(checkpoint and checkpoint["ok"]),
                       "gpu_inference": "not tested by doctor"})
    if config.scene is not None:
        checks += [{"component": "scene", "valid": bool(SceneState.model_validate_json(
            Path(config.scene).read_text()))}]
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "doctor", "protocol"])
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    validate_plan(config.tasks, config.max_tasks)
    if args.command == "doctor":
        result = doctor(config)
    elif args.command == "protocol":
        context = ToolContext(config, SceneState.model_validate_json(Path(config.scene).read_text()),
                              Path(config.output), None)
        registry = context.registry()
        result = {role: registry.catalog(role) for role in sorted(ALL_ROLES)}
    else:
        # Validate inputs before creating run output or consuming budget.
        checks = doctor(config)
        missing = [c["component"] for c in checks
                   if c.get("key_present") is False or
                   ("executable" in c and not c["executable"]) or
                   c.get("python_exists") is False or c.get("repo_exists") is False or
                   c.get("checkpoint_ready") is False]
        if missing:
            raise SystemExit("Setup incomplete for: " + ", ".join(missing) +
                             ". Run doctor; no model calls made.")
        context = ToolContext(config, SceneState.model_validate_json(Path(config.scene).read_text()),
                              Path(config.output), None)
        for ref in config.evidence:
            context.evidence(ref)
        result = Runner(config).run()
    print(json.dumps(result, indent=2))
    if args.command == "run" and result["error"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
