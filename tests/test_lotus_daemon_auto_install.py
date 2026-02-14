import os
import json
import importlib


def test_lotus_daemon_status_triggers_auto_install(monkeypatch, tmp_path):
    lotus_daemon_mod = importlib.import_module("ipfs_kit_py.lotus_daemon")
    install_lotus_mod = importlib.import_module("ipfs_kit_py.install_lotus")

    # Avoid consuming the one-shot install attempt during __init__.
    monkeypatch.delenv("IPFS_KIT_AUTO_INSTALL_BINARIES", raising=False)
    monkeypatch.setenv("IPFS_KIT_BIN_DIR", str(tmp_path / "bin"))

    calls = {"install": 0, "check": 0}

    class FakeInstaller:
        def __init__(self, resources=None, metadata=None):
            self.metadata = metadata or {}

        def install_lotus_daemon(self):
            calls["install"] += 1
            return True

    monkeypatch.setattr(install_lotus_mod, "install_lotus", FakeInstaller)
    monkeypatch.setattr("shutil.which", lambda name: None)

    daemon = lotus_daemon_mod.lotus_daemon(metadata={"lotus_path": str(tmp_path / ".lotus")})

    # Make _check_lotus_binary return None first, then a fake path after install.
    def fake_check():
        calls["check"] += 1
        return None if calls["check"] == 1 else str(tmp_path / "bin" / "lotus")

    monkeypatch.setattr(daemon, "_check_lotus_binary", fake_check)
    daemon.lotus_binary_path = None
    daemon.binary_available = False
    daemon._auto_install_attempted.clear()

    # Enable auto-install only for the status call.
    monkeypatch.setenv("IPFS_KIT_AUTO_INSTALL_BINARIES", "1")

    # Stub run_command for `lotus net id`.
    def fake_run_command(cmd, **kwargs):
        # Return a minimal JSON response lotus_daemon expects.
        return {"success": True, "returncode": 0, "stdout": json.dumps({"ID": "peer", "Addresses": []}), "stderr": ""}

    monkeypatch.setattr(daemon, "run_command", fake_run_command)

    status = daemon.daemon_status()
    assert status["success"] is True
    assert status["daemon_info"]["binary_available"] is True
    assert calls["install"] == 1

    # PATH should be prefixed with the managed bin dir.
    assert os.environ["PATH"].split(os.pathsep)[0] == str(tmp_path / "bin")
