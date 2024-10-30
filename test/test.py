from ..ipfs_kit_py import ipfs_kit_py
import json

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
        storacha_kit = None
        ipfs_install = None
        ipfs_follow = None
        try:
            init = self.ipfs_kit_py.init()
            results["init"] = init
        except Exception as e:
            results["init"] = e
        try:
            ipfs_kit_install = self.ipfs_kit_py.install_ipfs()
            ipfs_kit_install_test = ipfs_kit_install.test()
            results["ipfs_kit_install"] = ipfs_kit_install_test
        except Exception as e:
            results["ipfs__kit_install"] = e
            
        try:
            storacha_kit = self.ipfs_kit_py.storacha_kit_py()
            storacha__kit_test = storacha_kit.test()
            results["storacha_kit"] = storacha__kit_test
        except Exception as e:
            results["storacha"] = e
        
        try:
            ipfs_cluster_follow = self.ipfs_kit_py.ipfs_cluster_follow()
            ipfs_cluster_follow_test = ipfs_cluster_follow.test()
            results["ipfs_cluster_follow"] = ipfs_cluster_follow_test
        except Exception as e:
            results["ipfs_cluster_follow"] = e
            
        try:
            ipfs_cluster_ctl = self.ipfs_kit_py.ipfs_cluster_ctl()
            ipfs_cluster_ctl_test = ipfs_cluster_ctl.test()
            results["ipfs_cluster_ctl"] = ipfs_cluster_ctl_test
        except Exception as e:
            results["ipfs_cluster_ctl"] = e
            
        try:
            ipfs_cluster_service = self.ipfs_kit_py.ipfs_cluster_service()
            ipfs_cluster_service_test = ipfs_cluster_service.test()
            results["ipfs_cluster_service"] = ipfs_cluster_service_test
        except Exception as e:
            results["ipfs_cluster_service"] = e
        
        try:
            ipfs_kit = self.ipfs_kit_py.ipfs_kit()
            ipfs_kit_test = ipfs_kit.test()
            results["ipfs_kit"] = ipfs_kit_test
        except Exception as e:
            results["ipfs_kit"] = e
            
        try:
            s3_kit = self.ipfs_kit_py.s3_kit()
            s3_kit_test = s3_kit.test()
            results["s3_kit"] = s3_kit_test
        except Exception as e:
            results["s3_kit"] = e
            
        try:
            test_fio = self.ipfs_kit_py.test_fio()
            test_fio_test = test_fio.test()
            results["test_fio"] = test_fio_test
        except Exception as e:
            results["test_fio"] = e
        
        with open("test_results.json", "w") as f:
            f.write(json.dumps(results))
        return results
    
if __name__ == "__main__":
    resources = {}
    metadata = {}
    test_ipfs_kit = test_ipfs_kit_py(resources, metadata)
    test_ipfs_kit.test()