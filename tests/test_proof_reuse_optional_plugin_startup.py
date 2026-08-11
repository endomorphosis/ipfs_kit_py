import importlib

from ipfs_kit_py import pytest_proof_reuse as bridge


def test_only_missing_accelerator_is_optional(monkeypatch):
    real_import = importlib.import_module

    def missing_accelerator(name):
        if name == bridge.ACCELERATOR_PLUGIN:
            raise ModuleNotFoundError("missing", name="ipfs_accelerate_py")
        return real_import(name)

    monkeypatch.setattr(bridge.importlib, "import_module", missing_accelerator)
    monkeypatch.setattr(bridge, "_accelerator_is_absent_namespace", lambda: True)
    monkeypatch.setattr(bridge, "_accelerator_plugin_is_undiscoverable", lambda: True)
    assert bridge._optional_accelerator_plugin() is None


def test_namespace_only_missing_testing_hierarchy_is_optional(monkeypatch):
    def missing_testing(name):
        raise ModuleNotFoundError("missing", name="ipfs_accelerate_py.testing")

    monkeypatch.setattr(bridge.importlib, "import_module", missing_testing)
    monkeypatch.setattr(bridge, "_accelerator_is_absent_namespace", lambda: True)
    monkeypatch.setattr(bridge, "_accelerator_plugin_is_undiscoverable", lambda: True)
    assert bridge._optional_accelerator_plugin() is None


def test_regular_accelerator_missing_testing_hierarchy_remains_visible(monkeypatch):
    def missing_testing(name):
        raise ModuleNotFoundError("missing", name="ipfs_accelerate_py.testing")

    monkeypatch.setattr(bridge.importlib, "import_module", missing_testing)
    monkeypatch.setattr(bridge, "_accelerator_is_absent_namespace", lambda: False)

    try:
        bridge._optional_accelerator_plugin()
    except ModuleNotFoundError as exc:
        assert exc.name == "ipfs_accelerate_py.testing"
    else:
        raise AssertionError("an incomplete regular accelerator was hidden")


def test_transitive_import_failure_remains_visible(monkeypatch):
    def broken_plugin(name):
        raise ModuleNotFoundError("missing", name="requests")

    monkeypatch.setattr(bridge.importlib, "import_module", broken_plugin)
    # This is the dangerous case: no accelerator hierarchy can be discovered,
    # but the import error names a dependency outside its optional chain.
    monkeypatch.setattr(bridge, "_accelerator_is_absent_namespace", lambda: True)
    monkeypatch.setattr(bridge, "_accelerator_plugin_is_undiscoverable", lambda: True)
    try:
        bridge._optional_accelerator_plugin()
    except ModuleNotFoundError as exc:
        assert exc.name == "requests"
    else:
        raise AssertionError("transitive failure was hidden")


def test_namespace_root_does_not_hide_plugin_internal_import_failure(monkeypatch):
    def broken_plugin(name):
        raise ModuleNotFoundError(
            "missing", name="ipfs_accelerate_py.runtime_dependency"
        )

    monkeypatch.setattr(bridge.importlib, "import_module", broken_plugin)
    monkeypatch.setattr(bridge, "_accelerator_is_absent_namespace", lambda: True)
    monkeypatch.setattr(bridge, "_accelerator_plugin_is_undiscoverable", lambda: False)

    try:
        bridge._optional_accelerator_plugin()
    except ModuleNotFoundError as exc:
        assert exc.name == "ipfs_accelerate_py.runtime_dependency"
    else:
        raise AssertionError("a plugin-internal failure was hidden")
