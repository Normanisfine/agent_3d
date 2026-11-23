"""论文定性对比图的素材：同一个房间、同一个机位，4 个组各渲染一张，外加原视频帧和整体图。

机位不手挑：每个房间取"能看到最多 50 cm 以下标注目标"的高清帧（目标中心投进画面、在相机前 0.3–4.5 m，
且和该帧深度图在该像素的深度相差不到 max(0.2 m, 10%)，算作没被挡住），
--top k 时取前 k 个互相至少隔 --gap 帧的，供排版时选。50 cm 以下的实例按评测结果上色（判据 D、相机拟合尺度，和主表一致）。
用法：PYTHONPATH=src .runtime/venv/bin/python scripts/paper/qualitative.py [--rooms 42897538 ...] [--top 3] [--overview] [--seed 0]
输出 paper/smallobj/figures/qual/<房间>/{frame_<k>.jpg, <组>_<k>.png, <组>_overview.png, meta.json}
"""
import argparse
import os
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from smallobj import align, boxes, evaluate, score
from smallobj.export_blend import BLENDER

PROJ = Path(__file__).resolve().parents[2]
ROOMS = ["42897538", "42898849", "42899617", "42899712", "42899729", "44358442"]
ARMS = ["A0", "A1", "A2", "A5"]
OUT = PROJ / "paper" / "smallobj" / "figures" / os.environ.get("QUAL_DIR", "qual")
SMALL = ("XS", "S")


def roles_for(run, gts, tf, th):
    """实例 id → 结果。只给 50 cm 以下的上色：配上小目标的按建对 / 摆错；没配上且自己最长边不到 50 cm 的算 extra。"""
    raw = boxes.load(run / "export" / "objects.json")
    preds = score.prepare_predictions(raw, tf, th)
    rows = evaluate.outcomes(preds, gts, th)
    roles, used = {}, set()
    for r in rows:
        if r.get("pred_id"):
            used.add(r["pred_id"])
            if r["bin"] in SMALL:
                roles[r["pred_id"]] = r["D"]
    for p in preds:
        if p["object_id"] not in used and max(p["size"]) < th["bin_edges_m"][1]:
            roles[p["object_id"]] = "extra"
    counts = {k: sum(v == k for v in roles.values()) for k in ("correct", "misplaced", "extra")}
    counts["instances"] = len(preds)
    return roles, counts


def pick_frames(cams, gts, tf, th, top, gap, depth_dir):
    """每帧能看到的小目标数（真值中心变回流程坐标再投影），从多到少取互相隔开的 top 帧。"""
    centers = np.array([g["center"] for g in gts if evaluate.size_bin(g, th["bin_edges_m"]) in SMALL], float)
    pipe = (centers - tf["t"]) @ tf["R"] / tf["s"]  # 真值 = s·R·x + t 的逆
    W, H = cams["size_wh"]
    seen = []
    for i, f in enumerate(cams["frames"]):
        w2c = np.linalg.inv(np.asarray(f["c2w"], float))
        pc = pipe @ w2c[:3, :3].T + w2c[:3, 3]
        z = pc[:, 2]
        uv = pc @ np.asarray(f["K"], float).T
        with np.errstate(divide="ignore", invalid="ignore"):
            u, v = uv[:, 0] / z, uv[:, 1] / z
        m = 0.04
        ok = (z > 0.3) & (z < 4.5) & (u > m * W) & (u < (1 - m) * W) & (v > m * H) & (v < (1 - m) * H)
        depth = np.load(depth_dir / f"{int(f['source_frame']):06d}.npy")
        d = depth[np.clip(v[ok], 0, H - 1).astype(int), np.clip(u[ok], 0, W - 1).astype(int)]
        seen.append(int((np.abs(z[ok] - d) < np.maximum(0.2, 0.1 * z[ok])).sum()))
    order, chosen = np.argsort(seen)[::-1], []
    for i in order:
        if len(chosen) == top:  # --top 0：只用 --extra 指定的机位
            break
        if all(abs(int(cams["frames"][i]["source_frame"]) - int(cams["frames"][j]["source_frame"])) >= gap for j in chosen):
            chosen.append(int(i))
    return chosen, seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rooms", nargs="*", default=ROOMS)
    ap.add_argument("--arms", nargs="*", default=ARMS)
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--gap", type=int, default=40)
    ap.add_argument("--seed", default="0")
    ap.add_argument("--overview", action="store_true")
    ap.add_argument("--samples", type=int, default=96)
    ap.add_argument("--extra", nargs="*", default=[], help="另外指定的机位，格式 房间号:视频帧号，排在按规则取的机位后面（手挑的画面）")
    ap.add_argument("--uniform", action="store_true", help="不按结果上色：50 cm 以下的实例统一用一种蓝（架构图用）")
    a = ap.parse_args()
    th = json.loads((PROJ / "configs" / "thresholds.json").read_text())
    for sid in a.rooms:
        P, scene = PROJ / "perception" / sid, PROJ / "scenes" / sid
        gts = boxes.load(scene / "gt" / "boxes.json")
        tf = align.pipeline_to_gt(P / "bundle", scene, with_scale=True)
        cams = json.loads((P / "hd" / "cameras.json").read_text())
        idx, seen = pick_frames(cams, gts, tf, th, a.top, a.gap, P / "hd" / "depth")
        for e in a.extra:
            if e.split(":")[0] == sid:
                idx.append(next(i for i, f in enumerate(cams["frames"]) if int(f["source_frame"]) == int(e.split(":")[1])))
        out = OUT / sid
        out.mkdir(parents=True, exist_ok=True)
        meta = {"room": sid, "seed": a.seed, "n_small_targets": sum(evaluate.size_bin(g, th["bin_edges_m"]) in SMALL for g in gts),
                "frames": [{"k": k, "source_frame": int(cams["frames"][i]["source_frame"]), "small_targets_in_view": seen[i]} for k, i in enumerate(idx)],
                "arms": {}}
        for k, i in enumerate(idx):
            f = cams["frames"][i]
            Image.open(P / "hd" / "frames" / f"{int(f['source_frame']):06d}.png").convert("RGB").save(out / f"frame_{k}.jpg", quality=92)
        for arm in a.arms:
            run = PROJ / "runs" / f"{arm}-claude" / sid / a.seed
            if not (run / "scene.blend").exists():
                continue
            roles, counts = roles_for(run, gts, tf, th)
            if a.uniform:
                roles = {p["object_id"]: "correct" for p in score.prepare_predictions(boxes.load(run / "export" / "objects.json"), tf, th)
                         if max(p["size"]) < th["bin_edges_m"][1]}
            meta["arms"][arm] = counts
            with tempfile.TemporaryDirectory() as tmp:
                spec = {"views": [{"name": f"{arm}_{k}", "c2w": cams["frames"][i]["c2w"], "K": cams["frames"][i]["K"], "size_wh": cams["size_wh"]}
                                  for k, i in enumerate(idx)],
                        "out_dir": tmp, "roles": roles, "overview": a.overview, "samples": a.samples}
                Path(tmp, "spec.json").write_text(json.dumps(spec))
                cp = subprocess.run([str(BLENDER), "-b", str(run / "scene.blend"), "--python", str(Path(__file__).with_name("blender_paper_render.py")),
                                     "--", str(Path(tmp, "spec.json"))], capture_output=True, text=True)
                if cp.returncode != 0 or "rendered" not in cp.stdout:
                    print(sid, arm, "渲染失败", cp.stderr[-600:], cp.stdout[-300:], flush=True)
                    continue
                for p in Path(tmp).glob("*.png"):
                    im = Image.open(p)
                    if p.name == "overview.png":  # 透明底：裁到房间范围，垫白
                        box = im.getchannel("A").point(lambda x: 255 if x > 8 else 0).getbbox()
                        im = im.crop((max(0, box[0] - 20), max(0, box[1] - 20), min(im.width, box[2] + 20), min(im.height, box[3] + 20)))
                        bg = Image.new("RGBA", im.size, "white")
                        bg.alpha_composite(im)
                        im = bg.convert("RGB")
                    im.save(out / (f"{arm}_overview.png" if p.name == "overview.png" else p.name))
            print(sid, arm, counts, [l for l in cp.stdout.splitlines() if "cycles device" in l], flush=True)
        (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n")
        print(sid, meta["frames"], flush=True)


if __name__ == "__main__":
    main()
