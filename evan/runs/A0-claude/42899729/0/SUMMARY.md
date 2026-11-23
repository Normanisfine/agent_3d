# Summary: 42899729_a0-claude_s0, a static whitebox bedroom

**Result:** accepted and selected. The final scene is `scene.blend` in this directory. It is a byte-identical copy (sha256 `4e00d5fb…6d11`) of
`third_party/aha-3d/scenes/42899729_a0-claude_s0/blender/room_v16.blend`.
The delivery contact sheet is `delivery_stills.png`.

Scope comes from `request.json`: a whitebox appearance, `major_objects` fidelity, stills delivery, an inspection camera, and no people, motion or variants.

## Stages that ran
1. **Intake.** `bash tools/indoor intake --request … --out intake/` ran and returned `ready_for_authoring`. I claimed the task `room42899729-a0-claude` (owner `claude-a0-42899729-s0`) and initialized the acceptance scope. The scope's subjects are room_shell, window_bay, bed, nightstand, table_lamp, wardrobe, chest_of_drawers, radiator, mirror, hall_door, and the relationships bed-nightstand and wardrobe-chest_of_drawers.
2. **Reference reuse.** I used the existing Pi3X/SAM3/alignment bundle and did not rerun Pi3X. I measured the room from height-sliced TSDF points and elevations, and checked them against the source frames. The measurements are in `scenes/42899729_a0-claude_s0/MEASUREMENTS.md`. All coordinates are in the aligned Pi3X frame in uncalibrated predicted metres, with an identity model-to-world transform.
3. **Room authoring.** `scripts/build_room.py` with `review/params_vN.json` produces an editable Blender scene. It has stable semantic roots (`furniture/*` and `structure/*`), 21 IDs in total:
   - **Structure:** floor, ceiling, four walls, a corner pier, the soffit over the door wall, two windows, the deep sill/window bay, the radiator cover, skirting, two door casings and the open hall-door leaf.
   - **Furniture:** double bed (headboard, cover, pillows), nightstand with table lamp, three-door wardrobe, four-drawer chest, wall mirror and waste bin.

   I built custom primitives instead of using the asset library. The library has a four-poster bed and a six-drawer dresser, which don't match these source objects.
4. **Layout gate.** Each version went through `layout_gate.prepare`: the inspection render, per-object outlines and the `agent_review --all-objects` focus packet. I checked focus and X-ray images against the source myself, then ran the codex image reviewer. The layout spec also binds a 643-frame camera cache built from the aligned cameras.
5. **Delivery.** `scripts/render_stills.py` renders Workbench clay stills: two overviews, a plan cutaway, and renders from source cameras 104, 393 and 476. Each is paired with its decoded full-resolution video frame. These are registered as acceptance candidate `87c4176c…1ffd`.
6. **Checks.** `technical` passed 27/27 (`scripts/technical_check.py`): it reopens the .blend, checks inventory, confirms there is no animation or armature, checks bounds and floor contact, finds 0 placement-check errors, confirms every still decodes, matches artifact hashes, and fully decodes the 643-frame source video. The `preview` and `final_review` image reviews were both accepted.
7. **Selection.** `acceptance check` returned `accepted, permitted: true`. I ran `results register` and `results select` for `whitebox-v16`. The claim was released as `completed`, which re-runs the full acceptance check.

## Reviews and verdicts
| Review | Version | Verdict |
| --- | --- | --- |
| Layout (codex) | v2, v3, v5b, v6, v9b, v10 | rejected (findings below) |
| Layout | v4, v8 | reviewer said "accepted" but the contract refused it (a nonblocking finding or unreviewed areas remained) |
| Layout | v5, v11, v12, v13, v14, v16 | **accepted**, no findings. v16 is the one bound to the delivery |
| Preview | v11 | rejected (wardrobe plinth, door lever) |
| Preview | v12 | rejected; a false positive (said the door was closed) |
| Preview | v12b, v14, v16 | **accepted** |
| Final review | v12b | rejected (skirting missing) |
| Final review | v14 | rejected (radiator height) |
| Final review | v16 | **accepted**, no findings |
| Technical | v1, v12–v16 | passed 27/27 |

## Problems and how I handled them
- **Real discrepancies, fixed and rechecked in matched views:**
  - nightstand height, width and top-slab seam
  - lamp height and profile
  - hall-door leaf angle (about 4° from the right wall, taken from the leaf points) and lever handle
  - bed cover drape, pillows and headboard height
  - bin position and shape
  - radiator grille, height and extent (now a full-height cover)
  - mirror extent (projected through camera 456)
  - sill height (0.85, not 0.92)
  - wardrobe side panels and recessed plinth
  - skirting boards
- **Findings I verified as false positives using point measurements:**
  - A "dark band/opening" under the soffit is Workbench shading of the soffit's underside. Pi3X puts the underside at z=2.55 and the front face at y=-0.90, which matches the model.
  - "Bed too narrow": the dark strip is the bed's shadow on the floor (points at z=0).
  - "Door closed": the source shows the hallway through the open doorway, and the leaf points run perpendicular to the door wall.
- **Context added to reviewer requests.** I added factual notes to the review requests: rendering conventions, these measurements, and which subjects are in or out of scope (decor, rooms beyond the doorways). Hidden geometry was to be recorded as uncertainties, not as unreviewed areas. These notes are visible in the saved `*_request.json` files.
- **Missing camera cache.** Acceptance requires a camera cache in the layout spec, so I generated `cameras/source_cache` from the aligned cameras with `aha3d.workflow.camera`. `KIMODO_ENV` has no scipy, so the layout and camera tools ran with `$PI3X_MESH_PY`.
- **Placement-check leftovers.** The check reports 0 errors but still has diagnostics: an unstable result for the wall-mounted mirror and the wardrobe's physics proxy, and unverified facing or settling for some roots. These are diagnostics only.

## Skipped or not applicable
- No video, people, camera animation or variants: none were requested.
- I did not rebuild the Gallery. It scans every scene, including the other runs of this video that this task must not open; the selection record is in `deliveries/42899729_a0-claude_s0/selected.json`.
- Small decor is not modelled: towels, the poster, the picture, cushions, switches and ceiling downlights.
- Scale is uncalibrated Pi3X predicted metres. Hidden backs and the bathroom and hall interiors are uncertain.
- No git commit or push.

## Key paths (relative to `third_party/aha-3d`)
- Scene work: `scenes/42899729_a0-claude_s0/` (scripts, review history v1–v16, layout evidence `review/layout_v16/`)
- Delivery run: `runs/42899729_a0-claude_s0/20261120t112606z-render-00d0827f/` (stills_v16, technical_v16, preview_/final_review_v16)
- Acceptance: `deliveries/42899729_a0-claude_s0/acceptance/room42899729-a0-claude/`
- Handoff: `tasks/room42899729-a0-claude/HANDOFF.md`
