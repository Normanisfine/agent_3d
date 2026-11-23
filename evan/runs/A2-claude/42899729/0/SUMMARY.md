# SUMMARY — 42899729_a2-claude_s0, precise static whitebox bedroom

## Final result
- Final scene: `runs/A2-claude/42899729/0/scene.blend` (a byte-identical copy of
  `third_party/aha-3d/scenes/42899729_a2-claude_s0/blender/room_v24.blend`).
- 65 semantic roots, each with its own `instance_id`. Everything is built from code with boxes,
  cylinders, spheres and one custom drape mesh. No image-to-3D generator was used.
  - Structure: floor, ceiling, walls, the bulkhead over the doors, skirting, window sill, two
    sash windows, two door frames, two door leaves, and the visible parts of the en-suite and
    hallway.
  - Furniture and fixtures: bed, bed throw, 4 pillows, 2 cushions, folded towel stack and 2
    rolled towels, Chaplin flyer, 2 nightstands, 2 lamps, wardrobe, 4-drawer chest, 2 folding
    chairs, wastebasket, radiator and its valve, full-length mirror, tower fan, 2 roller blinds.
  - Wall art: 3 poppy canvases, the Paris canvas, and the London print in the hallway.
  - Small fittings: 3 switches/sockets on the door wall, 1 switch and 1 socket on the right wall,
    1 socket by the bed, 3 ceiling spotlights, smoke detector.
  - En-suite: shower enclosure, basin, mirror cabinet, towel rail, toilet, pedal bin.
- Builder: `third_party/aha-3d/scenes/42899729_a2-claude_s0/work/build_room.py`. The world frame is
  the Pi3X aligned room frame (Z up, predicted metres, not calibrated).
- Delivery stills: `third_party/aha-3d/scenes/42899729_a2-claude_s0/delivery_v24/`
  - plan, front and side cutaways, plus a perspective overview;
  - early, middle and late renders from the source cameras of frames 41, 331 and 476;
  - the matching source frames.
- Selected delivery: `third_party/aha-3d/deliveries/42899729_a2-claude_s0/versions/whitebox-v24.json`
  (acceptance candidate `d232ea88fe93127040716dd3e70a23c4dea0047944804894568ead36cad3038e`).
- Inventory decisions: `inventory_decisions.json` covers all 32 detector items: 20 built, 12 skipped.
  - Most detector labels were wrong (for example "bathtub" for the bed, shower tray and sill;
    "refrigerator" for the wardrobe and chest). I mapped each item using its position and crop.
  - Skipped items: duplicates, mirror reflections located behind the wall, false detections on a
    door jamb, one object outside the window, and the skirting (already built as structure).
  - Many visible objects were missing from the inventory and were built anyway: the door-side
    nightstand and lamp, tower fan, chairs, art, blinds, radiator valve, fittings, doors, the
    en-suite fixtures, and others.

## Stages run
1. Read `AGENTS.md`, `docs/INDEX.md`, the scene workflow skill, scene requests, layout inspection
   and the RoomKit skill. The claim `room42899729-a2-claude` already existed.
2. Intake: `bash tools/indoor intake --request …/request.json --out …/intake` returned
   `ready_for_authoring`. I initialized the acceptance scope after that.
3. Reference: reused the Pi3X/SAM3/alignment bundle. No new inference and no GPU jobs.
   - I measured walls, openings, sill, radiator, bed, nightstands, chest and wardrobe from the
     static TSDF points.
   - Things missing from Pi3X were placed by checking against the source video and HD frames: the
     upper wardrobe, the door-side nightstand, the fan, the mirror glass, the ceiling fittings
     (placed by ray-casting), and the flyer corners (ray-cast).
4. Authoring loop, versions v01 to v24:
   - After every change I rendered the model from all 32 HD source cameras and overlaid it on the
     source frames (`work/ov_v*/`).
   - The repository layout gate (`layout_gate.prepare`) ran with 17 source frames plus plan, front
     and side X-ray views, per-object focus packets, and the placement check.
5. Acceptance:
   - Layout review was recorded with `layout_gate.record_review`.
   - Candidate registered.
   - Technical check: `work/technical_validate.py` reopens the scene and checks the semantic roots,
     render decoding, inventory consistency and placement.
   - Preview and final_review image checks recorded.
   - `indoor acceptance check` returned **accepted, permitted**.
   - `results register`, then `results select whitebox-v24`, then the task claim released as
     `completed` (its completion gate re-runs acceptance).

## Reviews and verdicts (codex image reviewer via `indoor acceptance review-images`)
- Layout gate v24 (about 360 images): **accepted**. Final stills v24: **accepted**. Preview v24:
  **accepted**. Technical check: passed. Placement check: 0 errors.
- Earlier rejections, each fixed and re-reviewed:
  - blind hems too low;
  - pillows and towels too slab-like; throw too short;
  - a wall slab behind the window glass;
  - bathroom door swung the wrong way, so it stood inside the bedroom;
  - window-wall piers too deep;
  - headboard too tall and bed foot too long;
  - throw drape read as a rigid box, then as strips;
  - hallway door leaf angle and width;
  - flyer corners and towel roll height;
  - radiator and drape fit.
- Some reviewer outputs failed schema validation:
  - images not cited in observations;
  - several aspects joined into one string;
  - nonblocking findings listed alongside an accepted verdict.

  I never edited a reviewer's judgment. I re-ran the reviewer with format instructions and the
  known tool limits stated in `reviewer_context`. One run hit the 600 s codex timeout and was
  retried.

## Problems and how I handled them
- Pi3X has no geometry for the upper wardrobe, the door-side nightstand, the fan or the mirror
  glass. I sized and placed them from the source RGB, checked through camera overlays.
- The ID-render colours came out sRGB-encoded, and two build bugs placed objects wrongly (the lamp
  spheres at the world origin, a blind roller off its pivot). All were fixed.
- The acceptance policy needs the scope subjects in the review and a camera cache in the layout
  spec. I added a source-timing camera cache (`work/source_camera_cache.npz`) and the scope
  subjects to the review request.
- Gallery rebuild (`results build --verify --posters`) failed before writing anything:
  `Invalid identifier: '45261575_A0_s0'`, another scene's directory that I may not modify. The
  gallery claim was released as `blocked`, and the Gallery was **not** rebuilt.

## Approximations and skipped items
- Dimensions are predicted Pi3X metres, not calibrated.
- The bathroom and hallway are built only as far as they are visible through the doorways.
- The Paris canvas appears only in frames 500–530, which have no cached camera. I placed it from
  those frames and kept it out of the gate's object packet.
- The hallway door leaf width (0.78 m) was fitted from source frames 166 and 476. Pi3X gives a
  0.63 m clear opening.
- Shapes are simplified primitives (whitebox scope); there are no materials.
- No git commit or push was made.
