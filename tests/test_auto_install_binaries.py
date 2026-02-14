import os
import subprocess
import importlib


def test_auto_install_ipfs_opt_in(monkeypatch, tmp_path):
    from ipfs_kit_py.daemon_config_manager import DaemonConfigManager

    manager = DaemonConfigManager()
    manager.ipfs_path = str(tmp_path / ".ipfs")

    monkeypatch.delenv("IPFS_KIT_AUTO_INSTALL_BINARIES", raising=False)
    monkeypatch.setenv("IPFS_KIT_BIN_DIR", str(tmp_path / "bin"))

    assert manager._attempt_install_ipfs() is False
    assert "ipfs" not in manager._auto_install_attempted


def test_auto_install_ipfs_attempts_once(monkeypatch, tmp_path):
    from ipfs_kit_py.daemon_config_manager import DaemonConfigManager
    install_ipfs_mod = importlib.import_module("ipfs_kit_py.install_ipfs")

    manager = DaemonConfigManager()
    manager.ipfs_path = str(tmp_path / ".ipfs")

    monkeypatch.setenv("IPFS_KIT_AUTO_INSTALL_BINARIES", "1")
    monkeypatch.setenv("IPFS_KIT_BIN_DIR", str(tmp_path / "bin"))

    calls = {"count": 0}

    class FakeInstaller:
        def __init__(self, resources=None, metadata=None):
            self.metadata = metadata or {}

        def install_ipfs_daemon(self):
            calls["count"] += 1
            return True

    monkeypatch.setattr(install_ipfs_mod, "install_ipfs", FakeInstaller)
    monkeypatch.setattr("shutil.which", lambda name: None)

    assert manager._attempt_install_ipfs() is True
    assert calls["count"] == 1
    assert os.environ["PATH"].split(os.pathsep)[0] == str(tmp_path / "bin")

    # Second call should be a no-op due to one-shot guard.
    assert manager._attempt_install_ipfs() is False
    assert calls["count"] == 1


def test_auto_install_lotus_retry_on_missing_binary(monkeypatch, tmp_path):
    from ipfs_kit_py.daemon_config_manager import DaemonConfigManager
    install_lotus_mod = importlib.import_module("ipfs_kit_py.install_lotus")

    manager = DaemonConfigManager()
    manager.lotus_path = str(tmp_path / ".lotus")

    monkeypatch.setenv("IPFS_KIT_AUTO_INSTALL_BINARIES", "1")
    monkeypatch.setenv("IPFS_KIT_BIN_DIR", str(tmp_path / "bin"))

    class FakeInstaller:
        def __init__(self, resources=None, metadata=None):
            self.metadata = metadata or {}

        def install_lotus_daemon(self):
            return True

    monkeypatch.setattr(install_lotus_mod, "install_lotus", FakeInstaller)
    monkeypatch.setattr("shutil.which", lambda name: None)

    run_calls = {"count": 0}

    def fake_run(argv, **kwargs):
        run_calls["count"] += 1
        if run_calls["count"] == 1:
            raise FileNotFoundError()
        return subprocess.CompletedProcess(argv, 0, stdout="lotus version x", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert manager._check_lotus_running() is True
    assert run_calls["count"] == 2
