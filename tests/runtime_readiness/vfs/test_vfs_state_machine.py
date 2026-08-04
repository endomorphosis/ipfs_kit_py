"""State-machine and differential tests for the canonical VFS service (KITA-006).

Acceptance coverage:

* generated traces match the reference model for all supported operations;
* failure creates no success event;
* rename/move changes state;
* return/error types are stable;
* operations are bounded, cancellation-aware, and side-effect-free outside
  the injected storage boundary.
"""

from __future__ import annotations

import copy

import pytest

from ipfs_kit_py.core.operation_contracts import OperationState
from ipfs_kit_py.core.vfs.contracts import (
    AtomicBoundary,
    VFSEntryKind,
    VFSError,
    VFSErrorCode,
    VFSMount,
    VFSOperation,
    VFSOperationKind,
    VFSOperationResult,
    VFSUnsupportedError,
)
from ipfs_kit_py.core.vfs.service import (
    CANONICAL_VFS_SERVICE_SCHEMA,
    CanonicalVFSService_V1,
    MAX_PAYLOAD_BYTES,
    CancellationToken,
    CanonicalVFSService,
    InMemoryVFSStorage,
    VFSEventKind,
    VFSExecuteRequest,
    make_op,
)
from tests.runtime_readiness.vfs.reference_model import (
    REFERENCE_MODEL_SCHEMA,
    VFSReferenceModel,
    VFSReferenceModel_V1,
    canonical_trace_step,
    traces_match,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pair() -> tuple[CanonicalVFSService, VFSReferenceModel]:
    storage = InMemoryVFSStorage()
    service = CanonicalVFSService(storage=storage, clock=lambda: 1_700_000_000_000)
    ref = VFSReferenceModel(clock_ms=1_700_000_000_000)
    return service, ref


def _seed_both(
    service: CanonicalVFSService,
    ref: VFSReferenceModel,
    path: str,
    *,
    content: bytes = b"",
    kind: VFSEntryKind = VFSEntryKind.FILE,
) -> None:
    assert isinstance(service.storage, InMemoryVFSStorage)
    service.storage.seed(path, content=content, kind=kind)
    ref.seed(path, content=content, kind=kind)


def _ops_for_full_crud() -> list[tuple[VFSOperation, VFSExecuteRequest | None]]:
    """A deterministic multi-step schedule covering supported ops."""

    return [
        (
            make_op(VFSOperationKind.MKDIR, operation_id="op:mkdir-docs", path="docs"),
            None,
        ),
        (
            make_op(VFSOperationKind.CREATE, operation_id="op:create-readme", path="docs/readme"),
            VFSExecuteRequest(payload=b"hello-vfs"),
        ),
        (
            make_op(VFSOperationKind.STAT, operation_id="op:stat-readme", path="docs/readme"),
            None,
        ),
        (
            make_op(VFSOperationKind.LIST, operation_id="op:list-docs", path="docs"),
            VFSExecuteRequest(page_size=16),
        ),
        (
            make_op(VFSOperationKind.READ, operation_id="op:read-readme", path="docs/readme"),
            None,
        ),
        (
            make_op(
                VFSOperationKind.RANGE_READ,
                operation_id="op:range-readme",
                path="docs/readme",
                range_start=0,
                range_end=5,
            ),
            None,
        ),
        (
            make_op(VFSOperationKind.STREAM, operation_id="op:stream-readme", path="docs/readme"),
            VFSExecuteRequest(stream_chunk_size=4),
        ),
        (
            make_op(VFSOperationKind.REPLACE, operation_id="op:replace-readme", path="docs/readme"),
            VFSExecuteRequest(payload=b"hello-vfs-v2"),
        ),
        (
            make_op(
                VFSOperationKind.RENAME,
                operation_id="op:rename-readme",
                source_path="docs/readme",
                target_path="docs/README",
            ),
            None,
        ),
        (
            make_op(
                VFSOperationKind.MOVE,
                operation_id="op:move-readme",
                source_path="docs/README",
                target_path="docs/notes",
            ),
            None,
        ),
        (
            make_op(VFSOperationKind.MKDIR, operation_id="op:mkdir-tmp", path="tmp"),
            None,
        ),
        (
            make_op(VFSOperationKind.CREATE, operation_id="op:create-tmp-a", path="tmp/a"),
            VFSExecuteRequest(payload=b"a"),
        ),
        (
            make_op(VFSOperationKind.DELETE, operation_id="op:delete-tmp-a", path="tmp/a"),
            None,
        ),
        (
            make_op(VFSOperationKind.RMDIR, operation_id="op:rmdir-tmp", path="tmp"),
            None,
        ),
        (
            make_op(VFSOperationKind.RESOLVE, operation_id="op:resolve-notes", path="docs/notes"),
            None,
        ),
    ]


# ---------------------------------------------------------------------------
# Schema / surface
# ---------------------------------------------------------------------------


def test_interface_aliases_and_schemas() -> None:
    assert CanonicalVFSService_V1 == CANONICAL_VFS_SERVICE_SCHEMA
    assert CanonicalVFSService_V1.endswith("@1")
    assert VFSReferenceModel_V1 == REFERENCE_MODEL_SCHEMA
    assert VFSReferenceModel_V1.endswith("@1")
    assert CanonicalVFSService.CONTRACT_VERSION == 1
    assert VFSReferenceModel.CONTRACT_VERSION == 1


# ---------------------------------------------------------------------------
# Differential traces — all supported operations
# ---------------------------------------------------------------------------


def test_full_crud_trace_matches_reference_model() -> None:
    service, ref = _pair()
    schedule = _ops_for_full_crud()
    svc_trace = service.run_trace(schedule)
    ref_trace = ref.run_trace(schedule)
    assert traces_match(svc_trace, ref_trace), (
        canonical_trace_step(svc_trace[-1]),
        canonical_trace_step(ref_trace[-1]),
    )
    assert all(step["success"] for step in svc_trace)
    # Rename/move must leave source absent and target present in final namespace.
    final_ns = svc_trace[-1]["namespace"]
    assert "docs/notes" in final_ns
    assert "docs/readme" not in final_ns
    assert "docs/README" not in final_ns


def test_cas_write_trace_matches_reference() -> None:
    service, ref = _pair()
    _seed_both(service, ref, "file", content=b"v1")
    entry = service.storage.get("file")
    assert entry is not None
    schedule = [
        (
            make_op(
                VFSOperationKind.CAS_WRITE,
                operation_id="op:cas-1",
                path="file",
                precondition_version_cid=entry.version_cid,
            ),
            VFSExecuteRequest(payload=b"v2"),
        )
    ]
    # Reference seed produced same version identity (same gen sequence).
    ref_entry = ref.get("file")
    assert ref_entry is not None
    assert ref_entry.version_cid == entry.version_cid
    assert traces_match(service.run_trace(schedule), ref.run_trace(schedule))


def test_cas_precondition_failure_matches_reference() -> None:
    service, ref = _pair()
    _seed_both(service, ref, "file", content=b"v1")
    schedule = [
        (
            make_op(
                VFSOperationKind.CAS_WRITE,
                operation_id="op:cas-bad",
                path="file",
                precondition_version_cid="sha256:" + "0" * 64,
            ),
            VFSExecuteRequest(payload=b"v2"),
        )
    ]
    svc_trace = service.run_trace(schedule)
    ref_trace = ref.run_trace(schedule)
    assert traces_match(svc_trace, ref_trace)
    assert svc_trace[0]["success"] is False
    assert svc_trace[0]["error_code"] == VFSErrorCode.PRECONDITION_FAILED.value
    assert svc_trace[0]["state"] == OperationState.PRECONDITION_FAILED.value


def test_mount_unmount_trace_matches_reference() -> None:
    service, ref = _pair()
    mount = VFSMount(
        mount_id="mount:extra",
        mount_path="mnt",
        backend_id="backend:alt",
        namespace_id="ns:default",
    )
    # mount_path "mnt" is under root "" which always exists.
    schedule = [
        (
            make_op(VFSOperationKind.MOUNT, operation_id="op:mount-1", path="mnt"),
            VFSExecuteRequest(mount=mount),
        ),
        (
            make_op(
                VFSOperationKind.UNMOUNT,
                operation_id="op:unmount-1",
                mount_id="mount:extra",
            ),
            None,
        ),
    ]
    assert traces_match(service.run_trace(schedule), ref.run_trace(schedule))


# ---------------------------------------------------------------------------
# Failure creates no success event
# ---------------------------------------------------------------------------


def test_failure_creates_no_success_event() -> None:
    service = CanonicalVFSService(clock=lambda: 0)
    service.clear_event_log()
    outcome = service.execute(
        make_op(VFSOperationKind.STAT, operation_id="op:missing", path="nope")
    )
    assert outcome.success is False
    assert outcome.result.success is False
    assert isinstance(outcome.result, VFSOperationResult)
    assert isinstance(outcome.result.error, VFSError)
    assert outcome.result.error.code is VFSErrorCode.NOT_FOUND
    kinds = [e.kind for e in outcome.events]
    assert VFSEventKind.SUCCESS not in kinds
    assert VFSEventKind.FAILURE in kinds
    # Global log agrees.
    assert all(e.kind is not VFSEventKind.SUCCESS for e in service.event_log)


def test_failed_create_does_not_mutate_namespace() -> None:
    service = CanonicalVFSService(clock=lambda: 0)
    service.storage.seed("exists", content=b"x")
    before = service.storage.snapshot()
    outcome = service.execute(
        make_op(VFSOperationKind.CREATE, operation_id="op:dup", path="exists"),
        VFSExecuteRequest(payload=b"y"),
    )
    assert not outcome.success
    assert outcome.result.error is not None
    assert outcome.result.error.code is VFSErrorCode.ALREADY_EXISTS
    assert service.storage.snapshot() == before
    assert VFSEventKind.SUCCESS not in [e.kind for e in outcome.events]


# ---------------------------------------------------------------------------
# Rename / move changes state
# ---------------------------------------------------------------------------


def test_rename_changes_namespace_state() -> None:
    service = CanonicalVFSService(clock=lambda: 0)
    service.storage.seed("a", content=b"blob")
    before = service.storage.snapshot()
    assert "a" in before and "b" not in before
    outcome = service.execute(
        make_op(
            VFSOperationKind.RENAME,
            operation_id="op:rename-ab",
            source_path="a",
            target_path="b",
        )
    )
    assert outcome.success
    after = service.storage.snapshot()
    assert "a" not in after
    assert "b" in after
    assert after["b"]["content_cid"] == before["a"]["content_cid"]
    assert after["b"]["version_cid"] != before["a"]["version_cid"]
    assert VFSEventKind.SUCCESS in [e.kind for e in outcome.events]
    # Observed transition records a real version change.
    tr = outcome.result.observed_transition
    assert tr is not None and tr.observed
    assert tr.from_version_cid != tr.to_version_cid


def test_move_directory_tree() -> None:
    service = CanonicalVFSService(clock=lambda: 0)
    service.storage.seed("src/x", content=b"1")
    service.storage.seed("src/y", content=b"2")
    outcome = service.execute(
        make_op(
            VFSOperationKind.MOVE,
            operation_id="op:move-src",
            source_path="src",
            target_path="dst",
        )
    )
    assert outcome.success
    snap = service.storage.snapshot()
    assert "src" not in snap and "src/x" not in snap
    assert "dst" in snap and "dst/x" in snap and "dst/y" in snap


def test_rename_noop_source_target_identical_fails() -> None:
    service = CanonicalVFSService(clock=lambda: 0)
    service.storage.seed("a", content=b"x")
    outcome = service.execute(
        make_op(
            VFSOperationKind.RENAME,
            operation_id="op:rename-same",
            source_path="a",
            target_path="a",
        )
    )
    assert not outcome.success
    assert outcome.result.error is not None
    assert outcome.result.error.code is VFSErrorCode.NO_STATE_CHANGE
    assert "a" in service.storage.snapshot()


# ---------------------------------------------------------------------------
# Stable return / error types
# ---------------------------------------------------------------------------


def test_return_and_error_types_are_stable() -> None:
    service = CanonicalVFSService(clock=lambda: 0)
    ok = service.execute(
        make_op(VFSOperationKind.MKDIR, operation_id="op:mkdir-d", path="d")
    )
    assert isinstance(ok.result, VFSOperationResult)
    assert ok.result.success is True
    assert ok.result.state is OperationState.COMMITTED
    assert ok.result.error is None
    assert ok.result.observed_transition is not None

    bad = service.execute(
        make_op(VFSOperationKind.READ, operation_id="op:read-missing", path="d")
    )
    assert isinstance(bad.result, VFSOperationResult)
    assert bad.result.success is False
    assert isinstance(bad.result.error, VFSError)
    assert isinstance(bad.result.error.code, VFSErrorCode)
    assert bad.result.error.code is VFSErrorCode.IS_DIRECTORY
    # Transport projection shape is stable.
    proj = bad.result.error.as_transport_projection()
    assert proj["error"] is True
    assert proj["code"] == VFSErrorCode.IS_DIRECTORY.value


def test_cross_mount_rename_is_typed_unsupported() -> None:
    service = CanonicalVFSService(clock=lambda: 0)
    service.storage.seed("a", content=b"x")
    other = VFSMount(
        mount_id="mount:other",
        mount_path="other",
        backend_id="backend:other",
        namespace_id="ns:default",
    )
    service.execute(
        make_op(VFSOperationKind.MOUNT, operation_id="op:m1", path="other"),
        VFSExecuteRequest(mount=other),
    )
    outcome = service.execute(
        make_op(
            VFSOperationKind.RENAME,
            operation_id="op:cross",
            source_path="a",
            target_path="other/a",
            source_mount_id="mount:default",
            target_mount_id="mount:other",
        )
    )
    assert not outcome.success
    assert outcome.result.error is not None
    assert outcome.result.error.code in (
        VFSErrorCode.UNSUPPORTED,
        VFSErrorCode.CROSS_BOUNDARY,
    )
    assert outcome.result.state is OperationState.UNSUPPORTED
    # Source untouched.
    assert service.storage.get("a") is not None


def test_unsupported_atomic_boundary_on_request() -> None:
    with pytest.raises(VFSUnsupportedError):
        make_op(
            VFSOperationKind.DELETE,
            operation_id="op:bad-bound",
            path="x",
            atomic_boundary=AtomicBoundary.CROSS_MOUNT,
        )


# ---------------------------------------------------------------------------
# Bounds, cancellation, deadlines, isolation
# ---------------------------------------------------------------------------


def test_payload_bound_rejected() -> None:
    service = CanonicalVFSService(clock=lambda: 0)
    service.execute(make_op(VFSOperationKind.MKDIR, operation_id="op:d", path="d"))
    huge = b"x" * (MAX_PAYLOAD_BYTES + 1)
    outcome = service.execute(
        make_op(VFSOperationKind.CREATE, operation_id="op:huge", path="d/f"),
        VFSExecuteRequest(payload=huge),
    )
    assert not outcome.success
    assert outcome.result.error is not None
    assert "bound" in outcome.result.error.message.lower() or outcome.result.state is OperationState.REJECTED
    assert service.storage.get("d/f") is None


def test_cancellation_before_commit() -> None:
    service = CanonicalVFSService(clock=lambda: 0)
    token = CancellationToken()
    token.cancel()
    outcome = service.execute(
        make_op(VFSOperationKind.MKDIR, operation_id="op:cancel", path="c"),
        VFSExecuteRequest(cancel=token),
    )
    assert not outcome.success
    assert outcome.result.state is OperationState.CANCELLED
    assert VFSEventKind.SUCCESS not in [e.kind for e in outcome.events]
    assert VFSEventKind.CANCELLED in [e.kind for e in outcome.events]
    assert service.storage.get("c") is None


def test_deadline_exceeded() -> None:
    service = CanonicalVFSService(clock=lambda: 1000)
    outcome = service.execute(
        make_op(VFSOperationKind.MKDIR, operation_id="op:dl", path="late"),
        VFSExecuteRequest(deadline_unix_ms=500, now_unix_ms=1000),
    )
    assert not outcome.success
    assert outcome.result.state is OperationState.DEADLINE_EXCEEDED
    assert VFSEventKind.SUCCESS not in [e.kind for e in outcome.events]
    assert service.storage.get("late") is None


def test_side_effects_confined_to_injected_storage() -> None:
    storage = InMemoryVFSStorage()
    service = CanonicalVFSService(storage=storage, clock=lambda: 0)
    other = InMemoryVFSStorage()
    other.seed("foreign", content=b"secret")
    foreign_before = other.snapshot()
    service.execute(
        make_op(VFSOperationKind.CREATE, operation_id="op:local", path="local"),
        VFSExecuteRequest(payload=b"data"),
    )
    assert storage.get("local") is not None
    assert other.snapshot() == foreign_before
    assert other.get("local") is None


def test_idempotency_key_replays_without_second_mutation() -> None:
    service = CanonicalVFSService(clock=lambda: 0)
    op = make_op(
        VFSOperationKind.CREATE,
        operation_id="op:idemp-1",
        path="once",
        idempotency_key="idem:once",
    )
    first = service.execute(op, VFSExecuteRequest(payload=b"1"))
    assert first.success
    second = service.execute(
        make_op(
            VFSOperationKind.CREATE,
            operation_id="op:idemp-2",
            path="once",
            idempotency_key="idem:once",
        ),
        VFSExecuteRequest(payload=b"2"),
    )
    # Cached outcome from first call.
    assert second.success
    assert second.result.resulting_version_cid == first.result.resulting_version_cid
    entry = service.storage.get("once")
    assert entry is not None
    assert entry.content == b"1"


def test_listing_order_and_pagination() -> None:
    service = CanonicalVFSService(clock=lambda: 0)
    for name in ("c", "a", "b"):
        service.storage.seed(name, content=name.encode())
    page1 = service.execute(
        make_op(VFSOperationKind.LIST, operation_id="op:list-1", path=""),
        VFSExecuteRequest(page_size=2),
    )
    assert page1.success
    assert page1.result.listing is not None
    names = [e.name for e in page1.result.listing.entries]
    assert names == sorted(names, key=lambda n: n.encode("utf-8"))
    assert page1.result.listing.has_more is True
    page2 = service.execute(
        make_op(VFSOperationKind.LIST, operation_id="op:list-2", path=""),
        VFSExecuteRequest(page_size=2, cursor=page1.result.listing.next_cursor),
    )
    assert page2.success
    assert page2.result.listing is not None
    # Combined unique names cover a,b,c (root also has only those seeds).
    all_names = names + [e.name for e in page2.result.listing.entries]
    assert set(all_names) >= {"a", "b", "c"}


def test_path_rejection_is_failure_not_success() -> None:
    service = CanonicalVFSService(clock=lambda: 0)
    # VFSOperation normalizes on construction — invalid paths raise there.
    with pytest.raises(Exception):
        make_op(VFSOperationKind.STAT, operation_id="op:trav", path="../secret")


def test_rmdir_not_empty_fails_cleanly() -> None:
    service = CanonicalVFSService(clock=lambda: 0)
    service.storage.seed("dir/f", content=b"x")
    outcome = service.execute(
        make_op(VFSOperationKind.RMDIR, operation_id="op:rmdir-full", path="dir")
    )
    assert not outcome.success
    assert outcome.result.error is not None
    assert outcome.result.error.code is VFSErrorCode.NOT_EMPTY
    assert service.storage.get("dir") is not None


def test_generated_adversarial_failure_then_success_ordering() -> None:
    """Failure then success: failure events never include success."""

    service, ref = _pair()
    schedule = [
        (
            make_op(VFSOperationKind.DELETE, operation_id="op:del-miss", path="missing"),
            None,
        ),
        (
            make_op(VFSOperationKind.MKDIR, operation_id="op:mkdir-ok", path="ok"),
            None,
        ),
        (
            make_op(VFSOperationKind.CREATE, operation_id="op:create-ok", path="ok/f"),
            VFSExecuteRequest(payload=b"z"),
        ),
    ]
    svc_trace = service.run_trace(schedule)
    ref_trace = ref.run_trace(schedule)
    assert traces_match(svc_trace, ref_trace)
    assert svc_trace[0]["success"] is False
    assert "success" not in svc_trace[0]["event_kinds"] or svc_trace[0]["event_kinds"] == [
        "failure"
    ]
    assert svc_trace[0]["event_kinds"] == ["failure"]
    assert svc_trace[1]["success"] is True
    assert "success" in svc_trace[1]["event_kinds"]


def test_reference_model_independent_of_service_storage() -> None:
    """Reference model does not touch a service storage instance."""

    storage = InMemoryVFSStorage()
    storage.seed("only-service", content=b"1")
    ref = VFSReferenceModel()
    ref.seed("only-ref", content=b"2")
    assert storage.get("only-ref") is None
    assert ref.get("only-service") is None
    assert ref.get("only-ref") is not None


def test_stream_chunking_deterministic() -> None:
    service, ref = _pair()
    _seed_both(service, ref, "blob", content=b"abcdefgh")
    schedule = [
        (
            make_op(VFSOperationKind.STREAM, operation_id="op:stream", path="blob"),
            VFSExecuteRequest(stream_chunk_size=3),
        )
    ]
    svc = service.run_trace(schedule)
    rtrace = ref.run_trace(schedule)
    assert traces_match(svc, rtrace)
    assert svc[0]["chunk_count"] == 3  # 3+3+2
    assert svc[0]["data_size"] == 8
