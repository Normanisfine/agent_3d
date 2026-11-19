# Repository audit (read-only, 2026-11-15)

## Existing implementation

- `../../repos/aha-3d`, inspected revision `82f4b1110cfe4b55fff19df3b3790852ce07b171`: preserve in place. Its own coordination rules apply before any future writes/runs in that checkout.
- `src/aha3d/cli.py` and `tools/indoor`: intake, plan, prepare, execute, run, preview, placement checks and acceptance. `bash tools/indoor run SCENE --recipe RECIPE` runs an existing scene recipe, not arbitrary RGB reconstruction.
- `tools/layout_inspection/build_reference.py`: Pi3X/SAM3 reference geometry, alignment, meshes and source overlays. Documented new-video command uses `--video`, `--checkpoint`, `--upstream`, `--mesh-python`, `--num-frames 32`, `--out`.
- `src/aha3d/blender`, `tools/scene_variant.py`, `assets/`: editable Blender assembly and asset reuse. Reference geometry is not a completed authored room.
- Scene recipes consume saved Blender scenes. Runs retain snapshots, inputs, staged assembly, calibration, verification and rendering. Existing diagnostics are not hidden-GT instance reconstruction metrics.
- Pi3X alignment is a predicted world basis and predicted metric scale. Consume the final camera basis from `reference_build.json`; metric alignment to benchmark GT remains an explicit experiment prerequisite.
- `../../data/ai2thor/prepared/FloorPlan301/capture_v2`: withheld metadata, cameras, depth, instance labels and coverage. Its README points to RGB in `../../repos/aha-3d/references/ai2thor_bedroom/rgb_v2` (confirmed present). Export selected RGB into a new input directory. Existing evaluation targets include physics annotations and coverage, not a canonical oriented-box benchmark.
- No native CA-1M dataset archive was identified in the top-level data inventory. The dashboards do document an earlier reconstruction of CA-1M capture 42897538, so real-video work exists; that does not establish availability of native evaluation annotations. A normalized box adapter is provided; native export is a remaining integration step.
- Shared `repos/`, `data/`, `checkpoints/`, `envs/`, `tools/` stay in place. `smallobj-video2blender` is reserved for the user's friend and was neither read nor changed.

## Smallest integration

Keep all new code in `agen3d`. Record commands for the existing reference builder; import a reviewed canonical scene exported from AHa-3D into the new verifier/evaluator. Do not invent an automatic reconstruction API or treat primitive boxes as a reconstructed baseline. The harness supports bounded scene-state repair; applying accepted edits to an authored Blender scene requires the explicit export/apply bridge and render verification in a later integration step.

## Implementation layout

`src/agen3d/`: schemas, RGB preparation, AHa command adapter, geometry, offline evaluation, verification/repair, budget routing, CLI. `configs/`: small experiment configurations. `tests/`: offline synthetic behavioral tests. `docs/`: this audit, protocols and proposed experiments.

No files need migration yet. No baseline, model, Blender, simulator, installation or test execution was performed. The workspace `.git` contains no HEAD; a feature branch cannot be created here without initializing a repository. The upstream Git checkout is left alone.
