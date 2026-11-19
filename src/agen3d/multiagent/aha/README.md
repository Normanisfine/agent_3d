# AHA-backed construction

This is the automated AHA runtime for `design/designv2.md`; the agent-driven
comparison arm lives in `../aha_driven`. The old V1/V2/V3
entry points remain historical compatibility paths; this runtime does not call
those policies or maintain a parallel box-based scene.

## Original AHA and the two controllers

Upstream AHa-3D uses an AI agent for overall planning, tool choice, scene authoring
and review/repair, with Python executing prepared recipes and resumable stages.
It has no built-in parallel object reconstruction scheduler; its GPU batch worker
runs sequentially. Manual coordination of separate files is not automatic
object-level parallel reconstruction.

This automated Agen3D modification adds a dependency/capacity scheduler that
builds independent object branches concurrently, then merges, reviews and commits
serially. The separate [agent-driven controller](../aha_driven/README.md) shares
these execution primitives but lets the main agent explicitly launch a single
wave, merge branches, review candidates and commit them. It does not automatically
advance the graph or retry failures. Both keep one canonical-scene writer and
serial GPU generation; object-review calls can overlap within configured limits.

## Implemented

- Codex/Claude supervisor returns a validated, ordered construction plan.
- Qwen proposes real Blender programs or registered collection replacements.
- Worker code runs in Bubblewrap with no network, credentials or writable inputs
  outside its candidate directory. The local AHA helpers and asset files are read-only.
- A fresh Blender process reopens each candidate and validates target semantic IDs,
  bounds, actual changes and preserved cameras before AHA renders source-linked
  inspection and object-focus packets.
- Fresh Qwen tasks review each affected object's complete focus-image set.
  Critical tasks go directly to the strong builder; failed cheap repairs escalate.
- Hunyuan adapter creates masked crops, invokes the pinned local shape service,
  converts GLB geometry into a semantic Blender hierarchy, fits declared bounds,
  and uses the same validation/review route. GPU work has a nonblocking lease.
- The independent final review uses AHA's real Codex image-delivery contract and
  `layout_gate.record_review` / `require_current`. A rejected final review can
  trigger direct strong reconstruction and a second final review.
- Budget reservations protect takeover/final-review capacity. Unknown model or
  GPU charges remain unknown, not zero. Reports retain failures and partial scenes.

## Current boundary

**This implementation is not a validated end-to-end room reconstructor.** A job
can now start from a video or the FloorPlan209 dataset directory: preparation,
strong-agent reference review, empty Blender seed creation, and construction
share one job and ledger. Alternatively, supply an AHA-compatible reference
bundle, reviewed camera basis, inspection configuration and initial `.blend`.
The seed may be an empty scene, but nonempty objects should have AHA semantic roots. Required source image
paths must be actual source views, not rendered stand-ins. Pack existing textures
into the seed before isolated construction; linked external dependencies are not
silently granted filesystem access.

The runtime reports `layout_validated`, never complete delivery acceptance. Its
`handoff.json` identifies the exact scene and AHA evidence to consume in the
existing AHA task/delivery workflow. Full task acceptance, final video delivery,
arbitrary raw RGB-folder conversion are not yet implemented in this entry point.
The dataset-directory input uses its existing `reference/original_camera_rgb.mp4`;
it never reads simulator ground truth. Strong builders can reconstruct object/structural
geometry; camera changes require regenerating/reviewing upstream reference inputs.

Claude can supervise and construct. The final AHA gate remains Codex because the
upstream contract explicitly binds `codex_exec_images`. Qwen reviews are advisory
and are never disguised as Codex receipts. No upstream checkout was edited.

## Commands

From `agen3d/` (host terminal with GPU and Bubblewrap access):

Start FloorPlan209, including preparation, with:

```bash
HF_HOME=/home/mj/dl_project/cache/huggingface OMP_NUM_THREADS=8 PYTHONPATH=src \
  .venv/bin/python -m agen3d.multiagent.aha.cli run \
  configs/multiagent/aha.floorplan209.json --env-file .env --cuda
```

Edit that config's `output` to a new directory for each attempt. `preparation.input`
accepts a video, the dataset directory, or its `reference` directory. Do not mix
`preparation` with explicit `source_scene`, `layout_spec`, `source_images` or `masks`.
The job retains `reference/`, `bootstrap/`, `reference-review.json`, and a resolved
`construction-config.json`. A rejected or incomplete reference review stops with
`blocked_preparation`; it does not silently approve alignment. Automatic alignment
repair/retry is not implemented. Successful preparation proceeds to the existing
construction and independent final layout gate.

If preparation completed but the reference review blocked the job, rerun the same
command with `--resume-preparation`. Keep the original config and output unchanged.
This narrowly resumes at reference review after checking saved input hashes;
it does not resume failed construction or partial GPU preparation. The original
ledger/budget and cumulative active wall time are retained, with prior reports
archived in `history/`. Concurrent resumes are rejected by a job lock.
Reference reviews distinguish blocking `defects` from non-blocking `limitations`;
a pass still requires no blocking defects. Invalid schema responses get at most
one fresh, charged correction attempt with the same images. A valid rejection
is not retried automatically or converted into a pass. Limitations are carried
into construction context.

Review responses are bound to the exact candidate revision and every delivered
image. A filename is accepted as an alias only when it identifies one supplied
image unambiguously; missing, repeated, unknown or stale evidence is rejected.
The same bounded correction retry handles invalid coverage. Raw responses and
alias mappings remain auditable. On resume, the latest successful reference
response can be reused only if its revision and delivered image hashes still
match. Reuse retains its original cost and creates `reference-review-reuse.json`;
it never revives an older pass over a later invalid/rejected response.

`scripts/audit_aha_runtime.py` exercises real isolated Blender construction,
native rendering and object packets using a deliberately incomplete floor fixture,
without model calls. `scripts/audit_aha_reviews.py` is a separate live negative
control that sends those fixture images to configured Qwen/Codex providers and
records its own ledger. Neither audit claims room reconstruction quality.
The final Codex transport requests explicit observations for every supplied image,
each object's focus views, all review aspects, and whole-room completeness. It
retains raw and normalized responses in `review-transport/`; AHA's native validator
still decides whether the response satisfies its contract. An invalid final
response is `blocked_review`, not a geometric defect or an accepted room.

All stages use `ledger.sqlite`; `report.json` includes total job wall time,
stage timings and itemized charges, including failed preparation. Model API costs
use returned usage charges. Set `host_hourly_usd` to your chosen all-in local host
rate to price non-overlapping CPU/GPU execution intervals (preparation, meshing,
Blender and Hunyuan). This is elapsed host time, not measured GPU utilization.
By default, `codex_budget_exempt: true` and `local_compute_budget_exempt: true` exclude local Codex CLI calls and CPU/GPU stages from the dollar cap. Paid API calls (including OpenRouter) still consume the budget. Excluded calls retain usage, timing, and unknown actual costs in the ledger; exclusion does not assert zero cost. Judge/repair holdbacks are disabled for excluded Codex roles. Set either flag to `false` to restore budget enforcement for that category. The cost summary separates `paid_api`, `codex_cli`, and `local_compute`, with call counts, elapsed time, known/unknown cost, and available token counts per category. CPU/GPU time is combined host wall time, not separate utilization measurements. Historical ledger entries are not rewritten and remain `unclassified`.
No rate is guessed. CLI model charges can also remain unknown. Reservations are
budget guards, not invoices: timeout-based host reservations protect judge/repair
funds before execution, while actual elapsed charges replace them afterward.
One-time dependency installs/checkpoint downloads are not rerun or charged as
per-job inference. `stages.json` and the ledger survive preparation failures.
Native preparation produces structural/reference masks, not registered furniture
instance masks. Hunyuan construction is offered only when matching object masks
are registered in prepared-input mode; video jobs currently use code/catalog
construction. Automatic object-mask proposals are not implemented.

```bash
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha.cli doctor --cuda --full-hashes --report recon/aha_readiness.json
```

`doctor` probes executable Blender, isolated execution, AHA imports, model imports,
CUDA tensors, checkpoint completeness, and CLI binaries. It does **not** claim
model inference succeeded just because imports or checkpoint sizes pass.
`required_ready` without a config means base construction tools only. Optional
specialists are included in `all_tools_ready`.

Copy `configs/multiagent/aha.example.json` and fill the scene-specific paths. The
example deliberately references nonexistent input placeholders and cannot launch
an accidentally fabricated room. `layout_spec.json` uses the native AHA fields:
`reference`, `cameras`, `inputs`, `config`, `source_video`, with optional
`reference_manifest`, `inputs_metadata`, `camera_cache`, and `required_object_ids`.
Paths resolve relative to that specification; `source_scene` is supplied by the
committer for each candidate. The native gate checks matching hashes, frame
coverage, camera basis, source timing, and object evidence.

```bash
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha.cli doctor configs/multiagent/my_room.json --env-file .env --cuda
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha.cli run configs/multiagent/my_room.json --env-file .env
```

An editable install also exposes `agen3d-aha`. Existing `agen3d-reconstruct` remains
the legacy raw pipeline; it does not silently change behavior.

To invoke native AHA reference preparation from a video or compatible complete
bundle (requires the reference meshing runtime, Pi3X and SAM3):

```bash
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha.cli prepare-reference --video /absolute/source.mp4 --output /absolute/new-reference
```

This produces reference evidence, not an authored room. It checks Open3D before
launching inference, stages AHA's SAM3 checkpoint layout without copying weights,
and preserves the native 32/64-frame bundle contract. A legacy 16-frame Agen3D
cache is not automatically compatible.

Install the reference-meshing and isolated Hunyuan shape runtimes with:

```bash
.venv/bin/python scripts/setup_multiagent.py --reference --runtime hunyuan
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.models fetch hunyuan-shape
```

The Hunyuan package lock targets Python 3.11 and CUDA 12.8; it installs shape
inference dependencies, without the texture/demo/training stack. Use the pinned
source at `external/hunyuan3d-2.1` and `.venvs/hunyuan/bin/python`. Enable
`hunyuan` in a scene config after interpreter and checkpoint verification.
No implicit downloads occur during inference. Check actual inference separately:

```bash
HF_HOME="$PWD/.cache/huggingface" .venvs/hunyuan/bin/python scripts/smoke_hunyuan.py --output recon/hunyuan-smoke-NEW
```

This reduced-resolution smoke verifies offline model loading, GPU generation and
GLB round-trip, not object fidelity or full-room quality. SAM3 segmentation uses
the existing `models/sam3/sam3.pt`; it is not a SAM 3D Objects checkpoint. The
optional SAM 3D/HiSpatial routes are not required for this construction design.

## Verification

- `tests/test_aha_construction.py`: stale/scoped proposals, false completion,
  final-gate backend honesty, takeover routing, failed-repair rollback and accounting.
- `scripts/smoke_aha_blender.py --output NEW_DIRECTORY`: real isolated build,
  reopen, RoomKit import, generated-GLB conversion, and invalid-scope rejection.
- `scripts/smoke_aha_models.py --output NEW_DIRECTORY --env-file .env`: one small
  paid/CLI image+JSON request per Qwen/Codex transport; persists responses and charges.

A successful smoke test is not a fidelity benchmark. Hunyuan GLB conversion can
be tested with a fixture while actual Hunyuan generation remains unavailable.

## Dependency-aware parallel construction

The automated run now performs host calibration before planning, then records a
validated dependency graph in `dependency-plan.json`. Tasks declare
`parallel_safe`, `reads_object_ids` and `dependency_reason`; omitted parallel
safety is conservative/serial. The scheduler adds read/write conflict edges and
barriers around global scene edits. Ready, disjoint tasks build private scenes
concurrently. A serial committer imports only their semantic roots, reopens the
merged scene, regenerates evidence and requires fresh visual review before commit.
GPU generation stays serial. Failures fall back to bounded serial repair without
silently accepting stale candidates. The final native layout gate is unchanged.
Object reviews run concurrently with full image coverage; a shared semaphore
bounds all construction/review model calls. Concurrent host billing allocates
overlapping local intervals once rather than multiplying the host rate.

Optional configuration (defaults shown):

```json
"parallelism": {
  "enabled": true,
  "max_builds": 4,
  "max_model_calls": 4,
  "memory_per_build_gib": 4,
  "benchmark": true
}
```

CPU affinity, cgroup limits, free RAM and current load cap concurrency. The local
Blender calibration selects the smallest tested count within 90% of best observed
synthetic throughput. It is a recommendation, not a proven scene/API optimum.
Use `enabled: false` for serial execution; `benchmark: false` uses hardware
estimates only. A benchmark failure lowers build concurrency to one.

```bash
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha.cli capacity \
  configs/multiagent/aha.floorplan209.json --output recon/capacity-NEW
```

During a run, watch `progress.json`, `tasks.json`, and `stages.json` in the output
directory. The machine measurements are in `capacity/capacity.json`. Token savings
come from concise repair context, not from running more agents. Full call receipts
and failed attempts remain recorded. A reviewed partial scene can be supplied
through a new prepared-input config; this is a new continuation run, not general
in-place construction resume.

Offline merge/performance verification (no paid calls):

```bash
PYTHONPATH=src .venv/bin/python scripts/evaluate_aha_parallel.py \
  PATH/TO/construction-config.json --output recon/parallel-eval-NEW \
  --workers 4 --provider-delay 2
```

The evaluator uses real Blender but fixture proposals and stubbed visual review.
It tests concurrency and scene preservation, not room quality. Scheduler tests
also cover conflicts, parallel review coverage, atomic budgets and overlapping
host accounting.

The hosted transport now sends the declared schema as `response_format=json_schema`
with explicit input/output separation. This was added after the monitored
2026-11-16 pilot produced three 8,000-token Qwen input echoes under generic JSON
mode. A capped live schema probe passed before restarting. Build packets retain
object inventory and the selected reference-camera context, omitting duplicated
full-scene camera matrices. Actual provider outputs still pass local Pydantic
validation; schema routing does not establish geometric quality. The isolated
worker also supports `import roomkit` as an alias for its already-provided module.

The subsequent full construction attempt still failed: three schema-shaped Qwen
responses entered repeated-import loops and hit 8,000 tokens inside unfinished
code strings. `aha-parallel-20261116T013143Z/stopped.json` records the stop. A small
abstention-schema probe is insufficient to establish build readiness. Use a
representative executable proposal test before another full run; no room-quality
claim follows from the transport change.

## Qwen transport diagnosis (2026-11-16)

The model ID, Chat Completions endpoint, image data URLs and provider pin matched
OpenRouter/DeepInfra documentation. However, generic JSON validity, JSON Schema
validity, Python execution and visual correctness are distinct gates.

Controlled calls on the same failed cabinet-door task are archived under
`recon/qwen-diagnosis-20261116/`. DeepInfra forced-schema calls looped under both
legacy greedy decoding and Qwen's published Instruct evaluation sampling. Removing
forced decoding stopped that loop; one response then exposed a duplicate tagging
mistake. After clarifying the helper contract, a further response passed isolated
Blender checks but produced incorrect door placement/proportions. This is evidence
of both integration and geometry-quality problems, not proof that all Qwen tasks
fail or that a full room is ready to run.

`ModelSpec` now exposes `response_mode` (`schema`, `json`, `text`), `temperature`,
`top_p`, `top_k`, `presence_penalty`, `repetition_penalty` and `seed`. Defaults retain
schema mode and temperature 0 for compatibility; no historical run config is
rewritten. A diagnostic Qwen profile is:

```json
{
  "backend": "openrouter",
  "model": "qwen/qwen3-vl-30b-a3b-instruct",
  "provider": "DeepInfra",
  "response_mode": "text",
  "temperature": 0.7,
  "top_p": 0.8,
  "top_k": 20,
  "presence_penalty": 1.5,
  "repetition_penalty": 1.0,
  "seed": 3407
}
```

This is a transport/code-generation candidate, not a quality-validated full-room
configuration. Text mode retains the raw response and may remove exactly one
surrounding JSON Markdown fence; prose, broken JSON and schema violations are not
silently repaired. Local schema, scope, saved-scene and visual gates remain required.
Finish reasons and normalized token counters are recorded. A `length` finish is
explicitly rejected after recording its response and charge. Proposal requests
require a code field, and reviewer-only response instructions are no longer sent
to builders. Builder packets explain center/full-extent/Z-up conventions and the
actual `roomkit.box`/`tag_root` object contract. Both controllers share these changes.

References:
- [Qwen3-VL published generation settings](https://github.com/QwenLM/Qwen3-VL#evaluation-reproduction)
- [OpenRouter structured output semantics](https://openrouter.ai/docs/guides/features/structured-outputs)
- [OpenRouter model/provider capabilities](https://openrouter.ai/api/v1/models/qwen/qwen3-vl-30b-a3b-instruct/endpoints)
- [DeepInfra image request format](https://deepinfra.com/Qwen/Qwen3-VL-30B-A3B-Instruct/api)

The single-task diagnostic script `scripts/diagnose_qwen_api.py` never starts a
room job. `--bounded` is a separate programming control with explicit geometry,
not an image-fitting or reconstruction-quality evaluation.

The bounded multipart control also failed, including a repeat supplied with the
explicit one-root/multiple-children example: Qwen assigned the same instance ID to
multiple parts. This profile is therefore not validated as a Blender authoring
worker. The single technically valid unbounded door was a one-part box with Z
bounds 2.7–3.5 m above a floor at Z=0, so it cannot count as reconstruction success.
Seven small diagnostic model calls are retained, including both sampling settings,
both providers, text/schema modes and the bounded controls. No full room run was
restarted during this diagnosis, and no benchmark acceptance threshold was relaxed.

### Diagnostic output after failure

Every normal run termination now writes `output.json` and, when a usable scene
exists, `final_scene.blend`. This is an editable diagnostic candidate, **not an
acceptance receipt**. `report.json.scene` remains the canonical committed scene;
`report.json.output.scene` identifies the diagnostic export. Local and final
review gates are unchanged, and `delivery_accepted` remains false.

After fresh-process artifact validation, candidates receive a hash-bound
`artifact.json` receipt before evidence rendering. Export selects the latest
verified serial/merged candidate extending the current canonical revision, or
falls back to the canonical scene. It does not claim to rank visual quality,
include blocked tasks, or combine unmerged branches. Rejected and unreviewed
geometry may therefore be inspected without committing it. Invalid, modified,
and stale candidates are excluded. Preparation failure before any usable scene
produces an explicit unavailable receipt, not a fabricated scene.

The export is a byte copy: existing cameras are retained, but animation, asset
packing and final video delivery are not added. External resource paths remain
unchanged; the manifest also links the original candidate location. Hard process
termination cannot guarantee a final export. Historical candidates without the
new verification receipt are not automatically promoted to diagnostic output.
