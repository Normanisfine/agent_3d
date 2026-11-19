"""Offline labels and metrics. Never imported by reconstruction or verification."""
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import Field, model_validator
from scipy.optimize import linear_sum_assignment

from .geometry import oriented_iou
from .io import read_model
from .schema import Box, Record, SceneState


class Label(Record):
    object_id: str
    box: Box
    category: str | None = None
    box_kind: Literal["oriented", "axis_aligned"] = "oriented"
    visible_frames: int = Field(ge=0)
    max_area_fraction: float = Field(ge=0, le=1)


class EvaluationContext(Record):
    schema_version: Literal[1] = 1
    dataset: Literal["ai2thor", "ca1m"]
    scene_id: str
    split: Literal["train", "val", "test"]
    alignment_id: str
    coordinate_frame: Literal["RH_Z_UP_METRES"] = "RH_Z_UP_METRES"
    input_manifest_sha256: str
    labels: list[Label]
    annotation_notes: str

    @model_validator(mode="after")
    def unique_labels(self):
        if len({o.object_id for o in self.labels}) != len(self.labels):
            raise ValueError("Duplicate GT instance IDs")
        if self.dataset == "ai2thor" and any(o.category is None for o in self.labels):
            raise ValueError("AI2-THOR semantic evaluation requires categories")
        return self


def summary(values):
    return {"mean": float(np.mean(values)), "median": float(np.median(values)),
            "p90": float(np.percentile(values, 90))} if values else None


def prf(tp, npred, ngt):
    # Undefined denominators stay null in JSON. Reporting them as 1 would reward
    # empty scenes and bias averages when annotation coverage is sparse.
    precision = tp / npred if npred else None
    recall = tp / ngt if ngt else None
    return {"precision": precision, "recall": recall,
            "f1": 2 * tp / (npred + ngt) if npred + ngt else None}


def evaluate(scene: SceneState, gt: EvaluationContext, input_hash: str,
             thresholds=(0.1, 0.25, 0.5), min_visible_frames=2):
    if (scene.scene_id, scene.alignment_id) != (gt.scene_id, gt.alignment_id):
        raise ValueError("Scene identity / evaluated coordinate alignment mismatch")
    if input_hash != gt.input_manifest_sha256:
        raise ValueError("GT visibility must be derived from these exact input frames")
    if min_visible_frames < 1 or any(not 0 < t <= 1 for t in thresholds):
        raise ValueError("Invalid evaluation gates")
    pred = [o for o in scene.objects if o.status not in {"rejected", "missing"}]
    # Visibility is evaluator-owned and bound to the exact RGB manifest hash.
    # A target visible only in an unsampled frame is not part of recall.
    labels = [o for o in gt.labels if o.visible_frames >= min_visible_frames]
    ious = np.zeros((len(pred), len(labels)))
    for i, p in enumerate(pred):
        for j, g in enumerate(labels):
            if gt.dataset == "ca1m" or p.category == g.category:
                ious[i, j] = oriented_iou(p.box, g.box)
    results = {}
    for threshold in thresholds:
        # Cardinality dominates total IoU: a high-IoU pair must not steal two valid matches.
        valid = ious >= threshold
        reward = valid * (min(ious.shape, default=0) + 1 + ious)
        rows, cols = linear_sum_assignment(-reward)
        # The assignment solver also returns zero-reward edges; discard those
        # after solving so below-threshold pairs never count as true positives.
        pairs = [(int(i), int(j)) for i, j in zip(rows, cols) if valid[i, j]]
        matched_p, matched_g = {i for i, _ in pairs}, {j for _, j in pairs}
        records = []
        for i, j in pairs:
            p, g = pred[i], labels[j]
            # Sorted lengths remove arbitrary local-axis permutations of a cuboid.
            extent_error = np.mean(np.abs(np.sort(p.box.extent) / np.sort(g.box.extent) - 1))
            records.append({"prediction": p.object_id, "target": g.object_id,
                            "iou": float(ious[i, j]),
                            "center_error_cm": float(np.linalg.norm(np.subtract(p.box.center, g.box.center)) * 100),
                            "relative_extent_error": float(extent_error)})
        strata = {}
        for name, lo, hi in (("tiny", 0, .001), ("small", .001, .01),
                             ("medium", .01, .1), ("large", .1, 1.000001)):
            ids = {j for j, g in enumerate(labels) if lo <= g.max_area_fraction < hi}
            strata[name] = {"count": len(ids), "recall": len(ids & matched_g) / len(ids) if ids else None}
        results[str(threshold)] = {
            **prf(len(pairs), len(pred), len(labels)), "matches": records,
            "unmatched_predictions": [p.object_id for i, p in enumerate(pred) if i not in matched_p],
            "unmatched_targets": [g.object_id for j, g in enumerate(labels) if j not in matched_g],
            "iou": summary([r["iou"] for r in records]),
            "center_error_cm": summary([r["center_error_cm"] for r in records]),
            "relative_extent_error": summary([r["relative_extent_error"] for r in records]),
            "area_strata": strata,
        }
    return {"scene_id": scene.scene_id, "dataset": gt.dataset, "split": gt.split,
            "scale_mode": scene.scale_mode, "alignment_id": scene.alignment_id,
            "input_manifest_sha256": input_hash, "min_visible_frames": min_visible_frames,
            "box_kinds": sorted({g.box_kind for g in labels}),
            "excluded_gt_count": len(gt.labels) - len(labels), "thresholds": results,
            "unavailable_metrics": ["orientation (symmetry annotations required)",
                                    "relations", "mesh accuracy", "held-out render agreement"]}


def load_gt(path: Path):
    return read_model(path, EvaluationContext)
