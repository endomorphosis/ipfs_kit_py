"""Conformance tests for the versioned Iroh directory manifest store."""

from __future__ import annotations

import copy
import json
import stat
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.iroh.errors import (
    IrohConflictError,
    IrohInvalidManifestError,
    IrohInvalidPathError,
    IrohNotFoundError,
    IrohUnsupportedVersionError,
)
from ipfs_kit_py.iroh.manifest import (
    DirectoryManifest,
    IrohManifestStore,
    ManifestEntry,
    ManifestHead,
    ManifestPermissions,
    ParentRevision,
    canonical_json,
    migrate_manifest,
    validate_manifest,
    validate_manifest_path,
)
from ipfs_kit_py.iroh.manifest_cli import migrate_file

NAMESPACE = "a" * 64
WRITER = "b" * 64
OTHER_WRITER = "c" * 64
BLOB = "d" * 64
NOW = "2026-07-13T18:00:00Z"


def root() -> ManifestEntry:
    return ManifestEntry.root(mtime=NOW)


def file(path: str = "hello.txt") -> ManifestEntry:
    return ManifestEntry(path, "file", False, 0o644, NOW, {}, BLOB, 5)


class MemoryManifestClient:
    def __init__(self) -> None:
        self.head: ManifestHead | None = None
        self.documents: dict[str, dict[str, Any]] = {}
        self.heads: list[ManifestHead] = []
        self.corrupt_open = False

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> Any:
        del timeout
        params = dict(params or {})
        if method == "manifests.create":
            if self.head is not None:
                raise IrohConflictError("namespace exists", operation=method)
            return self._commit(params["manifest"], params["manifest_hash"])
        if method == "manifests.open":
            if self.corrupt_open:
                return {"head": {"revision": "damaged", "manifest_hash": "bad"}}
            if self.head is None:
                raise IrohNotFoundError("missing", operation=method)
            return {"head": self.head.to_dict()}
        if method == "manifests.read":
            wanted = params.get("manifest_hash")
            if wanted is None:
                if self.head is None:
                    raise IrohNotFoundError("missing", operation=method)
                wanted = self.head.manifest_hash
            document = self.documents.get(wanted)
            if document is None:
                raise IrohNotFoundError("missing", operation=method)
            revision = document["revision"]
            return {
                "head": {
                    "namespace_id": NAMESPACE,
                    "revision": revision,
                    "manifest_hash": wanted,
                },
                "manifest": copy.deepcopy(document),
            }
        if method == "manifests.history":
            return {"heads": [head.to_dict() for head in reversed(self.heads)]}
        if method == "manifests.compare_and_swap":
            if "recovery_head" in params:
                selected = params["recovery_head"]
                self.head = ManifestHead(NAMESPACE, selected["revision"], selected["manifest_hash"])
                self.corrupt_open = False
                return {"head": self.head.to_dict()}
            if self.head is None or self.head.token != (
                params["expected_revision"],
                params["expected_manifest_hash"],
            ):
                raise IrohConflictError("head changed", operation=method)
            return self._commit(params["manifest"], params["manifest_hash"])
        raise AssertionError(method)

    def _commit(self, document: dict[str, Any], manifest_hash: str) -> dict[str, Any]:
        self.documents[manifest_hash] = copy.deepcopy(document)
        self.head = ManifestHead(NAMESPACE, document["revision"], manifest_hash)
        self.heads.append(self.head)
        return {"head": self.head.to_dict(), "manifest": copy.deepcopy(document)}


def test_golden_contract_manifest_reads_and_canonicalizes() -> None:
    fixture = Path(__file__).parent / "fixtures/iroh/filesystem/manifest-v1.json"
    manifest = validate_manifest(fixture.read_bytes())
    assert manifest.revision == 7
    assert manifest.entries[0].path == ""
    assert manifest.entries[2].tombstone is True
    assert validate_manifest(manifest.canonical_bytes()) == manifest


def test_entries_enforce_paths_tree_modes_metadata_and_tombstones() -> None:
    with pytest.raises(IrohInvalidPathError):
        validate_manifest_path("not/../safe")
    with pytest.raises(IrohInvalidPathError):
        validate_manifest_path("e\u0301")
    with pytest.raises(IrohInvalidManifestError):
        ManifestEntry("x", "file", False, 0o755, NOW, {}, BLOB, 1)
    with pytest.raises(IrohInvalidManifestError):
        ManifestEntry("x", "file", False, 0o644, NOW, {"api_token": "secret"}, BLOB, 1)
    with pytest.raises(IrohInvalidManifestError):
        ManifestEntry("x", "file", True, 0o644, NOW, {}, BLOB, 1, NOW)

    tombstone = ManifestEntry.deleted("gone.txt", "file", mode=0o644, mtime=NOW, deleted_at=NOW)
    manifest = DirectoryManifest.create(NAMESPACE, WRITER, 0, [root(), tombstone], created_at=NOW)
    assert manifest.entries[1].to_dict() == {
        "path": "gone.txt",
        "kind": "file",
        "tombstone": True,
        "mode": 0o644,
        "mtime": NOW,
        "metadata": {},
        "deleted_at": NOW,
    }


def test_manifest_semantics_reject_missing_parent_and_unauthorized_writer() -> None:
    with pytest.raises(IrohInvalidManifestError, match="parent"):
        DirectoryManifest.create(NAMESPACE, WRITER, 1, [root()], created_at=NOW)
    permissions = ManifestPermissions.owner_only(OTHER_WRITER)
    with pytest.raises(IrohInvalidManifestError, match="writer_id"):
        DirectoryManifest.create(
            NAMESPACE, WRITER, 0, [root()], permissions=permissions, created_at=NOW
        )
    with pytest.raises(IrohInvalidManifestError, match="parent"):
        DirectoryManifest.create(
            NAMESPACE,
            WRITER,
            2,
            [root()],
            parent_revision=ParentRevision(0, "e" * 64),
            created_at=NOW,
        )


def test_canonical_json_uses_jcs_number_and_key_rules() -> None:
    assert canonical_json({"z": 1.0, "tiny": 1e-7, "minus": -0.0}) == (
        b'{"minus":0,"tiny":1e-7,"z":1}'
    )
    assert canonical_json({"large": 1e20}) == b'{"large":100000000000000000000}'


@pytest.mark.asyncio
async def test_writers_use_full_head_cas_and_detect_conflicts() -> None:
    client = MemoryManifestClient()
    store = IrohManifestStore(client)
    genesis = await store.create_namespace(NAMESPACE, WRITER, [root()], created_at=NOW)

    first = DirectoryManifest.create(
        NAMESPACE,
        WRITER,
        1,
        [root(), file()],
        parent_revision=ParentRevision(genesis.head.revision, genesis.head.manifest_hash),
        permissions=genesis.manifest.permissions,
        created_at=NOW,
    )
    committed = await store.publish(first, expected_head=genesis.head)
    assert committed.head.revision == 1

    stale = DirectoryManifest.create(
        NAMESPACE,
        WRITER,
        1,
        [root()],
        parent_revision=ParentRevision(genesis.head.revision, genesis.head.manifest_hash),
        permissions=genesis.manifest.permissions,
        created_at=NOW,
    )
    with pytest.raises(IrohConflictError):
        await store.publish(stale, expected_head=genesis.head)


@pytest.mark.asyncio
async def test_corrupt_head_recovers_latest_valid_hash_linked_history() -> None:
    client = MemoryManifestClient()
    store = IrohManifestStore(client)
    genesis = await store.create_namespace(NAMESPACE, WRITER, [root()], created_at=NOW)
    second = await store.publish(
        DirectoryManifest.create(
            NAMESPACE,
            WRITER,
            1,
            [root(), file()],
            parent_revision=ParentRevision(*genesis.head.token),
            permissions=genesis.manifest.permissions,
            created_at=NOW,
        ),
        expected_head=genesis.head,
    )
    # History can contain an unreadable/corrupt candidate. It must not outrank
    # the fully verified chain ending at revision 1.
    client.heads.append(ManifestHead(NAMESPACE, 2, "f" * 64))
    client.corrupt_open = True

    audit = await store.recover_head(NAMESPACE)
    assert audit.previous_head is None
    assert audit.recovered_head == second.head
    assert audit.dry_run is True
    repaired = await store.recover_head(NAMESPACE, dry_run=False)
    assert repaired.recovered_head == second.head
    assert client.head == second.head


def test_old_schema_migrates_deterministically_and_future_schema_fails() -> None:
    old = {
        "schema_version": 0,
        "namespace": NAMESPACE,
        "revision": 0,
        "mtime": NOW,
        "author": WRITER,
        "files": [
            {
                "path": "hello.txt",
                "type": "file",
                "hash": BLOB,
                "size": 5,
                "modified_at": NOW,
                "content_type": "text/plain",
            }
        ],
    }
    migrated = migrate_manifest(old)
    assert migrated["schema_version"] == 1
    assert migrated["entries"][0]["path"] == ""
    assert migrated["entries"][1]["metadata"] == {"content_type": "text/plain"}
    assert validate_manifest(old).to_dict() == migrated
    with pytest.raises(IrohUnsupportedVersionError):
        validate_manifest({"schema_version": 2})


def test_migration_file_is_atomic_private_and_preserves_source_on_failure(tmp_path: Path) -> None:
    valid = {
        "schema_version": 0,
        "namespace": NAMESPACE,
        "revision": 0,
        "mtime": NOW,
        "author": WRITER,
        "files": [],
    }
    source = tmp_path / "old.json"
    source.write_text(json.dumps(valid), encoding="utf-8")
    target = migrate_file(source)
    assert target == source
    assert json.loads(source.read_text(encoding="utf-8"))["schema_version"] == 1
    assert stat.S_IMODE(source.stat().st_mode) == 0o600

    broken = tmp_path / "broken.json"
    broken.write_text("{not-json", encoding="utf-8")
    before = broken.read_bytes()
    with pytest.raises(IrohInvalidManifestError):
        migrate_file(broken)
    assert broken.read_bytes() == before
