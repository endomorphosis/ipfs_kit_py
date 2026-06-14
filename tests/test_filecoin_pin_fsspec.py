"""Tests for Filecoin pin fsspec upload/status/retrieval behavior."""

import hashlib
import os
import sys

import fsspec
import pytest

from ipfs_kit_py import filecoin_pin_fsspec
from ipfs_kit_py.enhanced_fsspec import FilecoinFileSystem, FilecoinPinFileSystem


class FakeFilecoinPinClient:
    mock_mode = True
    api_endpoint = "mock://filecoin-pin"

    def __init__(self):
        self.objects = {}

    def add_content(self, content, metadata=None):
        metadata = metadata or {}
        if isinstance(content, bytes):
            data = content
        elif hasattr(content, "read"):
            data = content.read()
        else:
            with open(content, "rb") as handle:
                data = handle.read()
        digest = hashlib.sha256(data).hexdigest()
        cid = f"bafybeib{digest[:52]}"
        record = {
            "success": True,
            "cid": cid,
            "status": "pinned",
            "request_id": f"req-{digest[:8]}",
            "deal_ids": ["deal-1", "deal-2"],
            "size": len(data),
            "replication": metadata.get("replication", 3),
            "filename": metadata.get("name"),
            "mock": True,
        }
        self.objects[cid] = {**record, "data": bytes(data)}
        return record

    def get_metadata(self, identifier, **kwargs):
        record = self.objects.get(identifier)
        if not record:
            return {"success": False, "cid": identifier, "error": "missing"}
        return {key: value for key, value in record.items() if key != "data"}

    def list_pins(self, **kwargs):
        pins = [
            {key: value for key, value in record.items() if key != "data"}
            for record in self.objects.values()
        ]
        return {"success": True, "pins": pins, "count": len(pins), "mock": True}

    def get_content(self, identifier, **kwargs):
        record = self.objects.get(identifier)
        if not record:
            return {"success": False, "cid": identifier, "error": "missing"}
        return {
            "success": True,
            "cid": identifier,
            "data": record["data"],
            "size": len(record["data"]),
            "mock": True,
        }


@pytest.fixture
def fs():
    filesystem = FilecoinFileSystem(skip_instance_cache=True)
    filesystem.filecoin_client = FakeFilecoinPinClient()
    return filesystem


def test_filecoin_protocol_registration_uses_pin_backend():
    registered = fsspec.filesystem("filecoin", skip_instance_cache=True)

    assert isinstance(registered, FilecoinFileSystem)
    assert registered.backend == "filecoin"
    status = registered.get_backend_status()
    assert status["provider"] == "filecoin_pin"
    assert status["mock_mode"] is True


def test_put_file_info_exists_ls_and_cached_retrieval(fs, tmp_path):
    source = tmp_path / "source.txt"
    target = tmp_path / "download.txt"
    source.write_bytes(b"uploaded through filecoin pin")

    fs.put_file(str(source), "filecoin://uploads/source.txt")
    info = fs.info("filecoin://uploads/source.txt")

    assert info["name"].startswith("filecoin://bafy")
    assert info["alias"] == "filecoin://uploads/source.txt"
    assert info["type"] == "file"
    assert info["size"] == len(b"uploaded through filecoin pin")
    assert info["status"] == "pinned"
    assert info["request_id"].startswith("req-")
    assert info["deal_ids"] == ["deal-1", "deal-2"]
    assert info["filename"] == "source.txt"
    assert fs.exists("filecoin://uploads/source.txt") is True

    listing = fs.ls("filecoin://", detail=True)
    names = fs.ls("filecoin://", detail=False)
    assert info["name"] in [item["name"] for item in listing]
    assert names == [item["name"] for item in listing]

    assert fs.cat_file("filecoin://uploads/source.txt") == b"uploaded through filecoin pin"
    assert fs.cat_file(info["name"], start=9, end=16) == b"through"

    with fs.open(info["name"], "rb") as handle:
        assert handle.read() == b"uploaded through filecoin pin"

    fs.get_file(info["name"], str(target))
    assert target.read_bytes() == b"uploaded through filecoin pin"


def test_pipe_file_uploads_bytes_and_records_pin_metadata(fs):
    fs.pipe_file("filecoin://pipe/data.bin", b"pipe payload", metadata={"replication": 5})
    info = fs.info("filecoin://pipe/data.bin")

    assert info["name"].startswith("filecoin://bafy")
    assert info["replication"] == 5
    assert info["status"] == "pinned"
    assert fs.exists(info["name"]) is True


def test_retrieve_by_cid_when_retrieval_is_configured(tmp_path):
    uploader = FilecoinFileSystem(skip_instance_cache=True)
    client = FakeFilecoinPinClient()
    uploader.filecoin_client = client
    uploader.pipe_file("filecoin://payload.bin", b"retrieved by cid")
    cid = uploader.info("filecoin://payload.bin")["cid"]

    retriever = FilecoinFileSystem(
        metadata={"retrieval_enabled": True},
        skip_instance_cache=True,
    )
    retriever.filecoin_client = client

    assert retriever.cat_file(f"filecoin://{cid}") == b"retrieved by cid"


def test_retrieval_fails_clearly_when_unavailable():
    filesystem = FilecoinFileSystem(skip_instance_cache=True)
    filesystem.filecoin_client = FakeFilecoinPinClient()

    with pytest.raises(NotImplementedError, match="Filecoin pin retrieval is not configured"):
        filesystem.cat_file("filecoin://bafybeibmissing")


def test_open_write_modes_are_explicitly_unsupported(fs):
    fs.pipe_file("filecoin://readonly.bin", b"content")

    with pytest.raises(NotImplementedError, match="supports only 'rb'"):
        fs.open("filecoin://readonly.bin", "wb")


def test_filecoin_pin_fsspec_module_exports_registration():
    assert filecoin_pin_fsspec.FilecoinFileSystem is FilecoinFileSystem
    assert filecoin_pin_fsspec.FilecoinPinFileSystem is FilecoinPinFileSystem


def test_filecoin_missing_dependency_falls_back_to_in_memory_mock(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "ipfs_kit_py.mcp.storage_manager.backends.filecoin_pin_backend",
        None,
    )

    filesystem = FilecoinFileSystem(skip_instance_cache=True)

    status = filesystem.get_backend_status()
    assert status["mock_mode"] is True
    assert status["api_endpoint"] == "mock://filecoin-pin"
    filesystem.pipe_file("filecoin://mock-only.txt", b"dependency-free")
    assert filesystem.info("filecoin://mock-only.txt")["status"] == "pinned"


def test_filecoin_missing_dependency_can_be_required_for_live_mode(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "ipfs_kit_py.mcp.storage_manager.backends.filecoin_pin_backend",
        None,
    )

    with pytest.raises(ImportError):
        FilecoinFileSystem(metadata={"require_live": True}, skip_instance_cache=True)


@pytest.mark.skipif(
    not (os.getenv("IPFS_KIT_LIVE_FILECOIN_PIN") and os.getenv("FILECOIN_PIN_API_KEY")),
    reason="set IPFS_KIT_LIVE_FILECOIN_PIN=1 and FILECOIN_PIN_API_KEY to run live Filecoin pin fsspec smoke tests",
)
def test_live_filecoin_pin_status_requires_explicit_env_gate():
    filesystem = FilecoinFileSystem(
        metadata={"api_key": os.environ["FILECOIN_PIN_API_KEY"], "require_live": True},
        skip_instance_cache=True,
    )

    status = filesystem.get_backend_status()

    assert status["backend"] == "filecoin"
    assert status["provider"] == "filecoin_pin"
    assert status["mock_mode"] is False
