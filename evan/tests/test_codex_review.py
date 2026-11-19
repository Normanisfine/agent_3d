"""scripts/codex_review.sh：AHa-3D 内部审查调的 codex 包装。用一个假 codex 测：固定模型和推理强度、额度用完换账户重试。"""
import json
import os
import subprocess
from pathlib import Path

WRAPPER = Path(__file__).resolve().parents[1] / "scripts" / "codex_review.sh"

FAKE = r"""#!/usr/bin/env bash
# 假 codex：记下参数、CODEX_HOME 和 stdin；CODEX_HOME 在 FAKE_LIMITED 里就报额度用完
stdin=""; [ -t 0 ] || stdin="$(cat)"
STDIN="$stdin" python3 -c 'import json,sys,os; open(os.environ["FAKE_LOG"],"a").write(json.dumps({"args":sys.argv[1:],"home":os.environ.get("CODEX_HOME"),"stdin":os.environ["STDIN"]})+"\n")' "$@"
for h in $FAKE_LIMITED; do
  if [ "$h" = "$CODEX_HOME" ]; then echo "ERROR: You've hit your usage limit. Upgrade to Pro or try again at 10:35 PM." >&2; exit 1; fi
done
echo "review ok"
"""


def setup(tmp_path, limited=()):
    fake = tmp_path / "codex"
    fake.write_text(FAKE)
    fake.chmod(0o755)
    homes = [tmp_path / "a", tmp_path / "b"]
    for h in homes:
        h.mkdir()
    env = {**os.environ, "CODEX_REAL": str(fake), "CODEX_HOMES": " ".join(map(str, homes)), "CODEX_HOME": str(homes[0]),
           "CODEX_BLOCK_DIR": str(tmp_path / "blocked"), "FAKE_LOG": str(tmp_path / "log.jsonl"),
           "FAKE_LIMITED": " ".join(str(tmp_path / x) for x in limited), "CODEX_MODEL": "m1", "CODEX_EFFORT": "medium"}
    return env, homes


def calls(tmp_path):
    p = tmp_path / "log.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def run(env, *args, stdin="PROMPT"):
    return subprocess.run(["bash", str(WRAPPER), *args], input=stdin, text=True, capture_output=True, env=env)


def test_exec_pins_model_and_effort(tmp_path):
    env, homes = setup(tmp_path)
    r = run(env, "exec", "--ephemeral", "--image", "x.png", "-")
    assert r.returncode == 0 and "review ok" in r.stdout
    (c,) = calls(tmp_path)
    assert c["args"][:5] == ["exec", "-m", "m1", "-c", "model_reasoning_effort=medium"]
    assert c["args"][5:] == ["--ephemeral", "--image", "x.png", "-"]
    assert c["home"] == str(homes[0]) and c["stdin"] == "PROMPT"


def test_usage_limit_retries_next_account_and_remembers(tmp_path):
    env, homes = setup(tmp_path, limited=["a"])
    r = run(env, "exec", "-")
    assert r.returncode == 0 and "review ok" in r.stdout
    assert [c["home"] for c in calls(tmp_path)] == [str(homes[0]), str(homes[1])]
    assert all(c["stdin"] == "PROMPT" for c in calls(tmp_path))  # 重试时 prompt 原样再送一次
    # 记住 a 用完了：下一次直接用 b
    r = run(env, "exec", "-")
    assert r.returncode == 0
    assert [c["home"] for c in calls(tmp_path)][2:] == [str(homes[1])]


def test_all_accounts_limited_fails_like_codex(tmp_path):
    env, _ = setup(tmp_path, limited=["a", "b"])
    r = run(env, "exec", "-")
    assert r.returncode != 0 and "usage limit" in r.stderr


def test_other_subcommands_pass_through(tmp_path):
    env, homes = setup(tmp_path)
    r = run(env, "login", "status", stdin="")
    assert r.returncode == 0
    (c,) = calls(tmp_path)
    assert c["args"] == ["login", "status"] and c["home"] == str(homes[0])
