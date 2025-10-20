import unittest
import time
from fastapi.testclient import TestClient
from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestDashboardNetworkHistory(unittest.TestCase):
    def setUp(self):
        self.app = ConsolidatedMCPDashboard({'host':'127.0.0.1','port':0})
        self.client = TestClient(self.app.app)

    def test_network_history_accumulates(self):
        # Initial fetch (may be empty)
        r0 = self.client.get('/api/metrics/network')
        self.assertEqual(r0.status_code, 200)
        data0 = r0.json()
        pts0 = data0.get('points', [])

        # Need at least two snapshots to record first delta
        self.app._gather_metrics_snapshot()
        time.sleep(0.01)
        self.app._gather_metrics_snapshot()
        time.sleep(0.01)
        self.app._gather_metrics_snapshot()

        r1 = self.client.get('/api/metrics/network')
        self.assertEqual(r1.status_code, 200)
        data1 = r1.json()
        pts1 = data1.get('points', [])
        self.assertGreaterEqual(len(pts1), len(pts0))
        # Expect at least one point after snapshots
        self.assertGreaterEqual(len(pts1), 1)
        # Each point should have required keys
        for p in pts1:
            self.assertIn('ts', p)
            self.assertIn('rx_bps', p)
            self.assertIn('tx_bps', p)

        # Filtering with seconds should not increase count and should return subset
        r2 = self.client.get('/api/metrics/network?seconds=1')
        self.assertEqual(r2.status_code, 200)
        pts2 = r2.json().get('points', [])
        self.assertLessEqual(len(pts2), len(pts1))

if __name__ == '__main__':  # pragma: no cover
    unittest.main()
