# Material showcase: 42897538 / A5 base

## Result
- **`scene.blend`** is a byte-identical copy of
  `third_party/aha-3d/scenes/42897538_showcase_mat_a5/blender/materials_v9.blend` (sha256 prefix 6815efc98b54a312).
- It is built from a copy of the reviewed whitebox `runs/A5-claude/42897538/0/scene.blend` (room_v13, sha256 prefix
  53d9441679699245), saved as `scenes/42897538_showcase_mat_a5/blender/base_v13.blend`. The base run was only read.
- **`stills/`** holds 21 Cycles renders and `views.json`, which records every camera and its settings.
  - 13 source-camera views: `source_000000` … `source_000955`. These are the same frames, cameras (K, principal-point
    shift, pixel aspect) and 1024×768 resolution as the base whitebox stills.
  - `plan`, `front`, `side`, `overview_se`, `overview_nw`: the same camera transforms and ortho scales as the base
    stills, rendered at 1.2× resolution (1680 px wide).
  - 3 interior eye-level views, 1920×1280: `interior_sw` (from the window corner towards the TV, door and sofa),
    `interior_ne` (from the hall door towards the loveseat and windows) and `interior_w` (from the loveseat end towards
    the sofa and mirror).
- **`compare/`** holds 13 side-by-side images, one for every matched source frame from 0 to 955. The left half is the
  source video frame (`perception/42897538/hd/frames`) and the right half is the material render from the same camera.
- `materials_report.json` lists every material with its provenance (registered asset ID and library hash, or
  "authored"), every light, the world, the render settings and all 484 slot assignments (object, old → new).
- `superseded_v6/` and `superseded_v8/` hold the two earlier, review-rejected deliveries. They were moved there
  intact, not overwritten.

## What changed
- **Geometry is unchanged.** A signature of every non-light object was compared between the base and the output
  (`build/geometry_signature.py`): world matrix, evaluated vertices and faces, name, parent, `instance_id`,
  `semantic_class` and render visibility. All 591 objects are identical in v6, v8 and v9. All 107 `instance_id`
  roots are kept.
- **Only material slots were reassigned.** Rules map (root, old whitebox material) to a new material, with a few
  part-index overrides: worktop and plinth of the kitchen runs, the oven top, and the tree base and top. Shared mesh
  data would get object-linked slots; none was shared. No object is left on a `WB_*` material, and unused `WB_*`
  materials were removed.
- **Added:** the `showcase_lighting` collection (10 lights), a new world, and Cycles/AgX render settings.
- Script: `scenes/42897538_showcase_mat_a5/build/apply_materials.py` (base → materials_vN).

## Material choices
**Registered library materials** (asset index searched first; some have colour or roughness overrides):

| Surfaces | Asset |
| --- | --- |
| Walls | `roomkit-v1/warm-ivory-lime-plaster` (neutralized off-white) |
| Skirting, window frames, radiator, hall door frame | `roomkit-v1/warm-white-painted-joinery` |
| Door handles, sink, oven, cabinet handles | `roomkit-v1/brushed-stainless-steel` |
| Table-lamp base | `roomkit-v1/satin-blackened-iron` |
| TV screen | `roomkit-v1/dark-television-glass` |
| Tan lamp shade | `roomkit-v1/lampshade-ivory-linen` |
| Tree foliage | `roomkit-v1/deep-green-orchid-leaves` |
| Mirror and picture frames, carriage clock (antique gold) | `roomkit-v1/aged-brass-handles` |
| Living-room and hall beige carpet | `additional-444547-47-v1/pale-wool-carpet` |
| Kitchen floor and black worktops | `additional-444547-44-v1/dark-stone` |
| Turned lamp table (dark red-brown) | `additional-444547-44-v1/mahogany-sideboard` |
| Plates, sill ornament | `additional-444547-45-v1/porcelain` |

**Authored Principled materials** (used where nothing in the library fit):
- **Leather and fabric:** muted beige glossy leather with a clear coat (both sofas), a greyish cream leather
  (ottoman), cream check fabric (loveseat cushions) and a mauve-grey textured cushion (sofa cushions).
- **Rugs:** procedural Persian-style rugs with a field, border band and floral speckles: cream/salmon for the living
  room, red/navy for the kitchen, and a multicolour hall runner.
- **Wood:** honey oak with grain (doors, kitchen door frame), black-brown LACK-style wood (coffee table, corner side
  table, TV stand) and a red-brown chest top.
- **Plastics:** glossy black (TV bezel, phone), black (plugs, bin, black cables), white (sockets, power strips, white
  cables, switches), yellow ethernet cable, a dark dimmer switch and dark-green fairy-light wire.
- **Metal and glass:**
  - chrome (chandelier arms, radiator valves, tap) and a gold bauble finish
  - a mirror material
  - clear thin window glass and frosted door/transom glass. Both are transparent to secondary rays, so mirrors and
    daylight work through them.
  - crystal for the glass bowl and chandelier drops, and an opal ceiling-light shade
- **Kitchen and hall:** white gloss for the kitchen doors and hall chest, white appliance enamel (fridge) and black
  oven glass.
- **Small objects:** baked biscuits, a printed tissue box, a printed magazine/poster sheet, a muted oil painting, a
  brown carved tree base, a white package, and translucent vertical-blind fabric.
- **Emissive bulbs:** warm emission for the chandelier and hall bulbs and for the fairy lights.

## Lighting and render settings
- **World:** a gradient sky above the horizon and lawn green below it, seen through the windows. Strength is 8 for
  camera and glossy rays and 2 for diffuse lighting, so the exterior looks bright, as in the video, without flooding
  the room.
- **Daylight:**
  - a soft afternoon sun from the south-west (2.6 W/m², 6° angle, near neutral)
  - Cycles portal lights on the west, south and kitchen windows
- **Interior fill (neutral):**
  - living-room ceiling area light: 4×2.8 m, 160 W
  - kitchen fill: 40 W. The kitchen ceiling is unmodelled in the base.
  - hall fill: 25 W, slightly warm
- **Practicals (warm):** 2 chandelier point lights (45 W each) and a hall ceiling light (20 W). The chandeliers are lit
  in the source (frames 462, 585, 924).
- **Cycles:**
  - GPU (OptiX, RTX 5070 Ti Laptop), 256 samples with OpenImageDenoise
  - max bounces 8 (diffuse 4, glossy 4, transparent 16), indirect clamp 10
  - AgX view transform, Medium High Contrast look, exposure −1.2
- **Timing:** each full 21-view render took about 25–30 minutes on the shared GPU.
- **Section views:** for `plan`, `front`, `side` and the overviews, the ceilings (and, for front/side, the cut wall
  with its wall-mounted items) are hidden from **camera rays only**. Lighting is identical to the source-camera views.
  In Workbench the base hid them with `hide_render` and the clip plane; in Cycles that exposed the unlit insides of the
  wall boxes as black.
- Render script: `build/render_stills.py`. Compare script: `build/make_compare.py`.

## Reviews and verdicts
- **My own review.** At every iteration I checked matched source-vs-render sheets (frames 0, 62, 154, 246, 308, 400,
  493, 616, 709, 893, 924, 955) and the overview and interior stills. I also compared mean pixel colours on walls,
  carpet, sofa and door against the source frames to calibrate exposure and white balance. Iterations v1 to v5 fixed:
  - an inverted rug border
  - a wrong oak grain direction
  - over-exposure
  - over-saturated orange leather and walls
  - exterior seen through glass rendering black in the mirror. Fixed by making the glass transparent to non-camera
    rays.
  - black section views
- **Codex image reviewer** (`tools/review_images.py` → `review_contract.run_reviewer`). Each round used 16 images:
  8 stills and 8 compares (frames 0, 154, 308, 400, 616, 709, 893, 924).
  - **v6: rejected.** Blocking: a warm ambient cast. Non-blocking: pale, matte leather; flat saturated gold. The
    adapter also refused to record it (see below). Raw judgment: `review/review_v6_raw.json`.
  - **v8: rejected.** Blocking: a residual warm cream cast; mustard frames. Non-blocking: pale leather. Also not
    recorded by the adapter. Raw judgment: `review/review_v8_raw.json`.
  - **v9 (delivered): rejected.** This is a valid recorded judgment: `review/review_v9.json`.
    - Blocking: the sofas still read as pale, largely matte rather than darker, glossier leather.
    - Blocking: the frames still read mustard yellow-orange with conspicuous speckling.
    - Non-blocking: the lighting is flatter than the source, with weaker cool daylight versus warm fixtures.
    - Non-blocking: the table-lamp base is near-black rather than brown-bronze.
- **The 3-round repair budget declared in the acceptance scope is spent.** The two v9 blocking findings stay open
  (see below). **Acceptance did not pass.** No candidate was registered. The claim was released as **handoff**, not
  completed.

## Problems and how they were handled
- **`tools/review_images.py` is not executable** in the checkout, so its self-invocation failed with
  PermissionError. Rather than chmod a shared file, I called it through a wrapper,
  `build/review_images_exec.sh`.
- **Custom review coverage never validates.** Codex's output schema limits `aspect` to the default enum
  (inventory/placement/…), so coverage names like "materials" or "lighting" fail with "coverage incomplete" (v6, v8).
  v9 used `inventory` and `relationships`, and its judgment validated.
- **Waiting on renders.** The Blender render processes stayed as unreaped zombies, so a `kill -0` waiter never ended.
  The v6 waiter hit its time limit after the render had already finished. Later waits polled the log for `RENDER_OK`.
- **Shared GPU.** Another task held the GPU at 99% during the renders. Free memory was checked each time, and only one
  GPU job of mine ran at a time.
- **Geometry limits** (out of scope; geometry is final): faceted primitive sofas, slab-like blinds, a simple
  cone-shaped tree. Some of the "matte/pale" impression of the leather comes from the faceting.

## Open findings and next actions (if more presentation polish is wanted)
1. **Leather:** darken towards about sRGB (176,156,120) and lower roughness to about 0.2 for broader highlights.
2. **Frames:** remove the speckle noise. Use a deeper brown-gold base, about sRGB (96,70,38), metallic, roughness
   0.3.
3. **Lamp base:** use a bronze tint instead of near-black iron.
4. **Lighting:** optionally cool the window/portal contribution slightly and strengthen the chandelier warmth.

Each is a one-line change in `build/apply_materials.py`. Then rerun apply → render → compare → review into new
`_v10` paths.
