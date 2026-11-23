# 42899617_a2-claude_s0: precise static whitebox bathroom

## Final scene

- **Final `.blend`:** `runs/A2-claude/42899617/0/scene.blend`. This is a byte-identical copy (sha256 prefix `40f5f18b519b0bff`) of
  `third_party/aha-3d/scenes/42899617_a2-claude_s0/blender/room_v11.blend`. A copy is also at
  `deliveries/42899617_a2-claude_s0/room_v11.blend`.
- **Generator:** `scenes/42899617_a2-claude_s0/build_room.py` (copied here). It rebuilds the room deterministically with
  `blender -b --python-exit-code 1 --python build_room.py -- --out OUT.blend`.
- **Contents:** 41 semantic roots, each an Empty with its own `instance_id` and child meshes.
  - **Structure (`structure/*`):** floor, ceiling, 6 walls (L-shaped room), door architrave on both sides, 3 wainscot runs
    with dado rail and raised panel mouldings, 2 skirtings, the tiled boxing around the toilet, bath wall tiling with the blue
    band and grout joints, and the sink splashback with grout joints.
  - **Objects (`furniture/*`):** bathtub, bath_mixer (crossheads, spout, handset, hose), bath_towel, mirror_bath, sink,
    sink_stand (under-basin towel rail), sink_tap_west, sink_tap_east, mirror_sink, mirror_strip_light, towel_radiator,
    radiator_switch_box, trash_bin, picture_abstract, toilet (pan, seat, raised lid, cistern, flush pipe, lever),
    toilet_brush, toilet_roll_holder, picture_work_hard, ceiling_lamp_alcove, ceiling_lamp_main (crystal chandeliers),
    ceiling_vent, smoke_detector, door_leaf, door_handle.
- **How it was built:** procedural primitives only (boxes, cylinders, tubes, booleans). No image-to-3D generator was
  used, and no library asset fitted these bathroom fixtures.
- **Coordinates:** authored directly in the reviewed Pi3X aligned frame (`bundle/alignment/cameras.json`), with an
  identity model-to-world transform. Units are uncalibrated predicted metres; no physical scale calibration was done.

## Stages run

1. **Claim and intake.**
   - Claim `room42899617-a2-claude` (owner `claude-a2-42899617-s0`) covers `scenes/42899617_a2-claude_s0` and
     `deliveries/42899617_a2-claude_s0`.
   - `tools/indoor intake` was run with the prefilled request; output is in `intake/`.
   - The acceptance scope (`scope.json`) was initialized with `acceptance init` (status `awaiting_review`).
2. **Reference.** Reused the given bundle: Pi3X, SAM3 masks, floor/wall alignment and TSDF mesh. Pi3X was not rerun.
3. **Measurement.**
   - Room planes and fixture extents came from plan and elevation slices of the static reference layer (`work/`).
   - Small objects were located by ray casting and triangulating source pixels with the cached cameras (`work/ray.py`,
     `work/tri.py`).
   - Measured planes: walls x=1.11/2.98/3.795, y=0.88/−0.87/−0.105; ceiling z=2.69.
4. **Room authoring.**
   - Built 11 candidates (v01–v11). Each round used a layout-inspection render (top/front/side and native-source X-ray
     overlays), the object outline export, `agent_review --all-objects` focus packets and the placement check.
   - Fixes driven by inspection included:
     - door height and width
     - toilet lid placement bug
     - roll holder position (triangulated)
     - sink stand (wall towel rail, not floor legs)
     - toilet boxing length (starts at x≈2.75)
     - tile band height (0.87–0.94)
     - splashback and mirror boundary (z=1.14)
     - "WORK HARD" poster size (0.54 × 0.63 m, ray-measured)
     - corridor-side architrave (ray-measured)
     - cistern and raised lid (ray-measured)
     - all placement penetrations (final placement check: 0 errors, 29 warnings, mostly wall-mounted items without a
       floor support, 4 unverified)
5. **Layout gate.**
   - `layout_gate.prepare` produced hash-bound evidence for v06, v07, v08, v09, v10 and v11 (`gate/ev_*`).
   - Views: top, front, side, plus source frames 19, 56, 74, 148, 297, 352, 482, 501 and 519.
6. **Stills.** `render_stills.py` (Workbench) rendered plan/front/side/iso cutaways and native source-camera views. Final
   set: `stills_final_v11/` (also in `deliveries/42899617_a2-claude_s0/stills_v11/`), with overview sheets
   `final_ortho.jpg` and `final_src.jpg`.

## Reviews and verdicts

My own visual review compared X-ray overlays and focus images for every object against matched source frames. All main
items — bath, toilet, sink, both mirrors, radiator, door and boxing — line up with the source silhouettes in plan and in
the native views. I did not register a findings ledger.

Automated image reviews with `acceptance review-images` (codex) returned **rejected** in every round:

| Candidate | Blocking findings | What happened |
| --- | --- | --- |
| v06 | 5 | Mixer, door trim, chandelier, sink/tap/cistern profiles, wainscot panels. All were repaired in v07/v08. |
| v08 | 2 | Poster size and hose loop. Both were repaired in v09/v10. |
| v10 | 4 | Corridor trim, mixer, sink profile, toilet lid/cistern. All were repaired in v11 using ray measurements. |
| v11 | 5 | Not repaired; geometry is frozen at v11 (see below). |

The v06, v08 and v11 runs also failed the adapter schema check ("Every required image needs concrete observations").
Only the v10 judgment was written as a valid file.

The v11 findings were not repaired because they contradict the evidence:

- The door handle is on the leaf's free edge (ray-measured x≈1.78, z≈1.0), not the hinge side.
- The toilet, poster, mirror and radiator are visible in the solid orthographic panels; the reviewer said they were not.
- The remaining items are fine profile detail: the basin lip, the mixer hose curve, and tile and panel spacing.

**Final status:** the layout gate is **not accepted**. The task acceptance check and Gallery selection were not run or
passed. The repair budget of 3 was exceeded (4 review rounds), so I stopped and am recording this rather than claiming
acceptance. Logs are `gate/judgment_v*.log` and requests are `gate/request_v*.json`.

## Inventory

`inventory_decisions.json` covers all 33 items: 19 built and 14 skipped.

- **Skipped as duplicates:** b014 and b031 (sink mirror), b015 (poster), b021 (towel), b024 (bath mirror), b013 (strip
  light end cap).
- **Skipped as mirror reflections or the operator's shirt:** b006, b016, b030.
- **Skipped as misclassified parts of built items:** b007 (splashback top), b009 (bath rim), b023 (bath end).
- **Skipped as outside the room:** b027.

Objects visible in the video but missing from the inventory, all built:

- toilet roll holder
- sink taps (separate roots)
- door handle and leaf
- smoke detector
- ceiling vent
- second chandelier (b011 and b028 are two distinct lamps; triangulation puts them 1.1 m apart)
- wainscot panelling, tiling and splashback

## Problems and approximations

- **Scale:** predicted metres, uncalibrated.
- **Ceiling vent:** only seen at the top edge of video frame ~90, outside all cached cameras. Its position (≈2.6, 0.35,
  ceiling) is an approximate ray estimate.
- **Mirrors:** the glass is a flat proxy panel; reflected content is excluded.
- **Fixture detail:** taps, mixer, hose, chandelier crystals and grout are simplified primitives. The basin and cistern
  are rounded boxes, not sculpted ceramics.
- **Not modelled:** the bath and basin plug/chain/overflow, door hinges, and the light switch (it is on the corridor
  wall, outside the room).
- **Shared GPU:** another process was using about 7.5 GB at the end. My jobs were single short Workbench and
  inspection renders, run one at a time.
- **Not done:** no git commits; no people/motion (out of scope); Pi3X was not rerun.

## Coordination

Claim `room42899617-a2-claude` was checkpointed and released with status `handoff` (writers stopped, delivery unaccepted). The scene/delivery directories are gitignored; there were no repository source edits.
