"""一次 agent 运行的记录：token 用量（codex --json 事件）、订阅额度变化（~/.codex/sessions 会话记录）、状态。"""
import json
import re
import os
from pathlib import Path

SESSIONS = Path.home() / ".codex" / "sessions"


def sessions_dir():
    """当前 Codex 账户的会话记录目录：跟着 CODEX_HOME 走（两个 Plus 账户轮换时各有各的目录）。"""
    home = os.environ.get("CODEX_HOME")
    return Path(home) / "sessions" if home else SESSIONS
TOOL_CAP_EXIT = 200  # run_agent.sh 的看门狗因工具调用次数到上限而停掉 agent 时用的退出码


def _lines(path):
    for line in Path(path).read_text(errors="replace").splitlines():
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def parse_codex_events(path):
    """累加所有 turn.completed 的 usage；thread_id 用来找会话记录。
    codex exec 整次只有一个 turn，所以另数 tool_calls（完成的命令执行次数），当"轮数"用。"""
    out = {"thread_id": None, "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0,
           "reasoning_output_tokens": 0, "turns": 0, "tool_calls": 0}
    for e in _lines(path):
        if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "command_execution":
            out["tool_calls"] += 1
        elif e.get("type") == "thread.started":
            out["thread_id"] = e.get("thread_id")
        elif e.get("type") == "turn.completed":
            out["turns"] += 1
            for k in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"):
                out[k] += int(e.get("usage", {}).get(k, 0))
    return out


def parse_claude_stream(path):
    """headless Claude Code（--output-format stream-json）的记录：键和 parse_codex_events 一样，
    另加 cost_usd_equiv（API 等价美元）。输入 token = 新输入 + 写缓存 + 读缓存；tool_calls 数 tool_use 块。
    后台任务结束后会话会接着跑，一次运行可能有多条 result：usage 和 num_turns 是那一段的，要累加；
    total_cost_usd 在一个进程里是累计的，取最后一条。撞 5 小时上限后续跑（run_agent.sh 先写一条 smallobj_resume）
    是新进程，total_cost_usd 从 0 重新累计，所以按续跑分段，各段最后一条相加。"""
    out = {"thread_id": None, "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0,
           "reasoning_output_tokens": 0, "turns": 0, "tool_calls": 0, "cost_usd_equiv": None, "limit_hit": False}
    done = 0.0   # 前几个进程的费用
    for e in _lines(path):
        t = e.get("type")
        if t == "smallobj_resume":
            done = out["cost_usd_equiv"] or 0.0
        elif t == "system" and e.get("subtype") == "init":
            out["thread_id"] = e.get("session_id")
        elif t == "assistant":
            out["tool_calls"] += sum(1 for c in e.get("message", {}).get("content", []) if c.get("type") == "tool_use")
        elif t == "result":
            u = e.get("usage", {})
            out["thread_id"] = out["thread_id"] or e.get("session_id")
            out["input_tokens"] += int(u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0))
            out["cached_input_tokens"] += int(u.get("cache_read_input_tokens", 0))
            out["output_tokens"] += int(u.get("output_tokens", 0))
            out["turns"] += int(e.get("num_turns", 0))
            out["cost_usd_equiv"] = done + e["total_cost_usd"] if e.get("total_cost_usd") is not None else out["cost_usd_equiv"]
            text = str(e.get("result", "")).lower()
            out["limit_hit"] = bool(e.get("is_error")) and ("limit" in text or "rate" in text or "quota" in text)
    return out


def claude_rate_limits(path):
    """Claude 订阅的额度：stream 里 rate_limit_event 的 5 小时（primary）和每周（weekly）使用率，换成百分点，
    取第一条和最后一条；哪个窗口不是 allowed 就记 reached。一条都没有返回 {}。"""
    evs = [e["rate_limit_info"] for e in _lines(path) if e.get("type") == "rate_limit_event" and e.get("rate_limit_info")]
    if not evs:
        return {}
    pct = lambda info, k: round(100 * info.get("unifiedWindows", {}).get(k, {}).get("utilization", 0.0), 3)  # noqa: E731
    reached = any(i.get("status", "allowed") != "allowed" or any(w.get("status", "allowed") != "allowed"
                                                                 for w in i.get("unifiedWindows", {}).values()) for i in evs)
    return {"primary_start": pct(evs[0], "five_hour"), "primary_end": pct(evs[-1], "five_hour"),
            "weekly_start": pct(evs[0], "seven_day"), "weekly_end": pct(evs[-1], "seven_day"), "reached": reached}


def claude_windows(path):
    """最后一条 rate_limit_event 里 5 小时和每周窗口的使用率（百分点）和重置时间；没有就返回 {}。"""
    evs = [e["rate_limit_info"] for e in _lines(path) if e.get("type") == "rate_limit_event" and e.get("rate_limit_info")]
    if not evs:
        return {}
    win = evs[-1].get("unifiedWindows", {})
    return {k: {"pct": round(100 * win.get(k, {}).get("utilization", 0.0), 3), "resets_at": win.get(k, {}).get("resetsAt")}
            for k in ("five_hour", "seven_day")}


def claude_limit_pause(events_path, now=None):
    """运行中途撞到 Claude 5 小时上限时，等到窗口重置后一分钟的秒数（至少 120）；不是这种情况返回 None。
    每周额度用完、没撞上限、或读不到额度都返回 None（照旧记 rate_limited 停下）。"""
    import time
    if not parse_claude_stream(events_path)["limit_hit"]:
        return None
    w = claude_windows(events_path)
    if not w or w["seven_day"]["pct"] >= 100 or not w["five_hour"]["resets_at"]:
        return None
    now = time.time() if now is None else now
    return max(120, int(w["five_hour"]["resets_at"] - now) + 60)


def claude_pauses(events_path):
    """因 5 小时上限等待的总秒数（run_agent.sh 续跑前写的 smallobj_resume 记录）。"""
    return sum(float(e.get("paused_s", 0)) for e in _lines(events_path) if e.get("type") == "smallobj_resume")


def claude_gate(windows, weekly_max, primary_max, now=None):
    """开跑前看 Claude 订阅额度：("run", 0)、("wait", 等到 5 小时窗口重置后一分钟的秒数) 或 ("stop", None)。
    每周到 weekly_max 就停；5 小时窗口到 primary_max 就等（10-28 起默认 100：用完才等，运行中途撞上限由 run_agent.sh
    等重置后续跑）；读不到额度也停。"""
    import time
    if not windows:
        return "stop", None
    if windows["seven_day"]["pct"] >= weekly_max:
        return "stop", None
    if windows["five_hour"]["pct"] >= primary_max:
        now = time.time() if now is None else now
        return "wait", max(60, int(windows["five_hour"]["resets_at"] - now) + 60)
    return "run", 0


def find_rollout(thread_id, sessions=None):
    sessions = sessions or sessions_dir()
    hits = sorted(Path(sessions).rglob(f"*{thread_id}*.jsonl")) if thread_id else []
    return hits[-1] if hits else None


def _windows(rl):
    """一条 rate_limits 里的 (5 小时窗口, 每周窗口)，没有的是 None。按 window_minutes 认：
    不超过一天的是短窗口，三天以上的是每周窗口（10-27 的第二个 Plus 账户只有每周窗口，放在 primary、secondary 为 null）。
    没有 window_minutes 字段时按位置：primary 是 5 小时，secondary 是每周。"""
    short = weekly = None
    for pos, w in (("primary", rl.get("primary")), ("secondary", rl.get("secondary"))):
        if not w:
            continue
        m = w.get("window_minutes")
        if m is None:
            if pos == "primary":
                short = short or w
            else:
                weekly = weekly or w
        elif m <= 1440:
            short = w
        elif m >= 3 * 1440:
            weekly = w
    return short, weekly


def rate_limits(rollout_path):
    """会话里第一条和最后一条 token_count 的额度百分比：5 小时窗口记 primary_*，每周窗口记 weekly_*（没有的窗口不出现）。"""
    found = []
    for e in _lines(rollout_path):
        p = e.get("payload", {})
        if p.get("type") == "token_count" and p.get("rate_limits"):
            found.append(p["rate_limits"])
    if not found:
        return {}
    (sa, wa), (sb, wb) = _windows(found[0]), _windows(found[-1])
    out = {}
    if sa and sb:
        out.update(primary_start=sa["used_percent"], primary_end=sb["used_percent"])
    if wa and wb:
        out.update(weekly_start=wa["used_percent"], weekly_end=wb["used_percent"])
    reached = [f["rate_limit_reached_type"] for f in found if f.get("rate_limit_reached_type")]
    if reached:
        out["reached"] = reached[-1]  # 运行中撞了额度上限
    return out


def status_from_exit(code):
    return {0: "ok", 124: "timeout", TOOL_CAP_EXIT: "tool_cap"}.get(int(code), "crashed")


def final_status(exit_code, usage, limits):
    """一次运行的状态。基础设施问题（codex 不在、会话没开出来）记 infra，撞额度上限记 rate_limited，
    都不算 agent 的失败；其余按退出码：ok / timeout / tool_cap / crashed。"""
    code = int(exit_code)
    if code in (126, 127) or not usage.get("thread_id"):
        return "infra"
    if code != 0 and (limits.get("reached") or usage.get("limit_hit")):
        return "rate_limited"
    return status_from_exit(code)


# agent 不该碰的真值路径（CA-1M 真值框、位姿、深度、按真值算的可见性缓存）
# 10-26：去掉 "visibility.json"（agent 自己的文件名里也会有，误判停过一次队列；真值的可见性缓存在 scenes/<id>/gt/ 下，
# 已被 "/gt/" 盖住），"RT.json" 改成 "/RT.json"（免得 REPORT.json 之类的名字被误判）
GT_PATTERNS = ("/gt/", "/RT.json", "world_instances", "../../scenes/")


def audit_gt_access(events_path, proj):
    """在 agent 执行过的命令里找真值路径；返回命中的命令（截断到 200 字符）。"""
    pats = GT_PATTERNS + (f"{proj}/scenes/",)
    hits = []
    for e in _lines(events_path):
        cmds = []
        item = e.get("item", {})
        if e.get("type") == "item.completed" and item.get("type") == "command_execution":  # Codex
            cmds.append(str(item.get("command", "")))
        elif e.get("type") == "assistant":  # Claude：Bash 的命令、Read/Edit 的路径都在 input 里
            cmds += [json.dumps(c.get("input", {}), ensure_ascii=False) for c in e.get("message", {}).get("content", [])
                     if c.get("type") == "tool_use"]
        hits += [c[:200] for c in cmds if any(p in c for p in pats)]
    return hits


def audit_same_video(events_path, run_dir):
    """在 agent 执行过的命令里找同一个视频别的运行：别的组的 AHa-3D 场景、交付目录（scenes|deliveries/<视频>_*），
    runs/ 下别的组的输出（runs/<组>/<视频>/）。自己的、别的视频的不算。返回命中的命令（截断到 200 字符）。
    10-28 起提示词明说不许碰；之前的运行用这个查过一遍。"""
    p = Path(run_dir)
    sid, arm, own = p.parent.name, p.parent.parent.name, aha_scene_run(run_dir)
    pats = [re.compile(rf"(?:scenes|deliveries)/({re.escape(sid)}_[A-Za-z0-9_-]+)"), re.compile(rf"runs/([^/\s\"']+)/{re.escape(sid)}(?=/|$|[\s\"'])")]
    hits = []
    for e in _lines(events_path):
        cmds = []
        item = e.get("item", {})
        if e.get("type") == "item.completed" and item.get("type") == "command_execution":
            cmds.append(str(item.get("command", "")))
        elif e.get("type") == "assistant":
            cmds += [json.dumps(c.get("input", {}), ensure_ascii=False) for c in e.get("message", {}).get("content", [])
                     if c.get("type") == "tool_use"]
        for c in cmds:
            # 10-26 之前 Codex 运行的场景 ID 组名是大写（123_A0_s0），按不分大小写比
            others = [m for m in pats[0].findall(c) if m.lower() != own] + [m for m in pats[1].findall(c) if m != arm]
            if others:
                hits.append(c[:200])
    return hits


AHA_ROOT = Path(__file__).resolve().parents[2] / "third_party" / "aha-3d"
_EVALUATE = ("import json, sys; from pathlib import Path; from aha3d.workflow import acceptance as a; "
             "r = a.evaluate(Path(sys.argv[1]), sys.argv[2], sys.argv[3]); "
             "print(json.dumps({'status': r['status'], 'permitted': r['permitted'], 'blockers': [b['code'] for b in r['blockers']]}))")


def aha_scene_run(run_dir):
    """runs/<组>/<场景>/<种子> → 这次运行在 AHa-3D 里的场景 ID（run_agent.sh 的 SCENE_RUN）。"""
    p = Path(run_dir)
    return f"{p.parent.name}_{p.parent.parent.name.lower()}_s{p.name}"


def _aha_evaluate(aha_root, scene, task):
    """用 AHa-3D 自己的环境跑它的只读判定 acceptance.evaluate（不写任何文件）。"""
    import subprocess
    py = Path(os.environ.get("KIMODO_ENV", str(Path(aha_root) / ".runtime" / "pi3x-inference" / "venv"))) / "bin" / "python"
    out = subprocess.run([str(py), "-c", _EVALUATE, str(aha_root), scene, task], capture_output=True, text=True,
                         timeout=300, env={**os.environ, "PYTHONPATH": str(Path(aha_root) / "src")})
    return json.loads(out.stdout.strip().splitlines()[-1])


def aha_acceptance(run_dir, aha_root=None, check=None):
    """AHa-3D 自己的验收结论（和我们的打分无关）：对这次运行在 deliveries/<SCENE_RUN>/acceptance/ 下的每个任务
    跑 AHa-3D 的只读判定 evaluate()，有一个任务判 accepted 且 permitted 就算过；没有验收目录就是 None。
    不看 SUMMARY.md：总结里"审查员 accepted 了某一关"会被误读成通过（10-27 发现两次）。"""
    aha_root = Path(aha_root or AHA_ROOT)
    check = check or _aha_evaluate
    acc = aha_root / "deliveries" / aha_scene_run(Path(run_dir).resolve()) / "acceptance"
    tasks = sorted(p.name for p in acc.iterdir() if p.is_dir()) if acc.is_dir() else []
    if not tasks:
        return {"accepted": None, "source": None}
    results = [check(aha_root, acc.parent.name, t) for t in tasks]
    if any(r["status"] == "accepted" and r["permitted"] for r in results):
        return {"accepted": True, "source": "aha_evaluate"}
    return {"accepted": False, "source": "aha_evaluate", "status": results[-1]["status"],
            "blockers": sorted({b for r in results for b in r["blockers"]})}


def write_run_log(run_dir, exit_code, wall_s, usage, limits, leak_hits=None, account=None, same_video_hits=None, paused_s=0.0):
    """wall_s 不含等 Claude 5 小时窗口重置的时间，那部分记在 paused_s。"""
    log = {"status": final_status(exit_code, usage, limits), "exit_code": int(exit_code), "wall_s": float(wall_s),
           "paused_s": float(paused_s),
           "usage": usage, "rate_limits": limits,
           "leak_suspect": bool(leak_hits), "leak_hits": list(leak_hits or []),
           "same_video_suspect": bool(same_video_hits), "same_video_hits": list(same_video_hits or []),
           "aha_accepted": aha_acceptance(run_dir)["accepted"], "codex_home": account}
    if "weekly_start" in limits:
        log["weekly_delta"] = round(limits["weekly_end"] - limits["weekly_start"], 3)
        log["primary_delta"] = round(limits.get("primary_end", 0) - limits.get("primary_start", 0), 3) if "primary_start" in limits else None
    Path(run_dir, "run_log.json").write_text(json.dumps(log, indent=1) + "\n")
    return log


def current_limits(sessions=None, now=None):
    """最近一次 Codex 会话记录里的额度；窗口过了重置时间就当 0。"""
    import time
    sessions = sessions or sessions_dir()
    now = time.time() if now is None else now
    files = sorted(Path(sessions).rglob("rollout-*.jsonl"), key=lambda p: p.stat().st_mtime)
    for f in reversed(files):
        last = None
        for e in _lines(f):
            p = e.get("payload", {})
            if p.get("type") == "token_count" and p.get("rate_limits"):
                last = p["rate_limits"]
        if last:
            pr, wk = _windows(last)  # 没有 5 小时窗口的账户：primary 记 0（不受限）
            used = lambda w: 0.0 if (not w or now >= w.get("resets_at", 0)) else w["used_percent"]  # noqa: E731
            return {"primary": used(pr), "primary_resets_at": pr.get("resets_at") if pr else None,
                    "weekly": used(wk), "weekly_resets_at": wk.get("resets_at") if wk else None}
    return {}


def pick_account(homes, est_primary=60, now=None):
    """几个 Codex 账户（CODEX_HOME 目录）里挑一个这次跑得下的：5 小时窗口已用 + est_primary ≤ 95 且每周已用 + 10 ≤ 95。
    返回 (账户目录, 0)；都跑不下但还有账户每周额度够时返回 (None, 等到最早的窗口重置的秒数 + 2 分钟)；
    所有账户每周额度都不够返回 (None, None)。没有 auth.json（没登录）的目录跳过。"""
    import time
    now = time.time() if now is None else now
    waits = []
    for h in homes:
        h = Path(h)
        if not (h / "auth.json").exists():
            continue
        c = current_limits(h / "sessions", now=now)
        primary, weekly = c.get("primary", 0.0), c.get("weekly", 0.0)
        if weekly + 10 > 95:
            continue
        if primary + est_primary <= 95:
            return str(h), 0
        waits.append(max(60, int((c.get("primary_resets_at") or now) - now) + 120))
    return (None, min(waits)) if waits else (None, None)
