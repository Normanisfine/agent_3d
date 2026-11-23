"""对一个 gen3d.prepare_sam3d_job 目录跑 SAM 3D Objects。

在 Colab A100 上用官方环境跑（notebooks/sam3d_colab.ipynb）：官方环境是 torch 2.5.1+cu121，没有 Blackwell
（Betty 的 B200、笔记本的 RTX 50 系）的内核，见 docs/research/05-scenerig.md。
用法（SAM 3D 的环境里）：python sam3d_job.py <job_dir> <sam-3d-objects 仓库目录> [--seed 7]
每个物体写 <job_dir>/<item>/：
  mesh_cam.glb        摆好位姿的网格，OpenCV 相机坐标（x 右、y 下、z 前，单位同点图）；本地乘这一帧的 c2w 就到房间坐标
  mesh_canonical.glb  SAM 3D 原始输出的网格（Y 朝上，没乘位姿）
  splat.ply           高斯泼溅（有的话）
  pose.json           SAM 3D 原始位姿：rotation（四元数 wxyz）、translation、scale，都在 PyTorch3D 相机坐标
  status.json
坐标约定照 SceneRig（MIT，lib/tools/sam3d/sam3d_worker.py，commit 2defb4b）：
  - 点图传进去之前从 OpenCV 相机坐标转到 PyTorch3D 相机坐标（x、y 取反）——传了 pointmap，SAM 3D 就不再替你转；
  - 输出网格先 Y 朝上转 Z 朝上，倒着的翻正，再乘位姿（scale → rotate → translate），最后 x、y 取反回到 OpenCV。
"""
import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

# SAM 3D 的 notebook/inference.py 一导入就读 CONDA_PREFIX（默认环境已激活）；我们直接用环境里的 python 跑，没有激活
os.environ.setdefault("CONDA_PREFIX", sys.prefix)
job, repo = Path(sys.argv[1]), Path(sys.argv[2])
seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 7
sys.path.insert(0, str(repo / "notebook"))
import torch  # noqa: E402
from inference import Inference, load_image  # noqa: E402
from PIL import Image  # noqa: E402
from pytorch3d.transforms import Transform3d, quaternion_to_matrix  # noqa: E402

CV_P3D = torch.tensor([-1.0, -1.0, 1.0])  # OpenCV 相机 ↔ PyTorch3D 相机：x、y 取反（两个方向一样）
R_YUP_TO_ZUP = torch.tensor([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=torch.float32)


def posed_vertices(vertices, rotation, translation, scale):
    """照 SceneRig 的 transform_mesh_vertices：网格局部坐标 → PyTorch3D 相机坐标。"""
    v = torch.as_tensor(np.asarray(vertices), dtype=torch.float32).unsqueeze(0) @ R_YUP_TO_ZUP
    R = quaternion_to_matrix(rotation)
    if float(R[2, 1]) < 0:  # 局部 +Z 朝下：重建倒了，绕 Y 或 X 转 180°
        if float(R[1, 2]) > 0:
            v[..., 0] *= -1.0
            v[..., 2] *= -1.0
        else:
            v[..., 1] *= -1.0
            v[..., 2] *= -1.0
    tfm = Transform3d(dtype=v.dtype).scale(scale).rotate(R).translate(translation[0], translation[1], translation[2])
    return tfm.transform_points(v)[0]


model = Inference(str(repo / "checkpoints" / "hf" / "pipeline.yaml"), compile=False)
for it in json.loads((job / "inputs.json").read_text()):
    out = job / it["item_id"]
    out.mkdir(exist_ok=True)
    t0 = time.time()
    try:
        image = load_image(str(job / it["rgba"]))[..., :3]
        mask = np.asarray(Image.open(job / it["mask"])) > 0
        pm = torch.from_numpy(np.nan_to_num(np.load(job / it["pointmap"]), nan=0.0).astype(np.float32)) * CV_P3D
        res = model(image, mask, seed=seed, pointmap=pm)
        if res.get("gs") is not None:
            res["gs"].save_ply(str(out / "splat.ply"))
        S, T = res["scale"][0].cpu().float(), res["translation"][0].cpu().float()
        R = res["rotation"].squeeze().cpu().float()
        (out / "pose.json").write_text(json.dumps({"rotation_wxyz": R.tolist(), "translation": T.tolist(),
                                                   "scale": S.reshape(-1).tolist(), "frame": "pytorch3d_camera"}) + "\n")
        mesh = res.get("glb")
        if mesh is not None:
            mesh.export(str(out / "mesh_canonical.glb"))
            mesh.vertices = (posed_vertices(mesh.vertices, R, T, S) * CV_P3D).numpy().astype(np.float32)
            mesh.export(str(out / "mesh_cam.glb"))
        status = {"status": "ok" if mesh is not None else "no_mesh", "seconds": round(time.time() - t0, 1)}
    except Exception:  # noqa: BLE001 — 单个物体失败不影响其他物体
        status = {"status": "backend_error", "error": traceback.format_exc()[-800:]}
    (out / "status.json").write_text(json.dumps(status) + "\n")
    print(it["item_id"], status["status"], status.get("seconds", ""), flush=True)
