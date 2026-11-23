"""把清单 v2 整理成给 agent 的逐项清单（A5 用）：perception/<id>/inventory_v2.json → inventory_v2_list.json，并裁图。

阈值读 configs/checklist.json（开发集上选定的那一组，见 results/inventory_v2_checklist_dev.md；定稿后不再改）。
只按几何整理，不读真值、不打分。用法：PYTHONPATH=src .runtime/venv/bin/python scripts/build_checklist.py <scene_id> ...
"""
import json
import sys
from pathlib import Path

from smallobj import checklist, inventory

PROJ = Path(__file__).resolve().parent.parent


def main(scene_ids):
    cfg = json.loads((PROJ / "configs" / "checklist.json").read_text())
    for sid in scene_ids:
        P = PROJ / "perception" / sid
        entries = checklist.build(inventory.load(P / "inventory_v2.json"), **cfg)
        (P / "inventory_v2_list.json").write_text(json.dumps(entries, ensure_ascii=False, indent=1) + "\n")
        out = checklist.export_crops(sid, root=PROJ)
        print(f">> {sid}: 清单 v2 {len(inventory.load(P / 'inventory_v2.json'))} 条 → 逐项清单 {len(entries)} 条，裁图在 {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
