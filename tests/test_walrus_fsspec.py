import httpx
import pytest

from ipfs_kit_py.walrus_storage import WalrusConfigurationError


@pytest.fixture(autouse=True)
def clear_walrus_env(monkeypatch):
    for name in (
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
    ):
        monkeypatch.delenv(name, raising=False)


def test_fsspec_filesystem_registration(tmp_path):
    import fsspec
    import ipfs_kit_py.walrus_fsspec  # noqa: F401
    from ipfs_kit_py.walrus_fsspec import WalrusFileSystem

    fs = fsspec.filesystem(
        "walrus",
        aggregator_url="https://aggregator.test",
        index_path=tmp_path / "index.json",
        skip_instance_cache=True,
    )

    assert isinstance(fs, WalrusFileSystem)


def test_pipe_cat_open_info_exists_ls_ukey_and_rm(tmp_path):
    from ipfs_kit_py.walrus_fsspec import WalrusFileSystem

    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "PUT":
            assert request.url == "https://publisher.test/v1/blobs?epochs=4&deletable=true"
            assert request.content == b"hello walrus"
            return httpx.Response(
                200,
                json={
                    "newlyCreated": {
                        "blobObject": {
                            "blobId": "blob-written",
                            "id": "object-written",
                            "size": 12,
                            "storage": {"endEpoch": 20},
                        },
                        "event": {"txDigest": "tx-written"},
                        "cost": 8,
                    }
                },
            )
        if request.method == "GET":
            assert request.url == "https://aggregator.test/v1/blobs/blob-written"
            if "range" in request.headers:
                assert request.headers["range"] == "bytes=6-11"
                return httpx.Response(206, content=b"walrus")
            return httpx.Response(200, content=b"hello walrus")
        if request.method == "DELETE":
            assert request.url == (
                "https://delete.test/v1/blobs/blob-written?objectId=object-written"
            )
            return httpx.Response(200, json={"deleted": True})
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    fs = WalrusFileSystem(
        publisher_url="https://publisher.test",
        aggregator_url="https://aggregator.test",
        delete_url="https://delete.test",
        epochs=4,
        deletable=True,
        index_path=tmp_path / "index.json",
        transport=httpx.MockTransport(handler),
        skip_instance_cache=True,
    )

    entry = fs.pipe_file("walrus://docs/readme.txt", b"hello walrus", content_type="text/plain")
    assert entry["blob_id"] == "blob-written"
    assert entry["object_id"] == "object-written"

    assert fs.cat_file("walrus://docs/readme.txt") == b"hello walrus"
    assert fs.cat_file("walrus://docs/readme.txt", start=6, end=12) == b"walrus"
    with fs.open("walrus://docs/readme.txt", "rb") as handle:
        assert handle.read() == b"hello walrus"

    info = fs.info("walrus://docs/readme.txt")
    assert info["name"] == "docs/readme.txt"
    assert info["type"] == "file"
    assert info["size"] == 12
    assert info["blob_id"] == "blob-written"
    assert info["content_type"] == "text/plain"
    assert fs.exists("walrus://docs/readme.txt") is True
    assert fs.ukey("walrus://docs/readme.txt") == "blob-written"

    assert fs.ls("walrus://", detail=False) == ["docs/readme.txt"]
    assert fs.ls("walrus://docs", detail=False) == ["docs/readme.txt"]

    fs.rm("walrus://docs/readme.txt")
    assert fs.exists("walrus://docs/readme.txt") is False
    assert fs.ls("walrus://") == []
    assert [request.method for request in requests] == ["PUT", "GET", "GET", "GET", "DELETE"]


def test_put_file_and_get_file_round_trip_with_index(tmp_path):
    from ipfs_kit_py.walrus_fsspec import WalrusFileSystem

    source = tmp_path / "source.bin"
    dest = tmp_path / "downloaded.bin"
    source.write_bytes(b"local bytes")

    def handler(request):
        if request.method == "PUT":
            assert request.content == b"local bytes"
            return httpx.Response(200, json={"blobId": "blob-local", "blobSize": 11})
        if request.method == "GET":
            assert request.url == "https://aggregator.test/v1/blobs/blob-local"
            return httpx.Response(200, content=b"local bytes")
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    fs = WalrusFileSystem(
        publisher_url="https://publisher.test",
        aggregator_url="https://aggregator.test",
        index_path=tmp_path / "index.json",
        transport=httpx.MockTransport(handler),
        skip_instance_cache=True,
    )

    fs.put_file(str(source), "walrus://uploads/source.bin")
    fs.get_file("walrus://uploads/source.bin", str(dest))

    assert dest.read_bytes() == b"local bytes"
    assert fs.info("walrus://uploads/source.bin")["blob_id"] == "blob-local"


def test_direct_blob_id_read_info_exists_and_ukey(tmp_path):
    from ipfs_kit_py.walrus_fsspec import WalrusFileSystem

    def handler(request):
        if request.method == "HEAD":
            assert request.url == "https://aggregator.test/v1/blobs/blob-direct"
            return httpx.Response(
                200,
                headers={"content-length": "6", "content-type": "application/octet-stream"},
            )
        if request.method == "GET":
            assert request.url == "https://aggregator.test/v1/blobs/blob-direct"
            return httpx.Response(200, content=b"direct")
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    fs = WalrusFileSystem(
        aggregator_url="https://aggregator.test",
        index_path=tmp_path / "index.json",
        transport=httpx.MockTransport(handler),
        skip_instance_cache=True,
    )

    assert fs.cat_file("walrus://blob-direct") == b"direct"
    assert fs.info("walrus://blob-direct") == {
        "name": "blob-direct",
        "type": "file",
        "size": 6,
        "blob_id": "blob-direct",
        "content_type": "application/octet-stream",
    }
    assert fs.exists("walrus://blob-direct") is True
    assert fs.ukey("walrus://blob-direct") == "blob-direct"
    assert fs.ls("walrus://") == []


def test_direct_blob_id_read_surfaces_extracted_walrus_error(tmp_path):
    from ipfs_kit_py.walrus_fsspec import WalrusFileSystem

    def handler(request):
        assert request.method == "GET"
        assert request.url == "https://aggregator.test/v1/blobs/blob-missing"
        return httpx.Response(404, json={"error": {"message": "blob is not certified"}})

    fs = WalrusFileSystem(
        aggregator_url="https://aggregator.test",
        index_path=tmp_path / "index.json",
        transport=httpx.MockTransport(handler),
        skip_instance_cache=True,
    )

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        fs.cat_file("walrus://blob-missing")

    assert exc_info.value.response.status_code == 404
    assert "blob is not certified" in str(exc_info.value)


def test_open_write_uploads_on_close(tmp_path):
    from ipfs_kit_py.walrus_fsspec import WalrusFileSystem

    def handler(request):
        assert request.method == "PUT"
        assert request.content == b"buffered"
        return httpx.Response(200, json={"blobId": "blob-buffered", "blobSize": 8})

    fs = WalrusFileSystem(
        publisher_url="https://publisher.test",
        index_path=tmp_path / "index.json",
        transport=httpx.MockTransport(handler),
        skip_instance_cache=True,
    )

    with fs.open("walrus://buffered.bin", "wb") as handle:
        handle.write(b"buffered")

    assert fs.info("walrus://buffered.bin")["blob_id"] == "blob-buffered"


def test_missing_configuration_errors_are_clear(tmp_path):
    from ipfs_kit_py.walrus_fsspec import WalrusFileSystem

    fs = WalrusFileSystem(
        index_path=tmp_path / "index.json",
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
        skip_instance_cache=True,
    )

    with pytest.raises(WalrusConfigurationError, match="publisher URL"):
        fs.pipe_file("walrus://name.txt", b"data")

    fs.client.update_index("name.txt", {"blob_id": "blob-id", "object_id": "object-id"})
    with pytest.raises(WalrusConfigurationError, match="delete URL"):
        fs.rm("walrus://name.txt")
