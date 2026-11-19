# Agen3D

Geometry-grounded verification and cost-aware evaluation around the existing AHa-3D workflow. The current path is the [AHA-backed multiagent job](src/agen3d/multiagent/aha/README.md), which includes video reference preparation and construction in one budgeted run. The V1/V2/V3 pipeline is retained for historical compatibility. Full end-to-end reconstruction quality remains unverified.

Two AHA controllers are available for comparison: the [automated wrapper](src/agen3d/multiagent/aha/README.md)
schedules dependency-safe object branches and repairs in Python; the [agent-driven
workflow](src/agen3d/multiagent/aha_driven/README.md) lets the main AI agent select
build waves, merges, reviews and commits explicitly. Both support independent
object builds in parallel, with serial integration and GPU generation. Original
upstream AHA is agent-led overall, uses Python for prepared stages, and has no
built-in parallel object scheduler. Parallelism is an Agen3D extension, not a
proven speed or token advantage.


Start FloorPlan209 from a GPU-enabled host terminal:

```bash
cd /home/mj/dl_project/agen3d
HF_HOME=/home/mj/dl_project/cache/huggingface OMP_NUM_THREADS=8 PYTHONPATH=src \
  .venv/bin/python -m agen3d.multiagent.aha.cli run \
  configs/multiagent/aha.floorplan209.json --env-file .env --cuda
```

Configuration: [aha.floorplan209.json](configs/multiagent/aha.floorplan209.json).
Use a new `output` path for each job. Preparation, reference review, construction
and failed attempts share `ledger.sqlite` and `report.json`. Set `host_hourly_usd`
to price local execution; `null` retains unknown cost and budget reservations.

## Layout

```text
agen3d/
  recon/         Per-scene, per-method reconstructions and evaluations
  evan/          Preserved smallobj-video2blender code and saved results
  external/      Independent AHa-3D checkout (ignored)
  configs/        Small pilot plan and RGB selection example
  src/agen3d/    Typed state, adapters, geometry, evaluation, repair, routing, CLI
  tests/         Offline behavioral and raw-input tests
  docs/          Repository audit, protocol, proposed experiments
  paper/         Academic LaTeX draft and bibliography
  log/           Experiment history, cost records and decisions
  outputs/       Other generated artifacts (ignored)
```

Use `external/aha-3d` for the AHa-3D source checkout. Reuse `../data`, `../checkpoints`, `../envs` and `../tools` in place. No root files were migrated. `../smallobj-video2blender` belongs to the separate project and is untouched.

Start with [repo audit](docs/repo_audit.md), [implementation boundaries](docs/protocol.md), and [proposed experiments](docs/experiments.md). The [paper](paper/main.tex) distinguishes the proposed study from prior dashboard demonstrations.

## Legacy V1/V2/V3 jobs

Run commands from `/home/mj/dl_project/agen3d` in a terminal with GPU access.
The Python script calls the configured local Codex planner, OpenRouter workers,
Pi3X/SAM3, local Blender, and the configured final judge. All three raw-input configs use Codex `gpt-6-astra` at
`medium` reasoning effort for both planner and judge. No separate interactive agent
session or Blender window is needed.

Before the first job, follow the [environment setup instructions](src/agen3d/multiagent/README.md#environments-and-external-code)
and run the worker import/CUDA preflight. For the supplied FloorPlan209 V1 job:

```bash
cd /home/mj/dl_project/agen3d
.venv/bin/python -m agen3d.multiagent.pipeline.cli doctor configs/multiagent/ai2thor_floorplan209_v1.json --env-file .env
.venv/bin/python -m agen3d.multiagent.pipeline.cli run configs/multiagent/ai2thor_floorplan209_v1.json --env-file .env
```

Use `ai2thor_floorplan209_v2.json` or `ai2thor_floorplan209_v3.json` for the other variants. Their default destinations are
`recon/ai2thor_floorplan209/v1`, `v2`, and `v3`, respectively. Each destination must
not exist when starting a job; keep previous runs and choose a new path for retries.

To create a config for another room, copy `example.json` in the same directory,
then edit it. Name jobs `<dataset>_<scene>_v#.json`; use `generic` for user-captured
rooms without benchmark labels:

```bash
cp configs/multiagent/example.json configs/multiagent/generic_my_room_v1.json
```

Set `input` to a video or RGB folder, `scene_id` to your room name, and `output` to
`../../recon/generic_my_room/v1`. Set `dataset_kind` to `generic` and `evaluation_dataset`
to `null` for a room without benchmark labels. Keep the `models`, `services`,
`aha_repo`, and `blender` settings for this machine. Review `frames`,
`segmentation_views`, `repair_rounds`, and the USD budget. Set CPU/GPU hourly rates
if known; otherwise leave them `null`. Paths inside JSON are relative to the config
file, so an absolute input path is convenient. Do not put API keys in the config.

```bash
.venv/bin/python -m agen3d.multiagent.pipeline.cli doctor configs/multiagent/generic_my_room_v1.json --env-file .env
.venv/bin/python -m agen3d.multiagent.pipeline.cli run configs/multiagent/generic_my_room_v1.json --env-file .env
```

Supply `OPENROUTER_API_KEY` through the environment or the explicitly loaded `.env`.
Local Codex/Claude use their existing logins. This machine's Blender executable is
`../tools/blender/blender-4.5.14-linux-x64/blender` relative to the project root;
the supplied configs already reference it. Video input additionally needs `ffmpeg`
and `ffprobe`. `doctor` checks setup without making model calls; it does not verify
CUDA inference or provider authentication.

Preprocessing is included in measured runtime and compute accounting. Unknown costs
remain unknown. Inspect `report.json` for status, timing and costs, and `selected.json`
for the selected `.blend` path. The supplied FloorPlan209 configs also run separate
post-reconstruction evaluation. See the [multi-agent guide](src/agen3d/multiagent/README.md)
for config fields, input overrides, output contents and accounting limits.

## Current worker-model compromise

The initial Qwen3-VL-8B worker through Parasail repeatedly failed with upstream
HTTP 429 limits. With user approval, all V1/V2/V3 configs now use **Mistral Small 3.2
24B through OpenRouter/DeepInfra** for routine workers. V3 retains **Qwen3-VL-30B-A3B
through DeepInfra** as its medium escalation tier. Planner and judge remain Codex
Astra at medium effort. The existing OpenRouter key covers both hosted models.

This change prioritizes availability and lower listed token prices; it is not a
proven reconstruction-quality improvement. Mistral's standard DeepInfra prices checked
2026-11-15 are $0.075 input / $0.20 output per million tokens, versus the old Qwen8B
route's $0.25 / $0.75. Actual room costs depend on image tokenization and call counts.
Mistral completed the current visual inventory, but no matched quality comparison
has been run. DeepInfra is pinned; there is no automatic cross-provider fallback or
guarantee against future rate limits.

Treat current runs as a Mistral-worker baseline. Keep that worker fixed across the
three variants, and evaluate the original Qwen baseline separately. V3's escalation
also changes model family, which must be considered when attributing improvements
to routing. See the [full comparison and sources](src/agen3d/multiagent/README.md#worker-model-compromise-mistral-instead-of-qwen8b).

## External AHa-3D setup

From this directory, run:

```bash
python scripts/setup_external.py
```

The setup clones the upstream repository at the exact commit in
`external.lock.json`. The independent checkout under `external/` is ignored,
not vendored or a submodule. An existing checkout must match the pin; the setup
refuses to overwrite local changes or switch an existing revision. To upgrade,
review the new revision, update the lock, and explicitly update your checkout.

`agen3d plan-reference` defaults to this checkout regardless of the working
directory when using an editable install; `--repo` overrides it. The setup only
fetches source: AHa dependencies, checkpoints and local data require separate
setup. The RGB selection example still uses data in the original shared
checkout because those locally generated frames are not part of a Git clone.

## How the code fits together

1. `datasets.py` exports selected RGB frames and a hashed manifest. Its reader exposes only those frames.
2. `aha.py` constructs a command for the existing AHa geometry builder. It does not launch work or invent an authored reconstruction.
3. `schema.py` defines the shared scene, box, observation and issue formats. `io.py` loads validated artifacts and refuses to overwrite existing output files.
4. `verification.py` finds duplicate tracks and declared support gaps, then offers bounded scene-state repairs with rollback.
5. `routing.py` tracks supplied costs and chooses deterministic, open-model, strong-model or stop decisions within a budget.
6. `label_export.py` and `evaluation.py` run separately with privileged annotations. `geometry.py` supplies oriented-box intersections and corner conversion.
7. `cli.py` exposes the explicit preparation, planning, verification, repair and evaluation commands.

The [log guide](log/README.md) explains how to record planned/failed/completed experiments and costs. Keep unknown measurements as null. The [journal](log/journal.md) records project decisions; reconstruction artifacts belong in `recon/<scene>/<version>/`.

## Lower-level geometry and evaluation commands

These commands expose individual harness steps; use the raw-input runner above for a reconstruction job. Do not modify shared model environments.

```bash
cd agen3d
python -m pip install -e '.[dev]'
agen3d plan configs/pilot.json
pytest
agen3d prepare-rgb configs/ai2thor_selection.example.json outputs/inputs/example
agen3d verify path/to/scene_state.json outputs/issues.json
agen3d repair path/to/scene_state.json outputs/repair-001
agen3d export-labels ai2thor outputs/inputs/example/manifest.json \
  ../data/ai2thor/prepared/FloorPlan301/capture_v2 \
  outputs/evaluator/labels.json --alignment-id thor-world-v1
agen3d evaluate path/to/aligned_scene_state.json outputs/evaluator/labels.json \
  outputs/inputs/example/manifest.json outputs/evaluator/metrics.json
```

The two-frame input example only illustrates export; it is not the pilot selection. `plan-reference --help` describes construction of an existing AHa geometry command, without executing it. Scene state must be explicitly exported and aligned; copying an alignment label does not perform alignment. Evaluation files must not be mounted into future reconstruction agents.

The multi-agent pipeline now includes Blender assembly and source-render checks. Full end-to-end validation and automatic CA-1M evaluation remain outstanding. Generated-asset services and robotics are not part of the default raw-input job.

## Evan's preserved experiments

`evan/` contains a copy of `smallobj-video2blender` at commit
`0605b5ff7cb02d0d0d889f2ee6a8f36f02c49be1`, including all locally available
results. No experiments were rerun. The original project remains in place;
its Git metadata is not nested in this project.

- [Test results](evan/results/test_opus/README.md) and [development results](evan/results/dev_opus/README.md)
- [A1 material showcase](evan/results/showcase/47331262_A1/README.md)
- [A2 material showcase](evan/results/showcase/42897538_A2/README.md)
- [Original project guide](evan/README.md)

`evan/migration_manifest.json` records the source revision and a SHA-256 checksum
for every copied file. Code, prompts, configuration, reports, metrics and saved
images were preserved unchanged. The scripts retain the original machine's
runtime paths; this is an archive of existing experiments, not a configured
execution environment.

The source copy does **not** contain the raw `runs/`, input/perception data,
generated meshes, or original `.blend` reconstructions referenced by the reports.
Those artifacts would need to be obtained from Evan's original machine or backup
to inspect or edit the 3D scenes without rerunning. Saved renders and reported
results are available here under `evan/results/`.

[Preserved reconstructions and evaluations](recon/README.md) include FloorPlan209 / aha3d_ori with Evan metrics.

# agent_3d
