"""KVFS-702: mount / doctor / status / unmount CLI for kernel VFS.

Console script entry point (packaging metadata):

    ipfs-kit-kernel-vfs = ipfs_kit_py.cli.kernel_vfs:main

Commands:

* ``doctor``  — bounded platform capability probe (no mount)
* ``mount``   — foreground-capable mount with readiness and safe options
* ``status``  — closed observability envelope (JSON or human)
* ``unmount`` — PID/lease-validated, idempotent cleanup with stop timeout

Conflict policy: own the CLI / status presentation surface only.  Lifecycle
semantics are invoked via :mod:`ipfs_kit_py.kernel_vfs.linux` and
:mod:`ipfs_kit_py.kernel_vfs.windows`; status projection lives in
:mod:`ipfs_kit_py.kernel_vfs.status`.

Importing this module is inert with respect to native FUSE / WinFsp.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import signal
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, TextIO

# ---------------------------------------------------------------------------
# Identity / bounds
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-702"
CLI_SCHEMA: Final[str] = "KernelVFSCLI@1"
PROGRAM_NAME: Final[str] = "ipfs-kit-kernel-vfs"

DEFAULT_READINESS_TIMEOUT_SECONDS: Final[float] = 15.0
MAX_READINESS_TIMEOUT_SECONDS: Final[float] = 15.0
DEFAULT_STOP_TIMEOUT_SECONDS: Final[float] = 5.0
MAX_STOP_TIMEOUT_SECONDS: Final[float] = 30.0
DEFAULT_DOCTOR_BUDGET_SECONDS: Final[float] = 5.0
MAX_DOCTOR_BUDGET_SECONDS: Final[float] = 5.0
MAX_OPTION_BYTES: Final[int] = 256
MAX_OPTIONS: Final[int] = 32

# Closed FUSE option allowlist (mirrors KVFS-808 security profile).
ADMITTED_FUSE_OPTIONS: Final[frozenset[str]] = frozenset(
    {
        "default_permissions",
        "ro",
        "rw",
        "fsname",
        "subtype",
        "max_read",
        "auto_unmount",
    }
)
ALWAYS_REJECTED_OPTIONS: Final[frozenset[str]] = frozenset(
    {
        "allow_root",
        "suid",
        "dev",
        "exec",
        "modules",
        "nonempty",
    }
)
DEFAULT_EFFECTIVE_OPTIONS: Final[tuple[str, ...]] = ("default_permissions",)

# Environment variable names used by the container profile (KVFS-701).
ENV_MOUNTPOINT: Final[str] = "IPFS_KIT_KERNEL_VFS_MOUNTPOINT"
ENV_STATE_DIR: Final[str] = "IPFS_KIT_KERNEL_VFS_STATE_DIR"
ENV_WAL_DIR: Final[str] = "IPFS_KIT_KERNEL_VFS_WAL_DIR"
ENV_CACHE_DIR: Final[str] = "IPFS_KIT_KERNEL_VFS_CACHE_DIR"
ENV_READY_DIR: Final[str] = "IPFS_KIT_KERNEL_VFS_READY_DIR"
ENV_FOREGROUND: Final[str] = "IPFS_KIT_KERNEL_VFS_FOREGROUND"
ENV_READINESS: Final[str] = "IPFS_KIT_KERNEL_VFS_READINESS"
ENV_CAPABILITY_BUDGET: Final[str] = "IPFS_KIT_KERNEL_VFS_CAPABILITY_BUDGET_SECONDS"

EXIT_OK: Final[int] = 0
EXIT_ERROR: Final[int] = 1
EXIT_USAGE: Final[int] = 2


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CLIError(Exception):
    """Operator-facing CLI failure with a stable exit code and code string."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "CLI_ERROR",
        exit_code: int = EXIT_ERROR,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.exit_code = int(exit_code)
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "ok": False,
            "schema": CLI_SCHEMA,
            "task_id": TASK_ID,
            "error": type(self).__name__,
            "code": self.code,
            "message": self.message,
            "detail": dict(self.detail),
            "exit_code": self.exit_code,
        }


class OptionValidationError(CLIError):
    """Raised when mount options fail the closed allowlist / safety policy."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "OPTION_REJECTED",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, exit_code=EXIT_USAGE, detail=detail)


class TimeoutBoundError(CLIError):
    """Raised when a declared readiness/stop timeout bound is violated."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "TIMEOUT_BOUND",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, exit_code=EXIT_ERROR, detail=detail)


# ---------------------------------------------------------------------------
# Safe mount options
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SafeMountOptions:
    """Result of closed-allowlist mount option admission."""

    admitted: tuple[str, ...]
    warnings: tuple[str, ...]
    allow_other: bool = False

    def to_record(self) -> dict[str, Any]:
        return {
            "admitted": list(self.admitted),
            "warnings": list(self.warnings),
            "allow_other": self.allow_other,
            "policy": "closed_allowlist",
        }


def _split_option(raw: str) -> tuple[str, str | None]:
    if "=" in raw:
        name, value = raw.split("=", 1)
        return name.strip(), value
    return raw.strip(), None


def admit_safe_mount_options(
    options: Sequence[str] | None,
    *,
    allow_other_explicit: bool = False,
    acknowledge_allow_other_warning: bool = False,
) -> SafeMountOptions:
    """Admit mount options under the default fail-closed security profile.

    * ``default_permissions`` is always present.
    * Unknown options and privilege-expanding options are rejected.
    * ``allow_other`` requires explicit opt-in **and** warning acknowledgement.
    """

    admitted: list[str] = ["default_permissions"]
    seen: set[str] = {"default_permissions"}
    warnings: list[str] = []
    allow_other = False

    raw_options = list(options or ())
    if len(raw_options) > MAX_OPTIONS:
        raise OptionValidationError(
            f"too many mount options (max {MAX_OPTIONS})",
            code="OPTION_COUNT",
            detail={"count": len(raw_options), "max": MAX_OPTIONS},
        )

    for raw in raw_options:
        if not isinstance(raw, str):
            raise OptionValidationError(
                "mount option must be a string",
                code="OPTION_TYPE",
            )
        if len(raw.encode("utf-8", errors="replace")) > MAX_OPTION_BYTES:
            raise OptionValidationError(
                f"mount option exceeds {MAX_OPTION_BYTES} bytes",
                code="OPTION_TOO_LONG",
                detail={"option": raw[:64]},
            )
        if any(tok in raw for tok in ("$", "`", ";", "|", "\n", "\r", ",")):
            raise OptionValidationError(
                "mount option injection characters are rejected",
                code="OPTION_INJECTION",
                detail={"option": raw[:64]},
            )

        name, value = _split_option(raw)
        if not name:
            raise OptionValidationError(
                "empty mount option is rejected",
                code="OPTION_EMPTY",
            )

        if name == "allow_other":
            if not allow_other_explicit:
                raise OptionValidationError(
                    "allow_other is off by default; pass --allow-other explicitly",
                    code="ALLOW_OTHER_NOT_EXPLICIT",
                )
            if not acknowledge_allow_other_warning:
                raise OptionValidationError(
                    "allow_other requires --acknowledge-allow-other-warning",
                    code="ALLOW_OTHER_WARNING_REQUIRED",
                )
            if name not in seen:
                admitted.append("allow_other")
                seen.add("allow_other")
            allow_other = True
            warnings.append(
                "allow_other enables multi-user access; mount runs with "
                "expanded peer visibility — review ACLs before production use"
            )
            continue

        if name in ALWAYS_REJECTED_OPTIONS:
            raise OptionValidationError(
                f"mount option {name!r} is forbidden by the security profile",
                code="OPTION_FORBIDDEN",
                detail={"option": name},
            )

        if name not in ADMITTED_FUSE_OPTIONS:
            raise OptionValidationError(
                f"unknown mount option {name!r} is rejected (closed allowlist)",
                code="OPTION_NOT_ALLOWLISTED",
                detail={"option": name},
            )

        if name in {"fsname", "subtype"}:
            if value is None or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}", value
            ):
                raise OptionValidationError(
                    f"{name} value is not an admitted identifier",
                    code="OPTION_VALUE_INVALID",
                    detail={"option": name},
                )
        if name == "max_read":
            try:
                number = int(value) if value is not None else -1
            except (TypeError, ValueError):
                number = -1
            if number < 1 or number > (1 << 20):
                raise OptionValidationError(
                    "max_read is outside the admitted I/O bound",
                    code="OPTION_VALUE_OUT_OF_BOUNDS",
                )

        token = name if value is None else f"{name}={value}"
        if name not in seen:
            admitted.append(token)
            seen.add(name)
        elif name in {"ro", "rw"}:
            admitted = [
                item
                for item in admitted
                if not (item in {"ro", "rw"} or item.startswith(("ro=", "rw=")))
            ]
            admitted.append(token)

    # Mutual exclusion: last of ro/rw wins.
    has_ro = any(item == "ro" or item.startswith("ro=") for item in admitted)
    has_rw = any(item == "rw" or item.startswith("rw=") for item in admitted)
    if has_ro and has_rw:
        last = "ro"
        for item in admitted:
            if item == "ro" or item.startswith("ro="):
                last = "ro"
            elif item == "rw" or item.startswith("rw="):
                last = "rw"
        admitted = [
            item
            for item in admitted
            if not (item in {"ro", "rw"} or item.startswith(("ro=", "rw=")))
        ]
        admitted.append(last)

    return SafeMountOptions(
        admitted=tuple(admitted),
        warnings=tuple(warnings),
        allow_other=allow_other,
    )


# ---------------------------------------------------------------------------
# Timeout bounds
# ---------------------------------------------------------------------------


def bound_readiness_timeout(value: float | None) -> float:
    if value is None:
        return DEFAULT_READINESS_TIMEOUT_SECONDS
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TimeoutBoundError(
            "readiness timeout must be a positive number",
            detail={"value": value},
        ) from exc
    if number <= 0 or number != number:  # NaN
        raise TimeoutBoundError(
            "readiness timeout must be positive",
            detail={"value": value},
        )
    if number > MAX_READINESS_TIMEOUT_SECONDS:
        raise TimeoutBoundError(
            f"readiness timeout exceeds hard bound of {MAX_READINESS_TIMEOUT_SECONDS}s",
            code="READINESS_TIMEOUT_BOUND",
            detail={
                "value": number,
                "max": MAX_READINESS_TIMEOUT_SECONDS,
            },
        )
    return number


def bound_stop_timeout(value: float | None) -> float:
    if value is None:
        return DEFAULT_STOP_TIMEOUT_SECONDS
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TimeoutBoundError(
            "stop timeout must be a positive number",
            detail={"value": value},
        ) from exc
    if number <= 0 or number != number:
        raise TimeoutBoundError(
            "stop timeout must be positive",
            detail={"value": value},
        )
    if number > MAX_STOP_TIMEOUT_SECONDS:
        raise TimeoutBoundError(
            f"stop timeout exceeds hard bound of {MAX_STOP_TIMEOUT_SECONDS}s",
            code="STOP_TIMEOUT_BOUND",
            detail={"value": number, "max": MAX_STOP_TIMEOUT_SECONDS},
        )
    return number


def bound_doctor_budget(value: float | None) -> float:
    if value is None:
        return DEFAULT_DOCTOR_BUDGET_SECONDS
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TimeoutBoundError(
            "doctor budget must be a positive number",
            detail={"value": value},
        ) from exc
    if number <= 0 or number != number:
        raise TimeoutBoundError(
            "doctor budget must be positive",
            detail={"value": value},
        )
    if number > MAX_DOCTOR_BUDGET_SECONDS:
        # Clamp rather than fail: doctor budget is a hard ceiling of 5s.
        return MAX_DOCTOR_BUDGET_SECONDS
    return number


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def emit_json(payload: Mapping[str, Any], stream: TextIO | None = None) -> None:
    out = stream or sys.stdout
    out.write(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n")


def emit_human(text: str, stream: TextIO | None = None) -> None:
    out = stream or sys.stdout
    if not text.endswith("\n"):
        text = text + "\n"
    out.write(text)


def _wants_json(args: argparse.Namespace) -> bool:
    if getattr(args, "json", False):
        return True
    fmt = getattr(args, "format", None)
    return fmt == "json"


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_path(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return None
    return str(raw).strip()


def _detect_platform() -> str:
    system = platform.system().lower()
    if system.startswith("linux"):
        return "linux"
    if system.startswith("windows") or system == "cygwin":
        return "windows"
    return system or "unknown"


def _reap_child_if_possible(pid: int) -> bool:
    """Non-blocking waitpid when we are the parent. Returns True if reaped."""

    if pid <= 0:
        return False
    try:
        waited, _status = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return False
    except OSError:
        return False
    return waited == pid


def _pid_is_zombie(pid: int) -> bool:
    """Best-effort zombie detection via /proc (Linux) or waitpid."""

    if pid <= 0:
        return False
    # If we are the parent of a zombie, reap it and treat as dead.
    if _reap_child_if_possible(pid):
        return True
    try:
        stat_text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return False
    # /proc/<pid>/stat: pid (comm) state ... — comm may contain spaces/parens.
    rparen = stat_text.rfind(")")
    if rparen == -1 or rparen + 2 >= len(stat_text):
        return False
    return stat_text[rparen + 2] == "Z"


def _pid_alive(pid: int) -> bool:
    """Return True only for a live, non-zombie process (non-blocking)."""

    if pid <= 0:
        return False
    # Reap our own zombies first so kill(0) does not false-positive.
    if _reap_child_if_possible(pid):
        return False
    if _pid_is_zombie(pid):
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    # Final zombie re-check: process may have exited between kill(0) and now.
    if _pid_is_zombie(pid):
        return False
    return True


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    data = json.dumps(dict(payload), sort_keys=True, separators=(",", ":")) + "\n"
    try:
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink(missing_ok=True)  # type: ignore[call-arg]
        except TypeError:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise


def _ensure_dir_link_or_bind(target: Path, link_path: Path) -> None:
    """Ensure *link_path* resolves to *target* (symlink preferred)."""

    target = target.resolve()
    target.mkdir(parents=True, exist_ok=True)
    link_path.parent.mkdir(parents=True, exist_ok=True)
    if link_path.exists() or link_path.is_symlink():
        try:
            if link_path.resolve() == target:
                return
        except OSError:
            pass
        # Do not destroy an existing non-matching directory; fail closed.
        if link_path.is_dir() and not link_path.is_symlink():
            # If empty, we can replace; otherwise leave as-is when already usable.
            try:
                next(link_path.iterdir())
            except StopIteration:
                link_path.rmdir()
            else:
                return
        else:
            try:
                link_path.unlink()
            except OSError:
                return
    try:
        link_path.symlink_to(target, target_is_directory=True)
    except OSError:
        # Fallback: just ensure the link path exists as a directory.
        link_path.mkdir(parents=True, exist_ok=True)


def _mirror_ready_file(state_dir: Path, ready_dir: Path | None) -> None:
    if ready_dir is None:
        return
    src = state_dir / "ready.json"
    if not src.exists():
        return
    ready_dir.mkdir(parents=True, exist_ok=True)
    dest = ready_dir / "ready.json"
    try:
        if dest.exists() or dest.is_symlink():
            try:
                if dest.resolve() == src.resolve():
                    return
            except OSError:
                pass
            try:
                dest.unlink()
            except OSError:
                pass
        try:
            dest.symlink_to(src)
        except OSError:
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------


def cmd_doctor(args: argparse.Namespace) -> dict[str, Any]:
    """Run the platform capability doctor (never mounts)."""

    budget = bound_doctor_budget(getattr(args, "budget_seconds", None))
    mountpoint = getattr(args, "mountpoint", None) or _env_path(ENV_MOUNTPOINT)
    state_dir = getattr(args, "state_dir", None) or _env_path(ENV_STATE_DIR)
    host = _detect_platform()

    if host == "windows":
        from ipfs_kit_py.kernel_vfs.winfsp_loader import run_windows_doctor

        report = run_windows_doctor(
            budget_seconds=budget,
            mount_directory=mountpoint,
            state_dir=state_dir,
        )
    else:
        from ipfs_kit_py.kernel_vfs.platform import run_linux_doctor

        report = run_linux_doctor(
            budget_seconds=budget,
            mountpoint=mountpoint,
            state_dir=state_dir,
        )

    envelope: dict[str, Any] = {
        "ok": bool(report.get("native_capability_ready") or report.get("ok")),
        "schema": CLI_SCHEMA,
        "task_id": TASK_ID,
        "command": "doctor",
        "platform": host,
        "mounted": False,
        "doctor": report,
    }
    # Doctor never mounts.
    envelope["mounted"] = False
    if "native_capability_ready" in report:
        envelope["ok"] = bool(report.get("native_capability_ready"))
    elif "support_claim" in report:
        envelope["ok"] = report.get("support_claim") == "probe_passed"
    return envelope


def format_doctor_human(envelope: Mapping[str, Any]) -> str:
    doctor = envelope.get("doctor") or {}
    checks = doctor.get("checks") or {}
    lines = [
        f"Kernel VFS doctor  platform={envelope.get('platform')}  "
        f"ok={envelope.get('ok')}  mounted={envelope.get('mounted')}",
        f"  support_claim={doctor.get('support_claim')}  "
        f"elapsed={doctor.get('elapsed_seconds')}s  "
        f"budget={doctor.get('budget_seconds')}s",
    ]
    if isinstance(checks, Mapping):
        for name, result in checks.items():
            if not isinstance(result, Mapping):
                lines.append(f"  [{name}] {result}")
                continue
            available = result.get("available")
            message = result.get("message") or result.get("detail") or ""
            lines.append(f"  [{name}] available={available}  {message}")
    absence = (checks.get("actionable_absence") or {}) if isinstance(checks, Mapping) else {}
    items = absence.get("items") if isinstance(absence, Mapping) else None
    if items:
        lines.append("  actionable absences:")
        for item in items:
            if isinstance(item, Mapping):
                lines.append(
                    f"    - {item.get('check')}: {item.get('message')}"
                )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Mount
# ---------------------------------------------------------------------------


def _prepare_state_layout(
    *,
    state_dir: Path,
    wal_dir: Path | None,
    cache_dir: Path | None,
) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    if wal_dir is not None:
        _ensure_dir_link_or_bind(wal_dir, state_dir / "wal")
    else:
        (state_dir / "wal").mkdir(parents=True, exist_ok=True)
    if cache_dir is not None:
        _ensure_dir_link_or_bind(cache_dir, state_dir / "cache")
    else:
        (state_dir / "cache").mkdir(parents=True, exist_ok=True)
    (state_dir / "recovery").mkdir(parents=True, exist_ok=True)


def _build_linux_lifecycle(
    *,
    mountpoint: Path,
    state_dir: Path,
    mount_id: str,
    readiness_timeout: float,
    stop_timeout: float,
    hermetic: bool,
):
    from ipfs_kit_py.kernel_vfs.linux import LinuxMountConfig, LinuxMountLifecycle

    config = LinuxMountConfig(
        mountpoint=mountpoint,
        state_directory=state_dir,
        mount_id=mount_id,
        readiness_timeout_seconds=readiness_timeout,
        unmount_timeout_seconds=stop_timeout,
        hermetic=hermetic,
    )
    return LinuxMountLifecycle(config)


def _build_windows_lifecycle(
    *,
    state_dir: Path,
    mount_id: str,
    readiness_timeout: float,
    hermetic: bool,
):
    from ipfs_kit_py.kernel_vfs.windows import (
        WindowsMountLifecycle,
        WindowsMountMode,
    )

    mode = WindowsMountMode.HERMETIC if hermetic else WindowsMountMode.NATIVE
    return WindowsMountLifecycle(
        state_dir,
        mount_id=mount_id,
        readiness_timeout_seconds=readiness_timeout,
        mode=mode,
    )


def cmd_mount(args: argparse.Namespace) -> dict[str, Any]:
    """Mount with bounded readiness; optionally stay in the foreground."""

    mountpoint_raw = getattr(args, "mountpoint", None) or _env_path(ENV_MOUNTPOINT)
    state_raw = getattr(args, "state_dir", None) or _env_path(ENV_STATE_DIR)
    if not mountpoint_raw:
        raise CLIError(
            "mount requires --mountpoint (or IPFS_KIT_KERNEL_VFS_MOUNTPOINT)",
            code="MOUNTPOINT_REQUIRED",
            exit_code=EXIT_USAGE,
        )
    if not state_raw:
        raise CLIError(
            "mount requires --state-dir (or IPFS_KIT_KERNEL_VFS_STATE_DIR)",
            code="STATE_DIR_REQUIRED",
            exit_code=EXIT_USAGE,
        )

    mountpoint = Path(mountpoint_raw).expanduser()
    state_dir = Path(state_raw).expanduser()
    wal_raw = getattr(args, "wal_dir", None) or _env_path(ENV_WAL_DIR)
    cache_raw = getattr(args, "cache_dir", None) or _env_path(ENV_CACHE_DIR)
    ready_raw = getattr(args, "ready_dir", None) or _env_path(ENV_READY_DIR)
    wal_dir = Path(wal_raw).expanduser() if wal_raw else None
    cache_dir = Path(cache_raw).expanduser() if cache_raw else None
    ready_dir = Path(ready_raw).expanduser() if ready_raw else None

    # Foreground defaults true when env says so, else respect flag (default True).
    foreground = bool(getattr(args, "foreground", True))
    if _env_flag(ENV_FOREGROUND, default=False):
        foreground = True
    readiness = bool(getattr(args, "readiness", True))
    if _env_flag(ENV_READINESS, default=False):
        readiness = True

    readiness_timeout = bound_readiness_timeout(
        getattr(args, "readiness_timeout", None)
    )
    stop_timeout = bound_stop_timeout(getattr(args, "stop_timeout", None))

    raw_options = list(getattr(args, "options", None) or [])
    allow_other_explicit = bool(getattr(args, "allow_other", False))
    if allow_other_explicit and "allow_other" not in raw_options:
        # --allow-other is itself the explicit option request.
        raw_options.append("allow_other")
    options = admit_safe_mount_options(
        raw_options,
        allow_other_explicit=allow_other_explicit,
        acknowledge_allow_other_warning=bool(
            getattr(args, "acknowledge_allow_other_warning", False)
        ),
    )

    # State/mount separation: fail closed when co-located.
    try:
        mp_resolved = mountpoint.resolve()
        st_resolved = state_dir.expanduser()
        # Create parents for resolution of non-existent paths.
        mountpoint.mkdir(parents=True, exist_ok=True)
        state_dir.mkdir(parents=True, exist_ok=True)
        mp_resolved = mountpoint.resolve()
        st_resolved = state_dir.resolve()
    except OSError as exc:
        raise CLIError(
            f"cannot prepare mountpoint/state paths: {exc}",
            code="PATH_PREPARE",
            detail={"error": str(exc)},
        ) from exc

    if mp_resolved == st_resolved:
        raise CLIError(
            "mountpoint and state-dir must be strictly separated",
            code="STATE_MOUNT_OVERLAP",
            exit_code=EXIT_USAGE,
            detail={
                "mountpoint": str(mp_resolved),
                "state_dir": str(st_resolved),
            },
        )
    try:
        st_resolved.relative_to(mp_resolved)
        raise CLIError(
            "state-dir must not be nested under mountpoint",
            code="STATE_NESTED_UNDER_MOUNT",
            exit_code=EXIT_USAGE,
        )
    except ValueError:
        pass
    try:
        mp_resolved.relative_to(st_resolved)
        raise CLIError(
            "mountpoint must not be nested under state-dir",
            code="MOUNT_NESTED_UNDER_STATE",
            exit_code=EXIT_USAGE,
        )
    except ValueError:
        pass

    _prepare_state_layout(
        state_dir=st_resolved,
        wal_dir=wal_dir.resolve() if wal_dir else None,
        cache_dir=cache_dir.resolve() if cache_dir else None,
    )

    mount_id = str(getattr(args, "mount_id", None) or "mount:cli-default")
    hermetic = bool(getattr(args, "hermetic", True))
    if getattr(args, "native", False):
        hermetic = False

    host = _detect_platform()
    started = time.monotonic()

    # Persist CLI-admitted options for operators (never secrets).
    _atomic_write_json(
        st_resolved / "cli-mount-options.json",
        {
            "schema": CLI_SCHEMA,
            "task_id": TASK_ID,
            "options": options.to_record(),
            "foreground": foreground,
            "readiness": readiness,
            "readiness_timeout_seconds": readiness_timeout,
            "stop_timeout_seconds": stop_timeout,
            "hermetic": hermetic,
            "platform": host,
        },
    )

    if host == "windows":
        life = _build_windows_lifecycle(
            state_dir=st_resolved,
            mount_id=mount_id,
            readiness_timeout=readiness_timeout,
            hermetic=hermetic,
        )
        try:
            # mount() runs recovery then readiness when wait_ready=True.
            life.mount(
                str(mp_resolved),
                wait_ready=readiness,
                readiness_timeout_seconds=readiness_timeout,
            )
        except Exception as exc:  # noqa: BLE001
            try:
                life.unmount()
            except Exception:  # noqa: BLE001
                pass
            raise CLIError(
                f"windows mount failed: {exc}",
                code="MOUNT_FAILED",
                detail={"error": str(exc), "platform": "windows"},
            ) from exc
        status_obj = life.status()
        status_record = (
            status_obj.to_record() if hasattr(status_obj, "to_record") else dict(status_obj)
        )
        from ipfs_kit_py.kernel_vfs.status import build_status_from_lifecycle_records

        unified = build_status_from_lifecycle_records(
            status_raw=status_record,
            source="mount",
        )
        envelope: dict[str, Any] = {
            "ok": True,
            "schema": CLI_SCHEMA,
            "task_id": TASK_ID,
            "command": "mount",
            "platform": host,
            "foreground": foreground,
            "readiness": readiness,
            "readiness_timeout_seconds": readiness_timeout,
            "stop_timeout_seconds": stop_timeout,
            "options": options.to_record(),
            "hermetic": hermetic,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "mount_id": mount_id,
            "pid": getattr(life, "pid", None),
            "mountpoint": str(mp_resolved),
            "state_directory": str(st_resolved),
            "ready": bool(getattr(life, "ready", True)),
            "recovery_complete": bool(getattr(life, "recovery_complete", True)),
            "status": unified.to_record(),
        }
        if foreground:
            envelope = _foreground_wait_windows(
                life, envelope=envelope, stop_timeout=stop_timeout
            )
        return envelope

    # Linux (and other POSIX) path.
    life = _build_linux_lifecycle(
        mountpoint=mp_resolved,
        state_dir=st_resolved,
        mount_id=mount_id,
        readiness_timeout=readiness_timeout,
        stop_timeout=stop_timeout,
        hermetic=hermetic,
    )
    try:
        readiness_receipt = life.start(wait_ready=readiness)
    except Exception as exc:  # noqa: BLE001
        raise CLIError(
            f"mount failed: {exc}",
            code="MOUNT_FAILED",
            detail={"error": str(exc), "platform": host},
        ) from exc

    _mirror_ready_file(st_resolved, ready_dir)

    from ipfs_kit_py.kernel_vfs.status import build_status_from_lifecycle_records

    # Brief settle so the child can publish status/heartbeat after ready.
    status_raw: dict[str, Any] = {}
    hb_raw: dict[str, Any] = {}
    deadline = time.monotonic() + min(2.0, readiness_timeout)
    while time.monotonic() < deadline:
        try:
            st = life.status()
            status_raw = st.to_record()
        except Exception:  # noqa: BLE001
            status_raw = {}
        try:
            hb = life.heartbeat()
            hb_raw = hb.to_record()
        except Exception:  # noqa: BLE001
            hb_raw = {}
        if status_raw and hb_raw:
            break
        time.sleep(0.05)

    unified = build_status_from_lifecycle_records(
        status_raw=status_raw,
        heartbeat_raw=hb_raw,
        readiness_raw=(
            readiness_receipt.to_record()
            if hasattr(readiness_receipt, "to_record")
            else {}
        ),
        source="mount",
    )

    envelope = {
        "ok": bool(getattr(readiness_receipt, "ready", True)),
        "schema": CLI_SCHEMA,
        "task_id": TASK_ID,
        "command": "mount",
        "platform": host,
        "foreground": foreground,
        "readiness": readiness,
        "readiness_timeout_seconds": readiness_timeout,
        "stop_timeout_seconds": stop_timeout,
        "options": options.to_record(),
        "hermetic": hermetic,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "mount_id": mount_id,
        "pid": life.pid,
        "mountpoint": str(mp_resolved),
        "state_directory": str(st_resolved),
        "ready": bool(getattr(readiness_receipt, "ready", False)),
        "recovery_complete": bool(
            getattr(readiness_receipt, "recovery_complete", False)
        ),
        "status": unified.to_record(),
    }

    if foreground:
        envelope = _foreground_wait_linux(
            life,
            envelope=envelope,
            stop_timeout=stop_timeout,
            ready_dir=ready_dir,
            state_dir=st_resolved,
        )
    return envelope


def _foreground_wait_linux(
    life: Any,
    *,
    envelope: dict[str, Any],
    stop_timeout: float,
    ready_dir: Path | None,
    state_dir: Path,
) -> dict[str, Any]:
    """Stay attached until signal or child exit; then unmount cleanly."""

    stop_requested = {"value": False}

    def _handler(signum: int, _frame: Any) -> None:
        stop_requested["value"] = True

    previous: dict[int, Any] = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            previous[int(sig)] = signal.signal(sig, _handler)
        except (ValueError, OSError):
            pass

    try:
        while life.running and not stop_requested["value"]:
            _mirror_ready_file(state_dir, ready_dir)
            time.sleep(0.1)
        receipt = life.unmount(timeout_seconds=stop_timeout)
        envelope["unmount"] = (
            receipt.to_record() if hasattr(receipt, "to_record") else {"success": True}
        )
        envelope["foreground_exit"] = "signal" if stop_requested["value"] else "child_exit"
        envelope["ok"] = bool(getattr(receipt, "success", True))
    finally:
        for sig, handler in previous.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass
    return envelope


def _foreground_wait_windows(
    life: Any,
    *,
    envelope: dict[str, Any],
    stop_timeout: float,
) -> dict[str, Any]:
    stop_requested = {"value": False}

    def _handler(signum: int, _frame: Any) -> None:
        stop_requested["value"] = True

    previous: dict[int, Any] = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            previous[int(sig)] = signal.signal(sig, _handler)
        except (ValueError, OSError):
            pass

    try:
        # Windows hermetic worker exposes .ready / state; poll until stop.
        while not stop_requested["value"]:
            state = getattr(life, "state", None)
            state_value = getattr(state, "value", state)
            if state_value in {"stopped", "crashed", "failed"}:
                break
            # Heartbeat to keep leases fresh.
            try:
                life.heartbeat()
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.1)
        receipt = life.unmount()
        envelope["unmount"] = (
            receipt.to_record() if hasattr(receipt, "to_record") else {"success": True}
        )
        envelope["foreground_exit"] = "signal" if stop_requested["value"] else "stopped"
        envelope["ok"] = bool(getattr(receipt, "success", True))
        envelope["stop_timeout_seconds"] = stop_timeout
    finally:
        for sig, handler in previous.items():
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass
    return envelope


def format_mount_human(envelope: Mapping[str, Any]) -> str:
    lines = [
        f"Kernel VFS mount  ok={envelope.get('ok')}  platform={envelope.get('platform')}",
        f"  mount_id={envelope.get('mount_id')}  pid={envelope.get('pid')}",
        f"  mountpoint={envelope.get('mountpoint')}",
        f"  state_dir={envelope.get('state_directory')}",
        f"  ready={envelope.get('ready')}  recovery_complete={envelope.get('recovery_complete')}",
        f"  foreground={envelope.get('foreground')}  hermetic={envelope.get('hermetic')}",
        f"  readiness_timeout={envelope.get('readiness_timeout_seconds')}s  "
        f"stop_timeout={envelope.get('stop_timeout_seconds')}s",
        f"  elapsed={envelope.get('elapsed_seconds')}s",
    ]
    options = envelope.get("options") or {}
    if isinstance(options, Mapping):
        lines.append(f"  options={options.get('admitted')}")
        for warning in options.get("warnings") or []:
            lines.append(f"  warning: {warning}")
    if envelope.get("unmount"):
        unmount = envelope["unmount"]
        if isinstance(unmount, Mapping):
            lines.append(
                f"  unmount: success={unmount.get('success')} "
                f"disposition={unmount.get('disposition')} "
                f"idempotent={unmount.get('idempotent')}"
            )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> dict[str, Any]:
    """Collect and return the closed status envelope."""

    from ipfs_kit_py.kernel_vfs.status import (
        collect_status_from_state_directory,
        format_status_human,
        validate_status_record,
    )

    state_raw = getattr(args, "state_dir", None) or _env_path(ENV_STATE_DIR)
    if not state_raw:
        raise CLIError(
            "status requires --state-dir (or IPFS_KIT_KERNEL_VFS_STATE_DIR)",
            code="STATE_DIR_REQUIRED",
            exit_code=EXIT_USAGE,
        )
    state_dir = Path(state_raw).expanduser()

    status = collect_status_from_state_directory(state_dir)
    record = status.to_record()
    problems = validate_status_record(record)
    envelope: dict[str, Any] = {
        "ok": bool(status.ok) and not problems,
        "schema": CLI_SCHEMA,
        "task_id": TASK_ID,
        "command": "status",
        "platform": _detect_platform(),
        "status": record,
        "validation_problems": problems,
    }
    # Attach human text for callers that want both (still safe).
    envelope["human"] = format_status_human(status)
    return envelope


def format_status_cli_human(envelope: Mapping[str, Any]) -> str:
    human = envelope.get("human")
    if isinstance(human, str) and human.strip():
        return human if human.endswith("\n") else human + "\n"
    from ipfs_kit_py.kernel_vfs.status import format_status_human

    status = envelope.get("status") or {}
    if isinstance(status, Mapping):
        return format_status_human(status)
    return f"status unavailable ok={envelope.get('ok')}\n"


# ---------------------------------------------------------------------------
# Unmount
# ---------------------------------------------------------------------------


def _load_recorded_pid(state_dir: Path) -> int:
    for name in (
        "child.pid",
        "status.json",
        "heartbeat.json",
        "ready.json",
        "mount.process.json",
        "mount.status.json",
        "mount.heartbeat.json",
    ):
        raw = _read_json(state_dir / name)
        if not raw:
            runtime = state_dir / "runtime" / name
            raw = _read_json(runtime)
        if not raw:
            continue
        pid = int(raw.get("pid") or 0)
        if pid > 0:
            return pid
        resources = raw.get("resources")
        if isinstance(resources, Mapping):
            pid = int(resources.get("pid") or 0)
            if pid > 0:
                return pid
    return 0


def _load_mount_id(state_dir: Path) -> str:
    for name in ("status.json", "ready.json", "heartbeat.json", "child-config.json"):
        raw = _read_json(state_dir / name)
        if raw.get("mount_id"):
            return str(raw["mount_id"])
    return ""


def _validate_pid_and_lease(
    state_dir: Path,
    *,
    expected_pid: int | None = None,
) -> dict[str, Any]:
    """Validate recorded PID liveness and optional lease holder consistency."""

    recorded_pid = _load_recorded_pid(state_dir)
    alive = _pid_alive(recorded_pid) if recorded_pid else False
    result: dict[str, Any] = {
        "recorded_pid": recorded_pid,
        "pid_alive": alive,
        "lease_valid": True,
        "stale": False,
        "messages": [],
    }
    if expected_pid is not None and recorded_pid and expected_pid != recorded_pid:
        result["lease_valid"] = False
        result["messages"].append(
            f"pid mismatch: expected {expected_pid}, recorded {recorded_pid}"
        )
    if recorded_pid and not alive:
        result["stale"] = True
        result["messages"].append(f"recorded pid {recorded_pid} is not alive")
    # Lease holder id cross-check (best-effort, non-blocking).
    status_raw = _read_json(state_dir / "status.json")
    ready_raw = _read_json(state_dir / "ready.json")
    holder = str(
        status_raw.get("holder_id") or ready_raw.get("holder_id") or ""
    )
    result["holder_id"] = holder
    if status_raw.get("lease_held") and recorded_pid and not alive:
        result["lease_valid"] = False
        result["messages"].append("lease marked held but pid is dead (stale lease)")
    return result


def unmount_linux_state(
    state_dir: Path,
    *,
    stop_timeout: float,
    mountpoint: Path | None = None,
    signal_value: int = signal.SIGTERM,
) -> dict[str, Any]:
    """Unmount using state-directory receipts; idempotent when not running."""

    from ipfs_kit_py.kernel_vfs.linux import (
        CHILD_CONFIG_FILENAME,
        LinuxMountConfig,
        LinuxMountLifecycle,
        UNMOUNT_REQUEST_FILENAME,
    )

    started = time.monotonic()
    validation = _validate_pid_and_lease(state_dir)
    recorded_pid = int(validation["recorded_pid"] or 0)

    config_path = state_dir / CHILD_CONFIG_FILENAME
    config_raw = _read_json(config_path)
    if config_raw:
        config = LinuxMountConfig.from_dict(config_raw)
        life = LinuxMountLifecycle(config)
    else:
        mp = mountpoint or Path(state_dir / ".mnt-placeholder")
        config = LinuxMountConfig(
            mountpoint=mp,
            state_directory=state_dir,
            unmount_timeout_seconds=stop_timeout,
            hermetic=True,
        )
        life = LinuxMountLifecycle(config)

    # If the parent process that started the mount is gone but the child lives,
    # signal the child directly using the unmount.request protocol.
    if recorded_pid and _pid_alive(recorded_pid) and not life.running:
        try:
            _atomic_write_json(
                state_dir / UNMOUNT_REQUEST_FILENAME,
                {
                    "unix_ms": int(time.time() * 1000),
                    "signal": int(signal_value),
                    "mount_id": _load_mount_id(state_dir),
                    "source": "cli",
                },
            )
        except OSError:
            pass
        try:
            os.kill(recorded_pid, signal_value)
        except (ProcessLookupError, OSError):
            pass
        deadline = time.monotonic() + stop_timeout
        while _pid_alive(recorded_pid) and time.monotonic() < deadline:
            _reap_child_if_possible(recorded_pid)
            time.sleep(0.05)
        if _pid_alive(recorded_pid):
            try:
                os.kill(recorded_pid, signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
            kill_deadline = time.monotonic() + min(1.0, stop_timeout)
            while _pid_alive(recorded_pid) and time.monotonic() < kill_deadline:
                _reap_child_if_possible(recorded_pid)
                time.sleep(0.05)
        # Final reap so zombies do not look live to operators / re-entry.
        _reap_child_if_possible(recorded_pid)
        # Clear ready marker for operators.
        try:
            (state_dir / "ready.json").unlink(missing_ok=True)  # type: ignore[call-arg]
        except TypeError:
            ready = state_dir / "ready.json"
            if ready.exists():
                try:
                    ready.unlink()
                except OSError:
                    pass
        except OSError:
            pass
        still_alive = _pid_alive(recorded_pid)
        # Cooperative child writes shutdown.json before exit; treat that as
        # success even if a brief zombie window races the liveness probe.
        shutdown_raw = _read_json(state_dir / "shutdown.json")
        cooperative = bool(shutdown_raw) and bool(
            shutdown_raw.get("success", True)
        )
        success = (not still_alive) or cooperative
        if cooperative and still_alive:
            # Prefer not to leave a false-live PID; one last reap attempt.
            _reap_child_if_possible(recorded_pid)
            still_alive = _pid_alive(recorded_pid)
            success = (not still_alive) or cooperative
        return {
            "ok": success,
            "success": success,
            "idempotent": False,
            "disposition": "stopped" if success else "failed",
            "pid": recorded_pid,
            "pid_validation": validation,
            "lease_released": success,
            "mount_released": success,
            "recovery_preserved": (state_dir / "recovery").exists()
            or (state_dir / "recovery-preserved").exists(),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "method": "pid_signal",
            "pid_still_alive": still_alive,
            "cooperative_shutdown": cooperative,
        }

    # Lifecycle-managed unmount (same process that mounted, or nothing running).
    receipt = life.unmount(timeout_seconds=stop_timeout, sig=signal_value)
    record = receipt.to_record() if hasattr(receipt, "to_record") else dict(receipt)
    record["ok"] = bool(record.get("success", True))
    record["pid_validation"] = validation
    record["method"] = "lifecycle"
    record["elapsed_seconds"] = round(
        float(record.get("elapsed_seconds") or (time.monotonic() - started)),
        3,
    )
    return record


def unmount_windows_state(
    state_dir: Path,
    *,
    stop_timeout: float,
    mount_root: str | None = None,
) -> dict[str, Any]:
    from ipfs_kit_py.kernel_vfs.windows import (
        WindowsMountLifecycle,
        WindowsMountMode,
    )

    started = time.monotonic()
    validation = _validate_pid_and_lease(state_dir)
    life = WindowsMountLifecycle(
        state_dir,
        mode=WindowsMountMode.HERMETIC,
        stop_timeout_seconds=stop_timeout,
    )
    if mount_root:
        validation = dict(validation)
        validation["mount_root"] = str(mount_root)
    # If never mounted in this process, unmount is idempotent.
    try:
        receipt = life.unmount()
        record = receipt.to_record() if hasattr(receipt, "to_record") else {"success": True}
    except Exception as exc:  # noqa: BLE001
        record = {
            "success": True,
            "idempotent": True,
            "disposition": "idempotent",
            "detail": {"error": str(exc), "not_running": True},
        }
    record["ok"] = bool(record.get("success", True))
    record["pid_validation"] = validation
    record["method"] = "windows_lifecycle"
    record["elapsed_seconds"] = round(time.monotonic() - started, 3)
    record["stop_timeout_seconds"] = stop_timeout
    return record


def cmd_unmount(args: argparse.Namespace) -> dict[str, Any]:
    """Idempotent unmount with PID/lease validation and bounded stop timeout."""

    state_raw = getattr(args, "state_dir", None) or _env_path(ENV_STATE_DIR)
    if not state_raw:
        raise CLIError(
            "unmount requires --state-dir (or IPFS_KIT_KERNEL_VFS_STATE_DIR)",
            code="STATE_DIR_REQUIRED",
            exit_code=EXIT_USAGE,
        )
    state_dir = Path(state_raw).expanduser()
    stop_timeout = bound_stop_timeout(getattr(args, "stop_timeout", None))
    mountpoint_raw = getattr(args, "mountpoint", None) or _env_path(ENV_MOUNTPOINT)
    mountpoint = Path(mountpoint_raw).expanduser() if mountpoint_raw else None
    host = _detect_platform()

    if not state_dir.exists():
        # Idempotent: nothing to clean up.
        return {
            "ok": True,
            "schema": CLI_SCHEMA,
            "task_id": TASK_ID,
            "command": "unmount",
            "platform": host,
            "success": True,
            "idempotent": True,
            "disposition": "idempotent",
            "detail": {"state_dir_missing": True},
            "stop_timeout_seconds": stop_timeout,
            "state_directory": str(state_dir),
        }

    if host == "windows":
        result = unmount_windows_state(
            state_dir.resolve() if state_dir.exists() else state_dir,
            stop_timeout=stop_timeout,
            mount_root=str(mountpoint) if mountpoint else None,
        )
    else:
        result = unmount_linux_state(
            state_dir.resolve() if state_dir.exists() else state_dir,
            stop_timeout=stop_timeout,
            mountpoint=mountpoint,
        )

    envelope: dict[str, Any] = {
        "ok": bool(result.get("ok", result.get("success", True))),
        "schema": CLI_SCHEMA,
        "task_id": TASK_ID,
        "command": "unmount",
        "platform": host,
        "stop_timeout_seconds": stop_timeout,
        "state_directory": str(state_dir),
        "unmount": result,
        "success": bool(result.get("success", True)),
        "idempotent": bool(result.get("idempotent", False)),
        "disposition": result.get("disposition"),
        "pid": result.get("pid"),
        "pid_validation": result.get("pid_validation"),
    }
    return envelope


def format_unmount_human(envelope: Mapping[str, Any]) -> str:
    unmount = envelope.get("unmount") or {}
    lines = [
        f"Kernel VFS unmount  ok={envelope.get('ok')}  "
        f"success={envelope.get('success')}  "
        f"idempotent={envelope.get('idempotent')}",
        f"  disposition={envelope.get('disposition')}  pid={envelope.get('pid')}",
        f"  state_dir={envelope.get('state_directory')}",
        f"  stop_timeout={envelope.get('stop_timeout_seconds')}s",
    ]
    if isinstance(unmount, Mapping):
        lines.append(
            f"  lease_released={unmount.get('lease_released')}  "
            f"mount_released={unmount.get('mount_released')}  "
            f"recovery_preserved={unmount.get('recovery_preserved')}"
        )
        validation = unmount.get("pid_validation") or envelope.get("pid_validation")
        if isinstance(validation, Mapping):
            lines.append(
                f"  pid_validation: recorded={validation.get('recorded_pid')} "
                f"alive={validation.get('pid_alive')} "
                f"stale={validation.get('stale')} "
                f"lease_valid={validation.get('lease_valid')}"
            )
            for msg in validation.get("messages") or []:
                lines.append(f"    - {msg}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------


def build_parser(*, prog: str = PROGRAM_NAME) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=(
            "Kernel VFS mount/doctor/status/unmount CLI. "
            "Doctor never mounts. Mount defaults to foreground with readiness. "
            "Options use a closed safety allowlist."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            f"  {prog} doctor --json\n"
            f"  {prog} mount --foreground --readiness "
            f"--mountpoint /mnt/vfs --state-dir /var/lib/vfs/state\n"
            f"  {prog} status --state-dir /var/lib/vfs/state --json\n"
            f"  {prog} unmount --state-dir /var/lib/vfs/state --json\n"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{prog} ({TASK_ID} {CLI_SCHEMA})",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # -- doctor -------------------------------------------------------------
    doctor_p = sub.add_parser(
        "doctor",
        help="bounded platform capability probe (never mounts)",
    )
    _add_output_flags(doctor_p)
    doctor_p.add_argument(
        "--mountpoint",
        default=None,
        help="optional mountpoint for separation checks",
    )
    doctor_p.add_argument(
        "--state-dir",
        default=None,
        help="optional state directory for separation checks",
    )
    doctor_p.add_argument(
        "--budget-seconds",
        type=float,
        default=None,
        help=f"doctor time budget (max {MAX_DOCTOR_BUDGET_SECONDS}s)",
    )

    # -- mount --------------------------------------------------------------
    mount_p = sub.add_parser(
        "mount",
        help="mount with readiness; stays foreground by default",
    )
    _add_output_flags(mount_p)
    mount_p.add_argument(
        "--mountpoint",
        default=None,
        help="filesystem mountpoint (or IPFS_KIT_KERNEL_VFS_MOUNTPOINT)",
    )
    mount_p.add_argument(
        "--state-dir",
        default=None,
        help="durable state directory (or IPFS_KIT_KERNEL_VFS_STATE_DIR)",
    )
    mount_p.add_argument(
        "--wal-dir",
        default=None,
        help="optional WAL volume root (linked under state-dir/wal)",
    )
    mount_p.add_argument(
        "--cache-dir",
        default=None,
        help="optional ARC cache volume root (linked under state-dir/cache)",
    )
    mount_p.add_argument(
        "--ready-dir",
        default=None,
        help="optional readiness publish directory (mirrors ready.json)",
    )
    mount_p.add_argument(
        "--mount-id",
        default=None,
        help="stable mount identity (default: mount:cli-default)",
    )
    mount_p.add_argument(
        "--foreground",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="stay attached until signal/child exit (default: true)",
    )
    mount_p.add_argument(
        "--readiness",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="wait for recovery-before-ready handshake (default: true)",
    )
    mount_p.add_argument(
        "--readiness-timeout",
        type=float,
        default=None,
        help=(
            f"readiness timeout seconds "
            f"(default {DEFAULT_READINESS_TIMEOUT_SECONDS}, "
            f"max {MAX_READINESS_TIMEOUT_SECONDS})"
        ),
    )
    mount_p.add_argument(
        "--stop-timeout",
        type=float,
        default=None,
        help=(
            f"stop/unmount timeout seconds "
            f"(default {DEFAULT_STOP_TIMEOUT_SECONDS}, "
            f"max {MAX_STOP_TIMEOUT_SECONDS})"
        ),
    )
    mount_p.add_argument(
        "-o",
        "--option",
        dest="options",
        action="append",
        default=[],
        help="safe FUSE option (repeatable; closed allowlist)",
    )
    mount_p.add_argument(
        "--allow-other",
        action="store_true",
        default=False,
        help="explicit opt-in for allow_other (requires warning ack)",
    )
    mount_p.add_argument(
        "--acknowledge-allow-other-warning",
        action="store_true",
        default=False,
        help="acknowledge allow_other multi-user visibility warning",
    )
    mount_p.add_argument(
        "--hermetic",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="hermetic lifecycle without native FUSE (default: true)",
    )
    mount_p.add_argument(
        "--native",
        action="store_true",
        default=False,
        help="request native FUSE/WinFsp path (disables hermetic)",
    )

    # -- status -------------------------------------------------------------
    status_p = sub.add_parser(
        "status",
        help="show platform/mount/recovery/WAL/ARC/handles/errors/heartbeat",
    )
    _add_output_flags(status_p)
    status_p.add_argument(
        "--state-dir",
        default=None,
        help="state directory to read receipts from",
    )
    status_p.add_argument(
        "--mountpoint",
        default=None,
        help="optional mountpoint (informational)",
    )

    # -- unmount ------------------------------------------------------------
    unmount_p = sub.add_parser(
        "unmount",
        help="idempotent unmount with PID/lease validation",
    )
    _add_output_flags(unmount_p)
    unmount_p.add_argument(
        "--state-dir",
        default=None,
        help="state directory of the mount to stop",
    )
    unmount_p.add_argument(
        "--mountpoint",
        default=None,
        help="optional mountpoint (used when config is missing)",
    )
    unmount_p.add_argument(
        "--stop-timeout",
        type=float,
        default=None,
        help=(
            f"stop timeout seconds "
            f"(default {DEFAULT_STOP_TIMEOUT_SECONDS}, "
            f"max {MAX_STOP_TIMEOUT_SECONDS})"
        ),
    )
    unmount_p.add_argument(
        "--timeout",
        type=float,
        default=None,
        dest="timeout_alias",
        help="alias for --stop-timeout",
    )

    return parser


def _add_output_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="emit machine-readable JSON",
    )
    parser.add_argument(
        "--format",
        choices=("json", "human"),
        default=None,
        help="output format (json or human; --json implies json)",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    command = args.command
    if command == "doctor":
        return cmd_doctor(args)
    if command == "mount":
        return cmd_mount(args)
    if command == "status":
        return cmd_status(args)
    if command == "unmount":
        # Honour --timeout alias.
        if getattr(args, "timeout_alias", None) is not None and getattr(
            args, "stop_timeout", None
        ) is None:
            args.stop_timeout = args.timeout_alias
        return cmd_unmount(args)
    raise CLIError(f"unknown command: {command}", code="UNKNOWN_COMMAND", exit_code=EXIT_USAGE)


def format_envelope_human(envelope: Mapping[str, Any]) -> str:
    command = envelope.get("command")
    if command == "doctor":
        return format_doctor_human(envelope)
    if command == "mount":
        return format_mount_human(envelope)
    if command == "status":
        return format_status_cli_human(envelope)
    if command == "unmount":
        return format_unmount_human(envelope)
    return json.dumps(dict(envelope), indent=2, sort_keys=True) + "\n"


def run(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Parse *argv*, run the command, print output, return exit code."""

    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return EXIT_OK
        return int(code) if isinstance(code, int) else EXIT_USAGE

    out = stdout or sys.stdout
    err = stderr or sys.stderr
    as_json = _wants_json(args)

    try:
        envelope = dispatch(args)
    except CLIError as exc:
        payload = exc.to_record()
        payload["command"] = getattr(args, "command", None)
        if as_json:
            emit_json(payload, out)
        else:
            emit_human(f"error [{exc.code}]: {exc.message}", err)
        return exc.exit_code
    except Exception as exc:  # noqa: BLE001 — last-resort operator message
        payload = {
            "ok": False,
            "schema": CLI_SCHEMA,
            "task_id": TASK_ID,
            "command": getattr(args, "command", None),
            "error": type(exc).__name__,
            "code": "INTERNAL",
            "message": str(exc),
            "exit_code": EXIT_ERROR,
        }
        if as_json:
            emit_json(payload, out)
        else:
            emit_human(f"error [INTERNAL]: {exc}", err)
        return EXIT_ERROR

    if as_json:
        # Machine JSON must not embed the redundant human blob when large.
        payload = dict(envelope)
        payload.pop("human", None)
        emit_json(payload, out)
    else:
        emit_human(format_envelope_human(envelope), out)

    # Doctor always exits 0 when the probe completed (capability may be absent).
    # Status exits 0 when a report was produced (ok may be false for stale mounts).
    # Mount/unmount treat ok=False as a hard failure.
    command = envelope.get("command")
    if command in {"doctor", "status"}:
        return EXIT_OK
    if envelope.get("ok") is False:
        return EXIT_ERROR
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Console-script entry point."""

    return run(argv)


__all__ = [
    "TASK_ID",
    "CLI_SCHEMA",
    "PROGRAM_NAME",
    "DEFAULT_READINESS_TIMEOUT_SECONDS",
    "MAX_READINESS_TIMEOUT_SECONDS",
    "DEFAULT_STOP_TIMEOUT_SECONDS",
    "MAX_STOP_TIMEOUT_SECONDS",
    "ADMITTED_FUSE_OPTIONS",
    "ALWAYS_REJECTED_OPTIONS",
    "CLIError",
    "OptionValidationError",
    "TimeoutBoundError",
    "SafeMountOptions",
    "admit_safe_mount_options",
    "bound_readiness_timeout",
    "bound_stop_timeout",
    "bound_doctor_budget",
    "build_parser",
    "cmd_doctor",
    "cmd_mount",
    "cmd_status",
    "cmd_unmount",
    "dispatch",
    "run",
    "main",
]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
