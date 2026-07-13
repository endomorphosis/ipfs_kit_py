"""Canonical VFS integration coverage for Iroh mounts."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import blake3

from ipfs_kit_py.ipfs_fsspec import VFSBackendRegistry, VFSCore
from ipfs_kit_py.iroh.errors import IrohConflictError, IrohNotFoundError
from ipfs_kit_py.iroh_fsspec import IrohFileSystem
from ipfs_kit_py.iroh_vfs import IrohVFSAdapter


NAMESPACE = "a" * 64
NOW = "2026-07-13T00:00:00Z"


def digest(value: bytes) -> str:
    return blake3.blake3(value).hexdigest()


def directory(path: str) -> dict[str, Any]:
    return {
        "path": path,
        "kind": "directory",
        "tombstone": False,
        "mode": 0o755,
        "mtime": NOW,
        "metadata": {},
    }


def file_entry(path: str, value: bytes) -> dict[str, Any]:
    return {
        "path": path,
        "kind": "file",
        "tombstone": False,
        "blob_hash": digest(value),
        "size": len(value),
        "mode": 0o644,
        "mtime": NOW,
        "metadata": {},
    }


class ManifestStore:
    def __init__(self, entries: list[dict[str, Any]]) -> None:
        self.manifest = {
            "schema_version": 1,
            "namespace_id": NAMESPACE,
            "revision": 1,
            "parent_revision": None,
            "created_at": NOW,
            "writer_id": "b" * 64,
            "permissions": {
                "owner": "b" * 64,
                "public_read": False,
                "readers": [],
                "writers": ["b" * 64],
            },
            "entries": entries,
        }
        self.head = "c" * 64

    async def read_head(self, namespace_id: str) -> dict[str, Any]:
        if namespace_id != NAMESPACE:
            raise IrohNotFoundError("missing namespace", operation="manifest.read")
        return {"manifest": copy.deepcopy(self.manifest), "head": self.head}

    async def compare_and_swap(
        self, namespace_id: str, expected_head: str, new_manifest: dict[str, Any]
    ) -> dict[str, Any]:
        if namespace_id != NAMESPACE or expected_head != self.head:
            raise IrohConflictError("stale head", operation="manifest.cas")
        self.manifest = copy.deepcopy(new_manifest)
        self.head = digest(repr(new_manifest).encode())
        return {"committed": True, "head": self.head}


class BlobStore:
    def __init__(self, values: dict[str, bytes]) -> None:
        self.values = dict(values)

    async def ingest(self, source: Any) -> dict[str, Any]:
        if isinstance(source, (str, Path)):
            value = Path(source).read_bytes()
        else:
            source.seek(0)
            value = source.read()
        blob_hash = digest(value)
        duplicate = blob_hash in self.values
        self.values[blob_hash] = value
        return {"blob_hash": blob_hash, "size": len(value), "deduplicated": duplicate}

    async def stat(self, blob_hash: str) -> dict[str, Any]:
        if blob_hash not in self.values:
            raise IrohNotFoundError("missing blob", operation="blob.stat")
        return {"blob_hash": blob_hash, "size": len(self.values[blob_hash]), "complete": True}

    async def read_range(self, blob_hash: str, *, start: int, end: int) -> bytes:
        return self.values[blob_hash][start:end]


class IPFSFileSystemDouble:
    def __init__(self, values: dict[str, bytes]) -> None:
        self.values = dict(values)

    def cat_file(self, path: str) -> bytes:
        return self.values[path]

    def pipe_file(self, path: str, value: bytes) -> dict[str, Any]:
        self.values[path] = bytes(value)
        return self.info(path)

    def info(self, path: str) -> dict[str, Any]:
        value = self.values[path]
        return {
            "name": path,
            "type": "file",
            "size": len(value),
            "cid": "bafy" + hashlib_sha256(value)[:32],
        }

    def exists(self, path: str) -> bool:
        return path in self.values


def hashlib_sha256(value: bytes) -> str:
    import hashlib

    return hashlib.sha256(value).hexdigest()


def filesystem() -> tuple[IrohFileSystem, ManifestStore, BlobStore]:
    seed = b"seed"
    manifests = ManifestStore(
        [directory(""), directory("docs"), file_entry("docs/seed.bin", seed)]
    )
    blobs = BlobStore({digest(seed): seed})
    return IrohFileSystem(manifest_store=manifests, blob_store=blobs), manifests, blobs


def test_registry_factory_and_direct_iroh_mount_are_canonical() -> None:
    registry = VFSBackendRegistry()
    assert registry.get_backend("iroh") == {"available": True, "name": "iroh"}
    assert isinstance(registry.create_filesystem("iroh"), IrohFileSystem)

    fs, _manifests, _blobs = filesystem()
    vfs = VFSCore(persist_mounts=False)
    mounted = vfs.mount("/archive", "iroh", f"iroh://{NAMESPACE}/", filesystem=fs)
    assert mounted["success"] is True
    assert mounted["backend"] == "iroh"
    assert vfs.resolve_path("/archive/docs/seed.bin")["resolved_path"] == (
        f"iroh://{NAMESPACE}/docs/seed.bin"
    )
    assert vfs.read("/archive/docs/seed.bin")["content"] == "seed"


def test_mount_subtree_isolation_and_path_policy() -> None:
    fs, _manifests, _blobs = filesystem()
    adapter = IrohVFSAdapter(fs, f"iroh://{NAMESPACE}/docs")
    assert adapter.resolve("seed.bin") == f"iroh://{NAMESPACE}/docs/seed.bin"

    vfs = VFSCore(persist_mounts=False)
    assert vfs.mount("/docs", "iroh", f"iroh://{NAMESPACE}/docs", filesystem=fs)["success"]
    assert vfs.read("/docs/seed.bin")["content"] == "seed"
    assert vfs.read("/docs/../outside.bin")["success"] is False
    assert vfs.resolve_path("/docs/../../outside.bin")["success"] is False


def test_iroh_mutations_preserve_envelopes_and_invalidate_stale_reads() -> None:
    fs, _manifests, _blobs = filesystem()
    vfs = VFSCore(persist_mounts=False)
    assert vfs.mount("/archive", "iroh", f"iroh://{NAMESPACE}/", filesystem=fs)["success"]

    written = vfs.write("/archive/new.bin", b"first")
    assert written["success"] is True
    metadata = written["integration"]["metadata"]
    assert metadata["backend"] == "iroh"
    assert metadata["iroh_hash"] == digest(b"first")
    assert metadata["cid"] is None
    assert metadata["lineage"]["namespace_id"] == NAMESPACE
    assert vfs.read("/archive/new.bin")["content"] == "first"

    # Simulate a different process advancing the namespace manifest. Iroh VFS
    # reads must observe the new head instead of a stale VFS byte-cache entry.
    fs.pipe_file(f"iroh://{NAMESPACE}/new.bin", b"second")
    assert vfs.read("/archive/new.bin")["content"] == "second"


def test_binary_cross_backend_copy_preserves_bytes_and_hash_domain_lineage(
    tmp_path: Path,
) -> None:
    fs, _manifests, _blobs = filesystem()
    local_root = tmp_path / "local"
    local_root.mkdir()
    payload = bytes(range(256)) + b"\x00\xffbinary"
    (local_root / "source.bin").write_bytes(payload)

    vfs = VFSCore(persist_mounts=False)
    assert vfs.mount("/local", "local", str(local_root))["success"]
    assert vfs.mount("/iroh", "iroh", f"iroh://{NAMESPACE}/", filesystem=fs)["success"]

    into_iroh = vfs.copy("/local/source.bin", "/iroh/copied.bin")
    assert into_iroh["success"] is True
    assert fs.cat_file(f"iroh://{NAMESPACE}/copied.bin") == payload
    lineage = into_iroh["lineage"]
    assert lineage["content_sha256"]
    assert lineage["destination"]["iroh_hash"] == digest(payload)
    assert "cid" not in lineage["destination"]
    copy_meta = into_iroh["copy_integration"]["metadata"]
    assert copy_meta["iroh_hash"] == digest(payload)
    assert copy_meta["cid"] is None

    back = vfs.copy("/iroh/copied.bin", "/local/roundtrip.bin")
    assert back["success"] is True
    assert (local_root / "roundtrip.bin").read_bytes() == payload
    assert back["lineage"]["source"]["iroh_hash"] == digest(payload)

    ipfs = IPFSFileSystemDouble({"ipfs://root/original.bin": payload})
    assert vfs.mount("/ipfs", "ipfs", "ipfs://root", filesystem=ipfs)["success"]
    ipfs_to_iroh = vfs.copy("/ipfs/original.bin", "/iroh/from-ipfs.bin")
    assert ipfs_to_iroh["success"] is True
    assert fs.cat_file(f"iroh://{NAMESPACE}/from-ipfs.bin") == payload
    assert ipfs_to_iroh["lineage"]["source"]["cid"].startswith("bafy")
    assert ipfs_to_iroh["lineage"]["destination"]["iroh_hash"] == digest(payload)

    iroh_to_ipfs = vfs.copy("/iroh/from-ipfs.bin", "/ipfs/from-iroh.bin")
    assert iroh_to_ipfs["success"] is True
    assert ipfs.values["ipfs://root/from-iroh.bin"] == payload
    assert iroh_to_ipfs["lineage"]["source"]["iroh_hash"] == digest(payload)
    assert iroh_to_ipfs["lineage"]["destination"]["cid"].startswith("bafy")


def test_named_mount_state_is_restart_safe(tmp_path: Path) -> None:
    fs, _manifests, _blobs = filesystem()

    class Manager:
        def get_backend_config(self, name: str, *, redact: bool = True) -> dict[str, Any]:
            assert name == "team_archive"
            del redact
            return {
                "name": name,
                "type": "iroh",
                "namespace": {"id": NAMESPACE, "access": "read-write"},
            }

        def get_backend_adapter(self, name: str, **options: Any) -> IrohFileSystem:
            assert name == "team_archive"
            assert options == {}
            return fs

    state = tmp_path / "mounts.json"
    first = VFSCore(backend_manager=Manager(), mount_state_path=state)
    mounted = first.mount("/archive", "iroh", "team_archive")
    assert mounted["success"] is True
    assert state.stat().st_mode & 0o777 == 0o600

    restarted = VFSCore(backend_manager=Manager(), mount_state_path=state)
    listed = restarted.list_mounts()
    assert listed["count"] == 1
    assert listed["mounts"][0]["backend_name"] == "team_archive"
    assert listed["mounts"][0]["target"] == f"iroh://{NAMESPACE}/"
    assert restarted.read("/archive/docs/seed.bin")["content"] == "seed"


def test_read_only_and_immutable_mounts_reject_mutation() -> None:
    fs, _manifests, blobs = filesystem()
    vfs = VFSCore(persist_mounts=False)
    assert vfs.mount(
        "/readonly", "iroh", f"iroh://{NAMESPACE}/", filesystem=fs, read_only=True
    )["success"]
    result = vfs.write("/readonly/no.bin", b"no")
    assert result["success"] is False

    blob_hash = digest(b"seed")
    blob_fs = IrohFileSystem(protocol="iroh+blob", blob_store=blobs)
    assert vfs.mount(
        "/blob", "iroh", f"iroh+blob://{blob_hash}", filesystem=blob_fs
    )["success"]
    assert vfs.read("/blob")["content"] == "seed"
    assert vfs.write("/blob", b"no")["success"] is False
