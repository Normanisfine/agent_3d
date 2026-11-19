"""在我们的高清帧上跑 Boxer（在 .runtime/boxer/venv 里运行，不改 Boxer 的代码）。

用法：python run_hd.py <hd_dir> <out_dir> <labels逗号分隔>
用自己的 HDLoader 换掉 run_boxer 里的 CALoader：帧、内参、位姿、深度全部来自 perception/<id>/hd/
（Pi3X 位姿和深度），不读 CA-1M 的真值位姿和激光深度。输出 <out_dir>/hd/boxer_3dbbs{,_fused}.csv。
"""
import json
import os
import sys
from pathlib import Path

HD_DIR = Path(sys.argv[1]).resolve()  # chdir 之前先转成绝对路径
OUT = str(Path(sys.argv[2]).resolve())
LABELS = sys.argv[3]
BOXER = Path(__file__).resolve().parents[2] / "third_party" / "boxer"
sys.path.insert(0, str(BOXER))
os.chdir(BOXER)

import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402

import run_boxer  # noqa: E402
from loaders.base_loader import BaseLoader  # noqa: E402
from utils.tw.camera import CameraTW  # noqa: E402
from utils.tw.obb import ObbTW  # noqa: E402
from utils.tw.pose import PoseTW  # noqa: E402



class HDLoader(BaseLoader):
    def __init__(self, seq_name, start_frame=0, skip_frames=1, max_frames=99999, resize=None, num_samples=100000):
        cams = json.loads((HD_DIR / "cameras.json").read_text())
        self.frames = cams["frames"][start_frame::skip_frames][:max_frames]
        self.length, self.index = len(self.frames), 0
        self.camera, self.device_name, self.resize = "rgb", "ipad", resize
        self.num_samples = num_samples
        # 10 fps 合成视频：帧号 × 0.1 s
        self.timestamp_ns = torch.tensor([int(f["source_frame"]) * 100_000_000 for f in self.frames])
        self._init_prefetch()

    def load(self, idx):
        f = self.frames[idx]
        s = int(f["source_frame"])
        img = np.array(Image.open(HD_DIR / "frames" / f"{s:06d}.png").convert("RGB"))
        H, W = img.shape[:2]
        K = np.asarray(f["K"], float)
        c2w = np.asarray(f["c2w"], float)
        cam = CameraTW.from_surreal(width=W, height=H, type_str="pinhole",
                                    params=torch.tensor([K[0, 0], K[1, 1], K[0, 2], K[1, 2]], dtype=torch.float32))
        T_wc = PoseTW.from_Rt(torch.tensor(c2w[:3, :3], dtype=torch.float32), torch.tensor(c2w[:3, 3], dtype=torch.float32))
        depth = np.nan_to_num(np.load(HD_DIR / "depth" / f"{s:06d}.npy"), nan=0.0).astype(np.float32)
        sdp_w = self.sdp_from_depth(depth, K[0, 0], K[1, 1], K[0, 2], K[1, 2],
                                    c2w[:3, :3].astype(np.float32), c2w[:3, 3].astype(np.float32), self.num_samples)
        img_t = self.img_to_tensor(img)
        if self.resize is not None:
            rh, rw = self.resize if isinstance(self.resize, (tuple, list)) else (self.resize, self.resize)
            img_t = torch.nn.functional.interpolate(img_t, size=(rh, rw), mode="bilinear", align_corners=True)
            cam = cam.scale((rw / W, rh / H))
        return {"img0": img_t.float(), "cam0": cam.float(), "T_world_rig0": (T_wc @ cam.T_camera_rig).float(),
                "obbs": ObbTW(torch.zeros(0, 165)), "sdp_w": sdp_w.float(), "time_ns0": int(self.timestamp_ns[idx])}


np.random.seed(0)  # sdp_from_depth 随机抽点；固定种子，清单可复现
torch.manual_seed(0)
run_boxer.CALoader = HDLoader
sys.argv = ["run_boxer.py", "--input", "ca1m-hd", "--labels", LABELS, "--skip_viz",
            "--output_dir", OUT, "--start_n", "0"]
run_boxer.main()
# Boxer 默认的融合要求一个物体至少被检测 4 次、置信度 ≥ 0.55，那是按稠密视频定的；
# 我们只有 32 帧（间隔约 1.2 s），一个物体常常只在 2–5 帧里出现，所以只要求 1 次，置信度沿用 BoxerNet 的 0.5。
from utils.fuse_3d_boxes import fuse_obbs_from_csv  # noqa: E402

fuse_obbs_from_csv(str(Path(OUT) / "ca1m-hd" / "boxer_3dbbs.csv"), min_detections=1, conf_threshold=0.5)
