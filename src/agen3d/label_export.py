"""Evaluator-only dataset adapters; no imports from reconstruction code."""
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .evaluation import EvaluationContext, Label
from .geometry import box_from_corners
from .io import digest, read_model
from .schema import InputManifest


def ai2thor_labels(manifest_path: Path, capture: Path, alignment_id: str):
    """Use selected frame metadata and instance colors, not all-capture coverage.

    THOR (x,y,z) -> canonical (x,z,y); reflection changes handedness. Rebuild
    right-handed box axes from corners. Non-oriented annotations stay labeled AABB.
    """
    manifest = read_model(manifest_path, InputManifest)
    if manifest.dataset != "ai2thor":
        raise ValueError("Expected AI2-THOR manifest")
    accumulated = {}
    # This mapping belongs to evaluation only; do not copy it into RGB exports.
    colors = json.loads((capture / "instance_colors.json").read_text())
    if not isinstance(colors, dict) or not all(isinstance(v, list) and len(v) == 3 for v in colors.values()):
        raise ValueError("Export instance_colors.json as {objectId: [r,g,b]} first")
    for frame in manifest.frames:
        # IDs refer to native capture filenames, validated against path traversal.
        if Path(frame.frame_id).name != frame.frame_id or not frame.frame_id.isdigit():
            raise ValueError("AI2-THOR frame IDs must be numeric filename stems")
        metadata = json.loads((capture / "metadata" / f"{frame.frame_id}.json").read_text())
        with Image.open(capture / "instances" / f"{frame.frame_id}.png") as image:
            pixels = np.asarray(image.convert("RGB"))
        for obj in metadata["objects"]:
            oid = obj["objectId"]
            if oid not in colors:
                continue
            count = int(np.all(pixels == colors[oid], axis=2).sum())
            if count == 0:
                continue
            obb = obj.get("objectOrientedBoundingBox")
            annotation = obb or obj.get("axisAlignedBoundingBox")
            if not annotation:
                raise ValueError(f"No box for visible object {oid}")
            box = box_from_corners(np.asarray(annotation["cornerPoints"])[:, [0, 2, 1]])
            label = accumulated.get(oid)
            if label and not np.allclose(label.box.center, box.center, atol=1e-3):
                raise ValueError(f"Moving object {oid}: static-scene evaluation invalid")
            if not label:
                label = Label(object_id=oid, box=box, category=obj["objectType"],
                              box_kind="oriented" if obb else "axis_aligned",
                              visible_frames=0, max_area_fraction=0)
                accumulated[oid] = label
            label.visible_frames += 1
            label.max_area_fraction = max(label.max_area_fraction, count / pixels.shape[0] / pixels.shape[1])
    return EvaluationContext(dataset="ai2thor", scene_id=manifest.scene_id, split=manifest.split,
                             alignment_id=alignment_id, input_manifest_sha256=digest(manifest_path),
                             labels=list(accumulated.values()), annotation_notes=
                             "Pixel visibility in selected frames; parentReceptacles are not asserted support relations.")


def ca1m_labels(manifest_path: Path, normalized_path: Path, alignment_id: str):
    """Import explicitly normalized CA-1M boxes; does not guess native archive layout.

    Each row has object_id, box (canonical metres), visible_frames, max_area_fraction.
    Visibility must be computed by the dataset export, not inferred from box presence.
    """
    manifest = read_model(manifest_path, InputManifest)
    if manifest.dataset != "ca1m":
        raise ValueError("Expected CA-1M manifest")
    payload = json.loads(normalized_path.read_text())
    if payload["input_manifest_sha256"] != digest(manifest_path):
        raise ValueError("Normalized labels belong to different input frames")
    labels = [Label.model_validate(row) for row in payload["labels"]]
    if any(label.category is not None for label in labels):
        raise ValueError("CA-1M protocol is class-agnostic")
    return EvaluationContext(dataset="ca1m", scene_id=manifest.scene_id, split=manifest.split,
                             alignment_id=alignment_id, input_manifest_sha256=digest(manifest_path),
                             labels=labels, annotation_notes=payload["annotation_notes"])
