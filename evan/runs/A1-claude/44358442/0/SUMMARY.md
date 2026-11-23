# 44358442: precise static whitebox bedroom (A1-claude)

**Status: scene delivered, acceptance blocked.** The final `.blend` and its stills exist. Every automated layout image review rejected the
model on fine soft-goods and poster detail. No accepted layout review exists, so `acceptance check` returns `blocked`
(`permitted: false`).

## Final scene
- **Final `.blend`:** `runs/A1-claude/44358442/0/scene.blend`.
  - It is a byte-identical copy of
    `third_party/aha-3d/scenes/44358442_a1-claude_s0/work_v007/room_v007.blend` (sha256 `035cb877…3c62`).
  - Build script, fully reproducible: `scenes/44358442_a1-claude_s0/work_v007/build_room.py`. Run it with
    `blender -b --python-exit-code 1 --python build_room.py -- OUT.blend`.
- **90 semantic roots.** Each root is an Empty carrying `instance_id`, `semantic_class`, `support_id` and `source_evidence` (frames and measurements).
  - **Structure:**
    - floor and ceiling;
    - four walls, with a window opening in the west wall and a doorway in the east wall;
    - coving and skirting;
    - recessed sash window (glass, frame and meeting rail);
    - curtain rail and two curtains;
    - pine door: open leaf with handle and sign, lining, architrave;
    - radiator, switch, socket, corner sensor.
  - **Furniture:**
    - two-door wardrobe with drawer, knobs and decal;
    - desk with drawer pedestal;
    - desk hutch with shelves and cubbies;
    - swivel desk chair;
    - side table with drawer and lower shelf;
    - white daybed;
    - two wall shelves with brackets;
    - low clothes rack;
    - square pendant lamp.
  - **Small objects, each with its own root:**
    - on and around the wardrobe: suitcase, cloth bundle, two boxes on the wardrobe top;
    - on the floor: yoga mat, shoes, floor bag, tape roll, floor cables, slippers;
    - clothing and baskets: six coats, laundry basket, robe on the chair;
    - on the hutch top: owl figurine, red tin, photo card, box stack and the blue item on it, dark box, picture card, red bottle,
      pink box, three magazine files, sticky note, drop card;
    - inside the hutch: upper and middle shelf trinkets;
    - on the desk: bottles, folders, book stack, laptop;
    - on and by the side table: projector and its cable, cardboard box, power strip;
    - bedding: duvet, two pillows, mustard throw, clothes on the bed;
    - on the walls: poster collage on the east wall, fairy lights, framed picture, wall ornament, calendar;
    - on the wall shelves: two book rows and a photo card;
    - on the windowsill: four cactus pots.
  - **Hallway context:** floor and brick wall seen through the door, plus a hallway cabinet, lamp and clock.
- **How it was built.** Everything is code-built from simple primitives: boxes, cylinders, spheres, rods, procedural cloth sheets
  and noise-displaced soft goods. No image-to-3D generator was used.
  - I searched `assets/INDEX.md` first. The library has no matching wardrobe, daybed, hutch, office chair or coat-rack assets, and
    primitives gave exact control of the measured dimensions.
- **Frame and scale.**
  - The scene is authored directly in the reviewed Pi3X floor/wall-aligned frame, so `model_to_world` is identity.
  - Units are predicted metres and uncalibrated.
  - Room planes: west x=-3.53, south y=-0.25, north y=2.85, east x=-0.565, ceiling z=2.23.

## Stages that ran
1. **Claim.** Task `room44358442-a1-claude`, owner `claude-a1-44358442-s0`.
2. **Intake.** `bash tools/indoor intake --request …/request.json --out …/intake` returned `ready_for_authoring`: whitebox, stills,
   precise, inspection camera, no people or motion.
3. **Acceptance scope.** Initialised from `scope.json`. Render `stills`, `repair_budget` 3, 13 named subjects. Persisted under
   `deliveries/44358442_a1-claude_s0/acceptance/room44358442-a1-claude/`.
4. **Reference reuse.**
   - The supplied bundle `perception/44358442/bundle` was reused; no Pi3X or SAM3 inference was run.
   - Measurements came from `work/ref/`: plan slices (`plan.py`), plane percentiles (`meas.py`), and per-frame world-coordinate
     maps (`xmap_*.jpg`) for 19 of the 32 cached frames.
5. **Authoring.** Seven versions, v001 → v007, each in its own `scenes/44358442_a1-claude_s0/work_v00N/`. Quick source-camera
   overlays are in `work/q1`, `q4`, `q5`, `q5b`, `q6`.
6. **Layout gate.**
   - `layout_gate.prepare` ran through `scenes/…/tools/run_layout.py` on v003, v004, v005, v006 and v007.
   - It used 10 native frames (0, 16, 32, 113, 227, 291, 324, 437, 453, 502), chosen by set cover (`tools/cover.py`), plus top, front
     and side views.
   - It produced 381 review images per packet, with all-object focus views.
   - The placement check ran inside the gate each time.
7. **Delivery stills.**
   - Final set `renders_v007/`: plan, front, side, and early/middle/late matched to source frames 49, 227 and 437, plus those source
     frames and `final_views.json`. Earlier sets are `renders_v003` to `renders_v006`.
8. **Candidates.** Registered v003 `8fb1bccf…`, v004 `1458d3ac…`, v005 `a14c7c6f…`, v006 `955cc1ee…` and v007 `835ab1d2…`
   (`candidate_v00N.json`); v007 is the current one.
   - `acceptance_check.json` → `blocked`, because no accepted layout review (`review.json`) exists.

## Reviews and verdicts
I ran `acceptance review-images` (codex, 381 images) on every gate packet.

| Version | Verdict | Blocking findings |
|---|---|---|
| v003 | rejected | coats too rigid, bedding too flat, cloth bundle/robe/bed clothes too blobby, regular poster grid |
| v004 | rejected | coat cluster, robe drape, bedding relief and pillows, poster layout; blocking uncertainty about the dark ceiling in clay renders (Workbench lighting) |
| v005 | rejected | coat mass, robe silhouette, duvet waves, floor bag (poster collage downgraded to nonblocking) |
| v006 | rejected (schema-valid; judgment file written) | hutch internal compartments, individual poster boundaries, wardrobe hardware position, garment folds |
| v007 (final) | rejected | coat cluster still angular, `pillow_1` too thick and regular, poster rectangles do not follow the real poster edges |

- **No placement errors flagged.** No review flagged a room-envelope, opening or major-furniture placement error. Every finding
  concerns soft-goods contour or internal-detail fidelity.
- **Schema failures.** Except for v006, every reviewer output failed the review schema: "Required visual review views incomplete"
  (images labelled `Image #N`) or "every required image needs concrete observations". The v006 review was schema-valid, so its
  judgment file was written, but its verdict was rejected.
- **Open findings.** The three v007 blocking findings are recorded as open reviewer findings in the acceptance ledger
  (`findings/*.json`).
- **My own visual check** (`work/q*/c*.jpg`, `work/v00N_finals.jpg`, native X-ray panels) shows close agreement for:
  - walls, ceiling, window, door and coving;
  - wardrobe, desk, hutch envelope, side table, daybed, shelves, calendar, picture, lamp and posters region;
  - hallway cabinet and lamp.

## Problems and how I handled them
- **Poster collage had no focus view (v002).** The 6 mm panels had no plan contour, so the gate failed. I thickened them (v003).
- **Coat rack orientation (v005).** The rack was first modeled with its rail along y. Pi3X only sees the east face of the front coat,
  so the plan extent was misleading. I re-oriented the rail along x, after source frames 49/113 showed broad coat backs facing the
  camera.
- **Placement-check defects fixed in v005/v007:**
  - desk and side table overlapped by 2 cm;
  - chair and laundry basket intersected;
  - coats 5 and 6 cut into the wardrobe;
  - chair seat cut into the desk pedestal.
  - The remaining placement "errors" are intended overlaps between soft items in contact: cloth on cloth, coats on the rail.
- **Wardrobe decal.** Moved to y≈0.27 by the knobs (xmap 113) after the v006 finding.
- **Script slip.** One stills render failed because a backgrounded shell line swallowed a variable. I reran it.
- **Overwritten intermediates.** I deleted and rebuilt `room_v004.blend` and `room_v005.blend` in place during same-version tweaks,
  before any evidence was generated from them. No reviewed output was overwritten.
- **Interruption.** The usage-limit pause stopped only a stale wait loop; the review it was waiting for had already finished.
- **GPU.** Free memory was checked with `nvidia-smi` before each Blender gate. Only Workbench/EEVEE work ran, one job at a time. No
  other process was touched.

## Skipped or not done
- **Further repair.** The scope's repair budget (3) was spent: v004, v005 and v006, plus v007 for validator and hardware defects
  only. The coat cluster, `pillow_1` and the individual poster boundaries remain open.
- **Acceptance and delivery.** No accepted layout review, so no technical or final-review check records. No
  `results register/select` and no Gallery rebuild. The claim is released as `blocked`, not `completed`.
- **Scale and hidden geometry.** Metric scale is not calibrated. Hidden backs and the full hallway are simple completions.
- **Not applicable to this static scope.** People, motion, camera animation and video were not requested and were not made.
- **Git.** No commits or pushes.

## Next actions
1. Model draped garments (soft shoulders, long overlapping folds) for `coat_1`–`coat_6`, and a flatter creased `pillow_1`.
2. Lay out posters from the actual poster edges in source frames 291, 324 and 453, instead of procedural subdivision.
3. Regenerate the gate with `scenes/44358442_a1-claude_s0/tools/run_layout.py` and rerun the review. Consider smaller per-object
   packets so the reviewer output validates.
