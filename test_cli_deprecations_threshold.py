import json, socket, subprocess, sys, time, urllib.request
from pathlib import Path


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1",0)); port=s.getsockname()[1]; s.close(); return port

def _wait_ready(port, timeout=20):
    url=f"http://127.0.0.1:{port}/api/system/deprecations"; end=time.time()+timeout
    while time.time()<end:
        try:
            with urllib.request.urlopen(url, timeout=1.2) as r:
                if r.status==200:
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False

def test_cli_deprecations_fail_if_hits_over(tmp_path: Path):
    port=_free_port()
    starter = subprocess.Popen([sys.executable,'-m','ipfs_kit_py.cli','mcp','start','--port',str(port),'--data-dir',str(tmp_path)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert _wait_ready(port)
        # Generate some hits
        for _ in range(4):
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/system/overview', timeout=2.0) as r:
                assert r.status==200
        # Fetch hits value baseline
        js = json.loads(subprocess.run([sys.executable,'-m','ipfs_kit_py.cli','mcp','deprecations','--port',str(port),'--json'], capture_output=True, text=True, timeout=15).stdout)
        overview = next(d for d in js if d.get('endpoint')=='/api/system/overview')
        hits = overview.get('hits',0)
        assert hits>=4
        # Run with threshold above hits -> expect success (0)
        res_ok = subprocess.run([sys.executable,'-m','ipfs_kit_py.cli','mcp','deprecations','--port',str(port),'--fail-if-hits-over',str(hits+5)], capture_output=True, text=True, timeout=15)
        assert res_ok.returncode==0, res_ok.stdout+res_ok.stderr
        # Run with threshold below hits -> expect exit code 3
        res_fail = subprocess.run([sys.executable,'-m','ipfs_kit_py.cli','mcp','deprecations','--port',str(port),'--fail-if-hits-over',str(hits-1)], capture_output=True, text=True, timeout=15)
        assert res_fail.returncode==3, f"Expected exit 3 got {res_fail.returncode}\nSTDOUT:\n{res_fail.stdout}\nSTDERR:\n{res_fail.stderr}"
    finally:
        subprocess.run([sys.executable,'-m','ipfs_kit_py.cli','mcp','stop','--port',str(port),'--data-dir',str(tmp_path)], capture_output=True, text=True, timeout=10)
        if starter.poll() is None:
            starter.terminate();
            try: starter.wait(timeout=5)
            except subprocess.TimeoutExpired: starter.kill()
