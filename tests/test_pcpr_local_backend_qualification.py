"""PCPR-020 fail-closed local Kit backend requalification."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ipfs_kit_py.assurance.backend_certification import (
    REQUIRED_SUITE_OPERATIONS,
    CertificationDisposition,
)
from ipfs_kit_py.assurance.local_backend_qualification import (
    CLOSED_RELEASE_OUTCOMES,
    HERMETIC_CANDIDATE_SUITES,
    PCPR_020_GOAL_ID,
    PCPR_020_TASK_ID,
    QUALIFICATION_INTERFACE,
    LocalBackendQualificationError,
    QualificationProbe,
    qualify_current_head_local_backend,
    refuse_hermetic_as_live,
    run_live_local_backend_suite,
    validate_pcpr_020_outer_receipt,
)
from ipfs_kit_py.assurance.local_durable import (
    BACKEND_ID,
    LiveLocalBackendError,
    LiveLocalFilesystemAdapter,
)
from ipfs_kit_py.core.operation_contracts import ErrorCode


NOW = datetime(2026, 9, 2, 2, 0, tzinfo=timezone.utc)


def test_closed_vocabularies_match_pcpr_020_requirements() -> None:
    assert PCPR_020_TASK_ID == "PCPR-020"
    assert PCPR_020_GOAL_ID == "PCPR-G300"
    assert QUALIFICATION_INTERFACE == "LocalBackendQualification@1"
    assert "release_candidate_qualified" in CLOSED_RELEASE_OUTCOMES
    assert "rnd_non_promoted" not in CLOSED_RELEASE_OUTCOMES
    assert HERMETIC_CANDIDATE_SUITES[-1].endswith(
        "test_pcpr_local_backend_qualification.py"
    )


def test_hermetic_adapter_cannot_mint_live_qualification() -> None:
    class _Hermetic:
        backend_id = "hermetic_filesystem_reference"
        live_provider = False
        is_hermetic = True
        simulated = False

    with pytest.raises(LocalBackendQualificationError):
        refuse_hermetic_as_live(_Hermetic())

    class _Simulated:
        backend_id = "local_filesystem"
        live_provider = True
        is_hermetic = False
        simulated = True

    with pytest.raises(LocalBackendQualificationError):
        refuse_hermetic_as_live(_Simulated())


def test_secret_configuration_is_rejected_without_retention(tmp_path: Path) -> None:
    secret = "pcpr-020-do-not-retain-this-secret"
    with pytest.raises(LiveLocalBackendError) as caught:
        LiveLocalFilesystemAdapter(
            tmp_path / "secret", configuration={"api_token": secret}
        )
    assert caught.value.error.code is ErrorCode.SECRET_MATERIAL
    assert secret not in str(caught.value)
    assert not (tmp_path / "secret").exists()


def test_live_local_suite_observes_python_durability_and_blocks_parity(
    tmp_path: Path,
) -> None:
    observations = run_live_local_backend_suite(tmp_path / "suite", now=NOW)
    ops = {item.operation: item for item in observations}
    assert set(ops) == set(REQUIRED_SUITE_OPERATIONS)
    for operation in REQUIRED_SUITE_OPERATIONS:
        if operation == "interface_parity":
            continue
        item = ops[operation]
        assert item.status.value == "passed"
        assert item.environment == "live"
        assert item.source == "live_observed"
        assert item.signature_valid is True
        assert item.freshness == "current"
    parity = ops["interface_parity"]
    assert parity.status.value == "blocked"
    assert parity.source == "unavailable"
    assert "cli_unavailable" in parity.limitations
    assert "mcp_unavailable" in parity.limitations
    assert "mcpp_unavailable" in parity.limitations


def test_current_head_is_rnd_non_promoted_and_not_a_release() -> None:
    verdict = qualify_current_head_local_backend(now=NOW)
    assert verdict.promotion_status == "rnd_non_promoted"
    assert verdict.supervisor_disposition == "supervisor_non_promoted"
    assert verdict.closed_release_outcome is None
    assert verdict.release_claim is False
    assert verdict.completion_authoritative is False
    assert verdict.contracts_frozen is False
    assert verdict.duckdb_or_quack_state_written is False
    assert verdict.local_backend_live_qualified is False
    assert verdict.suite_complete is False
    assert verdict.certification_disposition == CertificationDisposition.CONDITIONAL.value
    assert verdict.simulated_results_represented_as_live is False
    assert verdict.hermetic_results_represented_as_live is False
    assert verdict.python_local_durability_observed is True
    assert verdict.interface_parity_qualified is False
    assert verdict.live_ipfs_qualified is False
    assert verdict.live_ipfs_evidence_kind == "unavailable"
    assert verdict.this_task_created_competing_authority is False
    assert verdict.promotion_status not in CLOSED_RELEASE_OUTCOMES
    assert verdict.verdict_cid.startswith("b")
    assert "interface_parity" in verdict.operations_missing
    assert "write" in verdict.operations_observed
    assert "corruption" in verdict.operations_observed
    probe_ids = {item.probe_id for item in verdict.probes}
    assert "live_local_filesystem_adapter" in probe_ids
    assert "hermetic_filesystem_adapter_not_live" in probe_ids
    assert "cli_local_parity" in probe_ids
    assert "mcp_local_parity" in probe_ids
    assert "mcpp_local_parity" in probe_ids


def test_restart_survives_reopen(tmp_path: Path) -> None:
    adapter = LiveLocalFilesystemAdapter(tmp_path / "store")
    payload = b"pcpr-020-reopen"
    put = adapter.put("objects/reopen.bin", payload)
    adapter.close()
    restored = LiveLocalFilesystemAdapter.reopen(tmp_path / "store")
    got = restored.get("objects/reopen.bin")
    assert got.data == payload
    assert got.resulting_content_cid == put.resulting_content_cid
    refuse_hermetic_as_live(restored)


def test_corruption_fails_closed(tmp_path: Path) -> None:
    adapter = LiveLocalFilesystemAdapter(tmp_path / "store")
    adapter.put("objects/integrity.bin", b"clean")
    adapter.corrupt_for_test("objects/integrity.bin", b"dirty")
    with pytest.raises(LiveLocalBackendError) as caught:
        adapter.get("objects/integrity.bin")
    assert caught.value.error.code is ErrorCode.INTEGRITY_FAILURE


def test_receipt_validator_rejects_closed_release() -> None:
    with pytest.raises(LocalBackendQualificationError):
        validate_pcpr_020_outer_receipt(
            {
                "task_id": "PCPR-020",
                "acceptance": {
                    "promotion_status": "release_candidate_qualified",
                    "closed_release_outcome": "release_candidate_qualified",
                    "release_claim": True,
                },
            }
        )


def test_receipt_validator_accepts_rnd_non_promoted() -> None:
    validate_pcpr_020_outer_receipt(
        {
            "task_id": "PCPR-020",
            "evidence_legend": {"measured": "measured"},
            "acceptance": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "release_claim": False,
            },
            "qualification_verdict": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "local_backend_live_qualified": False,
                "simulated_results_represented_as_live": False,
            },
        }
    )


def test_unavailable_probe_fixture_shape() -> None:
    probe = QualificationProbe(
        probe_id="fixture",
        present=None,
        evidence_kind="unavailable",
        live=False,
        simulated_represented_as_live=False,
        reason="fixture unavailable",
    )
    mapping = probe.to_mapping()
    assert mapping["evidence_kind"] == "unavailable"
    assert mapping["live"] is False
    assert json.loads(json.dumps(mapping))["probe_id"] == "fixture"


def test_backend_id_is_local_filesystem() -> None:
    assert BACKEND_ID == "local_filesystem"
    assert LiveLocalFilesystemAdapter.backend_id == "local_filesystem"
    assert LiveLocalFilesystemAdapter.production_authorized is False
    assert LiveLocalFilesystemAdapter.simulated is False
