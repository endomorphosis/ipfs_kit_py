import os
import unittest
import tempfile
from fastapi.testclient import TestClient

# Import the dashboard app
from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestAssetServing(unittest.TestCase):
    def setUp(self):
        # Use a temp data dir to avoid touching real ~/.ipfs_kit during tests
        self._tmp = tempfile.TemporaryDirectory()
        cfg = {
            "host": "127.0.0.1",
            "port": 0,  # not used by TestClient
            "data_dir": self._tmp.name,
            "debug": False,
        }
        self.dashboard = ConsolidatedMCPDashboard(cfg)
        self.client = TestClient(self.dashboard.app)

    def tearDown(self):
        try:
            self.client.close()
        except Exception:
            pass
        self._tmp.cleanup()

    def test_mcp_client_served_from_static(self):
        # Ensure the static SDK exists where the server looks
        sdk_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'mcp-sdk.js')
        sdk_path = os.path.abspath(sdk_path)
        self.assertTrue(os.path.exists(sdk_path), f"Expected SDK file at {sdk_path}")

        r = self.client.get('/mcp-client.js')
        self.assertEqual(r.status_code, 200)
        # Header indicates source
        self.assertEqual(r.headers.get('X-MCP-SDK-Source'), 'static')
        body = r.text
        self.assertIn('MCP SDK (Browser/Node UMD)', body)
        # Shim should be appended
        self.assertIn('MCP.listTools', body)
        self.assertIn('MCP.callTool', body)

    def test_root_renders_beta(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        html = r.text
        self.assertIn('IPFS Kit MCP Dashboard', html)
        # Fallback tool runner exists but is hidden in beta mode
        self.assertIn('<div id="toolrunner-fallback"', html)
        self.assertIn('style="display:none"', html)


if __name__ == '__main__':
    unittest.main()
