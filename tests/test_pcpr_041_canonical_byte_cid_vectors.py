"""PCPR-041 Kit binding to canonical-byte and CID vectors."""

from __future__ import annotations

import pytest

from ipfs_kit_py.assurance.canonical_byte_cid_vectors import (
    INTERFACE,
    KIT_OWNED_VECTORS,
    KitCanonicalByteCidVectorError,
    PINNED_CATALOG_CID,
    SCHEMA,
    VECTOR_CIDS,
    kit_vector_binding_mapping,
    refuse_vector_remint,
)


def test_kit_vector_binding_pins_fourteen_cids_without_remint() -> None:
    assert INTERFACE == "KitCanonicalByteCidVectorBinding@1"
    assert SCHEMA == "ipfs_kit_py/assurance/canonical-byte-cid-vector-binding@1"
    assert len(VECTOR_CIDS) == 14
    assert KIT_OWNED_VECTORS == ("DurableArtifactReceipt",)
    assert PINNED_CATALOG_CID.startswith("baguqeera")
    assert refuse_vector_remint(
        "DurableArtifactReceipt",
        VECTOR_CIDS["DurableArtifactReceipt"],
    ) == VECTOR_CIDS["DurableArtifactReceipt"]
    with pytest.raises(KitCanonicalByteCidVectorError, match="remints"):
        refuse_vector_remint(
            "DurableArtifactReceipt",
            "baguqeeraaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
    payload = kit_vector_binding_mapping()
    assert payload["frozen"] is False
    assert payload["remint"] is False
    assert payload["reencode"] is False
    assert payload["sibling_import"] is False
    assert payload["semantic_authority"] is False
    assert payload["proof_validity_authority"] is False
    assert payload["task_completion_authority"] is False
    assert payload["duckdb_or_quack_state_written"] is False
    assert payload["catalog_cid"] == PINNED_CATALOG_CID
    assert payload["negative_vector_task"] == "PCPR-042"
