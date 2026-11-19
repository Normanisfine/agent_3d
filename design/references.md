# Research log for designv2

Researched/accessed: 2026-11-15. These are primary project documentation and
papers consulted for [designv2](designv2.md). Project capabilities and published
results are not measurements of Agen3D. Repository URLs may change; pin revisions
when implementing adapters. No external code or model weights were downloaded.

## R1. AHA-3D

- Official repository: https://github.com/KevinXu02/aha-3d
- Project: https://kevinxu02.github.io/real2sim-indoor-site/
- Inspected local sources: `external/aha-3d/README.md`,
  `docs/REAL2SIM_PIPELINE.md`, `docs/SCENE_WORKFLOW.md`,
  `src/aha3d/blender/roomkit.py`, `src/aha3d/blender/cabinets.py`.
- Contribution: reference geometry is separate from the authored editable room;
  reuse assets, author missing geometry, preserve orientation/materials and stable
  roots, inspect source-linked renders before accepting.
- Limitation: this audit does not establish a fully automatic code-generation
  API or guarantee that importing its helpers reproduces its demonstrated quality.
  The local checkout, not an assumed latest online revision, informed code reuse.

## R2. LEGO-Anything

- Title: *LEGO-Anything: Coding Agents for 3D Scene Reconstruction*.
- Paper: https://arxiv.org/abs/2609.36380 (submitted 2026-09-28).
- Consulted: paper abstract and benchmark summary.
- Contribution: iterative Blender code execution, rendered inspection and program
  revision; separate artifact validity, geometry, and appearance. Reports weak
  initialization, regressive edits and unreliable self-evaluation.
- Design use: executable candidates, rollback and independent quality gates.
- Limitation: single-image benchmark findings do not demonstrate that our Qwen
  worker or multi-view room pipeline will achieve the same results. No reported
  performance numbers are used as an Agen3D forecast.

## R3. Thinking in Blender

- Title: *Thinking in Blender: Staged Executable Inverse Graphics with
  Vision-Language Models*.
- Paper: https://arxiv.org/abs/2606.02580 (submitted 2026-06-01).
- Consulted: abstract describing Staged Executable Inverse Graphics.
- Contribution: progressive geometry, material, composition and lighting edits
  in executable Blender code space.
- Design use: staged construction and render feedback.
- Limitation: its single-image method studies reconstruction without specialist
  foundation models; our hybrid proposal is an engineering inference, not that
  paper's tested architecture.

## R4. Qwen3-VL

- Official repository: https://github.com/QwenLM/Qwen3-VL
- README consulted: https://raw.githubusercontent.com/QwenLM/Qwen3-VL/main/README.md
- Contribution: available multimodal model sizes, grounding/video capabilities,
  and deployment documentation; includes Qwen3-VL-30B-A3B and 8B variants.
- Design use: one shared worker endpoint for bounded image-grounded tasks.
- Limitation: published capabilities do not establish Blender program reliability,
  calibrated judgment, endpoint availability, or quality parity with a strong
  model on our tasks. Current prices were not audited for this proposal.

## R5. Hunyuan3D-2.1

- Official repository: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
- README consulted: https://raw.githubusercontent.com/Tencent-Hunyuan/Hunyuan3D-2.1/main/README.md
- Paper discovered: https://arxiv.org/abs/2506.15442
- Contribution: image-conditioned shape generation and a separate PBR texture
  pipeline. README reports 10 GB VRAM for shape, 21 GB for texture, and 29 GB
  combined.
- Design use: selective object geometry generation after retrieval/procedural
  routes are unsuitable; start shape-only.
- Limitation: those memory figures are upstream claims, not local profiling.
  A generated asset has no automatic guarantee of correct room scale, pose,
  hidden geometry or cross-view identity. This is not a visual judging model.
  The current local adapter's pinned revision/API still needs a smoke test.

## R6. SAM 3D Objects

- Official repository: https://github.com/facebookresearch/sam-3d-objects
- README consulted: https://raw.githubusercontent.com/facebookresearch/sam-3d-objects/main/README.md
- Contribution: masked natural-image object reconstruction with shape, texture,
  pose and layout; documentation targets clutter and occlusion.
- Design use: a relevant future alternative if Hunyuan crop reconstruction fails.
- Limitation: not included in the first implementation. Its camera/layout outputs
  require common-frame validation, and checkpoint/runtime access is not established
  by this research. Existing adapter code is not proof of a working integration.

## R7. Infinigen Indoors

- Title: *Infinigen Indoors: Photorealistic Indoor Scenes using Procedural Generation*.
- CVPR 2024 paper page:
  https://openaccess.thecvf.com/content/CVPR2024/html/Raistrick_Infinigen_Indoors_Photorealistic_Indoor_Scenes_using_Procedural_Generation_CVPR_2024_paper.html
- Project: https://infinigen.org/
- Contribution: Blender procedural indoor assets and constraint-based arrangement.
- Design use: parameterized object construction and explicit spatial constraints.
- Limitation: generating plausible indoor scenes is different from reconstructing
  the specific objects in source images. No wholesale Infinigen integration is
  proposed for the first milestone.

## R8. Holodeck

- Title: *Holodeck: Language Guided Generation of 3D Embodied AI Environments*.
- Official project: https://yueyang.ai/holodeck/
- Paper: https://arxiv.org/abs/2312.09067 (CVPR 2024).
- Contribution: language-guided environment generation using retrieved assets
  and scene placement machinery.
- Design use: structured planning and retrieval as components of a scene builder.
- Limitation: text-guided plausibility does not establish source-image fidelity.
  Holodeck is a design reference, not a replacement reconstruction backend here.

## Local implementation/run evidence

- `src/agen3d/multiagent/pipeline/runner.py`: fixed stage sequence, selection
  calls, transform-only repair, and final review flow.
- `src/agen3d/multiagent/pipeline/geometry.py`: predicted masks/points to tracked
  objects and hulls; floor/world-basis estimates.
- `src/agen3d/multiagent/pipeline/blender_scene.py`: catalog imports/hull fallback.
- `src/agen3d/multiagent/specialist_worker.py`: existing Hunyuan/SAM 3D adapters.
- `src/agen3d/multiagent/tools.py` and `README.md`: tool boundaries and deployment
  history, including the earlier provider-capacity issue.
- `recon/ai2thor_floorplan209/v1/report.json`, `selected.json`,
  `reconstruction/assets.json`: saved statuses, timing, accounting, and representations.
- `design/multiagent_design.md`: previous routing-oriented proposal, superseded
  for forward architecture by `designv2.md`.

The new proposal does not claim a fresh visual re-review of every frame or a
new reconstruction benchmark. Its run findings above come from saved artifacts
and inspected code; model choices and scheduling policy remain hypotheses to test.

## Follow-up: AHA-first integration audit

Same access date, 2026-11-15. Local code inspected to refine the proposal around
AHA as the base, rather than another reconstruction engine:

- `external/aha-3d/tools/review_images.py`: Codex schema-constrained CLI wrapper.
- `external/aha-3d/src/aha3d/workflow/review_contract.py`: actual image attachment,
  revision/coverage checks, immutable outputs, and Codex-specific delivery receipt.
  Qwen/Claude need an explicit transport integration, not a renamed receipt.
- `external/aha-3d/src/aha3d/workflow/object_review.py`: saved-scene export and
  source/plan/side evidence with object-level provenance and coverage checks.
- `external/aha-3d/tools/layout_inspection/agent_review.py`: deterministic
  diagnostics and image packet creation, not an existing VLM worker.
- `external/aha-3d/src/aha3d/pipeline/runner.py`: `ensure_layout`, `review_layout`,
  and review-required stages; existing assembly requires authored scene inputs.
- `external/aha-3d/src/aha3d/blender/variants.py`: collection-based import,
  orientation checks, asset placement and replacement; generated GLBs require
  conversion/staging before this route.
- `external/aha-3d/tools/layout_inspection/build_reference.py`: source/bundle
  input contracts, 32/64-frame tiers, endpoint coverage and camera-basis handling.
- `external/aha-3d/docs/LAYOUT_INSPECTION.md`, `docs/SCENE_WORKFLOW.md`, and
  `TOOLS_AND_SKILLS.md`: documented per-object inspection and workflow entry points.

Design inference: delegate bounded decision-making to Qwen, supply selected
missing assets with Hunyuan, preserve AHA execution/gates, and let the supervisor
perform expensive reconstruction when serious defects require it. These are
proposed changes, not evidence of completed adapters or quality/cost savings.
