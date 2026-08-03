"""Strict, signed UCAN authorization for MCP++ execution paths.

This module deliberately does not share the legacy unsigned delegation parser.
Tokens are compact EdDSA envelopes, capabilities are explicit, and the default
verification path requires a durable :class:`RevocationLedger`.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import math
import time
from typing import Any, Iterable, Mapping, Sequence

from .revocation import LedgerUnavailableError, RevocationLedger

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

    HAVE_CRYPTO_ED25519 = True
except Exception:  # pragma: no cover - exercised by fail-closed tests
    InvalidSignature = Exception  # type: ignore[assignment]
    serialization = None  # type: ignore[assignment]
    Ed25519PrivateKey = None  # type: ignore[assignment]
    Ed25519PublicKey = None  # type: ignore[assignment]
    HAVE_CRYPTO_ED25519 = False


_MAX_CHAIN = 32
_MAX_TOKEN_BYTES = 64 * 1024
_BOUND_NUMERIC = frozenset({"max_bytes", "max_uses", "max_rate"})
_BOUND_EXACT = frozenset({"tenant", "bucket", "path_prefix"})
_BOUND_ALLOWED = _BOUND_NUMERIC | _BOUND_EXACT | {"nbf", "exp"}


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64url(value: Any) -> bytes:
    text = value if isinstance(value, str) else ""
    if not text or len(text) > _MAX_TOKEN_BYTES or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for ch in text):
        raise ValueError("invalid_base64url")
    decoded = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    # Reject alternate encodings with non-significant trailing bits.  Signature
    # verification must cover the exact compact representation, not merely a
    # byte-equivalent decoding of it.
    if _b64url(decoded) != text:
        raise ValueError("noncanonical_base64url")
    return decoded


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _string(value: Any, name: str, *, maximum: int = 1024) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid_" + name)
    value = value.strip()
    if not value or len(value) > maximum or "\x00" in value:
        raise ValueError("invalid_" + name)
    return value


def _timestamp(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError("invalid_" + name)
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_" + name) from exc
    if not math.isfinite(parsed):
        raise ValueError("invalid_" + name)
    return parsed


def _safe_id(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode("ascii")).hexdigest()


def ucan_token_id(token: str) -> str:
    """Return the stable, non-secret identifier used in proofs and receipts."""
    if not isinstance(token, str) or not token or len(token) > _MAX_TOKEN_BYTES:
        raise ValueError("invalid_token")
    return _safe_id(token)


def _segments_cover(parent: str, child: str) -> bool:
    """Return whether an explicit URI/path-ish wildcard covers a child.

    A wildcard may cover only a complete following segment, never a textual
    prefix.  Thus ``tenant-a/*`` cannot accidentally cover ``tenant-ab``.
    """
    if parent == child or parent == "*":
        return True
    if not parent.endswith("/*"):
        return False
    prefix = parent[:-1]  # retain trailing slash
    return child.startswith(prefix) and len(child) > len(prefix)


def resource_covers(parent: str, child: str) -> bool:
    return _segments_cover(parent, child)


def ability_covers(parent: str, child: str) -> bool:
    return _segments_cover(parent, child)


def _parse_bounds(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict) or set(raw) - _BOUND_ALLOWED:
        raise ValueError("invalid_bounds")
    result: dict[str, Any] = {}
    for key, value in raw.items():
        if key in _BOUND_NUMERIC:
            number = _timestamp(value, key)
            if number < 0:
                raise ValueError("invalid_" + key)
            result[key] = number
        elif key in {"nbf", "exp"}:
            result[key] = _timestamp(value, key)
        else:
            result[key] = _string(value, key)
    if "nbf" in result and "exp" in result and result["nbf"] > result["exp"]:
        raise ValueError("invalid_bounds_window")
    return result


@dataclass(frozen=True)
class UCANCapability:
    """An explicit resource, ability, and optional request bound grant."""

    resource: str
    ability: str
    bounds: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, value: Any) -> "UCANCapability":
        if not isinstance(value, dict):
            raise ValueError("invalid_capability")
        # Deliberately do not accept aliases with defaults: omission must never
        # become a wildcard grant.
        if set(value) - {"resource", "ability", "bounds"}:
            raise ValueError("unknown_capability_field")
        return cls(
            resource=_string(value.get("resource"), "resource"),
            ability=_string(value.get("ability"), "ability"),
            bounds=_parse_bounds(value.get("bounds")),
        )

    def as_claim(self) -> dict[str, Any]:
        output: dict[str, Any] = {"resource": self.resource, "ability": self.ability}
        if self.bounds:
            output["bounds"] = dict(self.bounds)
        return output


@dataclass(frozen=True)
class UCANDelegation:
    """Parsed signed UCAN metadata; its compact token is intentionally absent."""

    issuer: str
    audience: str
    token_id: str
    nonce: str
    not_before: float | None
    expires_at: float
    capabilities: tuple[UCANCapability, ...]
    proofs: tuple[str, ...]
    kid: str


@dataclass(frozen=True)
class UCANVerificationResult:
    """A redacted decision suitable for audit receipts."""

    allowed: bool
    code: str
    chain_length: int = 0
    issuer: str | None = None
    audience: str | None = None
    token_ids: tuple[str, ...] = ()

    @property
    def reason(self) -> str:
        return self.code

    def to_receipt(self) -> dict[str, Any]:
        # Never add envelope strings, signature bytes, key material, or claims.
        return {
            "schema": "ipfs-kit.ucan-verification-receipt@1",
            "allowed": self.allowed,
            "code": self.code,
            "chain_length": self.chain_length,
            "issuer": self.issuer,
            "audience": self.audience,
            "token_ids": list(self.token_ids),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.to_receipt()


def _private_key(value: Any) -> Any:
    if not HAVE_CRYPTO_ED25519:
        raise RuntimeError("cryptography_ed25519_unavailable")
    if isinstance(value, Ed25519PrivateKey):
        return value
    if isinstance(value, bytes):
        if len(value) not in (32, 64):
            raise ValueError("invalid_ed25519_private_key")
        return Ed25519PrivateKey.from_private_bytes(value[:32])
    raise ValueError("invalid_ed25519_private_key")


def public_key_bytes(private_key: Any) -> bytes:
    """Return only public Ed25519 bytes for registration in a ledger."""
    return _private_key(private_key).public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )


def issue_ucan(
    *, issuer: str, audience: str, capabilities: Sequence[Mapping[str, Any] | UCANCapability],
    private_key: Any, kid: str, expires_at: float, nonce: str, not_before: float | None = None,
    proofs: Sequence[str] = (), issued_at: float | None = None,
) -> str:
    """Issue a canonical signed UCAN.  Private key bytes never leave this call."""
    issuer, audience, kid, nonce = _string(issuer, "issuer"), _string(audience, "audience"), _string(kid, "kid"), _string(nonce, "nonce")
    exp = _timestamp(expires_at, "exp")
    now = time.time() if issued_at is None else _timestamp(issued_at, "iat")
    nbf = None if not_before is None else _timestamp(not_before, "nbf")
    if exp <= now or (nbf is not None and nbf > exp):
        raise ValueError("invalid_token_window")
    parsed_capabilities = tuple(c if isinstance(c, UCANCapability) else UCANCapability.from_mapping(c) for c in capabilities)
    if not parsed_capabilities:
        raise ValueError("capabilities_required")
    parsed_proofs = tuple(_string(proof, "proof") for proof in proofs)
    if len(set(parsed_proofs)) != len(parsed_proofs):
        raise ValueError("duplicate_proof")
    header = {"alg": "EdDSA", "kid": kid, "typ": "UCAN", "v": 1}
    payload: dict[str, Any] = {
        "iss": issuer, "aud": audience, "exp": exp, "iat": now, "jti": nonce,
        "att": [capability.as_claim() for capability in parsed_capabilities], "prf": list(parsed_proofs),
    }
    if nbf is not None:
        payload["nbf"] = nbf
    encoded_header, encoded_payload = _b64url(_canonical_json(header)), _b64url(_canonical_json(payload))
    signed = (encoded_header + "." + encoded_payload).encode("ascii")
    return signed.decode("ascii") + "." + _b64url(_private_key(private_key).sign(signed))


# Readable aliases for callers that use JWT terminology.
sign_ucan = issue_ucan
create_signed_ucan = issue_ucan


class UCANVerifier:
    """Fail-closed verifier for a root-to-leaf attenuation chain."""

    def __init__(
        self, *, ledger: RevocationLedger | None = None, trusted_issuers: Iterable[str] | None = None,
        clock_skew_seconds: float = 0, max_chain_length: int = _MAX_CHAIN, require_ledger: bool = True,
    ) -> None:
        skew = _timestamp(clock_skew_seconds, "clock_skew")
        if skew < 0 or skew > 300 or max_chain_length < 1 or max_chain_length > _MAX_CHAIN:
            raise ValueError("invalid_verifier_configuration")
        self.ledger = ledger
        self.require_ledger = require_ledger
        self.clock_skew_seconds = skew
        self.max_chain_length = max_chain_length
        self.trusted_issuers = None if trusted_issuers is None else frozenset(_string(item, "issuer") for item in trusted_issuers)

    def _deny(self, code: str, chain: Sequence[UCANDelegation] = ()) -> UCANVerificationResult:
        leaf = chain[-1] if chain else None
        return UCANVerificationResult(False, code, len(chain), leaf.issuer if leaf else None, leaf.audience if leaf else None, tuple(d.token_id for d in chain))

    def _parse_and_verify(self, token: Any, now: float) -> tuple[UCANDelegation, str]:
        if not HAVE_CRYPTO_ED25519:
            raise ValueError("crypto_unavailable")
        if not isinstance(token, str) or len(token) > _MAX_TOKEN_BYTES:
            raise ValueError("invalid_token")
        parts = token.split(".")
        if len(parts) != 3 or not all(parts):
            raise ValueError("unsigned_or_malformed_token")
        try:
            header = json.loads(_unb64url(parts[0]).decode("utf-8"))
            payload = json.loads(_unb64url(parts[1]).decode("utf-8"))
            signature = _unb64url(parts[2])
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("malformed_token") from exc
        if not isinstance(header, dict) or set(header) != {"alg", "kid", "typ", "v"} or header.get("alg") != "EdDSA" or header.get("typ") != "UCAN" or header.get("v") != 1:
            raise ValueError("algorithm_or_version_downgrade")
        if not isinstance(payload, dict) or set(payload) - {"iss", "aud", "exp", "iat", "jti", "att", "prf", "nbf"}:
            raise ValueError("invalid_claims")
        issuer, audience = _string(payload.get("iss"), "issuer"), _string(payload.get("aud"), "audience")
        kid, nonce = _string(header.get("kid"), "kid"), _string(payload.get("jti"), "nonce")
        exp, iat = _timestamp(payload.get("exp"), "exp"), _timestamp(payload.get("iat"), "iat")
        nbf = None if "nbf" not in payload else _timestamp(payload["nbf"], "nbf")
        if exp < iat or (nbf is not None and nbf > exp):
            raise ValueError("invalid_time_window")
        if now > exp + self.clock_skew_seconds:
            raise ValueError("expired")
        # ``iat`` is also a lower validity bound.  Treating an absent ``nbf``
        # as a wildcard would make a future-issued token immediately usable.
        effective_nbf = max(iat, nbf) if nbf is not None else iat
        if now + self.clock_skew_seconds < effective_nbf:
            raise ValueError("not_yet_valid")
        att = payload.get("att")
        if not isinstance(att, list) or not att:
            raise ValueError("capabilities_required")
        capabilities = tuple(UCANCapability.from_mapping(item) for item in att)
        proofs_raw = payload.get("prf")
        if not isinstance(proofs_raw, list) or len(proofs_raw) > 1:
            raise ValueError("invalid_proofs")
        proofs = tuple(_string(item, "proof") for item in proofs_raw)
        if len(set(proofs)) != len(proofs):
            raise ValueError("duplicate_proof")
        if self.ledger is None:
            if self.require_ledger:
                raise ValueError("ledger_unavailable")
            key = None
        else:
            try:
                key = self.ledger.resolve_public_key(issuer, kid, now=now)
            except LedgerUnavailableError as exc:
                raise ValueError("ledger_unavailable") from exc
        if key is None:
            raise ValueError("verification_key_unavailable")
        if len(signature) != 64:
            raise ValueError("invalid_signature")
        try:
            Ed25519PublicKey.from_public_bytes(key).verify(signature, (parts[0] + "." + parts[1]).encode("ascii"))
        except (InvalidSignature, ValueError, TypeError) as exc:
            raise ValueError("invalid_signature") from exc
        delegation = UCANDelegation(issuer, audience, _safe_id(token), nonce, effective_nbf, exp, capabilities, proofs, kid)
        return delegation, token

    @staticmethod
    def _attenuates(parent: UCANCapability, child: UCANCapability) -> bool:
        if not resource_covers(parent.resource, child.resource) or not ability_covers(parent.ability, child.ability):
            return False
        # A child can add a bound to an unbounded parent.  It cannot remove or
        # relax an inherited bound.
        for name, parent_value in parent.bounds.items():
            if name not in child.bounds:
                return False
            child_value = child.bounds[name]
            if name in _BOUND_NUMERIC and child_value > parent_value:
                return False
            if name == "nbf" and child_value < parent_value:
                return False
            if name == "exp" and child_value > parent_value:
                return False
            if name in _BOUND_EXACT and child_value != parent_value:
                return False
        return True

    @staticmethod
    def _request_within(capability: UCANCapability, resource: str, ability: str, request_bounds: Mapping[str, Any]) -> bool:
        if not resource_covers(capability.resource, resource) or not ability_covers(capability.ability, ability):
            return False
        try:
            bounds = _parse_bounds(dict(request_bounds))
        except (TypeError, ValueError):
            return False
        for name, limit in capability.bounds.items():
            if name in _BOUND_NUMERIC:
                if name not in bounds or bounds[name] > limit:
                    return False
            elif name == "nbf":
                # Request has no independent validity time, therefore enforced
                # by token validation; if supplied it cannot precede the grant.
                if name in bounds and bounds[name] < limit:
                    return False
            elif name == "exp":
                if name in bounds and bounds[name] > limit:
                    return False
            elif name in _BOUND_EXACT and bounds.get(name) != limit:
                return False
        return True

    def verify(
        self, chain: str | Iterable[str], *, resource: str | None = None, ability: str | None = None,
        audience: str | None = None, expected_resource: str | None = None, expected_ability: str | None = None,
        expected_audience: str | None = None, request_bounds: Mapping[str, Any] | None = None,
        now: float | None = None, consume_nonce: bool = True,
    ) -> UCANVerificationResult:
        """Verify a root-to-leaf chain and atomically consume its leaf nonce."""
        expected_resource = resource if resource is not None else expected_resource
        expected_ability = ability if ability is not None else expected_ability
        expected_audience = audience if audience is not None else expected_audience
        try:
            target_resource = _string(expected_resource, "requested_resource")
            target_ability = _string(expected_ability, "requested_ability")
            target_audience = _string(expected_audience, "requested_audience")
            if target_resource == "*" or target_ability == "*":
                return self._deny("wildcard_request_rejected")
            target_bounds = dict(request_bounds or {})
            _parse_bounds(target_bounds)
            current = time.time() if now is None else _timestamp(now, "now")
        except (TypeError, ValueError):
            return self._deny("invalid_request")
        if not HAVE_CRYPTO_ED25519:
            return self._deny("crypto_unavailable")
        if self.require_ledger and (self.ledger is None or not self.ledger.available):
            return self._deny("ledger_unavailable")
        if isinstance(chain, str):
            tokens = [chain]
        else:
            try:
                tokens = list(chain)
            except TypeError:
                return self._deny("invalid_chain")
        if not tokens or len(tokens) > self.max_chain_length:
            return self._deny("invalid_chain_length")
        parsed: list[UCANDelegation] = []
        raw_tokens: list[str] = []
        try:
            for token in tokens:
                delegation, raw_token = self._parse_and_verify(token, current)
                if self.ledger is not None and (self.ledger.is_revoked(delegation.token_id) or self.ledger.is_revoked(delegation.nonce)):
                    return self._deny("revoked", parsed + [delegation])
                parsed.append(delegation)
                raw_tokens.append(raw_token)
        except LedgerUnavailableError:
            return self._deny("ledger_unavailable", parsed)
        except ValueError as exc:
            return self._deny(str(exc), parsed)
        if len({d.token_id for d in parsed}) != len(parsed) or len({d.nonce for d in parsed}) != len(parsed):
            return self._deny("cyclic_or_duplicate_chain", parsed)
        if self.trusted_issuers is not None and parsed[0].issuer not in self.trusted_issuers:
            return self._deny("untrusted_root_issuer", parsed)
        if parsed[0].proofs:
            return self._deny("cyclic_or_non_rooted_chain", parsed)
        for index in range(1, len(parsed)):
            parent, child = parsed[index - 1], parsed[index]
            if child.issuer != parent.audience or child.proofs != (parent.token_id,):
                return self._deny("proof_chain_mismatch", parsed)
            if child.not_before is not None and parent.not_before is not None and child.not_before < parent.not_before:
                return self._deny("time_attenuation_failed", parsed)
            if child.expires_at > parent.expires_at:
                return self._deny("time_attenuation_failed", parsed)
            for child_capability in child.capabilities:
                if not any(self._attenuates(parent_capability, child_capability) for parent_capability in parent.capabilities):
                    return self._deny("capability_attenuation_failed", parsed)
        leaf = parsed[-1]
        if leaf.audience != target_audience:
            return self._deny("audience_mismatch", parsed)
        if not any(self._request_within(capability, target_resource, target_ability, target_bounds) for capability in leaf.capabilities):
            return self._deny("capability_or_bounds_denied", parsed)
        if consume_nonce:
            if self.ledger is None:
                return self._deny("ledger_unavailable", parsed)
            try:
                # Namespace binds a nonce to its issuer, intended audience, and
                # token identity, avoiding cross-tenant nonce collisions.
                namespace = leaf.issuer + "\x00" + leaf.audience + "\x00" + leaf.token_id
                if not self.ledger.consume_nonce(namespace, leaf.nonce, expires_at=leaf.expires_at):
                    return self._deny("replayed", parsed)
            except LedgerUnavailableError:
                return self._deny("ledger_unavailable", parsed)
        return UCANVerificationResult(True, "ok", len(parsed), leaf.issuer, leaf.audience, tuple(d.token_id for d in parsed))

    verify_chain = verify


def verify_ucan(chain: str | Iterable[str], **kwargs: Any) -> UCANVerificationResult:
    """Convenience wrapper; callers should normally retain a verifier instance."""
    verifier = kwargs.pop("verifier", None)
    if verifier is None:
        verifier = UCANVerifier(ledger=kwargs.pop("ledger", None))
    if not isinstance(verifier, UCANVerifier):
        raise TypeError("verifier_must_be_UCANVerifier")
    return verifier.verify(chain, **kwargs)
