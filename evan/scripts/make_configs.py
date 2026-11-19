"""生成 configs/splits.json 和 configs/thresholds.json（只跑一次，之后不改）。"""
import json
import sys
from pathlib import Path

from smallobj import configs

root = Path(__file__).resolve().parent.parent / "configs"
root.mkdir(exist_ok=True)
for name, data in (("splits.json", configs.make_splits(configs.CA1M_IDS)), ("thresholds.json", configs.default_thresholds())):
    p = root / name
    if p.exists() and "--force" not in sys.argv:
        print(f"{p} 已存在，不覆盖")
        continue
    p.write_text(json.dumps(data, indent=1) + "\n")
    print(f"写了 {p}")
