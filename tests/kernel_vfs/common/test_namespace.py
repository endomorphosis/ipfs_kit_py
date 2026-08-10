"""KVFS-202: Namespace routing, mount table, stable inode, and path policy.

Acceptance coverage:

* longest-prefix mount resolution is deterministic;
* unknown or cross-mount mutation rejects;
* stable inode identity survives restart and same-mount rename;
* root confinement, Unicode normalization, symlink policy, pagination, and
  case policy have executable traces.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from ipfs_kit_py.core.vfs.contracts import (
    AtomicBoundary,
    AtomicityDisposition,
    CasePolicy,
    SymlinkPolicy,
    UnicodePolicy,
    UnsupportedReason,
    VFSDirEntry,
    VFSEntryKind,
    VFSMount,
    VFSPathPolicy,
    VFSPathRejectReason,
)
from ipfs_kit_py.core.vfs.namespace import (
    CONTRACT_VERSION,
    DEFAULT_MOUNT_ID,
    MountTable_V1,
    NamespaceRouter_V1,
    ROOT_INODE,
    SCHEMA_VERSION,
    StableInodeTable_V1,
    MountTable,
    NamespaceError,
    NamespaceErrorCode,
    NamespaceRouter,
    NamespaceTraceKind,
    StableInodeTable,
    durable_node_key,
)

# test file: ipfs_kit_py/tests/kernel_vfs/common/test_namespace.py
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
NAMESPACE_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "core" / "vfs" / "namespace.py"


# ---------------------------------------------------------------------------
# Artifact / schema
# ---------------------------------------------------------------------------


def test_declared_namespace_module_exists() -> None:
    assert NAMESPACE_PATH.is_file()
    assert NAMESPACE_PATH.stat().st_size > 0


def test_schema_versions_and_interface_aliases() -> None:
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert MountTable_V1.endswith("@1")
    assert StableInodeTable_V1.endswith("@1")
    assert NamespaceRouter_V1.endswith("@1")
    assert ROOT_INODE == 1


def test_module_has_no_fusepy_dependency() -> None:
    import ast

    source = NAMESPACE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    banned = frozenset({"fuse", "fusepy"})
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".", 1)[0] not in banned
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module:
                assert module.split(".", 1)[0] not in banned


# ---------------------------------------------------------------------------
# Longest-prefix mount resolution (deterministic)
# ---------------------------------------------------------------------------


def _mount(
    mount_id: str,
    mount_path: str,
    *,
    backend_id: str = "backend:mem",
    namespace_id: str = "ns:default",
    read_only: bool = False,
) -> VFSMount:
    return VFSMount(
        mount_id=mount_id,
        mount_path=mount_path,
        backend_id=backend_id,
        namespace_id=namespace_id,
        read_only=read_only,
        atomic_boundary=AtomicBoundary.SINGLE_MOUNT,
    )


def test_longest_prefix_mount_resolution_is_deterministic() -> None:
    table = MountTable(
        [
            _mount("mount:root", ""),
            _mount("mount:docs", "docs"),
            _mount("mount:docs-nested", "docs/nested"),
            _mount("mount:assets", "assets"),
        ]
    )

    # Nested path selects the longest covering prefix.
    nested = table.resolve("docs/nested/file.txt")
    assert nested.mount_id == "mount:docs-nested"
    assert nested.matched_prefix == "docs/nested"
    assert nested.relative_path == "file.txt"
    assert nested.absolute_path == "docs/nested/file.txt"

    # Mid-level path selects docs, not root.
    mid = table.resolve("docs/readme.md")
    assert mid.mount_id == "mount:docs"
    assert mid.matched_prefix == "docs"
    assert mid.relative_path == "readme.md"

    # Unrelated path falls through to root.
    other = table.resolve("tmp/x")
    assert other.mount_id == "mount:root"
    assert other.matched_prefix == ""
    assert other.relative_path == "tmp/x"

    # Exact mount root resolves with empty relative path.
    at_mount = table.resolve("docs/nested")
    assert at_mount.mount_id == "mount:docs-nested"
    assert at_mount.relative_path == ""

    # Repeat resolution is byte-identical (deterministic).
    again = table.resolve("docs/nested/file.txt")
    assert again.to_record() == nested.to_record()


def test_longest_prefix_tie_break_is_stable_across_insertion_order() -> None:
    # Two mounts cannot share a path; ensure sort order of distinct prefixes
    # does not depend on insertion order.
    first = MountTable(
        [
            _mount("mount:b", "a/b"),
            _mount("mount:a", "a"),
            _mount("mount:root", ""),
        ]
    )
    second = MountTable(
        [
            _mount("mount:root", ""),
            _mount("mount:a", "a"),
            _mount("mount:b", "a/b"),
        ]
    )
    for path in ("a/b/c", "a/x", "z"):
        assert first.resolve(path).to_record() == second.resolve(path).to_record()


def test_mount_path_conflict_rejects() -> None:
    table = MountTable([_mount("mount:a", "docs")])
    with pytest.raises(NamespaceError) as excinfo:
        table.add(_mount("mount:b", "docs"))
    assert excinfo.value.code is NamespaceErrorCode.MOUNT_CONFLICT


def test_explicit_mount_id_must_cover_path() -> None:
    table = MountTable(
        [
            _mount("mount:docs", "docs"),
            _mount("mount:assets", "assets"),
        ]
    )
    ok = table.resolve("docs/x", mount_id="mount:docs")
    assert ok.mount_id == "mount:docs"
    with pytest.raises(NamespaceError) as excinfo:
        table.resolve("assets/x", mount_id="mount:docs")
    assert excinfo.value.code is NamespaceErrorCode.MOUNT_NOT_FOUND


def test_router_resolve_records_trace() -> None:
    router = NamespaceRouter(
        mount_table=MountTable(
            [
                _mount("mount:root", ""),
                _mount("mount:docs", "docs"),
            ]
        )
    )
    resolution = router.resolve("/docs/a")
    assert resolution.mount_id == "mount:docs"
    kinds = router.trace.kinds()
    assert NamespaceTraceKind.RESOLVE_MOUNT.value in kinds
    assert any(step.success and step.mount_id == "mount:docs" for step in router.trace.steps)


# ---------------------------------------------------------------------------
# Unknown / cross-mount mutation rejects
# ---------------------------------------------------------------------------


def test_unknown_mount_id_rejects() -> None:
    table = MountTable.with_default_root()
    with pytest.raises(NamespaceError) as excinfo:
        table.require("mount:missing")
    assert excinfo.value.code is NamespaceErrorCode.UNKNOWN_MOUNT


def test_path_with_no_covering_mount_rejects() -> None:
    table = MountTable([_mount("mount:docs", "docs")])
    with pytest.raises(NamespaceError) as excinfo:
        table.resolve("other/file")
    assert excinfo.value.code in (
        NamespaceErrorCode.MOUNT_NOT_FOUND,
        NamespaceErrorCode.UNKNOWN_MOUNT,
    )


def test_cross_mount_rename_is_rejected() -> None:
    router = NamespaceRouter(
        mount_table=MountTable(
            [
                _mount("mount:a", "a", backend_id="backend:1", namespace_id="ns:1"),
                _mount("mount:b", "b", backend_id="backend:1", namespace_id="ns:1"),
                _mount("mount:root", ""),
            ]
        )
    )
    admission = router.admit_rename("a/x", "b/x")
    assert admission.allowed is False
    assert admission.code is NamespaceErrorCode.CROSS_MOUNT
    assert admission.boundary is AtomicBoundary.CROSS_MOUNT
    assert admission.disposition is AtomicityDisposition.UNSUPPORTED
    assert any(
        step.kind is NamespaceTraceKind.ADMIT_MUTATION and not step.success
        for step in router.trace.steps
    )


def test_cross_backend_rename_is_rejected() -> None:
    router = NamespaceRouter(
        mount_table=MountTable(
            [
                _mount("mount:a", "a", backend_id="backend:1", namespace_id="ns:1"),
                _mount("mount:b", "b", backend_id="backend:2", namespace_id="ns:1"),
            ]
        )
    )
    admission = router.admit_rename("a/x", "b/x")
    assert admission.allowed is False
    assert admission.code is NamespaceErrorCode.CROSS_MOUNT
    assert admission.boundary in (
        AtomicBoundary.CROSS_BACKEND,
        AtomicBoundary.CROSS_MOUNT,
    )


def test_unknown_source_path_mount_rejects_rename() -> None:
    router = NamespaceRouter(
        mount_table=MountTable([_mount("mount:docs", "docs")])
    )
    admission = router.admit_rename("other/x", "docs/x")
    assert admission.allowed is False
    assert admission.code in (
        NamespaceErrorCode.MOUNT_NOT_FOUND,
        NamespaceErrorCode.UNKNOWN_MOUNT,
        NamespaceErrorCode.PATH_POLICY,
    )


def test_read_only_mount_mutation_rejects() -> None:
    router = NamespaceRouter(
        mount_table=MountTable(
            [
                _mount("mount:ro", "ro", read_only=True),
                _mount("mount:root", ""),
            ]
        )
    )
    admission = router.admit_create("ro/file.txt")
    assert admission.allowed is False
    assert admission.code is NamespaceErrorCode.READ_ONLY_MOUNT


def test_same_mount_rename_is_admitted() -> None:
    router = NamespaceRouter(
        mount_table=MountTable(
            [
                _mount("mount:docs", "docs"),
                _mount("mount:root", ""),
            ]
        )
    )
    admission = router.admit_rename("docs/a", "docs/b")
    assert admission.allowed is True
    assert admission.boundary is AtomicBoundary.SINGLE_MOUNT
    assert admission.disposition is AtomicityDisposition.ATOMIC
    assert admission.source is not None
    assert admission.target is not None
    assert admission.source.mount_id == admission.target.mount_id == "mount:docs"


def test_rename_inode_rejects_cross_mount() -> None:
    router = NamespaceRouter(
        mount_table=MountTable(
            [
                _mount("mount:a", "a", backend_id="backend:1", namespace_id="ns:1"),
                _mount("mount:b", "b", backend_id="backend:1", namespace_id="ns:1"),
                _mount("mount:root", ""),
            ]
        )
    )
    router.allocate_inode("a/x", identity="blob-x")
    with pytest.raises(NamespaceError) as excinfo:
        router.rename_inode("a/x", "b/x")
    assert excinfo.value.code is NamespaceErrorCode.CROSS_MOUNT


# ---------------------------------------------------------------------------
# Stable inode identity — restart + same-mount rename
# ---------------------------------------------------------------------------


def test_stable_inode_survives_same_mount_rename() -> None:
    router = NamespaceRouter(
        mount_table=MountTable(
            [
                _mount("mount:docs", "docs"),
                _mount("mount:root", ""),
            ]
        )
    )
    created = router.allocate_inode(
        "docs/old.txt",
        identity="content:blob-1",
        kind=VFSEntryKind.FILE,
    )
    inode_num = created.inode
    node_key = created.node_key
    assert inode_num != ROOT_INODE
    assert node_key.startswith("node:")

    renamed = router.rename_inode("docs/old.txt", "docs/new.txt")
    assert renamed.inode == inode_num
    assert renamed.node_key == node_key
    assert renamed.path == "docs/new.txt"
    assert router.inodes.get_by_path("docs/old.txt") is None
    assert router.lookup_inode("docs/new.txt").inode == inode_num


def test_stable_inode_survives_restart_checkpoint() -> None:
    router = NamespaceRouter(
        mount_table=MountTable(
            [
                _mount("mount:docs", "docs"),
                _mount("mount:root", ""),
            ]
        )
    )
    first = router.allocate_inode("docs/a.txt", identity="id-a")
    second = router.allocate_inode("docs/b.txt", identity="id-b")
    router.rename_inode("docs/a.txt", "docs/a-renamed.txt")

    checkpoint = router.checkpoint()
    assert "content_id" in checkpoint
    assert checkpoint["inode_table"]["next_inode"] > second.inode

    # Simulate process restart: restore from durable checkpoint only.
    restored = NamespaceRouter.restore(checkpoint)
    by_path = restored.inodes.get_by_path("docs/a-renamed.txt")
    assert by_path is not None
    assert by_path.inode == first.inode
    assert by_path.node_key == first.node_key

    by_path_b = restored.inodes.get_by_path("docs/b.txt")
    assert by_path_b is not None
    assert by_path_b.inode == second.inode

    # Re-allocating the same durable identity reuses the inode number.
    again = restored.allocate_inode("docs/a-renamed.txt", identity="id-a")
    assert again.inode == first.inode

    # Mount table also restored — longest-prefix still works.
    assert restored.resolve("docs/x").mount_id == "mount:docs"


def test_durable_node_key_is_path_independent() -> None:
    key1 = durable_node_key(mount_id="mount:docs", identity="blob-1", namespace_id="ns:1")
    key2 = durable_node_key(mount_id="mount:docs", identity="blob-1", namespace_id="ns:1")
    key3 = durable_node_key(mount_id="mount:docs", identity="blob-2", namespace_id="ns:1")
    assert key1 == key2
    assert key1 != key3


def test_inode_table_root_reserved() -> None:
    table = StableInodeTable(root_mount_id=DEFAULT_MOUNT_ID)
    root = table.require_inode(ROOT_INODE)
    assert root.path == ""
    assert root.kind is VFSEntryKind.DIRECTORY
    with pytest.raises(NamespaceError):
        table.forget("")


def test_allocate_idempotent_for_same_node_key() -> None:
    table = StableInodeTable()
    a = table.allocate(
        mount_id=DEFAULT_MOUNT_ID,
        node_key="node:abc",
        path="f1",
        kind=VFSEntryKind.FILE,
    )
    b = table.allocate(
        mount_id=DEFAULT_MOUNT_ID,
        node_key="node:abc",
        path="f1",
        kind=VFSEntryKind.FILE,
    )
    assert a.inode == b.inode


# ---------------------------------------------------------------------------
# Executable policy traces
# ---------------------------------------------------------------------------


def test_root_confinement_trace() -> None:
    router = NamespaceRouter()
    ok, step_ok = router.trace_root_confinement("a/b", "docs")
    assert ok is not None
    assert step_ok.success is True
    assert step_ok.kind is NamespaceTraceKind.CONFINE
    assert step_ok.detail["root"] == "docs"

    bad, step_bad = router.trace_root_confinement("../outside", "docs")
    assert bad is None
    assert step_bad.success is False
    assert step_bad.code in {
        VFSPathRejectReason.TRAVERSAL.value,
        VFSPathRejectReason.ESCAPE.value,
    }


def test_unicode_normalization_trace() -> None:
    router = NamespaceRouter(
        path_policy=VFSPathPolicy(unicode_policy=UnicodePolicy.NFC_REQUIRED)
    )
    nfc = "café"
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd

    ok, step_ok = router.trace_unicode_policy(f"docs/{nfc}")
    assert ok is not None
    assert step_ok.success is True
    assert step_ok.kind is NamespaceTraceKind.UNICODE

    bad, step_bad = router.trace_unicode_policy(f"docs/{nfd}")
    assert bad is None
    assert step_bad.success is False
    assert step_bad.code in (
        NamespaceErrorCode.UNICODE_POLICY.value,
        VFSPathRejectReason.NON_NFC.value,
    )


def test_case_policy_trace() -> None:
    router = NamespaceRouter(
        path_policy=VFSPathPolicy(case_policy=CasePolicy.SENSITIVE)
    )
    # Distinct case spellings are distinct identities under sensitive policy.
    step = router.trace_case_policy("Docs/Readme", "docs/readme")
    assert step.success is True
    assert step.detail["identity_equal"] is False
    assert step.detail["case_policy"] == CasePolicy.SENSITIVE.value

    # Requesting case-fold comparison is typed unsupported.
    fold = router.trace_case_policy(
        "Docs/Readme", "docs/readme", request_case_fold=True
    )
    assert fold.success is False
    assert fold.code == NamespaceErrorCode.CASE_POLICY.value
    assert fold.detail["reason"] == UnsupportedReason.CASE_INSENSITIVE.value


def test_symlink_policy_trace() -> None:
    reject_router = NamespaceRouter(
        path_policy=VFSPathPolicy(symlink_policy=SymlinkPolicy.REJECT)
    )
    decision, step = reject_router.trace_symlink_policy(
        "target.txt", link_path="docs/link", root="docs"
    )
    assert decision.allowed is False
    assert step.success is False
    assert step.kind is NamespaceTraceKind.SYMLINK
    assert step.code == VFSPathRejectReason.SYMLINK_REJECTED.value

    follow_router = NamespaceRouter(
        path_policy=VFSPathPolicy(symlink_policy=SymlinkPolicy.FOLLOW_WITHIN_ROOT)
    )
    decision2, step2 = follow_router.trace_symlink_policy(
        "target.txt", link_path="docs/sub/link", root="docs"
    )
    assert decision2.allowed is True
    assert step2.success is True

    escape, step3 = follow_router.trace_symlink_policy(
        "../outside", link_path="docs/link", root="docs"
    )
    assert escape.allowed is False
    assert step3.success is False


def test_pagination_trace_is_stable_and_resumable() -> None:
    router = NamespaceRouter()
    entries = (
        VFSDirEntry(name="c", kind=VFSEntryKind.FILE),
        VFSDirEntry(name="a", kind=VFSEntryKind.FILE),
        VFSDirEntry(name="b", kind=VFSEntryKind.FILE),
        VFSDirEntry(name="d", kind=VFSEntryKind.DIRECTORY),
    )
    page1 = router.paginate("docs", entries, page_size=2)
    assert [e.name for e in page1.entries] == ["a", "b"]
    assert page1.has_more is True
    assert page1.next_cursor == "b"
    assert page1.order.value == "utf8_lexicographic"

    page2 = router.paginate("docs", entries, page_size=2, cursor=page1.next_cursor)
    assert [e.name for e in page2.entries] == ["c", "d"]
    assert page2.has_more is False
    assert page2.next_cursor == ""

    paginate_steps = [
        s for s in router.trace.steps if s.kind is NamespaceTraceKind.PAGINATE
    ]
    assert len(paginate_steps) >= 2
    assert all(s.success for s in paginate_steps)

    with pytest.raises(NamespaceError) as excinfo:
        router.paginate("docs", entries, page_size=2, cursor="missing")
    assert excinfo.value.code is NamespaceErrorCode.PAGINATION


def test_policy_trace_suite_covers_all_required_kinds() -> None:
    router = NamespaceRouter(
        path_policy=VFSPathPolicy(
            unicode_policy=UnicodePolicy.NFC_REQUIRED,
            case_policy=CasePolicy.SENSITIVE,
            symlink_policy=SymlinkPolicy.REJECT,
        )
    )
    records = router.run_policy_trace_suite()
    assert records
    kinds = {record["kind"] for record in records}
    for required in (
        NamespaceTraceKind.CONFINE.value,
        NamespaceTraceKind.UNICODE.value,
        NamespaceTraceKind.CASE.value,
        NamespaceTraceKind.SYMLINK.value,
        NamespaceTraceKind.PAGINATE.value,
    ):
        assert required in kinds, f"missing executable trace kind {required}"

    # At least one reject and one success for confinement / unicode / case.
    assert any(
        r["kind"] == NamespaceTraceKind.CONFINE.value and r["success"] for r in records
    )
    assert any(
        r["kind"] == NamespaceTraceKind.CONFINE.value and not r["success"] for r in records
    )
    assert any(
        r["kind"] == NamespaceTraceKind.UNICODE.value and r["success"] for r in records
    )
    assert any(
        r["kind"] == NamespaceTraceKind.CASE.value and not r["success"] for r in records
    )
    assert any(
        r["kind"] == NamespaceTraceKind.PAGINATE.value and r["success"] for r in records
    )


def test_normalize_rejects_traversal_with_path_policy_trace() -> None:
    router = NamespaceRouter()
    with pytest.raises(NamespaceError) as excinfo:
        router.normalize("../secret")
    assert excinfo.value.code is NamespaceErrorCode.PATH_POLICY
    assert any(
        step.kind is NamespaceTraceKind.NORMALIZE and not step.success
        for step in router.trace.steps
    )


def test_mount_table_and_router_round_trip_records() -> None:
    table = MountTable(
        [
            _mount("mount:root", ""),
            _mount("mount:docs", "docs"),
        ]
    )
    restored = MountTable.from_dict(table.to_record())
    assert [m.mount_id for m in restored.mounts()] == [m.mount_id for m in table.mounts()]

    router = NamespaceRouter(mount_table=table)
    router.allocate_inode("docs/x", identity="x")
    payload = router.to_record()
    assert payload["schema"] == NamespaceRouter_V1
    assert payload["mount_table"]["schema"] == MountTable_V1
    assert payload["inode_table"]["schema"] == StableInodeTable_V1
