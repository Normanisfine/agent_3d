# 42899617_a3r-claude_s0 — precise static whitebox bathroom

## Final result

- **Final scene:** `runs/A3r-claude/42899617/0/scene.blend`, a copy of
  `third_party/aha-3d/scenes/42899617_a3r-claude_s0/blender/room_v13.blend` (same SHA-256, `d6202695…`).
- **Build script:** `scenes/42899617_a3r-claude_s0/build/build_room.py` regenerates the scene from code.
- **Coordinates:** the Pi3X aligned room frame (predicted, uncalibrated metres; floor at z=0).
- **Objects:** 27 semantic roots, each with its own `instance_id`:
  - Structure: `room_shell` (walls, door opening, ceiling), `floor`, `wainscot`, `skirting_north`, `tub_tiles`, `sink_splashback`, `door_frame`.
  - Fixtures and objects: `door_leaf`, `bathtub`, `bath_tap`, `bath_mat`, `mirror_tub`, `sink`, `sink_trap`, `plug_adapter`, `trash_can`, `towel_radiator`, `mirror_sink`, `mirror_light`, `picture_north`, `picture_east`, `toilet`, `toilet_ledge`, `toilet_brush`, `toilet_roll`, `ceiling_light_toilet`, `ceiling_light_main`.
- **Acceptance:** the check for candidate `14313589c6e2…` returns `accepted / permitted: true`. All four checks passed: layout, preview, technical and final_review. Delivery `whitebox-v13` is registered and selected (`deliveries/42899617_a3r-claude_s0/selected.json`).
- **Delivery stills:** `deliveries/42899617_a3r-claude_s0/v13/views/` contains plan, front and side views plus source-camera stills for frames 37, 297 and 556. `contact_sheet.jpg` shows the stills next to their source frames.

## Stages that ran

1. **Intake:** `bash tools/indoor intake …` → `intake/` (status `ready_for_authoring`). The acceptance scope was initialised for task `room42899617-a3r-claude`, using the claim that was already registered for this run.
2. **Reference analysis:** reused the bundle without re-running Pi3X or SAM3. I took wall, floor, ceiling and fixture extents from the aligned point layers (`work/*.png` plan slices and elevations). The room is L-shaped: the tub sits in an alcove, the toilet alcove has an L-shaped tiled ledge, and the door is in the west wall.
3. **Gen3D:** job `090505-5bff89` covered all 13 route items (26 generations; the limit is 30). Every candidate generated (`ok`), but `place_mesh` returned `rejected_fit` for all 26 (for example, trash-can silhouette IoU was 0.47). All route items were therefore built with code. Results are in `work/place/`.
4. **Authoring and iteration:** room_v1 to v13. Each version was compared against source frames with my own blend renders (`scenes/…/review/rv_v*_compare.jpg`) and with `quick_check` contours.
5. **Layout gate:** `layout_gate.prepare` was run through `layout/run_gate.py`. It covers X-ray/source focus views for 9 source frames (37, 74, 93, 148, 297, 390, 482, 501, 556), the ortho views and the placement check.
6. **Delivery:** final renders → candidate registration → technical check (`build/technical_check.py`) → final image review → `results register` / `results select`.

## Reviews and verdicts (codex structured image review)

| Revision | Review | Verdict | Main findings → fix |
|---|---|---|---|
| v4 | layout | rejected (also failed the schema) | boxy tub and sink, toilet lid missing → rounded boolean tub and sink, upright lid, smooth hose |
| v6 | layout | rejected (schema incomplete) | round toilet bowl, tray-like sink, flat tub interior, door header too tall → reshaped |
| v7 | layout | rejected | elliptical sink well, **flush lever on the wrong side**, over-inset tub well, flat bin lid → fixed |
| v9 | layout | rejected | toilet bowl still too round → elongated bowl, seat and foot |
| v10 | layout | reviewer said "accepted", but the contract blocked it | one optional bath-mat note and generic unreviewed areas → draped curved mat |
| v11 | layout (with and without the delivery camera cache) | **accepted**, no findings | — |
| v13 | layout | **accepted**, no findings | interpenetration fixes only |
| v11 / v13 | final stills | **accepted**, no findings | — |

The v13 layout review is recorded in `scenes/…/layout/evidence_v13/review.json`.

## Problems and how they were handled

- **All generated meshes were rejected by `place_mesh`.** I built every route item with code primitives and noted this in the decisions file.
- **The placement check on v11 found 5 interpenetrations.** The worst was the trash can 4 cm into the ledge; the others involved the sink and wainscot, the architrave and tub, and the hose and tub rim. v13 fixes these. One contact remains: the bath mat sits 0.9 cm into the tub rim, which I accepted as a textile resting on the rim.
- **The reviewer's output failed the schema in some rounds.** These rounds lost the JSON (wrong aspect labels, images missing from observations). I added explicit schema instructions to the request `context`. Raw logs are in `layout/review_v*.log`.
- **The acceptance layout check needed a camera cache.** I built `delivery_cameras/stills_cameras.npz` from the native cameras (frames 37, 297, 556) and regenerated and re-reviewed the gate evidence with it.
- **The Gallery rebuild is blocked.** `results build --verify` fails on another task's scene id `45261575_A0_s0`. I did not modify it, and released the gallery claim as `blocked`.
- **In-place replacements:**
  - I deleted and rebuilt one unreviewed intermediate (`room_v12` and its evidence) under the same name.
  - `scene.blend` in this run directory was first copied from v11 and then replaced with v13, because the task names that file as the final location.

## Skipped or approximate

- **Inventory:** 19 items built and 14 skipped (`inventory_decisions.json`). The skipped items are:
  - mirror reflections: b006, b016, b030;
  - duplicates: b014, b015, b021, b024, b031;
  - parts of objects already built: b009, b023, b025, b013, b007;
  - one out-of-room false detection: b027.
- **Objects built that the inventory missed:** `toilet_roll`, `door_leaf`, `door_frame`, `wainscot`, `tub_tiles`, `sink_splashback`.
- **Limitations:**
  - Dimensions are in predicted, uncalibrated metres.
  - Mirror and glass areas are unreliable in the reference.
  - Fixtures are whitebox primitives, not sculpted ceramics.
  - No video or animation was requested or produced.
