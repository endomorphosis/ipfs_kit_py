import importlib
import importlib.metadata
import os
import sys


def test_import_is_inert_even_with_legacy_install_flag(monkeypatch):
    monkeypatch.setenv("IPFS_KIT_AUTO_INSTALL_BINARIES", "1")
    for name in list(sys.modules):
        if name == "ipfs_kit_py" or name.startswith("ipfs_kit_py."):
            sys.modules.pop(name)
    package = importlib.import_module("ipfs_kit_py")
    assert package.KUBO_BINARY is None
    assert "ipfs_kit_py.kubo_runtime" not in sys.modules
    assert "ipfs_kit_py.install_ipfs" not in sys.modules


def test_source_fallback_is_a_conditional_module_level_declaration(monkeypatch):
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    installed_bridge = importlib.metadata.EntryPoint(
        name="ipfs-kit-proof-reuse",
        value="ipfs_kit_py.pytest_proof_reuse",
        group="pytest11",
    )
    monkeypatch.setattr(
        importlib.metadata,
        "entry_points",
        lambda: importlib.metadata.EntryPoints((installed_bridge,)),
    )
    namespace = {}
    source = open(os.path.join(os.path.dirname(__file__), "..", "conftest.py"), encoding="utf-8").read()
    assert "pytest_load_initial_conftests" not in source
    exec(compile(source, "conftest.py", "exec"), namespace)
    assert namespace["pytest_plugins"] == ("ipfs_kit_py.pytest_proof_reuse",)
