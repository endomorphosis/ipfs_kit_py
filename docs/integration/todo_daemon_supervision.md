# Todo Daemon Supervision

`ipfs_kit_py` has three implementation todo boards that can be supervised by
the `ipfs_accelerate_py` agent supervisor stack:

- `TODO_VFS_GRAPHRAG_INDEXING.md` with task prefix `## vfs-graphrag-`
- `TODO_WALRUS_FSSPEC.md` with task prefix `## walrus-fsspec-`
- `TODO_FSSPEC_BACKENDS.md` with task prefix `## fsspec-backends-`

Use the launcher at `scripts/daemon/ipfs_kit_todo_supervisors.py` to run all
three boards as independent implementation-daemon tracks. The launcher uses the
`ipfs_accelerate_py.agent_supervisor.multi_supervisor_runner` master loop. Each
track starts an `implementation_supervisor`, and each implementation supervisor
starts and monitors its own `implementation_daemon`.

## Start Supervised Daemons

```bash
python scripts/daemon/ipfs_kit_todo_supervisors.py start
```

By default this starts the loop in supervised `--no-implement` mode. The daemons
parse and maintain backlog state, but they do not invoke autonomous
implementation commands.

To allow autonomous implementation attempts, pass `--implement` and optionally
an implementation command:

```bash
python scripts/daemon/ipfs_kit_todo_supervisors.py start \
  --implement \
  --implementation-command "codex exec --full-auto"
```

## Status

```bash
python scripts/daemon/ipfs_kit_todo_supervisors.py status
python scripts/daemon/ipfs_kit_todo_supervisors.py status --json
```

Runtime state lives under `data/agent_supervisor/ipfs_kit_todo/`:

- `master/ipfs_kit_todo.master.pid`
- `master/ipfs_kit_todo.master.log`
- `state/*_supervisor.pid`
- `state/*_managed_daemon.pid`
- `state/*_supervisor_status.json`
- `state/*_8h_run_ipfs_kit_todo.log`

## Current Progress Snapshot

The latest supervised implementation run completed all three task-board tracks.
Use the state JSON files, not the checkbox rendering in the markdown task
boards, as the progress ledger:

| Track | State file | Completed | Ready | Waiting | Blocked |
|-------|------------|-----------|-------|---------|---------|
| Walrus fsspec | `state/ipfs_kit_walrus_fsspec_task_state.json` | 7 / 7 | 0 | 0 | 0 |
| fsspec backends | `state/ipfs_kit_fsspec_backends_task_state.json` | 8 / 8 | 0 | 0 | 0 |
| VFS GraphRAG indexing | `state/ipfs_kit_vfs_graphrag_task_state.json` | 12 / 12 | 0 | 0 | 0 |

The daemon logs show successful implementation commits and validation commands
for each task. They also show `todo_update_result` entries with
`reason: status_line_missing`, so the source markdown boards can still display
unchecked boxes even after the state files mark the tasks complete.

Completed work includes Walrus storage and fsspec integration, fsspec backend
stabilization for Synapse, Storacha, Filecoin pin, and shared fsspec helpers,
plus VFS GraphRAG schema, index, fsspec hooks, VFS manager lifecycle/search,
graph/export/CLI surfaces, tests, and documentation.

## Stop

```bash
python scripts/daemon/ipfs_kit_todo_supervisors.py stop
```

The stop command terminates the detached master runner, the per-track
implementation supervisors, and their managed implementation daemons.
