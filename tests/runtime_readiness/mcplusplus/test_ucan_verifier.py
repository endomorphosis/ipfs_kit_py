"""Runtime-readiness tests for strict signed UCAN authorization."""

from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ipfs_kit_py.mcp_server.mcplusplus.revocation import RevocationLedger
from ipfs_kit_py.mcp_server.mcplusplus.ucan import (
    UCANVerifier,
    issue_ucan,
    public_key_bytes,
    ucan_token_id,
)


NOW = 1_800_000_000.0
ISSUER = "did:key:root-tenant-a"
SERVICE = "did:service:tenant-a"
CLIENT = "did:client:tenant-a"
RESOURCE = "tenant-a/bucket-a/documents/report.txt"


def _b64json(value: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")


def _setup(tmp_path):
    root_key, service_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    ledger = RevocationLedger(tmp_path / "authorization-ledger.json")
    ledger.register_public_key(ISSUER, "root-v1", public_key_bytes(root_key))
    ledger.register_public_key(SERVICE, "service-v1", public_key_bytes(service_key))
    verifier = UCANVerifier(ledger=ledger, trusted_issuers={ISSUER})
    return ledger, verifier, root_key, service_key


def _token(key, issuer=ISSUER, audience=CLIENT, *, capability=None, kid="root-v1", nonce="nonce-1", exp=NOW + 300, nbf=None, proofs=(), bounds=None):
    capability = capability or {"resource": RESOURCE, "ability": "store/read"}
    if bounds is not None:
        capability = {**capability, "bounds": bounds}
    return issue_ucan(
        issuer=issuer, audience=audience, capabilities=[capability], private_key=key, kid=kid,
        expires_at=exp, not_before=nbf, nonce=nonce, proofs=proofs, issued_at=NOW - 10,
    )


def _verify(verifier, token, *, nonce=True, **kwargs):
    return verifier.verify(token, resource=RESOURCE, ability="store/read", audience=CLIENT, now=NOW, consume_nonce=nonce, **kwargs)


def test_valid_signed_ucan_and_receipt_is_redacted(tmp_path):
    _ledger, verifier, root, _service = _setup(tmp_path)
    token = _token(root)

    result = _verify(verifier, token)

    assert result.allowed and result.code == "ok"
    receipt = result.to_receipt()
    rendered = json.dumps(receipt, sort_keys=True)
    assert token not in rendered
    assert "signature" not in rendered and "private" not in rendered
    assert receipt["token_ids"] == [ucan_token_id(token)]


@pytest.mark.parametrize("mutation,code", [
    ("tampered", "invalid_signature"),
    ("unsigned", "unsigned_or_malformed_token"),
    ("downgrade", "algorithm_or_version_downgrade"),
])
def test_forged_unsigned_and_downgraded_tokens_reject(tmp_path, mutation, code):
    _ledger, verifier, root, _service = _setup(tmp_path)
    token = _token(root, nonce="nonce-" + mutation)
    if mutation == "tampered":
        token = token[:-10] + ("A" if token[-10] != "A" else "B") + token[-9:]
    elif mutation == "unsigned":
        token = ".".join(token.split(".")[:2])
    else:
        header, payload, signature = token.split(".")
        token = _b64json({"alg": "none", "kid": "root-v1", "typ": "UCAN", "v": 1}) + "." + payload + "." + signature
    assert _verify(verifier, token, nonce=False).code == code


def test_token_signed_by_an_untrusted_private_key_is_forged(tmp_path):
    _ledger, verifier, _root, _service = _setup(tmp_path)

    forged = _token(Ed25519PrivateKey.generate(), nonce="wrong-private-key")

    assert _verify(verifier, forged, nonce=False).code == "invalid_signature"


def test_audience_and_time_window_fail_closed(tmp_path):
    _ledger, verifier, root, _service = _setup(tmp_path)
    assert _verify(verifier, _token(root, audience="did:wrong", nonce="wrong-audience"), nonce=False).code == "audience_mismatch"
    assert _verify(verifier, _token(root, nonce="expired", exp=NOW - 1), nonce=False).code == "expired"
    assert _verify(verifier, _token(root, nonce="future", nbf=NOW + 1), nonce=False).code == "not_yet_valid"


def test_resource_ability_and_bounds_only_attenuate(tmp_path):
    _ledger, verifier, root, service = _setup(tmp_path)
    parent = _token(
        root, audience=SERVICE, nonce="parent", capability={"resource": "tenant-a/bucket-a/*", "ability": "store/*"},
        bounds={"max_bytes": 100, "tenant": "tenant-a", "exp": NOW + 200}, exp=NOW + 200,
    )
    child = _token(
        service, issuer=SERVICE, audience=CLIENT, kid="service-v1", nonce="child", proofs=(ucan_token_id(parent),),
        capability={"resource": RESOURCE, "ability": "store/read"},
        bounds={"max_bytes": 50, "tenant": "tenant-a", "exp": NOW + 150}, exp=NOW + 150,
    )
    assert _verify(verifier, [parent, child], request_bounds={"max_bytes": 50, "tenant": "tenant-a"}).allowed

    widened = _token(
        service, issuer=SERVICE, audience=CLIENT, kid="service-v1", nonce="widened", proofs=(ucan_token_id(parent),),
        capability={"resource": "tenant-b/bucket-a/*", "ability": "store/*"},
        bounds={"max_bytes": 101, "tenant": "tenant-b", "exp": NOW + 201}, exp=NOW + 201,
    )
    assert _verify(verifier, [parent, widened], nonce=False).code in {"time_attenuation_failed", "capability_attenuation_failed"}


@pytest.mark.parametrize("capability", [
    {"ability": "store/read"}, {"resource": RESOURCE}, {"resource": "", "ability": "store/read"},
])
def test_missing_resource_or_ability_never_becomes_wildcard(tmp_path, capability):
    _ledger, verifier, root, _service = _setup(tmp_path)
    # Construct a signed envelope carrying the malformed claim to ensure the
    # verifier, not the issuer helper, rejects the omission.
    token = _token(root, nonce="bad-cap")
    header, _payload, _signature = token.split(".")
    payload = {"iss": ISSUER, "aud": CLIENT, "exp": NOW + 60, "iat": NOW - 1, "jti": "bad-cap", "att": [capability], "prf": []}
    malformed = header + "." + _b64json(payload) + ".AA"
    assert _verify(verifier, malformed, nonce=False).allowed is False


def test_cross_tenant_proof_and_cyclic_chains_reject(tmp_path):
    _ledger, verifier, root, service = _setup(tmp_path)
    parent = _token(root, audience=SERVICE, nonce="root", capability={"resource": "tenant-a/*", "ability": "store/*"})
    cross_tenant = _token(service, issuer=SERVICE, kid="service-v1", nonce="cross", proofs=(ucan_token_id(parent),), capability={"resource": "tenant-b/*", "ability": "store/read"})
    assert _verify(verifier, [parent, cross_tenant], nonce=False).code == "capability_attenuation_failed"

    # A token which claims a proof cannot be a root, so cycles and re-ordered
    # proof DAGs cannot enter an authorization chain.
    cyclic_root = _token(root, audience=SERVICE, nonce="cycle-root", proofs=("sha256:made-up",))
    child = _token(service, issuer=SERVICE, kid="service-v1", nonce="cycle-child", proofs=(ucan_token_id(cyclic_root),))
    assert _verify(verifier, [cyclic_root, child], nonce=False).code == "cyclic_or_non_rooted_chain"


def test_revocation_and_replay_are_durable_across_restart(tmp_path):
    ledger, verifier, root, _service = _setup(tmp_path)
    replay = _token(root, nonce="durable-replay")
    assert _verify(verifier, replay).allowed
    restarted = UCANVerifier(ledger=RevocationLedger(ledger.path), trusted_issuers={ISSUER})
    assert _verify(restarted, replay).code == "replayed"

    revoked = _token(root, nonce="durable-revocation")
    ledger.revoke(ucan_token_id(revoked), reason="operator revoke")
    assert _verify(restarted, revoked, nonce=False).code == "revoked"


def test_key_rotation_is_durable_and_old_key_rejects(tmp_path):
    ledger, verifier, root, _service = _setup(tmp_path)
    old_token = _token(root, nonce="old-key")
    new_key = Ed25519PrivateKey.generate()
    ledger.rotate_key(ISSUER, "root-v1", "root-v2", public_key_bytes(new_key))
    restarted = UCANVerifier(ledger=RevocationLedger(ledger.path), trusted_issuers={ISSUER})
    assert _verify(restarted, old_token, nonce=False).code == "verification_key_unavailable"
    assert _verify(restarted, _token(new_key, kid="root-v2", nonce="new-key")).allowed


def test_requested_unavailable_crypto_or_ledger_fails_closed(tmp_path, monkeypatch):
    _ledger, verifier, root, _service = _setup(tmp_path)
    token = _token(root, nonce="dependency")
    assert UCANVerifier(ledger=None).verify(token, resource=RESOURCE, ability="store/read", audience=CLIENT, now=NOW).code == "ledger_unavailable"
    monkeypatch.setattr("ipfs_kit_py.mcp_server.mcplusplus.ucan.HAVE_CRYPTO_ED25519", False)
    assert _verify(verifier, token, nonce=False).code == "crypto_unavailable"
