import json, socket, subprocess, sys, time, urllib.request
from pathlib import Path

def _free_port():
    s=socket.socket(); s.bind(("127.0.0.1",0)); p=s.getsockname()[1]; s.close(); return p

def _wait_ready(port, timeout=20):
    url=f"http://127.0.0.1:{port}/api/system/deprecations"; end=time.time()+timeout
    while time.time()<end:
        try:
            with urllib.request.urlopen(url, timeout=1.3) as r:
                if r.status==200: return True
        except Exception:
            pass
        time.sleep(0.3)
    return False

def test_cli_deprecations_report_json(tmp_path: Path):
    port=_free_port()
    report_path = tmp_path / 'report.json'
    starter = subprocess.Popen([sys.executable,'-m','ipfs_kit_py.cli','mcp','start','--port',str(port),'--data-dir',str(tmp_path/'data')], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert _wait_ready(port)
        # generate some hits
        for _ in range(2):
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/system/overview', timeout=5.0) as r:
                assert r.status==200
        # invoke deprecations with report-json (table output by default)
        res = subprocess.run([sys.executable,'-m','ipfs_kit_py.cli','mcp','deprecations','--port',str(port),'--report-json',str(report_path)], capture_output=True, text=True, timeout=20)
        assert res.returncode==0, res.stdout+res.stderr
        assert report_path.exists(), 'Report file not created'
        data = json.loads(report_path.read_text('utf-8'))
        assert 'generated_at' in data and 'deprecated' in data and 'summary' in data and 'raw' in data
        assert isinstance(data['deprecated'], list)
        # summary fields
        summary = data['summary']
        assert 'count' in summary and 'max_hits' in summary
        # ensure raw.deprecated matches filtered list length
        raw_list = data['raw'].get('deprecated') if isinstance(data['raw'], dict) else None
        assert raw_list is None or len(raw_list) >= len(data['deprecated'])
    finally:
        subprocess.run([sys.executable,'-m','ipfs_kit_py.cli','mcp','stop','--port',str(port),'--data-dir',str(tmp_path/'data')], capture_output=True, text=True, timeout=15)
        if starter.poll() is None:
            starter.terminate();
            try: starter.wait(timeout=5)
            except subprocess.TimeoutExpired: starter.kill()
