import json
from pathlib import Path
import subprocess
import sys

# We avoid external dependencies; perform lightweight schema validation manually.
# If jsonschema library becomes available in project context, this test can be upgraded.

SCHEMA_PATH = Path(__file__).parent.parent / 'data' / 'deprecations_report.schema.json'


def load_schema():
    with SCHEMA_PATH.open('r', encoding='utf-8') as f:
        return json.load(f)


def run_cli_report(tmp_path):
    report_path = tmp_path / 'report.json'
    cmd = [sys.executable, '-m', 'ipfs_kit_py.cli', 'mcp', 'deprecations', '--report-json', str(report_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode in (0, 3, 4), proc.stderr
    assert report_path.exists(), 'Report JSON file not created'
    with report_path.open('r', encoding='utf-8') as f:
        return json.load(f)


def test_report_conforms_to_schema(tmp_path):
    schema = load_schema()
    report = run_cli_report(tmp_path)

    # Core required keys
    for key in schema['required']:
        assert key in report, f"Missing top-level key: {key}"

    assert isinstance(report['generated_at'], str)
    assert isinstance(report['deprecated'], list)
    assert isinstance(report['summary'], dict)
    assert isinstance(report['policy'], dict)

    # Summary structure
    summary = report['summary']
    for k in ['count', 'max_hits']:
        assert k in summary, f"Missing summary key: {k}"
        assert isinstance(summary[k], int) and summary[k] >= 0

    # Policy sections
    hits_enf = report['policy'].get('hits_enforcement')
    mig_enf = report['policy'].get('migration_enforcement')
    assert hits_enf and mig_enf, 'Missing policy enforcement sections'

    for sec in (hits_enf, mig_enf):
        assert 'status' in sec
        assert sec['status'] in ('pass', 'violation', 'skipped')
        assert 'violations' in sec
        assert isinstance(sec['violations'], list)

    # Deprecated entries minimal checks
    for entry in report['deprecated']:
        for k in ['endpoint', 'remove_in', 'hits']:
            assert k in entry, f"Deprecated entry missing {k}"
        assert isinstance(entry['endpoint'], str)
        if entry['hits'] is not None:
            assert isinstance(entry['hits'], int) and entry['hits'] >= 0

    # Report version semantic check
    assert 'report_version' in report, 'report_version missing'
    import re as _re
    assert _re.match(r'^\d+\.\d+\.\d+$', report['report_version']), 'report_version must be semantic MAJOR.MINOR.PATCH'

    # If there are hits violations, ensure thresholds present
    if hits_enf['status'] == 'violation':
        for v in hits_enf['violations']:
            assert all(k in v for k in ['endpoint', 'hits', 'threshold'])

    # If migration violations, ensure endpoint present
    if mig_enf['status'] == 'violation':
        for v in mig_enf['violations']:
            assert 'endpoint' in v

    # Raw should be present (opaque)
    assert isinstance(report['raw'], dict)
