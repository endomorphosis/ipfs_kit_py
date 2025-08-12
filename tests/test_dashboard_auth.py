import unittest
from fastapi.testclient import TestClient
from consolidated_mcp_dashboard import ConsolidatedMCPDashboard
import time

class TestDashboardAuth(unittest.TestCase):
    def setUp(self):
        self.token = "testtoken123"
        self.app = ConsolidatedMCPDashboard({'host':'127.0.0.1','port':0,'api_token':self.token})
        self.client = TestClient(self.app.app)

    def test_read_endpoints_unprotected(self):
        # list buckets (read) should be allowed without token
        r = self.client.get('/api/state/buckets')
        self.assertEqual(r.status_code, 200)
        # tools list (read) should be allowed
        r2 = self.client.post('/mcp/tools/list')
        self.assertEqual(r2.status_code, 200)

    def test_mutating_bucket_requires_token(self):
        name = f"authbucket_{int(time.time())}"
        # Without token -> 401
        r = self.client.post('/api/state/buckets', json={'name': name})
        self.assertEqual(r.status_code, 401)
        # With wrong token -> 401
        r2 = self.client.post('/api/state/buckets', json={'name': name}, headers={'x-api-token':'wrong'})
        self.assertEqual(r2.status_code, 401)
        # With correct token -> 200
        r3 = self.client.post('/api/state/buckets', json={'name': name}, headers={'x-api-token':self.token})
        self.assertEqual(r3.status_code, 200)
        self.assertTrue(r3.json().get('ok'))

    def test_tools_call_requires_token(self):
        # choose a simple tool
        payload = {'name':'get_system_status','args':{}}
        r = self.client.post('/mcp/tools/call', json=payload)
        self.assertEqual(r.status_code, 401)
        r2 = self.client.post('/mcp/tools/call', json=payload, headers={'Authorization': f'Bearer {self.token}'})
        self.assertEqual(r2.status_code, 200)
        self.assertIn('result', r2.json())

if __name__ == '__main__':
    unittest.main()
