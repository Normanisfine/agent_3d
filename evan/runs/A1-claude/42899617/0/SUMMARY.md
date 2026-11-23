# Summary: 42899617 / A1-claude / run 0

**Outcome:** I built and saved an editable whitebox bathroom with 51 semantic roots. It passed
technical validation, but it is **not accepted**: the automated image reviewer rejected both the
layout review and the final-view review for the final candidate. I released the task as an
unaccepted `handoff`, not as `completed`.

## Final scene
- `runs/A1-claude/42899617/0/scene.blend` is a byte-identical copy of
  `third_party/aha-3d/scenes/42899617_a1-claude_s0/blender/room_v14.blend` (sha256 prefix 6fd3aa9f952f0d8c).
- Build it reproducibly with `scenes/42899617_a1-claude_s0/build/build_room.py`.
- It uses the Pi3X aligned room frame (Z up, floor z=0), in predicted metres at scale 1 (uncalibrated).
- Measurements are in `scenes/42899617_a1-claude_s0/notes/measurements.md`.
- Delivery stills are in `scenes/42899617_a1-claude_s0/renders/v14_stills/`:
  - orthographic plan, front, side and side_toilet views, plus an overview
  - clay renders from the exact source cameras at frames 56, 278, 519, 74 and 390, each next to its decoded source frame

## Stages run
1. **Intake.** Ran `bash tools/indoor intake` with the prefilled request, output in `intake/`. Status: ready_for_authoring.
2. **Claim and acceptance scope.** Claimed task `room42899617-a1-claude` for the scene and deliveries paths. Initialized the acceptance scope with reference reconstruction, stills, no people.
3. **Reference reuse.** Used the existing Pi3X + SAM3 bundle without rerunning inference. Took the room envelope and object positions from:
   - plan height maps and wall elevations of the static points
   - per-pixel 3D lookups of named source pixels
4. **Authoring.** Built 51 roots from RoomKit-style primitives; no image-to-3D generator and no library assets fit.
   - **Structure:** floor, ceiling and 6 walls (L-shaped room with a toilet alcove and a bath bay); panelling; tiles and the tile band; dado rail; skirting; tiled boxing; door frame.
   - **Fixtures:** door and 2 handles; bathtub and bath panel; deck mixer and handset; towel; bath-wall mirror; basin with 2 taps, plug and chain, towel rail and waste trap; basin mirror and wall light; towel radiator and its switch spur; pedal bin; toilet, seat, cistern and flush lever; brush holder; roll holder and roll.
   - **Decor and ceiling:** 2 pictures, 2 crystal ceiling lights, smoke detector.
5. **Layout inspection.** For each revision I ran:
   - the native contour check and the full X-ray inspection
   - the per-object outline/focus packet with a source inventory (all 26 class counts match)
   - the placement check

   I personally inspected each object's focus images against the source frames.
6. **Repair loop.** I made 13 revisions (v2 to v14):
   - **Placement fixes:** placement errors went from 22 to 4, and the remaining 4 are intended wall fixings or the roll sitting on its spindle.
   - **Wall and trim fixes:** mirror and light heights; splashback continuous above the dado rail (frame 519); pier panelling height.
   - **Fixture shape fixes:** basin width and depth (plan X-ray); bath mixer changed from wall-mounted to deck-mounted (frames 130 and 278); towel drape; radiator rail count; toilet pedestal and lid; tapered cistern; smooth shading.
7. **Acceptance evidence.**
   - Registered candidate `29f826a9a0ff1a0e…`.
   - Technical check: passed (`review/technical_v14/`). It reopens the scene in Blender, checks the semantic roots, geometry and absence of animation, and decodes all 10 stills.

## Reviews and verdicts
| Review | Verdict |
| --- | --- |
| Layout image review on v2, v7, v9 and v12 | Schema-invalid: the reviewer left 33–45 images without observations, so these could not be recorded. Raw logs are in `scenes/.../review/`. I used their findings to drive repairs. |
| Layout image review on v14 (221 images) | Valid but **rejected**. Recorded on the layout gate (`review/layout_v14/review.json`). |
| Final-view image review on v12 | Valid but **rejected**. |
| Final-view image review on v14 (13 images) | Valid but **rejected** (`review/final_v14_judgment.json`). |
| Technical check | **Passed** |
| Preview check | Not run, because the layout review is not accepted. |
| `acceptance check` | Blocked: CHECK_LAYOUT, CHECK_PREVIEW, CHECK_FINAL_REVIEW, plus 12 open reviewer findings. |

**Remaining blocking findings**, recorded in the acceptance ledger:
- basin rim and body profile
- bath mixer, handset and hose contours
- towel drape
- crystal ceiling-light shape
- toilet lid outline
- doorway trim proportions
- frame-482 ceiling junction: probably camera-pose drift in a motion-blurred late frame

Several findings ask for things outside the requested whitebox appearance: tile joints, the print's typography and mirror reflectivity. Some contradicted earlier rounds; for example, the basin was rejected as "boxy" in v2 and as "too rounded" in v14.

## Problems and how I handled them
- **Smoke detector not covered.** The ceiling and the smoke detector had no focus coverage, so I extended the ortho crops and added source frames 74 and 482.
- **Reviewer coverage.** The image reviewer repeatedly skipped images in the large packets. I reduced the source-frame set to 6 frames, and the v14 review then covered every image.
- **Pedal bin.** The reviewer said the bin is open; frames 0 and 575 show a closed stainless lid, so I treated that as a false positive and left the lid closed.
- **Finding IDs.** The ledger rejected the reviewer's finding IDs (`F01`…). I added the blocking findings with valid IDs that reference the unchanged judgment files.
- **Scale.** No physical reference length is visible in the video, so scale is uncalibrated. The doorway width (0.66) and the door-leaf length (0.70) disagree slightly.

## Skipped or not done
- Formal acceptance and selection/promotion of the delivery, and the Gallery rebuild. These are blocked by the rejected reviews.
- The preview check.
- The hallway beyond the door: it is outside the room and is treated as context only.
- No git commits.
