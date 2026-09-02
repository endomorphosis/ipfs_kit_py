"""PCPR-021 fail-closed pinned IPFS backend qualification."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ipfs_kit_py.assurance.backend_certification import (
    REQUIRED_SUITE_OPERATIONS,
    CertificationDisposition,
)
from ipfs_kit_py.assurance.pinned_ipfs import (
    BACKEND_ID,
    PINNED_DAEMON_BINARY,
    PINNED_DAEMON_DIGEST,
    LivePinnedIpfsAdapter,
    PinnedIpfsBackendError,
    provision_isolated_pinned_daemon,
)
from ipfs_kit_py.assurance.pinned_ipfs_qualification import (
    CLOSED_RELEASE_OUTCOMES,
    HERMETIC_CANDIDATE_SUITES,
    IPFS_SPECIFIC_OPERATIONS,
    PCPR_021_GOAL_ID,
    PCPR_021_TASK_ID,
    QUALIFICATION_INTERFACE,
    PinnedIpfsQualificationError,
    QualificationProbe,
    probe_sealed_ipfs_binary,
    qualify_current_head_pinned_ipfs,
    refuse_simulated_as_live,
    sealed_which,
    validate_pcpr_021_outer_receipt,
)
from ipfs_kit_py.core.operation_contracts import ErrorCode


NOW = datetime(2026, 9, 2, 2, 0, tzinfo=timezone.utc)


def test_closed_vocabularies_match_pcpr_021_requirements() -> None:
    assert PCPR_021_TASK_ID == "PCPR-021"
    assert PCPR_021_GOAL_ID == "PCPR-G300"
    assert QUALIFICATION_INTERFACE == "PinnedIpfsQualification@1"
    assert "release_candidate_qualified" in CLOSED_RELEASE_OUTCOMES
    assert "rnd_non_promoted" not in CLOSED_RELEASE_OUTCOMES
    assert "non_promoted_live_storage_gap" in CLOSED_RELEASE_OUTCOMES
    assert HERMETIC_CANDIDATE_SUITES[-1].endswith(
        "test_pcpr_pinned_ipfs_qualification.py"
    )
    assert "pin_persistence" in IPFS_SPECIFIC_OPERATIONS
    assert "upgrade" in IPFS_SPECIFIC_OPERATIONS
    assert "rollback" in IPFS_SPECIFIC_OPERATIONS
    assert "daemon_loss" in IPFS_SPECIFIC_OPERATIONS


def test_simulated_adapter_cannot_mint_live_qualification() -> None:
    def _transport(**kwargs: object) -> tuple[int, bytes]:
        del kwargs
        return 200, b'{"Version":"0.0-simulated"}'

    adapter = LivePinnedIpfsAdapter(transport=_transport)
    assert adapter.simulated is True
    assert adapter.live_provider is False
    assert adapter.is_hermetic is True
    assert adapter.transport_kind == "injected"
    with pytest.raises(PinnedIpfsQualificationError):
        refuse_simulated_as_live(adapter)


def test_hermetic_and_wrong_backend_cannot_mint_live() -> None:
    class _Hermetic:
        backend_id = "pinned_ipfs"
        live_provider = False
        is_hermetic = True
        simulated = False
        transport_kind = "http"

    with pytest.raises(PinnedIpfsQualificationError):
        refuse_simulated_as_live(_Hermetic())

    class _WrongBackend:
        backend_id = "local_filesystem"
        live_provider = True
        is_hermetic = False
        simulated = False
        transport_kind = "http"

    with pytest.raises(PinnedIpfsQualificationError):
        refuse_simulated_as_live(_WrongBackend())


def test_secret_configuration_is_rejected_without_retention() -> None:
    secret = "pcpr-021-do-not-retain-this-secret"
    with pytest.raises(PinnedIpfsBackendError) as caught:
        LivePinnedIpfsAdapter(configuration={"api_token": secret})
    assert caught.value.error.code is ErrorCode.SECRET_MATERIAL
    assert secret not in str(caught.value)


def test_absent_daemon_health_is_typed_unavailable() -> None:
    adapter = LivePinnedIpfsAdapter("http://127.0.0.1:1")
    refuse_simulated_as_live(adapter)
    with pytest.raises(PinnedIpfsBackendError) as caught:
        adapter.health()
    assert caught.value.error.code is ErrorCode.UNAVAILABLE
    assert caught.value.error.state.value == "unavailable"


def test_provision_without_binary_is_typed_unavailable(tmp_path: Path) -> None:
    with pytest.raises(PinnedIpfsBackendError) as caught:
        provision_isolated_pinned_daemon(
            ipfs_binary=None, repo=tmp_path / "repo"
        )
    assert caught.value.error.code is ErrorCode.UNAVAILABLE

    missing = tmp_path / "not-ipfs"
    with pytest.raises(PinnedIpfsBackendError) as caught_missing:
        provision_isolated_pinned_daemon(
            ipfs_binary=missing, repo=tmp_path / "repo2"
        )
    assert caught_missing.value.error.code is ErrorCode.UNAVAILABLE


def test_sealed_path_probe_does_not_use_inherited_path() -> None:
    probe = probe_sealed_ipfs_binary()
    assert probe.probe_id == "sealed_ipfs_binary"
    assert probe.simulated_represented_as_live is False
    assert probe.live is False
    path = sealed_which(PINNED_DAEMON_BINARY)
    if path == "unavailable":
        assert probe.present is False
        assert probe.evidence_kind == "unavailable"
        assert "typed unavailable" in probe.reason
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
    verdict = qualify_current_head_pinned_ipfs(now=NOW)
    assert verdict.promotion_status == "rnd_non_promoted"
    assert verdict.supervisor_disposition == "supervisor_non_promoted"
    assert verdict.closed_release_outcome is None
    assert verdict.release_claim is False
    assert verdict.completion_authoritative is False
    assert verdict.contracts_frozen is False
    assert verdict.duckdb_or_quack_state_written is False
    assert verdict.pinned_ipfs_live_qualified is False
    assert verdict.suite_complete is False
    assert verdict.certification_disposition == (
        CertificationDisposition.UNAVAILABLE.value
    )
    assert verdict.simulated_results_represented_as_live is False
    assert verdict.hermetic_results_represented_as_live is False
    assert verdict.interface_parity_qualified is False
    assert verdict.live_ipfs_evidence_kind == "unavailable"
    assert verdict.pinned_daemon_identity == PINNED_DAEMON_DIGEST
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
    extra_ops = {item["operation"] for item in verdict.ipfs_operations}
    assert extra_ops == set(IPFS_SPECIFIC_OPERATIONS)
    for item in verdict.ipfs_operations:
        assert item["evidence_kind"] == "unavailable"
        assert item["live"] is False
        assert item["simulated_represented_as_live"] is False
    probe_ids = {item.probe_id for item in verdict.probes}
    assert "live_pinned_ipfs_adapter" in probe_ids
    assert "sealed_ipfs_binary" in probe_ids
    assert "pinned_daemon_identity" in probe_ids
    assert "auto_install_not_used" in probe_ids
    assert "cli_ipfs_parity" in probe_ids
    assert "mcp_ipfs_parity" in probe_ids
    assert "mcpp_ipfs_parity" in probe_ids
    if verdict.sealed_ipfs_binary == "unavailable":
        assert verdict.python_pinned_ipfs_observed is False


def test_injected_transport_round_trip_is_not_live() -> None:
    store: dict[str, bytes] = {}
    pins: set[str] = set()

    def _transport(
        *,
        method: str,
        path: str,
        query: dict[str, str],
        body: bytes,
        headers: dict[str, str],
        timeout: float,
    ) -> tuple[int, bytes]:
        del method, headers, timeout
        if path.endswith("/version"):
            return 200, b'{"Version":"simulated"}'
        if path.endswith("/block/put"):
            marker = b"\r\n\r\n"
            index = body.find(marker)
            payload = body[index + 4 :]
            if payload.endswith(b"--\r\n"):
                payload = payload.rsplit(b"\r\n--", 1)[0]
            cid = LivePinnedIpfsAdapter.content_cid(payload)
            store[cid] = payload
            if query.get("pin") == "true":
                pins.add(cid)
            return 200, json.dumps({"Key": cid, "Size": len(payload)}).encode("ascii")
        if path.endswith("/block/get"):
            cid = query["arg"]
            return 200, store[cid]
        if path.endswith("/pin/add"):
            pins.add(query["arg"])
            return 200, b'{"Pins":["ok"]}'
        if path.endswith("/pin/ls"):
            keys = {cid: {"Type": "recursive"} for cid in pins}
            if "arg" in query:
                keys = {query["arg"]: keys[query["arg"]]} if query["arg"] in pins else {}
            return 200, json.dumps({"Keys": keys}).encode("ascii")
        return 404, b'{"Message":"missing"}'

    adapter = LivePinnedIpfsAdapter(transport=_transport)
    with pytest.raises(PinnedIpfsQualificationError):
        refuse_simulated_as_live(adapter)
    payload = b"pcpr-021-simulated-only"
    added = adapter.add(payload, pin=True)
    got = adapter.cat(added.resulting_content_cid)
    assert got.data == payload
    assert adapter.simulated is True
    assert adapter.live_provider is False


def test_receipt_validator_rejects_closed_release() -> None:
    with pytest.raises(PinnedIpfsQualificationError):
        validate_pcpr_021_outer_receipt(
            {
                "task_id": "PCPR-021",
                "acceptance": {
                    "promotion_status": "release_candidate_qualified",
                    "closed_release_outcome": "release_candidate_qualified",
                    "release_claim": True,
                },
            }
        )
    with pytest.raises(PinnedIpfsQualificationError):
        validate_pcpr_021_outer_receipt(
            {
                "task_id": "PCPR-021",
                "acceptance": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "release_claim": False,
                },
                "qualification_verdict": {
                    "promotion_status": "rnd_non_promoted",
                    "closed_release_outcome": None,
                    "pinned_ipfs_live_qualified": True,
                    "simulated_results_represented_as_live": False,
                },
            }
        )


def test_receipt_validator_accepts_rnd_non_promoted() -> None:
    validate_pcpr_021_outer_receipt(
        {
            "task_id": "PCPR-021",
            "evidence_legend": {"measured": "measured"},
            "acceptance": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "release_claim": False,
            },
            "qualification_verdict": {
                "promotion_status": "rnd_non_promoted",
                "closed_release_outcome": None,
                "pinned_ipfs_live_qualified": False,
                "simulated_results_represented_as_live": False,
                "live_ipfs_evidence_kind": "unavailable",
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


def test_backend_id_is_pinned_ipfs() -> None:
    assert BACKEND_ID == "pinned_ipfs"
    assert LivePinnedIpfsAdapter.backend_id == "pinned_ipfs"
    assert LivePinnedIpfsAdapter.production_authorized is False
    assert LivePinnedIpfsAdapter.simulated is False
    default = LivePinnedIpfsAdapter()
    assert default.live_provider is True
    assert default.transport_kind == "http"
