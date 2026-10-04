import os
import tempfile
import json
import unittest
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestBucketPolicyNested(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        cfg = {"data_dir": self.tmp.name, "host": "127.0.0.1", "port": 0}
        self.dashboard = ConsolidatedMCPDashboard(cfg)
        self.client = TestClient(self.dashboard.app)

    def tearDown(self):
        try:
            self.client.close()
        except Exception:
            pass
        self.tmp.cleanup()

    def test_rest_nested_policy(self):
        # create bucket
        r = self.client.post('/api/state/buckets', json={"name": "tb_rest", "backend": "mem"})
        self.assertEqual(r.status_code, 200)
        # update nested
        payload = {"policy": {"replication_factor": 2, "cache_policy": "disk", "retention_days": 4}}
        r = self.client.post('/api/state/buckets/tb_rest/policy', json=payload)
        self.assertEqual(r.status_code, 200, r.text)
        js = r.json()
        self.assertTrue(js.get('ok'))
        self.assertEqual(js['policy']['replication_factor'], 2)
        self.assertEqual(js['policy']['cache_policy'], 'disk')
        self.assertEqual(js['policy']['retention_days'], 4)
        # verify get
        r = self.client.get('/api/state/buckets/tb_rest/policy')
        self.assertEqual(r.status_code, 200)
        pol = r.json().get('policy')
        self.assertEqual(pol, {"replication_factor": 2, "cache_policy": "disk", "retention_days": 4})

    def test_rpc_nested_policy(self):
        # create bucket
        r = self.client.post('/api/state/buckets', json={"name": "tb_rpc", "backend": "mem"})
        self.assertEqual(r.status_code, 200)
        # rpc update
        body = {"name": "update_bucket_policy", "args": {"name": "tb_rpc", "policy": {"replication_factor": 3, "cache_policy": "memory", "retention_days": 7}}}
        r = self.client.post('/mcp/tools/call', json=body)
        self.assertEqual(r.status_code, 200, r.text)
        js = r.json()
        self.assertTrue(js.get('result', {}).get('ok'))
        self.assertEqual(js['result']['policy']['replication_factor'], 3)
        self.assertEqual(js['result']['policy']['cache_policy'], 'memory')
        self.assertEqual(js['result']['policy']['retention_days'], 7)
        # verify via REST
        r = self.client.get('/api/state/buckets/tb_rpc/policy')
        self.assertEqual(r.status_code, 200)
        pol = r.json().get('policy')
        self.assertEqual(pol, {"replication_factor": 3, "cache_policy": "memory", "retention_days": 7})


if __name__ == '__main__':
    unittest.main()
