"""End-to-end acceptance coverage for the public durable-state-root facade."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ipfs_kit_py.mcp_server.mcplusplus import (
    DurableStateRootAdapter,
    ProviderStatus,
    RootUpdateStatus,
)
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    ArtifactIntegrityError,
    DurableCoordinationStore,
    ROOT_CAS_INTERRUPTION_POINTS,
    cid_for_artifact,
)


def _payload(label: str) -> dict[str, str]:
    return {"schema": "datasets/semantic-state@1", "label": label}


def test_public_facade_preserves_caller_identity_and_is_namespace_isolated(tmp_path: Path) -> None:
    """The adapter verifies, but never calculates or translates, semantic identity."""

    alpha, beta = _payload("alpha"), _payload("beta")
    alpha_cid, beta_cid = cid_for_artifact(alpha), cid_for_artifact(beta)
    with DurableCoordinationStore(tmp_path / "store") as store:
        roots = DurableStateRootAdapter(store)
        assert roots.put_verified(alpha, expected_cid=alpha_cid, replicate=False).cid == alpha_cid
        assert roots.put_verified(beta, expected_cid=beta_cid, replicate=False).cid == beta_cid
        alpha_update = roots.compare_and_swap_root(
            "datasets/alpha", expected_revision=0, expected_root_cid=None,
            new_root_cid=alpha_cid, operation_id="alpha-publish",
        )
        beta_update = roots.compare_and_swap_root(
            "datasets/beta", expected_revision=0, expected_root_cid=None,
            new_root_cid=beta_cid, operation_id="beta-publish",
        )

    assert alpha_update.status is beta_update.status is RootUpdateStatus.UPDATED
    assert alpha_update.after.root_cid == alpha_cid
    assert beta_update.after.root_cid == beta_cid


def test_distinct_concurrent_writers_have_one_winner_and_a_typed_loser(tmp_path: Path) -> None:
    root = tmp_path / "store"
    with DurableCoordinationStore(root) as setup:
        first, second = _payload("one"), _payload("two")
        first_cid, second_cid = cid_for_artifact(first), cid_for_artifact(second)
        adapter = DurableStateRootAdapter(setup)
        adapter.put_verified(first, expected_cid=first_cid, replicate=False)
        adapter.put_verified(second, expected_cid=second_cid, replicate=False)

    def publish(cid: str, operation_id: str) -> object:
        with DurableCoordinationStore(root) as store:
            return DurableStateRootAdapter(store).compare_and_swap_root(
                "datasets/concurrent", expected_revision=0, expected_root_cid=None,
                new_root_cid=cid, operation_id=operation_id,
            )

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda args: publish(*args), ((first_cid, "one"), (second_cid, "two"))))

    assert sorted(result.status for result in results) == [RootUpdateStatus.CONFLICT, RootUpdateStatus.UPDATED]
    with DurableCoordinationStore(root) as store:
        current = DurableStateRootAdapter(store).current_root("datasets/concurrent")
    assert current.revision == 1
    assert current.root_cid in (first_cid, second_cid)


@pytest.mark.parametrize("boundary", ROOT_CAS_INTERRUPTION_POINTS)
def test_interrupted_publication_recovers_to_a_valid_state(tmp_path: Path, boundary: str) -> None:
    class Stop(RuntimeError):
        pass

    root, payload = tmp_path / boundary, _payload(boundary)
    cid = cid_for_artifact(payload)

    def interrupt(point: str) -> None:
        if point == boundary:
            raise Stop(point)

    with DurableCoordinationStore(root, crash_injector=interrupt) as store:
        adapter = DurableStateRootAdapter(store)
        adapter.put_verified(payload, expected_cid=cid, replicate=False)
        with pytest.raises(Stop):
            adapter.compare_and_swap_root(
                "datasets/recovery", expected_revision=0, expected_root_cid=None,
                new_root_cid=cid, operation_id="interrupted",
            )

    with DurableCoordinationStore(root) as store:
        current = DurableStateRootAdapter(store).current_root("datasets/recovery")
    assert (current.revision, current.root_cid) in ((0, None), (1, cid))


def test_corruption_stays_closed_and_absent_provider_is_explicit(tmp_path: Path) -> None:
    payload = _payload("corrupt")
    cid = cid_for_artifact(payload)
    with DurableCoordinationStore(tmp_path / "store") as store:
        adapter = DurableStateRootAdapter(store)
        unavailable = adapter.put_verified(payload, expected_cid=cid)
        assert unavailable.provider_status is ProviderStatus.UNAVAILABLE
        adapter.put_verified(payload, expected_cid=cid, replicate=False)
        store._block_path(cid).write_bytes(b"corrupt")
        with pytest.raises(ArtifactIntegrityError):
            adapter.compare_and_swap_root(
                "datasets/corrupt", expected_revision=0, expected_root_cid=None,
                new_root_cid=cid, operation_id="reject-corrupt",
            )
        assert adapter.current_root("datasets/corrupt").revision == 0
