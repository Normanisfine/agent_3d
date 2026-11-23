# Agent-driven AHA comparison arm

The conversational agent controls task selection, delegation, repair and stopping.
Python exposes persistent operations using the shared `../aha` execution tools, including dependency-safe parallel branches.
This is a second controller, not a second reconstruction backbone. The automated
`agen3d.multiagent.aha.cli run` entry point remains unchanged.

## Scope

Implemented: durable sessions, compact worker packets with explicitly selected
source images/assets, optional paid/CLI worker proposals, externally authored
proposals, isolated build/reopen/evidence generation, local reviews, explicit
single-writer commits, agent-selected parallel build waves, scoped merges, and the
same independent native Codex final layout gate.
No automatic plan or repair loop runs between commands. A worker proposal alone
never changes the canonical scene. A passing local review permits a commit, not
final acceptance. Final layout validation still needs upstream AHA delivery work.

Initialization accepts the same config as the automated arm, with a mandatory
new output directory. Raw-video initialization reuses the existing preparation
and strong reference-review stage; prepared inputs permit controlled reuse.
Failed initialization requires a fresh output (retain its report/logs).
Successful sessions resume between commands, including after failed builds.
Abrupt process termination is not a transactional stage-resume mechanism: inspect
partial candidates/reservations before continuing. Never edit session state to
claim successful work. Inputs and current scene hashes are checked on reopen.

## Agent operating protocol

1. Initialize and inspect the saved reference, source images and inventory.
   Record camera/scale uncertainties and the requested scope in a small task plan.
2. Own planning and room-level reasoning in the main agent. Delegate bounded
   tasks to workers with only the packet, relevant evidence and output contract.
   Use a fresh-context subagent when available, or the `propose` command's worker.
   Do not send the full conversation. A packet is context, not proof of accuracy.
3. Group related geometry into one bounded task when appropriate. Inspect source
   evidence before choosing IDs, dimensions or placement. Include dependencies
   in `Work.depends_on`; only committed tasks satisfy them.
4. Build a candidate, inspect its exact object-focus evidence, and record a review.
   External reviews must cover all affected objects' focus images. If defective,
   create a revised proposal; no automatic retry or strong takeover occurs.
5. For independent objects, explicitly launch a `wave`. It builds private branches
   concurrently but does not review or commit them. `merge` imports one branch
   into the current scene; then review and commit that merged candidate. Merge
   and commit stay serial. Direct stale proposals are still rejected. An unrelated
   scene commit invalidates pending branches; rebuild a wave instead of relabeling
   old proposals. A new commit invalidates the previous final handoff.
6. Request `final-review` when the requested room is ready. Address failures and
   repeat explicitly. Report remaining defects and upstream delivery obligations.

Keep full logs and images on disk. Return concise paths, changed IDs, defects and
next actions to the supervisor. Use the cheap worker only for well-specified
work; ambiguous global structure can go directly to `--strong`. These are token-
economy strategies, not a demonstrated token or speed improvement.

## Commands

From `agen3d/`, use `.venv/bin/python` with `PYTHONPATH=src`. The global
`--env-file .env` option goes before the subcommand when model credentials are needed.

```bash
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_driven.cli init \
  configs/multiagent/aha.floorplan209.json --output recon/comparison/driven-001 --cuda
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_driven.cli status recon/comparison/driven-001
```

Create a task JSON (use actual scene-specific IDs):

```json
{"task_id":"desk","object_ids":["desk_main"],"instruction":"Build the observed desk using the reviewed dimensions and source views.","depends_on":[],"severity":"routine"}
```

Generate a scoped packet using source IDs from `session.json`'s config:

```bash
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_driven.cli packet SESSION \
  --task task.json --images SOURCE_ID --assets ASSET_ID
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_driven.cli --env-file .env propose SESSION \
  --packet PACKET_JSON
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_driven.cli build SESSION \
  --task task.json --proposal PROPOSAL_JSON
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_driven.cli --env-file .env review SESSION \
  --candidate CANDIDATE_ID
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_driven.cli commit SESSION --candidate CANDIDATE_ID
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_driven.cli --env-file .env final-review SESSION
```

`SESSION`, IDs and artifact paths above are placeholders. Omit `--assets` when
no catalog asset is needed. Instead of `propose`, an external worker may write a
Proposal matching the packet's schema. Instead of an API review, pass
`review --review REVIEW_JSON` after actually inspecting the images. Review fields
are `candidate_revision`, `verdict` (`pass`/`repair`), `severity`, `observations`,
`defects`, and every exact required `reviewed_images` ID. External review is
explicitly recorded, not presented as an API receipt. It never replaces the
independent final native gate.

## Orchestration and parallel construction

### Using Evan's A2 Boxer inventory

From the `agen3d` repository, initialize a driven session with the same prepared
FloorPlan209 inputs and saved detections as the AHA-auto inventory experiment.
Choose a fresh session directory for each run.

```bash
exp=/home/mj/dl_project/agen3d_exp/06_aha_auto_inventory
session="$exp/aha-driven-inventory"
driven() { PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_driven.cli "$@"; }
driven init "$exp/aha-auto/construction-config.json" \
  --inventory "$exp/storage/perception/FloorPlan209/inventory.json" --output "$session"
```

The supervisor opens `$session/boxer-inventory.json` for the detection boxes,
scores, frame references, crop paths and labeled contact sheets. Check them
against the source views. Assign each detection's exact ID to one task's
`object_ids`, or include it in a top-level `omissions` list with a reason, e.g.
`{"item_id":"b028","reason":"Second view of the television assigned to b027."}`.
Use additional object IDs for visible items missed by the detector. Record
support dependencies in the plan. For a controller comparison, let the driven
supervisor author this plan from the shared inputs. Reusing a prior controller's
plan gives a fixed-plan execution comparison.

```bash
driven inventory-plan "$session" --plan /path/to/supervisor-plan.json
driven packet "$session" --task /path/to/ready-task.json --images SOURCE_ID
# For parallel-safe ready tasks in the registered plan
driven --env-file .env wave "$session"
```

Both build paths attach box metadata and available individual crops for the
task's assigned IDs. A detection with no crop still supplies its box. This mode
uses the A2 primitive/asset construction setting with Hunyuan generation
disabled. Review and commit each candidate as usual. The session saves the
registered plan in `inventory-plan.json` and records per-ID progress in
`inventory-decisions.json`. Final review requires each detection to be present
in the committed scene under its assigned task or explicitly omitted.

### Scheduling waves

Original upstream AHA is agent-led at the workflow level: the agent chooses tools,
authors scenes and reviews/repairs results; Python executes prepared recipes and
resumable stages. It has **no built-in parallel object reconstruction scheduler**.
Its GPU batch worker is sequential. Manually coordinated work in separate files
is possible, but is not an automatic object-parallel pipeline.

Both Agen3D modifications support bounded object parallelism. The automated `aha`
controller schedules successive dependency-ready waves and repair attempts. In
`aha_driven`, the main agent writes a Plan and explicitly requests **one wave**.
The shared scheduler adds read/write conflicts and global barriers. Tasks must
have `parallel_safe: true`; use `reads_object_ids` for placement/support inputs
and `depends_on` for semantic prerequisites. Exclusive tasks use the serial
build/review/commit path. Only committed dependencies unlock downstream work.

Example Plan after the room basis has been established (replace instructions
with actual source-derived constraints):

```json
{
  "summary": "Two independent furniture objects",
  "tasks": [
    {"task_id": "desk", "object_ids": ["desk_main"], "instruction": "Build the reviewed desk.", "parallel_safe": true},
    {"task_id": "sofa", "object_ids": ["sofa_main"], "instruction": "Build the reviewed sofa.", "parallel_safe": true}
  ]
}
```

```bash
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_driven.cli capacity SESSION
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_driven.cli --env-file .env wave SESSION --plan plan.json
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_driven.cli merge SESSION --branch 1-desk
# Review and commit the returned candidate, then merge/review/commit 1-sofa.
```

`capacity` uses the automated arm's hardware/Blender calibration and config caps;
the first wave calibrates if necessary. Limits persist across session reopen.
Wave workers reuse the automated arm's build packets and registered source views;
the separately selected-image `packet` interface remains available for individual
proposals. Both model calls and object reviews share bounded slots. GPU generation
is excluded from branch builds; use serial construction for it. Host accounting
shares overlapping compute intervals rather than charging the host multiple times.

A wave builds immutable branch scenes and preserves original parent identities.
`merge` uses the trusted semantic-root importer, fresh Blender verification and
new evidence. It does not run model review or commit. A passing `review` then
permits `commit`. Same-wave independent branches can be merged against earlier
same-wave commits. Modified branches and unrelated canonical edits are rejected.
Branch failures are recorded without automatic retries, repairs or takeover;
the agent decides the next action. Successful siblings remain available.
Session reopen preserves branches and capacity. Keep the whole session directory.

Offline integration check, with real isolated Blender but fixture proposals and
stubbed visual evidence/review (no paid calls and no quality certification):

```bash
PYTHONPATH=src .venv/bin/python scripts/evaluate_aha_driven_parallel.py \
  PREPARED_CONSTRUCTION_CONFIG --output /tmp/driven-parallel-smoke-NEW
```

## Fair comparison

Compare **automated AHA** with **agent-driven AHA** on identical prepared input
bundles, seed scene, requested objects/materials, models, budget policy and final
gate. Match concurrency caps/calibration policy as well, and record the selected
limits. Use separate output directories. Record input and code hashes, model settings,
worker task packets, failures, retries and final status. Evaluate frozen scenes
with the same held-out evaluation protocol. Never send hidden annotations to workers.

For controller-only comparisons, reuse the exact same reviewed reference and
exclude preparation equally. For end-to-end comparisons, include preparation
in both arms. Do not compare a validated layout to a full rendered delivery.
Report quality/completion alongside tokens, API cost and elapsed time; a fast
blocked attempt is not a successful reconstruction.

`report.json` includes the shared ledger, active command seconds and elapsed
session seconds (which include time between commands). The main conversation and
external subagents are **not metered by this CLI**: `external_supervisor_usage`
remains null. Attach provider/session usage exports to the experiment to measure
total input/output/cached tokens and cost. Do not report the worker ledger alone
as total cost. Final native review charges can also have unknown usage/cost,
matching the automated arm's current accounting limitation. Budget exemptions
are not zero-cost claims. No performance advantage is established by unit tests.

### Shared hosted-response and packet contract

Both controllers use `multiagent/providers.py`: hosted calls carrying a schema now
request `json_schema` output, explicitly separating input context from output keys.
Local validation remains required. This addresses the observed Qwen task-packet
echo failure; it does not certify generated geometry.

Agent-driven `packet` and parallel `build-wave` use the shared builder contract:
object inventory without duplicated full-scene camera matrices, retained selected
reference-camera evidence, explicit Blender helper instructions, and the same
object-local parallel restrictions. `packet` still honors explicitly selected
images/assets and omits prior-task history. Existing saved packets retain their
original contents; create a fresh packet to get the leaner context. The shared
isolated worker accepts `import roomkit` as an alias for its provided helper.

Live limitation (2026-11-16): the subsequent full construction probe still produced
repeated import text and truncated code from Qwen/DeepInfra, despite successful
small abstention-schema validation. That run was stopped. Schema conformance,
executable code, and visual acceptance are separate gates; the tiny schema probe
must not be treated as construction readiness. Validate a representative real
build before launching another full run with this worker configuration.

The subsequent [Qwen diagnosis](aha-auto.md#qwen-transport-diagnosis-2026-11-16)
adds shared sampling/output-mode settings, finish-reason handling, raw-response
retention, token accounting, required proposal code, and explicit coordinate/helper
contracts. These apply to `propose` and parallel branches through the shared
provider/runtime; explicit `packet` also includes the helper example. Text-mode
responses still require local schema and visual validation. No full-room readiness
is implied by a successful code-generation control.

### Candidate export independent of acceptance

Closing an operation, including a failed operation, refreshes `output.json` and
`final_scene.blend` whenever a usable scene exists. To explicitly refresh it:

```bash
python -m agen3d.multiagent.aha_driven.cli export /path/to/session
```

The shared AHA exporter chooses the latest hash-verified serial/merged extension
of the current scene, falling back to the canonical scene. Rejected geometry can
be exported for inspection; it cannot pass `commit` without a passing bound
review. `report.json.scene` is still canonical; `report.json.output` describes the
export, local review, provenance and limitations. Unmerged branches are retained
separately. A diagnostic export may be incomplete and is never delivery acceptance.
No extra model calls, rendering, camera animation or resource packing are done.
Historical candidates without an artifact receipt are not automatically selected.
