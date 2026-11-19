"""Export selected RGB only. This module never opens the ground_truth directory."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from agen3d.io import digest
from agen3d.schema import Frame, InputManifest
from ..store import save


def prepare(source: Path, output: Path, count: int, scene_id: str, dataset_kind="generic"):
    """Accept a video, a frame folder, or an RGB reference folder with manifest.

    Video decoding is done here, after the caller starts the run timer. Without
    capture timestamps, image folders get explicitly synthetic ordinal timestamps.
    """
    target = output / "inputs"
    (target / "rgb").mkdir(parents=True)
    if source.is_file():
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(source)],
            check=True, capture_output=True, text=True)
        records = json.loads(probe.stdout)["frames"]
        capture = {"build": "user-video", "frames": [
            {"frame_id": f"{i:06d}", "timestamp_s": float(r["best_effort_timestamp_time"])}
            for i, r in enumerate(records)]}
    elif (source / "manifest.json").exists():
        capture = json.loads((source / "manifest.json").read_text())
    else:
        paths = sorted(p for p in source.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"})
        capture = {"build": "user-rgbs-ordinal-timestamps", "frames": [
            {"frame_id": f"{i:06d}", "timestamp_s": float(i), "path": p.name}
            for i, p in enumerate(paths)]}
    indices = np.linspace(0, len(capture["frames"]) - 1, count).round().astype(int)
    if len(set(indices)) != count:
        raise ValueError("Not enough distinct source frames")
    if source.is_file():
        # Exact frame indices, rather than FPS resampling that changes the treatment.
        selection = "+".join(f"eq(n\\,{int(i)})" for i in indices)
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(source), "-vf", f"select={selection}",
            "-vsync", "0", str(target / "rgb/decoded_%06d.png")], check=True)
        decoded = sorted((target / "rgb").glob("decoded_*.png"))
        if len(decoded) != count:
            raise ValueError("Video decoder did not produce the exact selected frame count")
    frames = []
    for offset, index in enumerate(indices):
        record = capture["frames"][int(index)]
        filename = f"rgb/{record['frame_id']}.png"
        if source.is_file():
            decoded[offset].rename(target / filename)
        else:
            path = (source / record["path"]).resolve()
            if not path.is_relative_to(source.resolve()) or (record.get("sha256") and digest(path) != record["sha256"]):
                raise ValueError("Source image path/hash mismatch")
            if path.suffix.lower() == ".png":
                shutil.copyfile(path, target / filename)
            else:
                Image.open(path).convert("RGB").save(target / filename)
        frames.append(Frame(frame_id=record["frame_id"], timestamp_s=record["timestamp_s"],
                            path=filename, sha256=digest(target / filename)))
    manifest = InputManifest(dataset=dataset_kind, dataset_version=capture.get("build", "user-input"),
        scene_id=scene_id, split="train", frames=frames)
    save(target / "manifest.json", manifest.model_dump(mode="json"))
    # Native RGB is retained; overview sheets do not replace evidence for small objects.
    for group in range(0, count, 4):
        canvas = Image.new("RGB", (1024, 736), "white")
        draw = ImageDraw.Draw(canvas)
        for offset, frame in enumerate(frames[group:group + 4]):
            image = Image.open(target / frame.path).convert("RGB")
            image.thumbnail((512, 340))
            x, y = (offset % 2) * 512, (offset // 2) * 368
            canvas.paste(image, (x, y + 24))
            draw.text((x + 8, y + 5), frame.frame_id, fill="black")
        canvas.save(target / f"overview_{group // 4:02d}.jpg", quality=92)
    return manifest
