from __future__ import annotations

from pathlib import Path

from ipfs_kit_py.mcp_server.mcplusplus.profile_g import INTERFACE as PROFILE_G_INTERFACE
from ipfs_kit_py.mcp_server.mcplusplus.state_root_adapter import DurableStateRootAdapter
from ipfs_kit_py.proof_seal_store.contracts import (
    CONTRACT_VERSION as PROOF_SEAL_CONTRACT_VERSION,
    PROOF_SEAL_STORE_NAMESPACE,
)
from ipfs_kit_py.semantic_governor_store.contracts import (
    SEMANTIC_GOVERNOR_STORE_INTERFACE,
    SEMANTIC_GOVERNOR_STORE_SCHEMA,
)

KIT_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DOC = KIT_ROOT / "docs/external_agent_fabric_kit_contracts.md"
SURFACES = {
    "artifact_store": KIT_ROOT / "ipfs_kit_py/adversarial_assurance_store/__init__.py",
    "semantic_root": KIT_ROOT / "ipfs_kit_py/semantic_governor_store/__init__.py",
    "proof_sealer": KIT_ROOT / "ipfs_kit_py/proof_seal_store/__init__.py",
    "mcp_adapter": KIT_ROOT / "ipfs_kit_py/mcp_server/mcplusplus/__init__.py",
    "state_root_adapter": KIT_ROOT / "ipfs_kit_py/mcp_server/mcplusplus/state_root_adapter.py",
    "profile_g": KIT_ROOT / "ipfs_kit_py/mcp_server/mcplusplus/profile_g.py",
}


def test_kit_contract_doc_binds_existing_surfaces_and_excludes_profile_g() -> None:
    assert CONTRACTS_DOC.is_file()
    text = CONTRACTS_DOC.read_text(encoding="utf-8")
    assert "adversarial_assurance_store" in text
    assert "semantic_governor_store" in text
    assert "proof_seal_store" in text
    assert "mcp_server.mcplusplus" in text
    assert "**not** production authority" in text
    assert "DuckDB" in text
    assert "Quack" in text
    assert "Profile-G" in text or "Profile G" in text or "profile_g" in text


def test_bound_surfaces_exist_and_remain_storage_not_proof_authority() -> None:
    for path in SURFACES.values():
        assert path.is_file(), path
    assert PROOF_SEAL_CONTRACT_VERSION
    assert PROOF_SEAL_STORE_NAMESPACE
    proof_init = SURFACES["proof_sealer"].read_text(encoding="utf-8")
    assert "Kit never decides proof validity" in proof_init
    assert SEMANTIC_GOVERNOR_STORE_INTERFACE == "SemanticGovernorStore@1"
    assert SEMANTIC_GOVERNOR_STORE_SCHEMA.startswith("ipfs-kit.semantic-governor-store")
    assert DurableStateRootAdapter is not None
    adapter_text = SURFACES["state_root_adapter"].read_text(encoding="utf-8")
    assert "owns neither storage nor semantic identity" in adapter_text
    artifact_contracts = (
        KIT_ROOT / "ipfs_kit_py/adversarial_assurance_store/contracts.py"
    ).read_text(encoding="utf-8")
    assert "does not open a store" in artifact_contracts


def test_in_process_profile_g_is_not_production_duckdb_quack_authority() -> None:
    assert PROFILE_G_INTERFACE == "RuntimeProfileG@1"
    profile_text = SURFACES["profile_g"].read_text(encoding="utf-8")
    assert "RuntimeProfileG@1" in profile_text
    assert "in-process" in profile_text.lower() or "Kit-owned Profile G" in profile_text
    doc = CONTRACTS_DOC.read_text(encoding="utf-8")
    assert "opening or owning the authoritative DuckDB file" in doc
    assert "substituting for the fenced authenticated Quack owner/service" in doc
    assert "Do not treat `profile_g.py`" in doc
