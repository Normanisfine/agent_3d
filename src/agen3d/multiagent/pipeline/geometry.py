"""Turn predicted masks/point maps into tracked objects, never using benchmark labels."""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial import ConvexHull, QhullError

from agen3d.geometry import oriented_iou
from agen3d.schema import Box, ObjectState, Observation, SceneState
from ..store import save


def canonical_basis(points, masks):
    """Estimate floor-up from predicted floor masks; keep a documented fallback."""
    samples = []
    height, width = points.shape[1:3]
    for mask in masks:
        if mask["category"].lower() != "floor":
            continue
        pixels = np.asarray(Image.open(mask["path"]).resize((width, height), Image.Resampling.NEAREST)) > 127
        samples.append(points[mask["frame_index"]][pixels][::20])
    fallback = np.array([[1., 0, 0], [0, 0, 1], [0, -1, 0]])
    if not samples:
        return fallback, np.zeros(3), "first-camera-up fallback; floor not observed"
    cloud = np.concatenate(samples)
    cloud = cloud[np.isfinite(cloud).all(1)]
    if len(cloud) < 30:
        return fallback, np.zeros(3), "floor insufficient"
    rng = np.random.default_rng(6220)
    best = np.zeros(len(cloud), dtype=bool)
    for _ in range(128):
        a, b, c = cloud[rng.choice(len(cloud), 3, replace=False)]
        normal = np.cross(b - a, c - a)
        if np.linalg.norm(normal) < 1e-8:
            continue
        normal /= np.linalg.norm(normal)
        inside = np.abs((cloud - a) @ normal) < .04
        if inside.sum() > best.sum():
            best = inside
    if best.sum() < 30:
        return fallback, np.zeros(3), "floor plane fit failed"
    inliers = cloud[best]
    _, _, vt = np.linalg.svd(inliers - inliers.mean(0), full_matrices=False)
    up = vt[-1]
    if up @ np.array([0., -1., 0.]) < 0:
        up = -up
    right = np.array([1., 0., 0.]) - up * up[0]
    if np.linalg.norm(right) < .1:
        return fallback, np.zeros(3), "floor normal degenerate"
    right /= np.linalg.norm(right)
    rotation = np.stack([right, np.cross(up, right), up])
    translation = np.array([0., 0., -np.median(inliers @ up)])
    return rotation, translation, "RANSAC predicted floor plane"


def fit_box(points):
    """Upright PCA footprint with robust extents; orientation remains ambiguous by pi."""
    xy = points[:, :2] - np.median(points[:, :2], axis=0)
    _, vectors = np.linalg.eigh(xy.T @ xy)
    axis = vectors[:, -1]
    if axis[0] < 0:
        axis = -axis
    rotation = np.array([[axis[0], -axis[1], 0], [axis[1], axis[0], 0], [0, 0, 1.]])
    local = points @ rotation
    lo, hi = np.quantile(local, [.02, .98], axis=0)
    extent = np.maximum(hi - lo, .008)
    return Box(center=tuple(((lo + hi) / 2) @ rotation.T), extent=tuple(extent),
               rotation=tuple(map(tuple, rotation)))


def reconstruct(geometry_file, masks_file, manifest, inputs, output, max_objects=100):
    data = np.load(geometry_file)
    points = data["points"][0]
    confidence = 1 / (1 + np.exp(-np.clip(data["conf"][0, ..., 0], -30, 30)))
    masks = json.loads(Path(masks_file).read_text())["detections"]
    rotation, translation, basis_note = canonical_basis(points, masks)
    points = points @ rotation.T + translation
    cameras = data["camera_poses"][0].copy()
    cameras[:, :3, :3] = rotation @ cameras[:, :3, :3]
    cameras[:, :3, 3] = cameras[:, :3, 3] @ rotation.T + translation
    save(output / "cameras.predicted.json", {"frame_ids": [f.frame_id for f in manifest.frames],
        "camera_to_world": cameras.tolist(), "intrinsics": data["intrinsics"][0].tolist(),
        "height": points.shape[1], "width": points.shape[2],
        "basis": basis_note, "canonical_from_pi3x": {"rotation": rotation.tolist(), "translation": translation.tolist()}})
    tracks, rejected = [], []
    height, width = points.shape[1:3]
    colors = {}
    for detection in masks:
        category, index = detection["category"], detection["frame_index"]
        if category.lower() in {"floor", "wall", "ceiling"}:
            continue
        mask = np.asarray(Image.open(detection["path"]).resize((width, height), Image.Resampling.NEAREST)) > 127
        valid = mask & (confidence[index] > .2) & np.isfinite(points[index]).all(-1)
        cloud = points[index][valid]
        if len(cloud) < 12:
            rejected.append({**detection, "reason": "insufficient reliable points"})
            continue
        # Trim depth leakage around a segmentation boundary without fabricating unseen shape.
        center = np.median(cloud, axis=0)
        distances = np.linalg.norm(cloud - center, axis=1)
        cloud = cloud[distances <= np.quantile(distances, .95)]
        box = fit_box(cloud)
        if max(box.extent) > 8:
            rejected.append({**detection, "reason": "implausibly large point extent"})
            continue
        match = None
        for track in tracks:
            if track["category"] != category or index in track["frame_indices"]:
                continue
            overlap = oriented_iou(box, track["box"])
            distance = np.linalg.norm(np.array(box.center) - track["box"].center)
            if overlap > .15 or distance < .2 * min(max(box.extent), max(track["box"].extent)):
                match = track
                break
        if index not in colors:
            colors[index] = np.asarray(Image.open(inputs / manifest.frames[index].path).convert("RGB").resize((width, height)))
        color = np.median(colors[index][mask], axis=0).tolist()
        observation = {**detection, "area_fraction": float(mask.mean())}
        if match is None:
            tracks.append({"category": category, "box": box, "points": cloud[::max(1, len(cloud)//1500)],
                           "frame_indices": {index}, "observations": [observation], "color": color})
        else:
            match["points"] = np.concatenate([match["points"], cloud[::max(1, len(cloud)//1500)]])
            match["box"] = fit_box(match["points"])
            match["frame_indices"].add(index)
            match["observations"].append(observation)
    objects, mesh_specs, associations = [], {}, {}
    for number, track in enumerate(tracks[:max_objects]):
        oid = f"object_{number:03d}"
        mesh_path = output / "meshes" / f"{oid}.json"
        cloud = track["points"]
        box = track["box"]
        local = (cloud - box.center) @ np.asarray(box.rotation)
        try:
            hull = ConvexHull(local, qhull_options="QJ")
            vertices = local.tolist()
            faces = hull.simplices.tolist()
            # Orient hull faces consistently with the Qhull outward plane normal.
            for i, face in enumerate(faces):
                a, b, c = local[face]
                if np.dot(np.cross(b-a, c-a), hull.equations[i, :3]) < 0:
                    face[1], face[2] = face[2], face[1]
        except QhullError:
            rejected.append({"category": track["category"], "reason": "degenerate surface hull"})
            continue
        save(mesh_path, {"vertices": vertices, "faces": faces, "color": track["color"],
                         "representation": "convex completion of observed points; not recovered hidden geometry"})
        objects.append(ObjectState(object_id=oid, box=box, category=track["category"],
            mesh_source="generated", mesh_path=str(mesh_path),
            uncertainty="partial observed extent; front/back and occluded geometry uncertain",
            provenance=["SAM3 masks + Pi3X predicted points", "observed-point hull fallback"],
            observations=[Observation(frame_id=manifest.frames[d["frame_index"]].frame_id,
                                      mask=d["path"], track_id=oid) for d in track["observations"]]))
        mesh_specs[oid] = {"mesh": str(mesh_path), "asset_id": None, "color": track["color"]}
        associations[oid] = track["observations"]
    scene = SceneState(scene_id=manifest.scene_id, alignment_id="pi3x-predicted-world",
                       objects=objects)
    # Support is a proposal inferred from fitted boxes, not an imported GT relation.
    for obj in objects:
        candidates = []
        bottom = obj.box.center[2] - obj.box.extent[2] / 2
        for support in objects:
            if support is obj or support.box.center[2] >= obj.box.center[2]:
                continue
            top = support.box.center[2] + support.box.extent[2] / 2
            horizontal = np.abs(np.array(obj.box.center[:2]) - support.box.center[:2])
            if abs(top-bottom) < .08 and np.all(horizontal < np.array(support.box.extent[:2]) / 2):
                candidates.append((abs(top-bottom), support.object_id))
        if candidates:
            obj.support_id = min(candidates)[1]
    save(output / "scene.initial.json", scene.model_dump(mode="json"))
    save(output / "assets.json", mesh_specs)
    save(output / "associations.json", associations)
    save(output / "discarded_detections.json", {"rejected": rejected, "object_cap_dropped": max(0, len(tracks)-max_objects)})
    return scene, mesh_specs, associations
