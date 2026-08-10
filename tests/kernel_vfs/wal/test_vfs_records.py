"""KVFS-303: Canonical WAL records are the recoverable transaction source of truth.

Acceptance coverage:

* durable data carries transaction/operation/effect IDs, intent, bounded inline
  payload or staged content reference, checksum, preconditions, decision, and
  acknowledgement;
* marker-to-sidecar crash gaps are classified and incomplete pairs are not
  treated as recoverable;
* corrupt tails preserve the valid prefix; and
* secrets and unbounded data reject at construction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ipfs_kit_py.core.operation_contracts import (
    BodyRejectedError,
    ForgedIdentityError,
    InconsistentStateError,
    SecretMaterialError,
)
from ipfs_kit_py.core.wal.contracts import (
    WALAcknowledgementMode,
    WALCorruptionDisposition,
    WALRecord,
    WALRecordKind,
    WALRecordState,
)
from ipfs_kit_py.core.wal.segments import WALSegmentFile
from ipfs_kit_py.core.wal.vfs_records import (
    CANONICAL_ENVELOPE_KIND,
    CONTRACT_VERSION,
    SCHEMA_VERSION,
    VFSWALAcknowledgement,
    VFSWALContent,
    VFSWALContentKind,
    VFSWALDecision,
    VFSWALDurableData,
    VFSWALDurableData_V1,
    VFSWALGapError,
    VFSWALIntentKind,
    VFSWALPrecondition,
    VFSWALRecordBoundsError,
    VFSWALRecordError,
    MarkerSidecarGapKind,
    assert_no_unrecoverable_gaps,
    classify_marker_sidecar_gap,
    compute_content_checksum,
    make_durable_data,
    project_legacy_sidecar_intent,
    read_sidecar_jsonl,
    recover_vfs_wal_prefix,
    recoverable_transactions_from_prefix,
)


# ---------------------------------------------------------------------------
# Schema / vocabulary
# ---------------------------------------------------------------------------


def test_schema_versions_and_aliases() -> None:
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert VFSWALDurableData_V1.endswith("@1")
    assert CANONICAL_ENVELOPE_KIND.startswith("vfs_wal_durable_data")


# ---------------------------------------------------------------------------
# Canonical durable data fields
# ---------------------------------------------------------------------------


def _write_intent_data(**overrides: object) -> VFSWALDurableData:
    content = VFSWALContent.inline("hello-bytes", media_type="text/plain")
    base = dict(
        transaction_id="txn:write-1",
        operation_id="op:write-1",
        effect_id="effect:write-1",
        intent=VFSWALIntentKind.WRITE,
        content=content,
        preconditions=(
            VFSWALPrecondition(
                name="parent-exists",
                expected="yes",
                observed="yes",
                required=True,
            ),
        ),
        decision=VFSWALDecision.INTENT_RECORDED,
        path_ref="path:home-docs-a",
        generation_id="wal-gen:vfs-1",
        intent_detail={"offset": 0, "length": 11},
    )
    base.update(overrides)
    return make_durable_data(**base)  # type: ignore[arg-type]


def test_durable_data_contains_all_required_fields() -> None:
    data = _write_intent_data()
    assert data.transaction_id == "txn:write-1"
    assert data.operation_id == "op:write-1"
    assert data.effect_id == "effect:write-1"
    assert data.intent is VFSWALIntentKind.WRITE
    assert data.content.kind is VFSWALContentKind.INLINE_BOUNDED
    assert data.content.inline_payload == "hello-bytes"
    assert data.checksum.startswith("sha256:")
    assert data.content_checksum_matches()
    assert len(data.preconditions) == 1
    assert data.preconditions[0].name == "parent-exists"
    assert data.decision is VFSWALDecision.INTENT_RECORDED
    assert isinstance(data.acknowledgement, VFSWALAcknowledgement)
    assert data.is_self_contained()

    encoded = data.to_record()
    restored = VFSWALDurableData.from_dict(encoded)
    assert restored.content_id == data.content_id
    assert restored.effect_id == data.effect_id
    assert restored.acknowledgement.mode is WALAcknowledgementMode.BUFFERED


def test_staged_content_reference_allowed() -> None:
    staged = VFSWALContent.staged(
        "sha256:" + ("ab" * 32),
        size_bytes=1_048_576,
        media_type="application/octet-stream",
        staging_path_ref="stage:obj-1",
    )
    data = make_durable_data(
        transaction_id="txn:stage-1",
        operation_id="op:stage-1",
        effect_id="effect:stage-1",
        intent=VFSWALIntentKind.WRITE,
        content=staged,
        decision=VFSWALDecision.INTENT_RECORDED,
        path_ref="path:large-file",
        generation_id="wal-gen:vfs-2",
    )
    assert data.content.kind is VFSWALContentKind.STAGED_CONTENT_REF
    assert data.content.staged_content_cid.startswith("sha256:")
    assert not data.content.inline_payload


def test_inline_and_staged_are_mutually_exclusive() -> None:
    with pytest.raises(InconsistentStateError):
        VFSWALContent(
            kind=VFSWALContentKind.INLINE_BOUNDED,
            inline_payload="x",
            staged_content_cid="sha256:" + ("cd" * 32),
        )
    with pytest.raises(BodyRejectedError):
        VFSWALContent(
            kind=VFSWALContentKind.STAGED_CONTENT_REF,
            staged_content_cid="sha256:" + ("cd" * 32),
            inline_payload="smuggled",
        )


def test_committed_decision_requires_durable_acknowledgement() -> None:
    content = VFSWALContent.inline("x")
    with pytest.raises(InconsistentStateError):
        VFSWALDurableData(
            transaction_id="txn:c1",
            operation_id="op:c1",
            effect_id="effect:c1",
            intent=VFSWALIntentKind.WRITE,
            content=content,
            checksum=compute_content_checksum(
                intent=VFSWALIntentKind.WRITE, content=content
            ),
            preconditions=(),
            decision=VFSWALDecision.COMMITTED,
            acknowledgement=VFSWALAcknowledgement.buffered(),
        )


def test_unsatisfied_required_precondition_rejected() -> None:
    content = VFSWALContent.empty()
    with pytest.raises(InconsistentStateError):
        make_durable_data(
            transaction_id="txn:pre-1",
            operation_id="op:pre-1",
            effect_id="effect:pre-1",
            intent=VFSWALIntentKind.UNLINK,
            content=content,
            preconditions=(
                VFSWALPrecondition(
                    name="not-busy",
                    expected="free",
                    observed="busy",
                    required=True,
                ),
            ),
            decision=VFSWALDecision.INTENT_RECORDED,
        )


def test_rename_requires_target_path_ref() -> None:
    with pytest.raises(VFSWALRecordError, match="target_path_ref"):
        make_durable_data(
            transaction_id="txn:ren-1",
            operation_id="op:ren-1",
            effect_id="effect:ren-1",
            intent=VFSWALIntentKind.RENAME,
            path_ref="path:src",
        )


# ---------------------------------------------------------------------------
# Self-contained framing + recovery (no sidecar)
# ---------------------------------------------------------------------------


def test_frame_round_trip_is_self_contained(tmp_path: Path) -> None:
    data = _write_intent_data()
    record = data.to_wal_record(
        sequence_number=0,
        segment_id="wal-seg:1",
        state=WALRecordState.APPENDED,
    )
    assert record.transaction_id == data.transaction_id
    assert record.operation_id == data.operation_id
    assert record.backend_effect_id == data.effect_id
    assert record.checksum == data.checksum
    assert record.encoding == "vfs-wal-durable-data@1"
    assert record.payload is not None
    assert record.payload.inline_utf8
    envelope = json.loads(record.payload.inline_utf8)
    assert envelope["envelope_kind"] == CANONICAL_ENVELOPE_KIND

    extracted = VFSWALDurableData.from_wal_record(record)
    assert extracted is not None
    assert extracted.content_id == data.content_id
    assert extracted.intent is VFSWALIntentKind.WRITE
    assert extracted.preconditions[0].expected == "yes"
    assert extracted.decision is VFSWALDecision.INTENT_RECORDED
    assert extracted.acknowledgement.mode is WALAcknowledgementMode.BUFFERED

    # Persist and recover from segment media without any sidecar.
    segment_path = tmp_path / "canonical.wal"
    segment = WALSegmentFile(
        segment_path,
        generation_id="wal-gen:vfs-1",
        segment_id="wal-seg:1",
        first_sequence=0,
    )
    try:
        segment.append(record)
        segment.seal()
    finally:
        segment.close()

    prefix = recover_vfs_wal_prefix(segment_path)
    assert prefix.tail_corrupt is False
    assert len(prefix.durable_records) == 1
    assert prefix.durable_records[0].effect_id == "effect:write-1"
    assert prefix.gap_observations[0].gap_kind is (
        MarkerSidecarGapKind.CANONICAL_SELF_CONTAINED
    )
    assert prefix.gap_observations[0].recoverable is True
    recovered = recoverable_transactions_from_prefix(prefix)
    assert len(recovered) == 1
    assert recovered[0].transaction_id == "txn:write-1"


def test_committed_frame_carries_ack_evidence(tmp_path: Path) -> None:
    content = VFSWALContent.inline("done")
    data = make_durable_data(
        transaction_id="txn:commit-1",
        operation_id="op:commit-1",
        effect_id="effect:commit-1",
        intent=VFSWALIntentKind.CREATE,
        content=content,
        decision=VFSWALDecision.COMMITTED,
        path_ref="path:new-file",
        generation_id="wal-gen:commit",
    )
    assert data.acknowledgement.durable is True
    assert data.acknowledgement.fsync_receipt_id
    record = data.to_wal_record(
        sequence_number=0,
        segment_id="wal-seg:c1",
    )
    assert record.state is WALRecordState.COMMITTED
    assert record.kind is WALRecordKind.COMMIT
    assert record.fsync_receipt_id == data.acknowledgement.fsync_receipt_id

    path = tmp_path / "commit.wal"
    segment = WALSegmentFile(
        path,
        generation_id="wal-gen:commit",
        segment_id="wal-seg:c1",
    )
    try:
        segment.append(record)
        segment.seal()
    finally:
        segment.close()
    prefix = recover_vfs_wal_prefix(path)
    assert prefix.durable_records[0].decision is VFSWALDecision.COMMITTED
    assert prefix.durable_records[0].acknowledgement.durable is True


# ---------------------------------------------------------------------------
# Marker-to-sidecar crash gaps
# ---------------------------------------------------------------------------


def test_marker_without_sidecar_is_not_recoverable() -> None:
    marker = WALRecord(
        generation_id="wal-gen:gap",
        sequence_number=0,
        kind=WALRecordKind.INTENT,
        state=WALRecordState.APPENDED,
        acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED,
        transaction_id="txn:gap-1",
        operation_id="effect:gap-1",
        record_key="transaction:txn:gap-1:intent:effect:gap-1",
    )
    observation = classify_marker_sidecar_gap(
        transaction_id="txn:gap-1",
        wal_records=(marker,),
        sidecar_entries=(),
    )
    assert observation.gap_kind is MarkerSidecarGapKind.MARKER_WITHOUT_SIDECAR
    assert observation.recoverable is False
    with pytest.raises(VFSWALGapError, match="marker-to-sidecar"):
        assert_no_unrecoverable_gaps((observation,))


def test_sidecar_without_marker_is_not_acknowledged() -> None:
    observation = classify_marker_sidecar_gap(
        transaction_id="txn:gap-2",
        wal_records=(),
        sidecar_entries=(
            {
                "kind": "intent",
                "transaction_id": "txn:gap-2",
                "effect_id": "effect:gap-2",
                "intent": {"kind": "write", "path_ref": "path:x"},
            },
        ),
    )
    assert observation.gap_kind is MarkerSidecarGapKind.SIDECAR_WITHOUT_MARKER
    assert observation.recoverable is False


def test_legacy_marker_and_sidecar_pair_is_recoverable() -> None:
    marker = WALRecord(
        generation_id="wal-gen:legacy",
        sequence_number=0,
        kind=WALRecordKind.INTENT,
        state=WALRecordState.APPENDED,
        acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED,
        transaction_id="txn:legacy-1",
        operation_id="effect:legacy-1",
    )
    sidecar = {
        "kind": "intent",
        "transaction_id": "txn:legacy-1",
        "effect_id": "effect:legacy-1",
        "intent": {
            "kind": "write",
            "path_ref": "path:legacy",
            "inline_payload": "legacy-body",
        },
    }
    observation = classify_marker_sidecar_gap(
        transaction_id="txn:legacy-1",
        wal_records=(marker,),
        sidecar_entries=(sidecar,),
    )
    assert observation.gap_kind is MarkerSidecarGapKind.MARKER_AND_SIDECAR
    assert observation.recoverable is True

    projected = project_legacy_sidecar_intent(sidecar, generation_id="wal-gen:legacy")
    assert projected.effect_id == "effect:legacy-1"
    assert projected.content.inline_payload == "legacy-body"
    assert projected.intent is VFSWALIntentKind.WRITE


def test_canonical_record_eliminates_sidecar_gap(tmp_path: Path) -> None:
    """Self-contained durable data is recoverable even when sidecar is absent."""
    data = _write_intent_data(transaction_id="txn:canon-gap")
    record = data.to_wal_record(sequence_number=0, segment_id="wal-seg:g")
    path = tmp_path / "canon-gap.wal"
    segment = WALSegmentFile(
        path,
        generation_id="wal-gen:vfs-1",
        segment_id="wal-seg:g",
    )
    try:
        segment.append(record)
        segment.seal()
    finally:
        segment.close()

    # Sidecar deliberately missing — canonical path must still recover.
    prefix = recover_vfs_wal_prefix(path, sidecar_path=tmp_path / "missing.jsonl")
    assert prefix.gap_observations[0].gap_kind is (
        MarkerSidecarGapKind.CANONICAL_SELF_CONTAINED
    )
    assert_no_unrecoverable_gaps(prefix.gap_observations)
    assert recoverable_transactions_from_prefix(prefix)[0].effect_id == data.effect_id


def test_crash_after_marker_before_sidecar_preserves_gap_classification(
    tmp_path: Path,
) -> None:
    """Simulate the historic coordinator crash gap and prove it is classified."""
    # WAL has intent marker only (as the legacy coordinator wrote markers).
    path = tmp_path / "gap.wal"
    segment = WALSegmentFile(
        path,
        generation_id="wal-gen:crash",
        segment_id="wal-seg:crash",
    )
    try:
        segment.append(
            WALRecord(
                generation_id="wal-gen:crash",
                sequence_number=0,
                kind=WALRecordKind.BEGIN,
                state=WALRecordState.APPENDED,
                acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED,
                transaction_id="txn:crash-1",
                segment_id="wal-seg:crash",
            )
        )
        segment.append(
            WALRecord(
                generation_id="wal-gen:crash",
                sequence_number=1,
                kind=WALRecordKind.INTENT,
                state=WALRecordState.APPENDED,
                acknowledgement_mode=WALAcknowledgementMode.WAL_APPENDED,
                transaction_id="txn:crash-1",
                segment_id="wal-seg:crash",
                operation_id="effect:crash-1",
            )
        )
        segment.seal()
    finally:
        segment.close()

    # Sidecar has begin only — intent body never made it (crash between marker
    # write and sidecar append).
    sidecar = tmp_path / "transaction-decisions.jsonl"
    sidecar.write_text(
        json.dumps({"kind": "begin", "transaction_id": "txn:crash-1"}) + "\n",
        encoding="utf-8",
    )

    prefix = recover_vfs_wal_prefix(path, sidecar_path=sidecar)
    observation = prefix.gap_observations[0]
    assert observation.transaction_id == "txn:crash-1"
    # Intent marker without intent sidecar body → classic crash gap.
    assert observation.gap_kind is MarkerSidecarGapKind.MARKER_WITHOUT_SIDECAR
    assert observation.recoverable is False
    assert recoverable_transactions_from_prefix(prefix) == ()
    with pytest.raises(VFSWALGapError, match="marker-to-sidecar"):
        assert_no_unrecoverable_gaps(prefix.gap_observations)


def test_sidecar_torn_tail_preserves_valid_line_prefix(tmp_path: Path) -> None:
    sidecar = tmp_path / "decisions.jsonl"
    good = {
        "kind": "intent",
        "transaction_id": "txn:s1",
        "effect_id": "effect:s1",
        "intent": {"kind": "mkdir", "path_ref": "path:dir"},
    }
    sidecar.write_text(
        json.dumps(good, sort_keys=True) + "\n" + '{"kind":"intent","transaction_id":',
        encoding="utf-8",
    )
    entries = read_sidecar_jsonl(sidecar)
    assert len(entries) == 1
    assert entries[0]["effect_id"] == "effect:s1"


# ---------------------------------------------------------------------------
# Corrupt tail preserves valid prefix
# ---------------------------------------------------------------------------


def test_corrupt_tail_preserves_valid_durable_prefix(tmp_path: Path) -> None:
    first = _write_intent_data(
        transaction_id="txn:prefix-1",
        operation_id="op:prefix-1",
        effect_id="effect:prefix-1",
    )
    second = _write_intent_data(
        transaction_id="txn:prefix-2",
        operation_id="op:prefix-2",
        effect_id="effect:prefix-2",
        path_ref="path:second",
    )
    path = tmp_path / "torn.wal"
    segment = WALSegmentFile(
        path,
        generation_id="wal-gen:vfs-1",
        segment_id="wal-seg:torn",
    )
    try:
        segment.append(
            first.to_wal_record(sequence_number=0, segment_id="wal-seg:torn")
        )
        segment.append(
            second.to_wal_record(
                sequence_number=1,
                segment_id="wal-seg:torn",
                previous_sequence=0,
            )
        )
        segment.seal()
    finally:
        segment.close()

    # Append a torn frame tail after the sealed content.
    with open(path, "ab") as handle:
        handle.write(b"IWAL1\x00\x00\x00\x10torn-incomplete")

    prefix = recover_vfs_wal_prefix(path)
    assert prefix.tail_corrupt is True
    assert len(prefix.wal_records) == 2
    assert len(prefix.durable_records) == 2
    assert {item.effect_id for item in prefix.durable_records} == {
        "effect:prefix-1",
        "effect:prefix-2",
    }
    assert prefix.valid_bytes > 0
    # Explicit truncate disposition still leaves the logical prefix available.
    truncated = recover_vfs_wal_prefix(
        path, disposition=WALCorruptionDisposition.TRUNCATE_TO_VALID_PREFIX
    )
    assert len(truncated.durable_records) == 2
    assert path.stat().st_size == truncated.valid_bytes


# ---------------------------------------------------------------------------
# Secrets and unbounded data reject
# ---------------------------------------------------------------------------


def test_secrets_in_intent_detail_rejected() -> None:
    with pytest.raises(SecretMaterialError):
        make_durable_data(
            transaction_id="txn:sec-1",
            operation_id="op:sec-1",
            effect_id="effect:sec-1",
            intent=VFSWALIntentKind.WRITE,
            intent_detail={"api_key": "super-secret-value"},
        )


def test_secret_markers_in_inline_payload_rejected() -> None:
    with pytest.raises(SecretMaterialError):
        VFSWALContent.inline("password=hunter2")


def test_unbounded_body_keys_rejected_on_decode() -> None:
    data = _write_intent_data()
    payload = data.to_dict()
    payload["payload_bytes"] = "x" * 100
    with pytest.raises((BodyRejectedError, VFSWALRecordError)):
        VFSWALDurableData.from_dict(payload)


def test_oversized_inline_content_rejected() -> None:
    huge = "x" * 10_000
    with pytest.raises(VFSWALRecordBoundsError):
        VFSWALContent.inline(huge)


def test_raw_bytes_body_rejected() -> None:
    with pytest.raises(BodyRejectedError):
        make_durable_data(
            transaction_id="txn:bytes-1",
            operation_id="op:bytes-1",
            effect_id="effect:bytes-1",
            intent=VFSWALIntentKind.WRITE,
            intent_detail={"blob": b"not-allowed"},  # type: ignore[dict-item]
        )


def test_forged_durable_content_id_rejected() -> None:
    data = _write_intent_data()
    payload = data.to_record()
    payload["content_id"] = "b" + ("a" * 58)
    with pytest.raises(ForgedIdentityError):
        VFSWALDurableData.from_dict(payload)


def test_buffered_ack_cannot_claim_durable() -> None:
    with pytest.raises(InconsistentStateError):
        VFSWALAcknowledgement(
            mode=WALAcknowledgementMode.BUFFERED,
            durable=True,
        )


def test_checksum_required() -> None:
    content = VFSWALContent.empty()
    with pytest.raises(VFSWALRecordError, match="checksum"):
        VFSWALDurableData(
            transaction_id="txn:cs-1",
            operation_id="op:cs-1",
            effect_id="effect:cs-1",
            intent=VFSWALIntentKind.MKDIR,
            content=content,
            checksum="",
            preconditions=(),
            decision=VFSWALDecision.INTENT_RECORDED,
            acknowledgement=VFSWALAcknowledgement.buffered(),
        )
