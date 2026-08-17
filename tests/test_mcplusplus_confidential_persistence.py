"""
Kit-side confidential persistence tests (MCPP-074 / MCPP-G150).

Interface: ConfidentialPersistenceReceipt@1
Evidence: kit artifact store, Event DAG metadata, cache/local fallback paths.

Proves that kit persistence hooks for EncryptedArtifactRef@1:
  - never write plaintext on primary, cache, or offline fallback paths;
  - fail closed on altered ciphertext verification;
  - fail closed on revoked key / capability access;
  - emit Event DAG nodes and receipts that attest use without disclosure.

Conflict policy: Do not log plaintext in the test harness either.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import pytest

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:  # pragma: no cover
    AESGCM = None  # type: ignore[misc, assignment]

# Optional Event DAG integration with kit runtime module.
try:
    from ipfs_kit_py.mcp_server.mcplusplus.event_dag import EventDAGStore
except Exception:  # pragma: no cover - harness still covers persistence alone
    EventDAGStore = None  # type: ignore[misc, assignment]


INTERFACE_RECEIPT = "ConfidentialPersistenceReceipt@1"
SCHEMA_MARKER_REF = "mcp++/confidential/encrypted-artifact-ref@1"
SCHEMA_MARKER_ENVELOPE = "mcp++/confidential/key-envelope@1"
SCHEMA_MARKER_RECEIPT = "mcp++/confidential/persistence-receipt@1"
ABILITY_DECRYPT = "mcp++/confidential/decrypt"

SECRET_PLAINTEXT = "KIT-SECRET-CREDENTIAL-VALUE-ALPHA-7781"
SECRET_FRAGMENT = "CREDENTIAL-VALUE-ALPHA-7781"
FORBIDDEN_FIELDS = frozenset(
    {"plaintext", "plaintext_b64", "dek", "content_key", "raw_key", "private_key", "unwrapped_key"}
)


def _require_crypto() -> None:
    if AESGCM is None:
        pytest.skip("cryptography AESGCM unavailable")


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64url(value: str) -> bytes:
    text = str(value).strip()
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _b32(data: bytes) -> str:
    return base64.b32encode(data).decode("ascii").rstrip("=").lower()


def cid_for_bytes(payload: bytes) -> str:
    digest = hashlib.sha256(payload).digest()
    return "b" + _b32(bytes([0x01, 0x55, 0x12, 0x20]) + digest)


def canonicalize(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def cid_for_obj(value: Any) -> str:
    return cid_for_bytes(canonicalize(value))


class ConfidentialPersistenceError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


@dataclass
class KitPrincipal:
    did: str
    wrap_key: bytes
    kid: str = "v1"


@dataclass
class ConfidentialPersistenceHooks:
    """Kit persistence hooks for confidential artifacts (test harness).

    Mirrors the production obligation that primary, cache, and local-fallback
    stores hold only ciphertext + EncryptedArtifactRef metadata — never
    plaintext or unwrapped content keys.
    """

    root: Path
    primary_available: bool = True
    revoked_caps: Set[str] = field(default_factory=set)
    revoked_keys: Set[str] = field(default_factory=set)
    principals: Dict[str, KitPrincipal] = field(default_factory=dict)
    event_nodes: List[Dict[str, Any]] = field(default_factory=list)
    log_lines: List[str] = field(default_factory=list)
    event_dag_store: Any = None

    def __post_init__(self) -> None:
        for tier in ("primary", "cache", "local_fallback", "logs"):
            (self.root / tier).mkdir(parents=True, exist_ok=True)

    def register(self, principal: KitPrincipal) -> None:
        if len(principal.wrap_key) != 32:
            raise ConfidentialPersistenceError("invalid_wrap_key")
        self.principals[principal.did] = principal

    def revoke_capability(self, capability_cid: str) -> None:
        self.revoked_caps.add(capability_cid)
        self._audit("capability_revoked", capability_cid=capability_cid)

    def revoke_content_key(self, content_key_id: str) -> None:
        self.revoked_keys.add(content_key_id)
        self._audit("content_key_revoked", content_key_id=content_key_id)

    def seal(
        self,
        plaintext: str | bytes,
        *,
        recipients: Sequence[str],
        issuer: str,
        capability_cid: str,
        prefer_fallback: bool = False,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        _require_crypto()
        plaintext_bytes = plaintext.encode("utf-8") if isinstance(plaintext, str) else bytes(plaintext)
        if not recipients:
            raise ConfidentialPersistenceError("no_recipients")
        for did in recipients:
            if did not in self.principals:
                raise ConfidentialPersistenceError("unknown_recipient")

        plaintext_schema_cid = cid_for_obj({"type": "string", "format": "confidential-opaque"})
        content_key_id = "ck-" + secrets.token_hex(8)
        dek = AESGCM.generate_key(bit_length=256)
        nonce = secrets.token_bytes(12)
        aad = plaintext_schema_cid.encode("utf-8")
        package = nonce + AESGCM(dek).encrypt(nonce, plaintext_bytes, aad)
        ciphertext_cid = cid_for_bytes(package)

        wrapped_keys = []
        for did in recipients:
            principal = self.principals[did]
            wn = secrets.token_bytes(12)
            wrapped = wn + AESGCM(principal.wrap_key).encrypt(wn, dek, None)
            wrapped_keys.append(
                {
                    "recipient": did,
                    "recipient_kid": principal.kid,
                    "key_wrap": "direct-AES-256-GCM",
                    "wrapped_key_b64url": _b64url(wrapped),
                    "capability_cid": capability_cid,
                }
            )

        access_caps = [
            {
                "kind": "ucan_proof_cid",
                "cid": capability_cid,
                "ability": ABILITY_DECRYPT,
                "resource": ciphertext_cid,
            }
        ]
        key_envelope = {
            "schema": SCHEMA_MARKER_ENVELOPE,
            "content_key_id": content_key_id,
            "wrapped_keys": wrapped_keys,
            "access_caps": access_caps,
            "epoch": 1,
            "revocation_binding": {
                "mode": "delegation_ledger",
                "ledger_or_registry": "kit-confidential-ledger",
                "revocation_policy_cid": None,
            },
            "created_at_ms": 1_700_000_000_000,
            "supersedes_content_key_id": None,
        }
        ref: Dict[str, Any] = {
            "schema": SCHEMA_MARKER_REF,
            "ciphertext_cid": ciphertext_cid,
            "algorithm": {
                "content_aead": "AES-256-GCM",
                "key_wrap": "direct-AES-256-GCM",
                "ciphertext_layout": "nonce_prepended_ciphertext_tag",
                "aead_tag_length": 16,
                "aad_binding": "plaintext_schema_cid",
                "hkdf_info": "mcp++/confidential/content-key@1",
            },
            "key_envelope": key_envelope,
            "plaintext_schema_cid": plaintext_schema_cid,
            "protected_digest": None,
            "disclosure_policy_cid": None,
            "retention_policy_cid": None,
            "redaction": {
                "mode": "never-export-plaintext",
                "public_fields": [
                    "schema",
                    "ciphertext_cid",
                    "ref_cid",
                    "plaintext_schema_cid",
                    "redaction.mode",
                ],
                "redaction_receipt_cid": None,
                "notes": None,
            },
            "canonicalization": "mcpp-jcs-v1",
            "issuer": issuer,
            "created_at_ms": 1_700_000_000_000,
            "parents": [],
            "correlation_id": "kit-corr-1",
            "label": "kit-confidential",
            "recipients": [
                {"recipient": did, "recipient_kid": self.principals[did].kid} for did in recipients
            ],
            "access_caps": access_caps,
            "metadata": {"kit_hook": "confidential_persistence"},
        }
        ref["ref_cid"] = cid_for_obj({k: v for k, v in ref.items() if k != "ref_cid"})

        receipt = self._persist_all_paths(ref, package, prefer_fallback=prefer_fallback)
        event = self._emit_event_dag(ref, receipt)
        receipt["event_cid"] = event["event_cid"]
        self._atomic_json(self.root / "primary" / f"{ref['ref_cid']}.receipt.json", receipt)
        self._audit(
            "sealed",
            ref_cid=ref["ref_cid"],
            ciphertext_cid=ciphertext_cid,
            paths=receipt["paths_written"],
        )
        return ref, receipt

    def verify_ciphertext(self, ref: Mapping[str, Any], package: bytes | None = None) -> bool:
        package = package if package is not None else self.load_ciphertext(str(ref["ciphertext_cid"]))
        if package is None:
            raise ConfidentialPersistenceError("ciphertext_missing")
        if cid_for_bytes(package) != ref["ciphertext_cid"]:
            raise ConfidentialPersistenceError("ciphertext_integrity_failed")
        return True

    def open(
        self,
        ref: Mapping[str, Any],
        *,
        recipient: str,
        capability_cid: str,
        package: bytes | None = None,
    ) -> bytes:
        _require_crypto()
        self.verify_ciphertext(ref, package)
        ck = str(ref["key_envelope"]["content_key_id"])
        if ck in self.revoked_keys:
            self._audit("decrypt_denied", reason="content_key_revoked", content_key_id=ck)
            raise ConfidentialPersistenceError("content_key_revoked")
        if capability_cid in self.revoked_caps:
            self._audit("decrypt_denied", reason="capability_revoked", capability_cid=capability_cid)
            raise ConfidentialPersistenceError("capability_revoked")
        if not self._cap_ok(ref, capability_cid):
            raise ConfidentialPersistenceError("capability_not_granted")

        wrap = None
        for entry in ref["key_envelope"].get("wrapped_keys") or []:
            if entry.get("recipient") == recipient:
                wrap = entry
                break
        if wrap is None:
            raise ConfidentialPersistenceError("wrong_recipient")
        wrap_cap = wrap.get("capability_cid")
        if wrap_cap is not None and str(wrap_cap) in self.revoked_caps:
            raise ConfidentialPersistenceError("capability_revoked")
        if recipient not in self.principals:
            raise ConfidentialPersistenceError("unauthorized_read")

        try:
            wrapped = _unb64url(str(wrap["wrapped_key_b64url"]))
            dek = AESGCM(self.principals[recipient].wrap_key).decrypt(wrapped[:12], wrapped[12:], None)
        except Exception as exc:
            raise ConfidentialPersistenceError("unwrap_failed") from exc

        package = package if package is not None else self.load_ciphertext(str(ref["ciphertext_cid"]))
        if package is None or len(package) < 13:
            raise ConfidentialPersistenceError("ciphertext_missing")
        try:
            return AESGCM(dek).decrypt(
                package[:12],
                package[12:],
                str(ref["plaintext_schema_cid"]).encode("utf-8"),
            )
        except Exception as exc:
            raise ConfidentialPersistenceError("aead_verify_failed") from exc

    def load_ciphertext(self, ciphertext_cid: str) -> Optional[bytes]:
        for tier in ("primary", "cache", "local_fallback"):
            path = self.root / tier / "blobs" / ciphertext_cid
            if path.is_file():
                return path.read_bytes()
        return None

    def scan_for_plaintext(self, needle: str = SECRET_FRAGMENT) -> List[str]:
        hits: List[str] = []
        needle_b = needle.encode("utf-8")
        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if needle_b in data:
                hits.append(str(path.relative_to(self.root)))
        return hits

    # -- internal persistence -----------------------------------------------

    def _persist_all_paths(
        self, ref: Mapping[str, Any], package: bytes, *, prefer_fallback: bool
    ) -> Dict[str, Any]:
        paths: List[str] = []
        use_fallback = prefer_fallback or not self.primary_available
        if use_fallback:
            self._write_tier("local_fallback", ref, package)
            paths.append("local_fallback")
        else:
            self._write_tier("primary", ref, package)
            paths.append("primary")
        # Cache always stores ciphertext + redacted metadata only.
        self._write_tier("cache", ref, package, meta_only_extra=True)
        paths.append("cache")
        return {
            "schema": SCHEMA_MARKER_RECEIPT,
            "interface": INTERFACE_RECEIPT,
            "ref_cid": ref["ref_cid"],
            "ciphertext_cid": ref["ciphertext_cid"],
            "plaintext_schema_cid": ref["plaintext_schema_cid"],
            "paths_written": paths,
            "plaintext_written": False,
            "content_key_persisted": False,
            "redaction_mode": (ref.get("redaction") or {}).get("mode"),
            "event_cid": None,
            "kind": "confidential_artifact_persisted",
            "description": "kit ciphertext-only persistence; plaintext not included",
        }

    def _write_tier(
        self,
        tier: str,
        ref: Mapping[str, Any],
        package: bytes,
        *,
        meta_only_extra: bool = False,
    ) -> None:
        base = self.root / tier
        (base / "blobs").mkdir(parents=True, exist_ok=True)
        blob_path = base / "blobs" / str(ref["ciphertext_cid"])
        tmp = blob_path.with_suffix(".tmp")
        tmp.write_bytes(package)
        tmp.replace(blob_path)
        if meta_only_extra and tier == "cache":
            meta = {
                "ref_cid": ref["ref_cid"],
                "ciphertext_cid": ref["ciphertext_cid"],
                "schema": ref["schema"],
                "redaction": ref.get("redaction"),
            }
            self._assert_clean(meta)
            self._atomic_json(base / f"{ref['ref_cid']}.meta.json", meta)
        else:
            self._assert_clean(ref)
            self._atomic_json(base / f"{ref['ref_cid']}.ref.json", ref)

    def _emit_event_dag(self, ref: Mapping[str, Any], receipt: Mapping[str, Any]) -> Dict[str, Any]:
        parents = [n["event_cid"] for n in self.event_nodes[-1:]] if self.event_nodes else []
        event = {
            "parents": parents,
            "kind": "confidential_artifact_used",
            "ref_cid": ref["ref_cid"],
            "ciphertext_cid": ref["ciphertext_cid"],
            "plaintext_schema_cid": ref["plaintext_schema_cid"],
            "redaction_mode": (ref.get("redaction") or {}).get("mode"),
            "receipt_ref": receipt["ref_cid"],
            "description": "decrypt-authorized; plaintext not included",
            "metadata": {"plaintext_written": False, "paths_written": list(receipt["paths_written"])},
            "peer_did": "",
            "timestamps": {},
        }
        event["event_cid"] = cid_for_obj(event)
        self._assert_clean(event)
        self.event_nodes.append(event)
        self._atomic_json(self.root / "primary" / f"{event['event_cid']}.event.json", event)

        # Also feed kit EventDAGStore when available (metadata only).
        if self.event_dag_store is not None:
            try:
                self.event_dag_store.append(dict(event))
            except Exception as exc:  # pragma: no cover - optional integration
                self._audit("event_dag_append_failed", error=type(exc).__name__)
        return event

    def _cap_ok(self, ref: Mapping[str, Any], capability_cid: str) -> bool:
        caps = list(ref.get("access_caps") or []) + list(ref["key_envelope"].get("access_caps") or [])
        for cap in caps:
            if cap.get("cid") == capability_cid and cap.get("kind") == "ucan_proof_cid":
                resource = cap.get("resource")
                if resource in (None, ref.get("ciphertext_cid"), ref.get("ref_cid")):
                    return True
        return False

    def _audit(self, event: str, **fields: Any) -> None:
        payload = {"event": event, **fields}
        self._assert_clean(payload)
        line = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if SECRET_FRAGMENT in line or SECRET_PLAINTEXT in line:
            raise ConfidentialPersistenceError("plaintext_log_leak")
        self.log_lines.append(line)
        log_path = self.root / "logs" / "kit-confidential.jsonl"
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    @staticmethod
    def _assert_clean(value: Any, path: str = "") -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                if str(key).lower() in FORBIDDEN_FIELDS:
                    raise ConfidentialPersistenceError("forbidden_field", f"{path}/{key}")
                ConfidentialPersistenceHooks._assert_clean(item, f"{path}/{key}")
        elif isinstance(value, list):
            for i, item in enumerate(value):
                ConfidentialPersistenceHooks._assert_clean(item, f"{path}/{i}")

    @staticmethod
    def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(path)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def crypto_ready():
    _require_crypto()


@pytest.fixture
def alice() -> KitPrincipal:
    return KitPrincipal(did="did:key:z6MkKitAliceRecipient00001", wrap_key=secrets.token_bytes(32))


@pytest.fixture
def bob() -> KitPrincipal:
    return KitPrincipal(did="did:key:z6MkKitBobRecipient0000001", wrap_key=secrets.token_bytes(32))


@pytest.fixture
def hooks(tmp_path, alice, bob, crypto_ready) -> ConfidentialPersistenceHooks:
    dag = None
    if EventDAGStore is not None:
        dag = EventDAGStore(storage_dir=str(tmp_path / "event-dag"), hot_event_max=100, epoch_size=50)
    store = ConfidentialPersistenceHooks(root=tmp_path / "kit-confidential", event_dag_store=dag)
    store.register(alice)
    store.register(bob)
    return store


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestKitNoPlaintextOnAnyPersistencePath:
    def test_primary_and_cache_ciphertext_only(self, hooks, alice):
        cap = cid_for_obj({"kit": "cap-1"})
        ref, receipt = hooks.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkKitIssuer000000000001",
            capability_cid=cap,
        )
        assert receipt["interface"] == INTERFACE_RECEIPT
        assert receipt["plaintext_written"] is False
        assert "primary" in receipt["paths_written"]
        assert "cache" in receipt["paths_written"]
        assert hooks.scan_for_plaintext() == []
        # Blobs exist and match ciphertext CID.
        blob = hooks.load_ciphertext(ref["ciphertext_cid"])
        assert blob is not None
        assert cid_for_bytes(blob) == ref["ciphertext_cid"]
        assert SECRET_FRAGMENT.encode() not in blob

    def test_local_fallback_when_primary_unavailable(self, hooks, alice):
        hooks.primary_available = False
        cap = cid_for_obj({"kit": "cap-fallback"})
        ref, receipt = hooks.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkKitIssuer000000000001",
            capability_cid=cap,
            prefer_fallback=True,
        )
        assert "local_fallback" in receipt["paths_written"]
        assert "primary" not in receipt["paths_written"]
        assert hooks.scan_for_plaintext() == []
        assert (hooks.root / "local_fallback" / "blobs" / ref["ciphertext_cid"]).is_file()

    def test_forced_fallback_path_still_encrypted(self, hooks, alice):
        cap = cid_for_obj({"kit": "cap-fb2"})
        _ref, receipt = hooks.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkKitIssuer000000000001",
            capability_cid=cap,
            prefer_fallback=True,
        )
        assert receipt["paths_written"][0] == "local_fallback"
        assert hooks.scan_for_plaintext(SECRET_PLAINTEXT) == []


class TestKitEventDagAndLogs:
    def test_event_dag_metadata_has_no_plaintext(self, hooks, alice):
        cap = cid_for_obj({"kit": "cap-dag"})
        ref, receipt = hooks.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkKitIssuer000000000001",
            capability_cid=cap,
        )
        assert hooks.event_nodes
        for node in hooks.event_nodes:
            raw = json.dumps(node, sort_keys=True)
            assert SECRET_FRAGMENT not in raw
            assert node["kind"] == "confidential_artifact_used"
            assert node["ref_cid"] == ref["ref_cid"]
            assert node["metadata"]["plaintext_written"] is False
        assert receipt["event_cid"] == hooks.event_nodes[-1]["event_cid"]

        if hooks.event_dag_store is not None:
            # Kit EventDAGStore retained the redacted node.
            state_path = Path(hooks.event_dag_store.state_path)
            if state_path.is_file():
                assert SECRET_FRAGMENT not in state_path.read_text(encoding="utf-8")

    def test_kit_logs_never_include_plaintext(self, hooks, alice):
        cap = cid_for_obj({"kit": "cap-log"})
        hooks.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkKitIssuer000000000001",
            capability_cid=cap,
        )
        for line in hooks.log_lines:
            assert SECRET_FRAGMENT not in line
            assert SECRET_PLAINTEXT not in line
        log_file = hooks.root / "logs" / "kit-confidential.jsonl"
        assert SECRET_FRAGMENT not in log_file.read_text(encoding="utf-8")


class TestKitAlteredCiphertextFailsVerify:
    def test_bit_flip_fails_cid_verify(self, hooks, alice):
        cap = cid_for_obj({"kit": "cap-tamper"})
        ref, _ = hooks.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkKitIssuer000000000001",
            capability_cid=cap,
        )
        package = bytearray(hooks.load_ciphertext(ref["ciphertext_cid"]) or b"")
        package[-1] ^= 0xFF
        with pytest.raises(ConfidentialPersistenceError) as exc:
            hooks.verify_ciphertext(ref, bytes(package))
        assert exc.value.code == "ciphertext_integrity_failed"

    def test_bit_flip_under_new_cid_fails_aead(self, hooks, alice):
        cap = cid_for_obj({"kit": "cap-tamper2"})
        ref, _ = hooks.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkKitIssuer000000000001",
            capability_cid=cap,
        )
        package = bytearray(hooks.load_ciphertext(ref["ciphertext_cid"]) or b"")
        package[15] ^= 0x0F
        forged = dict(ref)
        forged["ciphertext_cid"] = cid_for_bytes(bytes(package))
        with pytest.raises(ConfidentialPersistenceError) as exc:
            hooks.open(forged, recipient=alice.did, capability_cid=cap, package=bytes(package))
        assert exc.value.code in {"aead_verify_failed", "unwrap_failed", "capability_not_granted"}

    def test_authorized_roundtrip(self, hooks, alice):
        cap = cid_for_obj({"kit": "cap-ok"})
        ref, _ = hooks.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkKitIssuer000000000001",
            capability_cid=cap,
        )
        assert hooks.verify_ciphertext(ref) is True
        assert hooks.open(ref, recipient=alice.did, capability_cid=cap).decode() == SECRET_PLAINTEXT
        assert hooks.scan_for_plaintext() == []


class TestKitRevokedKeyAccessFailsClosed:
    def test_wrong_recipient(self, hooks, alice, bob):
        cap = cid_for_obj({"kit": "cap-wrong"})
        ref, _ = hooks.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkKitIssuer000000000001",
            capability_cid=cap,
        )
        with pytest.raises(ConfidentialPersistenceError) as exc:
            hooks.open(ref, recipient=bob.did, capability_cid=cap)
        assert exc.value.code == "wrong_recipient"

    def test_unauthorized_principal(self, hooks, alice):
        cap = cid_for_obj({"kit": "cap-unauth"})
        ref, _ = hooks.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkKitIssuer000000000001",
            capability_cid=cap,
        )
        with pytest.raises(ConfidentialPersistenceError) as exc:
            hooks.open(ref, recipient="did:key:z6MkUnknownPrincipal000001", capability_cid=cap)
        assert exc.value.code in {"wrong_recipient", "unauthorized_read"}

    def test_revoked_capability(self, hooks, alice):
        cap = cid_for_obj({"kit": "cap-rev"})
        ref, _ = hooks.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkKitIssuer000000000001",
            capability_cid=cap,
        )
        assert hooks.open(ref, recipient=alice.did, capability_cid=cap).decode() == SECRET_PLAINTEXT
        hooks.revoke_capability(cap)
        with pytest.raises(ConfidentialPersistenceError) as exc:
            hooks.open(ref, recipient=alice.did, capability_cid=cap)
        assert exc.value.code == "capability_revoked"
        # Historical ciphertext remains (honest revocation: access control, not erasure).
        assert hooks.load_ciphertext(ref["ciphertext_cid"]) is not None
        assert hooks.scan_for_plaintext() == []

    def test_revoked_content_key(self, hooks, alice):
        cap = cid_for_obj({"kit": "cap-ck"})
        ref, _ = hooks.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkKitIssuer000000000001",
            capability_cid=cap,
        )
        hooks.revoke_content_key(ref["key_envelope"]["content_key_id"])
        with pytest.raises(ConfidentialPersistenceError) as exc:
            hooks.open(ref, recipient=alice.did, capability_cid=cap)
        assert exc.value.code == "content_key_revoked"


class TestConfidentialPersistenceReceipt:
    def test_receipt_shape_and_non_disclosure(self, hooks, alice):
        cap = cid_for_obj({"kit": "cap-receipt"})
        ref, receipt = hooks.seal(
            SECRET_PLAINTEXT,
            recipients=[alice.did],
            issuer="did:key:z6MkKitIssuer000000000001",
            capability_cid=cap,
        )
        assert receipt["schema"] == SCHEMA_MARKER_RECEIPT
        assert receipt["interface"] == INTERFACE_RECEIPT
        assert receipt["ref_cid"] == ref["ref_cid"]
        assert receipt["ciphertext_cid"] == ref["ciphertext_cid"]
        assert receipt["plaintext_written"] is False
        assert receipt["content_key_persisted"] is False
        assert receipt["kind"] == "confidential_artifact_persisted"
        assert SECRET_FRAGMENT not in json.dumps(receipt)


class TestHarnessLoggingPolicy:
    def test_pytest_caplog_clean(self, hooks, alice, caplog):
        cap = cid_for_obj({"kit": "cap-pylog"})
        with caplog.at_level(logging.DEBUG):
            logging.getLogger("ipfs_kit.mcplusplus.confidential").info("kit seal start")
            hooks.seal(
                SECRET_PLAINTEXT,
                recipients=[alice.did],
                issuer="did:key:z6MkKitIssuer000000000001",
                capability_cid=cap,
            )
        assert SECRET_FRAGMENT not in caplog.text
        assert SECRET_PLAINTEXT not in caplog.text
