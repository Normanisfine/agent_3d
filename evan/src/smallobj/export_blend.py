"""从 .blend 导出每个物体的重力对齐 3D 框。

几何用 AHa-3D 自带的 `tools/layout_inspection/export_model.py` 在无界面 Blender 里导出（按祖先节点的
instance_id 分组，类别是 semantic_class，如 `furniture/tables`、`architecture/room`）。
每组取全部顶点：底面用凸包上的最小面积矩形定朝向和长宽，竖直方向取最高最低点。
坐标就是 .blend 自己的坐标（AHa-3D 对齐后的参考坐标系），之后用 align.pipeline_to_gt 变到真值坐标系。
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from smallobj import boxes

PROJ = Path(__file__).resolve().parents[2]
AHA = PROJ / "third_party" / "aha-3d"
MIN_THICKNESS = 0.01  # 扁平物体（海报、地毯、表盘数字）至少按 1 cm 厚算，避免体积为 0
BLENDER = Path(os.environ.get("BLENDER", PROJ / "third_party" / "blender-5.2.1" / "blender"))


def fit_groups(vertices, faces, face_object_id, groups):
    """groups[k] 是第 k 个导出对象的 {"id","semantic_class"}；同 id 的部件合成一个框。"""
    vertices, faces, face_object_id = np.asarray(vertices), np.asarray(faces), np.asarray(face_object_id)
    by_id = {}
    for k, g in enumerate(groups):
        by_id.setdefault(g["id"], {"cat": g.get("semantic_class", "unknown"), "objs": []})["objs"].append(k)
    recs = []
    for gid, info in by_id.items():
        mask = np.isin(face_object_id, info["objs"])
        idx = np.unique(faces[mask].ravel())
        if idx.size == 0:
            continue
        pts = vertices[idx].astype(float)
        recs.append(boxes.fit_obb(pts, object_id=gid, category=info["cat"], source="pred", min_thickness=MIN_THICKNESS))
    return recs


def export_objects(blend, out_json, cameras_json=None):
    """导出 .blend 里每个物体的框到 out_json（含结构件，评测时再用 evaluate.filter_predictions 去掉）。返回物体数。"""
    blend, out_json = Path(blend), Path(out_json)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if cameras_json is None:  # export_model 只记录这个变换，不用它变换几何
            cameras_json = tmp / "cameras.json"
            cameras_json.write_text(json.dumps({"world_transform": np.eye(4).tolist()}))
        out = tmp / "export"
        subprocess.run([str(BLENDER), "-b", str(blend), "--python",
                        str(AHA / "tools/layout_inspection/export_model.py"), "--",
                        "--out", str(out), "--cameras", str(cameras_json)],
                       check=True, capture_output=True, text=True)
        model = np.load(out / "model.npz")
        report = json.loads((out / "model.json").read_text())
        recs = fit_groups(model["vertices"], model["faces"], model["face_object_id"], report["object_groups"])
    boxes.save(recs, out_json)
    return len(recs)
