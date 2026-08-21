"""Fail-closed vectors for campaign Merkle roots, seal manifests, and benchmarks (AAE-036).

Acceptance:

* deterministic roots commit operator/policy/admitted/detection/outcome/
  survivor/vacuity/held-out sets with required-set completeness
* seal manifests make seal availability and seal status explicit
* signature verification occurs before persistence, Merkle inclusion, or seal
  input — no invalid or not-yet-verified signed receipt can enter a manifest
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# Prefer this worktree's kit package when an outer PYTHONPATH pin is present.
_KIT_ROOT = Path(__file__).resolve().parents[2]
_KIT_PKG = _KIT_ROOT / "ipfs_kit_py"
if sys.path[:1] != [str(_KIT_ROOT)]:
    sys.path.insert(0, str(_KIT_ROOT))
import ipfs_kit_py as _ipfs_kit_py  # noqa: E402

if str(_KIT_PKG) not in list(_ipfs_kit_py.__path__):
    _ipfs_kit_py.__path__.insert(0, str(_KIT_PKG))

from ipfs_datasets_py.logic.software_contracts.adversarial_assurance import (
    AssuranceTerminalStatus,
    HeldOutResult,
    ReceiptAction,
    SealAvailabilityStatus,
    SignatureVerificationStatus,
)
from tests.adversarial_assurance_store.datasets_test_fixtures import receipt_fixtures
from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
)
from ipfs_kit_py.adversarial_assurance_store.artifacts import (
    DurableAssuranceArtifactStore,
    cid_for_assurance_artifact,
)
from ipfs_kit_py.adversarial_assurance_store.campaigns import (
    admit_campaign_receipt_payload,
)
from ipfs_kit_py.adversarial_assurance_store.contracts import (
    AssuranceArtifactKind,
    AssuranceNamespaceRole,
    AssuranceStoreStatus,
    assurance_namespace,
)
from ipfs_kit_py.adversarial_assurance_store.merkle import (
    BENCHMARK_ARTIFACT_INTERFACE,
    BENCHMARK_ARTIFACT_SCHEMA,
    CAMPAIGN_MERKLE_ROOT_INTERFACE,
    CAMPAIGN_MERKLE_ROOT_SCHEMA,
    MERKLE_MODULE_INTERFACE,
    MERKLE_SET_INTERFACE,
    MERKLE_SET_SCHEMA,
    REQUIRED_MERKLE_SET_KIND_VALUES,
    SEAL_MANIFEST_INTERFACE,
    SEAL_MANIFEST_SCHEMA,
    DurableAssuranceCampaignMerkleRepository,
    MerkleAdmissionError,
    MerkleSetKind,
    admit_campaign_merkle_root,
    admit_merkle_set_commitment,
    admit_seal_manifest,
    build_benchmark_artifact,
    build_campaign_merkle_root,
    build_merkle_set_commitment,
    build_seal_manifest,
    cid_for_benchmark_artifact,
    cid_for_campaign_merkle_root,
    cid_for_merkle_set,
    cid_for_seal_manifest,
    compute_member_set_root,
    merkle_set_kinds,
    seal_availability_statuses,
    seal_available_for_status,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


WORKSPACE = "worker-1"
CAMPAIGN_ID = "camp-merkle-1"


@pytest.fixture()
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "merkle-store"


@pytest.fixture()
def coordination(store_dir: Path) -> DurableCoordinationStore:
    root = DurableCoordinationStore(store_dir)
    yield root
    root.close()


@pytest.fixture()
def artifacts(
    coordination: DurableCoordinationStore,
) -> DurableAssuranceArtifactStore:
    store = DurableAssuranceArtifactStore(coordination)
    yield store
    store.close()


@pytest.fixture()
def merkle(
    coordination: DurableCoordinationStore,
    artifacts: DurableAssuranceArtifactStore,
) -> DurableAssuranceCampaignMerkleRepository:
    repo = DurableAssuranceCampaignMerkleRepository(
        coordination, artifacts=artifacts
    )
    yield repo
    repo.close()


def _leaf_payload(tag: str) -> dict[str, Any]:
    return {
        "schema": "ipfs-kit.adversarial-assurance-store.test-leaf@1",
        "tag": tag,
    }


def _leaf(tag: str) -> str:
    return cid_for_artifact(_leaf_payload(tag))


def _put_leaf(
    coordination: DurableCoordinationStore, tag: str
) -> str:
    payload = _leaf_payload(tag)
    cid = cid_for_artifact(payload)
    coordination.put(payload, expected_cid=cid, codec="dag-json", replicate=False)
    return cid


def _campaign_payload(**overrides: Any) -> dict[str, Any]:
    return receipt_fixtures._campaign(**overrides).to_dict()


def _unverified_campaign_payload() -> dict[str, Any]:
    return receipt_fixtures._campaign(
        header=receipt_fixtures._header(
            "assurance_campaign_receipt",
            terminal_status=AssuranceTerminalStatus.REJECTED,
        ),
        held_out_result=HeldOutResult.FAILED,
        signature=receipt_fixtures._signature(
            signature_verification_status=SignatureVerificationStatus.UNVERIFIED
        ),
    ).to_dict()


def _put_verified_receipt(
    coordination: DurableCoordinationStore,
    artifacts: DurableAssuranceArtifactStore,
    payload: dict[str, Any] | None = None,
    *,
    op: str = "receipt-1",
) -> str:
    body = payload if payload is not None else _campaign_payload()
    sealed = admit_campaign_receipt_payload(body)
    expected = cid_for_assurance_artifact(
        AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT, sealed
    )
    result = artifacts.put_artifact(
        AssuranceArtifactKind.ASSURANCE_CAMPAIGN_RECEIPT,
        sealed,
        expected_cid=expected,
        operation_id=op,
        replicate=False,
    )
    assert result.local_durable is True
    # Ensure durable under coordination store used by merkle repo.
    assert coordination.get_bytes(expected)
    return expected


def _commit_all_sets(
    merkle: DurableAssuranceCampaignMerkleRepository,
    coordination: DurableCoordinationStore,
    *,
    campaign_id: str = CAMPAIGN_ID,
    include_receipt_in: MerkleSetKind | None = None,
    receipt_cid: str | None = None,
) -> dict[str, str]:
    set_cids: dict[str, str] = {}
    for kind in MerkleSetKind:
        members = [
            _put_leaf(coordination, f"{kind.value}-a"),
            _put_leaf(coordination, f"{kind.value}-b"),
        ]
        if include_receipt_in is kind and receipt_cid is not None:
            members.append(receipt_cid)
        sealed = build_merkle_set_commitment(
            workspace=WORKSPACE,
            campaign_id=campaign_id,
            set_kind=kind,
            member_cids=members,
            operation_id=f"set-op-{kind.value}",
        )
        expected = cid_for_merkle_set(sealed)
        result = merkle.commit_merkle_set(
            WORKSPACE,
            campaign_id=campaign_id,
            set_kind=kind,
            member_cids=members,
            expected_cid=expected,
            operation_id=f"set-op-{kind.value}",
        )
        assert result.local_durable is True
        assert result.set_cid == expected
        set_cids[kind.value] = expected
    return set_cids


# ---------------------------------------------------------------------------
# Module surface / closed vocabularies
# ---------------------------------------------------------------------------


def test_module_interfaces_and_closed_vocabularies() -> None:
    assert MERKLE_MODULE_INTERFACE == "AssuranceCampaignMerkleRepository@1"
    assert MERKLE_SET_INTERFACE.endswith("@1")
    assert MERKLE_SET_SCHEMA.endswith("@1")
    assert CAMPAIGN_MERKLE_ROOT_INTERFACE.endswith("@1")
    assert CAMPAIGN_MERKLE_ROOT_SCHEMA.endswith("@1")
    assert SEAL_MANIFEST_INTERFACE.endswith("@1")
    assert SEAL_MANIFEST_SCHEMA.endswith("@1")
    assert BENCHMARK_ARTIFACT_INTERFACE.endswith("@1")
    assert BENCHMARK_ARTIFACT_SCHEMA.endswith("@1")
    assert merkle_set_kinds() == REQUIRED_MERKLE_SET_KIND_VALUES
    assert set(merkle_set_kinds()) == {
        "operator",
        "policy",
        "admitted",
        "detection",
        "outcome",
        "survivor",
        "vacuity",
        "held_out",
    }
    assert "bound" in seal_availability_statuses()
    assert "unavailable" in seal_availability_statuses()
    assert seal_available_for_status(SealAvailabilityStatus.BOUND) is True
    assert seal_available_for_status("unavailable") is False
    assert seal_available_for_status("not_requested") is False


def test_set_commitment_is_deterministic_and_closed() -> None:
    members = [_leaf("m1"), _leaf("m2"), _leaf("m0")]
    a = build_merkle_set_commitment(
        workspace=WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        set_kind=MerkleSetKind.OPERATOR,
        member_cids=members,
        operation_id="set-op-1",
    )
    b = build_merkle_set_commitment(
        workspace=WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        set_kind="operator",
        member_cids=list(reversed(members)),
        operation_id="set-op-1",
    )
    assert a == b
    assert a["member_cids"] == sorted(members)
    assert a["set_root"] == compute_member_set_root(sorted(members))
    assert cid_for_merkle_set(a) == cid_for_merkle_set(b)
    assert admit_merkle_set_commitment(a) == a
    with pytest.raises(MerkleAdmissionError, match="unknown merkle set kind"):
        build_merkle_set_commitment(
            workspace=WORKSPACE,
            campaign_id=CAMPAIGN_ID,
            set_kind="not-a-set",
            member_cids=[],
            operation_id="set-bad",
        )
    with pytest.raises(MerkleAdmissionError, match="unknown"):
        bad = dict(a)
        bad["extra"] = True
        admit_merkle_set_commitment(bad)


def test_campaign_root_requires_complete_required_sets() -> None:
    entries = []
    for kind in list(MerkleSetKind)[:-1]:
        entries.append(
            {
                "set_kind": kind.value,
                "set_cid": _leaf(f"set-{kind.value}"),
                "set_root": compute_member_set_root([_leaf(kind.value)]),
                "member_count": 1,
            }
        )
    with pytest.raises(MerkleAdmissionError, match="required-set completeness"):
        build_campaign_merkle_root(
            workspace=WORKSPACE,
            campaign_id=CAMPAIGN_ID,
            generation=1,
            set_entries=entries,
            previous_root_cid=None,
            seal_manifest_cid=None,
            operation_id="root-incomplete",
            require_complete=True,
        )


def test_campaign_root_deterministic_over_required_sets() -> None:
    entries = []
    for kind in MerkleSetKind:
        members = [_leaf(f"{kind.value}-1"), _leaf(f"{kind.value}-2")]
        entries.append(
            {
                "set_kind": kind.value,
                "set_cid": _leaf(f"setcid-{kind.value}"),
                "set_root": compute_member_set_root(members),
                "member_count": 2,
            }
        )
    a = build_campaign_merkle_root(
        workspace=WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        generation=1,
        set_entries=list(reversed(entries)),
        previous_root_cid=None,
        seal_manifest_cid=None,
        operation_id="root-1",
        require_complete=True,
    )
    b = build_campaign_merkle_root(
        workspace=WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        generation=1,
        set_entries=entries,
        previous_root_cid=None,
        seal_manifest_cid=None,
        operation_id="root-1",
        require_complete=True,
    )
    assert a == b
    assert a["required_set_completeness"] is True
    assert [e["set_kind"] for e in a["set_entries"]] == list(
        REQUIRED_MERKLE_SET_KIND_VALUES
    )
    assert cid_for_campaign_merkle_root(a) == cid_for_campaign_merkle_root(b)
    assert admit_campaign_merkle_root(a) == a


def test_seal_manifest_explicit_availability_and_status() -> None:
    set_cids = {
        kind: _leaf(f"set-{kind}") for kind in REQUIRED_MERKLE_SET_KIND_VALUES
    }
    root_cid = _leaf("campaign-root")
    bound = build_seal_manifest(
        workspace=WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        campaign_root_cid=root_cid,
        set_cids=set_cids,
        seal_status=SealAvailabilityStatus.BOUND,
        seal_evidence_cid=_leaf("seal-evidence"),
        receipt_cid=None,
        benchmark_artifact_cids=[],
        operation_id="seal-1",
    )
    assert bound["seal_status"] == "bound"
    assert bound["seal_available"] is True
    assert bound["required_set_completeness"] is True
    assert bound["missing_sets"] == []
    assert bound["required_sets"] == list(REQUIRED_MERKLE_SET_KIND_VALUES)
    assert admit_seal_manifest(bound) == bound

    unavailable = build_seal_manifest(
        workspace=WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        campaign_root_cid=root_cid,
        set_cids=set_cids,
        seal_status="unavailable",
        seal_evidence_cid=None,
        receipt_cid=None,
        benchmark_artifact_cids=[],
        operation_id="seal-2",
    )
    assert unavailable["seal_status"] == "unavailable"
    assert unavailable["seal_available"] is False

    with pytest.raises(MerkleAdmissionError, match="requires seal_evidence_cid"):
        build_seal_manifest(
            workspace=WORKSPACE,
            campaign_id=CAMPAIGN_ID,
            campaign_root_cid=root_cid,
            set_cids=set_cids,
            seal_status="bound",
            seal_evidence_cid=None,
            receipt_cid=None,
            benchmark_artifact_cids=[],
            operation_id="seal-bad-bound",
        )
    with pytest.raises(MerkleAdmissionError, match="forbids seal_evidence_cid"):
        build_seal_manifest(
            workspace=WORKSPACE,
            campaign_id=CAMPAIGN_ID,
            campaign_root_cid=root_cid,
            set_cids=set_cids,
            seal_status="unavailable",
            seal_evidence_cid=_leaf("nope"),
            receipt_cid=None,
            benchmark_artifact_cids=[],
            operation_id="seal-bad-unavail",
        )
    incomplete = build_seal_manifest(
        workspace=WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        campaign_root_cid=root_cid,
        set_cids={"operator": _leaf("only-op")},
        seal_status="not_requested",
        seal_evidence_cid=None,
        receipt_cid=None,
        benchmark_artifact_cids=[],
        operation_id="seal-incomplete",
    )
    assert incomplete["required_set_completeness"] is False
    assert "policy" in incomplete["missing_sets"]


# ---------------------------------------------------------------------------
# Durable repository behavior
# ---------------------------------------------------------------------------


def test_current_merkle_root_starts_at_generation_zero(
    merkle: DurableAssuranceCampaignMerkleRepository,
) -> None:
    head = merkle.current_merkle_root(WORKSPACE)
    assert head.generation == 0
    assert head.root_cid is None
    assert head.campaign_root is None
    assert head.namespace == assurance_namespace(
        WORKSPACE, AssuranceNamespaceRole.MERKLE
    )


def test_commit_campaign_roots_and_idempotent_replay(
    merkle: DurableAssuranceCampaignMerkleRepository,
    coordination: DurableCoordinationStore,
) -> None:
    set_cids = _commit_all_sets(merkle, coordination)
    first = merkle.commit_campaign_roots(
        WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        set_commitments=set_cids,
        expected_generation=0,
        expected_root_cid=None,
        operation_id="root-commit-1",
    )
    assert first.status is AssuranceStoreStatus.UPDATED
    assert first.before.generation == 0
    assert first.after.generation == 1
    assert first.after.required_set_completeness is True
    assert first.after.campaign_id == CAMPAIGN_ID
    assert first.root_cid is not None
    assert first.local_durable is True

    replay = merkle.commit_campaign_roots(
        WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        set_commitments=set_cids,
        expected_generation=0,
        expected_root_cid=None,
        operation_id="root-commit-1",
    )
    assert replay.status is AssuranceStoreStatus.UNCHANGED
    assert replay.after.root_cid == first.root_cid
    assert replay.after.campaign_root == first.after.campaign_root

    verified = merkle.get_verified_campaign_merkle_root(str(first.root_cid))
    assert verified["required_set_completeness"] is True
    assert [e["set_kind"] for e in verified["set_entries"]] == list(
        REQUIRED_MERKLE_SET_KIND_VALUES
    )

    # Survive restart: reopen store and re-read head.
    restarted = DurableAssuranceCampaignMerkleRepository(coordination)
    try:
        head = restarted.current_merkle_root(WORKSPACE)
        assert head.generation == 1
        assert head.root_cid == first.root_cid
        assert head.required_set_completeness is True
        assert head.campaign_root == first.after.campaign_root
    finally:
        restarted.close()


def test_commit_rejects_incomplete_required_sets(
    merkle: DurableAssuranceCampaignMerkleRepository,
    coordination: DurableCoordinationStore,
) -> None:
    set_cids = _commit_all_sets(merkle, coordination)
    incomplete = dict(set_cids)
    del incomplete["held_out"]
    with pytest.raises(MerkleAdmissionError, match="required-set completeness"):
        merkle.commit_campaign_roots(
            WORKSPACE,
            campaign_id=CAMPAIGN_ID,
            set_commitments=incomplete,
            expected_generation=0,
            expected_root_cid=None,
            operation_id="root-incomplete",
        )


def test_unverified_receipt_rejected_before_merkle_inclusion(
    merkle: DurableAssuranceCampaignMerkleRepository,
    coordination: DurableCoordinationStore,
    artifacts: DurableAssuranceArtifactStore,
) -> None:
    # Persist an unverified receipt bypassing campaign admission by writing
    # raw projected bytes is not allowed through put_artifact either — so
    # write the unverified payload via direct store put after computing CID
    # without the store-level campaign gate, still as datasets wire form.
    payload = _unverified_campaign_payload()
    # put_artifact enforces signature gate; use low-level put of the wire
    # mapping so the block is durable but not verified.
    from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
        cid_for_artifact,
    )

    raw_cid = cid_for_artifact(payload)
    coordination.put(
        payload, expected_cid=raw_cid, codec="dag-json", replicate=False
    )

    members = [_put_leaf(coordination, "op-a"), raw_cid]
    sealed = build_merkle_set_commitment(
        workspace=WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        set_kind=MerkleSetKind.OPERATOR,
        member_cids=members,
        operation_id="set-unverified",
    )
    expected = cid_for_merkle_set(sealed)
    with pytest.raises(
        MerkleAdmissionError, match="unverified|signature|rejected before"
    ):
        merkle.commit_merkle_set(
            WORKSPACE,
            campaign_id=CAMPAIGN_ID,
            set_kind=MerkleSetKind.OPERATOR,
            member_cids=members,
            expected_cid=expected,
            operation_id="set-unverified",
        )


def test_verified_receipt_may_enter_merkle_set(
    merkle: DurableAssuranceCampaignMerkleRepository,
    coordination: DurableCoordinationStore,
    artifacts: DurableAssuranceArtifactStore,
) -> None:
    receipt_cid = _put_verified_receipt(coordination, artifacts)
    members = [_put_leaf(coordination, "surv-a"), receipt_cid]
    sealed = build_merkle_set_commitment(
        workspace=WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        set_kind=MerkleSetKind.SURVIVOR,
        member_cids=members,
        operation_id="set-verified-receipt",
    )
    expected = cid_for_merkle_set(sealed)
    result = merkle.commit_merkle_set(
        WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        set_kind=MerkleSetKind.SURVIVOR,
        member_cids=members,
        expected_cid=expected,
        operation_id="set-verified-receipt",
    )
    assert result.local_durable is True
    verified = merkle.get_verified_merkle_set(result.set_cid)
    assert receipt_cid in verified["member_cids"]


def test_unverified_receipt_rejected_before_seal_input(
    merkle: DurableAssuranceCampaignMerkleRepository,
    coordination: DurableCoordinationStore,
    artifacts: DurableAssuranceArtifactStore,
) -> None:
    set_cids = _commit_all_sets(merkle, coordination)
    root = merkle.commit_campaign_roots(
        WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        set_commitments=set_cids,
        expected_generation=0,
        expected_root_cid=None,
        operation_id="root-for-seal",
    )
    assert root.root_cid is not None

    payload = _unverified_campaign_payload()
    from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
        cid_for_artifact,
    )

    raw_cid = cid_for_artifact(payload)
    coordination.put(
        payload, expected_cid=raw_cid, codec="dag-json", replicate=False
    )

    sealed = build_seal_manifest(
        workspace=WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        campaign_root_cid=root.root_cid,
        set_cids=set_cids,
        seal_status=SealAvailabilityStatus.UNAVAILABLE,
        seal_evidence_cid=None,
        receipt_cid=raw_cid,
        benchmark_artifact_cids=[],
        operation_id="seal-unverified",
    )
    expected = cid_for_seal_manifest(sealed)
    with pytest.raises(
        MerkleAdmissionError, match="unverified|signature|rejected before"
    ):
        merkle.publish_seal_manifest(
            WORKSPACE,
            campaign_id=CAMPAIGN_ID,
            campaign_root_cid=root.root_cid,
            set_cids=set_cids,
            seal_status=SealAvailabilityStatus.UNAVAILABLE,
            seal_evidence_cid=None,
            receipt_cid=raw_cid,
            benchmark_artifact_cids=[],
            expected_cid=expected,
            operation_id="seal-unverified",
        )


def test_publish_seal_manifest_with_verified_receipt_and_benchmarks(
    merkle: DurableAssuranceCampaignMerkleRepository,
    coordination: DurableCoordinationStore,
    artifacts: DurableAssuranceArtifactStore,
) -> None:
    receipt_cid = _put_verified_receipt(coordination, artifacts, op="rcpt-seal")
    set_cids = _commit_all_sets(
        merkle,
        coordination,
        include_receipt_in=MerkleSetKind.OUTCOME,
        receipt_cid=receipt_cid,
    )
    root = merkle.commit_campaign_roots(
        WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        set_commitments=set_cids,
        expected_generation=0,
        expected_root_cid=None,
        operation_id="root-seal-ok",
    )
    assert root.root_cid is not None

    metric_a = _put_leaf(coordination, "metric-a")
    metric_b = _put_leaf(coordination, "metric-b")
    bench = build_benchmark_artifact(
        workspace=WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        benchmark_id="bench-1",
        artifact_cids=[metric_b, metric_a],
        summary="latency_p50=12",
        operation_id="bench-op-1",
    )
    bench_cid = cid_for_benchmark_artifact(bench)
    bench_result = merkle.persist_benchmark_artifact(
        WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        benchmark_id="bench-1",
        artifact_cids=[metric_b, metric_a],
        summary="latency_p50=12",
        expected_cid=bench_cid,
        operation_id="bench-op-1",
    )
    assert bench_result.local_durable is True
    assert bench_result.artifact_cid == bench_cid

    evidence = _put_leaf(coordination, "seal-evidence-block")
    sealed = build_seal_manifest(
        workspace=WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        campaign_root_cid=root.root_cid,
        set_cids=set_cids,
        seal_status=SealAvailabilityStatus.BOUND,
        seal_evidence_cid=evidence,
        receipt_cid=receipt_cid,
        benchmark_artifact_cids=[bench_cid],
        operation_id="seal-ok",
    )
    seal_cid = cid_for_seal_manifest(sealed)
    published = merkle.publish_seal_manifest(
        WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        campaign_root_cid=root.root_cid,
        set_cids=set_cids,
        seal_status=SealAvailabilityStatus.BOUND,
        seal_evidence_cid=evidence,
        receipt_cid=receipt_cid,
        benchmark_artifact_cids=[bench_cid],
        expected_cid=seal_cid,
        operation_id="seal-ok",
    )
    assert published.local_durable is True
    assert published.seal_available is True
    assert published.seal_status is SealAvailabilityStatus.BOUND
    assert published.required_set_completeness is True

    verified = merkle.get_verified_seal_manifest(seal_cid)
    assert verified["seal_status"] == "bound"
    assert verified["seal_available"] is True
    assert verified["receipt_cid"] == receipt_cid
    assert verified["benchmark_artifact_cids"] == [bench_cid]
    assert verified["required_set_completeness"] is True
    assert verified["missing_sets"] == []

    # Link seal into a successor merkle root head.
    linked = merkle.commit_campaign_roots(
        WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        set_commitments=set_cids,
        expected_generation=1,
        expected_root_cid=root.root_cid,
        operation_id="root-with-seal",
        seal_manifest_cid=seal_cid,
    )
    assert linked.status is AssuranceStoreStatus.UPDATED
    assert linked.after.generation == 2
    assert linked.after.seal_manifest_cid == seal_cid

    restarted = DurableAssuranceCampaignMerkleRepository(coordination)
    try:
        head = restarted.current_merkle_root(WORKSPACE)
        assert head.generation == 2
        assert head.seal_manifest_cid == seal_cid
        seal = restarted.get_verified_seal_manifest(seal_cid)
        assert seal["seal_available"] is True
        bench_verified = restarted.get_verified_benchmark_artifact(bench_cid)
        assert bench_verified["benchmark_id"] == "bench-1"
        assert bench_verified["artifact_cids"] == sorted([metric_a, metric_b])
    finally:
        restarted.close()


def test_benchmark_rejects_unknown_keys_and_missing_members(
    merkle: DurableAssuranceCampaignMerkleRepository,
) -> None:
    with pytest.raises(MerkleAdmissionError, match="unknown"):
        bad = build_benchmark_artifact(
            workspace=WORKSPACE,
            campaign_id=CAMPAIGN_ID,
            benchmark_id="bench-x",
            artifact_cids=[],
            summary="ok",
            operation_id="bench-x",
        )
        bad["extra"] = 1
        from ipfs_kit_py.adversarial_assurance_store.merkle import (
            admit_benchmark_artifact,
        )

        admit_benchmark_artifact(bad)

    sealed = build_benchmark_artifact(
        workspace=WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        benchmark_id="bench-missing",
        artifact_cids=[_leaf("missing-member")],
        summary="ok",
        operation_id="bench-missing",
    )
    expected = cid_for_benchmark_artifact(sealed)
    with pytest.raises(MerkleAdmissionError, match="not durable"):
        merkle.persist_benchmark_artifact(
            WORKSPACE,
            campaign_id=CAMPAIGN_ID,
            benchmark_id="bench-missing",
            artifact_cids=[_leaf("missing-member")],
            summary="ok",
            expected_cid=expected,
            operation_id="bench-missing",
        )


def test_stale_generation_conflict_does_not_move_head(
    merkle: DurableAssuranceCampaignMerkleRepository,
    coordination: DurableCoordinationStore,
) -> None:
    set_cids = _commit_all_sets(merkle, coordination)
    first = merkle.commit_campaign_roots(
        WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        set_commitments=set_cids,
        expected_generation=0,
        expected_root_cid=None,
        operation_id="root-a",
    )
    assert first.status is AssuranceStoreStatus.UPDATED
    stale = merkle.commit_campaign_roots(
        WORKSPACE,
        campaign_id=CAMPAIGN_ID,
        set_commitments=set_cids,
        expected_generation=0,
        expected_root_cid=None,
        operation_id="root-stale",
    )
    assert stale.status is AssuranceStoreStatus.CONFLICT
    head = merkle.current_merkle_root(WORKSPACE)
    assert head.root_cid == first.root_cid
    assert head.generation == 1
