# Agen3D multi-agent design: strong leadership, cheap grounded workers

> Superseded for forward development by [designv2.md](designv2.md), which proposes
> one executable construction architecture. Retained as historical rationale;
> the V1/V2/V3 comparison below is no longer the implementation plan.

Discussion draft — 2026-11-15. Proposed architecture and experiments; no model deployment, paid inference, or experiments were performed for this draft.

## 1. Recommendation

Keep Astra/Fable as the **top planner and top judge**, and move repeated object inspection, candidate selection, fitting, and local verification into bounded workers. Preserve AHa-3D's geometry-first approach: compute Pi3X reference geometry and SAM 3 masks once, then reuse those artifacts across the workers.

Start with **V1: a shared cheap VLM with structured tools**. Compare it against **V2: specialist workers** and **V3: adaptive escalation**. These are three routing/organization variants of the same reconstruction pipeline, not three independently built systems. Test asset generators separately so their effects do not get confused with the benefits of cheaper agents.

The key research question is: **which decisions can a cheap worker make reliably when supplied with geometric evidence and checked by a verifier?** A smaller model need not reproduce everything Astra/Fable does. It needs to solve a narrow task, return evidence, or abstain.

Here, `strong_planner` and `strong_judge` are configuration aliases for the user's Astra/Fable deployments. Their exact callable model IDs, providers, prices, and API access remain to be resolved; these names are not assumed to be OpenRouter IDs. Use separate planner/judge contexts even when both aliases resolve to the same model.

## 2. What we retain from AHa-3D

The local reference builder explicitly uses Pi3X and SAM3 segmentation. That is distinct from an already-integrated SAM 3D Objects pipeline. See [repository audit](../docs/repo_audit.md) and [reference builder](../external/aha-3d/tools/layout_inspection/build_reference.py).

- **Pi3X:** cameras, point maps, confidence, and approximate metric geometry. Keep complete reference artifacts and coordinate transforms. Its estimated scale is not ground truth. [Official Pi3/Pi3X repository](https://github.com/yyfz/Pi3)
- **SAM 3:** image/video segmentation used to isolate visible evidence. Masks are observations to validate, not guaranteed object identities or complete inventories. [Official SAM 3 repository](https://github.com/facebookresearch/sam3)
- **Reusable assets and Blender assembly:** retrieve and fit existing objects before requesting expensive generation; preserve stable instance IDs and editable objects.
- **Source views and inspection:** render candidates back into source cameras, inspect support/contact and silhouettes, and retain before/after evidence.

Pi3X and segmentation outputs should improve the input to each agent, rather than become enormous arrays inserted into prompts. The VLM sees selected crops, overlays, and geometric summaries; numerical tools read the full data.

**SAM 3D Objects** is a separate candidate tool: it accepts an image and object mask and can propose shape, texture, and layout. Treat its pose/layout as a proposal to reconcile with the common scene coordinates. **Hunyuan3D** is another asset-generation backend. Neither should directly overwrite the canonical scene. [SAM 3D Objects](https://github.com/facebookresearch/sam-3d-objects), [Hunyuan3D-2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1)

## 3. Model shortlist and deployment choices

### Cheap general-purpose worker

Use **Qwen3-VL-8B-Instruct** as the initial reference worker. Compare **Qwen3-VL-4B-Instruct** for a smaller local deployment and **Qwen3-VL-30B-A3B-Instruct** through OpenRouter as a potentially inexpensive stronger worker. These are available model variants in the official Qwen release. Use Instruct first; long reasoning outputs are an additional experimental variable. [Qwen3-VL repository](https://github.com/QwenLM/Qwen3-VL)

Proposed responsibilities: category/attribute labeling, selecting useful reference views, ranking asset candidates, local source-versus-render comparisons, and choosing among a short list of repair actions. The agent must be allowed to return `insufficient_evidence`.

Public OpenRouter pages checked on 2026-11-15 list:

- `qwen/qwen3-vl-8b-instruct`: **$0.25 input / $0.75 output per million tokens**. [Model page](https://openrouter.ai/qwen/qwen3-vl-8b-instruct)
- `qwen/qwen3-vl-30b-a3b-instruct`: **$0.15 input / $0.60 output per million tokens** at the displayed starting rate. [Model page](https://openrouter.ai/qwen/qwen3-vl-30b-a3b-instruct)

These are public snapshots, not account-specific quotes or guaranteed future prices. Provider choice changes price and behavior. The larger model is currently cheaper at these displayed rates; model size alone is a poor routing rule. A3B denotes active parameters, not the total weight memory required for self-hosting.

For illustration only, 6,000 billed input tokens plus 500 output tokens would cost $0.001875 on the listed 8B rates and $0.0012 on the listed 30B-A3B rates. This excludes tool computation, other charges, retries, and strong-model calls. Actual image token accounting must come from the serving endpoint.

### Spatial specialist

**HiSpatial-3B** is an optional V2 worker for spatial questions that are not resolved by numerical checks. Its documented input is RGB plus a 3D point map, with MoGe in the reference inference path. A Pi3X adapter requires verification of camera coordinates, units, pixel alignment, resizing, and normalization; it is not automatically a drop-in replacement. Compare documented MoGe inputs against adapted Pi3X inputs explicitly. Its published training data includes CA-1M, so audit training/test overlap before interpreting CA-1M results. [Official HiSpatial repository](https://github.com/microsoft/HiSpatial)

Do not call a spatial VLM to compute a distance already available from two valid 3D coordinates. Use it for ambiguous support identity, object-relative orientation, or interpretation of conflicting observations.

### Asset specialists

- **SAM 3D Objects:** first candidate to test for masked objects in cluttered source images. Its returned layout remains provisional until multi-view fitting.
- **Hunyuan3D-2.1 Shape:** alternative for image-conditioned object geometry. Generate shape first; texture only an accepted candidate. Upstream reports about 10 GB for shape, 21 GB for texture, and 29 GB for the combined pipeline; actual peaks depend on configuration. [Official implementation](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1)
- **Procedural primitives and retrieval:** essential low-cost controls. A rectangular carton may be better represented by a fitted box and material than by a new generative mesh.

These tools replace manual asset modeling, not top-level judgment. Generated invisible surfaces are hypotheses. PBR appearance does not establish mass, friction, watertightness, or a usable collision mesh. Record model revision, seed, input masks/crops, asset provenance, and checkpoint license before deployment; open weights do not imply identical licensing terms.

### Where to run

Begin with OpenRouter for the cheap VLM and local queued geometry/generation tools. This avoids competing with Pi3X or asset generation for the same GPU and gives an early API cost baseline. Do not assume OpenRouter hosts the specialist 3D models.

For self-hosting, use one persistent inference service shared by all compatible roles, rather than loading a model per agent. Qwen documents vLLM/SGLang serving options. Choose a supported runtime/model revision and measure peak memory at the actual image resolution, context, and concurrency. [Qwen serving documentation](https://github.com/QwenLM/Qwen3-VL)

The earlier chat mentions 3090/5090 hardware, while the checked-in AHa machine guide targets a single GPU and serial GPU work. Actual available devices have not been verified here. Default to one GPU job at a time; make a separate VLM GPU an optional deployment profile. A model's nominal weight size is not its total runtime footprint.

## 4. Shared architecture and agent permissions

```text
Selected RGB frames
        |
Pi3X + SAM 3 reference artifacts -----> evidence store
        |                                   |
Strong planner -> task DAG -> cheap workers + numerical/specialist tools
                                 |
                            candidate patches
                                 |
                    deterministic validation + local critic
                                 |
                       single scene-state committer
                                 |
                  strong final judge -> accept / bounded repair / unresolved

Privileged benchmark labels -> separate offline evaluator only
```

An “agent” is a role-scoped task with an input schema, allowed tools, budget, and output schema. It need not be a separate model process. Workers do not freely chat or recursively spawn other workers; the scheduler creates tasks from the dependency graph. All tool names below are **proposed adapter interfaces**, not claims that these APIs already exist.

### A. Top planner — Astra/Fable

Input: scene overview, reference coverage, uncertainty summary, asset availability, and remaining budget.

Allowed tools: `read_scene`, `get_evidence`, `list_capabilities`, `create_tasks`, `prioritize_tasks`, `request_escalation_review`, `read_budget`.

Output: dependency-aware work plan, object priorities, success conditions, and capped repair decisions. It delegates tool execution and scene edits. One initial planning call plus bounded escalation calls is the default. Group several unresolved issues into one escalation packet where possible.

### B. Inventory and evidence worker — cheap Qwen VLM + SAM 3

Allowed tools: `get_frames`, `get_crop`, `segment`, `associate_tracks`, `summarize_geometry`, `propose_object`, `request_evidence`.

Output: candidate object identities, selected views, mask/track references, uncertain associations, and evidence-backed missing-object hypotheses. `associate_tracks` combines overlap/reprojection with optional semantic adjudication; it is not assumed to be solved by SAM alone.

It cannot delete confirmed instances, merge ambiguous duplicates silently, or invent unseen objects as observations. Include a coverage sweep of source images so the whole system does not overlook objects absent from the initial inventory.

### C. Geometry and placement worker — numerical tools; optional spatial VLM

Allowed tools: `read_points`, `estimate_extent`, `fit_support_plane`, `fit_transform`, `render_candidate`, `measure_source_fit`, `propose_transform`.

Output: transform proposals with units/frame conventions, fitting residuals, visible support, and degeneracy flags. V1 uses Qwen only when semantic interpretation is needed; V2 may use HiSpatial. Deterministic fitting remains identical across variants.

It cannot change the scene-wide scale or camera basis to make one object fit. Global alignment conflicts escalate. Limit nonuniform scaling and preserve category-appropriate shape constraints.

### D. Asset worker — cheap Qwen selector + asset tools

Allowed tools: `search_assets`, `render_asset_candidates`, `make_primitive`, `request_sam3d`, `request_hunyuan_shape`, `request_texture`, `inspect_mesh`, `propose_asset`.

Output: ranked candidate meshes and provenance. Generation calls require scheduler-issued budget leases. The worker cannot start both generators repeatedly until one looks good, or commit a mesh directly.

Default path: retrieve → fit; use a primitive when appropriate; generate only when neither meets the source-fit/semantic criteria. Which generator gets the first attempt is fixed by the experimental arm or a development-calibrated routing rule.

### E. Local critic — numerical checks + cheap VLM

Allowed tools: `read_candidate`, `get_source_render_pair`, `measure_source_fit`, `check_support`, `check_duplicates`, `inspect_mesh`, `emit_issue`.

Output: `pass`, `repair`, or `abstain`, with object IDs, issue types, evidence, and suggested permitted actions. Use a fresh critic context rather than the builder's narrative. Sharing weights does not make builder and critic independent; measure correlated failures.

Numerical success is required for automated acceptance, but it is not enough to establish object identity. A good silhouette can conceal a wrong object; a pretty render can conceal a missing instance.

### F. Top judge — Astra/Fable

Allowed tools: `read_scene`, `get_evidence`, `get_source_render_pair`, `read_issue_history`, `read_budget`, `request_audit_views`, `request_repair`, `finalize_review`.

Output: final acceptance status, blocking issues, unresolved uncertainty, and a bounded repair request. It gets the global overview, source/render pairs, a sample of cheap-worker passes, and all high-risk issues—not only the worker's summary. It can reject a proposed edit but cannot override a hard invalid-geometry or budget gate.

Use one mandatory final review in every primary variant, with another final check only if an authorized repair changes the scene. Keep the strong-model configuration fixed in routing experiments. Comparing Astra versus Fable or swapping planner/judge assignments is a later ablation.

### G. Optional physics worker — cheap VLM + VoMP/priors + simulator

Allowed tools: `inspect_mesh`, `estimate_material_prior`, `run_vomp`, `make_collision_proxy`, `check_mass_inertia`, `simulate_settle`, `simulate_interaction`, `propose_physics`.

Output: parameter ranges, construction assumptions, collision proxy, and simulation results. This is a later extension, not part of the first routing comparison. A suspicious 3.13 kg paper-box estimate triggers inspection of units, volume, solid/hollow assumptions, and contents uncertainty; a VLM should not silently replace it with an equally unsupported precise value.

### H. Scheduler, validator, and committer — no language model

Only this component reserves spend, schedules jobs, validates capabilities, applies patches, and writes the canonical scene. It enforces one writer per `.blend`, task idempotency, version checks, timeouts, and rollback. The benchmark evaluator has separate access to labels; no reconstruction role does.

## 5. Three variants to compare

### V1 — Shared cheap worker service: recommended first implementation

One Qwen endpoint serves inventory, asset selection, local semantic repair, and critic roles with separate prompts/contexts. Numerical tools handle fitting and verification. Strong planner at start; strong judge at finish; at most one batched intermediate escalation initially.

Start with Qwen3-VL-8B, then swap in 4B locally and 30B-A3B via API without changing tasks or evidence. This measures model substitution separately from architecture changes.

Expected advantage: simple integration, few model loads, easy attribution of costs. Main risk: the same small model repeats its own semantic mistakes. Audit accepted cases and allow abstention. Hypothesis: a large fraction of routine work needs good evidence and constrained actions more than a stronger model.

### V2 — Specialist workers

Keep the same strong leader/judge and common tools. Use Qwen for semantics, add HiSpatial for selected ambiguous spatial tasks, and retain numerical fitting. Specialist 3D tools are invoked by the same asset contract.

For the controlled V1/V2 comparison, hold the asset policy fixed. Then separately test retrieval/primitive-only versus SAM 3D versus Hunyuan generation. Giving only V2 a generator would confound specialization with access to better assets.

Expected advantage: better spatial interpretation without repeated strong calls. Main risks: extra loading/queue latency, input-adapter errors, and specialists that add little beyond existing numerical tools. Hypothesis: specialization helps only identifiable task categories; it should earn its additional cost on those categories.

### V3 — Adaptive cascade

Start each task with deterministic checks. Route straightforward visual decisions to 4B/8B; send unresolved tasks to the best development-selected medium VLM or spatial specialist; escalate high-impact contradictions to Astra/Fable. Preserve the initial strong planner and mandatory final strong judge.

Use evidence features: mask coverage, number and diversity of views, point confidence distribution, reprojection residuals, fit conditioning, cross-view disagreement, schema validity, task impact, and failed attempts. Do not interpret model self-confidence as calibrated probability.

Use a fixed rule-based router first. Later estimate success probability and expected quality gain from development traces. Choose the cheapest eligible action predicted to meet the task's risk limit, or stop with an explicit unresolved issue. A failed cheap call is sunk cost; do not keep cascading when direct escalation is cheaper.

Expected advantage: reserve expensive reasoning for cases that need it. Main risks: routing overhead and false acceptance. Hypothesis: adaptive routing improves the cost/quality frontier over a fixed cheap model, particularly on mixed-difficulty scenes.

**Initial preference:** implement V1, gather task traces, then build V3 using those traces. Add V2 specialists only where the trace identifies a persistent failure class.

## 6. Task lifecycle, evidence, and scene consistency

Every task carries `task_id`, `role`, `scene_version`, `object_ids`, `evidence_refs`, `allowed_tools`, `model_policy`, `max_calls`, `deadline`, and a reserved cost ceiling. Every result includes `status`, `candidate_patch`, `evidence_used`, `checks`, `uncertainty`, `usage`, and `escalation_reason`.

Example result contract, illustrative rather than an existing schema:

```json
{
  "task_id": "fit_box_04_v12",
  "scene_version": 12,
  "object_ids": ["box_04"],
  "status": "propose_patch",
  "candidate_patch": {"artifact_ref": "candidate/box_04/transform.json"},
  "evidence_used": ["frame_42/crop_box_04", "frame_68/mask_box_04"],
  "checks": {"artifact_ref": "candidate/box_04/source_fit.json"},
  "uncertainty": ["back surface unobserved"],
  "escalation_reason": null
}
```

Lifecycle: `queued → budget_reserved → running → proposed → verified → committed`, with explicit `failed`, `rejected`, `stale`, and `unresolved` outcomes. Persist task events and artifacts so a restart does not repeat a billed call blindly. Reconcile requests of unknown completion status before resubmitting.

Workers can read the same snapshot and compute independent candidates concurrently. The committer rejects a stale patch if its object, support, camera, or other dependencies changed. Changes to a table invalidate dependent placement checks for objects on that table. Final rendering and judging use the exact committed scene version.

An evidence packet contains a context view, usually 2–4 useful object crops, matching source/render views, mask boundaries, numeric extents/residuals, coordinate/scale provenance, and unresolved observations. These are pilot sizes, not universal limits. Permit bounded requests for additional views. Missing visibility must remain explicit.

A geometry residual against Pi3X is a consistency check against predicted geometry, not independent proof of truth. Combine it with source silhouettes and cross-view checks. Keep benchmark labels outside worker mounts, as required by the [current protocol](../docs/protocol.md).

## 7. Asset-generation experiment and fitting policy

The asset worker should answer “which representation is sufficient for this object?” before generating anything.

1. Select a source view using visibility, mask quality, and sharpness; retain context and other views for validation.
2. Retrieve a short candidate list, or choose a parameterized primitive for a simple shape.
3. Fit candidates into the common scene using masks, reliable points, support constraints, and camera projections.
4. If inadequate, request one SAM 3D or Hunyuan shape candidate under the chosen policy. Preserve each model's documented input convention; a tight crop suitable for one tool may discard layout cues needed by another.
5. Convert axes/units, estimate scale from scene evidence, and fit again. Validate in views other than the generation input.
6. Inspect mesh integrity and render fit before texturing. Create a separate collision proxy if needed.
7. Accept, request a bounded alternative, or retain an explicitly marked approximation/unresolved object.

Pilot caps: one initial generation plus one alternative per object, and a scene-level generation cap. Tune these on development scenes. Do not allow a generation retry loop to consume the reserved final-review budget.

Measure generation success **after fitting and validation**, cost per accepted asset, source-view agreement, geometry quality where available, collision usability, and failure categories. A beautiful standalone thumbnail is not the acceptance criterion.

## 8. Cost, compression, caching, and latency

### Reduce work before reducing model precision

- Run geometry once for each exact input/configuration and reuse it across roles.
- Use numerical checks before VLM calls. A known transform or support gap rarely needs verbal reasoning.
- Batch compatible object questions cautiously; keep clear object/view IDs and cap batch size to prevent identity mixing.
- Prioritize geometry and object completeness before expensive texture refinement.
- Use bounded local repair; re-render affected views/objects rather than the full video when sufficient.
- Reserve the strong judge's budget before starting optional work. A finished cheap pipeline without final review is an incomplete run for these variants.

### Three different caches

**Artifact cache:** key Pi3X outputs, masks, crops, generated meshes, and renders by their actual dependencies: source hashes/frame selection, checkpoint revision, preprocessing, prompt/mask where relevant, seed, tool version, and relevant scene state. A material change invalidates appearance renders but need not invalidate camera inference. A camera change invalidates projection-based checks.

**Decision cache:** reuse a worker answer only for the same task schema, evidence, model/provider configuration, prompt version, and relevant scene version/dependencies. Similar-looking objects are not an exact cache hit. Keep benchmark arms and stochastic repetitions isolated; intentional reuse must be labeled.

**Provider prompt/KV cache:** put stable role instructions and tool definitions first; place changing task evidence later. Savings depend on endpoint support, cache behavior, and actual hits. OpenRouter documents provider-specific caching and sticky routing; explicitly ordered providers take precedence over its automatic sticky behavior. Log cache reads/writes and observed billing rather than assuming a discount. [OpenRouter caching documentation](https://openrouter.ai/docs/guides/best-practices/prompt-caching)

### Compression that preserves evidence

Keep canonical scene state and issue history as structured records. Give each worker relevant objects and dependencies, not all past conversation. For the chief, retain decisions, provenance, unresolved contradictions, and changed objects; avoid repeated prose summaries.

Use a low-resolution room overview plus high-resolution crops for tiny objects. Select diverse views by visibility and geometry. Preserve native images for zoom requests. Never remove uncertainty or silently discard contradictory observations during summarization. Avoid lossy compression of numerical state used for fitting; compress only the presentation to the VLM.

Quantization is a separate ablation: compare the same checkpoint in supported precision modes, recording memory, throughput, schema failures, and task quality. Lower memory is useful, but quantization is not automatically cheaper end to end. Defer model pruning, distillation, and custom training until prompting/routing traces establish a worthwhile target.

### Scheduling and cost accounting

Use a CPU orchestration queue, bounded API concurrency, and an exclusive local GPU lease by default. Group jobs by model when that reduces loading costs without delaying critical tasks. Local VLM residency and generative-tool residency must be planned together. Record cold-start and warm-start latency separately.

Before launching concurrent work, atomically reserve its conservative maximum cost; reconcile actual charges afterward. Existing `CostTracker` is synchronous and does not yet provide this concurrency guarantee. Enforce scene, task, token, retry, GPU-time, and wall-time limits. Unknown prices block budgeted execution rather than becoming zero.

```text
C_scene = API charges for every call and retry
        + GPU allocation cost for all pipeline stages
        + separately billed CPU/render/storage/transfer costs

C_API = uncached_input * input_rate
      + cached_input * cache_read_rate
      + cache_write charges where applicable
      + billed_output/reasoning * applicable_rate
```

Use provider-reported charges when available and reconcile with the ledger. Report marginal local operating cost and a fully loaded GPU-cost estimate separately. For rented hardware, include allocated idle/loading time; do not bill the same GPU interval once per overlapping process. Report GPU-seconds even when monetary assumptions are uncertain.

Self-hosting wins economically only when its total allocation/operating cost and overhead are below the API cost for the same workload and quality. Measure the utilization break-even point; do not assume a locally owned GPU makes inference free.

### OpenRouter integration policy

Snapshot model/provider metadata and prices at run start. Validate image input, multi-image handling, structured output, tool calling if used, context limits, and usage reporting on the actual endpoint. Prefer a bounded structured decision followed by scheduler-dispatched tools over giving every small model a general shell.

Require supported parameters (`require_parameters: true` when using OpenRouter's provider routing). Pin provider/model for controlled runs; disable unrecorded fallbacks. A separate deployment experiment may allow an explicit fallback list and measure availability/cost. Provider routing can otherwise change the experimental treatment. [OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)

## 9. Experiments that distinguish model quality from system quality

Follow the existing [experiment plan](../docs/experiments.md) and [evaluation protocol](../docs/protocol.md). The V labels here describe multi-agent variants; they do not redefine existing B0–B6 baselines.

### Stage A — Offline task benchmark

Build approximately 100–200 development tasks from several scenes: identity/attribute labeling, duplicate association, candidate ranking, support interpretation, source/render criticism, and repair selection. Include small objects, occlusion, repeated categories, and inconsistent geometry. Freeze human-reviewed answers/acceptable actions and split by scene, not by crops of the same object.

Compare Qwen 4B, 8B, 30B-A3B, and one strong-model reference on the same packets. Test HiSpatial only on spatial tasks with verified adapters. Record correct actionable outputs, harmful edits, abstentions, schema validity, retries, cost per correct task, and latency. Have blinded human review audit subjective labels; the strong model's answer is not automatically ground truth.

Calibrate routing thresholds and cheap-pass audit rates on development tasks. Measure false acceptance and error rate among accepted predictions, not merely agreement with the strong judge. Test whether a larger cheap model avoids enough retries/escalations to beat a smaller one in total cost.

### Stage B — End-to-end routing comparison

Start with the existing development scenes; keep FloorPlan209 and historical CA-1M captures development-only. After integration works, expand toward the existing plan's 20–30 scenes/captures per dataset with splits by physical room and a stochastic subset repeated with three seeds. Audit data availability and model training overlap before freezing the test set.

Run these controls and variants:

- **Original AHa workflow:** historical system baseline rerun under the documented protocol when executable; saved artifacts alone are not matched-cost measurements.
- **All-strong, shared harness:** strong models handle all semantic worker decisions, with the same numerical tools, evidence, asset policy, and final review as the hybrids. This isolates model substitution.
- **All-cheap, shared harness:** diagnostic lower-cost control; explicitly exempt from the strong leadership requirement because it measures the value of strong oversight.
- **V1, V2, V3:** primary systems with strong planner and final judge.

Keep selected RGB frames, geometry artifacts, coordinate alignment procedure, tools, asset library, generation policy, verifier thresholds, and strong-model settings fixed when isolating routing. Report both the full cost of producing shared geometry and incremental routing cost; precomputed geometry is not free.

Primary quality: instance F1 at 3D-box IoU .25, IoU .1/.25/.5 results, tiny/small recall, placement error, and failed/incomplete scenes. Use the repo's existing area-bin definitions rather than the earlier chat's different bins. Center error is conditional on matching, so always report it alongside recall. Add support-relation and source-fit metrics once implemented. Physics metrics belong in the later extension.

Primary efficiency: total dollars/scene, dollars per successful scene including failed-run spend, strong calls/scene, task escalation fraction, total input/output/image usage, cache hits, GPU time, median/p95 wall time, and peak memory. Count invalid responses, timeouts, OOMs, and retries.

Use paired scene-level differences and bootstrap intervals; do not treat hundreds of objects from one scene as independent scene samples. Report cost–quality Pareto curves at matched total budget caps and cost to a predeclared quality threshold. Show completion rate and unresolved objects so early stopping cannot masquerade as cheap success.

### Stage C — Focused ablations

1. **Evidence:** RGB only vs RGB + numeric geometry summaries vs RGB + summaries + overlays; preserve the underlying available inputs and label exactly what each worker sees.
2. **Routing:** fixed cheap model vs cheap-plus-strong escalation vs three-tier cascade; compare threshold policies at matched budgets.
3. **Specialization:** Qwen spatial interpretation vs HiSpatial, with numerical fitting held fixed; separate MoGe/Pi3X adapter effects.
4. **Asset backend:** retrieval/primitive-only vs conditional SAM 3D vs conditional Hunyuan, using the same objects, input evidence, fitting, and generation budget.
5. **Compression:** full relevant evidence vs selected views/crops vs aggressive compression; measure small-object and critic false-acceptance regressions.
6. **Caching/hosting:** cold vs warm artifact/prompt caches; API vs local serving; include model loading and utilization.
7. **Precision:** supported full-precision vs quantized local workers, after identifying a useful base model.

Avoid the full Cartesian product. Screen models on Stage A, advance the best two cheap configurations, then compare V1–V3. Run asset and physics expansion after the routing study is stable.

### Choosing a winner

Predeclare an acceptable quality loss relative to all-strong using development data. A discussion starting point is at most 2 percentage points of F1 loss, no material tiny-object recall regression, and no increased invalid-scene rate; these are proposed tolerances, not established thresholds. Assess paired uncertainty rather than declaring equivalence from a nonsignificant difference.

Among eligible variants, choose the lowest total cost; report latency as another tradeoff. A 30–50% cost reduction is a useful project target, not a forecast. If none meets the quality criterion, identify the failing task categories and retain strong routing there.

## 10. Implementation boundary and next decisions

Existing code provides typed scene state, input/label separation helpers, geometric matching, basic support/duplicate checks, bounded scene-state repair, and synchronous budget routing. It does **not** yet implement provider execution, a resumable scheduler, process isolation, source-render verification, the authored Blender export/apply bridge, or specialist generation queues. See [implementation boundaries](../docs/protocol.md) and [routing primitives](../src/agen3d/routing.py).

Suggested implementation order:

1. Complete canonical Blender scene export/apply and source-render validation, so accepted patches affect a real reconstruction.
2. Add task/evidence contracts, persistent usage records, and an exact model/provider registry; resolve the Astra/Fable endpoint aliases.
3. Connect one cheap VLM and the strong planner/judge through V1; run the task benchmark before broad autonomous editing.
4. Add atomic budget reservations, cache dependencies, recovery, and bounded local repair.
5. Use recorded failure/escalation traces to implement V3; integrate V2 spatial specialization only if justified.
6. Add conditional asset generation and later uncertainty-aware physics as separate experiments.

For discussion, my default choices are **OpenRouter first**, **8B and 30B-A3B as initial API candidates**, **4B as a local efficiency candidate**, **numerical geometry before spatial VLM calls**, and **one strong planner plus an independently prompted strong final judge**. The remaining practical inputs are actual strong-model endpoints/prices, available GPU(s), and an acceptable per-scene pilot budget. None needs to be guessed to settle the architecture.
