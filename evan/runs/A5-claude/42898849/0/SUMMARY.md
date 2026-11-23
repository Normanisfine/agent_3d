# Run summary: 42898849 / A5-claude / 0

**Result:** the scene, the inventory decisions and the evidence were delivered, but the scene is
**not accepted**. The final visual review rejected it, and the layout image review could not run
because of an API size limit (details below).

- Final scene: `runs/A5-claude/42898849/0/scene.blend`. It is a byte-identical copy of
  `third_party/aha-3d/scenes/42898849_a5-claude_s0/blender/room_v11.blend` (sha256 `aa74d5d5e835…`).
- Inventory decisions: `runs/A5-claude/42898849/0/inventory_decisions.json` (all 809 detector items).

The scene is an editable static whitebox room: an open-plan living room and kitchen, plus the piano
bay and the entrance hall. It contains **376 semantic roots**, each an Empty with its own
`instance_id` and `semantic_class` and one mesh child:

- 34 structure objects: floor, ceiling, 11 wall segments with openings, chimney breasts, 4 windows,
  French doors, 3 door sets, sills and sockets.
- 59 furniture objects.
- 8 appliances.
- 275 decor objects: 108 tree baubles, 37 logs, 8 cushions, 8 fruits, 14 banner letters, books,
  glasses, frames, plants, candles and presents.

Everything was built in code from simple shapes (boxes, cylinders, cones, spheres, prisms and text
curves). No image-to-3D generator was used.

## Stages that ran

1. **Setup and scope.** Read the repository rules, the docs index, the scene workflow, scene requests,
   layout inspection and the RoomKit skill.
   - The scene claim already existed from an earlier attempt (status blocked; its files were gone), so
     I resumed it as owner `claude-a5-42898849-s0`.
   - Ran `bash tools/indoor intake` into `…/0/intake` (whitebox, stills, inspection camera, precise,
     no people or animation).
   - Initialized acceptance scope `room42898849-a5-claude` with 14 main subjects.
   - Note: I created the scope after the first room build rather than before it.
2. **Reference reuse.** Used the existing Pi3X, SAM3, floor/wall-alignment and mesh bundle; Pi3X was
   not rerun.
   - Read the room envelope, openings and furniture footprints from height slices of
     `mesh/layers.npz`.
   - Checked against video frames sampled every 3 s plus targeted frames.
3. **Inventory triage (all 809 items).** Final counts: 340 built, 248 duplicate, 188 part, 33 skipped.
   - Reviewed 17 contact sheets of the crops.
   - Assigned furniture and structure by hand. Small objects were clustered per family (baubles, logs,
     cushions, fruit), and every pile or row member was kept as its own instance.
   - The 33 skips: 30 garden or patio items seen through the glass (football goals, outdoor chairs,
     hedges), 2 door-head detections already built as banner stars, and 1 unidentifiable blur on the
     hall floor.
   - Detections that missed real objects were added anyway: radiators, a painting, a heater bar,
     roman blinds, the curtain rod, the left banner star, the tray and sheet music on the piano, and
     the island centerpiece.
4. **Room authoring (v1 to v11, each saved as a new file).**
   - Builder: `scenes/42898849_a5-claude_s0/workflow/build_scene.py`.
   - Specs: `spec_manual.py` and `plan_inventory.py`, producing `plan_vN/objects.json`.
5. **Layout inspection and repair.** Ran the matched orthographic and native-camera inspections and
   compared them against the source myself (`review/inspection_v1…v4`). Corrections made from that:
   - Door opening and partition position (from frame-0 geometry).
   - Counter and island height (0.85 m) and island extents.
   - Side-facing cabinets that had been built rotated 90°.
   - Cooker chimney width (from frame 1392).
   - Stool positions, bay corner-cabinet size, log stacking without overlaps, and baubles hung on the
     tree.
6. **Layout-gate evidence.** Generated with `workflow/gate_prepare.py`, which calls
   `layout_gate.prepare` with the repository renderer and object-review tools, for v6, v8, v9, v10
   and v11.
   - Final set `review/layout_v11`: 21 native source frames covering early, middle and late times;
     every one of the 376 objects has an orthographic and a source-view focus image.
   - The placement check is part of this. Its remaining penetrations are deliberate (baubles inside
     the tree envelope, fruit in the bowl, cushions on the sofas).
7. **Delivery and acceptance.** Eight Workbench stills per version (`review/stills_vN`: plan, three
   cutaways, four eye-level views). Candidates v8 to v11 were registered under
   `deliveries/42898849_a5-claude_s0/`.

## Reviews and verdicts

| Review | Result |
| --- | --- |
| Main-item comparisons I did myself (14 subjects + structure, native-camera focus images vs source) | Main items aligned; the corner-cabinet size mismatch was found and fixed in v8 |
| Layout-gate image review, `acceptance review-images` on the v8 packet | **Could not run.** 1325 images (~1.03 GB) exceed the Codex API limit ("Total image data … exceeds the 536870912 byte limit"; `review/layout_v8_review.log`). Later packets are the same size, so no layout `review.json` exists |
| Final visual review v8 (9 final views) | Rejected: door/window glazing divisions, stove and log regularity, cooker front, slab-like sofas |
| Final visual review v9 (27 views: 9 required + 9 matched source/model pairs) | Response missing a required aspect, so the adapter refused it; its draft verdict was rejected (fireplace recess, table apron, piano front, trunk, basket throw, tree, island volume, cooker surround) |
| Final visual review v10 | Rejected: sofa backs/arms, fireplace recess, corner cabinet, tree, trunk |
| Final visual review v11 (final) | **Rejected.** Blocking: fireplace proportions/stove/logs, trunk body, tree branching silhouette, side-table apron. Non-blocking: sofa banding, TV/hood |
| Technical check, v11 (`workflow/technical_check.py`) | **Passed.** Reopened the .blend: 376 unique `instance_id`s, every root has geometry, all 809 decisions resolve to existing instances, all stills decode |

`indoor acceptance check` is **blocked**:
- The layout `review.json` is missing.
- Seven findings are open in the ledger: `layout-review-request-too-large` plus `v11-final-review-f01…f06`.
- The task state is `incomplete`, because the repair budget of 3 rounds is used up.
- The task claim is released as `blocked`, with a handoff in `tasks/room42898849-a5-claude/HANDOFF.md`.

## Problems and how I handled them

- **Stale claim.** A blocked claim with the same task ID existed from an earlier attempt whose files
  were gone. I resumed it, rebuilt from scratch, and appended a fresh handoff section rather than
  overwriting the old one.
- **Evidence packet coverage.** The first packets failed because thin decor (banner letters, stars,
  sockets) had no usable orthographic contour, and some objects (TV alcove, hearth, piano frames) were
  not in any chosen source frame. Fixed by:
  - looking at the "front" orthographic view from the garden side;
  - raising the orthographic resolution to 1600;
  - adding 7 source frames;
  - thickening thin decor slightly.
- **Rotated side-facing cabinets.** The left kitchen run, fridge and wall cabinets were built rotated
  90°, which showed up in frame 1206. Fixed in the spec helper.
- **Codex size limit.** The layout image review is one call carrying every image, and it cannot fit
  under the API limit for a 376-object room. I did not modify repository tools (that would be a
  separate code task). It is recorded as a blocking validator finding with the suggested fix
  (batching the review).
- **Final review keeps rejecting primitive silhouettes.** I ran 3 repair rounds:
  - glazing grids, cooker front, rolled-arm sofas;
  - island drawers, a dense tree, trunk lid, a drawer table, piano keyboard, a stacked fridge;
  - thicker sofas, a solid trunk, an arched corner cupboard, a dark fireplace recess, tree branch
    tips, leafy plants.

  The remaining findings are shape refinements of whitebox primitives. They are left open in the
  ledger rather than waived.
- **Process hygiene.** Twice my `pkill -f` pattern matched its own shell. I only stopped processes I
  had started (gate_prepare and its Blender child for superseded versions). I never touched another
  run's files.

## Skipped or approximate

- **Skipped items:** the 33 skipped detector items and their reasons are listed in
  `inventory_decisions.json`.
- **Scale:** Pi3X metres are predicted, not physically calibrated; all heights follow the Pi3X
  reference, for example counters at about 0.85.
- **Hall:** the hall beyond the double door is only seen at the start of the clip and is modelled
  simply (walls, front door, console, lamp, painting, mat, radiator).
- **Small-object counts:** these follow the deduplicated detections and their positions come from the
  detector:
  - 108 tree baubles, hung on the tree envelope;
  - 37 logs, stacked without overlap inside the fireplace niches and log bucket;
  - 8 scatter cushions and 8 fruits.
- **Simplified detail:** the tree, plants, flowers and sofa upholstery are simple shapes, which is what
  the open reviewer findings are about.
