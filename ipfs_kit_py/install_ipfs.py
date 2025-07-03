import binascii
import json
import math
import os
import platform
import random
import shutil
import subprocess
import sys
import tempfile
import time

test_folder = os.path.dirname(os.path.dirname(__file__)) + "/test"
sys.path.append(test_folder)
try:
    from .ipfs_multiformats import ipfs_multiformats_py
except ImportError:
    from ipfs_multiformats import ipfs_multiformats_py  # Fallback for direct script execution
try:
    from .test_fio import test_fio  # Corrected import statement
except ImportError:
    from test_fio import test_fio  # Fallback for direct script execution

class install_ipfs:
    def __init__(self, resources=None, metadata=None):
        self.resources = {}
        self.metadata = metadata
        self.ipfs_path = None
        # Config attributes for storing configuration data
        self.config_ipfs_cluster_ctl_data = None
        self.config_ipfs_cluster_follow_data = None
        self.config_ipfs_cluster_service_data = None
        # Note: install methods are defined as class methods below, not attributes
        if resources is not None and isinstance(resources, dict):
            self.resources = resources
        elif resources is not None and isinstance(resources, install_ipfs):
            self.resources = resources.resources
        elif resources is not None and isinstance(resources, install_ipfs):
            self.resources = resources.resources
        elif resources is not None and isinstance(resources, list):
            self.resources = {}
            for resource in resources:
                if isinstance(resource, dict):
                    self.resources.update(resource)
                elif isinstance(resource, install_ipfs):
                    self.resources.update(resource.resources)
                else:
                    raise TypeError("resources must be a dict or install_ipfs instance")
                
        if self.resources == {} and resources is not None:
            self.resources = resources
        if self.resources is {} and resources is not None:
            self.resources = resources
        if self.metadata is None:
            self.metadata = {}
        if "config_ipfs" not in dir(self) and "config_ipfs" in list(self.metadata.keys()):
            self.config_ipfs = self.metadata["config_ipfs"]
        elif "config_ipfs" in list(dir(self)) and "config_ipfs" in list(self.metadata.keys()):
            self.config_ipfs = self.metadata["config_ipfs"]
        if "ipfs_path" not in list(dir(self)) and "ipfs_path" in list(self.metadata.keys()):
            self.ipfs_path = self.metadata["ipfs_path"]
        else:
            self.ipfs_path = os.path.join(os.path.expanduser("~"), ".ipfs")
        if "config_ipfs_cluster_ctl" not in dir(self) and "config_ipfs_cluster_ctl" in list(self.metadata.keys()):
            self.config_ipfs_cluster_ctl_data = self.metadata["config_ipfs_cluster_ctl"]
        else:
            self.config_ipfs_cluster_ctl_data = {}
        if "config_ipfs_cluster_follow" not in dir(self) and "config_ipfs_cluster_follow" in list(self.metadata.keys()):
            self.config_ipfs_cluster_follow_data = self.metadata["config_ipfs_cluster_follow"]
        else:
            self.config_ipfs_cluster_follow_data = {}
        if "config_ipfs_cluster_service" not in dir(self) and "config_ipfs_cluster_service" in list(self.metadata.keys()):
            self.config_ipfs_cluster_service_data = self.metadata["config_ipfs_cluster_service"]
        else:
            self.config_ipfs_cluster_service_data = {}
        if "ipfs_test_install" not in dir(self) and "ipfs_test_install" in list(self.metadata.keys()):
            self.ipfs_test_install_obj = self.metadata["ipfs_test_install"]
        else:
            self.ipfs_test_install_obj = test_fio(self.resources, self.metadata)
        # Note: install methods are defined as methods below, no need to assign them here
        self.env_path = os.environ.get("PATH", "")
        if metadata and "path" in list(metadata.keys()):
            self.path = metadata["path"]
        else:
            self.path = self.env_path
        if "ipfs_multiformats" not in list(dir(self)):
            if "ipfs_multiformats" in list(self.resources.keys()) and "ipfs_multiformats" not in list(dir(self)):
                self.ipfs_multiformats = self.resources["ipfs_multiformats"]
            else:
                self.resources["ipfs_multiformats"] = ipfs_multiformats_py(resources, metadata)
                self.ipfs_multiformats = self.resources["ipfs_multiformats"]
        self.this_dir = os.path.dirname(os.path.realpath(__file__))
        if platform.system() == "Windows":
            bin_path = os.path.join(self.this_dir, "bin").replace("/", "\\")
            self.path = f'"{self.path};{bin_path}"'
            self.path = self.path.replace("\\", "/")
            self.path = self.path.replace(";;", ";")
            self.path = self.path.split("/")
            self.path = "/".join(self.path)
            self.path_string = "set PATH=" + self.path + " ; "
        elif platform.system() == "Linux":
            self.path = self.path + ":" + os.path.join(self.this_dir, "bin")
            self.path_string = "PATH=" + self.path
        elif platform.system() == "Darwin":
            self.path = self.path + ":" + os.path.join(self.this_dir, "bin")
            self.path_string = "PATH=" + self.path
        self.ipfs_cluster_service_dists = {
            "macos arm64": "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.2/ipfs-cluster-service_v1.1.2_darwin-arm64.tar.gz",
            "macos x86_64": "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.2/ipfs-cluster-service_v1.1.2_darwin-amd64.tar.gz",
            "linux arm64": "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.2/ipfs-cluster-service_v1.1.2_linux-arm64.tar.gz",
            "linux x86_64": "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.2/ipfs-cluster-service_v1.1.2_linux-amd64.tar.gz",
            "linux x86": "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.2/ipfs-cluster-service_v1.1.2_linux-386.tar.gz",
            "linux arm": "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.2/ipfs-cluster-service_v1.1.2_linux-arm.tar.gz",
            "windows x86_64": "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.2/ipfs-cluster-service_v1.1.2_windows-amd64.zip",
            "windows x86": "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.2/ipfs-cluster-service_v1.1.2_windows-386.zip",
            "freebsd x86_64": "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.2/ipfs-cluster-service_v1.1.2_freebsd-amd64.tar.gz",
            "freebsd x86": "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.2/ipfs-cluster-service_v1.1.2_freebsd-386.tar.gz",
            "freebsd arm": "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.2/ipfs-cluster-service_v1.1.2_freebsd-arm.tar.gz",
            "openbsd x86_64": "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.2/ipfs-cluster-service_v1.1.2_openbsd-amd64.tar.gz",
            "openbsd x86": "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.2/ipfs-cluster-service_v1.1.2_openbsd-386.tar.gz",
            "openbsd arm": "https://dist.ipfs.tech/ipfs-cluster-service/v1.1.2/ipfs-cluster-service_v1.1.2_openbsd-arm.tar.gz",
        }
        self.ipfs_cluster_service_dists_cids = {
            "macos arm64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "macos x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux arm64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux arm": "bafybeigk5q3g3q3k7m3qy4q3f",
            "windows x86_64": "bafkreidaqcd7q6ot464azswgvflr6ibemh2ty7e745pegccyiwetelg4kq",
            "windows x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd arm": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd arm": "bafybeigk5q3g3q3k7m3qy4q3f",
        }

        self.ipfs_dists = {
            "macos arm64": "https://dist.ipfs.tech/kubo/v0.34.1/kubo_v0.34.1_darwin-arm64.tar.gz",
            "macos x86_64": "https://dist.ipfs.tech/kubo/v0.34.1/kubo_v0.34.1_darwin-amd64.tar.gz",
            "linux arm64": "https://dist.ipfs.tech/kubo/v0.34.1/kubo_v0.34.1_linux-arm64.tar.gz",
            "linux x86_64": "https://dist.ipfs.tech/kubo/v0.34.1/kubo_v0.34.1_linux-amd64.tar.gz",
            "linux x86": "https://dist.ipfs.tech/kubo/v0.34.1/kubo_v0.34.1_linux-386.tar.gz",
            "linux arm": "https://dist.ipfs.tech/kubo/v0.34.1/kubo_v0.34.1_linux-arm.tar.gz",
            "windows x86_64": "https://dist.ipfs.tech/kubo/v0.34.1/kubo_v0.34.1_windows-amd64.zip",
            "windows x86": "https://dist.ipfs.tech/kubo/v0.34.1/kubo_v0.34.1_windows-386.zip",
            "freebsd x86_64": "https://dist.ipfs.tech/kubo/v0.34.1/kubo_v0.34.1_freebsd-amd64.tar.gz",
            "freebsd x86": "https://dist.ipfs.tech/kubo/v0.34.1/kubo_v0.34.1_freebsd-386.tar.gz",
            "freebsd arm": "https://dist.ipfs.tech/kubo/v0.34.1/kubo_v0.34.1_freebsd-arm.tar.gz",
            "openbsd x86_64": "https://dist.ipfs.tech/kubo/v0.34.1/kubo_v0.34.1_openbsd-amd64.tar.gz",
            "openbsd x86": "https://dist.ipfs.tech/kubo/v0.34.1/kubo_v0.34.1_openbsd-386.tar.gz",
            "openbsd arm": "https://dist.ipfs.tech/kubo/v0.34.1/kubo_v0.34.1_openbsd-arm.tar.gz",
        }
        self.ipfs_dists_cids = {
            "macos arm64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "macos x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux arm64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux arm": "bafybeigk5q3g3q3k7m3qy4q3f",
            "windows x86_64": "bafkreicfvtaic6cdfaxamh6vvrji3begavxpz3lehzgdqfib3jqfrvawou",
            "windows x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd arm": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd arm": "bafybeigk5q3g3q3k7m3qy4q3f",
        }
        self.ipfs_cluster_follow_dists = {
            "macos arm64": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_darwin-amd64.tar.gz",
            "macos x86_64": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_darwin-amd64.tar.gz",
            "linux arm64": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_linux-arm64.tar.gz",
            "linux x86_64": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_linux-amd64.tar.gz",
            "linux x86": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_linux-386.tar.gz",
            "linux arm": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_linux-arm.tar.gz",
            "windows x86_64": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_windows-amd64.zip",
            "windows x86": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_windows-386.zip",
            "freebsd x86_64": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_freebsd-amd64.tar.gz",
            "freebsd x86": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_freebsd-386.tar.gz",
            "freebsd arm": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_freebsd-arm.tar.gz",
            "openbsd x86_64": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_openbsd-amd64.tar.gz",
            "openbsd x86": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_openbsd-386.tar.gz",
            "openbsd arm": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_openbsd-arm.tar.gz",
        }
        self.ipfs_cluster_follow_dists_cids = {
            "macos arm64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "macos x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux arm64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux arm": "bafybeigk5q3g3q3k7m3qy4q3f",
            "windows x86_64": "bafkreidaqcd7q6ot464azswgvflr6ibemh2ty7e745pegccyiwetelg4kq",
            "windows x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd arm": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd arm": "bafybeigk5q3g3q3k7m3qy4q3f",
        }
        self.ipfs_cluster_ctl_dists = {
            "macos arm64": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_darwin-arm64.tar.gz",
            "macos x86_64": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_darwin-amd64.tar.gz",
            "linux arm64": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_linux-arm64.tar.gz",
            "linux x86_64": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_linux-amd64.tar.gz",
            "linux x86": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_linux-386.tar.gz",
            "linux arm": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_linux-arm.tar.gz",
            "windows x86_64": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_windows-amd64.zip",
            "windows x86": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_windows-386.zip",
            "freebsd x86_64": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_freebsd-amd64.tar.gz",
            "freebsd x86": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_freebsd-386.tar.gz",
            "freebsd arm": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_freebsd-arm.tar.gz",
            "openbsd x86_64": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_openbsd-amd64.tar.gz",
            "openbsd x86": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_openbsd-386.tar.gz",
            "openbsd arm": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_openbsd-arm.tar.gz",
        }
        self.ipfs_cluster_ctl_dists_cids = {
            "macos arm64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "macos x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux arm64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux arm": "bafybeigk5q3g3q3k7m3qy4q3f",
            "windows x86_64": "bafkreic6tqlyynnsigedxf7t56w5srxs4bgmxguozykgh5brlv7k5o2coa",
            "windows x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd arm": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd arm": "bafybeigk5q3g3q3k7m3qy4q3f",
        }

        # Set up bin_path and tmp_path
        self.bin_path = os.path.join(self.this_dir, "bin")
        self.tmp_path = tempfile.mkdtemp()

        self.ipfs_cluster_follow_dists = {
            "macos arm64": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_darwin-amd64.tar.gz",
            "macos x86_64": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_darwin-amd64.tar.gz",
            "linux arm64": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_linux-arm64.tar.gz",
            "linux x86_64": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_linux-amd64.tar.gz",
            "linux x86": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_linux-386.tar.gz",
            "linux arm": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_linux-arm.tar.gz",
            "windows x86_64": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_windows-amd64.zip",
            "windows x86": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_windows-386.zip",
            "freebsd x86_64": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_freebsd-amd64.tar.gz",
            "freebsd x86": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_freebsd-386.tar.gz",
            "freebsd arm": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_freebsd-arm.tar.gz",
            "openbsd x86_64": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_openbsd-amd64.tar.gz",
            "openbsd x86": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_openbsd-386.tar.gz",
            "openbsd arm": "https://dist.ipfs.tech/ipfs-cluster-follow/v1.1.2/ipfs-cluster-follow_v1.1.2_openbsd-arm.tar.gz",
        }
        self.ipfs_cluster_follow_dists_cids = {
            "macos arm64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "macos x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux arm64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux arm": "bafybeigk5q3g3q3k7m3qy4q3f",
            "windows x86_64": "bafkreidaqcd7q6ot464azswgvflr6ibemh2ty7e745pegccyiwetelg4kq",
            "windows x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd arm": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd arm": "bafybeigk5q3g3q3k7m3qy4q3f",
        }
        self.ipfs_cluster_ctl_dists = {
            "macos arm64": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_darwin-arm64.tar.gz",
            "macos x86_64": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_darwin-amd64.tar.gz",
            "linux arm64": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_linux-arm64.tar.gz",
            "linux x86_64": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_linux-amd64.tar.gz",
            "linux x86": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_linux-386.tar.gz",
            "linux arm": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_linux-arm.tar.gz",
            "windows x86_64": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_windows-amd64.zip",
            "windows x86": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_windows-386.zip",
            "freebsd x86_64": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_freebsd-amd64.tar.gz",
            "freebsd x86": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_freebsd-386.tar.gz",
            "freebsd arm": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_freebsd-arm.tar.gz",
            "openbsd x86_64": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_openbsd-amd64.tar.gz",
            "openbsd x86": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_openbsd-386.tar.gz",
            "openbsd arm": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_openbsd-arm.tar.gz",
        }
        self.ipfs_cluster_ctl_dists_cids = {
            "macos arm64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "macos x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux arm64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux arm": "bafybeigk5q3g3q3k7m3qy4q3f",
            "windows x86_64": "bafkreic6tqlyynnsigedxf7t56w5srxs4bgmxguozykgh5brlv7k5o2coa",
            "windows x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd arm": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "openbsd arm": "bafybeigk5q3g3q3k7m3qy4q3f",
        }

    def hardware_detect(self):
        import platform

        architecture = platform.architecture()
        system = platform.system()
        processor = platform.processor()

        results = {"system": system, "processor": processor, "architecture": architecture}
        return results

    def install_tar_cmd(self):
        if platform.system() == "Windows":
            command = "choco install tar -y"
            subprocess.run(command, shell=True, check=True)

    def dist_select(self):
        hardware = self.hardware_detect()
        hardware["architecture"] = " ".join([str(x) for x in hardware["architecture"]])
        aarch = ""
        if "Intel" in hardware["processor"]:
            if "64" in hardware["architecture"]:
                aarch = "x86_64"
            elif "32" in hardware["architecture"]:
                aarch = "x86"
        elif "AMD" in hardware["processor"]:
            if "64" in hardware["architecture"]:
                aarch = "x86_64"
            elif "32" in hardware["architecture"]:
                aarch = "x86"
        elif "Qualcomm" in hardware["processor"]:
            if "64" in hardware["architecture"]:
                aarch = "arm64"
            elif "32" in hardware["architecture"]:
                aarch = "arm"
        elif "Apple" in hardware["processor"]:
            if "64" in hardware["architecture"]:
                aarch = "arm64"
            elif "32" in hardware["architecture"]:
                aarch = "x86"
        elif "ARM" in hardware["processor"]:
            if "64" in hardware["architecture"]:
                aarch = "arm64"
            elif "32" in hardware["architecture"]:
                aarch = "arm"
        else:
            aarch = "x86_64"
            pass
        results = str(hardware["system"]).lower() + " " + aarch
        return results

    def install_ipfs_daemon(self):
        # First check if IPFS is already installed using the corrected detection logic
        if self.ipfs_test_install():
            print("IPFS daemon already installed, skipping download")
            # Return CID of existing binary if possible
            if "bin_path" in dir(self) and self.bin_path is not None:
                command = ""
                restults = ""
                this_path = self.bin_path
                this_path = os.path.join(str(this_path), "ipfs.exe") if platform.system() == "Windows" else os.path.join(str(this_path), "ipfs") if dir(this_path) else os.path.join("~", "ipfs")
                this_path = this_path.replace("\\", "/")
                if os.path.exists(this_path):
                    if platform.system() == "Windows":
                        command = "powershell -Command \"Get-FileHash -Path '" + this_path + "' -Algorithm SHA256 | Select-Object -ExpandProperty Hash\""
                    subprocess.run(command, shell=True, check=True)
                if platform.system() == "Linux" or platform.system() == "Darwin":
                    command = "sha256sum " + this_path + " | awk '{print $1}'"
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode().strip()
                return results  # Return the hash of the existing binary
            else:
                print("IPFS binary not found in expected location, proceeding with download and installation")
        # If IPFS is not installed, proceed with download and installation
        if self.ipfs_test_install() is False:
            print("IPFS daemon not installed, proceeding with download and installation")
            pass
        # If IPFS is not installed, proceed with download and installation
        if self.ipfs_test_install() is None:
            print("IPFS daemon not installed, proceeding with download and installation")
            pass   
        if self.ipfs_test_install() is None or self.ipfs_test_install() is False:        
            # Binary not found, proceed with download and installation
            dist = self.dist_select()
            dist_tar = self.ipfs_dists[dist]
            url = self.ipfs_dists[self.dist_select()]
            if ".tar.gz" in url:
                url_suffix = ".tar.gz"
            else:
                url_suffix = "." + url.split(".")[-1]
            with tempfile.NamedTemporaryFile(
                suffix=url_suffix, dir=self.tmp_path, delete=False
            ) as this_tempfile:
                if platform.system() == "Linux":
                    command = "wget " + url + " -O " + this_tempfile.name
                elif platform.system() == "Windows":
                    drive, path = os.path.splitdrive(this_tempfile.name)
                    temp_path = this_tempfile.name.replace("\\", "/")
                    temp_path = temp_path.split("/")
                    temp_path = "/".join(temp_path)
                    # temp_path = drive + temp_path
                    this_tempfile.close()
                    command = f"powershell -Command \"Invoke-WebRequest -Uri '{url}' -OutFile '{temp_path}'\""
                    command = command.replace("'", "")
                elif platform.system() == "Darwin":
                    command = "curl " + url + " -o " + this_tempfile.name

                results = subprocess.check_output(command, shell=True)
                if url_suffix == ".zip":
                    if platform.system() == "Windows":
                        move_source_path = os.path.join(self.tmp_path, "kubo", "ipfs.exe").replace(
                            "\\", "/"
                        )
                        move_source_path = move_source_path.split("/")
                        move_source_path = "/".join(move_source_path)
                        move_dest_path = os.path.join(self.this_dir, "bin", "ipfs.exe").replace(
                            "\\", "/"
                        )
                        move_dest_path = move_dest_path.split("/")
                        move_dest_path = "/".join(move_dest_path)
                        if os.path.exists(move_source_path):
                            os.remove(move_source_path)
                        command = f'powershell -Command "Expand-Archive -Path {this_tempfile.name} -DestinationPath {os.path.dirname(os.path.dirname(move_source_path))}"'
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                        if os.path.exists(move_dest_path):
                            os.remove(move_dest_path)
                        if os.path.exists(move_source_path):
                            os.rename(move_source_path, move_dest_path)
                        else:
                            print(move_source_path)
                            raise Exception("IPFS binary not found after extraction")
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                    else:
                        command = "unzip " + this_tempfile.name + " -d " + self.tmp_path
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                        command = (
                            "cd "
                            + self.tmp_path
                            + "/kubo && mv ipfs.exe "
                            + self.this_dir
                            + "/bin/ && chmod +x "
                            + self.this_dir
                            + "/bin/ipfs.exe"
                        )
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                else:
                    command = "tar -xvzf " + this_tempfile.name + " -C " + self.tmp_path
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                if platform.system() == "Linux" and os.geteuid() == 0:
                    # command = "cd /tmp/kubo ; sudo bash install.sh"
                    command = "sudo bash " + os.path.join(self.tmp_path, "kubo", "install.sh")
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    command = "ipfs --version"
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    with open(os.path.join(self.this_dir, "ipfs.service"), "r") as file:
                        ipfs_service = file.read()
                    with open("/etc/systemd/system/ipfs.service", "w") as file:
                        file.write(ipfs_service)
                    command = "systemctl enable ipfs"
                    subprocess.call(command, shell=True)
                    pass
                elif platform.system() == "Linux" and os.geteuid() != 0:
                    command = "cd " + self.tmp_path + "/kubo && bash install.sh"
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    command = (
                        "cd "
                        + self.tmp_path
                        + '/kubo && mkdir -p "'
                        + self.this_dir
                        + '/bin/" && mv ipfs "'
                        + self.this_dir
                        + '/bin/" && chmod +x "$'
                        + self.this_dir
                        + '/bin/ipfs"'
                    )
                    results = subprocess.check_output(command, shell=True)
                    pass
                elif platform.system() == "Windows":
                    command = (
                        "move "
                        + os.path.join(self.tmp_path, "kubo", "ipfs.exe")
                        + " "
                        + os.path.join(self.this_dir, "bin", "ipfs.exe")
                    )
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    pass
                else:
                    # NOTE: Clean this up and make better logging or drop the error all together
                    print("You need to be root to write to /etc/systemd/system/ipfs.service")
                    command = f"cd {self.tmp_path}/kubo && mkdir -p \"{self.this_dir}/bin/\" && mv ipfs \"{self.this_dir}/bin/\" && chmod +x \"{self.this_dir}/bin/ipfs\""
                    results = subprocess.check_output(command, shell=True)
                    pass
        bin_path = self.bin_path
        bin_path = os.path.join(str(bin_path), "ipfs.exe") if platform.system() == "Windows" else os.path.join(str(bin_path), "ipfs") if dir(bin_path) else os.path.join("~", "ipfs")
        bin_path = bin_path.replace("\\", "/")
        if platform.system() == "Windows":
            command = os.path.join(self.bin_path, "ipfs.exe") + " --version"
        else:
            command = os.path.join(self.bin_path, "ipfs") + " --version"
        results = subprocess.check_output(command, shell=True)
        results = results.decode()
        if "ipfs" in results:
            if platform.system() == "Windows":
                return self.ipfs_multiformats.get_cid(
                    os.path.join(self.path_string, "ipfs.exe")
                )
            elif platform.system() == "Linux":
                return self.ipfs_multiformats.get_cid(os.path.join(self.path_string, "ipfs"))
        else:
            return False

    def install_ipfs_cluster_follow(self):
        # First check if ipfs-cluster-follow is already installed using the corrected detection logic
        if self.ipfs_cluster_follow_test_install():
            print("IPFS cluster follow already installed, skipping download")
            # Return CID of existing binary if possible
            this_path = self.bin_path
            this_path = os.path.join(str(this_path), "ipfs-cluster-follow.exe") if platform.system() == "Windows" else os.path.join(str(this_path), "ipfs-cluster-follow") if dir(this_path) else os.path.join("~", "ipfs-cluster-follow")
            this_path = this_path.replace("\\", "/")
            if os.path.exists(this_path): 
                if platform.system() == "Windows":
                    command = "powershell -Command \"Get-FileHash -Path '" + this_path + "' -Algorithm SHA256 | Select-Object -ExpandProperty Hash\""
                else:
                    command = "sha256sum " + this_path + " | awk '{print $1}'"
                results = subprocess.check_output(command, shell=True)
                results = results.decode().strip()
                return results
            else:
                print("ipfs-cluster-follow binary not found in expected location, proceeding with download and installation")
        # If ipfs-cluster-follow is not installed, proceed with download and installation
        if self.ipfs_cluster_follow_test_install() is False:
            print("IPFS cluster follow not installed, proceeding with download and installation")  
        if self.ipfs_cluster_follow_test_install() is None:
            print("IPFS cluster follow not installed, proceeding with download and installation")
        if self.ipfs_cluster_follow_test_install() is None or self.ipfs_cluster_follow_test_install() is False:
            print("IPFS cluster follow not installed, proceeding with download and installation")

        # Binary not found, proceed with download and installation
        dist = self.dist_select()
        dist_tar = self.ipfs_cluster_follow_dists[dist]
        url = self.ipfs_cluster_follow_dists[self.dist_select()]
        if ".tar.gz" in url:
            url_suffix = ".tar.gz"
        else:
            url_suffix = "." + url.split(".")[-1]
        with tempfile.NamedTemporaryFile(
            suffix=url_suffix, dir=self.tmp_path, delete=False
        ) as this_tempfile:
                if platform.system() == "Linux":
                    command = "wget " + url + " -O " + this_tempfile.name
                elif platform.system() == "Windows":
                    _, _ = os.path.splitdrive(this_tempfile.name)  # Removed unused variables
                    temp_path = this_tempfile.name.replace("\\", "/")
                    temp_path = temp_path.split("/")
                    temp_path = "/".join(temp_path)
                    # temp_path = drive + temp_path
                    this_tempfile.close()
                    command = f"powershell -Command \"Invoke-WebRequest -Uri '{url}' -OutFile '{temp_path}'\""
                    command = command.replace("'", "")
                elif platform.system() == "Darwin":
                    command = "curl " + url + " -o " + this_tempfile.name

                results = subprocess.check_output(command, shell=True)
                if url_suffix == ".zip":
                    if platform.system() == "Windows":
                        move_source_path = os.path.join(
                            self.tmp_path, "ipfs-cluster-follow", "ipfs-cluster-follow.exe"
                        ).replace("\\", "/")
                        move_source_path = move_source_path.split("/")
                        move_source_path = "/".join(move_source_path)
                        move_dest_path = os.path.join(
                            self.this_dir, "bin", "ipfs-cluster-follow.exe"
                        ).replace("\\", "/")
                        move_dest_path = move_dest_path.split("/")
                        move_dest_path = "/".join(move_dest_path)
                        if os.path.exists(move_source_path):
                            os.remove(move_source_path)
                        command = f'powershell -Command "Expand-Archive -Path {this_tempfile.name} -DestinationPath {os.path.dirname(os.path.dirname(move_source_path))}"'
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                        if os.path.exists(move_dest_path):
                            os.remove(move_dest_path)
                        if os.path.exists(move_source_path):
                            os.rename(move_source_path, move_dest_path)
                        else:
                            print(move_source_path)
                            raise Exception("Error moving ipfs.exe, source path does not exist")
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                    else:
                        command = f"unzip {this_tempfile.name} -d {self.tmp_path} && cd {self.tmp_path}/ipfs-cluster-follow && mv ipfs-cluster-follow.exe {self.this_dir}/bin/ && chmod +x {self.this_dir}/bin/ipfs-cluster-follow.exe"
                        results = subprocess.check_output(command, shell=True).decode()
                else:
                    command = "tar -xvzf " + this_tempfile.name + " -C " + self.tmp_path
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                if platform.system() == "Linux" and os.geteuid() == 0:
                    # command = "cd /tmp/kubo ; sudo bash install.sh"
                    command = "sudo bash " + os.path.join(self.tmp_path, "ipfs-cluster-follow", "install.sh")
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    command = "ipfs-cluster-follow --version"
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    with open(
                        os.path.join(self.this_dir, "ipfs-cluster-follow.service"), "r"
                    ) as file:
                        ipfs_service = file.read()
                    with open("/etc/systemd/system/ipfs-cluster-follow.service", "w") as file:
                        file.write(ipfs_service)
                    command = "systemctl enable ipfs-cluster-follow"
                    subprocess.call(command, shell=True)
                    pass
                elif platform.system() == "Linux" and os.geteuid() != 0:
                    command = "cd " + self.tmp_path + "/ipfs-cluster-follow && bash install.sh"
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    command = str("cd " + self.tmp_path + '/ipfs-cluster-follow && mkdir -p "' + self.this_dir + '/bin/" && mv ipfs-cluster-follow "' + self.this_dir + '/bin/" && chmod +x "$' + self.this_dir + '/bin/ipfs-cluster-follow"')
                    results = subprocess.check_output(command, shell=True)
                    pass
                elif platform.system() == "Windows":
                    command = (
                        "move "
                        + os.path.join(self.tmp_path, "ipfs-cluster-follow", "ipfs-cluster-follow.exe")
                        + " "
                        + os.path.join(self.this_dir, "bin", "ipfs-cluster-follow.exe")
                    )
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    pass
                else:
                    print("You need to be root to write to /etc/systemd/system/ipfs-cluster-follow.service")
                    command = f"cd {self.tmp_path}/ipfs-cluster-follow && mkdir -p \"{self.this_dir}/bin/\" && mv ipfs \"{self.this_dir}/bin/\" && chmod +x \"{self.this_dir}/bin/ipfs-cluster-follow\""
                    results = subprocess.check_output(command, shell=True)
                    pass
        bin_path = self.bin_path
        bin_path = os.path.join(str(bin_path), "ipfs-cluster-follow.exe") if platform.system() == "Windows" else os.path.join(str(bin_path), "ipfs-cluster-follow") if dir(bin_path) else os.path.join("~", "ipfs-cluster-follow")
        bin_path = bin_path.replace("\\", "/")
        if platform.system() == "Windows":
            command = os.path.join(self.bin_path, "ipfs-cluster-follow.exe") + " --version"
        else:
            command = os.path.join(self.bin_path, "ipfs-cluster-follow") + "    --version"
        results = subprocess.check_output(command, shell=True).decode()
        if "ipfs" in results:
            return self.ipfs_multiformats.get_cid(
                os.path.join(self.bin_path, "ipfs-cluster-follow.exe" if platform.system    () == "Windows" else "ipfs-cluster-follow")
            )
        else:
            return False

    def install_ipfs_cluster_ctl(self):
        # First check if ipfs-cluster-ctl is already installed using the corrected detection logic
        if self.ipfs_cluster_ctl_test_install():
            print("IPFS cluster ctl already installed, skipping download")
            # Return CID of existing binary if possible
            if platform.system() == "Windows" and os.path.exists(os.path.join(self.bin_path, "ipfs-cluster-ctl.exe")):
                return self.ipfs_multiformats.get_cid(os.path.join(self.bin_path, "ipfs-cluster-ctl.exe"))
            elif os.path.exists(os.path.join(self.bin_path, "ipfs-cluster-ctl")):
                return self.ipfs_multiformats.get_cid(os.path.join(self.bin_path, "ipfs-cluster-ctl"))
            else:
                return True  # Binary exists in PATH but not in our bin directory
                
        # Binary not found, proceed with download and installation

        dist = self.dist_select()
        dist_tar = self.ipfs_cluster_ctl_dists[dist]
        if os.path.exists(os.path.join(self.bin_path, "ipfs-cluster-ctl.exe")):
            return self.ipfs_multiformats.get_cid(
                os.path.join(self.bin_path, "ipfs-cluster-ctl.exe")
            )
        else:
            detect = False

        if detect == False:
            url = self.ipfs_cluster_ctl_dists[self.dist_select()]
            if ".tar.gz" in url:
                url_suffix = ".tar.gz"
            else:
                url_suffix = "." + url.split(".")[-1]
            with tempfile.NamedTemporaryFile(
                suffix=url_suffix, dir=self.tmp_path, delete=False
            ) as this_tempfile:
                if platform.system() == "Linux":
                    command = "wget " + url + " -O " + this_tempfile.name
                elif platform.system() == "Windows":
                    drive, path = os.path.splitdrive(this_tempfile.name)
                    temp_path = this_tempfile.name.replace("\\", "/")
                    temp_path = temp_path.split("/")
                    temp_path = "/".join(temp_path)
                    # temp_path = drive + temp_path
                    this_tempfile.close()
                    command = f"powershell -Command \"Invoke-WebRequest -Uri '{url}' -OutFile '{temp_path}'\""
                    command = command.replace("'", "")
                elif platform.system() == "Darwin":
                    command = "curl " + url + " -o " + this_tempfile.name

                results = subprocess.check_output(command, shell=True)
                if url_suffix == ".zip":
                    if platform.system() == "Windows":
                        move_source_path = os.path.join(
                            self.tmp_path, "ipfs-cluster-ctl", "ipfs-cluster-ctl.exe"
                        ).replace("\\", "/")
                        move_source_path = move_source_path.replace("\\", "/")
                        move_source_path = move_source_path.split("/")
                        move_source_path = "/".join(move_source_path)
                        # move_source_path = os.path.normpath(move_source_path)
                        move_dest_path = os.path.join(
                            self.this_dir, "bin", "ipfs-cluster-ctl.exe"
                        ).replace("\\", "/")
                        move_dest_path = move_dest_path.replace("\\", "/")
                        move_dest_path = move_dest_path.split("/")
                        move_dest_path = "/".join(move_dest_path)
                        # move_dest_path = os.path.normpath(move_dest_path)
                        parent_source_path = os.path.dirname(move_source_path)
                        if os.path.exists(parent_source_path):
                            if os.path.isdir(parent_source_path):
                                shutil.rmtree(parent_source_path)
                            else:
                                os.remove(parent_source_path)
                        command = f'powershell -Command "Expand-Archive -Path {this_tempfile.name} -DestinationPath {os.path.dirname(os.path.dirname(move_source_path))} -Force"'
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                        if os.path.exists(move_dest_path):
                            os.remove(move_dest_path)
                        if os.path.exists(move_source_path):
                            os.rename(move_source_path, move_dest_path)
                        else:
                            print(move_source_path)
                            raise ("Error moving ipfs-cluster-ctl.exe, source path does not exist")
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                    else:
                        command = "unzip " + this_tempfile.name + " -d " + self.tmp_path
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                        command = (
                            "cd "
                            + self.tmp_path
                            + "/ipfs-cluster-ctl && mv ipfs-cluster-ctl.exe "
                            + self.this_dir
                            + "/bin/ && chmod +x "
                            + self.this_dir
                            + "/bin/ipfs-cluster-ctl.exe"
                        )
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                else:
                    command = "tar -xvzf " + this_tempfile.name + " -C " + self.tmp_path
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                if platform.system() == "Linux" and os.geteuid() == 0:
                    # command = "cd /tmp/kubo ; sudo bash install.sh"
                    command = "sudo bash " + os.path.join(
                        self.tmp_path, "ipfs-cluster-ctl", "install.sh"
                    )
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    command = "ipfs-cluster-ctl --version"
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    with open(
                        os.path.join(self.this_dir, "ipfs-cluster-ctl.service"), "r"
                    ) as file:
                        ipfs_service = file.read()
                    with open("/etc/systemd/system/ipfs-cluster-ctl.service", "w") as file:
                        file.write(ipfs_service)
                    command = "systemctl enable ipfs-cluster-ctl"
                    subprocess.call(command, shell=True)
                    pass
                elif platform.system() == "Linux" and os.geteuid() != 0:
                    command = "cd " + self.tmp_path + "/ipfs-cluster-ctl && bash install.sh"
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    command = (
                        "cd "
                        + self.tmp_path
                        + '/ipfs-cluster-ctl && mkdir -p "'
                        + self.this_dir
                        + '/bin/" && mv ipfs-cluster-ctl "'
                        + self.this_dir
                        + '/bin/" && chmod +x "$'
                        + self.this_dir
                        + '/bin/ipfs-cluster-ctl"'
                    )
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    
        # Return version check result
        if platform.system() == "Windows":
            command = os.path.join(self.bin_path, "ipfs-cluster-ctl.exe") + " --version"
        else:
            command = os.path.join(self.bin_path, "ipfs-cluster-ctl") + " --version"
        results = subprocess.check_output(command, shell=True).decode()
        if "ipfs-cluster-ctl" in results:
            if platform.system() == "Windows":
                return self.ipfs_multiformats.get_cid(
                    os.path.join(self.bin_path, "ipfs-cluster-ctl.exe")
                )
            else:
                return self.ipfs_multiformats.get_cid(
                    os.path.join(self.bin_path, "ipfs-cluster-ctl")
                )
        else:
            return False

    def ipfs_test_install(self, method="path"):
        """Test if IPFS is installed."""
        try:
            if platform.system() == "Windows":
                command = os.path.join(self.bin_path, "ipfs.exe") + " --version"
            else:
                command = os.path.join(self.bin_path, "ipfs") + " --version"
            result = subprocess.check_output(command, shell=True)
            return "ipfs" in result.decode()
        except:
            return False

    def ipfs_cluster_follow_test_install(self):
        """Test if IPFS cluster follow is installed."""
        try:
            if platform.system() == "Windows":
                command = os.path.join(self.bin_path, "ipfs-cluster-follow.exe") + " --version"
            else:
                command = os.path.join(self.bin_path, "ipfs-cluster-follow") + " --version"
            result = subprocess.check_output(command, shell=True)
            return "ipfs-cluster-follow" in result.decode()
        except:
            return False

    def ipfs_cluster_ctl_test_install(self):
        """Test if IPFS cluster ctl is installed."""
        try:
            if platform.system() == "Windows":
                command = os.path.join(self.bin_path, "ipfs-cluster-ctl.exe") + " --version"
            else:
                command = os.path.join(self.bin_path, "ipfs-cluster-ctl") + " --version"
            result = subprocess.check_output(command, shell=True)
            return "ipfs-cluster-ctl" in result.decode()
        except:
            return False

    def config_ipfs(self, **kwargs):
        """Configure IPFS."""
        results = {}
        cluster_name = None
        secret = None
        disk_stats = None
        ipfs_path = None
        ipfs_cmd = None
        if platform.system() == "Windows":
            if self.ipfs_path:
                ipfs_path = self.ipfs_path.replace("\\", "/")
            ipfs_cmd = os.path.join(self.bin_path, "ipfs.exe").replace("\\", "/")
        if "cluster_name" in list(kwargs.keys()):
            cluster_name = kwargs["cluster_name"]
            self.cluster_name = cluster_name
        elif "cluster_name" in list(self.__dict__.keys()):
            cluster_name = self.cluster_name

        if "disk_stats" in list(kwargs.keys()):
            disk_stats = kwargs["disk_stats"]
            self.disk_stats = disk_stats
        elif "disk_stats" in list(self.__dict__.keys()):
            disk_stats = self.disk_stats

        if "ipfs_path" in list(kwargs.keys()):
            ipfs_path = kwargs["ipfs_path"]
            self.ipfs_path = ipfs_path
        elif "ipfs_path" in list(self.__dict__.keys()):
            ipfs_path = self.ipfs_path

        if "secret" in list(kwargs.keys()):
            secret = kwargs["secret"]
            self.secret = secret
        elif "secret" in list(self.__dict__.keys()):
            secret = self.secret

        if disk_stats is None:
            # Initialize with default disk stats if not provided
            if hasattr(self, 'disk_stats'):
                disk_stats = self.disk_stats
            else:
                disk_stats = {"disk_avail": 100 * 1024 * 1024 * 1024}  # Default 100GB
        if ipfs_path is None:
            ipfs_path = self.ipfs_path
        if cluster_name is None:
            cluster_name = "default-cluster"
        if secret is None:
            secret = binascii.hexlify(random.randbytes(32)).decode()

        if "this_dir" in list(self.__dict__.keys()):
            this_dir = self.this_dir
        else:
            this_dir = os.path.dirname(os.path.realpath(__file__))
        home_dir = os.path.expanduser("~")
        identity = None
        config = None
        peer_id = None
        run_daemon = None
        public_key = None
        ipfs_daemon = None
        if ipfs_path:
            os.makedirs(ipfs_path, exist_ok=True)
        else:
            return {"error": "ipfs_path is required"}
        
        try:
            # Prepare environment for subprocess calls
            cmd_env = os.environ.copy()
            cmd_env["IPFS_PATH"] = str(ipfs_path)
            cmd_env["PATH"] = str(self.path) if isinstance(self.path, str) else ":".join(self.path)  # Use the modified path

            # Determine the correct ipfs command path
            ipfs_cmd_path = (
                os.path.join(self.bin_path, "ipfs.exe")
                if platform.system() == "Windows"
                else os.path.join(self.bin_path, "ipfs")
            )

            # Ensure the command path exists and is executable
            if not os.path.isfile(ipfs_cmd_path):
                print(f"IPFS executable not found at: {ipfs_cmd_path}")
                return {"error": f"IPFS executable not found at: {ipfs_cmd_path}"}
            
            if platform.system() != "Windows" and not os.access(ipfs_cmd_path, os.X_OK):
                # Attempt to make it executable
                try:
                    os.chmod(ipfs_cmd_path, 0o755)
                    print(f"Made {ipfs_cmd_path} executable.")
                except Exception as chmod_err:
                    print(f"IPFS executable at {ipfs_cmd_path} is not executable: {chmod_err}")
                    return {"error": f"IPFS executable permission error: {chmod_err}"}

            ipfs_init_command = [ipfs_cmd_path, "init", "--profile=badgerds"]

            try:
                print(f"Running command: {' '.join(ipfs_init_command)}")
                ipfs_init_results = subprocess.check_output(
                    ipfs_init_command, shell=False, env=cmd_env
                )
                ipfs_init_results = ipfs_init_results.decode().strip()
                print(f"IPFS init result: {ipfs_init_results}")
            except subprocess.CalledProcessError as e:
                ipfs_init_results = e.output.decode() if e.output else str(e)
                print(f"IPFS init failed: {e}")
                # If init fails due to existing repo, try to proceed with config
                if "already initialized" not in ipfs_init_results:
                    return {"error": f"IPFS init failed: {e}"}
                else:
                    print("Repository already initialized, proceeding with configuration.")

            peer_id_command = [ipfs_cmd_path, "id"]
            print(f"Running command: {' '.join(peer_id_command)}")
            peer_id_results = subprocess.check_output(peer_id_command, shell=False, env=cmd_env)
            peer_id_results = peer_id_results.decode()
            peer_id = json.loads(peer_id_results)
            print(f"IPFS ID result: {peer_id}")

            results = {
                "config": "configured", 
                "identity": peer_id.get("ID", "unknown"), 
                "public_key": peer_id.get("PublicKey", "unknown"),
                "ipfs_path": ipfs_path,
                "cluster_name": cluster_name
            }
            
        except Exception as e:
            print(f"Error configuring IPFS: {e}")
            results = {"error": str(e)}
            
        return results

    def config_ipfs_cluster_follow(self, **kwargs):
        """Configure IPFS cluster follow."""
        results = {}
        cluster_name = None
        secret = None
        disk_stats = None
        ipfs_path = None

        if "cluster_name" in list(kwargs.keys()):
            cluster_name = kwargs["cluster_name"]
            self.cluster_name = cluster_name
        elif "cluster_name" in list(self.__dict__.keys()):
            cluster_name = self.cluster_name

        if "disk_stats" in list(kwargs.keys()):
            disk_stats = kwargs["disk_stats"]
            self.disk_stats = disk_stats
        elif "disk_stats" in list(self.__dict__.keys()):
            disk_stats = self.disk_stats

        if "ipfs_path" in list(kwargs.keys()):
            ipfs_path = kwargs["ipfs_path"]
            self.ipfs_path = ipfs_path
        elif "ipfs_path" in list(self.__dict__.keys()):
            ipfs_path = self.ipfs_path

        if "secret" in list(kwargs.keys()):
            secret = kwargs["secret"]
            self.secret = secret
        elif "secret" in list(self.__dict__.keys()):
            secret = self.secret

        if disk_stats is None:
            disk_stats = {"disk_avail": 100 * 1024 * 1024 * 1024}  # Default 100GB
        if ipfs_path is None:
            ipfs_path = self.ipfs_path
        if cluster_name is None:
            cluster_name = "default-cluster"
        if secret is None:
            secret = binascii.hexlify(random.randbytes(32)).decode()

        if "this_dir" in list(self.__dict__.keys()):
            this_dir = self.this_dir
        else:
            this_dir = os.path.dirname(os.path.realpath(__file__))

        home_dir = os.path.expanduser("~")
        follow_path = None
        worker_id = random.randbytes(32)
        worker_id = "worker-" + binascii.hexlify(worker_id).decode()
        
        if platform.system() == "Linux" and os.geteuid() == 0:
            follow_path = os.path.join("/root", ".ipfs-cluster-follow", cluster_name) + "/"
        elif platform.system() == "Linux" and os.geteuid() != 0:
            follow_path = os.path.join(
                os.path.expanduser("~"), ".ipfs-cluster-follow", cluster_name
            )
        elif platform.system() == "Windows":
            follow_path = os.path.join(
                os.path.expanduser("~"), ".ipfs-cluster-follow", cluster_name
            )
        
        if cluster_name is not None and ipfs_path is not None and disk_stats is not None:
            try:
                if os.path.exists(follow_path):
                    if platform.system() == "Linux":
                        rm_command = "rm -rf " + follow_path
                    elif platform.system() == "Windows":
                        rm_command = "rmdir /S /Q " + follow_path
                    elif platform.system() == "Darwin":
                        rm_command = "rm -rf " + follow_path
                    rm_results = subprocess.check_output(rm_command, shell=True)
                    rm_results = rm_results.decode()
                
                if platform.system() == "Linux":
                    follow_init_cmd = (
                        self.path_string
                        + " IPFS_PATH="
                        + ipfs_path
                        + " ipfs-cluster-follow "
                        + cluster_name
                        + " init "
                        + ipfs_path
                    )
                elif platform.system() == "Windows":
                    follow_init_cmd = (
                        " set IPFS_PATH="
                        + ipfs_path
                        + " &&  "
                        + os.path.join(self.bin_path, "ipfs-cluster-follow.exe")
                        + " "
                        + cluster_name
                        + " init "
                        + ipfs_path
                    )
                    follow_init_cmd = follow_init_cmd.replace("\\", "/")
                
                # Execute follow init command
                if follow_init_cmd:
                    follow_init_cmd_results = subprocess.check_output(follow_init_cmd, shell=True)
                    follow_init_cmd_results = follow_init_cmd_results.decode()
                    results["follow_init"] = follow_init_cmd_results
                    results["worker_id"] = worker_id
                    results["cluster_name"] = cluster_name
                    results["follow_path"] = follow_path
                
            except Exception as e:
                results["error"] = str(e)
                
        return results

    def config_ipfs_cluster_ctl(self, **kwargs):
        """Configure IPFS cluster ctl."""
        results = {}
        cluster_name = None
        secret = None
        disk_stats = None
        ipfs_path = None

        if "cluster_name" in list(kwargs.keys()):
            cluster_name = kwargs["cluster_name"]
            self.cluster_name = cluster_name
        elif "cluster_name" in list(self.__dict__.keys()):
            cluster_name = self.cluster_name

        if "disk_stats" in list(kwargs.keys()):
            disk_stats = kwargs["disk_stats"]
            self.disk_stats = disk_stats
        elif "disk_stats" in list(self.__dict__.keys()):
            disk_stats = self.disk_stats

        if "ipfs_path" in list(kwargs.keys()):
            ipfs_path = kwargs["ipfs_path"]
            self.ipfs_path = ipfs_path
        elif "ipfs_path" in list(self.__dict__.keys()):
            ipfs_path = self.ipfs_path

        if "secret" in list(kwargs.keys()):
            secret = kwargs["secret"]
            self.secret = secret
        elif "secret" in list(self.__dict__.keys()):
            secret = self.secret

        if disk_stats is None:
            disk_stats = {"disk_avail": 100 * 1024 * 1024 * 1024}  # Default 100GB
        if ipfs_path is None:
            ipfs_path = self.ipfs_path
        if cluster_name is None:
            cluster_name = "default-cluster"
        if secret is None:
            secret = binascii.hexlify(random.randbytes(32)).decode()

        run_cluster_ctl = None

        try:
            if platform.system() == "Linux":
                run_cluster_ctl_cmd = self.path_string + " ipfs-cluster-ctl --version"
            elif platform.system() == "Windows":
                run_cluster_ctl_cmd = (
                    os.path.join(self.bin_path, "ipfs-cluster-ctl.exe") + " --version"
                )
            elif platform.system() == "Darwin":
                run_cluster_ctl_cmd = self.path_string + " ipfs-cluster-ctl --version"
            else:
                return {"error": "Unsupported platform"}
                
            run_cluster_ctl = subprocess.check_output(run_cluster_ctl_cmd, shell=True)
            run_cluster_ctl = run_cluster_ctl.decode()
            results["run_cluster_ctl"] = run_cluster_ctl
            results["cluster_name"] = cluster_name
            results["ipfs_path"] = ipfs_path
            
        except Exception as e:
            results["error"] = str(e)
            return results

        return results

    def config_ipfs_cluster_service(self, **kwargs):
        """Configure IPFS cluster service."""
        cluster_name = None
        secret = None
        disk_stats = None
        ipfs_path = None
        
        if "secret" in list(kwargs.keys()):
            secret = kwargs["secret"]
        elif "secret" in list(self.__dict__.keys()):
            secret = self.secret

        if "cluster_name" in list(kwargs.keys()):
            cluster_name = kwargs["cluster_name"]
            self.cluster_name = cluster_name
        elif "cluster_name" in list(self.__dict__.keys()):
            cluster_name = self.cluster_name

        if "disk_stats" in list(kwargs.keys()):
            disk_stats = kwargs["disk_stats"]
            self.disk_stats = disk_stats
        elif "disk_stats" in list(self.__dict__.keys()):
            disk_stats = self.disk_stats

        if "ipfs_path" in list(kwargs.keys()):
            ipfs_path = kwargs["ipfs_path"]
            self.ipfs_path = ipfs_path
        elif "ipfs_path" in list(self.__dict__.keys()):
            ipfs_path = self.ipfs_path

        if disk_stats is None:
            disk_stats = {"disk_avail": 100 * 1024 * 1024 * 1024}  # Default 100GB
        if ipfs_path is None:
            ipfs_path = self.ipfs_path
        if cluster_name is None:
            cluster_name = "default-cluster"
        if secret is None:
            secret = binascii.hexlify(random.randbytes(32)).decode()

        if "this_dir" in list(self.__dict__.keys()):
            this_dir = self.this_dir
        else:
            this_dir = os.path.dirname(os.path.realpath(__file__))

        home_dir = os.path.expanduser("~")
        service_path = ""
        results = {}
        
        try:
            if platform.system() == "Linux" and os.geteuid() == 0:
                service_path = os.path.join("/root", ".ipfs-cluster")
            else:
                service_path = os.path.join(self.ipfs_path) if self.ipfs_path else os.path.join(home_dir, ".ipfs-cluster")
                
            if not os.path.exists(service_path):
                os.makedirs(service_path)
                
            if cluster_name is not None and ipfs_path is not None and disk_stats is not None:
                # Prepare environment for subprocess calls
                cmd_env = os.environ.copy()
                cmd_env["IPFS_PATH"] = str(self.ipfs_path) if self.ipfs_path else str(ipfs_path)
                cmd_env["PATH"] = str(self.path) if isinstance(self.path, str) else ":".join(self.path)

                # Determine the correct ipfs command path
                ipfs_cmd_path = (
                    os.path.join(self.bin_path, "ipfs.exe")
                    if platform.system() == "Windows"
                    else os.path.join(self.bin_path, "ipfs")
                )

                # Ensure the command path exists and is executable
                if not os.path.isfile(ipfs_cmd_path):
                    results["error"] = f"IPFS executable not found at: {ipfs_cmd_path}"
                    return results
                    
                if platform.system() != "Windows" and not os.access(ipfs_cmd_path, os.X_OK):
                    try:
                        os.chmod(ipfs_cmd_path, 0o755)
                        print(f"Made {ipfs_cmd_path} executable.")
                    except Exception as chmod_err:
                        results["error"] = f"IPFS executable permission error: {chmod_err}"
                        return results

                ipfs_init_command = [ipfs_cmd_path, "init", "--profile=badgerds"]
                try:
                    print(f"Running command: {' '.join(ipfs_init_command)}")
                    process = subprocess.run(
                        ipfs_init_command,
                        shell=False,
                        env=cmd_env,
                        capture_output=True,
                        text=True,
                    )
                    ipfs_init_results = process.stdout.strip() + process.stderr.strip()
                    print(f"IPFS init result: {ipfs_init_results}")
                    
                    if process.returncode != 0 and "already initialized" not in ipfs_init_results:
                        results["error"] = f"IPFS init failed: {ipfs_init_results}"
                        return results
                    
                    results["cluster_service"] = "configured"
                    results["service_path"] = service_path
                    results["cluster_name"] = cluster_name
                    results["secret"] = secret
                    
                except Exception as e:
                    results["error"] = str(e)
                    
        except Exception as e:
            results["error"] = str(e)
            
        return results

    def install_ipfs_cluster_service(self):
        """Install IPFS cluster service."""
        # Simplified cluster service installation
        dist = self.dist_select()
        url = self.ipfs_cluster_service_dists[self.dist_select()]
        
        if ".tar.gz" in url:
            url_suffix = ".tar.gz"
        else:
            url_suffix = "." + url.split(".")[-1]
            
        with tempfile.NamedTemporaryFile(
            suffix=url_suffix, dir=self.tmp_path, delete=False
        ) as this_tempfile:
            if platform.system() == "Linux":
                command = "wget " + url + " -O " + this_tempfile.name
            elif platform.system() == "Windows":
                temp_path = this_tempfile.name.replace("\\", "/")
                this_tempfile.close()
                command = f"powershell -Command \"Invoke-WebRequest -Uri '{url}' -OutFile '{temp_path}'\""
                command = command.replace("'", "")
            elif platform.system() == "Darwin":
                command = "curl " + url + " -o " + this_tempfile.name

            results = subprocess.check_output(command, shell=True)
            
            if url_suffix == ".zip":
                command = f'powershell -Command "Expand-Archive -Path {this_tempfile.name} -DestinationPath {self.tmp_path} -Force"'
                results = subprocess.check_output(command, shell=True)
            else:
                command = "tar -xvzf " + this_tempfile.name + " -C " + self.tmp_path
                results = subprocess.check_output(command, shell=True)

        return True