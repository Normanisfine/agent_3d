# Run summary — 42899712 / A0-claude / 0

**Outcome:** completed. A static, editable whitebox Blender room at `major_objects` fidelity passed every acceptance check. The delivery was registered and selected as `whitebox-v17`, and the task claim was released as `completed`. That release re-runs the full acceptance check on its own.

- **Final scene (copy):** `runs/A0-claude/42899712/0/scene.blend`. It is identical to `third_party/aha-3d/scenes/42899712_a0-claude_s0/blender/room_v17.blend`; the first 20 hex characters of both sha256 hashes are `2f7a3524cd5356c55a15`.
- **Final stills (copy):** `stills_v17/` holds the plan, front and side views, the native-camera renders (early / middle / late), and the matching source frames.
- **Acceptance candidate:** `af08be972ff5b56ce7d6e9795b2327154c50e0cce4119b6b12de05c55fcda680` for task `room42899712-a0-claude`.

## Stages run

1. **Intake.** Ran `bash tools/indoor intake --request …/request.json --out …/intake`. Status: `ready_for_authoring` (whitebox, stills, inspection camera, no people or motion).
2. **Claim and acceptance scope.**
   - The claim `room42899712-a0-claude`, owner `claude-a0-42899712-s0`, was already registered for this scene, and I used it.
   - I initialized the acceptance scope with `reference_reconstruction`, `render=stills`, 18 object subjects and 2 relationship subjects.
3. **Reference reuse.**
   - Reused the existing Pi3X, SAM3 and floor/wall bundle in `perception/42899712/bundle` without rerunning inference.
   - Measured the room from height-sliced plan views and elevations of the TSDF reference. For specific source pixels, I read 3D positions directly from the Pi3X per-pixel vertices (frames 35, 277, 346, 589, 831, 970). Details are in `scenes/42899712_a0-claude_s0/MEASUREMENTS.md`.
4. **Room authoring.**
   - `scripts/build_room.py` and `params/room_vN.json` build the room directly in the aligned Pi3X world frame. That frame is in uncalibrated predicted metres, and no transform is applied between model and world.
   - Each object has a stable ID and a tagged root. I checked the asset library first; it has no L-sofa, Z-chair, arc lamp or similar items, so all furniture is custom primitives.
   - **Contents:**
     - **Structure:** living room shell (two west windows, south hall door, kitchen opening, ceiling soffit, return wall above the cupboard, radiators), U-shaped kitchen shell, and a stub hallway.
     - **Furniture:** L-sofa with cushions, coffee table, rug, armchair, TV stand with TV, round dining table with 4 chairs, five-arm arc floor lamp, 4 wall sconces, tall tongue-and-groove cupboard, 3 kitchen counter runs (oven and hob on the south run), a tall kitchen unit, a painting and a photo.
5. **Layout gate, repeated until accepted.**
   - Each round: native-view and orthographic inspection with `render_blender.py`, then `layout_gate.prepare` (export, outlines, per-object review packet and placement check), then the Codex image review via `indoor acceptance review-images`.
   - Final evidence: 11 views (top, front, side and source frames 35/277/346/520/589/693/831/970) plus 25 per-object focus packets. The placement check reports 0 errors.
6. **Delivery stills.** `scripts/render_stills.py` renders Workbench clay images: a plan view, front and side cutaways, and the final scene from the reviewed native cameras at frames 35/520/970. A camera cache (`cameras/still_cameras.npz`) records those static cameras.
7. **Acceptance.**
   - Registered the candidate.
   - Technical check: reopened the scene, confirmed all subject roots and geometry are present, no animation, every still decodes, and 0 placement errors. Passed.
   - Final image review of the delivery stills: accepted.
   - Preview receipt: for a stills delivery this is the same reviewed set of stills.
   - `indoor acceptance check` returned accepted, `permitted: true`.
8. **Results.** Ran `results register` and `results select` for `whitebox-v17`, both accepted. Then released the task as completed.

## Reviews and verdicts

All reviews used the Codex image reviewer. Files are under `scenes/42899712_a0-claude_s0/layout/` and `checks/`.

| Review | Candidate | Verdict | Main findings |
| --- | --- | --- | --- |
| Layout v4 | room_v4 | rejected | Photo and sconces misplaced; lamp heads globe-shaped; claimed the cupboard was a radiator |
| Layout v9 | room_v9 | rejected, and output failed the schema check | Lamp arcs too high; photo; sconce_3 had no source view; missing return wall above the cupboard; cupboard identity |
| Layout v11 | room_v11 | rejected | Lamp arm shape; sofa had no cushion volumes; tall kitchen unit identity unclear |
| Layout v13 | room_v13 | rejected, and output failed the schema check | Lamp heads too high; soffit lower edge too high |
| Layout v14 | room_v14 | rejected | Reviewer saw a sixth lamp shade (overlapping shades plus arm tips) |
| Layout v15 | room_v15 | rejected | Same lamp-count problem; sconce_3 offset; north counter corner |
| Layout v16 | room_v16 | **accepted**, no findings | — |
| Final v16 | candidate 43b361a3… | "accepted" but invalid | One nonblocking finding (sconce bodies too narrow), which blocks acceptance |
| Layout v17 | room_v17 | **accepted**, no findings; recorded with `layout_gate.record_review` | — |
| Final v17 | candidate af08be97… | **accepted**, no findings | — |

Besides the automated reviewer, I compared the native renders with the source frames myself at every revision.

## Problems and how I handled them

- **Reviewer wrapper.** `tools/review_images.py` is not executable in this checkout (Permission denied). I used `bash tools/indoor acceptance review-images`, which calls `codex exec` directly without the output schema.
  - Two responses failed schema validation because aspects were combined in one string. I kept their raw JSON (`raw_judgment_v9.json`, `raw_judgment_v13.json`) and added format guidance to the request `notes`.
  - The adapter passes `-` (the stdin marker) after the `--image` arguments, and one reviewer treated it as a missing image. The request notes now explain it.
- **Python environment.** The `indoor` Python environment has no scipy, so `layout_gate.prepare` could not run there. I ran it through `$PI3X_MESH_PY` instead, without modifying either environment.
- **Missing camera cache.** The layout check needs a camera cache bound to the candidate. I generated `cameras/still_cameras.npz` with the project's `camera.interpolate`, evaluated only at the exact observed frames.
- **Relationship subjects.** The scope includes relationship subjects that the layout packet does not list, so I added them to the reviewer request.
- **Cupboard identity.** The reviewer twice called the tall cupboard a radiator. Frames 589 and 680/710 show a full-height tongue-and-groove door with a knob, and Pi3X places the knob at (−3.85, 4.73, 1.12). I kept the cupboard, added grooves and a knob, and added frame 589 as a source view.
- **Kitchen tall unit identity.** To settle what the tall kitchen unit is, I added frame 346 as a source view.
- **Placement errors in v3.** Two penetrations: the sofa plinth was a full bounding box under the rug, and a chair touched the table. Both were fixed by v4.

## Skipped or approximate

- **Gallery not rebuilt.** A rebuild scans every scene's deliveries, including the other runs of this video that this run must not open, and rewrites the shared index.
- **No git commits** were made.
- **Approximations:**
  - Furniture is primitive.
  - The hallway's length and its 2.6 m ceiling are assumed.
  - Kitchen upper cabinets, small decor (bin, side table, microwave) and window glazing are not modelled.
  - Splitting the west windows into two openings is an inference.
  - Scale is Pi3X predicted metres (uncalibrated).
- **Superseded outputs kept for history:**
  - Room versions v1–v16 and their evidence remain under `scenes/42899712_a0-claude_s0/`.
  - The interim v16 copies in this run directory were renamed to `stills_v16_superseded/`.
  - `work/` holds my measurement images.
