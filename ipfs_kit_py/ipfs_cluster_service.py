import sys
import os
import subprocess
import tempfile
import json

class ipfs_cluster_service:
    def __init__(self, resources, metadata= None):
        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        self.path = os.environ['PATH']
        self.path = self.path + ":" + os.path.join(self.this_dir, "bin")
        self.path_string = "PATH="+ self.path
        if metadata is not None:
            if "config" in metadata:
                if metadata['config'] is not None:
                    self.config = metadata['config']
            if "role" in metadata:
                if metadata['role'] is not None:
                    self.role = metadata['role']
                    if self.role not in  ["master","worker","leecher"]:
                        raise Exception("role is not either master, worker, leecher")
                    else:
                        self.role = "leecher"

            if self.role == "leecher" or self.role == "worker" or self.role == "master":
                pass
        
    def test_ipfs_cluster_service(self):
        detect = os.system(self.path_string + " which ipfs-cluster-service")
        if len(detect) > 0:
            return True
        else:
            return False
        pass

    def ipfs_cluster_service_start(self):
        if os.getuid() == 0:
            command = "systemctl start ipfs-cluster-service"
            results = subprocess.check_output(command, shell=True)
            results = results.decode()
        else:
            # TODO: Update these commands!!!!
            command = self.path_string + " ipfs-cluster-service daemon --bootstrap /ip4/167.99.96.231/tcp/9096/p2p/12D3KooWDYKMnVLKnP2SmM8umJEEKdhug93QYybmNUEiSe1Kwjmu"
            results = subprocess.check_output(command, shell=True)
            results = results.decode()
        
        return results  
    
    def ipfs_cluster_service_stop(self):
        if os.getuid() == 0:
            command = "systemctl stop ipfs-cluster-service"
            results = subprocess.check_output(command, shell=True)
            results = results.decode()
        else:
            command = "ps -ef | grep ipfs-cluster-service | grep -v grep | awk '{print $2}' | xargs kill -9"
            results = subprocess.check_output(command, shell=True)
            results = results.decode()
        return results
    
    def ipfs_cluster_service_status(self):
        if os.getuid() == 0:
            command = self.path_string + " ipfs-cluster-service status"
            results = subprocess.check_output(command, shell=True)
            results = results.decode()
        else:
            command = "ps -ef | grep ipfs-cluster-service | grep daemon | grep -v grep | wc -l"
            results = subprocess.check_output(command, shell=True)
            results = results.decode()
        return results
    
    def test(self):
        results = {}
        try:
            test = self.test_ipfs_cluster_service()
            results["test"] = test
        except Exception as e:
            results["test"] = e
        return results

if __name__ == "__main__":
    resources = {}
    metadata = {}
    this_ipfs_cluster_service = ipfs_cluster_service(resources, metadata)
    results = this_ipfs_cluster_service.test()
    print(results)
    pass
