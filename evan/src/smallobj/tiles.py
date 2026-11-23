"""放大再检测（借 SceneRig 第 2 层，`docs/research/05-scenerig.md`）：高清帧切成互相重叠的窗口，
每个窗口单独送进 SAM 3（模型把窗口缩放到自己的输入尺寸，小物体在里面就大了），结果贴回整帧。

只用 numpy：scripts/sam3_objects.py 在 AHa-3D 的 sam3 venv 里也能导入。
"""
import numpy as np


def windows(W: int, H: int, n: int = 3, frac: float = 0.5) -> list:
    """n×n 个窗口，每个占 frac 的宽高，从左上到右下均匀排开（n=3、frac=0.5 时相邻窗口重叠一半）。n=1 是整帧。"""
    if n <= 1:
        return [(0, 0, W, H)]
    w, h = int(round(W * frac)), int(round(H * frac))
    xs = np.linspace(0, W - w, n).round().astype(int)
    ys = np.linspace(0, H - h, n).round().astype(int)
    return [(int(x), int(y), int(x) + w, int(y) + h) for y in ys for x in xs]


def cut_by_inner_edge(mask: np.ndarray, win: tuple, W: int, H: int, margin: int = 2) -> bool:
    """窗口里的掩码碰到了窗口在画面内部的那条边（物体可能被窗口切开）。碰到画面本身的边不算。"""
    x0, y0, x1, y1 = win
    m = np.asarray(mask, bool)
    return bool((x0 > 0 and m[:, :margin].any()) or (x1 < W and m[:, -margin:].any())
                or (y0 > 0 and m[:margin, :].any()) or (y1 < H and m[-margin:, :].any()))


def paste(mask: np.ndarray, win: tuple, W: int, H: int) -> np.ndarray:
    x0, y0, x1, y1 = win
    full = np.zeros((H, W), bool)
    full[y0:y1, x0:x1] = np.asarray(mask, bool)
    return full


def _bbox(m):
    ys, xs = np.nonzero(m)
    return (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1) if len(xs) else None


def dedupe(dets: list, iou_min: float = 0.5) -> list:
    """同一帧里整帧和各窗口的检测去重。整帧（source="full"）的一个不动，和旧干净对照完全一样，消融"只看整帧"才可比；
    窗口的按得分从高到低，只有和已收的（整帧的、更高分的窗口的）同类别掩码 IoU 都 < iou_min 时才收。
    dets 是 [{label, score, mask（整帧 bool）, source, ...}]。"""
    kept = [{**d, "_bbox": _bbox(d["mask"])} for d in dets if d.get("source") == "full"]
    for d in sorted((d for d in dets if d.get("source") != "full"), key=lambda d: -d["score"]):
        bd = _bbox(d["mask"])
        if bd is None:
            continue
        dup = False
        for k in kept:
            if k["label"] != d["label"]:
                continue
            bk = k["_bbox"]
            if bk is None or bd[2] <= bk[0] or bk[2] <= bd[0] or bd[3] <= bk[1] or bk[3] <= bd[1]:
                continue
            inter = np.logical_and(d["mask"], k["mask"]).sum()
            union = np.logical_or(d["mask"], k["mask"]).sum()
            if union and inter / union >= iou_min:
                dup = True
                break
        if not dup:
            kept.append({**d, "_bbox": bd})
    return [{k: v for k, v in d.items() if k != "_bbox"} for d in kept]
