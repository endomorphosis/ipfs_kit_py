import json, os, socket, subprocess, sys, time, urllib.request
from pathlib import Path


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_ready(port: int, deadline: float = 25.0):
    dep_url = f"http://127.0.0.1:{port}/api/system/deprecations"
    end = time.time() + deadline
    while time.time() < end:
        try:
            with urllib.request.urlopen(dep_url, timeout=1.5) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.35)
    return False


def test_cli_deprecations_sort_and_min_hits(tmp_path: Path):
    port = _free_port()
    # Start server
    starter = subprocess.Popen([
        sys.executable, '-m', 'ipfs_kit_py.cli', 'mcp', 'start', '--port', str(port), '--data-dir', str(tmp_path)
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert _wait_ready(port), 'Server not ready in time'
        # Induce hits by calling deprecated endpoint multiple times
        dep_ep = f'http://127.0.0.1:{port}/api/system/overview'
        for _ in range(5):
            with urllib.request.urlopen(dep_ep, timeout=2.0) as r:
                assert r.status == 200
        # Retrieve JSON list normally
        base_res = subprocess.run([
            sys.executable, '-m', 'ipfs_kit_py.cli', 'mcp', 'deprecations', '--port', str(port), '--json'
        ], capture_output=True, text=True, timeout=20)
        assert base_res.returncode == 0
        base_items = json.loads(base_res.stdout)
        assert isinstance(base_items, list)
        overview = next((d for d in base_items if d.get('endpoint') == '/api/system/overview'), None)
        assert overview is not None and overview.get('hits', 0) >= 5
        # Sort by hits (should still contain overview)
        sort_res = subprocess.run([
            sys.executable, '-m', 'ipfs_kit_py.cli', 'mcp', 'deprecations', '--port', str(port), '--json', '--sort', 'hits'
        ], capture_output=True, text=True, timeout=20)
        assert sort_res.returncode == 0
        sort_items = json.loads(sort_res.stdout)
        assert sort_items[0].get('hits', 0) >= sort_items[-1].get('hits', 0)
        # Apply min-hits greater than observed to filter out
        high_filter = overview['hits'] + 100
        filt_res = subprocess.run([
            sys.executable, '-m', 'ipfs_kit_py.cli', 'mcp', 'deprecations', '--port', str(port), '--json', '--min-hits', str(high_filter)
        ], capture_output=True, text=True, timeout=20)
        assert filt_res.returncode == 0
        filt_items = json.loads(filt_res.stdout)
        assert isinstance(filt_items, list) and len(filt_items) == 0
    finally:
        # Stop server
        subprocess.run([
            sys.executable, '-m', 'ipfs_kit_py.cli', 'mcp', 'stop', '--port', str(port), '--data-dir', str(tmp_path)
        ], capture_output=True, text=True, timeout=15)
        if starter.poll() is None:
            starter.terminate()
            try:
                starter.wait(timeout=5)
            except subprocess.TimeoutExpired:
                starter.kill()


def test_cli_deprecations_persistence_across_restart(tmp_path: Path):
    port = _free_port()
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    # First run
    starter1 = subprocess.Popen([
        sys.executable, '-m', 'ipfs_kit_py.cli', 'mcp', 'start', '--port', str(port), '--data-dir', str(data_dir)
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert _wait_ready(port), 'Server (run1) not ready'
        dep_ep = f'http://127.0.0.1:{port}/api/system/overview'
        for _ in range(3):
            with urllib.request.urlopen(dep_ep, timeout=2.0) as r:
                assert r.status == 200
        # Fetch hits via CLI JSON
        res1 = subprocess.run([
            sys.executable, '-m', 'ipfs_kit_py.cli', 'mcp', 'deprecations', '--port', str(port), '--json'
        ], capture_output=True, text=True, timeout=20)
        items1 = json.loads(res1.stdout)
        ov1 = next(d for d in items1 if d.get('endpoint') == '/api/system/overview')
        hits_first = ov1.get('hits', 0)
        assert hits_first >= 3
    finally:
        subprocess.run([
            sys.executable, '-m', 'ipfs_kit_py.cli', 'mcp', 'stop', '--port', str(port), '--data-dir', str(data_dir)
        ], capture_output=True, text=True, timeout=15)
        if starter1.poll() is None:
            starter1.terminate()
            try:
                starter1.wait(timeout=5)
            except subprocess.TimeoutExpired:
                starter1.kill()
    # Second run (same data dir / port new process)
    starter2 = subprocess.Popen([
        sys.executable, '-m', 'ipfs_kit_py.cli', 'mcp', 'start', '--port', str(port), '--data-dir', str(data_dir)
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert _wait_ready(port), 'Server (run2) not ready'
        dep_ep = f'http://127.0.0.1:{port}/api/system/overview'
        for _ in range(2):
            with urllib.request.urlopen(dep_ep, timeout=2.0) as r:
                assert r.status == 200
        res2 = subprocess.run([
            sys.executable, '-m', 'ipfs_kit_py.cli', 'mcp', 'deprecations', '--port', str(port), '--json'
        ], capture_output=True, text=True, timeout=20)
        items2 = json.loads(res2.stdout)
        ov2 = next(d for d in items2 if d.get('endpoint') == '/api/system/overview')
        hits_second = ov2.get('hits', 0)
        # Should be at least hits_first (persisted) + 2 new requests
        assert hits_second >= hits_first + 2
    finally:
        subprocess.run([
            sys.executable, '-m', 'ipfs_kit_py.cli', 'mcp', 'stop', '--port', str(port), '--data-dir', str(data_dir)
        ], capture_output=True, text=True, timeout=15)
        if starter2.poll() is None:
            starter2.terminate()
            try:
                starter2.wait(timeout=5)
            except subprocess.TimeoutExpired:
                starter2.kill()
