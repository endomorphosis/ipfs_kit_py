"""KVFS-600: Windows namespace, case/name, permission, and open/delete semantics.

Acceptance coverage:

* collision-safe lookup preserves display spelling;
* ambiguous folds, reserved device names, trailing dots/spaces, invalid UTF
  conversion and traversal reject fail-closed;
* case-only rename, drive/directory roots, delete/share/rename while open,
  uid/gid/mode projection, ACL/ADS/reparse/symlink limits and errno behavior
  are executable.

Conflict policy: pure Windows policy/projection tests only; no WinFsp load,
no mount, no fusepy import.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import pytest

from ipfs_kit_py.core.vfs.host_contracts import HostErrno, HostPlatform
from ipfs_kit_py.kernel_vfs import windows_semantics as ws


# ---------------------------------------------------------------------------
# Import inertness
# ---------------------------------------------------------------------------


def test_module_import_is_inert() -> None:
    """Importing windows_semantics must not pull fusepy or load WinFsp."""

    # The module under test must not hard-import or load native WinFsp/fusepy.
    source = Path(ws.__file__).read_text(encoding="utf-8")
    assert "import fuse" not in source
    assert "import fusepy" not in source
    assert "from fuse" not in source
    assert "from fusepy" not in source
    assert "LoadLibrary" not in source
    assert "ctypes" not in source
    assert ws.TASK_ID == "KVFS-600"
    assert ws.CONTRACT_VERSION == 1
    assert ws.WindowsNamespacePolicy_V1.endswith("@1")
    # Identity schemas are versioned for plan aliases.
    assert ws.WindowsOpenShareTable_V1.endswith("@1")
    assert ws.WindowsAttrProjector_V1.endswith("@1")


# ---------------------------------------------------------------------------
# Name policy: reserved devices, trailing dots/spaces, invalid chars
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "CON",
        "con",
        "Prn",
        "AUX",
        "NUL",
        "COM1",
        "COM9",
        "LPT1",
        "LPT9",
        "CON.txt",
        "nul.log",
        "COM3:",
    ],
)
def test_reserved_device_names_reject(name: str) -> None:
    result = ws.validate_windows_component(name)
    assert result.ok is False
    assert result.reason is ws.WindowsNameRejectReason.RESERVED_DEVICE
    assert result.errno is HostErrno.EINVAL
    assert ws.is_reserved_device_name(name) is True

    policy = ws.WindowsSemanticsPolicy()
    traced = policy.validate_name(name)
    assert traced.ok is False
    steps = policy.trace.steps()
    assert steps[-1].kind is ws.WindowsTraceKind.NAME_VALIDATE
    assert steps[-1].success is False


@pytest.mark.parametrize("name", ["file.", "dir ", "name. ", "trailing..."])
def test_trailing_dots_and_spaces_reject(name: str) -> None:
    assert ws.has_trailing_dot_or_space(name) is True
    result = ws.validate_windows_component(name)
    assert result.ok is False
    assert result.reason is ws.WindowsNameRejectReason.TRAILING_DOT_SPACE
    assert result.errno is HostErrno.EINVAL


@pytest.mark.parametrize("name", ["ok.txt", "ReadMe", "café", "file_name-1"])
def test_valid_names_preserve_display_spelling(name: str) -> None:
    result = ws.validate_windows_component(name)
    assert result.ok is True
    assert result.display_spelling == name
    assert result.lookup_identity == ws.fold_windows_identity(name)
    assert result.detail.get("display_spelling_preserved") is True


@pytest.mark.parametrize("name", ["a<b", "x:y", "q|w", "star*", "q?z", "a\\b", "a/b"])
def test_invalid_filename_chars_reject(name: str) -> None:
    result = ws.validate_windows_component(name)
    assert result.ok is False
    assert result.reason is ws.WindowsNameRejectReason.INVALID_CHAR


# ---------------------------------------------------------------------------
# UTF conversion and traversal
# ---------------------------------------------------------------------------


def test_invalid_utf16_surrogate_rejects() -> None:
    lone = "bad\ud800name"
    assert ws.is_valid_utf16_text(lone) is False
    assert ws.is_valid_utf8_text(lone) is False
    result = ws.validate_windows_component(lone)
    assert result.ok is False
    assert result.reason in (
        ws.WindowsNameRejectReason.SURROGATE,
        ws.WindowsNameRejectReason.INVALID_UTF8,
        ws.WindowsNameRejectReason.INVALID_UTF16,
    )
    with pytest.raises(ws.WindowsSemanticsError) as ei:
        ws.validate_utf_conversion(lone)
    assert ei.value.code is ws.WindowsSemanticsErrorCode.UTF_CONVERSION
    assert ei.value.errno is HostErrno.EINVAL


def test_valid_utf_roundtrip() -> None:
    text = "ドキュメント.txt"
    assert ws.is_valid_utf8_text(text) is True
    assert ws.is_valid_utf16_text(text) is True
    ws.validate_utf_conversion(text)  # does not raise
    result = ws.validate_windows_component(text)
    assert result.ok is True
    assert result.display_spelling == text


def test_non_nfc_rejects_when_required() -> None:
    nfc = "café"
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd
    ok = ws.validate_windows_component(nfc, require_nfc=True)
    assert ok.ok is True
    bad = ws.validate_windows_component(nfd, require_nfc=True)
    assert bad.ok is False
    assert bad.reason is ws.WindowsNameRejectReason.NON_NFC


def test_path_traversal_rejects() -> None:
    with pytest.raises(ws.WindowsSemanticsError) as ei:
        ws.normalize_windows_namespace_path("../secret")
    assert ei.value.code is ws.WindowsSemanticsErrorCode.TRAVERSAL
    assert ei.value.errno is HostErrno.EPERM
    assert ei.value.reason is ws.WindowsNameRejectReason.TRAVERSAL

    with pytest.raises(ws.WindowsSemanticsError) as ei2:
        ws.normalize_windows_namespace_path("a/../../b")
    assert ei2.value.code is ws.WindowsSemanticsErrorCode.TRAVERSAL

    policy = ws.WindowsSemanticsPolicy()
    with pytest.raises(ws.WindowsSemanticsError):
        policy.normalize_path("docs/../../../etc/passwd")
    assert any(s.kind is ws.WindowsTraceKind.TRAVERSAL for s in policy.trace.steps())


def test_backslash_and_absolute_forms_reject() -> None:
    with pytest.raises(ws.WindowsSemanticsError) as ei:
        ws.normalize_windows_namespace_path("a\\b")
    assert ei.value.reason is ws.WindowsNameRejectReason.BACKSLASH

    with pytest.raises(ws.WindowsSemanticsError) as ei2:
        ws.normalize_windows_namespace_path("C:\\Windows")
    assert ei2.value.reason is ws.WindowsNameRejectReason.ABSOLUTE


# ---------------------------------------------------------------------------
# Collision-safe lookup preserves display spelling
# ---------------------------------------------------------------------------


def test_lookup_preserves_display_spelling() -> None:
    ns = ws.WindowsNamespace(case_mode=ws.WindowsCaseMode.INSENSITIVE)
    created = ns.create("ReadMe.txt", mode=0o100644, size=12)
    assert created.display_spelling == "ReadMe.txt"

    # Lookup via different case returns original display spelling.
    hit = ns.lookup("readme.txt")
    assert hit.found is True
    assert hit.display_spelling == "ReadMe.txt"
    assert hit.lookup_identity == ws.fold_windows_identity("ReadMe.txt")
    assert hit.entry is not None
    assert hit.entry.inode == created.inode
    assert hit.to_record()["display_spelling_preserved"] is True

    # Trace is executable.
    kinds = ns.trace.kinds()
    assert "create" in kinds
    assert "lookup" in kinds


def test_ambiguous_case_fold_collision_fails_closed() -> None:
    ns = ws.WindowsNamespace(case_mode=ws.WindowsCaseMode.INSENSITIVE)
    ns.create("File.txt")
    with pytest.raises(ws.WindowsSemanticsError) as ei:
        ns.create("file.TXT")
    assert ei.value.code is ws.WindowsSemanticsErrorCode.CASE_COLLISION
    assert ei.value.errno is HostErrno.EEXIST
    assert ei.value.reason is ws.WindowsNameRejectReason.CASE_FOLD_COLLISION
    assert ei.value.detail.get("fail_closed") is True
    assert ei.value.detail.get("existing_display") == "File.txt"

    # Original entry unchanged.
    hit = ns.lookup("FILE.txt")
    assert hit.found is True
    assert hit.display_spelling == "File.txt"

    collision_steps = [
        s for s in ns.trace.steps() if s.kind is ws.WindowsTraceKind.CASE_COLLISION
    ]
    assert collision_steps
    assert collision_steps[-1].success is False


def test_exact_duplicate_create_is_already_exists() -> None:
    ns = ws.WindowsNamespace()
    ns.create("same.txt")
    with pytest.raises(ws.WindowsSemanticsError) as ei:
        ns.create("same.txt")
    assert ei.value.code is ws.WindowsSemanticsErrorCode.ALREADY_EXISTS
    assert ei.value.errno is HostErrno.EEXIST


def test_case_sensitive_volume_allows_distinct_case() -> None:
    ns = ws.WindowsNamespace(case_mode=ws.WindowsCaseMode.SENSITIVE)
    a = ns.create("File.txt")
    b = ns.create("file.txt")
    assert a.display_spelling == "File.txt"
    assert b.display_spelling == "file.txt"
    assert ns.lookup("File.txt").entry is not None
    assert ns.lookup("file.txt").entry is not None
    assert ns.lookup("File.txt").display_spelling == "File.txt"


# ---------------------------------------------------------------------------
# Case-only rename
# ---------------------------------------------------------------------------


def test_case_only_rename_updates_display_spelling() -> None:
    ns = ws.WindowsNamespace(case_mode=ws.WindowsCaseMode.INSENSITIVE)
    ns.create("ReadMe")
    entry = ns.case_only_rename("ReadMe", "readme")
    assert entry.display_spelling == "readme"
    assert entry.lookup_identity == ws.fold_windows_identity("ReadMe")

    hit = ns.lookup("README")
    assert hit.found is True
    assert hit.display_spelling == "readme"

    steps = [s for s in ns.trace.steps() if s.kind is ws.WindowsTraceKind.CASE_ONLY_RENAME]
    assert steps and steps[-1].success is True
    assert steps[-1].detail.get("case_only") is True


def test_case_only_rename_rejects_identity_change() -> None:
    ns = ws.WindowsNamespace(case_mode=ws.WindowsCaseMode.INSENSITIVE)
    ns.create("alpha")
    with pytest.raises(ws.WindowsSemanticsError) as ei:
        ns.case_only_rename("alpha", "beta")
    assert ei.value.code is ws.WindowsSemanticsErrorCode.INVALID_ARGUMENT
    assert ei.value.errno is HostErrno.EINVAL


def test_rename_dispatches_case_only() -> None:
    ns = ws.WindowsNamespace(case_mode=ws.WindowsCaseMode.INSENSITIVE)
    ns.create("Docs")
    entry = ns.rename("Docs", "docs")
    assert entry.display_spelling == "docs"


# ---------------------------------------------------------------------------
# Drive / directory mount roots
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,canonical",
    [
        ("Z:", "Z:"),
        ("z:", "Z:"),
        ("C:\\", "C:"),
        ("d:", "D:"),
    ],
)
def test_drive_letter_roots(raw: str, canonical: str) -> None:
    root = ws.validate_drive_letter_root(raw)
    assert root.kind is ws.MountRootKind.DRIVE_LETTER
    assert root.canonical == canonical


@pytest.mark.parametrize("raw", ["", "ZZ:", "1:", "C:foo", "relative", "Z"])
def test_invalid_drive_letter_roots(raw: str) -> None:
    with pytest.raises(ws.WindowsSemanticsError) as ei:
        ws.validate_drive_letter_root(raw)
    assert ei.value.code is ws.WindowsSemanticsErrorCode.MOUNT_ROOT
    assert ei.value.errno is HostErrno.EINVAL


@pytest.mark.parametrize(
    "raw",
    [
        r"C:\Mount\ipfs",
        r"D:\data\winfsp",
        "/mnt/winfsp",
        "/var/run/kvfs-win",
    ],
)
def test_directory_roots(raw: str) -> None:
    root = ws.validate_directory_root(raw)
    assert root.kind is ws.MountRootKind.DIRECTORY
    assert root.canonical


@pytest.mark.parametrize(
    "raw",
    [".", "..", "relative/path", "../escape", "Z:"],
)
def test_invalid_directory_roots(raw: str) -> None:
    with pytest.raises(ws.WindowsSemanticsError) as ei:
        ws.validate_directory_root(raw)
    assert ei.value.code in (
        ws.WindowsSemanticsErrorCode.MOUNT_ROOT,
        ws.WindowsSemanticsErrorCode.TRAVERSAL,
    )


def test_mount_root_auto_detect_and_trace() -> None:
    policy = ws.WindowsSemanticsPolicy()
    drive = policy.validate_mount_root("Y:")
    assert drive.kind is ws.MountRootKind.DRIVE_LETTER
    directory = policy.validate_mount_root("/mnt/kvfs")
    assert directory.kind is ws.MountRootKind.DIRECTORY
    kinds = policy.trace.kinds()
    assert kinds.count("mount_root") == 2


# ---------------------------------------------------------------------------
# Delete / share / rename while open
# ---------------------------------------------------------------------------


def test_share_violation_on_conflicting_open() -> None:
    table = ws.WindowsOpenShareTable()
    h1 = table.open(
        "ns/file.bin",
        access=ws.WindowsAccess.READ | ws.WindowsAccess.WRITE,
        share=ws.WindowsShareMode.READ,  # does not share WRITE
    )
    assert h1.handle_id == 1

    with pytest.raises(ws.WindowsSemanticsError) as ei:
        table.open(
            "ns/file.bin",
            access=ws.WindowsAccess.WRITE,
            share=ws.WindowsShareMode.ALL,
        )
    assert ei.value.code is ws.WindowsSemanticsErrorCode.SHARE_VIOLATION
    assert ei.value.errno is HostErrno.EACCES
    assert ei.value.reason is ws.WindowsNameRejectReason.SHARE_VIOLATION


def test_compatible_shared_opens_succeed() -> None:
    table = ws.WindowsOpenShareTable()
    a = table.open(
        "ns/shared.txt",
        access=ws.WindowsAccess.READ,
        share=ws.WindowsShareMode.READ | ws.WindowsShareMode.WRITE | ws.WindowsShareMode.DELETE,
    )
    b = table.open(
        "ns/shared.txt",
        access=ws.WindowsAccess.READ,
        share=ws.WindowsShareMode.READ | ws.WindowsShareMode.DELETE,
    )
    assert table.open_count("ns/shared.txt") == 2
    table.release(a.handle_id)
    table.release(b.handle_id)
    assert table.open_count("ns/shared.txt") == 0


def test_delete_while_open_requires_share_delete() -> None:
    policy = ws.WindowsSemanticsPolicy()
    policy.create("locked.txt", size=4)
    policy.open(
        "locked.txt",
        access=ws.WindowsAccess.READ,
        share=ws.WindowsShareMode.READ,  # no DELETE share
    )
    with pytest.raises(ws.WindowsSemanticsError) as ei:
        policy.unlink("locked.txt")
    assert ei.value.code is ws.WindowsSemanticsErrorCode.SHARE_VIOLATION
    assert ei.value.errno is HostErrno.EACCES
    # Still present.
    assert policy.lookup("locked.txt").found is True


def test_delete_while_open_with_share_delete_marks_pending() -> None:
    policy = ws.WindowsSemanticsPolicy()
    policy.create("open-del.txt", size=8)
    handle = policy.open(
        "open-del.txt",
        access=ws.WindowsAccess.READ | ws.WindowsAccess.DELETE,
        share=ws.WindowsShareMode.ALL,
    )
    detail = policy.unlink("open-del.txt")
    assert detail["delete_pending"] is True
    assert detail["removed"] is False
    assert detail["open_count"] == 1
    assert handle.released is False
    # Handle remains valid; entry flagged delete-pending.
    entry = policy.lookup("open-del.txt").entry
    assert entry is not None
    assert entry.delete_pending is True
    assert policy.open_table.open_handles("open-del.txt")[0].delete_pending is True

    # Release is executable and reports final close.
    rel = policy.open_table.release(handle.handle_id)
    assert rel["final_close"] is True


def test_rename_while_open_requires_share_delete() -> None:
    policy = ws.WindowsSemanticsPolicy()
    policy.create("src.txt")
    policy.create("other.txt")  # ensure target form is free / distinct
    policy.open(
        "src.txt",
        access=ws.WindowsAccess.READ,
        share=ws.WindowsShareMode.READ,  # no DELETE
    )
    with pytest.raises(ws.WindowsSemanticsError) as ei:
        policy.rename("src.txt", "renamed.txt")
    assert ei.value.code is ws.WindowsSemanticsErrorCode.SHARE_VIOLATION
    assert ei.value.errno is HostErrno.EACCES
    assert policy.lookup("src.txt").found is True


def test_rename_while_open_with_share_delete_updates_handle_path() -> None:
    policy = ws.WindowsSemanticsPolicy()
    policy.create("old-name.txt")
    handle = policy.open(
        "old-name.txt",
        access=ws.WindowsAccess.READ,
        share=ws.WindowsShareMode.ALL,
    )
    entry = policy.rename("old-name.txt", "new-name.txt")
    assert entry.display_spelling == "new-name.txt"
    assert handle.path == "new-name.txt"
    assert policy.open_table.open_count("new-name.txt") == 1
    assert policy.open_table.open_count("old-name.txt") == 0
    assert policy.lookup("new-name.txt").found is True
    assert policy.lookup("old-name.txt").found is False


# ---------------------------------------------------------------------------
# uid/gid/mode projection
# ---------------------------------------------------------------------------


def test_uid_gid_mode_projection() -> None:
    policy = ws.WindowsSemanticsPolicy(
        uid_gid=ws.UidGidProjection(
            kind=ws.UidGidProjectionKind.FIXED,
            fixed_uid=1000,
            fixed_gid=1000,
        )
    )
    policy.create("proj.txt", mode=0o100444, size=32, uid=1000, gid=1000)
    projected = policy.project_attrs("proj.txt")
    assert projected.uid == 1000
    assert projected.gid == 1000
    assert projected.mode == 0o100444
    assert projected.readonly is True
    assert projected.file_attributes & ws.FILE_ATTRIBUTE_READONLY
    assert not (projected.file_attributes & ws.FILE_ATTRIBUTE_DIRECTORY)
    assert projected.acl_supported is False
    assert projected.ads_supported is False
    assert projected.reparse_supported is False
    assert projected.symlink_supported is False
    assert projected.display_spelling == "proj.txt"

    policy.create("dirA", is_directory=True, mode=0o040755)
    dproj = policy.project_attrs("dirA")
    assert dproj.is_directory is True
    assert dproj.file_attributes & ws.FILE_ATTRIBUTE_DIRECTORY
    assert dproj.nlink == 2


def test_uid_gid_caller_and_root_policies() -> None:
    caller = ws.UidGidProjection(kind=ws.UidGidProjectionKind.CALLER)
    assert caller.resolve(caller_uid=42, caller_gid=7) == (42, 7)
    root = ws.UidGidProjection(kind=ws.UidGidProjectionKind.ROOT)
    assert root.resolve(stored_uid=9, stored_gid=9, caller_uid=1, caller_gid=1) == (0, 0)


def test_mode_to_file_attributes_writable_file() -> None:
    attrs = ws.mode_to_file_attributes(0o100644, is_directory=False)
    assert attrs & ws.FILE_ATTRIBUTE_NORMAL
    assert not (attrs & ws.FILE_ATTRIBUTE_READONLY)


# ---------------------------------------------------------------------------
# ACL / ADS / reparse / symlink limits and errno behavior
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "feature",
    [
        ws.WindowsFeature.ACL,
        ws.WindowsFeature.ADS,
        ws.WindowsFeature.REPARSE,
        ws.WindowsFeature.SYMLINK,
        ws.WindowsFeature.HARDLINK,
        ws.WindowsFeature.SECURITY_DESCRIPTOR_SET,
        ws.WindowsFeature.EXTENDED_ATTRIBUTES,
    ],
)
def test_feature_limits_are_explicit_unsupported(feature: ws.WindowsFeature) -> None:
    result = ws.feature_limit(feature)
    assert result.supported is False
    assert result.errno is HostErrno.EOPNOTSUPP
    assert result.errno_number == ws.windows_errno_number(HostErrno.EOPNOTSUPP)

    with pytest.raises(ws.WindowsSemanticsError) as ei:
        ws.reject_unsupported_feature(feature)
    assert ei.value.code is ws.WindowsSemanticsErrorCode.FEATURE_UNSUPPORTED
    assert ei.value.errno is HostErrno.EOPNOTSUPP
    assert ei.value.reason is ws.WindowsNameRejectReason.FEATURE_UNSUPPORTED


def test_policy_feature_trace_and_errno_behavior() -> None:
    policy = ws.WindowsSemanticsPolicy()
    feat = policy.feature(ws.WindowsFeature.ADS)
    assert feat.supported is False
    assert any(s.kind is ws.WindowsTraceKind.FEATURE_LIMIT for s in policy.trace.steps())

    for err in (
        HostErrno.EINVAL,
        HostErrno.EEXIST,
        HostErrno.EACCES,
        HostErrno.ENOENT,
        HostErrno.EOPNOTSUPP,
        HostErrno.ENOSYS,
        HostErrno.EPERM,
    ):
        record = policy.errno_behavior(err)
        assert record["errno"] == err.value
        assert record["errno_number"] == ws.windows_errno_number(err)
        assert record["platform"] == HostPlatform.WINDOWS.value
        assert isinstance(record["errno_number"], int)


def test_reason_to_errno_mapping_is_stable() -> None:
    assert ws.reason_to_errno(ws.WindowsNameRejectReason.RESERVED_DEVICE) is HostErrno.EINVAL
    assert ws.reason_to_errno(ws.WindowsNameRejectReason.CASE_FOLD_COLLISION) is HostErrno.EEXIST
    assert ws.reason_to_errno(ws.WindowsNameRejectReason.TRAVERSAL) is HostErrno.EPERM
    assert ws.reason_to_errno(ws.WindowsNameRejectReason.SHARE_VIOLATION) is HostErrno.EACCES
    assert (
        ws.reason_to_errno(ws.WindowsNameRejectReason.FEATURE_UNSUPPORTED)
        is HostErrno.EOPNOTSUPP
    )


def test_error_to_record_includes_windows_errno_number() -> None:
    err = ws.WindowsSemanticsError(
        "collision",
        code=ws.WindowsSemanticsErrorCode.CASE_COLLISION,
        errno=HostErrno.EEXIST,
        reason=ws.WindowsNameRejectReason.CASE_FOLD_COLLISION,
        path="file.TXT",
    )
    record = err.to_record()
    assert record["errno"] == "EEXIST"
    assert record["errno_number"] == ws.windows_errno_number(HostErrno.EEXIST)
    assert record["reason"] == "case_fold_collision"


# ---------------------------------------------------------------------------
# Nested paths, directories, and facade integration
# ---------------------------------------------------------------------------


def test_nested_create_lookup_and_list() -> None:
    policy = ws.WindowsSemanticsPolicy()
    policy.create("docs", is_directory=True)
    policy.create("docs/ReadMe.md", size=100)
    hit = policy.lookup("docs/readme.md")
    assert hit.found is True
    assert hit.display_spelling == "ReadMe.md"

    entries = policy.namespace.list_dir("docs")
    names = {e.display_spelling for e in entries}
    assert "ReadMe.md" in names


def test_unlink_without_open_removes_immediately() -> None:
    policy = ws.WindowsSemanticsPolicy()
    policy.create("gone.txt")
    detail = policy.unlink("gone.txt")
    assert detail["removed"] is True
    assert detail["delete_pending"] is False
    assert policy.lookup("gone.txt").found is False


def test_validate_component_or_raise() -> None:
    ws.validate_windows_component_or_raise("good-name")
    with pytest.raises(ws.WindowsSemanticsError):
        ws.validate_windows_component_or_raise("CON")


def test_schemas_and_records_are_serializable() -> None:
    policy = ws.WindowsSemanticsPolicy()
    policy.create("x.txt", size=1)
    projected = policy.project_attrs("x.txt")
    assert projected.to_record()["schema"] == ws.WINDOWS_ATTR_PROJECTOR_SCHEMA
    root = ws.validate_mount_root("Z:")
    assert root.to_record()["kind"] == "drive_letter"
    result = ws.validate_windows_component("x.txt")
    assert result.to_record()["ok"] is True
    assert policy.trace.to_record()["schema"] == ws.WINDOWS_TRACE_SCHEMA


def test_share_helper_functions() -> None:
    h = ws.WindowsOpenHandle(
        handle_id=1,
        path="p",
        access=ws.WindowsAccess.READ,
        share=ws.WindowsShareMode.READ,
    )
    assert ws.share_permits(h, ws.WindowsAccess.READ) is True
    assert ws.share_permits(h, ws.WindowsAccess.WRITE) is False
    assert ws.access_permits_peer_share(ws.WindowsShareMode.READ, ws.WindowsAccess.READ) is True
    assert ws.access_permits_peer_share(ws.WindowsShareMode.NONE, ws.WindowsAccess.READ) is False
