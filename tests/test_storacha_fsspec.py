"""Tests for Storacha fsspec list/read/write/delete behavior."""

import fsspec
import pytest

from ipfs_kit_py import storacha_fsspec
from ipfs_kit_py.enhanced_fsspec import StorachaFileSystem


@pytest.fixture
def fs(monkeypatch):
    monkeypatch.delenv("STORACHA_API_KEY", raising=False)
    return StorachaFileSystem(skip_instance_cache=True)


def test_storacha_protocol_registration_uses_storacha_backend(monkeypatch):
    monkeypatch.delenv("STORACHA_API_KEY", raising=False)

    registered = fsspec.filesystem("storacha", skip_instance_cache=True)

    assert isinstance(registered, StorachaFileSystem)
    assert registered.backend == "storacha"
    assert registered.get_backend_status()["mock_mode"] is True


def test_put_file_ls_info_cat_open_and_get_file_round_trip(fs, tmp_path):
    source = tmp_path / "source.txt"
    target = tmp_path / "download.txt"
    source.write_bytes(b"uploaded through storacha")

    fs.put_file(str(source), "storacha://uploads/source.txt")
    info = fs.info("storacha://uploads/source.txt")

    assert info["name"].startswith("storacha://bafy")
    assert info["alias"] == "storacha://uploads/source.txt"
    assert info["type"] == "file"
    assert info["size"] == len(b"uploaded through storacha")
    assert info["filename"] == "source.txt"
    assert info["mock"] is True
    assert fs.exists("storacha://uploads/source.txt") is True

    listing = fs.ls("storacha://", detail=True)
    names = fs.ls("storacha://", detail=False)
    assert info["name"] in [item["name"] for item in listing]
    assert names == [item["name"] for item in listing]

    assert fs.cat_file("storacha://uploads/source.txt") == b"uploaded through storacha"
    assert fs.cat_file("storacha://uploads/source.txt", start=9, end=16) == b"through"

    with fs.open("storacha://uploads/source.txt", "rb") as handle:
        assert handle.read() == b"uploaded through storacha"

    fs.get_file("storacha://uploads/source.txt", str(target))
    assert target.read_bytes() == b"uploaded through storacha"


def test_pipe_file_delete_and_missing_info(fs):
    fs.pipe_file("storacha://pipe/data.bin", b"pipe payload")
    info = fs.info("storacha://pipe/data.bin")

    assert info["name"].startswith("storacha://bafy")
    assert fs.cat_file(info["name"]) == b"pipe payload"

    fs.rm("storacha://pipe/data.bin")

    assert fs.exists("storacha://pipe/data.bin") is False
    with pytest.raises(FileNotFoundError):
        fs.info("storacha://pipe/data.bin")


def test_open_write_modes_are_explicitly_unsupported(fs):
    fs.pipe_file("storacha://readonly.bin", b"content")

    with pytest.raises(NotImplementedError, match="supports only 'rb'"):
        fs.open("storacha://readonly.bin", "wb")


def test_storacha_fsspec_module_exports_registration():
    assert storacha_fsspec.StorachaFileSystem is StorachaFileSystem
