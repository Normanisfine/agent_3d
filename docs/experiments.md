# Proposed experiments — not run

## First: validate the measurement path

Run the synthetic tests after execution is authorized. Check exact boxes, disjoint/contact boxes, rotation, missing/duplicate instances, wrong categories, class-agnostic matching, frame binding, visibility, path traversal and rollback. Then manually audit a handful of THOR boxes against instance masks, including the coordinate reflection. Resolve metric scale and capture alignment before collecting scores.

## Pilot 1: reconstruction quality (B0/B1/B2)

Use three development scenes per dataset, initially two room layouts plus a cluttered small-object scene. FloorPlan301 has accessible RGB and withheld references; FloorPlan209 and CA-1M 42897538 are historical demonstration scenes and should be treated as development-only. Select additional scenes after access/coverage audit. Use 32 identical RGB frames with both trajectory endpoints. Freeze native frame IDs, timestamps, AHa commit, model revisions, prompts, recipe, hardware and seed (6220).

B0 preserves AHa's existing workflow. B1 adds a fixed rubric: inventory supported by observed frames, stable instance IDs, explicit uncertain hypotheses, extent/placement checks and unresolved issues. B2 adds deterministic verification with at most three accepted local interventions and 0.10 m maximum translation per intervention. Those are initial development settings, not calibrated thresholds. Add source-render checks before claiming geometric improvement from support snaps.

Primary outcomes: F1 at box IoU .25, all three IoU thresholds (.1/.25/.5), small/tiny recall, center-error distribution, failures and total cost. Compare paired per-scene changes; include unsuccessful scenes. Keep input geometry fixed when isolating the effect of the critic. Do not iterate using held-out labels.

## Pilot 2: routing efficiency (B2/B3/B4)

Only after Pilot 1 is reproducible, connect one open-VLM endpoint and one strong-model provider. B3 uses the open worker for routine judgments; B4 escalates unresolved low-confidence cases. Include all-strong and all-cheap controls. Calibrate confidence on development scenes; model self-confidence is not a calibrated probability. Set monetary caps and dated provider/GPU prices before starting; a null budget in the config means undecided, not unlimited.

Measure charged tokens (including failures/retries), active GPU seconds for all stages, segmentation/rendering time, wall time and peak memory. Avoid double-counting GPU billing when multiple processes share a rental. Compare quality at matched total budgets and cost to a quality threshold fixed from development data, not selected afterward from test results.

## Expansion

After the pilot, aim for 20–30 scenes/captures per dataset, split by physical room and freeze the split manifest. Repeat a stochastic subset with three seeds and use paired scene-level bootstrap confidence intervals. Keep expensive asset generation (B5) separate from routing comparisons. Physics (B6), robot replay and BEHAVIOR remain future work.

## Historical evidence

The two existing dashboards describe a CA-1M coffee-table physics pilot and a THOR laptop/contact demonstration. These motivate uncertainty-aware evaluation; they do not supply B0–B4 recall, pose or cost measurements. Preserve their scene IDs, assumptions and original provenance in the paper.
