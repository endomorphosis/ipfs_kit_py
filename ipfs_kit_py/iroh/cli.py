"""Safe, JSON-only operator CLI for the optional Iroh backend.

The CLI is deliberately an orchestration layer over the versioned runtime,
service, backend, VFS, synchronization, and garbage-collection APIs.  It does
not invoke a shell, put bearer tickets in argv, or expose exception text.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import inspect
import json
import os
import stat
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

import yaml

from ..backend_manager import BackendManager
from ..backend_registry import BackendConfigError, redact_backend_config
from ..iroh_install_cli import IrohInstallError, IrohInstallManager
from ..iroh_sync import (
    ConflictPolicy,
    IrohIPFSSyncAdapter,
    SyncError,
    SyncItem,
    SyncStateStore,
)
from .blob_store import IrohBlobStore
from .client import IrohRuntimeClient
from .config import IrohServiceConfig, load_config
from .errors import (
    IrohConflictError,
    IrohError,
    IrohIntegrityError,
    IrohInvalidConfigError,
    IrohNotFoundError,
    IrohPermissionDeniedError,
    IrohUnavailableError,
)
from .gc import GCPolicy, IrohGarbageCollector, ReferenceTracker
from .manifest import DirectoryManifest, IrohManifestStore
from .service import IrohService


EXIT_SUCCESS = 0
EXIT_USAGE = 2
EXIT_CONFIRMATION = 3
EXIT_INVALID = 4
EXIT_NOT_FOUND = 5
EXIT_CONFLICT = 6
EXIT_UNAVAILABLE = 7
EXIT_INTEGRITY = 8
EXIT_PERMISSION = 9
EXIT_FAILED = 10
EXIT_INTERRUPTED = 130

MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_TICKET_BYTES = 1024 * 1024


class JSONArgumentParser(argparse.ArgumentParser):
    """Argument parser whose failures remain machine readable."""

    def error(self, message: str) -> None:
        document = {
            "ok": False,
            "error": {"code": "usage", "message": "invalid command-line arguments"},
        }
        self._print_message(json.dumps(document, sort_keys=True) + "\n", sys.stderr)
        raise SystemExit(EXIT_USAGE)


class CLIError(RuntimeError):
    """An expected CLI-layer refusal with a stable public code."""

    def __init__(self, code: str, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.public_message = message
        self.exit_code = exit_code


@dataclass(slots=True)
class CLIContext:
    """Optional dependency injection for embedding and deterministic tests."""

    stdin: TextIO = field(default_factory=lambda: sys.stdin)
    stdout: TextIO = field(default_factory=lambda: sys.stdout)
    stderr: TextIO = field(default_factory=lambda: sys.stderr)
    install_manager_factory: Callable[..., Any] | None = None
    service_factory: Callable[[IrohServiceConfig], Any] | None = None
    backend_manager_factory: Callable[..., Any] | None = None
    client_factory: Callable[[IrohServiceConfig], Any] | None = None
    vfs_factory: Callable[..., Any] | None = None
    sync_factory: Callable[..., Any] | None = None
    ipfs_factory: Callable[[], Any] | None = None
    gc_factory: Callable[..., Any] | None = None


def _command_parser(commands: Any, name: str, help_text: str) -> argparse.ArgumentParser:
    return commands.add_parser(name, help=help_text, description=help_text)


def _subcommands(parser: argparse.ArgumentParser, destination: str = "action") -> Any:
    return parser.add_subparsers(dest=destination, required=True)


def _add_dry_run(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true", help="validate and preview only")


def _add_confirmation(parser: argparse.ArgumentParser) -> None:
    confirmation = parser.add_mutually_exclusive_group()
    confirmation.add_argument("--yes", action="store_true", help="confirm the destructive action")
    confirmation.add_argument(
        "--confirm",
        metavar="PHRASE",
        help="non-interactively type the confirmation phrase shown by a dry run",
    )


def _add_instance(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--instance", default="default", help="isolated Iroh instance")
    parser.add_argument("--state-root", help="override the platform Iroh state root")
    parser.add_argument("--config", help="explicit Iroh service configuration JSON")
    parser.add_argument("--timeout", type=float, default=None, help="RPC timeout in seconds")


def _add_gc_policy(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--retention-seconds", type=float, default=24 * 60 * 60)
    parser.add_argument("--max-delete-bytes", type=int)
    parser.add_argument("--max-delete-count", type=int)
    parser.add_argument("--quota-bytes", type=int)
    parser.add_argument("--run-id")


def build_parser(*, prog: str = "ipfs-kit-iroh") -> argparse.ArgumentParser:
    parser = JSONArgumentParser(prog=prog, description=__doc__)
    parser.add_argument("--compact", action="store_true", help="emit one-line JSON")
    commands = _subcommands(parser, "group")

    binary = _command_parser(commands, "binary", "manage the verified Iroh sidecar binary")
    binary_commands = _subcommands(binary)
    for name in ("install", "update"):
        command = _command_parser(binary_commands, name, f"{name} the pinned verified sidecar")
        command.add_argument("--bin-dir")
        command.add_argument("--version")
        command.add_argument("--allow-prerelease", action="store_true")
        command.add_argument("--check", action="store_true")
        _add_dry_run(command)
    inspect = _command_parser(binary_commands, "inspect", "inspect the managed sidecar")
    inspect.add_argument("--bin-dir")
    inspect.add_argument("--check", action="store_true")
    rollback = _command_parser(binary_commands, "rollback", "restore the retained sidecar")
    rollback.add_argument("--bin-dir")
    rollback.add_argument("--check", action="store_true")
    _add_dry_run(rollback)
    _add_confirmation(rollback)

    service = _command_parser(commands, "service", "control a supervised Iroh instance")
    service_commands = _subcommands(service)
    for name in ("status", "start", "stop", "restart"):
        command = _command_parser(service_commands, name, f"{name} the Iroh service")
        _add_instance(command)
        if name != "status":
            _add_dry_run(command)
        if name in {"stop", "restart"}:
            _add_confirmation(command)

    backend = _command_parser(commands, "backend", "manage validated named Iroh backends")
    backend_commands = _subcommands(backend)
    for name in ("list", "show", "health", "capabilities"):
        command = _command_parser(backend_commands, name, f"{name} Iroh backend configuration")
        command.add_argument("name", nargs=None if name != "list" else "?")
        command.add_argument("--backend-root")
    for name in ("validate", "create"):
        command = _command_parser(backend_commands, name, f"{name} an Iroh backend document")
        if name == "create":
            command.add_argument("name")
        command.add_argument("--file", required=True, help="JSON or YAML backend document")
        command.add_argument("--backend-root")
        if name == "create":
            _add_dry_run(command)
    remove = _command_parser(backend_commands, "remove", "remove a named Iroh backend")
    remove.add_argument("name")
    remove.add_argument("--backend-root")
    _add_dry_run(remove)
    _add_confirmation(remove)

    namespace = _command_parser(commands, "namespace", "inspect and recover manifest namespaces")
    namespace_commands = _subcommands(namespace)
    create_ns = _command_parser(namespace_commands, "create", "create an empty namespace manifest")
    create_ns.add_argument("namespace_id")
    create_ns.add_argument("writer_id")
    create_ns.add_argument("--public-read", action="store_true")
    create_ns.add_argument("--operation-id")
    _add_instance(create_ns)
    _add_dry_run(create_ns)
    for name in ("info", "history"):
        command = _command_parser(namespace_commands, name, f"show namespace {name}")
        command.add_argument("namespace_id")
        if name == "history":
            command.add_argument("--limit", type=int)
        _add_instance(command)
    recover = _command_parser(namespace_commands, "recover", "audit or repair a namespace head")
    recover.add_argument("namespace_id")
    recover.add_argument("--history-limit", type=int)
    recover_mode = recover.add_mutually_exclusive_group()
    recover_mode.add_argument("--apply", action="store_true")
    recover_mode.add_argument("--dry-run", action="store_true", help="audit without repairing (default)")
    _add_instance(recover)
    _add_confirmation(recover)

    blob = _command_parser(commands, "blob", "ingest, inspect, fetch, and export immutable blobs")
    blob_commands = _subcommands(blob)
    stat_blob = _command_parser(blob_commands, "stat", "inspect immutable blob metadata")
    stat_blob.add_argument("blob_hash")
    _add_instance(stat_blob)
    add_blob = _command_parser(blob_commands, "add", "ingest a local file")
    add_blob.add_argument("source")
    add_blob.add_argument("--expected-hash")
    _add_instance(add_blob)
    _add_dry_run(add_blob)
    fetch_blob = _command_parser(blob_commands, "fetch", "fetch a hash from an explicit provider")
    fetch_blob.add_argument("blob_hash")
    fetch_blob.add_argument("--provider", required=True)
    _add_instance(fetch_blob)
    _add_dry_run(fetch_blob)
    export_blob = _command_parser(blob_commands, "export", "atomically export a verified blob")
    export_blob.add_argument("blob_hash")
    export_blob.add_argument("destination")
    export_blob.add_argument("--overwrite", action="store_true")
    _add_instance(export_blob)
    _add_dry_run(export_blob)
    _add_confirmation(export_blob)

    ticket = _command_parser(commands, "ticket", "import a bearer ticket without putting it in argv")
    ticket_commands = _subcommands(ticket)
    import_ticket = _command_parser(ticket_commands, "import", "import and verify a read ticket")
    import_ticket.add_argument("expected_hash")
    source = import_ticket.add_mutually_exclusive_group(required=True)
    source.add_argument("--ticket-file", help="owner-only regular file containing the ticket")
    source.add_argument("--ticket-stdin", action="store_true", help="read the ticket from stdin")
    _add_instance(import_ticket)
    _add_dry_run(import_ticket)

    mount = _command_parser(commands, "mount", "manage canonical persistent VFS mounts")
    mount_commands = _subcommands(mount)
    list_mounts = _command_parser(mount_commands, "list", "list Iroh VFS mounts")
    list_mounts.add_argument("--mount-state")
    list_mounts.add_argument("--backend-root")
    add_mount = _command_parser(mount_commands, "add", "add an Iroh VFS mount")
    add_mount.add_argument("mount_point")
    target = add_mount.add_mutually_exclusive_group(required=True)
    target.add_argument("--target", help="iroh:// or iroh+blob:// target")
    target.add_argument("--backend", dest="backend_name", help="validated named Iroh backend")
    add_mount.add_argument("--read-only", action="store_true")
    add_mount.add_argument("--mount-state")
    add_mount.add_argument("--backend-root")
    _add_dry_run(add_mount)
    remove_mount = _command_parser(mount_commands, "remove", "remove a persistent VFS mount")
    remove_mount.add_argument("mount_point")
    remove_mount.add_argument("--mount-state")
    remove_mount.add_argument("--backend-root")
    _add_dry_run(remove_mount)
    _add_confirmation(remove_mount)

    sync = _command_parser(commands, "sync", "run explicit local/IPFS/Iroh reconciliation")
    sync_commands = _subcommands(sync)
    run_sync = _command_parser(sync_commands, "run", "run or resume a synchronization request")
    run_sync.add_argument("--file", required=True, help="JSON request containing an items array")
    run_sync.add_argument("--state-dir")
    run_sync.add_argument("--local-root")
    run_sync.add_argument("--operation-id")
    run_sync.add_argument(
        "--conflict-policy", choices=tuple(item.value for item in ConflictPolicy), default="fail"
    )
    run_sync.add_argument("--continue-on-error", action=argparse.BooleanOptionalAction, default=True)
    _add_instance(run_sync)
    _add_dry_run(run_sync)
    _add_confirmation(run_sync)
    sync_status = _command_parser(sync_commands, "status", "inspect sync mappings and receipts")
    sync_status.add_argument("--state-dir")
    sync_status.add_argument("--operation-id")
    _add_instance(sync_status)

    gc = _command_parser(commands, "gc", "plan and run reference-safe garbage collection")
    gc_commands = _subcommands(gc)
    plan_gc = _command_parser(gc_commands, "plan", "persist a non-destructive GC dry-run receipt")
    _add_instance(plan_gc)
    plan_gc.add_argument("--index")
    _add_gc_policy(plan_gc)
    for name in ("run", "collect"):
        run_gc = _command_parser(gc_commands, name, "run garbage collection (dry-run by default)")
        _add_instance(run_gc)
        run_gc.add_argument("--index")
        _add_gc_policy(run_gc)
        gc_mode = run_gc.add_mutually_exclusive_group()
        gc_mode.add_argument("--apply", action="store_true", help="release eligible blobs")
        gc_mode.add_argument("--dry-run", action="store_true", help="plan without releasing (default)")
        _add_confirmation(run_gc)
    resume_gc = _command_parser(gc_commands, "resume", "resume an interrupted live GC run")
    resume_gc.add_argument("run_id")
    resume_gc.add_argument("--index")
    _add_instance(resume_gc)
    _add_confirmation(resume_gc)

    return parser


def _service_config(args: argparse.Namespace) -> IrohServiceConfig:
    if getattr(args, "config", None):
        return load_config(args.config, state_root=args.state_root)
    return IrohServiceConfig.default(
        args.instance, state_root=getattr(args, "state_root", None), enabled=True
    )


def _client(config: IrohServiceConfig, context: CLIContext) -> Any:
    if context.client_factory is not None:
        return context.client_factory(config)
    return IrohRuntimeClient(endpoint=config.rpc_endpoint)


def _service(config: IrohServiceConfig, context: CLIContext) -> Any:
    return context.service_factory(config) if context.service_factory else IrohService(config)


async def _close_client(client: Any) -> None:
    close = getattr(client, "close", None)
    if close is None:
        return
    result = close()
    if inspect.isawaitable(result):
        await result


def _backend_manager(args: argparse.Namespace, context: CLIContext) -> Any:
    root = getattr(args, "backend_root", None)
    if context.backend_manager_factory:
        return context.backend_manager_factory(root)
    return BackendManager(ipfs_kit_path=root)


def _vfs(args: argparse.Namespace, context: CLIContext) -> Any:
    manager = _backend_manager(args, context)
    if context.vfs_factory:
        return context.vfs_factory(
            backend_manager=manager, mount_state_path=getattr(args, "mount_state", None)
        )
    from ..ipfs_fsspec import VFSCore

    return VFSCore(backend_manager=manager, mount_state_path=getattr(args, "mount_state", None))


def _sync_state_dir(args: argparse.Namespace, config: IrohServiceConfig) -> Path:
    return Path(getattr(args, "state_dir", None) or config.layout.data_dir / "sync")


def _gc_index(args: argparse.Namespace, config: IrohServiceConfig) -> Path:
    return Path(getattr(args, "index", None) or config.layout.data_dir / "references.duckdb")


def _to_jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _to_jsonable(value.to_dict())
    if dataclasses.is_dataclass(value):
        return _to_jsonable(dataclasses.asdict(value))
    if isinstance(value, Path):
        return os.fspath(value)
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError("CLI result is not JSON serializable")


def _read_document(path_text: str) -> Any:
    path = Path(path_text)
    if path.is_symlink() or not path.is_file():
        raise CLIError("invalid_input", "input must be a regular file", EXIT_INVALID)
    try:
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise CLIError("invalid_input", "input document is too large", EXIT_INVALID)
        text = path.read_text(encoding="utf-8")
        value = yaml.safe_load(text)
    except CLIError:
        raise
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise CLIError("invalid_input", "cannot read input document", EXIT_INVALID) from exc
    return value


def _ticket(args: argparse.Namespace, context: CLIContext) -> str:
    if args.ticket_stdin:
        value = context.stdin.read(MAX_TICKET_BYTES + 1)
    else:
        path = Path(args.ticket_file)
        if path.is_symlink() or not path.is_file():
            raise CLIError("invalid_ticket", "ticket source must be a regular file", EXIT_INVALID)
        try:
            info = path.stat()
            if os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077:
                raise CLIError(
                    "unsafe_permissions", "ticket file must be owner-only", EXIT_PERMISSION
                )
            if info.st_size > MAX_TICKET_BYTES:
                raise CLIError("invalid_ticket", "ticket is too large", EXIT_INVALID)
            value = path.read_text(encoding="utf-8")
        except CLIError:
            raise
        except (OSError, UnicodeError) as exc:
            raise CLIError("invalid_ticket", "cannot read ticket", EXIT_INVALID) from exc
    if len(value.encode("utf-8")) > MAX_TICKET_BYTES:
        raise CLIError("invalid_ticket", "ticket is too large", EXIT_INVALID)
    value = value.strip()
    if not value or any(ord(character) < 32 for character in value):
        raise CLIError("invalid_ticket", "ticket is empty or malformed", EXIT_INVALID)
    return value


def _confirmation_phrase(args: argparse.Namespace) -> str:
    if args.group == "service":
        return f"{args.action.upper()} IROH {args.instance}"
    if args.group == "backend":
        return f"REMOVE IROH BACKEND {args.name}"
    if args.group == "mount":
        return f"UNMOUNT IROH {args.mount_point}"
    if args.group == "namespace":
        return f"RECOVER IROH NAMESPACE {args.namespace_id}"
    if args.group == "blob":
        return f"OVERWRITE IROH EXPORT {args.destination}"
    if args.group == "sync":
        return f"RUN DESTRUCTIVE IROH SYNC {args.operation_id or 'new'}"
    if args.group == "gc":
        return f"RUN IROH GC {getattr(args, 'instance', 'default')}"
    if args.group == "binary":
        return "ROLLBACK IROH BINARY"
    return "CONFIRM IROH OPERATION"


def _confirm(args: argparse.Namespace, context: CLIContext) -> None:
    phrase = _confirmation_phrase(args)
    if getattr(args, "yes", False) or getattr(args, "confirm", None) == phrase:
        return
    if getattr(args, "confirm", None) is not None:
        raise CLIError("confirmation_mismatch", "confirmation phrase did not match", EXIT_CONFIRMATION)
    if context.stdin.isatty():
        context.stderr.write(f"Type {phrase!r} to continue: ")
        context.stderr.flush()
        if context.stdin.readline().strip() == phrase:
            return
    raise CLIError(
        "confirmation_required",
        f"destructive operation requires --yes or --confirm {phrase!r}",
        EXIT_CONFIRMATION,
    )


def _dry_run_result(args: argparse.Namespace, value: Any) -> dict[str, Any]:
    """Attach the exact follow-up confirmation phrase to a safe preview."""

    if isinstance(value, Mapping):
        result = dict(value)
    else:
        result = {"receipt": value}
    result["confirmation_phrase"] = _confirmation_phrase(args)
    return result


def _checked_manager_result(value: Any) -> Any:
    if isinstance(value, Mapping) and value.get("error"):
        code = str(value.get("code") or "backend_error")
        exit_code = EXIT_NOT_FOUND if "not_found" in code else EXIT_INVALID
        raise CLIError(code, "named backend operation failed", exit_code)
    return value


class _IrohSyncBridge:
    """Adapt streaming blob primitives to the byte-oriented sync contract."""

    def __init__(self, store: IrohBlobStore, staging_dir: Path) -> None:
        self.store = store
        self.staging_dir = staging_dir

    async def ingest(
        self, content: bytes, *, expected_hash: str, operation_id: str | None = None
    ) -> Any:
        del operation_id
        self.staging_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix="sync-", dir=self.staging_dir)
        path = Path(name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            return await self.store.ingest(path, expected_hash=expected_hash)
        finally:
            path.unlink(missing_ok=True)

    async def read_range(self, digest: str, offset: int, length: int | None) -> bytes:
        return await self.store.read_range(digest, offset, length)

    async def exists(self, digest: str) -> bool:
        try:
            await self.store.stat(digest)
            return True
        except (FileNotFoundError, IrohNotFoundError):
            return False


def _ipfs_client(context: CLIContext) -> Any:
    if context.ipfs_factory:
        return context.ipfs_factory()
    try:
        import ipfshttpclient

        return ipfshttpclient.connect()
    except Exception as exc:
        raise IrohUnavailableError("IPFS client is unavailable", operation="sync.ipfs") from exc


def _sync_adapter(
    args: argparse.Namespace,
    config: IrohServiceConfig,
    context: CLIContext,
    *, needs_ipfs: bool,
) -> tuple[Any, Any]:
    client = _client(config, context)
    iroh = _IrohSyncBridge(IrohBlobStore(client), config.layout.staging_dir)
    ipfs = _ipfs_client(context) if needs_ipfs else object()
    keywords = {
        "local_root": getattr(args, "local_root", None),
    }
    if context.sync_factory:
        adapter = context.sync_factory(ipfs, iroh, _sync_state_dir(args, config), **keywords)
    else:
        adapter = IrohIPFSSyncAdapter(ipfs, iroh, _sync_state_dir(args, config), **keywords)
    return adapter, client


async def execute(args: argparse.Namespace, context: CLIContext) -> Any:
    """Execute parsed arguments and return the unwrapped operation result."""

    group, action = args.group, args.action
    if group == "binary":
        factory = context.install_manager_factory or IrohInstallManager
        manager = factory(bin_dir=args.bin_dir)
        if action == "inspect":
            return manager.inspect(check=args.check)
        if action == "install":
            return manager.install(
                version=args.version,
                allow_prerelease=args.allow_prerelease,
                dry_run=args.dry_run,
                check=args.check,
            )
        if action == "update":
            return manager.update(
                version=args.version,
                allow_prerelease=args.allow_prerelease,
                dry_run=args.dry_run,
                check=args.check,
            )
        if not args.dry_run:
            _confirm(args, context)
        result = manager.rollback(dry_run=args.dry_run, check=args.check)
        return _dry_run_result(args, result) if args.dry_run else result

    if group == "service":
        config = _service_config(args)
        instance = _service(config, context)
        if action == "status":
            return await instance.status()
        if args.dry_run:
            result = {"action": action, "dry_run": True, "instance": config.instance}
            return _dry_run_result(args, result) if action in {"stop", "restart"} else result
        if action in {"stop", "restart"}:
            _confirm(args, context)
        result = await getattr(instance, action)()
        return {"action": action, "changed": bool(result), "instance": config.instance}

    if group == "backend":
        manager = _backend_manager(args, context)
        if action == "list":
            value = _checked_manager_result(manager.list_backends())
            if args.name:
                values = [item for item in value.get("backends", []) if item.get("name") == args.name]
                return {"backends": values, "total": len(values)}
            return value
        if action == "show":
            return _checked_manager_result(manager.show_backend(args.name))
        if action == "health":
            return manager.get_backend_health(args.name)
        if action == "capabilities":
            return manager.get_backend_capabilities(args.name)
        if action in {"validate", "create"}:
            document = _read_document(args.file)
            if not isinstance(document, Mapping):
                raise CLIError("invalid_config", "backend document must be an object", EXIT_INVALID)
            document = dict(document)
            document.setdefault("type", "iroh")
            if action == "create":
                if document.get("name") not in (None, args.name):
                    raise CLIError("invalid_config", "backend name does not match document", EXIT_INVALID)
                document["name"] = args.name
            normalized = manager.validate_backend_config(document)
            if action == "validate" or args.dry_run:
                return {"valid": True, "dry_run": action == "create", "backend": redact_backend_config(normalized)}
            config = dict(normalized)
            name = config.pop("name")
            backend_type = config.pop("type")
            return _checked_manager_result(manager.create_backend(name, backend_type, config=config))
        if args.dry_run:
            existing = _checked_manager_result(manager.show_backend(args.name))
            return _dry_run_result(
                args, {"action": "remove", "dry_run": True, "backend": existing}
            )
        _confirm(args, context)
        return _checked_manager_result(manager.remove_backend(args.name))

    if group == "namespace":
        config = _service_config(args)
        client = _client(config, context)
        try:
            store = IrohManifestStore(client, timeout=args.timeout)
            if action == "create":
                if args.dry_run:
                    manifest = DirectoryManifest.create(
                        args.namespace_id, args.writer_id, 0, (), public_read=args.public_read
                    )
                    return {"dry_run": True, "manifest": manifest.to_dict(), "manifest_hash": manifest.manifest_hash}
                return await store.create_namespace(
                    args.namespace_id,
                    args.writer_id,
                    public_read=args.public_read,
                    operation_id=args.operation_id,
                )
            if action == "info":
                return await store.read(args.namespace_id)
            if action == "history":
                return await store.history(args.namespace_id, limit=args.limit)
            if args.apply:
                _confirm(args, context)
            result = await store.recover_head(
                args.namespace_id, dry_run=not args.apply, history_limit=args.history_limit
            )
            return result if args.apply else _dry_run_result(args, result)
        finally:
            await _close_client(client)

    if group in {"blob", "ticket"}:
        config = _service_config(args)
        client = _client(config, context)
        try:
            store = IrohBlobStore(client, timeout=args.timeout)
            if group == "ticket":
                if args.dry_run:
                    # Validate the source without emitting or sending its contents.
                    _ticket(args, context)
                    return {"action": "ticket.import", "dry_run": True, "expected_hash": args.expected_hash}
                value = _ticket(args, context)
                try:
                    return await store.import_ticket(value, expected_hash=args.expected_hash)
                finally:
                    value = ""
            if action == "stat":
                return await store.stat(args.blob_hash, timeout=args.timeout)
            if action == "add":
                source = Path(args.source)
                if source.is_symlink() or not source.is_file():
                    raise CLIError("invalid_input", "blob source must be a regular file", EXIT_INVALID)
                if args.dry_run:
                    return {"action": "blob.add", "dry_run": True, "size": source.stat().st_size}
                return await store.ingest(source, expected_hash=args.expected_hash, timeout=args.timeout)
            if action == "fetch":
                if args.dry_run:
                    return {"action": "blob.fetch", "dry_run": True, "blob_hash": args.blob_hash}
                return await store.fetch(args.blob_hash, provider=args.provider, timeout=args.timeout)
            destination = Path(args.destination)
            if args.dry_run:
                result = {
                    "action": "blob.export",
                    "dry_run": True,
                    "blob_hash": args.blob_hash,
                    "destination": os.fspath(destination),
                }
                if args.overwrite and destination.exists():
                    return _dry_run_result(args, result)
                return result
            if args.overwrite and destination.exists():
                _confirm(args, context)
            return await store.export(
                args.blob_hash, destination, overwrite=args.overwrite, timeout=args.timeout
            )
        finally:
            await _close_client(client)

    if group == "mount":
        vfs = _vfs(args, context)
        if action == "list":
            value = vfs.list_mounts()
            value["mounts"] = [item for item in value.get("mounts", []) if item.get("backend") == "iroh"]
            value["count"] = len(value["mounts"])
            return value
        if action == "add":
            target = args.target or args.backend_name
            normalized_mount_point = "/" + args.mount_point.replace("\\", "/").strip("/")
            if normalized_mount_point == "//":
                normalized_mount_point = "/"
            existing_mount = next(
                (
                    item
                    for item in vfs.list_mounts().get("mounts", [])
                    if item.get("mount_point") == normalized_mount_point
                ),
                None,
            )
            if existing_mount is not None:
                raise CLIError(
                    "mount_exists",
                    "mount point already exists; remove it explicitly before replacement",
                    EXIT_CONFLICT,
                )
            if args.dry_run:
                if args.backend_name:
                    config = _checked_manager_result(_backend_manager(args, context).show_backend(args.backend_name))
                    if config.get("type") != "iroh":
                        raise CLIError("invalid_backend", "named backend is not Iroh", EXIT_INVALID)
                else:
                    from ..iroh_fsspec import parse_iroh_path

                    parse_iroh_path(target)
                return {
                    "action": "mount.add",
                    "dry_run": True,
                    "mount_point": args.mount_point,
                    "target": target,
                    "read_only": args.read_only,
                }
            return _checked_manager_result(
                vfs.mount(
                    args.mount_point,
                    "iroh",
                    target,
                    read_only=args.read_only,
                    backend_name=args.backend_name,
                )
            )
        if args.dry_run:
            mounts = vfs.list_mounts().get("mounts", [])
            exists = any(item.get("mount_point") == args.mount_point for item in mounts)
            if not exists:
                raise CLIError("not_found", "mount point was not found", EXIT_NOT_FOUND)
            return _dry_run_result(
                args,
                {"action": "mount.remove", "dry_run": True, "mount_point": args.mount_point},
            )
        _confirm(args, context)
        return _checked_manager_result(vfs.unmount(args.mount_point))

    if group == "sync":
        config = _service_config(args)
        if action == "status":
            state = SyncStateStore(_sync_state_dir(args, config))
            return {
                "mappings": state.mappings(),
                "receipts": state.list_receipts(args.operation_id),
            }
        document = _read_document(args.file)
        if isinstance(document, list):
            items_value = document
        elif isinstance(document, Mapping) and isinstance(document.get("items"), list):
            items_value = document["items"]
        else:
            raise CLIError("invalid_sync", "sync request must contain an items array", EXIT_INVALID)
        items = [SyncItem(**dict(item)) if isinstance(item, Mapping) else item for item in items_value]
        destructive = args.conflict_policy == ConflictPolicy.SOURCE_WINS.value or any(
            item.deleted
            or (
                item.destination == "local"
                and item.destination_path is not None
                and Path(item.destination_path).exists()
            )
            for item in items
        )
        if destructive and not args.dry_run:
            _confirm(args, context)
        needs_ipfs = any(item.source == "ipfs" or item.destination == "ipfs" for item in items)
        adapter, client = _sync_adapter(args, config, context, needs_ipfs=needs_ipfs)
        try:
            result = await adapter.reconcile(
                items,
                operation_id=args.operation_id,
                conflict_policy=args.conflict_policy,
                dry_run=args.dry_run,
                continue_on_error=args.continue_on_error,
            )
            return _dry_run_result(args, result) if destructive and args.dry_run else result
        finally:
            await _close_client(client)

    if group == "gc":
        config = _service_config(args)
        apply = action in {"run", "collect"} and args.apply
        if action == "resume" or apply:
            # Confirmation happens before opening/creating the DuckDB index or
            # constructing an RPC client, so a refusal has no side effects.
            _confirm(args, context)
        tracker = ReferenceTracker(_gc_index(args, config))
        client: Any | None = None
        try:
            client = _client(config, context)
            collector = (
                context.gc_factory(tracker, client)
                if context.gc_factory
                else IrohGarbageCollector(tracker, client)
            )
            if action == "resume":
                return await collector.resume(args.run_id)
            policy = GCPolicy(
                retention_seconds=args.retention_seconds,
                max_delete_bytes=args.max_delete_bytes,
                max_delete_count=args.max_delete_count,
                quota_bytes=args.quota_bytes,
            )
            result = await collector.collect(dry_run=not apply, policy=policy, run_id=args.run_id)
            return result if apply else _dry_run_result(args, result)
        finally:
            if client is not None:
                await _close_client(client)
            tracker.close()

    raise CLIError("usage", "unsupported command", EXIT_USAGE)


def _operation(args: argparse.Namespace) -> str:
    return f"{args.group}.{args.action}"


def _error(exc: BaseException) -> tuple[int, dict[str, Any]]:
    if isinstance(exc, CLIError):
        return exc.exit_code, {"code": exc.code, "message": exc.public_message}
    if isinstance(exc, (IrohPermissionDeniedError, PermissionError)):
        return EXIT_PERMISSION, {"code": "permission_denied", "message": "operation is not permitted"}
    if isinstance(exc, (IrohIntegrityError,)):
        return EXIT_INTEGRITY, {"code": "integrity_error", "message": "integrity verification failed"}
    if isinstance(exc, (IrohUnavailableError, ConnectionError, TimeoutError)):
        return EXIT_UNAVAILABLE, {"code": "unavailable", "message": "required service is unavailable"}
    if isinstance(exc, (IrohConflictError,)):
        return EXIT_CONFLICT, {"code": "conflict", "message": "operation conflicts with current state"}
    if isinstance(exc, (IrohNotFoundError, FileNotFoundError, KeyError)):
        return EXIT_NOT_FOUND, {"code": "not_found", "message": "requested resource was not found"}
    if isinstance(exc, (IrohInvalidConfigError, BackendConfigError, SyncError, ValueError, TypeError)):
        code = getattr(exc, "code", "invalid_input")
        return EXIT_INVALID, {"code": code, "message": "input validation failed"}
    if isinstance(exc, IrohError):
        return EXIT_FAILED, {"code": exc.code, "message": "Iroh operation failed"}
    if isinstance(exc, IrohInstallError):
        return EXIT_FAILED, {"code": "install_failed", "message": "Iroh binary operation failed"}
    return EXIT_FAILED, {"code": "operation_failed", "message": "Iroh operation failed"}


def _emit(stream: TextIO, document: Mapping[str, Any], *, compact: bool) -> None:
    if compact:
        json.dump(document, stream, sort_keys=True, separators=(",", ":"))
    else:
        json.dump(document, stream, indent=2, sort_keys=True)
    stream.write("\n")
    stream.flush()


def _result_failed(value: Any) -> bool:
    """Recognize completed operations whose receipt reports partial failure."""

    if not isinstance(value, Mapping):
        return False
    if value.get("status") in {"partial", "failed"}:
        return True
    failures = value.get("failures")
    return isinstance(failures, list) and bool(failures)


def _legacy_argv(argv: Sequence[str]) -> list[str]:
    """Keep the original ``ipfs-kit-iroh install`` interface compatible."""

    value = list(argv)
    offset = 1 if value[:1] == ["--compact"] else 0
    if len(value) > offset and value[offset] in {"install", "inspect", "update", "rollback"}:
        value.insert(offset, "binary")
    return value


def main(argv: Sequence[str] | None = None, *, context: CLIContext | None = None) -> int:
    context = context or CLIContext()
    parser = build_parser()
    arguments = _legacy_argv(sys.argv[1:] if argv is None else argv)
    try:
        args = parser.parse_args(arguments)
        result = _to_jsonable(asyncio.run(execute(args, context)))
        if _result_failed(result):
            document = {
                "ok": False,
                "operation": _operation(args),
                "result": result,
                "error": {
                    "code": "partial_failure",
                    "message": "operation completed with one or more failures",
                },
            }
            _emit(context.stderr, document, compact=args.compact)
            return EXIT_FAILED
        document = {"ok": True, "operation": _operation(args), "result": result}
        _emit(context.stdout, document, compact=args.compact)
        return EXIT_SUCCESS
    except KeyboardInterrupt:
        document = {"ok": False, "error": {"code": "interrupted", "message": "operation interrupted"}}
        _emit(context.stderr, document, compact=True)
        return EXIT_INTERRUPTED
    except SystemExit:
        raise
    except BaseException as exc:
        exit_code, error = _error(exc)
        document = {"ok": False, "error": error}
        if "args" in locals():
            document["operation"] = _operation(args)
        _emit(context.stderr, document, compact=getattr(locals().get("args"), "compact", True))
        return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
