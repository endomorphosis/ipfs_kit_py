"""KVFS-200: Persistent ranged VFS storage boundaries and backend adapters.

Acceptance coverage:

* memory, local, IPFS, and Iroh adapters expose confined
  stat / list / range-read / staged-write / delete / rename;
* files larger than 1 MiB are served without whole-object loading;
* immutable or unavailable backend operations reject explicitly; and
* effects and versions are observable after admitted mutations.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ipfs_kit_py.core.vfs import storage as ranged
from ipfs_kit_py.core.vfs.contracts import VFSEntryKind
from ipfs_kit_py.core.vfs.storage import (
    DEFAULT_CHUNK_BYTES,
    RANGED_VFS_STORAGE_SCHEMA,
    WHOLE_OBJECT_THRESHOLD_BYTES,
    IPFSRangedStorage,
    IrohRangedStorage,
    LocalRangedStorage,
    MemoryRangedStorage,
    RangedStorageError,
    RangedVFSStorageBoundary,
    RangedVFSStorage_V1,
    StorageBackendKind,
    StorageCapability,
    StorageErrorCode,
    StorageOp,
    adapter_exposes_confined_surface,
    create_ranged_storage,
)

# test file: .../tests/kernel_vfs/common/test_ranged_storage.py
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
STORAGE_PATH = PACKAGE_ROOT / "ipfs_kit_py" / "core" / "vfs" / "storage.py"

LARGE_SIZE = WHOLE_OBJECT_THRESHOLD_BYTES + (256 * 1024)  # 1.25 MiB
PARTIAL_LENGTH = 4_096


# ---------------------------------------------------------------------------
# Artifact presence / schema
# ---------------------------------------------------------------------------


def test_declared_storage_module_exists() -> None:
    assert STORAGE_PATH.is_file(), f"missing {STORAGE_PATH}"
    assert STORAGE_PATH.stat().st_size > 0


def test_schema_aliases_and_versions() -> None:
    assert ranged.STORAGE_CONTRACT_VERSION == 1
    assert ranged.STORAGE_SCHEMA_VERSION == "1.0.0"
    assert RANGED_VFS_STORAGE_SCHEMA == RangedVFSStorage_V1
    assert RangedVFSStorage_V1.endswith("@1")
    assert DEFAULT_CHUNK_BYTES == 65_536
    assert WHOLE_OBJECT_THRESHOLD_BYTES == 1_048_576


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _all_adapters(tmp_path: Path) -> list[RangedVFSStorageBoundary]:
    return [
        MemoryRangedStorage(clock=lambda: 1_700_000_000_000),
        LocalRangedStorage(tmp_path / "local", clock=lambda: 1_700_000_000_000),
        IPFSRangedStorage(clock=lambda: 1_700_000_000_000),
        IrohRangedStorage(clock=lambda: 1_700_000_000_000),
    ]


@pytest.fixture
def adapters(tmp_path: Path) -> list[RangedVFSStorageBoundary]:
    return _all_adapters(tmp_path)


# ---------------------------------------------------------------------------
# Surface exposure
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "factory",
    [
        lambda p: MemoryRangedStorage(),
        lambda p: LocalRangedStorage(p / "local-surface"),
        lambda p: IPFSRangedStorage(),
        lambda p: IrohRangedStorage(),
    ],
    ids=["memory", "local", "ipfs", "iroh"],
)
def test_adapters_expose_confined_surface(tmp_path: Path, factory) -> None:
    storage = factory(tmp_path)
    assert isinstance(storage, RangedVFSStorageBoundary)
    assert adapter_exposes_confined_surface(storage)
    required = {
        StorageCapability.STAT,
        StorageCapability.LIST,
        StorageCapability.RANGE_READ,
        StorageCapability.STAGED_WRITE,
        StorageCapability.DELETE,
        StorageCapability.RENAME,
    }
    assert required <= set(storage.capabilities)
    for name in (
        "stat",
        "list",
        "range_read",
        "begin_staged_write",
        "stage_write",
        "commit_staged_write",
        "abort_staged_write",
        "delete",
        "rename",
    ):
        assert callable(getattr(storage, name))


def test_create_ranged_storage_factory(tmp_path: Path) -> None:
    mem = create_ranged_storage("memory")
    local = create_ranged_storage(StorageBackendKind.LOCAL, root=tmp_path / "f")
    ipfs = create_ranged_storage(StorageBackendKind.IPFS)
    iroh = create_ranged_storage(StorageBackendKind.IROH)
    assert mem.backend_kind is StorageBackendKind.MEMORY
    assert local.backend_kind is StorageBackendKind.LOCAL
    assert ipfs.backend_kind is StorageBackendKind.IPFS
    assert iroh.backend_kind is StorageBackendKind.IROH


# ---------------------------------------------------------------------------
# CRUD: stat / list / staged-write / range-read / rename / delete
# ---------------------------------------------------------------------------


def test_confined_crud_cycle_on_all_adapters(adapters: list[RangedVFSStorageBoundary]) -> None:
    for storage in adapters:
        storage.mkdir("docs")
        handle = storage.begin_staged_write("docs/readme")
        storage.stage_write(handle, 0, b"hello-ranged-vfs")
        effect = storage.commit_staged_write(handle)
        assert effect.op is StorageOp.STAGED_WRITE
        assert effect.generation > 0
        assert effect.content_cid
        assert effect.version_cid
        assert effect.size_bytes == len(b"hello-ranged-vfs")

        st = storage.stat("docs/readme")
        assert st.kind is VFSEntryKind.FILE
        assert st.size_bytes == len(b"hello-ranged-vfs")
        assert st.content_cid == effect.content_cid
        assert st.version_cid == effect.version_cid
        assert st.backend_id == storage.backend_id

        listing = storage.list("docs")
        names = [e.name for e in listing.entries]
        assert names == ["readme"]
        assert listing.generation == storage.generation

        rr = storage.range_read("docs/readme", 0, 5)
        assert rr.data == b"hello"
        assert rr.version_cid == st.version_cid

        rename_effect = storage.rename("docs/readme", "docs/README")
        assert rename_effect.op is StorageOp.RENAME
        assert rename_effect.target_path == "docs/README"
        assert storage.stat("docs/README").size_bytes == len(b"hello-ranged-vfs")
        with pytest.raises(RangedStorageError) as missing:
            storage.stat("docs/readme")
        assert missing.value.code is StorageErrorCode.NOT_FOUND

        delete_effect = storage.delete("docs/README")
        assert delete_effect.op is StorageOp.DELETE
        with pytest.raises(RangedStorageError) as gone:
            storage.stat("docs/README")
        assert gone.value.code is StorageErrorCode.NOT_FOUND

        # Effects log is observable and ordered.
        ops = [e.op for e in storage.effects()]
        assert StorageOp.STAGED_WRITE in ops
        assert StorageOp.RENAME in ops
        assert StorageOp.DELETE in ops
        assert storage.generation >= rename_effect.generation


def test_path_confinement_rejects_escape(adapters: list[RangedVFSStorageBoundary]) -> None:
    for storage in adapters:
        for bad in ("../escape", "/absolute", "foo/../../etc/passwd", "C:\\windows"):
            with pytest.raises(RangedStorageError) as excinfo:
                storage.stat(bad)
            assert excinfo.value.code in {
                StorageErrorCode.PATH_ESCAPE,
                StorageErrorCode.INVALID_PATH,
            }


def test_abort_staged_write_leaves_namespace_unchanged(
    adapters: list[RangedVFSStorageBoundary],
) -> None:
    for storage in adapters:
        before = storage.generation
        handle = storage.begin_staged_write("ephemeral.bin")
        storage.stage_write(handle, 0, b"should-not-commit")
        storage.abort_staged_write(handle)
        assert storage.generation == before
        with pytest.raises(RangedStorageError) as excinfo:
            storage.stat("ephemeral.bin")
        assert excinfo.value.code is StorageErrorCode.NOT_FOUND


def test_partial_overwrite_via_non_truncate_stage(
    adapters: list[RangedVFSStorageBoundary],
) -> None:
    for storage in adapters:
        h1 = storage.begin_staged_write("patch.bin")
        storage.stage_write(h1, 0, b"ABCDEFGH")
        storage.commit_staged_write(h1)
        h2 = storage.begin_staged_write("patch.bin", truncate=False)
        storage.stage_write(h2, 2, b"xx")
        effect = storage.commit_staged_write(h2)
        assert effect.size_bytes == 8
        assert storage.range_read("patch.bin", 0, 8).data == b"ABxxEFGH"
        assert effect.version_cid != ""
        assert effect.generation == storage.generation


# ---------------------------------------------------------------------------
# Large files without whole-object loading
# ---------------------------------------------------------------------------


def test_large_file_range_read_does_not_touch_all_chunks(
    adapters: list[RangedVFSStorageBoundary],
) -> None:
    assert LARGE_SIZE > WHOLE_OBJECT_THRESHOLD_BYTES
    for storage in adapters:
        # Seed multi-MiB content without the test holding a whole-object buffer.
        pattern = b"KVFS-200-pattern-"
        effect = storage.seed_file(
            "large/blob.bin",
            size_bytes=LARGE_SIZE,
            pattern=pattern,
        )
        assert effect.size_bytes == LARGE_SIZE
        assert effect.content_cid
        assert effect.version_cid

        st = storage.stat("large/blob.bin")
        assert st.size_bytes == LARGE_SIZE
        assert st.size_bytes > WHOLE_OBJECT_THRESHOLD_BYTES

        # Mid-file partial read.
        offset = WHOLE_OBJECT_THRESHOLD_BYTES // 2
        result = storage.range_read("large/blob.bin", offset, PARTIAL_LENGTH)
        assert len(result.data) == PARTIAL_LENGTH
        assert result.size_bytes == LARGE_SIZE
        assert result.chunks_touched >= 1

        total_chunks = (LARGE_SIZE + storage.chunk_bytes - 1) // storage.chunk_bytes
        # Critical invariant: partial read must not consult every chunk.
        assert result.chunks_touched < total_chunks
        assert result.chunks_touched <= (PARTIAL_LENGTH // storage.chunk_bytes) + 2

        # Pattern is tiled from byte 0; partial slice must match that stream.
        tiled = (pattern * ((offset + PARTIAL_LENGTH) // len(pattern) + 2))[
            offset : offset + PARTIAL_LENGTH
        ]
        assert result.data == tiled


def test_large_staged_write_chunked_without_single_buffer(
    adapters: list[RangedVFSStorageBoundary],
) -> None:
    for storage in adapters:
        handle = storage.begin_staged_write("large/staged.bin")
        chunk = b"S" * storage.chunk_bytes
        written = 0
        while written < LARGE_SIZE:
            take = min(len(chunk), LARGE_SIZE - written)
            storage.stage_write(handle, written, chunk[:take])
            written += take
        effect = storage.commit_staged_write(handle)
        assert effect.size_bytes == LARGE_SIZE
        # Read first and last pages only.
        head = storage.range_read("large/staged.bin", 0, 16)
        tail = storage.range_read(
            "large/staged.bin", LARGE_SIZE - 16, 16
        )
        assert head.data == b"S" * 16
        assert tail.data == b"S" * 16
        assert head.chunks_touched < (LARGE_SIZE // storage.chunk_bytes)
        assert tail.chunks_touched < (LARGE_SIZE // storage.chunk_bytes)


def test_local_adapter_persists_body_on_disk(tmp_path: Path) -> None:
    storage = LocalRangedStorage(tmp_path / "persist", clock=lambda: 42)
    storage.seed_file("disk/file.bin", data=b"on-disk-bytes")
    st = storage.stat("disk/file.bin")
    assert st.size_bytes == len(b"on-disk-bytes")
    # Object directory should contain the body file.
    objects = list((tmp_path / "persist" / "objects").rglob("*"))
    files = [p for p in objects if p.is_file()]
    assert files, "local adapter must materialise object files under root"
    assert storage.range_read("disk/file.bin", 0, 7).data == b"on-disk"


# ---------------------------------------------------------------------------
# Immutable / unavailable rejections
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "factory",
    [
        lambda p, **kw: MemoryRangedStorage(**kw),
        lambda p, **kw: LocalRangedStorage(p / "imm-local", **kw),
        lambda p, **kw: IPFSRangedStorage(**kw),
        lambda p, **kw: IrohRangedStorage(**kw),
    ],
    ids=["memory", "local", "ipfs", "iroh"],
)
def test_immutable_backend_rejects_mutations(tmp_path: Path, factory) -> None:
    storage = factory(tmp_path, immutable=True, clock=lambda: 1)
    assert storage.is_immutable is True
    with pytest.raises(RangedStorageError) as excinfo:
        storage.begin_staged_write("nope.txt")
    assert excinfo.value.code is StorageErrorCode.IMMUTABLE

    with pytest.raises(RangedStorageError) as excinfo:
        storage.mkdir("nope-dir")
    assert excinfo.value.code is StorageErrorCode.IMMUTABLE

    with pytest.raises(RangedStorageError) as excinfo:
        storage.delete("missing")
    assert excinfo.value.code is StorageErrorCode.IMMUTABLE

    with pytest.raises(RangedStorageError) as excinfo:
        storage.rename("a", "b")
    assert excinfo.value.code is StorageErrorCode.IMMUTABLE


@pytest.mark.parametrize(
    "factory",
    [
        lambda p, **kw: MemoryRangedStorage(**kw),
        lambda p, **kw: LocalRangedStorage(p / "unavail-local", **kw),
        lambda p, **kw: IPFSRangedStorage(**kw),
        lambda p, **kw: IrohRangedStorage(**kw),
    ],
    ids=["memory", "local", "ipfs", "iroh"],
)
def test_unavailable_backend_rejects_explicitly(tmp_path: Path, factory) -> None:
    storage = factory(tmp_path, available=False, clock=lambda: 1)
    assert storage.is_available is False
    for call in (
        lambda: storage.stat(""),
        lambda: storage.list(""),
        lambda: storage.range_read("x", 0, 1),
        lambda: storage.begin_staged_write("x"),
        lambda: storage.delete("x"),
        lambda: storage.rename("a", "b"),
    ):
        with pytest.raises(RangedStorageError) as excinfo:
            call()
        assert excinfo.value.code is StorageErrorCode.UNAVAILABLE
        assert excinfo.value.backend_id == storage.backend_id


def test_per_entry_readonly_rejects_mutation(
    adapters: list[RangedVFSStorageBoundary],
) -> None:
    for storage in adapters:
        storage.seed_file("locked.bin", data=b"frozen", readonly=True)
        with pytest.raises(RangedStorageError) as excinfo:
            storage.begin_staged_write("locked.bin")
        assert excinfo.value.code is StorageErrorCode.IMMUTABLE
        with pytest.raises(RangedStorageError) as excinfo:
            storage.delete("locked.bin")
        assert excinfo.value.code is StorageErrorCode.IMMUTABLE
        # Reads still work.
        assert storage.range_read("locked.bin", 0, 6).data == b"frozen"


def test_ipfs_and_iroh_unavailable_toggle() -> None:
    ipfs = IPFSRangedStorage(available=True, clock=lambda: 1)
    ipfs.seed_file("a.bin", data=b"x")
    ipfs.set_available(False)
    with pytest.raises(RangedStorageError) as excinfo:
        ipfs.stat("a.bin")
    assert excinfo.value.code is StorageErrorCode.UNAVAILABLE

    iroh = IrohRangedStorage(available=True, clock=lambda: 1)
    iroh.seed_file("b.bin", data=b"y")
    iroh.set_available(False)
    with pytest.raises(RangedStorageError) as excinfo:
        iroh.list("")
    assert excinfo.value.code is StorageErrorCode.UNAVAILABLE


# ---------------------------------------------------------------------------
# Observable effects and versions
# ---------------------------------------------------------------------------


def test_effects_and_versions_are_observable(
    adapters: list[RangedVFSStorageBoundary],
) -> None:
    for storage in adapters:
        e1 = storage.mkdir("v")
        e2 = storage.seed_file("v/a.bin", data=b"one")
        e3 = storage.seed_file("v/b.bin", data=b"two")
        e4 = storage.rename("v/a.bin", "v/c.bin")

        effects = storage.effects()
        assert len(effects) >= 4
        assert effects[-1].effect_id == e4.effect_id
        assert e1.generation < e2.generation < e3.generation < e4.generation

        meta = storage.snapshot_meta()
        assert "v/c.bin" in meta
        assert "v/a.bin" not in meta
        assert meta["v/c.bin"]["content_cid"] == e2.content_cid
        assert meta["v/c.bin"]["version_cid"] == e4.version_cid
        assert meta["v/b.bin"]["version_cid"] == e3.version_cid

        # Version identity changes on rename even when content is unchanged.
        assert e2.version_cid != e4.version_cid
        assert e2.content_cid == e4.content_cid

        # Every effect carries backend identity.
        for effect in effects:
            assert effect.backend_id == storage.backend_id
            assert effect.generation >= 0
            record = effect.to_record()
            assert record["op"]
            assert "version_cid" in record


def test_content_cid_stable_across_identical_seeds(
    adapters: list[RangedVFSStorageBoundary],
) -> None:
    for storage in adapters:
        a = storage.seed_file("same/a", data=b"identical-payload")
        b = storage.seed_file("same/b", data=b"identical-payload")
        assert a.content_cid == b.content_cid
        assert a.version_cid != b.version_cid  # path + generation differ


def test_range_beyond_eof_returns_empty_or_partial(
    adapters: list[RangedVFSStorageBoundary],
) -> None:
    for storage in adapters:
        storage.seed_file("short.bin", data=b"abc")
        empty = storage.range_read("short.bin", 10, 5)
        assert empty.data == b""
        assert empty.chunks_touched == 0
        partial = storage.range_read("short.bin", 1, 100)
        assert partial.data == b"bc"


def test_delete_nonempty_directory_rejects(
    adapters: list[RangedVFSStorageBoundary],
) -> None:
    for storage in adapters:
        storage.mkdir("dir")
        storage.seed_file("dir/child", data=b"x")
        with pytest.raises(RangedStorageError) as excinfo:
            storage.delete("dir")
        assert excinfo.value.code is StorageErrorCode.NOT_EMPTY


def test_error_records_are_structured(adapters: list[RangedVFSStorageBoundary]) -> None:
    storage = adapters[0]
    with pytest.raises(RangedStorageError) as excinfo:
        storage.stat("does-not-exist")
    record = excinfo.value.to_record()
    assert record["code"] == StorageErrorCode.NOT_FOUND.value
    assert record["path"] == "does-not-exist"
    assert record["backend_id"] == storage.backend_id
