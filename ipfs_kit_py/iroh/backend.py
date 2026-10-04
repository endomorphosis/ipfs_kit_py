"""Validated named-backend configuration plugin for Iroh."""

from __future__ import annotations

import copy
import inspect
import json
import math
import os
import re
from collections.abc import Mapping
from importlib.resources import files
from pathlib import Path
from typing import Any

from ..backend_registry import BackendConfigError, ensure_json_compatible, validate_backend_name
from .client import redact


IROH_BACKEND_SCHEMA_VERSION = 1
_HEX32_RE = re.compile(r"^[a-f0-9]{64}$")
_INSTANCE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_SECRET_REF_RE = re.compile(
    r"^secretref:(?:secure-config|enhanced-secrets|credential-manager|environment):"
    r"[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$"
)
_SECRET_KEY_RE = re.compile(
    r"(?:^|_)(?:secret|token|ticket|password|passwd|private_key|node_key|"
    r"write_capability|identity_key)(?:$|_)",
    re.IGNORECASE,
)

_TOP_LEVEL = {
    "$schema",
    "schema_version",
    "name",
    "type",
    "enabled",
    "namespace",
    "service",
    "credentials",
    "timeouts",
    "sync",
}


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise BackendConfigError(f"{label} must be an object")
    return dict(value)


def _only(value: Mapping[str, Any], fields: set[str], label: str) -> None:
    unknown = set(value) - fields
    if unknown:
        raise BackendConfigError(
            f"{label} contains unknown settings: "
            + ", ".join(repr(item) for item in sorted(unknown))
        )


def _required(value: Mapping[str, Any], fields: set[str], label: str) -> None:
    missing = fields - set(value)
    if missing:
        raise BackendConfigError(
            f"{label} is missing required settings: "
            + ", ".join(repr(item) for item in sorted(missing))
        )


def _scan_inline_secrets(value: Any, path: str = "config") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            if _SECRET_KEY_RE.search(str(key)):
                if str(key).endswith("_ref") and isinstance(item, str) and _SECRET_REF_RE.fullmatch(item):
                    continue
                raise BackendConfigError(f"{child} must contain an approved secret reference, not secret material")
            _scan_inline_secrets(item, child)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_inline_secrets(item, f"{path}[{index}]")


def _secret_ref(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SECRET_REF_RE.fullmatch(value):
        raise BackendConfigError(f"{label} must be an approved secretref reference")
    return value


def _local_endpoint(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise BackendConfigError("service.rpc_endpoint must be a local endpoint URI")
    if value.startswith("unix:///"):
        path = value.removeprefix("unix://")
        if not os.path.isabs(path) or "\x00" in path or "\n" in path or "\r" in path:
            raise BackendConfigError("service.rpc_endpoint Unix path must be absolute")
        return value
    if re.fullmatch(r"npipe:////\./pipe/[A-Za-z0-9._-]{1,128}", value):
        return value
    raise BackendConfigError("service.rpc_endpoint must use an absolute Unix socket or local named pipe")


def _timeout(value: Any, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BackendConfigError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result) or result <= 0 or result > 3600:
        raise BackendConfigError(f"{label} must be greater than zero and at most 3600 seconds")
    return value


def validate_iroh_backend_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a schema-version-1 backend document."""

    value = ensure_json_compatible(config)
    _scan_inline_secrets(value)
    _only(value, _TOP_LEVEL, "Iroh backend configuration")
    _required(value, _TOP_LEVEL - {"$schema"}, "Iroh backend configuration")
    if value["schema_version"] != IROH_BACKEND_SCHEMA_VERSION or isinstance(value["schema_version"], bool):
        raise BackendConfigError("Iroh backend schema_version must be 1")
    validate_backend_name(value["name"])
    if value["type"] != "iroh":
        raise BackendConfigError("Iroh backend type must be 'iroh'")
    if not isinstance(value["enabled"], bool):
        raise BackendConfigError("enabled must be a boolean")
    if "$schema" in value and not isinstance(value["$schema"], str):
        raise BackendConfigError("$schema must be a URI-reference string")

    namespace = _mapping(value["namespace"], "namespace")
    _only(namespace, {"id", "access"}, "namespace")
    _required(namespace, {"id", "access"}, "namespace")
    if not isinstance(namespace["id"], str) or not _HEX32_RE.fullmatch(namespace["id"]):
        raise BackendConfigError("namespace.id must be a lowercase 32-byte hexadecimal Iroh ID")
    if namespace["access"] not in {"read-only", "read-write"}:
        raise BackendConfigError("namespace.access must be 'read-only' or 'read-write'")

    service = _mapping(value["service"], "service")
    _only(service, {"instance", "managed", "rpc_endpoint"}, "service")
    _required(service, {"instance", "managed", "rpc_endpoint"}, "service")
    if not isinstance(service["instance"], str) or not _INSTANCE_RE.fullmatch(service["instance"]):
        raise BackendConfigError("service.instance is not a valid named Iroh instance")
    if not isinstance(service["managed"], bool):
        raise BackendConfigError("service.managed must be a boolean")
    service["rpc_endpoint"] = _local_endpoint(service["rpc_endpoint"])

    credentials = _mapping(value["credentials"], "credentials")
    credential_fields = {"node_key_ref", "write_capability_ref", "read_ticket_ref"}
    _only(credentials, credential_fields, "credentials")
    _required(credentials, {"node_key_ref"}, "credentials")
    for field, reference in credentials.items():
        credentials[field] = _secret_ref(reference, f"credentials.{field}")
    if namespace["access"] == "read-write" and "write_capability_ref" not in credentials:
        raise BackendConfigError("read-write Iroh backends require credentials.write_capability_ref")

    timeouts = _mapping(value["timeouts"], "timeouts")
    timeout_fields = {"connect_seconds", "operation_seconds", "shutdown_seconds"}
    _only(timeouts, timeout_fields, "timeouts")
    _required(timeouts, timeout_fields, "timeouts")
    for field in timeout_fields:
        timeouts[field] = _timeout(timeouts[field], f"timeouts.{field}")

    sync = _mapping(value["sync"], "sync")
    sync_fields = {"enabled", "on_open", "read_consistency", "conflict_policy"}
    _only(sync, sync_fields, "sync")
    _required(sync, sync_fields, "sync")
    if not isinstance(sync["enabled"], bool) or not isinstance(sync["on_open"], bool):
        raise BackendConfigError("sync.enabled and sync.on_open must be booleans")
    if sync["read_consistency"] not in {"local", "synchronized"}:
        raise BackendConfigError("sync.read_consistency must be 'local' or 'synchronized'")
    if sync["conflict_policy"] != "fail":
        raise BackendConfigError("sync.conflict_policy must be 'fail'")
    if sync["read_consistency"] == "synchronized" and not sync["enabled"]:
        raise BackendConfigError("synchronized reads require sync.enabled=true")

    result = copy.deepcopy(value)
    result["namespace"] = namespace
    result["service"] = service
    result["credentials"] = credentials
    result["timeouts"] = timeouts
    result["sync"] = sync
    return result


def migrate_iroh_backend_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Migrate the supported legacy flat named-backend shape to version 1.

    Migration never resolves or manufactures credential material.  Legacy
    documents must already use approved references.
    """

    source = ensure_json_compatible(config)
    _scan_inline_secrets(source)
    version = source.get("schema_version")
    if version == IROH_BACKEND_SCHEMA_VERSION and not isinstance(version, bool):
        return validate_iroh_backend_config(source)
    if version not in (None, 0) or isinstance(version, bool):
        raise BackendConfigError(f"unsupported Iroh backend schema_version: {version!r}")

    # A nearly-current legacy document may only lack its version marker.
    if {"namespace", "service", "credentials"}.issubset(source):
        migrated = copy.deepcopy(source)
        migrated["schema_version"] = 1
        migrated.setdefault("enabled", True)
        migrated.setdefault(
            "timeouts",
            {"connect_seconds": 10, "operation_seconds": 300, "shutdown_seconds": 15},
        )
        migrated.setdefault(
            "sync",
            {"enabled": False, "on_open": False, "read_consistency": "local", "conflict_policy": "fail"},
        )
        return validate_iroh_backend_config(migrated)

    allowed = {
        "$schema", "schema_version", "name", "type", "enabled", "namespace_id",
        "namespace", "access", "read_only", "instance", "managed", "endpoint",
        "rpc_endpoint", "node_key_ref", "write_capability_ref", "read_ticket_ref",
        "connect_timeout", "operation_timeout", "shutdown_timeout", "sync_enabled",
        "sync_on_open", "read_consistency", "conflict_policy",
    }
    _only(source, allowed, "legacy Iroh backend configuration")
    _required(source, {"name", "type"}, "legacy Iroh backend configuration")
    namespace_id = source.get("namespace_id", source.get("namespace"))
    endpoint = source.get("rpc_endpoint", source.get("endpoint"))
    node_key_ref = source.get("node_key_ref")
    if namespace_id is None or endpoint is None or node_key_ref is None:
        raise BackendConfigError(
            "legacy Iroh config requires namespace_id, rpc_endpoint, and node_key_ref"
        )
    access = source.get("access")
    if access is None:
        access = "read-only" if source.get("read_only", False) else "read-write"
    credentials = {"node_key_ref": node_key_ref}
    for field in ("write_capability_ref", "read_ticket_ref"):
        if source.get(field) is not None:
            credentials[field] = source[field]
    migrated = {
        "schema_version": 1,
        "name": source["name"],
        "type": source["type"],
        "enabled": source.get("enabled", True),
        "namespace": {"id": namespace_id, "access": access},
        "service": {
            "instance": source.get("instance", source["name"]),
            "managed": source.get("managed", True),
            "rpc_endpoint": endpoint,
        },
        "credentials": credentials,
        "timeouts": {
            "connect_seconds": source.get("connect_timeout", 10),
            "operation_seconds": source.get("operation_timeout", 300),
            "shutdown_seconds": source.get("shutdown_timeout", 15),
        },
        "sync": {
            "enabled": source.get("sync_enabled", False),
            "on_open": source.get("sync_on_open", False),
            "read_consistency": source.get("read_consistency", "local"),
            "conflict_policy": source.get("conflict_policy", "fail"),
        },
    }
    if "$schema" in source:
        migrated["$schema"] = source["$schema"]
    return validate_iroh_backend_config(migrated)


class IrohBackendPlugin:
    """Registry plugin for the versioned Iroh filesystem backend."""

    type_name = "iroh"
    schema_version = IROH_BACKEND_SCHEMA_VERSION

    def validate(self, config: Mapping[str, Any]) -> dict[str, Any]:
        return validate_iroh_backend_config(config)

    def migrate(self, config: Mapping[str, Any]) -> dict[str, Any]:
        return migrate_iroh_backend_config(config)

    def schema(self) -> dict[str, Any]:
        resource = files("ipfs_kit_py.resources").joinpath("iroh-backend-config.schema.json")
        return json.loads(resource.read_text(encoding="utf-8"))

    def capabilities(self, config: Mapping[str, Any]) -> dict[str, Any]:
        value = self.validate(config)
        writable = value["namespace"]["access"] == "read-write"
        return {
            "protocols": ["iroh", "iroh+blob"],
            "read": True,
            "write": writable,
            "list": True,
            "delete": writable,
            "copy": writable,
            "move": writable,
            "transactions": writable,
            "async": True,
            "immutable_blobs": True,
            "sync": bool(value["sync"]["enabled"]),
            # Keep provider-neutral capability names from implying global
            # transaction or rename semantics that Iroh does not provide.
            "operation_limits": {
                "transactions": "single-namespace",
                "move": "not-atomic-cross-namespace",
            },
            "schema_version": IROH_BACKEND_SCHEMA_VERSION,
        }

    def health(self, config: Mapping[str, Any]) -> dict[str, Any]:
        value = self.validate(config)
        endpoint = value["service"]["rpc_endpoint"]
        if not value["enabled"]:
            return {
                "healthy": True,
                "ready": False,
                "status": "disabled",
                "certification_status": "blocked",
                "endpoint": endpoint,
                "managed": value["service"]["managed"],
            }
        reachable = False
        if endpoint.startswith("unix:///"):
            socket_path = Path(endpoint.removeprefix("unix://"))
            reachable = socket_path.exists() and not socket_path.is_dir()
        elif os.name == "nt":
            # Existence probing named pipes can block; RPC health owns that job.
            reachable = True
        return {
            "healthy": reachable,
            "ready": reachable,
            "status": "available" if reachable else "unavailable",
            "certification_status": "blocked" if not reachable else "unverified",
            "endpoint": endpoint,
            "managed": value["service"]["managed"],
        }

    async def certify_live_service(
        self, config: Mapping[str, Any], *, client: Any = None, client_factory: Any = None
    ) -> dict[str, Any]:
        """Prove a local sidecar by RPC, not merely by a socket pathname.

        Construction is intentionally lazy; this is the explicit operation that
        connects, performs health and version/capability negotiation, and fails
        closed as ``blocked`` when no pinned sidecar is available.
        """
        value = self.validate(config)
        endpoint = value["service"]["rpc_endpoint"]
        if not value["enabled"]:
            return {"status": "blocked", "healthy": False, "reason": "Iroh backend is disabled"}
        try:
            if client is None:
                if client_factory is not None:
                    client = client_factory()
                else:
                    from .client import IrohRuntimeClient
                    client = IrohRuntimeClient(endpoint=endpoint, timeout=value["timeouts"]["operation_seconds"])
            timeout = value["timeouts"]["connect_seconds"]
            health = client.health(timeout=timeout)
            if inspect.isawaitable(health):
                health = await health
            negotiated = client.negotiate(timeout=timeout)
            if inspect.isawaitable(negotiated):
                await negotiated
            return {
                "status": "passed", "healthy": True, "provider": "iroh-local-rpc",
                "endpoint": endpoint, "health": redact(dict(health)),
                # Iroh moves may be copy/remove and transactions are namespace scoped.
                "limitations": {"transactions": "single-namespace", "move": "not-atomic-cross-namespace"},
            }
        except Exception as exc:
            # The client redactor protects structured values and common URI
            # forms.  Exception text is unstructured, so also mask familiar
            # key=value credentials before exposing a diagnostic receipt.
            reason = re.sub(
                r"(?i)(\b(?:secret|token|ticket|password|credential|capability|authorization)[^=:\s]*[=:]\s*)[^\s,&]+",
                r"\1<redacted>",
                str(redact(str(exc))),
            )
            return {
                "status": "blocked", "healthy": False, "provider": "iroh-local-rpc",
                "endpoint": endpoint, "reason": reason,
            }

    def create_filesystem(
        self,
        config: Mapping[str, Any],
        *,
        client: Any = None,
        client_factory: Any = None,
        **storage_options: Any,
    ) -> Any:
        """Create an inert filesystem; connection remains lazy until first I/O."""

        value = self.validate(config)
        if client is None and client_factory is None:
            endpoint = value["service"]["rpc_endpoint"]
            timeout = value["timeouts"]["operation_seconds"]

            def client_factory() -> Any:
                from .client import IrohRuntimeClient

                return IrohRuntimeClient(endpoint=endpoint, timeout=timeout)

        from ..iroh_fsspec import IrohFileSystem

        return IrohFileSystem(
            client=client,
            client_factory=client_factory,
            read_only=value["namespace"]["access"] == "read-only",
            **storage_options,
        )


__all__ = [
    "IROH_BACKEND_SCHEMA_VERSION",
    "IrohBackendPlugin",
    "migrate_iroh_backend_config",
    "validate_iroh_backend_config",
]
