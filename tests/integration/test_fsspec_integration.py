import httpx


def test_create_walrus_filesystem_from_explicit_kwargs(tmp_path):
    from ipfs_kit_py.high_level_api import create_walrus_filesystem
    from ipfs_kit_py.walrus_fsspec import WalrusFileSystem

    fs = create_walrus_filesystem(
        aggregator_url="https://explicit-aggregator.test",
        index_path=tmp_path / "index.json",
        transport=httpx.MockTransport(lambda request: httpx.Response(404)),
        skip_instance_cache=True,
    )

    assert isinstance(fs, WalrusFileSystem)
    assert fs.client.aggregator_url == "https://explicit-aggregator.test"


def test_create_walrus_filesystem_uses_config_and_explicit_precedence(tmp_path):
    from ipfs_kit_py.high_level_api import create_walrus_filesystem

    fs = create_walrus_filesystem(
        {
            "walrus": {
                "publisher_url": "https://config-publisher.test",
                "aggregator_url": "https://config-aggregator.test",
                "epochs": 3,
                "index_path": tmp_path / "config-index.json",
            }
        },
        aggregator_url="https://explicit-aggregator.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(404)),
        skip_instance_cache=True,
    )

    assert fs.client.publisher_url == "https://config-publisher.test"
    assert fs.client.aggregator_url == "https://explicit-aggregator.test"
    assert fs.client.epochs == 3


def test_high_level_api_can_create_walrus_filesystem_from_loaded_config(tmp_path):
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI

    api = IPFSSimpleAPI.__new__(IPFSSimpleAPI)
    api.config = {
        "walrus": {
            "aggregator_url": "https://config-aggregator.test",
            "index_path": tmp_path / "index.json",
        }
    }

    fs = api.create_walrus_filesystem(
        transport=httpx.MockTransport(lambda request: httpx.Response(404)),
        skip_instance_cache=True,
    )

    assert fs.protocol == "walrus"
    assert fs.client.aggregator_url == "https://config-aggregator.test"


def test_vfs_registry_reports_and_creates_walrus_backend(tmp_path):
    from ipfs_kit_py.ipfs_fsspec import VFSBackendRegistry, get_available_vfs_backends
    from ipfs_kit_py.walrus_fsspec import WalrusFileSystem

    registry = VFSBackendRegistry()

    assert registry.get_backend("walrus")["available"] is True
    assert "walrus" in registry.available_backends()
    assert "walrus" in get_available_vfs_backends()

    fs = registry.create_filesystem(
        "walrus",
        aggregator_url="https://aggregator.test",
        index_path=tmp_path / "index.json",
        transport=httpx.MockTransport(lambda request: httpx.Response(404)),
        skip_instance_cache=True,
    )

    assert isinstance(fs, WalrusFileSystem)
