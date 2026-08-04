"""Canonical backend inventory and contracts.

The registry, configuration schemas, and user-facing names deliberately share
this small inventory.  A backend being listed here is not, by itself, evidence
that it can service storage requests: that is an explicit capability and
runtime-factory contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, Iterable, Mapping


class BackendCapability(str, Enum):
    """Operations a backend has explicitly declared."""

    CONFIGURATION = "configuration"
    HEALTH = "health"
    RUNTIME_FACTORY = "runtime_factory"
    STORAGE = "storage"


class BackendSupportTier(str, Enum):
    """Support level assigned by the inventory, never inferred at runtime."""

    PRODUCTION = "production"
    CONDITIONAL = "conditional"
    CONFIGURATION_ONLY = "configuration-only"
    EXPERIMENTAL = "experimental"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class BackendSpec:
    """One backend's canonical name and its public contract.

    ``runtime_factory`` names an optional operation on the registered plugin.
    Its presence is meaningful only when ``RUNTIME_FACTORY`` is also declared
    in ``capabilities``.  This keeps configuration-only legacy plugins from
    being mistaken for usable storage implementations.
    """

    type_name: str
    aliases: tuple[str, ...]
    capabilities: frozenset[BackendCapability]
    support_tier: BackendSupportTier
    health_contract: str
    secret_fields: tuple[str, ...] = ()
    runtime_factory: str | None = None
    excluded_reason: str | None = None

    @property
    def names(self) -> tuple[str, ...]:
        """All accepted public spellings, in deterministic order."""

        return (self.type_name, *self.aliases)

    @property
    def is_excluded(self) -> bool:
        return self.excluded_reason is not None

    def supports(self, capability: BackendCapability) -> bool:
        return capability in self.capabilities


def _legacy(
    type_name: str,
    *aliases: str,
    secret_fields: tuple[str, ...] = (),
) -> BackendSpec:
    return BackendSpec(
        type_name=type_name,
        aliases=aliases,
        capabilities=frozenset(
            {BackendCapability.CONFIGURATION, BackendCapability.HEALTH}
        ),
        support_tier=BackendSupportTier.CONFIGURATION_ONLY,
        health_contract="not-probed",
        secret_fields=secret_fields,
    )


# These are deliberately canonical, machine-facing names.  Alternate spellings
# are listed individually rather than applying a lossy hyphen/underscore rule:
# doing so makes name collisions visible at import time.
_ACTIVE_SPECS: tuple[BackendSpec, ...] = (
    _legacy("cluster"),
    _legacy("digitalocean", "digital-ocean", secret_fields=("token",)),
    _legacy("estuary", secret_fields=("api_key", "token")),
    _legacy("filecoin"),
    _legacy("filecoin_pin", "filecoin-pin", secret_fields=("api_key", "token")),
    _legacy("filesystem"),
    _legacy("ftp", secret_fields=("password",)),
    _legacy("gdrive", "g-drive", "google-drive", "google_drive", secret_fields=("token",)),
    _legacy("github", secret_fields=("token",)),
    _legacy("huggingface", "hugging-face", secret_fields=("token",)),
    _legacy("ipfs"),
    _legacy("ipfs_cluster", "ipfs-cluster"),
    _legacy("ipfs_cluster_follow", "ipfs-cluster-follow"),
    _legacy("lassie"),
    _legacy("local"),
    _legacy("local_fs", "local-fs"),
    _legacy("local_storage", "local-storage"),
    _legacy("minio", secret_fields=("access_key", "secret_key")),
    _legacy("parquet"),
    _legacy("s3", secret_fields=("access_key", "secret_key", "session_token")),
    _legacy("sshfs", secret_fields=("password", "private_key")),
    _legacy("storacha", secret_fields=("token", "private_key")),
    BackendSpec(
        type_name="iroh",
        aliases=(),
        capabilities=frozenset(
            {
                BackendCapability.CONFIGURATION,
                BackendCapability.HEALTH,
                BackendCapability.RUNTIME_FACTORY,
                BackendCapability.STORAGE,
            }
        ),
        support_tier=BackendSupportTier.CONDITIONAL,
        health_contract="structured",
        secret_fields=("token",),
        runtime_factory="create_filesystem",
    ),
)


_EXCLUDED_SPECS: tuple[BackendSpec, ...] = (
    BackendSpec(
        type_name="arrow",
        aliases=(),
        capabilities=frozenset(),
        support_tier=BackendSupportTier.UNSUPPORTED,
        health_contract="not-available",
        excluded_reason="A dashboard schema existed, but no backend plugin or runtime factory is registered.",
    ),
    BackendSpec(
        type_name="lotus",
        aliases=(),
        capabilities=frozenset(),
        support_tier=BackendSupportTier.UNSUPPORTED,
        health_contract="not-available",
        excluded_reason="A dashboard schema existed, but no backend plugin or runtime factory is registered.",
    ),
    BackendSpec(
        type_name="saturn",
        aliases=(),
        capabilities=frozenset(),
        support_tier=BackendSupportTier.UNSUPPORTED,
        health_contract="not-available",
        excluded_reason="No implementation is integrated with the backend registry.",
    ),
    BackendSpec(
        type_name="synapse",
        aliases=(),
        capabilities=frozenset(),
        support_tier=BackendSupportTier.UNSUPPORTED,
        health_contract="not-available",
        excluded_reason="No implementation is integrated with the backend registry.",
    ),
)


def _index(specs: Iterable[BackendSpec]) -> dict[str, BackendSpec]:
    result: dict[str, BackendSpec] = {}
    aliases: dict[str, str] = {}
    for spec in specs:
        if spec.type_name in result:
            raise RuntimeError(f"Duplicate backend specification: {spec.type_name}")
        result[spec.type_name] = spec
        for name in spec.names:
            owner = aliases.setdefault(name, spec.type_name)
            if owner != spec.type_name:
                raise RuntimeError(
                    f"Backend name {name!r} is ambiguous between {owner!r} and "
                    f"{spec.type_name!r}"
                )
    return result


ACTIVE_BACKEND_SPECS: Final[Mapping[str, BackendSpec]] = _index(_ACTIVE_SPECS)
EXCLUDED_BACKEND_SPECS: Final[Mapping[str, BackendSpec]] = _index(_EXCLUDED_SPECS)
BACKEND_SPECS: Final[Mapping[str, BackendSpec]] = _index(
    (*_ACTIVE_SPECS, *_EXCLUDED_SPECS)
)


def _aliases(specs: Iterable[BackendSpec]) -> Mapping[str, str]:
    mapping: dict[str, str] = {}
    for spec in specs:
        for name in spec.names:
            owner = mapping.setdefault(name, spec.type_name)
            if owner != spec.type_name:
                raise RuntimeError(
                    f"Backend name {name!r} is ambiguous between {owner!r} and "
                    f"{spec.type_name!r}"
                )
    return mapping


BACKEND_NAME_ALIASES: Final[Mapping[str, str]] = _aliases(BACKEND_SPECS.values())


def normalize_backend_type(type_name: str, *, include_excluded: bool = True) -> str | None:
    """Return a canonical backend name for an explicitly declared spelling.

    The function intentionally does not guess by replacing punctuation or
    changing case.  All aliases are reviewed inventory entries, so ambiguous
    future names fail closed instead of silently resolving to a different
    backend.
    """

    if not isinstance(type_name, str):
        return None
    canonical = BACKEND_NAME_ALIASES.get(type_name)
    if canonical is None:
        return None
    if not include_excluded and canonical in EXCLUDED_BACKEND_SPECS:
        return None
    return canonical


def get_backend_spec(type_name: str, *, include_excluded: bool = True) -> BackendSpec | None:
    """Look up an inventory entry by canonical name or declared alias."""

    canonical = normalize_backend_type(type_name, include_excluded=include_excluded)
    return BACKEND_SPECS.get(canonical) if canonical is not None else None


__all__ = [
    "ACTIVE_BACKEND_SPECS",
    "BACKEND_NAME_ALIASES",
    "BACKEND_SPECS",
    "BackendCapability",
    "BackendSpec",
    "BackendSupportTier",
    "EXCLUDED_BACKEND_SPECS",
    "get_backend_spec",
    "normalize_backend_type",
]
