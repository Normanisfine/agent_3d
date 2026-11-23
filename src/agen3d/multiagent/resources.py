"""Read an operator-owned shared resource registry; never move shared resources.

AGEN3D_RESOURCES can point outside this repository. Paths in that JSON file are
relative to the file itself, so every consumer resolves the same installation.
"""
import json
import os
from pathlib import Path


def resource_settings():
    filename = os.environ.get("AGEN3D_RESOURCES")
    if not filename:
        return {}, None
    path = Path(filename).expanduser().resolve()
    data = json.loads(path.read_text())
    if data.get("schema_version") != 1:
        raise ValueError("Shared resource registry requires schema_version=1")
    return data, path.parent


def setting_path(name):
    data, base = resource_settings()
    if name not in data:
        return None
    return (base / data[name]).resolve()


def interpreter_path(base, value):
    """Preserve virtualenv executable symlinks so Python discovers pyvenv.cfg."""
    return os.path.abspath(Path(base) / value)


def resolve_resource(reference, kind):
    prefix = {"repos": "repo:", "runtimes": "runtime:"}[kind]
    if not reference.startswith(prefix):
        return None
    alias = reference[len(prefix):]
    data, base = resource_settings()
    if base is None or alias not in data.get(kind, {}):
        raise ValueError(f"Missing {reference} in AGEN3D_RESOURCES registry")
    if kind == "runtimes":
        return interpreter_path(base, data[kind][alias])
    return str((base / data[kind][alias]).resolve())


def load_env(path):
    """Load literal KEY=value entries without executing shell code or overwriting exports."""
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.removeprefix("export ").partition("=")
        key = key.strip()
        if separator and (key == "OPENROUTER_API_KEY" or key.startswith("AGEN3D_")):
            os.environ.setdefault(key, value.strip().strip('"\''))


class Checkpoints:
    def __init__(self, root=None, lock=None):
        project = Path(__file__).resolve().parents[3]
        self.root = Path(root or os.environ.get("AGEN3D_MODEL_ROOT") or
                         setting_path("model_root") or project / "models").resolve()
        self.lock_path = Path(lock or os.environ.get("AGEN3D_MODEL_LOCK") or
                              setting_path("model_lock") or project / "models.lock.json")
        self.specs = json.loads(self.lock_path.read_text())["models"]

    def directory(self, name):
        if name not in self.specs or Path(name).name != name:
            raise ValueError(f"Unknown model alias {name}")
        return self.root / name

    def file(self, name, relative):
        directory = self.directory(name)
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Checkpoint file escapes model directory")
        return path

    def entrypoint(self, reference):
        prefix, separator, name = reference.partition(":")
        if prefix != "model" or not separator:
            raise ValueError(f"Expected model:alias, got {reference}")
        return self.file(name, self.specs[name]["entrypoint"])
