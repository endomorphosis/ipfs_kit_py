import json

import pytest

from ipfs_kit_py.fsspec_utils import (
    LocalMetadataIndex,
    backend_capabilities,
    ensure_protocol,
    is_content_id,
    normalize_metadata,
    normalize_protocol_path,
    raise_for_fsspec_result,
    read_json_index,
    standard_file_info,
    strip_protocol,
    write_json_index,
)


def test_strip_ensure_and_normalize_protocol_paths():
    assert strip_protocol("storacha://bafybeigdyrzt", ["storacha", "filecoin"]) == "bafybeigdyrzt"
    assert strip_protocol(["filecoin://cid", "plain"], "filecoin") == ["cid", "plain"]
    assert ensure_protocol("docs/readme.txt", "synapse") == "synapse://docs/readme.txt"
    assert ensure_protocol("storacha://cid", "filecoin", ["storacha", "filecoin"]) == "storacha://cid"
    assert normalize_protocol_path("/uploads/file.txt", "walrus") == "walrus://uploads/file.txt"
    assert normalize_protocol_path("filecoin://bafybeigdyrzt", "filecoin") == "filecoin://bafybeigdyrzt"


def test_is_content_id_recognizes_common_cid_shapes():
    assert is_content_id("QmYwAPJzv5CZsnAzt8auVTLJdMNbKjXrJLCJ4G7N9QLQ6N") is True
    assert is_content_id("bafybeigdyrzt5sfp7udm7hu76n7fd6wq2fqbc5lyh2vbcxq4wqt2xz7u4a") is True
    assert is_content_id("/ipfs/baga6ea4seaqao7s73y24kcutaosvacpdjgfe5pw76ooefnyqw4ynr3d2y6x2mpq") is True
    assert is_content_id("uploads/readme.txt") is False
    assert is_content_id(None) is False


def test_normalize_metadata_and_standard_file_info_skip_none_values():
    metadata = normalize_metadata({"cid": "bafy", "size": None}, {"backend": "storacha"}, content_type=None)

    assert metadata == {"cid": "bafy", "backend": "storacha"}

    info = standard_file_info(
        "bafy",
        protocol="storacha",
        size="42",
        metadata=metadata,
        exists=True,
    )

    assert info == {
        "cid": "bafy",
        "backend": "storacha",
        "exists": True,
        "name": "storacha://bafy",
        "type": "file",
        "size": 42,
    }


def test_json_index_read_write_and_local_metadata_index(tmp_path):
    index_path = tmp_path / "index.json"

    assert read_json_index(index_path)["items"] == {}

    write_json_index(index_path, {"items": {"docs/readme.txt": {"cid": "bafy"}}})
    assert json.loads(index_path.read_text())["items"]["docs/readme.txt"]["cid"] == "bafy"

    index = LocalMetadataIndex(index_path, protocol="storacha")
    entry = index.update("storacha://docs/manual.txt", {"cid": "bafy2", "size": 5})

    assert entry["name"] == "docs/manual.txt"
    assert index.get("/docs/manual.txt")["cid"] == "bafy2"
    assert sorted(index.list_items()) == ["docs/manual.txt", "docs/readme.txt"]
    assert index.remove("storacha://docs/manual.txt")["cid"] == "bafy2"
    assert index.get("storacha://docs/manual.txt") is None


def test_read_json_index_rejects_non_object_payload(tmp_path):
    index_path = tmp_path / "bad.json"
    index_path.write_text("[]")

    with pytest.raises(ValueError, match="JSON object"):
        read_json_index(index_path)


def test_backend_capabilities_are_normalized_and_extensible():
    report = backend_capabilities(
        "filecoin",
        protocol="filecoin",
        writable=True,
        delete=False,
        local_index=True,
        provider="filecoin_pin",
    )

    assert report["backend"] == "filecoin"
    assert report["protocol"] == "filecoin"
    assert report["provider"] == "filecoin_pin"
    assert report["readable"] is True
    assert report["writable"] is True
    assert report["delete"] is False
    assert report["local_index"] is True
    assert report["content_addressed"] is True
    assert report["mutable_paths"] is False


def test_walrus_filesystem_exposes_shared_capability_report(tmp_path):
    from ipfs_kit_py.walrus_fsspec import WalrusFileSystem

    fs = WalrusFileSystem(
        publisher_url="https://publisher.test",
        aggregator_url="https://aggregator.test",
        delete_url="https://delete.test",
        index_path=tmp_path / "index.json",
        skip_instance_cache=True,
    )

    status = fs.get_backend_status()

    assert status["backend"] == "walrus"
    assert status["protocol"] == "walrus"
    assert status["local_index"] is True
    assert status["delete"] is True
    assert status["index_path"] == str(tmp_path / "index.json")


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ({"success": False, "status": 404, "error": "missing"}, FileNotFoundError),
        ({"success": False, "status": 409, "error": "already exists"}, FileExistsError),
        ({"success": False, "status": 403, "error": "forbidden"}, PermissionError),
        ({"success": False, "error": "service unavailable"}, OSError),
    ],
)
def test_raise_for_fsspec_result_maps_common_backend_failures(result, expected):
    with pytest.raises(expected, match="Storacha read failed for storacha://missing"):
        raise_for_fsspec_result(
            result,
            backend="Storacha",
            operation="read",
            path="storacha://missing",
        )


def test_raise_for_fsspec_result_accepts_successful_result():
    raise_for_fsspec_result({"success": True}, backend="Walrus", operation="head")
