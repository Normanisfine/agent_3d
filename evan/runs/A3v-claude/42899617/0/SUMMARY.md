# 42899617 — precise static whitebox bathroom (A3v-claude, s0)

**Final scene:** `/home/user/6220/Project/ubuntu_final_project/runs/A3v-claude/42899617/0/scene.blend`
This is a byte-identical copy of `third_party/aha-3d/scenes/42899617_a3v-claude_s0/blender/room_v9.blend`, also delivered at `deliveries/42899617_a3v-claude_s0/v9/scene.blend`.
**Status:** built and technically valid. **Not accepted:** both image reviews rejected the final candidate (details below).

## What was built
The room is a small L-shaped bathroom, built in the aligned Pi3X frame. Units are predicted metres and uncalibrated. The floor is at z=0 and the ceiling at z≈2.68. The main area is x 1.14–3.80, y −0.10–0.875, and the bath alcove is x 1.14–2.95, y −0.86–−0.10.

There are 33 semantic roots, each with its own `instance_id`:
- **Structure:** floor, ceiling and 6 walls. The west wall has the door opening.
- **Built-ins:** door casing, panelled wainscot with dado rails and mouldings, skirting, the bath tile surround with its blue band, the sink splashback, and two tiled ledges beside the toilet.
- **Fixtures and objects:** open panelled door with brass levers, bathtub, bath/shower mixer, bath mat, toilet (raised lid, wall cistern, flush lever), brush holder, toilet-roll holder with roll, wall basin with taps, support loops and trap, pedal bin, towel radiator, radiator controller, mirror over the sink, bar light, large framed mirror over the bath, two framed prints and two crystal ceiling lights.

Everything was built with code using primitives and booleans; the build script is `scenes/42899617_a3v-claude_s0/work/build_room.py`. Placement came from Pi3X mesh slices and elevations plus HD depth lookups. Pi3X was not rerun.

## Inventory (`inventory_decisions.json`)
- **17 items built.** Their `object_id`s include `sink` (b000), `toilet` (b002), `mirror` (b004), `bathtub` (b019), `toilet_ledge_north` (b020) and `skirting` (b032).
- **16 items skipped**, each with a reason:
  - duplicates: b009, b014, b015, b021, b024, b025, b031
  - mirror reflections: b006, b016
  - sink underside or pipe, not a dispenser: b001, b026
  - mirror edge, not a toilet: b007
  - light end cap, not a speaker: b013
  - bath end, not a toilet: b023
  - hallway outside the room: b027
  - camera operator's sleeve reflected in the mirror: b030
- **Objects the detector missed, also built:** door, door casing, toilet-roll holder, radiator controller, south ledge, splashback, tile surround and wainscot.

## 3D generation
- Job `101359-6d0a5a` covered 9 items × 2 candidates (18 of the 30 allowed generations): b002, b000, b019, b018, b003, b008, b010, b017, b028. All 18 generated successfully.
- `place_mesh` rejected every candidate (`rejected_fit`; silhouette IoU 0.09–0.53). Results are in `placements/`.
- So no generated mesh is in the scene; all items are `method: code`.

## Stages that ran
1. **Claim and intake.** Claim `room42899617-a3v-claude`. Intake output is in `intake/` (`ready_for_authoring`). Acceptance scope was initialised with render `stills` and subjects bathtub, toilet, sink, mirror and door.
2. **Reference analysis.** Plan slices, wall elevations, and depth lookups on HD frames. Scripts are in `work/`.
3. **Room build.** Versions v1 to v9. Native-view contour checks (`quick_check`) were run on v1, v2, v4, v6 and v9.
4. **Layout evidence.** `layout_gate.prepare` runs, each producing an inspection, placement report and per-object packet. The final ones are `review/layout_v5`, `layout_v6`, `layout_v8` and `layout_v9`.
5. **Final views** in `review/final_views_v9/`, with a sheet in `deliveries/.../v9/stills_sheet.png`:
   - plan, front and side cutaways
   - clay renders from the source cameras at frames 56, 278 and 556, plus the matching source frames
6. **Candidate registered:** `cc0f5f44…76ef`. The technical check passed and was recorded: the scene opens, all 33 expected IDs are present with geometry, and the stills decode.

## Reviews and verdicts (codex `acceptance review-images`)
| Review | Candidate | Verdict | Blocking findings |
|---|---|---|---|
| Layout | v3 | rejected | sink profile, bath mixer, toilet-wall panelling, toilet lid shape |
| Layout | v5 | rejected | sink bowl and front rail, bath mixer |
| Layout | v6 | rejected | sink, light housing (too bulky), mixer |
| Layout | v8 | rejected | sink, mixer, mat drape, light height |
| Layout | v9 | rejected | sink, mixer, ceiling/wall seam in frame 482 |
| Final views | v9 | rejected | sink bulk, sink loops, mixer handset contour, toilet pedestal collar; mirror reflection uncertainty |

The v5 layout judgment passed schema validation; the others failed it ("every required image needs concrete observations"). Their raw judgments were kept in `review/layout_v*_raw_review.json` and are not recorded as layout reviews. The final-view rejection is recorded in the acceptance ledger as a failed `final_review` check, with findings `final-v9-f1` to `f4`.

## Problems and how they were handled
- **Fixed after verifying against source or depth:**
  - toilet lid shape: oval lid and seat
  - panelling behind the toilet: one broad inset panel
  - mixer position, measured by depth: y −0.42 to −0.62
  - mirror and light-bar height, measured by depth: mirror top 1.87, light 1.88–1.95
  - south mirror top: 1.93
  - metallic mirror material rendered black in clay previews
- **Sink and mixer stayed open.** Shape repairs on these did not converge. The reviewer's sink judgments contradicted each other between rounds (v6: walls too steep; v8/v9: bowl too deep and rounded). I stopped after the scope's repair budget of 3 was used.
- **Ceiling/wall seam in frame 482 (v9 layout finding).** This was not investigated.
- **Clay render offset.** A visual offset in the clay renders turned out to be my misreading. A camera projection test confirmed the render cameras match the source intrinsics.

## Not done or open
- Acceptance is blocked. The scope ledger has no accepted layout review, and the final review is rejected, so the claim was released as handoff, not completed.
- Open items: the sink basin shape, the bath mixer contour, the bath-mat drape, the toilet pedestal profile and the frame-482 ceiling seam.
- Unmeasured uncertainties: the exact appearance of the ceiling lights (blown out in the video), the hallway beyond the door, and the absolute scale (uncalibrated).
