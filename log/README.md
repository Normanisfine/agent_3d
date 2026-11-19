# Research log

Keep this folder as the durable memory of what was planned, attempted, spent, and learned. It is separate from `outputs/`, which holds bulky generated artifacts. Never put API keys, raw benchmark labels or private images here.

- `journal.md`: dated decisions, implementation progress and unresolved questions.
- `experiments/`: one small JSON record per experiment. Start from `experiment.template.json`; use a unique filename and preserve failed runs.
- `costs.jsonl`: append one JSON object per paid call or measured compute stage. Initially empty: no Agen3D experiments have run.
- `cost.template.json`: fields to capture for each cost event; null means unknown or not measured.

Use UTC timestamps for execution events and immutable experiment IDs such as `20261115-thor301-b0-seed6220`. Link output directories instead of copying results here. Keep model input/output tokens, GPU time, render/segmentation time, retries, hardware, prices and pricing date. Unknown cost is never silently counted as free. Record whether GPU cost uses rental time, active seconds or amortized ownership and avoid billing the same shared GPU time twice.

Mark status as `planned`, `running`, `completed`, `failed` or `cancelled`. “Completed” requires artifact paths and validation notes; a successful process exit alone does not establish research quality. Update the journal after each attempt, including failures and rejected repairs. Agent reconstruction must not read evaluation-bearing experiment logs during held-out runs.

Templates are intentionally plain JSON for easy manual editing. They are not consumed automatically by the reconstruction code. The current in-memory `CostTracker` is a routing primitive; persistent provider-event logging remains part of the future execution integration.
