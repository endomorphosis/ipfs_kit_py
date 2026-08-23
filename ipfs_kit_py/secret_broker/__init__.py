"""Opaque worker secret broker."""

from .external_worker import (
    EphemeralSecretFile,
    OpaqueHandle,
    SecretBroker,
    SecretBrokerError,
)

__all__ = (
    "EphemeralSecretFile",
    "OpaqueHandle",
    "SecretBroker",
    "SecretBrokerError",
)
