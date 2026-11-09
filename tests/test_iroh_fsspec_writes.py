"""Write-side conformance for the transactional Iroh fsspec backend."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import blake3
import pytest

from ipfs_kit_py.iroh.errors import (
    IrohAlreadyExistsError,
    IrohConflictError,
    IrohIsDirectoryError,
    IrohNotEmptyError,
    IrohNotFoundError,
    IrohPermissionDeniedError,
    IrohUnsupportedOperationError,
)
from ipfs_kit_py.iroh_fsspec import IrohFileSystem


NAMESPACE = "a" * 64
WRITER = "b" * 64
HEAD = "c" * 64
NOW = "2026-07-13T00:00:00Z"


def digest(value: bytes) -> str:
    return blake3.blake3(value).hexdigest()


def url(path: str = "", namespace: str = NAMESPACE) -> str:
    return f"iroh://{namespace}/" + path


def directory(path: str, mode: int = 0o755) -> dict[str, Any]:
    return {
        "path": path,
        "kind": "directory",
        "tombstone": False,
        "mode": mode,
        "mtime": NOW,
        "metadata": {},
    }


def file_entry(path: str, payload: bytes, mode: int = 0o644) -> dict[str, Any]:
    return {
        "path": path,
        "kind": "file",
        "tombstone": False,
        "blob_hash": digest(payload),
        "size": len(payload),
        "mode": mode,
        "mtime": NOW,
        "metadata": {},
    }


def manifest(entries: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "namespace_id": NAMESPACE,
        "revision": 3,
        "parent_revision": {"revision": 2, "manifest_hash": "d" * 64},
        "created_at": NOW,
        "writer_id": WRITER,
        "permissions": {
            "owner": WRITER,
            "public_read": False,
            "readers": [],
            "writers": [WRITER],
        },
        "entries": entries or [directory("")],
    }


class MemoryManifestStore:
    def __init__(self, value: dict[str, Any], *, head: str = HEAD) -> None:
        self.manifest = copy.deepcopy(value)
        self.head = head
        self.cas_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.force_conflict = False

    async def read_head(self, namespace_id: str) -> dict[str, Any]:
        if namespace_id != self.manifest["namespace_id"]:
            raise IrohNotFoundError("namespace missing", operation="manifests.read")
        return {"manifest": copy.deepcopy(self.manifest), "head": self.head}

    async def compare_and_swap(
        self, namespace_id: str, expected_head: str, new_manifest: dict[str, Any]
    ) -> dict[str, Any]:
        if self.force_conflict or namespace_id != NAMESPACE or expected_head != self.head:
            raise IrohConflictError("stale head", operation="manifests.compare_and_swap")
        self.cas_calls.append((namespace_id, expected_head, copy.deepcopy(new_manifest)))
        self.manifest = copy.deepcopy(new_manifest)
        self.head = digest(repr(new_manifest).encode())
        return {"committed": True, "head": self.head}


class MemoryBlobStore:
    def __init__(self, values: dict[str, bytes] | None = None) -> None:
        self.values = dict(values or {})
        self.ingests: list[str] = []

    async def ingest(self, source: Any) -> dict[str, Any]:
        if isinstance(source, (str, Path)):
            value = Path(source).read_bytes()
        else:
            source.seek(0)
            value = source.read()
        blob_hash = digest(value)
        self.ingests.append(blob_hash)
        duplicate = blob_hash in self.values
        self.values[blob_hash] = value
        return {
            "blob_hash": blob_hash,
            "size": len(value),
            "deduplicated": duplicate,
        }

    async def stat(self, blob_hash: str) -> dict[str, Any]:
        if blob_hash not in self.values:
            raise IrohNotFoundError("blob missing", operation="blobs.stat")
        return {"blob_hash": blob_hash, "size": len(self.values[blob_hash]), "complete": True}

    async def read_range(self, blob_hash: str, *, start: int, end: int) -> bytes:
        return self.values[blob_hash][start:end]


@pytest.fixture
def writable_tree() -> tuple[IrohFileSystem, MemoryManifestStore, MemoryBlobStore]:
    old = b"old"
    nested = b"nested"
    store = MemoryManifestStore(
        manifest(
            [
                directory(""),
                directory("docs"),
                directory("docs/archive"),
                file_entry("docs/archive/data.bin", nested),
                file_entry("docs/old.txt", old),
                directory("empty"),
            ]
        )
    )
    blobs = MemoryBlobStore({digest(old): old, digest(nested): nested})
    return IrohFileSystem(manifest_store=store, blob_store=blobs), store, blobs


def live(store: MemoryManifestStore) -> dict[str, dict[str, Any]]:
    return {
        entry["path"]: entry
        for entry in store.manifest["entries"]
        if not entry["tombstone"]
    }


def all_entries(store: MemoryManifestStore) -> dict[str, dict[str, Any]]:
    return {entry["path"]: entry for entry in store.manifest["entries"]}


def test_staged_open_flush_close_overwrite_and_exclusive_modes(writable_tree: Any) -> None:
    fs, manifests, blobs = writable_tree
    original_revision = manifests.manifest["revision"]

    handle = fs.open(url("new.bin"), "wb")
    handle.write(b"new payload")
    handle.flush()
    assert "new.bin" not in live(manifests)
    handle.close()

    assert fs.cat_file(url("new.bin")) == b"new payload"
    assert manifests.manifest["revision"] == original_revision + 1
    assert manifests.manifest["parent_revision"] == {
        "revision": original_revision,
        "manifest_hash": HEAD,
    }
    assert blobs.ingests[-1] == digest(b"new payload")

    with pytest.raises(IrohAlreadyExistsError):
        with fs.open(url("new.bin"), "xb") as exclusive:
            exclusive.write(b"must not win")
    assert fs.cat_file(url("new.bin")) == b"new payload"

    with fs.open(url("new.bin"), "wb") as replacement:
        replacement.write(b"replacement")
    assert fs.cat_file(url("new.bin")) == b"replacement"

    with pytest.raises(IrohIsDirectoryError):
        with fs.open(url("docs"), "wb") as bad:
            bad.write(b"not a file")


def test_pipe_put_and_mkdir_parent_semantics(writable_tree: Any, tmp_path: Path) -> None:
    fs, manifests, _blobs = writable_tree

    fs.makedirs(url("generated/deep"), exist_ok=False)
    assert {"generated", "generated/deep"} <= live(manifests).keys()
    revision = manifests.manifest["revision"]
    fs.makedirs(url("generated/deep"), exist_ok=True)
    assert manifests.manifest["revision"] == revision

    fs.pipe_file(url("generated/value.bin"), memoryview(b"pipe"), mode="create")
    source = tmp_path / "large.bin"
    source.write_bytes(b"local-source")
    fs.put_file(source, url("generated/local.bin"), mode="create")
    assert fs.cat_file(url("generated/value.bin")) == b"pipe"
    assert fs.cat_file(url("generated/local.bin")) == b"local-source"

    with pytest.raises(IrohNotFoundError):
        fs.mkdir(url("missing/leaf"), create_parents=False)
    with pytest.raises(IrohAlreadyExistsError):
        fs.mkdir(url("generated/deep"), exist_ok=False)


def test_copy_and_move_reuse_blob_hashes_and_commit_once(writable_tree: Any) -> None:
    fs, manifests, blobs = writable_tree
    source_hash = live(manifests)["docs/old.txt"]["blob_hash"]
    ingests = len(blobs.ingests)

    fs.copy(url("docs/old.txt"), url("docs/copy.txt"), mode="create")
    assert live(manifests)["docs/copy.txt"]["blob_hash"] == source_hash
    assert len(blobs.ingests) == ingests

    before = len(manifests.cas_calls)
    fs.mv(url("docs/archive"), url("history"), recursive=True)
    assert len(manifests.cas_calls) == before + 1
    assert "history/data.bin" in live(manifests)
    assert "docs/archive" not in live(manifests)
    assert all_entries(manifests)["docs/archive"]["tombstone"] is True
    assert all_entries(manifests)["docs/archive/data.bin"]["tombstone"] is True
    assert len(blobs.ingests) == ingests

    with pytest.raises(IrohAlreadyExistsError):
        fs.copy(url("docs/old.txt"), url("docs/copy.txt"), overwrite=False)


def test_recursive_delete_is_one_revision_and_nonrecursive_is_atomic(writable_tree: Any) -> None:
    fs, manifests, _blobs = writable_tree
    before = copy.deepcopy(manifests.manifest)

    with pytest.raises(IrohNotEmptyError):
        fs.rm(url("docs"), recursive=False)
    assert manifests.manifest == before

    calls = len(manifests.cas_calls)
    fs.rm(url("docs"), recursive=True)
    assert len(manifests.cas_calls) == calls + 1
    entries = all_entries(manifests)
    assert all(entries[path]["tombstone"] for path in entries if path.startswith("docs"))
    assert all("blob_hash" not in entries[path] for path in entries if path.startswith("docs"))

    with pytest.raises(IrohPermissionDeniedError):
        fs.rm(url(), recursive=True)


def test_transaction_batches_writers_and_rolls_back_staging(writable_tree: Any) -> None:
    fs, manifests, _blobs = writable_tree
    before = len(manifests.cas_calls)

    with fs.transaction:
        with fs.open(url("one.bin"), "wb") as first:
            first.write(b"one")
        with fs.open(url("two.bin"), "wb") as second:
            second.write(b"two")
        assert "one.bin" not in live(manifests)
    assert len(manifests.cas_calls) == before + 1
    assert fs.cat_file(url("one.bin")) == b"one"
    assert fs.cat_file(url("two.bin")) == b"two"

    committed = copy.deepcopy(manifests.manifest)
    abandoned: Any = None
    with pytest.raises(RuntimeError, match="abort"):
        with fs.transaction:
            abandoned = fs.open(url("abandoned.bin"), "wb")
            abandoned.write(b"private")
            abandoned.close()
            raise RuntimeError("abort")
    assert manifests.manifest == committed
    assert abandoned.closed is True
    assert abandoned._staging.closed is True


def test_conflict_leaves_head_unchanged_and_restart_retry_deduplicates(writable_tree: Any) -> None:
    fs, manifests, blobs = writable_tree
    before = copy.deepcopy(manifests.manifest)
    manifests.force_conflict = True

    with pytest.raises(IrohConflictError):
        fs.pipe_file(url("retry.bin"), b"retry")
    assert manifests.manifest == before
    assert digest(b"retry") in blobs.values  # published blob is unreferenced and GC-safe

    manifests.force_conflict = False
    restarted = IrohFileSystem(manifest_store=manifests, blob_store=blobs)
    restarted.pipe_file(url("retry.bin"), b"retry")
    assert restarted.cat_file(url("retry.bin")) == b"retry"
    assert blobs.ingests[-2:] == [digest(b"retry"), digest(b"retry")]


def test_permissions_blob_mutations_and_unsupported_modes_fail_closed(writable_tree: Any) -> None:
    fs, manifests, _blobs = writable_tree
    readonly = IrohFileSystem(manifest_store=manifests, blob_store=_blobs, read_only=True)
    with pytest.raises(IrohPermissionDeniedError):
        readonly.pipe_file(url("denied.bin"), b"no")

    blob_url = f"iroh+blob://{digest(b'old')}"
    blob_fs = IrohFileSystem(
        protocol="iroh+blob", manifest_store=manifests, blob_store=_blobs
    )
    with pytest.raises(IrohUnsupportedOperationError):
        blob_fs.pipe_file(blob_url, b"no")
    for mode in ("ab", "r+b", "w+b"):
        with pytest.raises(IrohUnsupportedOperationError):
            fs.open(url("docs/old.txt"), mode)
