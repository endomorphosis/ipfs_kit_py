"""Fail-closed provider adapter classifications.

This module is deliberately a *classification and promotion boundary*, not a
collection of SDK wrappers.  The backend inventory includes a number of old
configuration shapes and provider names.  An installed client library, an MCP
tool, or a hermetic fixture is not evidence that one of those names is a
canonical storage adapter.  The only path to a runtime here is an explicitly
registered canonical factory plus a current provider receipt.

The module performs no network I/O and never resolves a credential reference.
It retains only the names of accepted credential fields, so a configuration,
exception, status record, or receipt cannot accidentally disclose a secret or
even a secret-reference value.
"""

from __future__ import annotations

import json
import re
import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Final

from ..core.operation_contracts import (
    ErrorCategory,
    ErrorCode,
    OperationState,
    Retryability,
    StorageError,
)
from .spec import (
    BACKEND_SPECS,
    BackendCapability,
    BackendSpec,
    BackendSupportTier,
    get_backend_spec,
)


RECEIPT_SCHEMA: Final[str] = "ipfs-kit-provider-receipt/v1"
_SECRET_REF_RE: Final[re.Pattern[str]] = re.compile(
    r"^secretref:(?:secure-config|enhanced-secrets|credential-manager|environment):"
    r"[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$"
)
_IROH_CREDENTIAL_REF_RE: Final[re.Pattern[str]] = re.compile(
    r"^credential://iroh/[a-z0-9][a-z0-9._-]{0,255}$"
)
_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)
_IDEMPOTENCY_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$"
)
_SENSITIVE_KEY_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:secret|token|password|private[_-]?key|api[_-]?key|access[_-]?key|"
    r"authorization|credential|bearer)",
    re.IGNORECASE,
)


class ProviderAvailability(str, Enum):
    """Explicit disposition for one inventory entry."""

    RUNTIME_READY = "runtime-ready"
    CONFIGURATION_ONLY = "configuration-only"
    UNSUPPORTED = "unsupported"
    RECEIPT_REQUIRED = "receipt-required"
    CANONICAL_ADAPTER_MISSING = "canonical-adapter-missing"


class ProviderOperation(str, Enum):
    """The storage operations a provider receipt is allowed to attest."""

    HEALTH = "health"
    PUT = "put"
    GET = "get"
    STREAM = "stream"
    READ_RANGE = "read_range"
    LIST = "list"
    GET_METADATA = "get_metadata"
    SET_METADATA = "set_metadata"
    DELETE = "delete"


_MUTATING_OPERATIONS: Final[frozenset[ProviderOperation]] = frozenset(
    {ProviderOperation.PUT, ProviderOperation.SET_METADATA, ProviderOperation.DELETE}
)
_RECEIPT_OPERATIONS: Final[frozenset[str]] = frozenset(
    operation.value for operation in ProviderOperation
)


class ProviderAdapterError(RuntimeError):
    """Typed, secret-safe failure projected from a canonical ``StorageError``."""

    def __init__(self, error: StorageError) -> None:
        self.error = error
        super().__init__(error.message)


class ConfigurationOnlyProviderError(ProviderAdapterError):
    """A configured inventory entry has no declared storage runtime."""


class UnsupportedProviderError(ProviderAdapterError):
    """An excluded inventory entry has no implementation contract."""


class ProviderReceiptRequiredError(ProviderAdapterError):
    """A conditional or production entry lacks current provider evidence."""


class CanonicalAdapterMissingError(ProviderAdapterError):
    """A receipt exists but no explicitly registered canonical adapter exists."""


class ProviderReceiptError(ValueError):
    """Receipt parsing error with a deliberately non-diagnostic public message."""


def _raise_error(
    error_type: type[ProviderAdapterError],
    *,
    code: ErrorCode,
    category: ErrorCategory,
    state: OperationState,
    retryability: Retryability,
    message: str,
) -> None:
    raise error_type(
        StorageError(
            code=code,
            category=category,
            state=state,
            retryability=retryability,
            message=message,
        )
    )


@dataclass(frozen=True, repr=False)
class SecretReference:
    """Validated secret-reference authority with its target intentionally omitted."""

    authority: str

    def __repr__(self) -> str:
        return "SecretReference(<redacted>)"


def parse_authorized_secret_reference(value: object) -> SecretReference:
    """Accept only repository-approved reference schemes, never raw credentials."""

    if not isinstance(value, str):
        _raise_error(
            ProviderAdapterError,
            code=ErrorCode.SECRET_MATERIAL,
            category=ErrorCategory.VALIDATION,
            state=OperationState.REJECTED,
            retryability=Retryability.NEVER,
            message="credential material must be supplied by an authorized secret reference",
        )
    match = _SECRET_REF_RE.fullmatch(value)
    if match:
        return SecretReference(authority=value.split(":", 2)[1])
    if _IROH_CREDENTIAL_REF_RE.fullmatch(value):
        return SecretReference(authority="iroh")
    _raise_error(
        ProviderAdapterError,
        code=ErrorCode.SECRET_MATERIAL,
        category=ErrorCategory.VALIDATION,
        state=OperationState.REJECTED,
        retryability=Retryability.NEVER,
        message="credential material must be supplied by an authorized secret reference",
    )


def _is_sensitive_key(key: str) -> bool:
    return bool(_SENSITIVE_KEY_RE.search(key))


@dataclass(frozen=True)
class ProviderConfiguration:
    """A secret-free configuration summary suitable for status and factories."""

    public_values: Mapping[str, Any]
    credential_fields: tuple[str, ...] = ()

    def as_runtime_values(self) -> Mapping[str, Any]:
        """Return only non-secret configuration; secret references are never forwarded."""

        return dict(self.public_values)


def validate_provider_configuration(
    spec: BackendSpec, configuration: Mapping[str, Any] | None = None
) -> ProviderConfiguration:
    """Validate config while stripping all credential-reference values.

    Known credential keys must use ``<field>_ref`` and one of the approved
    reference syntaxes.  The resulting object remembers only which credential
    fields were requested, never their values.
    """

    if configuration is None:
        return ProviderConfiguration(public_values={})
    if not isinstance(configuration, Mapping):
        _raise_error(
            ProviderAdapterError,
            code=ErrorCode.INVALID_REQUEST,
            category=ErrorCategory.VALIDATION,
            state=OperationState.REJECTED,
            retryability=Retryability.NEVER,
            message="provider configuration must be a mapping",
        )

    allowed = frozenset(spec.secret_fields)
    seen: set[str] = set()

    def reject_secret() -> None:
        _raise_error(
            ProviderAdapterError,
            code=ErrorCode.SECRET_MATERIAL,
            category=ErrorCategory.VALIDATION,
            state=OperationState.REJECTED,
            retryability=Retryability.NEVER,
            message="credential material must be supplied by an authorized secret reference",
        )

    def clean(value: Any, *, credentials_scope: bool = False) -> Any:
        if isinstance(value, Mapping):
            public: dict[str, Any] = {}
            for raw_key, item in value.items():
                if not isinstance(raw_key, str):
                    _raise_error(
                        ProviderAdapterError,
                        code=ErrorCode.INVALID_REQUEST,
                        category=ErrorCategory.VALIDATION,
                        state=OperationState.REJECTED,
                        retryability=Retryability.NEVER,
                        message="provider configuration keys must be strings",
                    )
                key = raw_key.lower().replace("-", "_")
                if key == "credentials":
                    if not isinstance(item, Mapping):
                        reject_secret()
                    clean(item, credentials_scope=True)
                    continue
                if key.endswith("_ref"):
                    field_name = key[:-4]
                    if field_name not in allowed:
                        reject_secret()
                    parse_authorized_secret_reference(item)
                    seen.add(field_name)
                    continue
                if credentials_scope or _is_sensitive_key(key):
                    reject_secret()
                public[raw_key] = clean(item)
            return public
        if isinstance(value, list):
            return [clean(item) for item in value]
        if isinstance(value, tuple):
            return tuple(clean(item) for item in value)
        return value

    public_values = clean(configuration)
    return ProviderConfiguration(
        public_values=public_values,
        credential_fields=tuple(sorted(seen)),
    )


@dataclass(frozen=True)
class ProviderOperationSemantics:
    """Bounded request policy, separate from any live provider claim."""

    timeout_seconds: int = 30
    max_retries: int = 2
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    idempotency_required_for: frozenset[ProviderOperation] = field(
        default_factory=lambda: _MUTATING_OPERATIONS
    )
    consistency: str = "unverified"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.timeout_seconds, int)
            or self.timeout_seconds <= 0
            or self.timeout_seconds > 86_400
        ):
            raise ValueError("timeout_seconds must be a bounded positive integer")
        if not isinstance(self.max_retries, int) or not 0 <= self.max_retries <= 20:
            raise ValueError("max_retries must be between zero and twenty")
        if not isinstance(self.rate_limit_requests, int) or not 1 <= self.rate_limit_requests <= 100_000:
            raise ValueError("rate_limit_requests must be a bounded positive integer")
        if (
            not isinstance(self.rate_limit_window_seconds, int)
            or not 1 <= self.rate_limit_window_seconds <= 86_400
        ):
            raise ValueError("rate_limit_window_seconds must be a bounded positive integer")
        if self.consistency not in {"unverified", "eventual", "read-your-writes", "strong"}:
            raise ValueError("consistency is not a recognized provider consistency model")


@dataclass(frozen=True)
class ProviderRequest:
    """A preflighted request with no payload, endpoint, or credentials."""

    operation: ProviderOperation
    timeout_seconds: int
    retry_attempt: int
    idempotency_key_present: bool


class ProviderRequestGate:
    """Deterministic local admission for timeout, retry, idempotency, and rate limits."""

    def __init__(
        self,
        semantics: ProviderOperationSemantics,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.semantics = semantics
        self._clock = clock
        self._attempts: deque[float] = deque()

    @staticmethod
    def _operation(value: ProviderOperation | str) -> ProviderOperation:
        try:
            return value if isinstance(value, ProviderOperation) else ProviderOperation(value)
        except (TypeError, ValueError):
            _raise_error(
                ProviderAdapterError,
                code=ErrorCode.INVALID_REQUEST,
                category=ErrorCategory.VALIDATION,
                state=OperationState.REJECTED,
                retryability=Retryability.NEVER,
                message="provider operation is not declared by the contract",
            )

    def prepare(
        self,
        operation: ProviderOperation | str,
        *,
        timeout_seconds: int | None = None,
        retry_attempt: int = 0,
        idempotency_key: str | None = None,
    ) -> ProviderRequest:
        selected = self._operation(operation)
        timeout = self.semantics.timeout_seconds if timeout_seconds is None else timeout_seconds
        if not isinstance(timeout, int) or timeout <= 0:
            _raise_error(
                ProviderAdapterError,
                code=ErrorCode.INVALID_REQUEST,
                category=ErrorCategory.VALIDATION,
                state=OperationState.REJECTED,
                retryability=Retryability.NEVER,
                message="provider timeout must be a positive integer",
            )
        if timeout > self.semantics.timeout_seconds:
            _raise_error(
                ProviderAdapterError,
                code=ErrorCode.DEADLINE_EXCEEDED,
                category=ErrorCategory.TIMEOUT,
                state=OperationState.DEADLINE_EXCEEDED,
                retryability=Retryability.IDEMPOTENT_SAFE,
                message="provider timeout exceeds the declared operation bound",
            )
        if not isinstance(retry_attempt, int) or retry_attempt < 0:
            _raise_error(
                ProviderAdapterError,
                code=ErrorCode.INVALID_REQUEST,
                category=ErrorCategory.VALIDATION,
                state=OperationState.REJECTED,
                retryability=Retryability.NEVER,
                message="provider retry attempt must be a non-negative integer",
            )
        if retry_attempt > self.semantics.max_retries:
            _raise_error(
                ProviderAdapterError,
                code=ErrorCode.UNAVAILABLE,
                category=ErrorCategory.UNAVAILABLE,
                state=OperationState.UNAVAILABLE,
                retryability=Retryability.NEVER,
                message="provider retry budget is exhausted",
            )
        key_is_valid = isinstance(idempotency_key, str) and bool(
            _IDEMPOTENCY_KEY_RE.fullmatch(idempotency_key)
        )
        if selected in self.semantics.idempotency_required_for and not key_is_valid:
            _raise_error(
                ProviderAdapterError,
                code=ErrorCode.PRECONDITION_FAILED,
                category=ErrorCategory.PRECONDITION,
                state=OperationState.PRECONDITION_FAILED,
                retryability=Retryability.NEVER,
                message="provider mutation requires a bounded idempotency key",
            )
        now = self._clock()
        cutoff = now - self.semantics.rate_limit_window_seconds
        while self._attempts and self._attempts[0] <= cutoff:
            self._attempts.popleft()
        if len(self._attempts) >= self.semantics.rate_limit_requests:
            _raise_error(
                ProviderAdapterError,
                code=ErrorCode.BACKPRESSURE,
                category=ErrorCategory.BACKPRESSURE,
                state=OperationState.BACKPRESSURE,
                retryability=Retryability.IDEMPOTENT_SAFE,
                message="provider request rate limit is exhausted",
            )
        self._attempts.append(now)
        return ProviderRequest(
            operation=selected,
            timeout_seconds=timeout,
            retry_attempt=retry_attempt,
            idempotency_key_present=key_is_valid,
        )


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ProviderReceiptError("provider receipt is malformed")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProviderReceiptError("provider receipt is malformed") from exc
    if parsed.tzinfo is None:
        raise ProviderReceiptError("provider receipt is malformed")
    return parsed.astimezone(timezone.utc)


def _receipt_has_sensitive_key(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            isinstance(key, str)
            and (_is_sensitive_key(key) or _receipt_has_sensitive_key(item))
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_receipt_has_sensitive_key(item) for item in value)
    return False


@dataclass(frozen=True)
class ProviderReceipt:
    """Current, bounded, credential-free provider evidence."""

    receipt_id: str
    provider_type: str
    issued_at: datetime
    expires_at: datetime
    runtime_factory: str
    tested_operations: frozenset[ProviderOperation]
    semantics: ProviderOperationSemantics

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any], *, now: datetime | None = None
    ) -> "ProviderReceipt":
        if not isinstance(value, Mapping) or _receipt_has_sensitive_key(value):
            raise ProviderReceiptError("provider receipt is malformed")
        required = {
            "schema",
            "receipt_id",
            "provider_type",
            "issued_at",
            "expires_at",
            "runtime_factory",
            "tested_operations",
            "rate_limit",
            "timeout_seconds",
            "retry",
            "idempotency",
            "consistency",
        }
        if set(value) != required or value.get("schema") != RECEIPT_SCHEMA:
            raise ProviderReceiptError("provider receipt is malformed")
        provider_type = value["provider_type"]
        receipt_id = value["receipt_id"]
        runtime_factory = value["runtime_factory"]
        if not all(
            isinstance(item, str) and _IDENTIFIER_RE.fullmatch(item)
            for item in (provider_type, receipt_id, runtime_factory)
        ):
            raise ProviderReceiptError("provider receipt is malformed")
        spec = get_backend_spec(provider_type)
        if spec is None or spec.runtime_factory != runtime_factory:
            raise ProviderReceiptError("provider receipt does not match the backend inventory")
        issued_at = _parse_timestamp(value["issued_at"])
        expires_at = _parse_timestamp(value["expires_at"])
        reference_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if issued_at > reference_time or expires_at <= reference_time or expires_at <= issued_at:
            raise ProviderReceiptError("provider receipt is not current")
        operations = value["tested_operations"]
        if (
            not isinstance(operations, list)
            or not operations
            or any(not isinstance(item, str) or item not in _RECEIPT_OPERATIONS for item in operations)
            or not _RECEIPT_OPERATIONS.issubset(operations)
        ):
            raise ProviderReceiptError("provider receipt is malformed")
        rate_limit = value["rate_limit"]
        retry = value["retry"]
        idempotency = value["idempotency"]
        consistency = value["consistency"]
        if (
            not isinstance(rate_limit, Mapping)
            or set(rate_limit) != {"max_requests", "window_seconds"}
            or not isinstance(retry, Mapping)
            or set(retry) != {"max_attempts", "retryable_codes"}
            or not isinstance(idempotency, Mapping)
            or set(idempotency) != {"required_for_mutations"}
            or not isinstance(consistency, Mapping)
            or set(consistency) != {"model", "verified"}
            or idempotency["required_for_mutations"] is not True
            or consistency["verified"] is not True
            or consistency["model"] not in {"eventual", "read-your-writes", "strong"}
            or not isinstance(retry["retryable_codes"], list)
            or not all(item in {code.value for code in ErrorCode} for item in retry["retryable_codes"])
        ):
            raise ProviderReceiptError("provider receipt is malformed")
        try:
            semantics = ProviderOperationSemantics(
                timeout_seconds=value["timeout_seconds"],
                max_retries=retry["max_attempts"],
                rate_limit_requests=rate_limit["max_requests"],
                rate_limit_window_seconds=rate_limit["window_seconds"],
                consistency=consistency["model"],
            )
        except (TypeError, ValueError) as exc:
            raise ProviderReceiptError("provider receipt is malformed") from exc
        return cls(
            receipt_id=receipt_id,
            provider_type=provider_type,
            issued_at=issued_at,
            expires_at=expires_at,
            runtime_factory=runtime_factory,
            tested_operations=frozenset(ProviderOperation(item) for item in operations),
            semantics=semantics,
        )


def load_provider_receipt(path: str | Path, *, now: datetime | None = None) -> ProviderReceipt:
    """Load one local receipt document without exposing its contents on failure."""

    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ProviderReceiptError("provider receipt is unreadable") from exc
    return ProviderReceipt.from_mapping(loaded, now=now)


@dataclass(frozen=True)
class ProviderRuntimeRequest:
    """Secret-free data supplied to an explicitly registered canonical factory."""

    provider_type: str
    receipt_id: str
    configuration: Mapping[str, Any]
    credential_fields: tuple[str, ...]
    semantics: ProviderOperationSemantics


@dataclass(frozen=True)
class CanonicalRuntimeFactory:
    """An explicit bridge to a repository-owned canonical runtime adapter."""

    provider_type: str
    adapter_id: str
    create: Callable[[ProviderRuntimeRequest], Any]

    def __post_init__(self) -> None:
        if not _IDENTIFIER_RE.fullmatch(self.provider_type) or not _IDENTIFIER_RE.fullmatch(
            self.adapter_id
        ):
            raise ValueError("canonical runtime factory identifiers are malformed")
        if not callable(self.create):
            raise TypeError("canonical runtime factory create must be callable")


@dataclass(frozen=True)
class ProviderStatus:
    provider_type: str
    availability: ProviderAvailability
    health_contract: str
    supports_storage: bool
    receipt_id: str | None = None
    reason: str = ""


class ProviderBackendAdapter:
    """Base type for a classified inventory entry; never an SDK/client wrapper."""

    # This object is a canonical *classification* boundary, not a provider
    # runtime.  Keeping the runtime marker false prevents callers from treating
    # the catalog itself as a usable adapter.
    is_canonical_provider_adapter: Final[bool] = False
    is_provider_classification_adapter: Final[bool] = True
    is_hermetic: Final[bool] = False
    live_provider: Final[bool] = False

    def __init__(
        self,
        spec: BackendSpec,
        configuration: ProviderConfiguration,
        *,
        availability: ProviderAvailability,
        semantics: ProviderOperationSemantics | None = None,
        receipt: ProviderReceipt | None = None,
        factory: CanonicalRuntimeFactory | None = None,
    ) -> None:
        self.spec = spec
        self.configuration = configuration
        self.availability = availability
        self.semantics = semantics or ProviderOperationSemantics()
        self.receipt = receipt
        self.factory = factory
        self.request_gate = ProviderRequestGate(self.semantics)

    @property
    def provider_type(self) -> str:
        return self.spec.type_name

    @property
    def supports_storage(self) -> bool:
        return self.availability == ProviderAvailability.RUNTIME_READY

    def status(self) -> ProviderStatus:
        reason = {
            ProviderAvailability.CONFIGURATION_ONLY: "configuration-only inventory entry; storage is not declared",
            ProviderAvailability.UNSUPPORTED: "unsupported inventory entry; no runtime is declared",
            ProviderAvailability.RECEIPT_REQUIRED: "current provider receipt is required before runtime promotion",
            ProviderAvailability.CANONICAL_ADAPTER_MISSING: "current receipt exists but no canonical runtime adapter is registered",
            ProviderAvailability.RUNTIME_READY: "current provider receipt and canonical runtime adapter are registered",
        }[self.availability]
        return ProviderStatus(
            provider_type=self.provider_type,
            availability=self.availability,
            health_contract=self.spec.health_contract,
            supports_storage=self.supports_storage,
            receipt_id=self.receipt.receipt_id if self.receipt else None,
            reason=reason,
        )

    def prepare_operation(self, operation: ProviderOperation | str, **kwargs: Any) -> ProviderRequest:
        """Apply request semantics without claiming that a provider call occurred."""

        return self.request_gate.prepare(operation, **kwargs)

    def require_storage(self, operation: ProviderOperation | str, **kwargs: Any) -> ProviderRequest:
        """Preflight a storage operation, or return a typed non-runtime result."""

        if self.availability == ProviderAvailability.CONFIGURATION_ONLY:
            _raise_error(
                ConfigurationOnlyProviderError,
                code=ErrorCode.UNSUPPORTED,
                category=ErrorCategory.UNSUPPORTED,
                state=OperationState.UNSUPPORTED,
                retryability=Retryability.NEVER,
                message="provider is configuration-only and cannot advertise storage",
            )
        if self.availability == ProviderAvailability.UNSUPPORTED:
            _raise_error(
                UnsupportedProviderError,
                code=ErrorCode.UNSUPPORTED,
                category=ErrorCategory.UNSUPPORTED,
                state=OperationState.UNSUPPORTED,
                retryability=Retryability.NEVER,
                message="provider is unsupported and has no storage runtime",
            )
        if self.availability == ProviderAvailability.RECEIPT_REQUIRED:
            _raise_error(
                ProviderReceiptRequiredError,
                code=ErrorCode.CAPABILITY_MISSING,
                category=ErrorCategory.CAPABILITY,
                state=OperationState.UNAVAILABLE,
                retryability=Retryability.NEVER,
                message="provider runtime requires a current provider receipt",
            )
        if self.availability == ProviderAvailability.CANONICAL_ADAPTER_MISSING:
            _raise_error(
                CanonicalAdapterMissingError,
                code=ErrorCode.CAPABILITY_MISSING,
                category=ErrorCategory.CAPABILITY,
                state=OperationState.UNAVAILABLE,
                retryability=Retryability.NEVER,
                message="provider runtime requires a registered canonical adapter",
            )
        return self.prepare_operation(operation, **kwargs)

    def create_runtime(self) -> Any:
        """Create only an explicitly registered, receipt-gated canonical adapter."""

        self.require_storage(ProviderOperation.HEALTH)
        if self.receipt is None or self.factory is None:
            _raise_error(
                CanonicalAdapterMissingError,
                code=ErrorCode.CAPABILITY_MISSING,
                category=ErrorCategory.CAPABILITY,
                state=OperationState.UNAVAILABLE,
                retryability=Retryability.NEVER,
                message="provider runtime requires a registered canonical adapter",
            )
        runtime = self.factory.create(
            ProviderRuntimeRequest(
                provider_type=self.provider_type,
                receipt_id=self.receipt.receipt_id,
                configuration=self.configuration.as_runtime_values(),
                credential_fields=self.configuration.credential_fields,
                semantics=self.semantics,
            )
        )
        if (
            not getattr(runtime, "is_canonical_provider_adapter", False)
            or getattr(runtime, "provider_type", None) != self.provider_type
        ):
            _raise_error(
                CanonicalAdapterMissingError,
                code=ErrorCode.CAPABILITY_MISSING,
                category=ErrorCategory.CAPABILITY,
                state=OperationState.UNAVAILABLE,
                retryability=Retryability.NEVER,
                message="registered runtime did not identify as the expected canonical adapter",
            )
        return runtime


class ProviderAdapterCatalog:
    """Resolve every declared backend type into a typed, fail-closed adapter."""

    def __init__(
        self,
        *,
        receipts: Mapping[str, ProviderReceipt | Mapping[str, Any]] | None = None,
        runtime_factories: Mapping[str, CanonicalRuntimeFactory] | None = None,
        now: datetime | None = None,
    ) -> None:
        reference_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        self._receipts: dict[str, ProviderReceipt] = {}
        for supplied_name, supplied_receipt in (receipts or {}).items():
            spec = get_backend_spec(supplied_name)
            if spec is None:
                raise ProviderReceiptError("provider receipt does not match the backend inventory")
            receipt = (
                supplied_receipt
                if isinstance(supplied_receipt, ProviderReceipt)
                else ProviderReceipt.from_mapping(supplied_receipt, now=reference_time)
            )
            if receipt.provider_type != spec.type_name:
                raise ProviderReceiptError("provider receipt does not match the backend inventory")
            if not (receipt.issued_at <= reference_time < receipt.expires_at):
                raise ProviderReceiptError("provider receipt is not current")
            self._receipts[spec.type_name] = receipt
        self._factories = dict(runtime_factories or {})
        for provider_type, factory in self._factories.items():
            spec = get_backend_spec(provider_type)
            if (
                spec is None
                or not isinstance(factory, CanonicalRuntimeFactory)
                or factory.provider_type != spec.type_name
            ):
                raise ValueError("canonical runtime factory does not match the backend inventory")

    def resolve(
        self, type_name: str, *, configuration: Mapping[str, Any] | None = None
    ) -> ProviderBackendAdapter:
        spec = get_backend_spec(type_name)
        if spec is None:
            _raise_error(
                UnsupportedProviderError,
                code=ErrorCode.UNSUPPORTED,
                category=ErrorCategory.UNSUPPORTED,
                state=OperationState.UNSUPPORTED,
                retryability=Retryability.NEVER,
                message="provider type is not present in the backend inventory",
            )
        configured = validate_provider_configuration(spec, configuration)
        has_runtime_contract = spec.supports(BackendCapability.RUNTIME_FACTORY) and spec.supports(
            BackendCapability.STORAGE
        )
        if spec.is_excluded or spec.support_tier == BackendSupportTier.UNSUPPORTED:
            return ProviderBackendAdapter(
                spec,
                configured,
                availability=ProviderAvailability.UNSUPPORTED,
            )
        if not has_runtime_contract or spec.support_tier == BackendSupportTier.CONFIGURATION_ONLY:
            # Receipt data cannot promote registry-only entries such as Estuary.
            return ProviderBackendAdapter(
                spec,
                configured,
                availability=ProviderAvailability.CONFIGURATION_ONLY,
            )
        receipt = self._receipts.get(spec.type_name)
        if receipt is None:
            return ProviderBackendAdapter(
                spec,
                configured,
                availability=ProviderAvailability.RECEIPT_REQUIRED,
            )
        factory = self._factories.get(spec.type_name)
        if factory is None:
            return ProviderBackendAdapter(
                spec,
                configured,
                availability=ProviderAvailability.CANONICAL_ADAPTER_MISSING,
                semantics=receipt.semantics,
                receipt=receipt,
            )
        return ProviderBackendAdapter(
            spec,
            configured,
            availability=ProviderAvailability.RUNTIME_READY,
            semantics=receipt.semantics,
            receipt=receipt,
            factory=factory,
        )

    def inventory(
        self, *, configuration: Mapping[str, Mapping[str, Any]] | None = None
    ) -> Mapping[str, ProviderBackendAdapter]:
        supplied = configuration or {}
        return {
            type_name: self.resolve(type_name, configuration=supplied.get(type_name))
            for type_name in sorted(BACKEND_SPECS)
        }


def provider_adapter_for(
    type_name: str,
    *,
    configuration: Mapping[str, Any] | None = None,
    receipts: Mapping[str, ProviderReceipt | Mapping[str, Any]] | None = None,
    runtime_factories: Mapping[str, CanonicalRuntimeFactory] | None = None,
    now: datetime | None = None,
) -> ProviderBackendAdapter:
    """Convenience resolver for callers that only need one provider type."""

    return ProviderAdapterCatalog(
        receipts=receipts, runtime_factories=runtime_factories, now=now
    ).resolve(type_name, configuration=configuration)


__all__ = [
    "CanonicalAdapterMissingError",
    "CanonicalRuntimeFactory",
    "ConfigurationOnlyProviderError",
    "ProviderAdapterCatalog",
    "ProviderAdapterError",
    "ProviderAvailability",
    "ProviderBackendAdapter",
    "ProviderConfiguration",
    "ProviderOperation",
    "ProviderOperationSemantics",
    "ProviderReceipt",
    "ProviderReceiptError",
    "ProviderReceiptRequiredError",
    "ProviderRequest",
    "ProviderRequestGate",
    "ProviderRuntimeRequest",
    "ProviderStatus",
    "SecretReference",
    "UnsupportedProviderError",
    "load_provider_receipt",
    "parse_authorized_secret_reference",
    "provider_adapter_for",
    "validate_provider_configuration",
]
