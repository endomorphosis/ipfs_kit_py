import os
import tempfile
import shutil
import unittest
from fastapi.testclient import TestClient
from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestDashboardLogs(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='ipfs_kit_test_logs_')
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

    def test_logs_empty_initially(self):
        res = self.call_tool('get_logs', {'limit': 10})
        self.assertIsInstance(res, dict)
        self.assertIn('logs', res)
        self.assertEqual(res['logs'], [])

    def test_logs_after_bucket_and_pin_ops(self):
        # Perform operations that should be logged
        self.call_tool('create_bucket', {'name': 'alpha', 'backend': 'local'})
        self.call_tool('create_pin', {'cid': 'bafyalpha', 'name': 'alpha'})
        self.call_tool('delete_pin', {'cid': 'bafyalpha'})
        self.call_tool('delete_bucket', {'name': 'alpha'})

        res = self.call_tool('get_logs', {'limit': 10})
        logs = res.get('logs', [])
        self.assertGreaterEqual(len(logs), 4)
        # Check that expected messages exist
        msgs = '\n'.join([str(l.get('message', '')) for l in logs])
        self.assertIn('bucket created: alpha', msgs)
        self.assertIn('bucket deleted: alpha', msgs)
        self.assertIn('pin created: bafyalpha', msgs)
        self.assertIn('pin deleted: bafyalpha', msgs)
        # Component filtering
        only_buckets = self.call_tool('get_logs', {'component': 'buckets', 'limit': 10})['logs']
        self.assertTrue(all(l.get('component') == 'buckets' for l in only_buckets))
        only_pins = self.call_tool('get_logs', {'component': 'pins', 'limit': 10})['logs']
        self.assertTrue(all(l.get('component') == 'pins' for l in only_pins))

    def test_logs_limit_and_order(self):
        # Create multiple pins
        for i in range(5):
            self.call_tool('create_pin', {'cid': f'bafy{i}', 'name': f'n{i}'})
        res = self.call_tool('get_logs', {'component': 'pins', 'limit': 2})
        logs = res.get('logs', [])
        self.assertEqual(len(logs), 2)
        # Newest first: expect last two creations
        messages = [l.get('message', '') for l in logs]
        self.assertIn('pin created: bafy4', messages[0])
        self.assertIn('pin created: bafy3', messages[1])


if __name__ == '__main__':
    unittest.main()
