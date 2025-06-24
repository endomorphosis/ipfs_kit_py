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
from .ipfs_multiformats import ipfs_multiformats_py
from .test_fio import test_fio


class install_ipfs:
    def __init__(self, resources=None, metadata=None):
        self.resources = resources
        self.metadata = metadata
        if self.resources is None:
            self.resources = {}
        if self.metadata is None:
            self.metadata = {}
        self.install_ipfs_daemon = self.install_ipfs_daemon
        self.install_ipfs_cluster_follow = self.install_ipfs_cluster_follow
        self.install_ipfs_cluster_ctl = self.install_ipfs_cluster_ctl
        self.install_ipfs_cluster_service = self.install_ipfs_cluster_service
        self.env_path = os.environ.get("PATH", "")
        if metadata and "path" in list(metadata.keys()):
            self.path = metadata["path"]
        else:
            self.path = self.env_path
        if "ipfs_multiformats" not in list(dir(self)):
            if "ipfs_multiformats" in list(self.resources.keys()):
                self.ipfs_multiformats = resources["ipfs_multiformats"]
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
            "macos arm64": "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.1.2/ipfs-cluster-ctl_v1.1.2_darwin-amd64.tar.gz",
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

        self.ipfs_ipget_dists = {
            "macos arm64": "https://dist.ipfs.tech/ipget/v0.11.0/ipget_v0.11.0_darwin-amd64.tar.gz",
            "macos x86_64": "https://dist.ipfs.tech/ipget/v0.11.0/ipget_v0.11.0_darwin-amd64.tar.gz",
            "linux arm64": "https://dist.ipfs.tech/ipget/v0.11.0/ipget_v0.11.0_linux-arm64.tar.gz",
            "linux x86_64": "https://dist.ipfs.tech/ipget/v0.11.0/ipget_v0.11.0_linux-amd64.tar.gz",
            "linux x86": "https://dist.ipfs.tech/ipget/v0.11.0/ipget_v0.11.0_linux-386.tar.gz",
            "linux arm": "https://dist.ipfs.tech/ipget/v0.11.0/ipget_v0.11.0_linux-arm.tar.gz",
            "windows x86_64": "https://dist.ipfs.tech/ipget/v0.11.0/ipget_v0.11.0_windows-amd64.zip",
            "windows x86": "https://dist.ipfs.tech/ipget/v0.11.0/ipget_v0.11.0_windows-386.zip",
            "freebsd x86_64": "https://dist.ipfs.tech/ipget/v0.11.0/ipget_v0.11.0_freebsd-amd64.tar.gz",
            "freebsd x86": "https://dist.ipfs.tech/ipget/v0.11.0/ipget_v0.11.0_freebsd-386.tar.gz",
            "freebsd arm": "https://dist.ipfs.tech/ipget/v0.11.0/ipget_v0.11.0_freebsd-arm.tar.gz",
        }
        self.ipfs_ipget_dists_cids = {
            "macos arm64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "macos x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux arm64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "linux arm": "bafybeigk5q3g3q3k7m3qy4q3f",
            "windows x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "windows x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd x86_64": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd x86": "bafybeigk5q3g3q3k7m3qy4q3f",
            "freebsd arm": "bafybeigk5q3g3q3k7m3qy4q3f",
        }

        self.config = None
        self.secret = None
        self.role = None
        self.ipfs_path = None
        self.cluster_name = None
        self.cluster_location = None
        self.disk_name = None
        self.disk_stats = {}
        if metadata is not None:
            if self.secret == None:
                self.secret = random.randbytes(32)
                self.secret = binascii.hexlify(self.secret).decode()
                pass

            if "role" in list(metadata.keys()):
                self.role = metadata["role"]
                if self.role not in ["master", "worker", "leecher"]:
                    raise Exception("role is not either master, worker, leecher")
            else:
                self.role = "leecher"
                pass

            if "ipfs_path" in list(metadata.keys()):
                self.ipfs_path = metadata["ipfs_path"]
                if not os.path.exists(self.ipfs_path):
                    os.makedirs(self.ipfs_path)
                    pass
                test_disk = test_fio(None)
                self.disk_name = test_disk.disk_device_name_from_location(self.ipfs_path)
                self.disk_stats = {
                    "disk_size": test_disk.disk_device_total_capacity(self.disk_name),
                    "disk_used": test_disk.disk_device_used_capacity(self.disk_name),
                    "disk_avail": test_disk.disk_device_avail_capacity(self.disk_name),
                    "disk_name": self.disk_name,
                }
                pass
            else:
                if platform.system() == "Windows":
                    self.ipfs_path = os.path.join(
                        os.path.expanduser("~"), "AppData", "Local", "ipfs"
                    )
                    self.ipfs_path = self.ipfs_path.replace("\\", "/")
                    self.ipfs_path = self.ipfs_path.split("/")
                    self.ipfs_path = "/".join(self.ipfs_path)
                elif platform.system() == "Linux" and os.getuid() == 0:
                    self.ipfs_path = "/root/.cache/ipfs"
                elif platform.system() == "Linux" and os.getuid() != 0:
                    self.ipfs_path = os.path.join(os.path.expanduser("~"), ".cache", "ipfs")
                elif platform.system() == "Darwin":
                    self.ipfs_path = os.path.join(os.path.expanduser("~"), "Library", "ipfs")
                if not os.path.exists(self.ipfs_path):
                    os.makedirs(self.ipfs_path)
                    pass
                test_disk = test_fio(resources, metadata)  # Corrected instantiation
                self.disk_name = test_disk.disk_device_name_from_location(self.ipfs_path)
                self.disk_stats = {
                    "disk_size": test_disk.disk_device_total_capacity(self.disk_name),
                    "disk_used": test_disk.disk_device_used_capacity(self.disk_name),
                    "disk_avail": test_disk.disk_device_avail_capacity(self.disk_name),
                    "disk_name": self.disk_name,
                }

            if "cluster_name" in list(metadata.keys()):
                self.cluster_name = metadata["cluster_name"]
                pass

            if "cluster_location" in list(metadata.keys()):
                self.cluster_location = metadata["cluster_location"]
                pass

            if self.role in ["master", "worker", "leecher"] and self.ipfs_path is not None:
                self.ipfs_install_command = self.install_ipfs_daemon
                self.ipfs_config_command = self.config_ipfs
                pass

            if self.role == "worker":
                if self.cluster_name is not None and self.ipfs_path is not None:
                    self.cluster_install = self.install_ipfs_cluster_follow
                    self.cluster_config = self.config_ipfs_cluster_follow
                    pass
                pass

            if self.role == "master":
                if self.cluster_name is not None and self.ipfs_path is not None:
                    self.cluster_name = metadata["cluster_name"]
                    self.cluster_ctl_install = self.install_ipfs_cluster_ctl
                    self.cluster_ctl_config = self.config_ipfs_cluster_ctl
                    self.cluster_service_install = self.install_ipfs_cluster_service
                    self.cluster_service_config = self.config_ipfs_cluster_service
                    pass
                pass

            if "config" in metadata:
                if metadata["config"] is not None:
                    self.config = metadata["config"]

            if "role" in metadata:
                if metadata["role"] is not None:
                    self.role = metadata["role"]
                    if self.role not in ["master", "worker", "leecher"]:
                        raise Exception("role is not either master, worker, leecher")
                    else:
                        self.role = metadata["role"]
                        pass
                else:
                    self.role = "leecher"

            if "ipfs_path" in metadata:
                if metadata["ipfs_path"] is not None:
                    self.ipfs_path = metadata["ipfs_path"]
                    homedir_path = os.path.expanduser("~")

                    # NOTE bug invalid permissions check
                    if os.getuid != 0:
                        if homedir_path in os.path.realpath(self.ipfs_path):
                            if not os.path.exists(os.path.realpath(self.ipfs_path)):
                                os.makedirs(self.ipfs_path)
                    if os.getuid() == 0:
                        if not os.path.exists(self.ipfs_path):
                            os.makedirs(self.ipfs_path)
                            pass
                    test_disk = test_fio(resources, metadata)  # Corrected instantiation
                    self.disk_name = test_disk.disk_device_name_from_location(self.ipfs_path)
                    self.disk_stats = {
                        "disk_size": test_disk.disk_device_total_capacity(self.disk_name),
                        "disk_used": test_disk.disk_device_used_capacity(self.disk_name),
                        "disk_avail": test_disk.disk_device_avail_capacity(self.disk_name),
                        "disk_name": self.disk_name,
                    }
                    pass
                pass
            else:
                pass

            if "cluster_name" in metadata:
                if metadata["cluster_name"] is not None:
                    self.cluster_name = metadata["cluster_name"]
                    pass
                pass
            else:
                self.cluster_name = None

            if "cluster_location" in metadata:
                if metadata["cluster_location"] is not None:
                    self.cluster_location = metadata["cluster_location"]
                    pass
                pass

            if self.role == "leecher" or self.role == "worker" or self.role == "master":
                if self.ipfs_path is not None:
                    self.ipfs_install_command = self.install_ipfs_daemon
                    self.ipfs_config_command = self.config_ipfs
                pass

            if self.role == "worker":
                if self.cluster_name is not None and self.ipfs_path is not None:
                    self.cluster_install = self.install_ipfs_cluster_follow
                    self.cluster_config = self.config_ipfs_cluster_follow
                    pass
                pass

            if self.role == "master":
                if self.cluster_name is not None and self.ipfs_path is not None:
                    self.cluster_name = metadata["cluster_name"]
                    self.cluster_ctl_install = self.install_ipfs_cluster_ctl
                    self.cluster_ctl_config = self.config_ipfs_cluster_ctl
                    self.cluster_service_install = self.install_ipfs_cluster_service
                    self.cluster_service_config = self.config_ipfs_cluster_service
                    pass
        if "cluster_location" not in list(self.__dict__.keys()):
            self.cluster_location = "/ip4/167.99.96.231/tcp/9096/p2p/12D3KooWKw9XCkdfnf8CkAseryCgS3VVoGQ6HUAkY91Qc6Fvn4yv"
            pass
        self.bin_path = os.path.join(self.this_dir, "bin")
        self.bin_path = self.bin_path.replace("\\", "/")
        self.bin_path = self.bin_path.split("/")
        self.bin_path = "/".join(self.bin_path)
        if platform.system() == "Windows":
            self.tmp_path = os.environ.get("TEMP", "/tmp")
        else:
            self.tmp_path = "/tmp"

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
            if platform.system() == "Windows" and os.path.exists(os.path.join(self.bin_path, "ipfs.exe")):
                return self.ipfs_multiformats.get_cid(os.path.join(self.bin_path, "ipfs.exe"))
            elif os.path.exists(os.path.join(self.bin_path, "ipfs")):
                return self.ipfs_multiformats.get_cid(os.path.join(self.bin_path, "ipfs"))
            else:
                return True  # Binary exists in PATH but not in our bin directory
                
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
                            raise ("Error moving ipfs.exe, source path does not exist")
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
            command = os.path.join(self.path_string, "ipfs.exe") + " --version"
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
        else:
            return True

    def install_ipfs_cluster_follow(self):
        # First check if ipfs-cluster-follow is already installed using the corrected detection logic
        if self.ipfs_cluster_follow_test_install():
            print("IPFS cluster follow already installed, skipping download")
            # Return CID of existing binary if possible
            if platform.system() == "Windows" and os.path.exists(os.path.join(self.bin_path, "ipfs-cluster-follow.exe")):
                return self.ipfs_multiformats.get_cid(os.path.join(self.bin_path, "ipfs-cluster-follow.exe"))
            elif os.path.exists(os.path.join(self.bin_path, "ipfs-cluster-follow")):
                return self.ipfs_multiformats.get_cid(os.path.join(self.bin_path, "ipfs-cluster-follow"))
            else:
                return True  # Binary exists in PATH but not in our bin directory
                
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
                            raise ("Error moving ipfs.exe, source path does not exist")
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                    else:
                        command = "unzip " + this_tempfile.name + " -d " + self.tmp_path
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                        command = (
                            "cd "
                            + self.tmp_path
                            + "/ipfs-cluster-follow && mv ipfs-cluster-follow.exe "
                            + self.this_dir
                            + "/bin/ && chmod +x "
                            + self.this_dir
                            + "/bin/ipfs-cluster-follow.exe"
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
                        self.tmp_path, "ipfs-cluster-follow", "install.sh"
                    )
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
                    command = (
                        "cd "
                        + self.tmp_path
                        + '/ipfs-cluster-follow && mkdir -p "'
                        + self.this_dir
                        + '/bin/" && mv ipfs-cluster-follow "'
                        + self.this_dir
                        + '/bin/" && chmod +x "$'
                        + self.this_dir
                        + '/bin/ipfs-cluster-follow"'
                    )
                    results = subprocess.check_output(command, shell=True)
                    pass
                elif platform.system() == "Windows":
                    command = (
                        "move "
                        + os.path.join(
                            self.tmp_path, "ipfs-cluster-follow", "ipfs-cluster-follow.exe"
                        )
                        + " "
                        + os.path.join(self.this_dir, "bin", "ipfs-cluster-follow.exe")
                    )
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    pass
                else:
                    # NOTE: Clean this up and make better logging or drop the error all together
                    print(
                        "You need to be root to write to /etc/systemd/system/ipfs-cluster-follow.service"
                    )
                    command = (
                        "cd "
                        + self.tmp_path
                        + '/ipfs-cluster-follow && mkdir -p "'
                        + self.this_dir
                        + '/bin/" && mv ipfs "'
                        + self.this_dir
                        + '/bin/" && chmod +x "$'
                        + self.this_dir
                        + '/bin/ipfs-cluster-follow"'
                    )
                    results = subprocess.check_output(command, shell=True)
                    pass
            if platform.system() == "windows":
                command = os.path.join(self.bin_path, "ipfs-cluster-follow.exe") + " --version"
            if platform.system() == "linux":
                command = os.path.join(self.bin_path, "ipfs-cluster-follow") + " --version"
            if platform.system() == "darwin":
                command = os.path.join(self.bin_path, "ipfs-cluster-follow") + " --version"
            results = subprocess.check_output(command, shell=True)
            results = results.decode()
            if "ipfs" in results:
                if platform.system() == "Windows":
                    return self.ipfs_multiformats.get_cid(
                        os.path.join(self.bin_path, "ipfs-cluster-follow.exe")
                    )
                elif platform.system() == "Linux":
                    return self.ipfs_multiformats.get_cid(
                        os.path.join(self.bin_path, "ipfs-cluster-follow")
                    )
            else:
                return False
        else:
            return True

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
        detect = False
        results = {}
        dist = self.dist_select()
        dist_tar = self.ipfs_cluster_ctl_dists[dist]
                if os.path.exists(os.path.join(self.bin_path, "ipfs-cluster-ctl.exe")):
                    return self.ipfs_multiformats.get_cid(
                        os.path.join(self.bin_path, "ipfs-cluster-ctl.exe")
                    )
                else:
                    detect = False
            else:
                detect = False
        except Exception as e:
            detect = False
            print(e)
        finally:
            pass
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
                        move_source_path = move_source_path.split("/")
                        move_source_path = "/".join(move_source_path)
                        move_dest_path = os.path.join(
                            self.this_dir, "bin", "ipfs-cluster-ctl.exe"
                        ).replace("\\", "/")
                        move_dest_path = move_dest_path.split("/")
                        move_dest_path = "/".join(move_dest_path)
                        parent_source_path = os.path.dirname(move_source_path)
                        if os.path.exists(parent_source_path):
                            if os.path.isdir(parent_source_path):
                                shutil.rmtree(parent_source_path)
                            else:
                                os.remove(parent_source_path)
                        command = f'powershell -Command "Expand-Archive -Path {this_tempfile.name} -DestinationPath {os.path.dirname(os.path.dirname(move_source_path))} -Force" '
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
                    pass
                elif platform.system() == "Windows":
                    command = (
                        "move "
                        + os.path.join(self.tmp_path, "ipfs-cluster-ctl", "ipfs-cluster-ctl.exe")
                        + " "
                        + os.path.join(self.this_dir, "bin", "ipfs-cluster-ctl.exe")
                    )
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    pass
                else:
                    # NOTE: Clean this up and make better logging or drop the error all together
                    print(
                        "You need to be root to write to /etc/systemd/system/ipfs-cluster-ctl.service"
                    )
                    command = (
                        "cd "
                        + self.tmp_path
                        + '/ipfs-cluster-ctl && mkdir -p "'
                        + self.this_dir
                        + '/bin/" && mv ipfs "'
                        + self.this_dir
                        + '/bin/" && chmod +x "$'
                        + self.this_dir
                        + '/bin/ipfs-cluster-follow"'
                    )
                    results = subprocess.check_output(command, shell=True)
                    pass

            if platform.system() == "Linux" and os.geteuid() == 0:
                command = self.path_string + " ipfs-cluster-ctl --version"
            if platform.system() == "Linux" and os.geteuid() != 0:
                command = self.path_string + " ipfs-cluster-ctl --version"
            if platform.system() == "Windows":
                command = os.path.join(self.bin_path, "ipfs-cluster-ctl") + " --version"
            if platform.system() == "Darwin":
                command = self.path_string + " ipfs-cluster-ctl --version"
            results = subprocess.check_output(command, shell=True)
            results = results.decode()
            if "ipfs-cluster-ctl" in results:
                return self.ipfs_multiformats.get_cid(
                    os.path.join(self.bin_path, "ipfs-cluster-ctl.exe")
                )
            else:
                return False

    def install_ipfs_cluster_service(self):
        install_ipfs_cluster_service_cmd = None
        detect = False
        dist = self.dist_select()
        dist_tar = self.ipfs_cluster_service_dists[dist]
        detect = False
        results = {}
        if platform.system() == "Linux":
            ipfs_detect_cmd = os.path.join(self.bin_path, "ipfs-cluster-follow")
        elif platform.system() == "Windows":
            ipfs_detect_cmd = os.path.join(self.bin_path, "ipfs-cluster-follow.exe")
            ipfs_detect_cmd = ipfs_detect_cmd.replace("\\", "/")
            ipfs_detect_cmd = ipfs_detect_cmd.split("/")
            ipfs_detect_cmd = "/".join(ipfs_detect_cmd)
        elif platform.system() == "Darwin":
            ipfs_detect_cmd = os.path.join(self.bin_path, "ipfs-cluster-follow")
        try:
            ipfs_detect_cmd_results = subprocess.check_output(ipfs_detect_cmd, shell=True)
            ipfs_detect_cmd_results = ipfs_detect_cmd_results.decode()
            if len(ipfs_detect_cmd_results) > 0:
                if os.path.exists(os.path.join(self.bin_path, "ipfs-cluster-follow.exe")):
                    return self.ipfs_multiformats.get_cid(
                        os.path.join(self.bin_path, "ipfs-cluster-follow.exe")
                    )
                else:
                    return False
            else:
                return False
        except Exception as e:
            detect = False
            print(e)
        finally:
            pass
        if detect == False:
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
                            self.tmp_path, "ipfs-cluster-service", "ipfs-cluster-service.exe"
                        ).replace("\\", "/")
                        move_source_path = move_source_path.replace("\\", "/")
                        move_source_path = move_source_path.split("/")
                        move_source_path = "/".join(move_source_path)
                        # move_source_path = os.path.normpath(move_source_path)
                        move_dest_path = os.path.join(
                            self.this_dir, "bin", "ipfs-cluster-service.exe"
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
                        command = f'powershell -Command "Expand-Archive -Path {this_tempfile.name} -DestinationPath {os.path.dirname(os.path.dirname(move_source_path))}"'
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                        if os.path.exists(move_dest_path):
                            os.remove(move_dest_path)
                        if os.path.exists(move_source_path):
                            os.rename(move_source_path, move_dest_path)
                        else:
                            print(move_source_path)
                            raise (
                                "Error moving ipfs-cluster-service.exe, source path does not exist"
                            )
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                    else:
                        command = "unzip " + this_tempfile.name + " -d " + self.tmp_path
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                        command = (
                            "cd "
                            + self.tmp_path
                            + "/ipfs-cluster-service && mv ipfs-cluster-service.exe "
                            + self.this_dir
                            + "/bin/ && chmod +x "
                            + self.this_dir
                            + "/bin/ipfs-cluster-service.exe"
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
                        self.tmp_path, "ipfs-cluster-service", "install.sh"
                    )
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    command = "ipfs-cluster-service --version"
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    with open(
                        os.path.join(self.this_dir, "ipfs_cluster_service.service"), "r"
                    ) as file:
                        ipfs_service = file.read()
                    with open("/etc/systemd/system/ipfs_cluster_service.service", "w") as file:
                        file.write(ipfs_service)
                    command = "systemctl enable ipfs_cluster_service"
                    subprocess.call(command, shell=True)
                    pass
                elif platform.system() == "Linux" and os.geteuid() != 0:
                    command = "cd " + self.tmp_path + "/ipfs-cluster-service && bash install.sh"
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    command = (
                        "cd "
                        + self.tmp_path
                        + '/ipfs-cluster-service && mkdir -p "'
                        + self.this_dir
                        + '/bin/" && mv ipfs-cluster-service "'
                        + self.this_dir
                        + '/bin/" && chmod +x "$'
                        + self.this_dir
                        + '/bin/ipfs-cluster-service"'
                    )
                    results = subprocess.check_output(command, shell=True)
                    pass
                elif platform.system() == "Windows":
                    command = (
                        "move "
                        + os.path.join(
                            self.tmp_path, "ipfs-cluster-service", "ipfs-cluster-service.exe"
                        )
                        + " "
                        + os.path.join(self.this_dir, "bin", "ipfs-cluster-service.exe")
                    )
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    pass
                else:
                    # NOTE: Clean this up and make better logging or drop the error all together
                    print(
                        "You need to be root to write to /etc/systemd/system/ipfs-cluster-follow.service"
                    )
                    command = (
                        "cd "
                        + self.tmp_path
                        + '/ipfs-cluster-follow && mkdir -p "'
                        + self.this_dir
                        + '/bin/" && mv ipfs "'
                        + self.this_dir
                        + '/bin/" && chmod +x "$'
                        + self.this_dir
                        + '/bin/ipfs-cluster-follow"'
                    )
                    results = subprocess.check_output(command, shell=True)
                    pass

    def install_ipget(self):
        install_ipget_cmd = None
        detect = False
        if platform.system() == "Linux":
            detect_ipget_cmd = os.path.join(self.bin_path, "ipget --version")
        elif platform.system() == "Windows":
            detect_ipget_cmd = os.path.join(self.bin_path, "ipget.exe --version")
        try:
            detect_ipget_cmd_results = subprocess.check_output(detect_ipget_cmd, shell=True)
            detect_ipget_cmd_results = detect_ipget_cmd_results.decode()
            if len(detect_ipget_cmd_results) > 0:
                if os.path.exists(os.path.join(self.bin_path, "ipget.exe")):
                    return self.ipfs_multiformats.get_cid(os.path.join(self.bin_path, "ipget.exe"))
                else:
                    detect = False
            else:
                detect = False
        except Exception as e:
            detect = False
            print(e)
        finally:
            pass
        if detect == False:
            url = self.ipfs_ipget_dists[self.dist_select()]
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
                    temp_path = temp_path.split("/")
                    temp_path = "/".join(temp_path)
                    # temp_path = drive + temp_path
                    this_tempfile.close()
                    command = f"powershell -Command \"Invoke-WebRequest -Uri '{url}' -OutFile '{temp_path}'\""
                    command = command.replace("'", "")
                elif platform.system() == "Darwin":
                    command = "curl " + url + " -o " + this_tempfile.name
                results = subprocess.check_output(command, shell=True)
                results = results.decode()
                if url_suffix == ".zip":
                    if platform.system() == "Windows":
                        command = f'powershell -Command "Expand-Archive -Path {this_tempfile.name} -DestinationPath {self.tmp_path}"'
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                        move_source_path = os.path.join(
                            self.tmp_path, "ipget", "ipget.exe"
                        ).replace("\\", "/")
                        move_source_path = move_source_path.split("/")
                        move_source_path = "/".join(move_source_path)
                        move_dest_path = os.path.join(self.this_dir, "bin", "ipget.exe").replace(
                            "\\", "/"
                        )
                        move_dest_path = move_dest_path.split("/")
                        move_dest_path = "/".join(move_dest_path)
                        if os.path.exists(move_dest_path):
                            os.remove(move_dest_path)
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                        os.rename(move_source_path, move_dest_path)
                    else:
                        command = "unzip " + this_tempfile.name + " -d " + self.tmp_path
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                        command = (
                            "cd "
                            + self.tmp_path
                            + "/ipget && mv ipget "
                            + self.this_dir
                            + "/bin/ && chmod +x "
                            + self.this_dir
                            + "/bin/ipget"
                        )
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                else:
                    command = "tar -xvzf " + this_tempfile.name + " -C " + self.tmp_path
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                    # command = "cd /tmp/ipget ; sudo bash install.sh"
                    if platform.system() == "Linux" and os.getegid() == 0:
                        command = "cd sudo bash " + os.path.join(
                            self.tmp_path, "ipget", "install.sh"
                        )
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                        command = "sudo sysctl -w net.core.rmem_max=2500000"
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                        command = "sudo sysctl -w net.core.wmem_max=2500000"
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                    elif platform.system() == "Linux" and os.getegid() != 0:
                        command = (
                            "cd " + os.path.join(self.tmp_path, "ipget") + " && bash install.sh"
                        )
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                    elif platform.system() == "Darwin":
                        command = (
                            "cd " + os.path.join(self.tmp_path, "ipget") + " && bash install.sh"
                        )
                        results = subprocess.check_output(command, shell=True)
                        results = results.decode()
                if platform.system() == "Linux":
                    command = self.bin_path + "/ipget --version"
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                elif platform.system() == "Windows":
                    command = self.bin_path + "\\ipget.exe --version"
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()
                elif platform.system() == "Darwin":
                    command = self.bin_path + "/ipget --version"
                    results = subprocess.check_output(command, shell=True)
                    results = results.decode()

                if "ipget" in results:
                    if platform.system() == "Linux":
                        return self.ipfs_multiformats.get_cid(os.path.join(self.bin_path, "ipget"))
                    elif platform.system() == "Windows":
                        return self.ipfs_multiformats.get_cid(
                            os.path.join(self.bin_path, "ipget.exe")
                        )
                else:
                    return False

    def config_ipfs_cluster_service(self, **kwargs):
        cluster_name = None
        secret = None
        disk_stats = None
        ipfs_path = None
        found = False
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
            raise Exception("disk_stats is None")
        if ipfs_path is None:
            raise Exception("ipfs_path is None")
        if cluster_name is None:
            raise Exception("cluster_name is None")
        if secret is None:
            raise Exception("secret is None")

        if "this_dir" in list(self.__dict__.keys()):
            this_dir = self.this_dir
        else:
            this_dir = os.path.dirname(os.path.realpath(__file__))

        home_dir = os.path.expanduser("~")
        service_path = ""
        cluster_path = os.path.join(ipfs_path, cluster_name)
        run_daemon = ""
        init_cluster_daemon_results = ""
        results = {}
        try:
            if platform.system() == "Linux" and os.geteuid() == 0:
                service_path = os.path.join("/root", ".ipfs-cluster")
                pass
            else:
                # service_path = os.path.join(os.path.expanduser("~"), ".ipfs-cluster")
                service_path = os.path.join(self.ipfs_path)
                pass
            if not os.path.exists(service_path):
                os.makedirs(service_path)
                pass
            if cluster_name is not None and ipfs_path is not None and disk_stats is not None:
                # Prepare environment for subprocess calls
                cmd_env = os.environ.copy()
                cmd_env["IPFS_PATH"] = self.ipfs_path
                cmd_env["PATH"] = self.path  # Use the modified path

                # Determine the correct ipfs command path
                ipfs_cmd_path = (
                    os.path.join(self.bin_path, "ipfs.exe")
                    if platform.system() == "Windows"
                    else os.path.join(self.bin_path, "ipfs")
                )

                # Ensure the command path exists and is executable
                if not os.path.isfile(ipfs_cmd_path):
                    raise FileNotFoundError(f"IPFS executable not found at: {ipfs_cmd_path}")
                if platform.system() != "Windows" and not os.access(ipfs_cmd_path, os.X_OK):
                    # Attempt to make it executable
                    try:
                        os.chmod(ipfs_cmd_path, 0o755)
                        print(f"Made {ipfs_cmd_path} executable.")
                    except Exception as chmod_err:
                        raise PermissionError(
                            f"IPFS executable at {ipfs_cmd_path} is not executable and could not be changed: {chmod_err}"
                        )

                    ipfs_init_command = [ipfs_cmd_path, "init", "--profile=badgerds"]
                    try:
                        print(f"Running command: {' '.join(ipfs_init_command)}")
                        # Use check=False to handle 'already initialized' case gracefully
                        process = subprocess.run(
                            ipfs_init_command,
                            shell=False,
                            env=cmd_env,
                            capture_output=True,
                            text=True,
                        )
                        ipfs_init_results = process.stdout.strip() + process.stderr.strip()
                        print(f"IPFS init result: {ipfs_init_results}")
                        if (
                            process.returncode != 0
                            and "already initialized" not in ipfs_init_results
                        ):
                            raise subprocess.CalledProcessError(
                                process.returncode,
                                ipfs_init_command,
                                output=process.stdout,
                                stderr=process.stderr,
                            )
                        elif "already initialized" in ipfs_init_results:
                            print("Repository already initialized, proceeding with configuration.")
                    except Exception as e:
                        print(f"IPFS init command failed unexpectedly: {e}")
                        raise  # Re-raise other unexpected errors
                elif platform.system() == "Windows":
                    # On Windows, use the appropriate command syntax for initializing ipfs-cluster-service
                    env = os.environ.copy()
                    env["IPFS_PATH"] = ipfs_path
                    init_cluster_service = (
                        "set IPFS_PATH="
                        + ipfs_path
                        + " &&  "
                        + os.path.join(self.bin_path, "ipfs-cluster-service.exe")
                        + " init -f"
                    )
                    init_cluster_service_results = subprocess.check_output(
                        init_cluster_service, shell=True, env=env
                    )
                    init_cluster_service_results = init_cluster_service_results.decode()
                elif platform.system() == "Darwin":
                    init_cluster_service = (
                        self.path_string
                        + " IPFS_PATH="
                        + ipfs_path
                        + " ipfs-cluster-service init -f"
                    )
                    init_cluster_service_results = subprocess.check_output(
                        init_cluster_service, shell=True
                    )
                    init_cluster_service_results = init_cluster_service_results.decode()
                    pass
        except Exception as e:
            print(e)
            init_cluster_service_results = str(e)
        finally:
            if init_cluster_service_results == "":
                init_cluster_service_results = True
            else:
                init_cluster_service_results = False
            pass
        results["init_cluster_service_results"] = init_cluster_service_results
        if self.role == "worker" or self.role == "master":
            try:
                service_config = ""
                workerID = random.randbytes(32)
                workerID = "worker-" + binascii.hexlify(workerID).decode()
                with open(os.path.join(self.this_dir, "service.json")) as file:
                    service_config = file.read()
                service_config = service_config.replace(
                    '"cluster_name": "ipfs-cluster"', '"cluster_name": "' + cluster_name + '"'
                )
                service_config = service_config.replace(
                    '"secret": "96d5952479d0a2f9fbf55076e5ee04802f15ae5452b5faafc98e2bd48cf564d3"',
                    '"secret": "' + secret + '"',
                )
                with open(os.path.join(service_path, "service.json"), "w") as file:
                    file.write(service_config)
                with open(os.path.join(this_dir, "peerstore"), "r") as file:
                    peerlist = file.read()
                with open(service_path + "/peerstore", "w") as file:
                    file.write(peerlist)

                pebble_link = os.path.join(service_path, "pebble")
                pebble_dir = os.path.join(cluster_path, "pebble")

                if cluster_path != service_path:
                    if os.path.exists(pebble_link) or os.path.islink(pebble_link):
                        if platform.system() == "Linux" and os.geteuid() == 0:
                            remove_pebble_command = "rm -rf " + pebble_link
                        elif platform.system() == "Linux" and os.geteuid() != 0:
                            remove_pebble_command = "rm -rf " + pebble_link
                        elif platform.system() == "Windows":
                            remove_pebble_command = "rmdir /S /Q " + pebble_link
                        elif platform.system() == "Darwin":
                            remove_pebble_command = "rm -rf " + pebble_link
                        remove_pebble_command_results = subprocess.check_output(
                            remove_pebble_command, shell=True
                        )
                        remove_pebble_command_results = remove_pebble_command_results.decode()
                        pass
                    # link_pebble_command = "ln -s " + pebble_dir + " " + pebble_link
                    # link_pebble_command_results = subprocess.check_output(link_pebble_command, shell=True)
                    # link_pebble_command_results = link_pebble_command_results.decode()
                    # pass

                if platform.system() == "Linux" and os.geteuid() == 0:
                    with open(os.path.join(this_dir, "ipfs-cluster.service"), "r") as file:
                        service_file = file.read()

                    # service_file = service_file.replace("ExecStart=/usr/local/bin/ipfs-cluster-service daemon", "ExecStart=/usr/local/bin/ipfs-cluster-service daemon --peerstore "+ service_path + "/peerstore --service "+ service_path + "/service.json")
                    service_file = service_file.replace(
                        "ExecStart=/usr/local/bin/",
                        'ExecStart= bash -c "export IPFS_PATH='
                        + ipfs_path
                        + " && export PATH="
                        + self.path
                        + ' && ipfs-cluster-service daemon "',
                    )
                    with open("/etc/systemd/system/ipfs-cluster.service", "w") as file:
                        file.write(service_file)
                    enable_cluster_service = "systemctl enable ipfs-cluster"
                    enable_cluster_service_results = subprocess.check_output(
                        enable_cluster_service, shell=True
                    )
                    enable_cluster_service_results = enable_cluster_service_results.decode()

                    systemctl_daemon_reload = "systemctl daemon-reload"
                    systemctl_daemon_reload_results = subprocess.check_output(
                        systemctl_daemon_reload, shell=True
                    )
                    systemctl_daemon_reload_results = systemctl_daemon_reload_results.decode()
                    pass
                elif platform.system() == "Linux" and os.geteuid() != 0:
                    with open(os.path.join(this_dir, "ipfs-cluster.service"), "r") as file:
                        service_file = file.read()
                    service_file = service_file.replace(
                        "ExecStart=/usr/local/bin/ipfs-cluster-service daemon",
                        "ExecStart=/usr/local/bin/ipfs-cluster-service daemon --peerstore "
                        + service_path
                        + "/peerstore --service "
                        + service_path
                        + "/service.json",
                    )
                    with open("/etc/systemd/system/ipfs-cluster.service", "w") as file:
                        file.write(service_file)
                    enable_cluster_service = "systemctl enable ipfs-cluster"
                    enable_cluster_service_results = subprocess.check_output(
                        enable_cluster_service, shell=True
                    )
                    enable_cluster_service_results = enable_cluster_service_results.decode()
                    pass
                elif platform.system() == "Windows":
                    # Windows does not use systemctl or /etc/ system service files; run the service directly
                    enable_cluster_service = [
                        os.path.join(self.this_dir, "bin", "ipfs-cluster-service.exe"),
                        "daemon",
                        "--peerstore",
                        os.path.join(service_path, "peerstore"),
                        "--service",
                        os.path.join(service_path, "service.json"),
                    ]
                    enable_cluster_service = " ".join(enable_cluster_service)
                    enable_cluster_service = enable_cluster_service.replace("\\", "/")
                    enable_cluster_service = enable_cluster_service.split("/")
                    enable_cluster_service = "/".join(enable_cluster_service)
                    enable_cluster_service_results = subprocess.check_output(
                        enable_cluster_service, shell=True
                    )
                    enable_cluster_service_results = enable_cluster_service_results.decode()
                    pass
            except Exception as e:
                raise Exception(str(e))
            finally:
                pass
            pass
        try:
            run_daemon_results = ""
            if platform.system() == "Linux" and os.geteuid() == 0:
                reload_daemon = "systemctl daemon-reload"
                reload_daemon_results = subprocess.check_output(reload_daemon, shell=True)
                reload_daemon_results = reload_daemon_results.decode()
                enable_daemon = "systemctl enable ipfs-cluster"
                enable_daemon_results = subprocess.check_output(enable_daemon, shell=True)
                enable_daemon_results = enable_daemon_results.decode()
                start_daemon = "systemctl start ipfs-cluster"
                start_daemon_results = subprocess.check_output(start_daemon, shell=True)
                start_daemon_results = start_daemon_results.decode()
                time.sleep(5)
                run_daemon = "systemctl status ipfs-cluster"
                run_daemon_results = subprocess.check_output(run_daemon, shell=True)
                run_daemon_results = run_daemon_results.decode()
                pass
            elif platform.system() == "Linux" and os.geteuid() != 0:
                run_daemon_cmd = self.path_string + " ipfs-cluster-service -d daemon "
                run_daemon_results = subprocess.Popen(run_daemon_cmd, shell=True)
                time.sleep(5)
                find_daemon_command = "ps -ef | grep ipfs-cluster-service | grep -v grep | wc -l"
                find_daemon_command_results = subprocess.check_output(
                    find_daemon_command, shell=True
                )
                find_daemon_command_results = find_daemon_command_results.decode().strip()
                results["run_daemon"] = find_daemon_command_results

                if int(find_daemon_command_results) > 0:
                    self.kill_process_by_pattern("ipfs-cluster-service")
                    pass
                else:
                    print("ipfs-cluster-service daemon did not start")
                    raise Exception("ipfs-cluster-service daemon did not start")
                pass
            elif platform.system() == "Windows":
                run_daemon_cmd = (
                    os.path.join(self.bin_path, "ipfs-cluster-service.exe") + " -d daemon"
                )
                run_daemon_results = subprocess.Popen(run_daemon_cmd, shell=True)
                time.sleep(5)
                find_daemon_command = (
                    'powershell -Command "(tasklist | findstr ipfs-cluster-service).Count"'
                )
                find_daemon_command_results = subprocess.check_output(
                    find_daemon_command, shell=True
                )
                find_daemon_command_results = find_daemon_command_results.decode().strip()
                found = None
                int_found = int(find_daemon_command_results)
                if int(find_daemon_command_results) > 0 or int_found > 0:
                    found = True
                else:
                    found = False
                results["run_daemon"] = find_daemon_command_results
                if found == True:
                    self.kill_process_by_pattern("ipfs-cluster-service")
                    pass
                else:
                    print("ipfs-cluster-service daemon did not start")
                    raise Exception("ipfs-cluster-service daemon did not start")
                pass
        except Exception as e:
            print(e)
            pass
        finally:
            pass

        return found

    def config_ipfs_cluster_ctl(self, **kwargs):
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
            raise Exception("disk_stats is None")
        if ipfs_path is None:
            raise Exception("ipfs_path is None")
        if cluster_name is None:
            raise Exception("cluster_name is None")
        if secret is None:
            raise Exception("secret is None")

        run_cluster_ctl = None

        try:
            if platform.system() == "Linux" and os.geteuid() == 0:
                run_cluster_ctl_cmd = self.path_string + " ipfs-cluster-ctl --version"
            elif platform.system() == "Linux" and os.geteuid() != 0:
                run_cluster_ctl_cmd = self.path_string + " ipfs-cluster-ctl --version"
            elif platform.system() == "Windows":
                run_cluster_ctl_cmd = (
                    os.path.join(self.bin_path, "ipfs-cluster-ctl.exe") + " --version"
                )
            elif platform.system() == "Darwin":
                run_cluster_ctl_cmd = self.path_string + " ipfs-cluster-ctl --version"
            run_cluster_ctl = subprocess.check_output(run_cluster_ctl_cmd, shell=True)
            run_cluster_ctl = run_cluster_ctl.decode()
            pass
        except Exception as e:
            run_cluster_ctl = str(e)
            return False
        finally:
            pass

        results["run_cluster_ctl"] = run_cluster_ctl
        return results

    def config_ipfs_cluster_follow(self, **kwargs):
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
            raise Exception("disk_stats is None")
        if ipfs_path is None:
            raise Exception("ipfs_path is None")
        if cluster_name is None:
            raise Exception("cluster_name is None")
        if secret is None:
            raise Exception("secret is None")

        if "this_dir" in list(self.__dict__.keys()):
            this_dir = self.this_dir
        else:
            this_dir = os.path.dirname(os.path.realpath(__file__))

        home_dir = os.path.expanduser("~")
        cluster_path = os.path.join(os.path.dirname(ipfs_path), "ipfs-cluster", cluster_name)
        follow_path = os.path.join(ipfs_path, "ipfs_cluster") + "/"
        run_daemon = None
        follow_init_cmd_results = None
        worker_id = random.randbytes(32)
        worker_id = "worker-" + binascii.hexlify(worker_id).decode()
        follow_path = None
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
                    if platform.system() == "Linux" and os.geteuid() == 0:
                        rm_command = "rm -rf " + follow_path
                    elif platform.system() == "Linux" and os.geteuid() != 0:
                        rm_command = "rm -rf " + follow_path
                    elif platform.system() == "Windows":
                        rm_command = "rmdir /S /Q " + follow_path
                    elif platform.system() == "Darwin":
                        rm_command = "rm -rf " + follow_path
                    rm_results = subprocess.check_output(rm_command, shell=True)
                    rm_results = rm_results.decode()
                    pass
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
                    follow_init_cmd = follow_init_cmd.split("/")
                    follow_init_cmd = "/".join(follow_init_cmd)
                elif platform.system() == "Darwin":
                    follow_init_cmd = (
                        self.path_string
                        + " IPFS_PATH="
                        + ipfs_path
                        + " ipfs-cluster-follow "
                        + cluster_name
                        + " init "
                        + ipfs_path
                    )
                # follow_init_cmd = "ipfs-cluster-follow " + cluster_name + " init " + ipfs_path
                follow_init_cmd_results = subprocess.check_output(
                    follow_init_cmd, shell=True
                ).decode()
                if not os.path.exists(cluster_path):
                    os.makedirs(cluster_path)
                    pass
                if not os.path.exists(follow_path):
                    os.makedirs(follow_path)
                    pass
                with open(os.path.join(this_dir, "service_follower.json"), "r") as file:
                    service_config = file.read()
                service_config = service_config.replace(
                    '"cluster_name": "ipfs-cluster"', '"cluster_name": "' + cluster_name + '"'
                )
                service_config = service_config.replace(
                    '"peername": "worker"', '"peername": "' + worker_id + '"'
                )
                service_config = service_config.replace(
                    '"secret": "96d5952479d0a2f9fbf55076e5ee04802f15ae5452b5faafc98e2bd48cf564d3"',
                    '"secret": "' + secret + '"',
                )
                with open(os.path.join(follow_path, "service.json"), "w") as file:
                    file.write(service_config)
                with open(os.path.join(this_dir, "peerstore"), "r") as file:
                    peer_store = file.read()
                with open(os.path.join(follow_path, "peerstore"), "w") as file:
                    file.write(peer_store)

                pebble_link = os.path.join(follow_path, "pebble")
                pebble_dir = os.path.join(cluster_path, "pebble")

                if cluster_path != follow_path:
                    if os.path.exists(pebble_link):
                        if platform.system() == "Linux" and os.geteuid() == 0:
                            command2 = "rm -rf " + pebble_link
                        elif platform.system() == "Linux" and os.geteuid() != 0:
                            command2 = "rm -rf " + pebble_link
                        elif platform.system() == "Windows":
                            command2 = "rmdir /S /Q " + pebble_link
                        elif platform.system() == "Darwin":
                            command2 = "rm -rf " + pebble_link
                        results2 = subprocess.check_output(command2, shell=True)
                        results2 = results2.decode()
                        pass
                    if not os.path.exists(pebble_dir):
                        os.makedirs(pebble_dir)
                        pass

                    command3 = ""
                    if platform.system() == "Linux" and os.geteuid() == 0:
                        command3 = "ln -s " + pebble_dir + " " + pebble_link
                    elif platform.system() == "Linux" and os.geteuid() != 0:
                        command3 = "ln -s " + pebble_dir + " " + pebble_link
                    elif platform.system() == "Windows" and os.access(pebble_link, os.W_OK):
                        command3 = "mklink /D " + pebble_link + " " + pebble_dir
                    elif platform.system() == "Darwin" and os.access(pebble_link, os.W_OK):
                        command3 = "ln -s " + pebble_dir + " " + pebble_link
                    pass

                    if command3 != "":
                        results3 = subprocess.check_output(command3, shell=True)
                        results3 = results3.decode()
                        pass
                if platform.system() == "Linux" and os.geteuid() == 0:
                    with open(os.path.join(this_dir, "ipfs-cluster-follow.service"), "r") as file:
                        service_file = file.read()
                    # new_service = service_file.replace("ExecStart=/usr/local/bin/ipfs-cluster-follow run","ExecStart=/usr/local/bin/ipfs-cluster-follow "+ cluster_name + " run")
                    new_service = service_file.replace(
                        "ExecStart=",
                        'ExecStart= bash -c "export IPFS_PATH='
                        + ipfs_path
                        + " && export PATH="
                        + self.path
                        + " && /usr/local/bin/ipfs-cluster-follow "
                        + cluster_name
                        + ' run "',
                    )
                    new_service = new_service.replace(
                        "Description=IPFS Cluster Follow",
                        "Description=IPFS Cluster Follow " + cluster_name,
                    )
                    with open("/etc/systemd/system/ipfs-cluster-follow.service", "w") as file:
                        file.write(new_service)
                    enable_ipfs_cluster_follow_service = "systemctl enable ipfs-cluster-follow"
                    enable_ipfs_cluster_follow_service_results = subprocess.check_output(
                        enable_ipfs_cluster_follow_service, shell=True
                    )
                    enable_ipfs_cluster_follow_service_results = (
                        enable_ipfs_cluster_follow_service_results.decode()
                    )
                    subprocess.call("systemctl daemon-reload", shell=True)
                    pass
                else:
                    pass
            except Exception as e:
                raise Exception(str(e))
            finally:
                pass
            pass
        else:
            pass
        find_daemon_results = None
        try:
            if platform.system() == "Linux" and os.geteuid() == 0:
                find_daemon = "ps -ef | grep ipfs-cluster-follow | grep -v grep | wc -l"
            elif platform.system() == "Linux" and os.geteuid() != 0:
                find_daemon = "ps -ef | grep ipfs-cluster-follow | grep -v grep | wc -l"
            elif platform.system() == "Windows":
                find_daemon = 'powershell -Command "(tasklist | findstr ipfs-cluster-follow).Count"'
            elif platform.system() == "Darwin":
                find_daemon = "ps -ef | grep ipfs-cluster-follow | grep -v grep | wc -l"

            find_daemon_results = subprocess.check_output(find_daemon, shell=True)
            find_daemon_results = find_daemon_results.decode().strip()
            if int(find_daemon_results) > 0:
                self.kill_process_by_pattern("ipfs-cluster-follow")
                pass
            run_daemon_results = None
            if platform.system() == "Linux" and os.geteuid() == 0:
                reload_damon = "systemctl daemon-reload"
                reload_damon_results = subprocess.check_output(reload_damon, shell=True)
                reload_damon_results = reload_damon_results.decode()

                enable_damon = "systemctl enable ipfs-cluster-follow"
                enable_damon_results = subprocess.check_output(enable_damon, shell=True)
                enable_damon_results = enable_damon_results.decode()

                start_damon = "systemctl start ipfs-cluster-follow"
                start_damon_results = subprocess.check_output(start_damon, shell=True)
                start_damon_results = start_damon_results.decode()
                time.sleep(2)
                run_daemon = "systemctl status ipfs-cluster-follow"
                run_daemon_results = subprocess.check_output(run_daemon, shell=True)
                run_daemon_results = run_daemon_results.decode()

                find_daemon = "ps -ef | grep ipfs-cluster-follow | grep -v grep | wc -l"
                find_daemon_results = subprocess.check_output(find_daemon, shell=True)
                find_daemon_results = find_daemon_results.decode().strip()

                if int(find_daemon_results) == 0:
                    print("ipfs-cluster-follow daemon did not start")
                    raise Exception("ipfs-cluster-follow daemon did not start")
                if int(find_daemon_results) > 0:
                    self.kill_process_by_pattern("ipfs-cluster-follow")
                    pass

                pass
            elif platform.system() == "Linux" and os.geteuid() != 0:
                run_daemon_cmd = "ipfs-cluster-follow " + cluster_name + " run"
                run_daemon_results = subprocess.Popen(run_daemon_cmd, shell=True)
                if run_daemon_results is not None:
                    results["run_daemon"] = True
                    pass
                time.sleep(2)
                find_daemon = "ps -ef | grep ipfs-cluster-follow | grep -v grep | wc -l"
                find_daemon_results = subprocess.check_output(find_daemon, shell=True)
                find_daemon_results = find_daemon_results.decode().strip()

                if int(find_daemon_results) == 0:
                    print("ipfs-cluster-follow daemon did not start")
                    raise Exception("ipfs-cluster-follow daemon did not start")
                elif int(find_daemon_results) > 0:
                    self.kill_process_by_pattern("ipfs-cluster-follow")
                    pass
                pass
            elif platform.system() == "Windows":
                run_daemon_cmd = (
                    os.path.join(self.bin_path, "ipfs-cluster-follow.exe")
                    + " "
                    + cluster_name
                    + " run"
                )
                run_daemon_results = subprocess.Popen(run_daemon_cmd, shell=True)
                if run_daemon_results is not None:
                    results["run_daemon"] = True
                    pass
                time.sleep(2)
                find_daemon = 'powershell -Command "(tasklist | findstr ipfs-cluster-follow).Count"'
                find_daemon_results = subprocess.check_output(find_daemon, shell=True)
                find_daemon_results = find_daemon_results.decode().strip()
                if int(find_daemon_results) == 0:
                    print("ipfs-cluster-follow daemon did not start")
                    raise Exception("ipfs-cluster-follow daemon did not start")
                elif int(find_daemon_results) > 0:
                    self.kill_process_by_pattern("ipfs-cluster-follow")
                    pass
                pass
        except Exception as e:
            print(e)
            pass
        finally:
            pass

        if int(find_daemon_results) > 0:
            results["run_daemon"] = True
        else:
            results["run_daemon"] = False
            pass
        results["follow_init_cmd_results"] = follow_init_cmd_results
        return results

    def config_ipfs(self, **kwargs):
        results = {}
        cluster_name = None
        secret = None
        disk_stats = None
        ipfs_path = None
        ipfs_cmd = None
        if platform.system() == "Windows":
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
            raise Exception("disk_stats is None")
        if ipfs_path is None:
            raise Exception("ipfs_path is None")
        if cluster_name is None:
            raise Exception("cluster_name is None")
        if secret is None:
            raise Exception("secret is None")

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
        os.makedirs(ipfs_path, exist_ok=True)
        ipfs_dir_contents = os.listdir(ipfs_path)
        if len(ipfs_dir_contents) > 0:
            print("ipfs directory is not empty, attempting to clean...")
            for item_name in ipfs_dir_contents:
                item_path = os.path.join(ipfs_path, item_name)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.unlink(item_path)
                        print(f"Removed file/link: {item_path}")
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        print(f"Removed directory: {item_path}")
                except Exception as e:
                    print(f"Failed to remove {item_path}: {e}")
                    # Continue trying to remove other items
                # Removed the else block as it was causing issues and not strictly necessary
                # else:
                # 	print("unknown file type " + item_name + " in ipfs directory") # Corrected variable name again
                # 	pass
            pass

            results = {"config": None, "identity": None, "public_key": None}

        if disk_stats is not None and ipfs_path is not None:
            try:
                peer_id = None
                disk_available = None
                min_free_space = 32 * 1024 * 1024 * 1024
                allocate = None
                disk_available = self.disk_stats["disk_avail"]

                # Prepare environment for subprocess calls
                cmd_env = os.environ.copy()
                cmd_env["IPFS_PATH"] = self.ipfs_path
                cmd_env["PATH"] = self.path  # Use the modified path

                # Determine the correct ipfs command path
                ipfs_cmd_path = (
                    os.path.join(self.bin_path, "ipfs.exe")
                    if platform.system() == "Windows"
                    else os.path.join(self.bin_path, "ipfs")
                )

                # Ensure the command path exists and is executable
                if not os.path.isfile(ipfs_cmd_path):
                    raise FileNotFoundError(f"IPFS executable not found at: {ipfs_cmd_path}")
                if platform.system() != "Windows" and not os.access(ipfs_cmd_path, os.X_OK):
                    # Attempt to make it executable
                    try:
                        os.chmod(ipfs_cmd_path, 0o755)
                        print(f"Made {ipfs_cmd_path} executable.")
                    except Exception as chmod_err:
                        raise PermissionError(
                            f"IPFS executable at {ipfs_cmd_path} is not executable and could not be changed: {chmod_err}"
                        )

                ipfs_init_command = [ipfs_cmd_path, "init", "--profile=badgerds"]

                try:
                    print(f"Running command: {' '.join(ipfs_init_command)}")
                    ipfs_init_results = subprocess.check_output(
                        ipfs_init_command, shell=False, env=cmd_env
                    )
                    ipfs_init_results = ipfs_init_results.decode().strip()
                    print(f"IPFS init result: {ipfs_init_results}")
                except Exception as e:
                    ipfs_init_results = str(e)
                    print(f"IPFS init failed: {e}")
                    # If init fails due to existing repo, try to proceed with config
                    if "already initialized" not in ipfs_init_results:
                        # Re-raise if it's not the expected 'already initialized' error
                        raise e
                    else:
                        print("Repository already initialized, proceeding with configuration.")
                        pass  # Continue if already initialized

                peer_id_command = [ipfs_cmd_path, "id"]
                print(f"Running command: {' '.join(peer_id_command)}")
                peer_id_results = subprocess.check_output(peer_id_command, shell=False, env=cmd_env)
                peer_id_results = peer_id_results.decode()
                peer_id = json.loads(peer_id_results)
                print(f"IPFS ID result: {peer_id}")

                ipfs_profile_apply_command = [
                    ipfs_cmd_path,
                    "config",
                    "profile",
                    "apply",
                    "badgerds",
                ]
                print(f"Running command: {' '.join(ipfs_profile_apply_command)}")
                ipfs_profile_apply_results = subprocess.check_output(
                    ipfs_profile_apply_command, shell=False, env=cmd_env
                )
                ipfs_profile_apply_results = ipfs_profile_apply_results.decode()
                print(f"IPFS profile apply result: {ipfs_profile_apply_results}")

                if (
                    disk_available is not None
                    and min_free_space is not None
                    and disk_available > min_free_space
                ):
                    allocate = math.ceil(
                        ((disk_available - min_free_space) * 0.8) / 1024 / 1024 / 1024
                    )
                    datastore_command = [
                        ipfs_cmd_path,
                        "config",
                        "Datastore.StorageMax",
                        f"{allocate}GB",
                    ]
                    print(f"Running command: {' '.join(datastore_command)}")
                    datastore_command_results = subprocess.check_output(
                        datastore_command, shell=False, env=cmd_env
                    )
                    datastore_command_results = datastore_command_results.decode()
                    print(f"IPFS datastore config result: {datastore_command_results}")
                    pass

                peer_list_path = os.path.join(this_dir, "peerstore")
                peer_list_path = peer_list_path.replace("\\", "/")
                peer_list_path = peer_list_path.split("/")
                peer_list_path = "/".join(peer_list_path)
                if os.path.exists(peer_list_path):
                    print(f"Adding bootstrap peers from {peer_list_path}")
                    with open(peer_list_path, "r") as file:
                        peerlist = file.read()
                    peerlist = peerlist.split("\n")
                    for peer in peerlist:
                        if peer != "":
                            bootstrap_add_command = [ipfs_cmd_path, "bootstrap", "add", peer]
                            print(f"Running command: {' '.join(bootstrap_add_command)}")
                            bootstrap_add_command_results = subprocess.check_output(
                                bootstrap_add_command, shell=False, env=cmd_env
                            )
                            bootstrap_add_command_results = bootstrap_add_command_results.decode()
                            print(f"Bootstrap add result: {bootstrap_add_command_results}")
                            pass
                        pass
                if platform.system() == "Linux" and os.geteuid() == 0:
                    print("Configuring systemd service for IPFS...")
                    with open(os.path.join(self.this_dir, "ipfs.service"), "r") as file:
                        ipfs_service = file.read()
                    # Use absolute path for ipfs in service file
                    ipfs_service_text = ipfs_service.replace(
                        "ExecStart=",
                        'ExecStart= bash -c "export IPFS_PATH='
                        + ipfs_path
                        + " && export PATH="
                        + self.path
                        + " && "
                        + ipfs_cmd_path
                        + ' daemon --enable-gc --enable-pubsub-experiment "',
                    )
                    with open("/etc/systemd/system/ipfs.service", "w") as file:
                        file.write(ipfs_service_text)
                    print("Wrote /etc/systemd/system/ipfs.service")
                    pass

                config_get_cmd = [ipfs_cmd_path, "config", "show"]
                print(f"Running command: {' '.join(config_get_cmd)}")
                config_data = subprocess.check_output(config_get_cmd, shell=False, env=cmd_env)
                config_data = config_data.decode()
                try:
                    config_data = json.loads(config_data)
                except Exception as e:
                    print(e)
                results["config"] = config_data
                results["identity"] = peer_id["ID"]
                results["public_key"] = peer_id["PublicKey"]
                results["agent_version"] = peer_id["AgentVersion"]
                results["addresses"] = peer_id["Addresses"]
            except Exception as e:
                print("error configuring IPFS in config_ipfs()")
                print(e)
            finally:
                pass

        pass
        if platform.system() == "Linux" and os.geteuid() == 0:
            try:
                enable_daemon_cmd = "systemctl enable ipfs"
                enable_daemon_results = subprocess.check_output(enable_daemon_cmd, shell=True)
                enable_daemon_results = enable_daemon_results.decode()

                reload_daemon_cmd = "systemctl daemon-reload"
                reload_daemon_results = subprocess.check_output(reload_daemon_cmd, shell=True)
                reload_daemon_results = reload_daemon_results.decode()

                find_daemon_cmd = "ps -ef | grep ipfs | grep daemon | grep -v grep | wc -l"
                find_daemon_results = subprocess.check_output(find_daemon_cmd, shell=True)
                find_daemon_results = find_daemon_results.decode().strip()
                stop_daemon_cmd = "systemctl stop ipfs"

                if int(find_daemon_results) > 0:
                    stop_daemon_results = subprocess.check_output(stop_daemon_cmd, shell=True)
                    stop_daemon_results = stop_daemon_results.decode()
                    pass

                start_daemon_cmd = "systemctl start ipfs"
                start_daemon_results = subprocess.check_output(start_daemon_cmd, shell=True)
                start_daemon_results = start_daemon_results.decode()
                time.sleep(2)
                find_daemon_results = subprocess.check_output(find_daemon_cmd, shell=True)
                find_daemon_results = find_daemon_results.decode().strip()

                if int(find_daemon_results) > 0:
                    if platform.system() == "Linux" and os.geteuid() == 0:
                        test_daemon = (
                            'bash -c "export IPFS_PATH='
                            + ipfs_path
                            + " && export PATH="
                            + self.path
                            + ' && ipfs cat /ipfs/QmSgvgwxZGaBLqkGyWemEDqikCqU52XxsYLKtdy3vGZ8uq > /tmp/test.jpg"'
                        )
                    elif platform.system() == "Linux" and os.geteuid() != 0:
                        test_daemon = (
                            'bash -c "export IPFS_PATH='
                            + ipfs_path
                            + " && export PATH="
                            + self.path
                            + ' && ipfs cat /ipfs/QmSgvgwxZGaBLqkGyWemEDqikCqU52XxsYLKtdy3vGZ8uq > /tmp/test.jpg"'
                        )
                    elif platform.system() == "Windows":
                        test_daemon = (
                            f"set \"IPFS_PATH={ipfs_path}\" ; {os.path.join(self.bin_path, 'ipfs.exe')} cat /ipfs/QmSgvgwxZGaBLqkGyWemEDqikCqU52XxsYLKtdy3vGZ8uq > "
                            + os.path.join(os.path.expanduser("~"), "test.jpg")
                        )
                    elif platform.system() == "Darwin":
                        test_daemon = (
                            'bash -c "export IPFS_PATH='
                            + ipfs_path
                            + " && export PATH="
                            + self.path
                            + ' && ipfs cat /ipfs/QmSgvgwxZGaBLqkGyWemEDqikCqU52XxsYLKtdy3vGZ8uq > /tmp/test.jpg"'
                        )
                    test_daemon_results = subprocess.check_output(test_daemon, shell=True)
                    test_daemon_results = test_daemon_results.decode()
                    time.sleep(5)

                    if os.path.exists("/tmp/test.jpg"):
                        if os.path.getsize("/tmp/test.jpg") > 0:
                            os.remove("/tmp/test.jpg")
                            test_daemon_results = True
                            pass
                        else:
                            raise Exception("ipfs failed to download test file")
                        pass
                    pass

                    stop_daemon_cmd_results = subprocess.check_output(stop_daemon_cmd, shell=True)
                    stop_daemon_cmd_results = stop_daemon_cmd_results.decode()
                    find_daemon_results = (
                        subprocess.check_output(find_daemon_cmd, shell=True).decode().strip()
                    )
                    pass

                else:
                    raise Exception("ipfs daemon did not start")
                    pass
            except Exception as e:
                print("error starting ipfs daemon")
                print(e)
            finally:
                if int(find_daemon_results) > 0:
                    stop_daemon_cmd = "systemctl stop ipfs"
                    stop_daemon_results = subprocess.check_output(stop_daemon_cmd, shell=True)
                    stop_daemon_results = stop_daemon_results.decode()
                    pass
        elif platform.system() == "Linux" and os.geteuid() != 0:
            find_daemon_cmd = "ps -ef | grep ipfs | grep daemon | grep -v grep | wc -l"
            find_daemon_results = subprocess.check_output(find_daemon_cmd, shell=True)
            find_daemon_results = find_daemon_results.decode().strip()
            if int(find_daemon_results) > 0:
                kill_daemon_cmd = "ps -ef | grep ipfs | grep daemon | grep -v grep | awk '{print $2}' | xargs kill -9"
                kill_daemon_results = subprocess.check_output(kill_daemon_cmd, shell=True)
                kill_daemon_results = kill_daemon_results.decode()
                find_daemon_results = subprocess.check_output(find_daemon_cmd, shell=True)
                find_daemon_results = find_daemon_results.decode()
                pass

            run_daemon_cmd = (
                self.path_string
                + " IPFS_PATH="
                + self.ipfs_path
                + " ipfs daemon --enable-pubsub-experiment"
            )
            run_daemon = subprocess.Popen(run_daemon_cmd, shell=True)
            time.sleep(5)
            find_daemon_results = subprocess.check_output(find_daemon_cmd, shell=True)
            find_daemon_results = find_daemon_results.decode().strip()
            test_daemon_results = None
            try:
                if os.path.exists("/tmp/test.jpg"):
                    os.remove("/tmp/test.jpg")
                    pass
                if platform.system() == "Linux":
                    test_daemon = (
                        'bash -c "IPFS_PATH='
                        + self.ipfs_path
                        + " PATH="
                        + self.path
                        + ' ipfs cat /ipfs/QmSgvgwxZGaBLqkGyWemEDqikCqU52XxsYLKtdy3vGZ8uq > /tmp/test.jpg"'
                    )
                elif platform.system() == "Windows":
                    test_daemon = (
                        os.path(self.bin_path, "ipfs.exe")
                        + " cat /ipfs/QmSgvgwxZGaBLqkGyWemEDqikCqU52XxsYLKtdy3vGZ8uq > /tmp/test.jpg"
                    )
                test_daemon_results = subprocess.check_output(test_daemon, shell=True)
                test_daemon_results = test_daemon_results.decode()
                time.sleep(5)

                if os.path.exists("/tmp/test.jpg"):
                    if os.path.getsize("/tmp/test.jpg") > 0:
                        test_daemon_results = True
                        os.remove("/tmp/test.jpg")
                        pass
                    else:
                        raise Exception("ipfs failed to download test file")
                    pass
                else:
                    raise Exception("ipfs failed to download test file")

            except Exception as e:
                print("error starting ipfs daemon")
                print(e)
            finally:
                pass
            private_key = None
            if (
                "identity" in list(results.keys())
                and results["identity"] is not None
                and "identity" in list(results.keys())
                and results["identity"] != ""
                and len(results["identity"]) == 52
            ):
                identity = results["identity"]
                config = results["config"]
                if "PrivKey" in list(config["Identity"].keys()):
                    private_key = config["Identity"]["PrivKey"]
                ipfs_daemon = test_daemon_results
                pass
        elif platform.system() == "Windows":
            find_daemon_cmd = "tasklist | findstr ipfs.exe"
            find_daemon_results = ""
            try:
                if len(find_daemon_results) > 0:
                    try:
                        find_daemon_results = subprocess.check_output(find_daemon_cmd, shell=True)
                        find_daemon_results = find_daemon_results.decode().strip().splitlines()
                        kill_daemon_cmd = "taskkill /F /IM ipfs.exe"
                        kill_daemon_results = subprocess.check_output(kill_daemon_cmd, shell=True)
                        kill_daemon_results = kill_daemon_results.decode()
                        find_daemon_results = subprocess.check_output(find_daemon_cmd, shell=True)
                        find_daemon_results = find_daemon_results.decode().strip().splitlines()
                    except Exception as e:
                        print(e)
                        pass
                run_daemon_cmd = (
                    os.path.join(self.bin_path, "ipfs.exe") + " daemon --enable-pubsub-experiment"
                )
                run_daemon_cmd = run_daemon_cmd.replace("\\", "/")
                run_daemon_cmd = run_daemon_cmd.split("/")
                run_daemon_cmd = "/".join(run_daemon_cmd)
                # run_daemon_cmd = self.path_string + ' IPFS_PATH='+ self.ipfs_path + ' ipfs daemon --enable-pubsub-experiment'
                subprocess.Popen(run_daemon_cmd, shell=True)
                time.sleep(5)
                find_daemon_results = subprocess.check_output(
                    find_daemon_cmd, shell=True, env={**os.environ, "IPFS_PATH": self.ipfs_path}
                )
                find_daemon_results = find_daemon_results.decode().strip().splitlines()
            except Exception as e:
                find_daemon_results = None
                print("error starting ipfs daemon")
                print(e)

            test_daemon_results = None
            try:
                if os.path.exists("C:\\tmp\\test.jpg"):
                    os.remove("C:\\tmp\\test.jpg")
                    pass
                # test_daemon = 'bash -c "IPFS_PATH='+ self.ipfs_path + ' PATH='+ self.path +' ipfs cat /ipfs/QmSgvgwxZGaBLqkGyWemEDqikCqU52XxsYLKtdy3vGZ8uq > C:\\tmp\\test.jpg"'
                if platform.system() == "Windows":
                    ipfs_path = os.path.join(self.bin_path, "ipfs.exe").replace("\\", "/")
                    tmp_dir = "C:/tmp"
                    if not os.path.exists(tmp_dir):
                        os.makedirs(tmp_dir)
                    with tempfile.NamedTemporaryFile(delete=True, dir=tmp_dir) as file:
                        test_daemon = f"powershell -Command \"$env:IPFS_PATH='{self.ipfs_path}'; & '{ipfs_path}' cat /ipfs/QmSgvgwxZGaBLqkGyWemEDqikCqU52XxsYLKtdy3vGZ8uq \""
                elif platform.system() == "Linux":
                    test_daemon = (
                        os.path.join(self.bin_path, "ipfs")
                        + " cat /ipfs/QmSgvgwxZGaBLqkGyWemEDqikCqU52XxsYLKtdy3vGZ8uq > /tmp/test.jpg"
                    )
                test_daemon_results = subprocess.check_output(
                    test_daemon, shell=True, env={**os.environ, "IPFS_PATH": self.ipfs_path}
                )
                time.sleep(5)
                if len(test_daemon_results) > 10000:
                    # print("len(test_daemon_results) > 0")
                    # print(len(test_daemon_results))
                    test_daemon_results = True
                    pass
                else:
                    raise Exception("ipfs failed to download test file")
                # if os.path.exists("C:\\tmp\\test.jpg"):
                # 	if os.path.getsize("C:\\tmp\\test.jpg") > 0:
                # 		test_daemon_results = True
                # 		os.remove("C:\\tmp\\test.jpg")
                # 		pass
                # 	else:
                # 		raise Exception("ipfs failed to download test file")
                # 	pass
            except Exception as e:
                print("error starting ipfs daemon")
                print(e)
                test_daemon_results = e
            finally:
                pass
            private_key = None
            if (
                "identity" in list(results.keys())
                and results["identity"] is not None
                and results["identity"] != ""
                and len(results["identity"]) == 52
            ):
                identity = results["identity"]
                config = results["config"]
                if "PrivKey" in list(config["Identity"].keys()):
                    private_key = config["Identity"]["PrivKey"]
                ipfs_daemon = test_daemon_results
                pass
        else:
            pass

        self.kill_process_by_pattern("ipfs")
        results = {
            "config": config,
            "identity": identity,
            # "public_key":private_key,
            "public_key": None,
            "ipfs_daemon": ipfs_daemon,
        }

        return results

    def run_ipfs_cluster_service(self, **kwargs):
        run_ipfs_cluster_command_results = None
        if "ipfs_path" in list(kwargs.keys()):
            ipfs_path = kwargs["ipfs_path"]
        elif "ipfs_path" in list(self.__dict__.keys()):
            ipfs_path = self.ipfs_path
        try:
            ipfs_path = os.path.join(ipfs_path, "ipfs")
            if not os.path.exists(ipfs_path):
                os.makedirs(ipfs_path, exist_ok=True)
            if platform.system() == "Linux" and os.geteuid() == 0:
                run_command = self.path_string + " ipfs-cluster-service -d daemon "
            elif platform.system() == "Linux" and os.geteuid() != 0:
                run_command = self.path_string + " ipfs-cluster-service -d daemon "
            elif platform.system() == "Windows":
                run_command = os.path.join(self.bin_path, "ipfs-cluster-service.exe") + "-d daemon"
            elif platform.system() == "Darwin":
                run_command = self.path_string + " ipfs-cluster-service daemon"
            # run_command = self.path_string + " IPFS_CLUSTER_PATH="+ self.ipfs_path +" ipfs-cluster-service daemon"
            run_command_results = subprocess.Popen(run_command, shell=True)
            time.sleep(2)
            if platform.system() == "Linux" and os.geteuid() == 0:
                find_daemon = "ps -ef | grep ipfs-cluster-service | grep -v grep | wc -l"
            elif platform.system() == "Linux" and os.geteuid() != 0:
                find_daemon = "ps -ef | grep ipfs-cluster-service | grep -v grep | wc -l"
            elif platform.system() == "Windows":
                find_daemon = (
                    'powershell -Command "(tasklist | findstr ipfs-cluster-service).Count"'
                )
            elif platform.system() == "Darwin":
                find_daemon = "ps -ef | grep ipfs-cluster-service | grep -v grep | wc -l"
            find_daemon_results = subprocess.check_output(find_daemon, shell=True)
            find_daemon_results = find_daemon_results.decode().strip()
            if int(find_daemon_results) == 0:
                raise Exception("ipfs-cluster-service daemon did not start")
            elif int(find_daemon_results) > 0:
                self.kill_process_by_pattern("ipfs-cluster-service")
                return True
            else:
                print(find_daemon_results)
                print("error running ipfs-cluster-service")
                return False
        except Exception as e:
            run_command_results = str(e)
            print("error running ipfs-cluster-service")
            print(e)
            return run_command_results
        finally:
            pass

        return find_daemon_results

    def run_ipfs_cluster_ctl(self, **kwargs):
        if "ipfs_path" in list(kwargs.keys()):
            ipfs_path = kwargs["ipfs_path"]
        elif "ipfs_path" in list(self.__dict__.keys()):
            ipfs_path = self.ipfs_path
        try:
            os.makedirs(ipfs_path, exist_ok=True)
            if platform.system() == "Linux" and os.geteuid() == 0:
                run_ipfs_cluster_command = (
                    self.path_string
                    + " IPFS_CLUSTER_PATH="
                    + self.ipfs_path
                    + " ipfs-cluster-ctl --version"
                )
                run_ipfs_cluster_command_results = subprocess.check_output(
                    run_ipfs_cluster_command, shell=True
                )
                run_ipfs_cluster_command_results = run_ipfs_cluster_command_results.decode()

                run = (
                    self.path_string
                    + " IPFS_CLUSTER_PATH="
                    + self.ipfs_path
                    + " ipfs-cluster-ctl peers ls"
                )
                run_ipfs_cluster_command_results = subprocess.check_output(run, shell=True)
                run_ipfs_cluster_command_results = run_ipfs_cluster_command_results.decode()
                pass
            elif platform.system() == "Linux" and os.geteuid() != 0:
                run_ipfs_cluster_command = (
                    self.path_string
                    + " IPFS_CLUSTER_PATH="
                    + self.ipfs_path
                    + " ipfs-cluster-ctl --version"
                )
                run_ipfs_cluster_command_results = subprocess.check_output(
                    run_ipfs_cluster_command, shell=True
                )
                run_ipfs_cluster_command_results = run_ipfs_cluster_command_results.decode()

                run = (
                    self.path_string
                    + " IPFS_CLUSTER_PATH="
                    + self.ipfs_path
                    + " ipfs-cluster-ctl peers ls"
                )
                run_ipfs_cluster_command_results = subprocess.check_output(run, shell=True)
                run_ipfs_cluster_command_results = run_ipfs_cluster_command_results.decode()
                pass
            elif platform.system() == "Windows":
                run_ipfs_cluster_command = (
                    os.path.join(self.bin_path, "ipfs-cluster-ctl.exe") + " --version"
                )
                run_ipfs_cluster_command_results = subprocess.check_output(
                    run_ipfs_cluster_command, shell=True
                )
                run_ipfs_cluster_command_results = run_ipfs_cluster_command_results.decode()

                run = os.path.join(self.bin_path, "ipfs-cluster-ctl.exe") + " peers ls"
                run_ipfs_cluster_command_results = subprocess.check_output(run, shell=True)
                run_ipfs_cluster_command_results = run_ipfs_cluster_command_results.decode()
                pass
            elif platform.system() == "Darwin":
                run_ipfs_cluster_command = (
                    self.path_string
                    + " IPFS_CLUSTER_PATH="
                    + self.ipfs_path
                    + " ipfs-cluster-ctl --version"
                )
                run_ipfs_cluster_command_results = subprocess.check_output(
                    run_ipfs_cluster_command, shell=True
                )
                run_ipfs_cluster_command_results = run_ipfs_cluster_command_results.decode()

                run = (
                    self.path_string
                    + " IPFS_CLUSTER_PATH="
                    + self.ipfs_path
                    + " ipfs-cluster-ctl peers ls"
                )
                run_ipfs_cluster_command_results = subprocess.check_output(run, shell=True)
                run_ipfs_cluster_command_results = run_ipfs_cluster_command_results.decode()

        except Exception as e:
            run_ipfs_cluster_command_results = str(e)
            print("error running ipfs-cluster-ctl")
            print(e)
            return run_ipfs_cluster_command_results
        finally:
            pass

        return run_ipfs_cluster_command_results

    def remove_directory(self, dir_path):
        try:
            # get permissions of path
            if os.path.exists(dir_path):
                permissions = os.stat(dir_path)
                user_id = permissions.st_uid
                group_id = permissions.st_gid
                if platform.system() == "Windows":
                    my_user = os.getlogin()
                    my_group = os.getlogin()
                else:
                    my_user = os.getuid()
                    my_group = os.getgid()
                if user_id == my_user and os.access(dir_path, os.W_OK):
                    shutil.rmtree(dir_path)
                elif group_id == my_group and os.access(dir_path, os.W_OK):
                    shutil.rmtree(dir_path)
        except Exception as e:
            print("error removing directory " + dir_path)
            print(e)
            return False
        finally:
            return True

    def run_ipfs_cluster_follow(self, **kwargs):
        results = {}
        if "ipfs_path" in list(kwargs.keys()):
            ipfs_path = kwargs["ipfs_path"]
        elif "ipfs_path" in list(self.__dict__.keys()):
            ipfs_path = self.ipfs_path

        if not os.path.exists(ipfs_path):
            os.makedirs(ipfs_path, exist_ok=True)
            pass
        run_ipfs_cluster_follow_results = None
        try:
            if platform.system() == "Linux" and os.geteuid() == 0:
                start_daemon = "systemctl start ipfs-cluster-follow"
                start_daemon_results = subprocess.check_output(start_daemon, shell=True)
                start_daemon_results = start_daemon_results.decode()
                time.sleep(2)
                run_daemon = "systemctl status ipfs-cluster-follow"
                run_daemon_results = subprocess.check_output(run_daemon, shell=True)
                run_daemon_results = run_daemon_results.decode()
                find_daemon = "ps -ef | grep ipfs-cluster-follow | grep -v grep | wc -l"
                find_daemon_results = subprocess.check_output(find_daemon, shell=True)
                find_daemon_results = find_daemon_results.decode().strip()

                if int(find_daemon_results) == 0:
                    print("ipfs-cluster-follow daemon did not start")
                    raise Exception("ipfs-cluster-follow daemon did not start")
                else:
                    run_ipfs_cluster_follow_results = True
                pass
            elif platform.system() == "Linux" and os.geteuid() != 0:
                run_daemon_cmd = "ipfs-cluster-follow " + self.cluster_name + " run"
                run_daemon_results = subprocess.Popen(run_daemon_cmd, shell=True)
                if run_daemon_results is not None:
                    results["run_daemon"] = True
                    pass
                time.sleep(2)
                find_daemon = "ps -ef | grep ipfs-cluster-follow | grep -v grep | wc -l"
                find_daemon_results = subprocess.check_output(find_daemon, shell=True)
                find_daemon_results = find_daemon_results.decode().strip()

                if int(find_daemon_results) == 0:
                    print("ipfs-cluster-follow daemon did not start")
                    raise Exception("ipfs-cluster-follow daemon did not start")
                else:
                    run_ipfs_cluster_follow_results = True
                pass
            elif platform.system() == "Windows":
                run_daemon_cmd = (
                    os.path.join(self.bin_path, "ipfs-cluster-follow.exe")
                    + " "
                    + self.cluster_name
                    + " run"
                )
                run_daemon_results = subprocess.Popen(run_daemon_cmd, shell=True)
                if run_daemon_results is not None:
                    results["run_daemon"] = True
                    pass
                time.sleep(2)
                find_daemon = 'powershell -Command "(tasklist | findstr ipfs-cluster-follow).Count"'
                find_daemon_results = subprocess.check_output(find_daemon, shell=True)
                find_daemon_results = find_daemon_results.decode().strip()
                if int(find_daemon_results) == 0:
                    print("ipfs-cluster-follow daemon did not start")
                    raise Exception("ipfs-cluster-follow daemon did not start")
                else:
                    run_ipfs_cluster_follow_results = True
                pass
        except Exception as e:
            run_ipfs_cluster_follow_results = str(e)
            print("error running ipfs-cluster-follow")
            print(e)
            return False
        finally:
            return True

    def run_ipfs_daemon(self, **kwargs):
        if "ipfs_path" in list(kwargs.keys()):
            ipfs_path = kwargs["ipfs_path"]
        elif "ipfs_path" in list(self.__dict__.keys()):
            ipfs_path = self.ipfs_path
        try:
            if not os.path.exists(ipfs_path):
                os.makedirs(ipfs_path, exist_ok=True)
                pass
            run_ipfs_daemon_command = (
                self.path_string
                + " IPFS_PATH="
                + ipfs_path
                + " ipfs daemon --enable-pubsub-experiment"
            )
            run_ipfs_daemon_command_results = subprocess.Popen(run_ipfs_daemon_command, shell=True)
        except Exception as e:
            run_ipfs_daemon_command = str(e)
            print("error running ipfs daemon")
            print(e)
            return False
        finally:
            return True

    def kill_process_by_pattern(self, pattern):
        pids = None
        try:
            if platform.system() == "Windows":
                pid_cmds = "tasklist | findstr " + pattern
            else:
                pid_cmds = (
                    "ps -ef | grep "
                    + pattern
                    + " | grep -v grep | grep -v vscode | grep -v python3"
                )
            pids = subprocess.check_output(pid_cmds, shell=True)
            pids = pids.decode()
            pids = pids.split("\n")
        except Exception as e:
            pass
        finally:
            pass
        try:
            if pids is not None:
                for pid in pids:
                    while "  " in pid:
                        pid = pid.replace("  ", " ")
                    current_username = os.getlogin()
                    this_pid = None
                    if len(pid.split(" ")) > 1:
                        this_pid = pid.split(" ")[1]
                    if len(pid.split(" ")) > 0:
                        this_pid_user = pid.split(" ")[0]

                    if (this_pid != None and this_pid_user == current_username) or (
                        platform.system() == "Linux" and os.geteuid() == 0 and this_pid != None
                    ):
                        if platform.system() == "Windows":
                            kill_cmds = "taskkill /F /PID " + this_pid
                        else:
                            Tkill_cmds = "kill -9 " + this_pid
                        kill_results = subprocess.check_output(kill_cmds, shell=True)
                        kill_results = kill_results.decode()
                        pass

        except Exception as e:
            print("error killing process by pattern " + pattern)
            print(e)
            return False
        finally:
            return True

    def uninstall_ipfs_kit(self, **kwargs):
        home_dir = os.path.expanduser("~")
        self.kill_process_by_pattern("ipfs")
        self.remove_directory(self.ipfs_path)
        self.remove_directory(os.path.join(home_dir, ".ipfs-cluster-follow"))
        self.remove_directory(os.path.join(home_dir, ".ipfs-cluster"))
        self.remove_directory(os.path.join(home_dir, ".ipfs"))
        self.remove_binaries(
            "/usr/local/bin",
            ["ipfs", "ipget", "ipfs-cluster-service", "ipfs-cluster-ctl", "ipfs-cluster-follow"],
        )
        return True

    def uninstall_ipfs(self):
        try:
            self.kill_process_by_pattern("ipfs.daemon")
            detect_ipfs_command = None
            if platform.system() == "Darwin":
                detect_ipfs_command = "which ipfs"
            elif platform.system() == "Linux":
                detect_ipfs_command = "which ipfs"
            elif platform.system() == "Windows":
                detect_ipfs_command = "where ipfs"
            detect_ipfs_command_results = subprocess.check_output(detect_ipfs_command, shell=True)
            detect_ipfs_command_results = detect_ipfs_command_results.decode()
            self.remove_directory(detect_ipfs_command_results)
            self.remove_binaries(self.bin_path, ["ipfs"])
            if platform.system() == "Linux" and os.geteuid() == 0:
                self.remove_binaries("/etc/systemd/system", ["ipfs.service"])
            return True
        except Exception as e:
            results = str(e)
            return False
        finally:
            pass

    def uninstall_ipfs_cluster_service(self):

        try:
            self.kill_process_by_pattern("ipfs-cluster-service")
            detect_ipfs_cluster_service_cmd = None
            if platform.system() == "Windows":
                detect_ipfs_cluster_service_cmd = "where ipfs-cluster-service"
            else:
                detect_ipfs_cluster_service_cmd = "which ipfs-cluster-service"

            detect_ipfs_cluster_service_cmd_results = subprocess.check_output(
                detect_ipfs_cluster_service_cmd, shell=True
            )
            detect_ipfs_cluster_service_cmd_results = (
                detect_ipfs_cluster_service_cmd_results.decode()
            )
            self.remove_directory(detect_ipfs_cluster_service_cmd_results)
            self.remove_binaries(self.bin_path, ["ipfs-cluster-service"])
            if platform.system() == "Linux" and os.geteuid() == 0:
                self.remove_binaries("/etc/systemd/system", ["ipfs-cluster-service.service"])
            return True
        except Exception as e:
            results = str(e)
            return False
        finally:
            pass

    def uninstall_ipfs_cluster_follow(self):

        try:
            self.kill_process_by_pattern("ipfs-cluster-follow")
            detect_ipfs_cluster_follow_cmd = None
            if platform.system() == "Windows":
                detect_ipfs_cluster_follow_cmd = "where ipfs-cluster-follow"
            else:
                detect_ipfs_cluster_follow_cmd = "which ipfs-cluster-follow"
            detect_ipfs_cluster_follow_cmd_results = subprocess.check_output(
                detect_ipfs_cluster_follow_cmd, shell=True
            )
            detect_ipfs_cluster_follow_cmd_results = detect_ipfs_cluster_follow_cmd_results.decode()
            self.remove_directory(detect_ipfs_cluster_follow_cmd_results)
            self.remove_binaries(self.bin_path, ["ipfs-cluster-follow"])
            if platform.system() == "Linux" and os.geteuid() == 0:
                self.remove_binaries("/etc/systemd/system", ["ipfs-cluster-follow.service"])
            return True
        except Exception as e:
            results = str(e)
            return False
        finally:
            pass

    def uninstall_ipfs_cluster_ctl(self):
        try:
            self.kill_process_by_pattern("ipfs-cluster-ctl")
            detect_ipfs_cluster_ctl_cmd = None
            if platform.system() == "Windows":
                detect_ipfs_cluster_ctl_cmd = "where ipfs-cluster-ctl"
            else:
                detect_ipfs_cluster_ctl_cmd = "which ipfs-cluster-ctl"
            detect_ipfs_cluster_ctl_cmd_results = subprocess.check_output(
                detect_ipfs_cluster_ctl_cmd, shell=True
            )
            detect_ipfs_cluster_ctl_cmd_results = detect_ipfs_cluster_ctl_cmd_results.decode()
            self.remove_directory(detect_ipfs_cluster_ctl_cmd_results)
            self.remove_binaries(self.bin_path, ["ipfs-cluster-ctl"])
            return True
        except Exception as e:
            results = str(e)
            return False
        finally:
            pass

    def uninstall_ipget(self):
        try:
            self.kill_process_by_pattern("ipget")
            detect_ipget_command = None
            if platform.system() == "Windows":
                detect_ipget_command = "where ipget"
            else:
                detect_ipget_command = "which ipget"
            detect_ipget_command_results = subprocess.check_output(detect_ipget_command, shell=True)
            detect_ipget_command_results = detect_ipget_command_results.decode()
            self.remove_directory(detect_ipget_command_results)
            self.remove_binaries(self.bin_path, ["ipget"])
            return True
        except Exception as e:
            results = str(e)
            return False
        finally:
            pass

    def remove_binaries(self, bin_path, bin_list):
        try:
            for binary in bin_list:
                file_path = os.path.join(bin_path, binary)
                if os.path.exists(file_path):
                    binary_permission = os.stat(file_path)
                    user_id = binary_permission.st_uid
                    group_id = binary_permission.st_gid
                    if platform.system() == "Windows":
                        my_user = os.getlogin()
                        my_group = os.getlogin()
                    else:
                        my_user = os.getuid()
                        my_group = os.getgid()
                    parent_permissions = os.stat(bin_path)
                    parent_user = parent_permissions.st_uid
                    parent_group = parent_permissions.st_gid
                    if platform.system() == "Linux" and os.geteuid() == 0:
                        if (
                            user_id == my_user
                            and os.access(file_path, os.W_OK)
                            and parent_user == my_user
                            and os.access(bin_path, os.W_OK)
                        ):
                            rm_command = "chmod 777 " + file_path + " && rm -rf " + file_path
                            rm_results = subprocess.check_output(rm_command, shell=True)
                            rm_results = rm_results.decode()
                            pass
                        elif (
                            group_id == my_group
                            and os.access(file_path, os.W_OK)
                            and parent_group == my_group
                            and os.access(bin_path, os.W_OK)
                        ):
                            rm_command = "chmod 777 " + file_path + " && rm -rf " + file_path
                            rm_results = subprocess.check_output(rm_command, shell=True)
                            rm_results = rm_results.decode()
                            pass
                        rm_command = "rm -rf " + file_path + " && rm -rf " + file_path
                        rm_results = subprocess.check_output(rm_command, shell=True)
                        rm_results = rm_results.decode()
                        pass
                    elif platform.system() == "Windows":
                        if os.access(file_path, os.W_OK):
                            rm_command = "del /f " + file_path + " && del /f " + file_path
                            rm_results = subprocess.check_output(rm_command, shell=True)
                            rm_results = rm_results.decode()
                            pass
                        else:
                            print("insufficient permissions to remove " + file_path)
                            pass
                        pass
                    else:
                        print("insufficient permissions to remove " + file_path)
                        pass
        except Exception as e:
            print("error removing binaries")
            print(e)
            return False
        finally:
            return True
            pass

    def test_uninstall(self):
        results = {}
        ipfs_kit = self.uninstall_ipfs_kit()
        if self.role == "leecher" or self.role == "worker" or self.role == "master":
            results["ipfs"] = self.uninstall_ipfs()
            results["ipget"] = self.uninstall_ipget()
            pass
        if self.role == "worker":
            results["cluster_follow"] = self.uninstall_ipfs_cluster_follow()
            pass
        if self.role == "master":
            results["cluster_service"] = self.uninstall_ipfs_cluster_service()
            results["cluster_ctl"] = self.uninstall_ipfs_cluster_ctl()
            pass
        return results

    def install_executables(self, **kwargs):
        results = {}
        if self.role == "leecher" or self.role == "worker" or self.role == "master":
            ipfs = self.install_ipfs_daemon()
            results["ipfs"] = ipfs
        pass
        if self.role == "master":
            cluster_service = self.install_ipfs_cluster_service()
            cluster_ctl = self.install_ipfs_cluster_ctl()
            results["cluster_service"] = cluster_service
            results["cluster_ctl"] = cluster_ctl
            pass
        if self.role == "worker":
            cluster_follow = self.install_ipfs_cluster_follow()
            results["cluster_follow"] = cluster_follow
            pass
        return results

    def config_executables(self, **kwargs):
        results = {}
        if self.role == "leecher" or self.role == "worker" or self.role == "master":
            ipfs_config = self.config_ipfs(cluster_name=self.cluster_name, ipfs_path=self.ipfs_path)
            results["ipfs_config"] = ipfs_config["config"]
            pass
        if self.role == "master":
            cluster_service_config = self.config_ipfs_cluster_service(
                cluster_name=self.cluster_name, ipfs_path=self.ipfs_path
            )
            cluster_ctl_config = self.config_ipfs_cluster_ctl(
                cluster_name=self.cluster_name, ipfs_path=self.ipfs_path
            )
            results["cluster_service_config"] = cluster_service_config
            results["cluster_ctl_config"] = cluster_ctl_config
            pass
        if self.role == "worker":
            cluster_follow_config = self.config_ipfs_cluster_follow(
                cluster_name=self.cluster_name, ipfs_path=self.ipfs_path
            )
            results["cluster_follow_config"] = cluster_follow_config
            pass
        return results

    def ipfs_test_install(self):
        detect = 1  # Default to "not found"
        if platform.system() == "Darwin":
            detect = os.system("which ipfs")
        elif platform.system() == "Linux":
            detect = os.system("which ipfs")
        elif platform.system() == "Windows":
            detect = os.system("where ipfs")
        # os.system() returns 0 on success, non-zero on failure
        # 0 means binary was found, non-zero means not found
        if detect == 0:
            return True
        else:
            return False
        pass

    def ipfs_cluster_service_test_install(self):
        detect = 1  # Default to "not found"
        if platform.system() == "Darwin":
            detect = os.system("which ipfs-cluster-service")
        elif platform.system() == "Linux":
            detect = os.system("which ipfs-cluster-service")
        elif platform.system() == "Windows":
            detect = os.system("where ipfs-cluster-service")
        # os.system() returns 0 on success, non-zero on failure
        # 0 means binary was found, non-zero means not found
        if detect == 0:
            return True
        else:
            return False
        pass

    def ipfs_cluster_follow_test_install(self):
        detect = 1  # Default to "not found"
        if platform.system() == "Darwin":
            detect = os.system("which ipfs-cluster-follow")
        elif platform.system() == "Linux":
            detect = os.system("which ipfs-cluster-follow")
        elif platform.system() == "Windows":
            detect = os.system("where ipfs-cluster-follow")
        # os.system() returns 0 on success, non-zero on failure
        # 0 means binary was found, non-zero means not found
        if detect == 0:
            return True
        else:
            return False
        pass

    def ipfs_cluster_ctl_test_install(self):
        detect = 1  # Default to "not found"
        if platform.system() == "Darwin":
            detect = os.system("which ipfs-cluster-ctl")
        elif platform.system() == "Linux":
            detect = os.system("which ipfs-cluster-ctl")
        elif platform.system() == "Windows":
            detect = os.system("where ipfs-cluster-ctl")
        # os.system() returns 0 on success, non-zero on failure
        # 0 means binary was found, non-zero means not found
        if detect == 0:
            return True
        else:
            return False
        pass

    def ipget_test_install(self):
        detect = 1  # Default to "not found"
        if platform.system() == "Darwin":
            detect = os.system("which ipget")
        elif platform.system() == "Linux":
            detect = os.system("which ipget")
        elif platform.system() == "Windows":
            detect = os.system("where ipget")
        # os.system() returns 0 on success, non-zero on failure
        # 0 means binary was found, non-zero means not found
        if detect == 0:
            return True
        else:
            return False
        pass

    def install_and_configure(self, **kwargs):
        results = {}
        if self.role == "leecher" or self.role == "worker" or self.role == "master":
            ipget = self.install_ipget()
            ipfs = self.install_ipfs_daemon()
            ipfs_config = self.config_ipfs(cluster_name=self.cluster_name, ipfs_path=self.ipfs_path)
            ipfs_execute = self.run_ipfs_daemon()
            # NOTE: This fails some times but never when debugging so probably some sort of race issue
            results["ipfs"] = ipfs
            results["ipfs_config"] = ipfs_config["config"]
            results["ipfs_execute"] = ipfs_execute
            pass
        if self.role == "master":
            cluster_service = self.install_ipfs_cluster_service()
            cluster_ctl = self.install_ipfs_cluster_ctl()
            cluster_service_config = self.config_ipfs_cluster_service(
                cluster_name=self.cluster_name, ipfs_path=self.ipfs_path
            )
            cluster_ctl_config = self.config_ipfs_cluster_ctl(
                cluster_name=self.cluster_name, ipfs_path=self.ipfs_path
            )
            results["cluster_service"] = cluster_service
            results["cluster_ctl"] = cluster_ctl
            results["cluster_service_config"] = cluster_service_config
            results["cluster_ctl_config"] = cluster_ctl_config
            results["cluster_service_execute"] = self.run_ipfs_cluster_service()
            results["cluster_ctl_execute"] = self.run_ipfs_cluster_ctl()
            pass
        if self.role == "worker":
            cluster_follow = self.install_ipfs_cluster_follow()
            cluster_follow_config = self.config_ipfs_cluster_follow(
                cluster_name=self.cluster_name, ipfs_path=self.ipfs_path
            )
            results["cluster_follow"] = cluster_follow
            results["cluster_follow_config"] = cluster_follow_config
            results["cluster_follow__execute"] = self.run_ipfs_cluster_follow()
            pass
        self.kill_process_by_pattern("ipfs")
        self.kill_process_by_pattern("ipfs-cluster-follow")
        self.kill_process_by_pattern("ipfs-cluster-service")
        self.kill_process_by_pattern("ipfs-cluster-ctl")
        if platform.system() == "Linux" and os.geteuid() == 0:
            systemctl_reload = "systemctl daemon-reload"
            results["systemctl_reload"] = subprocess.run(systemctl_reload, shell=True)
        return results

    def test(self):
        results = {}
        try:
            this_install_ipfs = install_ipfs(None, metadata=metadata)
            results["uninstall"] = this_install_ipfs.test_uninstall()
            results["install"] = this_install_ipfs.install_and_configure()
        except Exception as e:
            import traceback

            error_output = traceback.format_exc()
            error_output += str(e)
            error_output += str(sys.exc_info()[-1].tb_lineno)
            results["error"] = error_output
            print(error_output)
        finally:
            print(results)
            with open("results.json", "w") as file:
                file.write(json.dumps(results))
            return results
        return None


if __name__ == "__main__":
    metadata = {
        "role": "master",
        "cluster_name": "cloudkit_storage",
        "cluster_location": "/ip4/167.99.96.231/tcp/9096/p2p/12D3KooWKw9XCkdfnf8CkAseryCgS3VVoGQ6HUAkY91Qc6Fvn4yv",
        # "cluster_location": "/ip4/167.99.96.231/udp/4001/quic-v1/p2p/12D3KooWS9pEXDb2FEsDv9TH4HicZgwhZtthHtSdSfyKKDnkDu8D",
        "config": None,
    }
    resources = {}
    install = install_ipfs(metadata, resources)
    results = install.test()
    print(results)
    pass
