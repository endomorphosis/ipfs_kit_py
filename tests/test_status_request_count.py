import importlib.util
from fastapi.testclient import TestClient


def load_dashboard(config=None):
    spec = importlib.util.spec_from_file_location('dash','/home/devel/ipfs_kit_py/consolidated_mcp_dashboard.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.ConsolidatedMCPDashboard(config)


def test_status_includes_request_count_and_increments():
    dash = load_dashboard()
    client = TestClient(dash.app)
    first = client.get('/api/mcp/status').json()['data']['counts']['requests']
    for _ in range(3):
        client.get('/api/mcp/status')
    last = client.get('/api/mcp/status').json()['data']['counts']['requests']
    assert last >= first + 3


def test_status_auth_enabled_flag_changes_with_token():
    dash = load_dashboard({'api_token': 'secret'})
    client = TestClient(dash.app)
    data = client.get('/api/mcp/status').json()['data']
    assert data['security']['auth_enabled'] is True
    # Unauthorized without token on a protected endpoint (e.g., tools call)
    r = client.post('/mcp/tools/call', json={'name':'noop','arguments':{}})
    assert r.status_code == 401
    # Authorized with header
    r2 = client.post('/mcp/tools/call', headers={'x-api-token':'secret'}, json={'name':'noop','arguments':{}})
    # Tool may or may not exist; we only assert it isn't 401 now
    assert r2.status_code != 401
