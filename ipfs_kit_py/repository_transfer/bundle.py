"""Bounded repository transfer modes (EAAEF-021).

Admit and reconstruct a repository from one of five closed locators:

* managed aliases
* Git bundles
* manifested source bundles
* approved remote aliases
* uploaded object sets

Callers never supply an arbitrary remote host path.  Reconstruction writes
only into a caller-supplied quarantine directory and never mutates a user
checkout.  Network fetch is not admitted; approved remotes reconstruct from
already-staged content-addressed artifacts.

Records are immutable, DAG-JSON compatible, content addressed, and strictly
versioned at major ``@1``.  Unknown schemas, floats, private material, and
hidden chain-of-thought are rejected.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import zlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from ipaddress import ip_address
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import MappingProxyType
from typing import Any, ClassVar, Final, TypeVar
from urllib.parse import urlparse

CONTRACT_VERSION: Final[int] = 1
SCHEMA_VERSION: Final[int] = CONTRACT_VERSION

REPOSITORY_HANDOFF_BUNDLE_INTERFACE: Final[str] = "RepositoryHandoffBundle@1"
REPOSITORY_SNAPSHOT_MANIFEST_INTERFACE: Final[str] = "RepositorySnapshotManifest@1"
DIRTY_OVERLAY_MANIFEST_INTERFACE: Final[str] = "DirtyOverlayManifest@1"
REPOSITORY_TRANSFER_RECEIPT_INTERFACE: Final[str] = "RepositoryTransferReceipt@1"

REPOSITORY_HANDOFF_BUNDLE_SCHEMA: Final[str] = (
    "ipfs_kit_py/repository-transfer/handoff-bundle@1"
)
REPOSITORY_SNAPSHOT_MANIFEST_SCHEMA: Final[str] = (
    "ipfs_kit_py/repository-transfer/snapshot-manifest@1"
)
DIRTY_OVERLAY_MANIFEST_SCHEMA: Final[str] = (
    "ipfs_kit_py/repository-transfer/dirty-overlay-manifest@1"
)
REPOSITORY_TRANSFER_RECEIPT_SCHEMA: Final[str] = (
    "ipfs_kit_py/repository-transfer/transfer-receipt@1"
)
REPOSITORY_TRANSFER_REQUEST_SCHEMA: Final[str] = (
    "ipfs_kit_py/repository-transfer/transfer-request@1"
)
TRANSFER_POLICY_SCHEMA: Final[str] = (
    "ipfs_kit_py/repository-transfer/transfer-policy@1"
)
SOURCE_BUNDLE_MANIFEST_SCHEMA: Final[str] = (
    "ipfs_kit_py/repository-transfer/source-bundle-manifest@1"
)
MANAGED_ALIAS_SCHEMA: Final[str] = (
    "ipfs_kit_py/repository-transfer/managed-alias@1"
)
APPROVED_REMOTE_ALIAS_SCHEMA: Final[str] = (
    "ipfs_kit_py/repository-transfer/approved-remote-alias@1"
)

REPOSITORY_TRANSFER_CONTRACT_FAMILY: Final[Mapping[str, str]] = MappingProxyType(
    {
        "bundle": REPOSITORY_HANDOFF_BUNDLE_INTERFACE,
        "snapshot": REPOSITORY_SNAPSHOT_MANIFEST_INTERFACE,
        "overlay": DIRTY_OVERLAY_MANIFEST_INTERFACE,
        "receipt": REPOSITORY_TRANSFER_RECEIPT_INTERFACE,
    }
)

ABSOLUTE_MAX_TEXT_BYTES: Final[int] = 65_536
ABSOLUTE_MAX_RECORD_BYTES: Final[int] = 1_048_576
ABSOLUTE_MAX_PATHS: Final[int] = 4_096
ABSOLUTE_MAX_REFS: Final[int] = 4_096
ABSOLUTE_MAX_OBJECTS: Final[int] = 100_000
ABSOLUTE_MAX_ARTIFACT_BYTES: Final[int] = 64 * 1024 * 1024
ABSOLUTE_MAX_DEPTH: Final[int] = 16
ABSOLUTE_MAX_ITEMS: Final[int] = 16_384
ABSOLUTE_MAX_ID_BYTES: Final[int] = 256
ABSOLUTE_MAX_REASON_BYTES: Final[int] = 256
ABSOLUTE_MAX_ALIAS_BYTES: Final[int] = 64

DEFAULT_MAX_PATHS: Final[int] = 1_024
DEFAULT_MAX_REFS: Final[int] = 256
DEFAULT_MAX_OBJECTS: Final[int] = 8_192
DEFAULT_MAX_ARTIFACT_BYTES: Final[int] = 8 * 1024 * 1024
DEFAULT_MAX_TEXT_BYTES: Final[int] = 16_384
DEFAULT_MAX_RECORD_BYTES: Final[int] = 262_144
DEFAULT_MAX_DEPTH: Final[int] = 8
DEFAULT_MAX_ID_BYTES: Final[int] = 128
DEFAULT_GIT_TIMEOUT_SECONDS: Final[float] = 30.0

_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")
_HEX64_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_GIT_OID_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
_ALIAS_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,63}$")
_REF_NAME_RE: Final[re.Pattern[str]] = re.compile(
    r"^(HEAD|refs/(heads|tags|remotes|notes)/[A-Za-z0-9._/\-]+)$"
)
_FILE_MODE_RE: Final[re.Pattern[str]] = re.compile(
    r"^(100644|100755|120000|160000|040000)$"
)

_HIDDEN_CHAIN_OF_THOUGHT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "chain_of_thought",
        "cot",
        "hidden_chain_of_thought",
        "hidden_cot",
        "hidden_reasoning",
        "hidden_thoughts",
        "internal_monologue",
        "model_thoughts",
        "private_reasoning",
        "private_thinking",
        "scratchpad",
        "thinking",
        "thinking_blocks",
        "thinking_private",
        "thinking_text",
    }
)
_PRIVATE_FIELD_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "cookie",
        "credential",
        "hidden_witness",
        "password",
        "private_key",
        "private_premise",
        "private_witness",
        "refresh_token",
        "secret",
        "session_token",
        "transcript_body",
        "witness",
    }
)
_HOST_PATH_FIELD_MARKERS: Final[frozenset[str]] = frozenset(
    {
        "absolute_path",
        "checkout",
        "checkout_path",
        "directory",
        "filesystem_path",
        "host_path",
        "local_path",
        "realpath",
        "repo_path",
        "repository_path",
        "source_path",
        "workdir",
        "working_directory",
        "working_tree",
        "worktree_path",
    }
)
_FORBIDDEN_URL_SCHEMES: Final[frozenset[str]] = frozenset(
    {
        "file",
        "git",
        "git+file",
        "git+ssh",
        "ssh",
        "rsync",
        "ftp",
        "unix",
        "smb",
        "nfs",
    }
)
_LOCAL_HOSTS: Final[frozenset[str]] = frozenset(
    {
        "",
        "localhost",
        "localhost.localdomain",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "::",
    }
)
_GIT_ENV: Final[Mapping[str, str]] = MappingProxyType(
    {
        "GIT_AUTHOR_NAME": "repository-transfer",
        "GIT_AUTHOR_EMAIL": "repository-transfer@example.test",
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+0000",
        "GIT_COMMITTER_NAME": "repository-transfer",
        "GIT_COMMITTER_EMAIL": "repository-transfer@example.test",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+0000",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GC_AUTO": "0",
        "LANG": "C",
        "LC_ALL": "C",
    }
)

TEnum = TypeVar("TEnum", bound=Enum)


class RepositoryTransferError(ValueError):
    """Malformed or unsafe repository transfer contract."""


class TransferBoundsError(RepositoryTransferError):
    """A transfer value exceeded a declared resource bound."""


class TransferIdentityError(RepositoryTransferError):
    """A claimed content identity did not match its canonical payload."""


class TransferVersionError(RepositoryTransferError):
    """Unsupported transfer schema name or contract version."""


class TransferTrustError(RepositoryTransferError):
    """Imported history or a locator attempted to grant extra authority."""


class TransferEngineError(RepositoryTransferError):
    """Reconstruction inside quarantine failed closed."""


class RepositoryTransferMode(str, Enum):
    """Closed locators admitted by RepositoryHandoffBundle@1."""

    MANAGED_ALIAS = "managed_alias"
    GIT_BUNDLE = "git_bundle"
    MANIFESTED_SOURCE_BUNDLE = "manifested_source_bundle"
    APPROVED_REMOTE_ALIAS = "approved_remote_alias"
    UPLOADED_OBJECT_SET = "uploaded_object_set"

    @property
    def is_alias(self) -> bool:
        return self in {
            RepositoryTransferMode.MANAGED_ALIAS,
            RepositoryTransferMode.APPROVED_REMOTE_ALIAS,
        }


class TransferVerdict(str, Enum):
    """Closed transfer outcomes.  Refusal is not reconstruction."""

    ADMITTED = "admitted"
    REFUSED = "refused"


class TransferRefusal(str, Enum):
    """Typed refusal codes.  Callers must not treat these as success."""

    ARBITRARY_HOST_PATH = "arbitrary_host_path"
    UNKNOWN_TRANSFER_MODE = "unknown_transfer_mode"
    UNKNOWN_ALIAS = "unknown_alias"
    UNAPPROVED_REMOTE = "unapproved_remote"
    ARTIFACT_MISSING = "artifact_missing"
    ARTIFACT_DIGEST_MISMATCH = "artifact_digest_mismatch"
    MANIFEST_PATH_ESCAPE = "manifest_path_escape"
    BOUNDS_EXCEEDED = "bounds_exceeded"
    FORBIDDEN_FIELD = "forbidden_field"
    USER_CHECKOUT_MUTATION = "user_checkout_mutation_refused"
    REMOTE_FETCH_NOT_ADMITTED = "remote_fetch_not_admitted"
    DECLARED_STATE_MISMATCH = "declared_state_mismatch"
    UNSAFE_SYMLINK = "unsafe_symlink"
    HOOKS_NOT_DISABLED = "hooks_not_disabled"
    NESTED_GIT_UNDECLARED = "nested_git_undeclared"
    ENGINE_FAILURE = "engine_failure"
    EMPTY_LOCATOR = "empty_locator"
    QUARANTINE_UNSAFE = "quarantine_unsafe"


class OverlayStatus(str, Enum):
    """Worktree overlay entry status."""

    UNMODIFIED = "unmodified"
    MODIFIED = "modified"
    ADDED = "added"
    DELETED = "deleted"
    UNTRACKED = "untracked"
    RENAMED = "renamed"
    SYMLINK = "symlink"
    GITLINK = "gitlink"


class ArtifactKind(str, Enum):
    """Concrete artifact a resolved locator must name."""

    GIT_BUNDLE = "git_bundle"
    SOURCE_BUNDLE = "manifested_source_bundle"
    OBJECT_SET = "uploaded_object_set"


def _normalize_key(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_")


def _canonical_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        raise RepositoryTransferError(
            "canonical transfer contracts cannot contain floats"
        )
    if isinstance(value, Enum):
        return _canonical_value(value.value)
    if isinstance(value, CanonicalTransferRecord):
        return value.to_dict()
    if isinstance(value, Mapping):
        if not all(isinstance(raw_key, str) for raw_key in value):
            raise RepositoryTransferError("canonical object keys must be strings")
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_canonical_value(item) for item in value]
        return sorted(items, key=canonical_json_bytes)
    raise RepositoryTransferError(
        f"unsupported canonical transfer value: {type(value).__name__}"
    )


def canonical_json_bytes(value: Any) -> bytes:
    """Encode deterministic DAG-JSON-compatible UTF-8 bytes."""

    return json.dumps(
        _canonical_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_json(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def content_identity(value: Any) -> str:
    digest = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    return f"sha256:{digest}"


def artifact_identity(data: bytes) -> str:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise RepositoryTransferError("artifact bytes are required")
    return f"sha256:{hashlib.sha256(bytes(data)).hexdigest()}"


def _enum(value: Any, enum_type: type[TEnum], name: str) -> TEnum:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(str(getattr(value, "value", value)))
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise RepositoryTransferError(f"{name} must be one of: {allowed}") from exc


def looks_like_host_path(value: Any) -> bool:
    """True when ``value`` nominates a filesystem, scp, or local URL path."""

    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    lowered = text.lower()
    if lowered.startswith("~") or lowered.startswith("\\\\") or lowered.startswith("//"):
        return True
    if PurePosixPath(text).is_absolute() or PureWindowsPath(text).is_absolute():
        return True
    if re.match(r"^[A-Za-z]:[\\/]", text):
        return True
    if "://" in text:
        scheme = lowered.split(":", 1)[0]
        if scheme in _FORBIDDEN_URL_SCHEMES or scheme.startswith("git+"):
            return True
        parsed = urlparse(text)
        host = (parsed.hostname or "").lower()
        if host in _LOCAL_HOSTS or _is_loopback_or_private_host(host):
            return True
    if re.match(r"^[^@\s:/]+@[^@\s:/]+:", text) and "://" not in text:
        return True
    if text.startswith("./") or text.startswith("../") or "/../" in text or text == "..":
        return True
    if "\\" in text and not text.startswith("refs\\"):
        return True
    return False


def _is_loopback_or_private_host(host: str) -> bool:
    if not host:
        return True
    try:
        address = ip_address(host.strip("[]"))
    except ValueError:
        return False
    return bool(
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def _text(
    value: Any,
    name: str,
    *,
    required: bool = True,
    max_bytes: int = ABSOLUTE_MAX_TEXT_BYTES,
    allow_host_path: bool = False,
) -> str:
    if value is None:
        result = ""
    elif not isinstance(value, str):
        raise RepositoryTransferError(f"{name} must be a string")
    else:
        result = value.strip()
    if required and not result:
        raise RepositoryTransferError(f"{name} is required")
    if "\x00" in result:
        raise RepositoryTransferError(f"{name} must not contain NUL")
    if not allow_host_path and looks_like_host_path(result):
        raise RepositoryTransferError(
            f"{name} must not be an arbitrary remote host path"
        )
    if len(result.encode("utf-8")) > max_bytes:
        raise TransferBoundsError(f"{name} exceeds {max_bytes} UTF-8 bytes")
    return result


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise RepositoryTransferError(f"{name} must be a boolean")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RepositoryTransferError(f"{name} must be a non-negative integer")
    return value


def _positive_int(value: Any, name: str) -> int:
    result = _nonnegative_int(value, name)
    if result < 1:
        raise RepositoryTransferError(f"{name} must be at least 1")
    return result


def _major_version(name: str) -> int | None:
    if not isinstance(name, str) or "@" not in name:
        return None
    suffix = name.rsplit("@", 1)[-1]
    if not suffix.isdigit():
        return None
    return int(suffix)


def _require_versioned_name(name: str, expected: str, field_name: str) -> None:
    if name == expected:
        return
    supplied_major = _major_version(name)
    expected_major = _major_version(expected) or CONTRACT_VERSION
    if supplied_major is not None and supplied_major != expected_major:
        raise TransferVersionError(
            f"unsupported {field_name} {name!r}; rebuild with {expected}"
        )
    raise TransferVersionError(
        f"unsupported {field_name} {name!r}; expected {expected}"
    )


def _schema_and_version(
    payload: Mapping[str, Any],
    expected_schema: str,
    expected_interface: str,
    *,
    artifact_name: str,
) -> None:
    if not isinstance(payload, Mapping):
        raise RepositoryTransferError(f"{artifact_name} payload must be an object")
    schema = payload.get("schema")
    if schema not in (None, "", expected_schema):
        _require_versioned_name(str(schema), expected_schema, "schema")
    interface = payload.get("interface")
    if interface not in (None, "", expected_interface):
        _require_versioned_name(str(interface), expected_interface, "interface")
    for key in ("contract_version", "schema_version"):
        version = payload.get(key)
        if version not in (None, "", CONTRACT_VERSION):
            raise TransferVersionError(
                f"unsupported {artifact_name} contract version; rebuild with "
                f"{expected_interface}"
            )


def _reject_unknown(
    payload: Mapping[str, Any], allowed: Iterable[str], *, artifact_name: str
) -> None:
    extra = set(payload).difference(allowed)
    for key in extra:
        reason = _key_is_forbidden(str(key))
        if reason == "hidden_chain_of_thought":
            raise RepositoryTransferError(
                f"{artifact_name} must not represent hidden chain-of-thought"
            )
        if reason == "private_material":
            raise RepositoryTransferError(
                f"{artifact_name} must not contain private material"
            )
        if reason == "host_path":
            raise RepositoryTransferError(
                f"{artifact_name} must not accept arbitrary remote host paths"
            )
        value = payload.get(key)
        if isinstance(value, str) and looks_like_host_path(value):
            raise RepositoryTransferError(
                f"{artifact_name} must not accept arbitrary remote host paths"
            )
    if extra:
        raise RepositoryTransferError(
            f"{artifact_name} contains unsupported fields; rebuild its canonical payload"
        )


def _claimed_identity(
    payload: Mapping[str, Any],
    actual: str,
    *,
    names: Sequence[str],
    artifact_name: str,
) -> None:
    for name in names:
        claimed = payload.get(name)
        if claimed not in (None, "") and claimed != actual:
            raise TransferIdentityError(
                f"{artifact_name} content identity does not match payload"
            )


def _digest_sha256(value: Any, name: str, *, required: bool = True) -> str:
    text = _text(value, name, required=required, max_bytes=80)
    if not text:
        return ""
    if _HEX64_RE.fullmatch(text):
        return f"sha256:{text}"
    if _SHA256_RE.fullmatch(text):
        return text
    raise RepositoryTransferError(f"{name} must be a sha256 hex digest")


def _git_oid(value: Any, name: str, *, required: bool = False) -> str:
    text = _text(value, name, required=required, max_bytes=64)
    if not text:
        return ""
    lowered = text.lower()
    if not _GIT_OID_RE.fullmatch(lowered):
        raise RepositoryTransferError(f"{name} must be a Git object id")
    return lowered


def _alias_name(value: Any, name: str) -> str:
    text = _text(value, name, max_bytes=ABSOLUTE_MAX_ALIAS_BYTES)
    if not _ALIAS_RE.fullmatch(text):
        raise RepositoryTransferError(f"{name} must be a managed alias token")
    return text


def _ref_name(value: Any, name: str) -> str:
    text = _text(value, name, max_bytes=DEFAULT_MAX_ID_BYTES)
    if not _REF_NAME_RE.fullmatch(text):
        raise RepositoryTransferError(f"{name} must be HEAD or a refs/ name")
    return text


def _file_mode(value: Any, name: str) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        text = f"{value:06o}"
    else:
        text = _text(value, name, max_bytes=16)
        if text.startswith("0o"):
            text = text[2:]
        if re.fullmatch(r"[0-7]{3,7}", text):
            text = f"{int(text, 8):06o}"
    if text in {"0644", "000644"}:
        text = "100644"
    if text in {"0755", "000755"}:
        text = "100755"
    if not _FILE_MODE_RE.fullmatch(text):
        raise RepositoryTransferError(f"{name} must be a Git file mode")
    return text


def _relative_path(value: Any, name: str) -> str:
    text = _text(value, name, max_bytes=DEFAULT_MAX_ID_BYTES * 4).replace("\\", "/")
    candidate = PurePosixPath(text)
    if (
        candidate.is_absolute()
        or ".." in candidate.parts
        or (candidate.parts and candidate.parts[0].endswith(":"))
        or looks_like_host_path(text)
    ):
        raise RepositoryTransferError(f"{name} must be repository-relative")
    normalized = candidate.as_posix().removeprefix("./")
    if normalized in ("", "."):
        raise RepositoryTransferError(f"{name} must not be empty")
    if normalized == ".git" or normalized.startswith(".git/"):
        raise RepositoryTransferError(f"{name} must not address Git metadata")
    return normalized


def _key_is_forbidden(key: str) -> str | None:
    normalized = _normalize_key(key)
    if normalized in _HIDDEN_CHAIN_OF_THOUGHT_KEYS:
        return "hidden_chain_of_thought"
    if any(
        normalized == marker or normalized.endswith("_" + marker) or marker in normalized
        for marker in _PRIVATE_FIELD_MARKERS
    ):
        return "private_material"
    if normalized in _HOST_PATH_FIELD_MARKERS:
        return "host_path"
    return None


def _reject_forbidden_keys(value: Any, *, name: str) -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            reason = _key_is_forbidden(str(raw_key))
            if reason == "hidden_chain_of_thought":
                raise RepositoryTransferError(
                    f"{name} must not represent hidden chain-of-thought"
                )
            if reason == "private_material":
                raise RepositoryTransferError(
                    f"{name} must not contain private material"
                )
            if reason == "host_path":
                raise RepositoryTransferError(
                    f"{name} must not accept arbitrary remote host paths"
                )
            _reject_forbidden_keys(item, name=name)
        return
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray, memoryview)
    ):
        for item in value:
            _reject_forbidden_keys(item, name=name)
        return
    if isinstance(value, str) and looks_like_host_path(value):
        raise RepositoryTransferError(
            f"{name} must not accept arbitrary remote host paths"
        )


def _approved_https_url(value: Any, name: str) -> str:
    text = _text(
        value, name, max_bytes=DEFAULT_MAX_TEXT_BYTES, allow_host_path=True
    )
    if looks_like_host_path(text) and not text.lower().startswith("https://"):
        raise RepositoryTransferError(f"{name} must not be an arbitrary remote host path")
    parsed = urlparse(text)
    if parsed.scheme.lower() != "https":
        raise RepositoryTransferError(f"{name} must be an https URL")
    if parsed.username or parsed.password:
        raise RepositoryTransferError(f"{name} must not contain userinfo")
    host = (parsed.hostname or "").lower()
    if host in _LOCAL_HOSTS or _is_loopback_or_private_host(host):
        raise RepositoryTransferError(f"{name} must not be a local host path")
    if not parsed.path or parsed.path == "/":
        raise RepositoryTransferError(f"{name} must include a repository path")
    return text


def _freeze_bounded(
    value: Any,
    *,
    name: str,
    max_depth: int,
    max_items: int,
    max_text_bytes: int,
) -> Any:
    seen = 0

    def visit(item: Any, depth: int) -> Any:
        nonlocal seen
        seen += 1
        if seen > max_items:
            raise TransferBoundsError(f"{name} exceeds its item-count limit")
        if depth > max_depth:
            raise TransferBoundsError(f"{name} exceeds its nesting-depth limit")
        if item is None or isinstance(item, bool):
            return item
        if isinstance(item, int) and not isinstance(item, bool):
            return item
        if isinstance(item, float):
            raise RepositoryTransferError(f"{name} cannot contain floats")
        if isinstance(item, str):
            return _text(item, name, required=False, max_bytes=max_text_bytes)
        if isinstance(item, Enum):
            return visit(item.value, depth)
        if isinstance(item, Mapping):
            if not all(isinstance(key, str) for key in item):
                raise RepositoryTransferError(f"{name} object keys must be strings")
            frozen: dict[str, Any] = {}
            for key in sorted(item):
                normalized_key = _text(key, f"{name} key", max_bytes=max_text_bytes)
                reason = _key_is_forbidden(normalized_key)
                if reason == "hidden_chain_of_thought":
                    raise RepositoryTransferError(
                        f"{name} must not represent hidden chain-of-thought"
                    )
                if reason == "private_material":
                    raise RepositoryTransferError(
                        f"{name} must not contain private material"
                    )
                if reason == "host_path":
                    raise RepositoryTransferError(
                        f"{name} must not accept arbitrary remote host paths"
                    )
                frozen[normalized_key] = visit(item[key], depth + 1)
            return MappingProxyType(frozen)
        if isinstance(item, Sequence) and not isinstance(
            item, (str, bytes, bytearray, memoryview)
        ):
            return tuple(visit(member, depth + 1) for member in item)
        raise RepositoryTransferError(
            f"{name} contains unsupported value type {type(item).__name__}"
        )

    return visit(value, 0)


_COMMON_WIRE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "schema",
        "interface",
        "contract_version",
        "schema_version",
        "content_id",
        "cid",
        "identity",
        "canonical_id",
    }
)


def _envelope(interface: str, body: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "interface": interface,
        "contract_version": CONTRACT_VERSION,
        **dict(body),
    }


class CanonicalTransferRecord:
    """Immutable content-addressed mixin for transfer contracts."""

    SCHEMA: ClassVar[str] = ""
    INTERFACE: ClassVar[str] = ""

    def _payload(self) -> dict[str, Any]:
        raise NotImplementedError

    @property
    def schema(self) -> str:
        return self.SCHEMA

    @property
    def schema_version(self) -> int:
        return CONTRACT_VERSION

    @property
    def interface(self) -> str:
        return self.INTERFACE

    def to_dict(self) -> dict[str, Any]:
        return _canonical_value({"schema": self.SCHEMA, **self._payload()})

    def to_json(self) -> str:
        return canonical_json(self.to_dict())

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @property
    def content_id(self) -> str:
        return content_identity(self.to_dict())

    @property
    def cid(self) -> str:
        return self.content_id

    @property
    def identity(self) -> str:
        return self.content_id

    @classmethod
    def from_json(cls, payload: str) -> CanonicalTransferRecord:
        try:
            value = json.loads(payload)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RepositoryTransferError(
                "transfer contract JSON is malformed"
            ) from exc
        if not isinstance(value, Mapping):
            raise RepositoryTransferError(
                "transfer contract JSON must contain an object"
            )
        decoder = getattr(cls, "from_dict", None)
        if decoder is None:
            raise RepositoryTransferError(f"{cls.__name__} does not support from_dict")
        return decoder(value)


@dataclass(frozen=True)
class TransferPolicy(CanonicalTransferRecord):
    """Count and byte limits for one transfer attempt."""

    SCHEMA: ClassVar[str] = TRANSFER_POLICY_SCHEMA
    INTERFACE: ClassVar[str] = "TransferPolicy@1"

    max_paths: int = DEFAULT_MAX_PATHS
    max_refs: int = DEFAULT_MAX_REFS
    max_objects: int = DEFAULT_MAX_OBJECTS
    max_artifact_bytes: int = DEFAULT_MAX_ARTIFACT_BYTES
    max_text_bytes: int = DEFAULT_MAX_TEXT_BYTES
    max_record_bytes: int = DEFAULT_MAX_RECORD_BYTES
    max_depth: int = DEFAULT_MAX_DEPTH
    max_id_bytes: int = DEFAULT_MAX_ID_BYTES
    git_timeout_seconds: int = int(DEFAULT_GIT_TIMEOUT_SECONDS)
    policy_id: str = "repository-transfer@1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_paths", _positive_int(self.max_paths, "max_paths"))
        object.__setattr__(self, "max_refs", _positive_int(self.max_refs, "max_refs"))
        object.__setattr__(
            self, "max_objects", _positive_int(self.max_objects, "max_objects")
        )
        object.__setattr__(
            self,
            "max_artifact_bytes",
            _positive_int(self.max_artifact_bytes, "max_artifact_bytes"),
        )
        object.__setattr__(
            self, "max_text_bytes", _positive_int(self.max_text_bytes, "max_text_bytes")
        )
        object.__setattr__(
            self,
            "max_record_bytes",
            _positive_int(self.max_record_bytes, "max_record_bytes"),
        )
        object.__setattr__(self, "max_depth", _positive_int(self.max_depth, "max_depth"))
        object.__setattr__(
            self, "max_id_bytes", _positive_int(self.max_id_bytes, "max_id_bytes")
        )
        object.__setattr__(
            self,
            "git_timeout_seconds",
            _positive_int(self.git_timeout_seconds, "git_timeout_seconds"),
        )
        object.__setattr__(
            self,
            "policy_id",
            _text(self.policy_id, "policy_id", max_bytes=DEFAULT_MAX_ID_BYTES),
        )
        if self.max_paths > ABSOLUTE_MAX_PATHS:
            raise TransferBoundsError("max_paths exceeds the absolute limit")
        if self.max_refs > ABSOLUTE_MAX_REFS:
            raise TransferBoundsError("max_refs exceeds the absolute limit")
        if self.max_objects > ABSOLUTE_MAX_OBJECTS:
            raise TransferBoundsError("max_objects exceeds the absolute limit")
        if self.max_artifact_bytes > ABSOLUTE_MAX_ARTIFACT_BYTES:
            raise TransferBoundsError("max_artifact_bytes exceeds the absolute limit")
        if self.max_text_bytes > ABSOLUTE_MAX_TEXT_BYTES:
            raise TransferBoundsError("max_text_bytes exceeds the absolute limit")
        if self.max_record_bytes > ABSOLUTE_MAX_RECORD_BYTES:
            raise TransferBoundsError("max_record_bytes exceeds the absolute limit")
        if self.max_depth > ABSOLUTE_MAX_DEPTH:
            raise TransferBoundsError("max_depth exceeds the absolute limit")
        if self.max_id_bytes > ABSOLUTE_MAX_ID_BYTES:
            raise TransferBoundsError("max_id_bytes exceeds the absolute limit")

    def _payload(self) -> dict[str, Any]:
        return _envelope(
            self.INTERFACE,
            {
                "max_paths": self.max_paths,
                "max_refs": self.max_refs,
                "max_objects": self.max_objects,
                "max_artifact_bytes": self.max_artifact_bytes,
                "max_text_bytes": self.max_text_bytes,
                "max_record_bytes": self.max_record_bytes,
                "max_depth": self.max_depth,
                "max_id_bytes": self.max_id_bytes,
                "git_timeout_seconds": self.git_timeout_seconds,
                "policy_id": self.policy_id,
            },
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> TransferPolicy:
        if payload is None:
            return cls()
        _schema_and_version(
            payload, cls.SCHEMA, cls.INTERFACE, artifact_name="transfer policy"
        )
        _reject_unknown(
            payload,
            _COMMON_WIRE_FIELDS.union(
                {
                    "max_paths",
                    "max_refs",
                    "max_objects",
                    "max_artifact_bytes",
                    "max_text_bytes",
                    "max_record_bytes",
                    "max_depth",
                    "max_id_bytes",
                    "git_timeout_seconds",
                    "policy_id",
                }
            ),
            artifact_name="transfer policy",
        )
        defaults = cls()
        result = cls(
            max_paths=payload.get("max_paths", defaults.max_paths),
            max_refs=payload.get("max_refs", defaults.max_refs),
            max_objects=payload.get("max_objects", defaults.max_objects),
            max_artifact_bytes=payload.get(
                "max_artifact_bytes", defaults.max_artifact_bytes
            ),
            max_text_bytes=payload.get("max_text_bytes", defaults.max_text_bytes),
            max_record_bytes=payload.get("max_record_bytes", defaults.max_record_bytes),
            max_depth=payload.get("max_depth", defaults.max_depth),
            max_id_bytes=payload.get("max_id_bytes", defaults.max_id_bytes),
            git_timeout_seconds=payload.get(
                "git_timeout_seconds", defaults.git_timeout_seconds
            ),
            policy_id=payload.get("policy_id", defaults.policy_id),
        )
        _claimed_identity(
            payload,
            result.content_id,
            names=("content_id", "cid", "identity", "canonical_id"),
            artifact_name="transfer policy",
        )
        return result


def _coerce_policy(value: Any) -> TransferPolicy:
    if value is None:
        return TransferPolicy()
    if isinstance(value, TransferPolicy):
        return value
    if isinstance(value, Mapping):
        return TransferPolicy.from_dict(value)
    raise RepositoryTransferError("policy must be a TransferPolicy object")


@dataclass(frozen=True)
class SourceFileEntry(CanonicalTransferRecord):
    """One repository-relative file in a manifested source bundle."""

    SCHEMA: ClassVar[str] = "ipfs_kit_py/repository-transfer/source-file-entry@1"
    INTERFACE: ClassVar[str] = "SourceFileEntry@1"

    path: str
    digest: str
    mode: str = "100644"
    byte_count: int = 0
    symlink_target: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _relative_path(self.path, "path"))
        object.__setattr__(self, "digest", _digest_sha256(self.digest, "digest"))
        object.__setattr__(self, "mode", _file_mode(self.mode, "mode"))
        object.__setattr__(
            self, "byte_count", _nonnegative_int(self.byte_count, "byte_count")
        )
        target = _text(
            self.symlink_target,
            "symlink_target",
            required=False,
            max_bytes=DEFAULT_MAX_ID_BYTES * 4,
        )
        if self.mode == "120000":
            if not target:
                raise RepositoryTransferError(
                    "symlink_target is required for mode 120000"
                )
            target_path = PurePosixPath(target.replace("\\", "/"))
            if (
                target_path.is_absolute()
                or ".." in target_path.parts
                or looks_like_host_path(target)
            ):
                raise RepositoryTransferError(
                    "symlink_target must stay inside the repository"
                )
        elif target:
            raise RepositoryTransferError("symlink_target is only valid for mode 120000")
        object.__setattr__(self, "symlink_target", target)

    def _payload(self) -> dict[str, Any]:
        return _envelope(
            self.INTERFACE,
            {
                "path": self.path,
                "digest": self.digest,
                "mode": self.mode,
                "byte_count": self.byte_count,
                "symlink_target": self.symlink_target,
            },
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SourceFileEntry:
        _schema_and_version(
            payload, cls.SCHEMA, cls.INTERFACE, artifact_name="source file entry"
        )
        _reject_unknown(
            payload,
            _COMMON_WIRE_FIELDS.union(
                {"path", "digest", "mode", "byte_count", "symlink_target"}
            ),
            artifact_name="source file entry",
        )
        result = cls(
            path=payload.get("path", ""),
            digest=payload.get("digest", ""),
            mode=payload.get("mode", "100644"),
            byte_count=payload.get("byte_count", 0),
            symlink_target=payload.get("symlink_target", ""),
        )
        _claimed_identity(
            payload,
            result.content_id,
            names=("content_id", "cid", "identity", "canonical_id"),
            artifact_name="source file entry",
        )
        return result


def _source_file_entries(
    values: Any, *, max_paths: int
) -> tuple[SourceFileEntry, ...]:
    if values is None:
        items: Sequence[Any] = ()
    elif isinstance(values, (str, bytes, bytearray, memoryview)) or not isinstance(
        values, Sequence
    ):
        raise RepositoryTransferError("files must be a sequence")
    else:
        items = values
    if len(items) > max_paths:
        raise TransferBoundsError("files exceeds its item-count limit")
    result: list[SourceFileEntry] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, SourceFileEntry):
            entry = item
        elif isinstance(item, Mapping):
            if "schema" in item or "interface" in item:
                entry = SourceFileEntry.from_dict(item)
            else:
                entry = SourceFileEntry(
                    path=item.get("path", ""),
                    digest=item.get("digest", ""),
                    mode=item.get("mode", "100644"),
                    byte_count=item.get("byte_count", 0),
                    symlink_target=item.get("symlink_target", ""),
                )
        else:
            raise RepositoryTransferError("files entries must be objects")
        if entry.path in seen:
            raise RepositoryTransferError("files must not contain duplicate paths")
        seen.add(entry.path)
        result.append(entry)
    return tuple(sorted(result, key=lambda item: item.path))


@dataclass(frozen=True)
class SourceBundleManifest(CanonicalTransferRecord):
    """Declared file set for manifested_source_bundle transfer."""

    SCHEMA: ClassVar[str] = SOURCE_BUNDLE_MANIFEST_SCHEMA
    INTERFACE: ClassVar[str] = "SourceBundleManifest@1"

    files: tuple[SourceFileEntry, ...]
    declared_tree: str = ""
    declared_head: str = ""
    untracked: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        files = _source_file_entries(self.files, max_paths=ABSOLUTE_MAX_PATHS)
        object.__setattr__(self, "files", files)
        object.__setattr__(
            self,
            "declared_tree",
            _text(self.declared_tree, "declared_tree", required=False, max_bytes=80),
        )
        if self.declared_tree and not (
            _SHA256_RE.fullmatch(self.declared_tree)
            or _GIT_OID_RE.fullmatch(self.declared_tree)
        ):
            raise RepositoryTransferError(
                "declared_tree must be a digest or Git object id"
            )
        object.__setattr__(
            self, "declared_head", _git_oid(self.declared_head, "declared_head")
        )
        untracked = tuple(
            _relative_path(path, "untracked") for path in (self.untracked or ())
        )
        if len(set(untracked)) != len(untracked):
            raise RepositoryTransferError("untracked must not contain duplicate paths")
        object.__setattr__(self, "untracked", untracked)
        if not files:
            raise RepositoryTransferError("source bundle files must not be empty")

    def tree_identity(self) -> str:
        if self.declared_tree:
            return self.declared_tree
        return content_identity(
            {
                "schema": "ipfs_kit_py/repository-transfer/source-tree@1",
                "files": [
                    {"path": item.path, "digest": item.digest, "mode": item.mode}
                    for item in self.files
                ],
            }
        )

    def _payload(self) -> dict[str, Any]:
        return _envelope(
            self.INTERFACE,
            {
                "files": [item.to_dict() for item in self.files],
                "declared_tree": self.declared_tree,
                "declared_head": self.declared_head,
                "untracked": list(self.untracked),
            },
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SourceBundleManifest:
        _schema_and_version(
            payload, cls.SCHEMA, cls.INTERFACE, artifact_name="source bundle manifest"
        )
        _reject_unknown(
            payload,
            _COMMON_WIRE_FIELDS.union(
                {"files", "declared_tree", "declared_head", "untracked"}
            ),
            artifact_name="source bundle manifest",
        )
        result = cls(
            files=payload.get("files", ()),
            declared_tree=payload.get("declared_tree", ""),
            declared_head=payload.get("declared_head", ""),
            untracked=payload.get("untracked", ()),
        )
        _claimed_identity(
            payload,
            result.content_id,
            names=("content_id", "cid", "identity", "canonical_id"),
            artifact_name="source bundle manifest",
        )
        return result


@dataclass(frozen=True)
class OverlayEntry(CanonicalTransferRecord):
    """One dirty-overlay path."""

    SCHEMA: ClassVar[str] = "ipfs_kit_py/repository-transfer/overlay-entry@1"
    INTERFACE: ClassVar[str] = "OverlayEntry@1"

    path: str
    status: OverlayStatus
    digest: str = ""
    mode: str = ""
    symlink_target: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _relative_path(self.path, "path"))
        object.__setattr__(self, "status", _enum(self.status, OverlayStatus, "status"))
        object.__setattr__(
            self, "digest", _digest_sha256(self.digest, "digest", required=False)
        )
        mode = _text(self.mode, "mode", required=False, max_bytes=16)
        object.__setattr__(self, "mode", _file_mode(mode, "mode") if mode else "")
        target = _text(
            self.symlink_target,
            "symlink_target",
            required=False,
            max_bytes=DEFAULT_MAX_ID_BYTES * 4,
        )
        if target and looks_like_host_path(target):
            raise RepositoryTransferError(
                "symlink_target must stay inside the repository"
            )
        object.__setattr__(self, "symlink_target", target)

    def _payload(self) -> dict[str, Any]:
        return _envelope(
            self.INTERFACE,
            {
                "path": self.path,
                "status": self.status.value,
                "digest": self.digest,
                "mode": self.mode,
                "symlink_target": self.symlink_target,
            },
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> OverlayEntry:
        _schema_and_version(
            payload, cls.SCHEMA, cls.INTERFACE, artifact_name="overlay entry"
        )
        _reject_unknown(
            payload,
            _COMMON_WIRE_FIELDS.union(
                {"path", "status", "digest", "mode", "symlink_target"}
            ),
            artifact_name="overlay entry",
        )
        result = cls(
            path=payload.get("path", ""),
            status=payload.get("status", OverlayStatus.UNTRACKED),
            digest=payload.get("digest", ""),
            mode=payload.get("mode", ""),
            symlink_target=payload.get("symlink_target", ""),
        )
        _claimed_identity(
            payload,
            result.content_id,
            names=("content_id", "cid", "identity", "canonical_id"),
            artifact_name="overlay entry",
        )
        return result


def _overlay_entries(values: Any, *, max_paths: int) -> tuple[OverlayEntry, ...]:
    if values is None:
        items: Sequence[Any] = ()
    elif isinstance(values, (str, bytes, bytearray, memoryview)) or not isinstance(
        values, Sequence
    ):
        raise RepositoryTransferError("entries must be a sequence")
    else:
        items = values
    if len(items) > max_paths:
        raise TransferBoundsError("entries exceeds its item-count limit")
    result: list[OverlayEntry] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, OverlayEntry):
            entry = item
        elif isinstance(item, Mapping):
            if "schema" in item or "interface" in item:
                entry = OverlayEntry.from_dict(item)
            else:
                entry = OverlayEntry(
                    path=item.get("path", ""),
                    status=item.get("status", OverlayStatus.UNTRACKED),
                    digest=item.get("digest", ""),
                    mode=item.get("mode", ""),
                    symlink_target=item.get("symlink_target", ""),
                )
        else:
            raise RepositoryTransferError("overlay entries must be objects")
        if entry.path in seen:
            raise RepositoryTransferError(
                "overlay entries must not contain duplicate paths"
            )
        seen.add(entry.path)
        result.append(entry)
    return tuple(sorted(result, key=lambda item: item.path))


@dataclass(frozen=True)
class DirtyOverlayManifest(CanonicalTransferRecord):
    """DirtyOverlayManifest@1 — uncommitted overlay over a reconstructed tree."""

    SCHEMA: ClassVar[str] = DIRTY_OVERLAY_MANIFEST_SCHEMA
    INTERFACE: ClassVar[str] = DIRTY_OVERLAY_MANIFEST_INTERFACE

    entries: tuple[OverlayEntry, ...] = ()
    rename_policy: str = "track"
    delete_policy: str = "track"
    untracked_policy: str = "include"

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "entries", _overlay_entries(self.entries, max_paths=ABSOLUTE_MAX_PATHS)
        )
        object.__setattr__(
            self,
            "rename_policy",
            _text(self.rename_policy, "rename_policy", max_bytes=32) or "track",
        )
        object.__setattr__(
            self,
            "delete_policy",
            _text(self.delete_policy, "delete_policy", max_bytes=32) or "track",
        )
        object.__setattr__(
            self,
            "untracked_policy",
            _text(self.untracked_policy, "untracked_policy", max_bytes=32) or "include",
        )

    @property
    def overlay_digest(self) -> str:
        return self.content_id

    def _payload(self) -> dict[str, Any]:
        return _envelope(
            self.INTERFACE,
            {
                "entries": [item.to_dict() for item in self.entries],
                "rename_policy": self.rename_policy,
                "delete_policy": self.delete_policy,
                "untracked_policy": self.untracked_policy,
            },
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> DirtyOverlayManifest:
        _schema_and_version(
            payload, cls.SCHEMA, cls.INTERFACE, artifact_name="dirty overlay manifest"
        )
        _reject_unknown(
            payload,
            _COMMON_WIRE_FIELDS.union(
                {
                    "entries",
                    "rename_policy",
                    "delete_policy",
                    "untracked_policy",
                    "overlay_digest",
                    "overlay_id",
                }
            ),
            artifact_name="dirty overlay manifest",
        )
        result = cls(
            entries=payload.get("entries", ()),
            rename_policy=payload.get("rename_policy", "track"),
            delete_policy=payload.get("delete_policy", "track"),
            untracked_policy=payload.get("untracked_policy", "include"),
        )
        _claimed_identity(
            payload,
            result.content_id,
            names=(
                "content_id",
                "cid",
                "identity",
                "canonical_id",
                "overlay_digest",
                "overlay_id",
            ),
            artifact_name="dirty overlay manifest",
        )
        return result


@dataclass(frozen=True)
class ShallowBoundary(CanonicalTransferRecord):
    """Shallow clone boundary recorded with a snapshot."""

    SCHEMA: ClassVar[str] = "ipfs_kit_py/repository-transfer/shallow-boundary@1"
    INTERFACE: ClassVar[str] = "ShallowBoundary@1"

    is_shallow: bool = False
    depth: int = 0
    boundary_commits: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "is_shallow", _bool(self.is_shallow, "is_shallow"))
        object.__setattr__(self, "depth", _nonnegative_int(self.depth, "depth"))
        commits = tuple(
            _git_oid(item, "boundary_commits") for item in (self.boundary_commits or ())
        )
        commits = tuple(item for item in commits if item)
        object.__setattr__(self, "boundary_commits", commits)
        if self.is_shallow and self.depth == 0 and not commits:
            raise RepositoryTransferError("shallow repositories must declare a boundary")
        if not self.is_shallow and (self.depth or commits):
            raise RepositoryTransferError(
                "non-shallow snapshots cannot declare a boundary"
            )

    def _payload(self) -> dict[str, Any]:
        return _envelope(
            self.INTERFACE,
            {
                "is_shallow": self.is_shallow,
                "depth": self.depth,
                "boundary_commits": list(self.boundary_commits),
            },
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> ShallowBoundary:
        if payload is None:
            return cls()
        _schema_and_version(
            payload, cls.SCHEMA, cls.INTERFACE, artifact_name="shallow boundary"
        )
        _reject_unknown(
            payload,
            _COMMON_WIRE_FIELDS.union({"is_shallow", "depth", "boundary_commits"}),
            artifact_name="shallow boundary",
        )
        result = cls(
            is_shallow=payload.get("is_shallow", False),
            depth=payload.get("depth", 0),
            boundary_commits=payload.get("boundary_commits", ()),
        )
        _claimed_identity(
            payload,
            result.content_id,
            names=("content_id", "cid", "identity", "canonical_id"),
            artifact_name="shallow boundary",
        )
        return result


def _refs_map(value: Any, *, max_refs: int) -> Mapping[str, str]:
    if value is None:
        mapping: Mapping[str, Any] = {}
    elif not isinstance(value, Mapping):
        raise RepositoryTransferError("refs must be an object")
    else:
        mapping = value
    if len(mapping) > max_refs:
        raise TransferBoundsError("refs exceeds its item-count limit")
    frozen: dict[str, str] = {}
    for raw_name, raw_oid in mapping.items():
        name = _ref_name(raw_name, "refs key")
        oid = _git_oid(raw_oid, "refs value", required=True)
        frozen[name] = oid
    return MappingProxyType(dict(sorted(frozen.items())))


def _string_tuple(value: Any, name: str, *, max_items: int) -> tuple[str, ...]:
    if value is None:
        items: Sequence[Any] = ()
    elif isinstance(value, (str, bytes, bytearray, memoryview)) or not isinstance(
        value, Sequence
    ):
        raise RepositoryTransferError(f"{name} must be a sequence of strings")
    else:
        items = value
    if len(items) > max_items:
        raise TransferBoundsError(f"{name} exceeds its item-count limit")
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _text(item, name, max_bytes=DEFAULT_MAX_ID_BYTES * 4)
        if text in seen:
            raise RepositoryTransferError(f"{name} must not contain duplicates")
        seen.add(text)
        result.append(text)
    return tuple(result)


def _sparse_pathspecs(value: Any, *, max_items: int) -> tuple[str, ...]:
    if value is None:
        items: Sequence[Any] = ()
    elif isinstance(value, (str, bytes, bytearray, memoryview)) or not isinstance(
        value, Sequence
    ):
        raise RepositoryTransferError("sparse_checkout must be a sequence of pathspecs")
    else:
        items = value
    if len(items) > max_items:
        raise TransferBoundsError("sparse_checkout exceeds its item-count limit")
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, str):
            raise RepositoryTransferError("sparse_checkout entries must be strings")
        text = item.strip()
        if not text or "\x00" in text:
            raise RepositoryTransferError("sparse_checkout is invalid")
        if "://" in text or text.startswith("~") or ".." in PurePosixPath(text.lstrip("/")).parts:
            raise RepositoryTransferError("sparse_checkout must not contain host paths")
        if text in seen:
            raise RepositoryTransferError("sparse_checkout must not contain duplicates")
        seen.add(text)
        result.append(text)
    return tuple(result)


@dataclass(frozen=True)
class SubmoduleRecord(CanonicalTransferRecord):
    """Declared submodule bound to an alias rather than a host path."""

    SCHEMA: ClassVar[str] = "ipfs_kit_py/repository-transfer/submodule-record@1"
    INTERFACE: ClassVar[str] = "SubmoduleRecord@1"

    path: str
    commit: str
    origin_alias: str = ""
    gitlink_mode: str = "160000"

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _relative_path(self.path, "path"))
        object.__setattr__(self, "commit", _git_oid(self.commit, "commit", required=True))
        alias = _text(
            self.origin_alias,
            "origin_alias",
            required=False,
            max_bytes=ABSOLUTE_MAX_ALIAS_BYTES,
        )
        if alias:
            alias = _alias_name(alias, "origin_alias")
        object.__setattr__(self, "origin_alias", alias)
        object.__setattr__(
            self, "gitlink_mode", _file_mode(self.gitlink_mode, "gitlink_mode")
        )
        if self.gitlink_mode != "160000":
            raise RepositoryTransferError("submodule gitlink_mode must be 160000")

    def _payload(self) -> dict[str, Any]:
        return _envelope(
            self.INTERFACE,
            {
                "path": self.path,
                "commit": self.commit,
                "origin_alias": self.origin_alias,
                "gitlink_mode": self.gitlink_mode,
            },
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SubmoduleRecord:
        _schema_and_version(
            payload, cls.SCHEMA, cls.INTERFACE, artifact_name="submodule record"
        )
        _reject_unknown(
            payload,
            _COMMON_WIRE_FIELDS.union(
                {"path", "commit", "origin_alias", "gitlink_mode", "url"}
            ),
            artifact_name="submodule record",
        )
        if payload.get("url"):
            raise RepositoryTransferError(
                "submodule record must not contain a host URL; use origin_alias"
            )
        result = cls(
            path=payload.get("path", ""),
            commit=payload.get("commit", ""),
            origin_alias=payload.get("origin_alias", ""),
            gitlink_mode=payload.get("gitlink_mode", "160000"),
        )
        _claimed_identity(
            payload,
            result.content_id,
            names=("content_id", "cid", "identity", "canonical_id"),
            artifact_name="submodule record",
        )
        return result


def _submodules(value: Any, *, max_items: int) -> tuple[SubmoduleRecord, ...]:
    if value is None:
        items: Sequence[Any] = ()
    elif isinstance(value, (str, bytes, bytearray, memoryview)) or not isinstance(
        value, Sequence
    ):
        raise RepositoryTransferError("submodules must be a sequence")
    else:
        items = value
    if len(items) > max_items:
        raise TransferBoundsError("submodules exceeds its item-count limit")
    result: list[SubmoduleRecord] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, SubmoduleRecord):
            record = item
        elif isinstance(item, Mapping):
            if "schema" in item or "interface" in item:
                record = SubmoduleRecord.from_dict(item)
            else:
                record = SubmoduleRecord(
                    path=item.get("path", ""),
                    commit=item.get("commit", ""),
                    origin_alias=item.get("origin_alias", ""),
                    gitlink_mode=item.get("gitlink_mode", "160000"),
                )
        else:
            raise RepositoryTransferError("submodules entries must be objects")
        if record.path in seen:
            raise RepositoryTransferError("submodules must not contain duplicate paths")
        seen.add(record.path)
        result.append(record)
    return tuple(sorted(result, key=lambda item: item.path))


def _tree_token(value: Any, name: str) -> str:
    text = _text(value, name, required=False, max_bytes=80)
    if text and not (_SHA256_RE.fullmatch(text) or _GIT_OID_RE.fullmatch(text)):
        raise RepositoryTransferError(f"{name} must be a digest or Git object id")
    return text


@dataclass(frozen=True)
class RepositorySnapshotManifest(CanonicalTransferRecord):
    """RepositorySnapshotManifest@1 — reconstructed HEAD/refs/index/worktree state."""

    SCHEMA: ClassVar[str] = REPOSITORY_SNAPSHOT_MANIFEST_SCHEMA
    INTERFACE: ClassVar[str] = REPOSITORY_SNAPSHOT_MANIFEST_INTERFACE

    head_commit: str = ""
    head_ref: str = ""
    head_tree: str = ""
    index_tree: str = ""
    worktree_tree: str = ""
    refs: Mapping[str, str] = MappingProxyType({})
    untracked: tuple[str, ...] = ()
    submodules: tuple[SubmoduleRecord, ...] = ()
    nested_repos: tuple[str, ...] = ()
    lfs_pointers: tuple[str, ...] = ()
    sparse_checkout: tuple[str, ...] = ()
    hooks_present: bool = False
    hooks_disabled: bool = True
    attributes: tuple[str, ...] = ()
    executable_paths: tuple[str, ...] = ()
    origin_alias: str = ""
    shallow: ShallowBoundary = ShallowBoundary()
    object_count: int = 0
    byte_count: int = 0
    is_git_repository: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "head_commit", _git_oid(self.head_commit, "head_commit"))
        head_ref = _text(
            self.head_ref, "head_ref", required=False, max_bytes=DEFAULT_MAX_ID_BYTES
        )
        if head_ref:
            head_ref = _ref_name(head_ref, "head_ref")
        object.__setattr__(self, "head_ref", head_ref)
        object.__setattr__(self, "head_tree", _tree_token(self.head_tree, "head_tree"))
        object.__setattr__(self, "index_tree", _tree_token(self.index_tree, "index_tree"))
        object.__setattr__(
            self, "worktree_tree", _tree_token(self.worktree_tree, "worktree_tree")
        )
        object.__setattr__(self, "refs", _refs_map(self.refs, max_refs=ABSOLUTE_MAX_REFS))
        object.__setattr__(
            self,
            "untracked",
            tuple(_relative_path(path, "untracked") for path in (self.untracked or ())),
        )
        object.__setattr__(
            self, "submodules", _submodules(self.submodules, max_items=ABSOLUTE_MAX_PATHS)
        )
        object.__setattr__(
            self,
            "nested_repos",
            tuple(
                _relative_path(path, "nested_repos") for path in (self.nested_repos or ())
            ),
        )
        object.__setattr__(
            self,
            "lfs_pointers",
            tuple(
                _relative_path(path, "lfs_pointers") for path in (self.lfs_pointers or ())
            ),
        )
        object.__setattr__(
            self,
            "sparse_checkout",
            _sparse_pathspecs(self.sparse_checkout, max_items=ABSOLUTE_MAX_PATHS),
        )
        object.__setattr__(self, "hooks_present", _bool(self.hooks_present, "hooks_present"))
        object.__setattr__(
            self, "hooks_disabled", _bool(self.hooks_disabled, "hooks_disabled")
        )
        object.__setattr__(
            self,
            "attributes",
            _string_tuple(self.attributes, "attributes", max_items=ABSOLUTE_MAX_PATHS),
        )
        object.__setattr__(
            self,
            "executable_paths",
            tuple(
                _relative_path(path, "executable_paths")
                for path in (self.executable_paths or ())
            ),
        )
        origin = _text(
            self.origin_alias,
            "origin_alias",
            required=False,
            max_bytes=ABSOLUTE_MAX_ALIAS_BYTES,
        )
        if origin:
            origin = _alias_name(origin, "origin_alias")
        object.__setattr__(self, "origin_alias", origin)
        shallow = self.shallow
        if isinstance(shallow, Mapping):
            shallow = ShallowBoundary.from_dict(shallow)
        elif shallow is None:
            shallow = ShallowBoundary()
        elif not isinstance(shallow, ShallowBoundary):
            raise RepositoryTransferError("shallow must be a ShallowBoundary object")
        object.__setattr__(self, "shallow", shallow)
        object.__setattr__(
            self, "object_count", _nonnegative_int(self.object_count, "object_count")
        )
        object.__setattr__(
            self, "byte_count", _nonnegative_int(self.byte_count, "byte_count")
        )
        object.__setattr__(
            self, "is_git_repository", _bool(self.is_git_repository, "is_git_repository")
        )
        if self.hooks_present and not self.hooks_disabled:
            raise RepositoryTransferError("reconstructed hooks must be disabled")
        if not self.head_tree:
            raise RepositoryTransferError("head_tree is required")

    def _payload(self) -> dict[str, Any]:
        return _envelope(
            self.INTERFACE,
            {
                "head_commit": self.head_commit,
                "head_ref": self.head_ref,
                "head_tree": self.head_tree,
                "index_tree": self.index_tree,
                "worktree_tree": self.worktree_tree,
                "refs": dict(self.refs),
                "untracked": list(self.untracked),
                "submodules": [item.to_dict() for item in self.submodules],
                "nested_repos": list(self.nested_repos),
                "lfs_pointers": list(self.lfs_pointers),
                "sparse_checkout": list(self.sparse_checkout),
                "hooks_present": self.hooks_present,
                "hooks_disabled": self.hooks_disabled,
                "attributes": list(self.attributes),
                "executable_paths": list(self.executable_paths),
                "origin_alias": self.origin_alias,
                "shallow": self.shallow.to_dict(),
                "object_count": self.object_count,
                "byte_count": self.byte_count,
                "is_git_repository": self.is_git_repository,
            },
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RepositorySnapshotManifest:
        _schema_and_version(
            payload,
            cls.SCHEMA,
            cls.INTERFACE,
            artifact_name="repository snapshot manifest",
        )
        _reject_unknown(
            payload,
            _COMMON_WIRE_FIELDS.union(
                {
                    "head_commit",
                    "head_ref",
                    "head_tree",
                    "index_tree",
                    "worktree_tree",
                    "refs",
                    "untracked",
                    "submodules",
                    "nested_repos",
                    "lfs_pointers",
                    "sparse_checkout",
                    "hooks_present",
                    "hooks_disabled",
                    "attributes",
                    "executable_paths",
                    "origin_alias",
                    "origin",
                    "shallow",
                    "object_count",
                    "byte_count",
                    "is_git_repository",
                }
            ),
            artifact_name="repository snapshot manifest",
        )
        if payload.get("origin"):
            raise RepositoryTransferError(
                "snapshot must not contain an origin host path; use origin_alias"
            )
        result = cls(
            head_commit=payload.get("head_commit", ""),
            head_ref=payload.get("head_ref", ""),
            head_tree=payload.get("head_tree", ""),
            index_tree=payload.get("index_tree", ""),
            worktree_tree=payload.get("worktree_tree", ""),
            refs=payload.get("refs", {}),
            untracked=payload.get("untracked", ()),
            submodules=payload.get("submodules", ()),
            nested_repos=payload.get("nested_repos", ()),
            lfs_pointers=payload.get("lfs_pointers", ()),
            sparse_checkout=payload.get("sparse_checkout", ()),
            hooks_present=payload.get("hooks_present", False),
            hooks_disabled=payload.get("hooks_disabled", True),
            attributes=payload.get("attributes", ()),
            executable_paths=payload.get("executable_paths", ()),
            origin_alias=payload.get("origin_alias", ""),
            shallow=payload.get("shallow"),
            object_count=payload.get("object_count", 0),
            byte_count=payload.get("byte_count", 0),
            is_git_repository=payload.get("is_git_repository", False),
        )
        _claimed_identity(
            payload,
            result.content_id,
            names=("content_id", "cid", "identity", "canonical_id"),
            artifact_name="repository snapshot manifest",
        )
        return result


@dataclass(frozen=True)
class ManagedAlias(CanonicalTransferRecord):
    """Operator-configured alias bound to a staged concrete artifact."""

    SCHEMA: ClassVar[str] = MANAGED_ALIAS_SCHEMA
    INTERFACE: ClassVar[str] = "ManagedAlias@1"

    name: str
    artifact_kind: ArtifactKind
    artifact_id: str
    declared_head: str = ""
    declared_tree: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _alias_name(self.name, "name"))
        object.__setattr__(
            self, "artifact_kind", _enum(self.artifact_kind, ArtifactKind, "artifact_kind")
        )
        object.__setattr__(
            self, "artifact_id", _digest_sha256(self.artifact_id, "artifact_id")
        )
        object.__setattr__(
            self, "declared_head", _git_oid(self.declared_head, "declared_head")
        )
        object.__setattr__(
            self, "declared_tree", _tree_token(self.declared_tree, "declared_tree")
        )

    def _payload(self) -> dict[str, Any]:
        return _envelope(
            self.INTERFACE,
            {
                "name": self.name,
                "artifact_kind": self.artifact_kind.value,
                "artifact_id": self.artifact_id,
                "declared_head": self.declared_head,
                "declared_tree": self.declared_tree,
            },
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ManagedAlias:
        _schema_and_version(
            payload, cls.SCHEMA, cls.INTERFACE, artifact_name="managed alias"
        )
        _reject_unknown(
            payload,
            _COMMON_WIRE_FIELDS.union(
                {
                    "name",
                    "artifact_kind",
                    "artifact_id",
                    "declared_head",
                    "declared_tree",
                    "path",
                    "url",
                }
            ),
            artifact_name="managed alias",
        )
        if payload.get("path") or payload.get("url"):
            raise RepositoryTransferError(
                "managed alias must not contain a host path or remote URL"
            )
        result = cls(
            name=payload.get("name", ""),
            artifact_kind=payload.get("artifact_kind", ArtifactKind.GIT_BUNDLE),
            artifact_id=payload.get("artifact_id", ""),
            declared_head=payload.get("declared_head", ""),
            declared_tree=payload.get("declared_tree", ""),
        )
        _claimed_identity(
            payload,
            result.content_id,
            names=("content_id", "cid", "identity", "canonical_id"),
            artifact_name="managed alias",
        )
        return result


@dataclass(frozen=True)
class ApprovedRemoteAlias(CanonicalTransferRecord):
    """Operator-approved remote named only by alias, staged as an artifact."""

    SCHEMA: ClassVar[str] = APPROVED_REMOTE_ALIAS_SCHEMA
    INTERFACE: ClassVar[str] = "ApprovedRemoteAlias@1"

    name: str
    approved_url: str
    artifact_kind: ArtifactKind
    artifact_id: str
    declared_head: str = ""
    declared_tree: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _alias_name(self.name, "name"))
        object.__setattr__(
            self, "approved_url", _approved_https_url(self.approved_url, "approved_url")
        )
        kind = _enum(self.artifact_kind, ArtifactKind, "artifact_kind")
        if kind is ArtifactKind.SOURCE_BUNDLE:
            raise RepositoryTransferError(
                "approved remotes must resolve to a Git bundle or object set"
            )
        object.__setattr__(self, "artifact_kind", kind)
        object.__setattr__(
            self, "artifact_id", _digest_sha256(self.artifact_id, "artifact_id")
        )
        object.__setattr__(
            self, "declared_head", _git_oid(self.declared_head, "declared_head")
        )
        object.__setattr__(
            self, "declared_tree", _tree_token(self.declared_tree, "declared_tree")
        )

    def _payload(self) -> dict[str, Any]:
        return _envelope(
            self.INTERFACE,
            {
                "name": self.name,
                "approved_url": self.approved_url,
                "artifact_kind": self.artifact_kind.value,
                "artifact_id": self.artifact_id,
                "declared_head": self.declared_head,
                "declared_tree": self.declared_tree,
            },
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ApprovedRemoteAlias:
        _schema_and_version(
            payload, cls.SCHEMA, cls.INTERFACE, artifact_name="approved remote alias"
        )
        _reject_unknown(
            payload,
            _COMMON_WIRE_FIELDS.union(
                {
                    "name",
                    "approved_url",
                    "artifact_kind",
                    "artifact_id",
                    "declared_head",
                    "declared_tree",
                    "path",
                    "url",
                }
            ),
            artifact_name="approved remote alias",
        )
        if payload.get("path"):
            raise RepositoryTransferError(
                "approved remote alias must not contain a host path"
            )
        result = cls(
            name=payload.get("name", ""),
            approved_url=payload.get("approved_url") or payload.get("url") or "",
            artifact_kind=payload.get("artifact_kind", ArtifactKind.GIT_BUNDLE),
            artifact_id=payload.get("artifact_id", ""),
            declared_head=payload.get("declared_head", ""),
            declared_tree=payload.get("declared_tree", ""),
        )
        _claimed_identity(
            payload,
            result.content_id,
            names=("content_id", "cid", "identity", "canonical_id"),
            artifact_name="approved remote alias",
        )
        return result


@dataclass(frozen=True)
class TransferLocator(CanonicalTransferRecord):
    """Mode-specific locator that never carries a host path."""

    SCHEMA: ClassVar[str] = "ipfs_kit_py/repository-transfer/locator@1"
    INTERFACE: ClassVar[str] = "TransferLocator@1"

    mode: RepositoryTransferMode
    alias: str = ""
    artifact_id: str = ""
    manifest_id: str = ""
    head_ref: str = ""
    declared_head: str = ""
    declared_tree: str = ""
    object_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", _enum(self.mode, RepositoryTransferMode, "mode"))
        alias = _text(self.alias, "alias", required=False, max_bytes=ABSOLUTE_MAX_ALIAS_BYTES)
        if alias:
            alias = _alias_name(alias, "alias")
        object.__setattr__(self, "alias", alias)
        object.__setattr__(
            self,
            "artifact_id",
            _digest_sha256(self.artifact_id, "artifact_id", required=False),
        )
        object.__setattr__(
            self,
            "manifest_id",
            _digest_sha256(self.manifest_id, "manifest_id", required=False),
        )
        head_ref = _text(
            self.head_ref, "head_ref", required=False, max_bytes=DEFAULT_MAX_ID_BYTES
        )
        if head_ref:
            head_ref = _ref_name(head_ref, "head_ref")
        object.__setattr__(self, "head_ref", head_ref)
        object.__setattr__(
            self, "declared_head", _git_oid(self.declared_head, "declared_head")
        )
        object.__setattr__(
            self, "declared_tree", _tree_token(self.declared_tree, "declared_tree")
        )
        object.__setattr__(
            self, "object_count", _nonnegative_int(self.object_count, "object_count")
        )
        if self.mode.is_alias:
            if not self.alias:
                raise RepositoryTransferError("alias locators require an alias token")
            if self.artifact_id or self.manifest_id:
                raise RepositoryTransferError(
                    "alias locators must not embed artifact identities"
                )
        elif self.mode is RepositoryTransferMode.MANIFESTED_SOURCE_BUNDLE:
            if not self.manifest_id and not self.artifact_id:
                raise RepositoryTransferError(
                    "manifested source bundles require a manifest identity"
                )
        elif not self.artifact_id:
            raise RepositoryTransferError("artifact locators require artifact_id")

    def _payload(self) -> dict[str, Any]:
        return _envelope(
            self.INTERFACE,
            {
                "mode": self.mode.value,
                "alias": self.alias,
                "artifact_id": self.artifact_id,
                "manifest_id": self.manifest_id,
                "head_ref": self.head_ref,
                "declared_head": self.declared_head,
                "declared_tree": self.declared_tree,
                "object_count": self.object_count,
            },
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> TransferLocator:
        _schema_and_version(
            payload, cls.SCHEMA, cls.INTERFACE, artifact_name="transfer locator"
        )
        _reject_unknown(
            payload,
            _COMMON_WIRE_FIELDS.union(
                {
                    "mode",
                    "alias",
                    "artifact_id",
                    "manifest_id",
                    "head_ref",
                    "declared_head",
                    "declared_tree",
                    "object_count",
                    "path",
                    "url",
                    "remote",
                    "host_path",
                }
            ),
            artifact_name="transfer locator",
        )
        for banned in ("path", "url", "remote", "host_path"):
            if payload.get(banned):
                raise RepositoryTransferError(
                    "locator must not accept arbitrary remote host paths"
                )
        result = cls(
            mode=payload.get("mode", ""),
            alias=payload.get("alias", ""),
            artifact_id=payload.get("artifact_id", ""),
            manifest_id=payload.get("manifest_id", ""),
            head_ref=payload.get("head_ref", ""),
            declared_head=payload.get("declared_head", ""),
            declared_tree=payload.get("declared_tree", ""),
            object_count=payload.get("object_count", 0),
        )
        _claimed_identity(
            payload,
            result.content_id,
            names=("content_id", "cid", "identity", "canonical_id"),
            artifact_name="transfer locator",
        )
        return result


def locator_from_mapping(mode: RepositoryTransferMode, raw: Any) -> TransferLocator:
    """Build a locator from a caller mapping after host-path rejection."""

    if isinstance(raw, TransferLocator):
        if raw.mode is not mode:
            raise RepositoryTransferError("locator mode does not match request mode")
        return raw
    if raw is None:
        raise RepositoryTransferError("locator is required")
    if isinstance(raw, str):
        if looks_like_host_path(raw):
            raise RepositoryTransferError(
                "locator must not accept arbitrary remote host paths"
            )
        if mode.is_alias:
            return TransferLocator(mode=mode, alias=raw)
        return TransferLocator(mode=mode, artifact_id=raw)
    if not isinstance(raw, Mapping):
        raise RepositoryTransferError("locator must be an object")
    _reject_forbidden_keys(raw, name="locator")
    payload = dict(raw)
    payload.setdefault("mode", mode.value)
    if "schema" in payload or "interface" in payload:
        return TransferLocator.from_dict(payload)
    return TransferLocator(
        mode=payload.get("mode", mode),
        alias=payload.get("alias", ""),
        artifact_id=payload.get("artifact_id", ""),
        manifest_id=payload.get("manifest_id", ""),
        head_ref=payload.get("head_ref", ""),
        declared_head=payload.get("declared_head", ""),
        declared_tree=payload.get("declared_tree", ""),
        object_count=payload.get("object_count", 0),
    )


@dataclass(frozen=True)
class RepositoryTransferRequest(CanonicalTransferRecord):
    """Caller request naming one closed transfer mode and locator."""

    SCHEMA: ClassVar[str] = REPOSITORY_TRANSFER_REQUEST_SCHEMA
    INTERFACE: ClassVar[str] = "RepositoryTransferRequest@1"

    mode: RepositoryTransferMode
    locator: TransferLocator
    idempotency_key: str
    declared_head: str = ""
    declared_tree: str = ""
    origin_alias: str = ""
    overlay_entries: tuple[OverlayEntry, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", _enum(self.mode, RepositoryTransferMode, "mode"))
        locator = locator_from_mapping(self.mode, self.locator)
        if locator.mode is not self.mode:
            raise RepositoryTransferError("locator mode must match request mode")
        object.__setattr__(self, "locator", locator)
        object.__setattr__(
            self,
            "idempotency_key",
            _text(self.idempotency_key, "idempotency_key", max_bytes=DEFAULT_MAX_ID_BYTES),
        )
        object.__setattr__(
            self, "declared_head", _git_oid(self.declared_head, "declared_head")
        )
        object.__setattr__(
            self, "declared_tree", _tree_token(self.declared_tree, "declared_tree")
        )
        origin = _text(
            self.origin_alias,
            "origin_alias",
            required=False,
            max_bytes=ABSOLUTE_MAX_ALIAS_BYTES,
        )
        if origin:
            origin = _alias_name(origin, "origin_alias")
        object.__setattr__(self, "origin_alias", origin)
        object.__setattr__(
            self,
            "overlay_entries",
            _overlay_entries(self.overlay_entries, max_paths=ABSOLUTE_MAX_PATHS),
        )

    def _payload(self) -> dict[str, Any]:
        return _envelope(
            self.INTERFACE,
            {
                "mode": self.mode.value,
                "locator": self.locator.to_dict(),
                "idempotency_key": self.idempotency_key,
                "declared_head": self.declared_head,
                "declared_tree": self.declared_tree,
                "origin_alias": self.origin_alias,
                "overlay_entries": [item.to_dict() for item in self.overlay_entries],
            },
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RepositoryTransferRequest:
        _schema_and_version(
            payload,
            cls.SCHEMA,
            cls.INTERFACE,
            artifact_name="repository transfer request",
        )
        _reject_unknown(
            payload,
            _COMMON_WIRE_FIELDS.union(
                {
                    "mode",
                    "locator",
                    "idempotency_key",
                    "declared_head",
                    "declared_tree",
                    "origin_alias",
                    "overlay_entries",
                    "path",
                    "url",
                }
            ),
            artifact_name="repository transfer request",
        )
        if payload.get("path") or payload.get("url"):
            raise RepositoryTransferError(
                "transfer request must not accept arbitrary remote host paths"
            )
        result = cls(
            mode=payload.get("mode", ""),
            locator=payload.get("locator"),
            idempotency_key=payload.get("idempotency_key", ""),
            declared_head=payload.get("declared_head", ""),
            declared_tree=payload.get("declared_tree", ""),
            origin_alias=payload.get("origin_alias", ""),
            overlay_entries=payload.get("overlay_entries", ()),
        )
        _claimed_identity(
            payload,
            result.content_id,
            names=("content_id", "cid", "identity", "canonical_id"),
            artifact_name="repository transfer request",
        )
        return result


@dataclass(frozen=True)
class RepositoryHandoffBundle(CanonicalTransferRecord):
    """RepositoryHandoffBundle@1 — admitted reconstruction identities."""

    SCHEMA: ClassVar[str] = REPOSITORY_HANDOFF_BUNDLE_SCHEMA
    INTERFACE: ClassVar[str] = REPOSITORY_HANDOFF_BUNDLE_INTERFACE

    mode: RepositoryTransferMode
    locator: TransferLocator
    snapshot_id: str
    overlay_id: str
    reconstructed_tree_id: str
    artifact_ids: tuple[str, ...] = ()
    origin_alias: str = ""
    quarantine_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", _enum(self.mode, RepositoryTransferMode, "mode"))
        object.__setattr__(self, "locator", locator_from_mapping(self.mode, self.locator))
        object.__setattr__(
            self, "snapshot_id", _digest_sha256(self.snapshot_id, "snapshot_id")
        )
        object.__setattr__(
            self, "overlay_id", _digest_sha256(self.overlay_id, "overlay_id")
        )
        object.__setattr__(
            self,
            "reconstructed_tree_id",
            _tree_token(self.reconstructed_tree_id, "reconstructed_tree_id"),
        )
        if not self.reconstructed_tree_id:
            raise RepositoryTransferError("reconstructed_tree_id is required")
        ids = tuple(
            _digest_sha256(item, "artifact_ids") for item in (self.artifact_ids or ())
        )
        if len(set(ids)) != len(ids):
            raise RepositoryTransferError("artifact_ids must not contain duplicates")
        object.__setattr__(self, "artifact_ids", ids)
        origin = _text(
            self.origin_alias,
            "origin_alias",
            required=False,
            max_bytes=ABSOLUTE_MAX_ALIAS_BYTES,
        )
        if origin:
            origin = _alias_name(origin, "origin_alias")
        object.__setattr__(self, "origin_alias", origin)
        object.__setattr__(
            self,
            "quarantine_id",
            _digest_sha256(self.quarantine_id, "quarantine_id", required=False),
        )

    def _payload(self) -> dict[str, Any]:
        return _envelope(
            self.INTERFACE,
            {
                "mode": self.mode.value,
                "locator": self.locator.to_dict(),
                "snapshot_id": self.snapshot_id,
                "overlay_id": self.overlay_id,
                "reconstructed_tree_id": self.reconstructed_tree_id,
                "artifact_ids": list(self.artifact_ids),
                "origin_alias": self.origin_alias,
                "quarantine_id": self.quarantine_id,
            },
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RepositoryHandoffBundle:
        _schema_and_version(
            payload, cls.SCHEMA, cls.INTERFACE, artifact_name="repository handoff bundle"
        )
        _reject_unknown(
            payload,
            _COMMON_WIRE_FIELDS.union(
                {
                    "mode",
                    "locator",
                    "snapshot_id",
                    "overlay_id",
                    "reconstructed_tree_id",
                    "artifact_ids",
                    "origin_alias",
                    "quarantine_id",
                    "path",
                }
            ),
            artifact_name="repository handoff bundle",
        )
        if payload.get("path"):
            raise RepositoryTransferError("bundle must not contain a host path")
        result = cls(
            mode=payload.get("mode", ""),
            locator=payload.get("locator"),
            snapshot_id=payload.get("snapshot_id", ""),
            overlay_id=payload.get("overlay_id", ""),
            reconstructed_tree_id=payload.get("reconstructed_tree_id", ""),
            artifact_ids=payload.get("artifact_ids", ()),
            origin_alias=payload.get("origin_alias", ""),
            quarantine_id=payload.get("quarantine_id", ""),
        )
        _claimed_identity(
            payload,
            result.content_id,
            names=("content_id", "cid", "identity", "canonical_id"),
            artifact_name="repository handoff bundle",
        )
        return result


@dataclass(frozen=True)
class RepositoryTransferReceipt(CanonicalTransferRecord):
    """RepositoryTransferReceipt@1 — admitted reconstruction or typed refusal."""

    SCHEMA: ClassVar[str] = REPOSITORY_TRANSFER_RECEIPT_SCHEMA
    INTERFACE: ClassVar[str] = REPOSITORY_TRANSFER_RECEIPT_INTERFACE

    request_id: str
    verdict: TransferVerdict
    mode: RepositoryTransferMode
    policy_id: str
    reason_code: str = ""
    bundle_id: str = ""
    snapshot_id: str = ""
    overlay_id: str = ""
    reconstructed_tree_id: str = ""
    user_checkout_mutated: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _digest_sha256(self.request_id, "request_id")
        )
        object.__setattr__(self, "verdict", _enum(self.verdict, TransferVerdict, "verdict"))
        object.__setattr__(self, "mode", _enum(self.mode, RepositoryTransferMode, "mode"))
        object.__setattr__(
            self,
            "policy_id",
            _text(self.policy_id, "policy_id", max_bytes=DEFAULT_MAX_ID_BYTES),
        )
        reason = _text(
            self.reason_code,
            "reason_code",
            required=False,
            max_bytes=ABSOLUTE_MAX_REASON_BYTES,
        )
        if reason:
            reason = _enum(reason, TransferRefusal, "reason_code").value
        object.__setattr__(self, "reason_code", reason)
        object.__setattr__(
            self, "bundle_id", _digest_sha256(self.bundle_id, "bundle_id", required=False)
        )
        object.__setattr__(
            self,
            "snapshot_id",
            _digest_sha256(self.snapshot_id, "snapshot_id", required=False),
        )
        object.__setattr__(
            self, "overlay_id", _digest_sha256(self.overlay_id, "overlay_id", required=False)
        )
        object.__setattr__(
            self,
            "reconstructed_tree_id",
            _tree_token(self.reconstructed_tree_id, "reconstructed_tree_id"),
        )
        object.__setattr__(
            self,
            "user_checkout_mutated",
            _bool(self.user_checkout_mutated, "user_checkout_mutated"),
        )
        if self.user_checkout_mutated:
            raise TransferTrustError("transfer must not mutate a user checkout")
        if self.verdict is TransferVerdict.ADMITTED:
            if reason:
                raise RepositoryTransferError("admitted receipts cannot carry a refusal")
            if not (self.bundle_id and self.snapshot_id and self.reconstructed_tree_id):
                raise RepositoryTransferError(
                    "admitted receipts must bind bundle, snapshot and tree identities"
                )
        else:
            if not reason:
                raise RepositoryTransferError("refused receipts require a typed reason")
            if self.bundle_id or self.snapshot_id or self.reconstructed_tree_id:
                raise RepositoryTransferError(
                    "refused receipts must not claim reconstruction identities"
                )

    @property
    def reconstructed(self) -> bool:
        return self.verdict is TransferVerdict.ADMITTED

    def _payload(self) -> dict[str, Any]:
        return _envelope(
            self.INTERFACE,
            {
                "request_id": self.request_id,
                "verdict": self.verdict.value,
                "mode": self.mode.value,
                "policy_id": self.policy_id,
                "reason_code": self.reason_code,
                "bundle_id": self.bundle_id,
                "snapshot_id": self.snapshot_id,
                "overlay_id": self.overlay_id,
                "reconstructed_tree_id": self.reconstructed_tree_id,
                "user_checkout_mutated": self.user_checkout_mutated,
            },
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RepositoryTransferReceipt:
        _schema_and_version(
            payload,
            cls.SCHEMA,
            cls.INTERFACE,
            artifact_name="repository transfer receipt",
        )
        _reject_unknown(
            payload,
            _COMMON_WIRE_FIELDS.union(
                {
                    "request_id",
                    "verdict",
                    "mode",
                    "policy_id",
                    "reason_code",
                    "bundle_id",
                    "snapshot_id",
                    "overlay_id",
                    "reconstructed_tree_id",
                    "user_checkout_mutated",
                }
            ),
            artifact_name="repository transfer receipt",
        )
        result = cls(
            request_id=payload.get("request_id", ""),
            verdict=payload.get("verdict", ""),
            mode=payload.get("mode", ""),
            policy_id=payload.get("policy_id", ""),
            reason_code=payload.get("reason_code", ""),
            bundle_id=payload.get("bundle_id", ""),
            snapshot_id=payload.get("snapshot_id", ""),
            overlay_id=payload.get("overlay_id", ""),
            reconstructed_tree_id=payload.get("reconstructed_tree_id", ""),
            user_checkout_mutated=payload.get("user_checkout_mutated", False),
        )
        _claimed_identity(
            payload,
            result.content_id,
            names=("content_id", "cid", "identity", "canonical_id"),
            artifact_name="repository transfer receipt",
        )
        return result


@dataclass(frozen=True)
class RepositoryTransferResult:
    """Transfer outcome: typed receipt plus optional reconstructed records."""

    receipt: RepositoryTransferReceipt
    bundle: RepositoryHandoffBundle | None = None
    snapshot: RepositorySnapshotManifest | None = None
    overlay: DirtyOverlayManifest | None = None
    repository_root: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.receipt, RepositoryTransferReceipt):
            raise RepositoryTransferError("receipt is required")
        if self.receipt.verdict is TransferVerdict.ADMITTED:
            if self.bundle is None or self.snapshot is None or self.overlay is None:
                raise RepositoryTransferError(
                    "admitted results must include bundle, snapshot and overlay"
                )
            if self.bundle.content_id != self.receipt.bundle_id:
                raise TransferIdentityError("bundle identity does not match receipt")
            if self.snapshot.content_id != self.receipt.snapshot_id:
                raise TransferIdentityError("snapshot identity does not match receipt")
            if self.overlay.content_id != self.receipt.overlay_id:
                raise TransferIdentityError("overlay identity does not match receipt")
        elif self.bundle is not None or self.snapshot is not None:
            raise RepositoryTransferError("refused results must not include a bundle")
        if self.repository_root and looks_like_host_path(self.repository_root):
            object.__setattr__(self, "repository_root", "")

    @property
    def admitted(self) -> bool:
        return self.receipt.verdict is TransferVerdict.ADMITTED


_DECODERS: Final[Mapping[str, type[CanonicalTransferRecord]]] = MappingProxyType(
    {
        REPOSITORY_HANDOFF_BUNDLE_SCHEMA: RepositoryHandoffBundle,
        REPOSITORY_HANDOFF_BUNDLE_INTERFACE: RepositoryHandoffBundle,
        REPOSITORY_SNAPSHOT_MANIFEST_SCHEMA: RepositorySnapshotManifest,
        REPOSITORY_SNAPSHOT_MANIFEST_INTERFACE: RepositorySnapshotManifest,
        DIRTY_OVERLAY_MANIFEST_SCHEMA: DirtyOverlayManifest,
        DIRTY_OVERLAY_MANIFEST_INTERFACE: DirtyOverlayManifest,
        REPOSITORY_TRANSFER_RECEIPT_SCHEMA: RepositoryTransferReceipt,
        REPOSITORY_TRANSFER_RECEIPT_INTERFACE: RepositoryTransferReceipt,
        REPOSITORY_TRANSFER_REQUEST_SCHEMA: RepositoryTransferRequest,
        SOURCE_BUNDLE_MANIFEST_SCHEMA: SourceBundleManifest,
        TRANSFER_POLICY_SCHEMA: TransferPolicy,
        "TransferPolicy@1": TransferPolicy,
        MANAGED_ALIAS_SCHEMA: ManagedAlias,
        "ManagedAlias@1": ManagedAlias,
        APPROVED_REMOTE_ALIAS_SCHEMA: ApprovedRemoteAlias,
        "ApprovedRemoteAlias@1": ApprovedRemoteAlias,
        "ipfs_kit_py/repository-transfer/locator@1": TransferLocator,
        "TransferLocator@1": TransferLocator,
        "ipfs_kit_py/repository-transfer/source-file-entry@1": SourceFileEntry,
        "ipfs_kit_py/repository-transfer/overlay-entry@1": OverlayEntry,
        "ipfs_kit_py/repository-transfer/shallow-boundary@1": ShallowBoundary,
        "ipfs_kit_py/repository-transfer/submodule-record@1": SubmoduleRecord,
    }
)


def decode_transfer_contract(
    payload: Mapping[str, Any] | str,
) -> CanonicalTransferRecord:
    """Decode one versioned transfer contract from canonical JSON or a mapping."""

    if isinstance(payload, str):
        try:
            value = json.loads(payload)
        except (TypeError, json.JSONDecodeError) as exc:
            raise RepositoryTransferError(
                "transfer contract JSON is malformed"
            ) from exc
    else:
        value = payload
    if not isinstance(value, Mapping):
        raise RepositoryTransferError("transfer contract must be an object")
    key = value.get("schema") or value.get("interface")
    decoder = _DECODERS.get(str(key))
    if decoder is None:
        raise TransferVersionError(
            f"unsupported transfer contract {key!r}; rebuild with an @1 schema"
        )
    return decoder.from_dict(value)


def _git(
    args: Sequence[str],
    *,
    cwd: Path,
    timeout: float,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update(_GIT_ENV)
    env["HOME"] = str(cwd)
    try:
        completed = subprocess.run(
            ["git", "-c", "init.defaultBranch=main", *args],
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TransferEngineError("git exceeded its timeout") from exc
    except OSError as exc:
        raise TransferEngineError("git is unavailable") from exc
    stdout = completed.stdout.decode("utf-8", "replace") if isinstance(completed.stdout, bytes) else completed.stdout
    stderr = completed.stderr.decode("utf-8", "replace") if isinstance(completed.stderr, bytes) else completed.stderr
    if check and completed.returncode != 0:
        raise TransferEngineError(f"git {' '.join(args[:3])} failed: {stderr[:200]}")
    return subprocess.CompletedProcess(completed.args, completed.returncode, stdout, stderr)


def _git_bytes(
    args: Sequence[str],
    *,
    cwd: Path,
    timeout: float,
) -> bytes:
    env = dict(os.environ)
    env.update(_GIT_ENV)
    env["HOME"] = str(cwd)
    try:
        completed = subprocess.run(
            ["git", "-c", "init.defaultBranch=main", *args],
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TransferEngineError("git exceeded its timeout") from exc
    if completed.returncode != 0:
        detail = (completed.stderr or b"").decode("utf-8", "replace")[:200]
        raise TransferEngineError(f"git {' '.join(args[:3])} failed: {detail}")
    return completed.stdout if isinstance(completed.stdout, bytes) else completed.stdout.encode()


def _disable_hooks(repository: Path, *, timeout: float) -> None:
    hooks = repository / ".git" / "hooks-disabled"
    hooks.mkdir(parents=True, exist_ok=True)
    _git(
        ["config", "--local", "core.hooksPath", ".git/hooks-disabled"],
        cwd=repository,
        timeout=timeout,
    )


def _clear_origin(repository: Path, *, timeout: float, origin_alias: str) -> None:
    existing = _git(["remote"], cwd=repository, timeout=timeout, check=False)
    remotes = [line.strip() for line in existing.stdout.splitlines() if line.strip()]
    for remote in remotes:
        _git(["remote", "remove", remote], cwd=repository, timeout=timeout, check=False)
    if origin_alias:
        _git(
            ["remote", "add", "origin", f"alias:{origin_alias}"],
            cwd=repository,
            timeout=timeout,
            check=False,
        )


def _fingerprint_tree(root: Path) -> str:
    entries: list[dict[str, str]] = []
    if not root.exists():
        return content_identity({"missing": True})
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries.append(
                {
                    "path": relative,
                    "kind": "symlink",
                    "target": path.readlink().as_posix(),
                }
            )
        elif path.is_file():
            entries.append(
                {
                    "path": relative,
                    "kind": "file",
                    "digest": artifact_identity(path.read_bytes()),
                    "mode": oct(path.stat().st_mode & 0o777),
                }
            )
        elif path.is_dir():
            entries.append({"path": relative, "kind": "dir"})
    return content_identity({"entries": entries})


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left.as_posix() == right.as_posix()


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def _require_quarantine(path: Path, *, user_checkout: Path | None) -> Path:
    if not isinstance(path, Path):
        raise RepositoryTransferError("quarantine_root must be a path")
    if user_checkout is not None:
        if (
            _same_path(path, user_checkout)
            or _is_within(path, user_checkout)
            or _is_within(user_checkout, path)
        ):
            raise RepositoryTransferError("quarantine_root must not be a user checkout")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _worktree_entries(root: Path) -> list[SourceFileEntry]:
    entries: list[SourceFileEntry] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if relative == ".git" or relative.startswith(".git/"):
            continue
        if path.is_dir() and not path.is_symlink():
            continue
        if path.is_symlink():
            target = path.readlink().as_posix()
            digest = artifact_identity(target.encode("utf-8"))
            entries.append(
                SourceFileEntry(
                    path=relative,
                    digest=digest,
                    mode="120000",
                    byte_count=len(target.encode("utf-8")),
                    symlink_target=target,
                )
            )
            continue
        data = path.read_bytes()
        mode = "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"
        entries.append(
            SourceFileEntry(
                path=relative,
                digest=artifact_identity(data),
                mode=mode,
                byte_count=len(data),
            )
        )
    return entries


def _source_tree_id(entries: Sequence[SourceFileEntry]) -> str:
    return content_identity(
        {
            "schema": "ipfs_kit_py/repository-transfer/source-tree@1",
            "files": [
                {"path": item.path, "digest": item.digest, "mode": item.mode}
                for item in sorted(entries, key=lambda item: item.path)
            ],
        }
    )


def _lfs_pointers(root: Path) -> tuple[str, ...]:
    found: list[str] = []
    marker = b"version https://git-lfs.github.com/spec/v1"
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith(".git/"):
            continue
        try:
            prefix = path.read_bytes()[:120]
        except OSError:
            continue
        if prefix.startswith(marker):
            found.append(relative)
    return tuple(found)


def _sparse_patterns(repository: Path) -> tuple[str, ...]:
    sparse = repository / ".git" / "info" / "sparse-checkout"
    if not sparse.is_file():
        return ()
    patterns = []
    for line in sparse.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text and not text.startswith("#") and "://" not in text:
            patterns.append(text)
    return tuple(patterns)


def _attribute_paths(root: Path) -> tuple[str, ...]:
    found: list[str] = []
    for candidate in (root / ".gitattributes", root / ".git" / "info" / "attributes"):
        if candidate.is_file():
            found.append(candidate.relative_to(root).as_posix())
    return tuple(found)


def _snapshot_git_repository(
    repository: Path,
    *,
    policy: TransferPolicy,
    origin_alias: str,
) -> RepositorySnapshotManifest:
    timeout = float(policy.git_timeout_seconds)
    head_commit = _git(["rev-parse", "HEAD"], cwd=repository, timeout=timeout).stdout.strip()
    head_ref_raw = _git(
        ["symbolic-ref", "-q", "HEAD"],
        cwd=repository,
        timeout=timeout,
        check=False,
    ).stdout.strip()
    head_tree = _git(
        ["rev-parse", "HEAD^{tree}"], cwd=repository, timeout=timeout
    ).stdout.strip()
    index_tree = _git(
        ["write-tree"], cwd=repository, timeout=timeout, check=False
    ).stdout.strip()
    refs_text = _git(
        ["show-ref", "--head"], cwd=repository, timeout=timeout, check=False
    ).stdout
    refs: dict[str, str] = {}
    for line in refs_text.splitlines():
        if not line.strip():
            continue
        oid, name = line.split(None, 1)
        if name == "HEAD" or _REF_NAME_RE.fullmatch(name):
            refs[name] = oid
    if len(refs) > policy.max_refs:
        raise TransferBoundsError("refs exceeds its item-count limit")
    untracked = tuple(
        line
        for line in _git(
            ["ls-files", "--others", "--exclude-standard", "-z"],
            cwd=repository,
            timeout=timeout,
            check=False,
        ).stdout.split("\0")
        if line
    )
    worktree = _worktree_entries(repository)
    executables = tuple(item.path for item in worktree if item.mode == "100755")
    object_count_text = _git(
        ["rev-list", "--all", "--count"],
        cwd=repository,
        timeout=timeout,
        check=False,
    ).stdout.strip()
    try:
        object_count = int(object_count_text.splitlines()[-1]) if object_count_text else 0
    except ValueError:
        object_count = 0
    shallow_file = repository / ".git" / "shallow"
    if shallow_file.is_file():
        commits = tuple(
            line.strip()
            for line in shallow_file.read_text(encoding="utf-8").splitlines()
            if _GIT_OID_RE.fullmatch(line.strip())
        )
        shallow = ShallowBoundary(is_shallow=True, depth=1, boundary_commits=commits)
    else:
        shallow = ShallowBoundary()
    hooks_dir = repository / ".git" / "hooks"
    hooks_present = hooks_dir.is_dir() and any(hooks_dir.iterdir())
    return RepositorySnapshotManifest(
        head_commit=head_commit,
        head_ref=head_ref_raw or "HEAD",
        head_tree=head_tree,
        index_tree=index_tree or head_tree,
        worktree_tree=_source_tree_id(worktree),
        refs=refs,
        untracked=untracked,
        lfs_pointers=_lfs_pointers(repository),
        sparse_checkout=_sparse_patterns(repository),
        hooks_present=hooks_present,
        hooks_disabled=True,
        attributes=_attribute_paths(repository),
        executable_paths=executables,
        origin_alias=origin_alias,
        shallow=shallow,
        object_count=object_count,
        byte_count=sum(item.byte_count for item in worktree),
        is_git_repository=True,
    )


def _snapshot_source_tree(
    repository: Path,
    *,
    origin_alias: str,
    overlay: DirtyOverlayManifest,
) -> RepositorySnapshotManifest:
    entries = _worktree_entries(repository)
    tree_id = _source_tree_id(entries)
    return RepositorySnapshotManifest(
        head_tree=tree_id,
        worktree_tree=tree_id,
        untracked=tuple(
            item.path
            for item in overlay.entries
            if item.status is OverlayStatus.UNTRACKED
        ),
        lfs_pointers=_lfs_pointers(repository),
        hooks_present=False,
        hooks_disabled=True,
        attributes=_attribute_paths(repository),
        executable_paths=tuple(item.path for item in entries if item.mode == "100755"),
        origin_alias=origin_alias,
        object_count=len(entries),
        byte_count=sum(item.byte_count for item in entries),
        is_git_repository=False,
    )


def _overlay_from_entries(entries: Sequence[OverlayEntry]) -> DirtyOverlayManifest:
    return DirtyOverlayManifest(entries=tuple(entries))


class ArtifactStore:
    """In-memory content-addressed artifact map.  Keys are sha256 identities."""

    def __init__(self, blobs: Mapping[str, bytes] | None = None) -> None:
        stored: dict[str, bytes] = {}
        for key, data in dict(blobs or {}).items():
            identity = _digest_sha256(key, "artifact store key")
            payload = bytes(data)
            actual = artifact_identity(payload)
            if identity != actual:
                raise TransferIdentityError("artifact store digest does not match bytes")
            stored[identity] = payload
        self._blobs = stored

    def add(self, data: bytes) -> str:
        payload = bytes(data)
        identity = artifact_identity(payload)
        self._blobs[identity] = payload
        return identity

    def get(self, identity: str) -> bytes | None:
        return self._blobs.get(_digest_sha256(identity, "artifact_id"))

    def __contains__(self, identity: str) -> bool:
        try:
            return _digest_sha256(identity, "artifact_id") in self._blobs
        except RepositoryTransferError:
            return False


@dataclass(frozen=True)
class ResolvedArtifact:
    kind: ArtifactKind
    artifact_id: str
    declared_head: str = ""
    declared_tree: str = ""
    origin_alias: str = ""
    source_mode: RepositoryTransferMode = RepositoryTransferMode.GIT_BUNDLE


def _managed_index(
    aliases: Iterable[ManagedAlias] | Mapping[str, Any],
) -> dict[str, ManagedAlias]:
    if isinstance(aliases, Mapping):
        values = []
        for name, item in aliases.items():
            if isinstance(item, ManagedAlias):
                if item.name != name:
                    raise RepositoryTransferError("managed alias name mismatch")
                values.append(item)
            elif isinstance(item, Mapping):
                payload = dict(item)
                payload.setdefault("name", name)
                values.append(
                    ManagedAlias.from_dict(payload)
                    if "schema" in payload
                    else ManagedAlias(
                        name=payload.get("name", name),
                        artifact_kind=payload.get("artifact_kind", ArtifactKind.GIT_BUNDLE),
                        artifact_id=payload.get("artifact_id", ""),
                        declared_head=payload.get("declared_head", ""),
                        declared_tree=payload.get("declared_tree", ""),
                    )
                )
            else:
                raise RepositoryTransferError("managed aliases must be objects")
        aliases = values
    index: dict[str, ManagedAlias] = {}
    for item in aliases:
        if not isinstance(item, ManagedAlias):
            raise RepositoryTransferError("managed aliases must be ManagedAlias records")
        if item.name in index:
            raise RepositoryTransferError("managed aliases must not contain duplicates")
        index[item.name] = item
    return index


def _remote_index(
    aliases: Iterable[ApprovedRemoteAlias] | Mapping[str, Any],
) -> dict[str, ApprovedRemoteAlias]:
    if isinstance(aliases, Mapping):
        values = []
        for name, item in aliases.items():
            if isinstance(item, ApprovedRemoteAlias):
                if item.name != name:
                    raise RepositoryTransferError("approved remote alias name mismatch")
                values.append(item)
            elif isinstance(item, Mapping):
                payload = dict(item)
                payload.setdefault("name", name)
                values.append(
                    ApprovedRemoteAlias.from_dict(payload)
                    if "schema" in payload
                    else ApprovedRemoteAlias(
                        name=payload.get("name", name),
                        approved_url=payload.get("approved_url") or payload.get("url") or "",
                        artifact_kind=payload.get("artifact_kind", ArtifactKind.GIT_BUNDLE),
                        artifact_id=payload.get("artifact_id", ""),
                        declared_head=payload.get("declared_head", ""),
                        declared_tree=payload.get("declared_tree", ""),
                    )
                )
            else:
                raise RepositoryTransferError("approved remote aliases must be objects")
        aliases = values
    index: dict[str, ApprovedRemoteAlias] = {}
    for item in aliases:
        if not isinstance(item, ApprovedRemoteAlias):
            raise RepositoryTransferError(
                "approved remotes must be ApprovedRemoteAlias records"
            )
        if item.name in index:
            raise RepositoryTransferError(
                "approved remote aliases must not contain duplicates"
            )
        index[item.name] = item
    return index


def resolve_transfer_locator(
    request: RepositoryTransferRequest,
    *,
    managed_aliases: Iterable[ManagedAlias] | Mapping[str, Any] = (),
    approved_remotes: Iterable[ApprovedRemoteAlias] | Mapping[str, Any] = (),
) -> ResolvedArtifact | TransferRefusal:
    """Resolve an alias or concrete locator without touching the filesystem."""

    locator = request.locator
    if locator.mode is RepositoryTransferMode.MANAGED_ALIAS:
        alias = _managed_index(managed_aliases).get(locator.alias)
        if alias is None:
            return TransferRefusal.UNKNOWN_ALIAS
        return ResolvedArtifact(
            kind=alias.artifact_kind,
            artifact_id=alias.artifact_id,
            declared_head=request.declared_head or alias.declared_head,
            declared_tree=request.declared_tree or alias.declared_tree,
            origin_alias=request.origin_alias or alias.name,
            source_mode=RepositoryTransferMode.MANAGED_ALIAS,
        )
    if locator.mode is RepositoryTransferMode.APPROVED_REMOTE_ALIAS:
        alias = _remote_index(approved_remotes).get(locator.alias)
        if alias is None:
            return TransferRefusal.UNAPPROVED_REMOTE
        return ResolvedArtifact(
            kind=alias.artifact_kind,
            artifact_id=alias.artifact_id,
            declared_head=request.declared_head or alias.declared_head,
            declared_tree=request.declared_tree or alias.declared_tree,
            origin_alias=request.origin_alias or alias.name,
            source_mode=RepositoryTransferMode.APPROVED_REMOTE_ALIAS,
        )
    kind = {
        RepositoryTransferMode.GIT_BUNDLE: ArtifactKind.GIT_BUNDLE,
        RepositoryTransferMode.MANIFESTED_SOURCE_BUNDLE: ArtifactKind.SOURCE_BUNDLE,
        RepositoryTransferMode.UPLOADED_OBJECT_SET: ArtifactKind.OBJECT_SET,
    }[locator.mode]
    return ResolvedArtifact(
        kind=kind,
        artifact_id=locator.artifact_id or locator.manifest_id,
        declared_head=request.declared_head or locator.declared_head,
        declared_tree=request.declared_tree or locator.declared_tree,
        origin_alias=request.origin_alias or locator.alias,
        source_mode=locator.mode,
    )


def admit_transfer_request(
    request: RepositoryTransferRequest,
    *,
    managed_aliases: Iterable[ManagedAlias] | Mapping[str, Any] = (),
    approved_remotes: Iterable[ApprovedRemoteAlias] | Mapping[str, Any] = (),
) -> TransferRefusal | None:
    """Return a typed refusal if the locator cannot be admitted, else None."""

    resolved = resolve_transfer_locator(
        request,
        managed_aliases=managed_aliases,
        approved_remotes=approved_remotes,
    )
    if isinstance(resolved, TransferRefusal):
        return resolved
    return None


def _refused_result(
    request: RepositoryTransferRequest,
    reason: TransferRefusal,
    *,
    policy: TransferPolicy,
) -> RepositoryTransferResult:
    receipt = RepositoryTransferReceipt(
        request_id=request.content_id,
        verdict=TransferVerdict.REFUSED,
        mode=request.mode,
        policy_id=policy.policy_id,
        reason_code=reason.value,
    )
    return RepositoryTransferResult(receipt=receipt)


def _write_source_files(
    destination: Path,
    manifest: SourceBundleManifest,
    store: ArtifactStore,
    *,
    policy: TransferPolicy,
) -> TransferRefusal | None:
    if len(manifest.files) > policy.max_paths:
        return TransferRefusal.BOUNDS_EXCEEDED
    for entry in manifest.files:
        if entry.byte_count > policy.max_artifact_bytes:
            return TransferRefusal.BOUNDS_EXCEEDED
        target = destination / entry.path
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return TransferRefusal.ENGINE_FAILURE
        if entry.mode == "120000":
            if looks_like_host_path(entry.symlink_target):
                return TransferRefusal.UNSAFE_SYMLINK
            try:
                if target.exists() or target.is_symlink():
                    target.unlink()
                target.symlink_to(entry.symlink_target)
            except OSError:
                return TransferRefusal.UNSAFE_SYMLINK
            continue
        blob = store.get(entry.digest)
        if blob is None:
            return TransferRefusal.ARTIFACT_MISSING
        if artifact_identity(blob) != entry.digest:
            return TransferRefusal.ARTIFACT_DIGEST_MISMATCH
        if len(blob) > policy.max_artifact_bytes:
            return TransferRefusal.BOUNDS_EXCEEDED
        target.write_bytes(blob)
        os.chmod(target, 0o755 if entry.mode == "100755" else 0o644)
    return None


def _reconstruct_git_bundle(
    destination: Path,
    bundle_bytes: bytes,
    *,
    policy: TransferPolicy,
    origin_alias: str,
    head_ref: str,
) -> None:
    timeout = float(policy.git_timeout_seconds)
    if len(bundle_bytes) > policy.max_artifact_bytes:
        raise TransferBoundsError("git bundle exceeds max_artifact_bytes")
    staging = destination.parent / ".staging"
    staging.mkdir(parents=True, exist_ok=True)
    bundle_path = staging / "source.bundle"
    bundle_path.write_bytes(bundle_bytes)
    if destination.exists():
        shutil.rmtree(destination)
    _git(
        ["clone", "--quiet", bundle_path.as_posix(), destination.as_posix()],
        cwd=staging,
        timeout=timeout,
    )
    _disable_hooks(destination, timeout=timeout)
    _clear_origin(destination, timeout=timeout, origin_alias=origin_alias)
    if head_ref and head_ref != "HEAD":
        _git(
            ["checkout", "--quiet", head_ref],
            cwd=destination,
            timeout=timeout,
            check=False,
        )
    shutil.rmtree(staging, ignore_errors=True)


def _reconstruct_object_set(
    destination: Path,
    payload: bytes,
    *,
    policy: TransferPolicy,
    origin_alias: str,
    declared_head: str,
) -> None:
    timeout = float(policy.git_timeout_seconds)
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransferEngineError("object set is not canonical JSON") from exc
    if not isinstance(document, Mapping):
        raise TransferEngineError("object set must be an object")
    _reject_forbidden_keys(document, name="object set")
    objects = document.get("objects")
    refs = document.get("refs")
    if not isinstance(objects, Sequence) or not isinstance(refs, Mapping):
        raise TransferEngineError("object set must include objects and refs")
    if len(objects) > policy.max_objects:
        raise TransferBoundsError("object set exceeds max_objects")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    _git(["init", "--quiet"], cwd=destination, timeout=timeout)
    _disable_hooks(destination, timeout=timeout)
    object_root = destination / ".git" / "objects"
    for item in objects:
        if not isinstance(item, Mapping):
            raise TransferEngineError("object set entries must be objects")
        oid = _git_oid(item.get("id", ""), "object id", required=True)
        kind = _text(item.get("type", ""), "object type", max_bytes=16)
        if kind not in {"blob", "tree", "commit", "tag"}:
            raise TransferEngineError("object set type is not a Git object type")
        data_hex = item.get("data_hex")
        data_text = item.get("data")
        if isinstance(data_hex, str):
            try:
                raw = bytes.fromhex(data_hex)
            except ValueError as exc:
                raise TransferEngineError("object set data_hex is invalid") from exc
        elif isinstance(data_text, str):
            raw = data_text.encode("utf-8")
        else:
            raise TransferEngineError("object set entry is missing data")
        header = f"{kind} {len(raw)}\0".encode("utf-8")
        stored = zlib.compress(header + raw)
        actual = hashlib.sha1(header + raw).hexdigest()
        if actual != oid:
            raise TransferIdentityError("object set Git identity does not match payload")
        bucket = object_root / oid[:2]
        bucket.mkdir(parents=True, exist_ok=True)
        (bucket / oid[2:]).write_bytes(stored)
    ref_map = _refs_map(refs, max_refs=policy.max_refs)
    for name, oid in ref_map.items():
        if name == "HEAD":
            continue
        _git(["update-ref", name, oid], cwd=destination, timeout=timeout)
    head_oid = declared_head or ref_map.get("HEAD") or next(iter(ref_map.values()), "")
    if not head_oid:
        raise TransferEngineError("object set does not declare HEAD")
    head_ref = next(
        (name for name, oid in ref_map.items() if oid == head_oid and name != "HEAD"),
        "",
    )
    if head_ref:
        _git(["symbolic-ref", "HEAD", head_ref], cwd=destination, timeout=timeout)
    _git(["checkout", "--quiet", "-f", "HEAD"], cwd=destination, timeout=timeout)
    _clear_origin(destination, timeout=timeout, origin_alias=origin_alias)


def encode_git_object_set(
    repository: Path, *, policy: TransferPolicy | None = None
) -> bytes:
    """Encode Git objects and refs from a fixture repository for staging."""

    bounds = _coerce_policy(policy)
    timeout = float(bounds.git_timeout_seconds)
    oids = [
        line.strip().split()[0]
        for line in _git(
            ["rev-list", "--objects", "--all"],
            cwd=repository,
            timeout=timeout,
        ).stdout.splitlines()
        if line.strip()
    ]
    if len(oids) > bounds.max_objects:
        raise TransferBoundsError("object set exceeds max_objects")
    objects: list[dict[str, str]] = []
    seen: set[str] = set()
    for oid in oids:
        if oid in seen:
            continue
        seen.add(oid)
        kind = _git(["cat-file", "-t", oid], cwd=repository, timeout=timeout).stdout.strip()
        data = _git_bytes(["cat-file", kind, oid], cwd=repository, timeout=timeout)
        objects.append({"id": oid, "type": kind, "data_hex": data.hex()})
    refs_text = _git(
        ["show-ref", "--head"], cwd=repository, timeout=timeout, check=False
    ).stdout
    refs: dict[str, str] = {}
    for line in refs_text.splitlines():
        if not line.strip():
            continue
        oid, name = line.split(None, 1)
        refs[name] = oid
    document = {
        "schema": "ipfs_kit_py/repository-transfer/git-object-set@1",
        "contract_version": CONTRACT_VERSION,
        "objects": objects,
        "refs": refs,
    }
    _reject_forbidden_keys(document, name="object set")
    return canonical_json_bytes(document)


def create_git_bundle(repository: Path, *, policy: TransferPolicy | None = None) -> bytes:
    """Create a Git bundle from a fixture repository for tests and staging."""

    bounds = _coerce_policy(policy)
    timeout = float(bounds.git_timeout_seconds)
    staging = repository / ".git" / "transfer.bundle"
    _git(
        ["bundle", "create", staging.as_posix(), "--all"],
        cwd=repository,
        timeout=timeout,
    )
    data = staging.read_bytes()
    staging.unlink(missing_ok=True)
    if len(data) > bounds.max_artifact_bytes:
        raise TransferBoundsError("git bundle exceeds max_artifact_bytes")
    return data


def _assert_user_checkout_unchanged(user_checkout: Path | None, before: str) -> None:
    if user_checkout is None:
        return
    if _fingerprint_tree(user_checkout) != before:
        raise TransferTrustError("transfer mutated a user checkout")


def _load_source_manifest(
    resolved: ResolvedArtifact,
    blob: bytes | None,
    source_manifests: Mapping[str, SourceBundleManifest | Mapping[str, Any]] | None,
) -> SourceBundleManifest | TransferRefusal | None:
    manifests = source_manifests or {}
    raw_manifest = manifests.get(resolved.artifact_id)
    if raw_manifest is None and blob is not None:
        try:
            decoded = json.loads(blob.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            decoded = None
        if isinstance(decoded, Mapping):
            raw_manifest = decoded
    if isinstance(raw_manifest, SourceBundleManifest):
        return raw_manifest
    if isinstance(raw_manifest, Mapping):
        try:
            if "schema" in raw_manifest:
                return SourceBundleManifest.from_dict(raw_manifest)
            return SourceBundleManifest(
                files=raw_manifest.get("files", ()),
                declared_tree=raw_manifest.get("declared_tree", ""),
                declared_head=raw_manifest.get("declared_head", ""),
                untracked=raw_manifest.get("untracked", ()),
            )
        except RepositoryTransferError as exc:
            message = str(exc)
            if "relative" in message or "metadata" in message:
                return TransferRefusal.MANIFEST_PATH_ESCAPE
            if "host path" in message:
                return TransferRefusal.ARBITRARY_HOST_PATH
            return TransferRefusal.FORBIDDEN_FIELD
    if blob is None:
        return TransferRefusal.ARTIFACT_MISSING
    return None


def transfer_repository(
    request: RepositoryTransferRequest | Mapping[str, Any],
    *,
    artifacts: ArtifactStore | Mapping[str, bytes] | None = None,
    managed_aliases: Iterable[ManagedAlias] | Mapping[str, Any] = (),
    approved_remotes: Iterable[ApprovedRemoteAlias] | Mapping[str, Any] = (),
    quarantine_root: Path,
    user_checkout: Path | None = None,
    policy: TransferPolicy | Mapping[str, Any] | None = None,
    source_manifests: Mapping[str, SourceBundleManifest | Mapping[str, Any]] | None = None,
) -> RepositoryTransferResult:
    """Admit a bounded locator and reconstruct it into ``quarantine_root``.

    ``user_checkout`` is never written.  Host paths, unknown aliases, missing
    artifacts and declared-state mismatches return a typed refusal receipt.
    """

    bounds = _coerce_policy(policy)
    if isinstance(request, Mapping):
        try:
            request = RepositoryTransferRequest.from_dict(request)
        except RepositoryTransferError as exc:
            dummy = RepositoryTransferRequest(
                mode=RepositoryTransferMode.GIT_BUNDLE,
                locator=TransferLocator(
                    mode=RepositoryTransferMode.GIT_BUNDLE,
                    artifact_id="sha256:" + ("0" * 64),
                ),
                idempotency_key="invalid-request",
            )
            message = str(exc)
            reason = (
                TransferRefusal.ARBITRARY_HOST_PATH
                if "host path" in message
                else TransferRefusal.UNKNOWN_TRANSFER_MODE
                if "must be one of" in message
                else TransferRefusal.FORBIDDEN_FIELD
            )
            return _refused_result(dummy, reason, policy=bounds)
    elif not isinstance(request, RepositoryTransferRequest):
        raise RepositoryTransferError("request must be a RepositoryTransferRequest")
    store = artifacts if isinstance(artifacts, ArtifactStore) else ArtifactStore(artifacts)
    checkout_before = _fingerprint_tree(user_checkout) if user_checkout is not None else ""
    try:
        quarantine = _require_quarantine(quarantine_root, user_checkout=user_checkout)
    except RepositoryTransferError:
        result = _refused_result(request, TransferRefusal.QUARANTINE_UNSAFE, policy=bounds)
        _assert_user_checkout_unchanged(user_checkout, checkout_before)
        return result
    try:
        resolved = resolve_transfer_locator(
            request,
            managed_aliases=managed_aliases,
            approved_remotes=approved_remotes,
        )
    except RepositoryTransferError as exc:
        reason = (
            TransferRefusal.ARBITRARY_HOST_PATH
            if "host path" in str(exc)
            else TransferRefusal.FORBIDDEN_FIELD
        )
        result = _refused_result(request, reason, policy=bounds)
        _assert_user_checkout_unchanged(user_checkout, checkout_before)
        return result
    if isinstance(resolved, TransferRefusal):
        result = _refused_result(request, resolved, policy=bounds)
        _assert_user_checkout_unchanged(user_checkout, checkout_before)
        return result
    blob = store.get(resolved.artifact_id)
    manifest: SourceBundleManifest | None = None
    if resolved.kind is ArtifactKind.SOURCE_BUNDLE:
        loaded = _load_source_manifest(resolved, blob, source_manifests)
        if isinstance(loaded, TransferRefusal):
            result = _refused_result(request, loaded, policy=bounds)
            _assert_user_checkout_unchanged(user_checkout, checkout_before)
            return result
        manifest = loaded
    elif blob is None:
        reason = (
            TransferRefusal.REMOTE_FETCH_NOT_ADMITTED
            if request.mode is RepositoryTransferMode.APPROVED_REMOTE_ALIAS
            else TransferRefusal.ARTIFACT_MISSING
        )
        result = _refused_result(request, reason, policy=bounds)
        _assert_user_checkout_unchanged(user_checkout, checkout_before)
        return result
    if blob is not None and len(blob) > bounds.max_artifact_bytes:
        result = _refused_result(request, TransferRefusal.BOUNDS_EXCEEDED, policy=bounds)
        _assert_user_checkout_unchanged(user_checkout, checkout_before)
        return result
    destination = quarantine / request.content_id[7:23]
    try:
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        if resolved.kind is ArtifactKind.GIT_BUNDLE:
            if blob is None:
                raise TransferEngineError("git bundle bytes are missing")
            _reconstruct_git_bundle(
                destination,
                blob,
                policy=bounds,
                origin_alias=resolved.origin_alias,
                head_ref=request.locator.head_ref,
            )
            overlay = _overlay_from_entries(request.overlay_entries)
            snapshot = _snapshot_git_repository(
                destination, policy=bounds, origin_alias=resolved.origin_alias
            )
        elif resolved.kind is ArtifactKind.OBJECT_SET:
            if blob is None:
                raise TransferEngineError("object set bytes are missing")
            _reconstruct_object_set(
                destination,
                blob,
                policy=bounds,
                origin_alias=resolved.origin_alias,
                declared_head=resolved.declared_head,
            )
            overlay = _overlay_from_entries(request.overlay_entries)
            snapshot = _snapshot_git_repository(
                destination, policy=bounds, origin_alias=resolved.origin_alias
            )
        else:
            if manifest is None:
                raise TransferEngineError("source bundle manifest is missing")
            write_error = _write_source_files(
                destination, manifest, store, policy=bounds
            )
            if write_error is not None:
                shutil.rmtree(destination, ignore_errors=True)
                result = _refused_result(request, write_error, policy=bounds)
                _assert_user_checkout_unchanged(user_checkout, checkout_before)
                return result
            overlay_entries = list(request.overlay_entries)
            present = {item.path for item in overlay_entries}
            for path in manifest.untracked:
                if path not in present:
                    overlay_entries.append(
                        OverlayEntry(path=path, status=OverlayStatus.UNTRACKED)
                    )
            overlay = _overlay_from_entries(overlay_entries)
            snapshot = _snapshot_source_tree(
                destination, origin_alias=resolved.origin_alias, overlay=overlay
            )
        expected_head = (
            resolved.declared_head or request.declared_head or request.locator.declared_head
        )
        expected_tree = (
            resolved.declared_tree or request.declared_tree or request.locator.declared_tree
        )
        if expected_head and snapshot.head_commit and snapshot.head_commit != expected_head:
            shutil.rmtree(destination, ignore_errors=True)
            result = _refused_result(
                request, TransferRefusal.DECLARED_STATE_MISMATCH, policy=bounds
            )
            _assert_user_checkout_unchanged(user_checkout, checkout_before)
            return result
        reconstructed_tree = snapshot.head_tree
        if expected_tree and reconstructed_tree != expected_tree:
            shutil.rmtree(destination, ignore_errors=True)
            result = _refused_result(
                request, TransferRefusal.DECLARED_STATE_MISMATCH, policy=bounds
            )
            _assert_user_checkout_unchanged(user_checkout, checkout_before)
            return result
        artifact_ids = [resolved.artifact_id]
        if manifest is not None:
            artifact_ids.extend(item.digest for item in manifest.files)
        bundle = RepositoryHandoffBundle(
            mode=request.mode,
            locator=request.locator,
            snapshot_id=snapshot.content_id,
            overlay_id=overlay.content_id,
            reconstructed_tree_id=reconstructed_tree,
            artifact_ids=tuple(dict.fromkeys(artifact_ids)),
            origin_alias=resolved.origin_alias,
            quarantine_id=content_identity(
                {
                    "schema": "ipfs_kit_py/repository-transfer/quarantine-slot@1",
                    "request_id": request.content_id,
                    "tree": reconstructed_tree,
                }
            ),
        )
        receipt = RepositoryTransferReceipt(
            request_id=request.content_id,
            verdict=TransferVerdict.ADMITTED,
            mode=request.mode,
            policy_id=bounds.policy_id,
            bundle_id=bundle.content_id,
            snapshot_id=snapshot.content_id,
            overlay_id=overlay.content_id,
            reconstructed_tree_id=reconstructed_tree,
            user_checkout_mutated=False,
        )
        result = RepositoryTransferResult(
            receipt=receipt,
            bundle=bundle,
            snapshot=snapshot,
            overlay=overlay,
            repository_root=destination.name,
        )
        _assert_user_checkout_unchanged(user_checkout, checkout_before)
        return result
    except TransferBoundsError:
        shutil.rmtree(destination, ignore_errors=True)
        result = _refused_result(request, TransferRefusal.BOUNDS_EXCEEDED, policy=bounds)
        _assert_user_checkout_unchanged(user_checkout, checkout_before)
        return result
    except TransferIdentityError:
        shutil.rmtree(destination, ignore_errors=True)
        result = _refused_result(
            request, TransferRefusal.ARTIFACT_DIGEST_MISMATCH, policy=bounds
        )
        _assert_user_checkout_unchanged(user_checkout, checkout_before)
        return result
    except RepositoryTransferError as exc:
        shutil.rmtree(destination, ignore_errors=True)
        message = str(exc)
        if "host path" in message:
            reason = TransferRefusal.ARBITRARY_HOST_PATH
        elif "symlink" in message:
            reason = TransferRefusal.UNSAFE_SYMLINK
        else:
            reason = TransferRefusal.ENGINE_FAILURE
        result = _refused_result(request, reason, policy=bounds)
        _assert_user_checkout_unchanged(user_checkout, checkout_before)
        return result
