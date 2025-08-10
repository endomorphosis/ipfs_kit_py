import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from consolidated_mcp_dashboard import ConsolidatedMCPDashboard


class TestBucketBackendMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.app = ConsolidatedMCPDashboard({'host': '127.0.0.1', 'port': 0, 'data_dir': cls.tmpdir.name})
        cls.client = TestClient(cls.app.app)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.tmpdir.cleanup()
        except Exception:
            pass

    def rpc(self, name, args=None):
        r = self.client.post('/mcp/tools/call', json={
            'jsonrpc': '2.0', 'method': 'tools/call', 'id': 1,
            'params': {'name': name, 'arguments': args or {}}
        })
        self.assertEqual(r.status_code, 200)
        return r.json()['result']

    def test_bucket_local_fs_mapping(self):
        # Create a local_fs backend pointing to a temp subdir
        backend_root = os.path.join(self.tmpdir.name, 'storage_root')
        os.makedirs(backend_root, exist_ok=True)
        be = self.rpc('backend_create', {
            'name': 'local1', 'type': 'local_fs',
            'config': { 'base_path': backend_root }
        })
        self.assertTrue(be.get('success', False))
        # Create bucket bound to that backend (writes YAML + registry)
        bk = self.rpc('create_bucket', { 'name': 'mapped', 'backend': 'local1' })
        self.assertEqual(bk.get('name'), 'mapped')
        # Resolve bucket path
        rbp = self.rpc('resolve_bucket_path', { 'bucket': 'mapped' })
        self.assertEqual(os.path.realpath(rbp.get('path') or ''), os.path.realpath(backend_root))
        # Now write/read via Files tool with bucket mapping
        wr = self.rpc('write_file', { 'bucket': 'mapped', 'path': 'a/b/c.txt', 'content': 'hello' })
        self.assertIn('bytes', wr)
        rd = self.rpc('read_file', { 'bucket': 'mapped', 'path': 'a/b/c.txt' })
        self.assertEqual(rd.get('content'), 'hello')
        # The file should exist under backend_root/a/b/c.txt
        path = os.path.join(backend_root, 'a', 'b', 'c.txt')
        with open(path, 'r', encoding='utf-8') as f:
            self.assertEqual(f.read(), 'hello')


if __name__ == '__main__':
    unittest.main()
