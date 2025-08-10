import tempfile
import shutil
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestDashboardStateBucketsPins(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix='ipfs_kit_test_')
        cfg = {'host': '127.0.0.1', 'port': 0, 'data_dir': cls.tmpdir}
        cls.app = ConsolidatedMCPDashboard(cfg)
        cls.client = TestClient(cls.app.app)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def call_tool(self, name, args=None):
        args = args or {}
        r = self.client.post('/mcp/tools/call', json={'jsonrpc': '2.0', 'method': 'tools/call', 'id': 1, 'params': {'name': name, 'arguments': args}})
        self.assertEqual(r.status_code, 200)
        return r.json()['result']

    def test_bucket_create_and_list(self):
        # initially empty
        res = self.call_tool('list_buckets')
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 0)
        # create
        created = self.call_tool('create_bucket', {'name': 'alpha', 'backend': 'local'})
        self.assertEqual(created.get('name'), 'alpha')
        # list again
        res2 = self.call_tool('list_buckets')
        names = [b.get('name') for b in res2]
        self.assertIn('alpha', names)

    def test_pin_create_and_list(self):
        # initially empty
        res = self.call_tool('list_pins')
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 0)
        # create
        created = self.call_tool('create_pin', {'cid': 'bafy123', 'name': 'testpin'})
        self.assertEqual(created.get('cid'), 'bafy123')
        # list again
        res2 = self.call_tool('list_pins')
        cids = [p.get('cid') for p in res2]
        self.assertIn('bafy123', cids)


if __name__ == '__main__':
    unittest.main()
