"""Public package export freeze checks for adversarial_assurance_store (AAE-038).

Acceptance:

* Final package exports artifact, campaign, Merkle, policy-CAS, and recovery
  interfaces
* Import and negative tests
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# Prefer this worktree's kit package when an outer PYTHONPATH pin is present.
_KIT_ROOT = Path(__file__).resolve().parents[2]
_KIT_PKG = _KIT_ROOT / "ipfs_kit_py"
if sys.path[:1] != [str(_KIT_ROOT)]:
    sys.path.insert(0, str(_KIT_ROOT))
import ipfs_kit_py as _ipfs_kit_py  # noqa: E402

if str(_KIT_PKG) not in list(_ipfs_kit_py.__path__):
    _ipfs_kit_py.__path__.insert(0, str(_KIT_PKG))

import ipfs_kit_py.adversarial_assurance_store as aae_store
from ipfs_kit_py.adversarial_assurance_store import (
    ASSURANCE_ARTIFACT_STORE_INTERFACE,
    ASSURANCE_POLICY_REPOSITORY_INTERFACE,
    ASSURANCE_RECOVERY_INTERFACE,
    ASSURANCE_RECOVERY_REPORT_INTERFACE,
    CAMPAIGN_MODULE_INTERFACE,
    MERKLE_MODULE_INTERFACE,
    PACKAGE,
    PACKAGE_INTERFACE,
    POLICY_MODULE_INTERFACE,
    REQUIRED_CAS_INTERRUPTION_POINTS,
    AssuranceRecoveryReport,
    DurableAssuranceArtifactStore,
    DurableAssuranceCampaignMerkleRepository,
    DurableAssurancePolicyRepository,
    DurableAssuranceRecovery,
    DurableMutationCampaignRepository,
    recover_assurance_campaigns,
)


# ---------------------------------------------------------------------------
# Stable interface pins
# ---------------------------------------------------------------------------


def test_package_interface_pins_are_stable() -> None:
    assert PACKAGE_INTERFACE == "AdversarialAssuranceStore@1"
    assert PACKAGE == "ipfs_kit_py.adversarial_assurance_store"
    assert ASSURANCE_ARTIFACT_STORE_INTERFACE == "AssuranceArtifactStore@1"
    assert CAMPAIGN_MODULE_INTERFACE == "MutationCampaignRepository@1"
    assert MERKLE_MODULE_INTERFACE == "AssuranceCampaignMerkleRepository@1"
    assert ASSURANCE_POLICY_REPOSITORY_INTERFACE == "AssurancePolicyRepository@1"
    assert POLICY_MODULE_INTERFACE == ASSURANCE_POLICY_REPOSITORY_INTERFACE
    assert ASSURANCE_RECOVERY_INTERFACE == "AssuranceRecovery@1"
    assert ASSURANCE_RECOVERY_REPORT_INTERFACE == "AssuranceRecoveryReport@1"
    assert len(REQUIRED_CAS_INTERRUPTION_POINTS) == 6


def test_package_exports_artifact_campaign_merkle_policy_and_recovery() -> None:
    required = (
        # Artifacts
        "DurableAssuranceArtifactStore",
        "AssuranceArtifactKind",
        "seal_assurance_artifact",
        "cid_for_assurance_artifact",
        "ASSURANCE_ARTIFACT_STORE_INTERFACE",
        # Campaigns
        "DurableMutationCampaignRepository",
        "DurableAssuranceGapRepository",
        "CampaignPhase",
        "ExecutionClaimStatus",
        "CampaignStateSnapshot",
        "assert_terminal_success_admissible",
        "CAMPAIGN_MODULE_INTERFACE",
        # Merkle
        "DurableAssuranceCampaignMerkleRepository",
        "MerkleSetKind",
        "MerkleRootSnapshot",
        "MERKLE_MODULE_INTERFACE",
        # Policy CAS
        "DurableAssurancePolicyRepository",
        "AssurancePolicyVersionSnapshot",
        "AssurancePromotionStateSnapshot",
        "ASSURANCE_POLICY_REPOSITORY_INTERFACE",
        "POLICY_CAS_SCHEMA",
        # Recovery
        "recover_assurance_campaigns",
        "DurableAssuranceRecovery",
        "AssuranceRecoveryReport",
        "AssuranceRecovery",
        "assert_writer_fence",
        "assert_terminal_claim_not_ambiguous",
        "ASSURANCE_RECOVERY_INTERFACE",
        "ASSURANCE_RECOVERY_REPORT_INTERFACE",
        "REQUIRED_CAS_INTERRUPTION_POINTS",
    )
    for name in required:
        assert hasattr(aae_store, name), f"missing public export {name}"
        assert name in aae_store.__all__, f"{name} missing from __all__"


def test_importing_package_has_no_side_effects_and_exports_are_callable() -> None:
    # Re-import is stable.
    reloaded = importlib.reload(aae_store)
    assert reloaded.PACKAGE_INTERFACE == PACKAGE_INTERFACE
    assert callable(reloaded.recover_assurance_campaigns)
    assert callable(reloaded.assert_writer_fence)
    assert issubclass(reloaded.DurableAssuranceArtifactStore, object)
    assert issubclass(reloaded.DurableMutationCampaignRepository, object)
    assert issubclass(reloaded.DurableAssuranceCampaignMerkleRepository, object)
    assert issubclass(reloaded.DurableAssurancePolicyRepository, object)
    assert issubclass(reloaded.DurableAssuranceRecovery, object)
    assert issubclass(reloaded.AssuranceRecoveryReport, object)


def test_submodule_imports_match_package_exports() -> None:
    from ipfs_kit_py.adversarial_assurance_store import artifacts as art
    from ipfs_kit_py.adversarial_assurance_store import campaigns as camp
    from ipfs_kit_py.adversarial_assurance_store import merkle as merk
    from ipfs_kit_py.adversarial_assurance_store import policy as pol
    from ipfs_kit_py.adversarial_assurance_store import recovery as rec

    assert art.DurableAssuranceArtifactStore is DurableAssuranceArtifactStore
    assert camp.DurableMutationCampaignRepository is DurableMutationCampaignRepository
    assert (
        merk.DurableAssuranceCampaignMerkleRepository
        is DurableAssuranceCampaignMerkleRepository
    )
    assert pol.DurableAssurancePolicyRepository is DurableAssurancePolicyRepository
    assert rec.recover_assurance_campaigns is recover_assurance_campaigns
    assert rec.AssuranceRecoveryReport is AssuranceRecoveryReport
    assert rec.DurableAssuranceRecovery is DurableAssuranceRecovery


# ---------------------------------------------------------------------------
# Negative / fail-closed package surface
# ---------------------------------------------------------------------------


def test_package_does_not_export_second_storage_or_wal_engine() -> None:
    forbidden = (
        "WAL",
        "WriteAheadLog",
        "open_second_store",
        "mint_cid",
        "sign_receipt",
        "IncrementalProofSealer",
        "production_policy",
        "mutate_production_policy",
    )
    for name in forbidden:
        assert not hasattr(aae_store, name), f"must not export {name}"
        assert name not in aae_store.__all__


def test_package_does_not_change_production_policy_on_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Import and recovery helpers never touch a production policy path."""

    production = tmp_path / "production-policy.json"
    production.write_text('{"revision": 1, "policy": "live"}\n', encoding="utf-8")
    before = production.read_text(encoding="utf-8")

    # Point common env vars away from the production fixture; package import
    # must still leave the fixture bytes untouched.
    monkeypatch.setenv("ASSURANCE_PRODUCTION_POLICY_PATH", str(production))
    monkeypatch.setenv("AAE_PRODUCTION_POLICY", str(production))
    importlib.reload(aae_store)

    assert production.read_text(encoding="utf-8") == before
    # Calling recover with an empty disposable store still must not write
    # outside the disposable store directory.
    store_dir = tmp_path / "disposable-coordination"
    from ipfs_kit_py.mcp_server.mcplusplus.coordination_storage import (
        DurableCoordinationStore,
    )

    with DurableCoordinationStore(store_dir) as store:
        report = aae_store.recover_assurance_campaigns(store)
        assert isinstance(report, AssuranceRecoveryReport)
        assert report.reconstructed_policy_heads == ()
        assert report.reconstructed_promotion_heads == ()
    assert production.read_text(encoding="utf-8") == before
    assert not any(store_dir.rglob("production-policy.json"))


def test_recover_requires_coordination_store_type() -> None:
    with pytest.raises(TypeError, match="DurableCoordinationStore"):
        recover_assurance_campaigns(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="DurableCoordinationStore"):
        DurableAssuranceRecovery(object())  # type: ignore[arg-type]


def test_negative_unknown_exports_and_private_rebuild_engine() -> None:
    # Domain recovery must not re-export a private second rebuild engine API.
    assert not hasattr(aae_store, "_reconstructed_root_chain")
    assert not hasattr(aae_store, "rebuild_indexes_from_scratch")
    # Unknown attribute access fails closed.
    with pytest.raises(AttributeError):
        getattr(aae_store, "InventedSecondObjectStore")


def test_all_lists_only_declared_public_names() -> None:
    for name in aae_store.__all__:
        assert hasattr(aae_store, name), f"__all__ entry {name} is not defined"
        assert not name.startswith("_"), f"private name {name} must not be public"
