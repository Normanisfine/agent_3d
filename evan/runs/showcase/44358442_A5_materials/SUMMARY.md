# 44358442 A5: furnished materials and lighting (showcase revision)

**Status: delivered.** The independent Codex image reviewer **accepted** the final revision (v7b). Its only remarks are two non-blocking, optional refinements. The project's formal acceptance gate is still incomplete (see "Reviews and verdicts"). The task claim is released as `handoff`, not `completed`.

## What changed
- **Base scene.** `runs/A5-claude/44358442/0/scene.blend` (sha256 `722a9694…`) was copied unchanged to `scenes/44358442_showcase_mat_a5/blender/base_v5.blend`. The original was never written.
- **Final scene.** `scene.blend` here is byte-identical to `scenes/44358442_showcase_mat_a5/blender/materials_v7b.blend` (sha256 `70a20e12…`).
- **Only these were changed:**
  - material slots on the existing meshes;
  - a new world;
  - five added lights: `daylight_sun`, `window_portal`, `window_sky_fill`, `pendant_bulb`, `hall_lamp_bulb`;
  - energy and colour of the two existing whitebox area lights;
  - Cycles render settings.
- **Geometry is untouched.** `review/geometry_check_final.json` compares base and final:
  - all 983 non-light objects have identical names, world matrices, vertex positions, `instance_id` and `semantic_class`;
  - all 377 semantic roots are intact;
  - no mesh keeps a `wb_*` whitebox material.
  - `apply_materials.py` also aborts if its own geometry fingerprint changes.
- **Builder code** is in `scenes/44358442_showcase_mat_a5/build/`:
  - `apply_materials.py`: materials, world and lights;
  - `render_materials.py`: Cycles renders using the base run's exact camera definitions;
  - `render_final_v7b.sh`;
  - `make_compare.py`;
  - `verify_geometry.py`.
- **Per-object assignments** are in `materials_assignment.json`.

## Material choices
**Registered library materials** (from `assets/INDEX.md`):

| Material | Used for |
| --- | --- |
| `roomkit-v1/warm-white-painted-joinery` | white desk, hutch, nightstands, daybed |
| `additional-444547-47-v1/pale-wool-carpet` | room and landing carpet |
| `roomkit-v1/honey-oak-beams` | wardrobe top and knobs |
| `roomkit-v1/brushed-stainless-steel` | clothes rack, hanger hooks |
| `roomkit-v1/satin-blackened-iron` | chair frame, curtain rod and rings, black knobs |
| `roomkit-v1/charcoal-woven-upholstery` | chair seat and back |
| `roomkit-v1/dark-television-glass` | phone screen, projector lens |
| `roomkit-v1/deep-green-orchid-leaves` | plants |
| `roomkit-v1/glazed-cream-ceramic` | cat figurine, lamp base |
| `roomkit-v1/lampshade-ivory-linen` | hallway lamp shade (the authored lit variant is the one assigned) |
| `roomkit-v1/warm-practical-bulbs` | string lights |
| `roomkit-v1/aged-brass-handles` | door handle |

**Authored Principled BSDF materials** (where nothing in the library fit):
- **Walls and trim:** mint/turquoise wall paint with subtle variation; white ceiling and satin trim; cream landing walls.
- **Landing brick:** muted ochre brick, procedural Brick texture with darker mortar and bump.
- **Door and frame:** orange lacquered pine.
- **Window:** dark varnished frame and clear glass. The glass is mostly transparent for all rays so daylight enters, with a faint reflection.
- **Wardrobe:** ivory painted body.
- **Curtains:** red gingham (procedural check).
- **Duvet:** pale-blue floral (procedural rose and leaf pattern); one floral pillow; white pillows; mattress ticking.
- **Textiles and clothing:**
  - mustard throw;
  - navy fleece gown with white hood lining;
  - black, navy and brown coats with tonal noise;
  - denim floor pile;
  - yellow yoga mat;
  - teal tote;
  - wicker baskets with mixed laundry;
  - cream rug.
- **Shoes and slippers:** tan and black leather shoes with rubber soles; cream fleece slippers.
- **Small objects:**
  - white and black plastics;
  - black cables;
  - black luggage shell;
  - red tin;
  - blue tissue box;
  - yellow sticky note;
  - white paper;
  - kraft boxes;
  - terracotta pots;
  - white enamel radiator.
  - Bottles, hutch clutter and storage boxes get seeded colours from palettes taken from the video (toiletries, kraft/cream/red boxes).
- **Lit fixtures:** emissive paper pendant shade, lit table-lamp shade, wall light.
- **Pictures, posters, calendar, cards and books are textured from the source video.**
  - Each object takes the source frame with the largest unoccluded, frontal view. Occlusion is checked by scene ray casts from the Pi3X camera.
  - The surface colour is looked up by projecting through that frame's exact Pi3X camera (shader-only; no UVs or mesh edits).
  - 191 of 248 such objects got a projection, using 16 packed frames.
  - The rest (41 books, 9 postcards, a few cards) get seeded cloth or print colours.
  - The frames are packed into the `.blend`; copies are in `scenes/44358442_showcase_mat_a5/references/frames/`.

## Lighting and render settings
- **World:** overcast daylight sky, strength 1.7 for lighting. Camera rays see a soft blue-green foliage backdrop through the window. In the cut-away inspection views (plan/front/side/overview) the backdrop is switched to neutral grey.
- **Daylight:** sun from the garden side (2.2, 8° angle) plus a window portal and a cool area sky-fill just inside the window.
- **Interior fill:** warm ceiling area lights (room 70 W, landing 45 W), a pendant bulb (40 W) and the hallway lamp (12 W). Area lights are hidden from camera and reflections.
- **Cycles:** GPU (OptiX), 256 samples with adaptive sampling, OIDN denoising. AgX view transform with the Punchy look, exposure −0.8. Caustics off.
- **Resolutions:**
  - Inspection stills and interior views: 2048×1536.
  - Matched source-camera views: 1024×768, the same as the base whitebox.
- **Timing:** about 45–70 s per 2K still and about 15–25 s per 1K view, on a GPU shared with other tasks.

## Deliverables
- **`stills/`**
  - `plan`, `front`, `side`, `overview`, `overview_2` (2048 px). Same cameras and hidden objects as the base `final_views`.
  - `interior_000162`, `interior_000243`, `interior_000453` (2048 px, source cameras).
  - `model_000016/130/194/243/291/340/437/502` (1024×768). These are the same source cameras, resolution and frame numbers as every source-camera whitebox render in the base `final_views/`.
  - Camera provenance: `views.json` and `matched_views.json`.
- **`compare/`:** 13 side-by-side images, source frame on the left and the matched-camera render on the right. Frames 16, 32, 65, 97, 130, 194, 243, 291, 340, 389, 437, 453 and 502 (1.6–50.2 s).
- **`final_views.json`:** final-view manifest with the input binding.
- **`review/`:** all requests, judgments, logs and finding records.
- **`superseded_v4/`, `superseded_v5/`, `superseded_v6/`:** earlier delivery copies, kept instead of overwritten.

## Reviews and verdicts
1. **Intake.** `bash tools/indoor intake` recorded `intake/` (status `ready_for_authoring`, no questions). Claim `showcase-44358442-mat-a5`. Acceptance scope initialized: kind reconstruction, stills, `reference_reconstruction: false` because geometry is reused.
2. **My own visual checks** (matched source/render pairs) at each iteration:
   - v1–v3: fixed a visible window-fill light, over-exposure, sparse duvet roses and pastel box colours.
   - v4→v5: fixed a door that rendered pale beige; it now uses orange pine.
3. **Codex review, v5** (`acceptance review-images`, candidate `062940b1…`): **rejected**. Blocking: brick too red with pale mortar; mustard throw pale tan. Non-blocking: window backdrop looked like masonry; garments too uniform.
4. **Codex review, v6** (candidate `d5db665b…`): **rejected**. Same three issues still visible; non-blocking: smooth carpet.
   - The "masonry" turned out to be the poster wall reflected in the glass. It was fixed by reducing the glass reflection.
   - AgX desaturation was flattening the mustard throw. It was fixed with the Punchy look and a deeper base colour; the throw now renders about (180,114,23) against (210,129,0) in the source.
5. **Codex review, v7b** (candidate `fc849878…`): **accepted**. Remaining non-blocking remarks: carpet looks smooth and cool, and the overall palette is cooler and greener than the warm white balance of the source footage.
   - The gate validator refused to store an "accepted" verdict that still carries any finding or unreviewed area. The reviewer always lists geometry as out of scope.
   - The raw judgment is kept as `review/final_review_v7b_raw.json`, and the log is `review/final_review_v7b.log`.
6. Reviewer findings `review-v5-f1..f4` and `review-v6-f1..f5` are recorded in the ledger. They remain **open**: closing them requires a validated before/after review record, which the gate would not persist (see 5). The v7b images show them fixed.
7. **Not done:** no technical or preview check receipts and no Gallery/results selection. Acceptance is therefore `incomplete`, and the claim is released as `handoff`.

## Problems and how they were handled
- **Repair budget:** 3 repairs, 2 used after independent review (v6, v7b).
- **Camera aspect:** the base run's camera conversion uses square pixels, but the Pi3X processing size (364×266) is slightly anisotropic relative to the 1024×768 video. Kept for exact parity with the whitebox stills; renders can sit up to about 2.5% vertically off the source near the image edges.
- **Projected textures:** posters, pictures and books carry the source frame's baked lighting. Where the simplified geometry differs from the real object, a projection can pick up a neighbouring wall colour.
- **Carpet:** the registered material is smooth (a reviewer remark), and was kept to reuse the library material.
- **Palette:** cooler than the source's warm auto white balance.
- **Session binding:** the session name I first used was already bound to another task (`42898849_showcase_mat_a5`), so I bound this task under a new session name. The other task's binding was not touched.
- **Wait loops:** two of my wait loops never exited because `pgrep -f` matched the loop's own command line. They were stopped; no renders were affected.
- **No changes outside scope:** no Pi3X inference was rerun, nothing outside this run directory and `scenes/44358442_showcase_mat_a5/` was modified, and there are no git commits.
