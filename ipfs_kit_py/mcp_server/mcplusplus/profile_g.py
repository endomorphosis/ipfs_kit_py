"""Kit-owned Profile G runtime fencing (RuntimeProfileG@1).

Binds exclusive-execution coordination into the kit MCP server so claim leases,
logical epochs, and fencing tokens reject expired renewals and stale completions
fail-closed. Field names match accelerate's runtime and risk-scheduling.md §6–§9
(MCPP-069); this module must not introduce a forked vocabulary.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from typing import Any, Callable

INTERFACE = "RuntimeProfileG@1"
PROFILE_G_VERSION = "1.0"
PROFILE_G_CAPABILITY = "mcp++/risk-scheduling"
LEASE_CLOCK = "unix-ms-with-logical-epoch"

MIN_LEASE_MS = 5_000
MAX_LEASE_MS = 300_000
SAFE_INTEGER = 9_007_199_254_740_991

# Normative lease / resolution / completion field names (risk-scheduling.md).
NORMATIVE_LEASE_FIELDS: tuple[str, ...] = (
    "task_cid",
    "claim_cid",
    "resolution_cid",
    "claimant_did",
    "logical_epoch",
    "fencing_token",
    "lease_expires_at_ms",
    "state",
)
NORMATIVE_RESOLUTION_FIELDS: tuple[str, ...] = (
    "outcome",
    "logical_epoch",
    "accepted_claim_cid",
    "considered_claim_cids",
    "fencing_token",
    "lease_expires_at_ms",
    "resolver_did",
)
NORMATIVE_COMPLETION_FIELDS: tuple[str, ...] = (
    "task_cid",
    "claim_cid",
    "resolution_cid",
    "fencing_token",
    "output_cid",
    "status",
)

ERROR_NUMBERS: dict[str, int] = {
    "G_INVALID_ARTIFACT": -32602,
    "G_CAPABILITY_NOT_NEGOTIATED": -32040,
    "G_CID_MISMATCH": -32041,
    "G_AUTHORITY_DENIED": -32042,
    "G_POLICY_DENIED": -32043,
    "G_NOT_READY": -32044,
    "G_IDEMPOTENCY_CONFLICT": -32045,
    "G_CLAIM_CONFLICT": -32046,
    "G_LEASE_EXPIRED": -32047,
    "G_STALE_FENCE": -32048,
    "G_QUORUM_UNAVAILABLE": -32049,
    "G_LIMIT_EXCEEDED": -32050,
    "G_PROVIDER_UNAVAILABLE": -32051,
    "G_EVIDENCE_INVALID": -32052,
    "G_REDACTED": -32053,
    "G_NOT_FOUND": -32044,
    "G_COMPLETION_CONFLICT": -32046,
    "G_COORDINATION_UNAVAILABLE": -32049,
}


class ProfileGError(RuntimeError):
    """Stable Profile G coordination failure with a wire error code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        path: str = "",
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path
        self.retryable = retryable
        self.details = dict(details or {})

    def to_error_data(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
        details = dict(self.details)
        if self.path:
            details.setdefault("path", self.path)
        if details:
            payload["details"] = details
        return payload

    def data(self) -> dict[str, Any]:
        """Wire-shaped error body compatible with kit transport mapping."""
        return self.to_error_data()


def _require_int(value: Any, name: str, *, low: int = 0, high: int = SAFE_INTEGER) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ProfileGError("G_INVALID_ARTIFACT", f"invalid integer for {name}", path=f"/{name}")
    return value


def _require_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or "\0" in value:
        raise ProfileGError("G_INVALID_ARTIFACT", f"invalid string for {name}", path=f"/{name}")
    return value


def claim_order_key(claim: Mapping[str, Any]) -> tuple[Any, ...]:
    """Normative conflict order: minimum key wins among same-epoch claims."""
    return (
        -_require_int(claim["logical_epoch"], "logical_epoch", low=1),
        _require_int(claim["risk_bucket"], "risk_bucket"),
        -_require_int(claim["capability_fit_millionths"], "capability_fit_millionths", low=0, high=1_000_000),
        _require_int(claim["expected_finish_ms"], "expected_finish_ms"),
        _require_text(claim["claimant_did"], "claimant_did").encode("utf-8"),
        _require_text(claim["claim_cid"], "claim_cid").encode("utf-8"),
    )


def select_winning_claim(claims: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return the deterministic winner among one or more claim records."""
    if not claims:
        raise ProfileGError("G_NOT_FOUND", "no claims to resolve")
    return dict(min(claims, key=claim_order_key))


def next_fencing_token(logical_epoch: int, prior_fencing_token: int = 0) -> int:
    """Issue the next fencing token for an accepted resolution.

    ``fencing_token' = max(logical_epoch, prior_fencing_token + 1)`` with
    ``prior_fencing_token = 0`` when no prior resolution exists.
    """
    epoch = _require_int(logical_epoch, "logical_epoch", low=1)
    prior = _require_int(prior_fencing_token, "prior_fencing_token", low=0)
    return max(epoch, prior + 1)


def lease_is_live(lease_expires_at_ms: int, now_ms: int) -> bool:
    """Exclusive execution is live only while ``now_ms < lease_expires_at_ms``."""
    return _require_int(now_ms, "now_ms") < _require_int(lease_expires_at_ms, "lease_expires_at_ms")


def lease_is_expired(lease_expires_at_ms: int, now_ms: int) -> bool:
    """Lease is past its renew/takeover bound when ``now_ms > lease_expires_at_ms``."""
    return _require_int(now_ms, "now_ms") > _require_int(lease_expires_at_ms, "lease_expires_at_ms")


def require_lease_renewable(lease_expires_at_ms: int, now_ms: int) -> None:
    """Fail closed on renew-after-expiry with ``G_LEASE_EXPIRED``."""
    if lease_is_expired(lease_expires_at_ms, now_ms):
        raise ProfileGError(
            "G_LEASE_EXPIRED",
            "lease expired; acquire a new claim instead of renewing",
            path="/lease_expires_at_ms",
            details={
                "now_ms": int(now_ms),
                "lease_expires_at_ms": int(lease_expires_at_ms),
            },
        )


def require_current_fence(presented_token: int, current_token: int) -> None:
    """Reject any fencing token that is not exactly the current accepted fence."""
    presented = _require_int(presented_token, "fencing_token", low=1)
    current = _require_int(current_token, "current_fencing_token", low=1)
    if presented != current:
        raise ProfileGError(
            "G_STALE_FENCE",
            "fencing token is stale",
            path="/fencing_token",
            details={"submitted_token": presented, "highest_sink_token": current},
        )


def expected_claim_epoch(latest_terminal_epoch: int = 0) -> int:
    """Next legal logical epoch after the latest terminal/accepted epoch."""
    return _require_int(latest_terminal_epoch, "latest_terminal_epoch", low=0) + 1


def require_claim_epoch(
    *,
    submitted_epoch: int,
    latest_terminal_epoch: int = 0,
    prior_lease_expires_at_ms: int | None = None,
    now_ms: int | None = None,
    prior_epoch_expired: bool = False,
) -> int:
    """Validate epoch admission for first claims and post-expiry takeovers."""
    submitted = _require_int(submitted_epoch, "logical_epoch", low=1)
    expected = expected_claim_epoch(latest_terminal_epoch)
    if submitted != expected:
        raise ProfileGError(
            "G_INVALID_ARTIFACT",
            "logical epoch jump is not allowed",
            path="/logical_epoch",
            details={
                "latest_terminal_epoch": int(latest_terminal_epoch),
                "submitted_epoch": submitted,
                "expected_epoch": expected,
            },
        )
    if submitted == 1:
        return submitted
    if not prior_epoch_expired:
        raise ProfileGError(
            "G_CLAIM_CONFLICT",
            "takeover requires an explicit prior-epoch expiry record",
            path="/logical_epoch",
        )
    if (
        prior_lease_expires_at_ms is not None
        and now_ms is not None
        and not lease_is_expired(prior_lease_expires_at_ms, now_ms)
    ):
        raise ProfileGError(
            "G_CLAIM_CONFLICT",
            "takeover before prior lease expiry",
            path="/logical_epoch",
            details={
                "prior_lease_expires_at_ms": int(prior_lease_expires_at_ms),
                "now_ms": int(now_ms),
            },
        )
    return submitted


def require_completion_authority(
    *,
    claim_cid: str,
    fencing_token: int,
    accepted_claim_cid: str,
    current_fencing_token: int,
    lease_expires_at_ms: int,
    now_ms: int,
) -> None:
    """Authorize exclusive completion under the current lease and fencing token.

    Expired leases and lower fencing tokens fail with ``G_STALE_FENCE``. A claim
    mismatch (or a non-current higher fence) fails with ``G_CLAIM_CONFLICT``.
    """
    claim = _require_text(claim_cid, "claim_cid")
    accepted = _require_text(accepted_claim_cid, "accepted_claim_cid")
    presented = _require_int(fencing_token, "fencing_token", low=1)
    current = _require_int(current_fencing_token, "current_fencing_token", low=1)

    if not lease_is_live(lease_expires_at_ms, now_ms):
        raise ProfileGError(
            "G_STALE_FENCE",
            "expired lease cannot complete",
            path="/lease_expires_at_ms",
            details={
                "now_ms": int(now_ms),
                "lease_expires_at_ms": int(lease_expires_at_ms),
                "submitted_token": presented,
                "highest_sink_token": current,
            },
        )
    if presented < current:
        raise ProfileGError(
            "G_STALE_FENCE",
            "fencing token is stale",
            path="/fencing_token",
            details={"submitted_token": presented, "highest_sink_token": current},
        )
    if claim != accepted or presented != current:
        raise ProfileGError(
            "G_CLAIM_CONFLICT",
            "completion claim or fence does not match the accepted resolution",
            path="/claim_cid",
            details={
                "submitted_claim_cid": claim,
                "accepted_claim_cid": accepted,
                "submitted_token": presented,
                "highest_sink_token": current,
            },
        )


def resolve_claims(
    claims: Sequence[Mapping[str, Any]],
    *,
    logical_epoch: int,
    prior_fencing_token: int = 0,
    now_ms: int,
    requested_lease_ms: int | None = None,
    resolver_did: str = "did:web:resolver.example",
) -> dict[str, Any]:
    """Select the winner and materialize accepted resolution fence/lease fields."""
    winner = select_winning_claim(claims)
    epoch = _require_int(logical_epoch, "logical_epoch", low=1)
    if int(winner["logical_epoch"]) != epoch:
        raise ProfileGError("G_INVALID_ARTIFACT", "claims span mixed logical epochs")
    if requested_lease_ms is None:
        lease_ms = _require_int(
            winner.get("requested_lease_ms", MIN_LEASE_MS),
            "requested_lease_ms",
            low=MIN_LEASE_MS,
            high=MAX_LEASE_MS,
        )
    else:
        lease_ms = _require_int(requested_lease_ms, "requested_lease_ms", low=MIN_LEASE_MS, high=MAX_LEASE_MS)
    now = _require_int(now_ms, "now_ms")
    fence = next_fencing_token(epoch, prior_fencing_token)
    return {
        "outcome": "accepted",
        "logical_epoch": epoch,
        "accepted_claim_cid": winner["claim_cid"],
        "considered_claim_cids": sorted(str(item["claim_cid"]) for item in claims),
        "fencing_token": fence,
        "lease_expires_at_ms": now + lease_ms,
        "resolver_did": _require_text(resolver_did, "resolver_did"),
        "winner": dict(winner),
    }


@dataclass(frozen=True, slots=True)
class AcceptedLease:
    """Materialized exclusive lease from an accepted ClaimResolution."""

    task_cid: str
    claim_cid: str
    resolution_cid: str
    claimant_did: str
    logical_epoch: int
    fencing_token: int
    lease_expires_at_ms: int
    state: str = "accepted"

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_cid": self.task_cid,
            "claim_cid": self.claim_cid,
            "resolution_cid": self.resolution_cid,
            "claimant_did": self.claimant_did,
            "logical_epoch": self.logical_epoch,
            "fencing_token": self.fencing_token,
            "lease_expires_at_ms": self.lease_expires_at_ms,
            "state": self.state,
        }


class ClaimLeaseCoordinator:
    """In-process claim/lease/epoch/fence index for exclusive task execution.

    Peers and durable stores rebuild equivalent state from the Event DAG; this
    helper enforces the same fail-closed rules for renew, release, expire, and
    completion on the kit side.
    """

    def __init__(self, *, clock_ms: Callable[[], int] | None = None) -> None:
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self._lock = threading.RLock()
        self._leases: MutableMapping[str, AcceptedLease] = {}
        self._expiry_epochs: set[tuple[str, int]] = set()
        self._completions: MutableMapping[str, dict[str, Any]] = {}

    def _now(self, now_ms: int | None) -> int:
        return self._clock_ms() if now_ms is None else _require_int(now_ms, "now_ms")

    def get_lease(self, task_cid: str) -> AcceptedLease | None:
        with self._lock:
            return self._leases.get(task_cid)

    def accept_resolution(
        self,
        *,
        task_cid: str,
        claim_cid: str,
        resolution_cid: str,
        claimant_did: str,
        logical_epoch: int,
        fencing_token: int,
        lease_expires_at_ms: int,
        prior_fencing_token: int | None = None,
        now_ms: int | None = None,
    ) -> AcceptedLease:
        """Record an accepted resolution as the current exclusive lease."""
        task = _require_text(task_cid, "task_cid")
        claim = _require_text(claim_cid, "claim_cid")
        resolution = _require_text(resolution_cid, "resolution_cid")
        claimant = _require_text(claimant_did, "claimant_did")
        epoch = _require_int(logical_epoch, "logical_epoch", low=1)
        fence = _require_int(fencing_token, "fencing_token", low=1)
        expires = _require_int(lease_expires_at_ms, "lease_expires_at_ms")
        now = self._now(now_ms)

        with self._lock:
            prior = self._leases.get(task)
            if prior is not None and prior.logical_epoch >= epoch and prior.state in {
                "accepted",
                "completed",
            }:
                return prior
            prior_token = (
                int(prior.fencing_token)
                if prior is not None
                else (0 if prior_fencing_token is None else int(prior_fencing_token))
            )
            expected_fence = next_fencing_token(epoch, prior_token)
            if fence != expected_fence:
                raise ProfileGError(
                    "G_INVALID_ARTIFACT",
                    "fencing token is not the next legal token",
                    path="/fencing_token",
                    details={"submitted": fence, "expected": expected_fence},
                )
            if (
                prior is not None
                and prior.state == "accepted"
                and lease_is_live(prior.lease_expires_at_ms, now)
            ):
                raise ProfileGError(
                    "G_CLAIM_CONFLICT",
                    "cannot accept a higher epoch while a live lease exists",
                    path="/logical_epoch",
                )
            latest_terminal = prior.logical_epoch if prior is not None else 0
            require_claim_epoch(
                submitted_epoch=epoch,
                latest_terminal_epoch=latest_terminal,
                prior_lease_expires_at_ms=(
                    None if prior is None else prior.lease_expires_at_ms
                ),
                now_ms=now,
                prior_epoch_expired=(
                    latest_terminal == 0
                    or (task, latest_terminal) in self._expiry_epochs
                    or (prior is not None and prior.state in {"expired", "released"})
                ),
            )
            lease = AcceptedLease(
                task_cid=task,
                claim_cid=claim,
                resolution_cid=resolution,
                claimant_did=claimant,
                logical_epoch=epoch,
                fencing_token=fence,
                lease_expires_at_ms=expires,
                state="accepted",
            )
            self._leases[task] = lease
            return lease

    def renew(
        self,
        *,
        task_cid: str,
        claim_cid: str,
        fencing_token: int,
        requested_lease_ms: int,
        claimant_did: str | None = None,
        now_ms: int | None = None,
    ) -> AcceptedLease:
        """Extend an unexpired current lease; expired leases raise G_LEASE_EXPIRED."""
        task = _require_text(task_cid, "task_cid")
        claim = _require_text(claim_cid, "claim_cid")
        token = _require_int(fencing_token, "fencing_token", low=1)
        duration = _require_int(requested_lease_ms, "requested_lease_ms", low=MIN_LEASE_MS, high=MAX_LEASE_MS)
        now = self._now(now_ms)

        with self._lock:
            lease = self._leases.get(task)
            if lease is None or lease.state != "accepted":
                raise ProfileGError("G_NOT_FOUND", "no active lease to renew")
            require_lease_renewable(lease.lease_expires_at_ms, now)
            require_current_fence(token, lease.fencing_token)
            if lease.claim_cid != claim:
                raise ProfileGError("G_CLAIM_CONFLICT", "claim is not the accepted lease holder")
            if claimant_did is not None and lease.claimant_did != claimant_did:
                raise ProfileGError("G_CLAIM_CONFLICT", "claimant is not the lease holder")
            renewed = AcceptedLease(
                task_cid=lease.task_cid,
                claim_cid=lease.claim_cid,
                resolution_cid=lease.resolution_cid,
                claimant_did=lease.claimant_did,
                logical_epoch=lease.logical_epoch,
                fencing_token=lease.fencing_token,
                lease_expires_at_ms=now + duration,
                state="accepted",
            )
            self._leases[task] = renewed
            return renewed

    def release(
        self,
        *,
        task_cid: str,
        claim_cid: str,
        fencing_token: int,
        now_ms: int | None = None,
    ) -> AcceptedLease:
        """End a live lease without completion."""
        task = _require_text(task_cid, "task_cid")
        claim = _require_text(claim_cid, "claim_cid")
        token = _require_int(fencing_token, "fencing_token", low=1)
        now = self._now(now_ms)

        with self._lock:
            lease = self._leases.get(task)
            if lease is None or lease.state != "accepted":
                raise ProfileGError("G_NOT_FOUND", "no active lease to release")
            require_current_fence(token, lease.fencing_token)
            if lease.claim_cid != claim:
                raise ProfileGError("G_CLAIM_CONFLICT", "claim is not the accepted lease holder")
            released = AcceptedLease(
                task_cid=lease.task_cid,
                claim_cid=lease.claim_cid,
                resolution_cid=lease.resolution_cid,
                claimant_did=lease.claimant_did,
                logical_epoch=lease.logical_epoch,
                fencing_token=lease.fencing_token,
                lease_expires_at_ms=min(lease.lease_expires_at_ms, now),
                state="released",
            )
            self._leases[task] = released
            self._expiry_epochs.add((task, lease.logical_epoch))
            return released

    def expire(self, task_cid: str, *, now_ms: int | None = None) -> AcceptedLease:
        """Mark a past-due lease expired so a higher epoch can be claimed."""
        task = _require_text(task_cid, "task_cid")
        now = self._now(now_ms)

        with self._lock:
            lease = self._leases.get(task)
            if lease is None or lease.state not in {"accepted", "expired"}:
                raise ProfileGError("G_NOT_FOUND", "no lease to expire")
            if lease.state == "expired":
                return lease
            if not lease_is_expired(lease.lease_expires_at_ms, now):
                raise ProfileGError(
                    "G_CLAIM_CONFLICT",
                    "lease has not expired",
                    details={
                        "now_ms": now,
                        "lease_expires_at_ms": lease.lease_expires_at_ms,
                    },
                )
            expired = AcceptedLease(
                task_cid=lease.task_cid,
                claim_cid=lease.claim_cid,
                resolution_cid=lease.resolution_cid,
                claimant_did=lease.claimant_did,
                logical_epoch=lease.logical_epoch,
                fencing_token=lease.fencing_token,
                lease_expires_at_ms=lease.lease_expires_at_ms,
                state="expired",
            )
            self._leases[task] = expired
            self._expiry_epochs.add((task, lease.logical_epoch))
            return expired

    def authorize_completion(
        self,
        *,
        task_cid: str,
        claim_cid: str,
        fencing_token: int,
        now_ms: int | None = None,
        output_cid: str | None = None,
    ) -> AcceptedLease:
        """Validate completion against the current lease and fence; reject stale writers."""
        task = _require_text(task_cid, "task_cid")
        claim = _require_text(claim_cid, "claim_cid")
        token = _require_int(fencing_token, "fencing_token", low=1)
        now = self._now(now_ms)

        with self._lock:
            lease = self._leases.get(task)
            if lease is None or lease.state not in {"accepted", "completed"}:
                raise ProfileGError("G_NOT_FOUND", "no accepted resolution")
            prior = self._completions.get(task)
            if prior is not None:
                if prior.get("claim_cid") == claim and (
                    output_cid is None or prior.get("output_cid") == output_cid
                ):
                    return lease
                raise ProfileGError(
                    "G_COMPLETION_CONFLICT",
                    "task already has a successful completion",
                    details={"existing": prior},
                )
            require_completion_authority(
                claim_cid=claim,
                fencing_token=token,
                accepted_claim_cid=lease.claim_cid,
                current_fencing_token=lease.fencing_token,
                lease_expires_at_ms=lease.lease_expires_at_ms,
                now_ms=now,
            )
            completed = AcceptedLease(
                task_cid=lease.task_cid,
                claim_cid=lease.claim_cid,
                resolution_cid=lease.resolution_cid,
                claimant_did=lease.claimant_did,
                logical_epoch=lease.logical_epoch,
                fencing_token=lease.fencing_token,
                lease_expires_at_ms=lease.lease_expires_at_ms,
                state="completed",
            )
            self._leases[task] = completed
            if output_cid is not None:
                self._completions[task] = {
                    "claim_cid": claim,
                    "fencing_token": token,
                    "output_cid": _require_text(output_cid, "output_cid"),
                }
            return completed

    def resolve_and_accept(
        self,
        claims: Sequence[Mapping[str, Any]],
        *,
        task_cid: str,
        resolution_cid: str,
        logical_epoch: int,
        now_ms: int | None = None,
        requested_lease_ms: int | None = None,
        resolver_did: str = "did:web:resolver.example",
    ) -> tuple[AcceptedLease, dict[str, Any]]:
        """Run conflict order, issue fence/lease, and record the accepted lease."""
        now = self._now(now_ms)
        with self._lock:
            prior = self._leases.get(task_cid)
            prior_token = prior.fencing_token if prior is not None else 0
            fragment = resolve_claims(
                claims,
                logical_epoch=logical_epoch,
                prior_fencing_token=prior_token,
                now_ms=now,
                requested_lease_ms=requested_lease_ms,
                resolver_did=resolver_did,
            )
            winner = fragment["winner"]
            lease = self.accept_resolution(
                task_cid=task_cid,
                claim_cid=fragment["accepted_claim_cid"],
                resolution_cid=resolution_cid,
                claimant_did=str(winner["claimant_did"]),
                logical_epoch=fragment["logical_epoch"],
                fencing_token=fragment["fencing_token"],
                lease_expires_at_ms=fragment["lease_expires_at_ms"],
                now_ms=now,
            )
            return lease, fragment

    def status(self, task_cid: str, *, now_ms: int | None = None) -> dict[str, Any]:
        """Return a schedule/status-compatible snapshot for one task."""
        now = self._now(now_ms)
        with self._lock:
            lease = self._leases.get(task_cid)
            if lease is None:
                return {
                    "task_cid": task_cid,
                    "state": "ready",
                    "resolution_cid": None,
                    "fencing_token": None,
                    "logical_epoch": 0,
                    "lease_expires_at_ms": None,
                }
            state = lease.state
            if state == "accepted" and lease_is_expired(lease.lease_expires_at_ms, now):
                state = "expired"
            return {
                "task_cid": task_cid,
                "state": "leased" if state == "accepted" else state,
                "resolution_cid": lease.resolution_cid,
                "fencing_token": lease.fencing_token,
                "logical_epoch": lease.logical_epoch,
                "lease_expires_at_ms": lease.lease_expires_at_ms,
                "claim_cid": lease.claim_cid,
                "claimant_did": lease.claimant_did,
            }


class RuntimeProfileG:
    """RuntimeProfileG@1: kit fencing surface shared with accelerate semantics."""

    interface = INTERFACE
    version = PROFILE_G_VERSION
    capability = PROFILE_G_CAPABILITY

    def __init__(self, *, clock_ms: Callable[[], int] | None = None, provider: str = "ipfs_kit_py") -> None:
        self.provider = provider
        self.coordinator = ClaimLeaseCoordinator(clock_ms=clock_ms)

    def metadata(self) -> dict[str, Any]:
        return {
            "interface": INTERFACE,
            "version": PROFILE_G_VERSION,
            "capability": PROFILE_G_CAPABILITY,
            "provider": self.provider,
            "lease_clock": LEASE_CLOCK,
            "normative_lease_fields": list(NORMATIVE_LEASE_FIELDS),
            "normative_resolution_fields": list(NORMATIVE_RESOLUTION_FIELDS),
            "normative_completion_fields": list(NORMATIVE_COMPLETION_FIELDS),
            "error_numbers": dict(ERROR_NUMBERS),
        }

    def resolve_and_accept(
        self,
        claims: Sequence[Mapping[str, Any]],
        *,
        task_cid: str,
        resolution_cid: str,
        logical_epoch: int,
        now_ms: int | None = None,
        requested_lease_ms: int | None = None,
        resolver_did: str = "did:web:resolver.example",
    ) -> tuple[AcceptedLease, dict[str, Any]]:
        return self.coordinator.resolve_and_accept(
            claims,
            task_cid=task_cid,
            resolution_cid=resolution_cid,
            logical_epoch=logical_epoch,
            now_ms=now_ms,
            requested_lease_ms=requested_lease_ms,
            resolver_did=resolver_did,
        )

    def publish_completion(
        self,
        *,
        task_cid: str,
        claim_cid: str,
        fencing_token: int,
        output_cid: str,
        now_ms: int | None = None,
    ) -> dict[str, Any]:
        """Publish a fenced completion receipt fragment; deny stale fences."""
        lease = self.coordinator.authorize_completion(
            task_cid=task_cid,
            claim_cid=claim_cid,
            fencing_token=fencing_token,
            now_ms=now_ms,
            output_cid=output_cid,
        )
        return {
            "task_cid": lease.task_cid,
            "claim_cid": lease.claim_cid,
            "resolution_cid": lease.resolution_cid,
            "fencing_token": lease.fencing_token,
            "output_cid": output_cid,
            "status": "succeeded",
            "state": lease.state,
            "provider": self.provider,
            "provider_version": PROFILE_G_VERSION,
        }

    def authorize_completion(
        self,
        *,
        task_cid: str,
        claim_cid: str,
        fencing_token: int,
        now_ms: int | None = None,
        output_cid: str | None = None,
    ) -> AcceptedLease:
        return self.coordinator.authorize_completion(
            task_cid=task_cid,
            claim_cid=claim_cid,
            fencing_token=fencing_token,
            now_ms=now_ms,
            output_cid=output_cid,
        )

    def renew(self, **kwargs: Any) -> AcceptedLease:
        return self.coordinator.renew(**kwargs)

    def release(self, **kwargs: Any) -> AcceptedLease:
        return self.coordinator.release(**kwargs)

    def expire(self, task_cid: str, *, now_ms: int | None = None) -> AcceptedLease:
        return self.coordinator.expire(task_cid, now_ms=now_ms)

    def status(self, task_cid: str, *, now_ms: int | None = None) -> dict[str, Any]:
        return self.coordinator.status(task_cid, now_ms=now_ms)

    def dispatch(self, method: str, params: Mapping[str, Any]) -> Any:
        """Handle fencing-critical schedule methods when no external provider is bound."""
        if not isinstance(params, Mapping):
            raise ProfileGError("G_INVALID_ARTIFACT", "params must be an object")
        if method == "mcp++/risk/profile":
            return self.metadata()
        if method == "mcp++/schedule/status":
            task_cid = _require_text(params.get("task_cid"), "task_cid")
            return self.status(task_cid, now_ms=params.get("now_ms"))
        if method == "mcp++/schedule/resolve":
            claims = params.get("claims")
            if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes)):
                raise ProfileGError("G_INVALID_ARTIFACT", "claims must be an array", path="/claims")
            lease, fragment = self.resolve_and_accept(
                list(claims),
                task_cid=_require_text(params.get("task_cid"), "task_cid"),
                resolution_cid=_require_text(params.get("resolution_cid"), "resolution_cid"),
                logical_epoch=_require_int(params.get("logical_epoch"), "logical_epoch", low=1),
                now_ms=params.get("now_ms"),
                requested_lease_ms=params.get("requested_lease_ms"),
                resolver_did=str(params.get("resolver_did") or "did:web:resolver.example"),
            )
            result = dict(fragment)
            result["lease"] = lease.to_dict()
            return result
        if method == "mcp++/schedule/renew":
            lease = self.renew(
                task_cid=_require_text(params.get("task_cid"), "task_cid"),
                claim_cid=_require_text(params.get("claim_cid"), "claim_cid"),
                fencing_token=_require_int(params.get("fencing_token"), "fencing_token", low=1),
                requested_lease_ms=_require_int(
                    params.get("requested_lease_ms", MIN_LEASE_MS),
                    "requested_lease_ms",
                    low=MIN_LEASE_MS,
                    high=MAX_LEASE_MS,
                ),
                claimant_did=params.get("claimant_did"),
                now_ms=params.get("now_ms"),
            )
            return lease.to_dict()
        if method == "mcp++/schedule/release":
            lease = self.release(
                task_cid=_require_text(params.get("task_cid"), "task_cid"),
                claim_cid=_require_text(params.get("claim_cid"), "claim_cid"),
                fencing_token=_require_int(params.get("fencing_token"), "fencing_token", low=1),
                now_ms=params.get("now_ms"),
            )
            return lease.to_dict()
        if method == "mcp++/schedule/reconcile":
            # Completion attempts ride reconcile when publishing a fenced receipt.
            if params.get("action") in {None, "complete", "publish_completion"}:
                return self.publish_completion(
                    task_cid=_require_text(params.get("task_cid"), "task_cid"),
                    claim_cid=_require_text(params.get("claim_cid"), "claim_cid"),
                    fencing_token=_require_int(params.get("fencing_token"), "fencing_token", low=1),
                    output_cid=_require_text(params.get("output_cid"), "output_cid"),
                    now_ms=params.get("now_ms"),
                )
            raise ProfileGError(
                "G_INVALID_ARTIFACT",
                "unsupported reconcile action",
                path="/action",
                details={"action": params.get("action")},
            )
        raise ProfileGError(
            "G_PROVIDER_UNAVAILABLE",
            "Profile G method requires an external provider",
            retryable=True,
            details={"method": method},
        )


_LOCK = threading.Lock()
_RUNTIME: RuntimeProfileG | None = None


def get_runtime() -> RuntimeProfileG:
    """Process-wide RuntimeProfileG@1 singleton used by kit transport binding."""
    global _RUNTIME
    if _RUNTIME is None:
        with _LOCK:
            if _RUNTIME is None:
                _RUNTIME = RuntimeProfileG()
    return _RUNTIME


def configure_runtime(runtime: RuntimeProfileG) -> None:
    """Replace the process-wide runtime (tests and custom deployments)."""
    global _RUNTIME
    with _LOCK:
        _RUNTIME = runtime


def reject_expired_lease(lease_expires_at_ms: int, now_ms: int) -> None:
    """Unit-test-facing alias: renew path rejects expired leases."""
    require_lease_renewable(lease_expires_at_ms, now_ms)


def reject_stale_fencing_token(presented_token: int, current_token: int) -> None:
    """Unit-test-facing alias: completion path rejects stale fencing tokens."""
    require_current_fence(presented_token, current_token)


__all__ = [
    "AcceptedLease",
    "ClaimLeaseCoordinator",
    "ERROR_NUMBERS",
    "INTERFACE",
    "LEASE_CLOCK",
    "MAX_LEASE_MS",
    "MIN_LEASE_MS",
    "NORMATIVE_COMPLETION_FIELDS",
    "NORMATIVE_LEASE_FIELDS",
    "NORMATIVE_RESOLUTION_FIELDS",
    "PROFILE_G_CAPABILITY",
    "PROFILE_G_VERSION",
    "ProfileGError",
    "RuntimeProfileG",
    "claim_order_key",
    "configure_runtime",
    "expected_claim_epoch",
    "get_runtime",
    "lease_is_expired",
    "lease_is_live",
    "next_fencing_token",
    "reject_expired_lease",
    "reject_stale_fencing_token",
    "require_claim_epoch",
    "require_completion_authority",
    "require_current_fence",
    "require_lease_renewable",
    "resolve_claims",
    "select_winning_claim",
]
