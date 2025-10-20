import tempfile
import shutil
import unittest
from fastapi.testclient import TestClient
from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestDashboardDeleteFlows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix='ipfs_kit_test_del_')
        cfg = {'host': '127.0.0.1', 'port': 0, 'data_dir': cls.tmpdir}
        cls.app = ConsolidatedMCPDashboard(cfg)
        cls.client = TestClient(cls.app.app)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def call_tool(self, name, args=None):
        r = self.client.post('/mcp/tools/call', json={
            'jsonrpc': '2.0', 'method': 'tools/call', 'id': 1,
            'params': {'name': name, 'arguments': args or {}}
        })
        self.assertEqual(r.status_code, 200)
        return r.json()['result']

    def test_delete_bucket_flow(self):
        # Create then delete
        self.call_tool('create_bucket', {'name': 'to_del', 'backend': 'local'})
        del_res = self.call_tool('delete_bucket', {'name': 'to_del'})
        self.assertIn(del_res.get('status'), ['deleted', 'absent'])
        # List should not contain it
        lst = self.call_tool('list_buckets')
        self.assertNotIn('to_del', [b.get('name') for b in lst])

    def test_delete_pin_flow(self):
        # Create then delete
        self.call_tool('create_pin', {'cid': 'bafyToDel', 'name': 'x'})
        del_res = self.call_tool('delete_pin', {'cid': 'bafyToDel'})
        self.assertIn(del_res.get('status'), ['deleted', 'absent'])
        # List should not contain it
        lst = self.call_tool('list_pins')
        self.assertNotIn('bafyToDel', [p.get('cid') for p in lst])


if __name__ == '__main__':
    unittest.main()
