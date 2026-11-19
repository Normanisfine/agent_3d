import hashlib
import json

import pytest

from agen3d.multiagent.models import ModelRegistry
from agen3d.multiagent.resources import resolve_resource


def registry(tmp_path):
    lock = tmp_path / "models.lock.json"
    lock.write_text(json.dumps({"models": {"tiny": {"repo_id": "test/tiny",
        "revision": "a" * 40, "entrypoint": "weights.bin",
        "files": {"weights.bin": {"size": 4, "sha256": hashlib.sha256(b"data").hexdigest()},
                  "config.json": {"size": 2, "git_blob_sha1": hashlib.sha1(b"blob 2\0{}").hexdigest()}}}}}))
    return ModelRegistry(tmp_path / "models", lock)


def test_import_resolve_and_tampering(tmp_path):
    r = registry(tmp_path)
    source = tmp_path / "original"
    source.mkdir()
    (source / "weights.bin").write_bytes(b"data")
    (source / "config.json").write_bytes(b"{}")
    assert r.import_local("tiny", source)["ok"]
    weights = r.resolve("model:tiny")
    assert weights.read_bytes() == b"data"
    weights.write_bytes(b"evil")
    assert not r.verify("tiny")["ok"]
    assert (source / "weights.bin").read_bytes() == b"data"
    with pytest.raises(FileNotFoundError):
        r.resolve("model:tiny")


def test_missing_and_traversal(tmp_path):
    r = registry(tmp_path)
    assert not r.verify("tiny")["ok"]
    with pytest.raises(ValueError):
        r.file("tiny", "../../escape")
    with pytest.raises(ValueError):
        r.resolve("latest")


def test_shared_resource_registry(tmp_path, monkeypatch):
    original = registry(tmp_path)
    shared = tmp_path / "resources.json"
    shared.write_text(json.dumps({"schema_version": 1, "model_root": "shared-models",
                                  "model_lock": original.lock_path.name,
                                  "repos": {"sam3": "external/sam3"},
                                  "runtimes": {"sam3": "envs/sam3/bin/python"}}))
    monkeypatch.setenv("AGEN3D_RESOURCES", str(shared))
    monkeypatch.delenv("AGEN3D_MODEL_ROOT", raising=False)
    monkeypatch.delenv("AGEN3D_MODEL_LOCK", raising=False)
    assert ModelRegistry().root == tmp_path / "shared-models"
    assert resolve_resource("repo:sam3", "repos") == str(tmp_path / "external/sam3")
    assert resolve_resource("runtime:sam3", "runtimes") == str(tmp_path / "envs/sam3/bin/python")
    with pytest.raises(ValueError):
        resolve_resource("runtime:missing", "runtimes")
