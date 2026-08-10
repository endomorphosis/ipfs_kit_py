"""KVFS-103: hermetic callback, path, handle, and fault fixture corpus.

Validates KernelVFSFixture@1 / FaultSchedule@1 / ExpectedStateTrace@1 records
and the frozen content-identified FixtureManifest@1 at manifest.json.

Coverage (acceptance):
- every required and explicit-unsupported host callback
- open flag combinations (O_CREAT/O_EXCL/O_TRUNC/O_APPEND)
- traversal and Unicode/case path edges
- partial/sparse I/O
- rename/unlink while open (handle survival)
- concurrent faults
- WAL crash points
- corrupt ARC
- WinFsp name policy edges
- Docker capability failures
- exact expected traces

Conflict policy: inert bounded fixture data only — no native driver, credential,
network, user path, or executable payload.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Final, Iterable, Mapping, Sequence

import pytest

from ipfs_kit_py.core.vfs import host_contracts as hc

# ---------------------------------------------------------------------------
# Schema identities
# ---------------------------------------------------------------------------

KERNEL_VFS_FIXTURE_SCHEMA: Final[str] = "ipfs_kit_py/kernel-vfs/fixture@1"
FAULT_SCHEDULE_SCHEMA: Final[str] = "ipfs_kit_py/kernel-vfs/fault-schedule@1"
EXPECTED_STATE_TRACE_SCHEMA: Final[str] = (
    "ipfs_kit_py/kernel-vfs/expected-state-trace@1"
)
FIXTURE_MANIFEST_SCHEMA: Final[str] = "ipfs_kit_py/kernel-vfs/fixture-manifest@1"
MANIFEST_ID: Final[str] = "manifest:kernel-vfs-fixtures@1"
INTERFACE_BUNDLE: Final[str] = (
    "KernelVFSFixture@1+FaultSchedule@1+ExpectedStateTrace@1"
)
TASK_ID: Final[str] = "KVFS-103"

FIXTURES_DIR: Final[Path] = Path(__file__).resolve().parent
MANIFEST_PATH: Final[Path] = FIXTURES_DIR / "manifest.json"

MAX_TRACE_STEPS: Final[int] = 64
MAX_FAULTS: Final[int] = 32
MAX_FIXTURES: Final[int] = 256
MAX_STRING_LEN: Final[int] = 512

# ---------------------------------------------------------------------------
# Required coverage categories (acceptance surface)
# ---------------------------------------------------------------------------

REQUIRED_COVERAGE_CATEGORIES: Final[tuple[str, ...]] = (
    "callback_required",
    "callback_unsupported",
    "flag_combination",
    "path_traversal",
    "unicode_case",
    "partial_sparse_io",
    "rename_unlink_while_open",
    "concurrent_fault",
    "wal_crash_point",
    "corrupt_arc",
    "winfsp_name",
    "docker_capability",
    "expected_trace",
)

ALLOWED_POLARITIES: Final[frozenset[str]] = frozenset(
    {"positive", "adversarial", "differential"}
)

ALLOWED_FAULT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "crash_before_commit",
        "crash_after_intent",
        "crash_after_commit",
        "corrupt_arc",
        "torn_write",
        "concurrent_rename",
        "concurrent_unlink",
        "handle_lease_expiry",
        "docker_missing_device",
        "docker_missing_cap",
        "path_escape",
        "case_fold_collision",
        "reserved_device_name",
        "resource_exhaustion",
        "cancellation",
        "timeout",
    }
)

ALLOWED_TRACE_STATES: Final[frozenset[str]] = frozenset(
    {
        "ready",
        "accepted",
        "staged",
        "intent_appended",
        "committed",
        "recovered",
        "denied",
        "failed",
        "capability_absent",
        "handle_open",
        "handle_released",
        "namespace_mutated",
        "cache_miss",
        "cache_invalidated",
    }
)

ALLOWED_TERMINAL_OUTCOMES: Final[frozenset[str]] = frozenset(
    {
        "success",
        "denied",
        "error",
        "capability_absent",
        "contract_violation_observed",
        "recovered",
    }
)

# Stable required / unsupported callback names from host contracts.
REQUIRED_CALLBACKS: Final[tuple[str, ...]] = tuple(
    sorted(k.value for k in hc.REQUIRED_SUPPORTED_CALLBACKS)
)
UNSUPPORTED_CALLBACKS: Final[tuple[str, ...]] = tuple(
    sorted(k.value for k in hc.EXPLICIT_UNSUPPORTED_CALLBACKS)
)

# Flag combinations that must have explicit state-machine traces (plan §3.3).
FLAG_COMBINATIONS: Final[tuple[tuple[str, ...], ...]] = (
    ("O_RDONLY",),
    ("O_WRONLY", "O_CREAT"),
    ("O_RDWR", "O_CREAT", "O_EXCL"),
    ("O_WRONLY", "O_CREAT", "O_TRUNC"),
    ("O_WRONLY", "O_APPEND"),
    ("O_RDWR", "O_CREAT", "O_EXCL", "O_TRUNC"),
)

# Safety: patterns that must never appear in the hermetic corpus.
_BANNED_NETWORK = re.compile(
    r"(?i)\bhttps?://|\bftp://|\bws[s]?://|\bfile://|\bgit@"
)
_BANNED_USER_PATH = re.compile(
    r"(?i)(/home/|/users/|\\\\users\\\\|\$home|~[a-z0-9_]|c:\\\\users)"
)
_BANNED_SECRET_KEYS: Final[frozenset[str]] = frozenset(
    {
        "password",
        "secret",
        "secret_key",
        "api_key",
        "token",
        "private_key",
        "credential",
        "passwd",
    }
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class FixtureValidationError(ValueError):
    """Raised when a fixture or manifest fails schema/safety validation."""

    def __init__(self, message: str, *, reason_codes: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.reason_codes = tuple(reason_codes)


class SafetyViolation(FixtureValidationError):
    """Raised when a fixture violates hermetic safety policy."""


# ---------------------------------------------------------------------------
# Content addressing
# ---------------------------------------------------------------------------


def canonical_json(value: Any) -> str:
    """Deterministic JSON for content addressing (sorted keys, no whitespace)."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def content_id_for(value: Any) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _with_content_id(body: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(body)
    out["content_id"] = content_id_for(out)
    return out


# ---------------------------------------------------------------------------
# Compact recipes (no full envelopes / content ids)
# ---------------------------------------------------------------------------

Recipe = dict[str, Any]


def _step(
    index: int,
    state: str,
    *,
    operation: str | None = None,
    error_code: str | None = None,
    observed_effect: str = "none",
    state_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "index": index,
        "state": state,
        "operation": operation,
        "error_code": error_code,
        "observed_effect": observed_effect,
        "state_snapshot": dict(state_snapshot or {}),
    }


def _terminal(
    outcome: str,
    *,
    namespace: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "namespace": dict(namespace or {}),
        "evidence": dict(evidence or {}),
        "error_code": error_code,
    }


def _recipe(
    slug: str,
    *,
    categories: Sequence[str],
    polarity: str,
    description: str,
    steps: Sequence[Mapping[str, Any]],
    terminal: Mapping[str, Any],
    faults: Sequence[Mapping[str, Any]] = (),
    initial_state: Mapping[str, Any] | None = None,
    callback: str | None = None,
    flags: Sequence[str] = (),
    platform: str = "hermetic",
) -> Recipe:
    return {
        "slug": slug,
        "categories": list(categories),
        "polarity": polarity,
        "description": description,
        "steps": list(steps),
        "terminal": dict(terminal),
        "faults": list(faults),
        "initial_state": dict(initial_state or {}),
        "callback": callback,
        "flags": list(flags),
        "platform": platform,
    }


def _callback_recipes() -> list[Recipe]:
    recipes: list[Recipe] = []
    for name in REQUIRED_CALLBACKS:
        recipes.append(
            _recipe(
                f"callback-required-{name}",
                categories=("callback_required", "expected_trace"),
                polarity="positive",
                description=f"Required host callback {name} succeeds with exact trace",
                callback=name,
                steps=(
                    _step(0, "ready", operation="init"),
                    _step(
                        1,
                        "accepted",
                        operation=name,
                        observed_effect="callback_projected",
                        state_snapshot={"callback": name, "disposition": "required_supported"},
                    ),
                    _step(2, "committed", operation=name, observed_effect="acknowledged"),
                ),
                terminal=_terminal(
                    "success",
                    evidence={"callback": name, "false_success": False},
                ),
            )
        )
    for name in UNSUPPORTED_CALLBACKS:
        errno = hc.default_unsupported_errno(name).value
        recipes.append(
            _recipe(
                f"callback-unsupported-{name}",
                categories=("callback_unsupported", "expected_trace"),
                polarity="adversarial",
                description=(
                    f"Explicit-unsupported callback {name} returns {errno} "
                    "without false success"
                ),
                callback=name,
                steps=(
                    _step(0, "ready", operation="init"),
                    _step(
                        1,
                        "denied",
                        operation=name,
                        error_code=errno,
                        observed_effect="explicit_unsupported",
                        state_snapshot={
                            "callback": name,
                            "disposition": "explicit_unsupported",
                            "errno": errno,
                        },
                    ),
                ),
                terminal=_terminal(
                    "denied",
                    evidence={
                        "callback": name,
                        "errno": errno,
                        "false_success": False,
                    },
                    error_code=errno,
                ),
            )
        )
    return recipes


def _flag_recipes() -> list[Recipe]:
    recipes: list[Recipe] = []
    for flags in FLAG_COMBINATIONS:
        slug = "flags-" + "-".join(f.removeprefix("O_").lower() for f in flags)
        creates = "O_CREAT" in flags
        exclusive = "O_EXCL" in flags
        truncates = "O_TRUNC" in flags
        appends = "O_APPEND" in flags
        recipes.append(
            _recipe(
                slug,
                categories=("flag_combination", "expected_trace"),
                polarity="positive",
                description=f"Open/create flag combination {'|'.join(flags)}",
                callback="create" if creates else "open",
                flags=flags,
                initial_state={
                    "path": "ns/file.bin",
                    "exists": not exclusive,
                    "size": 64 if not truncates else 0,
                },
                steps=(
                    _step(0, "ready"),
                    _step(
                        1,
                        "handle_open",
                        operation="create" if creates else "open",
                        observed_effect="handle_issued",
                        state_snapshot={
                            "flags": list(flags),
                            "generation": 1,
                            "append": appends,
                            "truncated": truncates,
                        },
                    ),
                    _step(
                        2,
                        "committed" if creates or truncates else "accepted",
                        operation="release",
                        observed_effect="handle_reclaimed",
                    ),
                ),
                terminal=_terminal(
                    "success",
                    evidence={
                        "flags": list(flags),
                        "handle_generation_tagged": True,
                    },
                ),
            )
        )
    return recipes


def _specialized_recipes() -> list[Recipe]:
    return [
        _recipe(
            "path-traversal-dotdot",
            categories=("path_traversal", "expected_trace"),
            polarity="adversarial",
            description="Parent-traversal path is denied without namespace mutation",
            callback="open",
            initial_state={"path": "ns/../escape"},
            steps=(
                _step(0, "ready"),
                _step(
                    1,
                    "denied",
                    operation="open",
                    error_code="EPERM",
                    observed_effect="path_escape_blocked",
                    state_snapshot={"path": "ns/../escape", "normalized_rejected": True},
                ),
            ),
            terminal=_terminal(
                "denied",
                namespace={"escape": False},
                evidence={"mutated": False, "path_escape": True},
                error_code="EPERM",
            ),
            faults=(
                {
                    "kind": "path_escape",
                    "at_operation_index": 1,
                    "effects": ["reject"],
                    "parameters": {"path": "ns/../escape"},
                },
            ),
        ),
        _recipe(
            "path-absolute-escape",
            categories=("path_traversal", "expected_trace"),
            polarity="adversarial",
            description="Absolute host path is rejected as non-hermetic escape",
            callback="mkdir",
            initial_state={"path": "/ABS/kvfs-escape-probe"},
            steps=(
                _step(0, "ready"),
                _step(
                    1,
                    "denied",
                    operation="mkdir",
                    error_code="EPERM",
                    observed_effect="path_escape_blocked",
                    state_snapshot={
                        "path": "/ABS/kvfs-escape-probe",
                        "absolute": True,
                    },
                ),
            ),
            terminal=_terminal(
                "denied",
                evidence={"mutated": False, "absolute_path_rejected": True},
                error_code="EPERM",
            ),
            faults=(
                {
                    "kind": "path_escape",
                    "at_operation_index": 1,
                    "effects": ["reject"],
                    "parameters": {"path": "/ABS/kvfs-escape-probe"},
                },
            ),
        ),
        _recipe(
            "unicode-nfc-nfd-identity",
            categories=("unicode_case", "expected_trace"),
            polarity="differential",
            description="NFC/NFD Unicode path forms resolve under declared identity policy",
            callback="getattr",
            platform="hermetic",
            initial_state={
                "display_name": "caf\u00e9.txt",
                "lookup_identity": "cafe\u0301.txt",
            },
            steps=(
                _step(0, "ready"),
                _step(
                    1,
                    "accepted",
                    operation="getattr",
                    observed_effect="identity_resolved",
                    state_snapshot={
                        "display_spelling_preserved": True,
                        "lookup_collided": False,
                    },
                ),
            ),
            terminal=_terminal(
                "success",
                evidence={"unicode_normalization": "policy_bound"},
            ),
        ),
        _recipe(
            "case-only-rename-linux",
            categories=("unicode_case", "expected_trace"),
            polarity="positive",
            description="Case-only rename on case-sensitive Linux namespace",
            callback="rename",
            platform="linux",
            initial_state={"src": "ns/ReadMe", "dst": "ns/readme"},
            steps=(
                _step(0, "ready"),
                _step(
                    1,
                    "namespace_mutated",
                    operation="rename",
                    observed_effect="renamed",
                    state_snapshot={"src": "ns/ReadMe", "dst": "ns/readme"},
                ),
                _step(2, "committed", operation="rename"),
            ),
            terminal=_terminal(
                "success",
                namespace={"ns/readme": True, "ns/ReadMe": False},
                evidence={"mutated": True, "case_only": True},
            ),
        ),
        _recipe(
            "case-fold-collision-windows",
            categories=("unicode_case", "winfsp_name", "expected_trace"),
            polarity="adversarial",
            description="Ambiguous case-fold collision fails closed on WinFsp volume",
            callback="create",
            platform="windows",
            initial_state={"existing": "ns/File.txt", "create": "ns/file.TXT"},
            steps=(
                _step(0, "ready"),
                _step(
                    1,
                    "denied",
                    operation="create",
                    error_code="EEXIST",
                    observed_effect="case_fold_collision",
                    state_snapshot={"collision": True},
                ),
            ),
            terminal=_terminal(
                "denied",
                evidence={"mutated": False, "fail_closed": True},
                error_code="EEXIST",
            ),
            faults=(
                {
                    "kind": "case_fold_collision",
                    "at_operation_index": 1,
                    "effects": ["reject"],
                    "parameters": {"left": "File.txt", "right": "file.TXT"},
                },
            ),
        ),
        _recipe(
            "partial-sparse-write",
            categories=("partial_sparse_io", "expected_trace"),
            polarity="positive",
            description="Partial write beyond EOF creates sparse hole with exact extents",
            callback="write",
            initial_state={"path": "ns/sparse.bin", "size": 0, "handle": 7},
            steps=(
                _step(0, "handle_open", state_snapshot={"handle": 7, "generation": 3}),
                _step(
                    1,
                    "staged",
                    operation="write",
                    observed_effect="extent_staged",
                    state_snapshot={
                        "offset": 4096,
                        "length": 128,
                        "hole_before": 4096,
                        "dirty_in_handle_only": True,
                    },
                ),
                _step(
                    2,
                    "committed",
                    operation="fsync",
                    observed_effect="wal_and_backend_durable",
                ),
            ),
            terminal=_terminal(
                "success",
                evidence={
                    "sparse": True,
                    "arc_contains_only_committed": True,
                    "read_own_writes": True,
                },
            ),
        ),
        _recipe(
            "partial-read-hole",
            categories=("partial_sparse_io", "expected_trace"),
            polarity="positive",
            description="Read of sparse hole returns zeroes without fabricating content",
            callback="read",
            initial_state={"path": "ns/sparse.bin", "size": 4224, "handle": 8},
            steps=(
                _step(0, "handle_open"),
                _step(
                    1,
                    "accepted",
                    operation="read",
                    observed_effect="zero_fill_hole",
                    state_snapshot={"offset": 0, "length": 64, "bytes_are_zero": True},
                ),
            ),
            terminal=_terminal(
                "success",
                evidence={"hole_read": True, "content_fabricated": False},
            ),
        ),
        _recipe(
            "rename-while-open",
            categories=("rename_unlink_while_open", "expected_trace"),
            polarity="positive",
            description="Rename does not invalidate an already-open generation-tagged handle",
            callback="rename",
            initial_state={
                "path": "ns/a.txt",
                "handle": 11,
                "generation": 5,
                "open": True,
            },
            steps=(
                _step(
                    0,
                    "handle_open",
                    state_snapshot={"handle": 11, "path": "ns/a.txt", "generation": 5},
                ),
                _step(
                    1,
                    "namespace_mutated",
                    operation="rename",
                    observed_effect="renamed",
                    state_snapshot={"src": "ns/a.txt", "dst": "ns/b.txt"},
                ),
                _step(
                    2,
                    "accepted",
                    operation="read",
                    observed_effect="handle_still_valid",
                    state_snapshot={"handle": 11, "generation": 5},
                ),
                _step(3, "committed", operation="release"),
            ),
            terminal=_terminal(
                "success",
                namespace={"ns/b.txt": True, "ns/a.txt": False},
                evidence={"handle_survived_rename": True, "mutated": True},
            ),
        ),
        _recipe(
            "unlink-while-open",
            categories=("rename_unlink_while_open", "expected_trace"),
            polarity="positive",
            description="Unlink removes namespace entry but open handle remains usable",
            callback="unlink",
            initial_state={
                "path": "ns/victim.txt",
                "handle": 12,
                "generation": 9,
                "open": True,
            },
            steps=(
                _step(0, "handle_open", state_snapshot={"handle": 12, "generation": 9}),
                _step(
                    1,
                    "namespace_mutated",
                    operation="unlink",
                    observed_effect="unlinked",
                    state_snapshot={"path": "ns/victim.txt", "nlink": 0},
                ),
                _step(
                    2,
                    "staged",
                    operation="write",
                    observed_effect="handle_write_ok",
                    state_snapshot={"handle": 12, "offset": 0, "length": 4},
                ),
                _step(
                    3,
                    "handle_released",
                    operation="release",
                    observed_effect="last_close_reclaims",
                ),
            ),
            terminal=_terminal(
                "success",
                namespace={"ns/victim.txt": False},
                evidence={"handle_survived_unlink": True, "mutated": True},
            ),
        ),
        _recipe(
            "concurrent-rename-unlink-fault",
            categories=("concurrent_fault", "expected_trace"),
            polarity="adversarial",
            description="Concurrent rename and unlink serialize under path/handle locks",
            callback="rename",
            steps=(
                _step(0, "ready"),
                _step(
                    1,
                    "accepted",
                    operation="rename",
                    observed_effect="lock_acquired",
                    state_snapshot={"lock": "path:ns/x"},
                ),
                _step(
                    2,
                    "failed",
                    operation="unlink",
                    error_code="EBUSY",
                    observed_effect="contended",
                ),
                _step(3, "committed", operation="rename"),
            ),
            terminal=_terminal(
                "success",
                evidence={
                    "serialized": True,
                    "lost_update": False,
                    "duplicate_effect": False,
                },
            ),
            faults=(
                {
                    "kind": "concurrent_rename",
                    "at_operation_index": 1,
                    "effects": ["contend"],
                    "parameters": {"peers": 2},
                },
                {
                    "kind": "concurrent_unlink",
                    "at_operation_index": 2,
                    "effects": ["reject_busy"],
                    "parameters": {"path": "ns/x"},
                },
            ),
        ),
        _recipe(
            "wal-crash-before-commit",
            categories=("wal_crash_point", "expected_trace"),
            polarity="adversarial",
            description="Crash after WAL intent but before commit recovers without effect",
            callback="write",
            steps=(
                _step(0, "handle_open"),
                _step(
                    1,
                    "intent_appended",
                    operation="write",
                    observed_effect="wal_intent",
                    state_snapshot={"wal_pos": 42, "committed": False},
                ),
                _step(
                    2,
                    "failed",
                    operation="crash",
                    error_code="EIO",
                    observed_effect="crash_before_commit",
                ),
                _step(
                    3,
                    "recovered",
                    operation="recover",
                    observed_effect="intent_rolled_back",
                    state_snapshot={"applied": False},
                ),
            ),
            terminal=_terminal(
                "recovered",
                evidence={
                    "effect_applied": False,
                    "duplicate_effect": False,
                    "wal_crash_point": "before_commit",
                },
            ),
            faults=(
                {
                    "kind": "crash_before_commit",
                    "at_operation_index": 2,
                    "effects": ["abort_intent"],
                    "parameters": {"wal_pos": 42},
                },
            ),
        ),
        _recipe(
            "wal-crash-after-commit",
            categories=("wal_crash_point", "expected_trace"),
            polarity="adversarial",
            description="Crash after commit replays decision identity exactly once",
            callback="fsync",
            steps=(
                _step(0, "intent_appended", operation="write"),
                _step(
                    1,
                    "committed",
                    operation="fsync",
                    observed_effect="decision_identity",
                    state_snapshot={"wal_pos": 77, "decision": "dec:77"},
                ),
                _step(
                    2,
                    "failed",
                    operation="crash",
                    error_code="EIO",
                    observed_effect="crash_after_commit",
                ),
                _step(
                    3,
                    "recovered",
                    operation="recover",
                    observed_effect="replay_idempotent",
                    state_snapshot={"applied_once": True},
                ),
            ),
            terminal=_terminal(
                "recovered",
                evidence={
                    "effect_applied": True,
                    "duplicate_effect": False,
                    "wal_crash_point": "after_commit",
                },
            ),
            faults=(
                {
                    "kind": "crash_after_commit",
                    "at_operation_index": 2,
                    "effects": ["replay"],
                    "parameters": {"wal_pos": 77},
                },
            ),
        ),
        _recipe(
            "corrupt-arc-safe-miss",
            categories=("corrupt_arc", "expected_trace"),
            polarity="adversarial",
            description="Corrupt or stale ARC entry is a safe miss after recovery",
            callback="read",
            steps=(
                _step(0, "ready"),
                _step(
                    1,
                    "cache_invalidated",
                    operation="admit_arc",
                    observed_effect="corrupt_rejected",
                    state_snapshot={"generation": 0, "stale": True},
                ),
                _step(
                    2,
                    "cache_miss",
                    operation="read",
                    observed_effect="backend_fetch",
                    state_snapshot={"served_from_arc": False},
                ),
                _step(3, "accepted", operation="read"),
            ),
            terminal=_terminal(
                "success",
                evidence={
                    "stale_hit": False,
                    "safe_miss": True,
                    "corrupt_arc_admitted": False,
                },
            ),
            faults=(
                {
                    "kind": "corrupt_arc",
                    "at_operation_index": 1,
                    "effects": ["reject_entry"],
                    "parameters": {"key": "arc:ns/file@gen0"},
                },
            ),
        ),
        _recipe(
            "winfsp-reserved-device-name",
            categories=("winfsp_name", "expected_trace"),
            polarity="adversarial",
            description="Windows reserved device name is rejected by name policy",
            callback="create",
            platform="windows",
            initial_state={"name": "CON"},
            steps=(
                _step(0, "ready"),
                _step(
                    1,
                    "denied",
                    operation="create",
                    error_code="EINVAL",
                    observed_effect="reserved_name_rejected",
                    state_snapshot={"name": "CON"},
                ),
            ),
            terminal=_terminal(
                "denied",
                evidence={"reserved_device_name": True, "mutated": False},
                error_code="EINVAL",
            ),
            faults=(
                {
                    "kind": "reserved_device_name",
                    "at_operation_index": 1,
                    "effects": ["reject"],
                    "parameters": {"name": "CON"},
                },
            ),
        ),
        _recipe(
            "winfsp-trailing-dot-space",
            categories=("winfsp_name", "expected_trace"),
            polarity="adversarial",
            description="Trailing dots/spaces on Windows names fail closed",
            callback="mkdir",
            platform="windows",
            initial_state={"name": "dir. "},
            steps=(
                _step(0, "ready"),
                _step(
                    1,
                    "denied",
                    operation="mkdir",
                    error_code="EINVAL",
                    observed_effect="trailing_rejected",
                    state_snapshot={"name": "dir. "},
                ),
            ),
            terminal=_terminal(
                "denied",
                evidence={"trailing_dot_space": True, "mutated": False},
                error_code="EINVAL",
            ),
        ),
        _recipe(
            "docker-missing-dev-fuse",
            categories=("docker_capability", "expected_trace"),
            polarity="adversarial",
            description="Container without /dev/fuse reports capability absence",
            callback="init",
            platform="linux",
            steps=(
                _step(0, "ready"),
                _step(
                    1,
                    "capability_absent",
                    operation="init",
                    error_code="ENODEV",
                    observed_effect="doctor_absent",
                    state_snapshot={
                        "device": "/dev/fuse",
                        "present": False,
                        "privileged": False,
                    },
                ),
            ),
            terminal=_terminal(
                "capability_absent",
                evidence={
                    "docker_capability": "missing_device",
                    "native_mount_attempted": False,
                },
                error_code="ENODEV",
            ),
            faults=(
                {
                    "kind": "docker_missing_device",
                    "at_operation_index": 1,
                    "effects": ["capability_error"],
                    "parameters": {"device": "/dev/fuse"},
                },
            ),
        ),
        _recipe(
            "docker-missing-sys-admin",
            categories=("docker_capability", "expected_trace"),
            polarity="adversarial",
            description="Container without SYS_ADMIN does not claim FUSE readiness",
            callback="init",
            platform="linux",
            steps=(
                _step(0, "ready"),
                _step(
                    1,
                    "capability_absent",
                    operation="init",
                    error_code="EPERM",
                    observed_effect="doctor_absent",
                    state_snapshot={
                        "cap_sys_admin": False,
                        "device": "/dev/fuse",
                        "present": True,
                    },
                ),
            ),
            terminal=_terminal(
                "capability_absent",
                evidence={
                    "docker_capability": "missing_cap",
                    "blanket_privileged_forbidden": True,
                    "native_mount_attempted": False,
                },
                error_code="EPERM",
            ),
            faults=(
                {
                    "kind": "docker_missing_cap",
                    "at_operation_index": 1,
                    "effects": ["capability_error"],
                    "parameters": {"cap": "SYS_ADMIN"},
                },
            ),
        ),
        _recipe(
            "handle-lease-expiry-reclaim",
            categories=("concurrent_fault", "expected_trace"),
            polarity="adversarial",
            description="Expired handle lease is reclaimed without double-free",
            callback="release",
            steps=(
                _step(
                    0,
                    "handle_open",
                    state_snapshot={"handle": 99, "generation": 2, "lease_ms": 0},
                ),
                _step(
                    1,
                    "failed",
                    operation="read",
                    error_code="EBADF",
                    observed_effect="lease_expired",
                ),
                _step(
                    2,
                    "handle_released",
                    operation="release",
                    observed_effect="idempotent_reclaim",
                ),
            ),
            terminal=_terminal(
                "error",
                evidence={"double_free": False, "lease_reclaimed": True},
                error_code="EBADF",
            ),
            faults=(
                {
                    "kind": "handle_lease_expiry",
                    "at_operation_index": 1,
                    "effects": ["invalidate_handle"],
                    "parameters": {"handle": 99},
                },
            ),
        ),
    ]


def all_recipes() -> tuple[Recipe, ...]:
    recipes = _callback_recipes() + _flag_recipes() + _specialized_recipes()
    slugs = [r["slug"] for r in recipes]
    if len(slugs) != len(set(slugs)):
        raise FixtureValidationError("duplicate recipe slugs", reason_codes=("duplicate",))
    return tuple(recipes)


# ---------------------------------------------------------------------------
# Expansion
# ---------------------------------------------------------------------------


def _expand_fault_schedule(
    slug: str, faults: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    if not faults:
        return None
    body_faults: list[dict[str, Any]] = []
    for fault in faults:
        core = {
            "kind": fault["kind"],
            "at_operation_index": int(fault["at_operation_index"]),
            "effects": list(fault.get("effects", ())),
            "parameters": dict(fault.get("parameters", {})),
        }
        body_faults.append(_with_content_id(core))
    schedule_body = {
        "schema": FAULT_SCHEDULE_SCHEMA,
        "schedule_id": f"fault-schedule:{slug}@1",
        "faults": body_faults,
        "finite": True,
        "safe": True,
    }
    return _with_content_id(schedule_body)


def _expand_trace(slug: str, recipe: Mapping[str, Any]) -> dict[str, Any]:
    steps_out: list[dict[str, Any]] = []
    for step in recipe.get("steps", ()):
        core = {
            "index": int(step["index"]),
            "state": step["state"],
            "operation": step.get("operation"),
            "error_code": step.get("error_code"),
            "observed_effect": step.get("observed_effect", "none"),
            "state_snapshot": dict(step.get("state_snapshot") or {}),
        }
        steps_out.append(_with_content_id(core))
    terminal = recipe.get("terminal") or {}
    trace_body = {
        "schema": EXPECTED_STATE_TRACE_SCHEMA,
        "trace_id": f"trace:{slug}@1",
        "steps": steps_out,
        "terminal": {
            "outcome": terminal["outcome"],
            "namespace": dict(terminal.get("namespace") or {}),
            "evidence": dict(terminal.get("evidence") or {}),
            "error_code": terminal.get("error_code"),
        },
        "finite": True,
        "safe": True,
    }
    return _with_content_id(trace_body)


def expand_recipe(recipe: Mapping[str, Any]) -> dict[str, Any]:
    slug = str(recipe["slug"])
    trace = _expand_trace(slug, recipe)
    schedule = _expand_fault_schedule(slug, recipe.get("faults") or ())
    body: dict[str, Any] = {
        "schema": KERNEL_VFS_FIXTURE_SCHEMA,
        "fixture_id": f"fixture:kernel-vfs:{slug}@1",
        "task_id": TASK_ID,
        "description": recipe["description"],
        "categories": list(recipe["categories"]),
        "polarity": recipe["polarity"],
        "platform": recipe.get("platform", "hermetic"),
        "callback": recipe.get("callback"),
        "flags": list(recipe.get("flags") or ()),
        "initial_state": dict(recipe.get("initial_state") or {}),
        "expected_trace": trace,
        "fault_schedule": schedule,
        "hermetic": True,
        "finite": True,
        "safe": True,
        "safety": {
            "network": False,
            "credentials": False,
            "user_paths": False,
            "executable_payloads": False,
            "production_side_effects": False,
            "native_driver": False,
        },
    }
    return _with_content_id(body)


def expand_all_recipes() -> tuple[dict[str, Any], ...]:
    return tuple(expand_recipe(r) for r in all_recipes())


def build_manifest(fixtures: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Build content-identified FixtureManifest@1 over expanded fixtures.

    Authoritative expanded form is recipe-generated in-process so the corpus
    stays compact (no bulk golden envelopes). The on-disk manifest.json freezes
    the compact recipe catalog and coverage claims.
    """
    expanded = list(fixtures) if fixtures is not None else list(expand_all_recipes())
    covered: set[str] = set()
    entries: list[dict[str, Any]] = []
    for fixture in expanded:
        cats = list(fixture["categories"])
        covered.update(cats)
        entry: dict[str, Any] = {
            "fixture_id": fixture["fixture_id"],
            "content_id": fixture["content_id"],
            "categories": cats,
            "trace_content_id": fixture["expected_trace"]["content_id"],
            "callback": fixture.get("callback"),
            "polarity": fixture["polarity"],
            "platform": fixture.get("platform", "hermetic"),
        }
        schedule = fixture.get("fault_schedule")
        entry["fault_schedule_content_id"] = (
            None if schedule is None else schedule["content_id"]
        )
        entries.append(entry)
    body: dict[str, Any] = {
        "schema": FIXTURE_MANIFEST_SCHEMA,
        "manifest_id": MANIFEST_ID,
        "interface": INTERFACE_BUNDLE,
        "task_id": TASK_ID,
        "hermetic": True,
        "finite": True,
        "safe": True,
        "recipe_driven": True,
        "fixture_count": len(entries),
        "required_callbacks": list(REQUIRED_CALLBACKS),
        "unsupported_callbacks": list(UNSUPPORTED_CALLBACKS),
        "coverage": {
            "required_categories": list(REQUIRED_COVERAGE_CATEGORIES),
            "covered_categories": sorted(covered),
        },
        "fixtures": entries,
    }
    return _with_content_id(body)


def compact_recipe_entries() -> list[dict[str, Any]]:
    """Stable compact recipe index rows (no envelopes / content ids)."""
    entries: list[dict[str, Any]] = []
    for recipe in all_recipes():
        entries.append(
            {
                "slug": recipe["slug"],
                "categories": list(recipe["categories"]),
                "polarity": recipe["polarity"],
                "callback": recipe.get("callback"),
                "flags": list(recipe.get("flags") or ()),
                "platform": recipe.get("platform", "hermetic"),
                "has_faults": bool(recipe.get("faults")),
            }
        )
    return entries


def build_compact_catalog() -> dict[str, Any]:
    """Compact on-disk catalog: recipe index + coverage, no full envelopes."""
    recipe_entries = compact_recipe_entries()
    covered: set[str] = set()
    for entry in recipe_entries:
        covered.update(entry["categories"])
    body: dict[str, Any] = {
        "schema": FIXTURE_MANIFEST_SCHEMA,
        "manifest_id": MANIFEST_ID,
        "interface": INTERFACE_BUNDLE,
        "task_id": TASK_ID,
        "hermetic": True,
        "finite": True,
        "safe": True,
        "recipe_driven": True,
        "catalog_kind": "compact_recipe_index@1",
        "fixture_count": len(recipe_entries),
        "required_callbacks": list(REQUIRED_CALLBACKS),
        "unsupported_callbacks": list(UNSUPPORTED_CALLBACKS),
        "coverage": {
            "required_categories": list(REQUIRED_COVERAGE_CATEGORIES),
            "covered_categories": sorted(covered),
        },
        "recipes": recipe_entries,
    }
    return _with_content_id(body)


def write_compact_catalog(path: Path | None = None) -> dict[str, Any]:
    """Atomically write the frozen compact recipe catalog with content_id."""
    target = path or MANIFEST_PATH
    catalog = build_compact_catalog()
    # Pretty-print for reviewability while keeping recipe rows compact.
    text = json.dumps(catalog, indent=2, ensure_ascii=False, allow_nan=False)
    # Ensure stable trailing newline for VCS cleanliness.
    if not text.endswith("\n"):
        text += "\n"
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(target)
    return catalog


def load_compact_catalog(path: Path | None = None) -> dict[str, Any]:
    """Load the frozen compact recipe catalog from manifest.json."""
    target = path or MANIFEST_PATH
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise FixtureValidationError(
            "manifest root must be an object", reason_codes=("schema_mismatch",)
        )
    return data


def load_manifest(path: Path | None = None) -> dict[str, Any]:
    """Load and cross-check the on-disk catalog, then return expanded manifest.

    The authoritative content-identified fixture index is built from recipes so
    hashes stay recomputable without bulk golden dumps. The on-disk file must
    still exist and agree on coverage, callbacks, and recipe slugs.
    """
    catalog = load_compact_catalog(path)
    expanded = build_manifest()
    # Fail closed if the frozen catalog drifts from the in-process recipes.
    if catalog.get("schema") != FIXTURE_MANIFEST_SCHEMA:
        raise FixtureValidationError(
            "on-disk manifest schema mismatch", reason_codes=("schema_mismatch",)
        )
    if catalog.get("task_id") != TASK_ID:
        raise FixtureValidationError(
            "on-disk manifest task_id mismatch", reason_codes=("task_mismatch",)
        )
    if set(catalog.get("required_callbacks") or ()) != set(REQUIRED_CALLBACKS):
        raise FixtureValidationError(
            "on-disk required_callbacks mismatch", reason_codes=("callback_gap",)
        )
    if set(catalog.get("unsupported_callbacks") or ()) != set(UNSUPPORTED_CALLBACKS):
        raise FixtureValidationError(
            "on-disk unsupported_callbacks mismatch", reason_codes=("callback_gap",)
        )
    disk_recipes = catalog.get("recipes") or ()
    disk_slugs = [str(r.get("slug")) for r in disk_recipes if isinstance(r, Mapping)]
    live_slugs = [r["slug"] for r in all_recipes()]
    if disk_slugs != live_slugs:
        raise FixtureValidationError(
            "on-disk recipe slugs drift from generators",
            reason_codes=("recipe_drift",),
        )
    disk_covered = set(catalog.get("coverage", {}).get("covered_categories") or ())
    live_covered = set(expanded["coverage"]["covered_categories"])
    if not set(REQUIRED_COVERAGE_CATEGORIES) <= disk_covered:
        raise FixtureValidationError(
            "on-disk coverage missing required categories",
            reason_codes=("coverage_gap",),
        )
    if disk_covered != live_covered:
        raise FixtureValidationError(
            "on-disk covered_categories drift from expansion",
            reason_codes=("coverage_gap",),
        )
    if int(catalog.get("fixture_count") or -1) != len(live_slugs):
        raise FixtureValidationError(
            "on-disk fixture_count mismatch", reason_codes=("count_mismatch",)
        )
    return expanded


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FixtureValidationError(
            f"{field} must be an object", reason_codes=("type_error",)
        )
    return value


def _require_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_STRING_LEN:
        raise FixtureValidationError(
            f"{field} must be a non-empty string <= {MAX_STRING_LEN}",
            reason_codes=("type_error",),
        )
    return value


def _require_sequence(value: Any, field: str, *, max_len: int) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise FixtureValidationError(
            f"{field} must be a sequence", reason_codes=("type_error",)
        )
    if len(value) > max_len:
        raise FixtureValidationError(
            f"{field} exceeds max length {max_len}", reason_codes=("unbounded",)
        )
    return value


def _assert_finite_numbers(value: Any, field: str) -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise FixtureValidationError(
                f"{field} contains non-finite float", reason_codes=("non-finite",)
            )
    elif isinstance(value, Mapping):
        for k, v in value.items():
            _assert_finite_numbers(v, f"{field}.{k}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for i, item in enumerate(value):
            _assert_finite_numbers(item, f"{field}[{i}]")


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for k, v in value.items():
            yield str(k)
            yield from _walk_keys(v)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            yield from _walk_keys(item)


def assert_fixture_safe(fixture: Mapping[str, Any]) -> None:
    payload = canonical_json(fixture)
    if _BANNED_NETWORK.search(payload):
        raise SafetyViolation(
            "network locator present in fixture", reason_codes=("network",)
        )
    if _BANNED_USER_PATH.search(payload):
        raise SafetyViolation(
            "user path present in fixture", reason_codes=("user_paths",)
        )
    for key in _walk_keys(fixture):
        lowered = key.lower()
        if lowered in _BANNED_SECRET_KEYS or any(
            tok in lowered for tok in ("password", "private_key", "secret_key", "api_key")
        ):
            raise SafetyViolation(
                f"secret-like key {key!r} present in fixture",
                reason_codes=("credentials",),
            )
    safety = fixture.get("safety")
    if not isinstance(safety, Mapping):
        raise SafetyViolation("fixture.safety missing", reason_codes=("unsafe_fixture",))
    for flag in (
        "network",
        "credentials",
        "user_paths",
        "executable_payloads",
        "production_side_effects",
        "native_driver",
    ):
        if safety.get(flag) is not False:
            raise SafetyViolation(
                f"fixture.safety.{flag} must be false",
                reason_codes=("unsafe_fixture",),
            )


def validate_expected_state_trace(trace: Any) -> Mapping[str, Any]:
    data = _require_mapping(trace, "expected_trace")
    schema = _require_str(data.get("schema"), "expected_trace.schema")
    if schema != EXPECTED_STATE_TRACE_SCHEMA:
        raise FixtureValidationError(
            f"expected_trace.schema must be {EXPECTED_STATE_TRACE_SCHEMA}",
            reason_codes=("schema",),
        )
    _require_str(data.get("trace_id"), "expected_trace.trace_id")
    steps = _require_sequence(
        data.get("steps"), "expected_trace.steps", max_len=MAX_TRACE_STEPS
    )
    if not steps:
        raise FixtureValidationError(
            "expected_trace.steps must be non-empty", reason_codes=("non-empty",)
        )
    for idx, step in enumerate(steps):
        sm = _require_mapping(step, f"steps[{idx}]")
        state = _require_str(sm.get("state"), f"steps[{idx}].state")
        if state not in ALLOWED_TRACE_STATES:
            raise FixtureValidationError(
                f"unknown trace state {state}", reason_codes=("unknown_state",)
            )
        _assert_finite_numbers(sm.get("state_snapshot"), f"steps[{idx}].state_snapshot")
        cid = _require_str(sm.get("content_id"), f"steps[{idx}].content_id")
        if not cid.startswith("sha256:"):
            raise FixtureValidationError(
                "step content_id must be sha256-prefixed",
                reason_codes=("identity_error",),
            )
    terminal = _require_mapping(data.get("terminal"), "expected_trace.terminal")
    outcome = _require_str(terminal.get("outcome"), "terminal.outcome")
    if outcome not in ALLOWED_TERMINAL_OUTCOMES:
        raise FixtureValidationError(
            f"unknown terminal outcome {outcome}", reason_codes=("unknown_outcome",)
        )
    if data.get("finite") is not True or data.get("safe") is not True:
        raise FixtureValidationError(
            "expected_trace must be finite and safe", reason_codes=("unsafe_fixture",)
        )
    cid = _require_str(data.get("content_id"), "expected_trace.content_id")
    if not cid.startswith("sha256:"):
        raise FixtureValidationError(
            "expected_trace.content_id must be sha256-prefixed",
            reason_codes=("identity_error",),
        )
    return data


def validate_fault_schedule(schedule: Any) -> Mapping[str, Any]:
    data = _require_mapping(schedule, "fault_schedule")
    schema = _require_str(data.get("schema"), "fault_schedule.schema")
    if schema != FAULT_SCHEDULE_SCHEMA:
        raise FixtureValidationError(
            f"fault_schedule.schema must be {FAULT_SCHEDULE_SCHEMA}",
            reason_codes=("schema",),
        )
    _require_str(data.get("schedule_id"), "fault_schedule.schedule_id")
    faults = _require_sequence(
        data.get("faults"), "fault_schedule.faults", max_len=MAX_FAULTS
    )
    for idx, fault in enumerate(faults):
        fm = _require_mapping(fault, f"faults[{idx}]")
        kind = _require_str(fm.get("kind"), f"faults[{idx}].kind")
        if kind not in ALLOWED_FAULT_KINDS:
            raise FixtureValidationError(
                f"unknown fault kind {kind}", reason_codes=("unknown fault kind",)
            )
        if not isinstance(fm.get("at_operation_index"), int):
            raise FixtureValidationError(
                f"faults[{idx}].at_operation_index must be int",
                reason_codes=("type_error",),
            )
        cid = _require_str(fm.get("content_id"), f"faults[{idx}].content_id")
        if not cid.startswith("sha256:"):
            raise FixtureValidationError(
                "fault content_id must be sha256-prefixed",
                reason_codes=("identity_error",),
            )
    if data.get("finite") is not True or data.get("safe") is not True:
        raise FixtureValidationError(
            "fault_schedule must be finite and safe", reason_codes=("unsafe_fixture",)
        )
    cid = _require_str(data.get("content_id"), "fault_schedule.content_id")
    if not cid.startswith("sha256:"):
        raise FixtureValidationError(
            "fault_schedule.content_id must be sha256-prefixed",
            reason_codes=("identity_error",),
        )
    return data


def validate_fixture(fixture: Any) -> Mapping[str, Any]:
    data = _require_mapping(fixture, "fixture")
    schema = _require_str(data.get("schema"), "fixture.schema")
    if schema != KERNEL_VFS_FIXTURE_SCHEMA:
        raise FixtureValidationError(
            f"fixture.schema must be {KERNEL_VFS_FIXTURE_SCHEMA}",
            reason_codes=("schema",),
        )
    _require_str(data.get("fixture_id"), "fixture.fixture_id")
    cats = _require_sequence(
        data.get("categories"), "fixture.categories", max_len=32
    )
    for i, cat in enumerate(cats):
        _require_str(cat, f"fixture.categories[{i}]")
    polarity = _require_str(data.get("polarity"), "fixture.polarity")
    if polarity not in ALLOWED_POLARITIES:
        raise FixtureValidationError(
            f"unknown polarity {polarity}", reason_codes=("polarity",)
        )
    if data.get("hermetic") is not True or data.get("finite") is not True:
        raise FixtureValidationError(
            "fixture.hermetic and fixture.finite must be true",
            reason_codes=("unsafe_fixture",),
        )
    validate_expected_state_trace(data.get("expected_trace"))
    schedule = data.get("fault_schedule")
    if schedule is not None:
        validate_fault_schedule(schedule)
    cid = _require_str(data.get("content_id"), "fixture.content_id")
    if not cid.startswith("sha256:"):
        raise FixtureValidationError(
            "fixture.content_id must be sha256-prefixed",
            reason_codes=("identity_error",),
        )
    assert_fixture_safe(data)
    return data


def validate_manifest(manifest: Any) -> Mapping[str, Any]:
    data = _require_mapping(manifest, "manifest")
    schema = _require_str(data.get("schema"), "manifest.schema")
    if schema != FIXTURE_MANIFEST_SCHEMA:
        raise FixtureValidationError(
            f"manifest.schema must be {FIXTURE_MANIFEST_SCHEMA}",
            reason_codes=("schema",),
        )
    _require_str(data.get("manifest_id"), "manifest.manifest_id")
    _require_str(data.get("interface"), "manifest.interface")
    fixtures = _require_sequence(
        data.get("fixtures"), "manifest.fixtures", max_len=MAX_FIXTURES
    )
    if not fixtures:
        raise FixtureValidationError(
            "manifest.fixtures must be non-empty", reason_codes=("empty_manifest",)
        )
    seen: set[str] = set()
    for idx, entry in enumerate(fixtures):
        em = _require_mapping(entry, f"manifest.fixtures[{idx}]")
        fid = _require_str(em.get("fixture_id"), f"fixtures[{idx}].fixture_id")
        if fid in seen:
            raise FixtureValidationError(
                f"duplicate fixture_id {fid}", reason_codes=("duplicate_fixture_id",)
            )
        seen.add(fid)
        _require_str(em.get("content_id"), f"fixtures[{idx}].content_id")
    coverage = _require_mapping(data.get("coverage"), "manifest.coverage")
    required = _require_sequence(
        coverage.get("required_categories"),
        "coverage.required_categories",
        max_len=64,
    )
    covered = _require_sequence(
        coverage.get("covered_categories"),
        "coverage.covered_categories",
        max_len=64,
    )
    missing = sorted(set(str(c) for c in required) - set(str(c) for c in covered))
    if missing:
        raise FixtureValidationError(
            f"manifest coverage missing categories: {', '.join(missing)}",
            reason_codes=("coverage_gap",),
        )
    if data.get("hermetic") is not True or data.get("finite") is not True:
        raise FixtureValidationError(
            "manifest must be hermetic and finite", reason_codes=("unsafe_fixture",)
        )
    if data.get("safe") is not True or data.get("recipe_driven") is not True:
        raise FixtureValidationError(
            "manifest must be safe and recipe_driven", reason_codes=("unsafe_fixture",)
        )
    count = data.get("fixture_count")
    if count != len(fixtures):
        raise FixtureValidationError(
            "manifest.fixture_count must match fixtures length",
            reason_codes=("count_mismatch",),
        )
    cid = _require_str(data.get("content_id"), "manifest.content_id")
    if not cid.startswith("sha256:"):
        raise FixtureValidationError(
            "manifest.content_id must be sha256-prefixed",
            reason_codes=("identity_error",),
        )
    return data


def assert_corpus_safe(fixtures: Sequence[Mapping[str, Any]]) -> None:
    for fixture in fixtures:
        assert_fixture_safe(fixture)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _fixtures() -> tuple[dict[str, Any], ...]:
    return expand_all_recipes()


def _manifest() -> dict[str, Any]:
    return load_manifest()


def test_declared_outputs_exist() -> None:
    assert MANIFEST_PATH.is_file(), f"missing {MANIFEST_PATH}"
    assert MANIFEST_PATH.stat().st_size > 0
    assert Path(__file__).is_file()


def test_on_disk_compact_catalog_matches_generators() -> None:
    """Frozen manifest.json is a compact recipe index, not bulk envelopes."""
    disk = load_compact_catalog()
    live = build_compact_catalog()
    assert disk["schema"] == FIXTURE_MANIFEST_SCHEMA
    assert disk["manifest_id"] == MANIFEST_ID
    assert disk["task_id"] == TASK_ID
    assert disk["catalog_kind"] == "compact_recipe_index@1"
    assert disk["hermetic"] is True
    assert disk["finite"] is True
    assert disk["safe"] is True
    assert disk["recipe_driven"] is True
    assert disk["required_callbacks"] == live["required_callbacks"]
    assert disk["unsupported_callbacks"] == live["unsupported_callbacks"]
    assert disk["coverage"] == live["coverage"]
    assert disk["fixture_count"] == live["fixture_count"]
    assert disk["recipes"] == live["recipes"]
    # Expanded fixtures are always content-identified in-process. The on-disk
    # compact index may freeze content_id; when present it must recompute.
    if "content_id" in disk:
        body = {k: v for k, v in disk.items() if k != "content_id"}
        assert disk["content_id"] == content_id_for(body)
        assert disk["content_id"] == live["content_id"]
        assert disk["content_id"].startswith("sha256:")
    else:
        # Body fields (excluding content_id) must still match generators.
        live_body = {k: v for k, v in live.items() if k != "content_id"}
        disk_body = {k: v for k, v in disk.items() if k != "content_id"}
        assert disk_body == live_body


def test_schema_identities_are_versioned() -> None:
    assert KERNEL_VFS_FIXTURE_SCHEMA.endswith("@1")
    assert FAULT_SCHEDULE_SCHEMA.endswith("@1")
    assert EXPECTED_STATE_TRACE_SCHEMA.endswith("@1")
    assert FIXTURE_MANIFEST_SCHEMA.endswith("@1")
    assert "kernel-vfs" in KERNEL_VFS_FIXTURE_SCHEMA


def test_required_callbacks_match_host_contract() -> None:
    assert set(REQUIRED_CALLBACKS) == {
        k.value for k in hc.REQUIRED_SUPPORTED_CALLBACKS
    }
    assert set(UNSUPPORTED_CALLBACKS) == {
        k.value for k in hc.EXPLICIT_UNSUPPORTED_CALLBACKS
    }
    assert set(REQUIRED_CALLBACKS).isdisjoint(UNSUPPORTED_CALLBACKS)


def test_every_callback_has_a_fixture() -> None:
    fixtures = _fixtures()
    covered_required = {
        f["callback"]
        for f in fixtures
        if "callback_required" in f["categories"] and f.get("callback")
    }
    covered_unsupported = {
        f["callback"]
        for f in fixtures
        if "callback_unsupported" in f["categories"] and f.get("callback")
    }
    assert set(REQUIRED_CALLBACKS) <= covered_required
    assert set(UNSUPPORTED_CALLBACKS) <= covered_unsupported


def test_manifest_covers_required_categories() -> None:
    manifest = _manifest()
    covered = set(manifest["coverage"]["covered_categories"])
    required = set(REQUIRED_COVERAGE_CATEGORIES)
    assert required <= covered


def test_every_acceptance_category_has_at_least_one_fixture() -> None:
    fixtures = _fixtures()
    by_cat: dict[str, list[str]] = {c: [] for c in REQUIRED_COVERAGE_CATEGORIES}
    for fixture in fixtures:
        for cat in fixture["categories"]:
            if cat in by_cat:
                by_cat[cat].append(fixture["fixture_id"])
    missing = [c for c, ids in by_cat.items() if not ids]
    assert not missing, f"categories without fixtures: {missing}"


def test_flag_combinations_are_represented() -> None:
    fixtures = _fixtures()
    seen: set[tuple[str, ...]] = set()
    for fixture in fixtures:
        if "flag_combination" in fixture["categories"]:
            seen.add(tuple(fixture.get("flags") or ()))
    for combo in FLAG_COMBINATIONS:
        assert combo in seen, f"missing flag combination {combo}"


def test_rename_unlink_wal_arc_winfsp_docker_present() -> None:
    fixtures = _fixtures()
    ids = [f["fixture_id"] for f in fixtures]
    assert any("rename-while-open" in i for i in ids)
    assert any("unlink-while-open" in i for i in ids)
    assert any("wal-crash" in i for i in ids)
    assert any("corrupt-arc" in i for i in ids)
    assert any("winfsp" in i for i in ids)
    assert any("docker" in i for i in ids)
    assert any("partial-sparse" in i or "sparse" in i for i in ids)


def test_expand_all_recipes_produces_valid_fixtures() -> None:
    fixtures = _fixtures()
    assert len(fixtures) == len(all_recipes())
    assert len(fixtures) <= MAX_FIXTURES
    for fixture in fixtures:
        validate_fixture(fixture)
        assert fixture["schema"] == KERNEL_VFS_FIXTURE_SCHEMA
        assert fixture["hermetic"] is True
        assert fixture["finite"] is True
        assert fixture["task_id"] == TASK_ID
        assert fixture["content_id"].startswith("sha256:")


def test_expected_traces_and_faults_are_finite_safe_content_identified() -> None:
    for fixture in _fixtures():
        trace = fixture["expected_trace"]
        validate_expected_state_trace(trace)
        assert trace["schema"] == EXPECTED_STATE_TRACE_SCHEMA
        assert trace["finite"] is True
        assert trace["safe"] is True
        assert trace["content_id"].startswith("sha256:")
        for step in trace["steps"]:
            assert step["content_id"].startswith("sha256:")
        schedule = fixture.get("fault_schedule")
        if schedule is not None:
            validate_fault_schedule(schedule)
            assert schedule["schema"] == FAULT_SCHEDULE_SCHEMA
            assert schedule["finite"] is True
            assert schedule["safe"] is True
            assert schedule["content_id"].startswith("sha256:")
            for fault in schedule["faults"]:
                assert fault["content_id"].startswith("sha256:")


def test_corpus_is_hermetic_safe() -> None:
    fixtures = _fixtures()
    assert_corpus_safe(fixtures)
    for fixture in fixtures:
        safety = fixture["safety"]
        for flag in (
            "network",
            "credentials",
            "user_paths",
            "executable_payloads",
            "production_side_effects",
            "native_driver",
        ):
            assert safety[flag] is False


def test_manifest_is_valid_and_content_identified() -> None:
    manifest = _manifest()
    validate_manifest(manifest)
    assert manifest["schema"] == FIXTURE_MANIFEST_SCHEMA
    assert manifest["manifest_id"] == MANIFEST_ID
    assert manifest["interface"] == INTERFACE_BUNDLE
    assert manifest["task_id"] == TASK_ID
    assert manifest["finite"] is True
    assert manifest["safe"] is True
    assert manifest["hermetic"] is True
    assert manifest["recipe_driven"] is True
    assert manifest["fixture_count"] == len(manifest["fixtures"])
    assert manifest["content_id"].startswith("sha256:")
    assert set(manifest["required_callbacks"]) == set(REQUIRED_CALLBACKS)
    assert set(manifest["unsupported_callbacks"]) == set(UNSUPPORTED_CALLBACKS)


def test_manifest_fixture_content_ids_match_expanded_fixtures() -> None:
    fixtures = {f["fixture_id"]: f for f in _fixtures()}
    manifest = _manifest()
    assert set(fixtures) == {e["fixture_id"] for e in manifest["fixtures"]}
    for entry in manifest["fixtures"]:
        fixture = fixtures[entry["fixture_id"]]
        assert entry["content_id"] == fixture["content_id"]
        assert entry["trace_content_id"] == fixture["expected_trace"]["content_id"]
        if fixture.get("fault_schedule") is None:
            assert entry.get("fault_schedule_content_id") is None
        else:
            assert (
                entry["fault_schedule_content_id"]
                == fixture["fault_schedule"]["content_id"]
            )


def test_build_manifest_matches_load_manifest() -> None:
    assert build_manifest()["content_id"] == load_manifest()["content_id"]


def test_expansion_is_deterministic() -> None:
    first = expand_all_recipes()
    second = expand_all_recipes()
    assert [f["content_id"] for f in first] == [f["content_id"] for f in second]
    assert build_manifest()["content_id"] == build_manifest()["content_id"]
    assert canonical_json(first[0]) == canonical_json(second[0])


def test_content_id_matches_body_hash() -> None:
    for recipe in all_recipes():
        fixture = expand_recipe(recipe)
        body = {k: v for k, v in fixture.items() if k != "content_id"}
        assert fixture["content_id"] == content_id_for(body)


def test_rejects_network_locator_in_fixture_payload() -> None:
    fixture = dict(expand_recipe(all_recipes()[0]))
    fixture["description"] = "fetch https://example.invalid/payload"
    with pytest.raises(SafetyViolation, match="network locator"):
        assert_fixture_safe(fixture)


def test_rejects_secret_like_keys() -> None:
    fixture = dict(expand_recipe(all_recipes()[0]))
    bad_state = dict(fixture["initial_state"])
    bad_state["api_key"] = "should-not-appear"
    fixture["initial_state"] = bad_state
    with pytest.raises(SafetyViolation):
        assert_fixture_safe(fixture)


def test_rejects_wrong_schema_identity() -> None:
    fixture = dict(expand_recipe(all_recipes()[0]))
    fixture["schema"] = "forged/schema@9"
    with pytest.raises(FixtureValidationError, match="schema"):
        validate_fixture(fixture)


def test_rejects_non_finite_float_in_trace() -> None:
    fixture = expand_recipe(all_recipes()[0])
    trace = json.loads(canonical_json(fixture["expected_trace"]))
    trace["steps"][0]["state_snapshot"] = {"nan_value": float("nan")}
    with pytest.raises(FixtureValidationError, match="non-finite"):
        validate_expected_state_trace(trace)


def test_rejects_empty_trace() -> None:
    with pytest.raises(FixtureValidationError, match="non-empty"):
        validate_expected_state_trace(
            {
                "schema": EXPECTED_STATE_TRACE_SCHEMA,
                "trace_id": "trace:empty@1",
                "steps": [],
                "terminal": {
                    "outcome": "success",
                    "namespace": {},
                    "evidence": {},
                },
                "finite": True,
                "safe": True,
                "content_id": "sha256:" + ("0" * 64),
            }
        )


def test_rejects_unknown_fault_kind() -> None:
    with pytest.raises(FixtureValidationError, match="unknown fault kind"):
        validate_fault_schedule(
            {
                "schema": FAULT_SCHEDULE_SCHEMA,
                "schedule_id": "fault-schedule:x@1",
                "faults": [
                    {
                        "kind": "launch_missiles",
                        "at_operation_index": 0,
                        "effects": [],
                        "parameters": {},
                        "content_id": "sha256:" + ("a" * 64),
                    }
                ],
                "finite": True,
                "safe": True,
                "content_id": "sha256:" + ("b" * 64),
            }
        )


def test_rejects_manifest_with_coverage_gap() -> None:
    manifest = dict(_manifest())
    coverage = dict(manifest["coverage"])
    coverage["covered_categories"] = [
        c for c in coverage["covered_categories"] if c != "corrupt_arc"
    ]
    manifest["coverage"] = coverage
    with pytest.raises(FixtureValidationError, match="coverage missing"):
        validate_manifest(manifest)


def test_rejects_duplicate_fixture_ids_in_manifest() -> None:
    manifest = dict(_manifest())
    fixtures = list(manifest["fixtures"])
    fixtures.append(dict(fixtures[0]))
    manifest["fixtures"] = fixtures
    manifest["fixture_count"] = len(fixtures)
    with pytest.raises(FixtureValidationError, match="duplicate fixture_id"):
        validate_manifest(manifest)


def test_unsupported_callbacks_never_false_succeed() -> None:
    fixtures = [
        f
        for f in _fixtures()
        if "callback_unsupported" in f["categories"]
    ]
    assert fixtures
    for fixture in fixtures:
        terminal = fixture["expected_trace"]["terminal"]
        assert terminal["outcome"] == "denied"
        expected_errno = hc.default_unsupported_errno(fixture["callback"]).value
        assert terminal.get("error_code") == expected_errno
        assert terminal.get("error_code") in {"ENOSYS", "EOPNOTSUPP"}
        assert terminal["evidence"].get("false_success") is False


def test_rename_while_open_handle_survives() -> None:
    matches = [
        f for f in _fixtures() if "rename-while-open" in f["fixture_id"]
    ]
    assert matches
    for fixture in matches:
        evidence = fixture["expected_trace"]["terminal"]["evidence"]
        assert evidence.get("handle_survived_rename") is True
        assert evidence.get("mutated") is True


def test_unlink_while_open_handle_survives() -> None:
    matches = [
        f for f in _fixtures() if "unlink-while-open" in f["fixture_id"]
    ]
    assert matches
    for fixture in matches:
        evidence = fixture["expected_trace"]["terminal"]["evidence"]
        assert evidence.get("handle_survived_unlink") is True


def test_wal_crash_points_are_exact() -> None:
    before = [
        f for f in _fixtures() if "wal-crash-before-commit" in f["fixture_id"]
    ]
    after = [
        f for f in _fixtures() if "wal-crash-after-commit" in f["fixture_id"]
    ]
    assert before and after
    assert before[0]["expected_trace"]["terminal"]["evidence"]["effect_applied"] is False
    assert after[0]["expected_trace"]["terminal"]["evidence"]["effect_applied"] is True
    assert after[0]["expected_trace"]["terminal"]["evidence"]["duplicate_effect"] is False


def test_corrupt_arc_is_safe_miss() -> None:
    matches = [f for f in _fixtures() if "corrupt-arc" in f["fixture_id"]]
    assert matches
    evidence = matches[0]["expected_trace"]["terminal"]["evidence"]
    assert evidence.get("safe_miss") is True
    assert evidence.get("stale_hit") is False
    assert evidence.get("corrupt_arc_admitted") is False


def test_docker_capability_failures_do_not_mount() -> None:
    matches = [
        f for f in _fixtures() if "docker_capability" in f["categories"]
    ]
    assert len(matches) >= 2
    for fixture in matches:
        terminal = fixture["expected_trace"]["terminal"]
        assert terminal["outcome"] == "capability_absent"
        assert terminal["evidence"].get("native_mount_attempted") is False


def test_recipe_slugs_are_unique() -> None:
    slugs = [r["slug"] for r in all_recipes()]
    assert len(slugs) == len(set(slugs))


def test_fixture_content_ids_are_unique() -> None:
    fixtures = _fixtures()
    ids = [f["content_id"] for f in fixtures]
    fixture_ids = [f["fixture_id"] for f in fixtures]
    assert len(ids) == len(set(ids))
    assert len(fixture_ids) == len(set(fixture_ids))


def test_sha256_content_ids_are_hex_and_recomputable() -> None:
    for fixture in _fixtures():
        digest = fixture["content_id"].removeprefix("sha256:")
        assert len(digest) == 64
        int(digest, 16)
        body = {k: v for k, v in fixture.items() if k != "content_id"}
        assert fixture["content_id"] == content_id_for(body)
        trace = fixture["expected_trace"]
        trace_body = {k: v for k, v in trace.items() if k != "content_id"}
        assert trace["content_id"] == content_id_for(trace_body)


def test_no_live_credentials_or_user_home_strings_in_corpus() -> None:
    payload = canonical_json(_fixtures()).lower()
    for banned in (
        "password=",
        "secret_key",
        "begin private key",
        "/home/",
        "/users/",
        "$home",
        "https://",
        "http://",
    ):
        assert banned not in payload


def test_corpus_includes_positive_and_adversarial_polarities() -> None:
    polarities = {f["polarity"] for f in _fixtures()}
    assert "adversarial" in polarities
    assert "positive" in polarities


def test_manifest_callback_lists_are_closed_and_sorted() -> None:
    manifest = _manifest()
    assert manifest["required_callbacks"] == list(REQUIRED_CALLBACKS)
    assert manifest["unsupported_callbacks"] == list(UNSUPPORTED_CALLBACKS)
    assert manifest["required_callbacks"] == sorted(manifest["required_callbacks"])
    assert manifest["unsupported_callbacks"] == sorted(
        manifest["unsupported_callbacks"]
    )


def test_compact_catalog_json_round_trip_preserves_content_id() -> None:
    """build_compact_catalog survives JSON freeze/reload with stable content_id."""
    live = build_compact_catalog()
    # Round-trip through the same pretty-print path as write_compact_catalog.
    encoded = json.dumps(live, indent=2, ensure_ascii=False, allow_nan=False)
    reloaded = json.loads(encoded)
    body = {k: v for k, v in reloaded.items() if k != "content_id"}
    assert reloaded["content_id"] == content_id_for(body)
    assert reloaded["content_id"] == live["content_id"]
    assert reloaded["recipes"] == live["recipes"]
    assert reloaded["fixture_count"] == len(all_recipes())
    assert set(REQUIRED_COVERAGE_CATEGORIES) <= set(
        reloaded["coverage"]["covered_categories"]
    )


if __name__ == "__main__":
    # Allow: python test_fixture_manifest.py --write-catalog
    import sys as _sys

    if "--write-catalog" in _sys.argv:
        written = write_compact_catalog()
        print(
            f"wrote {MANIFEST_PATH} "
            f"fixtures={written['fixture_count']} "
            f"content_id={written['content_id']}"
        )
        _sys.exit(0)
    raise SystemExit(
        "usage: python test_fixture_manifest.py --write-catalog"
    )
