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
