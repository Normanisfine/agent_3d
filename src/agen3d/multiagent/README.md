# Room reconstruction

Use AHA-auto to build an observed indoor room from an RGB walkthrough. Use AHA-driven to choose the objects, build steps, and repairs yourself. Both controllers use the same reference cameras, Blender tools, and visual review.

## Run a room

From the Agen3D project root, use a video showing the room from several angles and choose a new output directory.

```bash
.venv/bin/python -m agen3d.multiagent.aha.cli run configs/multiagent/aha.room.json \
  --input /data/rooms/studio/walkthrough.mp4 --output recon/studio/auto --env-file .env
```

The same config starts an agent-driven session.

```bash
.venv/bin/python -m agen3d.multiagent.aha_driven.cli --env-file .env init \
  configs/multiagent/aha.room.json --input /data/rooms/studio/walkthrough.mp4 \
  --output recon/studio/driven
```

`--input` also accepts a directory containing one video. Dataset directories with `reference/original_camera_rgb.mp4` or `original_camera_rgb.mp4` use that RGB capture. If a directory contains several other videos, pass the desired file. Room geometry, cameras, and object tasks come from the selected capture.

## Inputs and output

- **Runtime.** Video preparation uses CUDA, Pi3X, and SAM 3. Construction uses Blender, Bubblewrap, the local AHa-3D checkout, and the model settings in the [room config](../../../configs/multiagent/aha.room.json). Its default worker uses `OPENROUTER_API_KEY` and its supervisor and judge use the local Codex login.
- **Prepared room.** Supply a seed `.blend`, a layout specification, and source images using the [prepared-input config](../../../configs/multiagent/aha.example.json). Omit `--input` in this mode. JSON paths are relative to the config file. CLI paths are relative to the working directory.
- **Results.** Open `report.json` for the current scene path and status. When available, `final_scene.blend` is the latest candidate export. `handoff.json` records the scene that received final layout review and its verdict.

[AHA-auto](aha/README.md) · [AHA-driven](aha_driven/README.md) · [Archive](archive/README.md)
