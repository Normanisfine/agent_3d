# Agen3D multi-agent runtime

**Forward implementation:** use the [automated AHA runtime](aha/README.md) or the
[agent-driven AHA workflow](aha_driven/README.md)
and `python -m agen3d.multiagent.aha.cli`. It delegates to Qwen, supports strong
construction takeover, and uses native AHA evidence/gates. The V1/V2/V3 pipeline
below is retained for historical compatibility, not the current development plan.

This package implements the shared runtime for three reconstruction-agent designs. **All three raw-input configs use local Codex `gpt-6-astra` with `medium` reasoning effort for both planner and judge. OpenRouter routes routine worker decisions to Mistral Small 3.2 24B through DeepInfra; V3 retains Qwen3-VL-30B-A3B as its medium tier.** Both strong roles can instead use either installed CLI by changing their `backend`. Existing CLI authentication is reused; no separate strong-model API key is required by these adapters.

The shared raw-input pipeline accepts a room video or RGB folder for all three variants.
It performs frame preparation, Pi3X geometry, SAM3 segmentation, tracked-object fitting,
RoomKit asset selection, Blender rendering, bounded repair, and final review. This is a
pilot implementation; full end-to-end reconstruction quality has not been validated.
The older `agen3d-multi run` command still reviews exported scenes.

## Start a raw-input V1 pilot

From `/home/mj/dl_project/agen3d`:

```bash
.venv/bin/python -m agen3d.multiagent.pipeline.cli doctor configs/multiagent/ai2thor_floorplan209_v1.json --env-file .env
.venv/bin/python -m agen3d.multiagent.pipeline.cli run configs/multiagent/ai2thor_floorplan209_v1.json --env-file .env
```

The script orchestrates local Codex planning, OpenRouter Mistral workers through DeepInfra, local Pi3X/SAM3,
Blender, and a separate Codex final-review call (Astra, medium effort). No separate interactive agent session is needed.
Run in a terminal with GPU access. The default input is FloorPlan209's RGB reference
folder; benchmark labels are opened by a separate evaluator after model work finishes.
V2/V3 use `ai2thor_floorplan209_v2.json`/`ai2thor_floorplan209_v3.json`. V2 still needs distinct worker aliases to test
specialization; its supplied aliases otherwise match V1.

For your own video or RGB folder, add `--input /path/to/room.mp4` (or a folder) and
`--output /path/to/new-run`. Input overrides disable the example's ground-truth evaluation.
Each run requires a fresh output directory. Paths in configs are relative to the config;
CLI path overrides are relative to the working directory. `.env` is loaded only when
explicitly passed, without printing secrets or overriding exported variables.

The timer starts before input decoding, selection, copying and hashing. `report.json`
includes stage timing, model usage, GPU/render charges, and remaining allocated host
time (including preprocessing, geometry work, orchestration waits and evaluation).
Set `gpu_hourly_usd` and `cpu_hourly_usd` for compute estimates; unset rates remain
unknown. Unknown provider/subscription charges also keep the total cost unknown.
The call reservation budget excludes the additional retrospective host cost. Existing
checkpoints, installed environments and the asset library are reused setup resources;
the run does not include their original download/creation cost. Inference is fresh.
Outputs include `scene.final.json`, `selected.json` pointing to the selected `.blend`,
comparison images, `timing.json`, and optional `evaluation/metrics.json`.

## Create a job config

Copy `example.json` into the same config directory so its relative resource
paths keep working:

```bash
cp configs/multiagent/example.json configs/multiagent/generic_my_room_v1.json
```

Edit these fields in the copied JSON:

- `variant`: `v1`, `v2`, or `v3`. The example uses V1; copy the named V3 job for its medium model alias.
- `input`: an absolute path or config-relative path to a video, a folder of PNG/JPG/JPEG
  images, or an RGB reference folder with `manifest.json`. Plain image folders are
  sorted by filename; use zero-padded names for chronological order. Their timestamps
  are synthetic ordinals. At least `frames` distinct source frames are required.
- `scene_id`: the room's stable name. For an ordinary room, use `dataset_kind: "generic"`
  and `evaluation_dataset: null`. Do not retain FloorPlan209 labels for another room.
  Automatic benchmark evaluation currently supports AI2-THOR only; matching capture
  frame IDs and labels are required.
- `output`: use `../../recon/<scene>/<version>` from `configs/multiagent/`, for example
  `../../recon/generic_my_room/v1`. The supplied configs write to
  `recon/ai2thor_floorplan209/v1`, `v2`, and `v3`. The destination must not already exist.
  Preserve old runs; use a new scene/version run path such as `v1/run-002` for a retry.
- `frames`: 4–32 selected frames (default 16); `segmentation_views`: 2–16 and no more
  than `frames` (default 8); `repair_rounds`: 0–3 (default 1).
- `max_categories` and `max_objects`: optional bounds, defaulting to 32 and 100.
- `budget_usd` and `judge_reserve_usd`: model/service reservation budget and judge
  holdback. Per-call reservations are in `models` and `services`; unknown charges
  retain their reservations. The defaults are pilot limits, not measured total prices.
- `gpu_hourly_usd` and `cpu_hourly_usd`: configured compute rates, or `null` when unknown.
  Additional host costs are retrospective and outside the call reservation ceiling.
- `models`: keep `planner`, `judge`, and `cheap`; V3's template also supplies `medium`.
  V2 can add role-specific aliases such as `geometry` or `asset`. For a Codex role,
  set `backend: "codex"`, `model: "gpt-6-astra"`, and `reasoning_effort: "medium"`
  to pin the model and effort. Omitted model/effort settings use CLI defaults.
  `reasoning_effort` is currently supported only for Codex.
- `services`: keep both `pi3x` and `sam3`, with their interpreter, source repository,
  pinned checkpoint reference, reservation and optional timeout settings.
- `aha_repo` and `blender`: the asset-library checkout and local Blender executable.
  The supplied Blender path resolves to
  `/home/mj/dl_project/tools/blender/blender-4.5.14-linux-x64/blender`.
  Blender runs in background mode through its Python API and renders on CPU.

JSON paths resolve relative to the config file; absolute paths also work. Copying a
config elsewhere requires updating relative paths. Keep credentials out of JSON;
pass `--env-file .env` or export `OPENROUTER_API_KEY` before launching.

Validate and start the copied job:

```bash
.venv/bin/python -m agen3d.multiagent.pipeline.cli doctor configs/multiagent/generic_my_room_v1.json --env-file .env
.venv/bin/python -m agen3d.multiagent.pipeline.cli run configs/multiagent/generic_my_room_v1.json --env-file .env
```

For a one-off input override without a copied config:

```bash
.venv/bin/python -m agen3d.multiagent.pipeline.cli run configs/multiagent/ai2thor_floorplan209_v1.json \
  --env-file .env --input /path/to/room.mp4 --output recon/generic_my_room/v1
```

Use a folder instead of the video path for RGB images. CLI override paths resolve
relative to the working directory. `--input` automatically sets a generic scene ID
from the input filename/folder name and disables benchmark evaluation, even if the
config specified it. To retain matching benchmark evaluation, edit the config's
input and evaluator fields instead.

## Job artifacts and status

All artifacts stay under the configured reconstruction directory:

- `pipeline.config.json`: resolved run configuration.
- `inputs/`: selected RGBs, hashes, manifest and overview images.
- `agents/`: provider decisions, events and the reservation ledger.
- `jobs/`: specialist requests, logs, predicted geometry and masks.
- `reconstruction/` and `renders/`: scene assembly, assets, source comparisons and repairs.
- `scene.final.json` and `selected.json`: final scene state and selected `.blend` path.
- `timing.json` and `report.json`: stage times, usage, costs, status and errors.
- `evaluation/metrics.json`: post-run benchmark results when matching labels are configured.

`completed_with_unresolved` means the final judge did not pass the reconstruction;
`failed` includes an error and any stage timing already recorded. A successful process
exit alone is not a quality claim. Existing directories are rejected, including failed
runs; choose a new output path instead of deleting evidence. There is no resume support.

## Worker-model compromise: Mistral instead of Qwen8B

Decision recorded 2026-11-15. The initial cheap worker was
`qwen/qwen3-vl-8b-instruct` through OpenRouter/Parasail. Repeated requests failed
with HTTP 429 and `limit_source=upstream_provider_shared_pool`. Minimal text-only
requests with default routing and with fallbacks enabled also failed. This was
provider capacity, not evidence that the user's dollar budget was exhausted.

The user approved the following replacement in all three job configs and `example.json`:

- `cheap`: `mistralai/mistral-small-3.2-24b-instruct`, provider `DeepInfra`.
- V3 `medium`: `qwen/qwen3-vl-30b-a3b-instruct`, provider `DeepInfra`.
- Planner and judge remain local Codex `gpt-6-astra`, reasoning effort `medium`.

Both hosted models use the existing OpenRouter API key and billing. The configuration
pins DeepInfra using the adapter's provider allowlist; automatic cross-provider
fallback is disabled. This avoids the observed Parasail route, but does not guarantee
freedom from future limits or outages.

### Comparison relevant to this pipeline

All three models accept images and support JSON responses on the inspected endpoints.
Mistral is a 24B general-purpose multimodal instruction model. Qwen8B is the smaller
vision-language model originally planned for routine workers. Qwen30B-A3B is the
mixture-of-experts vision-language alternative retained for escalation. Model size
alone does not establish accuracy, API cost, or reconstruction quality.

Standard endpoint list prices checked on 2026-11-15, USD per million input/output
tokens, excluding cache discounts and alternative service tiers:

- Mistral Small 3.2 / DeepInfra: **$0.075 / $0.20**, 128K context.
- Qwen3-VL-8B / Parasail: **$0.25 / $0.75**, 262,144-token context.
- Qwen3-VL-30B-A3B / DeepInfra: **$0.15 / $0.60**, 262,144-token context.

At equal token counts, Mistral's listed rates are 70% lower for input and about 73%
lower for output than the former Qwen8B route. This does not predict the same savings
per room: image tokenization, response length, retries, cache hits and tool-call counts
differ. Use provider-reported run charges for actual comparisons.

Both replacement endpoints passed small text-only JSON smoke tests. Mistral also
completed the live FloorPlan209 visual inventory and recorded 17 categories. That
is execution evidence, not a verified inventory-recall score. We have no matched
Mistral-versus-Qwen room reconstruction evaluation and do not claim that either is
more accurate at small-object recovery, spatial judgments or repair decisions.

### Experimental interpretation

This is an availability/cost compromise, not a measured accuracy improvement.
The current experiment is a **Mistral-based worker baseline**, not the original
Qwen8B baseline. Keep the cheap worker/provider fixed across V1/V2/V3 when comparing
routing. V3 now changes model family when it escalates to Qwen30B; any benefit may
reflect that model change as well as routing. Calling it the medium tier does not
prove it is stronger on this task. V2 still needs explicit specialist aliases for a
meaningful specialist comparison.

To measure the compromise, run a separate matched-input ablation with identical
frames, prompts, budgets, services and evaluation, changing only the worker/model
provider under test. Keep failed historical runs and their cost records separate.
Each run's `pipeline.config.json` records the configuration actually used; do not
relabel earlier Qwen runs as Mistral runs.

Sources: [Mistral model card](https://huggingface.co/mistralai/Mistral-Small-3.2-24B-Instruct-2506),
[Qwen30B model card](https://huggingface.co/Qwen/Qwen3-VL-30B-A3B-Instruct),
[Mistral endpoints](https://openrouter.ai/api/v1/models/mistralai/mistral-small-3.2-24b-instruct/endpoints),
[Qwen8B endpoints](https://openrouter.ai/api/v1/models/qwen/qwen3-vl-8b-instruct/endpoints),
[Qwen30B endpoints](https://openrouter.ai/api/v1/models/qwen/qwen3-vl-30b-a3b-instruct/endpoints).
Prices and availability can change.

## Code layout

```text
multiagent/
  v1_shared/            One cheap endpoint; separate role contexts
  v2_specialists/       Role-specific aliases and optional spatial specialist
  v3_adaptive/          Cheap -> medium -> local strong leader on unresolved tasks
  pipeline/            Shared raw-input CLI, preparation, reconstruction and accounting
  contracts.py         Strict config, task, decision, evidence and service schemas
  protocol.py          Tool discovery, role permissions and generated agent prompts
  tools.py             Actual tools, evidence checks, candidate artifacts, GPU leases
  providers.py         OpenRouter/OpenAI-compatible HTTP; Codex and Claude CLI adapters
  engine.py            Task DAG, bounded turns, escalation and final judge
  store.py             SQLite reservations, charge reconciliation and event history
  models.py            Central checkpoint lockfile, import, fetch, verify and resolver
  specialist_worker.py Isolated Pi3X/SAM 3/SAM 3D/Hunyuan/HiSpatial subprocess entry
  process.py           Timeout handling that terminates subprocess descendants
  blender_bridge.py    Export boxes, apply selected transforms to a copy, render
  cli.py               run / doctor / protocol commands
```

The three design folders intentionally contain routing policies rather than duplicated engines. Tool schemas, evidence processing, numerical checks, accounting, and the final judge are shared, allowing controlled comparisons.

## Config layout

`configs/multiagent/` contains one template and named reconstruction jobs:

```text
example.json                         Generic V1 template; replace the input placeholder
ai2thor_floorplan209_v1.json          FloorPlan209 V1 job
ai2thor_floorplan209_v2.json          FloorPlan209 V2 job
ai2thor_floorplan209_v3.json          FloorPlan209 V3 job
```

Name new jobs `<dataset>_<scene>_v#.json`, using lowercase names with underscores.
Use `generic` for user-captured rooms without a benchmark dataset. Set `variant` to
match the filename. For a V3 job, copy the existing V3 job to retain its `medium`
model alias, then change the scene, input, output and evaluation settings.
The example is a template, not a ready-to-run job: its input path must be replaced.

Legacy exported-scene job configs have been removed. The mock runtime config lives
under `tests/fixtures/multiagent/offline.json` only for tests. Optional specialist
reference fragments live in [services.optional.example.json](services.optional.example.json);
these are not runnable raw-input jobs or enabled pipeline stages.

V3 currently escalates on abstention, malformed output, or turn exhaustion. It is a bounded initial policy, **not** a trained/calibrated confidence router. V1/V2 do not automatically send every failed worker to the strong model; the mandatory final judge sees unresolved work. Tool errors are returned to the agent and recorded; repeated invalid requests consume the turn budget.

## Tool protocol

See [TOOL_PROTOCOL.md](TOOL_PROTOCOL.md) for the wire contract. The executable registry in `tools.py` is authoritative. `protocol` prints the exact role-specific schemas, and `Registry.prompt()` inserts those schemas into every agent request.

Roles: `planner`, `inventory`, `geometry`, `asset`, `critic`, `judge`, `physics`. Workers return one strict JSON `Decision`, requesting named tools or finishing with `done`, `pass`, `repair`, or `abstain`. Only the planner may create worker tasks. Only the scheduler reserves spend and invokes specialists. Every tool argument is validated; a role cannot call another role's tool, and object-scoped tools enforce the task's declared object IDs.

No worker has a general shell tool in this protocol. Claude is launched with native tools/MCP disabled. Codex is launched read-only with shell, execution and multi-agent features disabled and user config ignored; it still uses the existing login and the CLI's default model unless `model` is explicitly configured. Both receive images as actual multimodal inputs, not text filenames. These CLI controls are **not a substitute for OS isolation**: for benchmark runs, withhold evaluator labels from the agent processes/filesystem mounts.

## Central checkpoint store

All checkpoints live under `agen3d/models/` by default. Set `AGEN3D_MODEL_ROOT` to relocate the entire store, for example onto a shared data volume. Every environment, agent launcher, and external model receives the same resolved checkpoint path. Service config uses `checkpoint: "model:sam3"`, not an arbitrary path or floating Hugging Face model name.

For resources shared across multiple projects, set `AGEN3D_RESOURCES=/path/to/resources.json` using [resources.example.json](resources.example.json) as the schema. It supplies `model_root`, `model_lock`, `repos`, and `runtimes`. Service configs can then use `repo: sam3` syntax **as the string `"repo:sam3"`**, and `"runtime:sam3"` for the interpreter. Registry paths may be absolute or relative to that registry file. `AGEN3D_MODEL_ROOT` and `AGEN3D_MODEL_LOCK` override registry defaults when explicitly set. This package consumes the shared registry; it does not relocate or modify another agent's resource layout.

```text
agen3d/
  models.lock.json          Versioned official repository revisions + per-file hashes/sizes
  models/                  Ignored large binaries; reproducible from the lockfile
    manifest.json          Local import/download provenance and verification results
    sam3/                  sam3.pt and config.json
    pi3x/                  model.safetensors and config.json
    sam3d/checkpoints/     SAM 3D Objects pipeline and weights, when access is available
    hunyuan-shape/          Pinned Hunyuan shape backend files, when fetched
    hispatial/             Pinned spatial model files, when fetched
    moge/                  Pinned depth model used by HiSpatial, when fetched
    hub/                   Shared auxiliary cache; not proof that an unlisted model is pinned
```

```bash
.venv/bin/agen3d-models list
.venv/bin/agen3d-models verify sam3
.venv/bin/agen3d-models path pi3x
.venv/bin/agen3d-models import sam3 --source /path/to/existing/checkpoint-directory
.venv/bin/agen3d-models fetch sam3d
```

Install the optional download client on a fresh machine with `.venv/bin/python -m pip install -e '.[models]'` (or `uv pip install --python .venv/bin/python -e '.[models]'` when pip is absent). Fetch uses your existing Hugging Face authentication; never put tokens into the registry. Gated access must be granted to that account separately.

Files are verified using SHA-256 for Hub LFS objects and the Git blob SHA-1 for regular repository files, including the Git blob header. Import copies bytes into the project store, preserving the originals. Existing destination files are not overwritten. `list` is a cheap size/presence check; `verify` and `path` perform full hash verification. The runtime verifies checkpoint contents before starting a specialist. It sets offline model flags, preventing silent downloads of moving upstream revisions during an experiment. Missing auxiliary dependencies therefore fail explicitly.

To upgrade a checkpoint, deliberately update its pinned revision and file metadata, import/fetch into a clean model root, then verify and rerun the corresponding smoke test. Do not label a manually replaced file as the old checkpoint revision. This first implementation does not expose an automatic lockfile-upgrade command.

## Environments and external code

`multiagent.external.lock.json` pins five external source repos independently of `models.lock.json`: SAM 3, Pi3, SAM 3D Objects, Hunyuan3D-2.1, and HiSpatial. The existing AHa checkout keeps its original separate lockfile. `setup_multiagent.py --sources` checks the pins and preserves existing checkouts rather than switching revisions under ongoing work.

The orchestrator uses `.venv` with Python 3.12 here. GPU workers use separate interpreters to avoid conflicting PyTorch/CUDA packages. Source paths and interpreter paths belong to operator config; models cannot choose arbitrary executables.

The initial `.venvs/sam3` and `.venvs/pi3x` environments borrowed packages from an
older checkout. Use the self-contained `.venvs/sam3-clean` and `.venvs/pi3x-clean`
environments for new jobs. Installation uses the captured version pins and the
trusted PyPI/PyTorch indexes; these are version locks, not wheel-hash locks.

From the project root, prepare all dependencies used by the default pipeline:

```bash
python3 scripts/setup_multiagent.py --core --sources
.venv/bin/python scripts/setup_multiagent.py --runtime pi3x
.venv/bin/python scripts/setup_multiagent.py --runtime sam3
.venv/bin/agen3d-models verify pi3x
.venv/bin/agen3d-models verify sam3
.venv/bin/python scripts/check_multiagent_runtime.py configs/multiagent/ai2thor_floorplan209_v1.json --cuda
```

The last command imports the actual worker modules and executes a small CUDA matrix
operation in each configured interpreter. Run it in a GPU-enabled terminal before
paid reconstruction calls. It does not call Codex/OpenRouter or perform model inference.
Source/checkpoint setup is separate from per-job preprocessing. Keep setup records
and any model smoke-test costs separate from reconstruction measurements.
The launcher preserves virtualenv Python symlinks: dereferencing them would bypass
`pyvenv.cfg` and lose the environment's dependencies.

SAM 3D's upstream environment uses several compiled CUDA extensions. Its default historical CUDA recipe must not be assumed to support a 5090 unchanged. Hunyuan and HiSpatial sources/launchers are present, but their separate environments/checkpoints are not activated by default. Their install guides remain in the pinned external repositories. SAM 3D weight access was denied by the active HF account during setup; SAM 3 segmentation weights are separate and available locally.

## Evidence and generated artifacts

Every input evidence entry has a stable ID, kind, relative path, SHA-256, and description. Paths must resolve inside `evidence_root`; symlink/path escapes and hash changes are rejected. Images are attached on demand through `get_evidence`, with a 12-image per-task cap. Give small objects useful crops, not only a downsampled room overview.

Generated masks/meshes/point-map archives are registered by the runtime under its own output directory, hashed, and assigned new IDs. A model cannot register an arbitrary host file. A task sees accumulated task results and open issues; raw numerical point maps stay out of text prompts.

Pi3X returns predicted reference coordinates and metric scale; it does not silently convert its world basis into the canonical scene's right-handed Z-up frame. Align/reference those outputs explicitly. SAM masks are predictions, not ground-truth inventory. HiSpatial uses a pinned local MoGe model; a Pi3X-to-HiSpatial adapter is not yet implemented.

Specialist results are reused on exact repeated requests within the run. The cache key includes input hashes, arguments, model lockfile, and service configuration. Cross-run response caching, provider KV-cache optimization, learned compression, and resumable task execution are not yet implemented. Durable events/charges survive failures; existing output directories are rejected to prevent accidental replay.

## Costs and execution limits

SQLite `BEGIN IMMEDIATE` protects budget reservations from races. Unknown charges retain their entire reservation; missing billing data is never interpreted as free. Actual reported overages are recorded even if larger than the reservation, so subsequent calls stop. Reserve the final judge's allocation before worker calls.

**The USD budget is a scheduler accounting ceiling, not a provider-enforced guarantee.** An operator-defined reservation may underestimate an actual request. Codex/Claude subscription usage is recorded separately from known API charges; their missing marginal cash cost remains unknown. Claude's reported equivalent USD is preserved as usage metadata, not treated as a subscription invoice. For hard spending limits, configure the provider/account cap as well.

All CLI/API calls have timeouts and bounded turns. Process timeouts kill subprocess descendants. GPU jobs use a nonblocking filesystem lease across runs sharing the same output parent; jobs from unrelated projects must still be coordinated externally. The historical scheduler described here is serial. The current AHA controllers
support dependency-safe parallel object branches and serial integration; see their
linked READMEs for orchestration and recovery behavior.

Each run writes `report.json`, `ledger.sqlite`, input/config snapshots, per-task decisions, model responses, proposed transforms, semantic issues, and specialist job logs. API keys are read from environment variables and are not serialized.

## Blender bridge

The standalone script runs inside Blender's Python; it does not require the orchestrator packages there:

```bash
blender -b source.blend -P src/agen3d/multiagent/blender_bridge.py -- \
  export --output scene.json --scene-id my_room
blender -b source.blend -P src/agen3d/multiagent/blender_bridge.py -- \
  apply --proposals selected_proposals.json --output candidate.blend
blender -b candidate.blend -P src/agen3d/multiagent/blender_bridge.py -- \
  render --output candidate.png --frame 1
```

Objects use custom `agen3d_id` or their existing Blender name as stable ID; optional properties are `agen3d_category` and `agen3d_support_id`. The bridge requires metre units and rejects stale boxes, reflection/shear, invalid rotations, excessive translations, and unsupported animated/constrained/modified edits. It never overwrites source files. Select one transform proposal per object. The raw-input pipeline uses its own assembly script and source-fit repair gate; this standalone bridge remains a lower-level exported-scene tool.

## Validation

```bash
.venv/bin/python -m pytest tests -q
.venv/bin/ruff check src/agen3d/multiagent tests/test_multiagent.py tests/test_model_registry.py
```

Tests cover role/object permission enforcement, evidence traversal/hash checks, concurrent reservations, unknown/overage accounting, task dependencies, bounded retries/escalation, mock runs, proposal isolation, and checkpoint import/tampering. GPU and CLI smoke-test status is recorded in [SETUP_STATUS.md](SETUP_STATUS.md). Successful smoke tests are integration checks, not scene reconstruction quality measurements.
