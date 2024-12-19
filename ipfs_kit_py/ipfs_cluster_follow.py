import sys
import os
import subprocess
import tempfile
import json

class ipfs_cluster_follow:
    def __init__(self, resources=None, metadata=None):
        self.resources = resources
        self.metadata = metadata
        self.ipfs_follow_info = self.ipfs_follow_info
        self.ipfs_follow_list = self.ipfs_follow_list
        self.ipfs_follow_start = self.ipfs_follow_start
        self.ipfs_follow_stop = self.ipfs_follow_stop
        self.ipfs_follow_run = self.ipfs_follow_run
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
            
            if "cluster_name" in metadata:
                if metadata['cluster_name'] is not None:
                    self.cluster_name = metadata['cluster_name']

            if self.role == "leecher" or self.role == "worker" or self.role == "master":
                pass

    def ipfs_follow_start(self, **kwargs):
        if "cluster_name" in list(self.__dict__.keys()):
            cluster_name = self.cluster_name
        if "cluster_name" in kwargs:
            cluster_name = kwargs['cluster_name']
        try:
            if os.getuid() == 0:
                command1 = "systemctl start ipfs-cluster-follow"
                results1 = subprocess.check_output(command1, shell=True)
                results1 = results1.decode()
            else:
                command1 = "export IPFS_PATH=" + self.ipfs_path + " && " + self.path_string + " ipfs-cluster-follow " + cluster_name + " run"
                results1 = subprocess.run(command1, shell=True)
                results1 = results1.decode()
        except Exception as e:
            results = str(e)
        finally:
            pass
        detect = "ps -ef | grep ipfs-cluster-follow | grep -v grep | awk '{print $2}'"
        detect_results = subprocess.check_output(detect, shell=True)
        detect_results = detect_results.decode()
        results2 = False

        if len(detect_results) == 0:
            homedir = os.path.expanduser("~")
            ls_file = os.listdir(homedir + "/.ipfs-cluster-follow/" + cluster_name)      
            if "api-socket" in ls_file:
                rm_command = "rm ~/.ipfs-cluster-follow/" + cluster_name + "/api-socket"
                rm_results = subprocess.check_output(rm_command, shell=True)
                rm_results = rm_results.decode()
                results2 = True   
            try:
                command2 = self.path_string + " ipfs-cluster-follow " + cluster_name + " run"
                results2 = subprocess.Popen(command2, shell=True, stdout=subprocess.PIPE)
            except Exception as e:
                results = str(e)
            finally:
                pass

        results = {
            "systemctl": results1,
            "bash": results2
        }
        return results

    def ipfs_follow_stop(self, **kwargs):
        if "cluster_name" in list(self.__dict__.keys()):
            cluster_name = self.cluster_name
        if "cluster_name" in kwargs:
            cluster_name = kwargs['cluster_name']
        try:
            if os.getuid() == 0:
                command1 = "systemctl stop ipfs-cluster-follow"
                results1 = subprocess.check_output(command1, shell=True)
                results1 = results1.decode()
            else:
                command1 = "export IPFS_PATH=" + self.ipfs_path + " && " + self.path_string + " ipfs-cluster-follow " + cluster_name + " stop"
                results1 = subprocess.run(command1, shell=True)
                results1 = results1.decode()
        except Exception as e:
            results1 = str(e)
        finally:
            pass
        try:
            command2 = "ps -ef | grep ipfs-cluster-follow | grep -v grep | awk '{print $2}' | xargs kill -9"
            results2 = subprocess.check_output(command2, shell=True)
            results2 = results2.decode()
        except Exception as e:
            results2 = str(e)
        finally:
            pass

        try:
            command3 = "rm ~/.ipfs-cluster-follow/" + cluster_name + "/api-socket"
            results3 = subprocess.check_output(command3, shell=True)
            results3 = results3.decode()
        except Exception as e:
            results3 = str(e)
        finally:
            pass

        results = {
            "systemctl": results1,
            "bash": results2,
            "api-socket": results3
        }
        return results  

#    def ipfs_follow_run(self, **kwargs):
#        if "cluster_name" in list(self.keys()):
#            cluster_name = self.cluster_name
#        if "cluster_name" in kwargs:
#            cluster_name = kwargs['cluster_name']
#
#        command = "ipfs cluster-follow " + cluster_name + " run"
#        results = subprocess.check_output(command, shell=True)
#        results = results.decode()
#        return results

    def ipfs_follow_list(self, **kwargs):
        if "cluster_name" in list(self.__dict__.keys()):
            cluster_name = self.cluster_name
        if "cluster_name" in kwargs:
            cluster_name = kwargs['cluster_name']

        command = self.path_string + " ipfs-cluster-follow " + cluster_name + " list"
        results = subprocess.check_output(command, shell=True)
        results = results.decode()
        results_dict = {}
        if len(results) > 0:
            results = results.split("\n")
            for i in range(len(results)):

                while "  " in results[i]:
                    results[i] = results[i].replace("  ", " ")

                results[i] = results[i].split(" ")
                if len(results[i]) >= 2:
                    results[i] = {
                        results[i][1]: results[i][0]
                    }

            for i in range(len(results)):
                if type(results[i]) == dict:
                    key = list(results[i].keys())[0]
                    value = results[i][key]
                    results_dict[key] = value
                    
            return results_dict
        else:
            return False

    def ipfs_follow_info(self, **kwargs):
        results_dict = {}
        if "cluster_name" in list(self.__dict__.keys()):
            cluster_name = self.cluster_name
        if "cluster_name" in list(kwargs.keys()):
            cluster_name = kwargs['cluster_name']
        try:
            command = self.path_string + " ipfs-cluster-follow " + cluster_name + " info"
            results = subprocess.check_output(command, shell=True)
            results = results.decode()
            results = results.split("\n")
            if len(results) > 0:
                results_dict = {
                    "cluster_name": cluster_name,
                    "config_folder": results[2].split(": ")[1],
                    "config_source": results[3].split(": ")[1],
                    "cluster_peer_online": results[4].split(": ")[1],
                    "ipfs_peer_online": results[5].split(": ")[1],
                }

        except Exception as e:
            results = str(e)
        finally:
            pass
        
        return results_dict
        
    
    def ipfs_follow_run(self, **kwargs):
        if "cluster_name" in list(self.keys()):
            cluster_name = self.cluster_name
        if "cluster_name" in kwargs:
            cluster_name = kwargs['cluster_name']

        command = self.path_string + " ipfs-cluster-follow "+ cluster_name +" run"
        results = subprocess.check_output(command, shell=True)
        results = results.decode()
        results = results.split("\n")
        return results


    def test_ipfs_cluster_follow(self):
        detect = subprocess.check_output(self.path_string + " which ipfs-cluster-follow", shell=True)
        detect = detect.decode()
        if len(detect) > 0:
            return True
        else:
            return False
        pass
    
    def test(self):
        results = {}
        try:
            results["test_ipfs_cluster_follow"] = self.test_ipfs_cluster_follow()
        except Exception as e:
            results["test_ipfs_cluster_follow"] = e
        return results

ipfs_cluster_follow = ipfs_cluster_follow
if __name__ == "__main__":
    metadata = {
        "cluster_name": "test"
    }
    resources = {
        
    }
    this_ipfs_cluster_follow = ipfs_cluster_follow(resources, metadata)
    results = this_ipfs_cluster_follow.test_ipfs_cluster_follow()
    print(results)
    pass
