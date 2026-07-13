"""Read-side conformance tests for the Iroh fsspec implementation."""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import blake3
import pytest

from ipfs_kit_py.iroh.errors import IrohIntegrityError
from ipfs_kit_py.iroh.errors import IrohNotFoundError
from ipfs_kit_py.iroh.errors import IrohUnavailableError
from ipfs_kit_py.iroh.errors import IrohUnsupportedOperationError
from ipfs_kit_py.iroh_fsspec import IrohFileSystem


NAMESPACE = "a" * 64
ROOT = Path(__file__).resolve().parents[1]


def digest(value: bytes) -> str:
    return blake3.blake3(value).hexdigest()


def url(path: str = "") -> str:
    return f"iroh://{NAMESPACE}/" + path


class MemoryManifestStore:
    def __init__(self, manifest: dict[str, Any]) -> None:
        self.manifest = manifest
        self.reads = 0

    async def read_head(self, namespace_id: str) -> dict[str, Any]:
        self.reads += 1
        if namespace_id != NAMESPACE:
            raise IrohNotFoundError("missing namespace", operation="manifest.read_head")
        return {"manifest": self.manifest, "head": "f" * 64}


class MemoryBlobStore:
    def __init__(
        self,
        local: dict[str, bytes] | None = None,
        remote: dict[str, bytes] | None = None,
    ) -> None:
        self.local = dict(local or {})
        self.remote = dict(remote or {})
        self.fetches: list[tuple[str, dict[str, Any]]] = []
        self.ranges: list[tuple[str, int, int]] = []

    async def stat(self, blob_hash: str) -> dict[str, Any]:
        if blob_hash not in self.local:
            raise IrohNotFoundError("missing blob", operation="blobs.stat")
        return {"hash": blob_hash, "size": len(self.local[blob_hash]), "complete": True}

    async def read_range(self, blob_hash: str, *, start: int, end: int) -> bytes:
        if blob_hash not in self.local:
            raise IrohNotFoundError("missing blob", operation="blobs.read_range")
        self.ranges.append((blob_hash, start, end))
        return self.local[blob_hash][start:end]

    async def fetch(self, blob_hash: str, **kwargs: Any) -> dict[str, Any]:
        self.fetches.append((blob_hash, kwargs))
        if blob_hash not in self.remote:
            raise IrohNotFoundError("no peer has blob", operation="blobs.ingest")
        self.local[blob_hash] = self.remote[blob_hash]
        return {"hash": blob_hash, "size": len(self.local[blob_hash])}


@pytest.fixture
def tree() -> tuple[IrohFileSystem, dict[str, bytes], MemoryManifestStore, MemoryBlobStore]:
    payloads = {
        "readme": b"hello from iroh\nsecond line\n",
        "report": bytes(range(128)),
        "nested": b"nested",
    }
    hashes = {name: digest(value) for name, value in payloads.items()}
    entries = [
        entry("", "directory"),
        entry("docs", "directory"),
        entry("docs/archive", "directory"),
        entry("docs/archive/data.bin", "file", hashes["nested"], len(payloads["nested"])),
        entry("docs/readme.txt", "file", hashes["readme"], len(payloads["readme"])),
        entry("empty", "directory"),
        entry("report.bin", "file", hashes["report"], len(payloads["report"])),
        {
            **entry("removed.txt", "file", hashes["nested"], len(payloads["nested"])),
            "tombstone": True,
            "deleted_at": "2026-07-13T00:00:00Z",
        },
    ]
    # Tombstones must not retain content addressing fields.
    entries[-1].pop("blob_hash")
    entries[-1].pop("size")
    manifest = {"namespace_id": NAMESPACE, "revision": 4, "entries": entries}
    manifests = MemoryManifestStore(manifest)
    blobs = MemoryBlobStore({hashes[name]: value for name, value in payloads.items()})
    fs = IrohFileSystem(manifest_store=manifests, blob_store=blobs, block_size=8)
    return fs, payloads, manifests, blobs


def entry(
    path: str,
    kind: str,
    blob_hash: str | None = None,
    size: int | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "path": path,
        "kind": kind,
        "tombstone": False,
        "mode": 0o755 if kind == "directory" else 0o644,
        "mtime": "2026-07-13T00:00:00Z",
        "metadata": {"content_type": "application/octet-stream"} if kind == "file" else {},
    }
    if kind == "file":
        value.update(blob_hash=blob_hash, size=size)
    return value


def test_info_ls_and_type_queries_follow_the_live_tree(tree: Any) -> None:
    fs, payloads, _manifests, _blobs = tree
    root = url()

    assert fs.info(root)["type"] == "directory"
    listing = fs.ls(root, detail=True)
    assert [(item["name"], item["type"]) for item in listing] == [
        (url("docs"), "directory"),
        (url("empty"), "directory"),
        (url("report.bin"), "file"),
    ]
    readme = fs.info(f"{root}docs/readme.txt")
    assert readme["size"] == len(payloads["readme"])
    assert readme["revision"] == 4
    assert readme["blob_hash"] == digest(payloads["readme"])
    assert fs.ls(f"{root}docs/readme.txt", detail=False) == [url("docs/readme.txt")]
    assert fs.exists(f"{root}removed.txt") is False
    assert fs.isfile(f"{root}docs/readme.txt") is True
    assert fs.isdir(f"{root}docs") is True
    assert fs.isfile(f"{root}docs") is False


def test_find_walk_and_glob_are_recursive_and_deterministic(tree: Any) -> None:
    fs, _payloads, manifests, _blobs = tree
    root = url()

    assert fs.find(root) == [
        url("docs/archive/data.bin"),
        url("docs/readme.txt"),
        url("report.bin"),
    ]
    assert fs.find(f"{root}docs", maxdepth=1, withdirs=True) == [
        url("docs"),
        url("docs/archive"),
        url("docs/readme.txt"),
    ]
    assert fs.glob(f"{root}docs/**/*.bin") == [
        url("docs/archive/data.bin")
    ]
    assert fs.glob(f"{root}docs/**/*.bin", maxdepth=1) == []
    assert fs.glob(f"{root}docs/**/*.bin", maxdepth=2) == [
        url("docs/archive/data.bin")
    ]

    detailed = fs.find(f"{root}docs", withdirs=True, detail=True)
    assert list(detailed) == [
        url("docs"),
        url("docs/archive"),
        url("docs/archive/data.bin"),
        url("docs/readme.txt"),
    ]
    assert detailed[url("docs/readme.txt")] == fs.info(url("docs/readme.txt"))

    walked = list(fs.walk(f"{root}docs"))
    assert walked == [
        (url("docs"), ["archive"], ["readme.txt"]),
        (url("docs/archive"), [], ["data.bin"]),
    ]
    # Each high-level discovery call observes one head rather than reloading
    # the mutable manifest at every directory level.
    assert manifests.reads == 8


def test_walk_supports_detail_bottom_up_depth_and_top_down_pruning(tree: Any) -> None:
    fs, _payloads, _manifests, _blobs = tree
    root = url()

    detailed = list(fs.walk(f"{root}docs", detail=True, maxdepth=1))
    assert list(detailed[0][1]) == ["archive"]
    assert detailed[0][1]["archive"]["type"] == "directory"
    assert list(detailed[0][2]) == ["readme.txt"]

    assert list(fs.walk(f"{root}docs", topdown=False)) == [
        (url("docs/archive"), [], ["data.bin"]),
        (url("docs"), ["archive"], ["readme.txt"]),
    ]

    walker = fs.walk(f"{root}docs")
    first = next(walker)
    first[1][:] = []
    assert list(walker) == []


def test_cat_ranges_and_open_are_seekable_streaming_reads(tree: Any) -> None:
    fs, payloads, manifests, blobs = tree
    path = f"iroh://{NAMESPACE}/report.bin"
    payload = payloads["report"]

    assert fs.cat_file(path, start=10, end=20) == payload[10:20]
    assert fs.cat_file(path, start=-12) == payload[-12:]
    assert fs.cat_file(path, end=-120) == payload[:-120]
    assert fs.cat_file(path, start=90, end=30) == b""

    reads_before = manifests.reads
    with fs.open(path, "rb") as handle:
        assert handle.size == len(payload)
        assert handle.read(7) == payload[:7]
        assert handle.seek(-5, 2) == len(payload) - 5
        assert handle.read() == payload[-5:]
        assert handle.seek(4) == 4
        target = bytearray(6)
        assert handle.readinto(target) == 6
        assert bytes(target) == payload[4:10]
        assert handle.seek(0) == 0
        assert handle.readline() == payload[:11]
        assert list(handle) == [payload[11:]]
    assert manifests.reads == reads_before + 1
    assert all(end - start <= len(payload) for _hash, start, end in blobs.ranges)


def test_range_validation_rejects_bad_arguments_and_collaborator_results(tree: Any) -> None:
    fs, _payloads, _manifests, blobs = tree
    path = url("report.bin")

    with pytest.raises(TypeError, match="start"):
        fs.cat_file(path, start=1.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="end"):
        fs.cat_file(path, end=True)  # type: ignore[arg-type]

    async def non_bytes(_hash: str, *, start: int, end: int) -> int:
        del start, end
        return 8

    blobs.read_range = non_bytes  # type: ignore[method-assign]
    with pytest.raises(IrohIntegrityError, match="non-bytes"):
        fs.cat_file(path, 0, 8)


def test_text_open_and_vendored_fallback_are_streaming(tree: Any) -> None:
    fs, _payloads, _manifests, _blobs = tree
    with fs.open(url("docs/readme.txt"), "rt", encoding="utf-8") as handle:
        assert handle.readline() == "hello from iroh\n"
        assert handle.read() == "second line\n"

    script = r"""
import builtins
import importlib
import sys

real_import = builtins.__import__
for loaded in list(sys.modules):
    if loaded == "fsspec" or loaded.startswith("fsspec."):
        del sys.modules[loaded]

def isolated_import(name, *args, **kwargs):
    if name == "fsspec" or name.startswith("fsspec."):
        raise ModuleNotFoundError("external fsspec isolated", name=name)
    return real_import(name, *args, **kwargs)

builtins.__import__ = isolated_import
module = importlib.import_module("ipfs_kit_py.iroh_fsspec")
namespace = "a" * 64
blob_hash = "b" * 64
payload = b"one\ntwo\n"

class ManifestStore:
    def read_head(self, requested):
        assert requested == namespace
        return {
            "namespace_id": namespace,
            "revision": 1,
            "entries": [
                {"path": "", "kind": "directory"},
                {
                    "path": "value.txt",
                    "kind": "file",
                    "blob_hash": blob_hash,
                    "size": len(payload),
                },
            ],
        }

class BlobStore:
    def stat(self, requested):
        assert requested == blob_hash
        return {"size": len(payload), "complete": True}

    def read_range(self, requested, *, start, end):
        assert requested == blob_hash
        return payload[start:end]

filesystem = module.IrohFileSystem(
    manifest_store=ManifestStore(), blob_store=BlobStore(), block_size=3
)
with filesystem.open(f"iroh://{namespace}/value.txt", "rb") as handle:
    assert handle.readline() == b"one\n"
    assert handle.read() == b"two\n"
with filesystem.open(f"iroh://{namespace}/value.txt", "rt", encoding="utf-8") as handle:
    assert handle.read() == "one\ntwo\n"
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), value] if (value := env.get("PYTHONPATH")) else [str(ROOT)]
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_cat_and_get_file_stream_without_materializing_the_tree(
    tree: Any, tmp_path: Path
) -> None:
    fs, payloads, _manifests, _blobs = tree
    path = f"iroh://{NAMESPACE}/docs/readme.txt"

    assert fs.cat(path) == payloads["readme"]
    assert fs.cat(f"iroh://{NAMESPACE}/docs", recursive=True) == {
        url("docs/archive/data.bin"): payloads["nested"],
        url("docs/readme.txt"): payloads["readme"],
    }
    assert fs.cat(
        f"iroh://{NAMESPACE}/docs", recursive=True, maxdepth=1
    ) == {url("docs/readme.txt"): payloads["readme"]}
    destination = tmp_path / "parents" / "readme.txt"
    fs.get_file(path, destination)
    assert destination.read_bytes() == payloads["readme"]

    output = io.BytesIO()
    fs.get_file(path, output)
    assert output.getvalue() == payloads["readme"]


def test_cat_and_get_file_pin_one_manifest_snapshot(tmp_path: Path) -> None:
    original = b"original head"
    replacement = b"replacement head"
    original_hash = digest(original)
    replacement_hash = digest(replacement)
    first = {
        "namespace_id": NAMESPACE,
        "revision": 1,
        "entries": [
            entry("", "directory"),
            entry("docs", "directory"),
            entry("docs/value.txt", "file", original_hash, len(original)),
        ],
    }
    second = {
        "namespace_id": NAMESPACE,
        "revision": 2,
        "entries": [
            entry("", "directory"),
            entry("docs", "directory"),
            entry("docs/value.txt", "file", replacement_hash, len(replacement)),
        ],
    }

    class AdvancingManifestStore:
        def __init__(self) -> None:
            self.reads = 0

        async def read_head(self, namespace_id: str) -> dict[str, Any]:
            assert namespace_id == NAMESPACE
            self.reads += 1
            return {"manifest": first if self.reads == 1 else second}

    manifests = AdvancingManifestStore()
    blobs = MemoryBlobStore({original_hash: original, replacement_hash: replacement})
    fs = IrohFileSystem(manifest_store=manifests, blob_store=blobs, block_size=4)

    assert fs.cat(url("docs"), recursive=True) == {
        url("docs/value.txt"): original
    }
    assert manifests.reads == 1

    destination = tmp_path / "value.txt"
    fs.get_file(url("docs/value.txt"), destination)
    assert destination.read_bytes() == replacement
    assert manifests.reads == 2


def test_get_file_is_atomic_and_reports_progress(tree: Any, tmp_path: Path) -> None:
    fs, payloads, _manifests, blobs = tree
    destination = tmp_path / "report.bin"
    destination.write_bytes(b"previous")

    class Callback:
        def __init__(self) -> None:
            self.size: int | None = None
            self.updates: list[int] = []

        def set_size(self, size: int) -> None:
            self.size = size

        def relative_update(self, size: int) -> None:
            self.updates.append(size)

    callback = Callback()
    fs.get_file(url("report.bin"), destination, callback=callback)
    assert destination.read_bytes() == payloads["report"]
    assert callback.size == len(payloads["report"])
    assert sum(callback.updates) == len(payloads["report"])
    assert max(callback.updates) <= fs.blocksize

    async def short_range(blob_hash: str, *, start: int, end: int) -> bytes:
        return blobs.local[blob_hash][start : max(start, end - 1)]

    blobs.read_range = short_range  # type: ignore[method-assign]
    destination.write_bytes(b"keep me")
    with pytest.raises(IrohIntegrityError):
        fs.get_file(url("report.bin"), destination)
    assert destination.read_bytes() == b"keep me"
    assert list(tmp_path.glob(".report.bin.iroh-*.tmp")) == []


def test_missing_paths_and_directories_raise_standard_errors(tree: Any) -> None:
    fs, _payloads, _manifests, _blobs = tree
    root = url()

    for operation in (fs.info, fs.ls, fs.cat_file):
        with pytest.raises(FileNotFoundError):
            operation(f"{root}missing")
    with pytest.raises(IsADirectoryError):
        fs.cat_file(f"{root}docs")
    with pytest.raises(FileNotFoundError):
        fs.find(f"{root}missing")
    assert fs.glob(f"{root}missing/*.txt") == []


def test_lookup_predicates_do_not_hide_backend_outages() -> None:
    class UnavailableManifestStore:
        async def read_head(self, namespace_id: str) -> dict[str, Any]:
            del namespace_id
            raise IrohUnavailableError("sidecar unavailable", operation="manifest.read")

    fs = IrohFileSystem(manifest_store=UnavailableManifestStore(), blob_store=MemoryBlobStore())
    for operation in (fs.exists, fs.isfile, fs.isdir):
        with pytest.raises(IrohUnavailableError):
            operation(url("anything"))


def test_immutable_blob_urls_support_info_ranges_and_open(tree: Any) -> None:
    fs, payloads, _manifests, _blobs = tree
    blob_hash = digest(payloads["nested"])
    blob_fs = IrohFileSystem(
        protocol="iroh+blob",
        blob_store=fs.blob_store,
        block_size=2,
    )
    url = f"iroh+blob://{blob_hash}"

    assert blob_fs.info(url) == {
        "name": url,
        "size": len(payloads["nested"]),
        "type": "file",
        "blob_hash": blob_hash,
    }
    assert blob_fs.cat_file(url, 1, -1) == payloads["nested"][1:-1]
    with blob_fs.open(url, "rb") as handle:
        assert handle.read(3) + handle.read() == payloads["nested"]
    with pytest.raises(IrohUnsupportedOperationError):
        blob_fs.ls(url)


def test_cold_peer_fetch_and_offline_cache_behavior() -> None:
    payload = b"available from a peer"
    blob_hash = digest(payload)
    blobs = MemoryBlobStore(remote={blob_hash: payload})
    online = IrohFileSystem(
        protocol="iroh+blob",
        blob_store=blobs,
        fetch_options={"provider": "peer-id"},
    )
    url = f"iroh+blob://{blob_hash}"

    assert online.cat_file(url) == payload
    assert blobs.fetches == [(blob_hash, {"provider": "peer-id"})]

    offline = IrohFileSystem(protocol="iroh+blob", blob_store=blobs, offline=True)
    assert offline.cat_file(url) == payload
    blobs.local.clear()
    with pytest.raises(IrohNotFoundError, match="local cache"):
        offline.cat_file(url)
    assert len(blobs.fetches) == 1
