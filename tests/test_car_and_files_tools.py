import base64
import unittest
from fastapi.testclient import TestClient

from ipfs_kit_py.mcp.dashboard.consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestCarAndFilesTools(unittest.TestCase):
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

    def test_bucket_aware_file_ops(self):
        # Write a file into a bucket
        res = self.rpc('write_file', { 'bucket': 'demo', 'path': 'hello.txt', 'content': 'hi' })
        self.assertIn('bytes', res)
        # Read it back
        res2 = self.rpc('read_file', { 'bucket': 'demo', 'path': 'hello.txt' })
        self.assertEqual(res2.get('content'), 'hi')
        # List files
        res3 = self.rpc('list_files', { 'bucket': 'demo', 'path': '' })
        self.assertTrue(any(f.get('name') == 'hello.txt' for f in res3.get('files', [])))

    def test_car_import_export_remove(self):
        data = b'car-bytes-example'
        b64 = base64.b64encode(data).decode('ascii')
        # Import
        imp = self.rpc('import_car', { 'name': 'demo', 'content_b64': b64 })
        self.assertEqual(imp.get('status'), 'ok')
        # List
        lst = self.rpc('list_cars')
        names = [c.get('name') for c in lst.get('cars', [])]
        self.assertIn('demo.car', names)
        # Export
        exp = self.rpc('export_car', { 'name': 'demo' })
        out = base64.b64decode(exp.get('content_b64') or '')
        self.assertEqual(out, data)
        # Remove
        rm = self.rpc('remove_car', { 'name': 'demo' })
        self.assertEqual(rm.get('status'), 'deleted')


if __name__ == '__main__':
    unittest.main()
