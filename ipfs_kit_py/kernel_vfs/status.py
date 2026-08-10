"""KVFS-702: unified kernel VFS status schema and observability surface.

This module owns the **closed, operator-safe status envelope** used by the
mount CLI and any future observability exporters.  It aggregates platform,
mount, recovery/WAL, ARC, handle, error, and heartbeat signals without:

* embedding secrets (tokens, passwords, API keys, credentials);
* emitting high-cardinality per-path series (individual file paths, inode
  lists, open-handle path tables).

Lifecycle semantics (Linux / Windows mount start-stop) remain in
:mod:`ipfs_kit_py.kernel_vfs.linux` and :mod:`ipfs_kit_py.kernel_vfs.windows`.
This module only **reads** lifecycle receipts and **projects** them into the
stable ``KernelVFSStatus@1`` schema.

Importing this module is inert: no mounts, no native library loads, no
network I/O.
"""

from __future__ import annotations

import json
import os
import platform
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Final

# ---------------------------------------------------------------------------
# Identity / schema
# ---------------------------------------------------------------------------

TASK_ID: Final[str] = "KVFS-702"
CONTRACT_VERSION: Final[int] = 1
SCHEMA_MAJOR: Final[int] = 1
SCHEMA_MINOR: Final[int] = 0
SCHEMA_PATCH: Final[int] = 0
SCHEMA_VERSION: Final[str] = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}.{SCHEMA_PATCH}"

STATUS_NAMESPACE: Final[str] = "ipfs_kit_py/kernel_vfs/status"
STATUS_SCHEMA: Final[str] = f"{STATUS_NAMESPACE}@{SCHEMA_MAJOR}"
STATUS_ENVELOPE_SCHEMA: Final[str] = f"{STATUS_NAMESPACE}/envelope@{SCHEMA_MAJOR}"

# Public interface alias.
KernelVFSStatus_V1: Final[str] = STATUS_SCHEMA

# On-disk lifecycle filenames (must match linux.py / windows.py).
READY_FILENAME: Final[str] = "ready.json"
HEARTBEAT_FILENAME: Final[str] = "heartbeat.json"
STATUS_FILENAME: Final[str] = "status.json"
CHILD_PID_FILENAME: Final[str] = "child.pid"
CHILD_CONFIG_FILENAME: Final[str] = "child-config.json"
SHUTDOWN_FILENAME: Final[str] = "shutdown.json"
# Windows lifecycle uses alternate names under the state runtime tree.
WINDOWS_STATUS_FILENAME: Final[str] = "mount.status.json"
WINDOWS_HEARTBEAT_FILENAME: Final[str] = "mount.heartbeat.json"
WINDOWS_READY_FILENAME: Final[str] = "mount.ready.json"
WINDOWS_PROCESS_FILENAME: Final[str] = "mount.process.json"

# Bounds
MAX_ERROR_ENTRIES: Final[int] = 16
MAX_TEXT_BYTES: Final[int] = 4_096
MAX_PATH_DISPLAY_BYTES: Final[int] = 512
REDACTED: Final[str] = "[REDACTED]"

# Secret key fragments (case-insensitive substring match on mapping keys).
SECRET_KEY_FRAGMENTS: Final[tuple[str, ...]] = (
    "password",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "auth_token",
    "authorization",
    "credential",
    "private_key",
    "client_secret",
    "session_token",
    "cookie",
    "bearer",
)

# High-cardinality / path-list keys that must never appear as unbounded series.
HIGH_CARDINALITY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "paths",
        "path_list",
        "open_paths",
        "handle_paths",
        "inode_list",
        "inodes",
        "files",
        "file_list",
        "entries_by_path",
        "per_path",
        "path_stats",
        "path_metrics",
        "hot_paths",
        "recent_paths",
        "directory_listing",
        "readdir_names",
        "child_names",
    }
)

# Closed top-level status sections required by acceptance.
REQUIRED_STATUS_SECTIONS: Final[tuple[str, ...]] = (
    "platform",
    "mount",
    "recovery",
    "wal",
    "arc",
    "handles",
    "errors",
    "heartbeat",
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class StatusError(Exception):
    """Base error for status schema construction failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "STATUS_ERROR",
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.detail = dict(detail or {})

    def to_record(self) -> dict[str, Any]:
        return {
            "error": type(self).__name__,
            "message": self.message,
            "code": self.code,
            "detail": dict(self.detail),
        }


class StatusValidationError(StatusError):
    """Raised when a constructed status envelope fails closed validation."""

    def __init__(
        self,
        message: str,
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="STATUS_VALIDATION", detail=detail)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unix_ms() -> int:
    return int(time.time() * 1000)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _pid_is_zombie(pid: int) -> bool:
    """Best-effort zombie detection via /proc (Linux).

    Read-only: never waitpid here.  Status collection must not steal the
    lifecycle owner's child handle.
    """

    if pid <= 0:
        return False
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
    # Process may have become a zombie between kill(0) and this check.
    if _pid_is_zombie(pid):
        return False
    return True


def _clamp_text(value: Any, *, limit: int = MAX_TEXT_BYTES) -> str:
    text = "" if value is None else str(value)
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text
    # Truncate on byte boundary for display only.
    return encoded[: max(0, limit - 3)].decode("utf-8", errors="replace") + "..."


def _safe_path_display(value: Any) -> str:
    """Render a path for status without expanding into path series."""

    return _clamp_text(value, limit=MAX_PATH_DISPLAY_BYTES)


def _detect_platform_name() -> str:
    system = platform.system().lower()
    if system.startswith("linux"):
        return "linux"
    if system.startswith("windows") or system == "cygwin":
        return "windows"
    if system == "darwin":
        return "darwin"
    return system or "unknown"


# ---------------------------------------------------------------------------
# Secret redaction + high-cardinality suppression
# ---------------------------------------------------------------------------


def _key_looks_secret(key: str) -> bool:
    key_l = str(key).lower()
    return any(frag in key_l for frag in SECRET_KEY_FRAGMENTS)


_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*")
_PEM_RE = re.compile(r"-----BEGIN[^-]+-----.*?-----END[^-]+-----", re.DOTALL)


def redact_secrets(payload: Any) -> Any:
    """Recursively redact secret-looking keys and credential markers.

    Returns a deep copy with secrets replaced by :data:`REDACTED`.  Never
    raises on unexpected types.
    """

    if isinstance(payload, Mapping):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            if _key_looks_secret(str(key)):
                out[str(key)] = REDACTED
            else:
                out[str(key)] = redact_secrets(value)
        return out
    if isinstance(payload, list):
        return [redact_secrets(item) for item in payload]
    if isinstance(payload, tuple):
        return [redact_secrets(item) for item in payload]
    if isinstance(payload, str):
        if any(frag in payload.lower() for frag in SECRET_KEY_FRAGMENTS):
            # Value itself embeds a secret marker (e.g. "password=...").
            if "=" in payload or ":" in payload or "bearer" in payload.lower():
                return REDACTED
        if _BEARER_RE.search(payload) or _PEM_RE.search(payload):
            return REDACTED
        if "-----begin" in payload.lower():
            return REDACTED
        return payload
    return payload


def suppress_high_cardinality(payload: Any) -> Any:
    """Drop high-cardinality path lists and per-path series from a payload.

    Aggregate counters and closed identity fields are retained.  Nested
    mappings whose keys are themselves filesystem paths are collapsed to a
    count summary.
    """

    if isinstance(payload, Mapping):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            key_s = str(key)
            key_l = key_s.lower()
            if key_l in HIGH_CARDINALITY_KEYS or key_s in HIGH_CARDINALITY_KEYS:
                if isinstance(value, (list, tuple, set)):
                    out[key_s] = {"suppressed": True, "count": len(value)}
                elif isinstance(value, Mapping):
                    out[key_s] = {"suppressed": True, "count": len(value)}
                else:
                    out[key_s] = {"suppressed": True}
                continue
            # Collapse mappings that look like path→metric tables.
            if isinstance(value, Mapping) and value and _looks_like_path_table(value):
                out[key_s] = {
                    "suppressed": True,
                    "count": len(value),
                    "reason": "high_cardinality_path_table",
                }
                continue
            out[key_s] = suppress_high_cardinality(value)
        return out
    if isinstance(payload, list):
        # Unbounded path-like string lists are summarized.
        if payload and all(isinstance(item, str) and _looks_like_path(item) for item in payload):
            return {"suppressed": True, "count": len(payload), "reason": "path_list"}
        return [suppress_high_cardinality(item) for item in payload]
    if isinstance(payload, tuple):
        return suppress_high_cardinality(list(payload))
    return payload


def _looks_like_path(value: str) -> bool:
    if not value:
        return False
    if value.startswith(("/", "./", "../", "~/", "\\\\", "C:\\", "c:\\")):
        return True
    if "/" in value and not value.startswith(("mount:", "wal-gen:", "path:", "inode:")):
        # Relative multi-segment paths without a closed identity prefix.
        return True
    return False


def _looks_like_path_table(mapping: Mapping[str, Any]) -> bool:
    keys = list(mapping.keys())
    if not keys:
        return False
    sample = keys[: min(8, len(keys))]
    pathish = sum(1 for k in sample if _looks_like_path(str(k)))
    return pathish >= max(1, len(sample) // 2)


def sanitize_status_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Apply secret redaction then high-cardinality suppression."""

    cleaned = redact_secrets(dict(payload))
    if not isinstance(cleaned, dict):
        cleaned = {"value": cleaned}
    cleaned = suppress_high_cardinality(cleaned)
    if not isinstance(cleaned, dict):
        return {"value": cleaned}
    return cleaned


# ---------------------------------------------------------------------------
# Status record
# ---------------------------------------------------------------------------


@dataclass
class KernelVFSStatus:
    """Closed observability snapshot for one mount / state directory.

    Sections (all required in :meth:`to_record`):

    * ``platform`` — OS / architecture / host platform name
    * ``mount`` — mount identity, PID, lifecycle, lease, mountpoint/state roots
    * ``recovery`` — recovery completion and disposition (no WAL bodies)
    * ``wal`` — generation / position aggregates only
    * ``arc`` — generation / entry aggregates only
    * ``handles`` — open-handle / open-callback counts
    * ``errors`` — bounded recent error codes (no secret detail)
    * ``heartbeat`` — sequence, age, worker liveness
    """

    SCHEMA: ClassVar[str] = STATUS_SCHEMA

    platform: dict[str, Any] = field(default_factory=dict)
    mount: dict[str, Any] = field(default_factory=dict)
    recovery: dict[str, Any] = field(default_factory=dict)
    wal: dict[str, Any] = field(default_factory=dict)
    arc: dict[str, Any] = field(default_factory=dict)
    handles: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    heartbeat: dict[str, Any] = field(default_factory=dict)
    ok: bool = False
    ready: bool = False
    status_unix_ms: int = 0
    source: str = "state_directory"
    task_id: str = TASK_ID

    def to_record(self) -> dict[str, Any]:
        """Return a sanitized, closed status envelope."""

        raw: dict[str, Any] = {
            "schema": self.SCHEMA,
            "contract_version": CONTRACT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "task_id": self.task_id,
            "ok": bool(self.ok),
            "ready": bool(self.ready),
            "status_unix_ms": int(self.status_unix_ms or _unix_ms()),
            "source": str(self.source),
            "platform": dict(self.platform),
            "mount": dict(self.mount),
            "recovery": dict(self.recovery),
            "wal": dict(self.wal),
            "arc": dict(self.arc),
            "handles": dict(self.handles),
            "errors": [dict(item) for item in self.errors[:MAX_ERROR_ENTRIES]],
            "heartbeat": dict(self.heartbeat),
        }
        cleaned = sanitize_status_payload(raw)
        # Ensure required sections always exist after sanitization.
        for section in REQUIRED_STATUS_SECTIONS:
            cleaned.setdefault(section, {} if section != "errors" else [])
        if not isinstance(cleaned.get("errors"), list):
            cleaned["errors"] = []
        return cleaned

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_record(), indent=indent, sort_keys=True) + "\n"

    @classmethod
    def from_record(cls, payload: Mapping[str, Any]) -> "KernelVFSStatus":
        errors_raw = payload.get("errors") or []
        errors: list[dict[str, Any]] = []
        if isinstance(errors_raw, Sequence) and not isinstance(errors_raw, (str, bytes)):
            for item in errors_raw[:MAX_ERROR_ENTRIES]:
                if isinstance(item, Mapping):
                    errors.append(dict(item))
        return cls(
            platform=dict(payload.get("platform") or {}),
            mount=dict(payload.get("mount") or {}),
            recovery=dict(payload.get("recovery") or {}),
            wal=dict(payload.get("wal") or {}),
            arc=dict(payload.get("arc") or {}),
            handles=dict(payload.get("handles") or {}),
            errors=errors,
            heartbeat=dict(payload.get("heartbeat") or {}),
            ok=bool(payload.get("ok")),
            ready=bool(payload.get("ready")),
            status_unix_ms=int(payload.get("status_unix_ms") or 0),
            source=str(payload.get("source") or "state_directory"),
            task_id=str(payload.get("task_id") or TASK_ID),
        )


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def build_platform_section(
    *,
    platform_name: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the closed ``platform`` section (no secrets, no path series)."""

    name = platform_name or _detect_platform_name()
    section: dict[str, Any] = {
        "name": name,
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
    }
    if extra:
        for key, value in extra.items():
            if _key_looks_secret(str(key)):
                continue
            if str(key).lower() in HIGH_CARDINALITY_KEYS:
                continue
            section[str(key)] = value
    return section


def build_status_from_lifecycle_records(
    *,
    status_raw: Mapping[str, Any] | None = None,
    heartbeat_raw: Mapping[str, Any] | None = None,
    readiness_raw: Mapping[str, Any] | None = None,
    platform_extra: Mapping[str, Any] | None = None,
    source: str = "lifecycle",
    errors: Sequence[Mapping[str, Any]] | None = None,
) -> KernelVFSStatus:
    """Project Linux/Windows lifecycle receipts into :class:`KernelVFSStatus`."""

    status_raw = dict(status_raw or {})
    heartbeat_raw = dict(heartbeat_raw or {})
    readiness_raw = dict(readiness_raw or {})

    # Windows nests resources; Linux is flat.
    resources = status_raw.get("resources")
    if not isinstance(resources, Mapping):
        resources = heartbeat_raw.get("resources") if isinstance(
            heartbeat_raw.get("resources"), Mapping
        ) else {}
    resources = dict(resources or {})

    pid = int(
        status_raw.get("pid")
        or heartbeat_raw.get("pid")
        or resources.get("pid")
        or readiness_raw.get("pid")
        or 0
    )
    mountpoint = str(
        status_raw.get("mountpoint")
        or resources.get("mount_root")
        or readiness_raw.get("mountpoint")
        or heartbeat_raw.get("mountpoint")
        or ""
    )
    state_directory = str(
        status_raw.get("state_directory")
        or resources.get("state_directory")
        or readiness_raw.get("state_directory")
        or heartbeat_raw.get("state_directory")
        or ""
    )
    mount_id = str(
        status_raw.get("mount_id")
        or readiness_raw.get("mount_id")
        or heartbeat_raw.get("mount_id")
        or resources.get("mount_id")
        or ""
    )
    lifecycle_state = str(
        status_raw.get("lifecycle_state")
        or status_raw.get("state")
        or readiness_raw.get("lifecycle_state")
        or heartbeat_raw.get("lifecycle_state")
        or heartbeat_raw.get("state")
        or ""
    )
    ready = bool(
        status_raw.get("ready")
        if "ready" in status_raw
        else readiness_raw.get("ready", False)
    )
    recovery_complete = bool(
        status_raw.get("recovery_complete")
        if "recovery_complete" in status_raw
        else readiness_raw.get("recovery_complete", False)
    )
    lease_held = bool(status_raw.get("lease_held", False))
    if "resource_lease_held" in (status_raw.get("detail") or {}):
        detail = status_raw.get("detail") or {}
        if isinstance(detail, Mapping):
            lease_held = lease_held or bool(detail.get("resource_lease_held"))
            lease_held = lease_held or bool(detail.get("state_lease_held"))
    holder_id = str(
        status_raw.get("holder_id")
        or readiness_raw.get("holder_id")
        or resources.get("state_lease_holder_id")
        or ""
    )
    mounted = bool(status_raw.get("mounted", ready and pid > 0 and _pid_alive(pid)))

    wal_src = status_raw.get("wal") if isinstance(status_raw.get("wal"), Mapping) else {}
    if not wal_src and isinstance(heartbeat_raw.get("wal"), Mapping):
        wal_src = heartbeat_raw["wal"]  # type: ignore[assignment]
    if not wal_src and isinstance(readiness_raw.get("wal"), Mapping):
        wal_src = readiness_raw["wal"]  # type: ignore[assignment]
    wal_src = dict(wal_src or {})
    cache_src = (
        status_raw.get("cache") if isinstance(status_raw.get("cache"), Mapping) else {}
    )
    if not cache_src and isinstance(heartbeat_raw.get("cache"), Mapping):
        cache_src = heartbeat_raw["cache"]  # type: ignore[assignment]
    if not cache_src and isinstance(readiness_raw.get("cache"), Mapping):
        cache_src = readiness_raw["cache"]  # type: ignore[assignment]
    cache_src = dict(cache_src or {})

    workers_src = (
        status_raw.get("workers") if isinstance(status_raw.get("workers"), Mapping) else {}
    )
    workers_src = dict(workers_src or {})

    open_callbacks = int(
        status_raw.get("open_callbacks")
        or heartbeat_raw.get("open_callbacks")
        or 0
    )
    open_handles = int(
        status_raw.get("open_handles")
        or heartbeat_raw.get("open_handles")
        or open_callbacks
    )

    hb_ms = int(
        heartbeat_raw.get("heartbeat_unix_ms")
        or status_raw.get("heartbeat_unix_ms")
        or 0
    )
    status_ms = int(status_raw.get("status_unix_ms") or status_raw.get("unix_ms") or _unix_ms())
    sequence = int(heartbeat_raw.get("sequence") or heartbeat_raw.get("cycle") or 0)
    workers_running = int(
        heartbeat_raw.get("workers_running")
        or workers_src.get("running")
        or (1 if workers_src.get("worker_running") else 0)
    )

    error_items: list[dict[str, Any]] = []
    if errors:
        for item in errors[:MAX_ERROR_ENTRIES]:
            if isinstance(item, Mapping):
                error_items.append(
                    {
                        "code": _clamp_text(item.get("code") or item.get("error") or "error"),
                        "message": _clamp_text(item.get("message") or ""),
                    }
                )
    exit_code = status_raw.get("exit_code")
    if exit_code not in (None, 0) and ready is False:
        error_items.append(
            {
                "code": "MOUNT_EXIT",
                "message": f"mount exit_code={exit_code}",
            }
        )

    platform_name = _detect_platform_name()
    if resources.get("mount_root_kind"):
        platform_name = "windows"
    elif mountpoint and not str(mountpoint).startswith("/") and ":" in str(mountpoint):
        # Drive-letter style root.
        platform_name = "windows"

    platform_section = build_platform_section(
        platform_name=platform_name,
        extra=platform_extra,
    )

    mount_section = {
        "mount_id": mount_id,
        "pid": pid,
        "pid_alive": _pid_alive(pid) if pid else False,
        "mountpoint": _safe_path_display(mountpoint),
        "state_directory": _safe_path_display(state_directory),
        "lifecycle_state": lifecycle_state,
        "ready": ready,
        "mounted": mounted,
        "lease_held": lease_held,
        "holder_id": holder_id,
    }
    if resources.get("mount_root_kind"):
        mount_section["mount_root_kind"] = str(resources.get("mount_root_kind"))
    if resources.get("process_id"):
        mount_section["process_id"] = str(resources.get("process_id"))

    recovery_section = {
        "recovery_complete": recovery_complete,
        "required": True,
        "phases": list(readiness_raw.get("recovery_phases") or [])[:32],
    }

    wal_section = {
        "generation": str(
            wal_src.get("generation")
            or readiness_raw.get("wal_generation")
            or ""
        ),
        "position": str(wal_src.get("position") or ""),
        # Directory presence only — never list WAL segment paths.
        "directory_bound": bool(wal_src.get("directory") or resources.get("wal_directory")),
    }

    arc_section = {
        "generation": int(
            cache_src.get("generation")
            or readiness_raw.get("cache_generation")
            or status_raw.get("generation")
            or 0
        ),
        "entries": int(cache_src.get("entries") or 0),
        "directory_bound": bool(
            cache_src.get("directory") or resources.get("cache_directory")
        ),
    }

    handles_section = {
        "open_callbacks": open_callbacks,
        "open_handles": open_handles,
        "workers_running": workers_running,
    }

    heartbeat_section = {
        "sequence": sequence,
        "heartbeat_unix_ms": hb_ms,
        "age_seconds": (
            round(max(0.0, (status_ms - hb_ms) / 1000.0), 3) if hb_ms else None
        ),
        "workers_running": workers_running,
        "pid": pid,
    }

    ok = bool(ready and recovery_complete and (pid <= 0 or _pid_alive(pid)))

    return KernelVFSStatus(
        platform=platform_section,
        mount=mount_section,
        recovery=recovery_section,
        wal=wal_section,
        arc=arc_section,
        handles=handles_section,
        errors=error_items,
        heartbeat=heartbeat_section,
        ok=ok,
        ready=ready,
        status_unix_ms=status_ms,
        source=source,
    )


def collect_status_from_state_directory(
    state_directory: str | Path,
    *,
    platform_extra: Mapping[str, Any] | None = None,
) -> KernelVFSStatus:
    """Load lifecycle receipts from a state directory and build status.

    Works for both Linux (``status.json`` / ``heartbeat.json`` / ``ready.json``)
    and Windows (``mount.status.json`` / ``mount.heartbeat.json``) layouts.
    Missing files yield a not-ready status rather than raising.
    """

    state_dir = Path(state_directory)
    errors: list[dict[str, Any]] = []

    if not state_dir.exists():
        errors.append(
            {
                "code": "STATE_DIR_MISSING",
                "message": f"state directory does not exist: {_safe_path_display(state_dir)}",
            }
        )
        status = build_status_from_lifecycle_records(
            platform_extra=platform_extra,
            source="state_directory",
            errors=errors,
        )
        status.mount["state_directory"] = _safe_path_display(state_dir)
        status.ok = False
        status.ready = False
        return status

    # Prefer Linux filenames; fall back to Windows.
    status_raw = _read_json(state_dir / STATUS_FILENAME)
    if not status_raw:
        status_raw = _read_json(state_dir / WINDOWS_STATUS_FILENAME)
        runtime = state_dir / "runtime"
        if not status_raw and runtime.is_dir():
            status_raw = _read_json(runtime / WINDOWS_STATUS_FILENAME)

    heartbeat_raw = _read_json(state_dir / HEARTBEAT_FILENAME)
    if not heartbeat_raw:
        heartbeat_raw = _read_json(state_dir / WINDOWS_HEARTBEAT_FILENAME)
        runtime = state_dir / "runtime"
        if not heartbeat_raw and runtime.is_dir():
            heartbeat_raw = _read_json(runtime / WINDOWS_HEARTBEAT_FILENAME)

    readiness_raw = _read_json(state_dir / READY_FILENAME)
    if not readiness_raw:
        readiness_raw = _read_json(state_dir / WINDOWS_READY_FILENAME)
        runtime = state_dir / "runtime"
        if not readiness_raw and runtime.is_dir():
            readiness_raw = _read_json(runtime / WINDOWS_READY_FILENAME)

    # PID file is authoritative when status is absent.
    if not status_raw and not heartbeat_raw and not readiness_raw:
        pid_raw = _read_json(state_dir / CHILD_PID_FILENAME)
        if pid_raw:
            readiness_raw = {
                "pid": int(pid_raw.get("pid") or 0),
                "ready": False,
                "recovery_complete": False,
                "state_directory": str(state_dir),
            }
        else:
            errors.append(
                {
                    "code": "STATUS_UNAVAILABLE",
                    "message": "no status/heartbeat/ready receipts in state directory",
                }
            )

    # Validate PID vs lease if both present.
    pid = int(
        (heartbeat_raw or {}).get("pid")
        or (status_raw or {}).get("pid")
        or (readiness_raw or {}).get("pid")
        or 0
    )
    if pid and not _pid_alive(pid):
        errors.append(
            {
                "code": "STALE_PID",
                "message": f"recorded pid {pid} is not alive",
            }
        )

    result = build_status_from_lifecycle_records(
        status_raw=status_raw,
        heartbeat_raw=heartbeat_raw,
        readiness_raw=readiness_raw,
        platform_extra=platform_extra,
        source="state_directory",
        errors=errors,
    )
    if not result.mount.get("state_directory"):
        result.mount["state_directory"] = _safe_path_display(state_dir)
    # Stale PID cannot be ok/ready.
    if pid and not _pid_alive(pid):
        result.ok = False
        result.mount["pid_alive"] = False
    return result


def validate_status_record(payload: Mapping[str, Any]) -> list[str]:
    """Return a list of validation problems (empty means valid).

    Checks required sections and rejects secret/high-cardinality leakage.
    """

    problems: list[str] = []
    if not isinstance(payload, Mapping):
        return ["status payload must be a mapping"]

    for section in REQUIRED_STATUS_SECTIONS:
        if section not in payload:
            problems.append(f"missing required section: {section}")

    # Secret key scan on the closed envelope.
    def _scan(obj: Any, path: str) -> None:
        if isinstance(obj, Mapping):
            for key, value in obj.items():
                key_s = str(key)
                if _key_looks_secret(key_s):
                    problems.append(f"secret key present at {path}.{key_s}")
                if key_s.lower() in HIGH_CARDINALITY_KEYS:
                    # Allowed only when already suppressed to a count summary.
                    if not (
                        isinstance(value, Mapping) and value.get("suppressed") is True
                    ):
                        problems.append(
                            f"high-cardinality key not suppressed at {path}.{key_s}"
                        )
                _scan(value, f"{path}.{key_s}")
        elif isinstance(obj, list):
            for index, item in enumerate(obj[:32]):
                _scan(item, f"{path}[{index}]")

    _scan(payload, "status")
    return problems


def format_status_human(status: KernelVFSStatus | Mapping[str, Any]) -> str:
    """Render a multi-line human-readable status report."""

    if isinstance(status, KernelVFSStatus):
        record = status.to_record()
    else:
        record = sanitize_status_payload(dict(status))

    platform_s = record.get("platform") or {}
    mount = record.get("mount") or {}
    recovery = record.get("recovery") or {}
    wal = record.get("wal") or {}
    arc = record.get("arc") or {}
    handles = record.get("handles") or {}
    heartbeat = record.get("heartbeat") or {}
    errors = record.get("errors") or []

    lines = [
        f"Kernel VFS status  schema={record.get('schema')}  task={record.get('task_id')}",
        f"  ok={record.get('ok')}  ready={record.get('ready')}",
        (
            f"  platform: {platform_s.get('name')} "
            f"{platform_s.get('system')}/{platform_s.get('machine')} "
            f"python={platform_s.get('python_version')}"
        ),
        (
            f"  mount: id={mount.get('mount_id')} pid={mount.get('pid')} "
            f"alive={mount.get('pid_alive')} state={mount.get('lifecycle_state')} "
            f"mounted={mount.get('mounted')} lease_held={mount.get('lease_held')}"
        ),
        (
            f"  mountpoint={mount.get('mountpoint')} "
            f"state_dir={mount.get('state_directory')}"
        ),
        (
            f"  recovery: complete={recovery.get('recovery_complete')} "
            f"phases={len(recovery.get('phases') or [])}"
        ),
        (
            f"  wal: generation={wal.get('generation')} "
            f"position={wal.get('position')} bound={wal.get('directory_bound')}"
        ),
        (
            f"  arc: generation={arc.get('generation')} "
            f"entries={arc.get('entries')} bound={arc.get('directory_bound')}"
        ),
        (
            f"  handles: open={handles.get('open_handles')} "
            f"callbacks={handles.get('open_callbacks')} "
            f"workers={handles.get('workers_running')}"
        ),
        (
            f"  heartbeat: seq={heartbeat.get('sequence')} "
            f"age_s={heartbeat.get('age_seconds')} "
            f"unix_ms={heartbeat.get('heartbeat_unix_ms')}"
        ),
    ]
    if errors:
        lines.append(f"  errors ({len(errors)}):")
        for item in errors[:MAX_ERROR_ENTRIES]:
            if isinstance(item, Mapping):
                lines.append(
                    f"    - [{item.get('code')}] {item.get('message')}"
                )
            else:
                lines.append(f"    - {item}")
    else:
        lines.append("  errors: none")
    return "\n".join(lines) + "\n"


def merge_error(
    status: KernelVFSStatus,
    *,
    code: str,
    message: str,
) -> KernelVFSStatus:
    """Return a copy of *status* with an additional bounded error entry."""

    errors = list(status.errors)
    errors.append({"code": _clamp_text(code), "message": _clamp_text(message)})
    status.errors = errors[:MAX_ERROR_ENTRIES]
    status.ok = False
    return status


def assert_no_secrets(payload: Mapping[str, Any]) -> None:
    """Raise :class:`StatusValidationError` if secrets leak into *payload*."""

    problems = [
        p for p in validate_status_record(payload) if "secret" in p or "high-cardinality" in p
    ]
    # Also scan for secret key fragments more aggressively.
    def _walk(obj: Any) -> None:
        if isinstance(obj, Mapping):
            for key, value in obj.items():
                if _key_looks_secret(str(key)):
                    problems.append(f"secret key: {key}")
                _walk(value)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(payload)
    if problems:
        raise StatusValidationError(
            "status payload failed secret/cardinality policy",
            detail={"problems": problems[:32]},
        )


__all__ = [
    "TASK_ID",
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "STATUS_SCHEMA",
    "STATUS_ENVELOPE_SCHEMA",
    "KernelVFSStatus_V1",
    "REDACTED",
    "SECRET_KEY_FRAGMENTS",
    "HIGH_CARDINALITY_KEYS",
    "REQUIRED_STATUS_SECTIONS",
    "MAX_ERROR_ENTRIES",
    "StatusError",
    "StatusValidationError",
    "KernelVFSStatus",
    "redact_secrets",
    "suppress_high_cardinality",
    "sanitize_status_payload",
    "build_platform_section",
    "build_status_from_lifecycle_records",
    "collect_status_from_state_directory",
    "validate_status_record",
    "format_status_human",
    "merge_error",
    "assert_no_secrets",
]
