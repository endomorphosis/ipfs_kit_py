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

## Stop

```bash
python scripts/daemon/ipfs_kit_todo_supervisors.py stop
```

The stop command terminates the detached master runner, the per-track
implementation supervisors, and their managed implementation daemons.
