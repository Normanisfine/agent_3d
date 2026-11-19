"""在 Betty 上对一个 gen3d.prepare_sam3d_job 目录跑 SAM 3D Objects（**未在集群上测试**，第一次跑完回来改）。

用法（SAM 3D 的环境里）：python sam3d_job.py <job_dir> <sam-3d-objects 仓库目录> [--seed 7]
每个物体写 <job_dir>/<item>/{splat.ply, mesh.glb（如果输出里有）, pose.json, status.json}。
pose.json = {"quat_l2c": wxyz, "trans_l2c": [3], "scale_l2c": [3]}，坐标约定见 place.backend_pose_to_world。
"""
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np

job, repo = Path(sys.argv[1]), Path(sys.argv[2])
seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 7
sys.path.insert(0, str(repo / "notebook"))
import torch  # noqa: E402
from inference import Inference, load_image  # noqa: E402
from PIL import Image  # noqa: E402

model = Inference(str(repo / "checkpoints" / "hf" / "pipeline.yaml"), compile=False)
for it in json.loads((job / "inputs.json").read_text()):
    out = job / it["item_id"]
    out.mkdir(exist_ok=True)
    t0 = time.time()
    try:
        image = load_image(str(job / it["rgba"]))[..., :3]
        mask = np.asarray(Image.open(job / it["mask"])) > 0
        pm = torch.from_numpy(np.nan_to_num(np.load(job / it["pointmap"]), nan=0.0))
        res = model(image, mask, seed=seed, pointmap=pm)
        res["gs"].save_ply(str(out / "splat.ply"))
        if res.get("glb") is not None:
            res["glb"].export(str(out / "mesh.glb"))
        to = lambda v: np.asarray(v.detach().cpu() if hasattr(v, "detach") else v, float).reshape(-1).tolist()  # noqa: E731
        (out / "pose.json").write_text(json.dumps({"quat_l2c": to(res["rotation"]), "trans_l2c": to(res["translation"]),
                                                    "scale_l2c": to(res["scale"])}) + "\n")
        status = {"status": "ok", "seconds": round(time.time() - t0, 1)}
    except Exception:  # noqa: BLE001 — 单个物体失败不影响其他物体
        status = {"status": "backend_error", "error": traceback.format_exc()[-800:]}
    (out / "status.json").write_text(json.dumps(status) + "\n")
    print(it["item_id"], status["status"], flush=True)
