import unittest, time, json
from fastapi.testclient import TestClient
from consolidated_mcp_dashboard import ConsolidatedMCPDashboard

class TestDashboardRealtimeWebSocket(unittest.TestCase):
    def setUp(self):
        self.dash = ConsolidatedMCPDashboard({'host':'127.0.0.1','port':0})
        self.client = TestClient(self.dash.app)

    def test_realtime_websocket_metrics(self):
        # Connect to websocket
        with self.client.websocket_connect('/ws') as ws:
            initial = ws.receive_json()
            self.assertEqual(initial.get('type'), 'system_update')
            # Next message should be immediate metrics snapshot we send on connect
            first_metrics = ws.receive_json()
            self.assertEqual(first_metrics.get('type'), 'metrics')
            # Ensure core metric keys exist (values may be missing if psutil not present)
            for key in ['cpu','mem','disk']:
                self.assertIn(key, first_metrics)
            # Averages may or may not exist yet; ensure keys are present
            for akey in ['avg_cpu','avg_mem','avg_disk']:
                self.assertIn(akey, first_metrics)

if __name__ == '__main__':  # pragma: no cover
    unittest.main()
