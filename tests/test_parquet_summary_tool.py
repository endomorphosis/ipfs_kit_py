import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestParquetSummaryTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.app = ConsolidatedMCPDashboard({'host': '127.0.0.1', 'port': 0, 'data_dir': cls.tmpdir.name})
        cls.client = TestClient(cls.app.app)

    @classmethod
    def tearDownClass(cls):
        try: cls.tmpdir.cleanup()
        except Exception: pass

    def rpc(self, name, args=None):
        r = self.client.post('/mcp/tools/call', json={
            'jsonrpc': '2.0', 'method': 'tools/call', 'id': 1,
            'params': {'name': name, 'arguments': args or {}}
        })
        self.assertEqual(r.status_code, 200)
        return r.json()['result']

    def test_parquet_summary_no_files(self):
        res = self.rpc('get_parquet_summary')
        self.assertIn('pins', res)
        self.assertIn('buckets', res)
        # Rows may be None if pyarrow not installed; but path keys must exist
        self.assertIn('path', res['pins'])
        self.assertIn('path', res['buckets'])


if __name__ == '__main__':
    unittest.main()
