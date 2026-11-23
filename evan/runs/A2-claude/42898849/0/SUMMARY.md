# 42898849_a2-claude_s0: static whitebox room (precise)

**Final scene:** `runs/A2-claude/42898849/0/scene.blend`. This is a byte-identical copy of
`third_party/aha-3d/scenes/42898849_a2-claude_s0/blender/room_v014.blend` (sha256 `d6995f58…`).

**Status:** the room is built and technically validated, but it has **not been accepted**. The
project's layout gate has no valid review recorded, and the final image review rejected the scene.
Details are under "Reviews" below.

## What was built
- **Structure.** Open-plan living room and kitchen, plus a piano nook. The walls come from
  ceiling-height slices of the Pi3X reference. The north wall is slightly skewed and is kept that way.
  Ceiling height is 2.55 m.
- **Openings.** French doors with sidelights, four windows with glazing bars, Roman blinds and sills,
  the glazed nook door, and the entrance doorway with two open glazed leaves.
- **Built-in masonry.** Two chimney breasts, one for the stove recess and one for the range alcove.
- **Objects.** 148 semantic roots in total, each with a unique `instance_id` and a declared front and
  facing.
  - Every object is made from code primitives: boxes, cylinders and cones, spheres, and prisms. No
    image-to-3D generator was used. Helpers are in `scenes/42898849_a2-claude_s0/build/primitives.py`
    and the scene is assembled by `build_room.py`.
  - Small objects are built individually: books, candles, vases, the jug, coffee machine, frother,
    kettle, toaster, canister, bread bin, plates, fruit bowl, picture frames, figurines, the ball, gifts,
    the lantern, a towel, a clock and plants.
- **Visible objects the detector missed (added).** Christmas tree, piano, TV cabinet, curtains and
  rod, three radiators, doormat, sink and tap, log stacks, heart ornament, toy, glassware, angel
  figurines, driftwood, a white tablet, two small plants, the bread bin and the door banner.
- **Inventory decisions.** All 141 items are recorded in `inventory_decisions.json`: 138 built and 3
  skipped.
  - Many detections were duplicates or parts of one physical object. These are marked "built" with the
    shared `object_id` and an explanatory note.
  - **Skipped b000:** a "mirror" whose crop shows a wide room view; no mirror or plane exists there.
  - **Skipped b004:** its crop shows only the island top; the points show no stool there.
  - **Skipped b029:** a lamp in the hallway, outside the room.

## Stages run
1. **Claim and intake.** Claimed task `room42898849-a2-claude` and recorded intake under `intake/`
   (`ready_for_authoring`). Initialized the acceptance scope (render = stills).
2. **Reference reuse.** Used the existing Pi3X bundle with no new inference. Built a camera cache in
   `scenes/.../reference/camera_cache` from the reviewed cameras, at 10 fps and 1439 frames.
3. **Authoring.** Measured the reference point cloud (plan and elevation slices, coloured floor
   samples) and used the inventory. Built the room through v001–v014.
4. **Placement checks** (`indoor check-placement`). The early rooms had 45 penetration errors; v014
   has 0. The remaining warnings are expected: wall-hung items, thin rug contacts, and gravity
   tumbling of small decor.
5. **Layout gate evidence.** Ran `layout_gate.prepare` for v007b, v011, v013 and v014. Each run
   produced 16 native source frames covering the early, middle and late parts of the clip, top, front
   and side views, X-ray overlays, and per-object focus images.
6. **Final stills.** Rendered plan, front and side views, plus early/middle/late renders from the
   native cameras of frames 186, 928 and 1392, paired with the matching source frames. They are in
   `stills/`.
7. **Acceptance records.** Registered candidate `09aa05c7…`. The technical check passed and was
   recorded. The final review was recorded with a rejected verdict, and the acceptance check reports
   blocked.

## Reviews and verdicts
- **My own visual review.** I compared each version against the source using matched X-ray and
  source overlays and native renders. These checks confirmed and drove these fixes:
  - **Corner unit:** rebuilt as a triangular prism matching the reference front line (4.62, 0.34) →
    (4.96, 0.66). The pot, ball and plant around it were repositioned.
  - **Island:** lengthened to the measured body extent, x −3.58…−1.08.
  - **Stools:** four in a row at the measured seat positions.
  - **Rug b002:** made axis-aligned at 1.88 × 2.74 m.
  - **Heights:** the tall fridge top now matches the wall-cabinet tops, and the tree was shortened.
  - **Other:** the banner was lowered, and glazing bars, door rails and panels were added.
- **Codex layout reviews** (`review/layout_judgment_*`). All runs returned **rejected**, and no run
  could be recorded: each failed the contract rule that every one of the ~590 images in the packet must
  be observed (464/589 and 475/586 images covered, with one run covering 0).
  - Placement findings I could verify (corner, island, stools, rug, fridge, banner) were corrected.
  - The remaining findings are about the shape of the primitive proxies: tiered-cone tree, plant
    leaves, upholstery, window bar layout and stove profile.
  - One finding reversed direction: the stools were reported as too far north, then after I moved them
    south, as shifted toward the foreground.
- **Final image review** (`review/final_review_v014.json`, 9 images): **rejected**. Its five findings
  are now in the task ledger:
  - F01–F04 (blocking): the tree silhouette; simple upholstery forms; side-table, piano and
    corner-cabinet detailing; simplified kitchen fronts.
  - F05 (nonblocking): it could not bind some object IDs to what it saw in the images.
- **Technical check:** **passed**. The scene reopens with unique roots that match the build manifest,
  every mesh belongs to a root, there is no animation, every inventory target exists, placement has 0
  errors, and the stills decode.

## Problems and how they were handled
- **Layout evidence regenerated several times.**
  - The first evidence spec had no `camera_cache`, which the acceptance check requires. I stopped my
    own job and regenerated.
  - Some small objects had no source-frame focus view, so I added source frames. The front-view crop
    excluded the corner shelf, so I widened it.
- **`tools/review_images.py` is not executable** and re-invokes itself, so it failed with permission
  denied. I used `indoor acceptance review-images`, which goes through the same reviewer contract, and
  did not change file modes.
- **Ledger ID format.** The reviewer's finding IDs ("F01") were not valid ledger identifiers. The
  recorded report copy uses `final-v014-fNN`; the raw reviewer JSON is unchanged.
- **Superseded attempts.** Stopped or abandoned partial evidence directories are labelled with
  `*.ABANDONED.txt`. Earlier rooms (v001–v013) are kept, and nothing was overwritten.
- **GPU use.** One GPU job at a time, after checking `nvidia-smi`. I only ever stopped processes I had
  started.

## Skipped or approximate
- **Not done:** the layout gate was not accepted and the delivery was not selected or published, so
  the Gallery was not rebuilt. The acceptance state is `incomplete` and the task handoff is in
  `third_party/aha-3d/tasks/room42898849-a2-claude/HANDOFF.md`.
- **Approximations:**
  - Pi3X metres are uncalibrated.
  - Primitive proxies simplify curved or organic shapes: the tree, plants, upholstery, logs and stove.
  - Window glazing is left open so clay renders show the openings.
  - Hidden backs and undersides are unseen.
  - The hallway beyond the entrance doorway is not modelled.
