import unittest
from fastapi.testclient import TestClient

from consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestDashboardStatusAndWebSocket(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ConsolidatedMCPDashboard({'host': '127.0.0.1', 'port': 0})
        cls.client = TestClient(cls.app.app)

    def test_mcp_status_endpoint(self):
        r = self.client.get('/api/mcp/status')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data.get('success'))
        d = data.get('data') or {}
        self.assertIn('protocol_version', d)
        self.assertIsInstance(d.get('total_tools'), int)
        self.assertIn('uptime', d)

    def test_websocket_system_update(self):
        with self.client.websocket_connect('/ws') as ws:
            msg = ws.receive_json()
            self.assertEqual(msg.get('type'), 'system_update')
            inner = (msg.get('data') or {}).get('data') or {}
            self.assertIn('uptime', inner)
            # echo path
            ws.send_text('ping')
            ack = ws.receive_text()
            self.assertEqual(ack, 'ack')


if __name__ == '__main__':
    unittest.main()
