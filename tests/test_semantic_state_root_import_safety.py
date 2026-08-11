"""Regression guard: importing the public facade is inert."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def test_public_facade_import_has_no_mutating_or_external_audit_events(tmp_path: Path) -> None:
    """An ordinary import must not install, start, connect, or mutate process state."""

    script = """
import json
import os
import sys
events = []
def audit(event, args):
    if event in {'os.putenv', 'os.unsetenv', 'os.mkdir', 'os.remove', 'os.rename', 'os.replace', 'subprocess.Popen', 'socket.connect', 'threading.Thread.start'}:
        events.append(event)
sys.addaudithook(audit)
before_environment = dict(os.environ)
before_threads = {thread.name for thread in __import__('threading').enumerate()}
from ipfs_kit_py.mcp_server.mcplusplus import DurableStateRootAdapter, StateRootSnapshot
after_threads = {thread.name for thread in __import__('threading').enumerate()}
import ipfs_kit_py.mcp_server.mcplusplus as mcplusplus
print(json.dumps({'events': events, 'environment_unchanged': before_environment == dict(os.environ), 'threads_unchanged': before_threads == after_threads, 'exports': [DurableStateRootAdapter.__name__, StateRootSnapshot.__name__], 'dir_exports': ['DurableStateRootAdapter' in dir(mcplusplus), 'StateRootSnapshot' in dir(mcplusplus)]}))
"""
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["IPFS_KIT_AUTO_INSTALL_DEPS"] = "0"
    environment["IPFS_KIT_AUTO_INSTALL_BINARIES"] = "0"
    completed = subprocess.run(
        [sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
        env=environment, check=True, text=True, capture_output=True,
    )
    result = json.loads(completed.stdout)
    assert result["events"] == []
    assert result["environment_unchanged"] is True
    assert result["threads_unchanged"] is True
    assert result["exports"] == ["DurableStateRootAdapter", "StateRootSnapshot"]
    assert result["dir_exports"] == [True, True]
