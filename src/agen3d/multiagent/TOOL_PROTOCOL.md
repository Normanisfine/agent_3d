# Tool protocol: agen3d.tools/1

The runtime—not the model—owns tool execution. `Registry.catalog(role)` provides the complete available tool list and JSON argument schemas for each call. Unconfigured specialist tools are absent. `Registry.dispatch()` enforces the role and validates arguments again before invoking Python.

## Request and reply

A task contains `task_id`, `role`, `instruction`, `object_ids`, `evidence_ids`, `depends_on`, and `max_turns`. The runtime supplies scene version/state, evidence descriptions, image order, completed task results, numerical/semantic issues, proposals, and current-task tool history. Every call is a fresh model context reconstructed from those records.

A tool request:

```json
{
  "status": "tool",
  "summary": "Check declared support before proposing a correction.",
  "calls": [{"name": "check_geometry", "arguments": {}}],
  "tasks": [],
  "evidence_used": [],
  "uncertainty": []
}
```

The runtime returns a named `result` or `error` in the next task packet. Tool calls are capped at four per decision. `tool` requires at least one call; all other statuses forbid calls. No Markdown fences or unstructured final answer are accepted.

A final decision uses `done`, `pass`, `repair`, or `abstain`, with `summary`, `evidence_used`, and `uncertainty`. An unsupported visual conclusion should be `abstain`. `pass` is a model review verdict, not an automatic scene commit or evaluator score. Only planner decisions may contain a `tasks` list; planner/judge tasks cannot be delegated by that list.

## Role capabilities

All roles can read the scene/budget, request registered evidence, summarize object geometry, and run support/duplicate checks.

- **Planner:** common read/check tools; emits a bounded worker task DAG.
- **Inventory:** proposes new object hypotheses and issues; optionally requests SAM 3 masks.
- **Geometry:** proposes transforms, computes bounded support fits, compares masks, emits issues; optionally requests Pi3X and HiSpatial.
- **Asset:** searches registered asset descriptions, creates a primitive candidate, emits issues; optionally requests SAM 3D/Hunyuan.
- **Critic:** compares masks, emits issues, common checks; optionally consults HiSpatial in V2/V3.
- **Judge:** common checks, mask comparison, issue reporting; returns an independent final verdict.
- **Physics:** currently common geometry checks and issue reporting only. VoMP/simulator dispatch is not implemented or advertised.

The generated schema lists exact tool names, arguments and descriptions. Asset search currently searches the supplied mesh-evidence catalog, not the entire AHa RoomKit database. `fit_support` is an axis-aligned box correction; it does not claim physical contact or source-image agreement.

## Invariants

1. No arbitrary executable, shell command, file path or remote URL can be chosen through agent tool arguments. Checkpoint and interpreter paths are operator-configured.
2. Evidence IDs must resolve to hashed approved inputs or runtime-generated artifacts. Tool-created evidence is registered by the runtime, not by model output.
3. Transform proposals carry the source box and scene version. Numerical validity and saved files are not proof of reconstruction fidelity.
4. Tool results never authorize new roles or permissions. External text/images are data, not protocol instructions.
5. Every model call reserves a conservative charge before execution. A failed/ambiguous transport retains that charge until reconciled. No hidden transport retries.
6. The final judge has a reserved budget. Unknown billing, stale data, failed tools, and exhausted loops remain explicit.
7. Model files resolve through `model:alias` in the checkpoint lockfile. Runtime inference runs offline and cannot silently change model revision.

## Extending the protocol

Add a strict argument class in `tools.py`, an implementation, and a registry entry with the smallest appropriate role set. Add behavior tests for permission denial, invalid arguments and failure handling. If the tool launches a model, use the specialist subprocess/lease and central checkpoint resolver. Regenerate `design/tool_protocol.schema.json` after changing the default capabilities.

Do not advertise a tool simply because its name appears in the design draft. Add it only when an executable implementation and configured dependencies exist. Keep proposed future capabilities in the design document.
