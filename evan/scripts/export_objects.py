"""给仿真同学的逐物体交接记录：每次运行写一份 <run>/objects.json（内容和容差见 smallobj.handoff）。

只读 <run>/export/objects.json（没有就跳过，不在这里跑 Blender 导出）、inventory_decisions.json 和感知目录的 hd/cameras.json；
不碰 .blend、不重新打分。
用法：PYTHONPATH=src .runtime/venv/bin/python scripts/export_objects.py runs/A2-claude/42897538/0 [更多运行目录 ...]
"""
import sys
from pathlib import Path

from smallobj import handoff


def main(run_dirs):
    total = {"instances": 0, "on_floor": 0, "on_instance": 0, "no_support": 0}
    for run in (Path(r).resolve() for r in run_dirs):
        if not (run / "export" / "objects.json").exists():
            print(f"{run}：没有 export/objects.json，跳过", flush=True)
            continue
        out = handoff.write(run)
        c = out["counts"]
        objs = out["objects"]
        n_in = sum(o["support"] is None and o["inside"] is not None for o in objs)
        n_views = sum(bool(o["views"]) for o in objs)
        inv = "—" if objs and objs[0]["from_inventory"] is None else str(sum(bool(o["from_inventory"]) for o in objs))
        print(f"{out['run']}：{c['instances']} 个实例，地面 {c['on_floor']}，放在别的实例上 {c['on_instance']}，"
              f"无支撑 {c['no_support']}（其中在别的实例的框里 {n_in}）；来自清单 {inv}；有源帧 {n_views}", flush=True)
        for k in total:
            total[k] += c[k]
    print("合计：", total)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
