# 44358442_a5-claude_s1 — precise static whitebox room (A5-claude, run 1)

**Final scene:** `runs/A5-claude/44358442/1/scene.blend`, a byte-identical copy of
`third_party/aha-3d/scenes/44358442_a5-claude_s1/blender/room_v21.blend`
(sha256 prefix `6d8c7c86fd92cf4d`). Semantics export: `scene.semantics.json`.

**Status:** delivered, but **not accepted**. The acceptance ledger is `blocked`/`incomplete`, with 3 open findings (see below). No git commit or push was made.

## What was built
- The room is authored entirely in code with primitives (boxes, cylinders, cones and polyline cables). No image-to-3D generation and no library assets were used.
  - Builder: `work/build_scene.py`. Planner: `work/plan_objects.py`.
- **388 semantic roots, each with a unique `instance_id`.** I checked this by reopening `scene.blend`.
  - **Structure:** floor, ceiling and 4 walls. The window wall has a real opening; the poster wall has the door opening.
  - **Trim and door:** skirting, coving, door frame, and the open door leaf with its handle.
  - **Window:** sash window with sill, meeting rail and glass. Curtains and curtain rod are separate.
  - **Hallway seen through the door:** floor, brick wall and side walls.
  - **Main furniture:**
    - wardrobe with doors, drawer, knobs and feet
    - desk with a two-drawer pedestal
    - desk hutch with all its shelves, dividers and small drawer
    - side table with drawer and lower shelf
    - office chair
    - daybed, plus separate mattress and duvet
    - clothes rack
    - two-tier wall shelf with brackets
    - radiator
    - pendant lamp
  - **Small objects, one root each:**
    - 180 posters on the collage wall
    - books: every detected book plus fill books, so both shelf rows are as dense as in the source
    - bottles, storage boxes, magazine files, cards and papers
    - 7 coats and 6 hangers
    - 3 window-sill pots and 1 seedling
    - shoes, slippers, pillows, blanket and jackets
    - projector, mouse, mouse pad, phone/stapler, pen, power strip and cables
    - light switch, string lights, calendar, framed picture and wall ornaments
    - in the hallway: nightstand, lamp, clock, basket, rug, sconce and picture
- **Things the detector missed that I added** (`plan_v21/extras.json`):
  - yoga mat, two clothes piles, ring light, plastic bag under the wardrobe
  - wall note, ceiling sensor, curtain rod, hallway clock, pen
  - fill books on the wall shelf
- **Coordinate frame:** the Pi3X aligned room frame from `perception/44358442/bundle/alignment/cameras.json`, scale 1, identity model-to-world.
  - The reference geometry was reused as-is; Pi3X was not rerun.
  - Heights of the shelves, pendant, radiator, window and bed arms were measured from reference points.

## Inventory decisions
File: `inventory_decisions.json`. All 884 items are covered, and every `object_id` exists in the scene.

| Action | Count | What it covers |
|---|---|---|
| built | 350 | Each maps to its own distinct object. |
| duplicate | 226 | Overlapping re-detections: posters (overlap on the wall plane), books, boxes, lamp shades, curtains, cables and so on. |
| part | 88 | Drawers, shelves and cabinet doors of the hutch, desk, side table and wardrobe; bed panels and mattress views; mouse cable; curtain hooks. |
| skipped | 220 | 218 "flower" detections that are the rose print on the duvet cover (all lie on the bed surface), plus 2 "plant" detections of garden vegetation outside the window glass. |

- Repeated objects (posters, books, bottles, coats, pots) are built one instance per physical item.
- Some detections were judged against the video and repositioned to match it:
  - c792: labelled "shelf", but the crop shows the brown shoes.
  - c1680: a curtain hook at rod height, not a clothes hanger.
  - c203 and other boxes: snapped onto their real supports.

## Stages run
1. **Claim and scope.** Claim `room44358442-a5-claude-s1`. Intake: `intake/` (ready_for_authoring). Acceptance scope initialized (render: stills, 12 subjects).
2. **Source analysis.** Frame contact sheets, inventory crop sheets (`work/crops_sheets/`), and reference point-cloud plan and height-band studies.
3. **Authoring.** Revisions v1 to v21, each saved as a new `.blend` under `scenes/44358442_a5-claude_s1/blender/`.
4. **Layout gate.** `layout_gate.prepare` produced X-ray overlays, model export, outlines and an all-object focus packet over 14 views.
   - Views: top, front, side, plus source frames 0, 32, 49, 130, 194, 243, 275, 308, 324, 372 and 453.
   - Evidence kept for v6–v10, v19 and v21. Final: `layout/v21/`.
5. **Placement check** (`tools/indoor check-placement`). Penetration errors fell from 135 (v10) to 3 (v21):
   - Two hangers inside their coats (physically correct).
   - One 1.2 cm contact between two magazine files on the hutch top.
   - Reports: `scenes/44358442_a5-claude_s1/placement/v21/`.
6. **Final stills from `scene.blend`.** In `final_views/`:
   - plan, front and side orthographic views, plus `ortho_overview.jpg`
   - 7 source-matched views (frames 32 to 502) and `source_comparison.jpg`

## Reviews and verdicts
- **Full gate review (`acceptance review-images` on the full packet): failed — timed out.**
  - The packet is 1214 images for 383 objects, and the reviewer has a fixed 600 s limit (`work/review_v6.log`).
  - I did not change the gate code, so there is no accepted layout review.
- **Reduced codex reviews** (61 images: whole-room X-ray/source views plus focus images of the 12 scope subjects). Every round returned **rejected**. I verified each finding against measurements or overlays before acting on it.

  | Version | Finding | What I did |
  |---|---|---|
  | v6 | daybed oversized; pendant shade too large and low | Both fixed in v7. |
  | v7 | pendant overcorrected; radiator top too high | Both measured and fixed in v8. |
  | v8 / v9 | window bottom too high; bed ends | Window opening re-measured. Frame 243 offset diagnosed (see below). |
  | v10 | bed head end; shelf slightly high | Head end attributed to the frame 243 camera; shelf left for v20. |
  | v19 | wall shelf boards too high (confirmed: measured 1.565 / 1.875 m instead of 1.675 / 1.93 m); wardrobe left edge; window | Shelf and wardrobe fixed in v20. Window is occluded in the cited views, and its edge matches the visible glazing. |
  | v21 (final) | Still open: daybed head end in frame 243, wardrobe outline offsets | Shelf, window, pendant and radiator findings are closed. |

  - Logs: `work/review_v*_reduced.log`. JSON is kept where the output passed the schema: `layout/v7_reduced_review.json`, `layout/v10_reduced_review.json`.
- **My own visual review.** I compared matched source and render views and blended overlays at every revision (`work/cmp_v*.jpg`, `work/blend_v20.jpg`, `final_views/source_comparison.jpg`).
  - Structure, all main furniture, the wall shelf rows, the poster collage extent, window, door and hallway line up with the source.
  - Daybed in frame 243: the side table shows the same ~40 px offset there, while bed and side table align in frames 372 and 502 (`layout/v10_daybed_frame243_camera_offset_evidence.jpg`). This points to a camera reprojection offset in frame 243, not a bed error.

## Open findings (acceptance ledger, all blocking)
- `v21-daybed-head-end-frame243`: likely a camera offset; needs confirmation against an independent landmark.
- `v21-wardrobe-outline-offsets`: a few centimetres at the occluded base and left edge.
- `full-layout-packet-review-timeout`: the full per-object packet still needs a reviewer that can process it.

## Problems and how they were handled
- **Thin wall items had no orthographic contour.** I re-aimed the side inspection view at the poster wall and gave thin wall items a minimum thickness.
- **Some objects were missing from the first five source frames.** I chose 11 source frames by greedy coverage over all 32 cached cameras.
- **A Blender transform bug** dropped object locations when a yaw was applied. Fixed in v2.
- **Many penetrations between small objects.** I added a deterministic pass that clamps heights to the shelves, keeps items inside the hutch and away from panels, separates overlapping objects, and packs shelf books into rows. I also fixed furniture conflicts by hand: side table vs desk, coats vs wardrobe, pillows vs frame, and others.
- **The disk filled up during the v20 gate run.** The machine-wide disk is shared with other runs. I deleted only my own superseded, unreviewed gate attempts (`layout/v3`, `v3b`, `v4`, `v5`, `v18`, `v20`) and reran the gate as v21. Less than 0.5 GB was free at the end.
- **`tools/review_images.py` is not executable,** so I used `indoor acceptance review-images` instead.

## Skipped or not done
- **Not accepted:** the layout gate has no accepted review (findings above).
- **Not run:** the preview, technical and final-review acceptance checks, and Gallery registration and selection, because acceptance is not permitted.
- **Claim released as `handoff`.**
- **Appearance:** whitebox only, with flat tints per object type for readability and no textures (as requested).
