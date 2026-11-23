# 42899712 A5 room — furnished materials and lighting (showcase)

## Result
- **Scene:** `scene.blend` is a byte copy of
  `third_party/aha-3d/scenes/42899712_showcase_mat_a5/blender/materials_v13.blend` (sha256 `006bee0a…`).
  Base: `runs/A5-claude/42899712/0/scene.blend` (v14 whitebox, sha256 `f590e815…`). It was copied unchanged
  to `scenes/42899712_showcase_mat_a5/blender/base_v14.blend`; the original was never opened for writing.
- **Stills (`stills/`):** `overview_plan.png` (1950×1600, same ortho camera as the base `plan.png`), `front.png`
  and `side.png` (1920×1200, same cameras and wall cutaways as the base stills), `overview_3q.png` (new 3/4
  bird's-eye cutaway), and interior views `interior_source_000589/000693/000243.png` (1638×1197, from source
  cameras). The base run's three source-camera whitebox stills are matched with the same file names, cameras and
  728×532 resolution: `early_source_000035.png`, `middle_source_000520.png` and `late_source_001039.png`.
  `stills/source_cameras_hires/` has all 10 source-camera renders at 1638×1197.
- **Comparisons (`compare/`):** 10 side-by-side images for frames 35, 139, 243, 416, 520, 589, 693, 762, 970 and 1039
  (t = 3.5–103.9 s of a 107.5 s clip). The left half is the source video frame (1024×768 HD frame, resized as a whole
  frame without cropping to the Pi3X processed aspect, same as the camera inputs). The right half is the material
  render from the matched aligned source camera (`perception/42899712/bundle/alignment/cameras.json`).
- **Metadata:** `metadata/materials_manifest.json` (every material with its provenance, the part→material
  assignment for all 318 meshes, the 31 lights), `metadata/geometry_check.json`, `metadata/render_views.json`,
  `metadata/render_jobs.json`, `metadata/exposure_stats.txt`. Scripts are in `scripts/`. Review requests and
  judgments are in `review/`.

## What changed (and what did not)
- **Geometry is unchanged.** `scripts/geometry_signature.py` hashed every non-light object in the base and the
  final file: object set, parent, world matrix, mesh vertex/face hash, `instance_id`, `semantic_class` and
  `hide_render`. Result: 403 = 403 objects, 0 missing, 0 added, 0 changed, all 85 semantic roots and their
  `instance_id`s kept (`metadata/geometry_check.json`, `passed: true`).
- **Materials only:** every mesh's slot was reassigned (318 meshes, no mesh left on a `wb_*` whitebox material; the
  now-unused `wb_*` materials were purged). Meshes whose data is shared use object-linked slots.
- **Added:** 31 lights in a new `A5_lighting` collection, a new world (`A5_daylight_sky`), and Cycles render
  settings. The whitebox `sun` light was replaced by `daylight_sun`.
- **Pi3X was not rerun.** The existing aligned cameras and HD frames from `perception/42899712/bundle` were reused.

## Material choices
I searched `assets/INDEX.md` first. These registered materials were imported (copied, then tinted where noted):

| Use | Registered source | Adjustment |
| --- | --- | --- |
| Floor (pale travertine/limestone tiles) | `roomkit-v1/warm-limestone` (world coords) | warm beige tint and 1.2×0.6 m world-space tile seams |
| Kitchen worktops (light grey quartz) | `roomkit-v1/honed-ivory-stone-countertop` | slightly grey tint |
| Sofa (charcoal grey woven fabric) | `roomkit-v1/charcoal-woven-upholstery` | cool tint (0.62, 0.65, 0.74) |
| Sofa cushions (cream) | `roomkit-v1/cream-linen-cushions` | — |
| Armchair (oatmeal fabric) + walnut legs | `roomkit-v1/ivory-linen-sofa`, `walnut-furniture-frames` | warm tint |
| Sink, faucet, hob plate, oven trim, kettle, utensil pot, toaster, handles | `roomkit-v1/brushed-stainless-steel` | — |
| Doors, window frames, white cabinet, radiators, vent, picture frame | `roomkit-v1/warm-white-painted-joinery` | door lining tinted grey |
| TV screen | `roomkit-v1/dark-television-glass` | — |
| Window glass, glazed-door glass | `additional-444547-44-v1/glass-approximation` | door glass frosted (roughness 0.35) |

Authored Principled BSDF materials, where nothing in the library fit:
- **Walls:** matte greige emulsion. The kitchen walls get a taupe-grey band below z = 1.42 m, as seen in frames
  173/208/243 (the base run had not modelled the paint band). The ceiling and beam are flat white.
- **Kitchen:** near-black brown high-gloss lacquer fronts, plinths, tall unit, upper cabinets and dishwasher.
  The oven door and microwave window are black glass. Pan supports are black cast iron. The coffee machine is red
  with black parts. The knife block is natural wood. The tray is clear plastic. The oven glove has procedural
  black/white polka dots and the tea towel is white with procedural red stripes (both visible in frame 243). The
  clock face is frosted glass. Sockets and switches are white plastic.
- **Living/dining:** black faux-leather Z-chairs with chrome runners and smoked glass on the round table. The coffee
  table, TV-stand shelves and side table are gloss black glass. The arc lamp is polished chrome. The rug is a deep red
  shag (noise bump). The pedal bin is dark brushed steel. Coasters, card and shelf box are white. Downlight lenses
  are emissive.
- **Pictures:** the London-embankment canvas and the B&W family photo use perspective-rectified crops of source
  frames 624 and 416 (`scenes/…/textures/`, packed into the .blend). The floor picture in the hall is a brown print.

## Lighting and render settings
- **Daylight:** a sun (3.5, cool white, 3° angle) entering through the window wall, two window sky portals, and two
  window-sized cool area fills (320 W). The world is a soft sky gradient (strength 1.6).
- **Interior:** each of the 4 cube sconces has an up spot and a down spot (130 W, saturated warm ~2400 K, 50° cone,
  full blend) plus a soft 8 W point glow. There are 6 warm kitchen downlight spots (30 W) and 5 small warm bulbs
  (6 W) inside the arc-lamp shades. Soft, camera-invisible area fills sit under the living/kitchen/hall ceilings
  (150/70/30 W, warm-neutral).
- **Render:** Cycles on GPU (OptiX, RTX 5070 Ti Laptop), 384 samples, adaptive sampling (0.02), denoising, 8 bounces,
  caustics off, indirect clamp 8. View transform Khronos PBR Neutral, exposure −0.7. The cutaway views
  (plan/front/side/3q, ceilings removed) use an extra −0.5 EV.
  A full render of the 17 images takes about 13 minutes.
- **Exposure check** (`metadata/exposure_stats.txt`): clipped pixels are at most 0.46 % (the side cutaway) and
  under 0.03 % in every source-camera view. Near-black pixels are at most 2.5 %, all from black objects (TV, gloss
  glass), not underexposure.

## Reviews and verdicts
- **My own visual review** of all 10 matched-camera comparisons and the 4 cutaways, at every iteration (v1–v13).
  Main corrections:
  - v1: tinting a library material overwrote its base colour, which made the sofa and armchair white. Fixed by
    multiplying the tint into the colour instead.
  - Rug sheen washed the red out to pink.
  - The scene was too bright and too neutral overall.
  - The floor was too grey and needed tile seams.
- **Structured image reviewer** (`acceptance review-images`, codex; 14 images per request; repair budget 3 rounds).
  All three judgments passed the schema check and **all three were rejected**:
  1. **v5 rejected.** Sconce light white rather than warm, weak daylight, toaster plain grey, sofa too warm and
     smooth, chairs brownish. The arc-lamp chrome contrast and rug colour were raised as nonblocking.
     → Saturated warm sconces, cooler and stronger daylight, darker matte leather, deeper rug red, chrome toaster.
     The view transform changed from AgX to Khronos PBR Neutral, because AgX bleached the warm sconce pools to white.
  2. **v9 rejected.** Now too warm overall, sofa brown-black, sconce pools broad with hard edges; lamp-shade
     undersides not lit (nonblocking).
     → Warm-neutral fill, more daylight, neutral greige walls, bluer sofa tint, narrower soft-edged sconce beams with
     a point glow, bulbs inside the lamp shades.
  3. **v12 rejected.** Sofa near-black, toaster a plain pale block, overview/side cutaways washed out; daylight and
     lamp-shade glow still weak (nonblocking).
     → **v13** (delivered): lighter charcoal sofa, brushed-steel toaster, −0.5 EV for the cutaway views only. With the
     3-round budget used up, **v13 was not re-reviewed by the reviewer**. I checked it myself against frames
     35–1039: the sofa now reads charcoal grey like frames 520/589, and the cutaways keep shading on the white walls.
- **Acceptance status: not accepted.** No candidate was registered and no Gallery selection was made. The
  task claim `showcase-42899712-mat-a5` is released as `handoff`, not `completed`.

## Problems and handling / known limits
- `tools/review_images.py` is not executable (it fails with a permission error when it calls itself as the
  executable). I used the equivalent `bash tools/indoor acceptance review-images` instead.
- The interiors of the arc-lamp shades do not glow: the back-face emission did not show, likely because of the shade
  normals or closed shells, and the geometry may not be edited. The small bulbs inside the shades provide the light,
  but the bright undersides seen in frame 970 are only partly reproduced.
- The toaster is a single slanted block in the base geometry. A material alone cannot show its slots or dials, so
  it reads as a plain steel block.
- The source video has a strong, varying warm white balance. The renders aim for a middle ground: neutral greige
  walls in daylight and warm pools near the sconces. The floor is paler and less yellow than in the warm kitchen
  frames (e.g. 139).
- Window views show a sky gradient, not the brick building opposite (frame 693).
- Remaining approximations inherited from the base scene's geometry (box-shaped pillows, chair and toaster shapes,
  door leaf edges) are out of scope here.

## Paths
- Working scene directory: `third_party/aha-3d/scenes/42899712_showcase_mat_a5/` (`blender/materials_v1…v13.blend`,
  `renders/final_v3, v5, v9, v12, v13` and `compare_v*`, `review/`, `work/`).
- The interim v5 delivery copies were moved, not deleted, to `superseded_v5/` in this run directory.
- Acceptance scope: `third_party/aha-3d/deliveries/42899712_showcase_mat_a5/acceptance/showcase-42899712-mat-a5/scope.json`.
- **Next actions** if acceptance is needed: register v13 as a candidate, run one more reviewer round on v13, and
  close the remaining findings: lamp-shade underside glow (needs shade geometry or normal fixes, outside this
  task's scope) and stronger daylight colour.
