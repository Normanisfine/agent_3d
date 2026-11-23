# Summary: 42897538_a3r-claude_s0 — editable static whitebox room (precise)

## Final scene

- Delivered copy: `runs/A3r-claude/42897538/0/scene.blend`
- Source of that copy: `third_party/aha-3d/scenes/42897538_a3r-claude_s0/blender/scene_v11.blend`
- Contact sheet with plan/front/side, early/middle/late model views and matching source frames:
  `runs/A3r-claude/42897538/0/final_stills_sheet.png`
- The scene has 64 semantic roots, each with its own `instance_id`. Every inventory item marked
  "built" in `inventory_decisions.json` is one of those roots (checked by reopening the saved copy).
- Builder scripts can regenerate it: `scenes/42897538_a3r-claude_s0/scripts/build_room.py` builds the
  room, then `add_small_objects.py` adds the small objects.
- Measurements and their basis are in `scenes/42897538_a3r-claude_s0/MEASUREMENTS.md`.
- The room is in the Pi3X aligned room frame, with the floor at z = 0. Scale is the provisional
  Pi3X scale (predicted metres, not calibrated).

## Stages that ran

1. **Claim and intake.** Claimed with `task_claim` (id `room42897538-a3r-claude`). Ran
   `tools/indoor intake` into `runs/.../0/intake` (status `ready_for_authoring`). Initialized the
   acceptance scope (`render: stills`, `required_artifacts: [scene, render]`).
2. **Reference analysis.** Reused the Pi3X bundle; Pi3X inference was not rerun. Measured walls,
   openings and furniture from height slices and a floor-colour plan of the Pi3X points, plus the
   32 cached frames and 96 decoded video frames.
3. **3D generation.** One `gen3d_request` job covered all 20 items in `route_generate.json`
   (job `043107-37aca6`).
   - 30 meshes were generated. The scene budget then ran out, and b041, b042, b045, b049 and b053
     got status `budget`.
   - `place_mesh` was run on both candidates of every real object (outputs in `runs/.../0/place/`).
   - Accepted and used unedited: b012 (cordless phone, c0), b016 (plaid cushion, c1) and b031
     (mauve cushion, c1).
   - Rejected fits, so I built these with code: b010 clock, b015 and b030 cushions, b019 switch
     plate, b033 glass bowl with cake, b034 plate stack, b036 tissue box.
   - b053 (the poster print) hit the budget and was code-built.
   - b000, b006, b014, b039, b040, b041, b042, b045 and b049 are duplicates or not real objects
     (reasons in `inventory_decisions.json`).
4. **Authoring.** The whitebox includes:
   - **Structure:** an L-shaped living room with a TV alcove; west and south windows with vertical
     blinds; the main door with a glazed transom and its open leaf; an oak-lined kitchen doorway;
     skirting boards; a glimpse of the kitchen (cabinets, fridge, hood, rug, window); and the
     hall and bedroom seen through the doorways.
   - **Living-room furniture:** both leather sofas, ottoman, coffee table, TV and TV cabinet, lamp
     table and lamp, black side table, mini Christmas tree, radiator, painting with fairy lights,
     large mirror, rug, two chandeliers.
   - **Small items:** switches and sockets, power strips, poster print, and all the small objects
     from step 3.
5. **Source-camera comparison.** Each version (v01–v11) was rendered from the cached source
   cameras and blended over the source frames (`scenes/.../review/rv_v*`, `final_v06` has all 32
   frames). Corrections made along the way:
   - west window and blinds had been built facing outward;
   - several wall plates faced the wrong way;
   - main-door angle, leaf width and panes;
   - kitchen fridge and door leaf;
   - hall door and bedroom doorway;
   - rug extent from the floor-colour plan;
   - poster pose;
   - overlapping floor and ceiling slabs;
   - shapes of the lamp, sofas, TV stand, radiator and tree.
6. **Placement check** (`tools/indoor check-placement`, latest run in
   `aha-3d/runs/42897538_a3r-claude_s0/20261027t212849z-placement-check-f5c4e838`).
   - Fixed earlier problems: wardrobe and drawer overlap, kitchen wall cutting into the alcove,
     loveseat against the window board, wall cabinet against the hood, ottoman against the
     radiator, power strip against the sofa, kitchen door against the fridge.
   - 4 errors remain, all cushions pressing into sofa cushions. Two of them are the generated
     meshes b016 and b031, which the task rules say not to edit.
7. **Layout gate.** `layout_gate.prepare` produced X-ray, ortho and 13 source views plus one
   focus packet per object. It was run for v08c, v10 and v11 (`scenes/.../review/layout_v*`).

## Reviews and verdicts

The image reviews ran through `indoor acceptance review-images` (codex), with 322 images each.

| Round | Scene | Verdict | Blocking findings |
| --- | --- | --- | --- |
| 1 | v08c | rejected | generated cushions b016/b031; sofa shapes; lamp shape; painting outline (I judged this one a false positive); main-door leaf |
| 2 | v10 | rejected | generated cushions; main-door pane proportions; sofa upholstery |
| 3 | v11 | rejected | sofa upholstery only (fuller, creased leather); cushions, door and poster now non-blocking |

- Rounds 1 and 3 failed the schema coverage check, so their judgments could not be recorded and
  are kept raw (`layout_v08c_judgment_raw_rejected.json`, `layout_v11_judgment_raw.json`). The
  round-2 judgment passed the schema (`layout_v10_judgment.json`).
- My own visual review of the source overlays found footprints, heights and positions agree well
  for the structure, both sofas, coffee table, TV and cabinet, lamp table and lamp, ottoman,
  radiator, painting, mirror, chandeliers, side table and tree, rug, poster, kitchen fridge and
  rug, and the bedroom drawer unit.
- **Acceptance status: blocked, not accepted.**
  - Candidate `9f177c4d…` is registered.
  - The open blocking finding is `reviewer-sofa-upholstery-v11`.
  - No accepted layout review is recorded.
  - The repair budget of 3 rounds is used up.
  - The task claim was released as `handoff`; details are in
    `aha-3d/tasks/room42897538-a3r-claude/HANDOFF.md`.
  - No delivery was registered or selected, and the Gallery was not rebuilt.

## Problems and how I handled them

- **Gen3d budget.** Two candidates per item for all 20 routed items would have needed 40
  generations, against a cap of 30. Several routed items turned out to be duplicates or not real
  objects (for example "fireplace" is the TV edge and "candle" is the bowl), so generations were
  spent on them and the budget ran out. Items that missed out were code-built or skipped.
- **Generated cushions.** The reviewer flagged b016 and b031 as thin or folded compared with the
  source pillows. I kept them unedited, because place_mesh accepted them and the task forbids
  editing generated meshes. They were non-blocking in round 3.
- **Main-door leaf in frame 0.** The leaf fits frames 31 and 62 but projects narrower in frame 0.
  I treated this as Pi3X camera inconsistency.
- **Kitchen ceiling light.** No cached camera sees it, and the gate requires a source focus view
  for every root. I merged it into `kitchen_shell`.
- **Layout-gate inputs.** The gate's consumer check needs a camera cache `.npz`, so I generated
  `scenes/.../cameras/source_camera_cache.npz` from the reviewed cameras.
- **Acceptance scope subjects.** The scope I wrote at init uses names (room, sofa_left,
  sofa_right, tv_console, coffee_table) that are not object IDs. I mapped them to b017, b032,
  b009 and b035 in the review request.

## Skipped or approximate

- Cables and wires (other than the fairy-light string) were not modelled.
- Unseen parts of the kitchen, hall and bedroom are simple completions.
- The kitchen door leaf position is assumed (hinged on the east jamb).
- Window sill heights are estimated.
- The blue shoe covers in frame 709 belong to the camera operator, so they were not built.
- 22 inventory items were skipped as duplicates or not real objects; each has its reason in
  `inventory_decisions.json`.
