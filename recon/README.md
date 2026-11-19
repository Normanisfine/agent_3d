# Preserved reconstructions and evaluations

Layout: `recon/<scene>/<method>/`. Original reference inputs and evaluator-only
GT live at the scene level; each method owns its saved reconstruction and evaluation.

- [FloorPlan209 / aha3d_ori](ai2thor_floorplan209/aha3d_ori/README.md): existing
  AHA-3D v8 scene, original RGB, recovered simulator labels and Evan's metrics.

Keep inputs, reconstruction artifacts and evaluation labels separate. Do not feed
`ground_truth/` into reconstruction methods. Preserve existing results; rerunning
an evaluation is separate from rerunning reconstruction.
