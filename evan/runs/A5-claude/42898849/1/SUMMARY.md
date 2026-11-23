# Room 42898849 (A5-claude, s1): precise static whitebox, run summary

Unattended run. The scope comes from `request.json`: whitebox, stills, precise fidelity, inspection camera, no people or motion, and no variants.

## Final deliverables

- **Final scene:** `runs/A5-claude/42898849/1/scene.blend`.
  - Copy of `third_party/aha-3d/scenes/42898849_a5-claude_s1/blender/room_v9.blend`.
  - sha256 `bd48c7ae5f6e9c46ba60207574215978df18539e5f2661fab977e4ddd9b2dd44` (acceptance candidate revision 4763e8d9d1d04fe28c7f850b4a288e43c2b8b10977e71402a916626bc20eae1e).
  - 356 semantic roots. Each is an Empty with `instance_id` and `semantic_class`, with primitive mesh children.
  - Collections: Architecture, Fixtures, Furniture, Appliances, Lighting, Decor.
- **Inventory decisions:** `inventory_decisions.json`, covering all 809 items.
  - 312 built, 361 duplicate, 104 part, 32 skipped.
  - Every `built` entry maps to its own unique `instance_id`.
- **Stills:** `stills_v9/`.
  - Plan, front, side and three perspective views.
  - Exact-source-camera renders: `early_000000`, `middle_000696`, `late_001392`, plus the matching source frames.
  - Twelve `cmp_*.jpg` sheets laid out as source | whitebox | 50% blend.
- **Build code** (re-runnable, no image-to-3D):
  - `work/build_spec.py` writes the spec and decisions.
  - `work/build_blend.py` builds the Blender scene.
  - `work/render_views.py` and `work/compose.py` produce the stills.

## Scene content

- **Structure**
  - L-shaped open-plan room in the Pi3X-aligned frame (floor z=0, ceiling 2.54 m).
  - Kitchen back wall, garden wall with French doors and two windows, right wall with window, and chimney breast with fireplace opening.
  - Piano alcove, hall partition with open glazed double doors, and a short hall stub (front door, side table, lamp, picture, mat).
- **Furniture**
  - Two sofas with 10 cushions and two throws; oak side table, painted side table, console table, trunk.
  - TV cupboard with TV and lamp; corner cabinet; piano with wicker chair and stool.
  - Island with 5 bar stools; full kitchen runs, wall cabinets, open shelves and tall units; range cooker in an inglenook.
- **Small objects**, each its own instance, including:
  - 93 tree ornaments, 44 firewood logs, 14 "MERRY CHRISTMAS" letters, 8 fruit and 6 shelf glasses.
  - 4 piano goblets, 3 piano frames, candles, books, mugs, plants, figurines, gifts and NOEL letters.
  - Kettle, toaster, coffee machine, frother, knife block, bread bin, paper towel holder, etc.
- **Visible objects the detector missed**, built without an inventory item:
  - basketball, NOEL letters N/E/L, 3 gift parcels, gift log, Santa figure, plush reindeer and metal log holder;
  - bread bin, paper towel holder, casserole dish, driftwood, glass jar, paper note, sheet music;
  - shelf sign, gold figurine, orange figurine, jute bag, bag on the tall unit, hall radiator.
- **Skipped items (32):**
  - 30 are garden or patio scenery seen through the glass: soccer goals, hedges and trees, patio chairs and table.
  - `c615` is a blurred rug edge with nothing at that place.
  - `c779` is bare hall floor.

## Stages run

1. **Claim and scope.** Task `room42898849-a5-claude-s1`, owner `claude-a5-42898849-s1`.
   - Recorded with `tools/indoor intake`, output in `intake/`.
   - Acceptance scope initialized under `deliveries/42898849_a5-claude_s1/acceptance/…`.
2. **Reference reuse.** The prepared Pi3X/SAM3/alignment bundle in `perception/42898849/bundle` was reused; Pi3X was not rerun.
   - I measured walls, counters, cabinet heights, the island and furniture footprints from `mesh/layers.npz`.
   - Matched source cameras come from `hd/cameras.json`.
3. **Inventory triage.** All 809 detections were handled using region crop sheets and source frames.
   - Repeated small items were deduplicated geometrically: ornaments 0.10 m, logs 0.07 m, fruit 0.05 m, glasses 0.045 m.
   - Everything else was assigned explicitly per object.
4. **Authoring and repair rounds, v1 to v9**, each checked against exact-source-camera renders and blends.
   - **v2:** fireplace opening widened, tree size and position, sink window, sofa back.
   - **v3:** placement-check penetrations fixed (kitchen run vs chimney jamb, coffee nook depth, hall wall through fridge, stools in island, items in walls, TV-top items).
   - **v5:** corner cabinet rebuilt lower to match frame 464 and the detector heights.
   - **v6:** trunk, yucca, ball.
   - **v7:** kitchen wall cabinets and tall units lowered to the mesh-measured 1.22–1.97 m; shelf items moved; stove door; trunk straps.
   - **v8:** hall doors rebuilt as glazed frames.
   - **v9:**
     - central rug near edge at y=3.70 (frame 0);
     - tree apex at 1.80 m (frames 928/974);
     - hearth front at x=4.35 and taller stove (frame 696);
     - narrower yucca.
5. **Layout gate.** `layout/run_gate.py` drives `aha3d.workflow.layout_gate.prepare` with the repo renderer and object packet.
   - Evidence is complete for `room_v5`: `layout/evidence_v5`, status `awaiting_agent_review`, 15 views.
   - Its placement report is at `evidence_v5/inspection/placement/`.
6. **Placement check on the final candidates:** `placement_v8/`, run on the v8 copy of `scene.blend`.
   - Remaining "errors" are intended nesting: ornaments in foliage, logs in the fireplace, fruit in the basket, blanket in the basket, cushions on sofas, and a sink inset in the worktop.
   - Two minor real issues remain: corner-cabinet shelves sink up to 5 cm into the corner walls, and the two counter runs overlap 1 cm at the L-joint.

## Reviews and verdicts

| Review | Input | Verdict |
| --- | --- | --- |
| Layout gate (`acceptance review-images`) | `layout/layout_request_v5.json`: 1122 images, about 1.1 GB | **Failed to run.** The Codex API rejected it because total image data exceeds the 536,870,912-byte per-request limit (`layout/layout_judgment_v5.log`). |
| Final views, v6 | `final_review_request.json` | Rejected, 4 blocking findings. The output failed schema validation and was not saved; raw text is in `final_review_v6b_raw.json`. |
| Final views, v8 | `final_review_request_v8.json` | **Rejected**, 7 blocking findings (`final_review_v8.json`). |
| Final views, v9 (final) | `final_review_request_v9.json` | **Rejected**, 3 blocking and 2 nonblocking findings (`final_review_v9.json`). |
| My own visual review | `work/rv_v*/cmp/*`, `stills_v9/` | Structure, kitchen runs and island, sofas, tree, piano, fireplace and TV corner register with the source at the exact cameras. The open v9 findings below are confirmed. |

**Open blocking findings**, recorded in the acceptance ledger as `final-review-v9-*` plus `layout-gate-review-transport`:

1. **Kitchen proportions:** the sink-window blind and upper cabinets are too high relative to the counter in frame 1392.
   - Frames 928 and 1021 and the global mesh disagree with each other here, so the per-frame poses are inconsistent.
2. **Trunk:** its projected extent is too large toward the right and foreground in frame 742.
3. **Stove:** too narrow, with its base too high in frame 696.
4. **Layout gate:** the review could not run, and that evidence is for v5 rather than v9.

**Acceptance status:** `incomplete`, not accepted. Blockers:
- layout review;
- preview and technical check reports, which were not recorded;
- the rejected final review.

No delivery was selected or promoted. The claim is released as `handoff`.

## Problems and how I handled them

- **Object packet coverage.** The packet needs plan/side plus source focus images for every object.
  - I chose source frames by set cover over all objects: 0, 186, 232, 464, 510, 603, 696, 742, 928, 1021, 1067, 1392.
  - I raised ortho resolution to 1800 so thin or tiny objects keep a contour.
  - I made the banner a ribbon and corrected the corner-cabinet heights so the angels project into frame 464.
- **Full disk.** The shared disk filled up (370/393 GB) during gate runs.
  - I deleted only my own failed, incomplete gate attempts: `layout/evidence_v2`, `v3`, `v4` and the partial `v6`, none of which had `evidence.json`.
  - About 2.4 GB is free afterwards.
  - I did not regenerate gate evidence for v9 (about 1.4 GB, and it can't be reviewed anyway) to avoid filling the shared disk again.
- **Reviewer entry point.** `tools/review_images.py` is not executable, so I used `bash tools/indoor acceptance review-images`. I changed no repo files.
- **Glass in renders.** Workbench renders glass panes opaque, so the inspection stills hide `surface_role=glass` panes at render time only. The scene keeps them.
- **Pi3X pose inconsistencies.** Frames 464, 1021 and 742 conflict with the global mesh and with other frames, so I generally followed the mesh plus multi-frame agreement. These are among the remaining reviewer findings.

## Not done / skipped

- No accepted delivery and no Gallery or results selection, because acceptance is blocked.
- The preview and technical acceptance check reports were not produced.
- Layout-gate evidence for the final v9 scene was not regenerated.
- No materials, people, motion or variants, as the scope requires.
- The usage-limit pause stopped earlier background watchers; their underlying jobs had either finished or were rerun.

## Key paths

- **Scene versions:** `third_party/aha-3d/scenes/42898849_a5-claude_s1/blender/room_v1.blend` … `room_v9.blend`.
- **Acceptance:** `third_party/aha-3d/deliveries/42898849_a5-claude_s1/acceptance/room42898849-a5-claude-s1/` (scope, candidates, findings, state).
- **Task:** `third_party/aha-3d/tasks/room42898849-a5-claude-s1/`.
- **Next actions:**
  - Fix the kitchen upper-cabinet heights after reconciling the frame 1392 and frame 928 poses, then the trunk footprint and stove width/base.
  - Regenerate the layout gate for the final scene, and review its per-object packet in batches under the 512 MiB request limit.
  - Record the technical and preview checks.
