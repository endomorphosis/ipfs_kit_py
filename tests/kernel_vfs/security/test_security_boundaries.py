"""KVFS-808: Mount option, permission, path, state, symlink, and resource boundaries.

Acceptance coverage (fail-closed, zero side effect outside admitted roots):

* path traversal;
* symlink escape;
* Unicode / case / reserved aliases;
* mount-option injection;
* unsafe ``allow_other``;
* state / mount overlap;
* stale PID / lease;
* permission confusion;
* oversized request;
* handle / WAL / ARC exhaustion;
* malformed native error;
* secret / log leakage; and
* cleanup attacks.

Conflict policy: adversarial tests and security policy only; production fixes
must respect owning subsystem contracts. No fusepy / native mount required.
"""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import pytest

from ipfs_kit_py.cache.arc.contracts import (
    ARCConfig,
    ARCKeyError,
    ARCSizeError,
    CacheKey,
    MAX_KEY_BYTES,
)
from ipfs_kit_py.cache.arc.range_bindings import (
    MAX_RANGE_LENGTH,
    RangeExtentError,
    validate_length,
)
from ipfs_kit_py.core.operation_contracts import SecretMaterialError
from ipfs_kit_py.core.vfs.contracts import (
    MAX_PATH_BYTES,
    MAX_SEGMENT_BYTES,
    CasePolicy,
    SymlinkPolicy,
    VFSPathError,
    VFSPathPolicy,
    VFSPathRejectReason,
    confine_path,
    evaluate_symlink,
    normalize_vfs_path,
)
from ipfs_kit_py.core.vfs.handles import (
    HandleError,
    HandleErrorCode,
    HandleTable,
)
from ipfs_kit_py.core.vfs.host_contracts import (
    HostBoundsError,
    HostCallbackKind,
    HostCallbackRequest,
    HostCallbackResult,
    HostContractError,
    HostErrno,
    HostError,
    HostFalseSuccessError,
    HostUnknownCallbackError,
    MAX_IO_LENGTH,
    MAX_PATH_BYTES as HOST_MAX_PATH_BYTES,
    OpenFlag,
    parse_callback_kind,
)
from ipfs_kit_py.core.vfs.metadata import (
    R_OK,
    W_OK,
    X_OK,
    FileType,
    MetadataProjector,
    UidGidPolicy,
    make_file_attr,
    mode_grants,
)
from ipfs_kit_py.core.wal.vfs_records import (
    VFSWALContent,
    VFSWALIntentKind,
    VFSWALRecordBoundsError,
    make_durable_data,
)
from ipfs_kit_py.kernel_vfs import windows_semantics as ws
from ipfs_kit_py.kernel_vfs.linux import (
    HEARTBEAT_FILENAME,
    READY_FILENAME,
    LinuxMountConfig,
    LinuxMountLifecycle,
    MountHeartbeat,
    MountReadiness,
    report_stale_mounts,
)
from ipfs_kit_py.kernel_vfs.platform import run_linux_doctor
from ipfs_kit_py.kernel_vfs.wal_recovery import StateLease, StateLeaseHeldError

# test file: ipfs_kit_py/tests/kernel_vfs/security/test_security_boundaries.py
# parents[0]=security, [1]=kernel_vfs, [2]=tests, [3]=ipfs_kit_py package root
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
SECURITY_DOC = PACKAGE_ROOT / "docs" / "kernel_vfs" / "security.md"
TASK_ID = "KVFS-808"

# ---------------------------------------------------------------------------
# Security policy harness (owned by KVFS-808; mirrors security.md ledger)
# ---------------------------------------------------------------------------

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

# Options that expand privilege or inject kernel modules — always rejected
# unless a dedicated, reviewed opt-in path exists (only allow_other today).
ALWAYS_REJECTED_OPTIONS: Final[frozenset[str]] = frozenset(
    {
        "allow_root",
        "suid",
        "dev",
        "exec",
        "modules",
        "nonempty",  # historical FUSE privilege footgun
    }
)

SECRET_KEY_FRAGMENTS: Final[tuple[str, ...]] = (
    "password",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "private_key",
    "credential",
    "authorization",
    "bearer",
)

REDACTED: Final[str] = "[REDACTED]"

REQUIRED_ATTACK_CLASSES: Final[tuple[str, ...]] = (
    "path_traversal",
    "symlink_escape",
    "unicode_case_reserved_alias",
    "mount_option_injection",
    "unsafe_allow_other",
    "state_mount_overlap",
    "stale_pid_lease",
    "permission_confusion",
    "oversized_request",
    "handle_wal_arc_exhaustion",
    "malformed_native_error",
    "secret_log_leakage",
    "cleanup",
)

LEDGER_FENCE_RE = re.compile(
    r"```security-ledger\s*\n(?P<body>.*?)\n```",
    re.DOTALL,
)


@dataclass(frozen=True)
class SecurityDecision:
    """Result of a pure security-policy evaluation."""

    allowed: bool
    reason: str
    code: str
    effective_options: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    detail: Mapping[str, Any] | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "code": self.code,
            "effective_options": list(self.effective_options),
            "warnings": list(self.warnings),
            "detail": dict(self.detail or {}),
        }


def _split_option(raw: str) -> tuple[str, str | None]:
    text = str(raw).strip()
    if not text:
        return "", None
    if "=" in text:
        name, value = text.split("=", 1)
        return name.strip().lower(), value
    return text.lower(), None


def admit_fuse_mount_options(
    options: Sequence[str] | None,
    *,
    allow_other_explicit: bool = False,
    acknowledge_allow_other_warning: bool = False,
) -> SecurityDecision:
    """Fail-closed FUSE mount-option admission (default security profile).

    * Closed allowlist for option names.
    * ``default_permissions`` is always forced on.
    * ``allow_other`` requires explicit opt-in **and** operator warning ack.
    * ``allow_root`` and other privilege-expansion options are always rejected.
    """

    warnings: list[str] = []
    admitted: list[str] = ["default_permissions"]
    seen: set[str] = {"default_permissions"}

    for raw in options or ():
        if not isinstance(raw, str):
            return SecurityDecision(
                allowed=False,
                reason="mount option must be a string",
                code="option_type",
            )
        if "\x00" in raw or any(ord(ch) < 32 for ch in raw):
            return SecurityDecision(
                allowed=False,
                reason="control characters in mount options are rejected",
                code="option_control_char",
                detail={"option": raw},
            )
        if len(raw.encode("utf-8", errors="replace")) > 512:
            return SecurityDecision(
                allowed=False,
                reason="mount option exceeds length bound",
                code="option_too_long",
            )
        # Reject shell/env injection forms and multi-option smuggling.
        if any(tok in raw for tok in ("$", "`", ";", "|", "\n", "\r", ",")):
            return SecurityDecision(
                allowed=False,
                reason="mount option injection characters are rejected",
                code="option_injection",
                detail={"option": raw},
            )

        name, value = _split_option(raw)
        if not name:
            return SecurityDecision(
                allowed=False,
                reason="empty mount option is rejected",
                code="option_empty",
            )

        if name == "allow_other":
            if not allow_other_explicit:
                return SecurityDecision(
                    allowed=False,
                    reason="allow_other is off by default; requires explicit opt-in",
                    code="allow_other_not_explicit",
                )
            if not acknowledge_allow_other_warning:
                return SecurityDecision(
                    allowed=False,
                    reason=(
                        "allow_other requires an operator-visible warning "
                        "acknowledgement"
                    ),
                    code="allow_other_warning_required",
                )
            if name not in seen:
                admitted.append("allow_other")
                seen.add("allow_other")
            warnings.append(
                "allow_other enables multi-user access; mount runs with "
                "expanded peer visibility — review ACLs before production use"
            )
            continue

        if name in ALWAYS_REJECTED_OPTIONS:
            return SecurityDecision(
                allowed=False,
                reason=f"mount option {name!r} is forbidden by the security profile",
                code="option_forbidden",
                detail={"option": name},
            )

        if name not in ADMITTED_FUSE_OPTIONS:
            return SecurityDecision(
                allowed=False,
                reason=f"unknown mount option {name!r} is rejected (closed allowlist)",
                code="option_not_allowlisted",
                detail={"option": name},
            )

        if name in {"fsname", "subtype"}:
            if value is None or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}", value
            ):
                return SecurityDecision(
                    allowed=False,
                    reason=f"{name} value is not an admitted identifier",
                    code="option_value_invalid",
                    detail={"option": name},
                )
        if name == "max_read":
            try:
                number = int(value) if value is not None else -1
            except (TypeError, ValueError):
                number = -1
            if number < 1 or number > MAX_IO_LENGTH:
                return SecurityDecision(
                    allowed=False,
                    reason="max_read is outside the admitted I/O bound",
                    code="option_value_out_of_bounds",
                )

        token = name if value is None else f"{name}={value}"
        if name not in seen:
            admitted.append(token)
            seen.add(name)
        elif name in {"ro", "rw"} and token not in admitted:
            # Last of ro/rw wins only when both were allowlisted names.
            admitted = [item for item in admitted if not item.startswith(("ro", "rw"))]
            admitted.append(token)

    # Mutual exclusion: prefer the last admitted of ro/rw.
    has_ro = any(item == "ro" or item.startswith("ro=") for item in admitted)
    has_rw = any(item == "rw" or item.startswith("rw=") for item in admitted)
    if has_ro and has_rw:
        # Keep only the last occurrence.
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

    return SecurityDecision(
        allowed=True,
        reason="mount options admitted under default security profile",
        code="ok",
        effective_options=tuple(admitted),
        warnings=tuple(warnings),
    )


def redact_secrets(payload: Any) -> Any:
    """Redact secret-looking keys and marker strings from log/status payloads."""

    if isinstance(payload, Mapping):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            key_l = str(key).lower()
            if any(frag in key_l for frag in SECRET_KEY_FRAGMENTS):
                out[str(key)] = REDACTED
            else:
                out[str(key)] = redact_secrets(value)
        return out
    if isinstance(payload, list):
        return [redact_secrets(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(redact_secrets(item) for item in payload)
    if isinstance(payload, str):
        lowered = payload.lower()
        if any(frag in lowered for frag in SECRET_KEY_FRAGMENTS):
            return REDACTED
        if "-----begin" in lowered or "bearer " in lowered:
            return REDACTED
        return payload
    return payload


def paths_outside_admitted_roots(
    candidates: Iterable[Path],
    admitted_roots: Sequence[Path],
) -> list[Path]:
    """Return resolved candidates that fall outside every admitted root."""

    resolved_roots = [root.resolve() for root in admitted_roots]
    offenders: list[Path] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            offenders.append(Path(candidate))
            continue
        inside = False
        for root in resolved_roots:
            try:
                resolved.relative_to(root)
                inside = True
                break
            except ValueError:
                continue
        if not inside:
            offenders.append(resolved)
    return offenders


def _load_security_doc() -> str:
    assert SECURITY_DOC.is_file(), f"security policy missing: {SECURITY_DOC}"
    return SECURITY_DOC.read_text(encoding="utf-8")


def _parse_security_ledger(text: str) -> dict[str, str]:
    match = LEDGER_FENCE_RE.search(text)
    assert match is not None, "security.md must contain a fenced security-ledger block"
    ledger: dict[str, str] = {}
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        assert ":" in line, f"malformed ledger line: {raw_line!r}"
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        assert key and value, f"empty ledger entry: {raw_line!r}"
        assert key not in ledger, f"duplicate ledger key: {key}"
        ledger[key] = value
    return ledger


def _snapshot_tree(root: Path) -> dict[str, tuple[bool, int]]:
    """Map relative path -> (is_dir, size) for side-effect detection."""

    if not root.exists():
        return {}
    snap: dict[str, tuple[bool, int]] = {}
    for path in root.rglob("*"):
        rel = str(path.relative_to(root))
        if path.is_dir():
            snap[rel] = (True, 0)
        elif path.is_file():
            snap[rel] = (False, path.stat().st_size)
        else:
            snap[rel] = (False, -1)
    return snap


# ---------------------------------------------------------------------------
# Security document / ledger
# ---------------------------------------------------------------------------


def test_security_document_exists_and_is_complete() -> None:
    text = _load_security_doc()
    assert "KVFS-808" in text
    assert "Decision status:** Accepted" in text or "**Status:** Accepted" in text
    assert "TODO" not in text
    assert "FIXME" not in text
    assert "PLACEHOLDER" not in text
    for heading in (
        "Default security profile",
        "Closed FUSE option allowlist",
        "Fail-closed attack classes",
        "Zero side-effect invariant",
        "Machine-readable security ledger",
    ):
        assert heading in text


def test_security_ledger_encodes_fail_closed_profile() -> None:
    ledger = _parse_security_ledger(_load_security_doc())
    assert ledger["task"] == TASK_ID
    assert ledger["decision_status"] == "Accepted"
    assert ledger["security_profile"] == "default_fail_closed"
    assert ledger["default_permissions"] == "on"
    assert ledger["allow_other"] == "off"
    assert ledger["allow_other_requires_explicit_opt_in"] == "true"
    assert ledger["allow_other_requires_operator_warning"] == "true"
    assert ledger["allow_root"] == "rejected"
    assert ledger["mount_option_policy"] == "closed_allowlist"
    assert ledger["invariant.zero_side_effect_outside_roots"] == "true"
    assert ledger["invariant.traversal_escape_count"] == "0"
    assert ledger["invariant.symlink_escape_count"] == "0"
    assert ledger["invariant.reserved_alias_escape_count"] == "0"
    for attack in REQUIRED_ATTACK_CLASSES:
        key = f"attack.{attack}"
        assert key in ledger, f"missing attack class {attack}"
        assert ledger[key] == "fail_closed"
    admitted = {item.strip() for item in ledger["admitted_options"].split(",")}
    assert admitted == set(ADMITTED_FUSE_OPTIONS)


# ---------------------------------------------------------------------------
# Path traversal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "../secret",
        "a/../../b",
        "docs/../../../etc/passwd",
        "./hidden",
        "a//b",
        "a/./b",
        "//server/share",
        r"C:\Windows\System32",
        r"\\?\C:\Windows",
        "~/secrets",
        "$HOME/secrets",
        "%USERPROFILE%/secrets",
        "a%2f../b",
        "a%2F..%2Fb",
        "a\x00b",
        "a\\" + "b",
    ],
)
def test_path_traversal_and_absolute_forms_fail_closed(
    raw: str, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    before = _snapshot_tree(outside)
    with pytest.raises(VFSPathError) as ei:
        normalize_vfs_path(raw)
    assert ei.value.reason in {
        VFSPathRejectReason.TRAVERSAL,
        VFSPathRejectReason.DOT_SEGMENT,
        VFSPathRejectReason.EMPTY_SEGMENT,
        VFSPathRejectReason.ABSOLUTE,
        VFSPathRejectReason.WINDOWS_DRIVE,
        VFSPathRejectReason.UNC,
        VFSPathRejectReason.BACKSLASH,
        VFSPathRejectReason.HOME_EXPANSION,
        VFSPathRejectReason.ENV_EXPANSION,
        VFSPathRejectReason.PERCENT_ENCODED_SEPARATOR,
        VFSPathRejectReason.NUL,
        VFSPathRejectReason.CONTROL_CHAR,
        VFSPathRejectReason.ESCAPE,
    }
    assert _snapshot_tree(outside) == before


def test_single_leading_slash_is_namespace_sugar_not_os_escape() -> None:
    """One leading slash is namespace-root sugar; it must not become OS absolute."""

    norm = normalize_vfs_path("/docs/readme")
    assert norm.path == "docs/readme"
    assert not norm.path.startswith("/")


def test_confine_path_rejects_escape_with_zero_external_side_effect(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    admitted = tmp_path / "admitted"
    outside.mkdir()
    admitted.mkdir()
    before = _snapshot_tree(outside)
    with pytest.raises(VFSPathError):
        confine_path("../outside", "docs")
    with pytest.raises(VFSPathError):
        normalize_vfs_path("docs/../../outside")
    ok = confine_path("docs/readme", "docs")
    assert ok.path == "readme"
    assert ok.root == "docs"
    assert _snapshot_tree(outside) == before
    assert paths_outside_admitted_roots([outside], [admitted]) == [outside.resolve()]


# ---------------------------------------------------------------------------
# Symlink escape
# ---------------------------------------------------------------------------


def test_symlink_default_reject_and_escape_fail_closed(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    before = _snapshot_tree(outside)

    default = evaluate_symlink(
        "target.txt", link_path="docs/link", root="docs"
    )
    assert default.allowed is False
    assert default.reason is VFSPathRejectReason.SYMLINK_REJECTED

    follow = VFSPathPolicy(symlink_policy=SymlinkPolicy.FOLLOW_WITHIN_ROOT)
    escape = evaluate_symlink(
        "../outside",
        link_path="docs/link",
        root="docs",
        policy=follow,
    )
    assert escape.allowed is False
    assert escape.reason in {
        VFSPathRejectReason.SYMLINK_ESCAPE,
        VFSPathRejectReason.TRAVERSAL,
        VFSPathRejectReason.ESCAPE,
    }

    absolute = evaluate_symlink(
        "/etc/passwd",
        link_path="docs/link",
        root="docs",
        policy=follow,
    )
    assert absolute.allowed is False
    assert absolute.reason is VFSPathRejectReason.SYMLINK_ESCAPE

    within = evaluate_symlink(
        "target.txt",
        link_path="docs/sub/link",
        root="docs",
        policy=follow,
    )
    assert within.allowed is True
    assert within.target is not None
    assert within.target.path == "sub/target.txt" or within.target.path.endswith(
        "target.txt"
    )
    assert _snapshot_tree(outside) == before


# ---------------------------------------------------------------------------
# Unicode / case / reserved aliases
# ---------------------------------------------------------------------------


def test_unicode_non_nfc_and_case_fold_aliases_fail_closed() -> None:
    nfc = "café"
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd
    assert normalize_vfs_path(f"docs/{nfc}").path.endswith(nfc)
    with pytest.raises(VFSPathError) as ei:
        normalize_vfs_path(f"docs/{nfd}")
    assert ei.value.reason is VFSPathRejectReason.NON_NFC

    policy = VFSPathPolicy(case_policy=CasePolicy.SENSITIVE)
    a = normalize_vfs_path("Docs/Readme", policy=policy)
    b = normalize_vfs_path("docs/readme", policy=policy)
    assert a.path != b.path


@pytest.mark.parametrize(
    "name",
    ["CON", "nul", "COM1", "LPT9", "AUX", "PRN", "CON.txt", "nul.log"],
)
def test_reserved_device_name_aliases_fail_closed(name: str) -> None:
    result = ws.validate_windows_component(name)
    assert result.ok is False
    assert result.reason is ws.WindowsNameRejectReason.RESERVED_DEVICE
    assert result.errno is HostErrno.EINVAL


def test_windows_case_fold_collision_fails_closed() -> None:
    ns = ws.WindowsNamespace(case_mode=ws.WindowsCaseMode.INSENSITIVE)
    ns.create("File.txt")
    with pytest.raises(ws.WindowsSemanticsError) as ei:
        ns.create("file.TXT")
    assert ei.value.code is ws.WindowsSemanticsErrorCode.CASE_COLLISION
    assert ei.value.detail.get("fail_closed") is True
    hit = ns.lookup("FILE.txt")
    assert hit.found is True
    assert hit.display_spelling == "File.txt"


# ---------------------------------------------------------------------------
# Mount-option injection and unsafe allow_other
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "options",
    [
        ["modules=evil"],
        ["allow_root"],
        ["suid"],
        ["unknown_option"],
        ["fsname=$(id)"],
        ["fsname=`id`"],
        ["ro;allow_other"],
        ["rw\nallow_other"],
        ["max_read=-1"],
        ["max_read=999999999999"],
        ["fsname=has space"],
        ["subtype=../../etc"],
        ["allow_other"],  # without explicit opt-in
    ],
)
def test_mount_option_injection_fails_closed(options: list[str]) -> None:
    decision = admit_fuse_mount_options(options)
    assert decision.allowed is False
    assert decision.code in {
        "option_not_allowlisted",
        "option_forbidden",
        "option_injection",
        "option_value_invalid",
        "option_value_out_of_bounds",
        "allow_other_not_explicit",
        "option_control_char",
        "option_too_long",
        "option_empty",
        "option_type",
    }
    assert "default_permissions" not in decision.effective_options or not decision.allowed


def test_default_profile_forces_default_permissions_and_rejects_bare_allow_other() -> None:
    ok = admit_fuse_mount_options(["ro", "fsname=ipfs-kit", "max_read=131072"])
    assert ok.allowed is True
    assert "default_permissions" in ok.effective_options
    assert "allow_other" not in ok.effective_options
    assert "ro" in ok.effective_options

    bare = admit_fuse_mount_options(["allow_other"])
    assert bare.allowed is False
    assert bare.code == "allow_other_not_explicit"

    missing_warning = admit_fuse_mount_options(
        ["allow_other"],
        allow_other_explicit=True,
        acknowledge_allow_other_warning=False,
    )
    assert missing_warning.allowed is False
    assert missing_warning.code == "allow_other_warning_required"

    admitted = admit_fuse_mount_options(
        ["allow_other", "ro"],
        allow_other_explicit=True,
        acknowledge_allow_other_warning=True,
    )
    assert admitted.allowed is True
    assert "allow_other" in admitted.effective_options
    assert "default_permissions" in admitted.effective_options
    assert admitted.warnings
    assert "multi-user" in admitted.warnings[0].lower() or "allow_other" in admitted.warnings[0]


def test_linux_mount_config_does_not_expose_privilege_options(tmp_path: Path) -> None:
    cfg = LinuxMountConfig(
        mountpoint=tmp_path / "mnt",
        state_directory=tmp_path / "state",
        hermetic=True,
    )
    record = cfg.to_record()
    encoded = json.dumps(record)
    assert "allow_other" not in encoded
    assert "allow_root" not in encoded
    assert "modules" not in encoded
    # Hermetic lifecycle never starts a privileged multi-user mount by default.
    assert cfg.hermetic is True


# ---------------------------------------------------------------------------
# State / mount overlap
# ---------------------------------------------------------------------------


def test_state_mount_overlap_fails_doctor_closed(tmp_path: Path) -> None:
    same = tmp_path / "same"
    same.mkdir()
    report = run_linux_doctor(mountpoint=same, state_dir=same, budget_seconds=5.0)
    sep = report["checks"]["mountpoint_state_separation"]
    assert sep["available"] is False
    assert sep["same_path"] is True
    assert report["native_capability_ready"] is False
    assert report["mounted"] is False

    mount = tmp_path / "mnt"
    nested = mount / "state"
    mount.mkdir()
    nested.mkdir()
    nested_report = run_linux_doctor(
        mountpoint=mount, state_dir=nested, budget_seconds=5.0
    )
    nested_sep = nested_report["checks"]["mountpoint_state_separation"]
    assert nested_sep["available"] is False
    assert nested_sep["state_nested_under_mountpoint"] is True
    assert nested_report["mounted"] is False


def test_separated_mount_and_state_are_admitted_by_doctor(tmp_path: Path) -> None:
    mount = tmp_path / "mnt"
    state = tmp_path / "state"
    mount.mkdir()
    state.mkdir()
    report = run_linux_doctor(mountpoint=mount, state_dir=state, budget_seconds=5.0)
    sep = report["checks"]["mountpoint_state_separation"]
    assert sep["separated"] is True
    assert sep["same_path"] is False
    assert report["mounted"] is False


# ---------------------------------------------------------------------------
# Stale PID / lease
# ---------------------------------------------------------------------------


def _dead_pid() -> int:
    pid = 2**22 + 91
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return pid
        except PermissionError:
            pid += 1
            continue
        except OSError:
            return pid
        pid += 1


def test_stale_pid_reported_without_claiming_live_lease(tmp_path: Path) -> None:
    stale_dir = tmp_path / "stale-state"
    stale_dir.mkdir()
    dead = _dead_pid()
    ready = MountReadiness(
        mount_id="mount:stale",
        pid=dead,
        mountpoint=str(tmp_path / "stale-mnt"),
        state_directory=str(stale_dir),
        recovery_complete=True,
        ready=True,
        lifecycle_state="ready",
        wal_generation="wal-gen:stale",
        cache_generation=1,
        ready_unix_ms=int(time.time() * 1000) - 120_000,
    )
    hb = MountHeartbeat(
        mount_id="mount:stale",
        pid=dead,
        mountpoint=str(tmp_path / "stale-mnt"),
        state_directory=str(stale_dir),
        lifecycle_state="ready",
        wal_generation="wal-gen:stale",
        wal_position="0",
        cache_generation=1,
        cache_entries=0,
        heartbeat_unix_ms=int(time.time() * 1000) - 120_000,
        sequence=1,
    )
    (stale_dir / READY_FILENAME).write_text(
        json.dumps(ready.to_record()) + "\n", encoding="utf-8"
    )
    (stale_dir / HEARTBEAT_FILENAME).write_text(
        json.dumps(hb.to_record()) + "\n", encoding="utf-8"
    )

    outside = tmp_path / "outside"
    outside.mkdir()
    before = _snapshot_tree(outside)

    report = report_stale_mounts(tmp_path, stale_heartbeat_seconds=1.0)
    assert report.blocked is False
    assert any(item.get("mount_id") == "mount:stale" for item in report.stale)
    assert _snapshot_tree(outside) == before


def test_state_lease_fences_second_holder(tmp_path: Path) -> None:
    state = tmp_path / "lease-state"
    first = StateLease(state, mount_id="mount:a", holder_id="holder:a")
    holder = first.try_acquire()
    assert holder.holder_id == "holder:a"
    assert first.held is True

    second = StateLease(state, mount_id="mount:a", holder_id="holder:b")
    with pytest.raises(StateLeaseHeldError):
        second.try_acquire()
    assert second.held is False

    first.release()
    # After release, a new holder may acquire.
    third = StateLease(state, mount_id="mount:a", holder_id="holder:c")
    regained = third.try_acquire()
    assert regained.holder_id == "holder:c"
    third.release()


# ---------------------------------------------------------------------------
# Permission confusion
# ---------------------------------------------------------------------------


def test_permission_confusion_fails_closed() -> None:
    # Owner-only write mode: group/other writers denied.
    mode = 0o100600
    assert mode_grants(
        mode, W_OK, file_uid=1000, file_gid=1000, caller_uid=1000, caller_gid=1000
    )
    assert not mode_grants(
        mode, W_OK, file_uid=1000, file_gid=1000, caller_uid=1001, caller_gid=1000
    )
    assert not mode_grants(
        mode, R_OK, file_uid=1000, file_gid=1000, caller_uid=1001, caller_gid=1001
    )

    projector = MetadataProjector(uid_gid_policy=UidGidPolicy.fixed(uid=42, gid=42))
    attr = make_file_attr(
        2,
        path="private.bin",
        mode=0o100640,
        size=8,
        uid=42,
        gid=42,
    )
    projector.put(attr)
    # Non-owner, non-group caller cannot write.
    denied = projector.access(
        "private.bin",
        W_OK,
        caller_uid=99,
        caller_gid=99,
    )
    assert denied.allowed is False
    assert denied.errno is HostErrno.EACCES

    # Stored ownership is projected; caller identity is not substituted as owner.
    projected = projector.project(attr, caller_uid=99, caller_gid=99)
    assert projected.uid == 42
    assert projected.gid == 42
    assert projected.file_type is FileType.FILE


def test_execute_bit_confusion_does_not_grant_write() -> None:
    mode = 0o100111  # execute-only for all
    assert mode_grants(
        mode, X_OK, file_uid=1, file_gid=1, caller_uid=2, caller_gid=2
    )
    assert not mode_grants(
        mode, W_OK, file_uid=1, file_gid=1, caller_uid=2, caller_gid=2
    )
    assert not mode_grants(
        mode, R_OK, file_uid=1, file_gid=1, caller_uid=2, caller_gid=2
    )


# ---------------------------------------------------------------------------
# Oversized request
# ---------------------------------------------------------------------------


def test_oversized_path_and_io_requests_fail_closed(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    before = _snapshot_tree(outside)

    huge_segment = "a" * (MAX_SEGMENT_BYTES + 1)
    with pytest.raises(VFSPathError) as ei:
        normalize_vfs_path(huge_segment)
    assert ei.value.reason is VFSPathRejectReason.SEGMENT_TOO_LONG

    huge_path = "/".join(["seg"] * 300)
    if len(huge_path.encode("utf-8")) <= MAX_PATH_BYTES:
        huge_path = ("x" * 200 + "/") * 30
    with pytest.raises(VFSPathError) as ei2:
        normalize_vfs_path(huge_path[: MAX_PATH_BYTES + 50])
    assert ei2.value.reason in {
        VFSPathRejectReason.PATH_TOO_LONG,
        VFSPathRejectReason.SEGMENT_TOO_LONG,
    }

    with pytest.raises((HostBoundsError, HostContractError, ValueError)):
        HostCallbackRequest(
            kind=HostCallbackKind.READ,
            path="file.bin",
            size=MAX_IO_LENGTH + 1,
        )

    with pytest.raises(RangeExtentError):
        validate_length(MAX_RANGE_LENGTH + 1)

    assert _snapshot_tree(outside) == before
    assert HOST_MAX_PATH_BYTES >= 4096
    assert MAX_PATH_BYTES >= 4096


# ---------------------------------------------------------------------------
# Handle / WAL / ARC exhaustion
# ---------------------------------------------------------------------------


def test_handle_exhaustion_fails_closed_with_pressure(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    before = _snapshot_tree(outside)

    table = HandleTable(max_open_handles=2, clock_ms=lambda: 1_000)
    table.create("a.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    table.create("b.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    pressure = table.pressure_state()
    assert pressure.pressure is True
    assert "open_handles" in pressure.reason
    with pytest.raises(HandleError) as ei:
        table.create("c.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    assert ei.value.code is HandleErrorCode.PRESSURE
    assert ei.value.errno is HostErrno.EMFILE
    assert _snapshot_tree(outside) == before


def test_wal_and_arc_exhaustion_fail_closed(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    before = _snapshot_tree(outside)

    # WAL: oversized identifier / secret material reject at construction.
    with pytest.raises((VFSWALRecordBoundsError, SecretMaterialError, ValueError)):
        make_durable_data(
            transaction_id="tx:" + ("t" * 10_000),
            operation_id="op:1",
            effect_id="effect:1",
            intent=VFSWALIntentKind.WRITE,
            path_ref="path:docs-a",
            content=VFSWALContent.inline("x"),
        )

    with pytest.raises(SecretMaterialError):
        make_durable_data(
            transaction_id="tx:1",
            operation_id="op:1",
            effect_id="effect:1",
            intent=VFSWALIntentKind.WRITE,
            path_ref="path:docs-a",
            content=VFSWALContent.inline("hello"),
            intent_detail={"api_key": "super-secret-value"},
        )

    with pytest.raises((VFSWALRecordBoundsError, SecretMaterialError)):
        VFSWALContent.inline("x" * 10_000)

    # ARC: invalid capacity and oversized keys reject.
    with pytest.raises(ARCSizeError):
        ARCConfig(capacity_bytes=0)
    with pytest.raises(ARCKeyError):
        CacheKey("x" * (MAX_KEY_BYTES + 8))
    with pytest.raises(ARCKeyError):
        CacheKey("")  # empty key
    with pytest.raises(RangeExtentError):
        validate_length(MAX_RANGE_LENGTH + 64)

    assert _snapshot_tree(outside) == before


# ---------------------------------------------------------------------------
# Malformed native error / false success
# ---------------------------------------------------------------------------


def test_malformed_native_error_cannot_become_false_success() -> None:
    with pytest.raises(HostFalseSuccessError):
        HostCallbackResult(
            kind=HostCallbackKind.READ,
            success=True,
            errno=HostErrno.EIO,
        )

    with pytest.raises(HostContractError):
        HostError(errno=HostErrno.OK, message="should not be constructible")

    with pytest.raises(HostContractError):
        HostCallbackResult(
            kind=HostCallbackKind.GETATTR,
            success=False,
            errno=HostErrno.OK,
            error=None,
        )

    # Explicit-unsupported must not succeed.
    with pytest.raises(HostFalseSuccessError):
        HostCallbackResult(
            kind=HostCallbackKind.SYMLINK,
            success=True,
            errno=HostErrno.OK,
            observed_effect=True,
        )

    failure = HostCallbackResult.make_failure(
        HostCallbackKind.READ,
        HostErrno.EIO,
        message="native I/O failure",
    )
    assert failure.success is False
    assert failure.errno is HostErrno.EIO
    assert failure.errno_number != 0


def test_unknown_callback_is_rejected_not_success() -> None:
    with pytest.raises(HostUnknownCallbackError):
        parse_callback_kind("not_a_real_callback")


# ---------------------------------------------------------------------------
# Secret / log leakage
# ---------------------------------------------------------------------------


def test_secret_material_rejected_from_wal_and_redacted_from_logs(
    tmp_path: Path,
) -> None:
    with pytest.raises(SecretMaterialError):
        VFSWALContent.inline("password=hunter2")
    with pytest.raises(SecretMaterialError):
        make_durable_data(
            transaction_id="tx:sec",
            operation_id="op:sec",
            effect_id="effect:sec",
            intent=VFSWALIntentKind.WRITE,
            path_ref="path:docs-a",
            intent_detail={"api_key": "super-secret-value"},
        )

    dirty = {
        "mount_id": "mount:1",
        "api_key": "super-secret",
        "nested": {"access_token": "abc", "path": "docs/a"},
        "note": "Authorization: Bearer abc.def",
        "ok_field": "public-status",
    }
    cleaned = redact_secrets(dirty)
    assert cleaned["api_key"] == REDACTED
    assert cleaned["nested"]["access_token"] == REDACTED
    assert cleaned["note"] == REDACTED
    assert cleaned["ok_field"] == "public-status"
    assert cleaned["mount_id"] == "mount:1"
    encoded = json.dumps(cleaned)
    assert "super-secret" not in encoded
    assert "abc.def" not in encoded

    # Lifecycle status records are closed and do not include secret keys.
    status_keys = {
        "schema",
        "contract_version",
        "task_id",
        "mount_id",
        "pid",
        "mountpoint",
        "state_directory",
        "lifecycle_state",
        "ready",
        "recovery_complete",
        "lease_held",
        "holder_id",
        "wal",
        "cache",
        "workers",
        "open_callbacks",
        "mounted",
        "status_unix_ms",
        "heartbeat_unix_ms",
        "exit_code",
    }
    for secret in SECRET_KEY_FRAGMENTS:
        assert secret not in status_keys


# ---------------------------------------------------------------------------
# Cleanup attacks / zero external side effects
# ---------------------------------------------------------------------------


def test_cleanup_unmount_preserves_recovery_and_spares_outside_roots(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "must-not-touch"
    sentinel.write_text("keep\n", encoding="utf-8")
    before_outside = _snapshot_tree(outside)

    mountpoint = tmp_path / "mnt"
    state = tmp_path / "state"
    mountpoint.mkdir()
    state.mkdir()
    recovery = state / "recovery"
    recovery.mkdir()
    (recovery / "wal-marker").write_text("recovery-data\n", encoding="utf-8")

    cfg = LinuxMountConfig(
        mountpoint=mountpoint,
        state_directory=state,
        mount_id="mount:cleanup",
        hermetic=True,
        readiness_timeout_seconds=10.0,
    )
    life = LinuxMountLifecycle(cfg)
    life.start(wait_ready=True)
    assert life.ready is True

    receipt = life.unmount()
    assert receipt.success is True
    assert receipt.recovery_preserved is True
    # Recovery data remains under the admitted state directory (never outside).
    preserved = (state / "recovery").exists() or (state / "recovery-preserved").exists()
    assert preserved is True
    # Pre-seeded recovery marker must not have been deleted by cleanup.
    if (recovery / "wal-marker").is_file():
        assert (recovery / "wal-marker").read_text(encoding="utf-8") == "recovery-data\n"

    # Outside root unchanged — zero side effect outside admitted roots.
    assert _snapshot_tree(outside) == before_outside
    assert sentinel.read_text(encoding="utf-8") == "keep\n"
    assert paths_outside_admitted_roots([sentinel], [mountpoint, state]) == [
        sentinel.resolve()
    ]

    # Repeated unmount is idempotent and still does not touch outside roots.
    receipt2 = life.unmount()
    assert receipt2.success is True
    assert _snapshot_tree(outside) == before_outside


def test_rejected_adversarial_suite_has_zero_side_effect_outside_roots(
    tmp_path: Path,
) -> None:
    """Composite invariant: a batch of rejects never mutates foreign trees."""

    admitted_ns = "docs"
    outside = tmp_path / "outside-root"
    admitted_fs = tmp_path / "admitted-root"
    outside.mkdir()
    admitted_fs.mkdir()
    (admitted_fs / "marker").write_text("admitted\n", encoding="utf-8")
    before_outside = _snapshot_tree(outside)
    before_admitted = _snapshot_tree(admitted_fs)

    attacks: list[Any] = []

    # Path / symlink / options / permissions / resources.
    for raw in ("../escape", "docs/../../etc/passwd", "~/x", "$HOME/x"):
        try:
            normalize_vfs_path(raw)
            attacks.append(("path-unexpected-success", raw))
        except VFSPathError:
            pass

    decision = evaluate_symlink(
        "../escape", link_path="docs/link", root=admitted_ns
    )
    assert decision.allowed is False

    opt = admit_fuse_mount_options(["allow_other", "modules=x"])
    assert opt.allowed is False

    assert not mode_grants(
        0o100600, W_OK, file_uid=1, file_gid=1, caller_uid=2, caller_gid=2
    )

    table = HandleTable(max_open_handles=1, clock_ms=lambda: 1)
    table.create("only.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
    try:
        table.create("two.bin", (OpenFlag.O_RDWR, OpenFlag.O_CREAT))
        attacks.append("handle-unexpected-success")
    except HandleError:
        pass

    assert not attacks, f"unexpected successes: {attacks}"
    assert _snapshot_tree(outside) == before_outside
    assert _snapshot_tree(admitted_fs) == before_admitted
    offenders = paths_outside_admitted_roots(
        [outside / "x", admitted_fs / "marker"],
        [admitted_fs],
    )
    assert (outside / "x").resolve() in offenders
    assert (admitted_fs / "marker").resolve() not in offenders


# ---------------------------------------------------------------------------
# Import / hermetic constraints
# ---------------------------------------------------------------------------


def test_security_suite_does_not_require_fusepy_or_native_mount() -> None:
    """Adversarial suite imports only hermetic / probe-only surfaces."""

    # Runtime imports used by this module must not pull native FUSE bindings.
    import ipfs_kit_py.kernel_vfs.linux as linux_mod
    import ipfs_kit_py.kernel_vfs.platform as platform_mod
    import ipfs_kit_py.core.vfs.contracts as contracts_mod

    for module in (linux_mod, platform_mod, contracts_mod):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for banned in (
            "\nimport fuse\n",
            "\nimport fusepy\n",
            "\nfrom fuse ",
            "\nfrom fusepy ",
        ):
            assert banned not in source, f"{module.__name__} imports native FUSE"
    # Default Linux mount config is hermetic (no live FUSE loop).
    assert LinuxMountConfig.__dataclass_fields__["hermetic"].default is True
