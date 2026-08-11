def test_bridge_import_does_not_import_accelerator_or_installer_modules():
    import sys
    import ipfs_kit_py.pytest_proof_reuse  # noqa: F401

    assert "ipfs_kit_py.install_ipfs" not in sys.modules
    assert "ipfs_kit_py.kubo_runtime" not in sys.modules

