import types

from ipfs_kit_py import pytest_proof_reuse as bridge


class PluginManager:
    def __init__(self):
        self.plugins = {}

    def hasplugin(self, name):
        return name in self.plugins

    def register(self, plugin, name):
        self.plugins[name] = plugin


def test_bridge_uses_the_accelerator_canonical_registration_name():
    assert bridge.PLUGIN_NAME == "ipfs-proof-reuse"


def test_bridge_is_noop_without_accelerator(monkeypatch):
    monkeypatch.setattr(bridge, "_optional_accelerator_plugin", lambda: None)
    manager = PluginManager()
    bridge.pytest_addoption(None, manager)
    assert manager.plugins == {}


def test_bridge_registers_at_most_one_accelerator(monkeypatch):
    plugin = types.ModuleType("accelerator")
    monkeypatch.setattr(bridge, "_optional_accelerator_plugin", lambda: plugin)
    manager = PluginManager()
    bridge.pytest_addoption(None, manager)
    bridge.pytest_configure(types.SimpleNamespace(pluginmanager=manager))
    assert manager.plugins == {bridge.PLUGIN_NAME: plugin}
