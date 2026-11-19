# AHA diagnosed — instance planning and bounded review

New opt-in version based on the [original-AHA diagnosis](../../../../diagnose/DIAGNOSIS.md).
The original `aha`, `aha_driven`, and `aha_next` code and historical runs are
preserved. This version imports their existing artifact validation, isolation,
budgets, model transports and native final gate; it is not a standalone frozen fork.

## What changes

**Explicit instance intent.** The strong planner produces an `InstancePlan` with a
scope statement and one entry per physical instance, including source-image IDs,
support, and build/preserve/exclude intent. Repeated tables, mirrors, vases and
accessories must have distinct IDs. A multipart object still has one root; a room
shell may be one structural instance. Validation rejects duplicate IDs, unknown
source IDs, absent preserved instances, unaccounted existing roots, and untasked
build instances. Exclusions require a reason and remain in the report.

Declared support objects are added to scheduler read sets. A consumer cannot run
before its support exists or has an earlier construction task. Existing dependency
and read/write-conflict checks remain in force. `instance-status.json` distinguishes
intent, artifact presence and task status; presence never means visual acceptance.

This makes intent auditable, but cannot prove the planner detected every source
object or that an asserted single instance really is one. Existing grouped scenes
need an explicit migration task; the runtime does not silently split old meshes or
load evaluator annotations. The diagnosis's identity ablation remains separate.

**Expressive strong construction.** All build tasks use the configured supervisor
with the original isolated Blender code/asset capabilities. There is no universal
box-recipe restriction. Object-local context includes assigned instances, declared
supports and their inventory; redundant prior-task history is omitted. Global
reference geometry and all registered construction source images are retained.

**Complete bounded local reviews.** Before any review call, all required focus
images and declared original source views must exist and be nonempty. Each call
receives at most eight images by default. Large packets are split with a common
focus/source anchor, preserving the union of every required image. Each response
must contain exactly one concrete observation per delivered image, bound to the
candidate revision. Merely listing reviewed image IDs cannot pass.

The batches execute under existing model concurrency limits. All required batches
must pass before local commit. Shared anchors help cross-view interpretation, but
batch judgments do not independently establish complete-room consistency; the
native final judge still performs that review.

**Evidence/transport errors do not rebuild geometry.** Missing evidence, malformed
reviews, or changed review inputs block at review. Geometry is retained for
inspection; no reconstruction retry is spent on an invalid review. Actionable
visual defects still trigger bounded strong repair. Failure reports distinguish
`blocked_review` task outcomes from `blocked_construction`.

**Exact review reuse.** Review cache keys include candidate revision, task, object
and support metadata, image IDs/paths/bytes, model settings, and policy version.
Concurrent identical requests share one call; changed images/revisions/instructions
invalidate reuse. Original call charges remain in the ledger and cache hits are
logged. This cache does not reuse judgments across scene edits or skip rendering.

**Parallel branches without head-of-line waits.** Independent branch builds run
concurrently. Finished branches are merged/reviewed in completion order, with one
canonical writer. Repairs are deferred until successful siblings are processed.
Fresh merged-scene review and unchanged scope/camera checks remain required.

## Cheap-model policy

Default: strong construction and strong local review. The diagnosis did not
establish reliable cheap general construction, so this is a quality-oriented
baseline rather than a claim of demonstrated cost reduction.

`--cheap-triage` optionally enables one screening round per task. Cheap rejection
can request strong repair; cheap passes always go through strong review. Invalid
cheap responses fall through to strong review, while budget exhaustion stops.
A later repair of the same task skips cheap screening. Receipts expose the route.

This avoids cheap false acceptance, but cheap false rejection can still waste a
repair. It may cost more on mostly-correct candidates. Evaluate it with matched
packets before using it as a cost optimization. The CLI caps cheap screening output
at 2,400 tokens and uses text transport with mandatory local schema validation.

## Run

From `agen3d/`, choose a new output directory:

```bash
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_diagnosed.cli \
  recon/ai2thor_floorplan209/aha-parallel-20261116T012253Z/config.json \
  --output recon/ai2thor_floorplan209/aha-diagnosed-001 --env-file .env --cuda
```

This example continues from the pilot's reviewed shell. Existing prepared-input
or raw-preparation AHA configs are supported. The input config is read-only.
Add `--max-review-images 6` to use smaller local packets or `--cheap-triage` to test
screening. These options affect local reviews, not the independent final gate.

Run records include `variant.json`, `instance-plan.json`, `instance-status.json`,
`dependency-plan.json`, per-call responses, `covered-reviews/`, task outcomes,
stage timings, and the shared ledger. `report.json` names `aha_diagnosed` and lists
exclusions and limitations. Final `layout_validated` still is not full delivery
acceptance.

## Remaining boundaries

The native whole-room final-review transport and evidence rendering are unchanged.
This version does not yet distribute the final 92–111-image review or cache renders.
It tightens the pre-commit review contract, reduces avoidable reconstruction retries,
and provides an instance-aware execution baseline. Final-review decomposition needs
its own native image-delivery receipts and budget accounting before implementation.

No live full-room quality/cost benefit has been demonstrated. No source ground truth
or evaluation-bearing diagnosis data is loaded by reconstruction. No old scenes,
reference bundles, provider configuration files or upstream AHA checkout are edited.

## Validation

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q \
  src/agen3d/multiagent/aha_diagnosed/tests \
  tests/test_aha_scheduling.py tests/test_aha_construction.py

PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_diagnosed.evaluate \
  recon/ai2thor_floorplan209/aha-parallel-20261116T012253Z/config.json \
  --output /tmp/aha-diagnosed-smoke-NEW --workers 3
```

The offline integration uses real isolated Blender construction/merge/verification
and fixture model responses. Mock focus evidence deliberately does not claim
visual assessment. It checks four separate commits, seed preservation, zero
fallbacks, and four per-image-bound review receipts. The unit/regression suite
checks instance coverage, support ordering, missing evidence, cache invalidation,
cheap-pass escalation and review failure without rebuilding geometry.

Research log: [`log/journal.md`](../../../../log/journal.md). Experiment records
under `log/experiments/` identify the diagnostic results and this implementation.
