"""CA-1M（Apple Cubify Anything）单个视频的下载、解包、真值框、输入视频和相机轨迹。

压缩包里每帧是 `<vid>/<时间戳ns>.wide/...`（1024×768 原图、内参）和 `<vid>/<时间戳ns>.gt/...`
（注册到激光扫描坐标系的位姿 RT、激光渲染深度）；整场景真值框在 `<vid>/world.gt/instances.json`，
每个框是 position、scale、R（列是框的三个轴）。图片已经转正，竖拍视频的宽高是对调的。

真值（位姿、深度、框）只给评测用，不进 agent 的输入。
"""
import json
import subprocess
import tarfile
from pathlib import Path

import numpy as np

from smallobj import boxes

BASE_URL = "https://ml-site.cdn-apple.com/datasets/ca1m"

# 结构件：评测前去掉（设计文档第 8 节：墙、地面、天花板、门框）。按类别名完全相等匹配；
# 门框在 CA-1M 里有 doorframe、door_frame 两种写法（10-22 在 3 个开发场景上核过）。
# 10-23 补：门、窗、窗台、踢脚线也去掉，因为 AHa-3D 把它们当结构件建，预测侧按结构件过滤，两边要对称。
# 开关、插座保留（它们是真的小物体）。
STRUCTURAL_DEFAULT = {"wall", "floor", "ceiling", "doorframe", "door_frame", "door frame",
                      "door", "window", "window sill", "baseboard", "base board"}
# 壳体零件：最薄一维 < 6 cm 且最长边 ≥ 1.5 m（顶角线、踢脚线、天花板或地面面板、地毯），CA-1M 多标成 "object"
SHELL_DEFAULT = (0.06, 1.5)

# 只解这几样；每帧的 wide/instances.json（相机坐标下的框）和 LiDAR 深度用不到
_KEEP = {
    "wide/image.png": "image.png",
    "wide/image/K.json": "K.json",
    "gt/RT.json": "RT.json",
    "gt/depth.png": "depth.png",
    "gt/depth/K.json": "depth_K.json",
}


def tar_url(video_id: str, split: str = "val") -> str:
    return f"{BASE_URL}/{split}/ca1m-{split}-{video_id}.tar"


def download(video_id: str, split: str = "val", root: Path = Path("scenes")) -> Path:
    """断点续传下载到 `<root>/<video_id>/raw.tar`；已经下完就跳过。"""
    out = Path(root) / str(video_id) / "raw.tar"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    part = out.with_suffix(".tar.part")
    subprocess.run(["curl", "-sSf", "-C", "-", "-o", str(part), tar_url(video_id, split)], check=True)
    part.rename(out)
    return out


def extract(tar_path: Path, scene_dir: Path) -> list[int]:
    """解出每帧需要的文件到 `frames/<ts>/`，整场景真值框到 `gt/world_instances.json`。返回升序时间戳。"""
    scene_dir = Path(scene_dir)
    stamps = set()
    with tarfile.open(tar_path, "r|*") as tf:
        for member in tf:
            if not member.isfile():
                continue
            parts = member.name.split("/", 1)
            if len(parts) != 2:
                continue
            key = parts[1]
            if key == "world.gt/instances.json":
                dst = scene_dir / "gt" / "world_instances.json"
            else:
                stamp, _, rest = key.partition(".")
                if not stamp.isdigit() or rest not in _KEEP:
                    continue
                stamps.add(int(stamp))
                dst = scene_dir / "frames" / stamp / _KEEP[rest]
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(tf.extractfile(member).read())
    return sorted(stamps)


def _record_from_world(inst: dict) -> dict:
    """position/scale/R（R 的列是框轴）→ 重力对齐的 boxes.record；倾斜的框取绕竖直轴的外包框。"""
    R = np.asarray(inst["R"], float).reshape(3, 3)
    scale = np.asarray(inst["scale"], float)
    center = np.asarray(inst["position"], float)
    v = int(np.argmax(np.abs(R[2, :])))
    a, b = [i for i in range(3) if i != v]
    yaw = float(np.arctan2(R[1, a], R[0, a]))
    if abs(R[2, v]) >= 0.95:
        size = [scale[a], scale[b], scale[v]]
    else:
        signs = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float)
        world = center + (signs * scale / 2) @ R.T
        local = (world - center) @ boxes.rot_z(yaw)
        size = (local.max(0) - local.min(0)).tolist()
    return boxes.record(inst["id"], inst.get("category", "object"), center, yaw, size)


def world_boxes(scene_dir: Path, structural: set[str], shell=None, shell_keep=()) -> list[dict]:
    """读整场景真值框，去掉结构件（按类别）和壳体零件（shell=(最大厚度, 最小长度)），写 `gt/boxes.json`。

    壳体零件指踢脚线、墙板、天花板条这类 AHa-3D 当结构建的东西；shell_keep 里的类别（地毯等）不算，照样保留。
    """
    scene_dir = Path(scene_dir)
    raw = json.loads((scene_dir / "gt" / "world_instances.json").read_text())
    recs = [_record_from_world(i) for i in raw if i.get("category", "object") not in structural]
    if shell is not None:
        recs = [r for r in recs if r["category"] in shell_keep or not boxes.is_shell(r, *shell)]
    boxes.save(recs, scene_dir / "gt" / "boxes.json")
    return recs


def frame_stamps(scene_dir: Path) -> list[int]:
    return sorted(int(p.name) for p in (Path(scene_dir) / "frames").iterdir() if p.name.isdigit())


def make_video(scene_dir: Path, fps: int = 10) -> Path:
    """按时间戳顺序把原图写成 `input.mp4`，并写 `frame_map.json`（视频帧号 → 真实时间戳）。

    个别场景拍摄中途转了手机，少数帧按另一种朝向存（如 42899698 的 443 帧里有 8 帧竖着）：
    只用多数朝向的帧，丢掉的时间戳写进 `dropped_timestamps_ns`。
    """
    import imageio.v3 as iio
    from collections import Counter
    from PIL import Image

    scene_dir = Path(scene_dir)
    all_stamps = frame_stamps(scene_dir)
    sizes = {s: Image.open(scene_dir / "frames" / str(s) / "image.png").size for s in all_stamps}
    (w, h), _ = Counter(sizes.values()).most_common(1)[0]
    stamps = [s for s in all_stamps if sizes[s] == (w, h)]
    dropped = [s for s in all_stamps if sizes[s] != (w, h)]
    w2, h2 = w - w % 2, h - h % 2  # mp4 要求偶数宽高
    frames = [np.asarray(Image.open(scene_dir / "frames" / str(s) / "image.png").convert("RGB"))[:h2, :w2]
              for s in stamps]
    out = scene_dir / "input.mp4"
    iio.imwrite(out, np.stack(frames), fps=fps, codec="libx264", macro_block_size=1)
    (scene_dir / "frame_map.json").write_text(json.dumps(
        {"fps": fps, "width": w2, "height": h2, "timestamps_ns": stamps, "dropped_timestamps_ns": dropped},
        indent=1) + "\n")
    return out


def camera_track(scene_dir: Path) -> dict[int, np.ndarray]:
    """时间戳 → `gt/RT.json` 的 4×4 相机到世界矩阵（行优先，激光扫描坐标系，z 朝上）。

    10-22 在 45261575 上核过：RT 的平移落在真值框的坐标范围里，取逆则落到几十米外，所以是相机到世界。
    """
    scene_dir = Path(scene_dir)
    return {s: np.asarray(json.loads((scene_dir / "frames" / str(s) / "RT.json").read_text()), float).reshape(4, 4)
            for s in frame_stamps(scene_dir)}


def project(points_world: np.ndarray, c2w: np.ndarray, K: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """世界点 → 像素（OpenCV 相机：x 右、y 下、z 朝前）。返回 (N,2) 像素和 (N,) 相机深度。"""
    w2c = np.linalg.inv(c2w)
    cam = points_world @ w2c[:3, :3].T + w2c[:3, 3]
    z = cam[:, 2]
    uv = (cam[:, :2] / np.where(np.abs(z) < 1e-9, 1e-9, z)[:, None]) * [K[0, 0], K[1, 1]] + [K[0, 2], K[1, 2]]
    return uv, z


def draw_check(scene_dir: Path, out_png: Path, where: float = 0.5) -> Path:
    """把 `gt/boxes.json` 的真值框投影到第 where（0–1）位置那一帧原图上，人工检查位姿和框是否对得上。"""
    from PIL import Image, ImageDraw

    scene_dir = Path(scene_dir)
    stamps = frame_stamps(scene_dir)
    s = stamps[min(len(stamps) - 1, int(where * len(stamps)))]
    fdir = scene_dir / "frames" / str(s)
    img = Image.open(fdir / "image.png").convert("RGB")
    K = np.asarray(json.loads((fdir / "K.json").read_text()), float).reshape(3, 3)
    c2w = camera_track(scene_dir)[s]
    draw = ImageDraw.Draw(img)
    for rec in boxes.load(scene_dir / "gt" / "boxes.json"):
        uv, z = project(boxes.corners(rec), c2w, K)
        if np.any(z <= 0.05):
            continue
        for i, j in boxes.EDGES:
            draw.line([tuple(uv[i]), tuple(uv[j])], fill=(0, 255, 0), width=2)
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    return Path(out_png)
