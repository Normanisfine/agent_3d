"""Clone pinned external source without changing an existing checkout."""
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", *map(str, args)], text=True).strip()


def main():
    spec = json.loads((ROOT / "external.lock.json").read_text())["aha-3d"]
    repo = ROOT / "external" / "aha-3d"
    if not repo.exists():
        repo.parent.mkdir(parents=True, exist_ok=True)
        git("clone", spec["url"], repo)
        git("-C", repo, "checkout", "--detach", spec["commit"])
    if not (repo / ".git").exists():
        raise SystemExit(f"Not an independent Git checkout: {repo}")
    revision = git("-C", repo, "rev-parse", "HEAD")
    if revision != spec["commit"]:
        raise SystemExit(f"{repo}: expected {spec['commit']}, found {revision}. "
                         "Review and update the checkout explicitly; no files changed.")
    if git("-C", repo, "status", "--porcelain", "--untracked-files=normal"):
        raise SystemExit(f"{repo}: local changes found; preserve or resolve them before use.")
    print(f"Ready: {repo} @ {revision}")


if __name__ == "__main__":
    main()
