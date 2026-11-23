# SUMMARY — 42899729_a5-claude_s0 (precise static whitebox room)

## Result

- **Final scene:** `runs/A5-claude/42899729/0/scene.blend`. It is a byte-identical copy of
  `third_party/aha-3d/deliveries/42899729_a5-claude_s0/v17/scene.blend` (candidate revision
  `866aff4d79861f718c909fd720d5dbb8e0843b3f8415473ba77020948f8c289a`).
- **Built by:** `third_party/aha-3d/scenes/42899729_a5-claude_s0/build/build_room.py`, run as
  `blender -b --python-exit-code 1 --python build_room.py -- --out OUT.blend`. Snapshots of
  earlier iterations are in `build_room_vN.py`.
- **What the scene holds:** 58 semantic roots, each an Empty with a unique `instance_id` and
  `semantic_class`. The scene has no animation.
  - The scene is authored directly in the Pi3X floor/wall-aligned room frame, at the provisional
    Pi3X scale.
  - Everything is built from code with primitives: cubes, cylinders, spheres, a torus, and
    bevel/subdivision modifiers. No image-to-3D generator was used.
  - No suitable registered RoomKit asset matched these objects after searching `assets/INDEX.md`.
- **Inventory decisions:** `runs/A5-claude/42899729/0/inventory_decisions.json`, one entry for
  each of the 102 detector items.
  - 30 built, 35 duplicate, 33 part, 4 skipped.
  - The decision script is `work/decisions.py`.
- **Stills:** `deliveries/42899729_a5-claude_s0/v17/stills_{object,clay}/`.
  - They cover 17 source-camera comparisons (`compare_*.jpg`, `compare_sheet.jpg`) plus
    plan/front/side/back/west orthographic views.

### Objects modelled

**Structure**
- Floor, ceiling at 2.90 m, and four walls; the west wall is the grey accent wall.
- North-east pier and the south-wall jog.
- South bulkhead with its underside at 2.53 m.
- Window boxing (radiator housing) with a deep ledge.
- Two tall sash windows and two roller blinds, both partly lowered.
- Entrance door, open 90° against the east wall, with jambs, trims, grooves and levers.
- En-suite door, open into the bathroom.
- Skirting boards.
- Two ceiling downlights.
- Two switches and two sockets.

**Furniture**
- Bed: divan, mattress, duvet and headboard.
- Bed throw with roll edges, drapes and hem folds.
- Nightstand.
- Wardrobe with 3 doors.
- Chest of drawers with 4 drawers and pulls.
- Two folded chairs; these were not in the detector list.

**Decor and small objects**
- 4 pillows and 2 dark cushions.
- Table lamp.
- Radiator with grille slats and end caps.
- Bedroom bin.
- Full-length wall mirror.
- 3 small canvases above the headboard; not in the list.
- Poster card on the bed.
- Towels, each a separate instance: 2 bath towels, a folded hand towel, a standing roll and a
  lying roll.

**Seen through doorways**
- Bathroom: shell with toilet alcove, shower (tray and glass), pedestal sink with tap, mirror
  cabinet, heated towel rail, pedal bin and toilet.
- Hallway: shell, bus picture and ceiling light.

## Stages run

1. **Intake.** I ran `bash tools/indoor intake --request …/request.json --out …/intake` and
   recorded the scope as whitebox, stills, precise, inspection camera, no people or animation.
2. **Claim and scope.**
   - The task claim `room42899729-a5-claude` already existed with this run's owner, and
     `scenes/42899729_a5-claude_s0` contained only `references/input.mp4`, so I reused the claim.
   - The acceptance scope was initialized at
     `deliveries/42899729_a5-claude_s0/acceptance/room42899729-a5-claude/`.
3. **Reference analysis.**
   - I reused the provided Pi3X/SAM3/alignment bundle and did not run Pi3X inference again.
   - Room planes, openings and furniture extents were measured from `mesh/layers.npz`. The
     scripts and plots are in `runs/A5-claude/42899729/0/work/`.
   - I checked object identity in the 32 HD source frames and the detector crops.
4. **Authoring and repair, versions v1 through v17** (`scenes/…/blender/room_vN.blend`). Each
   revision was compared against matched source-camera renders (`scenes/…/review/vN`,
   `compose.py` overlays). Main corrections:
   - Poster rotation; nightstand position; headboard height.
   - Toilet moved into an alcove hidden behind the door jamb.
   - Window heads raised to 2.75 m, and blind heights set.
   - Ceiling downlights made deep enough to register in the orthographic views.
   - Entrance leaf widened to 0.70 m to match the point cloud; both door heads lowered to 1.82 m.
   - Bulkhead lowered to 2.53 m; lamp shortened to the measured 0.32 m.
   - Softer pillows, duvet and throw; radiator grille; drawer pulls.
   - The object first modelled as a "luggage rack" was replaced by **two folded chairs**, as the
     source shows. Their placement was fixed so they no longer clip the pier or the boxing.
5. **Layout gate.**
   - `layout_gate.prepare` was run with export, outlines and per-object focus packets. Evidence is
     in `scenes/…/inspection/layout_vN`; the config is `inspection_config.json`.
   - Extra source frames were added until every object had both orthographic and source focus
     views.
   - The placement check on v17 reports 0 errors and 20 warnings. The warnings are hanging blinds,
     the draped throw, wall-mounted items and intended contacts.
6. **Technical check.**
   - `build/validate_scene.py` reopens the saved `.blend` and checks:
     - unique instance IDs;
     - every root has geometry;
     - there is no animation;
     - every `object_id` in the inventory decisions exists.
   - Its report and the placement report were recorded as the `technical` check for v17. It
     passed.

## Reviews and verdicts

All automated image reviews used `acceptance review-images`, which calls `codex exec` with the
images attached.

| Review | Candidate | Verdict / status |
| --- | --- | --- |
| Layout gate, 333 images | v6 | Not run: every codex account had hit its usage limit; I waited until 06:50 UTC |
| Layout gate | v9 | **Rejected.** 8 blocking findings: entrance leaf, bathroom door head and bulkhead, lamp height, pillows, rigid bed/throw, bulkhead shading, blind A hem, hallway picture. Output also failed schema validation (not every image observed). Concrete findings were fixed in v10. |
| Layout gate | v10 | **Rejected.** Lamp offset, rigid bedding, pillow slabs. Schema validation failed. |
| Final review, 9 final views | v10 | **Rejected.** Pillows, bedding, radiator, the folded chairs (identified by the reviewer), nightstand/dresser tops. Schema coverage incomplete. |
| Layout gate | v15 | **Rejected.** Throw hang depth, lying towel roll, two "blocking uncertainties" about occluded bathroom/hallway areas. Schema validation failed. |
| Final review | v15 | **Rejected** (valid structured judgment). Bedding, lamp, chairs. |
| Final review | v17 | **Rejected** (valid structured judgment). Blocking: headboard projects too high; foot throw reads boxy; folded chairs too low and forward. Nonblocking: pillow contours too uniform. All uncertainties nonblocking. |

My own visual review: I inspected the matched source/model overlays for every revision. In v17
the room envelope, doors, windows and blinds, wardrobe, dresser, nightstand and lamp, radiator,
mirror, canvases, towels, poster, chairs and visible bathroom fixtures agree with the source within
a few centimetres in the views I checked.

**Acceptance status: not accepted.** The current v17 candidate has a passing technical check, but
no accepted layout, preview or final review. The three blocking v17 reviewer findings are recorded
in the acceptance ledger:
- `v17-headboard-height`
- `v17-throw-profile`
- `v17-folding-chairs`

The task claim stays active, with a checkpoint note.

## Problems and how they were handled

- **Codex quota exhaustion.** I waited for the documented reset time (06:50 UTC) and then reran.
- **Layout reviews failed schema validation.** About 333 images per request were too many for
  every image to receive an observation. The raw judgments were extracted to
  `scenes/…/inspection/layout_v*_raw_judgment.json`, and their concrete findings were applied.
- **Gate refused objects without focus evidence.** Blinds, canvases, downlights and wall plates
  had no focus views. I added source frames, widened the crops and gave the downlights some depth.
- **The detector list missed or misnamed objects.**
  - The two folded chairs (first misread by me as a luggage rack), the three canvases, both doors,
    the blinds and the hallway picture were not in the list; I built them anyway.
  - Several detections are reflections in the wall mirror (frame 456). I marked them as
    duplicates of the real pillows, nightstand, lamp and bed.
- **Placement errors.** Penetrations from pillows, the throw, the chairs and the towel rail were
  fixed until the placement check reported 0 errors.
- **The acceptance CLI `check` prints `STATE_INVALID`** ("dictionary update sequence…"). This
  comes from the layout check while no layout review is recorded. The direct
  `acceptance.evaluate` call reports the real per-check blockers. I left this code issue
  untouched because code changes are out of scope.

## Skipped or not done

- **Inventory items skipped:**
  - `c005`: the camera operator reflected in the mirror.
  - `c123`: a 10-pixel corner crop; no outlet is visible there.
  - `c138` and `c141`: dark frame-edge regions near the floor south of the bed; there is no
    object at those positions in other views.
- **Not done:** fabric-accurate soft goods. The throw and pillows are primitive approximations,
  which is the main remaining reviewer objection. Hidden backs, the full bathroom/hallway beyond
  the doorways, and absolute metric scale remain uncertain (Pi3X scale is provisional). No
  Gallery/results selection or promotion was done, because the candidate is not accepted. No git
  commit or push was made.
- **Next action:**
  1. Model the throw and pillows as draped cloth meshes.
  2. Lower the headboard against frames 41/393.
  3. Refit the folded chairs' base and lean against frames 311/497.
  4. Regenerate layout v18, then rerun the final review.
