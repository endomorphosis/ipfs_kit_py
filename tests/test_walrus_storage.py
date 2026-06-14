import json

import httpx
import pytest

from ipfs_kit_py.walrus_storage import (
    WALRUS_INDEX_SCHEMA,
    WalrusBlobInfo,
    WalrusConfigurationError,
    WalrusMetadataIndex,
    WalrusStorageClient,
)


@pytest.fixture(autouse=True)
def clear_walrus_env(monkeypatch):
    names = [
        "WALRUS_PUBLISHER_URL",
        "WALRUS_AGGREGATOR_URL",
        "WALRUS_DELETE_URL",
        "WALRUS_CLIENT_TOKEN",
        "WALRUS_EPOCHS",
        "WALRUS_DELETABLE",
        "ABBY_RUNTIME_WALRUS_PUBLISHER_URL",
        "ABBY_RUNTIME_WALRUS_AGGREGATOR_URL",
        "ABBY_RUNTIME_WALRUS_DELETE_URL",
        "ABBY_RUNTIME_WALRUS_CLIENT_TOKEN",
        "ABBY_RUNTIME_WALRUS_EPOCHS",
        "ABBY_RUNTIME_WALRUS_DELETABLE",
        "VITE_WALRUS_STORAGE_PUBLISHER_URL",
        "VITE_WALRUS_STORAGE_AGGREGATOR_URL",
        "VITE_WALRUS_STORAGE_DELETE_URL",
        "VITE_WALRUS_STORAGE_CLIENT_TOKEN",
        "VITE_WALRUS_STORAGE_EPOCHS",
        "VITE_WALRUS_STORAGE_DELETABLE",
    ]
    for name in names:
        monkeypatch.delenv(name, raising=False)


def test_resolves_urls_with_query_flags_and_templates():
    client = WalrusStorageClient(
        publisher_url="https://publisher.test",
        aggregator_url="https://aggregator.test/api",
        delete_url="https://delete.test/blob/{blobId}/object/{objectId}/record/{recordId}",
        epochs=5,
        deletable=True,
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    assert (
        client.resolve_publisher_blob_url()
        == "https://publisher.test/v1/blobs?epochs=5&deletable=true"
    )
    assert (
        client.resolve_publisher_blob_url(epochs=2, deletable=False, permanent=True)
        == "https://publisher.test/v1/blobs?epochs=2&deletable=false&permanent=true"
    )
    assert (
        client.resolve_aggregator_blob_url("blob/id")
        == "https://aggregator.test/api/v1/blobs/blob%2Fid"
    )
    assert (
        client.resolve_delete_url("blob-id", object_id="object-id", record_id="record-id")
        == "https://delete.test/blob/blob-id/object/object-id/record/record-id"
    )


def test_environment_fallbacks(monkeypatch):
    monkeypatch.setenv("ABBY_RUNTIME_WALRUS_PUBLISHER_URL", "https://abby-publisher.test")
    monkeypatch.setenv("VITE_WALRUS_STORAGE_AGGREGATOR_URL", "https://vite-aggregator.test")
    monkeypatch.setenv("WALRUS_DELETE_URL", "https://delete.test")
    monkeypatch.setenv("WALRUS_CLIENT_TOKEN", "secret")
    monkeypatch.setenv("WALRUS_EPOCHS", "7")
    monkeypatch.setenv("WALRUS_DELETABLE", "false")

    client = WalrusStorageClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    )

    assert client.publisher_url == "https://abby-publisher.test"
    assert client.aggregator_url == "https://vite-aggregator.test"
    assert client.delete_url == "https://delete.test"
    assert client.client_token == "secret"
    assert client.epochs == 7
    assert client.deletable is False
    assert client.status()["auth_configured"] is True


def test_upload_retrieve_head_and_delete_use_mocked_http():
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "PUT":
            assert request.url == "https://publisher.test/v1/blobs?epochs=3&deletable=true"
            assert request.headers["authorization"] == "Bearer token"
            assert request.headers["content-type"] == "text/plain"
            assert request.content == b"hello"
            return httpx.Response(
                200,
                json={
                    "newlyCreated": {
                        "blobObject": {
                            "blobId": "blob-123",
                            "id": "object-123",
                            "storage": {"endEpoch": 9},
                            "size": 5,
                        },
                        "event": {"txDigest": "tx-123"},
                        "cost": 42,
                    }
                },
            )
        if request.method == "GET":
            assert request.url == "https://aggregator.test/v1/blobs/blob-123"
            assert request.headers["range"] == "bytes=1-3"
            return httpx.Response(206, content=b"ell")
        if request.method == "HEAD":
            assert request.url == "https://aggregator.test/v1/blobs/blob-123"
            return httpx.Response(
                200,
                headers={"content-length": "5", "content-type": "text/plain"},
            )
        if request.method == "DELETE":
            assert request.url == "https://delete.test/v1/blobs/blob-123?objectId=object-123"
            return httpx.Response(200, json={"deleted": True})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = WalrusStorageClient(
        publisher_url="https://publisher.test",
        aggregator_url="https://aggregator.test",
        delete_url="https://delete.test",
        client_token="token",
        epochs=3,
        deletable=True,
        transport=httpx.MockTransport(handler),
    )

    info = client.put_blob(b"hello", content_type="text/plain")
    assert info.blob_id == "blob-123"
    assert info.object_id == "object-123"
    assert info.tx_digest == "tx-123"
    assert info.end_epoch == 9
    assert info.cost == 42
    assert info.size == 5

    assert client.get_blob("blob-123", start=1, end=4) == b"ell"
    assert client.head_blob("blob-123") == {
        "status_code": 200,
        "headers": {"content-length": "5", "content-type": "text/plain"},
        "content_length": 5,
        "content_type": "text/plain",
    }
    assert client.delete_blob("blob-123", object_id="object-123") == {
        "success": True,
        "status_code": 200,
        "deleted": True,
    }
    assert [request.method for request in requests] == ["PUT", "GET", "HEAD", "DELETE"]


def test_normalizes_top_level_response():
    info = WalrusStorageClient.normalize_response(
        {
            "blobId": "blob-top",
            "blobObjectId": "object-top",
            "txDigest": "tx-top",
            "storage": {"end_epoch": "11"},
            "storageCost": "99",
            "blobSize": "100",
            "gatewayUrl": "https://gateway.test/v1/blobs/blob-top",
        }
    )

    assert info.blob_id == "blob-top"
    assert info.object_id == "object-top"
    assert info.tx_digest == "tx-top"
    assert info.end_epoch == 11
    assert info.cost == 99
    assert info.size == 100
    assert info.gateway_url == "https://gateway.test/v1/blobs/blob-top"


def test_normalizes_snake_case_newly_created_response():
    info = WalrusStorageClient.normalize_response(
        {
            "newlyCreated": {
                "blob_object": {
                    "blob_id": "blob-new",
                    "object_id": "object-new",
                    "storage": {"end_epoch": 12},
                    "size": "6",
                },
                "event": {"tx_digest": "tx-new"},
                "cost": "77",
            }
        }
    )

    assert info.blob_id == "blob-new"
    assert info.object_id == "object-new"
    assert info.tx_digest == "tx-new"
    assert info.end_epoch == 12
    assert info.cost == 77
    assert info.size == 6


def test_normalizes_already_certified_response():
    info = WalrusStorageClient.normalize_response(
        {
            "alreadyCertified": {
                "blob_id": "blob-certified",
                "blob_object_id": "object-certified",
                "event": {"txDigest": "tx-certified"},
                "storage": {"endEpoch": 13},
                "cost": 3,
                "size": 4,
            }
        }
    )

    assert info.blob_id == "blob-certified"
    assert info.object_id == "object-certified"
    assert info.tx_digest == "tx-certified"
    assert info.end_epoch == 13
    assert info.cost == 3
    assert info.size == 4


def test_missing_operation_urls_raise_clear_errors():
    client = WalrusStorageClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(500))
    )

    with pytest.raises(WalrusConfigurationError, match="publisher URL"):
        client.resolve_publisher_blob_url()
    with pytest.raises(WalrusConfigurationError, match="aggregator URL"):
        client.resolve_aggregator_blob_url("blob-id")
    with pytest.raises(WalrusConfigurationError, match="delete URL"):
        client.resolve_delete_url("blob-id")


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(400, text="plain failure"), "plain failure"),
        (httpx.Response(400, json={"message": "message failure"}), "message failure"),
        (httpx.Response(400, json={"error": "error failure"}), "error failure"),
        (
            httpx.Response(400, json={"error": {"message": "nested failure"}}),
            "nested failure",
        ),
    ],
)
def test_extracts_error_messages_from_walrus_responses(response, expected):
    assert WalrusStorageClient.extract_error_message(response) == expected


def test_http_errors_include_extracted_walrus_message():
    def handler(request):
        return httpx.Response(
            400,
            json={"error": {"message": "insufficient storage budget"}},
        )

    client = WalrusStorageClient(
        publisher_url="https://publisher.test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        client.put_blob(b"payload")

    assert exc_info.value.response.status_code == 400
    assert "insufficient storage budget" in str(exc_info.value)


def test_metadata_index_defaults_to_cache_path(monkeypatch, tmp_path):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    index = WalrusMetadataIndex()

    assert index.path == tmp_path / ".cache" / "ipfs_kit_py" / "walrus" / "index.json"
    assert index.load() == {"schema": WALRUS_INDEX_SCHEMA, "items": {}}


def test_metadata_index_update_load_get_and_remove_are_atomic(tmp_path):
    index_path = tmp_path / "walrus" / "index.json"
    index = WalrusMetadataIndex(index_path)

    entry = index.update(
        "walrus://datasets/example.txt",
        WalrusBlobInfo(
            blob_id="blob-123",
            object_id="object-123",
            tx_digest="tx-123",
            end_epoch=9,
            cost=42,
            size=5,
            gateway_url="https://aggregator.test/v1/blobs/blob-123",
        ),
        content_type="text/plain",
    )

    assert entry["name"] == "datasets/example.txt"
    assert entry["blob_id"] == "blob-123"
    assert entry["object_id"] == "object-123"
    assert entry["tx_digest"] == "tx-123"
    assert entry["end_epoch"] == 9
    assert entry["cost"] == 42
    assert entry["size"] == 5
    assert entry["content_type"] == "text/plain"
    assert entry["gateway_url"] == "https://aggregator.test/v1/blobs/blob-123"
    assert entry["created_at"].endswith("Z")

    on_disk = json.loads(index_path.read_text(encoding="utf-8"))
    assert on_disk == {
        "schema": WALRUS_INDEX_SCHEMA,
        "items": {"datasets/example.txt": entry},
    }
    assert index.get("/datasets/example.txt") == entry
    assert index.list_items() == {"datasets/example.txt": entry}
    assert list(index_path.parent.glob("*.tmp")) == []

    removed = index.remove("datasets/example.txt")

    assert removed == entry
    assert index.load() == {"schema": WALRUS_INDEX_SCHEMA, "items": {}}


def test_metadata_index_preserves_supplied_created_at_and_custom_fields(tmp_path):
    index = WalrusMetadataIndex(tmp_path / "index.json")

    entry = index.update(
        "name.bin",
        {
            "blob_id": "blob-abc",
            "content_type": "application/octet-stream",
            "created_at": "2026-06-13T00:00:00Z",
            "ignored": "value",
        },
    )

    assert entry == {
        "name": "name.bin",
        "created_at": "2026-06-13T00:00:00Z",
        "blob_id": "blob-abc",
        "content_type": "application/octet-stream",
    }


def test_storage_client_exposes_metadata_index_operations(tmp_path):
    client = WalrusStorageClient(
        index_path=tmp_path / "walrus-index.json",
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    entry = client.update_index(
        "logical/path.txt",
        {"blob_id": "blob-path", "size": 12},
        content_type="text/plain",
    )

    assert client.status()["index_path"] == str(tmp_path / "walrus-index.json")
    assert client.load_index()["items"] == {"logical/path.txt": entry}
    assert client.get_index_entry("walrus://logical/path.txt") == entry
    assert client.remove_index_entry("logical/path.txt") == entry
    assert client.get_index_entry("logical/path.txt") is None
