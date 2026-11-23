import json
import re
from pathlib import Path

from smallobj import inventory, prompts, runlog

PROJ = Path(__file__).resolve().parents[1]
DEV_RUN = PROJ / "runs" / "A1" / "45261575" / "0"
REPAIR_STOP = "- If a stage still fails after about three repair attempts, stop and document it.\n"


def _vars(arm="A1", scene_run="45261575_A1_s0"):
    run = PROJ / "runs" / arm / "45261575" / "0"
    return {"AHA": str(PROJ / "third_party" / "aha-3d"), "SCENE_RUN": scene_run, "REQUEST": str(run / "request.json"),
            "REF_DIR": str((PROJ / "perception" / "45261575" / "bundle").resolve()), "OUT": str(run),
            "SCENE_ID": "45261575", "INVENTORY": str(PROJ / "perception" / "45261575" / "inventory.json"),
            "CROPS": str(PROJ / "perception" / "45261575" / "inventory_crops"),
            "ROUTE": str(run / "route_generate.json"), "TOOLS": str(PROJ / "scripts" / "agent_tools")}


def test_a1_render_matches_dev_run():
    if not (DEV_RUN / "prompt.md").exists():
        import pytest
        pytest.skip("开发集 A1 运行不在本机")
    prompt, request = prompts.render("A1", _vars())
    # 10-27 起去掉"修约 3 次就停"（AHa-3D 原版要求一直修到验收通过），10-28 起加了"不许碰同一个视频别的运行"；
    # 除此之外和开发集运行逐字一致
    prompt = re.sub(r"- Other runs on this machine .*? folders other than `[^`]*`\.\n", "", prompt, flags=re.S)
    assert prompt == (DEV_RUN / "prompt.md").read_text().replace(REPAIR_STOP, "")
    assert json.loads(request) == json.loads((DEV_RUN / "request.json").read_text())


def test_same_video_isolation_rule():
    # 10-28：AHa-3D 默认 reuse_allowed（"复用已审过的输入"），同一个视频别的组的场景目录会被当成可复用的；
    # 各组要互相独立，提示词里明说不许碰同一个视频别的运行（别的视频的照旧不限，和之前的运行一致）
    for arm in prompts.ARMS:
        prompt, _ = prompts.render(arm, _vars(arm, f"45261575_{arm.lower()}-claude_s0"))
        rules = prompt.split("## Rules")[1]
        assert "`scenes/45261575_*`" in rules and "`deliveries/45261575_*`" in rules, arm
        assert "`runs/*/45261575/`" in rules and f"`45261575_{arm.lower()}-claude_s0`" in rules, arm


def test_no_repair_stop_rule():
    # 修复轮数不设上限：按 AHa-3D 原版，验收没过就继续修（10-27 Yifan 定）
    for arm in prompts.ARMS:
        assert "repair attempts" not in prompts.template(arm), arm


def test_prompt_templates_fully_rendered():
    for arm in ("A0", "A1", "A2", "A3r", "A3v"):
        prompt, request = prompts.render(arm, _vars(arm))
        assert "{{" not in prompt and "{{" not in request, arm


def test_arms_differ_only_by_additions():
    a1 = prompts.template("A1").splitlines()
    rule = [l for l in a1 if "image-to-3D generator" in l]
    assert len(rule) == 1
    for arm in ("A2", "A3r", "A3v"):
        lines = prompts.template(arm).splitlines()
        it = iter(lines)
        keep = [l for l in a1 if not (arm.startswith("A3") and l in rule)]
        assert all(any(l == x for x in it) for l in keep), arm  # A1 的每一行按顺序都还在
    assert prompts.template("A2").count("inventory_decisions.json") >= 1
    assert "{{ROUTE}}" in prompts.template("A3r") and "{{ROUTE}}" not in prompts.template("A3v")


def test_route_rule():
    from smallobj import boxes
    items = []
    for iid, L in (("a", 0.3), ("b", 0.49), ("c", 0.5), ("d", 1.2)):
        r = boxes.record(iid, "x", (0, 0, 0), 0, (L, 0.1, 0.1))
        r["item_id"] = iid
        items.append(r)
    assert inventory.route_rule(items) == ["a", "b"]


def test_agent_tool_paths_pass_gt_audit(tmp_path):
    prompt, _ = prompts.render("A3v", _vars("A3v", "45261575_a3v_s0"))
    cmds = [l.strip().strip("`") for l in prompt.splitlines() if "agent_tools/" in l]
    assert len(cmds) >= 3
    ev = [{"type": "item.completed", "item": {"type": "command_execution", "command": c}} for c in cmds]
    p = tmp_path / "events.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in ev) + "\n")
    assert runlog.audit_gt_access(p, str(PROJ)) == []


def test_a5_adds_only_the_checklist_section():
    # A5（11-20）：A1 全文 + 清单 v2 的逐项清单一节；要求每个条目各建一个独立物体，重复和部件要指向已建的物体
    a1, a5 = prompts.template("A1").splitlines(), prompts.template("A5").splitlines()
    assert [l for l in a5 if l in a1 or not l.strip()] and all(l in a5 for l in a1)
    section = prompts.template("A5").split("## Object checklist")[1].split("## When you finish or stop")[0]
    for word in ("duplicate", "part", "one instance per", "{{INVENTORY}}", "{{CROPS}}"):
        assert word in section, word
    prompt, request = prompts.render("A5", _vars("A5", "45261575_a5-claude_s0"))
    assert "{{" not in prompt and "{{" not in request
