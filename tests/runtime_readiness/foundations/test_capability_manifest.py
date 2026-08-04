"""Regression coverage for KITA-001 capability/backend/test-gate inventory."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# tests/runtime_readiness/foundations/ -> parents[3] == package root (ipfs_kit_py/)
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
DOCS_DIR = PACKAGE_ROOT / "docs" / "runtime_readiness"
MANIFEST_PATH = DOCS_DIR / "capability_manifest.json"
INVENTORY_MD_PATH = DOCS_DIR / "surface_inventory.md"

CLOSED_SUPPORT_TIERS = frozenset(
    {
        "production",
        "conditional",
        "configuration-only",
        "experimental",
        "unsupported",
        "unknown-pending-proof",
    }
)

REQUIRED_DEFECT_IDS = frozenset(
    {
        "defect:vfs-noop-rename-journal-mismatch",
        "defect:overlapping-bucket-planes",
        "defect:wal-transaction-protocol",
        "defect:arc-accounting-concurrency",
        "defect:shadowed-replica-methods",
        "defect:backend-registry-factory-fracture",
        "defect:mcplusplus-construction-failure",
        "defect:graphrag-persistence-safety-drift",
        "defect:lazy-import-dependency-version-drift",
        "defect:default-test-exclusions",
    }
)

# Live BackendTypeRegistry.LEGACY_TYPES + iroh (planning "23" is not invented).
EXPECTED_REGISTERED_BACKENDS = frozenset(
    {
        "cluster",
        "digitalocean",
        "estuary",
        "filecoin",
        "filecoin_pin",
        "filesystem",
        "ftp",
        "gdrive",
        "github",
        "huggingface",
        "ipfs",
        "ipfs_cluster",
        "iroh",
        "lassie",
        "local",
        "local_fs",
        "local_storage",
        "minio",
        "parquet",
        "s3",
        "sshfs",
        "storacha",
    }
)

REQUIRED_CAPABILITY_IDS = frozenset(
    {
        "capability:vfs",
        "capability:virtual-buckets",
        "capability:wal-journal",
        "capability:arc-cache",
        "capability:replica-policy",
        "capability:graphrag",
        "capability:mcpplusplus-ucan-profile-d",
        "capability:storage-backend-conformance",
        "capability:package-interface-parity",
    }
)


@pytest.fixture(scope="module")
def manifest() -> dict:
    assert MANIFEST_PATH.is_file(), f"missing declared output {MANIFEST_PATH}"
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


# ---------------------------------------------------------------------------
# Artifact presence
# ---------------------------------------------------------------------------


def test_declared_inventory_artifacts_exist():
    assert MANIFEST_PATH.is_file(), f"missing {MANIFEST_PATH}"
    assert INVENTORY_MD_PATH.is_file(), f"missing {INVENTORY_MD_PATH}"
    text = INVENTORY_MD_PATH.read_text(encoding="utf-8")
    assert "CapabilityManifest@1" in text or "capability_manifest.json" in text
    assert "presence" in text.lower()
    assert "norecursedirs" in text or "tests/integration" in text


def test_manifest_schema_and_task_identity(manifest: dict):
    assert manifest["schema"] == "CapabilityManifest@1"
    assert manifest["schema_version"] == (
        "ipfs_kit_py.runtime_readiness.capability_manifest@1"
    )
    assert manifest["task_id"] == "KITA-001"
    for iface in (
        "CapabilityManifest@1",
        "RepositoryForestDescriptor@1",
        "BackendSupportTier@1",
    ):
        assert iface in manifest["interfaces"]


# ---------------------------------------------------------------------------
# Inventory policy: no correctness-from-presence
# ---------------------------------------------------------------------------


def test_checked_in_policy_forbids_presence_inference(manifest: dict):
    policy = manifest["policy"]
    assert policy["id"] == "CapabilityInventoryPolicy@1"
    assert policy["checked_in"] is True
    assert policy["correctness_from_presence"] is False
    assert policy["presence_is_not_support"] is True
    assert set(policy["support_tiers"]) == CLOSED_SUPPORT_TIERS
    for forbidden in (
        "registry_presence_implies_support",
        "import_success_implies_correctness",
        "schema_form_implies_runtime",
        "test_file_presence_implies_gate_coverage",
        "optional_extra_installed_implies_backend_ready",
    ):
        assert forbidden in policy["forbidden_inferences"]
    for required in (
        "repository_forest",
        "backend_registry_types",
        "test_gate_exclusions",
        "confirmed_baseline_defects",
    ):
        assert required in policy["exhaustiveness_scope"]
    # Production is gated; must not be free-form.
    for req in (
        "live_conformance_receipt",
        "complete_required_operations",
        "current_tree_evidence",
    ):
        assert req in policy["production_requires"]


# ---------------------------------------------------------------------------
# Confirmed defects
# ---------------------------------------------------------------------------


def test_all_required_confirmed_defects_recorded(manifest: dict):
    defects = manifest["confirmed_defects"]
    by_id = {d["id"]: d for d in defects}
    assert set(manifest["required_defect_ids"]) >= REQUIRED_DEFECT_IDS
    for defect_id in REQUIRED_DEFECT_IDS:
        assert defect_id in by_id, f"missing required defect {defect_id}"
        entry = by_id[defect_id]
        assert entry["status"] == "confirmed-observation"
        assert entry["severity"] == "P0"
        assert entry.get("summary")
        assert entry.get("locations")


def test_vfs_noop_rename_and_journal_mismatch_details(manifest: dict):
    defect = next(
        d
        for d in manifest["confirmed_defects"]
        if d["id"] == "defect:vfs-noop-rename-journal-mismatch"
    )
    blob = json.dumps(defect).lower()
    assert "rename" in blob
    assert "log_operation" in blob
    assert "record_operation" in blob or "does not define" in blob
    assert "vfs_manager" in blob


def test_default_test_exclusions_name_integration_tree(manifest: dict):
    defect = next(
        d
        for d in manifest["confirmed_defects"]
        if d["id"] == "defect:default-test-exclusions"
    )
    blob = json.dumps(defect)
    assert "tests/integration" in blob
    assert "norecursedirs" in blob.lower() or "pytest.ini" in blob


# ---------------------------------------------------------------------------
# Backends: exhaustive registry, closed tiers, no false production
# ---------------------------------------------------------------------------


def test_registered_backends_match_live_registry_surface(manifest: dict):
    backends = manifest["backends"]
    assert backends["schema"] == "BackendSupportTier@1"
    assert backends["registered_type_count"] == 22
    assert set(backends["registered_types"]) == EXPECTED_REGISTERED_BACKENDS
    assert "iroh" in backends["registered_types"]
    assert len(backends["legacy_types"]) == 21
    assert backends["production_count"] == 0
    # Planning estimate may differ; inventory must not invent types to match it.
    assert backends["planning_estimate_type_count"] == 23
    assert "does not invent" in backends["planning_estimate_note"].lower() or (
        "live" in backends["planning_estimate_note"].lower()
    )


def test_every_backend_has_closed_support_tier(manifest: dict):
    types = manifest["backends"]["types"]
    assert len(types) == 22
    names = {entry["type_name"] for entry in types}
    assert names == EXPECTED_REGISTERED_BACKENDS
    production = []
    for entry in types:
        assert entry["support_tier"] in CLOSED_SUPPORT_TIERS, entry["type_name"]
        assert entry["registry_present"] is True
        assert entry.get("support_tier_rationale")
        # Presence alone cannot yield production without evidence machinery.
        if entry["support_tier"] == "production":
            production.append(entry["type_name"])
            assert entry.get("evidence_status") not in (None, "unknown-pending-proof")
    assert production == [], f"unexpected production backends without proof: {production}"


def test_legacy_backends_lack_create_filesystem_except_iroh(manifest: dict):
    for entry in manifest["backends"]["types"]:
        if entry["type_name"] == "iroh":
            assert entry["has_create_filesystem"] is True
            assert entry["support_tier"] == "conditional"
            assert entry["plugin_class"] == "IrohBackendPlugin"
        else:
            assert entry["has_create_filesystem"] is False
            assert entry["plugin_class"] == "LegacyBackendPlugin"
            assert entry["runtime_via_backend_manager_get_backend_adapter"] == (
                "unsupported"
            )


def test_schema_and_adapter_registry_divergence_recorded(manifest: dict):
    backends = manifest["backends"]
    assert backends["adapter_registry"]["divergence_from_type_registry"] is True
    assert backends["dashboard_schemas"]["divergence_from_type_registry"] is True
    adapter_map = backends["adapter_registry"]["mapping"]
    for key in ("ipfs", "filesystem", "sshfs", "s3", "minio", "digitalocean"):
        assert key in adapter_map
    schema_keys = set(backends["dashboard_schemas"]["keys"])
    assert "ipfs-cluster" in schema_keys
    # Schema-only keys that are not registered types.
    schema_only = {
        e["type_name"] for e in backends["schema_only_advertisements"]
    }
    for key in ("lotus", "arrow", "ipfs-cluster-follow"):
        assert key in schema_only
    for entry in backends["schema_only_advertisements"]:
        assert entry["support_tier"] in CLOSED_SUPPORT_TIERS
        assert entry["registry_present"] is False
        # Forms are not support.
        assert entry["support_tier"] != "production"


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


def test_capabilities_cover_program_surfaces_with_tiers(manifest: dict):
    caps = manifest["capabilities"]
    by_id = {c["id"]: c for c in caps}
    assert REQUIRED_CAPABILITY_IDS <= set(by_id)
    for cap_id in REQUIRED_CAPABILITY_IDS:
        cap = by_id[cap_id]
        assert cap["support_tier"] in CLOSED_SUPPORT_TIERS
        assert cap["support_tier"] != "production"
    # MCP++ construction path must not be advertised as production.
    mcpp = by_id["capability:mcpplusplus-ucan-profile-d"]
    assert mcpp["support_tier"] == "unsupported"
    assert "defect:mcplusplus-construction-failure" in mcpp["related_defects"]


# ---------------------------------------------------------------------------
# Surfaces, test gates, version drift
# ---------------------------------------------------------------------------


def test_cli_and_mcp_surfaces_tiered(manifest: dict):
    surfaces = manifest["surfaces"]
    scripts = {s["name"]: s for s in surfaces["cli"]["console_scripts"]}
    for name in (
        "ipfs-kit",
        "ipfs-kit-mcp",
        "ipfs-kit-mcp-tools",
        "ipfs-kit-iroh",
    ):
        assert name in scripts
        assert scripts[name]["support_tier"] in CLOSED_SUPPORT_TIERS
    assert scripts["ipfs-kit-mcp"]["support_tier"] == "unsupported"
    assert surfaces["mcpplusplus"]["support_tier"] == "unsupported"


def test_test_gates_record_integration_exclusion(manifest: dict):
    gates = manifest["test_gates"]
    default = gates["default_pytest_ini"]
    assert default["path"] == "pytest.ini"
    assert "tests/integration" in default["norecursedirs"]
    assert "tests/archived_stale_tests" in default["norecursedirs"]
    assert gates["integration_tree"]["default_collected"] is False
    assert gates["integration_tree"]["approximate_test_module_count"] >= 100
    families = set(gates["integration_tree"]["coverage_families"])
    for family in ("storage_wal", "storage_backends", "replication_policy"):
        assert family in families


def test_version_identity_mismatch_recorded(manifest: dict):
    version = manifest["version_identity"]
    assert version["mismatch"] is True
    assert version["runtime_version"]["value"] == "0.2.0"
    meta_values = {m["value"] for m in version["metadata_versions"]}
    assert "0.3.0" in meta_values
    assert "defect:lazy-import-dependency-version-drift" in version["related_defects"]


def test_repository_forest_descriptor(manifest: dict):
    forest = manifest["repository_forest"]
    assert forest["schema"] == "RepositoryForestDescriptor@1"
    bound = forest["planning_bound"]
    assert bound["ipfs_kit_py_gitlink"]
    assert bound["ipfs_datasets_py_gitlink"]
    assert bound["ipfs_accelerate_py"]
    repos = {
        r["path"]: r for r in forest["inventory_observation"]["repositories"]
    }
    assert "ipfs_kit_py" in repos
    assert "ipfs_datasets_py" in repos
    assert repos["ipfs_datasets_py"]["revision_match_planning_bound"] is True


def test_duplicate_implementations_and_optional_deps(manifest: dict):
    dups = manifest["duplicate_implementations"]
    for key in (
        "vfs_managers",
        "bucket_managers",
        "wal_journal_variants",
        "graphrag_variants",
        "backend_registries",
    ):
        assert len(dups[key]) >= 2
    extras = {e["name"] for e in manifest["optional_dependencies"]["extras"]}
    for name in ("iroh", "ai_ml", "s3", "full"):
        assert name in extras
    for extra in manifest["optional_dependencies"]["extras"]:
        assert extra["support_tier"] in CLOSED_SUPPORT_TIERS


def test_no_advertised_item_uses_open_tier_vocabulary(manifest: dict):
    """Every support_tier string in the document is from the closed set."""

    def walk(node, path="$"):
        if isinstance(node, dict):
            if "support_tier" in node:
                tier = node["support_tier"]
                assert tier in CLOSED_SUPPORT_TIERS, f"{path}: {tier!r}"
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(manifest)


def test_surface_inventory_mentions_required_defect_themes():
    text = INVENTORY_MD_PATH.read_text(encoding="utf-8").lower()
    for needle in (
        "rename",
        "bucket",
        "wal",
        "arc",
        "ensure_replication",
        "create_filesystem",
        "eventdagstore",
        "graphrag",
        "0.2.0",
        "0.3.0",
        "tests/integration",
        "production",
        "unknown-pending-proof",
        "configuration-only",
    ):
        assert needle in text, f"surface_inventory.md missing theme {needle!r}"


def test_manifest_cross_links_surface_inventory(manifest: dict):
    xref = manifest["cross_references"]
    assert "surface_inventory.md" in xref["surface_inventory_md"]
    # Companion file must exist relative to package docs.
    assert (PACKAGE_ROOT / xref["surface_inventory_md"]).is_file()
