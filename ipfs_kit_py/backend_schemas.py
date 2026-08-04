"""Dashboard schemas derived from the canonical backend inventory.

``SCHEMAS`` contains precisely the registry's active backend types.  Surfaces
which used to have a form without an implementation remain available as
explicitly disabled records in ``EXCLUDED_SCHEMAS`` instead of being advertised
as usable storage backends.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from .backends.spec import (
    ACTIVE_BACKEND_SPECS,
    EXCLUDED_BACKEND_SPECS,
    BackendSpec,
    normalize_backend_type,
)


_DISPLAY_NAMES: Mapping[str, str] = {
    "cluster": "Cluster",
    "digitalocean": "DigitalOcean",
    "estuary": "Estuary",
    "filecoin": "Filecoin",
    "filecoin_pin": "Filecoin Pin",
    "filesystem": "Filesystem",
    "ftp": "FTP",
    "gdrive": "Google Drive",
    "github": "GitHub",
    "huggingface": "HuggingFace",
    "ipfs": "IPFS",
    "ipfs_cluster": "IPFS Cluster",
    "ipfs_cluster_follow": "IPFS Cluster Follow",
    "iroh": "Iroh",
    "lassie": "Lassie",
    "local": "Local",
    "local_fs": "Local Filesystem",
    "local_storage": "Local Storage",
    "minio": "MinIO",
    "parquet": "Parquet",
    "s3": "S3",
    "sshfs": "SSHFS",
    "storacha": "Storacha",
    "arrow": "Arrow",
    "lotus": "Lotus",
    "saturn": "Saturn",
    "synapse": "Synapse",
}


# Field details are presentation metadata only.  The surrounding envelope is
# generated below, so adding a backend cannot accidentally drift from aliases,
# capabilities, support tier, or availability.
_FORM_FIELDS: Mapping[str, Mapping[str, Mapping[str, Any]]] = {
    "digitalocean": {"token": {"type": "password", "required": True}},
    "estuary": {"api_key": {"type": "password", "required": True}},
    "filecoin": {
        "lotus_rpc_url": {"type": "text", "required": True},
        "lotus_token": {"type": "password", "required": True},
    },
    "ftp": {
        "host": {"type": "text", "required": True},
        "username": {"type": "text", "required": True},
        "password": {"type": "password", "required": True},
        "port": {"type": "number", "default": 21},
        "use_tls": {"type": "checkbox", "default": False},
        "passive": {"type": "checkbox", "default": True},
        "remote_path": {"type": "text", "default": "/"},
    },
    "gdrive": {
        "credentials_path": {"type": "text", "required": True},
        "default_folder_id": {"type": "text", "required": False},
    },
    "github": {
        "token": {"type": "password", "required": True},
        "default_org": {"type": "text", "required": False},
        "default_repo": {"type": "text", "required": False},
    },
    "huggingface": {
        "token": {"type": "password", "required": True},
        "default_org": {"type": "text", "required": False},
        "cache_dir": {"type": "text", "required": False},
    },
    "ipfs": {
        "api_endpoint": {
            "type": "text",
            "required": True,
            "default": "/ip4/127.0.0.1/tcp/5001",
        },
    },
    "ipfs_cluster": {
        "endpoint": {"type": "text", "required": True},
        "username": {"type": "text", "required": False},
        "password": {"type": "password", "required": False},
    },
    "ipfs_cluster_follow": {
        "name": {"type": "text", "required": True},
        "template": {"type": "text", "required": False},
        "trusted_peers": {"type": "text", "required": False},
    },
    "minio": {
        "endpoint": {"type": "text", "required": True},
        "access_key": {"type": "password", "required": True},
        "secret_key": {"type": "password", "required": True},
    },
    "parquet": {
        "storage_path": {"type": "text", "required": True},
        "compression": {
            "type": "select",
            "choices": ["snappy", "gzip", "brotli", "lz4"],
            "default": "snappy",
        },
        "batch_size": {"type": "number", "default": 10000},
    },
    "s3": {
        "access_key": {"type": "password", "required": True},
        "secret_key": {"type": "password", "required": True},
        "region": {"type": "text", "required": True},
        "endpoint": {"type": "text", "required": False},
    },
    "sshfs": {
        "hostname": {"type": "text", "required": True},
        "username": {"type": "text", "required": True},
        "port": {"type": "number", "default": 22},
        "password": {"type": "password", "required": False},
        "private_key": {"type": "text", "required": False},
        "remote_path": {"type": "text", "default": "/tmp/ipfs_kit"},
    },
    "storacha": {
        "api_key": {"type": "password", "required": True},
        "endpoint": {"type": "text", "required": False},
    },
    "arrow": {
        "memory_pool": {
            "type": "select",
            "choices": ["system", "jemalloc"],
            "default": "system",
        },
        "thread_count": {"type": "number", "required": False},
    },
    "lotus": {
        "endpoint": {"type": "text", "required": True},
        "token": {"type": "password", "required": True},
    },
}


def _schema(spec: BackendSpec) -> dict[str, Any]:
    names = list(spec.names)
    return {
        "name": _DISPLAY_NAMES[spec.type_name],
        "type": spec.type_name,
        "aliases": list(spec.aliases),
        "fields": copy.deepcopy(_FORM_FIELDS.get(spec.type_name, {})),
        "available": not spec.is_excluded,
        "capabilities": sorted(capability.value for capability in spec.capabilities),
        "health_contract": spec.health_contract,
        "secret_fields": list(spec.secret_fields),
        "runtime_factory": spec.runtime_factory,
        "support_tier": spec.support_tier.value,
        "support_tier_source": "explicit-backend-spec",
        "cli_names": names,
        "mcp_names": names,
        "documentation_names": names,
        "excluded_reason": spec.excluded_reason,
    }


SCHEMAS: dict[str, dict[str, Any]] = {
    name: _schema(spec) for name, spec in ACTIVE_BACKEND_SPECS.items()
}
EXCLUDED_SCHEMAS: dict[str, dict[str, Any]] = {
    name: _schema(spec) for name, spec in EXCLUDED_BACKEND_SPECS.items()
}


def get_backend_schema(
    type_name: str, *, include_excluded: bool = True
) -> dict[str, Any] | None:
    """Return a fresh schema record for a canonical name or declared alias."""

    canonical = normalize_backend_type(type_name, include_excluded=include_excluded)
    if canonical is None:
        return None
    schema = SCHEMAS.get(canonical)
    if schema is None and include_excluded:
        schema = EXCLUDED_SCHEMAS.get(canonical)
    return copy.deepcopy(schema) if schema is not None else None


__all__ = ["EXCLUDED_SCHEMAS", "SCHEMAS", "get_backend_schema"]
