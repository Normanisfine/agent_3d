# Run summary — 42899617_a5-claude_s0 (precise static whitebox)

**Final scene:** `runs/A5-claude/42899617/0/scene.blend`. This is a byte-identical copy (sha256 `b7bacabd…`) of
`third_party/aha-3d/scenes/42899617_a5-claude_s0/blender/room_v16.blend`.
**Inventory decisions:** `runs/A5-claude/42899617/0/inventory_decisions.json` (100/100 items handled).
**Acceptance status: not accepted.** The scene is built and passed the technical checks. The Codex image reviewer
still rejects it over fixture-shape detail (see below).

## What the room is
The video shows a small L-shaped bathroom, about 2.7 × 1.8 m in Pi3X predicted metres (uncalibrated), with a
toilet alcove of about 0.8 × 1.0 m and a 2.69 m ceiling. It is authored directly in the Pi3X aligned frame
(identity model-to-world). There are 41 semantic roots, each with its own `instance_id`:
- **Structure (13):** `floor`, `ceiling`, `wall-west` (with a door opening), `wall-north`, `wall-south`,
  `wall-bath-end`, `wall-alcove-south`, `wall-east`, `door-frame`, `skirting`, `wainscot-panelling` (dado rail and
  raised mouldings), `bath-wall-tiles` (white field, dark top band, grout grid), `basin-splashback-tiles`.
- **Objects (28):** `bathtub` (roll-top rim, rounded cavity, apron, drain, overflow), `bath-mixer-tap` (deck bridge
  mixer), `bath-shower-handset` (with hose), `bath-mat-towel` (draped cloth), `toilet` (lathe pan, seat, raised
  lid), `toilet-cistern` (with lever and flush pipe), `toilet-ledge-north`, `toilet-ledge-south`,
  `toilet-ledge-back` (tiled caps over recessed faces), `toilet-brush`, `toilet-roll-holder`, `toilet-roll`,
  `washbasin` (flared bowl, waste, overflow slots, trap, brackets), `basin-tap-left`, `basin-tap-right`,
  `basin-plug`, `basin-mirror`, `basin-wall-light`, `bath-mirror` (framed), `towel-radiator` (24-bar ladder),
  `radiator-control-box`, `pedal-bin`, `ceiling-light-main`, `ceiling-light-alcove` (crystal drops),
  `ceiling-sensor`, `painting`, `poster` (framed with relief), `door` (six-panel leaf, open about 90°, levers and
  hinges).

All geometry is code-built from RoomKit boxes and Blender primitives, plus lathe, tube and ribbon meshes
written in the builder. No image-to-3D generator was used. The asset library had no bathroom fixtures, so none
were reused.

## Stages that ran
1. **Intake:** `bash tools/indoor intake --request …/request.json --out …/intake` returned
   `ready_for_authoring` (whitebox, stills, precise, inspection camera, no people or motion).
2. **Claim and scope:** reused the existing claim `room42899617-a5-claude`. The task history listed an earlier
   attempt, but the scene directory was empty. Initialized the acceptance scope at
   `deliveries/42899617_a5-claude_s0/acceptance/room42899617-a5-claude/scope.json`.
3. **Reference reuse:** used the Pi3X/SAM3/alignment bundle. No new Pi3X inference and no GPU jobs. Room extents,
   fixture heights and positions were measured from `mesh/layers.npz` (measurement-valid points). Positions were
   checked by projecting candidates into the cached native cameras.
4. **Authoring:** `scenes/42899617_a5-claude_s0/scripts/build_room.py` built versions `room_v1` to `room_v16`.
   Each version was saved as a new file.
5. **Inspection:**
   - Native-camera overlays against source frames, using my own Workbench renderer (`scripts/render_views.py`,
     `review/v*_cmp`, `review/v*_render`).
   - `tools/layout_inspection` export plus `quick_check`.
   - Full `render_blender.py` inspection with the Pi3X reference.
   - Layout-gate evidence (`layout_gate.prepare`), including the per-object focus packet for all 41 IDs. I
     inspected the focus images of every main item and the small objects.
   - Placement check run after every edit.
6. **Delivery packaging:** `scenes/42899617_a5-claude_s0/delivery/v16/` contains the stills (plan, front, side,
   early, middle, late, source_*), `final_views.json`, `configuration.json` and a camera cache. The candidate
   `2d2109c6…` is registered. The technical check (scene reopen, unique IDs, inventory IDs exist, placement 0
   errors, renders decode) passed and is recorded.

## Reviews and verdicts
| Review | Verdict |
| --- | --- |
| Agent native-view and per-object focus review (v1, v2, v7, v8, v12, v16) | Layout, scale and object positions match the source. Repairs are listed under Problems. |
| Placement check v3 / v4 / v5 / v6 | 17 / 3 / 1 / 0 errors |
| Placement check v8 / v9 / v10 / v11 | 6 / 2 / 1 / 0 errors |
| Placement check v12 / v13 / v16 | 0 errors each |
| Codex layout review v6c | Rejected (fixture-shape findings) |
| Codex layout review v11 | Timed out after 600 s (263 images) |
| Codex layout review v16 | Rejected: toilet lid contour, basin opening, hose loop. Nonblocking: chandelier drops, sensor shape. |
| Codex final review v6b, v11, v13 | Rejected |
| Codex final review v12 | Verdict "accepted", but with 2 nonblocking findings, which the contract cannot record as accepted |
| Codex final review v16 | Rejected: under-basin waste routing, bath mixer arrangement. Nonblocking: plug placement. |

The 8 v16 reviewer findings are filed in the acceptance ledger as `codex-final-v16-*` and `codex-layout-v16-*`.
The acceptance state is `incomplete`, and the task claim was released as `handoff`.

## Problems and how they were handled
- **Codex usage limit:** blocked until 14:50, then I resumed. **Layout request size:** 263 images can exceed the
  reviewer's 600 s timeout (v11).
- **Acceptance layout check needs a camera cache:** generated one by interpolating
  `bundle/alignment/cameras.json` at the observed timestamps, then regenerated the evidence.
- **Reviewer findings from v6 onward:** fixed in v7 to v16. Fixes made:
  - Boolean artifacts in the basin and bath.
  - Toilet profile rebuilt as a lathe, with an oval lid.
  - Ledges rebuilt as tiled caps over recessed faces with trim.
  - Bath given a roll-top rim and rounded cavity.
  - Towel rebuilt as draped cloth.
  - Mixer rebuilt as a deck bridge mixer, with a compact handset and a connected hose.
  - Crystal chandeliers.
  - Wall light lowered about 6 cm, verified by projection.
  - Grout grids and panel mouldings added.
  - Framed artwork given relief.
  - Thinner radiator, lever and handles.
  - Slimmer basin trap; basin overflow slots and drain ring.
  - Penetrations introduced by the new geometry fixed after each placement check.
- **Stopped after 4 repair rounds:** the remaining objections are fixture-level detail and they changed between
  rounds (v12 was nearly accepted, v13 and v16 were not).
- **`indoor acceptance check` error:** it reports `STATE_INVALID: dictionary update sequence element #0…`. This
  is an error in the CLI. I did not investigate it because code changes are outside this task.
- **Not recorded as checks:** the `final_review`/`layout`/`preview` checks were not recorded (the reviewer never
  accepted). The scene was not selected or promoted, and the Gallery was not rebuilt.

## Inventory (100 detector items)
- **21 built** as their own instances.
- **44 duplicates.** Many are reflections in the two mirrors, re-detections of taps or bins, or repeated
  bath/mirror boxes.
- **29 parts.** Seat and lid strips belong to `toilet`; flush lever and flush pipe to `toilet-cistern`; drains
  and trap to `washbasin`; door handles (including their reflections) to `door`; bin liner to `pedal-bin`; hose
  pieces to `bath-shower-handset`.
- **6 skipped:**
  - c008, c012, c017, c037: hallway curtains seen through the doorway, outside the reconstructed room.
  - c061: hallway curtain rod, outside the room.
  - c055: reflection of the camera operator's phone in the mirror.
- **Built although the list missed them:** toilet brush, the three tiled toilet ledges, radiator control box,
  ceiling sensor, door, wall light (only partly listed), and both mirrors as framed objects.

## Skipped or limited
- No materials, people, motion, camera animation or video (all outside the requested scope).
- Hallway objects (curtains, rod, stool) are outside the room.
- Pi3X scale is uncalibrated predicted metres. The main-room ceiling is assumed flat at 2.69 m.
- Fixture interiors and backs not visible in the video are simplified.
