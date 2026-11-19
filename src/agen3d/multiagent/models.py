"""One versioned checkpoint registry for every agent, service and external repo."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

from .store import save
from .resources import setting_path

PROJECT = Path(__file__).resolve().parents[3]


class ModelRegistry:
    def __init__(self, root=None, lock=None):
        self.root = Path(root or os.environ.get("AGEN3D_MODEL_ROOT") or
                         setting_path("model_root") or PROJECT / "models").resolve()
        self.lock_path = Path(lock or os.environ.get("AGEN3D_MODEL_LOCK") or
                              setting_path("model_lock") or PROJECT / "models.lock.json")
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

    def verify(self, name, full=True):
        spec = self.specs[name]
        failures = []
        for filename, meta in spec["files"].items():
            path = self.file(name, filename)
            if not path.is_file():
                failures.append({"file": filename, "problem": "missing"})
                continue
            size = path.stat().st_size
            if size != meta["size"]:
                failures.append({"file": filename, "problem": "size_mismatch"})
                continue
            if full:
                digest = hashlib.sha256() if meta.get("sha256") else hashlib.sha1()
                if not meta.get("sha256"):
                    digest.update(f"blob {size}\0".encode())
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                        digest.update(chunk)
                expected = meta.get("sha256") or meta["git_blob_sha1"]
                if digest.hexdigest() != expected:
                    failures.append({"file": filename, "problem": "hash_mismatch"})
        return {"model": name, "revision": spec["revision"], "root": str(self.directory(name)),
                "ok": not failures, "verification": "hashes" if full else "sizes_only",
                "failures": failures}

    def resolve(self, reference, full=True):
        if not reference.startswith("model:"):
            raise ValueError("Use a model:alias reference for reproducible checkpoints")
        name = reference.split(":", 1)[1]
        result = self.verify(name, full=full)
        if not result["ok"]:
            raise FileNotFoundError(f"Checkpoint {name} incomplete/corrupt; run agen3d-models verify {name}")
        return self.file(name, self.specs[name]["entrypoint"])

    def record(self, name, source):
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "manifest.json"
        # Operator-facing inventory; lockfile remains authoritative.
        manifest = json.loads(path.read_text()) if path.exists() else {"models": {}}
        manifest["models"][name] = {"source": source, "verification": self.verify(name),
                                    "lock_sha256": hashlib.sha256(self.lock_path.read_bytes()).hexdigest()}
        save(path, manifest)

    def fetch(self, name):
        from huggingface_hub import hf_hub_download
        spec = self.specs[name]
        for filename in spec["files"]:
            hf_hub_download(repo_id=spec["repo_id"], revision=spec["revision"], filename=filename,
                            local_dir=self.directory(name))
        result = self.verify(name)
        if not result["ok"]:
            raise ValueError(f"Downloaded files failed verification: {result['failures']}")
        self.record(name, "huggingface_pinned")
        return result

    def import_local(self, name, source):
        source = Path(source).resolve()
        for filename in self.specs[name]["files"]:
            src, dest = source / filename, self.file(name, filename)
            if not src.is_file():
                raise FileNotFoundError(src)
            if dest.exists():
                # Existing files are verified below, never silently replaced.
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            temporary = dest.with_name(dest.name + ".importing")
            shutil.copyfile(src, temporary)
            temporary.replace(dest)
        result = self.verify(name)
        if not result["ok"]:
            raise ValueError(f"Imported files differ from pinned release: {result['failures']}")
        self.record(name, str(source))
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["list", "verify", "fetch", "import", "path"])
    parser.add_argument("name", nargs="?")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--lock", type=Path)
    args = parser.parse_args()
    registry = ModelRegistry(args.root, args.lock)
    if args.action == "list":
        result = [registry.verify(name, full=False) for name in registry.specs]
    elif args.name not in registry.specs:
        parser.error("Specify a model alias from list")
    elif args.action == "fetch":
        result = registry.fetch(args.name)
    elif args.action == "import":
        if not args.source:
            parser.error("import needs --source DIRECTORY")
        result = registry.import_local(args.name, args.source)
    elif args.action == "path":
        print(registry.resolve("model:" + args.name))
        return
    else:
        result = registry.verify(args.name)
    print(json.dumps(result, indent=2))
    if isinstance(result, dict) and result.get("ok") is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
