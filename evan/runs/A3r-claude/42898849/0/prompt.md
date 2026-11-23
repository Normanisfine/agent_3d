You are running AHa-3D (this repository) unattended. No human is available during
the run: never wait for answers. When the workflow says to ask the user, take the
answer from the prefilled request below, record the decision, and continue.

## Task

Your working directory is the AHa-3D repository root, `/home/user/6220/Project/ubuntu_final_project/third_party/aha-3d`. Relative paths in
its docs and in this prompt are relative to that root.

Reconstruct the room in `/home/user/6220/Project/ubuntu_final_project/third_party/aha-3d/scenes/42898849_a3r-claude_s0/references/input.mp4` as an
editable static whitebox room in Blender.

Scope is already decided and prefilled in `/home/user/6220/Project/ubuntu_final_project/runs/A3r-claude/42898849/0/request.json`. Run
`bash tools/indoor intake --request /home/user/6220/Project/ubuntu_final_project/runs/A3r-claude/42898849/0/request.json --out /home/user/6220/Project/ubuntu_final_project/runs/A3r-claude/42898849/0/intake` to record it.
Fidelity is `precise`: **every visible object must be built, including small ones**
(cups, bottles, books, remotes, keyboards, mice, lamps, plants, boxes, small decor).
Do not skip or merge small objects. Build them with code and simple shapes (RoomKit
primitives or library assets), or with the 3D generation tools below. Give each object
its own semantic root with an `instance_id`.

Start by reading `AGENTS.md`, then `docs/INDEX.md`, then only the stage guides you
need (`.agents/skills/indoor-scene-workflow/SKILL.md`, `docs/SCENE_REQUESTS.md`,
`docs/LAYOUT_INSPECTION.md`, `.agents/skills/blender-roomkit/SKILL.md`).

The reference geometry is already built (Pi3X + SAM3 + floor/wall alignment). Reuse
it and do not rerun Pi3X inference: `/home/user/6220/Project/ubuntu_final_project/perception/42898849/bundle` (contains `pi3x/`, `masks/`,
`alignment/`, `mesh/`, `source_views/`, `reference_build.json`).

## Environment (already exported in your shell)

`KIMODO_ENV`, `PI3X_PY`, `PI3X_MESH_PY`, `PI3X_UPSTREAM`, `PI3X_CHECKPOINT`,
`BLENDER_BIN` (Blender 5.2.1, also on PATH as `blender`), and `codex` on PATH for
`acceptance review-images` and `tools/review_images.py`.

## Rules

- Work only inside this repository and `/home/user/6220/Project/ubuntu_final_project/runs/A3r-claude/42898849/0`. Do not modify files elsewhere,
  install packages, or change Python environments.
- The GPU is shared. Check free memory with `nvidia-smi` before any GPU job; run
  one GPU job at a time; never kill a process you did not start.
- Never overwrite earlier outputs; always write to new directories.
- Other runs on this machine reconstruct the same video under other conditions.
  Do not open, copy or reuse anything from them: `scenes/42898849_*` and
  `deliveries/42898849_*` other than `42898849_a3r-claude_s0`, and the project's
  `runs/*/42898849/` folders other than `/home/user/6220/Project/ubuntu_final_project/runs/A3r-claude/42898849/0`.
- Do not commit or push with git.

## Object inventory

A detector has already listed the objects it found in the video: `/home/user/6220/Project/ubuntu_final_project/perception/42898849/inventory.json`
(a JSON list; each item has `item_id`, `category`, `center` [x, y, z] and `size`
[length, width, height] in metres in the same room coordinates as the reference
geometry, `yaw` in radians, and `best_frame` / `bbox2d_xyxy` in the original
full-resolution frame). A crop of each item from its best frame is
`/home/user/6220/Project/ubuntu_final_project/perception/42898849/inventory_crops/<item_id>.jpg`.

Treat it as a to-do list: handle **every** item. Build it, or say why you skip it
(duplicate of another item, not a real object, part of a structure you already
built, ...). The detector can be wrong: trust the video when they disagree, and
still build visible objects the inventory missed. Write your decisions to
`/home/user/6220/Project/ubuntu_final_project/runs/A3r-claude/42898849/0/inventory_decisions.json` as
`{"<item_id>": {"action": "built", "object_id": "<the instance_id you used>"}}` or
`{"<item_id>": {"action": "skipped", "reason": "..."}}`.

## 3D generation tools

Three command-line tools generate a mesh for an inventory item and fit it to the video:

- `/home/user/6220/Project/ubuntu_final_project/scripts/agent_tools/gen3d_request --scene 42898849 --items <id1,id2,...>`
  starts a background job (two mesh candidates per item) and prints a job id.
  Keep building other objects while it runs.
- `/home/user/6220/Project/ubuntu_final_project/scripts/agent_tools/gen3d_status <job_id> --scene 42898849`
  prints the job. When `status` is `done`, each candidate has `status` `ok` (with
  `candidate_id`) or a reason (`too_small`, `no_view`, `backend_error`, `budget`).
- `/home/user/6220/Project/ubuntu_final_project/scripts/agent_tools/place_mesh --scene 42898849 --item <item_id> --candidate <k>`
  fits one candidate and prints a JSON PlacementResult. If `status` is `accepted`,
  run its `blender_snippet` in Blender to import the mesh at `matrix_world`, then give
  it its own semantic root with `instance_id` = the item id. Otherwise build the
  object with code and simple shapes.

Do not edit the materials or geometry of generated meshes. A scene allows at most 30
generations in total.

## Which items to generate

Items listed in `/home/user/6220/Project/ubuntu_final_project/runs/A3r-claude/42898849/0/route_generate.json` (estimated longest side under 0.5 m) **must** go
through `gen3d_request` and then `place_mesh`; use an accepted mesh, otherwise build
the item with code and simple shapes. Build all other objects with code and simple
shapes as usual.

## When you finish or stop

Save the final scene as `/home/user/6220/Project/ubuntu_final_project/runs/A3r-claude/42898849/0/scene.blend` (a copy of your final `.blend`).
Write `/home/user/6220/Project/ubuntu_final_project/runs/A3r-claude/42898849/0/SUMMARY.md`: which stages ran; the final `.blend` path; which
reviews ran and their verdicts; problems and how you handled them; anything skipped.
