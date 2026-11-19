# Setup and verification status

## AHA-backed implementation — 2026-11-15

The forward path is now [aha/README.md](aha/README.md); the V1/V2/V3 notes below
describe the retained legacy implementation.

- Follow-up live Codex final-gate check **passed**: the schema-constrained response
  supplied concrete observations for all 72 images, covered object-focus/aspect
  requirements, and correctly rejected the floor-only fixture as an incomplete
  room. Native AHA validation and review recording succeeded. Evidence:
  `recon/aha_review_audit_002/audit-report.json`; elapsed 144.6 seconds, actual CLI
  charge unknown with $0.25 reserved. This used the locally installed authenticated
  Codex CLI with remote `gpt-6-astra` inference, not a local GPU language model.
  **82 Agen3D tests pass**. Original `aha-002` remains unchanged and can resume
  preparation review using its existing hash-bound approval and ledger. These
  checks establish integration/negative-control behavior, not full-room quality.
- Approved live negative-control audit used two Qwen calls and one Codex call.
  Known Qwen charge: **$0.00089145**; Codex charge unknown with **$0.25** reserved.
  Evidence/costs: `recon/aha_review_audit_001/followup-report.json`. It exposed a
  missing local-overlay legend/object context and an invalid final response:
  Codex assessed the existing floor alone and omitted observations for 34 images.
  Native validation correctly rejected it. Added explicit candidate metadata and
  reference-background legend; the second Qwen call no longer asserted the ceiling
  defect, but its prose remains imprecise and is not a critic-quality guarantee.
- The final transport now requests schema-constrained per-image/per-object/aspect
  observations and a whole-room completeness decision, preserving raw responses.
  Invalid final reviews produce `blocked_review` rather than geometry takeover.
  Offline tests cover the CLI wrapper with a local fake executable, native output
  normalization and rejection of missing/stale evidence. The separately approved
  live Codex follow-up subsequently passed, as recorded above.
- Expanded integration audit after the `aha-002` image-ID mismatch: exact unique
  filename aliases now map to supplied IDs, all coverage/revision failures are
  validated within the bounded review retry, and unchanged latest successful
  reference responses can be reused without another charge. Saved `aha-002`
  response replay verifies all 25 delivered images and the current revision:
  `recon/aha_runtime_audit_001/saved-review-replay.json`.
- Fixed bridge-failure stage reporting, final-repair task persistence and separate
  Blender build/verify logs; planner receives current budget/reservation context.
  **73 Agen3D tests and 53 upstream layout/object/review tests pass**. Real offline
  candidate construction/reopen and native rendering/object evidence passed with
  72 images (3 object-focus images): `recon/aha_runtime_audit_001/audit-report.json`.
  The original room job and its ledger were not modified by this audit. The later
  authorized live audit and its discovered issues are recorded above.
- `aha-002` completed preparation but its reference reviewer returned `pass` with
  nonempty `defects`. Added a reference-specific `limitations` field, explicit
  blocking-defect instructions and one charged schema-correction retry, retaining
  the no-unresolved-defects invariant. `--resume-preparation` now reuses completed,
  hash-verified preparation after a blocked review, keeps the original ledger and
  budget, and archives previous reports. Existing `aha-002` inputs/config were
  verified for resume; its contradictory response was not treated as acceptance.
- FloorPlan209 `aha-001` exposed a subprocess import-path bug after successful
  32-frame Pi3X inference: AHA's semantic worker could not import uninstalled
  SAM3 source. The preparation launcher now supplies absolute pinned source paths,
  and raw-job preflight probes that exact subprocess environment. Regression suite:
  **56 passed**. Actual recovery verification reused the saved Pi3X bundle and
  completed all 32 SAM3 frames, structural alignment, meshing and source overlays.
  Its compute reservation/timing is retained separately in
  `recon/ai2thor_floorplan209/aha-preparation-recovery-001/report.json`; original
  `aha-001` costs/artifacts are preserved. No hosted review/construction was run.
  The supplied config now targets fresh output `aha-002` for the next complete job.
- Integrated job entry: `configs/multiagent/aha.floorplan209.json` accepts the
  dataset directory and runs native reference preparation, strong reference
  review, empty seed/inspection setup, and construction in one job. Preparation,
  review, local Blender/Hunyuan execution and failures share the job ledger;
  `host_hourly_usd` prices local elapsed time when supplied, otherwise local cost
  remains unknown with its reservation retained. Resolved construction inputs
  are saved under the job; failed reference review stops before construction.
- New accounting/handoff tests bring the Agen3D suite to **55 passed**. Full
  raw-video-to-room execution is not yet benchmarked. Preparation does not infer
  a complete editable room or satisfy the independent final layout/delivery gate.
  Real synthetic-reference smoke passed Open3D meshing, isolated seed creation,
  scene reopen, and AHA native technical input validation:
  `recon/aha_preparation_smoke_001/report.json`. The FloorPlan209 raw-input config
  passes required host/CUDA/credential preflight:
  `recon/aha_floorplan209_readiness.json`. No full paid room job was launched.
- New construction runtime: typed task DAG, isolated Blender programs, native
  RoomKit imports, GLB conversion, object-focused Qwen critique, strong takeover,
  budget ledger, and native AHA final layout-review bridge.
- Agen3D suite: **46 passed**. Relevant upstream AHA review/layout/object tests:
  **53 passed**. These are contract tests, not an end-to-end reconstruction score.
- Real Blender smoke: program construction/reopen, registered collection import,
  generated-GLB conversion and invalid-scope rejection passed. Evidence:
  `recon/aha_blender_smoke_003/smoke.json`.
- Qwen3-VL-30B-A3B/DeepInfra and Codex GPT-6-astra passed one image+JSON call each.
  Evidence: `recon/aha_model_smoke_001/report.json`. Known Qwen charge:
  $0.00002565; Codex charge unknown, with $0.25 reserved. This does not measure
  construction skill or judge accuracy.
- Host RTX 5090, Bubblewrap, Blender, AHA imports, and Pi3X/SAM3 imports/CUDA tensor
  operations pass. Pi3X and SAM3 checkpoints pass full hash verification.
  Host execution is required; the outer session sandbox blocks GPU/network namespaces.
- **Environment/checkpoint repair completed:** `.venvs/hunyuan` now has an
  isolated Python 3.11 shape runtime (PyTorch 2.7.1+cu128), captured in
  `runtime-locks/hunyuan.txt`. The pinned Hunyuan 2.1 checkpoint passes full hashes.
  Offline GPU inference at 10 steps / resolution 128 exported and reloaded a GLB
  with 46,988 vertices / 93,976 faces: 20.5 seconds, 8.22 GB peak allocated CUDA
  memory. Evidence: `recon/aha_hunyuan_env_smoke_001/report.json`. This is a
  reduced-resolution smoke, not a default-settings or quality benchmark.
- Core Python now includes Open3D 0.19.0 and OpenCV headless 4.10.0.84. All 27
  relevant upstream reference/geometry tests pass without skips; Agen3D's 46 tests
  still pass. Core/Hunyuan dependency checks and changed-script Ruff checks pass.
- Reused the existing `models/sam3/sam3.pt`, verified its pinned hash again, and
  ran fresh offline CUDA segmentation: four paper-bag detections. Evidence:
  `recon/aha_sam3_env_smoke_001/result.json`. SAM3 segmentation weights are not
  interchangeable with SAM 3D Objects weights.
- Reproduce setup with `scripts/setup_multiagent.py --reference --runtime hunyuan`
  and `python -m agen3d.multiagent.models fetch hunyuan-shape` using core Python.
  Optional SAM 3D/HiSpatial environments/checkpoints remain absent; they are not
  required by the current design. Full readiness: `recon/aha_readiness.json`.
- No full room run was performed. The construction entry accepts prepared inputs
  or creates reference/camera/inspection inputs and an empty seed from a video
  inside the job. It returns a layout handoff; complete AHA delivery acceptance remains
  a separate workflow. Claude can supervise/build, but the native final gate
  remains Codex until its provider-specific receipt contract is generalized.

Verified 2026-11-15. These are environment and smoke checks, not a full reconstruction result.

## Ready for the default V1/V2/V3 pipeline

- Core `.venv`: dependency compatibility check passes; 36 offline tests and Ruff pass.
- Self-contained Python 3.11 environments installed at `.venvs/pi3x-clean` and
  `.venvs/sam3-clean`; all named job configs and `example.json` use them. They do
  not borrow packages from another checkout. Both dependency compatibility checks pass.
- PyTorch 2.7.1+cu128 / torchvision 0.22.1+cu128; CUDA matrix execution passes in
  both environments on the RTX 5090 (driver 595.99.02).
- Pi3X: actual two-frame GPU inference and geometry export pass.
- SAM3: actual batch-prompt GPU segmentation returns four paper-bag detections.
- Pi3X and SAM3 checkpoints pass full pinned hash verification.
- All five repositories in `multiagent.external.lock.json` match their pinned commits.
  AHa-3D also matches its separate lockfile.
- Blender 4.5.14 starts, imports RoomKit, and completes a small Cycles CPU render.
- The failed FloorPlan209 run already demonstrated a live Codex planner call and
  OpenRouter worker calls. Final Codex judge execution has not been tested end to end.

Setup smoke artifacts and logs: `setup_logs/runtime-20261115/`.
The original failed job remains at `recon/ai2thor_floorplan209/v1/` with its costs.
Use a fresh output path such as `recon/ai2thor_floorplan209/v1/run-002` for a retry.

## Fixes made

Interpreter paths now preserve virtualenv symlinks. Resolving them to the base
Python bypassed `pyvenv.cfg` and caused the observed missing-NumPy error.
Setup resolves pinned packages across the two trusted PyPI/PyTorch indexes.
The SAM3 image-worker lock excludes the unused `decord` video backend, whose wheel
metadata triggered a platform compatibility error. Pipeline video decoding uses ffmpeg.
A worker import/CUDA preflight is available before paid calls:

```bash
cd /home/mj/dl_project/agen3d
.venv/bin/python scripts/check_multiagent_runtime.py configs/multiagent/ai2thor_floorplan209_v1.json --cuda
```

## Remaining limits

- Full 16-frame reconstruction, rendering/repair quality and final evaluation remain
  unverified. A two-frame smoke test is not a full-run memory-capacity test.
- Pi3X uses its slower PyTorch RoPE fallback; the optional compiled extension is absent.
- GPU execution requires a device-enabled terminal; the agent's ordinary sandbox
  cannot access the driver.
- Optional generation is not enabled by the legacy default pipeline. Hunyuan shape
  is now installed and smoke-tested for the AHA route (see above). SAM3D/HiSpatial
  remain unconfigured. The previous SAM3D checkpoint fetch was denied by Hugging
  Face access gating; `sam3.pt` cannot substitute for that model's weights.
- Initial installs/downloads and smoke tests are one-time setup work, separate from
  per-job timing. Setup wall time/cost was not fully metered; do not report it as zero.
- Existing output directories cannot be resumed or overwritten by the runner.
