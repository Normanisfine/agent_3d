# Project journal

## 2026-11-15 — Initial structure and offline harness

Request: implement the geometry-grounded, cost-aware research idea in `agen3d`, keep the layout simple, preserve the friend's `smallobj-video2blender` project, propose experiments before running them, add academic paper sources, explanatory README/code comments, and a durable experiment/cost log.

Decisions:
- Reuse shared datasets, checkpoints, environments, tools and the AHa checkout in place. No migration or upstream edits.
- Inspect AHa entrypoints and write the repository audit first. Its reference builder and recipe runner are distinct; do not invent an automatic authored-scene API.
- Implement offline schemas, selected RGB export, annotation conversion, oriented-box matching, conservative support repair and cost-routing primitives.
- Keep native CA-1M decoding, Blender scene export/apply, source-render verification and live model orchestration explicitly pending.
- Prepare synthetic tests without executing them. No reconstruction, simulator, model inference, paid calls or benchmark experiments were launched.
- Draft the academic paper using the supplied idea and local historical dashboards. Historical physics trials are not new Agen3D results. On the user's later request, compile the paper PDF and inspect its layout; this is the only requested build execution.

Cost: no experiment charges recorded. Assistant-session billing and CPU compilation cost are unavailable; do not infer a zero total project cost.

Next: review the layout and pilot protocol; authorize offline tests and a small measurement-path audit; resolve scene export, alignment and native real-data annotations before B0/B2 runs. Budget and provider prices remain unset.

## 2026-11-15 — Existing reconstruction results added to paper

At the user's request, inspected the companion `smallobj-video2blender` project read-only. Added its metric definitions, three-scene/five-arm frozen test results, pooled versus macro recall, API-equivalent resource summaries, older ten-scene context, and generation/acceptance limitations to `paper/reconstruction.tex`. Preserved attribution and separated these A-series runs from unexecuted Agen3D B-series plans. Recorded source paths and a summary hash in the paper evidence files.

Recompiled the paper to eight pages using the existing TeX installation and visually inspected all pages. No experiments, model calls or tests were run; the companion project remains unchanged. Historical dollar figures were not inserted into Agen3D's own cost ledger because they are API-equivalent estimates from earlier work, not new charges.

## 2026-11-15 — Full research blueprint incorporated

Read `idea/chat.md` supplied by the user after the shared chat links could not expose conversation content. Revised the paper around the verifier-driven, cost-aware multi-agent research question. Added a proposed architecture diagram, worker contracts, model/hosting candidates, conditional generation, uncertain physics estimates and staged simulation validation. Preserved primary AI2-THOR/CA-1M scope and all existing A-series measurements, with proposed B-series experiments clearly separate.

Compiled the revised PDF to 11 pages, checked the final compiler log (no warnings/overfull/underfull boxes), and visually inspected all pages. Source interpretation and scope choices are in `paper/evidence.md`. No experimental execution or new cost measurements; no writes to `smallobj-video2blender`.

## 2026-11-15 — Keep Evan's reconstruction evaluation only

User clarified that they have not yet worked on reconstruction evaluation and asked to retain Evan's protocol. Updated abstract, contribution framing and evaluation/results sections accordingly. Removed the alternative proposed evaluation protocol and empty results table; retained Evan's metric definitions and saved measurements. Future verification/routing remains explicitly future work. No code changes or experiments. Recompiled the paper to 10 pages and visually inspected all pages; no final LaTeX warnings.


## 2026-11-16 — Original AHA diagnosis logged

At the user's request, profiled the original FloorPlan209 session rather than
extrapolating from the failed multi-agent wrapper. Findings and reproduction code
are in [diagnose/DIAGNOSIS.md](../diagnose/DIAGNOSIS.md); the detailed experiment
record is [20261116-original-aha-diagnosis.json](experiments/20261116-original-aha-diagnosis.json).
The diagnosis was originally recorded under `diagnose/`; this journal entry is a
retrospective durable project-log entry.

Recovered the 42.11-minute timeline, repeated evidence/review coverage failures,
and compaction usage omitted by the earlier cumulative-counter summary. The
identity-only intervention reproduced the baseline then changed D correctness
from 8/34 to 14/34 and IoU correctness from 7/34 to 11/34 without editing geometry.
This is representation/evaluation evidence, not improved visual fidelity. Five
diagnosis tests passed; no model calls or new room reconstruction were launched.

## 2026-11-16 — Diagnosis-led AHA version and offline validation

Implemented a new [aha_diagnosed](../src/agen3d/multiagent/archive/aha_diagnosed/README.md)
folder, preserving `aha`, `aha_driven`, `aha_next`, historical scenes and upstream.
Added explicit source-derived instance intent/support declarations; strong expressive
construction; bounded complete per-image local reviews; exact-revision review reuse;
completion-order parallel merges; and blocked-review handling that retains geometry
rather than reconstructing after an evidence/schema failure. Optional cheap triage
can request repair, but a cheap pass still requires strong review. It is off by default.

Validation: 33 unit/regression tests passed. Two offline real-Blender integration
checks committed four fixtures with three workers, preserved seed objects and had
zero fallback; the final check retained four bound review receipts. Fixture model
responses and mock focus evidence do not assess reconstruction quality. No paid
model calls or full-room job were launched. CPU/host and assistant-session costs
remain unknown; they are not logged as free.

The final native whole-room review and evidence rendering remain unchanged. This
version does not yet solve final-packet size, render reuse, or demonstrate live
quality/cost improvement. Next: compare instance coverage and exact review failures
on a bounded real task, then run matched strong-only versus cheap-triage trials.
Details: [offline validation record](experiments/20261116-aha-diagnosed-offline-validation.json).


## 2026-11-16T22:35:00.940824+00:00 — Live run launch blocked

User requested `aha-diagnosed-20261116T223340Z`. Automatic approval review rejected process creation because explicit external image/context transmission authorization was required. No model calls or reconstruction ran; the experiment remains planned with launch_status=blocked_by_automatic_approval_review. Configuration snapshot and experiment record are retained.


## 2026-11-16T22:41:38.120756+00:00 — Live diagnosed run started

User requested one run: `aha-diagnosed-20261116T223340Z`. Strong construction/review; cheap triage disabled. Fresh output: `/home/mj/dl_project/agen3d/recon/ai2thor_floorplan209/aha-diagnosed-20261116T223340Z`. Existing budget exemptions retained.

User explicitly authorized the Codex image/context transfer; host launch succeeded. Startup checks and the instance plan passed: 43 declared instances, 23 tasks, five existing structural roots preserved. Construction began with fit_openings. Authorization receipt: `/home/mj/dl_project/agen3d/recon/ai2thor_floorplan209/aha-diagnosed-20261116T223340Z/launch-authorization.json`.

Run `aha-diagnosed-20261116T223340Z` finished at 2026-11-16T22:49:18.758860+00:00: failed / blocked_construction. See `/home/mj/dl_project/agen3d/recon/ai2thor_floorplan209/aha-diagnosed-20261116T223340Z/report.json` and `/home/mj/dl_project/agen3d/recon/ai2thor_floorplan209/aha-diagnosed-20261116T223340Z.log`. Layout validation is separate from full delivery acceptance; unknown costs remain unknown.


## 2026-11-16 — Diagnosed v2 scope and scheduling fix

The failed opening task requested cuts in room_walls and wall_wainscoting while declaring them read-only. All three recorded programs reproduce the failure under their original scopes; all three pass construction and fresh-reopen checks with explicit wall-edit scopes, unchanged build code. This does not validate visual quality. New code is isolated in src/agen3d/multiagent/aha_diagnosed_v2. It adds explicit existing-root edit scopes, saves detailed scope differences, stops geometric retries on scope failures, and separates exclusive execution ordering from semantic success dependencies. The recorded corrected plan allows build_rug, build_ceiling_fixtures after an opening failure while blocking true wall dependents. Offline integration: four commits, three workers, zero fallbacks, zero hosted calls. Unit/regression checks: 55 passed. Old implementations and failed run preserved. Evidence: diagnose/results/aha-diagnosed-v2-scope/.


## V2 launch blocked by automatic approval review

Prepared aha-diagnosed-v2-20261116T232702Z; no process or model calls launched. Reviewer requires explicit payload/destination authorization despite prior authorization receipt. Configuration and planned experiment retained.


## 2026-11-16T23:30:16.392218+00:00 — Live diagnosed run started

User requested one run: `aha-diagnosed-v2-20261116T232702Z`. Strong construction/review; cheap triage disabled. Fresh output: `/home/mj/dl_project/agen3d/recon/ai2thor_floorplan209/aha-diagnosed-v2-20261116T232702Z`. Existing budget exemptions retained.

Run `aha-diagnosed-v2-20261116T232702Z` finished at 2026-11-16T23:47:23.128295+00:00: failed / blocked_construction. See `/home/mj/dl_project/agen3d/recon/ai2thor_floorplan209/aha-diagnosed-v2-20261116T232702Z/report.json` and `/home/mj/dl_project/agen3d/recon/ai2thor_floorplan209/aha-diagnosed-v2-20261116T232702Z.log`. Layout validation is separate from full delivery acceptance; unknown costs remain unknown.
