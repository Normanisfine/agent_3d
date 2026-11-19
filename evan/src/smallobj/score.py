"""一次运行的打分：导出 .blend → 去结构件 → 用相机轨迹对齐到真值 → 每个真值物体的结局 → 分档汇总。"""
import json
from pathlib import Path

from smallobj import align, boxes, evaluate, export_blend


def prepare_predictions(preds, transform, th):
    """去结构件 → 对齐到真值坐标。预测侧不按几何的薄壳规则去：同一件东西预测和真值厚度不同，
    规则会只去掉一侧（10-23 审查后试过，窗帘杆因此丢了正确配对）；真值侧对标明的地毯豁免，见 ca1m.world_boxes。"""
    kept = evaluate.filter_predictions(preds)
    return [align.apply(p, transform["s"], transform["R"], transform["t"]) for p in kept]


def alignment_ok(alignment, th):
    """对齐是否可信：相机中心残差中位数不超过上限，尺度在合理范围内。不可信的运行照常打分，但在报告里标出来。"""
    lo, hi = th.get("align_scale_range", [0.7, 1.4])
    return alignment["residual_median_m"] <= th.get("align_residual_max_m", 0.15) and lo <= alignment["s"] <= hi


def score_predictions(preds, gts, transform, th):
    """preds 在流程坐标系；transform = {"s","R","t"}（流程 → 真值）。返回 rows、summary、n_pred。"""
    moved = prepare_predictions(preds, transform, th)
    rows = evaluate.outcomes(moved, gts, th)
    return {"rows": rows, "summary": evaluate.summarize(rows), "n_pred": len(moved)}


def score_inventory(items, gts, transform, th):
    """清单框对齐到真值坐标后跑 outcomes（"检测到" = 判据 D 不是 missed）。不做结构件过滤。"""
    moved = [align.apply(it, transform["s"], transform["R"], transform["t"]) for it in items]
    return evaluate.outcomes(moved, gts, th)


def score_run(run_dir, scene_dir, bundle_dir, th):
    """对 runs/<arm>/<scene>/<seed>/ 打分；两种对齐（修尺度、不修尺度）各写一份 score_*.json。"""
    run_dir, scene_dir = Path(run_dir), Path(scene_dir)
    objects = run_dir / "export" / "objects.json"
    if not objects.exists():
        export_blend.export_objects(run_dir / "scene.blend", objects,
                                    cameras_json=Path(bundle_dir) / "alignment" / "cameras.json")
    preds = boxes.load(objects)
    gts = boxes.load(scene_dir / "gt" / "boxes.json")
    results = {}
    for with_scale, name in ((True, "sim3"), (False, "noscale")):
        tf = align.pipeline_to_gt(bundle_dir, scene_dir, with_scale=with_scale)
        res = score_predictions(preds, gts, tf, th)
        res["alignment"] = {"s": tf["s"], "residual_median_m": tf["residual_median_m"]}
        res["alignment"]["ok"] = alignment_ok(res["alignment"], th)
        (run_dir / f"score_{name}.json").write_text(json.dumps(res, indent=1) + "\n")
        results[name] = res
    return results
