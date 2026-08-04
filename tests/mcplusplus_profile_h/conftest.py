from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Standalone kit checkouts do not vendor ``mcplusplus_profile_h``; monorepo
# layouts may expose it under ``<repo>/src``. Search a few parent depths and
# soft-skip this suite when the shared package is unavailable.
_HERE = Path(__file__).resolve()
_CANDIDATE_ROOTS = []
for depth in (2, 3, 4, 5):
    if depth < len(_HERE.parents):
        _CANDIDATE_ROOTS.append(_HERE.parents[depth])

ROOT: Path | None = None
for _root in _CANDIDATE_ROOTS:
    src = _root / "src"
    if (src / "mcplusplus_profile_h").is_dir():
        sys.path.insert(0, str(src))
        ext = _root / "external" / "ipfs_kit"
        if ext.is_dir():
            sys.path.insert(0, str(ext))
        ROOT = _root
        break

pytest.importorskip(
    "mcplusplus_profile_h",
    reason=(
        "mcplusplus_profile_h is not installed and no monorepo src/ tree was "
        "found; Profile H kit tests require the shared package"
    ),
)

from ipfs_kit_py.mcp_server.mcplusplus.profile_h import (  # noqa: E402
    KitOperationTerms,
    KitPaymentConfig,
    PaidKitService,
)
from mcplusplus_profile_h import CallbackFacilitator, SettlementResult, VerificationResult  # noqa: E402
from mcplusplus_profile_h.canonical import cid_for  # noqa: E402


@pytest.fixture
def calls():
    return {"verify": 0, "settle": 0, "lookup": 0}


@pytest.fixture
def facilitator(calls):
    def verify(_payload, _requirement):
        calls["verify"] += 1
        return VerificationResult(True, "H_PAYMENT_VERIFIED", verifier_did="did:web:facilitator.test")

    def settle(_payload, requirement):
        calls["settle"] += 1
        return SettlementResult(True, requirement.network, "0xtest-transaction")

    return CallbackFacilitator(verify, settle)


@pytest.fixture
def config():
    common = {"namespaces": ("tenant-a",), "retention_seconds": 86_400, "max_retention_seconds": 172_800}
    return KitPaymentConfig(
        seller_did="did:web:kit.test",
        descriptor_cid=cid_for({"kit": "descriptor"}),
        pay_to="0x1111111111111111111111111111111111111111",
        asset="0x0000000000000000000000000000000000000001",
        catalog_version="2026-07-12",
        operations={
            "storage/add": KitOperationTerms("100", quota_units=8, unit="mebibyte", max_request_units=8, **common),
            "storage/pin": KitOperationTerms("200", quota_units=30, unit="gigabyte-day", max_request_units=30, **common),
            "storage/retrieve": KitOperationTerms("50", quota_units=16, unit="mebibyte", max_request_units=16, **common),
        },
    )


@pytest.fixture
def service(tmp_path, config, facilitator):
    return PaidKitService(config, tmp_path / "profile-h", facilitator)


@pytest.fixture
def request_context():
    from mcplusplus_profile_h import RequestContext

    return RequestContext(
        cid_for({"request": "pin-1"}), "pin-1", attributes={"subject": "buyer-1", "namespaces": ("tenant-a",)}
    )
