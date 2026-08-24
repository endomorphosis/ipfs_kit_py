"""PCCE-072: fail-closed receipt, proof-cache, and seal trust admission."""

from __future__ import annotations

import base64
import json
from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path
from typing import Any

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from ipfs_kit_py.proof_context.trust import (
    AdmissionReason,
    AuthorityUnavailableError,
    EvidenceFreshness,
    EvidenceMode,
    EvidenceProvenance,
    EvidenceReference,
    ProvenanceStatus,
    SignatureClaim,
    SignatureStatus,
    TrustAdmissionVerifier,
    TrustContractError,
    TrustEvidence,
    TrustExpectation,
    VerifiedArtifact,
    admit_cache_candidate,
    admit_evidence,
)
from ipfs_kit_py.proof_seal_store.contracts import (
    ArtifactKind,
    ArtifactReference,
    CacheCandidate,
)
from ipfs_kit_py.proof_seal_store.local_store import (
    HermeticProofSealStore,
    LocalStoreNotFoundError,
    content_cid_for_bytes,
)


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def _put_json(
    store: HermeticProofSealStore,
    kind: ArtifactKind,
    payload: dict[str, Any],
) -> EvidenceReference:
    data = _canonical(payload)
    artifact = store.put_immutable(kind, data)
    return EvidenceReference(
        cid=artifact.cid,
        kind=kind,
        byte_length=len(data),
        payload_schema=payload["schema"],
    )


class ObservedLiveAuthority:
    """Test port that records the complete locally supplied live observation."""

    def __init__(self, outcome: bool | BaseException | str = True) -> None:
        self.outcome = outcome
        self.calls = 0
        self.last_subject: VerifiedArtifact | None = None
        self.last_references: tuple[VerifiedArtifact, ...] = ()

    def verify_live_provenance(
        self,
        *,
        evidence: TrustEvidence,
        expectation: TrustExpectation,
        subject: VerifiedArtifact,
        references: tuple[VerifiedArtifact, ...],
    ) -> bool:
        self.calls += 1
        self.last_subject = subject
        self.last_references = references
        assert evidence.subject == expectation.subject
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome  # type: ignore[return-value]


class Ed25519VerificationAuthority:
    """Test-only installed-key verifier; it never signs inside production code."""

    def __init__(
        self,
        public_key: Ed25519PublicKey,
        *,
        outcome: bool | BaseException | str | None = None,
    ) -> None:
        self.public_key = public_key
        self.outcome = outcome
        self.calls = 0

    def verify_signature(
        self,
        *,
        algorithm: str,
        signer: str,
        message: bytes,
        signature: bytes,
    ) -> bool:
        self.calls += 1
        assert algorithm == "ed25519"
        assert signer == "test-key-1"
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        if self.outcome is not None:
            return self.outcome  # type: ignore[return-value]
        try:
            self.public_key.verify(signature, message)
        except InvalidSignature:
            return False
        return True


@dataclass(frozen=True)
class TrustFixture:
    store: HermeticProofSealStore
    evidence: TrustEvidence
    expectation: TrustExpectation
    live: ObservedLiveAuthority

    @property
    def descriptor_bytes(self) -> bytes:
        return self.evidence.canonical_bytes()

    @property
    def descriptor_cid(self) -> str:
        return content_cid_for_bytes(self.descriptor_bytes)


@pytest.fixture
def trust_fixture(tmp_path: Path) -> TrustFixture:
    store = HermeticProofSealStore(tmp_path)
    environment = _put_json(
        store,
        ArtifactKind.PROOF_MANIFEST,
        {"schema": "example.environment@1", "platform": "linux-x86_64"},
    )
    policy = _put_json(
        store,
        ArtifactKind.PROOF_MANIFEST,
        {"schema": "example.policy@1", "policy": "production-v4"},
    )
    parent = _put_json(
        store,
        ArtifactKind.CHECKPOINT_SEAL,
        {
            "schema": "example.seal@1",
            "environment_cid": environment.cid,
            "policy_cid": policy.cid,
            "generation": 3,
        },
    )
    subject = _put_json(
        store,
        ArtifactKind.PROOF_RECEIPT,
        {
            "schema": "example.receipt@1",
            "environment_cid": environment.cid,
            "policy_cid": policy.cid,
            "parent_seal_cid": parent.cid,
            "generation": 4,
            "status": "integrity_verified",
        },
    )
    references = (environment, policy, parent)
    evidence = TrustEvidence(
        subject=subject,
        producer="ipfs_accelerate_py.proof_context",
        repository_id="endomorphosis/ipfs_accelerate_py",
        tree_id="1" * 40,
        environment_cid=environment.cid,
        policy_cid=policy.cid,
        generation=4,
        parent_seal_cids=(parent.cid,),
        provenance=EvidenceProvenance.LIVE,
        freshness=EvidenceFreshness.CURRENT,
        terminal_status="integrity_verified",
        evidence_mode=EvidenceMode.INTEGRITY,
        cache_key="proof-cache/v1/exact-key",
        references=references,
        signature=None,
    )
    expectation = TrustExpectation(
        subject=subject,
        producer=evidence.producer,
        repository_id=evidence.repository_id,
        tree_id=evidence.tree_id,
        environment_cid=environment.cid,
        policy_cid=policy.cid,
        generation=4,
        parent_seal_cids=(parent.cid,),
        terminal_status=evidence.terminal_status,
        evidence_mode=evidence.evidence_mode,
        cache_key=evidence.cache_key,
        references=references,
        signature_required=False,
    )
    return TrustFixture(
        store=store,
        evidence=evidence,
        expectation=expectation,
        live=ObservedLiveAuthority(),
    )


def _admit(
    fixture: TrustFixture,
    *,
    evidence: TrustEvidence | None = None,
    expectation: TrustExpectation | None = None,
    live: ObservedLiveAuthority | None = None,
    signature_authority: Ed25519VerificationAuthority | None = None,
):
    selected = evidence or fixture.evidence
    descriptor = selected.canonical_bytes()
    return admit_evidence(
        fixture.store,
        descriptor,
        claimed_descriptor_cid=content_cid_for_bytes(descriptor),
        expectation=expectation or fixture.expectation,
        live_provenance_authority=live if live is not None else fixture.live,
        signature_authority=signature_authority,
    )


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _replace_reference(
    references: tuple[EvidenceReference, ...],
    cid: str,
    replacement: EvidenceReference,
) -> tuple[EvidenceReference, ...]:
    return tuple(replacement if item.cid == cid else item for item in references)


def _signed_fixture(
    fixture: TrustFixture,
    private_key: Ed25519PrivateKey,
) -> tuple[TrustEvidence, TrustExpectation]:
    expectation = replace(
        fixture.expectation,
        signature_required=True,
        signer="test-key-1",
        signature_algorithm="ed25519",
    )
    signature = private_key.sign(fixture.evidence.signing_bytes())
    encoded = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    evidence = replace(
        fixture.evidence,
        signature=SignatureClaim(
            algorithm="ed25519",
            signer="test-key-1",
            value=encoded,
        ),
    )
    return evidence, expectation


def test_positive_unsigned_local_admission_is_deterministic_and_read_only(
    trust_fixture: TrustFixture,
) -> None:
    before = _snapshot(trust_fixture.store.root_path)
    first = _admit(trust_fixture)
    second = _admit(trust_fixture)

    assert first.admitted and second.admitted
    assert first.reason is AdmissionReason.ADMITTED
    assert first.may_reuse and first.may_publish
    assert first.signature_status is SignatureStatus.NOT_REQUIRED
    assert first.provenance_status is ProvenanceStatus.VERIFIED
    assert first.grant is not None and second.grant is not None
    assert first.grant.cid == second.grant.cid
    assert first.grant.canonical_bytes == second.grant.canonical_bytes
    assert first.grant.qualification_credit is False
    assert first.qualification_credit is False
    assert _snapshot(trust_fixture.store.root_path) == before
    assert trust_fixture.live.calls == 2


def test_positive_ed25519_signature_uses_installed_verifier(
    trust_fixture: TrustFixture,
) -> None:
    private_key = Ed25519PrivateKey.from_private_bytes(b"\x07" * 32)
    evidence, expectation = _signed_fixture(trust_fixture, private_key)
    authority = Ed25519VerificationAuthority(private_key.public_key())

    result = _admit(
        trust_fixture,
        evidence=evidence,
        expectation=expectation,
        signature_authority=authority,
    )

    assert result.admitted
    assert result.signature_status is SignatureStatus.VERIFIED
    assert authority.calls == 1


@pytest.mark.parametrize(
    ("kind", "payload_schema", "terminal_status", "mode"),
    [
        (
            ArtifactKind.PROOF_OBJECT,
            "example.proof@1",
            "proved",
            EvidenceMode.CRYPTOGRAPHIC,
        ),
        (
            ArtifactKind.DELTA_SEAL,
            "example.delta-seal@1",
            "sealed",
            EvidenceMode.SEAL,
        ),
    ],
)
def test_positive_proof_and_seal_admission_use_the_same_read_only_gate(
    trust_fixture: TrustFixture,
    kind: ArtifactKind,
    payload_schema: str,
    terminal_status: str,
    mode: EvidenceMode,
) -> None:
    subject = _put_json(
        trust_fixture.store,
        kind,
        {
            "schema": payload_schema,
            "environment_cid": trust_fixture.evidence.environment_cid,
            "policy_cid": trust_fixture.evidence.policy_cid,
            "parent_seal_cid": trust_fixture.evidence.parent_seal_cids[0],
            "generation": trust_fixture.evidence.generation,
        },
    )
    evidence = replace(
        trust_fixture.evidence,
        subject=subject,
        terminal_status=terminal_status,
        evidence_mode=mode,
    )
    expectation = replace(
        trust_fixture.expectation,
        subject=subject,
        terminal_status=terminal_status,
        evidence_mode=mode,
    )

    result = _admit(trust_fixture, evidence=evidence, expectation=expectation)

    assert result.admitted
    assert result.grant is not None
    assert result.grant.subject.kind is kind


@pytest.mark.parametrize(
    ("field", "replacement", "reason"),
    [
        ("producer", "forged.producer", AdmissionReason.PRODUCER_MISMATCH),
        ("repository_id", "forged/repository", AdmissionReason.REPOSITORY_MISMATCH),
        ("tree_id", "2" * 40, AdmissionReason.TREE_MISMATCH),
        (
            "environment_cid",
            "sha256:" + "2" * 64,
            AdmissionReason.ENVIRONMENT_MISMATCH,
        ),
        ("policy_cid", "sha256:" + "3" * 64, AdmissionReason.POLICY_MISMATCH),
        ("generation", 5, AdmissionReason.GENERATION_MISMATCH),
        ("parent_seal_cids", (), AdmissionReason.PARENT_MISMATCH),
        ("terminal_status", "proved", AdmissionReason.STATUS_MISMATCH),
        ("evidence_mode", EvidenceMode.CRYPTOGRAPHIC, AdmissionReason.STATUS_MISMATCH),
        ("cache_key", "proof-cache/v1/poisoned", AdmissionReason.CACHE_KEY_MISMATCH),
        ("provenance", EvidenceProvenance.REPLAYED, AdmissionReason.PROVENANCE_NOT_LIVE),
        ("provenance", EvidenceProvenance.SIMULATED, AdmissionReason.SIMULATED),
        ("evidence_mode", EvidenceMode.SIMULATED, AdmissionReason.SIMULATED),
        ("freshness", EvidenceFreshness.STALE, AdmissionReason.STALE),
    ],
)
def test_context_replay_and_simulation_matrix_rejects_exact_reason(
    trust_fixture: TrustFixture,
    field: str,
    replacement: Any,
    reason: AdmissionReason,
) -> None:
    evidence = replace(trust_fixture.evidence, **{field: replacement})
    result = _admit(trust_fixture, evidence=evidence)

    assert not result.admitted
    assert result.reason is reason
    assert not result.may_reuse and not result.may_publish
    assert trust_fixture.live.calls == 0


def test_descriptor_cid_forgery_rejected_before_store_or_authority(
    trust_fixture: TrustFixture,
) -> None:
    result = admit_evidence(
        trust_fixture.store,
        trust_fixture.descriptor_bytes,
        claimed_descriptor_cid="sha256:" + "0" * 64,
        expectation=trust_fixture.expectation,
        live_provenance_authority=trust_fixture.live,
    )

    assert result.reason is AdmissionReason.DESCRIPTOR_CID_MISMATCH
    assert result.checks == ()
    assert trust_fixture.live.calls == 0


def test_noncanonical_duplicate_and_unknown_descriptor_fields_fail_closed(
    trust_fixture: TrustFixture,
) -> None:
    payload = trust_fixture.evidence.to_dict()
    pretty = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    noncanonical = admit_evidence(
        trust_fixture.store,
        pretty,
        claimed_descriptor_cid=content_cid_for_bytes(pretty),
        expectation=trust_fixture.expectation,
        live_provenance_authority=trust_fixture.live,
    )

    unknown_payload = dict(payload)
    unknown_payload["accept_anyway"] = True
    unknown_bytes = _canonical(unknown_payload)
    unknown = admit_evidence(
        trust_fixture.store,
        unknown_bytes,
        claimed_descriptor_cid=content_cid_for_bytes(unknown_bytes),
        expectation=trust_fixture.expectation,
        live_provenance_authority=trust_fixture.live,
    )

    duplicate = trust_fixture.descriptor_bytes.replace(
        b'{"cache_key":',
        b'{"cache_key":"poisoned","cache_key":',
        1,
    )
    duplicate_result = admit_evidence(
        trust_fixture.store,
        duplicate,
        claimed_descriptor_cid=content_cid_for_bytes(duplicate),
        expectation=trust_fixture.expectation,
        live_provenance_authority=trust_fixture.live,
    )

    assert noncanonical.reason is AdmissionReason.NON_CANONICAL
    assert unknown.reason is AdmissionReason.UNKNOWN_FIELD
    assert duplicate_result.reason is AdmissionReason.MALFORMED
    assert trust_fixture.live.calls == 0


@pytest.mark.parametrize("nested", ["subject", "reference", "signature"])
def test_nested_unknown_fields_are_rejected(
    trust_fixture: TrustFixture,
    nested: str,
) -> None:
    payload = trust_fixture.evidence.to_dict()
    expectation = trust_fixture.expectation
    if nested == "subject":
        payload["subject"]["unknown"] = "x"
    elif nested == "reference":
        payload["references"][0]["unknown"] = "x"
    else:
        private_key = Ed25519PrivateKey.from_private_bytes(b"\x09" * 32)
        evidence, expectation = _signed_fixture(trust_fixture, private_key)
        payload = evidence.to_dict()
        payload["signature"]["unknown"] = "x"
    raw = _canonical(payload)

    result = admit_evidence(
        trust_fixture.store,
        raw,
        claimed_descriptor_cid=content_cid_for_bytes(raw),
        expectation=expectation,
        live_provenance_authority=trust_fixture.live,
    )

    assert result.reason is AdmissionReason.UNKNOWN_FIELD


def test_subject_binding_schema_missing_and_corruption_matrix(
    trust_fixture: TrustFixture,
) -> None:
    alternate = _put_json(
        trust_fixture.store,
        ArtifactKind.PROOF_RECEIPT,
        {"schema": "example.receipt@1", "status": "integrity_verified"},
    )
    forged = replace(trust_fixture.evidence, subject=alternate)
    assert _admit(trust_fixture, evidence=forged).reason is AdmissionReason.SUBJECT_BINDING_MISMATCH

    class MissingSubjectReader:
        def get_verified_bytes(self, reference: ArtifactReference) -> bytes:
            if reference.cid == trust_fixture.evidence.subject.cid:
                raise LocalStoreNotFoundError("missing")
            return trust_fixture.store.get_verified_bytes(reference)

    missing = TrustAdmissionVerifier(
        MissingSubjectReader(),
        live_provenance_authority=trust_fixture.live,
    ).admit(
        trust_fixture.descriptor_bytes,
        claimed_descriptor_cid=trust_fixture.descriptor_cid,
        expectation=trust_fixture.expectation,
    )
    assert missing.reason is AdmissionReason.SUBJECT_MISSING

    class CorruptSubjectReader:
        def get_verified_bytes(self, reference: ArtifactReference) -> bytes:
            if reference.cid == trust_fixture.evidence.subject.cid:
                return b'{"schema":"example.receipt@1","tampered":true}'
            return trust_fixture.store.get_verified_bytes(reference)

    corrupt = TrustAdmissionVerifier(
        CorruptSubjectReader(),
        live_provenance_authority=trust_fixture.live,
    ).admit(
        trust_fixture.descriptor_bytes,
        claimed_descriptor_cid=trust_fixture.descriptor_cid,
        expectation=trust_fixture.expectation,
    )
    assert corrupt.reason is AdmissionReason.SUBJECT_CORRUPT

    wrong_schema_ref = replace(
        trust_fixture.evidence.subject,
        payload_schema="example.other-receipt@1",
    )
    wrong_schema_evidence = replace(trust_fixture.evidence, subject=wrong_schema_ref)
    wrong_schema_expectation = replace(trust_fixture.expectation, subject=wrong_schema_ref)
    wrong_schema = _admit(
        trust_fixture,
        evidence=wrong_schema_evidence,
        expectation=wrong_schema_expectation,
    )
    assert wrong_schema.reason is AdmissionReason.SUBJECT_SCHEMA_MISMATCH


def test_reference_corruption_missing_and_schema_matrix(
    trust_fixture: TrustFixture,
) -> None:
    target = trust_fixture.evidence.references[0]

    class ReferenceReader:
        def __init__(self, mode: str) -> None:
            self.mode = mode

        def get_verified_bytes(self, reference: ArtifactReference) -> bytes:
            if reference.cid == target.cid:
                if self.mode == "missing":
                    raise LocalStoreNotFoundError("missing")
                return b'{"schema":"example.corrupt@1"}'
            return trust_fixture.store.get_verified_bytes(reference)

    for mode, expected in (
        ("missing", AdmissionReason.REFERENCE_MISSING),
        ("corrupt", AdmissionReason.REFERENCE_CORRUPT),
    ):
        result = TrustAdmissionVerifier(
            ReferenceReader(mode),
            live_provenance_authority=trust_fixture.live,
        ).admit(
            trust_fixture.descriptor_bytes,
            claimed_descriptor_cid=trust_fixture.descriptor_cid,
            expectation=trust_fixture.expectation,
        )
        assert result.reason is expected

    wrong = replace(target, payload_schema="example.wrong-schema@1")
    references = _replace_reference(trust_fixture.evidence.references, target.cid, wrong)
    evidence = replace(trust_fixture.evidence, references=references)
    expectation = replace(trust_fixture.expectation, references=references)
    result = _admit(trust_fixture, evidence=evidence, expectation=expectation)
    assert result.reason is AdmissionReason.REFERENCE_SCHEMA_MISMATCH


def test_missing_and_orphaned_transitive_evidence_are_rejected(
    trust_fixture: TrustFixture,
) -> None:
    environment = next(
        item
        for item in trust_fixture.evidence.references
        if item.cid == trust_fixture.evidence.environment_cid
    )
    missing_refs = tuple(
        item for item in trust_fixture.evidence.references if item.cid != environment.cid
    )
    missing_evidence = replace(trust_fixture.evidence, references=missing_refs)
    missing_expectation = replace(trust_fixture.expectation, references=missing_refs)
    missing = _admit(
        trust_fixture,
        evidence=missing_evidence,
        expectation=missing_expectation,
    )
    assert missing.reason is AdmissionReason.MISSING_EVIDENCE

    orphan = _put_json(
        trust_fixture.store,
        ArtifactKind.PROOF_MANIFEST,
        {"schema": "example.orphan@1", "unused": True},
    )
    orphan_refs = trust_fixture.evidence.references + (orphan,)
    orphan_evidence = replace(trust_fixture.evidence, references=orphan_refs)
    orphan_expectation = replace(trust_fixture.expectation, references=orphan_refs)
    orphaned = _admit(
        trust_fixture,
        evidence=orphan_evidence,
        expectation=orphan_expectation,
    )
    assert orphaned.reason is AdmissionReason.MISSING_EVIDENCE


def test_undeclared_transitive_cid_in_subject_is_missing_evidence(
    trust_fixture: TrustFixture,
) -> None:
    undeclared_cid = content_cid_for_bytes(b"undeclared-transitive-object")
    subject = _put_json(
        trust_fixture.store,
        ArtifactKind.PROOF_RECEIPT,
        {
            "schema": "example.receipt@1",
            "environment_cid": trust_fixture.evidence.environment_cid,
            "policy_cid": trust_fixture.evidence.policy_cid,
            "parent_seal_cid": trust_fixture.evidence.parent_seal_cids[0],
            "undeclared_cid": undeclared_cid,
        },
    )
    evidence = replace(trust_fixture.evidence, subject=subject)
    expectation = replace(trust_fixture.expectation, subject=subject)

    result = _admit(trust_fixture, evidence=evidence, expectation=expectation)

    assert result.reason is AdmissionReason.MISSING_EVIDENCE


def test_signature_required_missing_unavailable_invalid_and_binding_matrix(
    trust_fixture: TrustFixture,
) -> None:
    private_key = Ed25519PrivateKey.from_private_bytes(b"\x0b" * 32)
    evidence, expectation = _signed_fixture(trust_fixture, private_key)

    missing = _admit(trust_fixture, expectation=expectation)
    assert missing.reason is AdmissionReason.SIGNATURE_REQUIRED
    assert missing.signature_status is SignatureStatus.MISSING

    unavailable = _admit(
        trust_fixture,
        evidence=evidence,
        expectation=expectation,
    )
    assert unavailable.reason is AdmissionReason.SIGNATURE_AUTHORITY_UNAVAILABLE
    assert unavailable.signature_status is SignatureStatus.UNAVAILABLE
    assert unavailable.qualification_credit is False

    invalid_claim = replace(
        evidence.signature,
        value=base64.urlsafe_b64encode(b"\x00" * 64).decode("ascii").rstrip("="),
    )
    invalid_evidence = replace(evidence, signature=invalid_claim)
    authority = Ed25519VerificationAuthority(private_key.public_key())
    invalid = _admit(
        trust_fixture,
        evidence=invalid_evidence,
        expectation=expectation,
        signature_authority=authority,
    )
    assert invalid.reason is AdmissionReason.SIGNATURE_INVALID
    assert invalid.signature_status is SignatureStatus.INVALID

    wrong_signer = replace(evidence.signature, signer="different-key")
    wrong_binding = _admit(
        trust_fixture,
        evidence=replace(evidence, signature=wrong_signer),
        expectation=expectation,
        signature_authority=authority,
    )
    assert wrong_binding.reason is AdmissionReason.SIGNATURE_BINDING_MISMATCH


@pytest.mark.parametrize(
    "outcome",
    [AuthorityUnavailableError("offline"), RuntimeError("failed"), "not-a-bool"],
)
def test_signature_authority_faults_are_unavailable_not_success(
    trust_fixture: TrustFixture,
    outcome: BaseException | str,
) -> None:
    private_key = Ed25519PrivateKey.from_private_bytes(b"\x0c" * 32)
    evidence, expectation = _signed_fixture(trust_fixture, private_key)
    authority = Ed25519VerificationAuthority(
        private_key.public_key(),
        outcome=outcome,
    )

    result = _admit(
        trust_fixture,
        evidence=evidence,
        expectation=expectation,
        signature_authority=authority,
    )

    assert result.reason is AdmissionReason.SIGNATURE_AUTHORITY_UNAVAILABLE
    assert result.signature_status is SignatureStatus.UNAVAILABLE
    assert trust_fixture.live.calls == 0


def test_unexpected_signature_on_unsigned_policy_is_rejected(
    trust_fixture: TrustFixture,
) -> None:
    private_key = Ed25519PrivateKey.from_private_bytes(b"\x0d" * 32)
    signed, _ = _signed_fixture(trust_fixture, private_key)

    result = _admit(trust_fixture, evidence=signed)

    assert result.reason is AdmissionReason.SIGNATURE_BINDING_MISMATCH
    assert result.signature_status is SignatureStatus.INVALID


@pytest.mark.parametrize(
    ("authority", "reason", "status"),
    [
        (None, AdmissionReason.PROVENANCE_AUTHORITY_UNAVAILABLE, ProvenanceStatus.UNAVAILABLE),
        (
            ObservedLiveAuthority(AuthorityUnavailableError("offline")),
            AdmissionReason.PROVENANCE_AUTHORITY_UNAVAILABLE,
            ProvenanceStatus.UNAVAILABLE,
        ),
        (
            ObservedLiveAuthority("not-a-bool"),
            AdmissionReason.PROVENANCE_AUTHORITY_UNAVAILABLE,
            ProvenanceStatus.UNAVAILABLE,
        ),
        (
            ObservedLiveAuthority(False),
            AdmissionReason.PROVENANCE_INVALID,
            ProvenanceStatus.INVALID,
        ),
    ],
)
def test_live_provenance_unavailable_or_invalid_never_admits(
    trust_fixture: TrustFixture,
    authority: ObservedLiveAuthority | None,
    reason: AdmissionReason,
    status: ProvenanceStatus,
) -> None:
    verifier = TrustAdmissionVerifier(
        trust_fixture.store,
        live_provenance_authority=authority,
    )

    result = verifier.admit(
        trust_fixture.descriptor_bytes,
        claimed_descriptor_cid=trust_fixture.descriptor_cid,
        expectation=trust_fixture.expectation,
    )

    assert result.reason is reason
    assert result.provenance_status is status
    assert not result.may_publish


def test_cache_candidate_positive_and_poisoning_matrix(
    trust_fixture: TrustFixture,
) -> None:
    candidate = CacheCandidate(
        cache_key=trust_fixture.expectation.cache_key,
        artifact=trust_fixture.expectation.subject.artifact_reference,
    )
    positive = admit_cache_candidate(
        trust_fixture.store,
        candidate,
        trust_fixture.descriptor_bytes,
        claimed_descriptor_cid=trust_fixture.descriptor_cid,
        expectation=trust_fixture.expectation,
        live_provenance_authority=trust_fixture.live,
    )
    assert positive.admitted
    assert "cache_candidate_binding" in positive.checks

    wrong_key = CacheCandidate(
        cache_key="proof-cache/v1/wrong-key",
        artifact=trust_fixture.expectation.subject.artifact_reference,
    )
    key_result = admit_cache_candidate(
        trust_fixture.store,
        wrong_key,
        trust_fixture.descriptor_bytes,
        claimed_descriptor_cid=trust_fixture.descriptor_cid,
        expectation=trust_fixture.expectation,
        live_provenance_authority=trust_fixture.live,
    )
    assert key_result.reason is AdmissionReason.CACHE_KEY_MISMATCH

    other_artifact = trust_fixture.expectation.references[0].artifact_reference
    wrong_artifact = CacheCandidate(
        cache_key=trust_fixture.expectation.cache_key,
        artifact=other_artifact,
    )
    artifact_result = admit_cache_candidate(
        trust_fixture.store,
        wrong_artifact,
        trust_fixture.descriptor_bytes,
        claimed_descriptor_cid=trust_fixture.descriptor_cid,
        expectation=trust_fixture.expectation,
        live_provenance_authority=trust_fixture.live,
    )
    assert artifact_result.reason is AdmissionReason.CACHE_ARTIFACT_MISMATCH

    invalid = admit_cache_candidate(
        trust_fixture.store,
        object(),  # type: ignore[arg-type]
        trust_fixture.descriptor_bytes,
        claimed_descriptor_cid=trust_fixture.descriptor_cid,
        expectation=trust_fixture.expectation,
        live_provenance_authority=trust_fixture.live,
    )
    assert invalid.reason is AdmissionReason.CACHE_CANDIDATE_INVALID


def test_rejection_cannot_mutate_blocks_cache_or_publish_current_seal(
    trust_fixture: TrustFixture,
) -> None:
    before = _snapshot(trust_fixture.store.root_path)
    forged = replace(trust_fixture.evidence, generation=999)

    result = _admit(trust_fixture, evidence=forged)

    assert result.reason is AdmissionReason.GENERATION_MISMATCH
    assert result.grant is None
    assert not result.may_reuse and not result.may_publish
    assert _snapshot(trust_fixture.store.root_path) == before
    assert not (trust_fixture.store.root_path / "cache_index").exists()
    assert not (trust_fixture.store.root_path / "current_seals").exists()


def test_reference_set_must_match_the_exact_frozen_expectation(
    trust_fixture: TrustFixture,
) -> None:
    evidence = replace(
        trust_fixture.evidence,
        references=trust_fixture.evidence.references[:-1],
    )

    result = _admit(trust_fixture, evidence=evidence)

    assert result.reason is AdmissionReason.REFERENCE_MISMATCH


def test_contracts_are_frozen_closed_and_root_kinds_are_narrow(
    trust_fixture: TrustFixture,
) -> None:
    with pytest.raises(FrozenInstanceError):
        trust_fixture.expectation.generation = 9  # type: ignore[misc]

    values = [reason.value for reason in AdmissionReason]
    assert len(values) == len(set(values))

    manifest_subject = replace(
        trust_fixture.expectation.subject,
        kind=ArtifactKind.PROOF_MANIFEST,
    )
    with pytest.raises(TrustContractError):
        replace(trust_fixture.expectation, subject=manifest_subject)

    seal_subject = replace(
        trust_fixture.expectation.subject,
        kind=ArtifactKind.CHECKPOINT_SEAL,
    )
    with pytest.raises(TrustContractError):
        replace(trust_fixture.expectation, subject=seal_subject)


def test_noncanonical_subject_bytes_are_corrupt_even_when_cid_matches(
    trust_fixture: TrustFixture,
    tmp_path: Path,
) -> None:
    payload = {
        "schema": "example.receipt@1",
        "environment_cid": trust_fixture.evidence.environment_cid,
        "policy_cid": trust_fixture.evidence.policy_cid,
        "parent_seal_cid": trust_fixture.evidence.parent_seal_cids[0],
    }
    pretty = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    store = HermeticProofSealStore(tmp_path / "pretty-store")
    artifact = store.put_immutable(ArtifactKind.PROOF_RECEIPT, pretty)
    subject = EvidenceReference(
        cid=artifact.cid,
        kind=artifact.kind,
        byte_length=len(pretty),
        payload_schema="example.receipt@1",
    )
    evidence = replace(trust_fixture.evidence, subject=subject)
    expectation = replace(trust_fixture.expectation, subject=subject)

    class SplitReader:
        def get_verified_bytes(self, reference: ArtifactReference) -> bytes:
            if reference.cid == subject.cid:
                return store.get_verified_bytes(reference)
            return trust_fixture.store.get_verified_bytes(reference)

    descriptor = evidence.canonical_bytes()
    result = TrustAdmissionVerifier(
        SplitReader(),
        live_provenance_authority=trust_fixture.live,
    ).admit(
        descriptor,
        claimed_descriptor_cid=content_cid_for_bytes(descriptor),
        expectation=expectation,
    )

    assert result.reason is AdmissionReason.SUBJECT_CORRUPT
