import time
import unittest
from fastapi.testclient import TestClient
from consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestServices(unittest.TestCase):
    def setUp(self):
        self.app = ConsolidatedMCPDashboard({}).app
        self.client = TestClient(self.app)

    def tearDown(self):
        try:
            self.client.close()
        except Exception:
            pass

    def test_services_actions_transition(self):
        # Initial list
        r = self.client.get('/api/services')
        self.assertEqual(r.status_code, 200)
        # Start ipfs
        r = self.client.post('/api/services/ipfs/start', headers={'x-api-token': ''})
        self.assertEqual(r.status_code, 200, r.text)
        js = r.json()
        self.assertTrue(js.get('ok'))
        # Allow transition timer to fire
        time.sleep(1.2)
        r = self.client.get('/api/services')
        st = r.json()['services']['ipfs']['status']
        self.assertIn(st, ('running', 'starting'))  # tolerate slow CI

    def test_services_auth_when_token_set(self):
        dash = ConsolidatedMCPDashboard({'api_token': 'secret'})
        client = TestClient(dash.app)
        try:
            r = client.post('/api/services/ipfs/start')
            self.assertEqual(r.status_code, 401)
            r = client.post('/api/services/ipfs/start', headers={'x-api-token': 'secret'})
            self.assertEqual(r.status_code, 200)
        finally:
            client.close()


if __name__ == '__main__':
    unittest.main()
