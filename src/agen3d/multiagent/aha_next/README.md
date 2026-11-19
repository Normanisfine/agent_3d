# AHA next: bounded cheap builders, evidence-complete review

Experimental opt-in controller. Existing `aha`, `aha_driven`, configs and historical
runs are untouched. This module imports their Blender isolation, artifact checks,
budget accounting, dependency conflict logic, scoped merge and final native gate.
It is not a frozen independent copy of those dependencies.

## Findings from the requested pilot

Source: `recon/ai2thor_floorplan209/aha-parallel-20261116T012253Z`.
`pilot-audit.json` contains the extracted receipts and timings. Reproduce with:

```bash
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_next.audit \
  recon/ai2thor_floorplan209/aha-parallel-20261116T012253Z --output /tmp/pilot-audit-new.json
```

- Three parallel Qwen builders each consumed 8,000 output tokens and roughly
  28,000 input tokens without returning usable proposals. Their recorded combined
  API charge is $0.02698665. Dollar cost was small; latency, wasted context and
  failure to finish were the larger problem. Adding workers multiplies this failure.
- The door review explicitly says source_000062 was absent. Repeated geometric
  repair without the needed image cannot reliably resolve casing dimensions.
- Three evidence-preparation stages took 24.41, 23.60 and 24.61 seconds. Individual
  build stages took about 1.1 seconds; verification about 0.4 seconds. More Blender
  workers alone cannot remove the serial rendering/review cost.
- The original scheduler consumes futures in plan order and executes repair inline.
  A slow or failed early branch delays committing already-finished siblings.
- Cheap builder packets repeat global inventory/history and ask for unrestricted
  Python. This combines source interpretation, geometry, API knowledge and program
  correctness in one failure-prone response.
- Existing later transport fixes are useful but did not prove room fidelity.
  This implementation retains them rather than claiming to rediscover a fix.

## Implemented changes

1. A cheap builder emits at most 16 box parts with finite metric transforms,
   colors, source IDs and one semantic root. A trusted compiler produces Blender
   code. Wrong scope, stale parents, unknown evidence and invalid extents fail
   before Blender. Parts have world-space centers, full extents and Z rotation.
   This intentionally narrow representation must abstain for unsupported shapes;
   strong builders retain unrestricted isolated Blender construction.
2. Global/exclusive and multi-root tasks go to the strong builder. A routine cheap
   canary must construct and pass local visual review before parallel cheap fan-out.
   Invalid recipes or construction failures disable subsequent cheap builds for
   that job. Calls already in flight can finish. Geometric rejection triggers
   strong repair immediately, rather than another cheap visual repair attempt.
   Existing takeover limits and dollar reservations still apply.
3. Independent completed branches are consumed with `as_completed`; canonical
   merge/review/commit remains serial. Repairs wait until successful siblings have
   been processed. Dependencies, read/write conflicts, immutable parent checks and
   fresh merged-scene review remain mandatory. Completion order is now timing-dependent.
4. Object-local packets omit unrelated inventory/history but retain declared reads,
   global reference geometry and all source images. Reviews receive every required
   focus view PLUS the original source images, bound to the exact revision. This
   increases review image cost deliberately to address the observed evidence gap.
5. The new CLI uses text output with local schema validation and a 2,400-token worker
   cap. It does not change sampling/model/provider or modify the supplied config.
   A recipe too large for the cap fails and escalates; the cap is not a fidelity claim.

## Run

From `agen3d/`, using a new output directory:

```bash
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_next.cli \
  recon/ai2thor_floorplan209/aha-parallel-20261116T012253Z/config.json \
  --output recon/ai2thor_floorplan209/aha-next-001 --env-file .env --cuda
```

The pilot config continues from its original reviewed shell. Use a different
existing AHA config for different prepared inputs or raw-video preparation.
The CLI requires an explicit fresh output; it cannot overwrite the old run.
Cheap reviewer calls remain cheap, and the independent final Codex gate is unchanged.
`layout_validated` still does not mean full upstream delivery acceptance.

## Verification and limits

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q src/agen3d/multiagent/aha_next/tests \
  tests/test_aha_scheduling.py tests/test_aha_construction.py
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_next.evaluate \
  recon/ai2thor_floorplan209/aha-parallel-20261116T012253Z/config.json \
  --output /tmp/aha-next-eval-NEW --workers 3 --provider-delay 1
```

Real isolated Blender fixture test: four objects committed, original objects and
cameras preserved, zero fallbacks, four fixture provider calls for both widths.
One worker: 7.49 seconds. Three workers including serial canary: 6.62 seconds
(1.13x). Results are in `offline-evaluation.json`; raw artifacts are under
`/tmp/aha-next-eval-20261116-host`. The first sandboxed attempt could not create
Bubblewrap's network namespace; the host retry retained Bubblewrap isolation.

This is a single synthetic-latency experiment with stubbed visual review. It does
not measure live model savings, improve measured room fidelity, or establish an
advantage over the old controller. No paid full-room run was launched in this change.

Remaining bottleneck: evidence rendering and fresh canonical review stay serial.
Safe next experiments are object-local evidence caching keyed by object, camera,
neighbor and reference hashes; batched merges followed by a fresh joint review;
and supervisor-authored per-object bounds/source-view briefs. None is silently
implemented here: each can change evidence validity or mask interaction defects.
The conservative circuit can also over-escalate after a task-specific failure;
measure this before adding per-task-class circuit recovery.

Before promoting: run old/new controllers on identical reviewed inputs, model
settings, budgets and held-out views. Count completed/accepted objects and final
gate result first, then wall time, paid usage, strong takeovers and total tokens.
Keep external supervisor usage and unknown CLI costs explicit. A cheap run that
abstains or stalls is not a quality or efficiency win.
