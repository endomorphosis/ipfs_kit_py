from ipfs_kit_py import ipfs_kit
import json

class test_ipfs_kit_py:
    def __init__(self, resources=None, metadata=None):
        self.resources = resources or {}
        self.metadata = metadata or {}
        self.ipfs_kit_py = ipfs_kit(self.resources, self.metadata)
        
    def __call__(self, *args, **kwds):
        return None

    def test(self):
        results = {}
        init = None
        storacha_kit = None
        ipfs_install = None
        ipfs_follow = None
        try:
            init = self.ipfs_kit_py.init()
            results["init"] = init
        except Exception as e:
            results["init"] = str(e)
        try:
            ipfs_kit_install = self.ipfs_kit_py.install_ipfs()
            ipfs_kit_install_test = ipfs_kit_install.test()
            results["ipfs_kit_install"] = ipfs_kit_install_test
        except Exception as e:
            results["ipfs_kit_install"] = str(e)
            
        try:
            storacha_kit = self.ipfs_kit_py.storacha_kit_py()
            storacha_kit_test = storacha_kit.test()
            results["storacha_kit"] = storacha_kit_test
        except Exception as e:
            results["storacha_kit"] = str(e)
        
        try:
            ipfs_cluster_follow = self.ipfs_kit_py.ipfs_cluster_follow()
            ipfs_cluster_follow_test = ipfs_cluster_follow.test()
            results["ipfs_cluster_follow"] = ipfs_cluster_follow_test
        except Exception as e:
            results["ipfs_cluster_follow"] = str(e)
            
        try:
            ipfs_cluster_ctl = self.ipfs_kit_py.ipfs_cluster_ctl()
            ipfs_cluster_ctl_test = ipfs_cluster_ctl.test()
            results["ipfs_cluster_ctl"] = ipfs_cluster_ctl_test
        except Exception as e:
            results["ipfs_cluster_ctl"] = str(e)
            
        try:
            ipfs_cluster_service = self.ipfs_kit_py.ipfs_cluster_service()
            ipfs_cluster_service_test = ipfs_cluster_service.test()
            results["ipfs_cluster_service"] = ipfs_cluster_service_test
        except Exception as e:
            results["ipfs_cluster_service"] = str(e)
        
        try:
            ipfs_kit = self.ipfs_kit_py.ipfs_kit()
            ipfs_kit_test = ipfs_kit.test()
            results["ipfs_kit"] = ipfs_kit_test
        except Exception as e:
            results["ipfs_kit"] = str(e)
            
        try:
            s3_kit = self.ipfs_kit_py.s3_kit()
            s3_kit_test = s3_kit.test()
            results["s3_kit"] = s3_kit_test
        except Exception as e:
            results["s3_kit"] = str(e)
            
        try:
            test_fio = self.ipfs_kit_py.test_fio()
            test_fio_test = test_fio.test()
            results["test_fio"] = test_fio_test
        except Exception as e:
            results["test_fio"] = str(e)
        
        # Process results to ensure all exceptions are converted to strings for JSON serialization
        for key, value in results.items():
            if isinstance(value, Exception):
                results[key] = str(value)
                
        with open("test_results.json", "w") as f:
            f.write(json.dumps(results))
        return results
    
if __name__ == "__main__":
    resources = {}
    metadata = {}
    test_ipfs_kit = test_ipfs_kit_py(resources, metadata)
    test_ipfs_kit.test()