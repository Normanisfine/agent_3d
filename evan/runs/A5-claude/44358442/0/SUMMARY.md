# 44358442_a5-claude_s0: precise static whitebox bedroom

**Status: delivered, not accepted.** The editable scene is complete and its layout matches the source views. However, the visual reviewer rejected the final revision, and the full layout-gate review could not run (see Problems). Acceptance state is `incomplete` and the task claim is released as `handoff`.

## Final scene
- Run copy: `runs/A5-claude/44358442/0/scene.blend`. It is byte-identical to `third_party/aha-3d/scenes/44358442_a5-claude_s0/blender/room_v5.blend` (sha256 `722a9694bf26…`).
- The scene has 377 semantic roots, each with a unique `instance_id`:
  - 24 structure roots: floor, ceiling, walls, landing, window, door, door frame, skirting, cornice.
  - 16 furniture/fixture roots.
  - 346 objects built from the inventory.
  - 15 extra objects seen in the video but missing from the detector list. They carry a `note` property: yoga mat, floor clothes pile, a fourth window pot, landing clock, wall sensor, curtain rod and 9 hutch-compartment items.
- Coordinates are in the reviewed Pi3X reference world: predicted metres, uncalibrated, identity model transform. The room is about 2.95 × 3.10 m with a 2.23 m ceiling, plus the landing seen through the door.
- Builder code is in `scenes/44358442_a5-claude_s0/build/`: `classify.py`, `build_scene.py`, `render_views.py`, `objects.json`. Earlier builder versions sit alongside as `build_scene_v2/v3/v4.py`.

## Stages run
1. Claimed the task (`room44358442-a5-claude`), ran intake (`intake/`), and initialised acceptance scope: reference reconstruction, stills, precise.
2. Reused the existing Pi3X/SAM3/alignment bundle without rerunning inference. Derived wall, floor and ceiling planes, the door and window openings from the bundle's points, and studied source frames.
3. Triaged all 884 inventory items in `inventory_decisions.json`: 346 built, 215 duplicate, 320 part, 3 skipped.
   - **Manual crop/frame review** for furniture, garments, bags, lamps, cables and similar items.
   - **Rule-based deduplication** for books, bottles, boxes, cards, flower pots and the poster wall (169 postcards, deduplicated on the wall plane).
   - **Duvet print:** 213 "flower" detections are the duvet print, so they are marked as parts of `duvet_01`.
   - **Skipped:** two tree-foliage detections outside the window, and one aggregate poster-wall box.
4. Built and iterated the whitebox:
   - v1/v2 blockout.
   - v3 (rejected by me: garment-scaling bug).
   - v4: garments and bedding fixed.
   - v5: draped duvet mesh, bevelled suitcase, open basket, hutch clutter.
5. Comparisons for each version:
   - Matched-camera layout inspection.
   - Full-resolution clay renders from the exact source cameras, shown beside the source frames (`views_v*/pairs`).
   - Plan, front, side and overview stills (`final_views/`).
6. Layout gate (`layout_gate.prepare`) produced valid evidence for v2d, v4 and v5 (17 views, every object with orthographic and source focus images). Two earlier attempts were fixed: a crop missed the ceiling, and too few source frames covered the postcards.
7. Registered acceptance candidate `efdf22e9…` (v5) and recorded the findings.

## Reviews and verdicts
- **Full layout-gate review (`acceptance review-images`, v2d packet): failed.** The packet has 1240 images, and the reviewer API rejected it for exceeding its 512 MB per-request limit (`review/layout_v2d_review.log`). The v5 packet is larger (1266 images), so it was not retried. No accepted layout review exists.
- **Compact independent review (Codex):** 8 source/model pairs plus 5 stills, through `tools/review_images.py` via a wrapper because the script lacks an executable bit. It **rejected** v2, v4 and v5; the judgments are copied here as `compact_v*_judgment.json`.
  - Fixed after v2: postcard z-fighting, flat bedding, slab-shaped coats/gown/curtains, projector and suitcase shapes.
  - Still open on v5 (recorded as findings `compact-v5-01..06`):
    - gown/chair silhouette;
    - coat volumes;
    - duvet regularity;
    - simplified hutch compartments and contents;
    - radiator shape;
    - details of the basket, suitcase, projector and landing cabinet.
  - Reviewer claims I judged wrong: it called the pendant shade cylindrical, but the source shade is a cube (frames 24 and 211).
- My own visual check: structure, furniture positions and heights, shelf books, hutch, calendar, poster wall, landing nightstand and lamp, and door all line up with frames 16, 130, 194, 243, 291, 340, 437 and 502.

## Problems and handling
- **Gate review transport limit:** the review cannot run on a 368+-object precise scene in one request. Recorded as blocking finding `layout-gate-review-transport`.
- **Primitive whitebox limits:** soft goods (coats, gown, bedding) and dense hutch clutter are simplified. The repair budget of 3 revisions was used; the remaining findings are left open, not waived.
- **Missing scale calibration:** no physical measurement exists, so dimensions are in predicted metres.
- **`acceptance check` CLI** reports `STATE_INVALID` from the layout check. The per-check evaluation shows the real blockers: open findings, layout not reviewed, and technical/preview/final-review checks not recorded.

## Not done or skipped
- No accepted layout review, technical check, final review or Gallery/results selection, so the task is not accepted or published.
- No git commits.
- Pi3X inference was not rerun.
