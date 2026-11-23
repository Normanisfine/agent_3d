# SUMMARY — 42899729 A5 material and lighting revision (`42899729_showcase_mat_a5`)

## Result

- **`scene.blend`** is a byte-identical copy of
  `third_party/aha-3d/scenes/42899729_showcase_mat_a5/blender/materials_v6.blend`
  (sha256 `4e770f0f4078bd7ad68d309ea705a8c8b8789cfd2fe61d7d8140b9b1d5c99952`).
- **Base:** `runs/A5-claude/42899729/0/scene.blend` (v17 whitebox).
  - It was copied unchanged to `scenes/42899729_showcase_mat_a5/blender/base_v17.blend`
    (sha256 `1c4e6da2…`, identical to the original). The original was only read.
- **Built by** `scenes/42899729_showcase_mat_a5/build/apply_materials.py`, run as:
  `blender -b base_v17.blend --python-exit-code 1 --python apply_materials.py -- OUT.blend REPORT.json`.
  The script only reassigns material slots and adds lights, a world and render settings.
- **Stills** (`stills/`):
  - Presentation views at 1920 px wide:
    - `overview`: perspective from above, ceilings hidden from camera rays;
    - `front`: orthographic, looking north at the windows;
    - `side`: orthographic, looking west at the bed and accent wall;
    - `back`: orthographic, looking south at the doors and mirror;
    - interiors: `interior_bed`, `interior_window`, `interior_doors`.
  - Renders from **8 source-video cameras**: `source_camera_frame_000000/000104/000166/000249/000331/000456/000497/000621.png`,
    at 2048×1536.
  - `views_render_manifest.json` holds each view's camera matrix, lens, shift and the roots hidden from the camera.
- **Comparisons** (`compare/compare_000XXX.jpg`): 8 side-by-side images, with the HD source frame on the left and the
  material render from the same source camera on the right. They cover frames 0, 104, 166, 249, 331, 456, 497
  and 621 of the 0–642 clip.
- `superseded/v3/` and `superseded/v5/` keep the earlier delivered versions. They were moved there, not overwritten.

## What changed (and what did not)

- **Geometry is unchanged.**
  - `build/validate_materials.py` reopens the saved `.blend` and compares all 314 non-light objects with the base
    signature: world transform, evaluated mesh vertices/faces, parent, `instance_id`, `semantic_class` and
    visibility.
  - Result: 0 added, 0 removed, 0 changed. The 58 `instance_id`s are unique and unchanged.
  - Reports: `scenes/…/review/validate_materials_v6.json` and `geom_base_v17.json`.
- **Materials.**
  - All 256 mesh material slots were reassigned; no `whitebox_*` material remains, and no slot is empty.
  - Slots on meshes shared between objects use object-linked slots, so mesh data is untouched.
- **Added:** 7 lights in a new `Lighting` collection, an `Overcast` world, and Cycles/AgX render settings. Nothing
  else was added.

## Material choices

Approximate colours and finishes come from the HD source frames. The asset library was searched first:
- 8 registered RoomKit materials are used, some with colour/roughness overrides recorded in the report.
- The rest are authored Principled BSDF materials. Procedural patterns use world or object coordinates; no image
  textures are used.

| Surface | Material |
| --- | --- |
| Walls, bulkhead, window boxing | `roomkit-v1/warm-ivory-lime-plaster`, warm off-white |
| West accent wall | `additional-444547-44-v1/warm-grey-wall-paint`, greige |
| Floor and hallway floor | `additional-444547-47-v1/pale-wool-carpet`, beige; fine fibre bump and colour noise |
| Doors, trims, skirting, window frames, ledge, mirror frame | `roomkit-v1/warm-white-painted-joinery`; door V-grooves slightly darker |
| Divan and headboard | `roomkit-v1/charcoal-woven-upholstery`, dark grey |
| Throw | Authored charcoal chevron quilting: world-mapped on top, drape-local on hanging sides, plain quilted edge rolls |
| Duvet, mattress, pillows | White cotton with sheen |
| Cushions | Dark teal-grey velvet |
| Wardrobe | Dark brown-grey matt laminate; darker plinth |
| Chest of drawers | High-gloss greige lacquer with chrome knobs |
| Nightstand | Darker brown-taupe gloss |
| Table lamp | Chrome base and stem, clear solid-glass balls, reflective silver shade |
| Radiator | White enamel with a chrome valve |
| Blinds | Translucent white fabric, white roller, brushed bottom bar |
| Window and shower glass | Thin glass: transparent plus a camera-ray Fresnel reflection, so daylight passes |
| Mirrors | Mirror metal |
| Levers, hinges, switch/socket plates, folding-chair frames, both bins | `roomkit-v1/brushed-stainless-steel`; black switch/socket inserts |
| Folding-chair seats | Light grey |
| Bathroom | Beige 300 mm floor tile, cream gloss 200 mm wall tile, `additional-444547-45-v1/porcelain` sanitaryware, chrome taps, shower posts and towel rail |
| Hallway | Pale sage paint; opal emissive ceiling light |
| Canvases above the bed | Procedural red-poppy print on white |
| Hallway picture | Dark canvas with red accents |
| Booklet on the bed | Generic orange print with a navy centre band; the film-poster artwork is deliberately not reproduced |
| Towels | White terry with a strong fine bump |
| Downlights | Warm emissive lens with white trim |

The scene contains **no plants and no screens**, so none were authored.

## Lighting and render settings

- **Daylight:** two area emitters just outside the north sashes (1.3×1.8 m, 360 W and 0.9×1.8 m, 260 W), cool white
  (0.95, 0.97, 1.0). The world is a pale overcast blue, strength 1.2.
- **Interior fill:** a warm (about 3000 K) 2.6×2.6 m ceiling area light at 170 W, and two 25 W spots at the real
  downlight positions.
- **Doorway rooms:** warm area fills in the bathroom (60 W) and hallway (45 W) for the views through the doors.
- All lights are invisible to camera and glossy rays.
- **Render:** Cycles on the GPU (OptiX, RTX 5070 Ti Laptop), 256 samples, denoising on, up to 8 bounces, AgX with
  Base Contrast, exposure −0.6.
- **Source cameras:** taken from `perception/42899729/hd/cameras.json`. These are the bundle's 32 aligned cameras
  scaled to the 1024×768 HD frames, and the base run used the same file. No Pi3X inference was run.
  - Rendered at 2× with square pixels at height H·fx/fy, then resampled to the native 4:3 frame.
- **Section and overview views:** walls and ceilings are hidden **from camera rays only**, so lighting matches the
  interior views. Black bands in front, side and back are wall and floor cross-sections.
- **Runtime:** the final render log is `scenes/…/review/logs/final_v6.log`, exit 0 with `RENDER_OK 15`; it took
  about 16 minutes.

## Iterations and reviews

**My own visual review:** I inspected each test and final render against matched source frames (sheets in
`scenes/…/review/`).
- **v1:** too bright and neutral; throw, divan, wardrobe, carpet and dresser too light. The overview showed floating
  bathroom fixtures. The side view showed the unlit back of the headboard; the bed is against the west wall.
- **v2:** colours darkened; side view changed to look west; back view added; overview hides only ceiling parts.
- **v3:** exposure lowered and warmer fill added.

**Codex image reviews** (`acceptance review-images`, with codex given the actual images):

| Review | Candidate | Verdict |
| --- | --- | --- |
| Final review, 9 final views | v3 `dc46cf88…` | **Rejected.** Blocking: lamp shade matte white instead of silver; nightstand too pale versus the source's brown. Non-blocking: rings on the throw's curved edge. The output also failed schema validation (free-text aspect names). |
| Final review, 12 views | v5 `bbbae57f…` | **Rejected.** Valid structured judgment. Lamp and nightstand fixes were accepted. Blocking: semicircular patches on the throw's hanging drape. Non-blocking: booklet cover simplified. |
| Final review, 12 views | v6 `b69ccf39…` | **Accepted by the reviewer.** All uncertainties non-blocking. The only remaining finding is the non-blocking, intentional booklet simplification. Judgment: `deliveries/…/v6/final_review_raw_judgment.json`. |

**Fixes between reviews:**
- v4/v5: silver metallic shade; separate brown-taupe nightstand material; plain quilted material on the throw's rolls
  and hem folds; bedroom bin changed to brushed steel, which matches the source's metal mesh bin.
- v6: drape faces use object-local chevron mapping. The world-space channels had run nearly parallel to the rotated
  vertical drapes, which caused the ring and grain motifs.

**Technical check:** recorded for v3, v5 and v6 (`deliveries/…/v6/technical_report.json`, status passed). The
validator is described above.

**Acceptance status: not accepted** (`indoor acceptance check` reports `blocked`, `permitted: false`).
- The gate's adapter refuses an accepted verdict that still lists any finding or unreviewed area. The v6 judgment
  lists the non-blocking booklet finding plus inherent unreviewed areas (hidden backs, animation), so it could not be
  recorded as `final_review`.
- Reviewer findings `v3-lampshade-finish`, `v3-nightstand-finish`, `v3-throw-pattern-artifacts` and
  `v5-booklet-cover-simplification` stay `open` in the ledger. They were corrected in v5/v6 and re-checked by the v6
  reviewer, but formal `resolve` needs a gate-validated structured review, so they were not closed.
- `layout` and `preview` checks are not satisfied. Layout is inherited from the base, which itself was never
  layout-accepted (see the base SUMMARY); no preview stage applies to this stills-only material pass.
- No Gallery/results selection or promotion was done.

## Problems and how they were handled

- **Geometry must not change.** Every material version was validated against the base signature before rendering.
- **Black cut faces in section views.** Near walls are hidden from camera rays only, and the side view was changed to
  avoid showing the unlit back of the headboard.
- **Too bright and neutral against the warm, dim source.** Exposure was lowered to −0.6, the fill warmed, and dark
  textiles and furniture darkened. Source white balance still differs; colours are approximate.
- **Throw pattern artifacts on rotated drapes.** Fixed with drape-local mapping (see the reviews).
- **Reviewer schema failure on v3.** The v5/v6 requests state the exact aspect-name rule.
- **Remaining approximations:**
  - The windows show a uniform overcast exterior with interior reflections, not the street.
  - Pictures and the booklet are generic procedural prints.
  - Textures are procedural and not matched to the source.
  - Inherited geometry approximations from the base remain: primitive pillows, boxy throw, no
    folding-chair seat detail.
- **Shared GPU:** free memory was checked before every render; one GPU job ran at a time, and only processes this
  task started were stopped.
- **Other paths:** nothing outside this run directory and the claimed `scenes/` and `deliveries/` paths was modified.
  No git commit or push was made.

## Evidence and paths

- **Task claim:** `showcase-42899729-mat-a5`, owner `claude-showcase-mat-a5-42899729-20261122`.
- **Acceptance:** `deliveries/42899729_showcase_mat_a5/acceptance/showcase-42899729-mat-a5/`; candidate and review
  files are in `deliveries/42899729_showcase_mat_a5/v{3,5,6}/`.
- **Intake:** `intake/` (`indoor intake` output, ready_for_authoring).
- **Build scripts:** `scenes/42899729_showcase_mat_a5/build/`:
  - `apply_materials.py`, `render_stills.py`, `make_compare.py`, `validate_materials.py`;
  - `geometry_signature.py`, `list_objects.py`, `probe_materials.py`, `sheet.py`.
- **Material report:** `materials_report.json` (per-slot old→new assignment, provenance, lights, world).

## Next actions (if acceptance is required)

1. Run the layout gate on the inherited geometry (or accept the base layout in its own task).
2. Adjust the review adapter or request so an accepted verdict with only non-blocking intentional simplifications can
   be recorded.
3. Then resolve the four reviewer findings against v6.
