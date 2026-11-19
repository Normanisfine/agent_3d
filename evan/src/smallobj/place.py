"""`place_mesh`：把生成的规范网格摆进场景（02 号笔记 §7.2 的做法：初始化 → ICP → 剪影坐标搜索 → 验收）。

规范网格来自 gen3d.clean_mesh：Z 朝上、最长边 1、原点在底面中心。位姿参数是 (x, y, z_底面, yaw, s)：
世界点 = Rz(yaw) · (s · L_u) + t，L_u 是换了朝上轴（5 种之一）再放回底面中心的网格点。
核心是纯函数 fit()；place_mesh() 只负责从 perception/ 和 gen/ 读文件，再调 fit()。
"""
import json
import time
from pathlib import Path

import numpy as np

from smallobj import align, boxes, silhouette

PROJ = Path(__file__).resolve().parents[2]
W_MIN_IOU, W_CHAMFER = 0.35, 0.12  # 目标 = (1 − 平均 IoU) + 0.35 (1 − 最差 IoU) + 0.12 · 归一化 Chamfer


def _rx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _ry(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


# 朝上轴候选：原样，加 4 个横躺的方向
UPS = [np.eye(3), _rx(np.pi / 2), _rx(-np.pi / 2), _ry(np.pi / 2), _ry(-np.pi / 2)]


def _bottom_centered(pts):
    lo, hi = pts.min(0), pts.max(0)
    c = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
    return pts - c, c


def gate(fit: dict, size_ratio, penetration_m: float, longest_m: float, gate: dict) -> bool:
    """验收（设计 §6）：剪影 IoU 够高且比方块版高出 margin；Chamfer 够小；尺寸在框的范围内；不穿进支撑面。"""
    lo, hi = gate["size_ratio"]
    return (fit["sil_iou_mean"] >= max(gate["sil_iou_min"], fit["primitive_sil_iou"] + gate["sil_margin"])
            and fit["chamfer_obs2mesh_cm"] / 100 <= max(gate["chamfer_min_m"], gate["chamfer_rel"] * longest_m)
            and all(lo <= r <= hi for r in size_ratio)
            and penetration_m <= gate["penetration_max_m"])


class _Problem:
    def __init__(self, mesh, views, obs, n_samples=20000, n_chamfer=4000):
        from scipy.spatial import cKDTree  # noqa: F401
        base = mesh.sample(n_samples, seed=0)
        self.samples, self.offsets = [], []
        for R in UPS:
            L, c = _bottom_centered(base @ R.T)
            self.samples.append(L)
            self.offsets.append(c)
        self.n_chamfer = n_chamfer
        self.obs = np.asarray(obs, float)
        self.views = []
        for v in views:
            m = np.asarray(v["mask"], bool)
            ys, xs = np.nonzero(m)
            W, H = v["size_wh"]
            w, h = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
            px, py = max(20, int(0.5 * w)), max(20, int(0.5 * h))
            roi = (max(0, xs.min() - px), max(0, ys.min() - py), min(W, xs.max() + 1 + px), min(H, ys.max() + 1 + py))
            self.views.append({**v, "roi": roi, "mask_roi": m[roi[1]:roi[3], roi[0]:roi[2]]})

    @staticmethod
    def world(L, yaw, s, t):
        return (np.asarray(s) * L) @ boxes.rot_z(yaw).T + t

    def ious(self, P):
        out = []
        for v in self.views:
            pred = silhouette.render_mask(P, v["K"], v["c2w"], v["size_wh"], roi=v["roi"])
            out.append(silhouette.iou(pred, v["mask_roi"]) * (1 - silhouette.outside_fraction(P, v["K"], v["c2w"], v["roi"])))
        return np.array(out)

    def chamfer(self, P):
        from scipy.spatial import cKDTree
        if len(self.obs) == 0:
            return 0.0, 1.0
        d = cKDTree(P[: self.n_chamfer]).query(self.obs)[0]
        d = np.sort(d)[: max(1, int(0.9 * len(d)))]  # 截掉最远的 10%（掩码边缘混进来的背景点）
        return float(d.mean()), d

    def objective(self, u, yaw, s, t):
        P = self.world(self.samples[u], yaw, s, t)
        io = self.ious(P)
        ch, _ = self.chamfer(P)
        longest = float(np.max(np.asarray(s) * np.ptp(self.samples[u], 0)))
        return (1 - io.mean()) + W_MIN_IOU * (1 - io.min()) + W_CHAMFER * min(ch / max(longest, 0.05), 1.0)

    def icp(self, u, yaw, s, t, s_bounds, support_z, t0, max_move, iters=10):
        """每步解一个只绕 z 轴的相似变换。尺度被夹住时，平移按夹住后的尺度重算（10-26 修：以前用没夹的尺度，
        物体会被甩出几米）；位置离起点超过 max_move 就停在上一步。"""
        from scipy.spatial import cKDTree
        if len(self.obs) < 10:
            return yaw, s, t
        for _ in range(iters):
            P = self.world(self.samples[u][: self.n_chamfer], yaw, s, t)
            d, idx = cKDTree(P).query(self.obs)
            keep = d <= np.quantile(d, 0.8)
            src, dst = P[idx[keep]], self.obs[keep]
            ds, dR, _ = align.align_sim3(src, dst, gravity=True, with_scale=True)
            s_new = float(np.clip(s * ds, *s_bounds)) if ds > 0 else s
            ds = s_new / s
            dt = dst.mean(0) - ds * dR @ src.mean(0)
            t_new = ds * dR @ t + dt
            if support_z is not None:
                t_new[2] = support_z
            if np.linalg.norm(t_new - t0) > max_move:
                break
            yaw, s, t = float(yaw + np.arctan2(dR[1, 0], dR[0, 0])), s_new, t_new
        return yaw, s, t


def fit(mesh, item: dict, views: list, obs, gate: dict, dof: int = 7, support_z=None) -> dict:
    """在 views（每个有 K、c2w、size_wh、mask）和观测点 obs 上找网格的位姿并验收，返回 PlacementResult 的几何部分。"""
    size = np.asarray(item["size"], float)
    s0 = float(size.max())
    obs = np.asarray(obs, float).reshape(-1, 3)
    # 只用清单框附近的观测点（掩码边缘可能混进远处背景的深度）
    near = np.linalg.norm(obs - np.asarray(item["center"], float), axis=1) <= max(0.3, 1.5 * s0)
    prob = _Problem(mesh, views, obs[near])
    max_move = max(0.5, 2.0 * s0)  # 位置离清单框的起点最多挪这么远
    s_bounds = (0.75 * s0, 1.25 * s0)
    t0 = np.array([item["center"][0], item["center"][1], item["center"][2] - size[2] / 2])
    if support_z is not None:
        t0[2] = support_z
    # 1) 粗搜：5 个朝上轴 × 每 10° 一个 yaw
    starts = sorted((prob.objective(u, np.radians(a), s0, t0), u, np.radians(a)) for u in range(len(UPS)) for a in range(0, 360, 10))
    best = None
    for _, u, yaw in starts[:3]:
        # 2) ICP，3) 有界坐标搜索（x, y, [z], yaw, s），步长减半 4 次
        yaw, s, t = prob.icp(u, yaw, s0, t0.copy(), s_bounds, support_z, t0, max_move)
        cur = prob.objective(u, yaw, s, t)
        L = s0
        steps = [0.1 * L, 0.1 * L, 0.05 * L, np.radians(10), 0.05 * s0]
        for _ in range(4):
            for dim, st in enumerate(steps):
                if dim == 2 and support_z is not None:
                    continue
                for sign in (1, -1):
                    yaw2, s2, t2 = yaw, s, t.copy()
                    if dim < 3:
                        t2[dim] += sign * st
                    elif dim == 3:
                        yaw2 += sign * st
                    else:
                        s2 = float(np.clip(s + sign * st, *s_bounds))
                    if np.linalg.norm(t2 - t0) > max_move:
                        continue
                    o = prob.objective(u, yaw2, s2, t2)
                    if o < cur:
                        cur, yaw, s, t = o, yaw2, s2, t2
                        break
            steps = [x / 2 for x in steps]
        if best is None or cur < best[0]:
            best = (cur, u, yaw, s, t)
    _, u, yaw, s, t = best
    P = prob.world(prob.samples[u], yaw, s, t)
    io = prob.ious(P)
    ch, d = prob.chamfer(P)
    # 方块版：把清单框本身当网格，用同样的帧和渲染方式
    import trimesh
    box = trimesh.creation.box(extents=size)
    box.apply_transform(np.block([[boxes.rot_z(item["yaw"]), np.asarray(item["center"], float)[:, None]], [np.zeros((1, 3)), np.ones((1, 1))]]))
    prim = prob.ious(box.sample(20000, seed=0))
    Rz = boxes.rot_z(yaw)
    A = Rz @ (s * UPS[u])
    M = np.eye(4)
    M[:3, :3] = A
    M[:3, 3] = t - Rz @ (s * prob.offsets[u])
    placed = mesh.vertices @ A.T + M[:3, 3]
    ob = boxes.fit_obb(placed)
    hs, hi = sorted(ob["size"][:2]), sorted(size[:2])
    ratio = [hs[0] / hi[0], hs[1] / hi[1], ob["size"][2] / size[2]]
    longest = float(max(ob["size"]))
    pen = max(0.0, support_z - placed[:, 2].min()) if support_z is not None else 0.0
    tol = max(gate["chamfer_min_m"], gate["chamfer_rel"] * longest)
    fitd = {"sil_iou_mean": float(io.mean()), "sil_iou_min": float(io.min()), "n_views": len(views),
            "chamfer_obs2mesh_cm": 100 * ch, "primitive_sil_iou": float(prim.mean()),
            "inlier_ratio": float((np.asarray(d) <= tol).mean()) if len(prob.obs) else 0.0,
            "size_ratio": [float(r) for r in ratio], "penetration_m": float(pen), "up_index": int(u)}
    ok = gate_fn(fitd, ratio, pen, longest, gate)
    return {"status": "accepted" if ok else "rejected_fit", "matrix_world": M.tolist(),
            "scale_xyz": [float(s)] * 3, "fit": fitd, "placed_box": ob}


gate_fn = gate


def blender_snippet(mesh_glb: str, M) -> str:
    """粘进 bpy 就能用：导入 GLB（Blender 会把 glTF 的 Y 朝上转成 Z 朝上，所以先把这一步转回去），再设 matrix_world。"""
    rows = ", ".join("(" + ", ".join(f"{v:.6f}" for v in r) + ")" for r in np.asarray(M))
    return ("import bpy\nfrom mathutils import Matrix\n"
            f"bpy.ops.import_scene.gltf(filepath={str(mesh_glb)!r})\n"
            "obj = bpy.context.selected_objects[0]\n"
            "C_inv = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))  # 抵消导入时的 Y→Z 转换\n"
            f"obj.matrix_world = Matrix(({rows})) @ C_inv\n")


def place_mesh(scene_id: str, item_id: str, candidate_id: int, init: str = "obb", dof: int = 7, support_z=None,
               inventory: str = "inventory.json", root: Path = PROJ) -> dict:
    """读 perception/<id>/（高清帧、深度、掩码、清单）和 gen/<id>/<item>/c<k>/，调 fit()，写 placement.json。"""
    import trimesh
    from PIL import Image

    from smallobj import clean_inventory, gen3d, hd
    t_start = time.time()
    root = Path(root)
    P, cdir = root / "perception" / scene_id, root / "gen" / scene_id / item_id / f"c{candidate_id}"
    meta = json.loads((cdir / "gen.json").read_text()) if (cdir / "gen.json").exists() else {"status": "no_view"}
    base = {"object_id": item_id, "candidate_id": candidate_id, "backend": meta.get("backend"),
            "frame": meta.get("frame"), "seed": meta.get("seed"), "mesh_glb": meta.get("mesh_glb"),
            "input": {"mask_px": meta.get("mask_px")}}
    if meta.get("status") != "ok":
        res = {**base, "status": meta.get("status", "backend_error")}
        return res
    items = {it["item_id"]: it for it in json.loads((P / inventory).read_text())}
    cams = hd.load(P / "hd")
    by_frame = {int(f["source_frame"]): f for f in cams["frames"]}
    mdir = P / gen3d.mask_dir(inventory)
    entries = [m for m in json.loads((mdir / "index.json").read_text()) if m["item_id"] == item_id and m.get("status") == "ok"]
    entries = sorted(entries, key=lambda m: -m["mask_px"])[:5]
    views, obs = [], []
    for m in entries:
        f = by_frame[int(m["frame"])]
        mask = np.asarray(Image.open(mdir / m["mask"])) > 0
        views.append({"K": f["K"], "c2w": f["c2w"], "size_wh": cams["size_wh"], "mask": mask})
        depth = np.load(P / "hd" / "depth" / f"{int(m['frame']):06d}.npy")
        obs.append(clean_inventory.points_from_mask(mask, depth, f["K"], f["c2w"]))
    obs = np.concatenate(obs) if obs else np.zeros((0, 3))
    if len(obs) > 6000:
        obs = obs[np.random.default_rng(0).choice(len(obs), 6000, replace=False)]
    gate_cfg = json.loads((root / "configs" / "gen_gate.json").read_text()) if (root / "configs" / "gen_gate.json").exists() \
        else json.loads((PROJ / "configs" / "gen_gate.json").read_text())
    mesh = trimesh.load(meta["mesh_glb"], force="mesh")
    res = {**base, **fit(mesh, items[item_id], views, obs, gate=gate_cfg, dof=dof, support_z=support_z)}
    res["seconds"] = {"place": round(time.time() - t_start, 1), "gen": meta.get("seconds")}
    res["blender_snippet"] = blender_snippet(meta["mesh_glb"], res["matrix_world"])
    (cdir / "placement.json").write_text(json.dumps(res, indent=1) + "\n")
    return res


def backend_pose_to_world(pose: dict, c2w, convention: str = "opencv") -> np.ndarray:
    """SAM 3D 给的"物体局部 → 相机"位姿（quat_l2c 为 wxyz、trans_l2c、scale_l2c）接上高清帧的 c2w，得到局部 → 世界的 4×4。

    convention：SAM 3D 的相机坐标是 OpenCV（x 右、y 下）还是 PyTorch3D（x 左、y 上）尚未核实（设计 §13），
    拿到第一批 Betty 输出后用剪影叠图确认，再固定。
    """
    from scipy.spatial.transform import Rotation
    w, x, y, z = pose["quat_l2c"]
    A = Rotation.from_quat([x, y, z, w]).as_matrix() @ np.diag(np.broadcast_to(np.asarray(pose["scale_l2c"], float), 3))
    t = np.asarray(pose["trans_l2c"], float)
    if convention == "pytorch3d":
        F = np.diag([-1.0, -1.0, 1.0])
        A, t = F @ A, F @ t
    elif convention != "opencv":
        raise ValueError(convention)
    L2C = np.eye(4)
    L2C[:3, :3], L2C[:3, 3] = A, t
    return np.asarray(c2w, float) @ L2C
