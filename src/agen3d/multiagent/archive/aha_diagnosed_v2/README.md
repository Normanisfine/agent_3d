# AHA diagnosed v2: explicit edits and independent failure handling

This opt-in version preserves `aha`, `aha_next`, and `aha_diagnosed`.

The FloorPlan209 run `aha-diagnosed-20261116T223340Z` failed because `fit_openings` instructed the builder to cut `room_walls` and `wall_wainscoting`, but authorized writes only to four opening roots. The scope validator correctly rejected all three programs. Separately, exclusive execution was implemented as a global success dependency, blocking unrelated tasks after that failure.

## Changes

- `ScopedWork.object_ids` identifies construction targets; `edit_object_ids` and `edit_reason` explicitly authorize edits to existing roots. The instance manifest must mark those roots `edit`. Existing edit targets must be present. Edit tasks execute exclusively.
- The lowered task/proposal write set includes both groups. Generated Blender code receives construction targets in `object_ids`, existing editable roots in `editable_object_ids`, and their union in `authorized_write_ids`. This prevents bulk cleanup of new targets from deleting existing walls.
- The isolated worker writes `scope-diff.json` with actual versus authorized changes. Unauthorized changes and missing required roots stop with `blocked_scope`, without repeated geometry generation. The fix requires correcting the plan; permissions are never widened automatically after rejection.
- Semantic read/write dependencies still require success. Exclusive execution and write-after-read barriers require completion only. Independent work can continue after a failure; true consumers stay blocked.
- Strong construction, covered local reviews, fresh-process verification, camera preservation, and native final review remain in place. Cheap triage remains optional and disabled by default.

## Evidence

Saved results: `diagnose/results/aha-diagnosed-v2-scope/` (relative to repository root).

All three recorded programs fail with original scopes and pass construction plus fresh-reopen verification with explicit wall edits, with their build code unchanged. The corrected saved plan permits `build_rug` and `build_ceiling_fixtures` after opening failure. Offline fixture integration committed four objects with three workers, zero fallbacks, and preserved baseline objects. Unit and regression tests: 55 passed. These checks made zero hosted-model calls and do **not** establish visual quality or full-room cost improvements.

Reproduce recorded scope failures and corrections:

```bash
PYTHONPATH=src .venv/bin/python diagnose/replay_opening_scope.py \
  --run recon/ai2thor_floorplan209/aha-diagnosed-20261116T223340Z \
  --output /tmp/aha-scope-replay-new
```

Run the new variant in a fresh output folder (normal model calls and evidence generation):

```bash
PYTHONPATH=src .venv/bin/python -m agen3d.multiagent.aha_diagnosed_v2.cli \
  configs/multiagent/aha-diagnosed-20261116T223340Z.json \
  --output recon/ai2thor_floorplan209/aha-diagnosed-v2-new
```

The live command replans using the explicit edit schema; it does not load the saved corrected plan automatically. A planner can still omit an intended edit. Such omissions are reported and stopped rather than repaired by granting inferred permissions. Full visual review and a matched live comparison remain necessary before claiming quality, speed, or cost gains. Smaller-model geometry generation has not been validated by this fix.
