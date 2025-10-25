import re
import unittest
from fastapi.testclient import TestClient
from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestAssets(unittest.TestCase):
    def setUp(self):
        self.app = ConsolidatedMCPDashboard({}).app
        self.client = TestClient(self.app)

    def tearDown(self):
        try:
            self.client.close()
        except Exception:
            pass

    def test_mcp_client_header_and_body(self):
        r = self.client.get('/mcp-client.js')
        self.assertEqual(r.status_code, 200)
        src = r.headers.get('X-MCP-SDK-Source') or r.headers.get('x-mcp-sdk-source')
        # Should be either 'static' or 'inline'
        self.assertIn(src, ('static', 'inline'))
        self.assertIn('listTools', r.text)
        self.assertIn('callTool', r.text)

    def test_root_html_includes_assets(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        body = r.text
        self.assertIn('/mcp-client.js', body)
        self.assertIn('/app.js', body)

    def test_app_js_contains_expected_functions(self):
        r = self.client.get('/app.js')
        self.assertEqual(r.status_code, 200)
        js = r.text
        # Files-tab loader should be loadVfsBuckets, not colliding with Buckets loadBuckets
        self.assertRegex(js, r"async\s+function\s+loadVfsBuckets\s*\(")
        # Buckets view still has loadBuckets definition once
        buckets_defs = len(re.findall(r"async\s+function\s+loadBuckets\s*\(", js))
        self.assertGreaterEqual(buckets_defs, 1)


if __name__ == '__main__':
    unittest.main()
