# 42897538_a5-claude_s1 — precise static whitebox room

## Final result

- **Final scene:** `runs/A5-claude/42897538/1/scene.blend`. This is a byte-identical copy of
  `third_party/aha-3d/scenes/42897538_a5-claude_s1/blender/room_v18.blend` (sha256 `407f8ddb…`).
- **Stills:** `runs/A5-claude/42897538/1/stills/`. These are plan, front and side orthographic views, plus Workbench renders from the native source cameras of frames 123, 493 and 924. The same files are in `scenes/42897538_a5-claude_s1/renders/final_v18/`.
- **Inventory decisions:** `runs/A5-claude/42897538/1/inventory_decisions.json`. All 249 detector items are covered: 67 built, 49 duplicates, 132 parts, 1 skipped.
- **Acceptance:** `indoor acceptance check` reports **accepted / permitted** for candidate `7c983d9f9c9cc693e5d92a99e920d9188ca75c228d4a4b0dbd97f723eedb3809`. The checks are layout, preview, technical and final_review, and all passed.
  - Delivery `whitebox-v18` is registered and selected in `deliveries/42897538_a5-claude_s1/`.
  - Task claim `room42897538-a5-claude-s1` is released as completed. This step re-ran the full acceptance check.

## Stages run

1. **Read and claim.** Read AGENTS.md, docs/INDEX.md, coordination, acceptance, scene requests, layout inspection, the indoor-scene-workflow skill and the RoomKit skill.
   - Claimed `scenes/` and `deliveries/42897538_a5-claude_s1`.
   - Ran `tools/indoor intake` with the prefilled request. Output is in `runs/A5-claude/42897538/1/intake/` (ready_for_authoring).
   - Initialized the acceptance scope: reference reconstruction, stills, no people.
2. **Reference reuse.** I reused the existing Pi3X/SAM3/alignment bundle and ran no new Pi3X inference.
   - Measured the room from the TSDF mesh: plan density maps, wall elevations, height histograms and floor-colour segmentation for the rug.
   - The living room is L-shaped: x −3.76…2.30 m, y −2.27…1.79 m, with a notch for the kitchen. Ceiling height is 2.46 m.
   - Openings: a kitchen doorway, a hall doorway with transom, and three low-sill windows (glass 0.30–2.15 m).
3. **Authoring.** `scenes/42897538_a5-claude_s1/scripts/build_room.py` builds the room in code from simple primitives (boxes, cylinders, spheres and curve tubes). No image-to-3D generation was used.
   - The registered library assets did not match these objects (leather sofas, Panasonic TV and so on), so everything is authored.
   - There are 87 semantic roots, each with its own `instance_id`.
   - Every small item is a separate instance: 11 ornaments, 5 stacked plates, the bowl and snacks, tissue box, clock, telephone, yellow cable, the power strips and cable bundles, sockets and switches, the magazine, 4 cushions, 2 strands of fairy lights, and blinds.
   - The kitchen and hallway glimpses are built too: fridge, oven, three kitchen cabinet units, sink, wall cabinet, bin and kitchen rug; the far hall door, chest of drawers, rug, switch and spotlight.
4. **Layout inspection.** For every candidate I ran `layout_gate.prepare` through `scripts/prepare_layout.py`. This covers the render_blender inspection, export_model, object_outline and `agent_review --all-objects`.
   - It uses 11 native source frames (0–924), chosen so that every object has orthographic and source focus views.
   - It also uses a 10 fps camera cache, `camera/camera_source_10fps.npz`, which the acceptance layout check needs.
   - Between candidates I used `quick_check` contour overlays, and back-projected source pixels through the native cameras for targeted measurements.
5. **Final views, technical check and acceptance.**
   - `scripts/render_final_views.py` renders the plan, front, side and native-camera stills.
   - `scripts/tech_check.py` checks that IDs are unique, that every root has finite geometry, that every inventory `object_id` exists in the scene, and that the stills decode.
   - `scripts/acceptance_helpers.py` writes the final-view manifest and the check reports. The checks were then recorded, followed by the acceptance check, results register/select and claim release.

## Reviews and verdicts (structured Codex image reviews via `acceptance review-images`)

| Review | Candidate | Verdict | Main points |
| --- | --- | --- | --- |
| Layout v4b | room_v4 | rejected | Front-right blind height; sofa cushion lean; tissue box (false positive: the silhouette ignores occlusion); picture size; tree height |
| Layout v6 | room_v6 | rejected | Blinds hang lower than modelled; the windows are low-sill (confirmed from Pi3X wall points) |
| Layout v7 | room_v7 | rejected | Sofa cushions still too upright; **missed second chandelier over the loveseat**; tree height |
| Final v9 / v10 / v12 / v14 / v16 / v17 | room_v6–v17 | rejected | Shape and proportion detail: ottoman, lamp body, lamp-table width, radiator ribs, cable routing, rug edge near the ottoman, TV-to-lamp gap, radiator extent. One run had malformed aspect fields. |
| Layout v14 | room_v14 | "accepted" but invalid | It listed two no-action nonblocking findings, which the validator does not allow; the scene was revised afterwards |
| **Final v18** | **room_v18** | **accepted** | No findings |
| **Layout v18** | **room_v18** | **accepted** | 369 images and 87 object focus sets; no findings. Recorded as `layout/evidence_v18/review.json` |

All rejected judgments and the raw reviewer outputs are kept under `scenes/42897538_a5-claude_s1/layout/` and `.../acceptance/`.

## Problems and how they were handled

- **Layout-gate coverage.** The gate needs every object in at least one orthographic view and one source view. I increased the source frames from 5 to 11, thickened the thin wires and cables (radius up to 6–8 mm, which looks thicker than reality), and raised the orthographic resolution to 1600 px.
- **Camera cache missing from the layout spec.** I generated an interpolated cache with `aha3d.workflow.camera.interpolate`, rebound the spec and regenerated the evidence.
- **Detector errors.**
  - Oven and cabinet positions were swapped; fixed from the detector coordinates and door-handle positions.
  - The second chandelier (c362/c122) was first marked as a duplicate. The layout review caught this, and I added `chandelier-02`.
  - Mirror reflections at x≈2.37 (plate, bowl, table, ottoman, blind, picture, lights) were marked as duplicates of the real objects.
  - The TV-screen reflections were marked as parts of `tv-01`.
- **Measured corrections from back-projecting source pixels:**
  - Frame 123: the lamp shade is about 0.58 m wide at its flared bottom and meets the TV's left edge at x = −0.84 m. The 0.30 m lamp table and the power strip on the floor at the table front were placed from the same frame.
  - Frame 493: rug edge (y = −1.72 m, fringe at x = −2.29 m) and ottoman position.
  - Frame 924: the radiator's right end is confirmed; its left end was extended to x = −3.00 m.
- **Reviewer runs.** Each Codex review took 10–20 minutes. Several were stopped deliberately when their evidence went stale. One returned a slightly wrong candidate hash, so later requests ask the reviewer to copy it exactly.
- **Interim copy.** An interim `scene.blend` (room_v6) was moved to `interim_superseded/` before the final copy was placed.

## Skipped / limitations

- **Inventory item skipped:** c463, a blue shoe cover on the camera operator's foot. It is a person, not a room object.
- **Gallery not rebuilt.** `results build` fails on an unrelated project directory (`scenes/45261575_A0_s0`: "Invalid identifier"). I did not modify it. The gallery claim was released as cancelled, and no gallery files were written.
- **Scale and unseen geometry.** Pi3X scale is provisional (predicted metres, no physical calibration). Kitchen and hallway interiors, the backs of furniture and other unseen geometry are simple completions.
- **Small parts and materials.** Cables, fairy-light strands, ornaments and plate spacing are approximate at the source resolution. Materials are clay greys only, because the request was whitebox.
