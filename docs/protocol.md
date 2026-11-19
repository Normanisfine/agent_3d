# Data, evaluation and implementation boundaries

## Inputs and coordinates

Prepare selected RGB frames through `prepare-rgb`. Paths in a selection are relative to its JSON file. Preserve native frame IDs and measured timestamps; the example is a two-frame I/O example, not a valid 32-frame reconstruction experiment. AHa's reference builder uses video and its own frame selection: reconcile its `inputs.json` against the final manifest before any comparison. Never evaluate visibility from all captured frames when fewer were supplied.

Canonical boxes use metres, right-handed Z-up, full extents and a rotation matrix whose columns are local axes. THOR coordinates convert `(x,y,z)` to `(x,z,y)`; box axes are reconstructed from corner positions to handle handedness. An `alignment_id` is a declaration, not a fitted alignment. Establish the transform from predicted cameras/geometry independently of test object labels and record scale provenance before evaluation. No automatic alignment is provided. Oracle scale must be labeled separately.

AI2-THOR labels come from selected metadata and instance-color images; object presence in two selected masks is the initial visibility gate. Simulator `visible` flags are not used as projected coverage. This is a pixel-visibility protocol, not a measured occlusion fraction. Missing oriented boxes remain explicitly axis-aligned; do not pool these as uniformly oriented GT. Moving scenes require a temporal evaluator and are rejected when observed box positions change. Native CA-1M export remains to be implemented against acquired files; the adapter accepts validated canonical boxes, frame-bound visibility and annotation notes. Do not infer CA-1M semantic or physical labels.

## Separation

Store evaluator labels outside the RGB export. ReconstructionContext accepts frame IDs only, resolves symlinks, checks containment and verifies hashes. Denied attempts are retained on the context. This protects callers that use the capability API; it does not stop arbitrary Python or an agent's shell from opening files. Before agent execution, mount only RGB, approved checkpoints/tools and a writable run directory in a container, and do not mount evaluator labels. No process sandbox is implemented here. The CLI imports evaluator code only for explicit offline commands.

## Matching and denominators

Evaluate proposed, confirmed and ambiguous predictions; exclude rejected/missing objects. Apply category gates for THOR and class-agnostic matching for CA-1M. At each fixed IoU threshold, maximize one-to-one match cardinality, then IoU. Report unmatched IDs, center error, relative sorted-extent error and IoU distributions. Extent sorting makes the measure independent of equivalent box-axis permutations; orientation error is unavailable without symmetry conventions.

Area bins are [0,.001), [.001,.01), [.01,.1), [.1,1] of the source raster, using the largest selected-frame instance area. Undefined precision/recall and empty error samples are JSON null. Unannotated visible objects and excluded low-visibility GT can affect false positives; audit benchmark annotation coverage before interpreting precision. Do not silently suppress unmatched predictions.

## Current status

Implemented: typed scene/input/label artifacts, RGB export, THOR label conversion, normalized CA-1M importer, exact convex oriented-box IoU, one-to-one metrics, duplicate-track/support checks, bounded support translation with rollback, dated cost ledger and routing policy, read-only AHa reference command planner, offline CLI and synthetic tests.

Not yet implemented: automatic AHa authored-scene export/apply bridge, native CA-1M decoder, camera alignment estimator, silhouette/depth render verifier, live model providers, persistent resumable model orchestration, generated-asset queue, full report/aggregate plotting, or process isolation. Support repair is a diagnostic scene-state operation, not a validated improvement to an editable Blender reconstruction. B3/B4 are policy primitives and experiment plans, not connected model runs. Dependencies are pinned direct requirements, not a resolved transitive lockfile.

Tests are supplied but deliberately unrun. No baseline or scientific result was produced in this implementation session.
