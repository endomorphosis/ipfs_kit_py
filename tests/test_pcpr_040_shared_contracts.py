"""PCPR-040 Kit binding to the shared-contract catalog."""

from __future__ import annotations

import pytest

from ipfs_kit_py.assurance.shared_contracts import (
    CONTRACT_SCHEMA_IDS,
    INTERFACE,
    KIT_OWNED_CONTRACTS,
    KitSharedContractError,
    NORMATIVE_SOURCE,
    PCPR_040_TASK_ID,
    SCHEMA,
    kit_binding_mapping,
    refuse_remint,
)


def test_kit_binding_pins_fourteen_identities_without_remint() -> None:
    assert PCPR_040_TASK_ID == "PCPR-040"
    assert INTERFACE == "KitSharedContractBinding@1"
    assert SCHEMA == "ipfs_kit_py/assurance/shared-contract-binding@1"
    assert NORMATIVE_SOURCE == (
        "ipfs_accelerate_py/assurance/shared-contracts-catalog@1"
    )
    assert len(CONTRACT_SCHEMA_IDS) == 14
    assert KIT_OWNED_CONTRACTS == ("DurableArtifactReceipt",)
    assert refuse_remint(
        "DurableArtifactReceipt",
        CONTRACT_SCHEMA_IDS["DurableArtifactReceipt"],
    ) == CONTRACT_SCHEMA_IDS["DurableArtifactReceipt"]
    with pytest.raises(KitSharedContractError, match="remints"):
        refuse_remint("DurableArtifactReceipt", "not_yet_normative")
    payload = kit_binding_mapping()
    assert payload["frozen"] is False
    assert payload["remint"] is False
    assert payload["sibling_import"] is False
    assert payload["semantic_authority"] is False
    assert payload["proof_validity_authority"] is False
    assert payload["task_completion_authority"] is False
    assert payload["duckdb_or_quack_state_written"] is False
