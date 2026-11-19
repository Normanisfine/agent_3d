"""按开发场景上 A1 的实测写 configs/run_caps.json（设计文档第 5 节：上限 = 中位数的 2 倍）。

用法：PYTHONPATH=src .runtime/venv/bin/python scripts/make_run_caps.py [--force]
墙钟取 run_log.json 的 wall_s；"轮数"取 events.jsonl 里完成的命令执行次数（codex exec 整次只有一个 turn）。
"""
import argparse
import json
import statistics
from datetime import date
from pathlib import Path

from smallobj import runlog

PROJ = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    out = PROJ / "configs" / "run_caps.json"
    if out.exists() and not args.force:
        raise SystemExit(f"{out} 已存在；上限一旦定下就冻结，确实要改用 --force")
    dev = json.loads((PROJ / "configs" / "splits.json").read_text())["dev"]
    runs = [r for r in sorted((PROJ / "runs" / "A1").glob("*/*")) if r.parent.name in dev and (r / "run_log.json").exists()]
    walls = [json.loads((r / "run_log.json").read_text())["wall_s"] for r in runs]
    calls = [runlog.parse_codex_events(r / "events.jsonl")["tool_calls"] for r in runs]
    caps = {"wall_s": int(round(2 * statistics.median(walls))),
            "tool_calls": int(2 * statistics.median(calls)),
            "basis": {"runs": [f"A1/{r.parent.name}/{r.name}" for r in runs],
                      "wall_s": [round(w) for w in walls], "tool_calls": calls,
                      "rule": "2 x median of dev A1 (design §5)", "date": date.today().isoformat()}}
    out.write_text(json.dumps(caps, indent=1) + "\n")
    print(json.dumps(caps, indent=1))


if __name__ == "__main__":
    main()
