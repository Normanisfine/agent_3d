You are running AHa-3D (this repository) unattended. No human is available during
the run: never wait for answers. When the workflow says to ask the user, take the
answer from the prefilled request below, record the decision, and continue.

## Task

Your working directory is the AHa-3D repository root, `/home/user/6220/Project/ubuntu_final_project/third_party/aha-3d`. Relative paths in
its docs and in this prompt are relative to that root.

This is a narrow **material revision** of an existing room, for presentation.
The base scene `/home/user/6220/Project/ubuntu_final_project/runs/A5-claude/42899617/0/scene.blend` was built and reviewed in an earlier task
from the video `/home/user/6220/Project/ubuntu_final_project/third_party/aha-3d/scenes/42899617_showcase_mat_a5/references/input.mp4`; its notes are in
`/home/user/6220/Project/ubuntu_final_project/runs/A5-claude/42899617/0/SUMMARY.md` (the base run saved no whitebox stills). The base scene is
read-only: copy it into `scenes/42899617_showcase_mat_a5/` and work on the copy.

Give the copy furnished materials and lighting that approximate what the source
video shows, then render presentation stills.

Scope is already decided and prefilled in `/home/user/6220/Project/ubuntu_final_project/runs/showcase/42899617_A5_materials/request.json`. Run
`bash tools/indoor intake --request /home/user/6220/Project/ubuntu_final_project/runs/showcase/42899617_A5_materials/request.json --out /home/user/6220/Project/ubuntu_final_project/runs/showcase/42899617_A5_materials/intake` to record it.

- **Geometry is final.** Do not move, add, delete, rescale or reshape any object.
  Only assign materials, and add lights and world lighting. Keep object names,
  semantic roots and `instance_id`s.
- **Materials.** Search the asset library (`assets/INDEX.md`) for registered
  materials first; author Principled BSDF materials where nothing fits. Approximate
  colors and finishes seen in the video: wall paint, floor, wooden furniture,
  leather and fabric, metal, glass, screens, plants, pictures and the small objects.
  Close texture matching is not required. Every visible object should get a
  plausible material; small objects should not stay grey.
- **Lighting.** Daylight through the windows plus soft interior fill, so the room
  reads like the video; avoid blown-out or very dark renders.
- Read `AGENTS.md`, `docs/INDEX.md`, `docs/SCENE_REQUESTS.md`,
  `docs/SCENE_VARIANTS.md` and `.agents/skills/blender-roomkit/SKILL.md` as needed.
- The reference geometry and source cameras are already built; reuse them and do
  not rerun Pi3X inference: `/home/user/6220/Project/ubuntu_final_project/perception/42899617/bundle` (contains `pi3x/`, `masks/`, `alignment/`,
  `mesh/`, `source_views/`, `reference_build.json`).

## Deliverables (in `/home/user/6220/Project/ubuntu_final_project/runs/showcase/42899617_A5_materials`)

- `scene.blend`: the material scene (a copy of your final `.blend`).
- `stills/`: overview, front, side and two or three interior views, at least 1600 px wide. Also render the material scene from at least
  six source-video cameras spread across the video (`/home/user/6220/Project/ubuntu_final_project/perception/42899617/bundle/source_views/`), keeping
  the frame number in each file name.
- `compare/`: at least 6 side-by-side images, source video frame on the left and
  the material render from the matched source camera on the right, for frames
  spread across the video.
- `SUMMARY.md`: what you changed, the material choices, the render settings, which
  reviews ran and their verdicts, problems and how you handled them.

## Environment (already exported in your shell)

`KIMODO_ENV`, `PI3X_PY`, `PI3X_MESH_PY`, `PI3X_UPSTREAM`, `PI3X_CHECKPOINT`,
`BLENDER_BIN` (Blender 5.2.1, also on PATH as `blender`), and `codex` on PATH for
`acceptance review-images` and `tools/review_images.py`.

## Rules

- Work only inside this repository and `/home/user/6220/Project/ubuntu_final_project/runs/showcase/42899617_A5_materials`. Do not modify files elsewhere,
  install packages, or change Python environments. Never modify `/home/user/6220/Project/ubuntu_final_project/runs/A5-claude/42899617/0`.
- Other AHa-3D tasks run on this machine at the same time in other scene
  directories; do not touch them.
- The GPU is shared. Check free memory with `nvidia-smi` before any GPU job; run
  one GPU job at a time; never kill a process you did not start.
- Never overwrite earlier outputs; always write to new directories.
- Do not commit or push with git.
