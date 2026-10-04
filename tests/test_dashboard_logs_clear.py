import tempfile
import shutil
import unittest
from fastapi.testclient import TestClient
from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestDashboardLogsClear(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='ipfs_kit_test_logs_clear_')
        cfg = {'host': '127.0.0.1', 'port': 0, 'data_dir': self.tmpdir}
        self.app = ConsolidatedMCPDashboard(cfg)
        self.client = TestClient(self.app.app)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def call_tool(self, name, args=None):
        r = self.client.post('/mcp/tools/call', json={
            'jsonrpc': '2.0', 'method': 'tools/call', 'id': 1,
            'params': {'name': name, 'arguments': args or {}}
        })
        self.assertEqual(r.status_code, 200)
        return r.json()['result']

    def test_clear_logs(self):
        # Generate some logs
        self.call_tool('create_bucket', {'name': 'alpha', 'backend': 'local'})
        self.call_tool('create_pin', {'cid': 'bafyalpha', 'name': 'alpha'})
        logs_before = self.call_tool('get_logs', {'limit': 100})['logs']
        self.assertGreaterEqual(len(logs_before), 2)

        cleared = self.call_tool('clear_logs')
        self.assertGreaterEqual(cleared.get('cleared', 0), 2)

        logs_after = self.call_tool('get_logs', {'limit': 100})['logs']
        self.assertEqual(logs_after, [])


if __name__ == '__main__':
    unittest.main()
