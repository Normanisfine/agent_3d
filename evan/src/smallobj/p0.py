"""P0 无 agent 流水线（设计 §5）：清单 → 小物体生成 + place_mesh → 过验收的用网格，否则用清单框（方块）。

只给估计最长边 < 0.5 m 的物体生成（和 A3r 同一条规则），每个 1 个候选；大物体直接用框。
（笔记本上 Hunyuan 每个物体 20–45 s，全部生成一个场景要几个小时。）
输出照 §15b：runs/P0|P0c/<scene>/<seed>/{export/objects.json, placements.json, run_log.json, scene.blend}。
"""
import json
import subprocess
import time
from pathlib import Path

from smallobj import boxes, gen3d, inventory, place

PROJ = Path(__file__).resolve().parents[2]
FLOOR_Z = 0.0  # AHa-3D 对齐后的房间坐标里地面在 z = 0（10-26 在 3 个开发场景上核对：Pi3X 点的 5% 分位 |z| < 3 mm）


def generation_targets(items, max_longest_m: float = 0.5) -> list:
    return [it["item_id"] for it in items if max(it["size"]) < max_longest_m]


def assemble(items: list, placements: dict) -> list:
    """每个清单物体一条：放置被接受的用网格摆好后的框（source="gen"），否则用清单框（source="box"）。"""
    out = []
    for it in items:
        pl = placements.get(it["item_id"])
        if pl and pl.get("status") == "accepted":
            b = pl["placed_box"]
            out.append(boxes.record(it["item_id"], it["category"], b["center"], b["yaw"], b["size"], source="gen"))
        else:
            out.append(boxes.record(it["item_id"], it["category"], it["center"], it["yaw"], it["size"], source="box"))
    return out


def run_p0(scene_id: str, inventory_name: str, run_dir: Path, backend: str = "hy3d_shape", root: Path = PROJ) -> dict:
    t0 = time.time()
    run_dir = Path(run_dir)
    (run_dir / "export").mkdir(parents=True, exist_ok=True)
    items = inventory.load(Path(root) / "perception" / scene_id / inventory_name)
    targets = generation_targets(items)
    gens = gen3d.request(scene_id, targets, backend=backend, n_candidates=1, inventory=inventory_name, root=root,
                         max_gen=None, budget_name=f"budget_p0_{Path(inventory_name).stem}")
    placements = {}
    for g in gens:
        if g["status"] != "ok":
            placements[g["item_id"]] = {"status": g["status"]}
            continue
        it = next(i for i in items if i["item_id"] == g["item_id"])
        support = FLOOR_Z if it["center"][2] - it["size"][2] / 2 < FLOOR_Z + 0.05 else None
        placements[g["item_id"]] = place.place_mesh(scene_id, g["item_id"], g["candidate_id"], support_z=support,
                                                    inventory=inventory_name, root=root)
    objs = assemble(items, placements)
    boxes.save(objs, run_dir / "export" / "objects.json")
    (run_dir / "placements.json").write_text(json.dumps(placements, indent=1) + "\n")
    blend = assemble_blend(objs, placements, run_dir / "scene.blend")
    status = {}
    for p in placements.values():
        status[p.get("status")] = status.get(p.get("status"), 0) + 1
    log = {"status": "ok", "exit_code": 0, "wall_s": round(time.time() - t0, 1), "arm": "P0", "inventory": inventory_name,
           "n_items": len(items), "n_targets": len(targets), "placement_status": status,
           "n_accepted": status.get("accepted", 0), "usage": {}, "blend_ok": blend}
    (run_dir / "run_log.json").write_text(json.dumps(log, indent=1) + "\n")
    return log


def assemble_blend(objs: list, placements: dict, out_blend: Path) -> bool:
    """Blender 无界面：接受的网格按 blender_snippet 的方式导入，其余物体放长方体。返回是否成功。"""
    from smallobj.export_blend import BLENDER
    spec = out_blend.with_suffix(".assemble.json")
    spec.write_text(json.dumps({"objects": objs, "meshes": {k: {"mesh_glb": v["mesh_glb"], "matrix_world": v["matrix_world"]}
                                                           for k, v in placements.items() if v.get("status") == "accepted"},
                                "out": str(out_blend)}))
    cp = subprocess.run([str(BLENDER), "-b", "--factory-startup", "--python", str(PROJ / "scripts" / "blender_assemble.py"),
                         "--", str(spec)], capture_output=True, text=True)
    (out_blend.with_suffix(".assemble.log")).write_text(cp.stdout[-5000:] + cp.stderr[-5000:])
    return cp.returncode == 0 and out_blend.exists()
