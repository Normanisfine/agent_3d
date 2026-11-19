"""Source/render evidence and numerical repair acceptance, independent of GT."""
import json

import numpy as np
from PIL import Image, ImageDraw

from ..store import save


def source_fit(render_dir, associations, camera_info):
    manifest = json.loads((render_dir / "manifest.json").read_text())
    height, width = camera_info["height"], camera_info["width"]
    views = {i: np.asarray(Image.open(render_dir / f"instances_{i:03d}.png").convert("RGB"), dtype=int)
             for i in manifest["views"]}
    scores = {}
    for oid, observations in associations.items():
        records = []
        color = np.asarray(manifest["palette"][oid])
        for observation in observations:
            index = observation["frame_index"]
            if index not in views:
                continue
            observed = np.asarray(Image.open(observation["path"]).resize((width, height), Image.Resampling.NEAREST)) > 127
            rendered = np.max(np.abs(views[index]-color), axis=2) <= 3
            union = np.logical_or(observed, rendered).sum()
            records.append({"frame_index": index, "iou": float(np.logical_and(observed, rendered).sum()/union)
                            if union else None, "source_pixels": int(observed.sum()),
                            "rendered_pixels": int(rendered.sum())})
        values = [v["iou"] for v in records if v["iou"] is not None]
        scores[oid] = {"mean_mask_iou": float(np.mean(values)) if values else None, "views": records}
    save(render_dir / "source_fit.json", scores)
    return scores


def overview_pairs(render_dir, manifest, inputs, views):
    result = []
    for index in views:
        source = Image.open(inputs / manifest.frames[index].path).convert("RGB")
        rendered = Image.open(render_dir / f"rgb_{index:03d}.png").convert("RGB")
        source = source.resize(rendered.size)
        width, height = rendered.size
        canvas = Image.new("RGB", (width*2, height+24), "white")
        canvas.paste(source, (0, 24))
        canvas.paste(rendered, (width, 24))
        draw = ImageDraw.Draw(canvas)
        draw.text((5, 4), f"SOURCE {manifest.frames[index].frame_id}", fill="black")
        draw.text((width+5, 4), "RECONSTRUCTION", fill="black")
        path = render_dir / f"comparison_{index:03d}.jpg"
        canvas.save(path, quality=92)
        result.append(path)
    return result


def object_focus(render_dir, manifest, inputs, associations, camera_info):
    """Every modeled object gets a source/render focus, not only a room-wide verdict."""
    outputs = {}
    width, height = camera_info["width"], camera_info["height"]
    views = set(json.loads((render_dir / "manifest.json").read_text())["views"])
    for oid, observations in associations.items():
        usable = [o for o in observations if o["frame_index"] in views]
        if not usable:
            continue
        observation = max(usable, key=lambda x: x["area_fraction"])
        index = observation["frame_index"]
        mask = np.asarray(Image.open(observation["path"]).resize((width,height), Image.Resampling.NEAREST)) > 127
        y, x = np.where(mask)
        if not len(x):
            continue
        bounds = (max(0,int(x.min())-20), max(0,int(y.min())-20),
                  min(width,int(x.max())+21), min(height,int(y.max())+21))
        source = Image.open(inputs / manifest.frames[index].path).convert("RGB").resize((width,height)).crop(bounds)
        rendered = Image.open(render_dir / f"rgb_{index:03d}.png").convert("RGB").crop(bounds)
        canvas = Image.new("RGB", (640, 360), "white")
        for offset, image in enumerate([source, rendered]):
            image.thumbnail((320, 330))
            canvas.paste(image,(offset*320,30))
        ImageDraw.Draw(canvas).text((5,5), f"{oid}: source (left) / reconstruction (right)",fill="black")
        path = render_dir / f"focus_{oid}.jpg"
        canvas.save(path, quality=92)
        outputs[oid] = path
    return outputs


def accept_repair(before, after, changed_ids, before_issues, after_issues):
    """Require source-fit improvement and no regression in basic geometry checks."""
    if not changed_ids or after_issues > before_issues:
        return False
    improved = False
    for oid in before:
        a, b = before[oid]["mean_mask_iou"], after.get(oid, {}).get("mean_mask_iou")
        if a is None or b is None:
            if oid in changed_ids:
                return False
            continue
        if b < a - .01:
            return False
        if oid in changed_ids and b > a + .005:
            improved = True
    return improved
