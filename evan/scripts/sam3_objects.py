"""SAM 3 物体掩码（在 AHa-3D 的 sam3-segmentation venv 里运行，模型只加载一次）。

用法：
  text 模式（干净对照清单）：python sam3_objects.py text <hd_dir> <labels.json> <out_dir> [--min-score 0.5] [--tiles 3]
    每个高清帧 × 每个类别做文本提示，所有得分 ≥ min-score 的实例都存；写 out_dir/index.json。
    --tiles 3（清单 v2，借 SceneRig 的放大再检测）：整帧之外再切 3×3 个重叠一半的窗口各跑一遍，
    被窗口内侧边缘切开的丢掉，贴回整帧后和整帧结果去重；index 里 source 记 full 或 tile。
  box 模式（生成用的物体掩码）：python sam3_objects.py box <hd_dir> <items.json> <out_dir>
    items.json 是 [{item_id, frame, bbox_xyxy, label}]；框提示加文本提示，取和框重合最多的掩码，
    写 out_dir/<item_id>/<frame>.png 和 out_dir/index.json。
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from smallobj import tiles  # noqa: E402  只用 numpy

AHA = Path(__file__).resolve().parents[1] / "third_party" / "aha-3d"
CKPT = AHA / ".runtime" / "sam3-segmentation" / "checkpoints" / "sam3.pt"


def _iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _results(result, W, H):
    masks = result["masks"].detach().float().cpu().numpy()
    boxes = result["boxes"].detach().float().cpu().numpy()
    scores = result["scores"].detach().float().cpu().numpy()
    for mask, box, score in zip(masks, boxes, scores):
        mask = np.squeeze(mask) > 0.5
        if mask.shape == (H, W) and mask.any():
            yield mask, [float(v) for v in box], float(score)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["text", "box"])
    ap.add_argument("hd_dir", type=Path)
    ap.add_argument("spec", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--min-score", type=float, default=0.5)
    ap.add_argument("--tiles", type=int, default=1, help="1 = 只跑整帧（原来的行为）；3 = 另加 3×3 个放大窗口")
    args = ap.parse_args()
    from sam3.model.sam3_image_processor import Sam3Processor
    from sam3.model_builder import build_sam3_image_model
    model = build_sam3_image_model(checkpoint_path=str(CKPT), load_from_HF=False, device="cuda", compile=False)
    proc = Sam3Processor(model, confidence_threshold=0.3)
    cams = json.loads((args.hd_dir / "cameras.json").read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    index = []
    if args.mode == "text":
        labels = json.loads(args.spec.read_text())["labels"]
        for f in cams["frames"]:
            s = int(f["source_frame"])
            image = Image.open(args.hd_dir / "frames" / f"{s:06d}.png").convert("RGB")
            W, H = image.size
            dets = []
            for win in [(0, 0, W, H)] + (tiles.windows(W, H, args.tiles) if args.tiles > 1 else []):
                src = "full" if win == (0, 0, W, H) else "tile"
                crop = image if src == "full" else image.crop(win)
                with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                    state = proc.set_image(crop)
                    for label in labels:
                        proc.reset_all_prompts(state)
                        for k, (mask, box, score) in enumerate(_results(proc.set_text_prompt(prompt=label, state=state),
                                                                        crop.width, crop.height)):
                            if score < args.min_score:
                                continue
                            if src == "tile":
                                if tiles.cut_by_inner_edge(mask, win, W, H):
                                    continue
                                mask = tiles.paste(mask, win, W, H)
                                box = [box[0] + win[0], box[1] + win[1], box[2] + win[0], box[3] + win[1]]
                            dets.append({"label": label, "k": k, "score": score, "mask": mask, "box": box, "source": src})
            if args.tiles > 1:
                dets = tiles.dedupe(dets)
                count = {}
                for d in dets:  # 去重后按类别重新编号
                    d["k"] = count[d["label"]] = count.get(d["label"], -1) + 1
            for d in dets:
                name = f"{s:06d}/{d['label'].replace(' ', '_')}_{d['k']}.png"
                (args.out / name).parent.mkdir(exist_ok=True)
                Image.fromarray(d["mask"].astype(np.uint8) * 255).save(args.out / name)
                index.append({"frame": s, "label": d["label"], "score": d["score"], "mask": name, "box_xyxy": d["box"],
                              "mask_px": int(d["mask"].sum()), "source": d["source"]})
            print(f"frame {s}: {sum(1 for r in index if r['frame'] == s)} masks", flush=True)
    else:
        items = json.loads(args.spec.read_text())
        by_frame = {}
        for it in items:  # 同一帧的物体一起做：图像只编码一次
            by_frame.setdefault(int(it["frame"]), []).append(it)
        for s, group in sorted(by_frame.items()):
            image = Image.open(args.hd_dir / "frames" / f"{s:06d}.png").convert("RGB")
            W, H = image.size
            with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                state = proc.set_image(image)
                for it in group:
                    b = np.clip(np.asarray(it["bbox_xyxy"], float), [0, 0, 0, 0], [W, H, W, H])
                    if (b[2:] - b[:2] <= 1).any():
                        index.append({"item_id": it["item_id"], "frame": s, "status": "no_view"})
                        continue
                    box_prompt = [(b[0] + b[2]) / 2 / W, (b[1] + b[3]) / 2 / H, (b[2] - b[0]) / W, (b[3] - b[1]) / H]
                    cands = []
                    for mode in ("box", "text"):
                        proc.reset_all_prompts(state)
                        res = proc.add_geometric_prompt(box_prompt, True, state) if mode == "box" \
                            else proc.set_text_prompt(prompt=it.get("label", "object"), state=state)
                        cands += [(m, bx, sc, mode) for m, bx, sc in _results(res, W, H)]
                    if not cands:
                        index.append({"item_id": it["item_id"], "frame": s, "status": "no_mask"})
                        continue
                    mask, box, score, mode = max(cands, key=lambda c: (_iou(c[1], b), c[2]))
                    name = f"{it['item_id']}/{s:06d}.png"
                    (args.out / it["item_id"]).mkdir(exist_ok=True)
                    Image.fromarray(mask.astype(np.uint8) * 255).save(args.out / name)
                    index.append({"item_id": it["item_id"], "frame": s, "status": "ok", "mask": name, "mode": mode,
                                  "score": score, "box_xyxy": box, "box_iou": _iou(box, b), "mask_px": int(mask.sum())})
    (args.out / "index.json").write_text(json.dumps(index, indent=1) + "\n")
    print(f"{len(index)} entries → {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
