# 42898849_a3v-claude_s0 — precise static whitebox room

**Final scene:** `/home/user/6220/Project/ubuntu_final_project/runs/A3v-claude/42898849/0/scene.blend`
(a copy of `third_party/aha-3d/scenes/42898849_a3v-claude_s0/blender/room_v9.blend`).
It has 150 semantic roots, each an Empty with a unique `instance_id`. Coordinates are the
Pi3X aligned room frame (Z up, floor z=0, predicted metres, identity transform, scale 1).

**Status: delivered but not accepted.** The automated image reviewer rejected all three
review rounds. The reasons were mostly stylization (see "Reviews"). The repair budget of 3 is used up.

## Stages that ran

1. **Claim and intake.** Task `room42898849-a3v-claude` claims `scenes/` and
   `deliveries/42898849_a3v-claude_s0`. The intake from the prefilled request is in `intake/`
   (`ready_for_authoring`: whitebox, stills, precise, inspection camera, no people or motion).
   Acceptance scope was initialized under `deliveries/42898849_a3v-claude_s0/acceptance/`.
2. **Reference reuse.** I reused the existing Pi3X, SAM3 and alignment bundle and did not
   rerun inference. I measured walls, openings and furniture from height-sliced plans and
   wall elevations of `mesh/layers.npz`, the 32 HD frames and their cameras, and the 141
   inventory crops. The ceiling is 2.54 m. The open-plan space is about 10.1 × 5.6 m:
   kitchen, middle area, living room with a chimney breast, and a piano alcove. A hallway
   extends 4.7 m.
3. **Authoring with code.** `work/build_room.py` builds every object from primitives,
   including the walls, windows, doors, radiators and curtains.
4. **3D generation.** I used all 30 generations: 15 items × 2 candidates (job `101144-75c6e3`,
   12 items; job `102335-73c644`, items b030, b130, b064). Only **b057** (the wood stove,
   candidate 0, silhouette IoU 0.86) passed placement. I imported it unmodified under its
   own root (`work/integrate_generated.py`). Every other candidate was `rejected_fit`, so
   those items are built with code. Placement JSONs are in `placements/`.
5. **Source comparison.** I rendered the model from all 32 cached source cameras
   (`stills_v9/render_*.png`) and composed source | model | blend sheets
   (`stills_v9/compare_{a,b,c}.jpg`). Plan, front, side and back overviews are also in
   `stills_v9/`. Repairs based on these comparisons:
   - island end trimmed
   - hall doorway narrowed and its door leaves set
   - back-kitchen window and radiator heights corrected
   - corner shelf opened
   - Christmas tree resized, then moved 0.2 m (−y) to match frames 928, 974 and 1113
   - banner moved into the doorway
6. **Layout gate.** The project's `layout_gate.prepare` and `render_blender.py` ran with 15
   source frames chosen so that every root has a plan/side view and a source focus view.
   The latest evidence is `scenes/.../work/layout_v9` (`awaiting_agent_review`).

## Reviews and verdicts

| Round | Scene | Reviewer (`acceptance review-images`, codex) | Verdict |
| --- | --- | --- | --- |
| 1 | room_v6 | 597 images reviewed | **rejected** |
| 2 | room_v8 | after repair 1: rounded sofas, bell pendants, chest/piano/chair/island detail, glazed door grids, single-slab ceiling, lower banner | **rejected** |
| 3 | room_v9 | after repair 2: tree position, French-door lower panels, squared stools (first attempt failed with "model at capacity"; retry completed) | **rejected** |

- **Schema failure.** None of the three judgments passed the contract check
  ("Required visual review views incomplete"), because the reviewer listed images as
  "Image #N" instead of their IDs. No formal layout acceptance could be recorded. The raw
  judgments are in `reviews/layout_v{6,8,9}_review_raw.json`.
- **What the round-3 blockers are about.** They concern shape fidelity of
  upholstered and organic items:
  - sofa and cushion forms
  - yucca leaves, Christmas tree tiers, garland, bouquet
  - stove front and log piles
  - chest edges, pendant glass, French-door and window proportions
  - island, piano and chair detail

  The geometry being primitive is the reason; position is no longer the problem. The tree
  misplacement found in round 2 was corrected and is not raised again.
- **My own visual review** of the source/model overlays found the structure, openings,
  cabinetry, island, sofas, tables, fireplace, piano, tree and small decor aligned with the
  source frames.
- **One mismatch I left in place.** In frame 1067 the window and radiator sit lower in
  the source than in the model. The Pi3X reference's own projection for that frame shows
  the same offset (`perception/.../source_views/source_001067_*`), so it is drift between
  that camera and the reference geometry, not a modelling error.

## Inventory (`inventory_decisions.json`)

All 141 items are handled:
- **102 built with code.**
- **1 generated** (b057).
- **38 skipped**, each with a reason. Most are duplicate detections, or parts of an
  already-built object (sofa arms, window sills, oven doors, rug fragments). One is not an
  object: b000, the "mirror", is the view through the opening.
- **Label corrections.** b103 "mirror" is the kitchen window, b105 "chair" is the hall
  door leaf, and b132/b128 are the kitchen chimney breast and beam. Each is built as that
  object.
- **Built although the detector missed them:**
  - Christmas tree, upright piano, built-in TV cupboard, goblets on the piano
  - kitchen sink and tap, worktop, glassware and ornaments on the lit shelves
  - pink box and book on the worktop, a second sill plant, beam plant, bow on the fridge column
  - island tray, heart ornament, log stacks
  - hall console, stairs, front door, doormats, banner, curtains, radiators, all windows and doors

## Problems and how I handled them

- **Generation:** 29 of 30 candidates failed the fit. Those items are built with code at
  their measured sizes. I did not edit the generated stove.
- **Layout-gate coverage:** the gate requires each object to have an ortho focus view and
  a source focus view. I picked 15 frames by greedy frustum cover, widened the side crop,
  included the ceiling, and moved the banner into the doorway.
- **Placement check** (`reviews/placement_v9_REPORT.md`, diagnostic): 53 "error"
  penetrations. Most are intended soft contacts: cushions in sofas, bouquet in vase, frames
  on sills, logs in the hearth. A few are real 2–6 cm overlaps that I did not repair:
  - the generated stove extends into the recess back wall
  - fridge column vs hall wall
  - yucca leaf tips vs wall
  - a gift vs the tree base

## Skipped or approximate

- **Approximate:** the hall stairs and front door are seen only from a distance (frame 232).
  The hallway ceiling height is assumed to be 2.54 m.
- **Not modelled:** ceiling downlights and switches or sockets (flush details).
- **Plain whitebox only.** No materials, and no video or interactive demo, per the request.
- **Not completed:** acceptance, candidate registration and selection. The reviewer
  rejected the scene and its output failed the schema. The task claim was released as `blocked` (no writers running); see the
  handoff in `tasks/room42898849-a3v-claude/`.
