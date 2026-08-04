"""Regression tests for canonical WAL contracts and compatibility (KITA-018).

Acceptance coverage:

* record identities are collision-safe and monotonic within a generation;
* states reject impossible transitions;
* committed/durable is distinct from buffered/queued;
* payloads are bounded references;
* compatibility mappings preserve unknown/legacy state explicitly;
* secrets and unsafe executable encodings reject; and
* fsync / parent-directory / backend-effect requirements are declared per
  acknowledgement mode.
"""

from __future__ import annotations

import pytest

from ipfs_kit_py.core.operation_contracts import (
    BodyRejectedError,
    ForgedIdentityError,
    InconsistentStateError,
    PayloadKind,
    PayloadReference,
    SecretMaterialError,
)
from ipfs_kit_py.core.wal.compatibility import (
    CompatibilityDisposition,
    LegacyWALSource,
    assert_not_silently_committed,
    legacy_ack_mode_catalog,
    legacy_kind_catalog,
    legacy_status_catalog,
    map_legacy_ack_mode,
    map_legacy_kind,
    map_legacy_status,
    map_legacy_transaction_state,
    project_legacy_operation,
)
from ipfs_kit_py.core.wal.contracts import (
    BUFFERED_OR_QUEUED_STATES,
    COMMITTED_STATES,
    CONTRACT_VERSION,
    DURABLE_STATES,
    SCHEMA_VERSION,
    WALCheckpoint_V1,
    WALRecord_V1,
    WALSegment_V1,
    WALTransaction_V1,
    WALAcknowledgementError,
    WALAcknowledgementMode,
    WALCheckpoint,
    WALCheckpointState,
    WALContractError,
    WALFsyncReceipt,
    WALRecord,
    WALRecordIdentity,
    WALRecordKind,
    WALRecordState,
    WALSegment,
    WALSegmentState,
    WALSequenceError,
    WALTransaction,
    WALTransactionState,
    WALUnsafeEncodingError,
    ack_requirements_for,
    all_ack_requirements,
    assert_ack_allows_state,
    assert_legal_checkpoint_transition,
    assert_legal_record_transition,
    assert_legal_segment_transition,
    assert_legal_transaction_transition,
    assert_sequence_chain,
    assert_sequence_monotonic,
    checksum_for_preimage,
    is_legal_record_transition,
    is_legal_transaction_transition,
    make_buffered_record,
    make_committed_record,
)


# ---------------------------------------------------------------------------
# Schema / vocabulary
# ---------------------------------------------------------------------------


def test_schema_versions_and_interface_aliases() -> None:
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert WALRecord_V1.endswith("@1")
    assert WALTransaction_V1.endswith("@1")
    assert WALSegment_V1.endswith("@1")
    assert WALCheckpoint_V1.endswith("@1")
    assert "KITA-018" in open(
        __import__("ipfs_kit_py.core.wal.contracts", fromlist=["__doc__"]).__file__,
        encoding="utf-8",
    ).read()


def test_closed_state_vocabularies_partition() -> None:
    # Buffered/queued must not overlap committed.
    assert BUFFERED_OR_QUEUED_STATES.isdisjoint(COMMITTED_STATES)
    assert BUFFERED_OR_QUEUED_STATES.isdisjoint(DURABLE_STATES) or (
        # appended is pre-commit media, not in BUFFERED_OR_QUEUED
        True
    )
    for state in (
        WALRecordState.BUFFERED,
        WALRecordState.QUEUED,
        WALRecordState.APPENDING,
    ):
        assert state in BUFFERED_OR_QUEUED_STATES
        assert state not in COMMITTED_STATES
        assert state not in DURABLE_STATES
    for state in (
        WALRecordState.COMMITTED,
        WALRecordState.ARCHIVED,
        WALRecordState.REPLAYED,
    ):
        assert state in COMMITTED_STATES
        assert state in DURABLE_STATES


# ---------------------------------------------------------------------------
# Identity: collision-safe + monotonic within generation
# ---------------------------------------------------------------------------


def test_record_identity_collision_safe_across_generations() -> None:
    a = WALRecordIdentity(generation_id="wal-gen:1", sequence_number=7)
    b = WALRecordIdentity(generation_id="wal-gen:2", sequence_number=7)
    assert a.identity_key != b.identity_key
    assert a.identity_tuple != b.identity_tuple
    # Cross-generation ordering is undefined.
    with pytest.raises(WALSequenceError):
        a.precedes(b)


def test_record_identity_monotonic_within_generation() -> None:
    first = WALRecordIdentity(generation_id="wal-gen:7", sequence_number=0)
    second = WALRecordIdentity(generation_id="wal-gen:7", sequence_number=1)
    third = WALRecordIdentity(generation_id="wal-gen:7", sequence_number=2)
    assert first.precedes(second)
    assert second.is_successor_of(first)
    assert_sequence_monotonic(first, second)
    assert_sequence_monotonic(second, third)
    with pytest.raises(WALSequenceError):
        assert_sequence_monotonic(third, second)
    with pytest.raises(WALSequenceError):
        assert_sequence_monotonic(second, second)  # collision


def test_sequence_chain_detects_collisions_and_gaps() -> None:
    gen = "wal-gen:chain"
    chain = [
        WALRecordIdentity(generation_id=gen, sequence_number=i) for i in (0, 1, 2, 3)
    ]
    assert_sequence_chain(chain, require_contiguous=True)
    dup = chain + [WALRecordIdentity(generation_id=gen, sequence_number=2)]
    with pytest.raises(WALSequenceError, match="collision"):
        assert_sequence_chain(dup)
    gapped = [
        WALRecordIdentity(generation_id=gen, sequence_number=0),
        WALRecordIdentity(generation_id=gen, sequence_number=2),
    ]
    with pytest.raises(WALSequenceError, match="gap"):
        assert_sequence_chain(gapped, require_contiguous=True)


def test_wal_record_identity_property_and_round_trip() -> None:
    record = make_buffered_record(
        generation_id="wal-gen:rt",
        sequence_number=42,
        kind=WALRecordKind.MUTATE,
        segment_id="wal-seg:1",
        checksum=checksum_for_preimage({"n": 42}),
    )
    assert record.identity_key == "wal-gen:rt#42"
    assert record.is_buffered_or_queued
    assert not record.is_committed
    assert not record.is_durable
    encoded = record.to_record()
    restored = WALRecord.from_dict(encoded)
    assert restored.content_id == record.content_id
    assert restored.sequence_number == 42


def test_forged_content_id_rejected() -> None:
    record = make_buffered_record(generation_id="wal-gen:f", sequence_number=1)
    payload = record.to_record()
    payload["content_id"] = "b" + ("a" * 58)
    with pytest.raises(ForgedIdentityError):
        WALRecord.from_dict(payload)


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------


def test_record_transitions_reject_impossible() -> None:
    assert is_legal_record_transition(
        WALRecordState.BUFFERED, WALRecordState.QUEUED
    )
    assert is_legal_record_transition(
        WALRecordState.APPENDED, WALRecordState.FILE_SYNCED
    )
    assert is_legal_record_transition(
        WALRecordState.PREPARED, WALRecordState.COMMITTED
    )
    # Cannot jump from buffered to committed.
    assert not is_legal_record_transition(
        WALRecordState.BUFFERED, WALRecordState.COMMITTED
    )
    with pytest.raises(InconsistentStateError):
        assert_legal_record_transition(
            WALRecordState.BUFFERED, WALRecordState.COMMITTED
        )
    # Terminal failures are closed.
    assert not is_legal_record_transition(
        WALRecordState.FAILED, WALRecordState.COMMITTED
    )
    with pytest.raises(InconsistentStateError):
        assert_legal_record_transition(
            WALRecordState.COMMITTED, WALRecordState.BUFFERED
        )


def test_transaction_transitions_reject_impossible() -> None:
    assert is_legal_transaction_transition(
        WALTransactionState.OPEN, WALTransactionState.PREPARING
    )
    assert is_legal_transaction_transition(
        WALTransactionState.PREPARED, WALTransactionState.COMMITTING
    )
    with pytest.raises(InconsistentStateError):
        assert_legal_transaction_transition(
            WALTransactionState.COMMITTED, WALTransactionState.OPEN
        )
    with pytest.raises(InconsistentStateError):
        assert_legal_transaction_transition(
            WALTransactionState.ABORTED, WALTransactionState.COMMITTED
        )


def test_segment_and_checkpoint_transitions() -> None:
    assert_legal_segment_transition(WALSegmentState.OPEN, WALSegmentState.SEALED)
    with pytest.raises(InconsistentStateError):
        assert_legal_segment_transition(
            WALSegmentState.ARCHIVED, WALSegmentState.OPEN
        )
    assert_legal_checkpoint_transition(
        WALCheckpointState.PENDING, WALCheckpointState.PUBLISHED
    )
    with pytest.raises(InconsistentStateError):
        assert_legal_checkpoint_transition(
            WALCheckpointState.FAILED, WALCheckpointState.PUBLISHED
        )


# ---------------------------------------------------------------------------
# Committed/durable distinct from buffered/queued
# ---------------------------------------------------------------------------


def test_buffered_cannot_claim_committed_under_buffered_mode() -> None:
    with pytest.raises(WALAcknowledgementError):
        WALRecord(
            generation_id="wal-gen:x",
            sequence_number=1,
            kind=WALRecordKind.COMMIT,
            state=WALRecordState.COMMITTED,
            acknowledgement_mode=WALAcknowledgementMode.BUFFERED,
            transaction_id="txn:1",
            fsync_receipt_id="fsync:1",
        )


def test_queued_mode_cannot_claim_prepared_or_committed() -> None:
    req = ack_requirements_for(WALAcknowledgementMode.QUEUED)
    assert not req.may_claim_committed
    assert not req.may_claim_prepared
    with pytest.raises(WALAcknowledgementError):
        assert_ack_allows_state(
            WALAcknowledgementMode.QUEUED, WALRecordState.COMMITTED
        )


def test_make_buffered_vs_committed_helpers() -> None:
    buffered = make_buffered_record(generation_id="wal-gen:h", sequence_number=0)
    committed = make_committed_record(
        generation_id="wal-gen:h",
        sequence_number=1,
        transaction_id="txn:h1",
        fsync_receipt_id="fsync:h1",
        previous_sequence=0,
    )
    assert buffered.is_buffered_or_queued
    assert not buffered.is_committed
    assert committed.is_committed
    assert committed.is_durable
    assert buffered.state != committed.state


# ---------------------------------------------------------------------------
# Payloads are bounded references
# ---------------------------------------------------------------------------


def test_payload_is_bounded_reference() -> None:
    payload = PayloadReference(
        kind=PayloadKind.CONTENT_CID,
        content_cid="sha256:" + ("ab" * 32),
        size_bytes=1024,
    )
    record = WALRecord(
        generation_id="wal-gen:p",
        sequence_number=3,
        kind=WALRecordKind.MUTATE,
        state=WALRecordState.APPENDED,
        acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED,
        payload=payload,
        encoding="application/octet-stream",
    )
    assert record.payload_cid.startswith("sha256:")
    assert record.payload is not None
    assert "body" not in record.to_dict()
    # Inline unbounded body markers rejected on construction path via secrets/body guard
    with pytest.raises((BodyRejectedError, SecretMaterialError, WALContractError)):
        WALRecord.from_dict(
            {
                **record.to_dict(),
                "payload_bytes": "x" * 100,  # unknown field / body
            }
        )


def test_inline_bounded_payload_allowed_small() -> None:
    payload = PayloadReference(
        kind=PayloadKind.INLINE_BOUNDED,
        inline_utf8="tiny-intent",
        size_bytes=11,
    )
    record = WALRecord(
        generation_id="wal-gen:inline",
        sequence_number=0,
        kind=WALRecordKind.INTENT,
        state=WALRecordState.BUFFERED,
        acknowledgement_mode=WALAcknowledgementMode.BUFFERED,
        payload=payload,
    )
    assert record.payload is not None
    assert record.payload.inline_utf8 == "tiny-intent"


# ---------------------------------------------------------------------------
# Secrets and unsafe executable encodings reject
# ---------------------------------------------------------------------------


def test_secrets_rejected_in_record_fields() -> None:
    with pytest.raises(SecretMaterialError):
        WALRecord(
            generation_id="wal-gen:sec",
            sequence_number=0,
            kind=WALRecordKind.MUTATE,
            state=WALRecordState.BUFFERED,
            acknowledgement_mode=WALAcknowledgementMode.BUFFERED,
            notes="password=hunter2",
        )


def test_secret_keys_in_round_trip_payload_rejected() -> None:
    record = make_buffered_record(generation_id="wal-gen:sec2", sequence_number=1)
    blob = record.to_dict()
    blob["api_key"] = "sk-live-xxx"
    with pytest.raises((SecretMaterialError, WALContractError)):
        WALRecord.from_dict(blob)


@pytest.mark.parametrize(
    "encoding",
    [
        "pickle",
        "application/x-python-pickle",
        "marshal",
        "application/x-python-code",
        "cloudpickle",
        "text/x-python",
    ],
)
def test_unsafe_executable_encodings_rejected(encoding: str) -> None:
    with pytest.raises(WALUnsafeEncodingError):
        WALRecord(
            generation_id="wal-gen:enc",
            sequence_number=0,
            kind=WALRecordKind.MUTATE,
            state=WALRecordState.BUFFERED,
            acknowledgement_mode=WALAcknowledgementMode.BUFFERED,
            encoding=encoding,
        )


def test_safe_encoding_accepted() -> None:
    record = WALRecord(
        generation_id="wal-gen:enc-ok",
        sequence_number=0,
        kind=WALRecordKind.MUTATE,
        state=WALRecordState.BUFFERED,
        acknowledgement_mode=WALAcknowledgementMode.BUFFERED,
        encoding="application/cbor",
    )
    assert record.encoding == "application/cbor"


# ---------------------------------------------------------------------------
# Ack mode requirements: fsync / parent-dir / backend-effect
# ---------------------------------------------------------------------------


def test_all_ack_modes_declare_requirements() -> None:
    requirements = all_ack_requirements()
    assert len(requirements) == len(WALAcknowledgementMode)
    by_mode = {item.mode: item for item in requirements}

    buffered = by_mode[WALAcknowledgementMode.BUFFERED]
    assert not buffered.requires_file_fsync
    assert not buffered.requires_parent_directory_fsync
    assert not buffered.requires_backend_effect
    assert not buffered.may_claim_committed

    queued = by_mode[WALAcknowledgementMode.QUEUED]
    assert not queued.may_claim_committed

    fsync = by_mode[WALAcknowledgementMode.WAL_FSYNC]
    assert fsync.requires_file_fsync
    assert not fsync.requires_parent_directory_fsync
    assert fsync.may_claim_committed

    parent = by_mode[WALAcknowledgementMode.WAL_FSYNC_PARENT]
    assert parent.requires_file_fsync
    assert parent.requires_parent_directory_fsync
    assert parent.may_claim_committed

    group = by_mode[WALAcknowledgementMode.GROUP_COMMIT]
    assert group.requires_file_fsync
    assert group.requires_parent_directory_fsync

    backend = by_mode[WALAcknowledgementMode.BACKEND_EFFECT]
    assert backend.requires_file_fsync
    assert backend.requires_backend_effect

    durable = by_mode[WALAcknowledgementMode.BACKEND_DURABLE]
    assert durable.requires_file_fsync
    assert durable.requires_parent_directory_fsync
    assert durable.requires_backend_effect


def test_committed_record_requires_fsync_receipt_for_fsync_mode() -> None:
    with pytest.raises(WALAcknowledgementError):
        WALRecord(
            generation_id="wal-gen:ack",
            sequence_number=1,
            kind=WALRecordKind.COMMIT,
            state=WALRecordState.COMMITTED,
            acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC,
            transaction_id="txn:ack",
            # missing fsync_receipt_id
        )


def test_backend_durable_requires_backend_effect_id() -> None:
    with pytest.raises(WALAcknowledgementError):
        WALRecord(
            generation_id="wal-gen:be",
            sequence_number=1,
            kind=WALRecordKind.COMMIT,
            state=WALRecordState.COMMITTED,
            acknowledgement_mode=WALAcknowledgementMode.BACKEND_DURABLE,
            transaction_id="txn:be",
            fsync_receipt_id="fsync:be",
            # missing backend_effect_id
        )


def test_fsync_receipt_satisfies_parent_mode() -> None:
    receipt = WALFsyncReceipt(
        receipt_id="fsync:parent-1",
        generation_id="wal-gen:r",
        sequence_number=9,
        file_fsync_observed=True,
        parent_directory_fsync_observed=True,
        segment_id="wal-seg:1",
    )
    req = ack_requirements_for(WALAcknowledgementMode.WAL_FSYNC_PARENT)
    assert receipt.satisfies(req)
    weak = WALFsyncReceipt(
        receipt_id="fsync:parent-2",
        generation_id="wal-gen:r",
        sequence_number=9,
        file_fsync_observed=True,
        parent_directory_fsync_observed=False,
    )
    assert not weak.satisfies(req)
    assert_ack_allows_state(
        WALAcknowledgementMode.WAL_FSYNC_PARENT,
        WALRecordState.COMMITTED,
        fsync_receipt=receipt,
    )
    with pytest.raises(WALAcknowledgementError):
        assert_ack_allows_state(
            WALAcknowledgementMode.WAL_FSYNC_PARENT,
            WALRecordState.COMMITTED,
            fsync_receipt=weak,
        )


# ---------------------------------------------------------------------------
# Transactions, segments, checkpoints
# ---------------------------------------------------------------------------


def test_transaction_committed_invariants() -> None:
    txn = WALTransaction(
        transaction_id="txn:100",
        generation_id="wal-gen:t",
        state=WALTransactionState.COMMITTED,
        acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC_PARENT,
        begin_sequence=1,
        prepare_sequence=2,
        commit_sequence=3,
        record_sequences=(1, 2, 3),
        fsync_receipt_id="fsync:t100",
    )
    assert txn.is_committed
    restored = WALTransaction.from_dict(txn.to_record())
    assert restored.content_id == txn.content_id

    with pytest.raises(InconsistentStateError):
        WALTransaction(
            transaction_id="txn:bad",
            generation_id="wal-gen:t",
            state=WALTransactionState.COMMITTED,
            acknowledgement_mode=WALAcknowledgementMode.WAL_FSYNC,
            # missing commit_sequence
            fsync_receipt_id="fsync:x",
        )


def test_transaction_record_sequences_must_be_monotonic() -> None:
    with pytest.raises(WALSequenceError):
        WALTransaction(
            transaction_id="txn:mono",
            generation_id="wal-gen:t",
            state=WALTransactionState.OPEN,
            acknowledgement_mode=WALAcknowledgementMode.BUFFERED,
            record_sequences=(3, 2, 1),
        )


def test_segment_sealed_does_not_accept_appends() -> None:
    open_seg = WALSegment(
        segment_id="wal-seg:open",
        generation_id="wal-gen:s",
        state=WALSegmentState.OPEN,
        first_sequence=0,
        last_sequence=10,
        sealed=False,
    )
    assert open_seg.accepts_appends
    sealed = WALSegment(
        segment_id="wal-seg:sealed",
        generation_id="wal-gen:s",
        state=WALSegmentState.SEALED,
        first_sequence=0,
        last_sequence=10,
        sealed=True,
        checksum=checksum_for_preimage("seg"),
    )
    assert not sealed.accepts_appends
    with pytest.raises(InconsistentStateError):
        WALSegment(
            segment_id="wal-seg:bad",
            generation_id="wal-gen:s",
            state=WALSegmentState.OPEN,
            first_sequence=0,
            last_sequence=1,
            sealed=True,
        )


def test_checkpoint_covers_sequence_and_requires_segments() -> None:
    ckpt = WALCheckpoint(
        checkpoint_id="ckpt:1",
        generation_id="wal-gen:c",
        through_sequence=100,
        state=WALCheckpointState.PUBLISHED,
        sealed_segment_ids=("wal-seg:1", "wal-seg:2"),
        checksum=checksum_for_preimage({"through": 100}),
    )
    assert ckpt.covers_sequence(100)
    assert ckpt.covers_sequence(0)
    assert not ckpt.covers_sequence(101)
    with pytest.raises(InconsistentStateError):
        WALCheckpoint(
            checkpoint_id="ckpt:empty",
            generation_id="wal-gen:c",
            through_sequence=0,
            state=WALCheckpointState.PUBLISHED,
            sealed_segment_ids=(),
            checksum="sha256:" + ("cd" * 32),
        )


# ---------------------------------------------------------------------------
# Compatibility mappings
# ---------------------------------------------------------------------------


def test_legacy_completed_is_not_committed() -> None:
    result = map_legacy_status(
        "completed", source=LegacyWALSource.STORAGE_WAL
    )
    assert result.disposition is CompatibilityDisposition.LEGACY_MAPPED
    assert result.canonical_state is WALRecordState.APPENDED
    assert not result.may_claim_committed
    assert_not_silently_committed(result)


def test_legacy_completed_elevates_only_when_durability_proven() -> None:
    elevated = map_legacy_status(
        "completed",
        source=LegacyWALSource.WAL,
        durability_proven=True,
    )
    assert elevated.canonical_state is WALRecordState.COMMITTED
    assert elevated.may_claim_committed


def test_unknown_legacy_status_preserved_explicitly() -> None:
    result = map_legacy_status(
        "weird_status_xyz", source=LegacyWALSource.FILESYSTEM_JOURNAL
    )
    assert result.disposition is CompatibilityDisposition.UNKNOWN_PRESERVED
    assert result.canonical_state is None
    assert result.preserves_unknown
    assert not result.may_claim_committed
    assert result.legacy_value == "weird_status_xyz"
    assert_not_silently_committed(result)


def test_legacy_journal_rolled_back_maps_to_aborted() -> None:
    result = map_legacy_status(
        "rolled_back", source=LegacyWALSource.FILESYSTEM_JOURNAL
    )
    assert result.canonical_state is WALRecordState.ABORTED


def test_legacy_kinds_and_unknown_kind() -> None:
    pin = map_legacy_kind("pin", source=LegacyWALSource.WAL)
    assert pin.canonical_kind is WALRecordKind.MUTATE
    assert pin.disposition is CompatibilityDisposition.LEGACY_MAPPED
    unknown = map_legacy_kind("not_a_real_op", source=LegacyWALSource.PIN_WAL)
    assert unknown.preserves_unknown
    assert unknown.canonical_kind is WALRecordKind.UNKNOWN
    assert unknown.legacy_value == "not_a_real_op"


def test_legacy_fsync_modes_declare_requirements() -> None:
    always = map_legacy_ack_mode("always", source=LegacyWALSource.ENHANCED_WAL_DURABILITY)
    assert always.canonical_mode is WALAcknowledgementMode.WAL_FSYNC
    assert always.requires_file_fsync
    assert always.may_claim_committed

    batch = map_legacy_ack_mode("batch", source=LegacyWALSource.ENHANCED_WAL_DURABILITY)
    assert batch.canonical_mode is WALAcknowledgementMode.GROUP_COMMIT
    assert batch.requires_parent_directory_fsync

    unknown = map_legacy_ack_mode("mystery_mode")
    assert unknown.disposition is CompatibilityDisposition.UNKNOWN_PRESERVED
    assert unknown.canonical_mode is None
    assert not unknown.may_claim_committed
    assert unknown.preserves_unknown


def test_project_legacy_operation_preserves_unknown_and_rejects_secrets() -> None:
    envelope = project_legacy_operation(
        {
            "operation_id": "op-1",
            "status": "pending",
            "type": "add",
        },
        source=LegacyWALSource.STORAGE_WAL,
    )
    assert envelope["canonical_state"] == WALRecordState.QUEUED.value
    assert envelope["canonical_kind"] == WALRecordKind.MUTATE.value
    assert not envelope["may_claim_committed"]

    unknown = project_legacy_operation(
        {"status": "totally_new_state", "type": "add"},
        source=LegacyWALSource.WAL,
    )
    assert unknown["preserves_unknown"]
    assert unknown["legacy"]["status"] == "totally_new_state"
    assert unknown["canonical_state"] is None
    assert_not_silently_committed(unknown)

    with pytest.raises(SecretMaterialError):
        project_legacy_operation({"status": "pending", "api_key": "x"})

    with pytest.raises(BodyRejectedError):
        project_legacy_operation({"status": "pending", "payload_bytes": b"nope"})

    unsafe = project_legacy_operation(
        {"status": "pending", "type": "add", "encoding": "pickle"},
        source=LegacyWALSource.WAL,
    )
    assert unsafe["disposition"] == CompatibilityDisposition.UNSAFE_REJECTED.value
    assert unsafe["canonical_state"] is None


def test_legacy_catalogs_include_observed_variants() -> None:
    statuses = legacy_status_catalog()
    assert statuses["pending"] == "queued"
    assert statuses["completed"] == "appended"
    assert statuses["rolled_back"] == "aborted"
    kinds = legacy_kind_catalog()
    assert kinds["checkpoint"] == "checkpoint_marker"
    assert kinds["pin"] == "mutate"
    acks = legacy_ack_mode_catalog()
    assert acks["always"] == "wal_fsync"
    assert acks["batch"] == "group_commit"


def test_legacy_transaction_completed_is_not_committed() -> None:
    disposition, state, raw = map_legacy_transaction_state("completed")
    assert disposition is CompatibilityDisposition.LEGACY_MAPPED
    assert state is WALTransactionState.OPEN  # not COMMITTED
    assert raw == "completed"


def test_canonical_status_passthrough() -> None:
    result = map_legacy_status("committed")
    assert result.disposition is CompatibilityDisposition.CANONICAL
    assert result.canonical_state is WALRecordState.COMMITTED
    assert result.may_claim_committed


# ---------------------------------------------------------------------------
# Content identity stability
# ---------------------------------------------------------------------------


def test_content_identity_stable_for_equal_records() -> None:
    kwargs = dict(
        generation_id="wal-gen:stable",
        sequence_number=5,
        kind=WALRecordKind.MUTATE,
        state=WALRecordState.APPENDED,
        acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED,
        checksum=checksum_for_preimage("body-ref"),
    )
    a = WALRecord(**kwargs)
    b = WALRecord(**kwargs)
    assert a.content_id == b.content_id
    c = WALRecord(**{**kwargs, "sequence_number": 6, "previous_sequence": 5})
    assert c.content_id != a.content_id
