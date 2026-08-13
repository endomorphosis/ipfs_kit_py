"""Privacy proofs for the durable governor store (SCG-022).

Acceptance:

* raw private source never appears in public reports (raw_private_public_reports == 0)
* sealed artifacts reject private-field markers at admission
* public history projections reject local paths and private markers
* recovery reports remain free of private payload content
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
    DurableCoordinationStore,
    cid_for_artifact,
)
from ipfs_kit_py.semantic_governor_store.artifacts import (
    PRIVATE_FIELD_MARKERS,
    DurableSemanticGovernorStore,
    GovernorArtifactAdmissionError,
    cid_for_governor_artifact,
    reject_private_raw_source,
    seal_governor_artifact,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    GovernorArtifactKind,
    GovernorStoreStatus,
)
from ipfs_kit_py.semantic_governor_store.history import (
    DurableAuditHistoryStore,
    GovernorHistoryAdmissionError,
    project_public_value,
    reject_public_local_paths,
)
from ipfs_kit_py.semantic_governor_store.policy import (
    DurableCompressionPolicyRepository,
    DurablePromotionStateRepository,
    GovernorPolicyAdmissionError,
)
from ipfs_kit_py.semantic_governor_store.recovery import recover_governor_store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


PRIVATE_MARKERS_SAMPLE: tuple[str, ...] = (
    "raw_private_source",
    "private_source",
    "raw_source",
    "source_text",
    "password",
    "secret",
    "api_key",
    "private_key",
    "access_token",
    "hidden_witness",
)


def _public_entry(store: DurableCoordinationStore, name: str) -> str:
    payload = {
        "schema": "example/governor-public-entry@1",
        "name": name,
        "status": "complete",
        "summary": "portable public facts only",
    }
    return store.put(payload, expected_cid=cid_for_artifact(payload), replicate=False)[
        "cid"
    ]


def _block(store: DurableCoordinationStore, name: str) -> str:
    payload = {"schema": "example/governor-policy@1", "name": name}
    return store.put(payload, expected_cid=cid_for_artifact(payload), replicate=False)[
        "cid"
    ]


def _contains_private_marker(value: Any) -> bool:
    blob = str(value).lower()
    for marker in PRIVATE_MARKERS_SAMPLE:
        if marker in blob:
            return True
    for marker in PRIVATE_FIELD_MARKERS:
        if marker in blob:
            return True
    return False


WORKSPACE = "default"


# ---------------------------------------------------------------------------
# Artifact admission — private raw source fails closed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", sorted(PRIVATE_FIELD_MARKERS))
def test_seal_rejects_every_private_field_marker(field: str) -> None:
    payload = {"case_id": "x", "summary": "ok", field: "LEAK"}
    with pytest.raises(GovernorArtifactAdmissionError, match="private"):
        seal_governor_artifact(GovernorArtifactKind.AUDIT, payload)


def test_put_artifact_rejects_nested_private_source(
    tmp_path: Path,
) -> None:
    private_payload = {
        "case_id": "nested",
        "meta": {"raw_private_source": "SECRET_SOURCE"},
    }
    # CID computation itself must refuse private payloads.
    with pytest.raises(GovernorArtifactAdmissionError, match="private"):
        cid_for_governor_artifact(GovernorArtifactKind.AUDIT, private_payload)

    # Valid-form CID so put reaches seal / private admission (not CID grammar).
    public_cid = cid_for_governor_artifact(
        GovernorArtifactKind.AUDIT,
        {"case_id": "nested", "meta": {"note": "public"}},
    )
    with DurableCoordinationStore(tmp_path / "artifact-private") as coordination:
        with DurableSemanticGovernorStore(coordination) as governor:
            with pytest.raises(GovernorArtifactAdmissionError, match="private"):
                governor.put_artifact(
                    GovernorArtifactKind.AUDIT,
                    private_payload,
                    expected_cid=public_cid,
                    operation_id="private-put",
                    replicate=False,
                )


def test_reject_private_raw_source_helper_is_recursive() -> None:
    with pytest.raises(GovernorArtifactAdmissionError, match="private"):
        reject_private_raw_source(
            {"ok": True, "items": [{"nested": {"password": "x"}}]}
        )
    # Public-only payload is admitted.
    reject_private_raw_source(
        {"case_id": "public", "summary": "no secrets", "counts": [1, 2, 3]}
    )


# ---------------------------------------------------------------------------
# Public history projection — zero private leakage
# ---------------------------------------------------------------------------


def test_public_history_projection_has_zero_private_reports(
    tmp_path: Path,
) -> None:
    raw_private_public_reports = 0
    with DurableCoordinationStore(tmp_path / "hist-public") as store:
        history = DurableAuditHistoryStore(store)
        first = _public_entry(store, "pub-1")
        second = _public_entry(store, "pub-2")
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
        if _contains_private_marker(dict(projection)):
            raw_private_public_reports += 1
        # Host store path must not appear either.
        if str(store.root) in str(dict(projection)):
            raw_private_public_reports += 1

        private = history.private_history_projection(WORKSPACE, "audit")
        if _contains_private_marker(dict(private)):
            raw_private_public_reports += 1

    assert raw_private_public_reports == 0


def test_public_projection_helpers_reject_private_and_paths() -> None:
    with pytest.raises(GovernorHistoryAdmissionError, match="private"):
        project_public_value({"summary": "ok", "raw_private_source": "LEAK"})
    with pytest.raises(GovernorHistoryAdmissionError, match="private"):
        project_public_value({"nested": {"api_key": "k"}})
    with pytest.raises(GovernorHistoryAdmissionError, match="local path"):
        project_public_value({"note": "/tmp/secret.bin"})
    with pytest.raises(GovernorHistoryAdmissionError, match="local path"):
        reject_public_local_paths({"source_path": "relative/named/path"})
    with pytest.raises(GovernorHistoryAdmissionError, match="local path"):
        reject_public_local_paths({"note": "C:\\Users\\secret"})
    # Portable CID references remain admissible.
    cid = "baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert project_public_value({"entry_cid": cid})["entry_cid"] == cid


def test_history_manifest_builder_rejects_private_injection(
    tmp_path: Path,
) -> None:
    """Manifests are public durable evidence — private keys cannot enter."""

    from ipfs_kit_py.semantic_governor_store.history import build_history_manifest

    entry = cid_for_artifact({"schema": "example/x@1", "n": 1})
    # build_history_manifest only accepts closed fields; ensure operation_id
    # cannot smuggle private content through unstructured side channels.
    manifest = build_history_manifest(
        workspace=WORKSPACE,
        role="audit",
        generation=1,
        entry_cid=entry,
        previous_head_cid=None,
        operation_id="clean-op-1",
    )
    assert not _contains_private_marker(manifest)
    with DurableCoordinationStore(tmp_path / "manifest") as store:
        # Storing a handcrafted private-bearing "entry" is fine as opaque
        # bytes, but public projection of history still only exposes CIDs.
        private_payload = {
            "schema": "example/private-bearing@1",
            "note": "opaque block; not a public projection",
        }
        private_cid = store.put(
            private_payload,
            expected_cid=cid_for_artifact(private_payload),
            replicate=False,
        )["cid"]
        history = DurableAuditHistoryStore(store)
        history.append_audit(
            WORKSPACE,
            entry_cid=private_cid,
            expected_generation=0,
            expected_head_cid=None,
            operation_id="opaque-1",
        )
        projection = history.public_history_projection(WORKSPACE, "audit")
        assert projection["entries"][0]["entry_cid"] == private_cid
        # Projection never expands entry bytes into the public report.
        assert "opaque block" not in str(dict(projection))
        assert not _contains_private_marker(dict(projection))


# ---------------------------------------------------------------------------
# Recovery report privacy
# ---------------------------------------------------------------------------


def test_recovery_report_exposes_no_private_payload_bytes(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "recovery-privacy") as store:
        history = DurableAuditHistoryStore(store)
        policy = DurableCompressionPolicyRepository(store)
        promotion = DurablePromotionStateRepository(store)

        entry = _public_entry(store, "recover-me")
        history.append_audit(
            WORKSPACE,
            entry_cid=entry,
            expected_generation=0,
            expected_head_cid=None,
            operation_id="recover-audit",
        )
        policy_cid = _block(store, "policy")
        policy.compare_and_swap_policy(
            WORKSPACE,
            expected_generation=0,
            expected_policy_cid=None,
            new_policy_cid=policy_cid,
            operation_id="recover-policy",
        )
        promo = _block(store, "promo")
        candidate = _block(store, "cand")
        auth = _block(store, "auth")
        promotion.compare_and_swap_promotion(
            WORKSPACE,
            expected_generation=0,
            expected_promotion_cid=None,
            new_promotion_cid=promo,
            operation_id="recover-promo",
            candidate_cid=candidate,
            authorization_cid=auth,
        )

        report = recover_governor_store(store, rebuild=True)
        wire = report.to_dict()
        assert report.errors == ()
        assert not _contains_private_marker(wire)
        # Recovery never embeds raw entry payloads — only head CIDs/generations.
        assert "recover-me" not in str(wire)
        assert str(store.root) not in str(wire)


# ---------------------------------------------------------------------------
# Promotion admission privacy / authority boundary
# ---------------------------------------------------------------------------


def test_candidate_self_authorization_fails_closed(tmp_path: Path) -> None:
    with DurableCoordinationStore(tmp_path / "self-auth") as store:
        promotion = DurablePromotionStateRepository(store)
        candidate = _block(store, "self")
        promo = _block(store, "promo")
        with pytest.raises(
            GovernorPolicyAdmissionError, match="cannot authorize its own promotion"
        ):
            promotion.compare_and_swap_promotion(
                WORKSPACE,
                expected_generation=0,
                expected_promotion_cid=None,
                new_promotion_cid=promo,
                operation_id="self-auth",
                candidate_cid=candidate,
                authorization_cid=candidate,
            )
        assert promotion.current_promotion(WORKSPACE).generation == 0
        report = recover_governor_store(store, rebuild=True)
        # Failed promotion invents nothing.
        assert report.reconstructed_promotion_heads == ()


def test_public_surfaces_across_roles_remain_clean(tmp_path: Path) -> None:
    raw_private_public_reports = 0
    with DurableCoordinationStore(tmp_path / "roles") as store:
        history = DurableAuditHistoryStore(store)
        for role, name in (
            ("audit", "a1"),
            ("calibration", "c1"),
            ("benchmark", "b1"),
        ):
            entry = _public_entry(store, name)
            result = history.append_history(
                WORKSPACE,
                role,
                entry_cid=entry,
                expected_generation=0,
                expected_head_cid=None,
                operation_id=f"{role}-1",
            )
            assert result.status is GovernorStoreStatus.UPDATED
            projection = history.public_history_projection(WORKSPACE, role)
            if _contains_private_marker(dict(projection)):
                raw_private_public_reports += 1
            if str(store.root) in str(dict(projection)):
                raw_private_public_reports += 1

    assert raw_private_public_reports == 0
