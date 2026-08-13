"""Fail-closed vectors for append-only governor histories (SCG-020).

Acceptance:

* replay is idempotent
* concurrent writers preserve both histories
* public projection exposes no raw private source or arbitrary local path
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
)
from ipfs_kit_py.semantic_governor_store.artifacts import (
    DurableSemanticGovernorStore,
    cid_for_governor_artifact,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    AuditHistoryStore,
    GovernorArtifactKind,
    GovernorHistoryRole,
    GovernorStoreStatus,
    history_namespace,
)
from ipfs_kit_py.semantic_governor_store.history import (
    DEFAULT_HISTORY_PAGE_SIZE,
    HISTORY_MANIFEST_INTERFACE,
    HISTORY_MANIFEST_SCHEMA,
    HISTORY_MODULE_INTERFACE,
    HISTORY_PUBLIC_PROJECTION_SCHEMA,
    MAX_HISTORY_PAGE_SIZE,
    DurableAuditHistoryStore,
    GovernorHistoryAdmissionError,
    build_history_manifest,
    cid_for_history_manifest,
    project_public_value,
    reject_public_local_paths,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _entry(
    store: DurableCoordinationStore,
    name: str,
    *,
    kind: str | None = None,
    **extra: Any,
) -> str:
    """Store a plain durable entry block (not necessarily a sealed envelope)."""

    payload: dict[str, Any] = {
        "schema": "example/governor-history-entry@1",
        "name": name,
        "status": "complete",
    }
    if kind is not None:
        # Nested under payload_kind so DurableAuditHistoryStore does not treat
        # the top-level as a sealed governor envelope kind gate.
        payload["payload_kind"] = kind
    payload.update(extra)
    return store.put(payload, expected_cid=cid_for_artifact(payload), replicate=False)[
        "cid"
    ]


def _sealed_entry(
    governor: DurableSemanticGovernorStore,
    kind: GovernorArtifactKind,
    name: str,
) -> str:
    payload = {
        "case_id": name,
        "summary": f"{kind.value} history entry",
        "status": "complete",
    }
    expected = cid_for_governor_artifact(kind, payload)
    result = governor.put_artifact(
        kind,
        payload,
        expected_cid=expected,
        operation_id=f"seal-{kind.value}-{name}",
        replicate=False,
    )
    return result.cid


@pytest.fixture()
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "history-store"


@pytest.fixture()
def coordination(store_dir: Path) -> DurableCoordinationStore:
    root = DurableCoordinationStore(store_dir)
    yield root
    root.close()


@pytest.fixture()
def history(coordination: DurableCoordinationStore) -> DurableAuditHistoryStore:
    return DurableAuditHistoryStore(coordination)


@pytest.fixture()
def governor(
    coordination: DurableCoordinationStore,
) -> DurableSemanticGovernorStore:
    store = DurableSemanticGovernorStore(coordination)
    yield store
    store.close()


WORKSPACE = "default"


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


def test_module_interfaces_are_versioned() -> None:
    assert HISTORY_MODULE_INTERFACE == "DurableAuditHistoryStore@1"
    assert HISTORY_MANIFEST_INTERFACE == "GovernorHistoryManifest@1"
    assert HISTORY_MANIFEST_SCHEMA.endswith("@1")
    assert HISTORY_PUBLIC_PROJECTION_SCHEMA.endswith("@1")
    assert DEFAULT_HISTORY_PAGE_SIZE <= MAX_HISTORY_PAGE_SIZE
    assert MAX_HISTORY_PAGE_SIZE == 256


def test_history_store_satisfies_protocol_shape(
    history: DurableAuditHistoryStore,
) -> None:
    for name in ("current_history", "append_history"):
        assert callable(getattr(history, name))
        assert hasattr(AuditHistoryStore, name)
    for name in ("append_audit", "append_calibration", "append_benchmark"):
        assert callable(getattr(history, name))


def test_build_history_manifest_is_deterministic() -> None:
    a = build_history_manifest(
        workspace=WORKSPACE,
        role=GovernorHistoryRole.AUDIT,
        generation=1,
        entry_cid=cid_for_artifact({"n": "e1"}),
        previous_head_cid=None,
        operation_id="append-1",
    )
    b = build_history_manifest(
        workspace=WORKSPACE,
        role="audit",
        generation=1,
        entry_cid=cid_for_artifact({"n": "e1"}),
        previous_head_cid=None,
        operation_id="append-1",
    )
    assert a == b
    assert a["schema"] == HISTORY_MANIFEST_SCHEMA
    assert a["interface_id"] == HISTORY_MANIFEST_INTERFACE
    assert a["previous_head_cid"] is None
    assert cid_for_history_manifest(a) == cid_for_history_manifest(b)


# ---------------------------------------------------------------------------
# Happy path, idempotent replay, and role convenience methods
# ---------------------------------------------------------------------------


def test_history_starts_at_generation_zero(
    history: DurableAuditHistoryStore,
) -> None:
    for role in GovernorHistoryRole:
        head = history.current_history(WORKSPACE, role)
        assert head.generation == 0
        assert head.head_cid is None
        assert head.transition_cid is None
        assert head.history_role is role
        assert head.namespace == history_namespace(WORKSPACE, role)


def test_append_audit_publishes_successor_and_replays_idempotently(
    coordination: DurableCoordinationStore,
    history: DurableAuditHistoryStore,
) -> None:
    entry = _entry(coordination, "audit-1", kind="audit")
    updated = history.append_audit(
        WORKSPACE,
        entry_cid=entry,
        expected_generation=0,
        expected_head_cid=None,
        operation_id="audit-publish-1",
    )
    assert updated.status is GovernorStoreStatus.UPDATED
    assert updated.before.generation == 0
    assert updated.after.generation == 1
    assert updated.entry_cid == entry
    assert updated.after.head_cid is not None
    assert updated.after.head_cid != entry
    assert updated.transition_cid == updated.after.transition_cid
    assert updated.local_durable is True
    assert history.current_history(WORKSPACE, GovernorHistoryRole.AUDIT) == updated.after

    # Deterministic manifest links the entry and prior head.
    manifest = coordination.get(updated.after.head_cid)
    assert manifest["entry_cid"] == entry
    assert manifest["previous_head_cid"] is None
    assert manifest["generation"] == 1
    assert manifest["operation_id"] == "audit-publish-1"

    replay = history.append_audit(
        WORKSPACE,
        entry_cid=entry,
        expected_generation=0,
        expected_head_cid=None,
        operation_id="audit-publish-1",
    )
    assert replay.status is GovernorStoreStatus.UNCHANGED
    assert replay.reason_code == "idempotent_replay"
    assert replay.after == updated.after
    assert replay.transition_cid is None
    assert replay.entry_cid == entry
    assert len(history.history_transitions(WORKSPACE, GovernorHistoryRole.AUDIT)) == 1


def test_append_calibration_and_benchmark_are_isolated(
    coordination: DurableCoordinationStore,
    history: DurableAuditHistoryStore,
) -> None:
    cal = _entry(coordination, "cal-1")
    bench = _entry(coordination, "bench-1")

    cal_result = history.append_calibration(
        WORKSPACE,
        entry_cid=cal,
        expected_generation=0,
        expected_head_cid=None,
        operation_id="cal-1",
    )
    bench_result = history.append_benchmark(
        WORKSPACE,
        entry_cid=bench,
        expected_generation=0,
        expected_head_cid=None,
        operation_id="bench-1",
    )
    assert cal_result.status is GovernorStoreStatus.UPDATED
    assert bench_result.status is GovernorStoreStatus.UPDATED
    assert history.current_history(
        WORKSPACE, GovernorHistoryRole.CALIBRATION
    ).generation == 1
    assert history.current_history(
        WORKSPACE, GovernorHistoryRole.BENCHMARK
    ).generation == 1
    assert history.current_history(
        WORKSPACE, GovernorHistoryRole.AUDIT
    ).generation == 0


def test_chained_appends_preserve_full_manifest_chain(
    coordination: DurableCoordinationStore,
    history: DurableAuditHistoryStore,
) -> None:
    first = _entry(coordination, "a1")
    second = _entry(coordination, "a2")
    third = _entry(coordination, "a3")

    r1 = history.append_history(
        WORKSPACE,
        GovernorHistoryRole.AUDIT,
        entry_cid=first,
        expected_generation=0,
        expected_head_cid=None,
        operation_id="chain-1",
    )
    assert r1.status is GovernorStoreStatus.UPDATED
    r2 = history.append_history(
        WORKSPACE,
        GovernorHistoryRole.AUDIT,
        entry_cid=second,
        expected_generation=1,
        expected_head_cid=r1.after.head_cid,
        operation_id="chain-2",
    )
    assert r2.status is GovernorStoreStatus.UPDATED
    r3 = history.append_history(
        WORKSPACE,
        GovernorHistoryRole.AUDIT,
        entry_cid=third,
        expected_generation=2,
        expected_head_cid=r2.after.head_cid,
        operation_id="chain-3",
    )
    assert r3.status is GovernorStoreStatus.UPDATED
    assert history.current_history(WORKSPACE, "audit").generation == 3
    assert history.list_entry_cids(WORKSPACE, "audit") == [first, second, third]
    assert len(history.history_transitions(WORKSPACE, "audit")) == 3


# ---------------------------------------------------------------------------
# Stale expectations, operation-id reuse, unavailable entries
# ---------------------------------------------------------------------------


def test_stale_expectation_cannot_overwrite_current(
    coordination: DurableCoordinationStore,
    history: DurableAuditHistoryStore,
) -> None:
    first = _entry(coordination, "h1")
    second = _entry(coordination, "h2")
    third = _entry(coordination, "h3")

    updated = history.append_audit(
        WORKSPACE,
        entry_cid=first,
        expected_generation=0,
        expected_head_cid=None,
        operation_id="h-1",
    )
    assert updated.status is GovernorStoreStatus.UPDATED

    stale_gen = history.append_audit(
        WORKSPACE,
        entry_cid=second,
        expected_generation=0,
        expected_head_cid=None,
        operation_id="h-stale-gen",
    )
    assert stale_gen.status is GovernorStoreStatus.CONFLICT
    assert stale_gen.reason_code == "stale_expectation"
    assert stale_gen.after == updated.after

    stale_cid = history.append_audit(
        WORKSPACE,
        entry_cid=third,
        expected_generation=1,
        expected_head_cid=second,
        operation_id="h-stale-cid",
    )
    assert stale_cid.status is GovernorStoreStatus.CONFLICT
    assert history.current_history(WORKSPACE, "audit").head_cid == updated.after.head_cid
    assert len(history.history_transitions(WORKSPACE, "audit")) == 1


def test_operation_id_reuse_with_different_payload_conflicts(
    coordination: DurableCoordinationStore,
    history: DurableAuditHistoryStore,
) -> None:
    first = _entry(coordination, "op-a")
    other = _entry(coordination, "op-b")
    history.append_audit(
        WORKSPACE,
        entry_cid=first,
        expected_generation=0,
        expected_head_cid=None,
        operation_id="once",
    )
    reuse = history.append_audit(
        WORKSPACE,
        entry_cid=other,
        expected_generation=0,
        expected_head_cid=None,
        operation_id="once",
    )
    assert reuse.status is GovernorStoreStatus.CONFLICT
    assert reuse.reason_code == "operation_id_reused"
    assert history.list_entry_cids(WORKSPACE, "audit") == [first]


def test_missing_entry_is_unavailable(
    coordination: DurableCoordinationStore,
    history: DurableAuditHistoryStore,
) -> None:
    missing = cid_for_artifact({"schema": "example/missing@1", "n": "gone"})
    result = history.append_audit(
        WORKSPACE,
        entry_cid=missing,
        expected_generation=0,
        expected_head_cid=None,
        operation_id="missing-entry",
    )
    assert result.status is GovernorStoreStatus.UNAVAILABLE
    assert result.reason_code == "entry_unavailable"
    assert result.local_durable is False
    assert history.current_history(WORKSPACE, "audit").generation == 0


def test_sealed_entry_wrong_kind_is_rejected(
    governor: DurableSemanticGovernorStore,
    history: DurableAuditHistoryStore,
) -> None:
    cal_cid = _sealed_entry(governor, GovernorArtifactKind.CALIBRATION, "wrong-role")
    with pytest.raises(GovernorHistoryAdmissionError, match="not valid for history role"):
        history.append_audit(
            WORKSPACE,
            entry_cid=cal_cid,
            expected_generation=0,
            expected_head_cid=None,
            operation_id="wrong-kind",
        )


def test_sealed_matching_kind_is_admitted(
    governor: DurableSemanticGovernorStore,
    history: DurableAuditHistoryStore,
) -> None:
    audit_cid = _sealed_entry(governor, GovernorArtifactKind.AUDIT, "ok-role")
    result = history.append_audit(
        WORKSPACE,
        entry_cid=audit_cid,
        expected_generation=0,
        expected_head_cid=None,
        operation_id="ok-kind",
    )
    assert result.status is GovernorStoreStatus.UPDATED
    assert result.entry_cid == audit_cid


def test_rejects_incoherent_expectations(
    coordination: DurableCoordinationStore,
    history: DurableAuditHistoryStore,
) -> None:
    cid = _entry(coordination, "x")
    with pytest.raises(GovernorHistoryAdmissionError):
        history.append_audit(
            WORKSPACE,
            entry_cid=cid,
            expected_generation=0,
            expected_head_cid=cid,
            operation_id="bad-zero",
        )
    with pytest.raises(GovernorHistoryAdmissionError):
        history.append_audit(
            WORKSPACE,
            entry_cid=cid,
            expected_generation=1,
            expected_head_cid=None,
            operation_id="bad-nonzero",
        )


# ---------------------------------------------------------------------------
# Concurrent writers preserve both histories
# ---------------------------------------------------------------------------


def test_concurrent_writers_preserve_both_histories(store_dir: Path) -> None:
    """One CAS wins; the loser retries and both immutable entries remain."""

    with DurableCoordinationStore(store_dir) as setup:
        one = _entry(setup, "concurrent-one")
        two = _entry(setup, "concurrent-two")

    def attempt(entry_cid: str, operation_id: str) -> dict[str, Any]:
        with DurableCoordinationStore(store_dir) as store:
            repo = DurableAuditHistoryStore(store)
            first = repo.append_audit(
                WORKSPACE,
                entry_cid=entry_cid,
                expected_generation=0,
                expected_head_cid=None,
                operation_id=operation_id,
            )
            if first.status is GovernorStoreStatus.UPDATED:
                return {
                    "status": first.status.value,
                    "entry_cid": entry_cid,
                    "retried": False,
                }
            # Conflict: re-read head and append as successor so both histories live.
            head = repo.current_history(WORKSPACE, GovernorHistoryRole.AUDIT)
            retry = repo.append_audit(
                WORKSPACE,
                entry_cid=entry_cid,
                expected_generation=head.generation,
                expected_head_cid=head.head_cid,
                operation_id=f"{operation_id}-retry",
            )
            return {
                "status": retry.status.value,
                "entry_cid": entry_cid,
                "retried": True,
                "first_status": first.status.value,
            }

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(attempt, one, "writer-1"),
            pool.submit(attempt, two, "writer-2"),
        ]
        results = [future.result() for future in as_completed(futures)]

    assert all(item["status"] == "updated" for item in results)
    assert sum(1 for item in results if item["retried"]) == 1

    with DurableCoordinationStore(store_dir) as store:
        repo = DurableAuditHistoryStore(store)
        head = repo.current_history(WORKSPACE, GovernorHistoryRole.AUDIT)
        assert head.generation == 2
        entries = set(repo.list_entry_cids(WORKSPACE, GovernorHistoryRole.AUDIT))
        assert entries == {one, two}
        assert len(repo.history_transitions(WORKSPACE, GovernorHistoryRole.AUDIT)) == 2


def test_concurrent_role_histories_do_not_interfere(store_dir: Path) -> None:
    with DurableCoordinationStore(store_dir) as setup:
        audit_entry = _entry(setup, "role-audit")
        cal_entry = _entry(setup, "role-cal")

    def write_audit() -> str:
        with DurableCoordinationStore(store_dir) as store:
            repo = DurableAuditHistoryStore(store)
            return repo.append_audit(
                WORKSPACE,
                entry_cid=audit_entry,
                expected_generation=0,
                expected_head_cid=None,
                operation_id="role-audit-1",
            ).status.value

    def write_cal() -> str:
        with DurableCoordinationStore(store_dir) as store:
            repo = DurableAuditHistoryStore(store)
            return repo.append_calibration(
                WORKSPACE,
                entry_cid=cal_entry,
                expected_generation=0,
                expected_head_cid=None,
                operation_id="role-cal-1",
            ).status.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda fn: fn(), (write_audit, write_cal)))

    assert sorted(statuses) == ["updated", "updated"]
    with DurableCoordinationStore(store_dir) as store:
        repo = DurableAuditHistoryStore(store)
        assert repo.list_entry_cids(WORKSPACE, "audit") == [audit_entry]
        assert repo.list_entry_cids(WORKSPACE, "calibration") == [cal_entry]


# ---------------------------------------------------------------------------
# Pagination bounds
# ---------------------------------------------------------------------------


def test_pagination_bounds_and_pages(
    coordination: DurableCoordinationStore,
    history: DurableAuditHistoryStore,
) -> None:
    head_cid = None
    generation = 0
    cids: list[str] = []
    for index in range(5):
        entry = _entry(coordination, f"page-{index}")
        cids.append(entry)
        result = history.append_audit(
            WORKSPACE,
            entry_cid=entry,
            expected_generation=generation,
            expected_head_cid=head_cid,
            operation_id=f"page-op-{index}",
        )
        assert result.status is GovernorStoreStatus.UPDATED
        head_cid = result.after.head_cid
        generation = result.after.generation

    page = history.list_entry_cids(WORKSPACE, "audit", offset=1, limit=2)
    assert page == cids[1:3]
    transitions = history.history_transitions(WORKSPACE, "audit", offset=2, limit=2)
    assert len(transitions) == 2
    assert transitions[0]["new_revision"] == 3

    with pytest.raises(GovernorHistoryAdmissionError, match="MAX_HISTORY_PAGE_SIZE"):
        history.list_entry_cids(
            WORKSPACE, "audit", offset=0, limit=MAX_HISTORY_PAGE_SIZE + 1
        )
    with pytest.raises(GovernorHistoryAdmissionError, match="positive integer"):
        history.history_transitions(WORKSPACE, "audit", limit=0)
    with pytest.raises(GovernorHistoryAdmissionError, match="non-negative"):
        history.history_transitions(WORKSPACE, "audit", offset=-1)


# ---------------------------------------------------------------------------
# Public / private projections — no private source or local paths
# ---------------------------------------------------------------------------


def test_public_projection_exposes_cids_only(
    coordination: DurableCoordinationStore,
    history: DurableAuditHistoryStore,
) -> None:
    first = _entry(coordination, "pub-1")
    second = _entry(coordination, "pub-2")
    r1 = history.append_audit(
        WORKSPACE,
        entry_cid=first,
        expected_generation=0,
        expected_head_cid=None,
        operation_id="pub-1",
    )
    history.append_audit(
        WORKSPACE,
        entry_cid=second,
        expected_generation=1,
        expected_head_cid=r1.after.head_cid,
        operation_id="pub-2",
    )

    projection = history.public_history_projection(WORKSPACE, "audit")
    assert projection["schema"] == HISTORY_PUBLIC_PROJECTION_SCHEMA
    assert projection["history_role"] == "audit"
    assert projection["generation"] == 2
    assert projection["total_entries"] == 2
    assert [row["entry_cid"] for row in projection["entries"]] == [first, second]

    # No private markers or path-shaped keys anywhere in the projection.
    serialized = str(dict(projection))
    for marker in (
        "private_source",
        "raw_source",
        "raw_private_source",
        "source_text",
        "password",
        "secret",
    ):
        assert marker not in serialized
    for pathish in ("/tmp/", "C:\\", "file:", "local_path", "absolute_path"):
        assert pathish not in serialized

    # Projection is free of host-local store paths even when the store root exists.
    assert str(coordination.root) not in serialized


def test_public_projection_rejects_private_and_path_values() -> None:
    with pytest.raises(GovernorHistoryAdmissionError, match="private"):
        project_public_value({"summary": "ok", "raw_private_source": "SECRET"})
    with pytest.raises(GovernorHistoryAdmissionError, match="local path"):
        project_public_value({"note": "/var/lib/governor/secret.bin"})
    with pytest.raises(GovernorHistoryAdmissionError, match="local path"):
        reject_public_local_paths({"local_path": "relative/but/named/path"})
    # Portable CID-shaped references remain admissible.
    assert project_public_value(
        {"entry_cid": "baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
    )["entry_cid"].startswith("baguqeer")


def test_private_projection_also_excludes_private_source_and_paths(
    coordination: DurableCoordinationStore,
    history: DurableAuditHistoryStore,
) -> None:
    entry = _entry(coordination, "priv-1")
    history.append_calibration(
        WORKSPACE,
        entry_cid=entry,
        expected_generation=0,
        expected_head_cid=None,
        operation_id="priv-1",
    )
    private = history.private_history_projection(WORKSPACE, "calibration")
    assert private["schema"].endswith("history-private@1")
    assert private["entries"][0]["entry_cid"] == entry
    assert "manifest" in private["entries"][0]
    assert "transitions" in private
    blob = str(dict(private))
    assert "raw_private_source" not in blob
    assert str(coordination.root) not in blob


def test_rejected_stale_records_remain_listable_after_success(
    coordination: DurableCoordinationStore,
    history: DurableAuditHistoryStore,
) -> None:
    """Conflict policy: rejected/stale appends never rewrite prior history."""

    kept = _entry(coordination, "kept")
    rejected = _entry(coordination, "rejected")
    first = history.append_audit(
        WORKSPACE,
        entry_cid=kept,
        expected_generation=0,
        expected_head_cid=None,
        operation_id="keep-1",
    )
    conflict = history.append_audit(
        WORKSPACE,
        entry_cid=rejected,
        expected_generation=0,
        expected_head_cid=None,
        operation_id="reject-1",
    )
    assert conflict.status is GovernorStoreStatus.CONFLICT
    # The rejected entry remains durable as an immutable block.
    assert coordination.has(rejected)
    assert history.list_entry_cids(WORKSPACE, "audit") == [kept]
    assert history.current_history(WORKSPACE, "audit") == first.after

