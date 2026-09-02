"""PCPR-022 fail-closed Iroh qualification or honest de-scope."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ipfs_kit_py.assurance.backend_certification import (
    REQUIRED_SUITE_OPERATIONS,
    CertificationDisposition,
)
from ipfs_kit_py.assurance.iroh import (
    BACKEND_ID,
    LIVE_SUPPORT_CLAIM,
    SIDECAR_BINARY,
    SIDECAR_DIGEST,
    SUPPORT_CLASS,
    IsolatedIrohSession,
    IrohBackendError,
    LiveIrohAdapter,
    provision_isolated_iroh_sidecar,
)
from ipfs_kit_py.assurance.iroh_qualification import (
    CLOSED_RELEASE_OUTCOMES,
    HERMETIC_CANDIDATE_SUITES,
    IROH_SPECIFIC_OPERATIONS,
    PCPR_022_GOAL_ID,
    PCPR_022_TASK_ID,
    QUALIFICATION_INTERFACE,
    IrohQualificationError,
    QualificationProbe,
    probe_sealed_iroh_sidecar,
    qualify_current_head_iroh,
    refuse_simulated_as_live,
    sealed_which,
    validate_pcpr_022_outer_receipt,
)
from ipfs_kit_py.core.operation_contracts import ErrorCode


NOW = datetime(2026, 9, 2, 3, 0, tzinfo=timezone.utc)


def test_closed_vocabularies_match_pcpr_022_requirements() -> None:
    assert PCPR_022_TASK_ID == "PCPR-022"
    assert PCPR_022_GOAL_ID == "PCPR-G300"
    assert QUALIFICATION_INTERFACE == "IrohQualification@1"
    assert "release_candidate_qualified" in CLOSED_RELEASE_OUTCOMES
    assert "rnd_non_promoted" not in CLOSED_RELEASE_OUTCOMES
    assert "non_promoted_live_storage_gap" in CLOSED_RELEASE_OUTCOMES
    assert HERMETIC_CANDIDATE_SUITES[-1].endswith("test_pcpr_iroh_qualification.py")
    assert "pin_persistence" in IROH_SPECIFIC_OPERATIONS
    assert "upgrade" in IROH_SPECIFIC_OPERATIONS
    assert "rollback" in IROH_SPECIFIC_OPERATIONS
    assert "daemon_loss" in IROH_SPECIFIC_OPERATIONS
    assert LIVE_SUPPORT_CLAIM is False
    assert SUPPORT_CLASS == "experimental"


def test_simulated_adapter_cannot_mint_live_qualification() -> None:
    def _transport(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {"jsonrpc": "2.0", "protocol_version": 1, "id": "x", "result": {"ready": True}}

    adapter = LiveIrohAdapter(transport=_transport)
    assert adapter.simulated is True
    assert adapter.live_provider is False
    assert adapter.is_hermetic is True
    assert adapter.transport_kind == "injected"
    assert adapter.live_support_claim is False
    with pytest.raises(IrohQualificationError):
        refuse_simulated_as_live(adapter)


def test_hermetic_and_wrong_backend_cannot_mint_live() -> None:
    class _Hermetic:
        backend_id = "iroh"
        live_provider = False
        is_hermetic = True
        simulated = False
        transport_kind = "unix-rpc"
        live_support_claim = False

    with pytest.raises(IrohQualificationError):
        refuse_simulated_as_live(_Hermetic())

    class _WrongBackend:
        backend_id = "pinned_ipfs"
        live_provider = True
        is_hermetic = False
        simulated = False
        transport_kind = "unix-rpc"
        live_support_claim = False

    with pytest.raises(IrohQualificationError):
        refuse_simulated_as_live(_WrongBackend())


def test_secret_configuration_is_rejected_without_retention() -> None:
    secret = "pcpr-022-do-not-retain-this-secret"
    with pytest.raises(IrohBackendError) as caught:
        LiveIrohAdapter(configuration={"api_token": secret})
    assert caught.value.error.code is ErrorCode.SECRET_MATERIAL
    assert secret not in str(caught.value)

    with pytest.raises(IrohBackendError) as nested:
        LiveIrohAdapter(configuration={"identity": {"node_key": secret}})
    assert nested.value.error.code is ErrorCode.SECRET_MATERIAL
    assert secret not in str(nested.value)


def test_absent_sidecar_health_is_typed_unavailable() -> None:
    adapter = LiveIrohAdapter("unix:///tmp/pcpr-022-missing-iroh.sock")
    refuse_simulated_as_live(adapter)
    with pytest.raises(IrohBackendError) as caught:
        adapter.health()
    assert caught.value.error.code is ErrorCode.UNAVAILABLE
    assert caught.value.error.state.value == "unavailable"


def test_provision_without_binary_is_typed_unavailable(tmp_path: Path) -> None:
    with pytest.raises(IrohBackendError) as caught:
        provision_isolated_iroh_sidecar(
            sidecar_binary=None, state_root=tmp_path / "state"
        )
    assert caught.value.error.code is ErrorCode.UNAVAILABLE

    missing = tmp_path / "not-iroh"
    with pytest.raises(IrohBackendError) as caught_missing:
        provision_isolated_iroh_sidecar(
            sidecar_binary=missing, state_root=tmp_path / "state2"
        )
    assert caught_missing.value.error.code is ErrorCode.UNAVAILABLE


def test_sealed_path_probe_does_not_use_inherited_path() -> None:
    probe = probe_sealed_iroh_sidecar()
    assert probe.probe_id == "sealed_iroh_sidecar"
    assert probe.simulated_represented_as_live is False
    assert probe.live is False
    path = sealed_which(SIDECAR_BINARY)
    if path == "unavailable":
        assert probe.present is False
        assert probe.evidence_kind == "unavailable"
        assert "typed unavailable" in probe.reason
        assert "experimental" in probe.reason
    else:
        assert probe.present is True
        assert Path(path).is_file()
        assert str(Path(path).parent) in {
            "/usr/local/sbin",
            "/usr/local/bin",
            "/usr/sbin",
            "/usr/bin",
        }


def test_current_head_is_rnd_non_promoted_and_not_a_release() -> None:
    verdict = qualify_current_head_iroh(now=NOW)
    assert verdict.promotion_status == "rnd_non_promoted"
    assert verdict.supervisor_disposition == "supervisor_non_promoted"
    assert verdict.closed_release_outcome is None
    assert verdict.release_claim is False
    assert verdict.completion_authoritative is False
    assert verdict.contracts_frozen is False
    assert verdict.duckdb_or_quack_state_written is False
    assert verdict.iroh_live_qualified is False
    assert verdict.suite_complete is False
    assert verdict.live_support_claim is False
    assert verdict.support_class == "experimental"
    assert verdict.certification_disposition == (
        CertificationDisposition.UNAVAILABLE.value
    )
    assert verdict.simulated_results_represented_as_live is False
    assert verdict.hermetic_results_represented_as_live is False
    assert verdict.interface_parity_qualified is False
    assert verdict.live_iroh_evidence_kind == "unavailable"
    assert verdict.sidecar_identity == SIDECAR_DIGEST
    assert verdict.this_task_created_competing_authority is False
    assert verdict.promotion_status not in CLOSED_RELEASE_OUTCOMES
    assert verdict.verdict_cid.startswith("b")
    assert set(item["operation"] for item in verdict.observations) == set(
        REQUIRED_SUITE_OPERATIONS
    )
    for item in verdict.observations:
        if item["operation"] == "interface_parity":
            continue
        assert item["status"] in {"unobserved", "blocked"}
        assert item["source"] == "unavailable"
        assert item["signature_valid"] is False
    extra_ops = {item["operation"] for item in verdict.iroh_operations}
    assert extra_ops == set(IROH_SPECIFIC_OPERATIONS)
    for item in verdict.iroh_operations:
        assert item["evidence_kind"] == "unavailable"
        assert item["live"] is False
        assert item["simulated_represented_as_live"] is False
    probe_ids = {item.probe_id for item in verdict.probes}
    assert "live_iroh_adapter" in probe_ids
    assert "sealed_iroh_sidecar" in probe_ids
    assert "sealed_iroh_binary" in probe_ids
    assert "sidecar_identity" in probe_ids
    assert "auto_install_not_used" in probe_ids
    assert "live_support_claim_removed" in probe_ids
    assert "cli_iroh_parity" in probe_ids
    assert "mcp_iroh_parity" in probe_ids
    assert "mcpp_iroh_parity" in probe_ids
    if verdict.sealed_iroh_sidecar == "unavailable":
        assert verdict.python_iroh_observed is False
        assert verdict.descoped is True


def test_injected_transport_round_trip_is_not_live() -> None:
    store: dict[str, bytes] = {}

    def _transport(
        *,
        method: str,
        params: dict[str, object],
        request_id: str,
        timeout: float,
    ) -> dict[str, object]:
        del timeout
        if method == "system.health":
            return {
                "jsonrpc": "2.0",
                "protocol_version": 1,
                "id": request_id,
                "result": {"ready": True, "version": "simulated"},
            }
        if method == "blobs.ingest":
            source = Path(str(params["source_path"]))
            payload = source.read_bytes()
            digest = str(params.get("expected_hash") or payload.hex()[:64].ljust(64, "0"))
            store[digest] = payload
            return {
                "jsonrpc": "2.0",
                "protocol_version": 1,
                "id": request_id,
                "result": {"blob_hash": digest, "size": len(payload)},
            }
        if method == "blobs.stat":
            digest = str(params["hash"])
            payload = store[digest]
            return {
                "jsonrpc": "2.0",
                "protocol_version": 1,
                "id": request_id,
                "result": {"hash": digest, "size": len(payload), "complete": True},
            }
        if method == "blobs.read_range":
            digest = str(params["hash"])
            payload = store[digest]
            import base64

            return {
                "jsonrpc": "2.0",
                "protocol_version": 1,
                "id": request_id,
                "result": {
                    "hash": digest,
                    "offset": 0,
                    "length": len(payload),
                    "verified": True,
                    "data": base64.b64encode(payload).decode("ascii"),
                },
            }
        if method == "blobs.protect":
            return {
                "jsonrpc": "2.0",
                "protocol_version": 1,
                "id": request_id,
                "result": {"protected": True},
            }
        return {
            "jsonrpc": "2.0",
            "protocol_version": 1,
            "id": request_id,
            "error": {"code": "unavailable", "message": "missing"},
        }

    adapter = LiveIrohAdapter(transport=_transport)
    with pytest.raises(IrohQualificationError):
        refuse_simulated_as_live(adapter)
    payload = b"pcpr-022-simulated-only"
    added = adapter.add(payload, pin=True)
    got = adapter.cat(added.resulting_content_cid)
    assert got.data == payload
    assert adapter.simulated is True
    assert adapter.live_provider is False
    assert adapter.live_support_claim is False


def test_receipt_validator_rejects_closed_release() -> None:
    with pytest.raises(IrohQualificationError):
        validate_pcpr_022_outer_receipt(
            {
                "task_id": "PCPR-022",
                "acceptance": {
                    "promotion_status": "release_candidate_qualified",
                    "closed_release_outcome": "release_candidate_qualified",
                    "release_claim": True,
                },
            }
        )
    with pytest.raises(IrohQualificationError):
        validate_pcpr_022_outer_receipt(
            {
                "task_id": "PCPR-022",
                "acceptance": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "release_claim": False,
                },
                "qualification_verdict": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "iroh_live_qualified": True,
                    "simulated_results_represented_as_live": False,
                },
            }
        )
    with pytest.raises(IrohQualificationError):
        validate_pcpr_022_outer_receipt(
            {
                "task_id": "PCPR-022",
                "acceptance": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "release_claim": False,
                    "live_support_claim": True,
                },
            }
        )


def test_receipt_validator_accepts_rnd_non_promoted() -> None:
    validate_pcpr_022_outer_receipt(
        {
            "task_id": "PCPR-022",
            "evidence_legend": {"measured": "measured"},
            "acceptance": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "release_claim": False,
                "live_support_claim": False,
            },
            "qualification_verdict": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "iroh_live_qualified": False,
                "simulated_results_represented_as_live": False,
                "live_support_claim": False,
                "live_iroh_evidence_kind": "unavailable",
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


def test_backend_id_is_iroh() -> None:
    assert BACKEND_ID == "iroh"
    assert LiveIrohAdapter.backend_id == "iroh"
    assert LiveIrohAdapter.production_authorized is False
    assert LiveIrohAdapter.simulated is False
    assert LiveIrohAdapter.live_support_claim is False
    default = LiveIrohAdapter()
    assert default.live_provider is True
    assert default.transport_kind == "unix-rpc"
    assert IsolatedIrohSession.__name__ == "IsolatedIrohSession"
