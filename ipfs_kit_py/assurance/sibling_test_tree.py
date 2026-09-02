"""PCPR-025 sibling test-tree decoupling surface.

Installed ``ipfs_kit_py`` distributions must not require an adjacent tests/
directory, a sibling checkout on sys.path, or Datasets tests as a package.
Normative vectors live in
``ipfs_kit_py.adversarial_assurance_store.normative_vectors``.

This module is not live qualification, not CLI/MCP/MCP++ parity, and not a
closed PCPR release. Hermetic source probes cannot mint live authority.
Importing this module does not require Datasets.
"""

from __future__ import annotations

from typing import Any, Final


INTERFACE: Final = "SiblingTestTreeDecoupling@1"
SCHEMA: Final = "ipfs_kit_py/assurance/sibling-test-tree@1"
BACKEND_ID: Final = "sibling_test_tree"
SUPPORT_CLASS: Final = "hermetic_qualified"
LIVE_SUPPORT_CLAIM: Final = False
CERTIFICATION_SCOPE: Final = (
    "pcpr-025-sibling-test-tree-decoupling; not a closed PCPR release"
)
VECTOR_INTERFACE: Final = "KitPackagedDatasetsAssuranceVectors@1"
VECTOR_SCHEMA: Final = (
    "ipfs_kit_py/adversarial_assurance_store/normative-vectors@1"
)
SIBLING_TESTS_PACKAGE_REQUIRED: Final = False
SIBLING_CHECKOUT_REQUIRED: Final = False


def packaged_vector_catalog() -> dict[str, Any]:
    """Compact catalog of packaged constructors. Not live evidence."""

    catalog: dict[str, Any] = {
        "schema": VECTOR_SCHEMA,
        "interface": VECTOR_INTERFACE,
        "sibling_tests_package_required": SIBLING_TESTS_PACKAGE_REQUIRED,
        "sibling_checkout_required": SIBLING_CHECKOUT_REQUIRED,
        "vectors": (
            "mutation_candidate",
            "mutation_operator",
            "assurance_campaign_receipt",
            "assurance_gap",
        ),
        "source": "ipfs_kit_py.adversarial_assurance_store.normative_vectors",
        "live": False,
        "simulated_represented_as_live": False,
        "datasets_import": "declared",
    }
    try:
        from ipfs_kit_py.adversarial_assurance_store import (  # noqa: F401
            normative_vectors,
        )

        catalog["datasets_import"] = "available"
        catalog.update(normative_vectors.packaged_vector_catalog())
    except ImportError:
        catalog["datasets_import"] = "unavailable"
    return catalog


def decoupling_contract() -> dict[str, object]:
    catalog = packaged_vector_catalog()
    return {
        "schema": SCHEMA,
        "interface": INTERFACE,
        "backend_id": BACKEND_ID,
        "support_class": SUPPORT_CLASS,
        "live_support_claim": LIVE_SUPPORT_CLAIM,
        "is_hermetic": True,
        "live_provider": False,
        "simulated": False,
        "production_authorized": False,
        "sibling_tests_package_required": SIBLING_TESTS_PACKAGE_REQUIRED,
        "sibling_checkout_required": SIBLING_CHECKOUT_REQUIRED,
        "vector_schema": VECTOR_SCHEMA,
        "vector_interface": VECTOR_INTERFACE,
        "vector_catalog": catalog,
        "certification_scope": CERTIFICATION_SCOPE,
    }


__all__ = [
    "INTERFACE",
    "SCHEMA",
    "BACKEND_ID",
    "SUPPORT_CLASS",
    "LIVE_SUPPORT_CLAIM",
    "CERTIFICATION_SCOPE",
    "VECTOR_INTERFACE",
    "VECTOR_SCHEMA",
    "SIBLING_TESTS_PACKAGE_REQUIRED",
    "SIBLING_CHECKOUT_REQUIRED",
    "packaged_vector_catalog",
    "decoupling_contract",
]
