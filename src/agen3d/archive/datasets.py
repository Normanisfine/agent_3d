"""RGB-only export from explicit frame selections, shared by both datasets.

Never hand a capture directory containing metadata to a reconstruction worker.
This capability API is not an OS sandbox; see docs/protocol.md.
"""
import json
from pathlib import Path

from PIL import Image

from .io import digest, read_model, write_new
from agen3d.archive.scene import Frame, InputManifest


class ReconstructionContext:
    def __init__(self, manifest_path: Path):
        self.root = manifest_path.resolve().parent
        self.manifest = read_model(manifest_path, InputManifest)
        self.frames = {f.frame_id: f for f in self.manifest.frames}
        self.denied = []

    def read_frame(self, frame_id: str) -> bytes:
        if frame_id not in self.frames:
            self.denied.append(frame_id)
            raise PermissionError("Only manifest frame IDs are accessible")
        frame = self.frames[frame_id]
        path = (self.root / frame.path).resolve()
        if not path.is_relative_to(self.root) or path.suffix.lower() != ".png":
            self.denied.append(frame_id)
            raise PermissionError("Frame path escapes the RGB export")
        data = path.read_bytes()
        import hashlib
        if hashlib.sha256(data).hexdigest() != frame.sha256:
            raise ValueError("Input frame changed")
        return data


def prepare_rgb(selection_path: Path, output: Path):
    """Selection keys: dataset/version/scene/split + frames[{id,path,timestamp_s}].

    Decode/re-encode to PNG to strip source metadata. Explicit timestamps avoid
    assuming FPS for simulator trajectories or irregular real captures.
    """
    selection = json.loads(selection_path.read_text())
    if output.exists():
        raise FileExistsError(output)
    frames = []
    # Validate before writing the new export.
    for i, item in enumerate(selection["frames"]):
        frames.append(Frame(frame_id=item["id"], timestamp_s=item["timestamp_s"],
                            path=f"rgb/{i:06d}.png", sha256="pending"))
    manifest = InputManifest(dataset=selection["dataset"], dataset_version=selection["version"],
                             scene_id=selection["scene"], split=selection["split"], frames=frames)
    (output / "rgb").mkdir(parents=True)
    for frame, item in zip(frames, selection["frames"]):
        source = (selection_path.parent / item["path"]).resolve()
        target = output / frame.path
        with Image.open(source) as image:
            image.convert("RGB").save(target)
        frame.sha256 = digest(target)
    write_new(output / "manifest.json", manifest)
    return manifest
