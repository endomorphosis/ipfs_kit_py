from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from ipfs_kit_py.mcp_server.mcplusplus.profile_h import CatalogSigner, KitPaymentError, PaidKitService
from mcplusplus_profile_h import Decision, PaymentContext, RequestContext
from mcplusplus_profile_h.canonical import cid_for


FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "protected_operations.json").read_text())


def payment(required):
    return PaymentContext(
        {"x402Version": 2, "accepted": required.payment_required["accepts"][0], "payload": {"signature": "private"}},
        required.receipt_cid,
        required.quote["requestCid"],
    )


def test_signed_catalog_contains_all_protected_fixtures(service):
    catalog = service.catalog()
    assert CatalogSigner.verify(catalog)
    assert catalog["signedCatalogCid"].startswith("baguq")
    operations = {item["operation"]: item for item in catalog["capabilities"]}
    for fixture in FIXTURES["operations"]:
        entry = operations[f"tool:{fixture['name']}"]
        assert entry["metadata"]["httpRoute"] == fixture["httpRoute"]
        assert entry["requirements"][0]["amount"].isdigit()
        assert entry["metadata"]["unit"] == fixture["expectedUnit"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture", FIXTURES["operations"], ids=lambda item: item["name"])
async def test_unpaid_then_paid_operation_is_fenced(service, request_context, calls, fixture):
    effects = 0

    async def effect():
        nonlocal effects
        effects += 1
        return {"cid": fixture["params"].get("cid", "bafkreigh2akiscaildcw453bqad37x3q2bvcwf4f5n4p5g5z7v5z3m4yya")}

    context = RequestContext(cid_for({"request": fixture["name"]}), fixture["name"], attributes=request_context.attributes)
    required = await service.dispatch(fixture["name"], context, fixture["params"], effect)
    assert required.decision.decision == Decision.PAYMENT_REQUIRED
    assert effects == calls["verify"] == calls["settle"] == 0
    paid = await service.dispatch(fixture["name"], context, fixture["params"], effect, payment=payment(required))
    assert paid.decision.decision == Decision.PAID
    assert effects == calls["verify"] == calls["settle"] == 1
    assert paid.value["entitlementCid"].startswith("baguq")


@pytest.mark.asyncio
async def test_invalid_payment_and_access_controls_precede_mutation(service, request_context, calls):
    params = FIXTURES["operations"][1]["params"]
    required = await service.dispatch("storage/pin", request_context, params, lambda: None)
    bad = payment(required)
    bad = PaymentContext({**bad.payload, "accepted": {**bad.payload["accepted"], "amount": "1"}}, bad.quote_cid, bad.request_cid)
    with pytest.raises(Exception) as mismatch:
        await service.dispatch("storage/pin", request_context, params, lambda: pytest.fail("mutated"), payment=bad)
    assert getattr(mismatch.value, "code", None) == "H_REQUEST_MISMATCH"
    assert calls == {"verify": 0, "settle": 0, "lookup": 0}

    denied = RequestContext(cid_for({"denied": 1}), "denied", authorized=False, attributes=request_context.attributes)
    result = await service.dispatch("storage/pin", denied, params, lambda: pytest.fail("mutated"))
    assert result.decision.decision == Decision.DENIED
    with pytest.raises(KitPaymentError) as wrong_namespace:
        await service.dispatch("storage/pin", request_context, {**params, "namespace": "tenant-b"}, lambda: None)
    assert wrong_namespace.value.code == "H_PAYMENT_POLICY_DENIED"


@pytest.mark.asyncio
async def test_entitlement_scope_quota_and_retention(service, request_context):
    params = FIXTURES["operations"][1]["params"]
    required = await service.dispatch("storage/pin", request_context, params, lambda: {"pinned": True})
    paid = await service.dispatch("storage/pin", request_context, params, lambda: {"pinned": True}, payment=payment(required))
    entitlement = paid.value["entitlementCid"]
    entitled_context = RequestContext(
        cid_for({"request": "entitled"}), "entitled", entitlement_cid=entitlement, attributes=request_context.attributes
    )
    result = await service.dispatch("storage/pin", entitled_context, params, lambda: {"pinned": True})
    assert result.value["usageRecordCid"].startswith("baguq")
    assert service.entitlements.get(entitlement)["consumedUnits"] == 1
    retry = await service.dispatch("storage/pin", entitled_context, params, lambda: pytest.fail("duplicate entitlement effect"))
    assert retry.replayed is True
    assert service.entitlements.get(entitlement)["consumedUnits"] == 1

    other_cid = "bafkreib6vvi5ykzbcw6rd7ja5b2e7jo3xv6x5zq5n53xln5w2e2f7h3ssu"
    other_context = RequestContext(cid_for({"request": "other"}), "other", entitlement_cid=entitlement, attributes=request_context.attributes)
    with pytest.raises(KitPaymentError) as scoped:
        await service.dispatch("storage/pin", other_context, {**params, "cid": other_cid}, lambda: None)
    assert scoped.value.code == "H_ENTITLEMENT_SCOPE_MISMATCH"
    with pytest.raises(KitPaymentError) as retention:
        await service.dispatch("storage/pin", request_context, {**params, "retention_seconds": 999999}, lambda: None)
    assert retention.value.code == "H_ENTITLEMENT_EXHAUSTED"


@pytest.mark.asyncio
async def test_http_libp2p_parity_and_replay(service, request_context, calls):
    params = FIXTURES["operations"][2]["params"]
    status, headers, body = await service.handle_http("POST", "/mcp/tools/storage/retrieve", request_context, params, lambda: b"data")
    assert status == 402 and "PAYMENT-REQUIRED" in headers
    assert body["quote"]["requestCid"] == request_context.request_cid
    required = await service.dispatch("storage/retrieve", request_context, params, lambda: b"data")
    p = payment(required)
    wire = base64.b64encode(json.dumps({"payload": p.payload, "quoteCid": p.quote_cid, "requestCid": p.request_cid}).encode()).decode()
    status, headers, body = await service.handle_http(
        "POST", "/mcp/tools/storage/retrieve", request_context, params, lambda: {"data": "ok"}, payment_header=wire
    )
    assert status == 200 and "PAYMENT-RESPONSE" in headers and body["data"] == "ok"
    replay = await service.handle_libp2p({"operation": "storage/retrieve", "params": params}, request_context, lambda: pytest.fail("replayed effect"))
    assert replay["receipt_cid"] and calls["settle"] == 1


@pytest.mark.asyncio
async def test_restart_recovers_receipt_without_resettling(tmp_path, config, facilitator, calls, request_context):
    state = tmp_path / "persistent"
    first = PaidKitService(config, state, facilitator)
    params = FIXTURES["operations"][0]["params"]
    required = await first.dispatch("storage/add", request_context, params, lambda: {"cid": "new"})
    paid = await first.dispatch("storage/add", request_context, params, lambda: {"cid": "new"}, payment=payment(required))
    restarted = PaidKitService(config, state, facilitator)
    assert restarted.catalog() == first.catalog()
    replay = await restarted.dispatch("storage/add", request_context, params, lambda: pytest.fail("duplicate mutation"))
    assert replay.replayed and replay.receipt_cid == paid.receipt_cid
    assert calls["settle"] == 1
    diagnostics = await restarted.diagnostics()
    assert diagnostics["catalogSignatureValid"] is True

