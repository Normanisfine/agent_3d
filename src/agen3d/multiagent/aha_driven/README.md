# AHA-driven

Start a session with the [room reconstruction guide](../README.md). The supervising agent chooses each task and when to commit it. Each command reopens the saved session.

For long commands such as `build`, `wave`, and `review`, set `yield_time_ms` to `30000` in `exec_command`. If it returns a running session, wait on that session directly with empty `write_stdin` calls and `yield_time_ms` set to `60000`. Skip the sleep between calls.

## Build an object

Use a source image ID from `session.json` and an object ID chosen for this room. For example, a task for a visible desk could be:

```json
{"task_id":"desk","object_ids":["desk_main"],"instruction":"Build the observed desk using the selected views."}
```

From the project root, use the paths and candidate ID returned by each command.

```bash
driven() { .venv/bin/python -m agen3d.multiagent.aha_driven.cli --env-file .env "$@"; }
session=recon/studio/driven

driven status "$session"
driven packet "$session" --task task.json --images SOURCE_IMAGE_ID
driven propose "$session" --packet PACKET_PATH
driven build "$session" --task task.json --proposal PROPOSAL_PATH
driven review "$session" --candidate CANDIDATE_ID
driven commit "$session" --candidate CANDIDATE_ID
```

Repeat for the room's objects. If a review requests repair, revise the proposal and build again. Run `driven final-review "$session"` when the room is ready. Read `handoff.json` for the layout verdict.

## Parallel tasks and object inventories

Use `wave SESSION --plan PLAN.json` for a group of dependency-ready tasks marked `parallel_safe`. Use `merge SESSION --branch BRANCH_ID`, then review and commit each merged candidate.

To use Boxer detections, add `--inventory /path/to/inventory.json` at initialization. Read `boxer-inventory.json` for the boxes and crops. Register a plan with `inventory-plan SESSION --plan PLAN.json`. Assign each detection ID to one task or include it in `omissions` with a reason. Then `wave SESSION` uses that plan.
