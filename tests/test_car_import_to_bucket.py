import base64
import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestCarImportToBucket(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.app = ConsolidatedMCPDashboard({'host': '127.0.0.1', 'port': 0, 'data_dir': cls.tmpdir.name})
        cls.client = TestClient(cls.app.app)

    @classmethod
    def tearDownClass(cls):
        try: cls.tmpdir.cleanup()
        except Exception: pass

    def rpc(self, name, args=None):
        r = self.client.post('/mcp/tools/call', json={
            'jsonrpc': '2.0', 'method': 'tools/call', 'id': 1,
            'params': {'name': name, 'arguments': args or {}}
        })
        self.assertEqual(r.status_code, 200)
        return r.json()['result']

    def test_car_import_into_bucket(self):
        # setup backend + bucket
        backend_root = os.path.join(self.tmpdir.name, 'root')
        os.makedirs(backend_root, exist_ok=True)
        self.rpc('backend_create', { 'name': 'localx', 'type': 'local_fs', 'config': { 'base_path': backend_root } })
        self.rpc('create_bucket', { 'name': 'bkt', 'backend': 'localx' })
        # import
        data = b'car-data-123'
        b64 = base64.b64encode(data).decode('ascii')
        res = self.rpc('import_car_to_bucket', { 'name': 'demo', 'bucket': 'bkt', 'content_b64': b64 })
        self.assertEqual(res.get('status'), 'ok')
        path = res.get('path')
        self.assertTrue(os.path.exists(path))
        with open(path, 'rb') as f:
            self.assertEqual(f.read(), data)
        # ensure placed under backend_root/cars/demo.car
        self.assertTrue(path.endswith('demo.car'))
        self.assertTrue(os.path.realpath(path).startswith(os.path.realpath(os.path.join(backend_root, 'cars'))))


if __name__ == '__main__':
    unittest.main()
