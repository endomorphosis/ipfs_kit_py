import unittest
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestBackendsServicesTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = ConsolidatedMCPDashboard({'host': '127.0.0.1', 'port': 0})
        cls.client = TestClient(cls.app.app)

    def rpc(self, name, args=None):
        r = self.client.post('/mcp/tools/call', json={
            'jsonrpc': '2.0', 'method': 'tools/call', 'id': 1,
            'params': {'name': name, 'arguments': args or {}}
        })
        self.assertEqual(r.status_code, 200)
        return r.json()['result']

    def test_backend_crud(self):
        name = 'testbe'
        # create
        res = self.rpc('backend_create', { 'name': name, 'type': 'ipfs', 'config': { 'endpoint': 'http://127.0.0.1:5001' } })
        self.assertTrue(res.get('success', False) or 'exists' in (res.get('error','')))
        # show
        res = self.rpc('backend_show', { 'name': name })
        self.assertEqual(res.get('name'), name)
        # update
        res = self.rpc('backend_update', { 'name': name, 'config': { 'token': 'abc' } })
        self.assertTrue(res.get('success', False))
        # remove
        res = self.rpc('backend_remove', { 'name': name })
        self.assertTrue(res.get('success', False))

    def test_service_control(self):
        res = self.rpc('control_service', { 'service': 'IPFS Daemon', 'action': 'start' })
        self.assertEqual(res.get('status'), 'ok')


if __name__ == '__main__':
    unittest.main()
