import unittest
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestDashboardSdkIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ConsolidatedMCPDashboard({'host': '127.0.0.1', 'port': 0})
        cls.client = TestClient(cls.app.app)

    def test_root_serves_html_with_sdk_and_app(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        html = r.text
        self.assertIn('/static/mcp-sdk.js', html)
        self.assertIn('/app.js', html)

    def test_app_js_contains_sdk_helpers(self):
        r = self.client.get('/app.js')
        self.assertEqual(r.status_code, 200)
        js = r.text
        self.assertIn('function rpcTool(', js)
        self.assertIn('ensureMcp()', js)

    def test_mcp_tools_list(self):
        r = self.client.post('/mcp/tools/list', json={
            'jsonrpc': '2.0', 'method': 'tools/list', 'id': 1
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        tools = (data.get('result') or {}).get('tools')
        self.assertIsInstance(tools, list)
        self.assertGreater(len(tools or []), 0)

    def test_mcp_tools_call_get_system_status(self):
        r = self.client.post('/mcp/tools/call', json={
            'jsonrpc': '2.0', 'method': 'tools/call',
            'params': {'name': 'get_system_status', 'arguments': {}},
            'id': 2
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn('result', data)
        status = data['result']
        # Expect common keys
        self.assertTrue('uptime' in status and 'cpu_percent' in status)

    def test_mcp_client_alias_serves_sdk(self):
        r = self.client.get('/mcp-client.js')
        self.assertEqual(r.status_code, 200)
        self.assertIn('MCP SDK', r.text or '')

    def test_logs_stream_endpoint_headers(self):
        r = self.client.get('/api/logs/stream')
        self.assertEqual(r.status_code, 200)
        # Content-Type for SSE
        self.assertIn('text/event-stream', r.headers.get('content-type', ''))


if __name__ == '__main__':
    unittest.main()
