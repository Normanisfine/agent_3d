# Run summary: 42899712_a1-claude_s0 (precise static whitebox)

**Status: stopped. The scene is delivered but not accepted.** The final scene is complete and editable. The last layout review still rejected it, citing shape detail of primitives (not placement), and those findings stay open in the acceptance ledger.

## Final scene

- `/home/user/6220/Project/ubuntu_final_project/runs/A1-claude/42899712/0/scene.blend`
  - Byte-identical copy of `scenes/42899712_a1-claude_s0/blender/room_v013.blend` (sha256 `493e89a5…6dc5eb`).
- Stills are in `stills_v013/`:
  - `plan.png`, `front.png` and `side.png` are orthographic cutaways.
  - `render_{early,middle,late}_*.png` are clay renders from the cached Pi3X cameras at frames 35, 520 and 1039, next to matching `source_*.png` video frames.
- Builder: `scenes/42899712_a1-claude_s0/build/build_room.py` with `layout_v013.json`.
  - It is fully code-generated from primitives. Rebuild with: `blender -b --python-exit-code 1 --python build_room.py -- --layout layout_v013.json --out X.blend`.
- Coordinate frame: the Pi3X aligned frame (`alignment/cameras.json` world transform), in predicted metres, uncalibrated, with floor at z=0. `model_to_world` is identity.

## What is modeled

There are **75 semantic roots**, each an Empty with its own `instance_id`.

- **Structure:** living room, kitchen and hall floors; all walls, including the hall doorway in the south wall, the kitchen opening in the east wall, and the west wall with recessed sash windows; ceilings at 3.0 m (living) and 2.36 m (kitchen); the ceiling beam; skirting; the living-room door leaf; the open hall-side door.
- **Living and dining:**
  - L-shaped chaise sofa and 2 cushions.
  - Coffee table, 2 coasters and the red rug.
  - Round glass dining table and 4 cantilever chairs.
  - Pedal bin.
  - TV, 3-tier glass TV stand and the small device on it.
  - Armchair and the five-head arc floor lamp.
  - Black glass side table and the tall white cupboard.
  - London print and B/W photo, both framed.
  - 4 wall sconces and 2 radiators.
  - Light switch, smoke detector, roller blind and the hall leaflet.
- **Kitchen:**
  - South, east and north base runs with worktops, the tall unit, 3 wall cabinets and the splashback.
  - Built-in appliances and fixtures: oven, 4-burner hob, dishwasher, inset sink and tap.
  - Countertop items: microwave, coffee machine, kettle, toaster, knife block, utensil pot and 6-glass set.
  - Hanging and wall items: tea towel, oven glove, wall clock and 4 downlights.

No image-to-3D generator was used.

## Stages that ran

1. **Intake.** `bash tools/indoor intake … --out runs/…/intake` returned `ready_for_authoring` (whitebox, stills, precise, inspection camera, no people or motion).
2. **Claim and scope.** The existing claim `room42899712-a1-claude` was reused and checkpointed as a fresh restart, because outputs from an earlier attempt were no longer on disk. Acceptance scope was initialised (`render: stills`, `reference_reconstruction: true`).
3. **Reference reuse.** The given Pi3X/SAM3/alignment bundle was reused as is; Pi3X was not rerun and no GPU inference was done. Room and object measurements came from plan and height slices of the fused cloud, per-frame source-pixel 3D lookups, coordinate-grid overlays on cached frames, and ray-plane intersections from the cached cameras.
4. **Authoring.** Revisions v001 to v013 were built. Each saved a distinct `.blend`; nothing was overwritten.
5. **Layout inspection on every reviewed candidate:**
   - `render_blender.py` produced X-ray, depth and reference overlays: top, front and side, plus native frames 35, 277, 520, 624, 693, 831, 866, 970, 1005, 1039 and 1074.
   - `object_outline` and `agent_review --all-objects` produced per-object focus images.
   - `layout_gate.prepare` produced hash-bound evidence (driver: `build/layout_evidence.py`).
   - The placement check ran as part of the renderer.
   - `quick_check` contour overlays and my own visual comparisons were used between revisions.
6. **Candidate.** v013 was registered as revision `2388e3ef…2006` (purpose `delivery`, completeness `partial`, with a `final_views` manifest).

## Reviews and verdicts

The image reviews used `acceptance review-images` (codex, 337 images per request). Every one returned **rejected**. Each output also failed the tool's schema check ("Every required image needs concrete observations"), so no judgment file could be recorded. The raw outputs are in `scenes/…/review/v0XX_review.log`.

| Rev | Main findings | What I changed next |
| --- | --- | --- |
| v005 | Arc lamp geometry; frame-35 doorway blocked; cushions; smoke detector offset; coasters | Lamp heads and detector placed by ray-plane intersection from cached cameras; door leaf moved; cushions resized and tilted |
| v008 | Door leaf misplaced in frame 1039; lamp crests; art and sconces read as slivers in clay; rigid sofa; cupboard extent | Door hinged at the west jamb; framed art with inset canvas; bevelled sofa; cupboard height 2.0 m |
| v010 | Skirting projecting through the sofa; TV shifted; rug edge; hall-view occlusion; sofa back gap | Hidden skirting removed; TV placed by ray (X −3.05 to −2.15); doorway widened; knife block and utensils relocated |
| v012 | Lamp arcs; towel and glove too long; cushions; window head | Lower arcs; shorter fabrics; window top raised to 2.85 m; rug edge |
| v013 | **Open, all shape detail:** sofa and pillow upholstery, chair profiles, hob grate and textile folds (blocking); lamp shade form and side-table base (non-blocking) | None. Stopped here. |

The three blocking v013 findings are in the acceptance ledger (`v013-sofa-upholstery`, `v013-dining-chair-profile`, `v013-hob-textiles`). Task state is set to `incomplete`.

My own visual check: in the native source views, v013 matches positions and extents for the structure, sofa, tables, chairs, TV, lamp, sconces, art, door and kitchen units.

## Problems and how I handled them

- **Inconsistent Pi3X cameras.** Some objects disagree between frame groups by up to about 0.5 m along the long room axis (for example, the sofa's right arm sits at X −1.45 in frames 520–589 and −0.9 in frames 866–935). I favoured frontal, high-confidence views and recorded each choice in the layout JSON history.
- **Southern west window unobserved.** No cached Pi3X frame sees it; it only appears in uncached frames 370 and 990. Because the packet requires a source focus view per object, this window and its blind are inside the `wall-living-west` root rather than having their own IDs.
- **Placement check (diagnostic):**
  - Inset sink into its worktop: intentional.
  - Cushions resting into the sofa: reduced.
  - Ceiling and wall fixtures: support-gap warnings, expected because they are mounted.
  - Cantilever chairs: gravity-instability warnings from simplified geometry.
- **Final acceptance check** (`indoor acceptance check`) fails internally with `STATE_INVALID` (a dictionary-update error inside the evaluator). Acceptance was therefore never permitted, so I did no selection, results promotion, Gallery rebuild or claim release. The claim stays active with a handoff.
- **Stale watchers.** Two of my background wait loops (`pgrep -f` matching their own command line) hit the time limit. They were only watchers; the review jobs themselves completed.

## Skipped or not done

- **Layout acceptance and final acceptance:** not achieved, for the reasons above.
- **Scale:** dimensions are in uncalibrated Pi3X predicted metres.
- **Appearance and inferred fixtures:** whitebox only. Hidden faces and the hall beyond the doorway are simple completions. The kitchen wall-cabinet extents and downlight positions are partly inferred from uncached frames.
- **Git:** no commits or pushes.
