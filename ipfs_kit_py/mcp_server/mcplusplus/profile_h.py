"""Profile H (x402) paid operations for :mod:`ipfs_kit_py`.

This module deliberately keeps payment credentials out of the storage backend.
It adapts the shared ``mcplusplus_profile_h`` seller runtime and places the
durable payment fence immediately in front of the supplied IPFS effect.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sqlite3
import threading
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

from mcplusplus_profile_h import (
    CallbackFacilitator,
    CapabilityCatalog,
    CommercialBinding,
    Decision,
    DuckDBPaymentLedger,
    FileCIDArtifactStore,
    PaidCapability,
    PaymentContext,
    PaymentDecision,
    PaymentPolicyEngine,
    PaymentRequirement,
    RequestContext,
    SellerResult,
    SellerRuntime,
    ProfileHControlPlane,
    ProfileHTransportAdapter,
    http_response,
    libp2p_response,
)
from mcplusplus_profile_h.canonical import canonical_json, cid_for, commitment
from mcplusplus_profile_h.errors import ProfileHError


_NAMESPACE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,127}$")
_CID = re.compile(r"^(?:Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{20,})$")


class KitPaymentError(ProfileHError):
    """Stable Profile H error raised before any kit side effect."""


@dataclass(frozen=True, slots=True)
class KitOperationTerms:
    """Commercial and resource limits for one protected operation."""

    amount: str
    quota_units: int = 1
    unit: str = "operation"
    max_request_units: int = 1
    retention_seconds: int = 86_400
    max_retention_seconds: int = 2_592_000
    namespaces: tuple[str, ...] = ("default",)

    def __post_init__(self) -> None:
        if not self.amount.isdigit() or (len(self.amount) > 1 and self.amount.startswith("0")):
            raise ValueError("amount must be a canonical atomic-unit integer")
        if self.quota_units < 1 or self.max_request_units < 1:
            raise ValueError("quota limits must be positive")
        if not 1 <= self.retention_seconds <= self.max_retention_seconds:
            raise ValueError("retention is outside configured bounds")
        if not self.namespaces or any(not _NAMESPACE.fullmatch(item) for item in self.namespaces):
            raise ValueError("at least one valid namespace is required")


@dataclass(frozen=True, slots=True)
class KitPaymentConfig:
    seller_did: str
    descriptor_cid: str
    pay_to: str
    asset: str
    network: str = "eip155:84532"
    scheme: str = "exact"
    catalog_version: str = "1"
    operations: Mapping[str, KitOperationTerms] = field(default_factory=dict)
    unlisted_free: bool = True

    def __post_init__(self) -> None:
        if not self.seller_did.startswith("did:") or not self.descriptor_cid:
            raise ValueError("seller_did and descriptor_cid are required")
        if ":" not in self.network or not self.pay_to or not self.asset:
            raise ValueError("valid network, asset, and payee are required")
        normalized = {str(key): value for key, value in self.operations.items()}
        if not normalized:
            raise ValueError("at least one paid operation must be configured")
        object.__setattr__(self, "operations", normalized)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "KitPaymentConfig":
        """Load an operator configuration without accepting unknown term types."""
        operations = {
            name: terms if isinstance(terms, KitOperationTerms) else KitOperationTerms(**dict(terms))
            for name, terms in dict(value.get("operations", {})).items()
        }
        fields = {key: item for key, item in value.items() if key != "operations"}
        return cls(operations=operations, **fields)


def default_operation_terms(amounts: Mapping[str, str]) -> dict[str, KitOperationTerms]:
    """Create the canonical storage, pin, and retrieval operation set."""
    required = {"storage/add", "storage/pin", "storage/retrieve"}
    missing = required.difference(amounts)
    if missing:
        raise ValueError(f"missing prices for: {', '.join(sorted(missing))}")
    return {
        "storage/add": KitOperationTerms(amounts["storage/add"], quota_units=1, unit="mebibyte", max_request_units=1024),
        "storage/pin": KitOperationTerms(amounts["storage/pin"], quota_units=30, unit="gigabyte-day", max_request_units=30),
        "storage/retrieve": KitOperationTerms(amounts["storage/retrieve"], quota_units=1024, unit="mebibyte", max_request_units=1024),
    }


class CatalogSigner:
    """Ed25519 catalog signer; only the public key is ever published."""

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._key = private_key

    @classmethod
    def generate(cls) -> "CatalogSigner":
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def load_or_create(cls, path: str | Path) -> "CatalogSigner":
        """Load a state-local key or create it with owner-only permissions."""
        key_path = Path(path)
        key_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            raw = key_path.read_bytes()
        except FileNotFoundError:
            key = Ed25519PrivateKey.generate()
            raw = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
            try:
                descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(raw)
            except FileExistsError:  # another process initialized the seller
                raw = key_path.read_bytes()
        if len(raw) != 32:
            raise ValueError("invalid persisted Ed25519 catalog key")
        os.chmod(key_path, 0o600)
        return cls(Ed25519PrivateKey.from_private_bytes(raw))

    def sign(self, document: Mapping[str, Any]) -> dict[str, Any]:
        unsigned = dict(document)
        unsigned.pop("signature", None)
        public = self._key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        unsigned.update({
            "signatureAlg": "Ed25519",
            "publicKey": base64.b64encode(public).decode("ascii"),
        })
        signature = self._key.sign(canonical_json(unsigned))
        return {
            **unsigned,
            "signature": base64.b64encode(signature).decode("ascii"),
        }

    @staticmethod
    def verify(document: Mapping[str, Any]) -> bool:
        try:
            unsigned = dict(document)
            unsigned.pop("signedCatalogCid", None)
            signature = base64.b64decode(unsigned.pop("signature"), validate=True)
            public = base64.b64decode(unsigned["publicKey"], validate=True)
            Ed25519PublicKey.from_public_bytes(public).verify(signature, canonical_json(unsigned))
            return True
        except (InvalidSignature, KeyError, TypeError, ValueError):
            return False


class EntitlementStore:
    """Durable, transactionally consumed quota and immutable usage receipts."""

    def __init__(self, path: str | Path, artifacts: FileCIDArtifactStore, clock_ms: Callable[[], int]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts = artifacts
        self.clock_ms = clock_ms
        self._lock = threading.RLock()
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS entitlements ("
                "cid TEXT PRIMARY KEY, subject TEXT NOT NULL, capability TEXT NOT NULL, "
                "namespace TEXT NOT NULL, cid_scope TEXT, quota INTEGER NOT NULL, consumed INTEGER NOT NULL, "
                "unit TEXT NOT NULL, expires INTEGER NOT NULL, settlement TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS entitlement_uses ("
                "idempotency_key TEXT PRIMARY KEY, request_cid TEXT NOT NULL, "
                "entitlement_cid TEXT NOT NULL, usage_cid TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=30, isolation_level=None)

    def issue(
        self, *, subject: str, capability_cid: str, namespace: str, cid_scope: str | None,
        quota: int, unit: str, expires_at: int, settlement_cid: str,
    ) -> str:
        artifact = {
            "schema": "mcp++/profile-h/paid-entitlement@1.0",
            "createdAt": self.clock_ms(), "parents": [settlement_cid],
            "correlationId": commitment({"settlement": settlement_cid, "subject": subject}),
            "settlementCid": settlement_cid, "subjectCommitment": commitment(subject),
            "capabilityCid": capability_cid, "namespace": namespace, "cidScope": cid_scope,
            "quotaUnits": quota, "consumedUnits": 0, "unit": unit, "expiresAt": expires_at,
        }
        entitlement_cid = self.artifacts.put(artifact)
        with self._connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO entitlements VALUES (?,?,?,?,?,?,?,?,?,?)",
                (entitlement_cid, commitment(subject), capability_cid, namespace, cid_scope,
                 quota, 0, unit, expires_at, settlement_cid),
            )
        return entitlement_cid

    def consume(
        self, entitlement_cid: str, *, subject: str, capability_cid: str,
        namespace: str, cid_scope: str | None, units: int,
    ) -> str:
        usage_cid, _ = self.consume_once(
            entitlement_cid, subject=subject, capability_cid=capability_cid,
            namespace=namespace, cid_scope=cid_scope, units=units,
            idempotency_key=commitment({"entitlement": entitlement_cid, "time": self.clock_ms()}),
            request_cid=commitment({"entitlement": entitlement_cid, "units": units, "time": self.clock_ms()}),
        )
        return usage_cid

    def consume_once(
        self, entitlement_cid: str, *, subject: str, capability_cid: str,
        namespace: str, cid_scope: str | None, units: int,
        idempotency_key: str, request_cid: str,
    ) -> tuple[str, bool]:
        """Consume once, returning the prior receipt for an identical retry."""
        if units < 1:
            raise KitPaymentError("H_ENTITLEMENT_EXHAUSTED", "usage units must be positive")
        with self._lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute(
                "SELECT request_cid,entitlement_cid,usage_cid FROM entitlement_uses WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if prior:
                db.rollback()
                if prior[0] != request_cid or prior[1] != entitlement_cid:
                    raise KitPaymentError("H_REQUEST_MISMATCH", "idempotency key is bound to another request")
                return str(prior[2]), True
            row = db.execute(
                "SELECT subject,capability,namespace,cid_scope,quota,consumed,unit,expires,settlement "
                "FROM entitlements WHERE cid=?", (entitlement_cid,),
            ).fetchone()
            if row is None:
                db.rollback()
                raise KitPaymentError("H_ENTITLEMENT_INVALID", "entitlement is unknown")
            expected_subject, expected_capability, expected_namespace, expected_cid, quota, consumed, unit, expires, settlement = row
            scoped = (
                expected_subject == commitment(subject) and expected_capability == capability_cid
                and expected_namespace == namespace and (expected_cid is None or expected_cid == cid_scope)
            )
            if not scoped:
                db.rollback()
                raise KitPaymentError("H_ENTITLEMENT_SCOPE_MISMATCH", "entitlement scope does not match request")
            if self.clock_ms() >= expires or consumed + units > quota:
                db.rollback()
                raise KitPaymentError("H_ENTITLEMENT_EXHAUSTED", "entitlement is expired or exhausted")
            usage = {
                "schema": "mcp++/profile-h/usage-record@1.0", "createdAt": self.clock_ms(),
                "parents": [entitlement_cid, settlement], "correlationId": commitment(request_cid),
                "entitlementCid": entitlement_cid, "unit": unit,
                "inputCid": cid_scope or commitment({"namespace": namespace}),
                "outputCid": commitment({"entitlement": entitlement_cid, "consumed": consumed + units}),
                "units": units, "recordedAt": self.clock_ms(),
            }
            usage_cid = self.artifacts.put(usage)
            db.execute("UPDATE entitlements SET consumed=consumed+? WHERE cid=?", (units, entitlement_cid))
            db.execute(
                "INSERT INTO entitlement_uses VALUES (?,?,?,?)",
                (idempotency_key, request_cid, entitlement_cid, usage_cid),
            )
            db.commit()
        return usage_cid, False

    def get(self, entitlement_cid: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT namespace,cid_scope,quota,consumed,unit,expires,settlement FROM entitlements WHERE cid=?",
                (entitlement_cid,),
            ).fetchone()
        if row is None:
            return None
        return {"entitlementCid": entitlement_cid, "namespace": row[0], "cidScope": row[1],
                "quotaUnits": row[2], "consumedUnits": row[3], "unit": row[4],
                "expiresAt": row[5], "settlementCid": row[6]}

    def get_usage(self, usage_cid: str, *, subject: str) -> dict[str, Any] | None:
        """Resolve usage only when it belongs to the authenticated subject."""
        with self._connect() as db:
            row = db.execute(
                "SELECT u.entitlement_cid FROM entitlement_uses u JOIN entitlements e ON e.cid=u.entitlement_cid "
                "WHERE u.usage_cid=? AND e.subject=?", (usage_cid, commitment(subject)),
            ).fetchone()
        return self.artifacts.get(usage_cid) if row else None


class PaidKitService:
    """Transport-neutral paid facade for IPFS add, pin, and retrieval effects."""

    ROUTES = {
        ("POST", "/mcp/tools/storage/add"): "storage/add",
        ("POST", "/mcp/tools/storage/pin"): "storage/pin",
        ("POST", "/mcp/tools/storage/retrieve"): "storage/retrieve",
    }

    def __init__(
        self, config: KitPaymentConfig, state_dir: str | Path, facilitator: Any, *,
        signer: CatalogSigner | None = None, clock_ms: Callable[[], int] | None = None,
        control_mode: str | None = None,
    ) -> None:
        self.config = config
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.clock_ms = clock_ms or (lambda: time.time_ns() // 1_000_000)
        self.signer = signer or CatalogSigner.load_or_create(self.state_dir / "catalog-signing.key")
        self.artifacts = FileCIDArtifactStore(self.state_dir / "artifacts")
        capabilities = []
        for name, terms in config.operations.items():
            requirement = PaymentRequirement(
                config.scheme, config.network, config.asset, terms.amount, config.pay_to,
                extra={"unit": terms.unit, "quotaUnits": terms.quota_units,
                       "retentionSeconds": terms.retention_seconds},
            )
            capabilities.append(PaidCapability(
                f"tool:{name}", (requirement,), metadata={
                    "ability": f"tool:{name}", "namespaces": list(terms.namespaces),
                    "unit": terms.unit, "quotaUnits": terms.quota_units,
                    "maxRequestUnits": terms.max_request_units,
                    "retentionSeconds": terms.retention_seconds,
                    "maxRetentionSeconds": terms.max_retention_seconds,
                    "httpRoute": f"/mcp/tools/{name}", "httpMethod": "POST",
                },
            ))
        catalog = CapabilityCatalog(capabilities, version=config.catalog_version)
        policy = PaymentPolicyEngine(catalog, unlisted=(Decision.FREE if config.unlisted_free else Decision.DENIED))
        self.runtime = SellerRuntime(
            policy, DuckDBPaymentLedger(self.state_dir / "payments.duckdb"), facilitator,
            self.artifacts, seller_did=config.seller_did, descriptor_cid=config.descriptor_cid,
            clock_ms=self.clock_ms,
        )
        self.entitlements = EntitlementStore(self.state_dir / "entitlements.sqlite3", self.artifacts, self.clock_ms)
        self._catalog = self._build_catalog()
        mode = control_mode or ("local-test" if isinstance(facilitator, CallbackFacilitator) else "facilitator")
        self.control_plane = ProfileHControlPlane(
            runtime=self.runtime, catalog=self.catalog, bind=self._commercial_binding,
            reconcile=self.reconcile, evidence=self._control_evidence, mode=mode,
            upstream_x402_http_conformance=mode != "local-test",
        )
        self.profile_h_transports = ProfileHTransportAdapter(self.control_plane)
        self.profile_h_http_app = self.profile_h_transports.http

    def _build_catalog(self) -> dict[str, Any]:
        saved_path = self.state_dir / "signed-catalog.json"
        try:
            saved = json.loads(saved_path.read_text(encoding="utf-8"))
            if (
                isinstance(saved, dict) and CatalogSigner.verify(saved)
                and saved.get("catalogCid") == self.runtime.policy.catalog.cid
                and saved.get("sellerDid") == self.config.seller_did
                and saved.get("descriptorCid") == self.config.descriptor_cid
            ):
                return saved
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        document = {
            "schema": "mcp++/profile-h/kit-catalog@1.0", "createdAt": self.clock_ms(),
            "sellerDid": self.config.seller_did, "descriptorCid": self.config.descriptor_cid,
            **self.runtime.policy.catalog.public_document(),
        }
        signed = self.signer.sign(document)
        signed["signedCatalogCid"] = cid_for(signed)
        # The self-describing response carries its CID outside the signed bytes.
        # Persist exactly the signed document so that the advertised CID resolves.
        self.artifacts.put({key: value for key, value in signed.items() if key != "signedCatalogCid"})
        temporary = saved_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(signed, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(saved_path)
        return signed

    def catalog(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._catalog))

    def _scope(self, operation: str, context: RequestContext, params: Mapping[str, Any]) -> tuple[KitOperationTerms, str, str | None, int]:
        terms = self.config.operations.get(operation)
        if terms is None:
            raise KitPaymentError("H_PAYMENT_POLICY_DENIED", "operation is not in the kit catalog")
        namespace = str(params.get("namespace", context.attributes.get("namespace", "default")))
        allowed_by_identity = tuple(context.attributes.get("namespaces", terms.namespaces))
        if not _NAMESPACE.fullmatch(namespace) or namespace not in terms.namespaces or namespace not in allowed_by_identity:
            raise KitPaymentError("H_PAYMENT_POLICY_DENIED", "namespace access denied")
        cid = params.get("cid")
        if cid is not None:
            cid = str(cid).removeprefix("/ipfs/")
            if not _CID.fullmatch(cid):
                raise KitPaymentError("H_REQUEST_MISMATCH", "invalid or non-canonical CID")
        units = params.get("units", params.get("size_mib", 1))
        if isinstance(units, bool) or not isinstance(units, int) or not 1 <= units <= terms.max_request_units:
            raise KitPaymentError("H_ENTITLEMENT_EXHAUSTED", "request exceeds configured quota bounds")
        retention = params.get("retention_seconds", terms.retention_seconds)
        if isinstance(retention, bool) or not isinstance(retention, int) or not 1 <= retention <= terms.max_retention_seconds:
            raise KitPaymentError("H_ENTITLEMENT_EXHAUSTED", "retention exceeds configured bounds")
        return terms, namespace, cid, units

    def _commercial_binding(self, operation: str, context: RequestContext,
                            params: Mapping[str, Any]) -> CommercialBinding:
        self._scope(operation, context, params)
        clean = RequestContext(context.request_cid, context.idempotency_key, context.authorized,
                               context.policy_allowed, None, context.attributes)
        return CommercialBinding(f"tool:{operation}", clean)

    def _control_evidence(self, kind: str, cid: str, context: RequestContext) -> Mapping[str, Any] | None:
        if kind == "entitlement":
            return self.entitlements.get(cid)
        return self.entitlements.get_usage(
            cid, subject=str(context.attributes.get("subject", "anonymous")),
        )

    async def profile_h(self, method: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Dispatch one complete Profile H control-plane operation."""
        return await self.control_plane.dispatch(method, params)

    async def handle_profile_h_libp2p(self, request: Mapping[str, Any]) -> dict[str, Any]:
        """Route one decoded Profile E frame through the seller authority."""
        return await self.profile_h_transports.libp2p(request)

    async def dispatch(
        self, operation: str, context: RequestContext, params: Mapping[str, Any],
        effect: Callable[[], Any | Awaitable[Any]], *, payment: PaymentContext | None = None,
    ) -> SellerResult:
        terms, namespace, cid_scope, units = self._scope(operation, context, params)
        capability = self.runtime.policy.catalog.resolve(f"tool:{operation}")
        assert capability is not None and capability.capability_cid
        usage_cid: str | None = None

        async def guarded_effect() -> Any:
            value = effect()
            if hasattr(value, "__await__"):
                value = await value
            return value

        # Existing entitlements must be validated by this service, not treated as
        # proof by the shared policy until their scope/quota is atomically consumed.
        runtime_context = RequestContext(
            context.request_cid, context.idempotency_key, context.authorized,
            context.policy_allowed, None, context.attributes,
        )
        if context.entitlement_cid:
            # Entitlements are a domain-owned payment proof. Authorization is
            # still evaluated independently, then quota is atomically fenced by
            # guarded_effect without mutating shared policy (safe concurrently).
            decision = self.runtime.policy.evaluate(f"tool:{operation}", runtime_context)
            if decision.decision in (Decision.DENIED, Decision.UNAVAILABLE):
                return SellerResult(decision)
            paid = PaymentDecision(
                Decision.PAID, decision.operation, "H_PAYMENT_SATISFIED",
                capability, evidence_cid=context.entitlement_cid,
            )
            usage_cid, replayed = self.entitlements.consume_once(
                context.entitlement_cid, subject=str(context.attributes.get("subject", "anonymous")),
                capability_cid=capability.capability_cid, namespace=namespace,
                cid_scope=cid_scope, units=units, idempotency_key=context.idempotency_key,
                request_cid=context.request_cid,
            )
            if replayed:
                return SellerResult(paid, receipt_cid=usage_cid, replayed=True)
            result = SellerResult(paid, value=await guarded_effect(), receipt_cid=context.entitlement_cid)
        else:
            result = await self.runtime.dispatch(f"tool:{operation}", runtime_context, guarded_effect, payment=payment)

        if result.decision.decision == Decision.PAID and result.decision.evidence_cid and not result.replayed and not context.entitlement_cid:
            entitlement_cid = self.entitlements.issue(
                subject=str(context.attributes.get("subject", "anonymous")),
                capability_cid=capability.capability_cid, namespace=namespace, cid_scope=cid_scope,
                quota=terms.quota_units, unit=terms.unit,
                expires_at=self.clock_ms() + terms.retention_seconds * 1000,
                settlement_cid=result.decision.evidence_cid,
            )
            if isinstance(result.value, Mapping):
                value = {**result.value, "entitlementCid": entitlement_cid}
            else:
                value = {"value": result.value, "entitlementCid": entitlement_cid}
            result = SellerResult(result.decision, value, result.quote, result.payment_required,
                                  result.settlement_response, result.receipt_cid, result.replayed)
        elif usage_cid and isinstance(result.value, Mapping):
            result = SellerResult(result.decision, {**result.value, "usageRecordCid": usage_cid},
                                  result.quote, result.payment_required, result.settlement_response,
                                  result.receipt_cid, result.replayed)
        return result

    async def handle_http(
        self, method: str, path: str, context: RequestContext, params: Mapping[str, Any],
        effect: Callable[[], Any | Awaitable[Any]] | None = None, *, payment_header: str | None = None,
    ) -> tuple[int, dict[str, str], Any]:
        if method.upper() == "GET" and path == "/mcp/payments/catalog":
            return 200, {"ETag": self._catalog["signedCatalogCid"]}, self.catalog()
        entitlement_prefix = "/mcp/payments/entitlements/"
        if method.upper() == "GET" and path.startswith(entitlement_prefix):
            if not context.authorized or not context.policy_allowed:
                return 403, {}, {"error": "H_PAYMENT_POLICY_DENIED"}
            entitlement = self.entitlements.get(path.removeprefix(entitlement_prefix))
            return (200, {}, entitlement) if entitlement else (404, {}, {"error": "H_ENTITLEMENT_INVALID"})
        operation = self.ROUTES.get((method.upper(), path))
        if operation is None:
            return 404, {}, {"error": "H_PAYMENT_POLICY_DENIED"}
        if effect is None:
            raise ValueError("a protected HTTP operation requires an effect callback")
        payment = self._decode_payment(payment_header, context) if payment_header else None
        return http_response(await self.dispatch(operation, context, params, effect, payment=payment))

    async def handle_libp2p(
        self, request: Mapping[str, Any], context: RequestContext,
        effect: Callable[[], Any | Awaitable[Any]] | None = None,
    ) -> dict[str, Any]:
        operation = str(request.get("operation", ""))
        if operation == "mcp++/payments/catalog":
            return {"result": self.catalog()}
        if operation == "mcp++/payments/entitlement/get":
            if not context.authorized or not context.policy_allowed:
                return {"error": {"code": "H_PAYMENT_POLICY_DENIED"}}
            entitlement = self.entitlements.get(str(request.get("entitlementCid", "")))
            return {"result": entitlement} if entitlement else {"error": {"code": "H_ENTITLEMENT_INVALID"}}
        params = request.get("params", {})
        if operation not in self.config.operations or not isinstance(params, Mapping) or effect is None:
            return {"error": {"code": "H_PAYMENT_POLICY_DENIED"}}
        raw_payment = request.get("payment_context")
        payment = None
        if isinstance(raw_payment, Mapping):
            payment = PaymentContext(
                raw_payment.get("payload", {}), str(raw_payment.get("quoteCid", "")),
                str(raw_payment.get("requestCid", "")), int(raw_payment.get("requirementIndex", 0)),
            )
        return libp2p_response(await self.dispatch(operation, context, params, effect, payment=payment))

    @staticmethod
    def _decode_payment(value: str, context: RequestContext) -> PaymentContext:
        try:
            data = json.loads(base64.b64decode(value, validate=True))
            return PaymentContext(data["payload"], data["quoteCid"], data["requestCid"], int(data.get("requirementIndex", 0)))
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise KitPaymentError("H_INVALID_PAYMENT_MESSAGE", "invalid PAYMENT-SIGNATURE header") from exc

    async def reconcile(self) -> list[dict[str, Any]]:
        return await self.runtime.reconcile()

    async def diagnostics(self) -> dict[str, Any]:
        result = await self.runtime.diagnostics()
        return {**result, "signedCatalogCid": self._catalog["signedCatalogCid"], "catalogSignatureValid": CatalogSigner.verify(self._catalog)}


__all__ = [
    "CatalogSigner", "EntitlementStore", "KitOperationTerms", "KitPaymentConfig",
    "KitPaymentError", "PaidKitService", "default_operation_terms",
]
