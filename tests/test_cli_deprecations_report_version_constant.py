import json, subprocess, sys, re, tempfile, pathlib, importlib


def test_report_version_constant_exposed():
    # Generate a report
    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        out = td_path / 'report.json'
        cmd = [sys.executable, '-m', 'ipfs_kit_py.cli', 'mcp', 'deprecations', '--report-json', str(out)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode in (0, 3, 4), proc.stderr
        assert out.exists(), 'Report not created'
        report = json.loads(out.read_text())
        # Validate presence and pattern
        ver = report.get('report_version')
        assert ver, 'report_version missing in report'
        assert re.match(r'^\d+\.\d+\.\d+$', ver), f'report_version not semantic: {ver}'

    # Ensure constant in module matches report value
    cli_mod = importlib.import_module('ipfs_kit_py.cli')
    assert getattr(cli_mod, 'REPORT_SCHEMA_VERSION', None) == ver, 'Module REPORT_SCHEMA_VERSION mismatch'
