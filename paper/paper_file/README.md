# CIS 6220 report

The report uses the NeurIPS preprint layout. It has eight pages of main text and one page of references. Build the final PDF with `make pdf` here or `make -C paper/paper_file pdf` from the repository root.

## Code behind the small-object comparison

All five variants use the [same AHa-3D runner](../../evan/scripts/run_agent.sh). The table maps the names in the paper to the saved prompt templates and experiment identifiers.

| Paper name | Configuration | Change |
| --- | --- | --- |
| AHa-3D (baseline) | [A0](../../evan/configs/prompts/A0.md) | Ask for structure and major objects. Surface decor is optional. |
| All objects | [A1](../../evan/configs/prompts/A1.md) | Give every visible object a separate identity and build it with primitives or library assets. |
| Inventory | [A2](../../evan/configs/prompts/A2.md) | Add detector boxes and crops and handle each listed candidate. |
| Required generation | [A3r](../../evan/configs/prompts/A3r.md) | Add a required generation attempt for eligible inventory items under 50 cm, within budget. |
| Selective generation | [A3v](../../evan/configs/prompts/A3v.md) | Let the agent choose which inventory items to generate. |

The [inventory](../../evan/src/smallobj/inventory.py), [generation](../../evan/src/smallobj/gen3d.py), and [placement](../../evan/src/smallobj/place.py) modules implement the additional tools. The [evaluator](../../evan/src/smallobj/evaluate.py) defines the exact matching rules. The [held-out summary](../../evan/results/test_opus/summary.json) contains the run-level evidence.

## Figures and evidence

The camera comparisons and size-stratified recall chart are rebuilt from saved CA-1M images and scores. Run `../../.venv/bin/python figures/plot_ca1m.py` from this directory before rebuilding the PDF if their source data change. The plotting script records the source room, camera view and crop for each image. Figure 1 uses development rooms. The physics figure pairs a source frame and its Inventory reconstruction from a held-out room with the coffee-table simulation and tissue-box density field.

The CA-1M reconstructions and physical-property pilot come from the team's existing experiments. The scheduler timing uses real Blender builds with simulated model latency and scripted reviews. Table 2 compares original AHa-3D, AHA-auto + Inventory, and AHA-driven + Inventory on FloorPlan209. The [original and auto comparison](../../../agen3d_exp/06_aha_auto_inventory/aha-auto-inventory-retry-01/evaluation/comparison_with_aha_ori.json) and [driven per-object scores and token breakdown](../../../agen3d_exp/07_aha_driven_inventory_20261120_211635_1nCGwL/evaluation/evan_object_scores.json) supply the table. The driven total includes the outer supervisor, the runtime ledger and one reused reference review. Historical experiment details, study attribution and prior revision notes are retained in [the evidence notes](evidence.md). The [scheduler measurements](scheduler-evidence.json), [extracted recall and cost values](existing-results.json) and [other figure provenance](figures/provenance.json) are available for reproduction.

The [original run profile](../../diagnose/results/original-profile-20261116-v2/commands.csv) lists the nine `authored_build_and_stills` commands from v1 through v8, including the interrupted v1 build and its rerun. For the controller comparison, the 20 to under 50 cm subgroup is `20_to_50cm` in the original/auto comparison and `bin == "S"` in the driven rows. The [supervisor event log](../../../agen3d_exp/07_aha_driven_inventory_20261120_211635_1nCGwL/output/supervisor-OR6x367Z/events.jsonl) identifies the Codex thread and records its final token usage. In that thread's response-level trace (`01a1fbe4-9009-70b3-816a-3ccfd1135cb8`), 65 of 216 responses emitted a sleep tool call. Their usage receipts sum to 8,469,760 cached input tokens. Sleep duration itself carries no token charge.

## Template provenance

The official NeurIPS 2025 call links to the [style archive](https://media.neurips.cc/Conferences/NeurIPS2025/Styles.zip). The vendored May 1, 2025 version was retrieved from a [template mirror](https://github.com/AmitHeshes/topics_in_adversarial_attacks_on_deep_learning/blob/main/neurips_2025.sty). The main source sets a course footer and retains the template typography and margins.
