"""Kit tests for EAAEF-021 bounded repository transfer."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

KIT_ROOT = Path(__file__).resolve().parents[1]
if str(KIT_ROOT) not in sys.path:
    sys.path.insert(0, str(KIT_ROOT))

from repository_transfer.bundle import TransferError, admit_transfer


def test_admitted_modes() -> None:
    alias = admit_transfer(mode="managed_alias", locator="repos/core", alias="core")
    assert alias.mode == "managed_alias"
    bundle = admit_transfer(mode="git_bundle", locator="artifacts/repo.bundle")
    assert bundle.mode == "git_bundle"
    remote = admit_transfer(
        mode="approved_remote_alias",
        locator="https://git.example/org/repo.git",
        alias="upstream",
    )
    assert remote.locator.startswith("https://")
    uploaded = admit_transfer(
        mode="uploaded_object_set",
        locator="objects/upload-1",
        object_ids=("deadbeefcafebabe",),
    )
    assert uploaded.object_ids == ("deadbeefcafebabe",)


def test_host_paths_are_refused() -> None:
    with pytest.raises(TransferError, match="host paths"):
        admit_transfer(mode="git_bundle", locator="/etc/passwd")
    with pytest.raises(TransferError, match="host paths"):
        admit_transfer(mode="git_bundle", locator="file:///home/alice/repo.git")
    with pytest.raises(TransferError, match="traversal"):
        admit_transfer(mode="manifested_source_bundle", locator="foo/../../etc/shadow")
