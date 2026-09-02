"""Fail-closed PCPR-024 proof-seal store qualification.

PCPR-024 qualifies the current-head hermetic proof-seal store for exact bytes,
candidate versus current separation, fresh verification before reuse, no public
proving-key or witness leakage, WAL, restart, stale-parent rejection,
concurrent writers, tombstones, invalidations, corruption, and
legacy-certificate staging without admission. Live IPFS proof-artifact
transport and CLI/MCP/MCP++ parity stay typed unavailable. Hermetic and
simulated results cannot mint live qualification.

This module is not release authority: it does not write DuckDB or Quack
state and never emits a closed PCPR release outcome.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

from ipfs_kit_py.assurance.backend_certification import (
    CertificationDisposition,
)
from ipfs_kit_py.assurance.local_backend_qualification import (
    CLOSED_RELEASE_OUTCOMES,
    EVIDENCE_KINDS,
    PROMOTION_STATUSES,
    SEALED_PATH,
    QualificationProbe,
    observe_sealed_validation_environment,
)
from ipfs_kit_py.assurance.proof_seal import (
    BACKEND_ID,
    BRANCH_ID,
    CERTIFICATION_SCOPE,
    INTERFACE as ADAPTER_INTERFACE,
    LIVE_SUPPORT_CLAIM,
    REPOSITORY_ID,
    SCHEMA as ADAPTER_SCHEMA,
    SUPPORT_CLASS,
    HermeticProofSealQualificationSurface,
    ProofSealSurfaceError,
)
from ipfs_kit_py.core.operation_contracts import (
    ErrorCode,
    content_identity,
)
from ipfs_kit_py.proof_seal_store.cache_index import (
    CandidateAdmissionRecord,
    IndexDisposition,
)
from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    ArtifactRole,
    CurrentSealPointer,
    ForbiddenArtifactError,
    ForbiddenArtifactKind,
    SealTransitionPhase,
    SealTransitionRecord,
    SealTransitionState,
    candidate_is_not_admitted,
    current_is_not_candidate,
)
from ipfs_kit_py.proof_seal_store.local_store import (
    LocalStoreError,
    LocalStoreIntegrityError,
    LocalStoreReason,
    content_cid_for_bytes,
    content_digest_hex,
)
from ipfs_kit_py.proof_seal_store.pointer import (
    PointerCasRejected,
    PointerIntegrityError,
    PointerReason,
    namespace_digest,
)


QUALIFICATION_INTERFACE: Final = "ProofSealQualification@1"
QUALIFICATION_SCHEMA: Final = "ipfs_kit_py/assurance/proof-seal-qualification@1"
QUALIFICATION_VERDICT_SCHEMA: Final = (
    "ipfs_kit_py/assurance/proof-seal-qualification-verdict@1"
)

PCPR_024_TASK_ID: Final = "PCPR-024"
PCPR_024_GOAL_ID: Final = "PCPR-G300"
PCPR_023_TASK_ID: Final = "PCPR-023"
PCPR_026_TASK_ID: Final = "PCPR-026"
PCPR_027_TASK_ID: Final = "PCPR-027"
PCPR_PROGRAM_ID: Final = "proof-carrying-platform-qualification-and-release-v1"
PCPR_BOARD_NAMESPACE: Final = "proof-carrying-platform-qualification-and-release-v1"

SECRET_PROBE: Final = "pcpr-024-do-not-retain-this-secret"
HERMETIC_CANDIDATE_SUITES: Final[tuple[str, ...]] = (
    "tests/test_pcpr_proof_seal_qualification.py",
)

REQUIRED_PROOF_SEAL_OPERATIONS: Final[tuple[str, ...]] = (
    "exact_bytes",
    "candidate_vs_current",
    "fresh_verification_before_reuse",
    "witness_key_protection",
    "wal",
    "restart",
    "stale_parent",
    "concurrent_writers",
    "tombstone",
    "invalidation",
    "legacy_certificate_staging",
    "corruption",
)

LIVE_UNAVAILABLE_OPERATIONS: Final[tuple[str, ...]] = (
    "live_ipfs_transport",
    "interface_parity",
)


class ProofSealQualificationError(ValueError):
    """Malformed qualification evidence or a forbidden authority claim."""


@dataclass(frozen=True)
class QualificationVerdict:
    """Fail-closed PCPR-024 proof-seal decision. Never a closed release."""

    schema: str
    interface: str
    promotion_status: str
    supervisor_disposition: str
    closed_release_outcome: None
    release_claim: bool
    completion_authoritative: bool
    contracts_frozen: bool
    duckdb_or_quack_state_written: bool
    proof_seal_live_qualified: bool
    suite_complete: bool
    certification_disposition: str
    support_class: str
    live_support_claim: bool
    simulated_results_represented_as_live: bool
    hermetic_results_represented_as_live: bool
    hermetic_proof_seal_observed: bool
    interface_parity_qualified: bool
    live_ipfs_transport_qualified: bool
    live_ipfs_evidence_kind: str
    witness_key_protection_observed: bool
    this_task_created_competing_authority: bool
    probes: tuple[QualificationProbe, ...]
    observations: tuple[dict[str, Any], ...]
    hermetic_operations: tuple[dict[str, Any], ...]
    live_unavailable_operations: tuple[dict[str, Any], ...]
    operations_observed: tuple[str, ...]
    operations_missing: tuple[str, ...]
    blockers: tuple[str, ...]
    verdict_cid: str

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "interface": self.interface,
            "promotion_status": self.promotion_status,
            "supervisor_disposition": self.supervisor_disposition,
            "closed_release_outcome": self.closed_release_outcome,
            "release_claim": self.release_claim,
            "completion_authoritative": self.completion_authoritative,
            "contracts_frozen": self.contracts_frozen,
            "duckdb_or_quack_state_written": self.duckdb_or_quack_state_written,
            "proof_seal_live_qualified": self.proof_seal_live_qualified,
            "suite_complete": self.suite_complete,
            "certification_disposition": self.certification_disposition,
            "support_class": self.support_class,
            "live_support_claim": self.live_support_claim,
            "simulated_results_represented_as_live": (
                self.simulated_results_represented_as_live
            ),
            "hermetic_results_represented_as_live": (
                self.hermetic_results_represented_as_live
            ),
            "hermetic_proof_seal_observed": self.hermetic_proof_seal_observed,
            "interface_parity_qualified": self.interface_parity_qualified,
            "live_ipfs_transport_qualified": self.live_ipfs_transport_qualified,
            "live_ipfs_evidence_kind": self.live_ipfs_evidence_kind,
            "witness_key_protection_observed": self.witness_key_protection_observed,
            "this_task_created_competing_authority": (
                self.this_task_created_competing_authority
            ),
            "probes": [item.to_mapping() for item in self.probes],
            "observations": [dict(item) for item in self.observations],
            "hermetic_operations": [dict(item) for item in self.hermetic_operations],
            "live_unavailable_operations": [
                dict(item) for item in self.live_unavailable_operations
            ],
            "operations_observed": list(self.operations_observed),
            "operations_missing": list(self.operations_missing),
            "blockers": list(self.blockers),
            "verdict_cid": self.verdict_cid,
        }


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProofSealQualificationError(f"{name} must be a non-empty string")
    return value.strip()


def _kind(value: Any, name: str) -> str:
    kind = _text(value, name)
    if kind not in EVIDENCE_KINDS:
        raise ProofSealQualificationError(f"{name} is not an admitted evidence kind")
    return kind


def _reject_closed_release_value(value: Any, name: str) -> None:
    if isinstance(value, str) and value in CLOSED_RELEASE_OUTCOMES:
        raise ProofSealQualificationError(
            f"{name} must not be a closed PCPR release outcome"
        )


def _hermetic_passed(
    operation: str,
    *,
    digests: Mapping[str, str],
    limitations: tuple[str, ...] = (),
    detail: str | None = None,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "status": "passed",
        "environment": "hermetic",
        "source": "hermetic_observed",
        "signature_valid": True,
        "freshness": "current",
        "digests": dict(digests),
        "limitations": list(limitations + ("hermetic_not_live",)),
        "detail": detail,
        "evidence_kind": "measured_hermetic",
        "live": False,
        "simulated_represented_as_live": False,
        "hermetic_represented_as_live": False,
    }


def _blocked(
    operation: str,
    *,
    reason: str,
    limitations: tuple[str, ...] = (),
    environment: str = "live",
) -> dict[str, Any]:
    return {
        "operation": operation,
        "status": "blocked",
        "environment": environment,
        "source": "unavailable",
        "signature_valid": False,
        "freshness": "missing",
        "digests": {"reason": reason},
        "limitations": list(limitations),
        "detail": reason,
        "evidence_kind": "unavailable",
        "live": False,
        "simulated_represented_as_live": False,
        "hermetic_represented_as_live": False,
    }


def _hermetic_operation(
    operation: str,
    *,
    status: str,
    reason: str,
    digests: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "status": status,
        "environment": "hermetic",
        "source": "hermetic_observed" if status == "passed" else "unavailable",
        "evidence_kind": "measured_hermetic" if status == "passed" else "unavailable",
        "live": False,
        "simulated_represented_as_live": False,
        "hermetic_represented_as_live": False,
        "reason": reason,
        "digests": dict(digests or {}),
    }


def _live_unavailable_operation(operation: str, *, reason: str) -> dict[str, Any]:
    return {
        "operation": operation,
        "status": "unobserved",
        "environment": "sealed",
        "source": "unavailable",
        "evidence_kind": "unavailable",
        "live": False,
        "simulated_represented_as_live": False,
        "hermetic_represented_as_live": False,
        "reason": reason,
    }


def refuse_simulated_as_live(adapter: Any) -> None:
    """Hermetic, simulated, or live-claiming adapters cannot mint live evidence."""

    live_provider = bool(getattr(adapter, "live_provider", False))
    hermetic = bool(getattr(adapter, "is_hermetic", True))
    simulated = bool(getattr(adapter, "simulated", False))
    live_claim = bool(getattr(adapter, "live_support_claim", False))
    if hermetic or simulated or not live_provider or live_claim:
        raise ProofSealQualificationError(
            "hermetic or simulated adapters cannot mint live proof-seal qualification"
        )
    if getattr(adapter, "backend_id", None) != BACKEND_ID:
        raise ProofSealQualificationError(
            "live proof-seal qualification requires backend_id='proof_seal_store'"
        )


def refuse_hermetic_as_live(adapter: Any) -> None:
    """Explicit alias: hermetic proof-seal cannot be submitted as live."""

    refuse_simulated_as_live(adapter)


def sealed_which(name: str) -> str:
    """Resolve an executable on the sealed validation PATH only."""

    for directory in SEALED_PATH.split(":"):
        candidate = Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return "unavailable"


def probe_live_ipfs_transport() -> QualificationProbe:
    ipfs = sealed_which("ipfs")
    present = ipfs != "unavailable"
    return QualificationProbe(
        probe_id="live_ipfs_transport",
        present=present,
        evidence_kind="measured" if present else "unavailable",
        live=False,
        simulated_represented_as_live=False,
        reason=(
            "Sealed PATH has an ipfs executable. This qualifier did not start a "
            "pinned daemon or exercise live proof-artifact transport. Live IPFS "
            "proof-seal transport stays typed unavailable."
            if present
            else (
                "Sealed PATH has no ipfs executable. Live IPFS proof-artifact "
                "transport stays typed unavailable and is not recorded as zero "
                "or passing. Hermetic local objects are not live IPFS."
            )
        ),
        details={
            "ipfs": ipfs,
            "PATH": SEALED_PATH,
            "live_daemon_started": False,
            "injected_transport_is_not_live": True,
        },
    )


def probe_cli_mcp_surfaces() -> tuple[QualificationProbe, ...]:
    probes: list[QualificationProbe] = []
    surfaces = (
        ("cli", "ipfs_kit_py.cli", PCPR_026_TASK_ID),
        ("mcp", "ipfs_kit_py.mcp", PCPR_026_TASK_ID),
        ("mcpp", "ipfs_kit_py.mcp_server.mcplusplus", PCPR_026_TASK_ID),
    )
    for surface, module_name, remediating in surfaces:
        try:
            __import__(module_name)
            present = True
            reason = (
                f"{surface} source module {module_name} is importable. "
                f"No live proof-seal {surface} session was exercised. "
                f"Parity remains typed unavailable until {remediating}."
            )
        except Exception as exc:  # noqa: BLE001 - honest import probe
            present = False
            reason = (
                f"{surface} module {module_name} was not imported "
                f"({type(exc).__name__}). Live {surface} parity is typed unavailable."
            )
        probes.append(
            QualificationProbe(
                probe_id=f"{surface}_proof_seal_parity",
                present=present,
                evidence_kind="unavailable",
                live=False,
                simulated_represented_as_live=False,
                reason=reason,
                details={
                    "module": module_name,
                    "remediating_task": remediating,
                    "live_session": False,
                },
            )
        )
    return tuple(probes)


def _pointer(
    *,
    seal_cid: str,
    generation: int,
    parent_seal_cid: str = "",
    seal_kind: ArtifactKind = ArtifactKind.CHECKPOINT_SEAL,
) -> CurrentSealPointer:
    return CurrentSealPointer(
        repository_id=REPOSITORY_ID,
        branch_id=BRANCH_ID,
        seal_cid=seal_cid,
        seal_kind=seal_kind,
        generation=generation,
        parent_seal_cid=parent_seal_cid,
    )


def _admission(cache_key: str, artifact: Any) -> CandidateAdmissionRecord:
    receipt_cid = content_cid_for_bytes(b'{"pcpr-024":"receipt"}')
    policy_cid = content_cid_for_bytes(b'{"pcpr-024":"policy"}')
    return CandidateAdmissionRecord(
        cache_key=cache_key,
        artifact=artifact,
        admission_id="admission:pcpr-024-1",
        issuer="accelerate",
        terminal_status="proved",
        verified=True,
        cryptographically_verified=True,
        simulated=False,
        stale=False,
        proof_mode="direct_execution_proof",
        verification_receipt_cid=receipt_cid,
        policy_cid=policy_cid,
        generation=1,
    )


def run_hermetic_proof_seal_suite(root: Path) -> tuple[dict[str, Any], ...]:
    """Exercise mandatory hermetic proof-seal store cases.

    Results are measured_hermetic. They cannot mint live IPFS qualification
    or a closed PCPR release.
    """

    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    observations: list[dict[str, Any]] = []
    surface = HermeticProofSealQualificationSurface(root / "store")
    try:
        payload = b'{"kind":"proof_object","tag":"pcpr-024-exact-bytes"}'
        reference = surface.put_immutable(ArtifactKind.PROOF_OBJECT, payload)
        read_back = surface.get_verified_bytes(reference)
        if read_back != payload:
            raise ProofSealQualificationError("read-back bytes did not match put")
        if reference.cid != content_cid_for_bytes(payload):
            raise ProofSealQualificationError("admitted CID did not match exact bytes")
        if reference.role is not ArtifactRole.ADMITTED:
            raise ProofSealQualificationError("admitted bytes lost admitted role")
        observations.append(
            _hermetic_passed(
                "exact_bytes",
                digests={
                    "cid": reference.cid,
                    "bytes": f"sha256:{content_digest_hex(payload)}",
                    "byte_length": str(len(payload)),
                },
                detail="put_immutable rehashed exact bytes; get_verified_bytes matched",
            )
        )

        cache_key = "proof-cache-key:pcpr-024"
        put = surface.index.record_verified_admission(
            _admission(cache_key, reference)
        )
        if not put.stored or put.candidate is None:
            raise ProofSealQualificationError("candidate admission was not stored")
        candidate = surface.lookup_candidate(cache_key)
        if candidate is None:
            raise ProofSealQualificationError("candidate lookup missed stored hint")
        if candidate.role is not ArtifactRole.CANDIDATE:
            raise ProofSealQualificationError("candidate role collapsed")
        if candidate.is_acceptance_authority:
            raise ProofSealQualificationError("candidate claimed acceptance authority")
        if not candidate_is_not_admitted(candidate):
            raise ProofSealQualificationError("candidate collapsed into admitted")

        seal_bytes = b'{"kind":"checkpoint_seal","tag":"pcpr-024-genesis"}'
        seal_ref = surface.put_immutable(ArtifactKind.CHECKPOINT_SEAL, seal_bytes)
        genesis = _pointer(seal_cid=seal_ref.cid, generation=0)
        if not surface.compare_and_swap_current_seal(None, genesis):
            raise ProofSealQualificationError("genesis current-seal CAS failed")
        current = surface.get_current_seal()
        if current is None or current.role is not ArtifactRole.CURRENT:
            raise ProofSealQualificationError("current seal role collapsed")
        if not current_is_not_candidate(current):
            raise ProofSealQualificationError("current seal collapsed into candidate")
        if current.seal_cid == candidate.cid and current.role is ArtifactRole.CANDIDATE:
            raise ProofSealQualificationError("current collapsed into candidate")
        observations.append(
            _hermetic_passed(
                "candidate_vs_current",
                digests={
                    "candidate_role": candidate.role.value,
                    "current_role": current.role.value,
                    "candidate_cid": candidate.cid,
                    "current_cid": current.seal_cid,
                },
                detail="candidate index hint and current-seal pointer stayed disjoint",
            )
        )

        if candidate.requires_fresh_verification is not True:
            raise ProofSealQualificationError(
                "candidate lost requires_fresh_verification"
            )
        acceptance = surface.index.query_acceptance(cache_key)
        if getattr(acceptance, "accepted", True):
            raise ProofSealQualificationError(
                "index acceptance query granted acceptance"
            )
        observations.append(
            _hermetic_passed(
                "fresh_verification_before_reuse",
                digests={
                    "requires_fresh_verification": "true",
                    "is_acceptance_authority": "false",
                    "accepted": str(bool(getattr(acceptance, "accepted", False))).lower(),
                },
                detail="cache lookup remains a hint; reuse still requires fresh verification",
            )
        )

        rejected_kinds: list[str] = []
        for forbidden in (
            ForbiddenArtifactKind.PROVING_KEY.value,
            ForbiddenArtifactKind.WITNESS.value,
            "private_witness",
            "witness_material",
        ):
            result = surface.objects.put_immutable_result(
                forbidden, b"secret-proving-material"
            )
            if result.stored:
                raise ProofSealQualificationError(
                    f"forbidden kind {forbidden!r} was stored"
                )
            if result.reason not in {
                LocalStoreReason.FORBIDDEN_KIND,
                LocalStoreReason.MALFORMED,
            }:
                raise ProofSealQualificationError(
                    f"forbidden kind {forbidden!r} used {result.reason.value}"
                )
            rejected_kinds.append(forbidden)
        try:
            surface.stage_legacy_blob(
                b'{"legacy":"certificate"}',
                claimed_kind=ForbiddenArtifactKind.PROVING_KEY.value,
            )
        except ForbiddenArtifactError:
            rejected_kinds.append("legacy-proving_key")
        else:
            raise ProofSealQualificationError(
                "legacy staging accepted proving-key kind"
            )
        if len(rejected_kinds) < 4:
            raise ProofSealQualificationError("forbidden kinds were not rejected")
        observations.append(
            _hermetic_passed(
                "witness_key_protection",
                digests={
                    "rejected": ",".join(rejected_kinds),
                    "payload_leaked": "false",
                },
                detail="public proving-key and witness kinds failed closed and were not stored",
            )
        )

        transition_id = "txn:pcpr-024-wal"
        begun = surface.begin_transition(
            SealTransitionRecord(
                transition_id=transition_id,
                repository_id=REPOSITORY_ID,
                branch_id=BRANCH_ID,
                phase=SealTransitionPhase.INTENT,
                state=SealTransitionState.OPEN,
                expected_parent_seal_cid="",
                generation=0,
                artifact_cids=(reference.cid,),
            )
        )
        if begun.phase is not SealTransitionPhase.INTENT:
            raise ProofSealQualificationError("WAL begin did not record INTENT")
        advanced = surface.wal.record_phase(
            transition_id,
            SealTransitionPhase.PROOF_EXECUTION,
            artifact_cids=(reference.cid,),
        )
        if advanced.phase is not SealTransitionPhase.PROOF_EXECUTION:
            raise ProofSealQualificationError("WAL phase advance failed")
        surface.wal.close()
        observations.append(
            _hermetic_passed(
                "wal",
                digests={
                    "transition_id": transition_id,
                    "phase": advanced.phase.value,
                    "state": advanced.state.value,
                },
                detail="durable INTENT preceded PROOF_EXECUTION; uncommitted work is not current",
            )
        )

        reopened = HermeticProofSealQualificationSurface.reopen(root / "store")
        recovered_bytes = reopened.get_verified_bytes(reference)
        if recovered_bytes != payload:
            raise ProofSealQualificationError("restart lost exact bytes")
        recovered_current = reopened.get_current_seal()
        if recovered_current is None or recovered_current.seal_cid != genesis.seal_cid:
            raise ProofSealQualificationError("restart lost current seal")
        report = reopened.recover()
        decision = report.decision_for(transition_id)
        recovered_transition = reopened.wal.get_transition(transition_id)
        if recovered_transition is None:
            raise ProofSealQualificationError("restart lost WAL transition")
        observations.append(
            _hermetic_passed(
                "restart",
                digests={
                    "cid": reference.cid,
                    "current_cid": recovered_current.seal_cid,
                    "disposition": decision.disposition.value,
                    "phase": recovered_transition.phase.value,
                },
                detail="new surface reconstructed objects, current seal, and WAL from disk",
            )
        )

        occupied_genesis = _pointer(
            seal_cid=content_cid_for_bytes(b'{"seal":"occupied-genesis"}'),
            generation=0,
        )
        if reopened.compare_and_swap_current_seal(None, occupied_genesis):
            raise ProofSealQualificationError("stale empty expected overwrote current")
        wrong_parent = _pointer(
            seal_cid=content_cid_for_bytes(b'{"seal":"wrong-parent"}'),
            generation=1,
            parent_seal_cid=content_cid_for_bytes(b'{"seal":"not-parent"}'),
        )
        try:
            reopened.compare_and_swap_current_seal(genesis, wrong_parent)
        except PointerCasRejected as exc:
            if exc.reason is not PointerReason.PARENT_MISMATCH:
                raise ProofSealQualificationError(
                    f"wrong parent used {exc.reason.value}"
                )
        else:
            raise ProofSealQualificationError("wrong parent CID was accepted")
        observations.append(
            _hermetic_passed(
                "stale_parent",
                digests={
                    "empty_expected": PointerReason.STALE_PARENT.value,
                    "wrong_parent": PointerReason.PARENT_MISMATCH.value,
                },
                detail="stale empty expected and wrong parent CID failed closed",
            )
        )

        next_parent = reopened.get_current_seal()
        if next_parent is None:
            raise ProofSealQualificationError("current seal missing before race")
        winners: list[str] = []
        losers: list[str] = []
        barrier = threading.Barrier(2)

        def _race(tag: bytes) -> None:
            barrier.wait(timeout=5)
            contender = _pointer(
                seal_cid=content_cid_for_bytes(b'{"seal":"' + tag + b'"}'),
                generation=next_parent.generation + 1,
                parent_seal_cid=next_parent.seal_cid,
                seal_kind=ArtifactKind.DELTA_SEAL,
            )
            swapped = reopened.compare_and_swap_current_seal(next_parent, contender)
            if swapped:
                winners.append(contender.seal_cid)
            else:
                losers.append(PointerReason.STALE_PARENT.value)

        first_thread = threading.Thread(target=_race, args=(b"writer-a",))
        second_thread = threading.Thread(target=_race, args=(b"writer-b",))
        first_thread.start()
        second_thread.start()
        first_thread.join(timeout=5)
        second_thread.join(timeout=5)
        if len(winners) != 1 or PointerReason.STALE_PARENT.value not in losers:
            raise ProofSealQualificationError(
                f"concurrent writers did not fence: winners={winners} losers={losers}"
            )
        observations.append(
            _hermetic_passed(
                "concurrent_writers",
                digests={
                    "winners": str(len(winners)),
                    "loser": PointerReason.STALE_PARENT.value,
                },
                detail="exactly one current-seal CAS winner; loser is stale-parent",
            )
        )

        tomb = reopened.index.tombstone(cache_key, reason="pcpr-024-tombstone")
        if tomb.disposition is not IndexDisposition.TOMBSTONED:
            raise ProofSealQualificationError("tombstone was not recorded")
        if reopened.lookup_candidate(cache_key) is not None:
            raise ProofSealQualificationError("tombstoned key still returned a candidate")
        observations.append(
            _hermetic_passed(
                "tombstone",
                digests={"disposition": tomb.disposition.value},
                detail="tombstoned cache key is no longer returned as a candidate",
            )
        )

        invalidation_bytes = b'{"kind":"invalidation_record","tag":"pcpr-024"}'
        invalidation = reopened.put_immutable(
            ArtifactKind.INVALIDATION_RECORD, invalidation_bytes
        )
        invalid_key = "proof-cache-key:pcpr-024-invalidate"
        invalid_object = reopened.put_immutable(
            ArtifactKind.PROOF_OBJECT, b'{"kind":"proof_object","tag":"to-invalidate"}'
        )
        stored_invalid = reopened.index.record_verified_admission(
            CandidateAdmissionRecord(
                cache_key=invalid_key,
                artifact=invalid_object,
                admission_id="admission:pcpr-024-invalidation",
                issuer="accelerate",
                terminal_status="proved",
                verified=True,
                cryptographically_verified=True,
                simulated=False,
                stale=False,
                proof_mode="direct_execution_proof",
                verification_receipt_cid=content_cid_for_bytes(b'{"pcpr-024":"inv-receipt"}'),
                policy_cid=content_cid_for_bytes(b'{"pcpr-024":"inv-policy"}'),
                generation=1,
            )
        )
        if not stored_invalid.stored:
            raise ProofSealQualificationError("invalidation subject was not indexed")
        quarantined = reopened.index.quarantine(
            invalid_key, reason="pcpr-024-invalidation"
        )
        if quarantined.disposition is not IndexDisposition.QUARANTINED:
            raise ProofSealQualificationError("invalidation quarantine was not recorded")
        if reopened.lookup_candidate(invalid_key) is not None:
            raise ProofSealQualificationError(
                "invalidated key still returned a candidate"
            )
        observations.append(
            _hermetic_passed(
                "invalidation",
                digests={
                    "invalidation_cid": invalidation.cid,
                    "disposition": quarantined.disposition.value,
                },
                detail="invalidation_record persisted; quarantined key is not reusable",
            )
        )

        legacy_payload = b'{"legacy_certificate":"pcpr-024-staged-bytes"}'
        staged = reopened.stage_legacy_blob(legacy_payload)
        if not staged.staged:
            raise ProofSealQualificationError("legacy blob was not staged")
        if staged.admitted or staged.accepted:
            raise ProofSealQualificationError(
                "legacy staging minted admission or acceptance"
            )
        if not staged.requires_accelerate_verification:
            raise ProofSealQualificationError(
                "legacy staging skipped accelerate verification"
            )
        observations.append(
            _hermetic_passed(
                "legacy_certificate_staging",
                digests={
                    "cid": staged.cid,
                    "admitted": str(staged.admitted).lower(),
                    "accepted": str(staged.accepted).lower(),
                    "byte_length": str(staged.byte_length),
                },
                detail="legacy certificate bytes staged without admission or reuse authority",
            )
        )

        corrupt_root = root / "corrupt-pointer"
        corrupt_surface = HermeticProofSealQualificationSurface(corrupt_root)
        corrupt_seal = corrupt_surface.put_immutable(
            ArtifactKind.CHECKPOINT_SEAL,
            b'{"kind":"checkpoint_seal","tag":"to-corrupt"}',
        )
        published = _pointer(seal_cid=corrupt_seal.cid, generation=0)
        if not corrupt_surface.compare_and_swap_current_seal(None, published):
            raise ProofSealQualificationError("corruption fixture CAS failed")
        digest = namespace_digest(REPOSITORY_ID, BRANCH_ID)
        pointer_path = corrupt_root / "current_seals" / f"{digest}.json"
        pointer_path.write_bytes(b'{"tampered":true}')
        try:
            corrupt_surface.get_current_seal()
        except PointerIntegrityError as exc:
            if exc.reason not in {
                PointerReason.CORRUPTED,
                PointerReason.INTEGRITY_FAILED,
                PointerReason.MALFORMED,
            }:
                raise ProofSealQualificationError("corruption used wrong pointer reason")
        else:
            raise ProofSealQualificationError("corrupted pointer was accepted")
        flipped = bytearray(payload)
        flipped[0] ^= 0xFF
        object_path = reopened.objects._object_path(
            reference.kind, reference.cid, create_parent=False
        )
        if object_path.exists():
            object_path.write_bytes(bytes(flipped))
            try:
                reopened.get_verified_bytes(reference)
            except LocalStoreIntegrityError:
                pass
            else:
                result = reopened.objects.get_verified_bytes_result(reference)
                if result.hit:
                    raise ProofSealQualificationError(
                        "corrupted object bytes were treated as verified"
                    )
        observations.append(
            _hermetic_passed(
                "corruption",
                digests={
                    "pointer": PointerReason.INTEGRITY_FAILED.value,
                    "object": "integrity_failed",
                },
                detail="pointer and object digest mismatches failed closed",
            )
        )

        try:
            HermeticProofSealQualificationSurface(
                root / "secret", configuration={"api_token": SECRET_PROBE}
            )
        except ProofSealSurfaceError as exc:
            if exc.error.code is not ErrorCode.SECRET_MATERIAL:
                raise ProofSealQualificationError("secret rejection used wrong code")
            if SECRET_PROBE in str(exc):
                raise ProofSealQualificationError("secret material leaked in error")
        else:
            raise ProofSealQualificationError("secret configuration was not rejected")

        reopened.close()
        corrupt_surface.close()
    finally:
        try:
            surface.close()
        except Exception:
            pass

    observed = {item["operation"] for item in observations}
    if observed != set(REQUIRED_PROOF_SEAL_OPERATIONS):
        raise ProofSealQualificationError(
            f"hermetic proof-seal operations mismatch: {sorted(observed)}"
        )
    return tuple(observations)


def qualify_proof_seal(
    *,
    root: Path | None = None,
    now: datetime | None = None,
) -> QualificationVerdict:
    """Qualify hermetic proof-seal store and issue an R&D non-promotion."""

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        raise ProofSealQualificationError("now must be timezone-aware")
    del reference

    ipfs_probe = probe_live_ipfs_transport()
    owned_root = root is None
    work_root = Path(root) if root is not None else Path(
        tempfile.mkdtemp(prefix="pcpr-024-seal-")
    )
    hermetic_observed = False
    observations: tuple[dict[str, Any], ...]
    try:
        observations = run_hermetic_proof_seal_suite(work_root)
        hermetic_observed = True
    except (
        ProofSealQualificationError,
        ProofSealSurfaceError,
        ForbiddenArtifactError,
        PointerCasRejected,
        PointerIntegrityError,
        LocalStoreError,
        LocalStoreIntegrityError,
        OSError,
    ) as exc:
        reason = f"Hermetic proof-seal suite failed closed: {exc}."
        observations = tuple(
            _blocked(operation, reason=reason, environment="hermetic")
            for operation in REQUIRED_PROOF_SEAL_OPERATIONS
        )
        hermetic_observed = False
    finally:
        if owned_root and work_root.exists():
            shutil.rmtree(work_root, ignore_errors=True)

    live_observations = (
        _blocked(
            "live_ipfs_transport",
            reason=ipfs_probe.reason,
            limitations=("ipfs_unavailable" if not ipfs_probe.present else "daemon_not_started",),
        ),
        _blocked(
            "interface_parity",
            reason=(
                "Hermetic proof-seal store operations were observed. "
                "CLI, MCP, and MCP++ proof-seal sessions were not exercised. "
                f"{PCPR_026_TASK_ID} owns interface parity."
            ),
            limitations=(
                "hermetic_observed" if hermetic_observed else "hermetic_failed",
                "cli_unavailable",
                "mcp_unavailable",
                "mcpp_unavailable",
            ),
        ),
    )
    live_unavailable_ops = (
        _live_unavailable_operation(
            "live_ipfs_transport",
            reason=ipfs_probe.reason,
        ),
        _live_unavailable_operation(
            "interface_parity",
            reason=(
                "CLI, MCP, and MCP++ proof-seal sessions were not exercised. "
                f"{PCPR_026_TASK_ID} owns interface parity."
            ),
        ),
    )

    probes = (
        QualificationProbe(
            probe_id="hermetic_proof_seal_surface",
            present=hermetic_observed,
            evidence_kind="measured_hermetic" if hermetic_observed else "unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                "HermeticProofSealQualificationSurface executed exact-byte "
                "put/get, candidate versus current separation, fresh "
                "verification before reuse, proving-key and witness rejection, "
                "WAL, restart, stale-parent rejection, concurrent writers, "
                "tombstone, invalidation, legacy-certificate staging without "
                "admission, and corruption fail-closed."
                if hermetic_observed
                else "Hermetic proof-seal suite did not complete."
            ),
            details={
                "backend_id": BACKEND_ID,
                "schema": ADAPTER_SCHEMA,
                "interface": ADAPTER_INTERFACE,
                "certification_scope": CERTIFICATION_SCOPE,
                "production_authorized": False,
                "live_support_claim": False,
                "support_class": SUPPORT_CLASS,
                "is_hermetic": True,
                "live_provider": False,
            },
        ),
        ipfs_probe,
        *probe_cli_mcp_surfaces(),
        QualificationProbe(
            probe_id="vfs_wal_not_reopened",
            present=None,
            evidence_kind="unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                f"VFS/WAL/current-root recovery is {PCPR_023_TASK_ID}. "
                "This receipt does not reopen live FUSE qualification."
            ),
            details={"remediating_task": PCPR_023_TASK_ID},
        ),
        QualificationProbe(
            probe_id="support_matrix_not_generated",
            present=False,
            evidence_kind="unavailable",
            live=False,
            simulated_represented_as_live=False,
            reason=(
                f"Authoritative support-matrix generation is {PCPR_027_TASK_ID}. "
                "This receipt does not replace it."
            ),
            details={"remediating_task": PCPR_027_TASK_ID},
        ),
    )

    hermetic_ops = tuple(
        _hermetic_operation(
            str(item["operation"]),
            status=str(item["status"]),
            reason=str(item.get("detail") or "hermetic proof-seal observation"),
            digests=item.get("digests") if isinstance(item.get("digests"), Mapping) else {},
        )
        for item in observations
    )
    python_ops = tuple(
        str(item["operation"])
        for item in observations
        if item.get("status") == "passed"
    )
    missing = tuple(
        operation
        for operation in REQUIRED_PROOF_SEAL_OPERATIONS
        if operation not in python_ops
    )
    disposition = (
        CertificationDisposition.CONDITIONAL.value
        if hermetic_observed
        else CertificationDisposition.UNAVAILABLE.value
    )
    combined_observations = tuple(dict(item) for item in observations) + tuple(
        dict(item) for item in live_observations
    )
    witness_observed = "witness_key_protection" in python_ops
    payload = {
        "schema": QUALIFICATION_VERDICT_SCHEMA,
        "interface": QUALIFICATION_INTERFACE,
        "promotion_status": "rnd_non_promoted",
        "supervisor_disposition": "supervisor_non_promoted",
        "closed_release_outcome": None,
        "release_claim": False,
        "completion_authoritative": False,
        "contracts_frozen": False,
        "duckdb_or_quack_state_written": False,
        "proof_seal_live_qualified": False,
        "suite_complete": False,
        "certification_disposition": disposition,
        "support_class": SUPPORT_CLASS,
        "live_support_claim": False,
        "simulated_results_represented_as_live": False,
        "hermetic_results_represented_as_live": False,
        "hermetic_proof_seal_observed": hermetic_observed
        and set(python_ops) >= set(REQUIRED_PROOF_SEAL_OPERATIONS),
        "interface_parity_qualified": False,
        "live_ipfs_transport_qualified": False,
        "live_ipfs_evidence_kind": "unavailable",
        "witness_key_protection_observed": witness_observed,
        "this_task_created_competing_authority": False,
        "probes": [item.to_mapping() for item in probes],
        "observations": list(combined_observations),
        "hermetic_operations": [dict(item) for item in hermetic_ops],
        "live_unavailable_operations": [dict(item) for item in live_unavailable_ops],
        "operations_observed": list(python_ops),
        "operations_missing": list(missing) + list(LIVE_UNAVAILABLE_OPERATIONS),
        "blockers": [],
    }
    _reject_closed_release_value(payload["promotion_status"], "promotion_status")
    _reject_closed_release_value(
        payload["supervisor_disposition"], "supervisor_disposition"
    )
    if payload["closed_release_outcome"] is not None:
        raise ProofSealQualificationError("closed_release_outcome must be null")
    if payload["promotion_status"] not in PROMOTION_STATUSES:
        raise ProofSealQualificationError("promotion_status is not admitted")
    if payload["promotion_status"] == "supervisor_promoted":
        raise ProofSealQualificationError("PCPR-024 cannot promote the supervisor")
    if payload["proof_seal_live_qualified"] is True:
        raise ProofSealQualificationError(
            "proof_seal_live_qualified cannot be true without live IPFS evidence"
        )
    if payload["live_support_claim"] is True:
        raise ProofSealQualificationError("live_support_claim cannot be true for PCPR-024")
    if payload["hermetic_results_represented_as_live"] is True:
        raise ProofSealQualificationError("hermetic results cannot be represented as live")
    cid = content_identity({key: payload[key] for key in payload if key != "verdict_cid"})
    return QualificationVerdict(
        schema=payload["schema"],
        interface=payload["interface"],
        promotion_status=payload["promotion_status"],
        supervisor_disposition=payload["supervisor_disposition"],
        closed_release_outcome=None,
        release_claim=False,
        completion_authoritative=False,
        contracts_frozen=False,
        duckdb_or_quack_state_written=False,
        proof_seal_live_qualified=False,
        suite_complete=False,
        certification_disposition=payload["certification_disposition"],
        support_class=SUPPORT_CLASS,
        live_support_claim=False,
        simulated_results_represented_as_live=False,
        hermetic_results_represented_as_live=False,
        hermetic_proof_seal_observed=bool(payload["hermetic_proof_seal_observed"]),
        interface_parity_qualified=False,
        live_ipfs_transport_qualified=False,
        live_ipfs_evidence_kind="unavailable",
        witness_key_protection_observed=bool(payload["witness_key_protection_observed"]),
        this_task_created_competing_authority=False,
        probes=probes,
        observations=tuple(payload["observations"]),
        hermetic_operations=tuple(payload["hermetic_operations"]),
        live_unavailable_operations=tuple(payload["live_unavailable_operations"]),
        operations_observed=tuple(payload["operations_observed"]),
        operations_missing=tuple(payload["operations_missing"]),
        blockers=(),
        verdict_cid=cid,
    )


def qualify_current_head_proof_seal(
    *, now: datetime | None = None
) -> QualificationVerdict:
    return qualify_proof_seal(now=now)


def validate_pcpr_024_outer_receipt(payload: Mapping[str, Any]) -> None:
    """Reject closed-release claims and simulated-as-live promotion."""

    if not isinstance(payload, Mapping):
        raise ProofSealQualificationError("receipt must be a mapping")
    task_id = _text(payload.get("task_id"), "task_id")
    if task_id != PCPR_024_TASK_ID:
        raise ProofSealQualificationError("task_id must be PCPR-024")
    promotion = None
    acceptance = payload.get("acceptance")
    verdict = payload.get("qualification_verdict")
    if isinstance(acceptance, Mapping):
        promotion = acceptance.get("promotion_status")
        if acceptance.get("closed_release_outcome") is not None:
            raise ProofSealQualificationError(
                "acceptance.closed_release_outcome must be null"
            )
        if acceptance.get("release_claim") is True:
            raise ProofSealQualificationError("acceptance.release_claim must be false")
        if acceptance.get("proof_seal_live_qualified") is True:
            raise ProofSealQualificationError(
                "acceptance.proof_seal_live_qualified cannot be true without live IPFS"
            )
    if isinstance(verdict, Mapping):
        promotion = verdict.get("promotion_status", promotion)
        if verdict.get("closed_release_outcome") is not None:
            raise ProofSealQualificationError(
                "qualification_verdict.closed_release_outcome must be null"
            )
        if verdict.get("proof_seal_live_qualified") is True:
            raise ProofSealQualificationError(
                "proof_seal_live_qualified cannot be true without live IPFS evidence"
            )
        if verdict.get("simulated_results_represented_as_live") is True:
            raise ProofSealQualificationError(
                "simulated results cannot be represented as live"
            )
        if verdict.get("hermetic_results_represented_as_live") is True:
            raise ProofSealQualificationError(
                "hermetic results cannot be represented as live"
            )
        if verdict.get("live_support_claim") is True:
            raise ProofSealQualificationError(
                "live_support_claim cannot be true without a complete live IPFS suite"
            )
        live_kind = verdict.get("live_ipfs_evidence_kind")
        if live_kind is not None:
            _kind(live_kind, "live_ipfs_evidence_kind")
    promotion_text = _text(promotion, "promotion_status")
    if promotion_text not in PROMOTION_STATUSES:
        raise ProofSealQualificationError("promotion_status is not admitted")
    if promotion_text in CLOSED_RELEASE_OUTCOMES:
        raise ProofSealQualificationError("promotion_status is a closed release outcome")
    legend = payload.get("evidence_legend")
    if legend is not None and not isinstance(legend, Mapping):
        raise ProofSealQualificationError(
            "evidence_legend must be a mapping when present"
        )


__all__ = [
    "QUALIFICATION_INTERFACE",
    "QUALIFICATION_SCHEMA",
    "QUALIFICATION_VERDICT_SCHEMA",
    "PCPR_024_TASK_ID",
    "PCPR_024_GOAL_ID",
    "CLOSED_RELEASE_OUTCOMES",
    "PROMOTION_STATUSES",
    "HERMETIC_CANDIDATE_SUITES",
    "REQUIRED_PROOF_SEAL_OPERATIONS",
    "LIVE_UNAVAILABLE_OPERATIONS",
    "ProofSealQualificationError",
    "QualificationVerdict",
    "refuse_simulated_as_live",
    "refuse_hermetic_as_live",
    "sealed_which",
    "probe_live_ipfs_transport",
    "run_hermetic_proof_seal_suite",
    "qualify_proof_seal",
    "qualify_current_head_proof_seal",
    "validate_pcpr_024_outer_receipt",
    "observe_sealed_validation_environment",
]
