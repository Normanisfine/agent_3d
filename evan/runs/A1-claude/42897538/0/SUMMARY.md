# 42897538 — precise static whitebox room (A1-claude)

**Status: scene delivered, acceptance blocked.** The final `.blend` and stills exist, but the layout review is
rejected and has no accepted record, so the acceptance check returns `blocked` (`permitted: false`).

## Final scene
- Final `.blend`: `runs/A1-claude/42897538/0/scene.blend`. It is a byte-identical copy of
  `third_party/aha-3d/scenes/42897538_a1-claude_s0/work_v007/room_v007.blend` (sha256 prefix `8c4ca8cddb9a59f4`).
- Build script (fully reproducible): `scenes/42897538_a1-claude_s0/work_v007/build_room.py`.
- 51 semantic roots, each an Empty with `instance_id`, `semantic_class`, `support_id` and `source_evidence`.
  - **Structure:** floor, ceiling, 6 walls (L-shaped room with a return wall), skirting, hallway door (open
    glazed oak leaf, frame, transom), kitchen opening (lining, architrave, open leaf), south and west windows,
    vertical blinds ×2.
  - **Furniture:** three-seat leather sofa, loveseat, ottoman, coffee bench with lower shelf, TV stand,
    plasma TV, lamp side table, table lamp, black corner table, rug.
  - **Small objects:** 4 throw cushions, glass bowl with biscuits, plate stack, tissue box, carriage clock,
    phone base, cable bundle, power strip, Christmas tree, string lights, photo print on the rug, painting,
    mirror, radiator, 2 swirl chandeliers, 2 switches, 2 sockets.
  - **Context:** approximate hallway and kitchen stubs seen through the openings
    (`context_hallway`, `context_kitchen`).
- Everything is built with code from simple shapes. The library had no matching assets: I searched
  `assets/INDEX.md`, and the sofas, chandelier and TV types differ. No image-to-3D generator was used.
- Frame: authored directly in the Pi3X aligned frame, so `model_to_world` is identity. Units are predicted
  metres and uncalibrated; ceiling is at 2.43.

## Stages that ran
1. **Claim.** `room42897538-claude-static`, owner `claude-a1-42897538`.
2. **Intake.** `intake/` (ready_for_authoring: whitebox, stills, precise, inspection camera, no people or motion).
3. **Acceptance scope.** Initialised under `deliveries/42897538_a1-claude_s0/acceptance/room42897538-claude-static/`.
4. **Reference reuse.** The existing Pi3X/SAM3/alignment bundle was reused; no Pi3X inference was run.
   Measurements came from plan, elevation and per-frame world-coordinate maps (`work/ref/`). The two
   chandelier positions were ray-cast from frames 462 and 924.
5. **Authoring.** v001 → v007, each in its own `scenes/42897538_a1-claude_s0/work_v00N/` directory.
   Quick source-camera overlays are in `work/q*/`.
6. **Layout gate.** `layout_gate.prepare` was run with 9 native frames (0, 92, 123, 246, 555, 616, 678, 770, 924),
   chosen by set cover so that every object gets a source focus view, plus top, front and side views.
   Evidence is in `work_v003/layout_a`, `work_v005/layout_a`, `work_v006/layout_a` and `work_v007/layout_b`.
7. **Delivery stills.** `renders_v007/`: plan, front, side, early/middle/late matched to source frames
   123/555/893, plus the source frames and `final_views.json`.
8. **Candidate registration.** Revision `bf2a6cb3…` (`candidate_v007b.json`). The first registration
   `9f8adf22…` had a malformed layout spec and is superseded. `acceptance_check.json` → blocked.

## Reviews and verdicts
These are `acceptance review-images` runs (codex, 243 images each).

| Version | Verdict | Result |
|---|---|---|
| v003 | rejected | Blocking: lamp proportions, sofa/pillow softness, door glazing, painting frame, plate stack/bowl. |
| v005 | (interrupted) | I stopped it myself (see Problems). |
| v006 | rejected | Lamp, painting, plates, bowl and TV were no longer flagged. Blocking: tree silhouette, tissue-box support, door glazing, sofa upholstery. |
| v007 | rejected | Blocking: door glazing legibility, sofa arms/cushions, throw-pillow poses, painting extent, plate stack. Nonblocking: cables, ottoman edge, print/rug/tissue outlines, wall-plate offsets. |

- Every reviewer output also failed the review schema ("every required image needs concrete observations").
  The packet has 243 images, so the judgment could not be recorded as a gate review.
- My own visual checks found good agreement for:
  - walls, openings, windows, blinds;
  - sofa, loveseat, coffee table, TV stand, TV, ottoman, radiator, mirror, painting, chandeliers;
  - the tabletop items.
  The door and plate findings are clay-render legibility at 364×266. The geometry has three frosted
  panes and a 9 cm, 7-plate stack.
- The tissue-box finding is an X-ray artefact. Contours ignore occlusion, so the shelf box projects through
  the tabletop. It sits on the lower shelf, matching frame 616.
- Five v007 blocking findings are recorded in the acceptance ledger as open (`findings/*.json`).

## Problems and how I handled them
- **Focus coverage gaps.** The layout packet needs a source focus view for every object. The first 5-frame
  set lacked one for `door_hallway`. String lights and one switch plate had no contour. I chose frames by set
  cover and made the bulbs and plates realistically thicker.
- **z-fighting.** The step wall and kitchen wall faces overlapped (v001). I shortened the step wall.
- **Orientation mistakes.** Sofa facing, wall plates, painting and radiator sides, and the door swing were
  wrong in an early draft. I fixed them before the first build.
- **Lamp sizing.** It was too tall in v004/v005 and too short in the v006 draft. It was settled from frame 123,
  and the side table was lowered to 0.55 m.
- **Killed processes (no other agent affected).** While stopping my superseded v005 review, a `pkill -f`
  pattern matched and killed my own shell, plus my own review wrapper. Because the shell died, the
  following broader `pkill` never ran. I checked that the one orphaned codex process had all 243 image
  arguments from my `work_v005`, then stopped only those two PIDs. No other agent's process was signalled.
- **Deleted output.** I deleted one stale evidence directory, `work_v007/layout_a`, minutes after creating
  it; it came from a build where my edit had aborted. All other outputs are kept in versioned directories.
- **Bad candidate.** The first candidate passed the layout spec as a path, which crashed the check. I
  re-registered with the spec inline.

## Skipped or not done
- **Further repair.** No further geometry repair after v007: the scope's repair budget of 3 rounds is spent.
  The open items are listed above and in the ledger.
- **Acceptance and selection.** No accepted layout review, no `results register/select`, no Gallery rebuild.
  The claim is released as `blocked`, not `completed`.
- **Context stubs.** The kitchen and hallway interiors beyond the openings are rough context stubs, not
  precise reconstructions.
- **Scale.** Metric scale is uncalibrated (Pi3X predicted metres).
- **Not applicable to this static scope.** No people, motion or video were requested, so none were made.
- **Git.** No commits or pushes.

## Next actions
1. Make glazing and plate-stack geometry readable in the clay inspection views.
2. Sculpt softer sofa arms and backs, and slumped pillows.
3. Re-measure the painting extent from frames 480 and 924.
4. Regenerate the gate and re-run the review. Consider fewer objects per packet, or a reviewer with longer
   output, so the schema validates.
