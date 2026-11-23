# Run summary — 42898849_a1-claude_s0 (precise static whitebox room)

**Outcome:** I built and delivered an editable precise-fidelity whitebox room. It has **not passed acceptance**: the
Codex image reviewer rejected the layout on every round, and the repair budget of 3 review rounds is used up. The task
claim is released as `blocked`, not `completed`.

## Final scene
- `/home/user/6220/Project/ubuntu_final_project/runs/A1-claude/42898849/0/scene.blend`
  (a byte-identical copy of `third_party/aha-3d/scenes/42898849_a1-claude_s0/blender/room_v9.blend`).
- It has 158 semantic roots, each with its own `instance_id`. The list is in `room_v9.ids.json` next to the source `.blend`.
  It covers the walls, floor, ceiling, 4 windows, the French doors, the open hall double doors, both chimney breasts,
  2 sofas, 6 cushions, the throw, the trunk table and 2 candles, 3 side tables, the console, the piano and its chair,
  the corner shelf unit and its 6 ornaments, the TV, the TV cabinet, lamps, 4 rugs/mats, the stove, logs and hearth
  items, the full kitchen (base/wall runs, 2 tall columns, range cooker, island, 4 stools, 2 pendants), every
  visible counter item (kettle, toaster, coffee machines, frother, knife block, tea caddy, fruit bowl, bottles,
  plates, plants, books, boxes, photo frames), radiators, blinds and curtains, the Christmas tree with 5 presents,
  seasonal decor (garland, NOEL letters, banner), pictures, 5 measured downlights, and the bay plant and ball.
- Builder (code only, RoomKit semantics plus primitives, no image-to-3D): `scenes/42898849_a1-claude_s0/build_room.py`.
  A frozen copy is in `final/`.
- Basis: the Pi3X aligned world from `bundle/alignment/cameras.json` (predicted metres, uncalibrated, floor z = 0).
  Walls are rotated −1.7° to match my fitted wall planes. The model-to-world transform is identity.
- Stills: `final/views/` has the plan, two cutaway views, and native-camera renders for frames 186/696/1392 next to
  the matching source frames. `final/contact_sheet.png` and `final/views/source_comparison.png` are also there.

## Stages run
1. **Coordination:** claimed `room42898849-a1-claude` and ran intake (`intake/`, status `ready_for_authoring`).
   Acceptance scope was initialised with render=stills and no people.
2. **Source analysis:** decoded the whole 144 s video into contact sheets. I reused the Pi3X bundle without rerunning
   inference. I measured walls by plane fits and furniture positions from source frames labelled with per-pixel
   world coordinates (`work/lab_*.png`), plus top-down slices (`work/plan_*`, `work/east_*`, `work/west_*`).
3. **Authoring:** built nine distinct scene versions, `room_v1` to `room_v9`. Each was written to a new file; nothing
   was overwritten.
4. **Inspection:**
   - Ran the quick native-contour check over 15 frames.
   - Ran the common-frame layout inspection (top/front/side plus source views).
   - Produced object outlines and `agent_review --all-objects` focus packets.
   - Produced gated `layout_gate.prepare` evidence for v4, v7 and v9 (v9 uses 21 views covering all 158 objects).
5. **Reviews** (all by `acceptance review-images` via codex):

   | Round | Verdict | Output |
   |---|---|---|
   | v4 | **rejected**, 10 blocking findings | Schema-invalid (not every image had an observation). Raw kept at `v4/layout-judgment.raw_invalid.json`. |
   | v7 | **rejected**, 6 blocking findings | Valid. Saved at `v7/layout-judgment.json`. |
   | v9 | **rejected**, 8 blocking findings | Schema-invalid (it cited numbered attachments, not image IDs). Raw kept at `v9/layout-judgment.raw_invalid.json`. |

   My own visual checks of the source-camera renders found good registration of walls, openings and major furniture
   across early, middle and late frames.
6. **Delivery bookkeeping:**
   - Registered candidate `b145fa83…fe99` (purpose delivery) with final-view manifest `final/final_views.json`.
   - Recorded the 9 v9 reviewer findings in the acceptance ledger (8 blocking, 1 nonblocking).
   - `acceptance check` result is `blocked` (no accepted layout review); saved at `final/acceptance_check.json`.

## Problems and how I handled them
- **Wrong orientations and positions found in review**, all fixed and checked against source frames:
  - Corner shelf unit was facing the wall (yaw 135 changed to −135).
  - South-sofa cushions were on the front edge.
  - Sofa arm rolls had zero height.
  - Stool layout: frames 960/974/1000 show 2 stools at the island's east end and 2 on its north side; I also
    corrected the island's extent.
  - Tree height, floor lamp, south wall cabinet, ball and candle positions.
- **Gate coverage failures:** every object needs an orthographic and a source-view contour. I fixed this by
  adjusting the crops, choosing source frames by greedy cover, enlarging the note card and downlights, and keeping
  only downlights I had measured.
- **Reviewer findings on shape detail**, worked on in rounds 2–3:
  - Glazing bars and door panels.
  - Rolled, bevelled upholstery.
  - Stepped trunk, arched stove door, apron side table.
  - Branched tree, leafy yucca.
  - Flared pendant shades, folded blinds, hanging banner tiles.
- **Still open:** the remaining findings ask for curved or woven detail (coffee machines, wicker chair, dense
  hydrangea, fabric folds) and photographic-level tiny-object resolution. Some "blocking uncertainties" cannot be
  fixed by editing geometry, such as physical dimensions that cannot be measured without calibration.
- **Pi3X per-frame depth error:** some objects shift by a few centimetres between views (for example the trunk in
  frame 742). I kept positions consistent with the fused plan rather than fitting to single views.
- **Environment:** the first gated attempt failed because Kimodo's Python lacks scipy. I used `$PI3X_MESH_PY`,
  which has it.
- **GPU:** I checked memory before each Blender/Workbench job. All jobs were small and run one at a time.

## Skipped / not done
- No accepted layout review, so the preview, technical and final_review checks were not recorded. There was no
  results selection and no Gallery build. I did not mark the task completed.
- No video: the scope is stills only. There are no people or animation, as requested.
- No materials beyond neutral clay tones (whitebox scope). Registered library assets were not used; everything is
  built from parametric primitives.
- No git commits.

## Pointers
- Handoff: `third_party/aha-3d/tasks/room42898849-a1-claude/HANDOFF.md`.
- Acceptance ledger: `third_party/aha-3d/deliveries/42898849_a1-claude_s0/acceptance/room42898849-a1-claude/`.
- Work files: `work/` (labelled frames, plans, scope, inspection configs, layout specs, helper scripts).
