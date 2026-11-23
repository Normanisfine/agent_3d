# Run summary: 42898849 / A5 material showcase

**Result:** the material scene, presentation stills, source-camera renders and comparisons are
delivered. The scene's geometry is verified identical to the base scene. However, the independent
image review **rejected** the final revision (v13). Four material and lighting findings are still
open after the declared repair budget of 3 rounds. They are listed below and are not waived.

## Deliverables

| Path | Contents |
| --- | --- |
| `scene.blend` | Final material scene. Byte copy of `third_party/aha-3d/scenes/42898849_showcase_mat_a5/blender/materials_v13.blend` (sha256 `a401074d0a6b…`). |
| `stills/` | 8 presentation views at 1920×1200: `overview`, `front`, `side`, `plan` (top-down), `interior_kitchen`, `interior_living`, `interior_bay`, `interior_hall_to_garden`. |
| `stills/source_frame_NNNNNN.png` | 9 renders from source-video cameras at 1200×1642, for frames 0, 186, 371, 510, 696, 928, 1067, 1206 and 1392 (0–144 s of the 10 fps clip). |
| `stills/renders.json` | Camera, resolution and render-setting provenance for every image. |
| `compare/compare_frame_NNNNNN.jpg` | 9 side-by-side images: source video frame on the left, the render from the matched source camera on the right. Same 9 frames as above. |
| `material_assignments.json` | Old whitebox slot → new material for each of the 376 `instance_id`s. Fallbacks: 0. |
| `technical_check.json` | Geometry identity and material coverage check of `scene.blend` against the base scene (passed). |
| `reviews/` | Request and verdicts for each image-review round. |
| `intake/` | Recorded request (`bash tools/indoor intake`). |
| `_superseded_v5/`, `_superseded_v8/`, `_superseded_v11/`, `_superseded_v12/` | Earlier deliveries from this task, moved rather than overwritten. |

Working files are in `third_party/aha-3d/scenes/42898849_showcase_mat_a5/`:

- `blender/base_v0.blend`: read-only copy of the base scene, sha256 `aa74d5d5e835…`, unchanged from `runs/A5-claude/42898849/0/scene.blend`.
- `blender/materials_v1…v13.blend`: one file per revision.
- Scripts in `workflow/`:
  - `apply_materials.py`: materials, lights and world.
  - `render_views.py`: stills and source cameras.
  - `deliver.py`: stills and compare images.
  - `geometry_fingerprint.py`: technical check.
  - `sheet.py`: contact sheets.
- `review/`: test renders, logs and contact sheets.

## What changed

Only materials, lights, world and render settings changed. No object was moved, added, deleted,
rescaled or reshaped.

- **Materials.** Every mesh material slot was relinked at the object level (`slot.link='OBJECT'`).
  Mesh data was not touched.
- **Lights.** The base scene's single `sun` lamp was replaced by a `Lighting` collection of 24 lights.
- **World.** A new world, `Overcast garden`.
- **Render settings.** Cycles on the GPU.

`technical_check.json` reopens both `.blend` files and compares every non-light object: type,
parent, world matrix, `instance_id`, `semantic_class`, vertex-coordinate sha256, vertex and polygon
counts, and slot count. Result:

- 752 objects in each file, with identical names and 0 differences.
- 376 unique `instance_id`s.
- 107 materials in use, and no whitebox `wb_*` material left.

## Material choices

**Registered RoomKit materials (`assets/roomkit/v1`), used where they fit:**

- Warm white painted joinery: doors.
- Honed ivory stone countertop: worktops.
- Brushed stainless steel: handles, rod, kettle, toaster, dish rack.
- Aged brass handles: lamp bases, TV-cabinet handles.
- Satin blackened iron: wood stove.
- Soot-dark refractory brick: fireplace recesses.
- Aged oak mantel: kitchen mantel.
- Honey oak beams: log holder.
- Walnut furniture frames: hall console.
- Dark television glass: TV.
- Deep green orchid leaves: plants.
- Glazed cream ceramic: vase.
- Charcoal ceramic bowl: shelf planter.
- Green pears: some fruit.
- Cream linen and taupe woven cushions: two of the cushions.

**Registered materials looked at and not used:**

- Warm ivory lime plaster: too mottled and pale for the flat cream emulsion in the video.
- Natural oak floorboards: wrong scale and orange tone; cross-laid boards on a test render.
- Ivory linen sofa: too white.
- Ivory woven rug with charcoal border: the video's rugs are plain grey.

**Authored Principled BSDF materials (prefix `MAT |`), approximating the video:**

| Surface | Material |
| --- | --- |
| Walls | Cream emulsion |
| Ceiling | White paint |
| Floor | World-space long oak boards running along +Y, as in the hall and galley views, with per-board tone, grain and soft seams. Final: pale natural oak. |
| Rugs | Grey wool carpet; coir doormats |
| Kitchen units, fridge, island, shelves | Gloss cream lacquer with grey plinths |
| Corner and TV cabinets | Painted cream |
| Window and door frames | White uPVC |
| Radiators | White enamel |
| Window glazing | Thin architectural glass: transparent with fresnel reflections, so daylight passes |
| Sofas | Greige linen; dark feet |
| Cushions | Blue-grey and cream knit |
| Throws | Cream, red and mink |
| Roman blinds and curtains | Taupe linen |
| Trunk, side tables, lamp table | Honey pine with black iron straps |
| Piano | Dark mahogany, a procedural black and ivory keyboard, ruled sheet-music paper |
| Bar stools | Grey leather seats, chrome bases |
| Range cooker | Cream enamel, black oven glass |
| Christmas tree | Fir needles with warm fairy-light speckles; ornaments alternate gold, red, silver and champagne |
| Presents | Red, gold, green and white wrap |
| Banner letters | Red and green felt, alternating |
| Stars, wreaths | Red and green felt; wreath foliage |
| Logs | Split firewood with bark |
| Hearth | Grey slate |
| Living-room mantel | Weathered grey oak |
| Hydrangea | Blue |
| Pictures | Framed-picture materials with an image-like interior inside a white, dark or silver border; gilt and dark frames for the two paintings |
| Books | Navy, red, green and cream covers |
| Small objects | Wicker baskets and lantern; porcelain figurines; mugs; candles; satin-chrome sockets; black cables and appliances; red boxes and sign; glass goblets; green bottle |

## Lighting and render settings

**Lights:**

- **Daylight:** a soft sun from the garden side (+Y), 2.2 W/m², 12° angle, warm white.
- **Window portals:** 5 portals at the French doors and the four windows.
- **World "Overcast garden":** a direction-based backdrop with lawn below, an irregular noisy
  treeline and a bright overcast sky, at strength 1.4. No exterior geometry was added.
- **Interior fill:** 4 soft ceiling area lights at 40–120 W, warm 0.88/0.76 tint.
- **Practical lamps:** point lights inside the 5 lamp shades (120–220 W) and the 2 pendants (20 W).
  The shades are emissive and translucent, so the light passes through them as a warm glow.
- **Kitchen:** 7 warm strip lights under the shelves and wall cabinets.

**Render settings:**

- Cycles, OptiX on the RTX 5070 Ti, 256 samples, denoising on.
- 8 bounces, 16 transparent bounces, indirect clamp 8.
- AgX view transform, "Medium High Contrast" look, exposure −0.4.
- Size and output:
  - Stills: 1920×1200.
  - Source cameras: 1200×1642 at the source aspect.
  - The full set of 17 images takes about 14 minutes.

**Cameras:**

- Source cameras come from `perception/42898849/bundle/alignment/cameras.json`: OpenCV
  camera-to-world converted with `diag(1,-1,-1)`, with lens and shift from the intrinsics.
  Pi3X was not rerun.
- Cutaway views (overview, plan, front, side) hide the ceiling for rendering only, use a transparent
  film and are composited onto a light grey backdrop.

**Exposure check, from pixel statistics:**

- No still has more than 1% clipped pixels, except the lamp-shade highlight at frame 696 (2.3%).
- No interior view has more than 3% near-black pixels.

## Reviews and verdicts

| Review | Result |
| --- | --- |
| My own visual checks at each revision (contact sheets in `review/test_vN`, `review/final_vN_sheet.jpg`) | Drove fixes v1→v5: overexposure, orange and wrongly scaled floor, white sofas, pale logs, black chimney tops in cutaways |
| Codex image review, round 1 (v5, 17 images) | **Rejected.** Piano keys all white; blank pictures and books; floor too brown and glossy. Non-blocking: weak lamps |
| Codex image review, round 2 (v8) | Answer refused by the adapter (the "uncertainty" aspect was missing). Draft verdict: rejected. Keys fixed; inserts too loud; floor; lamps. Saved as `reviews/material_review_v8_draft_unvalidated.json` |
| Codex image review, round 2 (v12) | **Rejected.** Picture inserts and sheet music; floor too tan with dark seams; flat window panes. Non-blocking: lamps |
| Codex image review, round 3 (v13, final) | **Rejected**, details below |
| Technical check of v13 (`technical_check.json`) | **Passed** |

Round 3 verdict on v13:

- **Resolved:** picture inserts.
- **Blocking and still open:**
  - `MAT-002` (piano): the sheet music reads as a striped surface, not printed paper.
  - `MAT-003` (floor): the floor is flat beige and needs more timber variation and a satin finish.
  - `MAT-004` (windows): the green exterior backdrop still reads as opaque.
  - `LIGHT-001`: the lamp shades are too white and the golden spill on the walls is too weak.

The repair budget is 3 rounds, and all 3 are used. The open findings are recorded in the
review files rather than waived.

## Problems and how they were handled

- **Overexposure and washed-out colour.** First tests were too bright. Fixed by lowering exposure
  to −0.4 and the world strength to 1.4, and by darkening the sofa and carpet base colours.
- **Floor orientation and scale.** The registered floorboards stretched and crossed the room. I
  authored world-space boards. Frames 0 and 1206 look along ±Y, which confirmed the boards run
  along Y. Board width and seams were tuned over several revisions. The reviewer's preferred tone
  (paler) and my reading of the darker galley frames disagree; the final tone follows the reviewer.
- **Black slabs in the cutaways.** These were chimney-breast tops under a ceiling hidden from the
  camera only. Fixed by hiding the ceiling completely in cutaway renders.
- **Lamps had no effect.** The point lights sat inside closed, opaque shade meshes. Fixed with a
  translucent, emissive shade material, without changing geometry.
- **Black windows from outside (v11).** This came from stronger glass reflection. I reverted to the
  earlier glass settings (v12) and re-rendered the full set.
- **Photo frames looked blank.** The visible faces are the frame box, not the small insert face. Fixed with
  a bounding-box "picture inside a border" material.
- **Review tooling.**
  - `tools/review_images.py` is not executable in the checkout, and I did not change repository
    files. I used `bash tools/indoor acceptance review-images` instead.
  - One reviewer reply left out a coverage aspect. Later requests asked for it explicitly.
- **Waiting on a finished process.** A zombie process made `kill -0` waits hang. Later waits poll
  the log for "Blender quit" instead. All Blender jobs I started have exited.
- **Earlier outputs.** Each new delivery moved the previous one into `_superseded_vN/`. Nothing was
  overwritten.

## Acceptance state and limits

- **Claim and scope.** Claim `showcase-42898849-mat-a5` covers `scenes/42898849_showcase_mat_a5` and
  `deliveries/42898849_showcase_mat_a5`. Its acceptance scope was initialized; `indoor acceptance check`
  reports `blocked`.
- **Layout.** This material task did not rebuild layout evidence. Geometry is inherited unchanged from
  the base run, whose own layout and final reviews were rejected or blocked; see its SUMMARY.
  Geometry is final by request.
- **Not edited.** Primitive silhouettes (slab sofas, cone tree and so on) are unchanged and out of scope.
- **Exterior.** The garden is a procedural world backdrop, not geometry, so it shows no parallax or
  detail.
- **Accuracy.** Colours are approximations under a different white balance. Texture matching was not
  attempted, per the request.
