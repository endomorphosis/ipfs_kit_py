from ..ipfs_kit_py import ipfs_kit_py

class test_ipfs_kit_py:
    def init(self, resources, metadata):
        self.resources = resources
        self.metadata = metadata
        self.ipfs_kit_py = ipfs_kit_py(resources, metadata)
        return None
    
    def __call__(self, *args, **kwds):
        return None

    def test(self):
        results = {}
        init = None
        storacha = None
        try:
            init = self.ipfs_kit_py.init()
            results["init"] = init
        except Exception as e:
            results["init"] = e
        try:
            storacha_kit = self.ipfs_kit_py.storacha_kit()
            storacha_test = storacha_kit.test()
            results["storacha"] = storacha_test
        except Exception as e:
            results["storacha"] = e
        
        return results
    
if __name__ == "__main__":
    resources = {}
    metadata = {}
    test_ipfs_kit = test_ipfs_kit_py(resources, metadata)
    test_ipfs_kit.test()