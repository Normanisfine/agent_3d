import numpy as np
import trimesh

from smallobj import boxes, gen3d, place, silhouette

K = [[500.0, 0, 320.0], [0, 500.0, 240.0], [0, 0, 1]]
GATE = {"sil_iou_min": 0.6, "sil_margin": 0.03, "chamfer_min_m": 0.015, "chamfer_rel": 0.1,
        "size_ratio": [0.75, 1.25], "penetration_max_m": 0.01}


def look_at(eye, target):
    """OpenCV 相机（x 右、y 下、z 前）放在 eye、看向 target，世界 z 朝上。"""
    z = np.subtract(target, eye); z = z / np.linalg.norm(z)
    x = np.cross(z, [0, 0, 1.0]); x = x / np.linalg.norm(x)
    y = np.cross(z, x)
    T = np.eye(4); T[:3, :3] = np.stack([x, y, z], 1); T[:3, 3] = eye
    return T


def l_shape():
    a = trimesh.creation.box(extents=(1.0, 0.4, 0.4)); a.apply_translation((0, 0, 0.2))
    b = trimesh.creation.box(extents=(0.4, 0.4, 1.0)); b.apply_translation((-0.3, 0, 0.5))
    return gen3d.clean_mesh(trimesh.util.concatenate([a, b]), up="z")


def scene(mesh, yaw=0.5, s=0.3, t=(1.0, 2.0, 0.0), seed=0):
    """把规范网格按已知位姿摆好，3 台相机拍：返回 views、观测点（带 3 mm 噪声）、真值摆放后的网格。"""
    rng = np.random.default_rng(seed)
    placed = mesh.copy()
    placed.apply_scale(s)
    placed.apply_transform(trimesh.transformations.rotation_matrix(yaw, [0, 0, 1]))
    placed.apply_translation(t)
    c = placed.bounds.mean(0)
    views, obs = [], []
    pts, fidx = trimesh.sample.sample_surface(placed, 20000, seed=seed)
    for ang in (0.3, 1.6, 2.9):
        eye = c + [1.2 * np.cos(ang), 1.2 * np.sin(ang), 0.5]
        T = look_at(eye, c)
        views.append({"K": K, "c2w": T.tolist(), "size_wh": (640, 480),
                      "mask": silhouette.render_mask(pts, K, T, (640, 480))})
        normals_ok = np.einsum("ij,ij->i", placed.face_normals[fidx[:3000]], pts[:3000] - eye) < 0  # 朝向这台相机的面
        obs.append(pts[:3000][normals_ok])
    obs = np.concatenate(obs) + rng.normal(0, 0.003, (sum(len(o) for o in obs), 3))
    return views, obs, placed


def perturbed_item(placed, yaw):
    b = boxes.fit_obb(placed.vertices, object_id="it", category="thing")
    b["center"] = (np.asarray(b["center"]) + [0.05, 0.0, 0.0]).tolist()
    b["yaw"] = float(b["yaw"] + np.radians(20))
    b["size"] = (np.asarray(b["size"]) * 1.1).tolist()
    return b


def test_place_recovers_pose():
    mesh = l_shape()
    views, obs, placed = scene(mesh)
    item = perturbed_item(placed, 0.5)
    res = place.fit(mesh, item, views, obs, gate=GATE, dof=7, support_z=0.0)
    assert res["status"] == "accepted", res["fit"]
    M = np.asarray(res["matrix_world"])
    got = trimesh.transform_points(mesh.vertices, M)
    assert np.linalg.norm(got.mean(0) - placed.vertices.mean(0)) < 0.02
    assert abs(np.linalg.norm(M[:3, 0]) - 0.3) < 0.3 * 0.03
    yaw = np.arctan2(M[1, 0], M[0, 0])
    assert abs(boxes.wrap(yaw - 0.5)) < np.radians(5)


def test_wrong_shape_rejected():
    views, obs, placed = scene(l_shape())
    sphere = gen3d.clean_mesh(trimesh.creation.icosphere(subdivisions=3), up="z")
    res = place.fit(sphere, perturbed_item(placed, 0.5), views, obs, gate=GATE, dof=7, support_z=0.0)
    assert res["status"] == "rejected_fit"


def test_gate_size_and_penetration():
    fit = {"sil_iou_mean": 0.8, "primitive_sil_iou": 0.6, "chamfer_obs2mesh_cm": 0.5}
    assert place.gate(fit, [1.0, 1.0, 1.0], 0.0, 0.2, GATE)
    assert not place.gate(fit, [1.3, 1.0, 1.0], 0.0, 0.2, GATE)
    assert not place.gate(fit, [1.0, 1.0, 1.0], 0.02, 0.2, GATE)
    assert not place.gate(dict(fit, primitive_sil_iou=0.79), [1.0, 1.0, 1.0], 0.0, 0.2, GATE)


def test_backend_pose_to_world():
    # 相机坐标系下的位姿（四元数 wxyz、平移、各向同性尺度）+ c2w → 世界变换：物体原点落在 c2w·t，尺度保持
    c2w = np.eye(4)
    c2w[:3, :3] = boxes.rot_z(0.7) @ [[1, 0, 0], [0, 0, 1], [0, -1, 0]]
    c2w[:3, 3] = (1.0, 2.0, 1.5)
    q = [np.cos(0.2), 0.0, np.sin(0.2), 0.0]  # 绕相机 y 轴转 0.4 rad
    pose = {"quat_l2c": q, "trans_l2c": [0.1, -0.2, 2.0], "scale_l2c": [0.3, 0.3, 0.3]}
    M = place.backend_pose_to_world(pose, c2w, convention="opencv")
    assert np.allclose(M[:3, 3], c2w[:3, :3] @ [0.1, -0.2, 2.0] + c2w[:3, 3])
    assert np.allclose(np.linalg.norm(M[:3, :3], axis=0), 0.3)
    # PyTorch3D 约定（x 左、y 上）：相机系的 x、y 取反后再走 OpenCV
    M2 = place.backend_pose_to_world(pose, c2w, convention="pytorch3d")
    assert np.allclose(M2[:3, 3], c2w[:3, :3] @ [-0.1, 0.2, 2.0] + c2w[:3, 3])


def test_place_stays_near_inventory_box_with_outliers():
    # 10-26 实测：观测点里混进远处的点时 ICP 的尺度更新会把物体甩出几米（toy b033 落到地板下 4 m）。
    # 期望：位置始终约束在清单框附近，尺度更新被夹住时平移也按夹住后的尺度算。
    mesh = l_shape()
    views, obs, placed = scene(mesh)
    rng = np.random.default_rng(1)
    far = placed.vertices.mean(0) + [0.0, 0.0, -3.0] + rng.normal(0, 0.5, (len(obs) // 2, 3))
    item = perturbed_item(placed, 0.5)
    res = place.fit(mesh, item, views, np.concatenate([obs, far]), gate=GATE, dof=7, support_z=None)
    got = np.asarray(res["placed_box"]["center"])
    assert np.linalg.norm(got - np.asarray(item["center"])) < 0.3, got


def test_fit_backend_refines_generator_pose():
    # SAM 3D 的网格带着它自己的位姿进房间坐标（SceneRig：保留生成的形状和朝向，只锚定位置和尺度）：
    # init="backend" 从这个位姿起步只做小范围微调，不再从清单框重新搜索朝向
    mesh = l_shape()
    views, obs, placed = scene(mesh)
    backend = placed.copy()
    c = backend.bounds.mean(0)
    backend.apply_translation(-c)
    backend.apply_scale(1.08)
    backend.apply_transform(trimesh.transformations.rotation_matrix(np.radians(6), [0, 0, 1]))
    backend.apply_translation(c + [0.03, -0.02, 0.0])
    res = place.fit(backend, perturbed_item(placed, 0.5), views, obs, gate=GATE, dof=7, support_z=0.0, init="backend")
    assert res["status"] == "accepted", res["fit"]
    M = np.asarray(res["matrix_world"])
    got = trimesh.transform_points(backend.vertices, M)
    assert np.linalg.norm(got.mean(0) - placed.vertices.mean(0)) < 0.02
    assert abs(np.linalg.norm(M[:3, 0]) - 1 / 1.08) < 0.03
