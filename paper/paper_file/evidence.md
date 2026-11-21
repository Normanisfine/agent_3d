# Evidence used in the draft

Read locally; the dashboards and original experiment artifacts were not modified.

- `../../dl_project_dashboard/README.md`, `../../dl_project_dashboard/assets/evidence.json`: FloorPlan209, AHa-3D authored_v8, uncalibrated scale; laptop 2 kg and friction manually assigned; kinematic pusher, not robot control; displacement with physics 0.0552871711 m.
- `../../progress-dashboard/README.md`, `../../progress-dashboard/overview.html`, `../../progress-dashboard/assets/coffee-evidence.json`: CA-1M 42897538, AHa-3D A2 meshes; six dynamic bodies and fixed table; uniform/average/spatial rest configurations pass; force-condition plate displacements 14.0691678971 / 14.6970385686 / 14.6886063740 mm. Eleven selected trials, with additional pose/friction conditions.
- `../../idea/agen3d.md`: research hypotheses and intended B0–B6 progression. This is a proposal, not experimental evidence.
- `../docs/repo_audit.md`: inspected upstream entrypoints and implementation revision.

The two dashboards largely report the same historical work; they are not independent replications. Neither supplies Agen3D reconstruction metrics, complete model-call cost comparisons, or measured physical ground truth. Historical simulation outputs were not independently revalidated. Do not present dashboard render replays as new simulator recordings.

Before submission: verify bibliography metadata, dataset release/terms, final scene splits and exact sampling; add quantitative results and uncertainty only after running the planned study. Review all claims against persisted artifacts.

## Added reconstruction evidence — 2026-11-15

Read `../../smallobj-video2blender` at the user's request; no files in that project were modified and no experiments were rerun.

- `results/test_opus/summary.json`: source of the pooled and equal-scene-weight D recall and mean wall-time/API-equivalent cost tables. The paper values were recalculated from saved counts/per-run summaries, not copied from rounded prose.
- `results/test_opus/README.md` and `runs.md`: three scenes, five arms, seed 0, driver, original workflow limits, audit and restart history, acceptance outcomes, generation attempts/acceptances/retention and alignment diagnostics.
- `configs/thresholds.json`, `src/smallobj/evaluate.py`, `score.py`, `align.py`, `report.py`, and `scripts/report_checkpoint.py`: frozen distance/IoU criteria, greedy one-to-one pairing, physical-size bins, full retained-GT denominator, visibility diagnostic and GT-camera-based scale alignment.
- `configs/prompts/A0.md`, `A3r.md`, `A3v.md`: reconstruction scope and rule/agent-selected generation policies.
- `results/test_a1/README.md`: older ten-scene Codex cohort, reported separately because runtime rules and coverage differ.
- `results/dev_opus/README.md`: same-video access issue in development A3v; not used as independent comparative evidence.
- `results/checkpoint/summary.md` and `results/phase2_dev.md`: development history and protocol revisions; their pre-freeze numbers are not pooled with frozen test results.

The A-series study is prior companion-project evidence, not an Agen3D B-series result. Do not reinterpret API-equivalent costs as billed totals, Sim(3)-corrected geometry as recovered RGB metric scale, or physical-size bins as projected-area bins. The saved test archive reports audit passes; these audits were not independently repeated here. `existing-results.json` records the numeric extraction and source hash for review.

## Research blueprint incorporated — 2026-11-15

Source: `../../idea/chat.md`, the user's local export of the planning conversation previously shared through inaccessible ChatGPT links. Treated as research intent and design proposals, not as an independently verified literature source.

Changes in the manuscript:
- Introduction: central question and H1/H2/H3; evaluation/repair and cost-aware orchestration are primary, physics/robotics is downstream validation.
- `architecture.tex`: shared scene state, specialized tool workers, strong chief, local repair/escalation, revision-aware edits and a labeled proposed-system diagram.
- Routing: candidate open/spatial VLMs and chief roles, shared hosting, measured memory/latency and full accounting; no unverified GPU capacity, cloud price, publication venue or checkpoint-availability assertions copied from the chat.
- `completion.tex`: retrieval/procedural-first generation, constrained placement and validation; uncertainty in physical parameters and five levels of physics/robot evaluation. The reported 3.13 kg tissue estimate is a diagnostic example, not a measured error against mass GT.
- Evaluation: AI2-THOR + CA-1M remain the primary reconstruction datasets following `idea/agen3d.md`; VisionSIM is optional diagnostics, ReplicaCAD a later physics candidate, and robot benchmarks later evaluation directions.
- Experimental naming: chat E0–E6 maps to proposed B0–B6; existing companion-project A-series results remain separate. Added the cheap-worker/no-critic control and fixed-driver rubric comparison.

Scope reconciliation: the chat proposes a 5% medium/large projected-area boundary; the existing Agen3D draft/harness uses 10%. This revision preserves the existing 10% proposal for consistency rather than silently changing evaluation code. These are development choices to freeze before new execution, not claimed community standards. The companion project's physical-size bins and legacy thresholds are unchanged.

No models, simulations, reconstruction experiments or tests were executed for this revision. Only document compilation and PDF rendering/inspection ran. The friend's reconstruction project was not modified.

## Current reconstruction-evaluation scope — supersedes earlier draft choices

At the user's explicit request, the paper now retains only Evan's existing reconstruction evaluation and archived results. The attribution to Evan follows the user's clarification; the bibliography retains the team attribution printed in the source repository. Removed the proposed Agen3D maximum-cardinality/IoU protocol, projected-area bins, visibility-filtered denominator, and empty F1/results table from the manuscript. Existing physical-size bins, I/D criteria, greedy matching, alignment and numerical results are unchanged.

Verification, routing and later generation/physics remain future system directions. They are not presented as a new completed evaluation contribution. This is a paper-scope correction: experimental code/configs in agen3d were not deleted or altered, and the friend's repository was not modified.

## Automated scheduler implementation evaluation — 2026-11-16 UTC

The automated wrapper is no longer the unchanged serial baseline described in
an earlier draft. `design/designv2.md` section 12 and `architecture.tex` describe
the new dependency/capacity stage, isolated parallel builds, serial semantic
merges, concurrent reviews and overlap-aware host accounting.

- `../recon/parallel-capacity-20261116-01/capacity.json`: 32 effective CPUs,
  approximately 48.10 GiB available RAM, and RTX 5090 diagnostics at measurement
  time. A small synthetic Blender probe selected four builds; model concurrency
  was capped at four by configuration, not derived from provider benchmarking.
- `../recon/parallel-evaluation-20261116-04/evaluation.json`: four independent
  fixture builds against the preserved FloorPlan209 shell; 11.323 s serial and
  6.625 s with four workers (1.709x). Both arms made four deterministic proposal
  calls, committed four fixtures, preserved pre-existing semantic signatures and
  reviewed cameras through real Blender validation, and had zero serial fallbacks.
  Each fixture proposal intentionally slept for 2 s. Visual reviews were stubbed.
  This single fixture run does not establish reconstruction quality, real API
  speed, statistical significance, or token savings.
- `scheduler-evidence.json`: copied numeric records with source SHA-256 hashes.
- `../recon/ai2thor_floorplan209/aha-20261116T004232Z/report.json`: failed serial
  run, 915.742 s, shell committed and door task exhausted repairs. Dependent tasks
  were blocked. Not an accepted reconstruction or a matched performance baseline.
- `../configs/multiagent/aha.floorplan209.parallel-eval.json`: live continuation
  configuration using the old reviewed shell and reference, new planning, the
  same configured models and a new $5 paid-API budget. The attempted live
  continuation was stopped at the user's request before a plan or construction
  tasks were produced. `stopped.json` preserves this outcome; pending model
  charges remain unknown. No full live evaluation was completed or restarted.

No changes were made to Evan's historical metrics, protocols or numeric results.
Full-room quality and cost per accepted reconstruction remain unestablished.

Final targeted verification: 75 tests passed, including the separate agent-driven
interface compatibility tests. The paper PDF was rebuilt and changed pages were
visually inspected; no overfull boxes were reported by the final LaTeX pass.


## Course-report revision — November 15, 2026 (local time)

This entry supersedes earlier format/scope notes above. The report now uses NeurIPS
2025 style with eight content pages and references starting on page nine. The
November 2 checkpoint at `../../checkpoint_report_nov_2.pdf` was read in full;
its author order, physics protocol and historical results anchor this revision.
The separate team/archive bibliography item was removed at the user's request,
while Evan's attribution and source provenance remain here and in the report.

Exact metric equations were checked against:
- `../../smallobj-video2blender/src/smallobj/evaluate.py`, `align.py`,
  `visibility.py`, and `configs/thresholds.json` (read-only).
- `../../runs/coffee-vomp-20261028/scripts/simulate.py` and `summarize.py`
  (read-only): drift starts at index 480; pulse displacement uses index 719;
  final-second speed uses the last 240 states; support uses final vertex bounds,
  strictly positive XY overlap and absolute clearance below 2 mm.
- `../../progress-dashboard/assets/coffee-evidence.json`: mass 3.129024183282729 kg,
  mean density 1016.683136543954 kg/m^3, voxel coverage and simulation results.
- `../../idea/chat.md`: user-recorded Astra judgment that the tissue mass was
  implausible. This is qualitative provenance, not an independently audited agent
  transcript or physical ground-truth label.

Physics remains a completed integration/pilot, with future calibration clearly
separate. AHA-auto and AHA-agent-driven are implemented controllers; no completed
matched full-room cost/quality comparison is claimed. Neither prior simulation
nor reconstruction was rerun for this revision. Historical numeric tables remain
unchanged. Scheduler fixture numbers come from `scheduler-evidence.json`.

Primary references verified against Apple/CVPR (CA-1M), NVIDIA's official VoMP
project page/ICLR citation, the AI2-THOR arXiv record, and AHa-3D's repository.
The user's course requirements were supplied in the conversation; fetching the
course URL failed. Writing guidance was read at:
- https://www.alignmentforum.org/posts/eJGptPbbFPZGLpjsp/highly-opinionated-advice-on-how-to-write-ml-papers
- https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005619
Template retrieval/provenance is documented in `README.md`.

## Research-question and dataset clarification

At the user's direction, title, abstract, introduction, experiment headings, discussion
and conclusion now separate small-object reconstruction, execution efficiency and
cost. Added AI2-THOR/FloorPlan209 and CA-1M dataset descriptions. Running-job status
is user-reported; the parallel AHA-auto/AHA-agent-driven table contains placeholders,
not newly collected results. Both controllers retain parallel-build capability.
Rebuilt and visually checked: eight content pages plus references, no overfull boxes
or unresolved references. Exact metric equations and archived numerical results retained.

## Monitored transport correction — 2026-11-16 UTC

`../recon/ai2thor_floorplan209/aha-parallel-20261116T012253Z/stopped.json`
records an interrupted live pilot: three routine Qwen calls echoed input packets
and hit the 8,000-token output cap under generic JSON-object mode. No accepted
room resulted. The hosted transport was changed to supply the response schema
explicitly, and duplicated camera matrices were removed from builder context.
`../recon/qwen-schema-probe-20261116-01/calls/` retains a successful capped schema
probe (reported API charge $0.0001764). Local output and geometry validation remain
mandatory. These observations establish a concrete failure/fix, not comparative
reconstruction quality. The subsequent run is a new continuation with separate
accounting; all failed-attempt costs must be retained in any aggregate comparison.

The next monitored continuation,
`../recon/ai2thor_floorplan209/aha-parallel-20261116T013143Z`, was also stopped:
three routine build responses began with the correct proposal fields but repeated
import text inside the code string until the 8,000-token cap, leaving invalid JSON.
The small schema probe therefore does not establish construction readiness.
Both controllers inherit the same provider contract; agent-driven explicit packets
now also share the compact inventory/helper instructions. A representative build
validation is still required. No accepted room or end-to-end efficiency gain was
established by these attempts.

## Diagram and visual evidence revision

Replaced the native text-box diagram with a programmatically drawn SVG/HTML/PNG
for Section 3.3. Added original checkpoint/dashboard AI2-THOR source and historical
reconstruction images; CA-1M A2 frame 616 source/whitebox/materials comparison; and
coffee-table replay plus cropped tissue density visualization. The new figure is
schematic, not a trace of a completed job. Other images are archived evidence,
not outputs of running AHA-auto/AHA-agent-driven jobs. The CA-1M appearance pass
preserves geometry; the physics still is a Blender replay of recorded Isaac poses.
No images were generated by an AI image model. Sources and crop coordinates are
recorded in `figures/provenance.json`; unchanged copies have matching hashes.

Removed Agen3D branding from the title and reframed the abstract around agentic
scene reconstruction. Removed repetitive prose to retain eight content pages and
all exact evaluation equations. Four figures and five tables are included.

## Small-object study in the report, November 19, 2026

- The introductory FloorPlan209 example uses the unaccepted original reconstruction. Its distance-and-size counts are in `../../recon/ai2thor_floorplan209/aha3d_ori/eval/objects_sim3_all_objects.csv`. The identity-only change from 1/18 to 4/18 below 0.5 m comes from the per-instance baseline and split rows in `../../diagnose/results/identity-ablation-20261116/identity-ablation.json`. Time to handoff comes from `../../diagnose/results/original-profile-20261116-v2/profile.json`.
- The A2 design motivation uses the pre-freeze three-room development comparison in `../../evan/results/phase2_dev.md`. The workflow variants and run-time gate are documented in `../../evan/configs/prompts/` and `../../evan/src/smallobj/place.py`.
- Both CA-1M result tables use `../../evan/results/test_opus/summary.json`. For the S-bin count table, multiply each archived `recall_D` and `recall_I` by its corresponding `n` under `recall_pooled[arm][alignment]["S"]` and round to the nearest integer. The fitted-scale D counts also match `funnel_D[arm]["S"]["correct"]`. The development protocol, FloorPlan209 identity split and scheduler fixture are separate comparisons.

## Small-object additions, November 20, 2026

No reconstruction, simulation or model call was run for these additions.

- Outcome table, instance counts, accepted-run counts and driver usage: `figures/extract_outcomes.py` reads `../../evan/results/test_opus/summary.json` and `runs.md` and writes `small-object-outcomes.json`. Matching is one-to-one, so the number of matched instances equals the number of matched targets.
- Revised inventory: `../../evan/results/inventory_v2_dev.md` (step-by-step scores on five development rooms) and `inventory_v2_chance.md` (random-shift control). Both are copied from the `scenerig-detection` branch of `smallobj-video2blender` at commit 97d1837; the code (`src/smallobj/tiles.py`, `labels.py`, `hd.py`, `settle.py`, `clean_inventory.py`) is on that branch and not in `evan/`, which mirrors `main`.
- The "18% to 40%" figure leaves out room 47331319 and comes from the per-room rows of `inventory_v2_dev.md`: (4+9+6+0)/104 and (8+12+19+3)/104.
- The random-shift control was run on the inventory before the support and shared-size step.
- Sign-flip bound in the Discussion: three paired rooms give 2^3 sign assignments, so the smallest two-sided p-value is 2/8.
- SceneRig, SAM 3 and MoGe-2 titles and author lists were checked against their arXiv abstract pages on November 20, 2026.
- These edits were test-compiled with tectonic (pdflatex is not installed on Evan's laptop): the main text ends on page 8, with the last line of the Conclusion near the bottom. `main.pdf` and `build/` were left as they were; run `make pdf` to rebuild them and confirm the page count under pdflatex.
- Unmatched reconstructions: Yifan checked all 63 against the video on November 20 (`../../evan/results/unmatched_audit/`: `answers_yifan_20261120.json`, `index.json`, summary in `README.md`). A model's first-pass guess agreed on 55; the human label is used for all. Counts: 22 unannotated, 27 misplaced or mis-sized, 5 duplicates, 9 absent.
- Later on November 20: the per-room bar chart (former Figure 4) was replaced by one sentence giving the same nine counts, the subsection was retitled, and "our method" in its first sentence now names the Inventory variant. `figures/ca1m-placement-by-room.pdf` is no longer included. With tectonic the main text then ends partway down page 8.

## Six rooms and the Checklist variant, November 21, 2026

New reconstruction runs were made for these additions (driver Claude Opus 5.5 at medium effort, reviewer and scoring protocol unchanged, one seed).

- Six-room outcome table, paired-difference table, instance counts, run time and cost: `../../evan/results/test_opus_6rooms/README.md` and `summary.json`, written by `scripts/report_rooms.py` in `smallobj-video2blender` from each run's `score_sim3.json` and `run_log.json`. Rooms 1 to 6 are 42897538, 42898849, 42899617, 42899712, 42899729 and 44358442; the first three are the rooms of the five-variant comparison, and the other three are the next three in the ID-sorted test queue. Run time excludes time spent waiting for a quota window.
- Checklist variant: prompt `configs/prompts/A5.md` and merging thresholds `configs/checklist.json` (IoU 0.4, center within 0.2 of the shorter diagonal), frozen at git tag `a5-frozen` after one trial on development room 47331262 and before any held-out Checklist run or any scoring of the revised inventory on held-out rooms.
- Random-shift control, unmatched instances, the agent's per-entry decisions and held-out inventory scores: `../../evan/results/test_opus_6rooms/checks.md`, written by `scripts/test_checks.py`. The control moves every reconstructed instance 0.5 to 1.5 m horizontally, 20 draws; Checklist keeps 1.2 + 2.5 correct placements under 50 cm on average.
- "286 against 182": matched targets under 50 cm are correct plus misplaced in the two smallest size groups (Checklist 50+65+92+79, Inventory 36+22+65+59).
- Postcards and tree ornaments: counted from instance names among Checklist's unmatched instances (168 `postcard_*` in room 6, 108 `ornament-tree-*` in room 2). They were not checked one by one against the video.
- Excluded run: the first Checklist run in room 2 (November 21, 09:47) finished without a single external image review because both reviewer accounts had hit their usage limits. Rule: a run whose review never ran for quota is excluded and repeated; all other six-room runs were scanned and none met it. Its scores (6/116, 30/142 under the two smallest groups) are kept beside the repeat (7 + 26 = 33).
- The three-room recall chart (`figures/ca1m-recall.pdf`, former Figure 3) was removed from the text to stay within eight pages; the six-room outcome table reports the same size groups. The file and `figures/plot_ca1m.py` are kept.
- The inventory table lost its "+ zoomed windows" row (760 entries, 28% / 13% and 70% / 40%); the next row now adds windows and room-specific categories together. The full table is in `../../evan/results/inventory_v2_dev.md`.
- Test-compiled with tectonic: the main text ends on page 8 with about a sixth of the page free. `main.pdf` and `build/` were not rebuilt.
- Second Checklist run (added November 22): seed 1 of the same six rooms, same prompt, checklist and settings, run November 21 15:55 to November 22 00:13. Counts are in the section on the two runs in `../../evan/results/test_opus_6rooms/README.md`: 155 of 543 under 50 cm (per room 15, 49, 7, 21, 13, 50) against 142 for seed 0 (18, 33, 5, 14, 11, 61), so the per-room change is -3, +16, +2, +7, +2, -11. Against Inventory (seed 0) seed 1 differs by +7, +27, -2, +5, +1, +16, total +54, sign-flip p = 0.094. Seed 1 averaged 113 minutes and $20.1 per room against 79 minutes and $13.3 for seed 0. The outcome and paired tables in the text use seed 0 only. All six seed-1 runs received external image reviews; in room 6 the full review packet (1,214 images) hit the reviewer's 600-second limit and the agent used reduced packets instead.
