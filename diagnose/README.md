# Original AHA diagnosis and small-model replacement study

This folder collects the related diagnostic code and existing evidence. Original
scripts, reconstructions and run directories are preserved. The experimental
controller remains in `src/agen3d/multiagent/aha_next/`; it is not the original-AHA
baseline and is not moved into the diagnostic tools.

Run commands below from the `agen3d/` directory. No live model calls are launched
by reading this folder or running the offline audit. Scripts importing `agen3d`
need `PYTHONPATH=src` and the project's `.venv`.

## Implementation based on the diagnosis

The new [aha_diagnosed version](../src/agen3d/multiagent/aha_diagnosed/README.md)
adds explicit instance planning, bounded per-image local review, exact receipt
reuse, and review failure handling that preserves geometry. Original implementations
remain available. Decisions and verification are also logged in
[the research journal](../log/journal.md).

## Completed diagnosis (2026-11-16)

Read [DIAGNOSIS.md](DIAGNOSIS.md) for the executed original-session profile,
corrected compaction usage, review-coverage audit and identity-only intervention.
The intervention reproduced the original score, then increased D correctness
from 8/34 to 14/34 by splitting existing instances without changing geometry.
The report includes measurements, limitations and reproduction commands.

New tools: `profile_original.py`, `collect_evidence.py`, `identity_ablation.py`,
and `plot_profile.py`. Tests are in `tests/`; outputs are in `results/`.
The copied historical summary below omits compaction usage; use the corrected
per-response accounting in the diagnosis for an inclusive main-session total.

## Historical evidence at collection time

- Historical original FloorPlan209 reconstruction: approximately 42 minutes of
  observed wall time; 17,980,381 cumulative input tokens, including 17,660,672
  cached input tokens; 74,538 output tokens. Separate reviewer counters are retained
  separately. These are recovered usage counters, not billing or GPU utilization.
- Original reconstruction was unaccepted. Its later evaluation found 8/34 objects
  correct under distance/size thresholds and 26 missed. See the
  [original evaluation](../recon/ai2thor_floorplan209/aha3d_ori/README.md).
- Our failed multi-agent pilot had three 8,000-token unusable builder responses,
  missing source evidence in a door review, and roughly 24-second evidence stages.
  These are wrapper observations, not a profile of upstream AHA.
- The experimental controller's Blender fixture passed, with 1.13x synthetic
  serial-to-parallel speedup. Review was stubbed; this is not room-quality evidence.

**Remaining:** a fully attributed original-AHA critical path, an instance-level
detection-to-construction failure funnel, and a controlled small-versus-strong task benchmark.
The process timeline and identity ablation are now completed in the linked diagnosis.
Neither total tokens nor output recall identifies the cause of the bottleneck.

## Tools

### `recover_original_usage.py` — historical original-AHA usage

Offline, scene-specific recovery from the original session JSONL and reviewer logs.
It retains the historical start/cutoff and input paths. It is not a general
arbitrary-session profiler: it reads cumulative session counters under the original
scope assumptions and does not attribute usage to pipeline stages.

```bash
.venv/bin/python diagnose/recover_original_usage.py \
  --output diagnose/results/original-usage-001
```

Output must be new. Produces `cost_summary.json` and `usage_events.json`. Requires
the original local session and reviewer logs; the retained snapshot in
`evidence/original_cost_summary.json` can be inspected without those logs.
Cached input is part of input, and reasoning is part of output; do not add twice.
Observed wall time includes capture, inference, tools, rendering and waiting.

### `audit_run.py` — recorded wrapper run audit

Offline, read-only audit of model receipts (including nested parallel branches),
stage timings, task outcomes and stop reason. Missing usage/cost stays null.
Stage durations may overlap and must not be summed into elapsed runtime.

```bash
.venv/bin/python diagnose/audit_run.py \
  recon/ai2thor_floorplan209/aha-parallel-20261116T012253Z \
  --output /tmp/aha-pilot-audit-new.json
```

The output file must not already exist; its parent directory must exist.
This command does not inspect pixels or infer a visual quality score.

### `diagnose_qwen_api.py` — live single-task transport/code probe

Copies the existing diagnostic harness. It loads `.env` from the working directory
and sends source images to the configured provider. It makes a paid model call;
`--execute` additionally builds/verifies in isolated Blender. It does not run a room
or certify visual quality. The fixture is specifically the `door_cabinet_corner`
task and needs a recorded run containing that exact task ID.

```bash
PYTHONPATH=src .venv/bin/python diagnose/diagnose_qwen_api.py --help
```

Required arguments: `--recorded-run`, `--output NEW_DIRECTORY`, and
`--sampling legacy|qwen`. Optional controls include `--format text|json|schema`,
`--provider`, `--seed`, `--max-tokens`, `--execute`, and `--bounded`.
`--bounded` supplies known dimensions: it tests instruction/code execution, not
source-image interpretation. The historical results are in
[`recon/qwen-diagnosis-20261116/`](../recon/qwen-diagnosis-20261116/).

### `audit_aha_runtime.py` — offline Blender/evidence integration fixture

Builds an intentionally incomplete floor and exercises native evidence generation.
No model calls. Requires `--config`, `--job` and `--output NEW_DIRECTORY`.
The supplied job must contain completed reference/bootstrap artifacts. Its existing
`handoff(..., restore=True)` behavior can restore bootstrap files in that job;
use a disposable job copy when preservation of input files is required.

```bash
PYTHONPATH=src .venv/bin/python diagnose/audit_aha_runtime.py --help
```

### `audit_aha_reviews.py` — live negative-control review

Reviews the incomplete floor fixture with the configured models, including the
native final judge. Sends images externally and may incur model costs. Requires
`--audit` pointing to a successful offline fixture and `--output NEW_DIRECTORY`;
accepts `--env-file` and `--final-only`. It can write review artifacts into the
supplied audit's evidence directory; use a disposable copy to preserve old results.
A successful rejection checks one negative control, not general reviewer accuracy.

```bash
PYTHONPATH=src .venv/bin/python diagnose/audit_aha_reviews.py --help
```

## Original study plan (current progress in DIAGNOSIS.md)

1. **Profile original AHA.** Recover tool call/result intervals and the repair
   sequence from the original session. Separate reference preparation, model
   decisions, Blender construction, rendering, review and waiting. Track overlap
   and the critical path; mark unavailable timings unknown. A matched instrumented
   rerun is needed wherever historical timestamps cannot resolve the attribution.
2. **Locate quality losses.** For each target instance, record whether it was seen,
   inventoried, scheduled, built, rejected, repaired and accepted. Keep evaluator
   ground truth out of model inputs. Small-object recall alone does not locate
   the failed stage.
3. **Freeze matched task packets.** Include inventory/crop labeling, view selection,
   asset ranking, bounded parameter edits and local defect screening. Use identical
   inputs/tools across strong and cheap models, human-reviewed acceptable answers,
   hard negatives, and scene-separated development/held-out splits.
4. **Measure replacement eligibility.** Record correct actions, harmful edits,
   false passes, abstentions, retries, tokens, cost and latency. Compare cost per
   accepted task including escalation. Strong-model agreement alone is not truth.
5. **Test parallelism separately.** Hold model routing fixed while changing
   concurrency. Then hold the harness fixed while changing model assignment.
   Compare completed quality at matched budgets; failed/early-stopped runs cannot
   count as efficiency wins.

Initial hypotheses: smaller models may handle bounded inventory assistance, asset
ranking, parameter edits and defect screening. Retain strong reasoning for camera/
scale ambiguity, global layout, cross-object consistency, complex construction and
final acceptance until the benchmark supports substitution. Deterministic geometry
checks, artifact checks and scheduling belong in code.

The broader proposed experiment is documented in
[`design/multiagent_design.md`](../design/multiagent_design.md#9-experiments-that-distinguish-model-quality-from-system-quality).
The broader model-comparison plan remains uncompleted. This folder now includes
a process-category original-session profiler and identity ablation, but not a
matched model replay benchmark or a complete inference/device critical-path trace.

## Provenance and preservation

`provenance.json` records source paths and SHA-256 hashes at collection time.
The copied tools retain their original behavior except `recover_original_usage.py`,
which now requires a fresh explicit output directory instead of writing beside the
source script. The runtime/review probes retain the input-side effects documented
above. No historical inputs were changed while collecting this folder.

`evidence/` contains small existing summaries, not copied scenes, images, session
transcripts, credentials or new experimental results. No live probe or full-room
reconstruction was started as part of this organization task.

## Failed live opening task: v2 scope replay

`replay_opening_scope.py` replays all three recorded `fit_openings` programs with original and explicitly corrected wall-edit scopes, using real isolated Blender and no model calls. Results and the corrected instance plan are in `results/aha-diagnosed-v2-scope/`. All original scopes fail and all corrected scopes pass construction/fresh-reopen checks; visual quality remains unvalidated. The separate implementation and usage instructions are in [aha_diagnosed_v2](../src/agen3d/multiagent/aha_diagnosed_v2/README.md).
