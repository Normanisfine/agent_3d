# Agen3D

Agen3D reconstructs indoor rooms from RGB walkthroughs and provides tools for scene geometry and evaluation. Start with the [room reconstruction guide](src/agen3d/multiagent/README.md) for video input, runtime requirements, and output files.

- [AHA-auto](src/agen3d/multiagent/aha/README.md) schedules object builds and repairs automatically.
- [AHA-driven](src/agen3d/multiagent/aha_driven/README.md) exposes build, review, and commit operations for a supervising agent.
- [Archived controllers](src/agen3d/multiagent/archive/README.md) includes the earlier reconstruction pipelines.

## Layout

```text
agen3d/
  recon/         Per-scene, per-method reconstructions and evaluations
  evan/          Preserved smallobj-video2blender code and saved results
  external/      Independent AHa-3D checkout (ignored)
  configs/        Small pilot plan and RGB selection example
  src/agen3d/    Room controllers, shared schema, and archived offline tools
  tests/         Offline behavioral and raw-input tests
  docs/          Repository audit, protocol, proposed experiments
  paper/         Academic LaTeX draft and bibliography
  log/           Experiment history, cost records and decisions
  outputs/       Other generated artifacts (ignored)
```

Use `external/aha-3d` for the AHa-3D source checkout. Reuse `../data`, `../checkpoints`, `../envs` and `../tools` in place. No root files were migrated. `../smallobj-video2blender` belongs to the separate project and is untouched.

Start with [repo audit](docs/repo_audit.md), [implementation boundaries](docs/protocol.md), and [proposed experiments](docs/experiments.md). The [paper](paper/main.tex) distinguishes the proposed study from prior dashboard demonstrations.

## External AHa-3D setup

From this directory, run:

```bash
python scripts/setup_external.py
```

The setup clones the upstream repository at the exact commit in
`external.lock.json`. The independent checkout under `external/` is ignored,
not vendored or a submodule. An existing checkout must match the pin; the setup
refuses to overwrite local changes or switch an existing revision. To upgrade,
review the new revision, update the lock, and explicitly update your checkout.

`agen3d plan-reference` defaults to this checkout regardless of the working
directory when using an editable install; `--repo` overrides it. The setup only
fetches source: AHa dependencies, checkpoints and local data require separate
setup. The RGB selection example still uses data in the original shared
checkout because those locally generated frames are not part of a Git clone.

## Python package

The room controllers live in [multiagent/](src/agen3d/multiagent/README.md). At the package root, `__init__.py` defines the version and `schema.py` provides their shared Pydantic base class.

The [offline tools](src/agen3d/archive/) contain the `agen3d` CLI (`cli.py`), reference command builder (`aha.py`), RGB export and file I/O (`datasets.py`, `io.py`), scene types and geometry (`scene.py`, `geometry.py`), scene repair (`verification.py`), budget routing (`routing.py`), and label export and scoring (`label_export.py`, `evaluation.py`).

## Lower-level geometry and evaluation commands

These commands expose individual harness steps; use the room reconstruction guide for a reconstruction job. Do not modify shared model environments.

```bash
cd agen3d
python -m pip install -e '.[dev]'
agen3d plan configs/pilot.json
pytest
agen3d prepare-rgb configs/ai2thor_selection.example.json outputs/inputs/example
agen3d verify path/to/scene_state.json outputs/issues.json
agen3d repair path/to/scene_state.json outputs/repair-001
agen3d export-labels ai2thor outputs/inputs/example/manifest.json \
  ../data/ai2thor/prepared/FloorPlan301/capture_v2 \
  outputs/evaluator/labels.json --alignment-id thor-world-v1
agen3d evaluate path/to/aligned_scene_state.json outputs/evaluator/labels.json \
  outputs/inputs/example/manifest.json outputs/evaluator/metrics.json
```

The two-frame input example only illustrates export; it is not the pilot selection. `plan-reference --help` describes construction of an existing AHa geometry command, without executing it. Scene state must be explicitly exported and aligned; copying an alignment label does not perform alignment. Evaluation files must not be mounted into future reconstruction agents.

## Experiment results

[Saved reconstructions and evaluations](recon/README.md) · [Evan’s experiments](evan/README.md)
