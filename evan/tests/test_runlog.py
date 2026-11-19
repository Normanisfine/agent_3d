import json
from pathlib import Path

from smallobj import runlog

FX = Path(__file__).parent / "fixtures"


def test_parse_tokens():
    u = runlog.parse_codex_events(FX / "codex_events.jsonl")
    assert u["thread_id"] == "01a16254-e02f-7361-8fe5-4a8887590d97"
    assert (u["input_tokens"], u["cached_input_tokens"], u["output_tokens"]) == (14227, 12288, 5)
    assert u["turns"] == 1


def test_rate_limits_from_rollout():
    r = runlog.rate_limits(FX / "codex_rollout.jsonl")
    assert r == {"primary_start": 39.0, "primary_end": 47.0, "weekly_start": 6.0, "weekly_end": 8.5}


def test_timeout_status_and_log(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    runlog.write_run_log(run, exit_code=124, wall_s=3600.4, usage={"thread_id": "t", "input_tokens": 1}, limits={"weekly_start": 6.0, "weekly_end": 9.0})
    log = json.loads((run / "run_log.json").read_text())
    assert log["status"] == "timeout" and log["wall_s"] == 3600.4
    assert log["weekly_delta"] == 3.0


def test_status_from_exit_code():
    assert runlog.status_from_exit(0) == "ok"
    assert runlog.status_from_exit(124) == "timeout"
    assert runlog.status_from_exit(1) == "crashed"


def test_current_limits_resets_after_window(tmp_path):
    import json as _j
    day = tmp_path / "2026" / "10" / "22"
    day.mkdir(parents=True)
    ev = {"type": "event_msg", "payload": {"type": "token_count", "rate_limits": {
        "primary": {"used_percent": 66.0, "window_minutes": 300, "resets_at": 1000},
        "secondary": {"used_percent": 10.0, "window_minutes": 10080, "resets_at": 5000}}}}
    (day / "rollout-x.jsonl").write_text(_j.dumps(ev) + "\n")
    assert runlog.current_limits(tmp_path, now=900) == {"primary": 66.0, "primary_resets_at": 1000, "weekly": 10.0, "weekly_resets_at": 5000}
    assert runlog.current_limits(tmp_path, now=1001)["primary"] == 0.0


def test_tool_calls_counted(tmp_path):
    # codex exec 的 turns 恒为 1；轮数上限按完成的命令执行次数算
    ev = [{"type": "thread.started", "thread_id": "t"},
          {"type": "item.started", "item": {"id": "item_1", "type": "command_execution"}},
          {"type": "item.completed", "item": {"id": "item_1", "type": "command_execution"}},
          {"type": "item.completed", "item": {"id": "item_2", "type": "agent_message"}},
          {"type": "item.completed", "item": {"id": "item_3", "type": "command_execution"}},
          {"type": "turn.completed", "usage": {"input_tokens": 3}}]
    p = tmp_path / "events.jsonl"
    p.write_text("\n".join(json.dumps(e, separators=(",", ":")) for e in ev) + "\n")
    assert runlog.parse_codex_events(p)["tool_calls"] == 2


def test_tool_cap_status():
    assert runlog.status_from_exit(runlog.TOOL_CAP_EXIT) == "tool_cap"


def test_infra_failures_not_blamed_on_agent():
    # codex 不在（127）、没开出会话、撞了额度上限：都是基础设施问题，不记成 agent 跑崩
    assert runlog.final_status(127, {"thread_id": "t"}, {}) == "infra"
    assert runlog.final_status(1, {"thread_id": None}, {}) == "infra"
    assert runlog.final_status(1, {"thread_id": "t"}, {"reached": "primary"}) == "rate_limited"
    assert runlog.final_status(0, {"thread_id": "t"}, {}) == "ok"
    assert runlog.final_status(124, {"thread_id": "t"}, {}) == "timeout"
    assert runlog.final_status(1, {"thread_id": "t"}, {}) == "crashed"


def test_rate_limit_reached_read_from_rollout(tmp_path):
    ev = {"type": "event_msg", "payload": {"type": "token_count", "rate_limits": {
        "primary": {"used_percent": 100.0}, "secondary": {"used_percent": 20.0}, "rate_limit_reached_type": "primary"}}}
    p = tmp_path / "rollout.jsonl"
    p.write_text(json.dumps(ev) + "\n")
    assert runlog.rate_limits(p)["reached"] == "primary"


def test_gt_access_audit(tmp_path):
    proj = "/home/u/proj"
    ev = [{"type": "item.completed", "item": {"type": "command_execution", "command": "ls refs/", "aggregated_output": "a"}},
          {"type": "item.completed", "item": {"type": "command_execution", "command": f"cat {proj}/scenes/123/gt/boxes.json"}},
          {"type": "item.completed", "item": {"type": "command_execution", "command": "cat ../../scenes/123/frames/1/RT.json"}}]
    p = tmp_path / "events.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in ev) + "\n")
    hits = runlog.audit_gt_access(p, proj)
    assert len(hits) == 2 and "boxes.json" in hits[0]


def _claude_events(tmp_path, cmds):
    ev = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": c}}]}} for c in cmds]
    p = tmp_path / "events.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in ev) + "\n")
    return p


def test_same_video_audit(tmp_path):
    # 10-28：同一个视频别的运行（别的组的 AHa-3D 场景、交付目录，runs/ 下别的组的输出）算串用；自己的、别的视频的不算
    run = Path("/p/runs/A3r-claude/123/0")
    bad = ["cat scenes/123_a2-claude_s0/blender/build_room.py",
           "ls /p/third_party/aha-3d/deliveries/123_a0-claude_s0/acceptance",
           "cp /p/runs/A2-claude/123/0/scene.blend /tmp/x.blend",
           "ls scenes/123_A1_s0",
           "ls /p/runs/P0/123/0"]
    ok = ["ls scenes/123_a3r-claude_s0/work_v001",
          "cat /p/runs/A3r-claude/123/0/prompt.md",
          "cat scenes/456_a2-claude_s0/blender/render_stills.py",
          "ls /p/runs/A2-claude/456/0",
          "ls /p/perception/123/bundle",
          "cat /p/runs/legacy/123-reference-20261009/alignment/alignment.json"]  # 输入的参考目录，不是别的运行
    p = _claude_events(tmp_path, ok + bad)
    hits = runlog.audit_same_video(p, run)
    assert sorted(json.loads(h)["command"] for h in hits) == sorted(bad)  # 命中记的是工具输入（同 audit_gt_access）


def test_same_video_audit_own_uppercase_scene(tmp_path):
    # 10-22 到 10-26 的 Codex 运行，AHa-3D 场景 ID 里的组名是大写（45261575_A0_s0），那是它自己的
    p = _claude_events(tmp_path, ["ls scenes/123_A0_s0/work_v001", "ls scenes/123_a1_s0"])
    hits = runlog.audit_same_video(p, Path("/p/runs/A0/123/0"))
    assert [json.loads(h)["command"] for h in hits] == ["ls scenes/123_a1_s0"]


def test_write_run_log_records_same_video_hits(tmp_path, monkeypatch):
    monkeypatch.setattr(runlog, "aha_acceptance", lambda run_dir: {"accepted": None, "source": None})
    log = runlog.write_run_log(tmp_path, 0, 1.0, {"thread_id": "t"}, {}, same_video_hits=["ls scenes/123_a2-claude_s0"])
    assert log["same_video_suspect"] is True and log["same_video_hits"] == ["ls scenes/123_a2-claude_s0"]
    log = runlog.write_run_log(tmp_path, 0, 1.0, {"thread_id": "t"}, {})
    assert log["same_video_suspect"] is False and log["same_video_hits"] == []


def test_write_run_log_status_and_leaks(tmp_path):
    log = runlog.write_run_log(tmp_path, exit_code=127, wall_s=1.0, usage={"thread_id": None}, limits={},
                               leak_hits=["cat /p/scenes/1/gt/boxes.json"])
    assert log["status"] == "infra" and log["leak_suspect"] is True


def test_aha_scene_run():
    # run_agent.sh 的 SCENE_RUN：<场景>_<组小写>_s<种子>
    assert runlog.aha_scene_run("/p/runs/A0-claude/42897538/0") == "42897538_a0-claude_s0"
    assert runlog.aha_scene_run("/p/runs/A1/44358442/0") == "44358442_a1_s0"


def _aha_tree(tmp_path, *tasks):
    run = tmp_path / "runs" / "A1" / "123" / "0"; run.mkdir(parents=True)
    for t in tasks:
        (tmp_path / "aha" / "deliveries" / "123_a1_s0" / "acceptance" / t).mkdir(parents=True)
    return run, tmp_path / "aha"


def test_aha_acceptance_uses_aha_evaluate(tmp_path):
    # AHa-3D 自己的只读判定：任一任务 accepted 且 permitted 才算过
    run, aha = _aha_tree(tmp_path, "t1", "t2")
    seen = []
    def check(root, scene, task):
        seen.append((Path(root), scene, task))
        return {"status": "accepted", "permitted": True, "blockers": []} if task == "t2" else \
               {"status": "blocked", "permitted": False, "blockers": ["OPEN_FINDING", "TASK_INCOMPLETE", "OPEN_FINDING"]}
    r = runlog.aha_acceptance(run, aha_root=aha, check=check)
    assert r["accepted"] is True and r["source"] == "aha_evaluate"
    assert sorted(seen) == [(aha, "123_a1_s0", "t1"), (aha, "123_a1_s0", "t2")]


def test_aha_acceptance_blocked_lists_blockers(tmp_path):
    run, aha = _aha_tree(tmp_path, "t1")
    r = runlog.aha_acceptance(run, aha_root=aha, check=lambda *_: {"status": "blocked", "permitted": False,
                                                                   "blockers": ["OPEN_FINDING", "TASK_INCOMPLETE", "OPEN_FINDING"]})
    assert r == {"accepted": False, "source": "aha_evaluate", "status": "blocked", "blockers": ["OPEN_FINDING", "TASK_INCOMPLETE"]}


def test_aha_acceptance_ignores_summary_wording(tmp_path):
    # 10-27：总结里"审查员 accepted 了布局"被旧版误读成通过；没有 AHa-3D 验收目录就是 None
    run, aha = _aha_tree(tmp_path)
    (run / "SUMMARY.md").write_text("# Result\nThe codex image reviewer accepted both the layout gate and the final views.\n")
    assert runlog.aha_acceptance(run, aha_root=aha, check=lambda *_: 1 / 0) == {"accepted": None, "source": None}


def test_write_run_log_records_aha_acceptance(tmp_path, monkeypatch):
    monkeypatch.setattr(runlog, "aha_acceptance", lambda run_dir: {"accepted": False, "source": "aha_evaluate"})
    log = runlog.write_run_log(tmp_path, 0, 1.0, {"thread_id": "t"}, {})
    assert log["aha_accepted"] is False


def test_parse_claude_stream():
    u = runlog.parse_claude_stream(FX / "claude_stream.jsonl")
    assert u["thread_id"] == "sess-123" and u["tool_calls"] == 3 and u["turns"] == 4
    assert (u["input_tokens"], u["cached_input_tokens"], u["output_tokens"]) == (54200, 50000, 800)
    assert u["cost_usd_equiv"] == 1.25


def test_parse_claude_stream_sums_segments(tmp_path):
    # 10-27 开发 A1：后台任务结束后会话接着跑，一次运行有多条 result；usage 和 num_turns 是这一段的，
    # total_cost_usd 是累计的。旧版只留最后一段，A1 记成 12 轮、输入 4.95M
    ev = [{"type": "system", "subtype": "init", "session_id": "s"},
          {"type": "result", "subtype": "success", "num_turns": 145, "total_cost_usd": 9.72,
           "usage": {"input_tokens": 200, "cache_creation_input_tokens": 300, "cache_read_input_tokens": 5000, "output_tokens": 70}},
          {"type": "result", "subtype": "success", "num_turns": 12, "total_cost_usd": 17.45,
           "usage": {"input_tokens": 20, "cache_creation_input_tokens": 30, "cache_read_input_tokens": 1000, "output_tokens": 10}}]
    p = tmp_path / "events.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in ev) + "\n")
    u = runlog.parse_claude_stream(p)
    assert u["turns"] == 157
    assert (u["input_tokens"], u["cached_input_tokens"], u["output_tokens"]) == (6550, 6000, 80)
    assert u["cost_usd_equiv"] == 17.45


def test_gt_access_audit_claude(tmp_path):
    ev = [{"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Read", "input": {"file_path": "/home/u/proj/scenes/1/gt/boxes.json"}},
        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}}]
    p = tmp_path / "events.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in ev) + "\n")
    assert len(runlog.audit_gt_access(p, "/home/u/proj")) == 1


def test_claude_usage_limit_is_rate_limited(tmp_path):
    ev = [{"type": "system", "subtype": "init", "session_id": "s"},
          {"type": "result", "subtype": "error_during_execution", "is_error": True, "session_id": "s",
           "result": "Claude usage limit reached. Your limit will reset at 7pm.", "usage": {}}]
    p = tmp_path / "events.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in ev) + "\n")
    u = runlog.parse_claude_stream(p)
    assert u["limit_hit"] is True
    assert runlog.final_status(1, u, {}) == "rate_limited"


def _limit_events(five, week, result):
    return [{"type": "system", "subtype": "init", "session_id": "s"},
            {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "unifiedWindows": {
                "five_hour": {"utilization": five, "resetsAt": 5000, "status": "allowed"},
                "seven_day": {"utilization": week, "resetsAt": 99999, "status": "allowed"}}}},
            result]


def test_claude_limit_pause(tmp_path):
    # 10-28 起（Yifan："5 小时窗口直接用完，不要有限制"）：运行中途撞到 5 小时上限，等窗口重置后续跑同一个会话；
    # 每周额度用完就不等（照旧记 rate_limited 停下）；没撞上限、读不到额度也不等
    hit = {"type": "result", "subtype": "success", "is_error": True, "session_id": "s", "num_turns": 40,
           "result": "You've hit your limit · resets 12:30pm", "usage": {}}
    ok = {"type": "result", "subtype": "success", "is_error": False, "session_id": "s", "num_turns": 40, "usage": {}}
    p = tmp_path / "events.jsonl"
    for ev, want in ((_limit_events(0.97, 0.5, hit), 4060), (_limit_events(0.97, 1.0, hit), None),
                     (_limit_events(0.97, 0.5, ok), None), (_limit_events(0.97, 0.5, hit)[::2], None)):
        p.write_text("\n".join(json.dumps(e) for e in ev) + "\n")
        assert runlog.claude_limit_pause(p, now=1000) == want
    p.write_text("\n".join(json.dumps(e) for e in _limit_events(0.97, 0.5, hit)) + "\n")
    assert runlog.claude_limit_pause(p, now=4990) == 120   # 重置时间已过或很近，至少等两分钟


def test_parse_claude_stream_sums_cost_across_resumes(tmp_path):
    # 续跑是一个新进程，total_cost_usd 从 0 重新累计；run_agent.sh 在续跑前写一条 smallobj_resume（带等待秒数）。
    # 同一进程里后台任务结束后的接续段也有 init，total_cost_usd 照旧是累计的，不能按 init 分段相加
    ev = [{"type": "system", "subtype": "init", "session_id": "s"},
          {"type": "result", "num_turns": 30, "total_cost_usd": 4.0, "usage": {"output_tokens": 10}},
          {"type": "system", "subtype": "init", "session_id": "s"},
          {"type": "result", "is_error": True, "result": "You've hit your limit", "num_turns": 10, "total_cost_usd": 6.0,
           "usage": {"output_tokens": 5}},
          {"type": "smallobj_resume", "paused_s": 3000, "session_id": "s"},
          {"type": "system", "subtype": "init", "session_id": "s"},
          {"type": "result", "is_error": False, "num_turns": 20, "total_cost_usd": 2.5, "usage": {"output_tokens": 7}}]
    p = tmp_path / "events.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in ev) + "\n")
    u = runlog.parse_claude_stream(p)
    assert (u["cost_usd_equiv"], u["turns"], u["output_tokens"], u["limit_hit"]) == (8.5, 60, 22, False)
    assert runlog.claude_pauses(p) == 3000
    log = runlog.write_run_log(tmp_path, 0, 500.0, u, {}, account="claude", paused_s=3000)
    assert (log["status"], log["wall_s"], log["paused_s"]) == ("ok", 500.0, 3000.0)
    assert runlog.write_run_log(tmp_path, 0, 500.0, u, {})["paused_s"] == 0.0


def test_gt_audit_no_false_positive_on_agent_file_names(tmp_path):
    # 10-26 测试集 A1 42899729：agent 自己的文件叫 storage-gap-and-chair-visibility.json，被误判碰了真值、整批停下
    proj = "/home/u/proj"
    ok = ["bash tools/indoor acceptance finding x runs/x/storage-gap-and-chair-visibility.json",
          "cat runs/x/support_REPORT.json"]
    bad = [f"cat {proj}/scenes/1/gt/visibility_364x266_100000.json", "cat ../../scenes/1/frames/7/RT.json",
           f"ls {proj}/scenes/1/gt/"]
    ev = [{"type": "item.completed", "item": {"type": "command_execution", "command": c}} for c in ok + bad]
    p = tmp_path / "events.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in ev) + "\n")
    assert len(runlog.audit_gt_access(p, proj)) == len(bad)


def _fake_home(root, name, primary, weekly, p_reset=1000, w_reset=5000, logged_in=True):
    home = root / name
    day = home / "sessions" / "2026" / "10" / "27"
    day.mkdir(parents=True)
    ev = {"type": "event_msg", "payload": {"type": "token_count", "rate_limits": {
        "primary": {"used_percent": primary, "resets_at": p_reset}, "secondary": {"used_percent": weekly, "resets_at": w_reset}}}}
    (day / "rollout-x.jsonl").write_text(json.dumps(ev) + "\n")
    if logged_in:
        (home / "auth.json").write_text("{}")
    return home


def test_sessions_follow_codex_home(tmp_path, monkeypatch):
    home = _fake_home(tmp_path, "acc-b", 40.0, 10.0)
    monkeypatch.setenv("CODEX_HOME", str(home))
    assert runlog.current_limits(now=900)["primary"] == 40.0


def test_pick_account_rotates(tmp_path):
    a = _fake_home(tmp_path, "a", 70.0, 30.0, p_reset=2000)      # 5 小时窗口快满
    b = _fake_home(tmp_path, "b", 10.0, 30.0)                   # 有空
    c = _fake_home(tmp_path, "c", 0.0, 0.0, logged_in=False)    # 没登录，不用
    assert runlog.pick_account([a, b, c], est_primary=60, now=900) == (str(b), 0)
    b2 = _fake_home(tmp_path, "b2", 50.0, 30.0, p_reset=1500)
    assert runlog.pick_account([a, b2], est_primary=60, now=900) == (None, 1500 - 900 + 120)  # 都满：等最早的重置
    full = _fake_home(tmp_path, "full", 0.0, 92.0)
    assert runlog.pick_account([full], est_primary=60, now=900) == (None, None)               # 每周额度都用完：停


def test_run_log_records_account(tmp_path):
    log = runlog.write_run_log(tmp_path, 0, 1.0, {"thread_id": "t"}, {}, account="/home/u/.codex-b")
    assert log["codex_home"] == "/home/u/.codex-b"


def test_windows_identified_by_length(tmp_path):
    # 10-27 第二个 Plus 账户：只有一个每周窗口，放在 primary（window_minutes=10080），secondary 是 null
    def ev(pct):
        return {"type": "event_msg", "payload": {"type": "token_count", "rate_limits": {
            "primary": {"used_percent": pct, "window_minutes": 10080, "resets_at": 5000}, "secondary": None}}}
    p = tmp_path / "rollout.jsonl"
    p.write_text(json.dumps(ev(0.0)) + "\n" + json.dumps(ev(5.0)) + "\n")
    r = runlog.rate_limits(p)
    assert r["weekly_start"] == 0.0 and r["weekly_end"] == 5.0 and "primary_start" not in r
    day = tmp_path / "home" / "sessions" / "2026" / "10" / "27"
    day.mkdir(parents=True)
    (day / "rollout-y.jsonl").write_text(p.read_text())
    c = runlog.current_limits(tmp_path / "home" / "sessions", now=100)
    assert c["primary"] == 0.0 and c["weekly"] == 5.0 and c["weekly_resets_at"] == 5000


def test_claude_rate_limits_from_stream(tmp_path):
    # 10-27 起主实验用 Claude 订阅：stream 里的 rate_limit_event 带 5 小时和每周窗口的使用率（0–1），换成百分点记开头和结尾
    def ev(five, week, status="allowed"):
        return {"type": "rate_limit_event", "rate_limit_info": {"status": status, "unifiedWindows": {
            "five_hour": {"utilization": five, "resetsAt": 1, "status": status},
            "seven_day": {"utilization": week, "resetsAt": 2, "status": status}}}}
    p = tmp_path / "events.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in [{"type": "system", "subtype": "init", "session_id": "s"},
                                                   ev(0.13, 0.23), ev(0.40, 0.30)]) + "\n")
    lim = runlog.claude_rate_limits(p)
    assert lim == {"primary_start": 13.0, "primary_end": 40.0, "weekly_start": 23.0, "weekly_end": 30.0, "reached": False}
    log = runlog.write_run_log(tmp_path, 0, 1.0, {"thread_id": "s"}, lim, account="claude")
    assert (log["weekly_delta"], log["primary_delta"]) == (7.0, 27.0)
    p.write_text(json.dumps(ev(1.0, 0.5, status="rejected")) + "\n")
    assert runlog.claude_rate_limits(p)["reached"] is True
    p.write_text(json.dumps({"type": "system", "subtype": "init", "session_id": "s"}) + "\n")
    assert runlog.claude_rate_limits(p) == {}


def test_claude_windows_and_gate(tmp_path):
    # 排 Claude 队列：开跑前用一次很短的调用读额度。每周到上限（Yifan 10-27 定 85%）就停；
    # 5 小时窗口到 primary_max 就等它重置（10-28 起默认 100，用完才等，中途撞上限由 run_agent.sh 续跑）；读不到额度也停
    def ev(five, week):
        return {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "unifiedWindows": {
            "five_hour": {"utilization": five, "resetsAt": 4600, "status": "allowed"},
            "seven_day": {"utilization": week, "resetsAt": 99999, "status": "allowed"}}}}
    p = tmp_path / "probe.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in [ev(0.10, 0.20), ev(0.12, 0.31)]) + "\n")
    w = runlog.claude_windows(p)
    assert w == {"five_hour": {"pct": 12.0, "resets_at": 4600}, "seven_day": {"pct": 31.0, "resets_at": 99999}}
    assert runlog.claude_gate(w, weekly_max=85, primary_max=50, now=1000) == ("run", 0)
    w["five_hour"]["pct"] = 60.0
    assert runlog.claude_gate(w, weekly_max=85, primary_max=50, now=1000) == ("wait", 3660)
    w["seven_day"]["pct"] = 85.0
    assert runlog.claude_gate(w, weekly_max=85, primary_max=50, now=1000) == ("stop", None)
    assert runlog.claude_gate({}, weekly_max=85, primary_max=50, now=1000) == ("stop", None)
    w["seven_day"]["pct"], w["five_hour"]["pct"] = 40.0, 99.0
    assert runlog.claude_gate(w, weekly_max=85, primary_max=100, now=1000) == ("run", 0)
    w["five_hour"]["pct"] = 100.0
    assert runlog.claude_gate(w, weekly_max=85, primary_max=100, now=1000) == ("wait", 3660)
    p.write_text("")
    assert runlog.claude_windows(p) == {}
