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
