"""Configuration and private state layout for managed Iroh sidecars.

This module deliberately does not start a service or resolve credentials.
Loading configuration is side-effect free; callers explicitly create the
state tree with :func:`ensure_state_layout` immediately before service use.
"""

from __future__ import annotations

import copy
import json
import os
import re
import stat
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .errors import (
    IrohConflictError,
    IrohInvalidConfigError,
    IrohUnsupportedVersionError,
)


CONFIG_SCHEMA_VERSION = 1
DEFAULT_RELEASE_BUNDLE = "iroh-1.0.2-ipfs-kit.1"
DEFAULT_PROTOCOL_VERSION = 1
DEFAULT_INSTANCE = "default"
DIRECTORY_MODE = 0o700
FILE_MODE = 0o600

_INSTANCE_RE = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$")
_CREDENTIAL_RE = re.compile(
    r"^credential://iroh/[a-z0-9](?:[a-z0-9._/-]{0,126}[a-z0-9])?$"
)
_SENSITIVE_KEY_RE = re.compile(
    r"(?:^|_)(?:secret|token|ticket|password|passwd|private_key|node_key|"
    r"author_key|write_capability|identity_key)(?:$|_)",
    re.IGNORECASE,
)
_BIND_RE = re.compile(r"^(?:\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9.-]+):(\d{1,5})$")
_NPIPE_RE = re.compile(r"^npipe:////\./pipe/[A-Za-z0-9._-]{1,128}$")


def _invalid(message: str) -> IrohInvalidConfigError:
    return IrohInvalidConfigError(message, operation="config")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _invalid(f"duplicate configuration key {key!r}")
        result[key] = value
    return result


def _expect_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _invalid(f"{label} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise _invalid(f"{label} contains a non-string key")
    return value


def _only(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        names = ", ".join(repr(name) for name in sorted(unknown))
        raise _invalid(f"{label} contains unknown fields: {names}")


def _string(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise _invalid(f"{label} must be a non-empty string")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise _invalid(f"{label} contains a control character")
    return value


def _positive_int(value: Any, label: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise _invalid(f"{label} must be an integer greater than or equal to {minimum}")
    return value


def _mode(value: Any, label: str, expected: int) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"0?[0-7]{3}", value):
        raise _invalid(f"{label} must be an octal permission mode")
    parsed = int(value, 8)
    if parsed != expected:
        raise _invalid(f"{label} must be owner-only ({expected:04o})")
    return parsed


def _absolute_path(value: Any, label: str) -> Path:
    text = _string(os.fspath(value) if isinstance(value, os.PathLike) else value, label)
    path = Path(text).expanduser()
    if not path.is_absolute() or ".." in path.parts:
        raise _invalid(f"{label} must be an absolute path without parent traversal")
    return Path(os.path.abspath(os.fspath(path)))


def _credential_ref(value: Any, label: str) -> str:
    reference = _string(value, label)
    if not _CREDENTIAL_RE.fullmatch(reference):
        raise _invalid(f"{label} must be a credential://iroh/ reference")
    return reference


def _reject_inline_secrets(value: Any, path: str = "config") -> None:
    """Reject secret-bearing field names anywhere in persisted input.

    Reference fields are allowed only when their value is a syntactically
    valid opaque credential reference. This check intentionally precedes
    ordinary shape validation so unknown inline-secret fields fail closed.
    """

    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            child = f"{path}.{key_text}"
            if _SENSITIVE_KEY_RE.search(key_text):
                if key_text.endswith("_ref"):
                    _credential_ref(item, child)
                else:
                    raise _invalid(f"{path} contains forbidden inline credential field {key_text!r}")
            else:
                _reject_inline_secrets(item, child)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_inline_secrets(item, f"{path}[{index}]")


def default_state_root() -> Path:
    """Return the platform-local Iroh state root without creating it."""

    override = os.environ.get("IPFS_KIT_IROH_STATE_DIR")
    if override:
        return _absolute_path(override, "IPFS_KIT_IROH_STATE_DIR")
    xdg_state = os.environ.get("XDG_STATE_HOME")
    base = _absolute_path(xdg_state, "XDG_STATE_HOME") if xdg_state else Path.home() / ".local" / "state"
    return base / "ipfs-kit" / "iroh"


def validate_instance_name(name: Any) -> str:
    value = _string(name, "instance")
    if len(value) > 64 or not _INSTANCE_RE.fullmatch(value):
        raise _invalid(
            "instance must be 1-64 lowercase ASCII letters, digits, underscores, or hyphens"
        )
    return value


@dataclass(frozen=True, slots=True)
class IrohStateLayout:
    """All persistent and ephemeral paths owned by one named sidecar."""

    instance: str
    root: Path
    data_dir: Path
    staging_dir: Path
    runtime_dir: Path
    log_dir: Path
    receipt_dir: Path
    config_path: Path
    rpc_socket_path: Path
    pid_path: Path
    lock_path: Path
    service_log_path: Path
    health_receipt_path: Path
    crash_receipt_path: Path
    owner_path: Path

    @classmethod
    def for_instance(
        cls,
        instance: str = DEFAULT_INSTANCE,
        *,
        state_root: str | os.PathLike[str] | None = None,
    ) -> "IrohStateLayout":
        name = validate_instance_name(instance)
        base = _absolute_path(state_root, "state_root") if state_root is not None else default_state_root()
        root = base / "instances" / name
        runtime = root / "run"
        logs = root / "logs"
        receipts = root / "receipts"
        return cls(
            instance=name,
            root=root,
            data_dir=root / "data",
            staging_dir=root / "staging",
            runtime_dir=runtime,
            log_dir=logs,
            receipt_dir=receipts,
            config_path=root / "config.json",
            rpc_socket_path=runtime / "sidecar.sock",
            pid_path=runtime / "sidecar.pid",
            lock_path=runtime / "service.lock",
            service_log_path=logs / "sidecar.log",
            health_receipt_path=receipts / "health.json",
            crash_receipt_path=receipts / "crash.json",
            owner_path=root / ".instance.json",
        )

    @property
    def rpc_endpoint(self) -> str:
        if os.name == "nt":
            return f"npipe:////./pipe/ipfs-kit-iroh-{self.instance}"
        return f"unix://{self.rpc_socket_path.as_posix()}"

    @property
    def directories(self) -> tuple[Path, ...]:
        return (
            self.root,
            self.data_dir,
            self.staging_dir,
            self.runtime_dir,
            self.log_dir,
            self.receipt_dir,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "root": str(self.root),
            "data_dir": str(self.data_dir),
            "staging_dir": str(self.staging_dir),
            "runtime_dir": str(self.runtime_dir),
            "log_dir": str(self.log_dir),
            "receipt_dir": str(self.receipt_dir),
            "service_log": str(self.service_log_path),
            "health_receipt": str(self.health_receipt_path),
            "crash_receipt": str(self.crash_receipt_path),
        }


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    max_storage_bytes: int = 100 * 1024**3
    max_staging_bytes: int = 10 * 1024**3
    max_concurrent_transfers: int = 16
    max_connections: int = 256
    max_open_files: int = 1024

    @classmethod
    def from_dict(cls, raw: Any) -> "ResourceLimits":
        value = _expect_mapping(raw, "resources")
        fields = {
            "max_storage_bytes",
            "max_staging_bytes",
            "max_concurrent_transfers",
            "max_connections",
            "max_open_files",
        }
        _only(value, fields, "resources")
        defaults = cls()
        return cls(
            **{
                name: _positive_int(value.get(name, getattr(defaults, name)), f"resources.{name}")
                for name in fields
            }
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "max_storage_bytes": self.max_storage_bytes,
            "max_staging_bytes": self.max_staging_bytes,
            "max_concurrent_transfers": self.max_concurrent_transfers,
            "max_connections": self.max_connections,
            "max_open_files": self.max_open_files,
        }


@dataclass(frozen=True, slots=True)
class OwnershipPolicy:
    uid: int | None = None
    gid: int | None = None
    directory_mode: int = DIRECTORY_MODE
    file_mode: int = FILE_MODE

    @classmethod
    def from_dict(cls, raw: Any) -> "OwnershipPolicy":
        value = _expect_mapping(raw, "ownership")
        _only(value, {"uid", "gid", "directory_mode", "file_mode"}, "ownership")
        uid, gid = value.get("uid"), value.get("gid")
        for item, label in ((uid, "ownership.uid"), (gid, "ownership.gid")):
            if item is not None and (
                isinstance(item, bool) or not isinstance(item, int) or item < 0
            ):
                raise _invalid(f"{label} must be null or a non-negative integer")
        return cls(
            uid=uid,
            gid=gid,
            directory_mode=_mode(value.get("directory_mode", "0700"), "ownership.directory_mode", DIRECTORY_MODE),
            file_mode=_mode(value.get("file_mode", "0600"), "ownership.file_mode", FILE_MODE),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "gid": self.gid,
            "directory_mode": f"{self.directory_mode:04o}",
            "file_mode": f"{self.file_mode:04o}",
        }


@dataclass(frozen=True, slots=True)
class IrohServiceConfig:
    """Validated schema-version-1 configuration for one managed sidecar."""

    instance: str
    layout: IrohStateLayout
    enabled: bool = False
    release_bundle: str = DEFAULT_RELEASE_BUNDLE
    protocol_version: int = DEFAULT_PROTOCOL_VERSION
    node_identity_ref: str = "credential://iroh/default/node-key"
    endpoint_bind: tuple[str, ...] = ("0.0.0.0:0", "[::]:0")
    relay_policy: str = "default"
    relay_urls: tuple[str, ...] = ()
    discovery_policy: str = "local"
    resources: ResourceLimits = field(default_factory=ResourceLimits)
    ownership: OwnershipPolicy = field(default_factory=OwnershipPolicy)

    @property
    def paths(self) -> IrohStateLayout:
        """Compatibility name for the configured state layout."""

        return self.layout

    @property
    def rpc_endpoint(self) -> str:
        return self.layout.rpc_endpoint

    @property
    def data_dir(self) -> Path:
        return self.layout.data_dir

    @property
    def staging_dir(self) -> Path:
        return self.layout.staging_dir

    @property
    def log_path(self) -> Path:
        return self.layout.service_log_path

    @property
    def receipt_dir(self) -> Path:
        return self.layout.receipt_dir

    @classmethod
    def default(
        cls,
        instance: str = DEFAULT_INSTANCE,
        *,
        state_root: str | os.PathLike[str] | None = None,
        enabled: bool = False,
        node_identity_ref: str | None = None,
    ) -> "IrohServiceConfig":
        name = validate_instance_name(instance)
        if not isinstance(enabled, bool):
            raise _invalid("enabled must be a boolean")
        layout = IrohStateLayout.for_instance(name, state_root=state_root)
        identity_ref = node_identity_ref or f"credential://iroh/{name}/node-key"
        return cls(
            instance=name,
            layout=layout,
            enabled=enabled,
            node_identity_ref=_credential_ref(identity_ref, "identity.node_identity_ref"),
        )

    @classmethod
    def from_dict(
        cls,
        raw: Any,
        *,
        state_root: str | os.PathLike[str] | None = None,
    ) -> "IrohServiceConfig":
        value = _expect_mapping(copy.deepcopy(raw), "configuration")
        _reject_inline_secrets(value)
        _only(
            value,
            {
                "schema_version", "kind", "instance", "enabled",
                "release_bundle", "protocol_version", "state_root", "rpc",
                "network", "identity", "resources", "logging", "ownership",
            },
            "configuration",
        )

        version = value.get("schema_version")
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version != CONFIG_SCHEMA_VERSION
        ):
            if isinstance(version, int) and not isinstance(version, bool) and version > CONFIG_SCHEMA_VERSION:
                raise IrohUnsupportedVersionError(
                    "Iroh service configuration version is newer than this package",
                    operation="config",
                )
            raise _invalid("configuration must be migrated to schema_version 1")
        if value.get("kind") != "ipfs-kit-iroh-service":
            raise _invalid("kind must be 'ipfs-kit-iroh-service'")

        instance = validate_instance_name(value.get("instance"))
        enabled = value.get("enabled")
        if not isinstance(enabled, bool):
            raise _invalid("enabled must be a boolean")
        if value.get("release_bundle") != DEFAULT_RELEASE_BUNDLE:
            raise IrohUnsupportedVersionError("unsupported Iroh release bundle", operation="config")
        protocol_version = value.get("protocol_version")
        if (
            isinstance(protocol_version, bool)
            or not isinstance(protocol_version, int)
            or protocol_version != DEFAULT_PROTOCOL_VERSION
        ):
            raise IrohUnsupportedVersionError("unsupported Iroh RPC protocol version", operation="config")

        configured_root = _absolute_path(value.get("state_root"), "state_root")
        if state_root is not None and configured_root != _absolute_path(state_root, "state_root"):
            raise _invalid("configured state_root conflicts with the caller override")
        layout = IrohStateLayout.for_instance(instance, state_root=configured_root)

        rpc = _expect_mapping(value.get("rpc"), "rpc")
        _only(rpc, {"kind", "endpoint"}, "rpc")
        if rpc.get("kind") != "local":
            raise _invalid("rpc.kind must be 'local'")
        _validate_rpc_endpoint(rpc.get("endpoint"))
        if rpc.get("endpoint") != layout.rpc_endpoint:
            raise _invalid("rpc.endpoint must be the socket assigned to this named instance")

        identity = _expect_mapping(value.get("identity"), "identity")
        _only(identity, {"node_identity_ref"}, "identity")
        identity_ref = _credential_ref(identity.get("node_identity_ref"), "identity.node_identity_ref")

        network = _expect_mapping(value.get("network"), "network")
        _only(network, {"endpoint_bind", "relay", "discovery"}, "network")
        binds_raw = network.get("endpoint_bind")
        if not isinstance(binds_raw, list) or not binds_raw:
            raise _invalid("network.endpoint_bind must be a non-empty array")
        binds = tuple(_validate_bind(item) for item in binds_raw)
        if len(binds) != len(set(bind_.lower() for bind_ in binds)):
            raise _invalid("network.endpoint_bind contains a duplicate address")

        relay = _expect_mapping(network.get("relay"), "network.relay")
        _only(relay, {"policy", "urls"}, "network.relay")
        relay_policy = relay.get("policy")
        if relay_policy not in {"default", "disabled", "custom"}:
            raise _invalid("network.relay.policy must be default, disabled, or custom")
        urls_raw = relay.get("urls")
        if not isinstance(urls_raw, list):
            raise _invalid("network.relay.urls must be an array")
        relay_urls = tuple(_validate_relay_url(url) for url in urls_raw)
        if len(relay_urls) != len(set(relay_urls)):
            raise _invalid("network.relay.urls contains a duplicate URL")
        if relay_policy == "custom" and not relay_urls:
            raise _invalid("custom relay policy requires at least one relay URL")
        if relay_policy != "custom" and relay_urls:
            raise _invalid("relay URLs are only allowed with the custom policy")

        discovery = _expect_mapping(network.get("discovery"), "network.discovery")
        _only(discovery, {"policy"}, "network.discovery")
        discovery_policy = discovery.get("policy")
        if discovery_policy not in {"disabled", "local", "dns", "all"}:
            raise _invalid("network.discovery.policy must be disabled, local, dns, or all")

        logging = _expect_mapping(value.get("logging"), "logging")
        logging_fields = {"log_path", "health_receipt_path", "crash_receipt_path"}
        _only(logging, logging_fields, "logging")
        expected_logging = {
            "log_path": layout.service_log_path,
            "health_receipt_path": layout.health_receipt_path,
            "crash_receipt_path": layout.crash_receipt_path,
        }
        for name, expected in expected_logging.items():
            actual = _absolute_path(logging.get(name), f"logging.{name}")
            if actual != expected:
                raise _invalid(f"logging.{name} must be the path assigned to this named instance")

        resources = ResourceLimits.from_dict(value.get("resources"))
        if resources.max_staging_bytes > resources.max_storage_bytes:
            raise _invalid("max_staging_bytes cannot exceed max_storage_bytes")
        ownership = OwnershipPolicy.from_dict(value.get("ownership"))
        return cls(
            instance=instance,
            layout=layout,
            enabled=enabled,
            node_identity_ref=identity_ref,
            endpoint_bind=binds,
            relay_policy=relay_policy,
            relay_urls=relay_urls,
            discovery_policy=discovery_policy,
            resources=resources,
            ownership=ownership,
        )

    def to_dict(self) -> dict[str, Any]:
        state_root = self.layout.root.parent.parent
        return {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "kind": "ipfs-kit-iroh-service",
            "instance": self.instance,
            "enabled": self.enabled,
            "release_bundle": self.release_bundle,
            "protocol_version": self.protocol_version,
            "state_root": str(state_root),
            "rpc": {"kind": "local", "endpoint": self.rpc_endpoint},
            "network": {
                "endpoint_bind": list(self.endpoint_bind),
                "relay": {"policy": self.relay_policy, "urls": list(self.relay_urls)},
                "discovery": {"policy": self.discovery_policy},
            },
            "identity": {"node_identity_ref": self.node_identity_ref},
            "resources": self.resources.to_dict(),
            "logging": {
                "log_path": str(self.layout.service_log_path),
                "health_receipt_path": str(self.layout.health_receipt_path),
                "crash_receipt_path": str(self.layout.crash_receipt_path),
            },
            "ownership": self.ownership.to_dict(),
        }


def _validate_rpc_endpoint(value: Any) -> str:
    endpoint = _string(value, "rpc.endpoint")
    if endpoint.startswith("unix:///"):
        path = endpoint.removeprefix("unix://")
        _absolute_path(path, "rpc.endpoint")
        return endpoint
    if _NPIPE_RE.fullmatch(endpoint):
        return endpoint
    raise _invalid("rpc.endpoint must be an absolute Unix socket URI or local named pipe")


def _validate_bind(value: Any) -> str:
    bind = _string(value, "network.endpoint_bind item")
    if any(char in bind for char in "/?#@"):
        raise _invalid("endpoint bind must use host:port syntax")
    match = _BIND_RE.fullmatch(bind)
    if match is None or int(match.group(1)) > 65535:
        raise _invalid("endpoint bind has an invalid host or port")
    return bind


def _validate_relay_url(value: Any) -> str:
    url = _string(value, "network.relay.urls item")
    try:
        parsed = urlsplit(url)
    except ValueError:
        raise _invalid("relay URL is malformed") from None
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise _invalid("relay URL must be an HTTPS URL without credentials")
    if parsed.query or parsed.fragment:
        raise _invalid("relay URL must not contain a query or fragment")
    try:
        if parsed.port is not None and not (1 <= parsed.port <= 65535):
            raise ValueError
    except ValueError:
        raise _invalid("relay URL has an invalid port") from None
    return url


def default_config(
    instance: str = DEFAULT_INSTANCE,
    *,
    state_root: str | os.PathLike[str] | None = None,
    enabled: bool = False,
    node_identity_ref: str | None = None,
) -> IrohServiceConfig:
    return IrohServiceConfig.default(
        instance,
        state_root=state_root,
        enabled=enabled,
        node_identity_ref=node_identity_ref,
    )


def parse_config(
    raw: Mapping[str, Any], *, state_root: str | os.PathLike[str] | None = None
) -> IrohServiceConfig:
    return IrohServiceConfig.from_dict(raw, state_root=state_root)


def loads_config(
    text: str, *, state_root: str | os.PathLike[str] | None = None
) -> IrohServiceConfig:
    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except IrohInvalidConfigError:
        raise
    except (json.JSONDecodeError, UnicodeError, TypeError) as exc:
        raise _invalid("configuration is not valid UTF-8 JSON") from exc
    return IrohServiceConfig.from_dict(value, state_root=state_root)


def load_config(
    path: str | os.PathLike[str], *, state_root: str | os.PathLike[str] | None = None
) -> IrohServiceConfig:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise _invalid("cannot read Iroh service configuration") from exc
    return loads_config(text, state_root=state_root)


def _json_bytes(document: Mapping[str, Any]) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        # Directory fsync is unavailable on some Windows/filesystem pairs.
        if os.name == "nt":
            return
        raise
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _assert_no_symlink_components(path: Path) -> None:
    """Reject existing symlinks in a state path before sensitive file I/O."""

    current = Path(path.anchor)
    for component in path.parts[1:] if path.is_absolute() else path.parts:
        current /= component
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise _invalid("cannot inspect Iroh state path") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise _invalid("Iroh state path must not contain symlinks")


def _assert_private_directory(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise _invalid("cannot inspect Iroh state directory") from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise _invalid("Iroh state path is not a real directory")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise _invalid("Iroh state directory is not owner-only")


def atomic_write_config(
    path: str | os.PathLike[str], config: IrohServiceConfig | Mapping[str, Any]
) -> None:
    """Validate and atomically persist a private configuration document."""

    validated = (
        IrohServiceConfig.from_dict(config.to_dict())
        if isinstance(config, IrohServiceConfig)
        else IrohServiceConfig.from_dict(config)
    )
    target = Path(path)
    if not target.is_absolute():
        target = Path(os.path.abspath(os.fspath(target)))
    payload = _json_bytes(validated.to_dict())
    temporary: Path | None = None
    descriptor: int | None = None
    try:
        _assert_no_symlink_components(target)
        target.parent.mkdir(mode=DIRECTORY_MODE, parents=True, exist_ok=True)
        _assert_private_directory(target.parent)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        temporary = Path(temporary_name)
        os.fchmod(descriptor, FILE_MODE)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        temporary = None
        target.chmod(FILE_MODE)
        _fsync_directory(target.parent)
    except IrohInvalidConfigError:
        raise
    except BaseException as exc:
        raise _invalid("cannot atomically write Iroh service configuration") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def _atomic_write_json(path: Path, document: Mapping[str, Any]) -> None:
    target = path
    temporary: Path | None = None
    descriptor: int | None = None
    try:
        _assert_no_symlink_components(target)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        temporary = Path(temporary_name)
        os.fchmod(descriptor, FILE_MODE)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(_json_bytes(document))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        temporary = None
        path.chmod(FILE_MODE)
        _fsync_directory(path.parent)
    except BaseException as exc:
        if isinstance(exc, IrohInvalidConfigError):
            raise
        raise _invalid("cannot atomically write Iroh state metadata") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def ensure_state_layout(config: IrohServiceConfig | IrohStateLayout) -> IrohStateLayout:
    """Create and verify one isolated owner-only state tree.

    Existing symlinks, non-directories, or an ownership marker naming another
    instance fail closed. No credential is read or written here.
    """

    layout = config if isinstance(config, IrohStateLayout) else config.layout
    policy = OwnershipPolicy() if isinstance(config, IrohStateLayout) else config.ownership
    _assert_no_symlink_components(layout.root)
    # Path.mkdir applies ``mode`` only to the leaf. Create this shared parent
    # explicitly so a new state root never leaves an enumerable instances dir.
    instances_dir = layout.root.parent
    try:
        instances_dir.mkdir(mode=policy.directory_mode, parents=True, exist_ok=True)
        if stat.S_IMODE(instances_dir.lstat().st_mode) & 0o077:
            instances_dir.chmod(policy.directory_mode)
        for directory in layout.directories:
            directory.mkdir(mode=policy.directory_mode, parents=True, exist_ok=True)
            _assert_private_directory(directory)
            metadata = directory.stat(follow_symlinks=False)
            if policy.uid is not None and metadata.st_uid != policy.uid:
                raise _invalid("Iroh state directory has the wrong owner")
            if policy.gid is not None and metadata.st_gid != policy.gid:
                raise _invalid("Iroh state directory has the wrong group")
    except IrohInvalidConfigError:
        raise
    except OSError as exc:
        raise _invalid("cannot create Iroh state layout") from exc

    marker = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "kind": "ipfs-kit-iroh-instance",
        "instance": layout.instance,
    }
    if layout.owner_path.exists() or layout.owner_path.is_symlink():
        if layout.owner_path.is_symlink():
            raise _invalid("Iroh instance ownership marker is a symlink")
        try:
            existing = json.loads(
                layout.owner_path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
            )
        except IrohInvalidConfigError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise _invalid("Iroh instance ownership marker is invalid") from exc
        if existing != marker:
            raise IrohConflictError(
                "Iroh state directory is already assigned to another instance",
                operation="config",
            )
        if stat.S_IMODE(layout.owner_path.stat(follow_symlinks=False).st_mode) & 0o077:
            layout.owner_path.chmod(FILE_MODE)
    else:
        _atomic_write_json(layout.owner_path, marker)
    return layout


def _split_bind(value: str) -> tuple[str, int]:
    host, port = value.rsplit(":", 1)
    return host.strip("[]").lower(), int(port)


def _binds_conflict(first: str, second: str) -> bool:
    first_host, first_port = _split_bind(first)
    second_host, second_port = _split_bind(second)
    if first_port != second_port:
        return False
    first_ipv6 = ":" in first_host
    second_ipv6 = ":" in second_host
    if first_ipv6 != second_ipv6:
        return False
    wildcard = "::" if first_ipv6 else "0.0.0.0"
    return first_host == second_host or first_host == wildcard or second_host == wildcard


def validate_instance_isolation(configs: Iterable[IrohServiceConfig]) -> None:
    """Reject state, RPC, or listener collisions across enabled instances."""

    seen_names: set[str] = set()
    seen_paths: dict[Path, str] = {}
    seen_rpc: dict[str, str] = {}
    seen_binds: dict[str, str] = {}
    for config in configs:
        if config.instance in seen_names:
            raise IrohConflictError("duplicate Iroh instance name", operation="config")
        seen_names.add(config.instance)
        if not config.enabled:
            continue

        for path in config.layout.directories:
            canonical = Path(os.path.abspath(os.fspath(path)))
            for existing, owner in seen_paths.items():
                if owner != config.instance and (
                    canonical == existing
                    or canonical in existing.parents
                    or existing in canonical.parents
                ):
                    raise IrohConflictError(
                        f"Iroh instances {owner!r} and {config.instance!r} have overlapping state paths",
                        operation="config",
                    )
            seen_paths[canonical] = config.instance

        rpc = config.rpc_endpoint
        if rpc in seen_rpc:
            raise IrohConflictError("enabled Iroh instances share an RPC endpoint", operation="config")
        seen_rpc[rpc] = config.instance
        for bind in config.endpoint_bind:
            if bind.endswith(":0"):
                continue
            if any(_binds_conflict(bind, existing) for existing in seen_binds):
                raise IrohConflictError(
                    "enabled Iroh instances have colliding endpoint binds",
                    operation="config",
                )
            seen_binds[bind] = config.instance


def migrate_config(
    raw: Mapping[str, Any], *, state_root: str | os.PathLike[str] | None = None
) -> dict[str, Any]:
    """Convert the documented legacy (version 0) shape to schema version 1.

    Migration is pure and never converts inline credential material into a
    reference. Current documents are normalized after validation; unknown
    future versions are rejected.
    """

    source = _expect_mapping(copy.deepcopy(raw), "configuration")
    _reject_inline_secrets(source)
    version = source.get("schema_version", source.get("version", 0))
    if not isinstance(version, bool) and version == CONFIG_SCHEMA_VERSION:
        return IrohServiceConfig.from_dict(source, state_root=state_root).to_dict()
    if isinstance(version, bool) or version != 0:
        raise IrohUnsupportedVersionError(
            "unsupported Iroh service configuration version", operation="config"
        )
    _only(
        source,
        {
            "schema_version", "version", "instance", "name", "state_dir",
            "enabled", "node_identity_ref", "node_key_ref", "endpoint_bind",
            "bind", "relay_mode", "relay_url", "discovery", "resource_limits",
            "uid", "gid",
        },
        "legacy configuration",
    )
    instance = source.get("instance", source.get("name", DEFAULT_INSTANCE))
    selected_root = state_root if state_root is not None else source.get("state_dir")
    identity_ref = source.get("node_identity_ref", source.get("node_key_ref"))
    if identity_ref is None:
        raise _invalid("legacy configuration requires node_identity_ref")
    config = IrohServiceConfig.default(
        instance,
        state_root=selected_root,
        enabled=source.get("enabled", False),
        node_identity_ref=identity_ref,
    )
    document = config.to_dict()
    bind = source.get("endpoint_bind", source.get("bind"))
    if bind is not None:
        document["network"]["endpoint_bind"] = bind if isinstance(bind, list) else [bind]
    relay_url = source.get("relay_url")
    document["network"]["relay"] = {
        "policy": source.get("relay_mode", "default"),
        "urls": [] if relay_url is None else ([relay_url] if isinstance(relay_url, str) else relay_url),
    }
    discovery = source.get("discovery", "local")
    if isinstance(discovery, bool):
        discovery = "local" if discovery else "disabled"
    document["network"]["discovery"] = {"policy": discovery}
    if "resource_limits" in source:
        document["resources"].update(
            _expect_mapping(source["resource_limits"], "resource_limits")
        )
    document["ownership"]["uid"] = source.get("uid")
    document["ownership"]["gid"] = source.get("gid")
    return IrohServiceConfig.from_dict(document).to_dict()


def migrate_config_file(
    path: str | os.PathLike[str],
    *,
    state_root: str | os.PathLike[str] | None = None,
    backup: bool = False,
) -> IrohServiceConfig:
    """Validate, migrate, and atomically replace a JSON configuration file."""

    target = Path(path)
    try:
        original = target.read_bytes()
        source = json.loads(original.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except IrohInvalidConfigError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _invalid("cannot read legacy Iroh service configuration") from exc

    migrated = migrate_config(source, state_root=state_root)
    validated = IrohServiceConfig.from_dict(migrated)
    if backup:
        backup_path = target.with_suffix(target.suffix + ".v0.bak")
        try:
            descriptor = os.open(backup_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, FILE_MODE)
        except FileExistsError as exc:
            raise IrohConflictError("migration backup already exists", operation="config") from exc
        except OSError as exc:
            raise _invalid("cannot create migration backup") from exc
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(original)
                stream.flush()
                os.fsync(stream.fileno())
            backup_path.chmod(FILE_MODE)
            _fsync_directory(backup_path.parent)
        except BaseException:
            try:
                backup_path.unlink()
            except OSError:
                pass
            raise
    atomic_write_config(target, validated)
    return validated


ServiceConfig = IrohServiceConfig
StateLayout = IrohStateLayout
load_service_config = load_config
save_config = atomic_write_config
migrate_service_config = migrate_config

__all__ = [
    "CONFIG_SCHEMA_VERSION", "DEFAULT_RELEASE_BUNDLE", "DEFAULT_PROTOCOL_VERSION",
    "DEFAULT_INSTANCE", "DIRECTORY_MODE", "FILE_MODE", "IrohStateLayout",
    "IrohServiceConfig", "ResourceLimits", "OwnershipPolicy", "ServiceConfig",
    "StateLayout", "default_state_root", "validate_instance_name", "default_config",
    "parse_config", "loads_config", "load_config", "load_service_config",
    "atomic_write_config", "save_config", "ensure_state_layout",
    "validate_instance_isolation", "migrate_config", "migrate_service_config",
    "migrate_config_file",
]
