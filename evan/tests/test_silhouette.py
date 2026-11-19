import numpy as np
import trimesh

from smallobj import silhouette


def test_render_mask_matches_projection():
    K = [[500.0, 0, 320.0], [0, 500.0, 240.0], [0, 0, 1]]
    cube = trimesh.creation.box(extents=(1, 1, 1))
    cube.apply_translation((0, 0, 2.0))  # 相机坐标系里正前方 2 m（c2w = 单位阵）
    m = silhouette.render_mask(cube.sample(20000, seed=0), K, np.eye(4), (640, 480))
    ys, xs = np.nonzero(m)
    uv = cube.vertices[:, :2] / cube.vertices[:, 2:] * 500 + [320, 240]
    assert abs(xs.min() - uv[:, 0].min()) <= 3 and abs(xs.max() - uv[:, 0].max()) <= 3
    assert abs(ys.min() - uv[:, 1].min()) <= 3 and abs(ys.max() - uv[:, 1].max()) <= 3
    assert silhouette.iou(m, m) == 1.0 and silhouette.iou(m, ~m) == 0.0
