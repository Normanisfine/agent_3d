"""清单 v2 的深度（借 SceneRig 用 MoGE 做度量摆放）：MoGe-2 在 32 张高清帧上算深度，按中位比例对齐到 Pi3X 尺度。

Pi3X 深度是从 10 万像素放大上来的，小物体只占几个像素，边缘还是 NaN；MoGe-2 在 1024×768 原图上算，边缘清楚。
相机视场用 Pi3X 的内参（不让 MoGe 自己猜）。只读输入视频的帧，不碰真值。
用法：.runtime/moge/bin/python scripts/run_moge.py <scene_id> ...
输出 perception/<id>/hd/depth_moge/<帧>.npy（相机 z，房间尺度，无效为 NaN）和 depth_moge/align.json（每帧尺度、有效比例）。
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

PROJ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJ / "src"))
from smallobj import hd  # noqa: E402

MODEL = "Ruicheng/moge-2-vitl-normal"


def main():
    from moge.model.v2 import MoGeModel
    model = MoGeModel.from_pretrained(MODEL).cuda().eval()
    for sid in sys.argv[1:]:
        H = PROJ / "perception" / sid / "hd"
        out = H / "depth_moge"
        out.mkdir(exist_ok=True)
        rec = []
        for f in json.loads((H / "cameras.json").read_text())["frames"]:
            s = int(f["source_frame"])
            img = np.asarray(Image.open(H / "frames" / f"{s:06d}.png").convert("RGB"))
            fov_x = math.degrees(2 * math.atan(img.shape[1] / (2 * float(f["K"][0][0]))))
            with torch.inference_mode():
                o = model.infer(torch.from_numpy(img).float().div(255).permute(2, 0, 1).cuda(), fov_x=fov_x)
            d = o["depth"].float().cpu().numpy()
            d[~o["mask"].cpu().numpy().astype(bool)] = np.nan
            al, sc = hd.align_depth(d, np.load(H / "depth" / f"{s:06d}.npy"))
            np.save(out / f"{s:06d}.npy", al)
            rec.append({"frame": s, "scale": sc, "valid": float(np.isfinite(al).mean())})
        (out / "align.json").write_text(json.dumps({"model": MODEL, "frames": rec}, indent=1) + "\n")
        print(sid, "MoGe 尺度中位数", round(float(np.median([r["scale"] for r in rec])), 3), flush=True)


if __name__ == "__main__":
    main()
