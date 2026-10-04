import json, os, re, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

# We create a temporary copy of the dashboard file where we add an extra deprecated endpoint lacking a migration mapping.

def _free_port():
    s=socket.socket(); s.bind(("127.0.0.1",0)); p=s.getsockname()[1]; s.close(); return p

def _wait_ready(port, timeout=25):
    url=f"http://127.0.0.1:{port}/api/system/deprecations"; end=time.time()+timeout
    while time.time()<end:
        try:
            with urllib.request.urlopen(url, timeout=1.4) as r:
                if r.status==200: return True
        except Exception:
            pass
        time.sleep(0.35)
    return False

def test_cli_deprecations_fail_if_missing_migration(tmp_path: Path):
    port=_free_port()
    # Copy original dashboard and inject synthetic deprecated endpoint without migration mapping
    orig = Path('consolidated_mcp_dashboard.py').resolve()
    assert orig.exists(), 'dashboard file missing'
    modified = tmp_path / 'consolidated_mcp_dashboard_custom.py'
    text = orig.read_text('utf-8')
    # Find the DEPRECATED_ENDPOINTS mapping; if not found, skip
    pattern = re.compile(r"(DEPRECATED_ENDPOINTS\s*=\s*{[^^}]*}\n)")
    # If explicit mapping variable isn't present, we inject after class init search fallback
    # Because DEPRECATED_ENDPOINTS is an instance attribute set inside __init__,
    # we patch __init__ to inject a synthetic deprecated endpoint without a migration mapping.
    injection = """
# Injected for test: add synthetic deprecated endpoint with no migration mapping
try:
    _orig_init = ConsolidatedMCPDashboard.__init__
    def _patched_init(self, *a, **kw):
        _orig_init(self, *a, **kw)
        try:
            self.DEPRECATED_ENDPOINTS['/api/test/no_migration'] = '9.9.9'
        except Exception:
            pass
    ConsolidatedMCPDashboard.__init__ = _patched_init
except Exception:
    pass
"""
    text += "\n" + injection + "\n"
    modified.write_text(text, encoding='utf-8')

    # Launch server pointing IPFS_KIT_SERVER_FILE to modified file
    env=os.environ.copy(); env['IPFS_KIT_SERVER_FILE']=str(modified)
    starter = subprocess.Popen([sys.executable,'-m','ipfs_kit_py.cli','mcp','start','--port',str(port),'--data-dir',str(tmp_path/'data')], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        assert _wait_ready(port), 'server not ready'
        # Confirm endpoint appears and lacks migration
        dep_js = json.loads(subprocess.run([sys.executable,'-m','ipfs_kit_py.cli','mcp','deprecations','--port',str(port),'--json'], capture_output=True, text=True, timeout=25).stdout)
        test_entry = next((d for d in dep_js if d.get('endpoint')=='/api/test/no_migration'), None)
        assert test_entry is not None, 'Injected deprecated endpoint not present'
        assert not test_entry.get('migration'), 'Migration unexpectedly present'
        # Run with enforcement flag expecting exit code 4
        res = subprocess.run([sys.executable,'-m','ipfs_kit_py.cli','mcp','deprecations','--port',str(port),'--fail-if-missing-migration'], capture_output=True, text=True, timeout=25)
        assert res.returncode==4, f"Expected exit 4 got {res.returncode}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        # Run with report-json to inspect policy block
        report_path = tmp_path/'mig_report.json'
        res2 = subprocess.run([sys.executable,'-m','ipfs_kit_py.cli','mcp','deprecations','--port',str(port),'--fail-if-missing-migration','--report-json',str(report_path)], capture_output=True, text=True, timeout=25)
        assert res2.returncode==4
        data = json.loads(report_path.read_text('utf-8'))
        mig_enf = data.get('policy',{}).get('migration_enforcement')
        assert mig_enf and mig_enf.get('status')=='violation'
        viols = mig_enf.get('violations') or []
        assert any(v.get('endpoint')=='/api/test/no_migration' for v in viols)
    finally:
        subprocess.run([sys.executable,'-m','ipfs_kit_py.cli','mcp','stop','--port',str(port),'--data-dir',str(tmp_path/'data')], capture_output=True, text=True, timeout=15)
        if starter.poll() is None:
            starter.terminate();
            try: starter.wait(timeout=5)
            except subprocess.TimeoutExpired: starter.kill()
