import unittest, time
from fastapi.testclient import TestClient
from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard

class TestBucketPolicy(unittest.TestCase):
    def setUp(self):
        self.app = ConsolidatedMCPDashboard({'host':'127.0.0.1','port':0,'api_token':'tok'}).app
        self.client = TestClient(self.app)
        # create a legacy bucket manually by writing directly via POST before policy usage (policy defaults should auto inject)
        self.name = f"policybucket_{time.time_ns()}"
        r = self.client.post('/api/state/buckets', json={'name': self.name}, headers={'x-api-token':'tok'})
        self.assertEqual(r.status_code, 200)

    def test_default_policy_injection(self):
        # list buckets should show policy with defaults
        r = self.client.get('/api/state/buckets')
        self.assertEqual(r.status_code, 200)
        items = r.json().get('items', [])
        target = [b for b in items if b.get('name') == self.name][0]
        pol = target.get('policy')
        self.assertIsNotNone(pol)
        self.assertEqual(pol.get('replication_factor'), 1)
        self.assertEqual(pol.get('cache_policy'), 'none')
        self.assertEqual(pol.get('retention_days'), 0)

    def test_get_policy_endpoint(self):
        r = self.client.get(f'/api/state/buckets/{self.name}/policy')
        self.assertEqual(r.status_code, 200)
        pol = r.json().get('policy') or {}
        self.assertEqual(pol.get('replication_factor'), 1)

    def test_update_policy_success(self):
        payload = {"replication_factor": 3, "cache_policy": "memory", "retention_days": 5}
        r = self.client.post(f'/api/state/buckets/{self.name}/policy', json=payload, headers={'x-api-token':'tok'})
        self.assertEqual(r.status_code, 200)
        pol = r.json().get('policy') or {}
        self.assertEqual(pol.get('replication_factor'), 3)
        self.assertEqual(pol.get('cache_policy'), 'memory')
        self.assertEqual(pol.get('retention_days'), 5)

    def test_update_policy_validation_replication(self):
        payload = {"replication_factor": 0}
        r = self.client.post(f'/api/state/buckets/{self.name}/policy', json=payload, headers={'x-api-token':'tok'})
        self.assertEqual(r.status_code, 400)

    def test_update_policy_validation_cache(self):
        payload = {"cache_policy": "invalid_choice"}
        r = self.client.post(f'/api/state/buckets/{self.name}/policy', json=payload, headers={'x-api-token':'tok'})
        self.assertEqual(r.status_code, 400)

    def test_update_policy_requires_token(self):
        payload = {"replication_factor": 2}
        r = self.client.post(f'/api/state/buckets/{self.name}/policy', json=payload)
        self.assertEqual(r.status_code, 401)

if __name__ == '__main__':
    unittest.main()
