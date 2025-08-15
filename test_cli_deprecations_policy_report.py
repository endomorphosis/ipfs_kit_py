import json, socket, subprocess, sys, time, urllib.request
from pathlib import Path

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
        time.sleep(0.3)
    return False

def test_cli_deprecations_policy_section_report(tmp_path: Path):
    port=_free_port()
    report_path = tmp_path / 'policy_report.json'
    starter = subprocess.Popen([sys.executable,'-m','ipfs_kit_py.cli','mcp','start','--port',str(port),'--data-dir',str(tmp_path/'data')], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert _wait_ready(port)
        # generate hits
        for _ in range(3):
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/system/overview', timeout=2.0) as r:
                assert r.status==200
        # first get baseline hits
        base = json.loads(subprocess.run([sys.executable,'-m','ipfs_kit_py.cli','mcp','deprecations','--port',str(port),'--json'], capture_output=True, text=True, timeout=20).stdout)
        overview = next(d for d in base if d.get('endpoint')=='/api/system/overview')
        hits = overview.get('hits',0)
        # run with threshold below hits to trigger violation + report
        res = subprocess.run([
            sys.executable,'-m','ipfs_kit_py.cli','mcp','deprecations','--port',str(port),
            '--fail-if-hits-over',str(hits-1),'--report-json',str(report_path)
        ], capture_output=True, text=True, timeout=25)
        assert res.returncode==3, f"Expected exit 3 got {res.returncode}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        assert report_path.exists(), 'Report file missing'
        data = json.loads(report_path.read_text('utf-8'))
        assert 'policy' in data, 'policy section missing'
        policy = data['policy']
        # New nested policy structure: hits_enforcement + migration_enforcement
        assert 'hits_enforcement' in policy, f"hits_enforcement missing in policy: {policy}"
        hits_policy = policy['hits_enforcement']
        assert hits_policy.get('status')=='violation', hits_policy
        assert isinstance(hits_policy.get('violations'), list) and len(hits_policy['violations'])>=1
        viol = hits_policy['violations'][0]
        assert viol.get('endpoint')=='/api/system/overview'
        assert viol.get('hits')==hits
        assert viol.get('threshold')==hits-1
        # Migration enforcement should exist but be skipped since flag not provided
        assert 'migration_enforcement' in policy, 'migration_enforcement section missing'
        mig_policy = policy['migration_enforcement']
        assert mig_policy.get('status') in ('skipped','pass','violation')  # normally 'skipped' here
    finally:
        subprocess.run([sys.executable,'-m','ipfs_kit_py.cli','mcp','stop','--port',str(port),'--data-dir',str(tmp_path/'data')], capture_output=True, text=True, timeout=15)
        if starter.poll() is None:
            starter.terminate();
            try: starter.wait(timeout=5)
            except subprocess.TimeoutExpired: starter.kill()
