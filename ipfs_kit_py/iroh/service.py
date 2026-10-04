"""Lifecycle supervision for the managed IPFS Kit Iroh sidecar.

The service is intentionally explicit: importing this module neither creates
state nor starts a process.  A PID is considered ours only when the private
receipt agrees with the instance, executable, and operating-system process
birth time.  This prevents a stale/recycled PID from ever being signalled.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import inspect
import json
import math
import os
import secrets
import signal
import socket
import stat
import sys
import tempfile
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .client import IrohRuntimeClient
from .config import (
    FILE_MODE,
    IrohServiceConfig,
    IrohStateLayout,
    default_config,
    ensure_state_layout,
    load_config,
)
from .errors import (
    IrohConflictError,
    IrohInvalidConfigError,
    IrohUnavailableError,
)


PID_RECEIPT_VERSION = 1
CRASH_RECEIPT_VERSION = 1
PID_RECEIPT_KIND = "ipfs-kit-iroh-process"
CRASH_RECEIPT_KIND = "ipfs-kit-iroh-crash"
DEFAULT_STARTUP_TIMEOUT = 30.0
DEFAULT_SHUTDOWN_TIMEOUT = 10.0
DEFAULT_KILL_TIMEOUT = 5.0
DEFAULT_PROBE_INTERVAL = 0.1
DEFAULT_CRASH_LIMIT = 3


class LifecycleMode(str, Enum):
    """Supported supervision modes."""

    MANAGED_CHILD = "managed-child"
    FOREGROUND = "foreground"


@dataclass(frozen=True, slots=True)
class _ProcessIdentity:
    pid: int
    birth: str
    executable: str


@dataclass(frozen=True, slots=True)
class _Ownership:
    state: str
    receipt: dict[str, Any] | None = None
    identity: _ProcessIdentity | None = None
    detail: str | None = None


ReadinessProbe = Callable[..., bool | Mapping[str, Any] | Awaitable[Any]]
ProcessFactory = Callable[..., Awaitable[Any]]


_INSTANCE_LOCKS: dict[str, asyncio.Lock] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _positive_timeout(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite positive number")
    result = float(value)
    if result <= 0 or not math.isfinite(result):
        raise ValueError(f"{name} must be a finite positive number")
    return result


def _positive_integer(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _same_path(first: str | os.PathLike[str], second: str | os.PathLike[str]) -> bool:
    return os.path.normcase(os.path.realpath(os.fspath(first))) == os.path.normcase(
        os.path.realpath(os.fspath(second))
    )


def _process_identity(pid: int) -> _ProcessIdentity | None:
    """Return a stable identity for a live, non-zombie process."""

    try:
        import psutil

        process = psutil.Process(pid)
        if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
            return None
        birth = f"{process.create_time():.6f}"
        executable = os.path.realpath(process.exe())
        return _ProcessIdentity(pid, birth, executable)
    except (ImportError, OSError, ValueError):
        pass
    except Exception:
        # AccessDenied and NoSuchProcess are deliberately indistinguishable
        # here.  An unverifiable process must never become owned.
        return None

    # A small dependency-free fallback keeps lifecycle usable in constrained
    # installations. Linux /proc supplies both executable and start ticks.
    try:
        os.kill(pid, 0)
        executable = os.path.realpath(os.readlink(f"/proc/{pid}/exe"))
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="ascii").split()
        return _ProcessIdentity(pid, f"proc:{fields[21]}", executable)
    except (OSError, ValueError, IndexError):
        return None


def _pid_exists(pid: int) -> bool:
    try:
        import psutil

        return psutil.pid_exists(pid)
    except ImportError:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise IrohConflictError(
            "managed Iroh receipt is not a regular file", operation="service.status"
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IrohConflictError(
            "managed Iroh receipt is invalid", operation="service.status"
        ) from exc
    if not isinstance(value, dict):
        raise IrohConflictError(
            "managed Iroh receipt is invalid", operation="service.status"
        )
    return value


def _atomic_json(path: Path, document: Mapping[str, Any]) -> None:
    """Durably replace an owner-only JSON receipt."""

    temporary: Path | None = None
    descriptor: int | None = None
    try:
        descriptor, name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(name)
        os.fchmod(descriptor, FILE_MODE)
        payload = (
            json.dumps(dict(document), indent=2, sort_keys=True, ensure_ascii=False)
            + "\n"
        ).encode("utf-8")
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
        path.chmod(FILE_MODE)
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory = os.open(path.parent, flags)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as exc:
        raise IrohUnavailableError(
            "cannot persist managed Iroh lifecycle receipt",
            operation="service.receipt",
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            with contextlib.suppress(FileNotFoundError):
                temporary.unlink()


class _FileLock:
    """A cross-process exclusive lock acquired without blocking the event loop."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.stream: Any = None

    def _acquire(self) -> None:
        self.stream = self.path.open("a+b")
        os.chmod(self.path, FILE_MODE)
        if os.name == "nt":
            import msvcrt

            self.stream.seek(0)
            if not self.stream.read(1):
                self.stream.write(b"0")
                self.stream.flush()
            self.stream.seek(0)
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX)

    def _release(self) -> None:
        if self.stream is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        finally:
            self.stream.close()
            self.stream = None

    async def __aenter__(self) -> "_FileLock":
        await asyncio.to_thread(self._acquire)
        return self

    async def __aexit__(self, *_: Any) -> None:
        await asyncio.to_thread(self._release)


class IrohService:
    """Supervise one configured Iroh sidecar instance.

    ``command`` is a complete argv vector. It exists both for embedding and
    deterministic tests; the production default is the verified managed
    executable followed by ``serve --config <path>``.
    """

    name = "iroh"

    def __init__(
        self,
        config: IrohServiceConfig | Mapping[str, Any] | None = None,
        *,
        executable: str | os.PathLike[str] | None = None,
        command: Sequence[str | os.PathLike[str]] | None = None,
        readiness_probe: ReadinessProbe | None = None,
        mode: LifecycleMode | str = LifecycleMode.MANAGED_CHILD,
        startup_timeout: float = DEFAULT_STARTUP_TIMEOUT,
        shutdown_timeout: float = DEFAULT_SHUTDOWN_TIMEOUT,
        kill_timeout: float = DEFAULT_KILL_TIMEOUT,
        probe_interval: float = DEFAULT_PROBE_INTERVAL,
        crash_limit: int = DEFAULT_CRASH_LIMIT,
        process_factory: ProcessFactory | None = None,
    ) -> None:
        self.config = self._coerce_config(config)
        self.layout: IrohStateLayout = self.config.layout
        self.mode = LifecycleMode(mode)
        self._install_manager: Any | None = None
        if executable is None:
            from ..iroh_install_cli import IrohInstallManager

            self._install_manager = IrohInstallManager()
            executable = self._install_manager.binary_path
        self.executable = os.path.realpath(
            os.fspath(executable)
        )
        default_command = (
            self.executable,
            "serve",
            "--config",
            os.fspath(self.layout.config_path),
        )
        self.command = tuple(os.fspath(part) for part in (command or default_command))
        if not self.command or any(not part for part in self.command):
            raise ValueError("command must be a non-empty argument vector")
        self.readiness_probe = readiness_probe or self._rpc_readiness_probe
        self.startup_timeout = _positive_timeout(startup_timeout, "startup_timeout")
        self.shutdown_timeout = _positive_timeout(shutdown_timeout, "shutdown_timeout")
        self.kill_timeout = _positive_timeout(kill_timeout, "kill_timeout")
        self.probe_interval = _positive_timeout(probe_interval, "probe_interval")
        self.crash_limit = _positive_integer(crash_limit, "crash_limit")
        self._process_factory = process_factory or asyncio.create_subprocess_exec
        self._process: Any | None = None
        self._watch_task: asyncio.Task[None] | None = None
        self._ready = False
        self._last_exit_code: int | None = None

    @staticmethod
    def _coerce_config(
        value: IrohServiceConfig | Mapping[str, Any] | None,
    ) -> IrohServiceConfig:
        if isinstance(value, IrohServiceConfig):
            return value
        if value is None:
            return default_config()
        if not isinstance(value, Mapping):
            raise TypeError("config must be an IrohServiceConfig or mapping")
        if "schema_version" in value:
            return IrohServiceConfig.from_dict(value)
        allowed = {"instance", "state_root", "enabled", "node_identity_ref"}
        unknown = set(value) - allowed
        if unknown:
            raise IrohInvalidConfigError(
                "registry Iroh configuration contains unknown fields: "
                + ", ".join(sorted(str(item) for item in unknown)),
                operation="service.config",
            )
        return default_config(
            str(value.get("instance", "default")),
            state_root=value.get("state_root"),
            enabled=value.get("enabled", False),
            node_identity_ref=value.get("node_identity_ref"),
        )

    def get_config(self) -> dict[str, Any]:
        return self.config.to_dict()

    def set_config(self, config: Mapping[str, Any]) -> bool:
        """Update registry configuration while stopped.

        The canonical registry calls this with an empty mapping after
        construction. Non-empty updates must be a complete validated document
        because the service schema is intentionally closed.
        """

        if not config:
            return True
        if self._process is not None and self._process.returncode is None:
            return False
        try:
            validated = self._coerce_config(config)
        except (TypeError, ValueError, IrohInvalidConfigError):
            return False
        if (
            validated.instance != self.config.instance
            or validated.layout != self.config.layout
        ):
            return False
        self.config = validated
        self.layout = validated.layout
        return True

    @property
    def _async_lock(self) -> asyncio.Lock:
        key = os.path.normcase(os.path.realpath(self.layout.lock_path))
        lock = _INSTANCE_LOCKS.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _INSTANCE_LOCKS[key] = lock
        return lock

    @contextlib.asynccontextmanager
    async def _lifecycle_lock(self):
        self._repair_owned_runtime_directory()
        ensure_state_layout(self.config)
        async with self._async_lock:
            async with _FileLock(self.layout.lock_path):
                yield

    def _repair_owned_runtime_directory(self) -> None:
        """Tighten a caller-created run directory before config validation.

        Operators and recovery tools commonly create ``run/`` before writing
        a stale PID receipt.  Repair is limited to the configured leaf, only
        when it is a real directory owned by the current account; symlinks,
        foreign ownership, and malformed state continue to fail closed in the
        configuration layer.
        """

        for path in self.layout.directories:
            try:
                metadata = path.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISDIR(metadata.st_mode) and (
                not hasattr(os, "getuid") or metadata.st_uid == os.getuid()
            ):
                path.chmod(self.config.ownership.directory_mode)

    def _ownership(self) -> _Ownership:
        receipt = _read_json_object(self.layout.pid_path)
        if receipt is None:
            return _Ownership("absent")
        pid = receipt.get("pid")
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            return _Ownership("foreign", receipt, detail="invalid PID receipt")
        if not _pid_exists(pid):
            return _Ownership("stale", receipt, detail="recorded process is gone")
        identity = _process_identity(pid)
        if identity is None:
            return _Ownership("foreign", receipt, detail="live process cannot be verified")
        valid = (
            receipt.get("schema_version") == PID_RECEIPT_VERSION
            and receipt.get("kind") == PID_RECEIPT_KIND
            and receipt.get("instance") == self.config.instance
            and isinstance(receipt.get("owner_token"), str)
            and bool(receipt["owner_token"])
            and receipt.get("birth") == identity.birth
            and isinstance(receipt.get("executable"), str)
            and _same_path(receipt["executable"], identity.executable)
            and _same_path(receipt["executable"], self.executable)
        )
        if not valid:
            return _Ownership("foreign", receipt, identity, "live PID is not owned")
        return _Ownership("owned", receipt, identity)

    def _remove_runtime_artifacts(self, expected_pid: int | None = None) -> None:
        if expected_pid is not None:
            with contextlib.suppress(IrohConflictError):
                current = _read_json_object(self.layout.pid_path)
                if current is not None and current.get("pid") != expected_pid:
                    return
        with contextlib.suppress(FileNotFoundError):
            self.layout.pid_path.unlink()
        if os.name != "nt":
            with contextlib.suppress(FileNotFoundError):
                metadata = self.layout.rpc_socket_path.lstat()
                if stat.S_ISSOCK(metadata.st_mode):
                    self.layout.rpc_socket_path.unlink()

    def _crash_receipt(self) -> dict[str, Any] | None:
        receipt = _read_json_object(self.layout.crash_receipt_path)
        if receipt is None:
            return None
        if (
            receipt.get("schema_version") != CRASH_RECEIPT_VERSION
            or receipt.get("kind") != CRASH_RECEIPT_KIND
            or receipt.get("instance") != self.config.instance
            or isinstance(receipt.get("crash_count"), bool)
            or not isinstance(receipt.get("crash_count"), int)
            or receipt["crash_count"] < 1
        ):
            raise IrohConflictError(
                "managed Iroh crash receipt is invalid", operation="service.status"
            )
        return receipt

    def _record_crash(self, reason: str, exit_code: int | None = None) -> int:
        previous = self._crash_receipt()
        count = int(previous["crash_count"]) + 1 if previous else 1
        _atomic_json(
            self.layout.crash_receipt_path,
            {
                "schema_version": CRASH_RECEIPT_VERSION,
                "kind": CRASH_RECEIPT_KIND,
                "instance": self.config.instance,
                "crash_count": count,
                "last_failure_at": _utc_now(),
                "reason": reason,
                "exit_code": exit_code,
            },
        )
        return count

    async def clear_crash_loop(self) -> bool:
        async with self._lifecycle_lock():
            ownership = self._ownership()
            if ownership.state == "owned":
                raise IrohConflictError(
                    "cannot clear crash-loop state while Iroh is running",
                    operation="service.clear_crash_loop",
                )
            with contextlib.suppress(FileNotFoundError):
                self.layout.crash_receipt_path.unlink()
            return True

    def _assert_ports_available(self) -> None:
        for bind in self.config.endpoint_bind:
            host, port_text = bind.rsplit(":", 1)
            port = int(port_text)
            if port == 0:
                continue
            host = host.strip("[]")
            for socket_type in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
                try:
                    addresses = socket.getaddrinfo(
                        host, port, type=socket_type, flags=socket.AI_PASSIVE
                    )
                except socket.gaierror as exc:
                    raise IrohConflictError(
                        f"Iroh endpoint bind cannot be resolved: {bind}",
                        operation="service.start",
                    ) from exc
                for family, socktype, protocol, _, address in addresses:
                    check = socket.socket(family, socktype, protocol)
                    try:
                        if family == socket.AF_INET6:
                            with contextlib.suppress(OSError):
                                check.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                        check.bind(address)
                    except OSError as exc:
                        raise IrohConflictError(
                            f"Iroh endpoint bind is already in use: {bind}",
                            operation="service.start",
                        ) from exc
                    finally:
                        check.close()

    async def _call_probe(self) -> bool:
        probe = self.readiness_probe
        try:
            try:
                signature = inspect.signature(probe)
                positional = [
                    parameter
                    for parameter in signature.parameters.values()
                    if parameter.kind
                    in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
                    and parameter.default is parameter.empty
                ]
                result = probe(self) if positional else probe()
            except (TypeError, ValueError):
                result = probe()
            if inspect.isawaitable(result):
                result = await result
            if isinstance(result, Mapping):
                return result.get("ready", result.get("healthy")) is True
            return result is True
        except asyncio.CancelledError:
            raise
        except Exception:
            return False

    async def _rpc_readiness_probe(self) -> bool:
        if os.name != "nt" and not self.layout.rpc_socket_path.exists():
            return False
        try:
            async with IrohRuntimeClient(
                endpoint=self.layout.rpc_socket_path,
                timeout=max(self.probe_interval, 0.05),
            ) as client:
                await client.health(timeout=max(self.probe_interval, 0.05))
            return True
        except Exception:
            return False

    async def _wait_ready(self, process: Any) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.startup_timeout
        while True:
            if process.returncode is not None:
                raise IrohUnavailableError(
                    "Iroh sidecar exited before it became ready",
                    operation="service.start",
                    metadata={"exit_code": process.returncode},
                )
            if await self._call_probe():
                return
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise IrohUnavailableError(
                    "Iroh sidecar did not become ready before the startup timeout",
                    operation="service.start",
                )
            await asyncio.sleep(min(self.probe_interval, remaining))

    async def _wait_adopted_ready(self, pid: int) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.startup_timeout
        while True:
            ownership = self._ownership()
            if ownership.state != "owned" or ownership.identity is None:
                raise IrohUnavailableError(
                    "adopted Iroh process exited before it became ready",
                    operation="service.start",
                )
            if ownership.identity.pid != pid:
                raise IrohConflictError(
                    "Iroh PID receipt changed during readiness probing",
                    operation="service.start",
                )
            if await self._call_probe():
                return
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise IrohUnavailableError(
                    "adopted Iroh process did not become ready before the startup timeout",
                    operation="service.start",
                )
            await asyncio.sleep(min(self.probe_interval, remaining))

    async def _spawn(self) -> Any:
        try:
            log_stream = None
            kwargs: dict[str, Any] = {"stdin": asyncio.subprocess.DEVNULL}
            # The supervisor owns signal forwarding in both modes. Isolating
            # the child prevents a terminal or service manager from racing our
            # receipt update by signalling both processes simultaneously.
            if os.name != "nt":
                kwargs["start_new_session"] = True
            else:
                kwargs["creationflags"] = getattr(
                    __import__("subprocess"), "CREATE_NEW_PROCESS_GROUP", 0
                )
            if self.mode is LifecycleMode.MANAGED_CHILD:
                log_stream = self.layout.service_log_path.open("ab", buffering=0)
                os.chmod(self.layout.service_log_path, FILE_MODE)
                kwargs.update(stdout=log_stream, stderr=log_stream)
            try:
                return await self._process_factory(*self.command, **kwargs)
            finally:
                if log_stream is not None:
                    log_stream.close()
        except (OSError, ValueError) as exc:
            raise IrohUnavailableError(
                "managed Iroh executable is unavailable", operation="service.start"
            ) from exc

    async def _verify_managed_installation(self) -> None:
        """Verify the IROH-005 receipt/digest before executing its binary."""

        if self._install_manager is None:
            return
        try:
            await asyncio.to_thread(self._install_manager.inspect, check=True)
        except Exception as exc:
            raise IrohUnavailableError(
                "managed Iroh installation is unavailable or failed verification",
                operation="service.start",
            ) from exc

    def _write_pid_receipt(self, process: Any) -> dict[str, Any]:
        identity = _process_identity(process.pid)
        if identity is None:
            raise IrohUnavailableError(
                "cannot verify the newly started Iroh process", operation="service.start"
            )
        if not _same_path(identity.executable, self.executable):
            raise IrohConflictError(
                "started process executable does not match managed Iroh executable",
                operation="service.start",
            )
        receipt = {
            "schema_version": PID_RECEIPT_VERSION,
            "kind": PID_RECEIPT_KIND,
            "instance": self.config.instance,
            "pid": process.pid,
            "birth": identity.birth,
            "executable": identity.executable,
            "owner_token": secrets.token_urlsafe(24),
            "started_at": _utc_now(),
            "mode": self.mode.value,
        }
        _atomic_json(self.layout.pid_path, receipt)
        return receipt

    async def start(self) -> bool:
        """Start the sidecar once and return when its readiness probe succeeds."""

        async with self._lifecycle_lock():
            if not self.config.enabled:
                raise IrohUnavailableError(
                    "Iroh service is disabled by configuration",
                    operation="service.start",
                )
            ownership = self._ownership()
            if ownership.state == "owned":
                assert ownership.identity is not None
                await self._wait_adopted_ready(ownership.identity.pid)
                self._ready = True
                return True
            if ownership.state == "foreign":
                raise IrohConflictError(
                    "recorded live PID is not owned by this Iroh instance",
                    operation="service.start",
                )
            if ownership.state == "stale":
                self._remove_runtime_artifacts()

            crash = self._crash_receipt()
            if crash is not None and crash["crash_count"] >= self.crash_limit:
                raise IrohUnavailableError(
                    "Iroh service crash-loop protection is active",
                    operation="service.start",
                    metadata={"crash_count": crash["crash_count"]},
                )

            self._assert_ports_available()
            await self._verify_managed_installation()
            # Persist exactly the configuration used by the child.
            from .config import atomic_write_config

            atomic_write_config(self.layout.config_path, self.config)
            process = await self._spawn()
            self._process = process
            try:
                receipt = self._write_pid_receipt(process)
                await self._wait_ready(process)
            except BaseException as exc:
                await self._terminate_failed_start(process)
                if isinstance(exc, asyncio.CancelledError):
                    raise
                exit_code = process.returncode
                self._record_crash("startup readiness failure", exit_code)
                if isinstance(exc, (IrohUnavailableError, IrohConflictError)):
                    raise
                raise IrohUnavailableError(
                    "Iroh sidecar did not become ready", operation="service.start"
                ) from exc

            self._ready = True
            self._last_exit_code = None
            with contextlib.suppress(FileNotFoundError):
                self.layout.crash_receipt_path.unlink()
            self._watch_task = asyncio.create_task(
                self._watch_process(process, int(receipt["pid"])),
                name=f"iroh-{self.config.instance}-watch",
            )
            return True

    async def _terminate_failed_start(self, process: Any) -> None:
        receipt = _read_json_object(self.layout.pid_path)
        if receipt is not None and receipt.get("pid") == process.pid:
            receipt["stopping"] = True
            _atomic_json(self.layout.pid_path, receipt)
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError, OSError):
                process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=self.shutdown_timeout)
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError, OSError):
                    process.kill()
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(process.wait(), timeout=self.kill_timeout)
        self._remove_runtime_artifacts(process.pid)
        self._ready = False
        self._process = None

    async def _watch_process(self, process: Any, pid: int) -> None:
        try:
            code = await process.wait()
            self._last_exit_code = code
            self._ready = False
            receipt = _read_json_object(self.layout.pid_path)
            planned = receipt is None or (
                receipt.get("pid") == pid and receipt.get("stopping") is True
            )
            if not planned:
                self._record_crash("managed child exited unexpectedly", code)
                self._remove_runtime_artifacts(pid)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Status reconciles receipts; a watcher must never crash the loop.
            return

    async def _wait_pid_exit(self, pid: int, timeout: float) -> bool:
        if self._process is not None and self._process.pid == pid:
            try:
                await asyncio.wait_for(
                    asyncio.shield(self._process.wait()), timeout=timeout
                )
                return True
            except asyncio.TimeoutError:
                return False
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while _pid_exists(pid):
            if loop.time() >= deadline:
                return False
            await asyncio.sleep(min(self.probe_interval, deadline - loop.time()))
        return True

    async def stop(self) -> bool:
        """Gracefully stop an owned process, escalating after the timeout."""

        async with self._lifecycle_lock():
            ownership = self._ownership()
            if ownership.state == "absent":
                self._ready = False
                return True
            if ownership.state == "stale":
                self._remove_runtime_artifacts()
                self._ready = False
                return True
            if ownership.state != "owned" or ownership.identity is None:
                raise IrohConflictError(
                    "recorded live PID is not owned; refusing to signal it",
                    operation="service.stop",
                )

            pid = ownership.identity.pid
            receipt = dict(ownership.receipt or {})
            receipt["stopping"] = True
            receipt["stop_requested_at"] = _utc_now()
            _atomic_json(self.layout.pid_path, receipt)

            # SIGTERM is the portable supervisor contract. A protocol-aware
            # sidecar may translate it into its own graceful shutdown sequence.
            with contextlib.suppress(ProcessLookupError, OSError):
                if self._process is not None and self._process.pid == pid:
                    self._process.terminate()
                else:
                    os.kill(pid, signal.SIGTERM)
            exited = await self._wait_pid_exit(pid, self.shutdown_timeout)
            if not exited:
                with contextlib.suppress(ProcessLookupError, OSError):
                    if self._process is not None and self._process.pid == pid:
                        self._process.kill()
                    else:
                        os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
                exited = await self._wait_pid_exit(pid, self.kill_timeout)
            if not exited:
                raise IrohUnavailableError(
                    "owned Iroh process did not exit after forced termination",
                    operation="service.stop",
                    metadata={"pid": pid},
                )

            self._remove_runtime_artifacts(pid)
            self._ready = False
            if self._watch_task is not None and self._watch_task is not asyncio.current_task():
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await self._watch_task
            self._watch_task = None
            self._process = None
            return True

    async def restart(self) -> bool:
        """Stop and start the configured instance, preserving crash protection."""

        await self.stop()
        return await self.start()

    async def status(self) -> dict[str, Any]:
        """Return liveness, readiness, and ownership as distinct fields."""

        self._repair_owned_runtime_directory()
        ensure_state_layout(self.config)
        ownership = self._ownership()
        crash = self._crash_receipt()
        crash_count = int(crash["crash_count"]) if crash else 0
        result: dict[str, Any] = {
            "name": self.name,
            "type": "storage",
            "instance": self.config.instance,
            "mode": self.mode.value,
            "status": "stopped",
            "running": False,
            "ready": False,
            "pid": None,
            "pid_ownership": ownership.state,
            "crash_count": crash_count,
            "crash_loop": crash_count >= self.crash_limit,
            "rpc_endpoint": self.config.rpc_endpoint,
            "last_exit_code": self._last_exit_code,
        }
        if ownership.receipt is not None:
            result["pid"] = ownership.receipt.get("pid")
            result["started_at"] = ownership.receipt.get("started_at")
        if ownership.state == "owned":
            result["running"] = True
            result["ready"] = await self._call_probe()
            result["status"] = "running" if result["ready"] else "starting"
        elif ownership.state == "foreign":
            result["running"] = True
            result["status"] = "foreign"
        elif ownership.state == "stale":
            result["status"] = "stale"
        elif crash_count:
            result["status"] = "crashed"
        return result

    async def health_check(self) -> bool:
        return bool((await self.status())["ready"])

    async def diagnostics(self, *, persist: bool = True) -> dict[str, Any]:
        """Return the allowlisted structured health receipt for this instance."""

        from .observability import IrohObservability

        return await IrohObservability(self.config, service=self).diagnostics(
            persist=persist
        )

    async def metrics(self, *, persist: bool = True) -> dict[str, Any]:
        """Return bounded-cardinality operational metrics for this instance."""

        from .observability import IrohObservability

        return await IrohObservability(self.config, service=self).metrics(
            persist=persist
        )

    async def run_foreground(self) -> int:
        """Run until the child exits, forwarding termination into ``stop``."""

        if self.mode is not LifecycleMode.FOREGROUND:
            raise ValueError("run_foreground requires mode='foreground'")
        await self.start()
        if self._process is None:
            # An already-running orphan was adopted. Poll it without claiming
            # its exit code, which is unavailable to a non-parent process.
            while (await self.status())["running"]:
                await asyncio.sleep(self.probe_interval)
            return self._last_exit_code or 0

        loop = asyncio.get_running_loop()
        stop_requested = asyncio.Event()
        installed: list[signal.Signals] = []
        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(signum, stop_requested.set)
                installed.append(signum)
            except (NotImplementedError, RuntimeError):
                pass
        wait_task = asyncio.create_task(self._process.wait())
        signal_task = asyncio.create_task(stop_requested.wait())
        try:
            done, _ = await asyncio.wait(
                {wait_task, signal_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if signal_task in done and stop_requested.is_set():
                await self.stop()
                return 0
            return int(await wait_task)
        finally:
            for task in (wait_task, signal_task):
                if not task.done():
                    task.cancel()
            for signum in installed:
                loop.remove_signal_handler(signum)


async def _async_main(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    service = IrohService(
        config,
        executable=args.executable,
        mode=LifecycleMode.FOREGROUND if args.action == "foreground" else LifecycleMode.MANAGED_CHILD,
    )
    if args.action == "start":
        result: Any = await service.start()
    elif args.action == "stop":
        result = await service.stop()
    elif args.action == "restart":
        result = await service.restart()
    elif args.action == "status":
        result = await service.status()
    elif args.action == "clear-crash-loop":
        result = await service.clear_crash_loop()
    else:
        return await service.run_foreground()
    print(json.dumps(result, sort_keys=True))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "stop", "restart", "status", "foreground", "clear-crash-loop"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--executable", type=Path)
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_async_main(args))
    except (IrohConflictError, IrohUnavailableError, IrohInvalidConfigError) as exc:
        print(json.dumps(exc.as_dict(), sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover - exercised through the module CLI
    raise SystemExit(main())


__all__ = [
    "CRASH_RECEIPT_KIND",
    "CRASH_RECEIPT_VERSION",
    "IrohService",
    "LifecycleMode",
    "PID_RECEIPT_KIND",
    "PID_RECEIPT_VERSION",
    "main",
]
