"""Focused provider-projection tests for the thin state-root adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    DurableCoordinationStore,
    IPFSHeliaBlockBackend,
    cid_for_artifact,
)
from ipfs_kit_py.mcp_server.mcplusplus.state_root_adapter import DurableStateRootAdapter
from ipfs_kit_py.mcp_server.mcplusplus.state_root_contracts import ProviderStatus, RootUpdateStatus


def _payload(name: str = "one") -> dict[str, str]:
    return {"schema": "example/state@1", "name": name}


def test_expected_cid_is_preserved_and_mismatch_fails_before_root_update(tmp_path: Path) -> None:
    payload = _payload()
    expected_cid = cid_for_artifact(payload)
    with DurableCoordinationStore(tmp_path / "store") as store:
        adapter = DurableStateRootAdapter(store)
        written = adapter.put_verified(payload, expected_cid=expected_cid, replicate=False)
        assert written.cid == expected_cid
        assert written.provider_status is ProviderStatus.NOT_REQUESTED
        updated = adapter.compare_and_swap_root(
            "semantic", expected_revision=0, expected_root_cid=None,
            new_root_cid=written.cid, operation_id="publish-1",
        )
        assert updated.status is RootUpdateStatus.UPDATED

        with pytest.raises(ArtifactIntegrityError, match="does not match expected"):
            adapter.put_verified(_payload("different"), expected_cid=expected_cid)
        assert adapter.current_root("semantic") == updated.after


def test_requested_absent_provider_is_typed_and_local_only_needs_no_provider(tmp_path: Path) -> None:
    payload = _payload()
    with DurableCoordinationStore(tmp_path / "store") as store:
        adapter = DurableStateRootAdapter(store)
        unavailable = adapter.put_verified(payload, expected_cid=cid_for_artifact(payload))
        assert unavailable.local_durable is True
        assert unavailable.provider_status is ProviderStatus.UNAVAILABLE
        assert unavailable.replicated is False

        local_only = adapter.put_verified(payload, expected_cid=unavailable.cid, replicate=False)
        assert local_only.provider_status is ProviderStatus.NOT_REQUESTED
        assert local_only.replicated is False


class _WrongCidProvider:
    def put(self, data: bytes, *, cid: str, codec: str) -> dict[str, str]:
        return {"cid": cid[:-1] + ("a" if cid[-1] != "a" else "b")}


class _FailingProvider:
    def put(self, data: bytes, *, cid: str, codec: str) -> None:
        raise OSError("provider offline")


@pytest.mark.parametrize(
    ("provider", "status"),
    [(_WrongCidProvider(), ProviderStatus.CORRUPT), (_FailingProvider(), ProviderStatus.FAILED)],
)
def test_optional_provider_failure_never_claims_replication(
    tmp_path: Path, provider: object, status: ProviderStatus
) -> None:
    payload = _payload()
    with DurableCoordinationStore(
        tmp_path / "store", backend=IPFSHeliaBlockBackend(provider)
    ) as store:
        result = DurableStateRootAdapter(store).put_verified(
            payload, expected_cid=cid_for_artifact(payload)
        )
    assert result.local_durable is True
    assert result.provider_status is status
    assert result.replicated is False


def test_adapter_projects_verified_reads_and_root_conflicts(tmp_path: Path) -> None:
    first, second = _payload("one"), _payload("two")
    with DurableCoordinationStore(tmp_path / "store") as store:
        adapter = DurableStateRootAdapter(store)
        one = adapter.put_verified(first, expected_cid=cid_for_artifact(first), replicate=False)
        two = adapter.put_verified(second, expected_cid=cid_for_artifact(second), replicate=False)
        assert adapter.get_verified(one.cid) == first
        updated = adapter.compare_and_swap_root(
            "semantic", expected_revision=0, expected_root_cid=None,
            new_root_cid=one.cid, operation_id="one",
        )
        stale = adapter.compare_and_swap_root(
            "semantic", expected_revision=0, expected_root_cid=None,
            new_root_cid=two.cid, operation_id="two",
        )
    assert updated.status is RootUpdateStatus.UPDATED
    assert stale.status is RootUpdateStatus.CONFLICT
