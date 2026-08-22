"""Bounded repository transfer modes (EAAEF-021).

Managed aliases, Git bundles, manifested source bundles, approved remote
aliases, and uploaded object sets.  Arbitrary remote host paths are refused.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Final
from urllib.parse import urlparse


TRANSFER_SCHEMA: Final[str] = "ipfs_kit_py/repository-transfer-request@1"
MODES: Final[frozenset[str]] = frozenset(
    {
        "managed_alias",
        "git_bundle",
        "manifested_source_bundle",
        "approved_remote_alias",
        "uploaded_object_set",
    }
)


class TransferError(ValueError):
    """Transfer request is outside the admitted modes."""


def _refuse_host_path(value: str, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise TransferError(f"{name} is required")
    if text.startswith("/") or text.startswith("file://") or text.startswith("~"):
        raise TransferError("arbitrary remote host paths are not accepted")
    parsed = urlparse(text)
    if parsed.scheme in {"file", "unix"}:
        raise TransferError("arbitrary remote host paths are not accepted")
    if parsed.scheme in {"http", "https", "ssh", "git"} and not parsed.netloc:
        raise TransferError("remote alias is missing a host")
    try:
        path = PurePosixPath(text)
        if ".." in path.parts:
            raise TransferError("path traversal is not accepted")
    except TransferError:
        raise
    return text


@dataclass(frozen=True)
class TransferRequest:
    mode: str
    locator: str
    alias: str = ""
    object_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise TransferError(f"unsupported transfer mode: {self.mode}")
        object.__setattr__(self, "locator", _refuse_host_path(self.locator, "locator"))
        if self.mode in {"managed_alias", "approved_remote_alias"} and not str(self.alias).strip():
            raise TransferError("alias is required")
        if self.mode == "uploaded_object_set" and not self.object_ids:
            raise TransferError("uploaded object set requires object ids")
        for oid in self.object_ids:
            if len(str(oid)) < 8:
                raise TransferError("object id is too short")

    def to_dict(self) -> Mapping[str, Any]:
        return MappingProxyType(
            {
                "schema": TRANSFER_SCHEMA,
                "mode": self.mode,
                "locator": self.locator,
                "alias": self.alias,
                "object_ids": list(self.object_ids),
            }
        )


def admit_transfer(
    *,
    mode: str,
    locator: str,
    alias: str = "",
    object_ids: Sequence[str] = (),
) -> TransferRequest:
    return TransferRequest(
        mode=mode,
        locator=locator,
        alias=alias,
        object_ids=tuple(object_ids),
    )
