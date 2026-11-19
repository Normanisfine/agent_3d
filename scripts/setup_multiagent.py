"""Reproducible core/source setup. Specialist GPU dependencies stay isolated.

Run from any directory with Python 3.11+. No credentials/checkpoints are downloaded.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(argv, **kwargs):
    return subprocess.run(list(map(str, argv)), check=True, **kwargs)


def sources():
    specs = json.loads((ROOT / "multiagent.external.lock.json").read_text())
    for name, spec in specs.items():
        target = ROOT / "external" / name
        if not target.exists():
            run(["git", "clone", "--no-checkout", "--filter=blob:none", spec["url"], target])
            run(["git", "-C", target, "checkout", "--detach", spec["commit"]])
        revision = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
        if revision != spec["commit"]:
            raise RuntimeError(f"Preserving existing {name}: revision differs from lock")
        print(f"Verified {name} @ {revision}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", action="store_true")
    parser.add_argument("--core", action="store_true")
    parser.add_argument("--reference", action="store_true",
                        help="Install AHA reference meshing dependencies in the core environment")
    parser.add_argument("--runtime", choices=["sam3", "pi3x", "hunyuan"],
                        help="Create a clean isolated GPU environment from its captured package lock")
    args = parser.parse_args()
    if args.core:
        if sys.version_info < (3, 11):
            raise RuntimeError("Use Python >=3.11 for the orchestrator")
        env = ROOT / ".venv"
        if not env.exists():
            run([sys.executable, "-m", "venv", env])
        run(["uv", "pip", "install", "--python", env / "bin/python", "-e", f"{ROOT}[dev]"],
            env={**os.environ, "UV_CACHE_DIR": str(ROOT / ".cache/uv")})
    if args.sources:
        sources()
    if args.reference:
        run(["uv", "pip", "install", "--python", ROOT / ".venv/bin/python",
             "-e", f"{ROOT}[reference]"],
            env={**os.environ, "UV_CACHE_DIR": str(ROOT / ".cache/uv")})
    if args.runtime:
        env = ROOT / ".venvs" / ("hunyuan" if args.runtime == "hunyuan" else args.runtime + "-clean")
        settings = {**os.environ, "UV_CACHE_DIR": str(ROOT / ".cache/uv"),
                    "UV_PYTHON_INSTALL_DIR": str(ROOT / ".python")}
        if not env.exists():
            run(["uv", "venv", "--python", "3.11", env], env=settings)
        # Both declared indexes are trusted: PyTorch mirrors only some PyPI versions.
        run(["uv", "pip", "install", "--python", env / "bin/python",
             "--index-strategy", "unsafe-best-match", "-r",
             ROOT / "runtime-locks" / (args.runtime + ".txt")], env=settings)
        print(f"Created clean runtime: {env}; point services.{args.runtime}.python here.")
    if not (args.core or args.sources or args.runtime or args.reference):
        parser.print_help()


if __name__ == "__main__":
    main()
