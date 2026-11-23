# 42899617_a5-claude_s1 — precise static whitebox bathroom

## Result
- **Final scene:** `runs/A5-claude/42899617/1/scene.blend`. This is a copy of
  `third_party/aha-3d/scenes/42899617_a5-claude_s1/blender/scene_final_v10.blend`
  (sha256 prefix `0525f362035713ea`). It was built by `build_scene.py`, which is also in this folder.
- The scene is an editable whitebox room in the Pi3X aligned room frame (from
  `bundle/alignment/cameras.json`). Units are the predicted metres, uncalibrated, scale 1, Z up, floor at z=0.
- 39 semantic roots, each with its own `instance_id`.
  - **24 objects:** bathtub, bath-mixer-tap, bath-shower-handset, bath-mat-towel, mirror-bath, sink, sink-tap-left,
  sink-tap-right, sink-plug, sink-waste-trap, sink-bracket-pipe, electrical-spur-box, mirror-sink, light-bar-sink,
  towel-radiator, painting, toilet-paper-holder, toilet-paper-roll, trash-can, toilet, toilet-cistern,
  toilet-brush-holder, poster, door. All were built from code primitives; no image-to-3D generator was used.
  - **2 lights:** ceiling-light-main, ceiling-light-alcove.
  - **13 structural roots:** floor, ceiling, wall-north, wall-south, wall-east, wall-west, wall-boxing-block,
  door-frame, skirting, wainscot-panelling, bath-wall-tiling, sink-splashback, toilet-platform (the tiled U-ledge).
- **Stills:** `stills/` (v10) has plan, front and side cutaways plus 5 source-camera views (frames 37, 148, 390, 501, 575).
  Earlier versions are kept as `scene_v6/v8/v9.blend` and `stills_v6/v8/v9`.
- **Inventory:** `inventory_decisions.json` covers all 100 detector items: 23 built, 48 duplicate, 23 part, 6 skipped.
  - Most duplicates are reflections in the two mirrors: the toilet, poster, door lever and sink light bar seen in
  the sink mirror or the bath-side mirror.
  - Skipped: the hallway curtains c008, c012, c017, c037 and the rail c061, which are outside the room and seen
  through the doorway; and c055, the operator's tablet reflected in the mirror.
  - Visible objects the list missed were also built: the door leaf, toilet-brush holder, electrical spur box,
  tiled ledge, wainscot, tiling and splashback.

## Stages run
1. Claim `room42899617-a5-claude-s1`, then intake (`intake/`), then acceptance scope init
   (`deliveries/42899617_a5-claude_s1/acceptance/room42899617-a5-claude-s1/scope.json`; render=stills, repair_budget 3).
2. Reused the existing Pi3X/SAM3/alignment bundle; no Pi3X inference was rerun. The room envelope, fixture extents
   and heights were measured from the TSDF layers (plan and elevation slices, region percentiles) and checked
   against source frames.
3. Blender build (v1 to v10), each version saved to a new directory.
4. Inspection on every candidate:
   - native contour quick_check;
   - matched layout inspection (`tools/layout_inspection/render_blender.py`: top, front and side plus 11–15 native
     frames), including the placement check;
   - object packets from `layout_gate.prepare`: export, object_outline and agent_review with all objects.
   Evidence is in `scenes/42899617_a5-claude_s1/analysis/layout_evidence_v{3,3b,6,8,9,10}`.
5. Workbench clay stills of the final scene.

## Reviews and verdicts
- My own visual checks of matched source and model views showed good alignment of the room envelope, bath, toilet,
  cistern, ledge, sink, mirrors, door frame and painting in the plan, front and side views and the native views.
- Codex image review (`acceptance review-images`):
  - **v3:** stopped by me after v6 replaced the candidate.
  - **v6:** **rejected**.
  - **v8:** **rejected**.
  - **v9:** **rejected**.
  - In all three completed runs the reviewer's JSON also failed the contract check ("Every required image needs
    concrete observations"), so the tool could not save a valid judgment. The raw judgments are in
    `reviews/layout_judgment_v{6,8,9}_raw.json`.
- Blocking findings and repairs:
  - **v6 → v8:** rounded the bath interior; rounded the sink bowl; flared the toilet foot and made the lid oval;
    added crystal-drop chandeliers; curved the bath spout; went from 13 to 22 radiator bars; moved the plug to hang
    in the basin; opened the bin top.
  - **v8 → v9:** lowered the spur box; removed the sink front roll; made the toilet pedestal taller and narrower and
    the bowl smoother; shortened the handset; added stiles and rails to the panelled wainscot.
  - **v9 → v10:** shortened the chandeliers; gave the sink a thinner lip; made the under-sink loop smaller; made the
    hose drop from the handset into the tub; made the seat thinner and the lid longer and oval.
- **v10 was not re-reviewed by Codex**, because the scope's repair budget of 3 review rounds was used up.

## Acceptance status
**Not accepted.** The layout gate has no recorded accepted review. No candidate was registered or selected, and the
task claim stays open (handoff), not completed.

Open items from the last review (v9) that v10 does not fully resolve:
- The sink's outer silhouette is still a rounded box, not the source's curved ceramic profile.
- Bath mixer and handset are simplified.
- Ceiling and doorway-head junction offsets are possibly camera-registration error; the reviewer marked this as
  uncertain.
- Nonblocking: no tile grids or panel detail beyond stiles and rails; rigid towel drape; simplified taps and cistern.

## Problems and handling
- **Booleans had no effect (v1–v5).** Parts are parented before the parent inverse is set, so each cutter was offset
  from its target. The tub, sink and bowl were therefore solid. Fixed in v6 by parenting the cutter the same way
  and baking the evaluated mesh.
- **Quick_check rejected non-cached frames.** It only accepts the 32 cached Pi3X frames; I used those.
- **No ceiling focus view.** The ceiling had no source view in the focus packet, so I added ceiling-facing frames
  74 and 482. I also added 445 and 538 so the spur box appears in the evidence.
- **Remaining placement "errors" (v10):** the shower hose lies in the tub and the plug hangs against the basin.
  Both are intended contacts. Gravity warnings on wall-mounted items are expected.

## Skipped or not done
- Final acceptance, results registration and Gallery were not done because the layout review never passed.
- Materials: whitebox, as requested.
- People: none, as requested.
- Animation: none, as requested.
- Objects outside the room (hallway curtains, step stool) were not modelled.
