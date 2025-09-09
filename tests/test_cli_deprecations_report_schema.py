import json, socket, subprocess, sys, time, urllib.request
from pathlib import Path

# Lightweight schema validation for --report-json output ensuring nested policy structure stability.

def _free_port():
    s=socket.socket(); s.bind(("127.0.0.1",0)); p=s.getsockname()[1]; s.close(); return p

def _wait_ready(port, timeout=20):
    url=f"http://127.0.0.1:{port}/api/system/deprecations"; end=time.time()+timeout
    while time.time()<end:
        try:
            with urllib.request.urlopen(url, timeout=1.2) as r:
                if r.status==200: return True
        except Exception:
            pass
        time.sleep(0.25)
    return False

def test_cli_deprecations_report_schema(tmp_path: Path):
    port=_free_port()
    report_path = tmp_path / 'schema_report.json'
    starter = subprocess.Popen([sys.executable,'-m','ipfs_kit_py.cli','mcp','start','--port',str(port),'--data-dir',str(tmp_path/'data')], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert _wait_ready(port)
        # touch the deprecated endpoint a few times to generate hits and ensure non-zero counts possible
        for _ in range(2):
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/system/overview', timeout=2.0) as r:
                assert r.status==200
        res = subprocess.run([
            sys.executable,'-m','ipfs_kit_py.cli','mcp','deprecations','--port',str(port),
            '--report-json',str(report_path), '--fail-if-hits-over','999999'
        ], capture_output=True, text=True, timeout=30)
        # Should not violate high threshold
        assert res.returncode==0, res.stdout+res.stderr
        assert report_path.exists()
        data = json.loads(report_path.read_text('utf-8'))
        # Top-level keys
        for key in ('generated_at','deprecated','summary','policy','raw'):
            assert key in data, f"Missing key: {key}"
        assert isinstance(data['deprecated'], list)
        assert isinstance(data['summary'], dict)
        assert isinstance(data['policy'], dict)
        pol = data['policy']
        # Nested policy sections
        assert 'hits_enforcement' in pol, 'hits_enforcement missing'
        assert 'migration_enforcement' in pol, 'migration_enforcement missing'
        he = pol['hits_enforcement']; me = pol['migration_enforcement']
        for sect in (he, me):
            assert isinstance(sect, dict)
            assert sect.get('status') in ('pass','violation','skipped'), sect
            # violations must be list
            assert isinstance(sect.get('violations'), list)
        # hits_enforcement threshold may be None or int
        thr = he.get('threshold')
        assert (thr is None) or isinstance(thr, int)
        # Deprecated entries minimal shape
        for d in data['deprecated']:
            assert 'endpoint' in d and 'remove_in' in d
            assert 'hits' in d
        # Summary fields
        assert 'count' in data['summary'] and 'max_hits' in data['summary']
    finally:
        subprocess.run([sys.executable,'-m','ipfs_kit_py.cli','mcp','stop','--port',str(port),'--data-dir',str(tmp_path/'data')], capture_output=True, text=True, timeout=15)
        if starter.poll() is None:
            starter.terminate();
            try: starter.wait(timeout=5)
            except subprocess.TimeoutExpired: starter.kill()
