"""Evaluator-only entrypoint. Launched AFTER model work, never imported by agents.

Only camera poses establish the evaluation frame. Object labels never align or
repair predictions. Metric-scale and oracle-scale diagnostics stay separate.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from agen3d.evaluation import EvaluationContext, Label, evaluate
from agen3d.geometry import box_from_corners
from agen3d.io import digest
from agen3d.schema import InputManifest, SceneState
from agen3d.multiagent.store import save


def camera_pose(record):
    yaw = np.deg2rad(record["agent"]["rotation"]["y"])
    pitch = np.deg2rad(record["agent"]["cameraHorizon"])
    right = np.array([np.cos(yaw), 0, -np.sin(yaw)])
    down = np.array([np.sin(yaw)*np.sin(pitch), -np.cos(pitch), np.cos(yaw)*np.sin(pitch)])
    forward = np.array([np.sin(yaw)*np.cos(pitch), -np.sin(pitch), np.cos(yaw)*np.cos(pitch)])
    # Unity -> canonical swaps Y/Z (reflection); camera Y-down compensates it.
    swap = np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]])
    pose = np.eye(4)
    pose[:3, :3] = swap @ np.stack([right, down, forward], axis=1)
    p = record["cameraPosition"]
    pose[:3, 3] = [p["x"], p["z"], p["y"]]
    return pose


def align_cameras(predicted, target, estimate_scale=False):
    """Orientation-constrained rigid alignment; optional scale uses cameras only."""
    cross = sum(g[:3, :3] @ p[:3, :3].T for p, g in zip(predicted, target))
    u, _, vt = np.linalg.svd(cross)
    rotation = u @ np.diag([1, 1, np.linalg.det(u @ vt)]) @ vt
    p, g = predicted[:, :3, 3], target[:, :3, 3]
    pc, gc = p - p.mean(0), g - g.mean(0)
    scale = 1.
    if estimate_scale:
        denominator = float((pc*pc).sum())
        if denominator < 1e-8:
            raise ValueError("Camera trajectory lacks translation; scale unidentifiable")
        scale = float(((pc @ rotation.T) * gc).sum() / denominator)
        if not .01 < scale < 100:
            raise ValueError("Camera-derived scale invalid")
    translation = g.mean(0) - scale * p.mean(0) @ rotation.T
    residual = np.linalg.norm(scale * p @ rotation.T + translation - g, axis=1)
    return rotation, translation, scale, residual


def transform_scene(scene, rotation, translation, scale, alignment_id):
    result = scene.model_copy(deep=True)
    result.alignment_id = alignment_id
    result.scale_mode = "oracle_scale" if scale != 1 else "estimated_scale"
    for obj in result.objects:
        obj.box.center = tuple(scale * np.asarray(obj.box.center) @ rotation.T + translation)
        obj.box.extent = tuple(scale * np.asarray(obj.box.extent))
        obj.box.rotation = tuple(map(tuple, rotation @ np.asarray(obj.box.rotation)))
    return SceneState.model_validate(result.model_dump())


def labels_from_capture(dataset, manifest, input_hash):
    gt = dataset / "ground_truth"
    accumulated, invalid = {}, {}
    for frame in manifest.frames:
        metadata = json.loads((gt / "metadata" / f"{frame.frame_id}.json").read_text())
        annotations = json.loads((gt / "annotations" / f"{frame.frame_id}.json").read_text())
        pixels = np.asarray(Image.open(gt / "instance_segmentation" / f"{frame.frame_id}.png").convert("RGB"), dtype=np.uint32)
        codes = pixels[..., 0] * 65536 + pixels[..., 1] * 256 + pixels[..., 2]
        unique, counts = np.unique(codes, return_counts=True)
        lookup = dict(zip(unique.tolist(), counts.tolist()))
        for obj in metadata["objects"]:
            oid = obj["objectId"]
            color = annotations["object_id_to_color"].get(oid)
            if color is None:
                continue
            count = lookup.get(color[0]*65536 + color[1]*256 + color[2], 0)
            if not count:
                continue
            obb = obj.get("objectOrientedBoundingBox")
            annotation = obb or obj.get("axisAlignedBoundingBox")
            try:
                box = box_from_corners(np.asarray(annotation["cornerPoints"])[:, [0, 2, 1]])
            except (ValueError, TypeError):
                invalid[oid] = "missing/degenerate bounding box"
                continue
            label = accumulated.get(oid)
            if label and np.linalg.norm(np.array(label.box.center)-box.center) > .01:
                raise ValueError(f"Moving GT object {oid}; static evaluator invalid")
            if label is None:
                label = Label(object_id=oid, category=obj["objectType"], box=box,
                              box_kind="oriented" if obb else "axis_aligned",
                              visible_frames=0, max_area_fraction=0)
                accumulated[oid] = label
            label.visible_frames += 1
            label.max_area_fraction = max(label.max_area_fraction, count / codes.size)
    return EvaluationContext(dataset="ai2thor", scene_id=manifest.scene_id, split=manifest.split,
        alignment_id="thor-world-camera-rigid", input_manifest_sha256=input_hash,
        labels=list(accumulated.values()), annotation_notes=json.dumps({
            "visibility": "actual selected-frame instance pixels; minimum two frames",
            "invalid_annotations": invalid, "static_center_tolerance_m": .01}))


def run(dataset, manifest_path, scene_path, cameras_path, output):
    output.mkdir(parents=True, exist_ok=False)
    manifest = InputManifest.model_validate_json(manifest_path.read_text())
    scene = SceneState.model_validate_json(scene_path.read_text())
    labels = labels_from_capture(dataset, manifest, digest(manifest_path))
    save(output / "labels.json", labels.model_dump(mode="json"))
    predicted = json.loads(cameras_path.read_text())
    target_by_id = {r["frame_id"]: r for r in json.loads((dataset / "ground_truth/cameras.json").read_text())["frames"]}
    if predicted["frame_ids"] != [f.frame_id for f in manifest.frames]:
        raise ValueError("Predicted cameras do not match selected frame manifest")
    target = np.array([camera_pose(target_by_id[f.frame_id]) for f in manifest.frames])
    poses = np.asarray(predicted["camera_to_world"])
    metrics = {}
    for name, scale_fit in [("primary_metric_scale", False), ("camera_scale_diagnostic", True)]:
        try:
            r, t, s, residual = align_cameras(poses, target, scale_fit)
            aligned = transform_scene(scene, r, t, s, labels.alignment_id)
            if scale_fit:
                aligned.scale_mode = "oracle_scale"
            result = evaluate(aligned, labels, digest(manifest_path))
            result["alignment"] = {"source": "camera orientations/centers only; no object fitting",
                                   "scale": s, "rotation": r.tolist(), "translation": t.tolist(),
                                   "camera_center_rmse_m": float(np.sqrt(np.mean(residual**2)))}
            save(output / f"scene.{name}.json", aligned.model_dump(mode="json"))
            metrics[name] = result
        except ValueError as exc:
            if not scale_fit:
                raise
            metrics[name] = {"status": "unavailable", "reason": str(exc)}
    save(output / "metrics.json", metrics)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("dataset", "manifest", "scene", "cameras", "output"):
        parser.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args()
    run(args.dataset, args.manifest, args.scene, args.cameras, args.output)


if __name__ == "__main__":
    main()
