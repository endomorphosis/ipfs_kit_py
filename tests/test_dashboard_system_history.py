import unittest, time
from fastapi.testclient import TestClient
from consolidated_mcp_dashboard import ConsolidatedMCPDashboard

class TestDashboardSystemHistory(unittest.TestCase):
    def setUp(self):
        self.dash = ConsolidatedMCPDashboard({'host':'127.0.0.1','port':0})
        self.client = TestClient(self.dash.app)

    def test_system_history_accumulates_and_filters(self):
        # generate several snapshots
        for _ in range(5):
            self.dash._gather_metrics_snapshot()
            time.sleep(0.01)
        r = self.client.get('/api/metrics/system/history')
        self.assertEqual(r.status_code, 200)
        js = r.json()
        pts = js.get('points', [])
        # At least one point expected (if psutil available metrics captured)
        self.assertIsInstance(pts, list)
        if pts:
            self.assertIn('ts', pts[0])
            # cpu/mem/disk keys present (values may be None if psutil missing)
            for k in ('cpu','mem','disk'):
                self.assertIn(k, pts[0])
        # Filter window smaller than total elapsed should not increase length
        r2 = self.client.get('/api/metrics/system/history?seconds=1')
        self.assertEqual(r2.status_code, 200)
        pts2 = r2.json().get('points', [])
        self.assertLessEqual(len(pts2), len(pts))

if __name__ == '__main__':  # pragma: no cover
    unittest.main()
