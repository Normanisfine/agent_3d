# AHA-auto

AHA-auto prepares a reference from the walkthrough, creates a Blender seed with the source cameras, and plans objects from the observed room. It schedules independent builds in parallel, merges them into one scene, and requests repairs when visual review finds a problem.

See the [room reconstruction guide](../README.md) for the launch command and inputs.

## Run outputs

- `report.json` records the job status, current scene, timing, and model costs.
- `tasks.json` records the result of each construction task.
- `construction-config.json` contains the prepared room inputs. Reuse it to build from the same reference with either controller and a new output directory.
- `handoff.json` identifies the reviewed scene. A `layout_validated` status means it passed final layout review.

If preparation finished and the job stopped at reference review, rerun the same command with `--resume-preparation` to reuse the prepared reference.
