# 42898849 (A3r-claude, s0) — static whitebox reconstruction

**Final scene:** `/home/user/6220/Project/ubuntu_final_project/runs/A3r-claude/42898849/0/scene.blend`
(a copy of `third_party/aha-3d/scenes/42898849_a3r-claude_s0/blender/room_v8.blend`).
It has 144 semantic roots, each with its own `instance_id`. The room is authored in the Pi3X aligned world frame, using uncalibrated predicted metres.

**Acceptance status: NOT accepted.** The codex layout review rejected both v7 and v8, so the acceptance gate is blocked. Details are below.

## Stages that ran
1. **Coordination and intake.** I claimed `room42898849-a3r-claude` and ran `tools/indoor intake` (output in `intake/`). I then initialized the acceptance scope: reference reconstruction, stills, no people.
2. **Reference reuse.** I used the existing Pi3X/SAM3 bundle and did not rerun inference. From the TSDF points I made local-frame plan and elevation slices to measure the room:
   - The room is rotated −1.6° about Z.
   - Walls sit at u = −5.13 / 5.03 and w = 1.38 / 1.72 / 0.35 / 6.85. The ceiling is at 2.55 m.
   - I measured the openings (French doors, 4 windows, the double hall door), the chimney breast and the piano bay.
   - I used the camera poses to work out which way the sofas face.
3. **Authoring.** The room is code-built from primitives: `scenes/42898849_a3r-claude_s0/scripts/{rk.py, build_room.py, smalls.py}`. I iterated through v1 to v8, comparing each version against source frames with matched-camera Workbench renders (`work/cmp_v*.jpg`). Fixes along the way:
   - south wall plane and piano width
   - cooker and fridge facing the wrong way
   - chest axes
   - tree position
   - rug extents
   - island extents
   - stool row
   - cushions and throw
   - blinds embedded in the walls (a sign bug)
   - sill items intersecting the window frames
4. **3D generation.**
   - Budget: the cap is 30 candidates, counted per candidate. I requested 30 routed items with `--n-candidates 1` (job `085735-86473d`) and all 30 generated `ok`.
   - Fitting: every one of the 30 got `rejected_fit` from `place_mesh` (silhouette IoU 0.15–0.82; results in `place/*.json`). All 30 were therefore built with code.
   - The other 41 routed items also went through `gen3d_request` (job `091344-81bd8e`) and all came back `budget`, so they were code-built as well.
   - No generated mesh is in the scene.
5. **Inventory.** All 141 items were handled in `inventory_decisions.json`:
   - 103 were built (b103 maps to `window_west_sink`).
   - 38 were skipped as duplicates, parts of built objects, a reflection (b000), or out of the room (b029, the hallway lamp). Each skip has a stated reason.
   - I added objects the detector missed: Christmas tree, piano, NE alcove cupboard, curtains, Roman blinds, radiators, doors and French doors, firewood stacks, goblets, figurines, sink faucet, fridge-top plant, island board and vase, and a window-sill candle wreath.
6. **Placement check (`tools/indoor check-placement`).**
   - It started at 50 errors and is down to 13 in v8 (`deliveries/42898849_a3r-claude_s0/layout/evidence_v8/inspection/placement/`).
   - The remaining 13 are soft decor contacts: gifts tucked under tree branches, foliage touching the wall/curtain, plant canes inside the pot, stacked cushions, and garland/logs touching the chimney breast.
   - Warnings for wall-mounted and hanging items (frames, blinds, pendants, curtain rod) are expected.
7. **Layout evidence and review.**
   - I generated `layout_gate.prepare` evidence (`deliveries/.../layout/evidence_v8`). Source frames 139, 186, 510, 835, 928, 1021 and 1392 were chosen by coverage so that every object has a source focus view. A camera cache is at `deliveries/.../cameras/inspection_cameras.npz`.
   - I ran `acceptance review-images` (codex) twice:
     - **v7 → rejected.** Findings: separated-bar blinds, stepped-cone tree, undivided upper-cabinet fronts, opaque windows, regular garland/logs, flat tops that can't be told apart in the top render.
     - I repaired all of these in v8: continuous blind panels, an irregular branch tree, cabinet door fronts, bevelled tops, jittered garland and logs, and glass alpha.
     - **v8 → rejected.** Findings: angular sofa upholstery, blinds still reading as bars, sparse tree volume, schematic stove/logs/garland, flat stool shells, piano/chair articulation, curtain folds, generic small-object primitives, and windows/ceiling not legible in the solid views.
   - Both reviewer outputs also failed the schema check ("Every required image needs concrete observations"). With 443 images, the reviewer did not observe every one.
   - Raw judgments are in `deliveries/.../layout/layout_judgment_v7d.log`, `layout_judgment_v8.log` and `layout_judgment_v8_raw.json`.
8. **Final views.** `deliveries/42898849_a3r-claude_s0/final_views_v8/` contains plan, cutaway front and side, early/middle/late model renders (frames 139/696/1392) and the matching source frames.
9. **Acceptance records.**
   - Candidate `3f517572…8ca0` is registered.
   - The 9 v8 reviewer findings are persisted in the ledger (8 blocking).
   - `acceptance check` returns **blocked**: there is no accepted layout review, and the findings are open.
   - The claim was released as `handoff`, not completed. See `tasks/room42898849-a3r-claude/HANDOFF.md`.

## Problems and how they were handled
- **All generated meshes were rejected by the fitter.** I built all of those objects with primitives instead.
- **The layout gate needed a `camera_cache` bound to the candidate.** I created the cache and regenerated the evidence. I stopped the in-progress v7c review because it would have been stale.
- **Some objects had no source focus view.** I re-chose source frames by greedy coverage and raised the front/side crop heights so the ceiling is included.
- **The reviewer's findings are mostly about primitive stylization**, which a whitebox can only approximate, and its outputs never passed schema completeness. I did not fabricate a review or override its verdict.

## Skipped / not done
- No layout acceptance, final_review or technical checks were recorded; they are blocked by the rejected layout review.
- No delivery was selected and the Gallery was not rebuilt.
- No generated meshes are used.
- The hallway is only a stub. The hallway lamp (b029) and the "Merry Christmas" banner on the hallway side were not modelled.
- Room metres are uncalibrated (Pi3X predicted scale).
