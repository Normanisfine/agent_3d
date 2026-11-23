"""把从 Betty 拉回来的感知结果里的绝对路径改成本机路径（PERCEPTION=betty 跑 agent 之前做一次）。

Betty 上的 build_reference 把自己的路径写进了 bundle 里的 json（/tmp/<用户>/ref-<id>/bundle、~/smallobj/aha-3d、~/smallobj/scenes），
本机上这些路径不存在。只改 json 里的路径字符串，不动几何和掩码；可以重复运行。
用法：.runtime/venv/bin/python scripts/betty/localize_bundle.py <scene_id> ...   改完会检查 json 里的绝对路径在本机都存在。
"""
import re
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[2]


def localize(sid: str) -> int:
    bundle = PROJ / "perception_betty" / sid / "bundle"
    rules = [(re.compile(rf"/tmp/[^/\"]+/ref-{re.escape(sid)}/bundle"), str(bundle)),
             (re.compile(r"/vast/home/[^\"]*?/smallobj/aha-3d"), str(PROJ / "third_party" / "aha-3d")),
             (re.compile(r"/vast/home/[^\"]*?/smallobj/scenes"), str(PROJ / "scenes"))]
    changed, missing = 0, []
    for f in sorted(bundle.rglob("*.json")):
        text = f.read_text()
        new = text
        for pat, to in rules:
            new = pat.sub(to, new)
        if new != text:
            f.write_text(new)
            changed += 1
        missing += [p for p in re.findall(r'"(/[^"\s]+)"', new) if not Path(p).exists()]
    print(f">> {sid}: 改了 {changed} 个文件" + (f"；本机不存在的路径 {sorted(set(missing))[:5]}" if missing else "；路径都在"))
    return len(missing)


if __name__ == "__main__":
    sys.exit(1 if sum(localize(s) for s in sys.argv[1:]) else 0)
