You are running AHa-3D (this repository) unattended. No human is available during
the run: never wait for answers. When the workflow says to ask the user, take the
answer from the prefilled request below, record the decision, and continue.

## Task

Your working directory is the AHa-3D repository root, `/home/user/6220/Project/ubuntu_final_project/third_party/aha-3d`. Relative paths in
its docs and in this prompt are relative to that root.

Reconstruct the room in `/home/user/6220/Project/ubuntu_final_project/third_party/aha-3d/scenes/44358442_a1-claude_s0/references/input.mp4` as an
editable static whitebox room in Blender.

Scope is already decided and prefilled in `/home/user/6220/Project/ubuntu_final_project/runs/A1-claude/44358442/0/request.json`. Run
`bash tools/indoor intake --request /home/user/6220/Project/ubuntu_final_project/runs/A1-claude/44358442/0/request.json --out /home/user/6220/Project/ubuntu_final_project/runs/A1-claude/44358442/0/intake` to record it.
Fidelity is `precise`: **every visible object must be built, including small ones**
(cups, bottles, books, remotes, keyboards, mice, lamps, plants, boxes, small decor).
Do not skip or merge small objects. Build them with code and simple shapes (RoomKit
primitives or library assets); do not use any image-to-3D generator. Give each object
its own semantic root with an `instance_id`.

Start by reading `AGENTS.md`, then `docs/INDEX.md`, then only the stage guides you
need (`.agents/skills/indoor-scene-workflow/SKILL.md`, `docs/SCENE_REQUESTS.md`,
`docs/LAYOUT_INSPECTION.md`, `.agents/skills/blender-roomkit/SKILL.md`).

The reference geometry is already built (Pi3X + SAM3 + floor/wall alignment). Reuse
it and do not rerun Pi3X inference: `/home/user/6220/Project/ubuntu_final_project/perception/44358442/bundle` (contains `pi3x/`, `masks/`,
`alignment/`, `mesh/`, `source_views/`, `reference_build.json`).

## Environment (already exported in your shell)

`KIMODO_ENV`, `PI3X_PY`, `PI3X_MESH_PY`, `PI3X_UPSTREAM`, `PI3X_CHECKPOINT`,
`BLENDER_BIN` (Blender 5.2.1, also on PATH as `blender`), and `codex` on PATH for
`acceptance review-images` and `tools/review_images.py`.

## Rules

- Work only inside this repository and `/home/user/6220/Project/ubuntu_final_project/runs/A1-claude/44358442/0`. Do not modify files elsewhere,
  install packages, or change Python environments.
- The GPU is shared. Check free memory with `nvidia-smi` before any GPU job; run
  one GPU job at a time; never kill a process you did not start.
- Never overwrite earlier outputs; always write to new directories.
- Other runs on this machine reconstruct the same video under other conditions.
  Do not open, copy or reuse anything from them: `scenes/44358442_*` and
  `deliveries/44358442_*` other than `44358442_a1-claude_s0`, and the project's
  `runs/*/44358442/` folders other than `/home/user/6220/Project/ubuntu_final_project/runs/A1-claude/44358442/0`.
- Do not commit or push with git.

## When you finish or stop

Save the final scene as `/home/user/6220/Project/ubuntu_final_project/runs/A1-claude/44358442/0/scene.blend` (a copy of your final `.blend`).
Write `/home/user/6220/Project/ubuntu_final_project/runs/A1-claude/44358442/0/SUMMARY.md`: which stages ran; the final `.blend` path; which
reviews ran and their verdicts; problems and how you handled them; anything skipped.
