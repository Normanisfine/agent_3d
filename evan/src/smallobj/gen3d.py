"""`gen3d_request`：给清单物体生成网格候选（02 号笔记 §7.2；设计 §6）。

流程：读掩码（scripts/sam3_objects.py box 模式写的 perception/<id>/item_masks/）→ 太小或看不到就不生成
→ 在掩码最大的几帧裁 RGBA（四周留 15%）→ 后端批量生成（子进程，模型只加载一次）→ 清理网格 → 缓存。
只读 perception/<id>/ 和 gen/，不碰 scenes/（真值）。
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from smallobj import hd

PROJ = Path(__file__).resolve().parents[2]
MIN_MASK_PX = 200
MAX_FACES = 20000
SCENE_BUDGET = 30
# 后端：名字 → 命令前缀（后面接 --batch jobs.json）
BACKENDS = {"hy3d_shape": [str(PROJ / ".runtime" / "hy3d" / "venv" / "bin" / "python"),
                           str(PROJ / "scripts" / "gen_backends" / "hy3d_shape.py")]}


def sharpness(image: np.ndarray, xyxy) -> float:
    """框内灰度的拉普拉斯方差（越大越清楚）。"""
    from scipy.ndimage import laplace
    H, W = image.shape[:2]
    x0, y0, x1, y1 = [int(round(v)) for v in xyxy]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x1 - x0 < 3 or y1 - y0 < 3:
        return 0.0
    g = image[y0:y1, x0:x1].astype(float).mean(-1) if image.ndim == 3 else image[y0:y1, x0:x1].astype(float)
    return float(laplace(g).var())


def pick_frames(item: dict, hd_cams: dict, sharp: dict, k: int = 3) -> list:
    """按"画面内面积 × (1 − 截断) × 清晰度"排序，取前 k 帧；完全看不到的帧不算。"""
    scored = []
    W, H = hd_cams["size_wh"]
    for f in hd_cams["frames"]:
        xyxy, trunc = hd.project_box(item, f, (W, H))
        if xyxy is None or trunc >= 1.0:
            continue
        inside = max(0.0, min(xyxy[2], W) - max(xyxy[0], 0)) * max(0.0, min(xyxy[3], H) - max(xyxy[1], 0))
        s = int(f["source_frame"])
        scored.append((inside * (1 - trunc) * sharp.get(s, 1.0), s))
    return [s for _, s in sorted(scored, reverse=True)[:k]]


def crop_rgba(image: np.ndarray, mask: np.ndarray, margin: float = 0.15) -> np.ndarray:
    """掩码外接框四周各放宽 margin 倍的宽高后裁剪（不超出画面），alpha = 掩码。"""
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    tx, ty = int(round(2 * margin * (x1 - x0))), int(round(2 * margin * (y1 - y0)))  # 两边合计，奇数时右下多 1
    H, W = mask.shape
    X0, X1 = max(0, x0 - tx // 2), min(W, x1 + tx - tx // 2)
    Y0, Y1 = max(0, y0 - ty // 2), min(H, y1 + ty - ty // 2)
    rgba = np.dstack([image[..., :3], mask.astype(np.uint8) * 255])
    return rgba[Y0:Y1, X0:X1]


def clean_mesh(mesh, up: str = "y"):
    """只留最大连通分量 → 减面到 ≤ 2 万 → 转成 Z 朝上 → 最长边缩放到 1 → 原点放到底面中心。"""
    import trimesh
    parts = mesh.split(only_watertight=False)
    if len(parts) > 1:
        mesh = max(parts, key=lambda m: len(m.faces))
    if len(mesh.faces) > MAX_FACES:
        mesh = mesh.simplify_quadric_decimation(face_count=MAX_FACES)
    mesh = mesh.copy()
    if up == "y":  # glTF 约定 Y 朝上：绕 x 轴转 +90°，(x, y, z) → (x, −z, y)
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    mesh.apply_scale(1.0 / max(mesh.extents.max(), 1e-9))
    lo, hi = mesh.bounds
    mesh.apply_translation([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
    return mesh


def cache_key(frame: int, mask: np.ndarray, backend: str, seed: int) -> str:
    h = hashlib.sha1(f"{int(frame)}|{backend}|{int(seed)}|{mask.shape}|".encode())
    h.update(np.packbits(np.asarray(mask, bool)).tobytes())
    return h.hexdigest()[:12]


def run_backend(name: str, jobs: list, timeout_s: float = None) -> dict:
    """批量调后端：jobs 是 [{rgba, out, seed}]，返回 {out 路径: 结果 dict}。子进程崩了或超时的都记 backend_error。"""
    if not jobs:
        return {}
    import tempfile
    timeout_s = timeout_s or 60 + 180 * len(jobs)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(jobs, f)
    try:
        cp = subprocess.run(BACKENDS[name] + ["--batch", f.name], capture_output=True, text=True, timeout=timeout_s)
        lines, err = cp.stdout.splitlines(), cp.stderr[-300:]
    except subprocess.TimeoutExpired as e:
        lines, err = (e.stdout or b"").decode(errors="replace").splitlines() if isinstance(e.stdout, bytes) else (e.stdout or "").splitlines(), "timeout"
    finally:
        Path(f.name).unlink(missing_ok=True)
    out = {}
    for line in lines:
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "out" in d:
            out[d["out"]] = d
    for j in jobs:
        out.setdefault(j["out"], {"status": "backend_error", "error": err or "no output"})
    return out


def mask_dir(inventory: str = "inventory.json") -> str:
    """Boxer 清单的掩码在 item_masks/，其他清单（干净对照）在 item_masks_<文件名>/。"""
    return "item_masks" if inventory == "inventory.json" else f"item_masks_{Path(inventory).stem}"


def _load_masks(P: Path, inventory: str = "inventory.json") -> dict:
    """item_id → [掩码条目]，按掩码像素数从大到小。"""
    idx_path = P / mask_dir(inventory) / "index.json"
    by_item = {}
    for m in (json.loads(idx_path.read_text()) if idx_path.exists() else []):
        by_item.setdefault(m["item_id"], []).append(m)
    for v in by_item.values():
        v.sort(key=lambda m: -m.get("mask_px", 0))
    return by_item


def request(scene_id: str, item_ids: list, backend: str = "hy3d_shape", n_candidates: int = 2, seed: int = 0,
            inventory: str = "inventory.json", root: Path = PROJ, max_gen=SCENE_BUDGET, budget_name: str = "budget") -> list:
    """见 _request。整个请求拿 gen/.gen.lock 的排他锁：同一时间只有一个后端进程占显卡，生成计数也不会丢更新。"""
    import fcntl
    if backend not in BACKENDS:
        raise ValueError(f"不认识的后端 {backend}")
    lock = Path(root) / "gen" / ".gen.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            return _request(scene_id, item_ids, backend, n_candidates, seed, inventory, Path(root), max_gen, budget_name)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _request(scene_id, item_ids, backend, n_candidates, seed, inventory, root, max_gen, budget_name):
    """每个物体出 n_candidates 个候选（掩码最大的几帧轮流用，种子 seed + k），返回每个候选一条结果。

    status：ok / too_small（最好那一帧掩码 < 200 像素）/ no_view（32 帧里都看不到或没掩码）/
    backend_error / budget（这次运行已经拿满 max_gen 个候选；agent 组 30 个，P0 不设上限，各用自己的计数文件）。
    预算按这次运行拿到的不同候选计：新生成的和从缓存拿的一样扣（缓存只省 GPU，10-27 起；否则同一场景后跑的组白拿
    先跑的组生成的候选），已经拿到的候选再要一次不重复扣。
    """
    import trimesh
    from PIL import Image
    root = Path(root)
    P, G = root / "perception" / scene_id, root / "gen" / scene_id
    masks = _load_masks(P, inventory)
    mdir = P / mask_dir(inventory)
    budget_path = G / f"{budget_name}.json"
    state = json.loads(budget_path.read_text()) if budget_path.exists() else {}
    used, seen = state.get("used", 0), set(state.get("keys", []))
    results, jobs, spent = [], [], False
    for iid in item_ids:
        ok = [m for m in masks.get(iid, []) if m.get("status") == "ok"]
        if not ok:
            results.append({"item_id": iid, "candidate_id": 0, "status": "no_view"})
            continue
        if ok[0]["mask_px"] < MIN_MASK_PX:
            results.append({"item_id": iid, "candidate_id": 0, "status": "too_small", "frame": ok[0]["frame"],
                            "mask_px": ok[0]["mask_px"]})
            continue
        for k in range(n_candidates):
            m = ok[k % len(ok)] if ok[k % len(ok)]["mask_px"] >= MIN_MASK_PX else ok[0]
            frame, s = int(m["frame"]), seed + k
            mask = np.asarray(Image.open(mdir / m["mask"])) > 0
            key = cache_key(frame, mask, backend, s)
            cdir = G / iid / f"c{k}"
            res = {"item_id": iid, "candidate_id": k, "frame": frame, "mask_px": int(m["mask_px"]), "seed": s,
                   "backend": backend, "key": key, "mesh_glb": str(cdir / "mesh.glb"), "cost_usd": 0.0}
            meta = cdir / "gen.json"
            hit = meta.exists() and (cdir / "mesh.glb").exists() and json.loads(meta.read_text()).get("key") == key \
                and json.loads(meta.read_text()).get("status") == "ok"  # 失败的不当缓存
            if not (hit and key in seen):  # 这次运行已经拿到过的成功候选再要不扣；失败的重新生成照扣
                if max_gen is not None and used >= max_gen:
                    results.append({**res, "status": "budget"})
                    continue
                used, spent = used + 1, True
                seen.add(key)
            if hit:
                results.append({**json.loads(meta.read_text()), "cached": True})
                continue
            cdir.mkdir(parents=True, exist_ok=True)
            (cdir / "mesh.glb").unlink(missing_ok=True)  # 旧网格不留：这次失败就不该再被当成可用
            image = np.asarray(Image.open(P / "hd" / "frames" / f"{frame:06d}.png").convert("RGB"))
            Image.fromarray(crop_rgba(image, mask)).save(cdir / "rgba.png")
            Image.fromarray(mask.astype(np.uint8) * 255).save(cdir / "mask.png")
            jobs.append({"rgba": str(cdir / "rgba.png"), "out": str(cdir / "raw.glb"), "seed": s})
            results.append({**res, "status": "pending"})
    if spent:
        G.mkdir(parents=True, exist_ok=True)
        budget_path.write_text(json.dumps({"used": used, "keys": sorted(seen)}) + "\n")
    done = run_backend(backend, jobs)
    for r in results:
        if r.get("status") != "pending":
            continue
        raw = str(Path(r["mesh_glb"]).with_name("raw.glb"))
        d = done.get(raw, {"status": "backend_error"})
        if d["status"] == "ok":
            mesh = clean_mesh(trimesh.load(raw, force="mesh"), up="y")
            mesh.export(r["mesh_glb"])
            r.update(status="ok", seconds=d.get("seconds"), faces=int(len(mesh.faces)))
        else:
            r.update(status="backend_error", error=d.get("error"))
        Path(r["mesh_glb"]).with_name("gen.json").write_text(json.dumps(r, indent=1) + "\n")
    return results


def item_mask_jobs(scene_id: str, item_ids: list = None, k: int = 3, inventory: str = "inventory.json",
                   root: Path = PROJ) -> list:
    """给 scripts/sam3_objects.py 的 box 模式准备输入：每个物体在最好的 k 帧（pick_frames）的投影框。"""
    from PIL import Image
    P = Path(root) / "perception" / scene_id
    cams = hd.load(P / "hd")
    items = json.loads((P / inventory).read_text())
    jobs = []
    for it in items:
        if item_ids is not None and it["item_id"] not in item_ids:
            continue
        sharp = {}
        for f in cams["frames"]:
            xyxy, trunc = hd.project_box(it, f, cams["size_wh"])
            if xyxy is not None and trunc < 1.0:
                img = np.asarray(Image.open(P / "hd" / "frames" / f"{int(f['source_frame']):06d}.png"))
                sharp[int(f["source_frame"])] = sharpness(img, xyxy)
        for s in pick_frames(it, cams, sharp, k=k):
            f = next(x for x in cams["frames"] if int(x["source_frame"]) == s)
            xyxy, _ = hd.project_box(it, f, cams["size_wh"])
            jobs.append({"item_id": it["item_id"], "frame": s, "bbox_xyxy": xyxy, "label": it["category"]})
    return jobs


if __name__ == "__main__":  # python -m smallobj.gen3d jobs <scene> <out.json> [inventory]
    if sys.argv[1] == "jobs":
        inv = sys.argv[4] if len(sys.argv) > 4 else "inventory.json"
        Path(sys.argv[3]).write_text(json.dumps(item_mask_jobs(sys.argv[2], inventory=inv)) + "\n")


def prepare_sam3d_job(scene_id: str, item_ids: list, inventory: str = "inventory.json", root: Path = PROJ) -> Path:
    """给 Betty 上的 SAM 3D 准备一个批处理目录 gen/<scene>/sam3d_jobs/<时间>/：
    inputs.json（[{item_id, frame, rgba, mask, pointmap, K}]）、<item>_rgba.png（整帧，alpha = 掩码）、
    <item>_mask.png、<item>_pointmap.npy（这一帧高清深度在相机坐标系下的点，H×W×3，无效为 NaN）。
    掩码最大那一帧不到 200 像素或看不到的物体不放进去。Betty 写回 <item>/{mesh.glb 或 splat.ply, pose.json}。"""
    import time
    from PIL import Image
    root = Path(root)
    P = root / "perception" / scene_id
    cams = hd.load(P / "hd")
    by_frame = {int(f["source_frame"]): f for f in cams["frames"]}
    masks = _load_masks(P, inventory)
    mdir = P / mask_dir(inventory)
    job = root / "gen" / scene_id / "sam3d_jobs" / time.strftime("%Y%m%d-%H%M%S")
    job.mkdir(parents=True, exist_ok=True)
    spec = []
    for iid in item_ids:
        ok = [m for m in masks.get(iid, []) if m.get("status") == "ok"]
        if not ok or ok[0]["mask_px"] < MIN_MASK_PX:
            continue
        m = ok[0]
        s = int(m["frame"])
        f = by_frame[s]
        K = np.asarray(f["K"], float)
        mask = np.asarray(Image.open(mdir / m["mask"])) > 0
        img = np.asarray(Image.open(P / "hd" / "frames" / f"{s:06d}.png").convert("RGB"))
        depth = np.load(P / "hd" / "depth" / f"{s:06d}.npy")
        H, W = depth.shape
        u, v = np.meshgrid(np.arange(W), np.arange(H))
        pm = np.stack([(u - K[0, 2]) / K[0, 0] * depth, (v - K[1, 2]) / K[1, 1] * depth, depth], -1).astype(np.float32)
        Image.fromarray(np.dstack([img, mask.astype(np.uint8) * 255])).save(job / f"{iid}_rgba.png")
        Image.fromarray(mask.astype(np.uint8) * 255).save(job / f"{iid}_mask.png")
        np.save(job / f"{iid}_pointmap.npy", pm)
        spec.append({"item_id": iid, "frame": s, "rgba": f"{iid}_rgba.png", "mask": f"{iid}_mask.png",
                     "pointmap": f"{iid}_pointmap.npy", "K": K.tolist(), "c2w": f["c2w"]})
    (job / "inputs.json").write_text(json.dumps(spec, indent=1) + "\n")
    return job
