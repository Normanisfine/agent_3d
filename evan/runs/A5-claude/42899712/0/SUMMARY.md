# 42899712_a5-claude_s0 — precise static whitebox room (run A5-claude/42899712/0)

## Result
- **Final scene:** `runs/A5-claude/42899712/0/scene.blend` (byte copy of
  `third_party/aha-3d/scenes/42899712_a5-claude_s0/blender/room_v14.blend`, sha256 `f590e815…`).
  85 semantic roots, each an Empty with its own `instance_id` and `semantic_class`
  (`structure/*`, `furniture/*`, `decor/*`, `appliance/*`, `fixture/*`, `lighting/*`, `electronics/*`).
- **Builder (reproducible):** `scenes/42899712_a5-claude_s0/scripts/build_room.py` (code-only primitives and
  RoomKit `semantics.tag_root`; no image-to-3D generator, no library assets). Authored directly in the
  aligned Pi3X room frame (identity model-to-world).
- **Inventory decisions:** `runs/A5-claude/42899712/0/inventory_decisions.json`, all 143 detector items:
  45 built, 45 duplicate, 48 part, 5 skipped (4 reflections of downlights/lights on glossy surfaces
  or walls, 1 splashback paint edge).
- **Stills:** `renders/stills_v14/` (plan, front and side cutaways, and source-camera renders for frames 35/520/1039,
  plus `source_vs_model.jpg`); also copied to `deliveries/42899712_a5-claude_s0/stills_v14/`.

## Built content
Structure: floor, living ceiling (3.0 m) with a cross beam (soffit 2.6 m), kitchen ceiling (2.33 m), hall ceiling,
walls with openings (hall doorway, kitchen opening 1.0 m wide, two sash windows with deep reveals/sills, one roller blind),
glazed double door (one leaf open into the living room, one into the hall), panel door to the left hall room.
Living/dining: L-sofa with chaise, 2 pillows, red rug, black-glass coffee table + 2 coasters, round glass dining table,
4 Z-chairs, pedal bin, white tall cabinet, 4 wall sconces, canvas print, small B&W photo, TV + 3-tier glass TV stand +
remote + shelf box, armchair, 5-shade arc floor lamp, side table + coaster tile + paper card, 3 radiators, smoke detector,
light switch, TV-wall socket, picture lying on the hall floor.
Kitchen (U-shape): front/right/back counters (doors, drawers), tall unit, 3 upper cabinets, oven, hob with pan supports,
dishwasher, sink, faucet, microwave, coffee machine, kettle, toaster, knife block, utensil holder, clear tray,
oven glove, tea towel, wall clock, 6 downlights, ceiling vent, 2 sockets.
Visible objects added that the detector missed: TV, TV stand, remote, shelf box, armchair-side radiator, white cabinet,
front-left sconce, upper cabinets, knife block, utensil holder, tray, oven glove, coasters, sockets, vent, windows, doors.

## Stages run
1. Claim (`room42899712-a5-claude`) and intake: `runs/A5-claude/42899712/0/intake/` (`ready_for_authoring`).
2. Acceptance scope init + bind: `deliveries/42899712_a5-claude_s0/acceptance/room42899712-a5-claude/scope.json`.
3. Reused the existing Pi3X/SAM3/alignment bundle (no Pi3X rerun). Room dimensions from Pi3X plan/elevation
   slices; object placement from source frames, Pi3X geometry and the detector list.
4. Iterative authoring v1–v14 with matched layout inspections (`review/inspection_*`), object outlines and
   agent-review packets, hash-bound layout gate evidence (`review/layout_gate_v4, v6, v7, v10, v11, v12, v13, v14`),
   placement checks (`third_party/aha-3d/runs/42899712_a5-claude_s0/*placement-check*`), Workbench stills.

## Reviews and verdicts
- My own visual review against source frames (35, 69, 139, 243, 277, 346, 450, 485, 520, 589, 624, 762, 866, 935, 970,
  1005, 1039): sofa, pillows, canvas, sconces, photo, TV, lamp, radiator, side table, rug, coffee table, microwave and
  kitchen appliances align in the X-ray overlays after the fixes listed below.
- Structured image reviewer (`acceptance review-images`, codex): run 3 times, **rejected every time**, and each
  response also failed the schema check (not every image had an observation), so no valid judgment file was written.
  Raw outputs are saved in `review/layout_judgment_v4_raw*.{json,log}`, `_v7_raw*` and `_v12_raw*`.
  - v4 rejected: F01 hall doorway blocked, F02 lamp stems, F03 rug too small, F04 TV too high/left, F05 kitchen/ceiling
    items lack direct source views, F06 sconce offset, F07 cloth drape. → Fixed F01–F04, F06 and F07 (v6/v7).
  - v7 rejected: lamp loops and shade shape, boxy sofa, cloth shapes, door leaf edges (plus nonblocking hob/pillow detail).
    → Lamp re-curved with open dome shades, bevelled upholstery, wider cloths, pan supports added (v11/v12).
  - v12 rejected: right pillow too high, towel too long, door edges, F05 coverage, lamp arcs above shades (nonblocking).
    → Pillow and towel fixed in v13/v14 and checked visually against frames 520/277. **v14 itself was not re-reviewed**
    because the repair budget of 3 review rounds was used up.
- Placement check on v14: one remaining error, the sink is recessed into the right counter on purpose (an inset basin).
  Other warnings are wall- or ceiling-mounted items and hanging cloths with no floor support, which is expected.
- **Acceptance status: not accepted.** No candidate was registered, no layout review accepted and no Gallery selection
  made, so the task claim stays active (checkpointed) rather than released as completed.

## Problems and handling
- The layout gate needs every object to have an ortho view and a source view. Choosing source frames to cover all
  objects (35, 69, 277, 520, 831, 970, 1005, 1039), thickening tiny fixtures and fixing wall items that faced into
  the wall resolved this.
- The doorway was originally ~0.4 m too far +x and blocked the hall view (frame 35). It was moved using rays from
  frames 35, 69 and 1039. The exact leaf swing is still uncertain (the reviewer still flags leaf edges).
- The cached Pi3X frames see the kitchen interior and ceiling poorly. The reviewer's F05 (downlights, vent, kitchen
  appliances only visible through the partition or at a distance) cannot be fixed without new source frames.
  Downlight layout (2×3 grid) is an approximation from noisy detections.
- Unknowns: hall depth and the room left of the hall, exact window heights and subdivisions, hidden furniture backs.
  Metric scale is Pi3X-predicted, not calibrated.
- `scene.blend` was first written from v7 and later replaced with the final v14 copy (both builds remain under
  `scenes/42899712_a5-claude_s0/blender/`).

## Skipped
- Detector items c130, c136, c159, c169, c188 (reasons in inventory_decisions.json).
- Not modelled: cables, wall paint bands, and hall areas outside source coverage.
