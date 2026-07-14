"""Contract tests for explicit IPFS/Iroh synchronization."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import blake3
import pytest
from jsonschema import Draft202012Validator, FormatChecker

from ipfs_kit_py.iroh.blob_store import IngestResult
from ipfs_kit_py.iroh_sync import (
    SYNC_CHECKPOINT_SCHEMA,
    SYNC_MAPPING_SCHEMA,
    SYNC_RECEIPT_SCHEMA,
    ConflictPolicy,
    IrohIPFSSyncAdapter,
    SyncCheckpointError,
    SyncItem,
    SyncValidationError,
    verify_cid,
)


def cid_for(content: bytes) -> str:
    """Create a raw CIDv1 with a SHA-256 multihash."""

    raw = bytes((1, 0x55, 0x12, 0x20)) + hashlib.sha256(content).digest()
    return base64.b32encode(raw).decode("ascii").lower().rstrip("=")


class MemoryIPFS:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.add_calls: list[bytes] = []
        self.cat_calls: list[str] = []
        self.unpinned: list[str] = []
        self.fail_once_for: set[bytes] = set()

    def seed(self, content: bytes) -> str:
        cid = cid_for(content)
        self.objects[cid] = content
        return cid

    def cat(self, cid: str) -> bytes:
        self.cat_calls.append(cid)
        return self.objects[cid]

    def add(self, content: bytes, **_kwargs: Any) -> dict[str, str]:
        self.add_calls.append(content)
        if content in self.fail_once_for:
            self.fail_once_for.remove(content)
            raise OSError("injected IPFS write failure")
        return {"Hash": self.seed(content)}

    def exists(self, cid: str) -> bool:
        return cid in self.objects

    def pin_rm(self, cid: str) -> None:
        self.unpinned.append(cid)


class MemoryIroh:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.ingest_calls: list[bytes] = []
        self.read_calls: list[str] = []
        self.fail_once_for: set[bytes] = set()
        self.corrupt_reads: set[str] = set()

    def seed(self, content: bytes) -> str:
        digest = blake3.blake3(content).hexdigest()
        self.objects[digest] = content
        return digest

    async def ingest(
        self, content: bytes, *, expected_hash: str, operation_id: str | None = None
    ) -> IngestResult:
        del operation_id
        self.ingest_calls.append(content)
        if content in self.fail_once_for:
            self.fail_once_for.remove(content)
            raise OSError("injected Iroh ingest failure")
        digest = blake3.blake3(content).hexdigest()
        assert digest == expected_hash
        deduplicated = digest in self.objects
        self.objects[digest] = content
        return IngestResult(digest, len(content), deduplicated=deduplicated)

    async def read_range(self, digest: str, offset: int, length: int | None) -> bytes:
        self.read_calls.append(digest)
        content = self.objects[digest]
        if digest in self.corrupt_reads:
            content += b"corrupt"
        return content[offset:] if length is None else content[offset : offset + length]

    async def exists(self, digest: str) -> bool:
        return digest in self.objects


@pytest.fixture
def stores() -> tuple[MemoryIPFS, MemoryIroh]:
    return MemoryIPFS(), MemoryIroh()


def test_schema_resources_match_exported_contract_and_validate_examples() -> None:
    resources = Path(__file__).parents[1] / "ipfs_kit_py" / "resources"
    contracts = (
        ("iroh-ipfs-sync-mapping.schema.json", SYNC_MAPPING_SCHEMA),
        ("iroh-ipfs-sync-checkpoint.schema.json", SYNC_CHECKPOINT_SCHEMA),
        ("iroh-ipfs-sync-receipt.schema.json", SYNC_RECEIPT_SCHEMA),
    )
    for filename, exported in contracts:
        resource = json.loads((resources / filename).read_text(encoding="utf-8"))
        assert resource == exported
        Draft202012Validator.check_schema(resource)


@pytest.mark.asyncio
async def test_ipfs_import_keeps_cid_and_iroh_hash_in_separate_domains(
    tmp_path: Path, stores: tuple[MemoryIPFS, MemoryIroh]
) -> None:
    ipfs, iroh = stores
    content = b"model payload"
    cid = ipfs.seed(content)
    sync = IrohIPFSSyncAdapter(ipfs, iroh, tmp_path / "state")

    receipt = await sync.import_from_ipfs(
        cid, logical_path="models/model.bin", operation_id="import-1"
    )

    assert receipt["status"] == "success"
    assert receipt["transferred_bytes"] == len(content)
    entry = receipt["entries"][0]
    assert entry["cid"] == cid
    assert entry["iroh_hash"] == blake3.blake3(content).hexdigest()
    assert entry["cid"] != entry["iroh_hash"]
    mapping = sync.get_mapping("models/model.bin")
    assert mapping is not None
    assert mapping["lineage"][-1]["source_backend"] == "ipfs"
    assert mapping["iroh_hash"] in iroh.objects
    assert (tmp_path / "state" / "mappings.json").stat().st_mode & 0o777 == 0o600
    Draft202012Validator(SYNC_RECEIPT_SCHEMA, format_checker=FormatChecker()).validate(receipt)


@pytest.mark.asyncio
async def test_iroh_export_to_ipfs_and_local_are_verified(
    tmp_path: Path, stores: tuple[MemoryIPFS, MemoryIroh]
) -> None:
    ipfs, iroh = stores
    content = bytes(range(256))
    digest = iroh.seed(content)
    root = tmp_path / "exports"
    sync = IrohIPFSSyncAdapter(ipfs, iroh, tmp_path / "state", local_root=root)

    ipfs_receipt = await sync.export_to_ipfs(digest, logical_path="data/ipfs.bin")
    local_receipt = await sync.export_to_local(
        digest, "nested/local.bin", logical_path="data/local.bin"
    )

    assert ipfs.objects[ipfs_receipt["entries"][0]["cid"]] == content
    assert (root / "nested" / "local.bin").read_bytes() == content
    assert local_receipt["entries"][0]["iroh_hash"] == digest
    with pytest.raises(SyncValidationError, match="escapes"):
        await sync.export_to_local(digest, "../escape.bin")


@pytest.mark.asyncio
async def test_direct_local_ipfs_roundtrip_uses_the_general_sync_contract(
    tmp_path: Path, stores: tuple[MemoryIPFS, MemoryIroh]
) -> None:
    ipfs, iroh = stores
    source = tmp_path / "source.bin"
    source.write_bytes(b"local to ipfs")
    export_root = tmp_path / "exports"
    sync = IrohIPFSSyncAdapter(ipfs, iroh, tmp_path / "state", local_root=export_root)

    uploaded = await sync.sync(
        [
            SyncItem(
                "roundtrip/source.bin",
                "local",
                "ipfs",
                local_path=str(source),
            )
        ]
    )
    cid = uploaded["entries"][0]["cid"]
    downloaded = await sync.sync(
        [
            SyncItem(
                "roundtrip/copy.bin",
                "ipfs",
                "local",
                cid=cid,
                destination_path="copy.bin",
            )
        ]
    )

    assert downloaded["status"] == "success"
    assert (export_root / "copy.bin").read_bytes() == source.read_bytes()
    mapping = sync.get_mapping("roundtrip/copy.bin")
    assert mapping is not None
    assert mapping["cid"] == cid
    assert mapping["iroh_hash"] is None


@pytest.mark.asyncio
async def test_local_import_verifies_expected_digest(
    tmp_path: Path, stores: tuple[MemoryIPFS, MemoryIroh]
) -> None:
    ipfs, iroh = stores
    source = tmp_path / "source.bin"
    source.write_bytes(b"local")
    sync = IrohIPFSSyncAdapter(ipfs, iroh, tmp_path / "state")

    receipt = await sync.import_from_local(
        source,
        expected_sha256=hashlib.sha256(b"local").hexdigest(),
    )
    assert receipt["status"] == "success"

    bad = await sync.import_from_local(
        source,
        logical_path="bad.bin",
        expected_sha256="0" * 64,
    )
    assert bad["status"] == "failed"
    assert bad["errors"][0]["error_type"] == "SyncIntegrityError"


@pytest.mark.asyncio
async def test_partial_failure_resumes_only_failed_entry(
    tmp_path: Path, stores: tuple[MemoryIPFS, MemoryIroh]
) -> None:
    ipfs, iroh = stores
    one, two = b"one", b"two"
    cid_one, cid_two = ipfs.seed(one), ipfs.seed(two)
    iroh.fail_once_for.add(two)
    sync = IrohIPFSSyncAdapter(ipfs, iroh, tmp_path / "state")
    items = [
        SyncItem("one", "ipfs", "iroh", cid=cid_one),
        SyncItem("two", "ipfs", "iroh", cid=cid_two),
    ]

    first = await sync.reconcile(items, operation_id="resumable")
    calls_after_failure = list(iroh.ingest_calls)
    second = await sync.reconcile(items, operation_id="resumable")

    assert first["status"] == "partial"
    assert first["failed_items"] == 1
    assert second["status"] == "success"
    assert second["resumed"] is True
    assert second["entries"][0]["replayed"] is True
    assert iroh.ingest_calls == calls_after_failure + [two]
    checkpoint = sync.state.get_checkpoint("resumable")
    assert checkpoint is not None
    assert [item["attempts"] for item in checkpoint["items"]] == [1, 2]


@pytest.mark.asyncio
async def test_idempotent_replay_and_new_operation_deduplication(
    tmp_path: Path, stores: tuple[MemoryIPFS, MemoryIroh]
) -> None:
    ipfs, iroh = stores
    cid = ipfs.seed(b"same")
    sync = IrohIPFSSyncAdapter(ipfs, iroh, tmp_path / "state")

    first = await sync.import_ipfs(cid, logical_path="same", operation_id="stable-op")
    counts = (len(ipfs.cat_calls), len(iroh.ingest_calls))
    replay = await sync.import_ipfs(cid, logical_path="same", operation_id="stable-op")
    dedupe = await sync.import_ipfs(cid, logical_path="same", operation_id="new-op")

    assert first["status"] == replay["status"] == "success"
    assert replay["resumed"] is True and replay["entries"][0]["replayed"] is True
    assert (len(ipfs.cat_calls), len(iroh.ingest_calls)) == (counts[0] + 1, counts[1])
    assert dedupe["deduplicated_items"] == 1
    with pytest.raises(SyncCheckpointError):
        await sync.import_ipfs(cid, logical_path="different", operation_id="stable-op")


@pytest.mark.asyncio
async def test_conflict_policies_are_explicit_and_auditable(
    tmp_path: Path, stores: tuple[MemoryIPFS, MemoryIroh]
) -> None:
    ipfs, iroh = stores
    old, new = ipfs.seed(b"old"), ipfs.seed(b"new")
    sync = IrohIPFSSyncAdapter(ipfs, iroh, tmp_path / "state")
    await sync.import_ipfs(old, logical_path="asset")

    failed = await sync.import_ipfs(new, logical_path="asset")
    skipped = await sync.import_ipfs(
        new, logical_path="asset", conflict_policy=ConflictPolicy.DESTINATION_WINS
    )
    replaced = await sync.import_ipfs(
        new, logical_path="asset", conflict_policy=ConflictPolicy.SOURCE_WINS
    )

    assert failed["status"] == "failed"
    assert failed["errors"][0]["error_type"] == "SyncConflictError"
    assert skipped["skipped_items"] == 1
    assert replaced["transferred_items"] == 1
    assert sync.get_mapping("asset")["cid"] == new  # type: ignore[index]


@pytest.mark.asyncio
async def test_keep_both_creates_a_deterministic_conflict_mapping(
    tmp_path: Path, stores: tuple[MemoryIPFS, MemoryIroh]
) -> None:
    ipfs, iroh = stores
    old, new = ipfs.seed(b"old"), ipfs.seed(b"new")
    sync = IrohIPFSSyncAdapter(ipfs, iroh, tmp_path / "state")
    await sync.import_ipfs(old, logical_path="asset")
    receipt = await sync.import_ipfs(new, logical_path="asset", conflict_policy="keep-both")
    conflict_path = receipt["entries"][0]["logical_path"]
    assert conflict_path.startswith("asset.conflict-")
    assert sync.get_mapping("asset")["cid"] == old  # type: ignore[index]
    assert sync.get_mapping(conflict_path)["cid"] == new  # type: ignore[index]


@pytest.mark.asyncio
async def test_keep_both_preserves_both_local_files(
    tmp_path: Path, stores: tuple[MemoryIPFS, MemoryIroh]
) -> None:
    ipfs, iroh = stores
    old_digest, new_digest = iroh.seed(b"old"), iroh.seed(b"new")
    root = tmp_path / "exports"
    sync = IrohIPFSSyncAdapter(ipfs, iroh, tmp_path / "state", local_root=root)
    await sync.export_local(old_digest, "asset.bin", logical_path="asset")

    receipt = await sync.export_local(
        new_digest,
        "asset.bin",
        logical_path="asset",
        conflict_policy=ConflictPolicy.KEEP_BOTH,
    )

    conflict_mapping = sync.get_mapping(receipt["entries"][0]["logical_path"])
    assert conflict_mapping is not None
    assert (root / "asset.bin").read_bytes() == b"old"
    assert Path(conflict_mapping["local_path"]).read_bytes() == b"new"


@pytest.mark.asyncio
async def test_deleted_entries_create_tombstones_and_do_not_delete_iroh_blobs(
    tmp_path: Path, stores: tuple[MemoryIPFS, MemoryIroh]
) -> None:
    ipfs, iroh = stores
    cid = ipfs.seed(b"gone")
    sync = IrohIPFSSyncAdapter(ipfs, iroh, tmp_path / "state")
    imported = await sync.import_ipfs(cid, logical_path="gone", operation_id="create")
    digest = imported["entries"][0]["iroh_hash"]

    deleted = await sync.reconcile(
        [SyncItem("gone", "ipfs", "iroh", deleted=True)], operation_id="delete"
    )
    replay = await sync.reconcile(
        [SyncItem("gone", "ipfs", "iroh", deleted=True)], operation_id="delete"
    )

    assert deleted["deleted_items"] == 1
    assert sync.get_mapping("gone")["deleted"] is True  # type: ignore[index]
    assert digest in iroh.objects
    assert replay["entries"][0]["replayed"] is True


@pytest.mark.asyncio
async def test_hash_verification_rejects_corrupt_iroh_and_ipfs_reads(
    tmp_path: Path, stores: tuple[MemoryIPFS, MemoryIroh]
) -> None:
    ipfs, iroh = stores
    content = b"content"
    digest = iroh.seed(content)
    iroh.corrupt_reads.add(digest)
    sync = IrohIPFSSyncAdapter(ipfs, iroh, tmp_path / "state")

    receipt = await sync.export_ipfs(digest, logical_path="corrupt")
    assert receipt["status"] == "failed"
    assert receipt["errors"][0]["error_type"] == "SyncIntegrityError"

    cid = cid_for(content)
    ipfs.objects[cid] = b"tampered"
    imported = await sync.import_ipfs(cid, logical_path="bad-ipfs")
    assert imported["status"] == "failed"
    assert "do not match CID" in imported["errors"][0]["error"]
    assert verify_cid(content, cid) is True
    assert verify_cid(b"wrong", cid) is False


@pytest.mark.asyncio
async def test_car_staging_is_opt_in_and_recorded(
    tmp_path: Path, stores: tuple[MemoryIPFS, MemoryIroh]
) -> None:
    ipfs, iroh = stores
    content = b"car"
    cid = ipfs.seed(content)

    class Stager:
        def __init__(self) -> None:
            self.reads: list[str] = []

        def read(self, requested: str, **_kwargs: Any) -> bytes:
            self.reads.append(requested)
            return ipfs.objects[requested]

        def write(self, payload: bytes, **_kwargs: Any) -> str:
            return ipfs.seed(payload)

    stager = Stager()
    sync = IrohIPFSSyncAdapter(ipfs, iroh, tmp_path / "state", car_stager=stager)
    receipt = await sync.import_ipfs(cid, logical_path="car", use_car=True)
    assert receipt["entries"][0]["car_staged"] is True
    assert stager.reads == [cid]
    assert not ipfs.cat_calls

    without = IrohIPFSSyncAdapter(ipfs, iroh, tmp_path / "other-state")
    with pytest.raises(SyncValidationError, match="without a CAR stager"):
        await without.import_ipfs(cid, use_car=True)


def test_iroh_hash_can_never_be_labeled_as_cid(
    stores: tuple[MemoryIPFS, MemoryIroh], tmp_path: Path
) -> None:
    ipfs, iroh = stores
    sync = IrohIPFSSyncAdapter(ipfs, iroh, tmp_path / "state")
    with pytest.raises(SyncValidationError, match="never be labeled"):
        SyncItem("bad", "ipfs", "iroh", cid="ab" * 32)
    assert sync.list_receipts() == []
