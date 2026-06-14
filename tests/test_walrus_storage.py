import httpx
import pytest

from ipfs_kit_py.walrus_storage import (
    WalrusConfigurationError,
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
