You are running AHa-3D (this repository) unattended as a smoke test. No human is
available during the run: never wait for answers. When the workflow says to ask
the user, take the answer from the prefilled request below, record the decision,
and continue.

## Task

Your working directory is the AHa-3D repository root, `{{AHA}}`. Relative
paths in its docs and in this prompt are relative to that root.

Reconstruct the office in `{{AHA}}/scenes/office48_v2s/references/office48.mp4`
(10 s, 30 fps, 303 frames) as an editable static whitebox room in Blender.

Scope is already decided and prefilled in `{{REQUEST}}`:
whitebox appearance; fidelity `major_objects` (walls, floor, ceiling, windows,
doors, main furniture and salient lamps; small decor optional); delivery
`stills` (editable .blend plus preview stills from the source cameras);
inspection camera; no people, no cabinet or object motion; no variants; no
interactive demo. Run `bash tools/indoor intake --request {{REQUEST}} --out <new run dir>/intake`
to record it.

Start by reading `AGENTS.md`, then `docs/INDEX.md`, then only the stage guides
you need (`.agents/skills/indoor-scene-workflow/SKILL.md`, `docs/SCENE_REQUESTS.md`,
`docs/LAYOUT_INSPECTION.md`, `.agents/skills/blender-roomkit/SKILL.md`).

The reference geometry is already built (Pi3X + SAM3 + floor/wall alignment).
Reuse it and do not rerun Pi3X inference:
`{{REF_DIR}}` (contains `pi3x/`, `masks/`, `alignment/`, `mesh/`,
`source_views/`, `reference_build.json`).

## Environment (already exported in your shell)

`KIMODO_ENV`, `PI3X_PY`, `PI3X_MESH_PY`, `PI3X_UPSTREAM`, `PI3X_CHECKPOINT`,
`BLENDER_BIN` (Blender 5.2.1, also on PATH as `blender`). The `codex` command
on PATH is a local shim that forwards `codex exec` image reviews to Claude, so
`acceptance review-images` and `tools/review_images.py` work as documented.

## Rules

- Work only inside this repository and `{{V2S_ROOT}}`. Do not modify files
  elsewhere, install packages, or change Python environments.
- The GPU is shared with other jobs. Before any GPU job, check free memory with
  `nvidia-smi`; run one GPU job at a time; never kill a process you did not start.
- Never overwrite earlier outputs; always write to new directories.
- Do not commit or push with git.
- If a stage still fails after about three repair attempts, stop and document it.

## When you finish or stop

Write `{{OUT}}/SUMMARY.md` covering: which stages ran; the final `.blend` path
and preview stills; which reviews ran and their verdicts; problems you hit and
how you handled them; anything skipped and why.
