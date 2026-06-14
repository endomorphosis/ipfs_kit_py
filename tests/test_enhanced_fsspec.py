import sys
import types

import fsspec
import pytest

from ipfs_kit_py import enhanced_fsspec


class _Client:
    def __init__(self, resources=None, metadata=None):
        self.resources = resources or {}
        self.metadata = metadata or {}


def _module(name, attr):
    module = types.ModuleType(name)
    setattr(module, attr, _Client)
    return module


BACKEND_MODULES = {
    "ipfs": ("ipfs_kit_py.ipfs_kit", "ipfs_kit"),
    "filecoin": ("ipfs_kit_py.lotus_kit", "lotus_kit"),
    "storacha": ("ipfs_kit_py.storacha_kit", "storacha_kit"),
    "synapse": ("ipfs_kit_py.synapse_storage", "synapse_storage"),
}


EXPECTED_CLASSES = {
    "ipfs": enhanced_fsspec.EnhancedIPFSFileSystem,
    "filecoin": enhanced_fsspec.FilecoinFileSystem,
    "storacha": enhanced_fsspec.StorachaFileSystem,
    "synapse": enhanced_fsspec.SynapseFileSystem,
}


@pytest.mark.parametrize("protocol", ["ipfs", "synapse", "storacha", "filecoin"])
def test_fsspec_filesystem_protocol_selects_intended_backend(monkeypatch, protocol):
    """Each protocol constructs its own backend without importing other backends."""
    intended_module, intended_attr = BACKEND_MODULES[protocol]

    for module_name in BACKEND_MODULES.values():
        monkeypatch.setitem(sys.modules, module_name[0], None)
    monkeypatch.setitem(
        sys.modules,
        intended_module,
        _module(intended_module, intended_attr),
    )

    fs = fsspec.filesystem(protocol, skip_instance_cache=True)

    assert isinstance(fs, EXPECTED_CLASSES[protocol])
    assert fs.backend == protocol


def test_registered_protocols_use_distinct_filesystem_classes():
    classes = {
        protocol: fsspec.get_filesystem_class(protocol)
        for protocol in ["ipfs", "synapse", "storacha", "filecoin"]
    }

    assert classes == EXPECTED_CLASSES
    assert len(set(classes.values())) == len(classes)


def test_protocol_specific_class_rejects_conflicting_backend(monkeypatch):
    module_name, attr = BACKEND_MODULES["synapse"]
    monkeypatch.setitem(sys.modules, module_name, _module(module_name, attr))

    with pytest.raises(ValueError, match="registered for the 'synapse' backend"):
        fsspec.filesystem("synapse", backend="ipfs", skip_instance_cache=True)


def test_base_filesystem_still_allows_explicit_backend(monkeypatch):
    module_name, attr = BACKEND_MODULES["synapse"]
    monkeypatch.setitem(sys.modules, module_name, _module(module_name, attr))

    fs = enhanced_fsspec.IPFSFileSystem(backend="synapse")

    assert type(fs) is enhanced_fsspec.IPFSFileSystem
    assert fs.backend == "synapse"


def test_mock_compatibility_matrix_has_expected_backend_metadata(monkeypatch):
    """Compatibility matrix: protocol classes expose deterministic mock-safe metadata."""
    monkeypatch.delenv("STORACHA_API_KEY", raising=False)
    monkeypatch.setitem(
        sys.modules,
        "ipfs_kit_py.mcp.storage_manager.backends.filecoin_pin_backend",
        None,
    )

    storacha = fsspec.filesystem("storacha", skip_instance_cache=True)
    filecoin = fsspec.filesystem("filecoin", skip_instance_cache=True)

    assert storacha.get_backend_status() == {
        "backend": "storacha",
        "connected": True,
        "mock_mode": True,
        "api_url": "mock://storacha",
        "space": "mock-space",
    }
    assert filecoin.get_backend_status() == {
        "backend": "filecoin",
        "provider": "filecoin_pin",
        "connected": True,
        "mock_mode": True,
        "retrieval_enabled": False,
        "api_endpoint": "mock://filecoin-pin",
    }
