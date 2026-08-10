"""KVFS-201: Kernel metadata, stat, access, statfs, time, unsupported ops.

Acceptance coverage:

* file type, mode, nlink, size, uid/gid policy, inode, atime/mtime/ctime
  are deterministic;
* access, statfs, utimens and exact errors are deterministic;
* chmod/chown/xattr/link/symlink/mknod either have reviewed semantics or
  stable unsupported (ENOSYS/EOPNOTSUPP) results.

Conflict policy: own metadata types/projection tests only; no mount-specific
callbacks or fusepy imports.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ipfs_kit_py.core.vfs.host_contracts import (
    EXPLICIT_UNSUPPORTED_CALLBACKS,
    HostCallbackKind,
    HostEntryKind,
    HostErrno,
    HostMetadata,
    HostPlatform,
    errno_number,
)
from ipfs_kit_py.core.vfs.metadata import (
    ACCESS_RESULT_SCHEMA,
    CONTRACT_VERSION,
    DEFAULT_DIR_PERM,
    DEFAULT_FILE_PERM,
    DEFAULT_FS_NAME,
    DEFAULT_SYMLINK_PERM,
    F_OK,
    KERNEL_METADATA_SCHEMA,
    KERNEL_STATFS_SCHEMA,
    METADATA_PROJECTOR_SCHEMA,
    METADATA_UNSUPPORTED_CALLBACKS,
    NLINK_DIR_BASE,
    NLINK_FILE_DEFAULT,
    R_OK,
    REVIEWED_UNSUPPORTED_CALLBACKS,
    S_IFDIR,
    S_IFLNK,
    S_IFMT,
    S_IFREG,
    S_IRUSR,
    S_IRWXU,
    S_IWUSR,
    S_IXUSR,
    SCHEMA_VERSION,
    UTIME_NOW,
    UTIME_OMIT,
    W_OK,
    X_OK,
    AccessResult,
    FileType,
    KernelMetadata,
    KernelMetadata_V1,
    KernelStatfs,
    KernelStatfs_V1,
    MetadataError,
    MetadataErrorCode,
    MetadataProjector,
    MetadataProjector_V1,
    MetadataTraceKind,
    NodeAttr,
    UidGidPolicy,
    UidGidPolicyKind,
    UtimensField,
    classify_utimens_ns,
    compose_mode,
    default_nlink,
    default_perm,
    file_type_bits,
    file_type_from_mode,
    host_kind_from_file_type,
    make_dir_attr,
    make_file_attr,
    make_symlink_attr,
    mode_grants,
    ms_to_ns,
    ns_to_ms,
    permission_bits,
    project_unsupported,
    unsupported_errno_for,
    validate_access_mask,
)

# test file: ipfs_kit_py/tests/kernel_vfs/common/test_metadata.py
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
METADATA_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "core" / "vfs" / "metadata.py"


# ---------------------------------------------------------------------------
# Artifact / schema / inertness
# ---------------------------------------------------------------------------


def test_declared_metadata_module_exists() -> None:
    assert METADATA_PATH.is_file()
    assert METADATA_PATH.stat().st_size > 0


def test_schema_versions_and_interface_aliases() -> None:
    assert CONTRACT_VERSION == 1
    assert SCHEMA_VERSION.startswith("1.")
    assert KernelMetadata_V1.endswith("@1")
    assert KernelStatfs_V1.endswith("@1")
    assert MetadataProjector_V1.endswith("@1")
    assert KERNEL_METADATA_SCHEMA == KernelMetadata_V1
    assert KERNEL_STATFS_SCHEMA == KernelStatfs_V1
    assert METADATA_PROJECTOR_SCHEMA == MetadataProjector_V1


def test_module_has_no_fusepy_dependency() -> None:
    source = METADATA_PATH.read_text(encoding="utf-8")
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
# File type / mode / nlink
# ---------------------------------------------------------------------------


def test_file_type_bits_are_posix() -> None:
    assert file_type_bits(FileType.FILE) == S_IFREG
    assert file_type_bits(FileType.DIRECTORY) == S_IFDIR
    assert file_type_bits(FileType.SYMLINK) == S_IFLNK
    assert file_type_from_mode(S_IFREG | 0o644) is FileType.FILE
    assert file_type_from_mode(S_IFDIR | 0o755) is FileType.DIRECTORY
    assert file_type_from_mode(S_IFLNK | 0o777) is FileType.SYMLINK


def test_compose_mode_applies_defaults_when_zero() -> None:
    assert compose_mode(FileType.FILE) == (S_IFREG | DEFAULT_FILE_PERM)
    assert compose_mode(FileType.DIRECTORY) == (S_IFDIR | DEFAULT_DIR_PERM)
    assert compose_mode(FileType.SYMLINK) == (S_IFLNK | DEFAULT_SYMLINK_PERM)
    # Explicit perm wins; type bits always present.
    assert compose_mode(FileType.FILE, 0o600) == (S_IFREG | 0o600)
    # Type bits in input are stripped and replaced.
    assert compose_mode(FileType.FILE, S_IFDIR | 0o640) == (S_IFREG | 0o640)


def test_default_nlink_policy() -> None:
    assert default_nlink(FileType.FILE) == NLINK_FILE_DEFAULT
    assert default_nlink(FileType.SYMLINK) == 1
    assert default_nlink(FileType.DIRECTORY) == NLINK_DIR_BASE
    assert default_nlink(FileType.DIRECTORY, child_dirs=3) == NLINK_DIR_BASE + 3


def test_permission_bits_mask() -> None:
    assert permission_bits(S_IFREG | 0o644) == 0o644
    assert default_perm(FileType.FILE) == DEFAULT_FILE_PERM


def test_host_kind_round_trip() -> None:
    assert host_kind_from_file_type(FileType.FILE) is HostEntryKind.FILE
    assert host_kind_from_file_type(FileType.DIRECTORY) is HostEntryKind.DIRECTORY
    assert host_kind_from_file_type(FileType.SYMLINK) is HostEntryKind.SYMLINK


# ---------------------------------------------------------------------------
# NodeAttr / KernelMetadata projection
# ---------------------------------------------------------------------------


def test_node_attr_effective_mode_and_directory_size() -> None:
    file_attr = make_file_attr(2, path="a.txt", size=42, mode=0)
    assert file_attr.effective_mode == (S_IFREG | DEFAULT_FILE_PERM)
    assert file_attr.size == 42

    dir_attr = make_dir_attr(1, path="", mode=0, child_dirs=2)
    assert dir_attr.size == 0
    assert dir_attr.effective_nlink == NLINK_DIR_BASE + 2
    assert dir_attr.effective_mode == (S_IFDIR | DEFAULT_DIR_PERM)


def test_kernel_metadata_to_host_metadata_round_trip() -> None:
    meta = KernelMetadata(
        inode=10,
        file_type=FileType.FILE,
        size=100,
        mode=S_IFREG | 0o644,
        nlink=1,
        uid=1000,
        gid=1000,
        atime_ns=1,
        mtime_ns=2,
        ctime_ns=3,
        generation=7,
        display_name="readme.txt",
        path="docs/readme.txt",
    )
    host = meta.to_host_metadata()
    assert isinstance(host, HostMetadata)
    assert host.inode == 10
    assert host.kind is HostEntryKind.FILE
    assert host.size == 100
    assert host.mode == (S_IFREG | 0o644)
    assert host.nlink == 1
    assert host.uid == 1000
    assert host.gid == 1000
    assert host.atime_ns == 1
    assert host.mtime_ns == 2
    assert host.ctime_ns == 3
    assert host.generation == 7
    assert host.display_name == "readme.txt"

    restored = KernelMetadata.from_dict(meta.to_record())
    assert restored == meta
    assert meta.content_id() == restored.content_id()


def test_project_stat_is_deterministic() -> None:
    proj = MetadataProjector(
        uid_gid_policy=UidGidPolicy.fixed(1000, 1000),
        default_now_ns=1_000_000_000,
    )
    proj.admit(
        inode=2,
        file_type=FileType.FILE,
        path="data.bin",
        size=4096,
        mode=0o600,
        now_ns=1_000_000_000,
        display_name="data.bin",
    )
    a = proj.getattr_path("data.bin")
    b = proj.getattr_path("data.bin")
    assert a.to_record() == b.to_record()
    assert a.inode == 2
    assert a.file_type is FileType.FILE
    assert a.size == 4096
    assert a.mode == (S_IFREG | 0o600)
    assert a.nlink == 1
    assert a.uid == 1000
    assert a.gid == 1000
    assert a.atime_ns == 1_000_000_000
    assert a.mtime_ns == 1_000_000_000
    assert a.ctime_ns == 1_000_000_000
    assert a.display_name == "data.bin"
    assert MetadataTraceKind.PROJECT_STAT.value in proj.trace.kinds()


def test_getattr_missing_path_returns_enoent() -> None:
    proj = MetadataProjector()
    result = proj.getattr_host(path="missing")
    assert result.success is False
    assert result.errno is HostErrno.ENOENT
    assert result.error is not None
    assert result.error.errno_number == errno_number(HostErrno.ENOENT)


def test_getattr_host_success_carries_metadata() -> None:
    proj = MetadataProjector(uid_gid_policy=UidGidPolicy.fixed(0, 0))
    proj.admit(inode=1, file_type=FileType.DIRECTORY, path="", mode=0o755)
    result = proj.getattr_host(path="")
    assert result.success is True
    assert result.errno is HostErrno.OK
    assert result.metadata is not None
    assert result.metadata.inode == 1
    assert result.metadata.kind is HostEntryKind.DIRECTORY
    assert result.metadata.mode == (S_IFDIR | 0o755)


def test_directory_and_symlink_projection() -> None:
    proj = MetadataProjector()
    proj.admit(
        inode=1,
        file_type=FileType.DIRECTORY,
        path="",
        child_dirs=1,
    )
    proj.admit(
        inode=3,
        file_type=FileType.SYMLINK,
        path="link",
        size=11,
    )
    d = proj.getattr_path("")
    assert d.file_type is FileType.DIRECTORY
    assert d.size == 0
    assert d.nlink == NLINK_DIR_BASE + 1
    assert d.mode == (S_IFDIR | DEFAULT_DIR_PERM)

    s = proj.getattr_path("link")
    assert s.file_type is FileType.SYMLINK
    assert s.size == 11
    assert s.nlink == 1
    assert s.mode == (S_IFLNK | DEFAULT_SYMLINK_PERM)


# ---------------------------------------------------------------------------
# uid/gid policy
# ---------------------------------------------------------------------------


def test_uid_gid_policy_fixed_caller_root() -> None:
    fixed = UidGidPolicy.fixed(1000, 100)
    assert fixed.resolve(stored_uid=None, stored_gid=None) == (1000, 100)
    assert fixed.resolve(stored_uid=42, stored_gid=7) == (42, 7)

    caller = UidGidPolicy.caller()
    assert caller.kind is UidGidPolicyKind.CALLER
    assert caller.resolve(caller_uid=500, caller_gid=500) == (500, 500)

    root = UidGidPolicy.root()
    assert root.resolve(stored_uid=9, stored_gid=9, caller_uid=1, caller_gid=1) == (
        0,
        0,
    )


def test_projector_applies_uid_gid_policy_on_admit_and_project() -> None:
    proj = MetadataProjector(uid_gid_policy=UidGidPolicy.caller())
    proj.admit(
        inode=5,
        file_type=FileType.FILE,
        path="x",
        caller_uid=111,
        caller_gid=222,
    )
    meta = proj.getattr_path("x", caller_uid=111, caller_gid=222)
    assert meta.uid == 111
    assert meta.gid == 222

    # CALLER policy re-projects from the getattr caller credentials.
    meta2 = proj.getattr_path("x", caller_uid=999, caller_gid=888)
    assert meta2.uid == 999
    assert meta2.gid == 888


def test_uid_gid_policy_round_trip() -> None:
    policy = UidGidPolicy.fixed(10, 20)
    restored = UidGidPolicy.from_dict(policy.to_record())
    assert restored == policy


# ---------------------------------------------------------------------------
# access(2)
# ---------------------------------------------------------------------------


def test_validate_access_mask() -> None:
    assert validate_access_mask(F_OK) == 0
    assert validate_access_mask(R_OK | W_OK | X_OK) == 7
    with pytest.raises(MetadataError) as excinfo:
        validate_access_mask(0o100)
    assert excinfo.value.code is MetadataErrorCode.INVALID_ACCESS_MASK
    assert excinfo.value.errno is HostErrno.EINVAL


def test_mode_grants_owner_group_other() -> None:
    mode = S_IFREG | 0o640  # rw-r-----
    assert mode_grants(
        mode, R_OK, file_uid=1, file_gid=2, caller_uid=1, caller_gid=9
    )
    assert mode_grants(
        mode, W_OK, file_uid=1, file_gid=2, caller_uid=1, caller_gid=9
    )
    assert not mode_grants(
        mode, X_OK, file_uid=1, file_gid=2, caller_uid=1, caller_gid=9
    )
    # Group: read only.
    assert mode_grants(
        mode, R_OK, file_uid=1, file_gid=2, caller_uid=9, caller_gid=2
    )
    assert not mode_grants(
        mode, W_OK, file_uid=1, file_gid=2, caller_uid=9, caller_gid=2
    )
    # Other: nothing.
    assert not mode_grants(
        mode, R_OK, file_uid=1, file_gid=2, caller_uid=9, caller_gid=9
    )
    # F_OK always true.
    assert mode_grants(
        mode, F_OK, file_uid=1, file_gid=2, caller_uid=9, caller_gid=9
    )


def test_mode_grants_root_and_execute() -> None:
    mode = S_IFREG | 0o600  # no execute bits
    assert mode_grants(
        mode, R_OK | W_OK, file_uid=1, file_gid=1, caller_uid=0, caller_gid=0
    )
    assert not mode_grants(
        mode, X_OK, file_uid=1, file_gid=1, caller_uid=0, caller_gid=0
    )
    mode_x = S_IFREG | 0o100
    assert mode_grants(
        mode_x, X_OK, file_uid=1, file_gid=1, caller_uid=0, caller_gid=0
    )


def test_access_f_ok_and_permission_denial() -> None:
    proj = MetadataProjector(uid_gid_policy=UidGidPolicy.fixed(1000, 1000))
    proj.admit(
        inode=2,
        file_type=FileType.FILE,
        path="secret",
        mode=0o600,
        uid=1000,
        gid=1000,
    )
    ok = proj.access("secret", F_OK, caller_uid=50, caller_gid=50)
    assert ok.allowed is True
    assert ok.errno is HostErrno.OK

    # Owner can read/write.
    owner = proj.access(
        "secret", R_OK | W_OK, caller_uid=1000, caller_gid=1000
    )
    assert owner.allowed is True

    # Stranger cannot read.
    denied = proj.access("secret", R_OK, caller_uid=50, caller_gid=50)
    assert denied.allowed is False
    assert denied.errno is HostErrno.EACCES
    assert denied.code == MetadataErrorCode.PERMISSION.value

    host = denied.to_host_result()
    assert host.success is False
    assert host.errno is HostErrno.EACCES
    assert host.errno_number == 13


def test_access_missing_path_is_enoent() -> None:
    proj = MetadataProjector()
    result = proj.access("nope", R_OK)
    assert result.allowed is False
    assert result.errno is HostErrno.ENOENT


def test_access_write_on_readonly_is_erofs() -> None:
    proj = MetadataProjector(read_only=True)
    proj.admit(inode=2, file_type=FileType.FILE, path="ro", mode=0o666)
    result = proj.access("ro", W_OK, caller_uid=0, caller_gid=0)
    assert result.allowed is False
    assert result.errno is HostErrno.EROFS

    # Per-node read_only also rejects writes.
    proj2 = MetadataProjector()
    proj2.admit(
        inode=2, file_type=FileType.FILE, path="nro", mode=0o666, read_only=True
    )
    result2 = proj2.access("nro", W_OK, caller_uid=0, caller_gid=0)
    assert result2.allowed is False
    assert result2.errno is HostErrno.EROFS


def test_access_invalid_mask_exact_error() -> None:
    proj = MetadataProjector()
    proj.admit(inode=2, file_type=FileType.FILE, path="f")
    result = proj.access("f", 0o100)
    assert result.allowed is False
    assert result.errno is HostErrno.EINVAL
    assert result.code == MetadataErrorCode.INVALID_ACCESS_MASK.value


def test_access_result_schema_and_false_success_guard() -> None:
    with pytest.raises(MetadataError):
        AccessResult(allowed=True, mask=F_OK, errno=HostErrno.EACCES)
    with pytest.raises(MetadataError):
        AccessResult(allowed=False, mask=F_OK, errno=HostErrno.OK)
    ok = AccessResult(allowed=True, mask=R_OK, inode=1, path="a")
    assert ok.to_record()["schema"] == ACCESS_RESULT_SCHEMA


# ---------------------------------------------------------------------------
# statfs
# ---------------------------------------------------------------------------


def test_statfs_hermetic_defaults_are_deterministic() -> None:
    a = KernelStatfs.hermetic_default()
    b = KernelStatfs.hermetic_default()
    assert a.to_record() == b.to_record()
    assert a.block_size == 4096
    assert a.fs_name == DEFAULT_FS_NAME
    assert a.total_bytes == a.block_size * a.total_blocks
    assert a.content_id() == b.content_id()


def test_statfs_bounds_and_invariants() -> None:
    with pytest.raises(MetadataError):
        KernelStatfs(block_size=0)
    with pytest.raises(MetadataError):
        KernelStatfs(total_blocks=10, free_blocks=11)
    with pytest.raises(MetadataError):
        KernelStatfs(total_blocks=10, free_blocks=5, available_blocks=6)


def test_projector_statfs_accounts_for_used_space() -> None:
    proj = MetadataProjector()
    proj.admit(inode=2, file_type=FileType.FILE, path="a", size=8192)
    proj.admit(inode=3, file_type=FileType.FILE, path="b", size=4096)
    fs = proj.statfs()
    # 8192+4096 = 12288 bytes → 3 blocks at 4096.
    assert fs.free_blocks == fs.total_blocks - 3
    assert fs.free_files == fs.total_files - 2
    assert MetadataTraceKind.STATFS.value in proj.trace.kinds()

    host = proj.statfs_host()
    assert host.success is True
    assert host.kind is HostCallbackKind.STATFS
    assert host.errno is HostErrno.OK


def test_statfs_round_trip() -> None:
    fs = KernelStatfs.hermetic_default(read_only=True, mount_id="mount:root", used_blocks=10)
    restored = KernelStatfs.from_dict(fs.to_record())
    assert restored == fs
    assert restored.read_only is True
    assert restored.available_blocks == 0


# ---------------------------------------------------------------------------
# utimens
# ---------------------------------------------------------------------------


def test_classify_utimens_sentinels() -> None:
    assert classify_utimens_ns(None) is UtimensField.OMIT
    assert classify_utimens_ns(UTIME_OMIT) is UtimensField.OMIT
    assert classify_utimens_ns(UTIME_NOW) is UtimensField.NOW
    assert classify_utimens_ns(12345) is UtimensField.SET
    with pytest.raises(MetadataError) as excinfo:
        classify_utimens_ns(-5)
    assert excinfo.value.code is MetadataErrorCode.INVALID_TIME
    assert excinfo.value.errno is HostErrno.EINVAL


def test_utimens_set_now_omit_and_ctime() -> None:
    proj = MetadataProjector(default_now_ns=1_000)
    proj.admit(
        inode=2,
        file_type=FileType.FILE,
        path="t",
        atime_ns=10,
        mtime_ns=20,
        ctime_ns=30,
        now_ns=1_000,
    )

    # Absolute set for atime; OMIT mtime; ctime advances.
    r1 = proj.utimens("t", atime_ns=500, mtime_ns=UTIME_OMIT, now_ns=2_000)
    assert r1.success is True
    assert r1.observed_effect is True
    assert r1.atime_ns == 500
    assert r1.mtime_ns == 20
    assert r1.ctime_ns == 2_000
    assert r1.atime_action is UtimensField.SET
    assert r1.mtime_action is UtimensField.OMIT

    # UTIME_NOW for mtime.
    r2 = proj.utimens("t", atime_ns=UTIME_OMIT, mtime_ns=UTIME_NOW, now_ns=3_000)
    assert r2.success is True
    assert r2.atime_ns == 500
    assert r2.mtime_ns == 3_000
    assert r2.ctime_ns == 3_000
    assert r2.mtime_action is UtimensField.NOW

    # Pure dual-OMIT is a no-op success without effect.
    r3 = proj.utimens("t", atime_ns=UTIME_OMIT, mtime_ns=None, now_ns=4_000)
    assert r3.success is True
    assert r3.observed_effect is False
    assert r3.ctime_ns == 3_000  # unchanged


def test_utimens_readonly_and_missing_errors() -> None:
    proj = MetadataProjector(read_only=True, default_now_ns=1)
    proj.admit(inode=2, file_type=FileType.FILE, path="ro")
    r = proj.utimens("ro", atime_ns=1, mtime_ns=1)
    assert r.success is False
    assert r.errno is HostErrno.EROFS

    proj2 = MetadataProjector()
    missing = proj2.utimens("gone", atime_ns=1, mtime_ns=1)
    assert missing.success is False
    assert missing.errno is HostErrno.ENOENT


def test_utimens_invalid_time_exact_error() -> None:
    proj = MetadataProjector()
    proj.admit(inode=2, file_type=FileType.FILE, path="f")
    bad = proj.utimens("f", atime_ns=-99, mtime_ns=UTIME_OMIT)
    assert bad.success is False
    assert bad.errno is HostErrno.EINVAL
    assert bad.code == MetadataErrorCode.INVALID_TIME.value


def test_utimens_host_result_success_and_failure() -> None:
    proj = MetadataProjector(default_now_ns=100)
    proj.admit(inode=2, file_type=FileType.FILE, path="f", now_ns=100)
    r = proj.utimens("f", atime_ns=UTIME_NOW, mtime_ns=UTIME_NOW, now_ns=200)
    host = r.to_host_result(metadata=proj.getattr_path("f").to_host_metadata())
    assert host.success is True
    assert host.kind is HostCallbackKind.UTIMENS
    assert host.observed_effect is True
    assert host.metadata is not None

    fail = proj.utimens("missing", atime_ns=1, mtime_ns=1)
    host_fail = fail.to_host_result()
    assert host_fail.success is False
    assert host_fail.errno is HostErrno.ENOENT


def test_ms_ns_conversion() -> None:
    assert ms_to_ns(1) == 1_000_000
    assert ns_to_ms(1_999_999) == 1


# ---------------------------------------------------------------------------
# Unsupported operations — stable ENOSYS / EOPNOTSUPP
# ---------------------------------------------------------------------------


def test_unsupported_catalogue_covers_plan_set() -> None:
    expected = {
        "chmod",
        "chown",
        "getxattr",
        "setxattr",
        "listxattr",
        "removexattr",
        "link",
        "symlink",
        "mknod",
        "readlink",
    }
    assert {k.value for k in METADATA_UNSUPPORTED_CALLBACKS} == expected
    assert REVIEWED_UNSUPPORTED_CALLBACKS == METADATA_UNSUPPORTED_CALLBACKS
    assert METADATA_UNSUPPORTED_CALLBACKS <= EXPLICIT_UNSUPPORTED_CALLBACKS


def test_unsupported_callbacks_return_stable_errno() -> None:
    proj = MetadataProjector()
    # Feature-shaped → EOPNOTSUPP; missing ops → ENOSYS (host_contracts default).
    assert unsupported_errno_for("chmod") is HostErrno.ENOSYS
    assert unsupported_errno_for("chown") is HostErrno.ENOSYS
    assert unsupported_errno_for("link") is HostErrno.ENOSYS
    assert unsupported_errno_for("symlink") is HostErrno.ENOSYS
    assert unsupported_errno_for("mknod") is HostErrno.ENOSYS
    assert unsupported_errno_for("readlink") is HostErrno.ENOSYS
    assert unsupported_errno_for("getxattr") is HostErrno.EOPNOTSUPP
    assert unsupported_errno_for("setxattr") is HostErrno.EOPNOTSUPP
    assert unsupported_errno_for("listxattr") is HostErrno.EOPNOTSUPP
    assert unsupported_errno_for("removexattr") is HostErrno.EOPNOTSUPP

    for name in ("chmod", "chown", "link", "symlink", "mknod", "getxattr"):
        result = proj.unsupported(name)
        assert result.success is False
        assert result.errno in (HostErrno.ENOSYS, HostErrno.EOPNOTSUPP)
        assert result.error is not None
        # Never false success.
        assert result.errno_number != 0

    # Determinism: same callback → same errno every time.
    assert project_unsupported("chmod").to_record() == project_unsupported(
        "chmod"
    ).to_record()


def test_unsupported_catalogue_map_is_closed_and_deterministic() -> None:
    proj = MetadataProjector()
    cat1 = proj.unsupported_catalogue()
    cat2 = proj.unsupported_catalogue()
    assert cat1 == cat2
    assert set(cat1) == {k.value for k in METADATA_UNSUPPORTED_CALLBACKS}
    for entry in cat1.values():
        assert entry["reviewed"] is True
        assert entry["errno"] in ("ENOSYS", "EOPNOTSUPP")
        assert entry["errno_number"] in (38, 95)


def test_unsupported_never_succeeds_and_records_trace() -> None:
    proj = MetadataProjector()
    result = proj.unsupported(HostCallbackKind.MKNOD, path="dev/null")
    assert result.success is False
    assert result.kind is HostCallbackKind.MKNOD
    steps = [s for s in proj.trace.steps if s.kind is MetadataTraceKind.UNSUPPORTED]
    assert steps
    assert steps[-1].success is False
    assert steps[-1].path == "dev/null"


def test_project_unsupported_rejects_required_callback() -> None:
    with pytest.raises(MetadataError) as excinfo:
        project_unsupported("getattr")
    assert excinfo.value.code is MetadataErrorCode.INVALID_ARGUMENT


# ---------------------------------------------------------------------------
# Rename path, size, nlink, checkpoint
# ---------------------------------------------------------------------------


def test_rename_path_preserves_inode_and_identity() -> None:
    proj = MetadataProjector()
    proj.admit(inode=9, file_type=FileType.FILE, path="old", size=10)
    renamed = proj.rename_path("old", "new")
    assert renamed.inode == 9
    assert renamed.path == "new"
    assert proj.get_by_path("old") is None
    assert proj.getattr_path("new").inode == 9


def test_set_size_updates_mtime_ctime() -> None:
    proj = MetadataProjector(default_now_ns=100)
    proj.admit(inode=2, file_type=FileType.FILE, path="f", size=0, now_ns=50)
    updated = proj.set_size(2, 99, now_ns=200)
    assert updated.size == 99
    assert updated.mtime_ns == 200
    assert updated.ctime_ns == 200
    proj.admit(inode=1, file_type=FileType.DIRECTORY, path="")
    with pytest.raises(MetadataError) as excinfo:
        proj.set_size(1, 1)
    assert excinfo.value.errno is HostErrno.EISDIR


def test_checkpoint_restore_preserves_metadata() -> None:
    proj = MetadataProjector(
        uid_gid_policy=UidGidPolicy.fixed(7, 8),
        default_now_ns=42,
    )
    proj.admit(
        inode=2,
        file_type=FileType.FILE,
        path="docs/a",
        size=5,
        mode=0o640,
        now_ns=42,
    )
    proj.utimens("docs/a", atime_ns=100, mtime_ns=200, now_ns=300)
    cp = proj.checkpoint()
    assert "content_id" in cp
    assert cp["contract_version"] == CONTRACT_VERSION

    restored = MetadataProjector.restore(cp)
    meta = restored.getattr_path("docs/a")
    assert meta.inode == 2
    assert meta.size == 5
    assert meta.mode == (S_IFREG | 0o640)
    assert meta.uid == 7
    assert meta.gid == 8
    assert meta.atime_ns == 100
    assert meta.mtime_ns == 200
    assert meta.ctime_ns == 300


def test_node_attr_round_trip() -> None:
    attr = make_symlink_attr(4, path="l", size=3, mode=0o777)
    restored = NodeAttr.from_dict(attr.to_record())
    assert restored.inode == attr.inode
    assert restored.file_type is FileType.SYMLINK
    assert restored.effective_mode == (S_IFLNK | 0o777)


# ---------------------------------------------------------------------------
# Exact errno numbers (Linux projection)
# ---------------------------------------------------------------------------


def test_exact_errno_numbers_for_metadata_errors() -> None:
    assert errno_number(HostErrno.ENOENT, HostPlatform.LINUX) == 2
    assert errno_number(HostErrno.EACCES, HostPlatform.LINUX) == 13
    assert errno_number(HostErrno.EINVAL, HostPlatform.LINUX) == 22
    assert errno_number(HostErrno.EROFS, HostPlatform.LINUX) == 30
    assert errno_number(HostErrno.ENOSYS, HostPlatform.LINUX) == 38
    assert errno_number(HostErrno.EISDIR, HostPlatform.LINUX) == 21
    assert errno_number(HostErrno.EOPNOTSUPP, HostPlatform.LINUX) == 95
    assert errno_number(HostErrno.EOPNOTSUPP, HostPlatform.WINDOWS) == 95


# ---------------------------------------------------------------------------
# End-to-end deterministic suite
# ---------------------------------------------------------------------------


def test_end_to_end_metadata_plane_is_deterministic() -> None:
    def build() -> dict:
        # Times stay within the safe integer bound used by host contracts.
        t0 = 1_700_000_000_000
        proj = MetadataProjector(
            uid_gid_policy=UidGidPolicy.fixed(1000, 1000),
            default_now_ns=t0,
        )
        proj.admit(
            inode=1,
            file_type=FileType.DIRECTORY,
            path="",
            mode=0o755,
            child_dirs=1,
            now_ns=t0,
        )
        proj.admit(
            inode=2,
            file_type=FileType.FILE,
            path="readme",
            size=12,
            mode=0o644,
            now_ns=t0,
            display_name="readme",
        )
        getattr_r = proj.getattr_host(path="readme").to_record()
        access_r = proj.access("readme", R_OK, caller_uid=1000, caller_gid=1000).to_record()
        access_x = proj.access("readme", X_OK, caller_uid=1000, caller_gid=1000).to_record()
        ut_r = proj.utimens(
            "readme",
            atime_ns=UTIME_NOW,
            mtime_ns=t0 + 100,
            now_ns=t0 + 50,
        ).to_record()
        fs_r = proj.statfs().to_record()
        unsup = {
            name: proj.unsupported(name).to_record()
            for name in ("chmod", "chown", "setxattr", "link", "symlink", "mknod")
        }
        return {
            "getattr": getattr_r,
            "access_r": access_r,
            "access_x": access_x,
            "utimens": ut_r,
            "statfs": fs_r,
            "unsupported": unsup,
            "checkpoint": {
                k: v
                for k, v in proj.checkpoint().items()
                if k != "content_id"
            },
        }

    first = build()
    second = build()
    assert first == second
    # File is not executable under 0o644 for owner triad (no X bit).
    assert first["access_r"]["allowed"] is True
    assert first["access_x"]["allowed"] is False
    assert first["access_x"]["errno"] == "EACCES"
    assert first["getattr"]["success"] is True
    assert first["getattr"]["metadata"]["mode"] == (S_IFREG | 0o644)
    assert first["getattr"]["metadata"]["nlink"] == 1
    assert first["getattr"]["metadata"]["uid"] == 1000
    assert first["utimens"]["success"] is True
    assert first["utimens"]["atime_action"] == "now"
    assert first["utimens"]["mtime_action"] == "set"
    for name, rec in first["unsupported"].items():
        assert rec["success"] is False
        assert rec["errno"] in ("ENOSYS", "EOPNOTSUPP")


def test_permission_owner_bits_helpers() -> None:
    # Sanity on exported permission constants used by mode_grants.
    assert S_IRUSR | S_IWUSR | S_IXUSR == S_IRWXU
    mode = compose_mode(FileType.DIRECTORY, S_IRWXU)
    assert mode & S_IFMT == S_IFDIR
    assert mode & S_IRWXU == S_IRWXU
