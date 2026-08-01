"""Regression tests for VFS namespace/path/mount/operation contracts (KITA-005).

Acceptance coverage:

* absolute, traversing, and escaping paths under configured roots are rejected;
* Unicode NFC and case-sensitivity policy is defined and enforced;
* symlink policy is explicit (reject / nofollow / follow-within-root);
* listing order, pagination, and stat field semantics are stable;
* atomic boundaries and typed unsupported cross-boundary cases are defined; and
* success is contingent on an observed admitted state transition.
"""

from __future__ import annotations

import unicodedata

import pytest

from ipfs_kit_py.core.operation_contracts import (
    ErrorCategory,
    ErrorCode,
    InconsistentStateError,
    OperationState,
    Retryability,
)
from ipfs_kit_py.core.vfs.contracts import (
    ATOMIC_BOUNDARIES,
    CONTRACT_VERSION,
    MUTATING_OPERATIONS,
    READ_OPERATIONS,
    SCHEMA_VERSION,
    UNSUPPORTED_ATOMIC_BOUNDARIES,
    VFSMount_V1,
    VFSOperation_V1,
    VFSPathPolicy_V1,
    VFSStat_V1,
    AtomicBoundary,
    AtomicityDisposition,
    CasePolicy,
    ListingOrder,
    NormalizedPath,
    ObservedStateTransition,
    PathForm,
    SymlinkPolicy,
    UnicodePolicy,
    UnsupportedReason,
    VFSContractError,
    VFSDirEntry,
    VFSEntryKind,
    VFSError,
    VFSErrorCode,
    VFSListing,
    VFSMount,
    VFSObservationError,
    VFSOperation,
    VFSOperationKind,
    VFSOperationResult,
    VFSPathError,
    VFSPathPolicy,
    VFSPathRejectReason,
    VFSStat,
    VFSUnsupportedError,
    assert_atomic_boundary_supported,
    classify_mount_pair,
    confine_path,
    content_identity,
    evaluate_symlink,
    join_namespace_path,
    make_failure,
    make_mutating_success,
    make_read_success,
    normalize_vfs_path,
    path_error_to_vfs_error,
    path_is_within_root,
    resolve_under_roots,
    unsupported_to_vfs_error,
)


# ---------------------------------------------------------------------------
# Schema / vocabulary
# ---------------------------------------------------------------------------


def test_schema_versions_and_interface_aliases() -> None:
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert VFSPathPolicy_V1.endswith("@1")
    assert VFSOperation_V1.endswith("@1")
    assert VFSStat_V1.endswith("@1")
    assert VFSMount_V1.endswith("@1")


def test_closed_operation_vocabularies() -> None:
    for kind in (
        "stat",
        "list",
        "read",
        "range_read",
        "stream",
        "create",
        "replace",
        "mkdir",
        "rmdir",
        "rename",
        "move",
        "delete",
        "cas_write",
        "mount",
        "unmount",
        "resolve",
    ):
        assert VFSOperationKind(kind)

    assert VFSOperationKind.CREATE in MUTATING_OPERATIONS
    assert VFSOperationKind.RENAME in MUTATING_OPERATIONS
    assert VFSOperationKind.STAT in READ_OPERATIONS
    assert VFSOperationKind.LIST in READ_OPERATIONS
    assert AtomicBoundary.SINGLE_MOUNT in ATOMIC_BOUNDARIES
    assert AtomicBoundary.CROSS_MOUNT in UNSUPPORTED_ATOMIC_BOUNDARIES


# ---------------------------------------------------------------------------
# Path normalization — reject absolute / traversal / escape
# ---------------------------------------------------------------------------


def test_normalize_root_and_relative_paths() -> None:
    root = normalize_vfs_path("")
    assert root.is_root
    assert root.path == ""
    assert root.segments == ()

    rooted = normalize_vfs_path("/docs/readme.md")
    assert rooted.path == "docs/readme.md"
    assert rooted.segments == ("docs", "readme.md")

    relative = normalize_vfs_path("docs/readme.md")
    assert relative.path == "docs/readme.md"


@pytest.mark.parametrize(
    "raw,reason",
    [
        ("../secret", VFSPathRejectReason.TRAVERSAL),
        ("docs/../../etc/passwd", VFSPathRejectReason.TRAVERSAL),
        ("docs/./x", VFSPathRejectReason.DOT_SEGMENT),
        ("./x", VFSPathRejectReason.DOT_SEGMENT),
        ("//absolute", VFSPathRejectReason.ABSOLUTE),
        (r"C:\windows\system32", VFSPathRejectReason.WINDOWS_DRIVE),
        ("C:/windows", VFSPathRejectReason.WINDOWS_DRIVE),
        (r"\\server\share", VFSPathRejectReason.UNC),
        ("//server/share/file", VFSPathRejectReason.UNC),
        ("docs\\file", VFSPathRejectReason.BACKSLASH),
        ("docs/\x00file", VFSPathRejectReason.NUL),
        ("docs/\x01file", VFSPathRejectReason.CONTROL_CHAR),
        ("~/home", VFSPathRejectReason.HOME_EXPANSION),
        ("docs/$HOME/x", VFSPathRejectReason.ENV_EXPANSION),
        ("docs/%2fsecret", VFSPathRejectReason.PERCENT_ENCODED_SEPARATOR),
        ("docs/%2Fsecret", VFSPathRejectReason.PERCENT_ENCODED_SEPARATOR),
        ("docs/%5csecret", VFSPathRejectReason.PERCENT_ENCODED_SEPARATOR),
        ("docs//nested", VFSPathRejectReason.EMPTY_SEGMENT),
    ],
)
def test_normalize_rejects_dangerous_paths(raw: str, reason: VFSPathRejectReason) -> None:
    with pytest.raises(VFSPathError) as excinfo:
        normalize_vfs_path(raw)
    assert excinfo.value.reason is reason


def test_leading_slash_rejected_when_disallowed() -> None:
    policy = VFSPathPolicy(allow_leading_slash=False)
    with pytest.raises(VFSPathError) as excinfo:
        normalize_vfs_path("/docs", policy=policy)
    assert excinfo.value.reason is VFSPathRejectReason.ABSOLUTE


def test_confine_path_under_root() -> None:
    confined = confine_path("a/b", "docs")
    assert confined.root == "docs"
    assert confined.path == "a/b"
    assert path_is_within_root(f"{confined.root}/{confined.path}", "docs")


def test_confine_path_rejects_traversal_escape() -> None:
    with pytest.raises(VFSPathError) as excinfo:
        confine_path("../outside", "docs")
    assert excinfo.value.reason is VFSPathRejectReason.TRAVERSAL


def test_resolve_under_roots_prefers_longest_root() -> None:
    resolved = resolve_under_roots("a/b", roots=("docs", "docs/nested"))
    # Path is relative; both succeed; longest root wins.
    assert resolved.root in ("docs", "docs/nested")
    assert resolved.path == "a/b"


def test_configured_roots_reject_unknown_root() -> None:
    policy = VFSPathPolicy(configured_roots=("docs", "assets"))
    with pytest.raises(VFSPathError) as excinfo:
        normalize_vfs_path("x", policy=policy, root="other")
    assert excinfo.value.reason is VFSPathRejectReason.ROOT_MISMATCH


def test_join_namespace_path_revalidates() -> None:
    joined = join_namespace_path("docs", "a", "b.txt")
    assert joined.path == "docs/a/b.txt"
    with pytest.raises(VFSPathError):
        join_namespace_path("docs", "..", "secret")


# ---------------------------------------------------------------------------
# Unicode / case policy
# ---------------------------------------------------------------------------


def test_unicode_nfc_required() -> None:
    # U+00E9 (é) NFC vs e + combining acute (NFD)
    nfc = "café"
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd
    assert normalize_vfs_path(f"docs/{nfc}").segments[-1] == nfc
    with pytest.raises(VFSPathError) as excinfo:
        normalize_vfs_path(f"docs/{nfd}")
    assert excinfo.value.reason is VFSPathRejectReason.NON_NFC


def test_case_sensitive_identity() -> None:
    policy = VFSPathPolicy.default()
    assert policy.case_policy is CasePolicy.SENSITIVE
    lower = normalize_vfs_path("Docs/Readme.md", policy=policy)
    upper = normalize_vfs_path("docs/readme.md", policy=policy)
    assert lower.path != upper.path
    assert lower.path == "Docs/Readme.md"
    assert upper.path == "docs/readme.md"


def test_case_insensitive_is_typed_unsupported_policy_value() -> None:
    policy = VFSPathPolicy(case_policy=CasePolicy.INSENSITIVE_UNSUPPORTED)
    assert policy.case_policy is CasePolicy.INSENSITIVE_UNSUPPORTED
    # Active normalization remains byte-stable / case-preserving.
    assert normalize_vfs_path("AbC", policy=policy).path == "AbC"


def test_path_policy_round_trip() -> None:
    policy = VFSPathPolicy(
        path_form=PathForm.NAMESPACE_RELATIVE,
        unicode_policy=UnicodePolicy.NFC_REQUIRED,
        symlink_policy=SymlinkPolicy.FOLLOW_WITHIN_ROOT,
        configured_roots=("docs",),
    )
    restored = VFSPathPolicy.from_dict(policy.to_record())
    assert restored.to_record() == policy.to_record()
    assert content_identity(policy.to_record()).startswith("sha256:")


# ---------------------------------------------------------------------------
# Symlink policy
# ---------------------------------------------------------------------------


def test_symlink_reject_policy() -> None:
    decision = evaluate_symlink(
        "target.txt",
        link_path="docs/link",
        root="docs",
        policy=VFSPathPolicy(symlink_policy=SymlinkPolicy.REJECT),
    )
    assert decision.allowed is False
    assert decision.reason is VFSPathRejectReason.SYMLINK_REJECTED


def test_symlink_nofollow_allows_link_without_target_resolution() -> None:
    decision = evaluate_symlink(
        "target.txt",
        link_path="docs/link",
        root="docs",
        policy=VFSPathPolicy(symlink_policy=SymlinkPolicy.NOFOLLOW),
    )
    assert decision.allowed is True
    assert decision.target is None


def test_symlink_follow_within_root() -> None:
    decision = evaluate_symlink(
        "target.txt",
        link_path="docs/sub/link",
        root="docs",
        policy=VFSPathPolicy(symlink_policy=SymlinkPolicy.FOLLOW_WITHIN_ROOT),
    )
    assert decision.allowed is True
    assert decision.target is not None
    assert decision.target.path == "sub/target.txt"
    assert decision.target.root == "docs"


def test_symlink_follow_rejects_escape() -> None:
    decision = evaluate_symlink(
        "../outside",
        link_path="docs/link",
        root="docs",
        policy=VFSPathPolicy(symlink_policy=SymlinkPolicy.FOLLOW_WITHIN_ROOT),
    )
    assert decision.allowed is False
    assert decision.reason in (
        VFSPathRejectReason.SYMLINK_ESCAPE,
        VFSPathRejectReason.TRAVERSAL,
    )


def test_symlink_absolute_target_rejected() -> None:
    decision = evaluate_symlink(
        "/etc/passwd",
        link_path="docs/link",
        root="docs",
        policy=VFSPathPolicy(symlink_policy=SymlinkPolicy.FOLLOW_WITHIN_ROOT),
    )
    assert decision.allowed is False
    assert decision.reason is VFSPathRejectReason.SYMLINK_ESCAPE


def test_symlink_cross_root_typed_unsupported() -> None:
    decision = evaluate_symlink(
        "x",
        link_path="a",
        root="docs",
        policy=VFSPathPolicy(symlink_policy=SymlinkPolicy.FOLLOW_CROSS_ROOT_UNSUPPORTED),
    )
    assert decision.allowed is False
    assert decision.reason is VFSPathRejectReason.SYMLINK_ESCAPE


# ---------------------------------------------------------------------------
# Mount and atomic boundaries
# ---------------------------------------------------------------------------


def test_mount_record_normalizes_path_and_rejects_cross_boundary() -> None:
    mount = VFSMount(
        mount_id="mount:docs",
        mount_path="/docs",
        backend_id="backend:ipfs-primary",
        namespace_id="namespace:tenant-a",
        read_only=False,
        atomic_boundary=AtomicBoundary.SINGLE_MOUNT,
    )
    assert mount.mount_path == "docs"
    assert mount.content_id.startswith("sha256:")
    assert VFSMount.from_dict(mount.to_record()).mount_id == mount.mount_id

    with pytest.raises(VFSUnsupportedError) as excinfo:
        VFSMount(
            mount_id="mount:bad",
            mount_path="x",
            backend_id="backend:x",
            atomic_boundary=AtomicBoundary.CROSS_MOUNT,
        )
    assert excinfo.value.reason is UnsupportedReason.CROSS_MOUNT_ATOMIC


def test_classify_mount_pair_same_and_cross() -> None:
    a = VFSMount(
        mount_id="mount:a",
        mount_path="a",
        backend_id="backend:1",
        namespace_id="ns:1",
    )
    b = VFSMount(
        mount_id="mount:a",
        mount_path="a",
        backend_id="backend:1",
        namespace_id="ns:1",
    )
    boundary, disposition = classify_mount_pair(a, b)
    assert boundary is AtomicBoundary.SINGLE_MOUNT
    assert disposition is AtomicityDisposition.ATOMIC

    c = VFSMount(
        mount_id="mount:c",
        mount_path="c",
        backend_id="backend:1",
        namespace_id="ns:1",
    )
    boundary, disposition = classify_mount_pair(a, c)
    assert boundary is AtomicBoundary.CROSS_MOUNT
    assert disposition is AtomicityDisposition.UNSUPPORTED

    d = VFSMount(
        mount_id="mount:d",
        mount_path="d",
        backend_id="backend:2",
        namespace_id="ns:1",
    )
    boundary, disposition = classify_mount_pair(a, d)
    assert boundary is AtomicBoundary.CROSS_BACKEND
    assert disposition is AtomicityDisposition.UNSUPPORTED


def test_assert_atomic_boundary_supported() -> None:
    assert (
        assert_atomic_boundary_supported(AtomicBoundary.SINGLE_NAMESPACE)
        is AtomicityDisposition.ATOMIC
    )
    with pytest.raises(VFSUnsupportedError) as excinfo:
        assert_atomic_boundary_supported(AtomicBoundary.CROSS_BACKEND)
    assert excinfo.value.reason is UnsupportedReason.CROSS_BACKEND_ATOMIC
    err = unsupported_to_vfs_error(excinfo.value)
    assert err.code is VFSErrorCode.CROSS_BOUNDARY
    assert err.state is OperationState.UNSUPPORTED


def test_mutating_operation_with_cross_mount_boundary_rejected() -> None:
    with pytest.raises(VFSUnsupportedError):
        VFSOperation(
            operation_id="operation:rename-1",
            kind=VFSOperationKind.RENAME,
            source_path="a/x",
            target_path="b/x",
            atomic_boundary=AtomicBoundary.CROSS_MOUNT,
        )


# ---------------------------------------------------------------------------
# Stat and listing semantics
# ---------------------------------------------------------------------------


def test_stat_field_semantics() -> None:
    stat = VFSStat(
        path="/docs/readme.md",
        kind=VFSEntryKind.FILE,
        size_bytes=128,
        mtime_unix_ms=1_700_000_000_000,
        mode=0o644,
        content_cid="sha256:" + ("11" * 32),
        version_cid="sha256:" + ("22" * 32),
        mount_id="mount:docs",
        generation_id="gen:1",
        observed=True,
    )
    assert stat.path == "docs/readme.md"
    assert stat.kind is VFSEntryKind.FILE
    assert VFSStat.from_dict(stat.to_record()).content_cid == stat.content_cid

    with pytest.raises(VFSContractError):
        VFSStat(path="dir", kind=VFSEntryKind.DIRECTORY, size_bytes=5)

    with pytest.raises(VFSContractError):
        VFSStat(path="f", kind=VFSEntryKind.FILE, target="somewhere")


def test_listing_utf8_order_and_pagination() -> None:
    entries = [
        VFSDirEntry(name="zeta", kind=VFSEntryKind.FILE),
        VFSDirEntry(name="alpha", kind=VFSEntryKind.DIRECTORY),
        VFSDirEntry(name="beta", kind=VFSEntryKind.FILE),
    ]
    listing = VFSListing.from_entries(
        "docs",
        entries,
        page_size=2,
        generation_id="gen:1",
        mount_id="mount:docs",
    )
    assert [e.name for e in listing.entries] == ["alpha", "beta"]
    assert listing.order is ListingOrder.UTF8_LEXICOGRAPHIC
    assert listing.has_more is True
    assert listing.next_cursor == "beta"
    assert listing.observed is True

    # Unsorted construction must fail.
    with pytest.raises(VFSContractError):
        VFSListing(
            path="docs",
            entries=(
                VFSDirEntry(name="zeta", kind=VFSEntryKind.FILE),
                VFSDirEntry(name="alpha", kind=VFSEntryKind.FILE),
            ),
        )


def test_listing_duplicate_names_rejected() -> None:
    with pytest.raises(VFSContractError):
        VFSListing(
            path="docs",
            entries=(
                VFSDirEntry(name="a", kind=VFSEntryKind.FILE),
                VFSDirEntry(name="a", kind=VFSEntryKind.DIRECTORY),
            ),
        )


def test_dir_entry_name_must_be_single_segment() -> None:
    with pytest.raises(VFSContractError):
        VFSDirEntry(name="a/b", kind=VFSEntryKind.FILE)
    with pytest.raises(VFSContractError):
        VFSDirEntry(name="..", kind=VFSEntryKind.FILE)


# ---------------------------------------------------------------------------
# Operation / error projection
# ---------------------------------------------------------------------------


def test_operation_rename_requires_paths() -> None:
    with pytest.raises(VFSContractError):
        VFSOperation(
            operation_id="operation:rename",
            kind=VFSOperationKind.RENAME,
            source_path="a",
        )


def test_cas_write_requires_precondition() -> None:
    with pytest.raises(VFSContractError):
        VFSOperation(
            operation_id="operation:cas",
            kind=VFSOperationKind.CAS_WRITE,
            path="docs/x",
        )


def test_path_error_projection() -> None:
    try:
        normalize_vfs_path("../x")
    except VFSPathError as exc:
        err = path_error_to_vfs_error(exc)
    assert err.code is VFSErrorCode.PATH_TRAVERSAL
    assert err.state is OperationState.REJECTED
    projection = err.as_transport_projection()
    assert projection["error"] is True
    assert projection["code"] == VFSErrorCode.PATH_TRAVERSAL.value


# ---------------------------------------------------------------------------
# Success contingent on observed state transition
# ---------------------------------------------------------------------------


def _write_op(**overrides: object) -> VFSOperation:
    base = dict(
        operation_id="operation:write-1",
        kind=VFSOperationKind.CREATE,
        path="docs/readme.md",
        mount_id="mount:docs",
        request_id="request:1",
    )
    base.update(overrides)
    return VFSOperation(**base)  # type: ignore[arg-type]


def test_mutating_success_requires_observed_transition() -> None:
    op = _write_op()
    with pytest.raises(VFSObservationError):
        VFSOperationResult(
            operation_id=op.operation_id,
            kind=op.kind,
            success=True,
            state=OperationState.COMMITTED,
            observed_transition=None,
            resulting_version_cid="sha256:" + ("33" * 32),
        )


def test_mutating_success_requires_observed_flag() -> None:
    op = _write_op()
    with pytest.raises(VFSObservationError):
        VFSOperationResult(
            operation_id=op.operation_id,
            kind=op.kind,
            success=True,
            state=OperationState.COMMITTED,
            observed_transition=ObservedStateTransition(
                from_state=OperationState.PROCESSING,
                to_state=OperationState.COMMITTED,
                observed=False,
                observation_id="obs:1",
                from_version_cid="sha256:" + ("11" * 32),
                to_version_cid="sha256:" + ("22" * 32),
                effect_evidence_ids=("effect:1",),
            ),
            resulting_version_cid="sha256:" + ("22" * 32),
        )


def test_mutating_success_rejects_identical_version_cids() -> None:
    op = _write_op()
    same = "sha256:" + ("aa" * 32)
    with pytest.raises(VFSObservationError):
        VFSOperationResult(
            operation_id=op.operation_id,
            kind=op.kind,
            success=True,
            state=OperationState.COMMITTED,
            observed_transition=ObservedStateTransition(
                from_state=OperationState.PROCESSING,
                to_state=OperationState.COMMITTED,
                observed=True,
                observation_id="obs:1",
                from_version_cid=same,
                to_version_cid=same,
                effect_evidence_ids=("effect:1",),
            ),
            resulting_version_cid=same,
        )


def test_mutating_success_rejects_missing_effect_evidence() -> None:
    op = _write_op()
    with pytest.raises(VFSObservationError):
        VFSOperationResult(
            operation_id=op.operation_id,
            kind=op.kind,
            success=True,
            state=OperationState.COMMITTED,
            observed_transition=ObservedStateTransition(
                from_state=OperationState.PROCESSING,
                to_state=OperationState.COMMITTED,
                observed=True,
                observation_id="obs:1",
                from_version_cid="sha256:" + ("11" * 32),
                to_version_cid="sha256:" + ("22" * 32),
                effect_evidence_ids=(),
            ),
            resulting_version_cid="sha256:" + ("22" * 32),
        )


def test_mutating_success_helper_and_round_trip() -> None:
    op = _write_op()
    result = make_mutating_success(
        op,
        from_version_cid="sha256:" + ("11" * 32),
        to_version_cid="sha256:" + ("22" * 32),
        effect_evidence_ids=("effect:wal-1",),
        observation_id="obs:write-1",
        resulting_content_cid="sha256:" + ("33" * 32),
    )
    assert result.success is True
    assert result.state is OperationState.COMMITTED
    assert result.observed_transition is not None
    assert result.observed_transition.observed is True
    assert result.resulting_version_cid.startswith("sha256:")
    record = result.to_record()
    assert record["success"] is True
    assert record["observed_transition"]["observed"] is True


def test_mutating_success_requires_committed_or_stronger() -> None:
    op = _write_op()
    with pytest.raises(InconsistentStateError):
        VFSOperationResult(
            operation_id=op.operation_id,
            kind=op.kind,
            success=True,
            state=OperationState.ACCEPTED,
            observed_transition=ObservedStateTransition(
                from_state=OperationState.ACCEPTED,
                to_state=OperationState.ACCEPTED,
                observed=True,
                observation_id="obs:1",
                from_version_cid="sha256:" + ("11" * 32),
                to_version_cid="sha256:" + ("22" * 32),
                effect_evidence_ids=("effect:1",),
            ),
            resulting_version_cid="sha256:" + ("22" * 32),
        )


def test_read_success_requires_observation() -> None:
    op = VFSOperation(
        operation_id="operation:stat-1",
        kind=VFSOperationKind.STAT,
        path="docs/readme.md",
        mount_id="mount:docs",
    )
    with pytest.raises(VFSObservationError):
        VFSOperationResult(
            operation_id=op.operation_id,
            kind=op.kind,
            success=True,
            state=OperationState.COMMITTED,
            observed_transition=None,
            stat=VFSStat(
                path=op.path,
                kind=VFSEntryKind.FILE,
                size_bytes=1,
                observed=True,
            ),
        )

    stat = VFSStat(path=op.path, kind=VFSEntryKind.FILE, size_bytes=1, observed=True)
    result = make_read_success(op, observation_id="obs:stat-1", stat=stat)
    assert result.success is True
    assert result.stat is not None
    assert result.observed_transition is not None
    assert result.observed_transition.observed is True


def test_failure_requires_error() -> None:
    op = _write_op()
    with pytest.raises(InconsistentStateError):
        VFSOperationResult(
            operation_id=op.operation_id,
            kind=op.kind,
            success=False,
            state=OperationState.FAILED,
            error=None,
        )

    err = VFSError(
        code=VFSErrorCode.NOT_FOUND,
        message="missing",
        category=ErrorCategory.NOT_FOUND,
        storage_code=ErrorCode.NOT_FOUND,
        retryability=Retryability.NEVER,
        state=OperationState.FAILED,
        path=op.path,
    )
    result = make_failure(op, err)
    assert result.success is False
    assert result.error is not None
    assert result.error.code is VFSErrorCode.NOT_FOUND


def test_illegal_observed_transition_rejected() -> None:
    with pytest.raises(InconsistentStateError):
        ObservedStateTransition(
            from_state=OperationState.FAILED,
            to_state=OperationState.COMMITTED,
            observed=True,
            observation_id="obs:bad",
        )


def test_delete_success_allows_empty_to_version_with_evidence() -> None:
    op = VFSOperation(
        operation_id="operation:delete-1",
        kind=VFSOperationKind.DELETE,
        path="docs/old.md",
        mount_id="mount:docs",
    )
    result = VFSOperationResult(
        operation_id=op.operation_id,
        kind=op.kind,
        success=True,
        state=OperationState.COMMITTED,
        observed_transition=ObservedStateTransition(
            from_state=OperationState.PROCESSING,
            to_state=OperationState.COMMITTED,
            observed=True,
            observation_id="obs:del-1",
            from_version_cid="sha256:" + ("11" * 32),
            to_version_cid="",
            effect_evidence_ids=("effect:delete-1",),
        ),
        path=op.path,
    )
    assert result.success is True


def test_list_success_with_stable_listing() -> None:
    op = VFSOperation(
        operation_id="operation:list-1",
        kind=VFSOperationKind.LIST,
        path="docs",
        mount_id="mount:docs",
    )
    listing = VFSListing.from_entries(
        "docs",
        [
            VFSDirEntry(name="b", kind=VFSEntryKind.FILE),
            VFSDirEntry(name="a", kind=VFSEntryKind.FILE),
        ],
    )
    result = make_read_success(op, observation_id="obs:list-1", listing=listing)
    assert result.listing is not None
    assert [e.name for e in result.listing.entries] == ["a", "b"]


def test_segment_and_path_byte_bounds() -> None:
    policy = VFSPathPolicy(max_segment_bytes=8, max_path_bytes=12)
    with pytest.raises(VFSPathError) as excinfo:
        normalize_vfs_path("toolongseg", policy=policy)
    assert excinfo.value.reason is VFSPathRejectReason.SEGMENT_TOO_LONG

    with pytest.raises(VFSPathError) as excinfo:
        # 4+1+4+1+4 = 14 bytes total > 12
        normalize_vfs_path("abcd/efgh/ijkl", policy=policy)
    assert excinfo.value.reason is VFSPathRejectReason.PATH_TOO_LONG


def test_normalized_path_record_shape() -> None:
    path = normalize_vfs_path("docs/x")
    assert isinstance(path, NormalizedPath)
    record = path.to_record()
    assert record["path"] == "docs/x"
    assert record["is_root"] is False
    assert record["schema"].endswith("@1")
