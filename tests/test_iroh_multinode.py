"""IROH-025 deterministic harness and opt-in real-node interoperability tests."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from ipfs_kit_py.iroh.multinode import (
    DIRECT_LAN,
    DRIVER_ENV,
    HARNESS_VERSION,
    INTERRUPTION_RESUME,
    KEY_ROTATION,
    LARGE_DATA,
    NAT_CONTAINER,
    OPT_IN_ENV,
    RELAY_FALLBACK,
    REQUIRED_SCENARIOS,
    VERSION_SKEW,
    CommandScenarioDriver,
    InteropConfigurationError,
    InteropDriverError,
    ResourceBounds,
    default_scenario_plans,
    enabled_from_environment,
    load_interoperability_evidence,
    load_interoperability_schema,
    run_from_environment,
    validate_evidence,
    validate_observation,
    write_deterministic_payload,
)


def _passing_observation(plan, *, payload_hash: str = "a" * 64):
    assertions = {
        "isolated_state": True,
        "hash_verified": True,
        "bounded_resources": True,
    }
    if plan.direct_path_blocked:
        assertions["direct_path_blocked"] = True
    if plan.interrupt_after_bytes is not None:
        assertions.update({"interrupted": True, "resumed_from_nonzero_offset": True})
    if plan.requires_previous_binary:
        assertions.update({"mixed_versions": True, "protocol_compatible": True})
    if plan.requires_identity_rotation:
        assertions.update({"identity_changed": True, "old_identity_rejected": True})
    return {
        "scenario_id": plan.scenario_id,
        "status": "passed",
        "transport": plan.expected_transport,
        "node_count": plan.node_count,
        "payload_hash": payload_hash,
        "payload_bytes": plan.payload_size,
        "content_verified": True,
        "versions": {
            "source": "iroh-1.0.2-ipfs-kit.1",
            "target": (
                "iroh-1.0.1-ipfs-kit.1"
                if plan.requires_previous_binary
                else "iroh-1.0.2-ipfs-kit.1"
            ),
        },
        "assertions": assertions,
        "metrics": {
            "duration_ms": 250,
            "peak_rss_bytes": 64 * 1024 * 1024,
            "max_transfer_chunk_bytes": 256 * 1024,
            "max_active_transfers": 1,
            "reconnect_count": 1 if plan.interrupt_after_bytes is not None else 0,
        },
    }


def test_checked_in_evidence_is_schema_valid_and_honest() -> None:
    evidence = load_interoperability_evidence()
    schema = load_interoperability_schema()
    assert validate_evidence(evidence) == evidence
    assert evidence["status"] == "not_run"
    assert evidence["results"] == []
    assert "no installable artifacts" in evidence["not_run_reason"]
    assert schema["properties"]["task_id"]["const"] == "IROH-025"
    try:
        import jsonschema
    except ImportError:
        pass
    else:
        jsonschema.Draft202012Validator(schema).validate(evidence)


def test_matrix_covers_every_required_real_topology_in_stable_order() -> None:
    plans = default_scenario_plans()
    assert tuple(plan.scenario_id for plan in plans) == REQUIRED_SCENARIOS
    by_name = {plan.scenario_id: plan for plan in plans}
    assert by_name[DIRECT_LAN].expected_transport == "direct"
    assert by_name[RELAY_FALLBACK].direct_path_blocked
    assert by_name[RELAY_FALLBACK].expected_transport == "relay"
    assert by_name[NAT_CONTAINER].topology == "isolated_containers_nat"
    assert by_name[INTERRUPTION_RESUME].interrupt_after_bytes == 128 * 1024
    assert by_name[VERSION_SKEW].requires_previous_binary
    assert by_name[KEY_ROTATION].requires_identity_rotation
    assert by_name[LARGE_DATA].payload_size == 32 * 1024 * 1024
    assert all(plan.node_count >= 2 for plan in plans)


def test_payload_generation_is_reproducible_streamed_and_private(tmp_path: Path) -> None:
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    first_hash = write_deterministic_payload(
        first, 2 * 1024 * 1024 + 17, seed="same", chunk_size=4096
    )
    second_hash = write_deterministic_payload(
        second, 2 * 1024 * 1024 + 17, seed="same", chunk_size=65536
    )
    assert first_hash == second_hash
    assert first.read_bytes() == second.read_bytes()
    assert first.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("plan", default_scenario_plans(), ids=lambda item: item.scenario_id)
def test_passing_observations_enforce_scenario_and_resource_contract(plan) -> None:
    observation = _passing_observation(plan)
    assert validate_observation(observation, plan, ResourceBounds()) == observation


def test_observation_cannot_claim_pass_when_transport_or_bounds_are_wrong() -> None:
    plan = default_scenario_plans()[1]
    wrong_transport = _passing_observation(plan)
    wrong_transport["transport"] = "direct"
    with pytest.raises(InteropConfigurationError, match="does not satisfy"):
        validate_observation(wrong_transport, plan, ResourceBounds())

    excessive_memory = _passing_observation(plan)
    excessive_memory["metrics"]["peak_rss_bytes"] = ResourceBounds().max_peak_rss_bytes + 1
    with pytest.raises(InteropConfigurationError, match="does not satisfy"):
        validate_observation(excessive_memory, plan, ResourceBounds())


def test_interruption_version_and_rotation_assertions_are_mandatory() -> None:
    plans = {plan.scenario_id: plan for plan in default_scenario_plans()}
    for scenario, missing in (
        (INTERRUPTION_RESUME, "resumed_from_nonzero_offset"),
        (VERSION_SKEW, "mixed_versions"),
        (KEY_ROTATION, "old_identity_rejected"),
    ):
        observation = _passing_observation(plans[scenario])
        del observation["assertions"][missing]
        with pytest.raises(InteropConfigurationError, match="omitted"):
            validate_observation(observation, plans[scenario], ResourceBounds())


@pytest.mark.parametrize(
    "sensitive_field",
    ["ticket", "private_key", "node_identity", "peer_id", "relay_url", "endpoint_address"],
)
def test_evidence_rejects_sensitive_or_peer_specific_fields(sensitive_field: str) -> None:
    evidence = load_interoperability_evidence()
    evidence["platform"][sensitive_field] = "must-not-persist"
    with pytest.raises(InteropConfigurationError, match="forbidden field"):
        validate_evidence(evidence)


def test_passing_evidence_requires_all_scenarios() -> None:
    evidence = load_interoperability_evidence()
    evidence.pop("not_run_reason")
    evidence["status"] = "passed"
    evidence["generated_at"] = "2026-07-13T12:00:00Z"
    evidence["run_id"] = "deterministic-test-run"
    evidence["platform"] = {"os": "linux", "architecture": "x86_64", "python": "3.12.10"}
    evidence["results"] = [_passing_observation(plan) for plan in default_scenario_plans()]
    assert validate_evidence(evidence)["status"] == "passed"
    evidence["results"].pop()
    with pytest.raises(InteropConfigurationError, match="every scenario"):
        validate_evidence(evidence)


def test_network_execution_is_explicitly_opt_in() -> None:
    assert not enabled_from_environment({})
    assert not enabled_from_environment({OPT_IN_ENV: "0", DRIVER_ENV: "ignored"})
    assert enabled_from_environment({OPT_IN_ENV: "yes"})


def test_driver_output_is_hard_bounded_and_process_is_reaped() -> None:
    bounds = ResourceBounds(
        scenario_timeout_seconds=2,
        max_driver_output_bytes=64,
    )
    driver = CommandScenarioDriver(
        [sys.executable, "-c", "import sys; sys.stdin.read(); sys.stdout.write('x' * 65)"],
        bounds=bounds,
    )
    with pytest.raises(InteropDriverError, match="exceeded"):
        asyncio.run(driver.run({"contract_version": 1}))


@pytest.mark.integration
@pytest.mark.requires_network
def test_real_multinode_interoperability_lane() -> None:
    """Run real binaries only when a release lane supplies the reviewed driver."""

    if not enabled_from_environment():
        pytest.skip(f"set {OPT_IN_ENV}=1 and the documented driver variables to run real nodes")
    evidence = asyncio.run(run_from_environment())
    assert evidence["harness_version"] == HARNESS_VERSION
    assert evidence["status"] == "passed", json.dumps(evidence, indent=2, sort_keys=True)
    assert [result["scenario_id"] for result in evidence["results"]] == list(REQUIRED_SCENARIOS)
    assert all(result["content_verified"] for result in evidence["results"])
    assert all(result["assertions"]["bounded_resources"] for result in evidence["results"])
