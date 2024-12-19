import os
import subprocess
import tempfile
import json
import math
import sys
import time
import random
import shutil
import binascii

test_folder = os.path.dirname(os.path.dirname(__file__)) + "/test"
sys.path.append(test_folder)
from .test_fio import test_fio

class install_ipfs:
	def __init__(self, resources=None, metadata=None):
		self.resources = resources
		self.metadata = metadata
		self.install_ipfs_daemon = self.install_ipfs_daemon
		self.install_ipfs_cluster_follow = self.install_ipfs_cluster_follow
		self.install_ipfs_cluster_ctl = self.install_ipfs_cluster_ctl
		self.install_ipfs_cluster_service = self.install_ipfs_cluster_service
		self.env_path = os.environ.get('PATH', '')
		if "path" in list(metadata.keys()):
			self.path = metadata['path']
		else:
			self.path = self.env_path
		self.this_dir = os.path.dirname(os.path.realpath(__file__))
		self.path = self.path + ":" + os.path.join(self.this_dir, "bin")
		self.path_string = "PATH="+ self.path
		self.ipfs_dist_tar = "https://dist.ipfs.tech/kubo/v0.26.0/kubo_v0.26.0_linux-amd64.tar.gz"
		self.ipfs_follow_dist_tar = "https://dist.ipfs.tech/ipfs-cluster-follow/v1.0.8/ipfs-cluster-follow_v1.0.8_linux-amd64.tar.gz"
		self.ipfs_cluster_dist_tar = "https://dist.ipfs.tech/ipfs-cluster-ctl/v1.0.8/ipfs-cluster-ctl_v1.0.8_linux-amd64.tar.gz"
		self.ipfs_cluster_service_dist_tar = "https://dist.ipfs.tech/ipfs-cluster-service/v1.0.8/ipfs-cluster-service_v1.0.8_linux-amd64.tar.gz"
		self.ipfs_ipget_dist_tar = "https://dist.ipfs.tech/ipget/v0.10.0/ipget_v0.10.0_linux-amd64.tar.gz"
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
				self.role = metadata['role']
				if self.role not in  ["master","worker","leecher"]:
					raise Exception("role is not either master, worker, leecher")
			else:
				self.role = "leecher"
				pass

			if "ipfs_path" in list(metadata.keys()):
				self.ipfs_path = metadata['ipfs_path']
				if not os.path.exists(self.ipfs_path):
					os.makedirs(self.ipfs_path)
					pass
				test_disk = test_fio(None)
				self.disk_name = test_disk.disk_device_name_from_location(self.ipfs_path)
				self.disk_stats = {
					"disk_size": test_disk.disk_device_total_capacity(self.disk_name),
					"disk_used": test_disk.disk_device_used_capacity(self.disk_name),
					"disk_avail": test_disk.disk_device_avail_capacity(self.disk_name),
					"disk_name": self.disk_name
				}
				pass
			else:
				if os.name == 'nt':  # Windows
					self.ipfs_path = os.path.join(os.path.expanduser("~"), "AppData", "Local", "ipfs")
				else:  # Linux and other Unix-like systems
					if os.geteuid() == 0:
						self.ipfs_path = "/root/.cache/ipfs"
					else:
						self.ipfs_path = os.path.join(os.path.expanduser("~"), ".cache", "ipfs")
				if not os.path.exists(self.ipfs_path):
					os.makedirs(self.ipfs_path)
					pass
				test_disk = test_fio(None)
				self.disk_name = test_disk.disk_device_name_from_location(self.ipfs_path)
				self.disk_stats = {
					"disk_size": test_disk.disk_device_total_capacity(self.disk_name),
					"disk_used": test_disk.disk_device_used_capacity(self.disk_name),
					"disk_avail": test_disk.disk_device_avail_capacity(self.disk_name),
					"disk_name": self.disk_name
				}

			if "cluster_name" in list(metadata.keys()):
				self.cluster_name = metadata['cluster_name']
				pass					

			if "cluster_location" in list(metadata.keys()):
				self.cluster_location = metadata['cluster_location']
				pass

			if self.role in ["master","worker","leecher"] and self.ipfs_path is not None:
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
					self.cluster_name = metadata['cluster_name']
					self.cluster_ctl_install = self.install_ipfs_cluster_ctl
					self.cluster_ctl_config = self.config_ipfs_cluster_ctl
					self.cluster_service_install = self.install_ipfs_cluster_service
					self.cluster_service_config = self.config_ipfs_cluster_service
					pass
				pass

			if "config" in metadata:
				if metadata['config'] is not None:
					self.config = metadata['config']
				
			if "role" in metadata:
				if metadata['role'] is not None:
					self.role = metadata['role']
					if self.role not in  ["master","worker","leecher"]:
						raise Exception("role is not either master, worker, leecher")
					else:
						self.role = metadata['role']
						pass
				else:
					self.role = "leecher"

			if "ipfs_path" in metadata:
				if metadata['ipfs_path'] is not None:
					self.ipfs_path = metadata['ipfs_path']
					homedir_path = os.path.expanduser("~")

					#NOTE bug invalid permissions check
					if os.getuid != 0:
						if homedir_path in os.path.realpath(self.ipfs_path):
							if not os.path.exists(os.path.realpath(self.ipfs_path)):
								os.makedirs(self.ipfs_path)
					if os.getuid() == 0:
						if not os.path.exists(self.ipfs_path):
							os.makedirs(self.ipfs_path)
							pass
					#test_disk = test_fio.test_fio(None)
					test_disk = test_fio(None)
					self.disk_name = test_disk.disk_device_name_from_location(self.ipfs_path)
					self.disk_stats = {
						"disk_size": test_disk.disk_device_total_capacity(self.disk_name),
						"disk_used": test_disk.disk_device_used_capacity(self.disk_name),
						"disk_avail": test_disk.disk_device_avail_capacity(self.disk_name),
						"disk_name": self.disk_name
					}
					pass
				pass
			else:
				pass

			if "cluster_name" in metadata:
				if metadata['cluster_name'] is not None:
					self.cluster_name = metadata['cluster_name']
					pass
				pass
			else:
				self.cluster_name = None

			if "cluster_location" in metadata:
				if metadata['cluster_location'] is not None:
					self.cluster_location = metadata['cluster_location']
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
					self.cluster_name = metadata['cluster_name']
					self.cluster_ctl_install = self.install_ipfs_cluster_ctl
					self.cluster_ctl_config = self.config_ipfs_cluster_ctl
					self.cluster_service_install = self.install_ipfs_cluster_service
					self.cluster_service_config = self.config_ipfs_cluster_service
					pass
		if "cluster_location"  not in list(self.__dict__.keys()):
			self.cluster_location = "/ip4/167.99.96.231/tcp/9096/p2p/12D3KooWKw9XCkdfnf8CkAseryCgS3VVoGQ6HUAkY91Qc6Fvn4yv"
			pass
		self.bin_path = os.path.join(self.this_dir, "bin")
		self.tmp_path = "/tmp"
	
	def install_ipfs_daemon(self):
		try:
			detect = subprocess.check_output(self.path_string + " which ipfs",shell=True)
			detect = detect.decode()
			detect_len = len(detect)
			if len(detect) > 0:
				return True
		except Exception as e:
			detect = 0
			print(e)
		finally:
			pass
		if detect == 0:
			with tempfile.NamedTemporaryFile(suffix=".tar.gz", dir=self.tmp_path) as this_tempfile:
				command = "wget https://dist.ipfs.tech/kubo/v0.26.0/kubo_v0.26.0_linux-amd64.tar.gz -O " + this_tempfile.name
				results = subprocess.check_output(command, shell=True)
				results = results.decode()
				command = "tar -xvzf " + this_tempfile.name + " -C " + self.tmp_path
				results = subprocess.check_output(command, shell=True)
				results = results.decode()
				if (os.geteuid() == 0):
					#command = "cd /tmp/kubo ; sudo bash install.sh"
					command = "sudo bash " + os.path.join(self.tmp_path, "kubo", "install.sh")
					results = subprocess.check_output(command, shell=True)
					results = results.decode()
					command = "ipfs --version"
					results = subprocess.check_output(command, shell=True)
					results = results.decode()
					with open (os.path.join(self.this_dir, "ipfs.service"), "r") as file:
						ipfs_service = file.read()
					with open("/etc/systemd/system/ipfs.service", "w") as file:
						file.write(ipfs_service)
					command = "systemctl enable ipfs"
					subprocess.call(command, shell=True)
					pass
				else:
					#NOTE: Clean this up and make better logging or drop the error all together
					print('You need to be root to write to /etc/systemd/system/ipfs.service')
					command = 'cd ' + self.tmp_path + '/kubo && mkdir -p "'+ self.this_dir + '/bin/" && mv ipfs "' + self.this_dir+ '/bin/" && chmod +x "$'+ self.this_dir+'/bin/ipfs"'
					results = subprocess.check_output(command, shell=True)
					pass
			command = self.path_string + " ipfs --version"
			results = subprocess.check_output(command, shell=True)
			results = results.decode()
			if "ipfs" in results:
				return True
			else:
				return False
		else:
			return True

	def install_ipfs_cluster_follow(self):
		try:
			detect_command = self.path_string + " ipfs-cluster-follow --version"
			detect_command_results = subprocess.check_output(detect_command,shell=True)
			detect_command_results = detect_command_results.decode()
			if len(detect) > 0:
				print("ipfs-cluster-follow is already installed.")
				return True
		except Exception as e:
			detect = 0
			print(e)
		finally:
			pass
		if detect == 0:
			with tempfile.NamedTemporaryFile(suffix=".tar.gz", dir=self.tmp_path) as this_tempfile:
				url = self.ipfs_follow_dist_tar
				tar_path = os.path.join("tmp",this_tempfile.name)
				if self.this_dir is not None:
					this_dir = self.this_dir
				else:
					this_dir = os.path.dirname(os.path.realpath(__file__))
					 
				try:
					download_ipfs_cluster_follow = "wget " + url + " -O " + this_tempfile.name
					download_ipfs_cluster_follow_results = subprocess.check_output(download_ipfs_cluster_follow, shell=True)
					download_ipfs_cluster_follow_results = download_ipfs_cluster_follow_results.decode()

					if os.path.exists(os.path.join(self.tmp_path, "ipfs-cluster-follow")):
						remove_command = "rm -rf " + os.path.join(self.tmp_path, "ipfs-cluster-follow")
						remove_command_results = subprocess.check_output(remove_command, shell=True)
						remove_command_results = remove_command_results.decode()
						pass

					if not os.path.exists(os.path.join(self.tmp_path, "ipfs-cluster-follow")):
						os.makedirs(os.path.join(self.tmp_path, "ipfs-cluster-follow"))
						pass

					expand_command = "tar -xvzf " + this_tempfile.name + " -C " + self.tmp_path
					expand_command_results = subprocess.check_output(expand_command, shell=True)
					expand_command_results = expand_command_results.decode()
					
					if os.geteuid() == 0:
						move_command = "sudo mv " + os.path.join(os.path.join(self.tmp_path,'ipfs-cluster-follow'),'ipfs-cluster-follow') + " " + "/usr/local/bin/ipfs-cluster-follow"
						move_command_results = subprocess.check_output(move_command, shell=True).decode()

						with open(os.path.join(this_dir, "ipfs-cluster-follow.service"), "r") as file:
							ipfs_cluster_follow = file.read()
						with open("/etc/systemd/system/ipfs-cluster-follow.service", "w") as file:
							file.write(ipfs_cluster_follow)
						systemctl_enable_command = "systemctl enable ipfs-cluster-follow"
						systemctl_enable_command_results = subprocess.call(systemctl_enable_command, shell=True)
						pass
					else:
						move_command = "mv " + os.path.join(self.tmp_path, "ipfs-cluster-follow","ipfs-cluster-follow") + " " + os.path.join( self.this_dir , "bin" , "ipfs-cluster-follow" )
						move_command_results = subprocess.check_output(move_command, shell=True)
						move_command_results = move_command_results.decode()
						pass

				except Exception as e:
					print(e)
					pass

				version_command = self.path_string + " ipfs-cluster-follow --version"
				version_command_results = subprocess.check_output(version_command, shell=True)
				version_command_results = version_command_results.decode()
				
				if "ipfs-cluster-follow" in version_command_results:
					return True
				else:
					return False
	
	def install_ipfs_cluster_ctl(self):
		try:
			detect = subprocess.check_output(self.path_string + " which ipfs-cluster-ctl",shell=True)
			detect = detect.decode()
			if len(detect) > 0:
				return True
		except Exception as e:
			detect = 0
			print(e)
		finally:
			pass
		url = self.ipfs_cluster_dist_tar
		with tempfile.NamedTemporaryFile(suffix=".tar.gz", dir=self.tmp_path) as this_tempfile:

			command = "wget " + url + " -O " + this_tempfile.name
			results = subprocess.check_output(command, shell=True)
			results = results.decode()

			command = "tar -xvzf " + this_tempfile.name + " -C " + self.tmp_path
			results = subprocess.check_output(command, shell=True)
			results = results.decode()
			if os.geteuid() == 0:
				# command = "cd /tmp/ipfs-cluster-ctl ; sudo mv ipfs-cluster-ctl /usr/local/bin/ipfs-cluster-ctl"
				command = "sudo mv " + os.path.join(self.tmp_path,"ipfs-cluster-ctl","ipfs-cluster-ctl") + " " + " /usr/local/bin/ipfs-cluster-ctl"
				results = subprocess.check_output(command, shell=True)
				results = results.decode()
			else:
				if not os.path.exists(os.path.join(self.this_dir, "bin")):
					os.makedirs(os.path.join(self.this_dir, "bin"))
					pass
				command = "mv " + os.path.join(self.tmp_path,"ipfs-cluster-ctl","ipfs-cluster-ctl") + " " + os.path.join(self.this_dir, "bin", "ipfs-cluster-ctl")
				results = subprocess.check_output(command, shell=True)
				results = results.decode()

			command = self.path_string + " ipfs-cluster-ctl --version"
			results = subprocess.check_output(command, shell=True)
			results = results.decode()
			if "ipfs-cluster-ctl" in results:
				return True
			else:
				return False
	
	def install_ipfs_cluster_service(self):
		try:
			detect = subprocess.check_output(self.path_string + " which ipfs-cluster-service",shell=True)
			detect = detect.decode()
			if len(detect) > 0:
				return True
		except Exception as e:
			detect = 0
			print(e)
		finally:
			pass
		if detect == 0:
			with tempfile.NamedTemporaryFile(suffix=".tar.gz", dir=self.tmp_path) as this_tempfile:
				url = self.ipfs_cluster_service_dist_tar
				command = "wget " + url + " -O " + this_tempfile.name
				results = subprocess.check_output(command, shell=True)
				results = results.decode()
				command = "tar -xvzf " + this_tempfile.name + " -C /tmp"
				results = subprocess.check_output(command, shell=True)
				results = results.decode()
				if os.geteuid() == 0:
					# command = "cd /tmp/ipfs-cluster-service ; sudo mv ipfs-cluster-service /usr/local/bin/ipfs-cluster-service"
					command = "mv " + os.path.join(self.tmp_path ,'ipfs-cluster-service','ipfs-cluster-service') + " " + "/usr/local/bin/ipfs-cluster-service"
					results = subprocess.check_output(command, shell=True)
					results = results.decode()
					with open(os.path.join(self.this_dir, "ipfs-cluster-service.service"), "r") as file:
						ipfs_cluster_service = file.read()
					with open("/etc/systemd/system/ipfs-cluster-service.service", "w") as file:
						file.write(ipfs_cluster_service)
					command = "systemctl enable ipfs-cluster-service"
					subprocess.call(command, shell=True)
				else:
					command = "mv " + os.path.join(self.tmp_path,'ipfs-cluster-service','ipfs-cluster-service') + " " + os.path.join(self.this_dir,"bin","ipfs-cluster-service")
					results = subprocess.check_output(command, shell=True)
					results = results.decode()

				command = self.path_string + " ipfs-cluster-service --version"
				results = subprocess.check_output(command, shell=True)
				results = results.decode()
				
				if "ipfs-cluster-service" in results:
					return True
				else:
					return False

	def install_ipget(self):
		try:
			detect = subprocess.check_output(self.path_string + " which ipget",shell=True)
			detect = detect.decode()
			detect_len = len(detect)
			if len(detect) > 0:
				return True
		except Exception as e:
			detect = 0
			print(e)
		finally:
			pass
		if detect == 0:
			with tempfile.NamedTemporaryFile(suffix=".tar.gz", dir=self.tmp_path) as this_tempfile:
				url = self.ipfs_ipget_dist_tar
				command = "wget " + url + " -O " + this_tempfile.name
				results = subprocess.check_output(command, shell=True)
				results = results.decode()
				command = "tar -xvzf " + this_tempfile.name + " -C " + self.tmp_path
				results = subprocess.check_output(command, shell=True)
				results = results.decode()
				# command = "cd /tmp/ipget ; sudo bash install.sh"
				if os.getegid() == 0:
					command = "cd sudo bash " + os.path.join(self.tmp_path, "ipget", "install.sh")
					results = subprocess.check_output(command, shell=True)
					results = results.decode()
					command = "sudo sysctl -w net.core.rmem_max=2500000"
					results = subprocess.check_output(command, shell=True)
					results = results.decode()
					command = "sudo sysctl -w net.core.wmem_max=2500000"
					results = subprocess.check_output(command, shell=True)
					results = results.decode()
				else:
					command = 'cd ' + self.tmp_path + '/ipget && mv ipget "' + self.this_dir + '/bin/" && chmod +x "' + self.this_dir + '/bin/ipget"'
					results = subprocess.call(command, shell=True)
					results = results.decode()

				command = "ipget --version"
				results = subprocess.check_output(command, shell=True)
				results = results.decode()
				if "ipget" in results:
					return True
				else:
					return False

	def config_ipfs_cluster_service(self, **kwargs):
		cluster_name = None
		secret = None
		disk_stats = None
		ipfs_path = None
		
		if "secret" in list(kwargs.keys()):
			secret = kwargs['secret']
		elif "secret" in list(self.__dict__.keys()):
			secret = self.secret
		
		if "cluster_name" in list(kwargs.keys()):
			cluster_name = kwargs['cluster_name']
			self.cluster_name = cluster_name
		elif "cluster_name" in list(self.__dict__.keys()):
			cluster_name = self.cluster_name
		
		
		if "disk_stats" in list(kwargs.keys()):
			disk_stats = kwargs['disk_stats']
			self.disk_stats = disk_stats
		elif "disk_stats" in list(self.__dict__.keys()):
			disk_stats = self.disk_stats

		if "ipfs_path" in list(kwargs.keys()):
			ipfs_path = kwargs['ipfs_path']
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
			if os.geteuid() == 0:
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
				if os.geteuid() == 0:
					enable_cluster_service = "systemctl enable ipfs-cluster"
					enable_cluster_service_results = subprocess.check_output(enable_cluster_service, shell=True)
					enable_cluster_service_results = enable_cluster_service_results.decode()					
					with open(os.path.join(self.this_dir, "service.json"), "r") as file:
						ipfs_cluster_service = file.read()
					with open(service_path + "/service.json", "w") as file:
						file.write(ipfs_cluster_service)
					init_cluster_service =  self.path_string + " IPFS_PATH="+ ipfs_path +" ipfs-cluster-service init -f"
					init_cluster_service_results = subprocess.check_output(init_cluster_service, shell=True)
					init_cluster_service_results = init_cluster_service_results.decode()
					pass
				else:
					init_cluster_service = self.path_string + " IPFS_PATH="+ ipfs_path +" ipfs-cluster-service init -f"
					init_cluster_service_results = subprocess.check_output(init_cluster_service, shell=True)
					init_cluster_service_results = init_cluster_service_results.decode()
					pass
		except Exception as e:
			print(e)
			init_cluster_service_results = str(e)
		finally:
			pass
		results["init_cluster_service_results"] = init_cluster_service_results
		if (self.role == "worker" or self.role == "master"):
			try:
				service_config = ""
				workerID = random.randbytes(32)
				workerID = "worker-" + binascii.hexlify(workerID).decode()
				with open(os.path.join(self.this_dir, "service.json")) as file:
					service_config = file.read()
				service_config = service_config.replace('"cluster_name": "ipfs-cluster"', '"cluster_name": "'+cluster_name+'"')				
				service_config = service_config.replace('"secret": "96d5952479d0a2f9fbf55076e5ee04802f15ae5452b5faafc98e2bd48cf564d3"', '"secret": "'+ secret +'"')
				with open(os.path.join(service_path , "service.json"), "w") as file:
					file.write(service_config)	
				with open(os.path.join(this_dir, "peerstore"), "r") as file:
					peerlist = file.read()
				with open(service_path + "/peerstore", "w") as file:
					file.write(peerlist)

				pebble_link = os.path.join(service_path,"pebble")
				pebble_dir = os.path.join(cluster_path, "pebble")

				if cluster_path != service_path:
					if os.path.exists(pebble_link) or os.path.islink(pebble_link):
						remove_pebble_command = "rm -rf " + pebble_link
						remove_pebble_command_results = subprocess.check_output(remove_pebble_command, shell=True)
						remove_pebble_command_results = remove_pebble_command_results.decode()
						pass
					# link_pebble_command = "ln -s " + pebble_dir + " " + pebble_link
					# link_pebble_command_results = subprocess.check_output(link_pebble_command, shell=True)
					# link_pebble_command_results = link_pebble_command_results.decode()
					# pass

				if os.geteuid() == 0:
					with open(os.path.join(this_dir, "ipfs-cluster.service"), "r") as file:
						service_file = file.read()

					# service_file = service_file.replace("ExecStart=/usr/local/bin/ipfs-cluster-service daemon", "ExecStart=/usr/local/bin/ipfs-cluster-service daemon --peerstore "+ service_path + "/peerstore --service "+ service_path + "/service.json")
					service_file = service_file.replace("ExecStart=/usr/local/bin/", "ExecStart= bash -c \"export IPFS_PATH="+ ipfs_path + " && export PATH=" + self.path + " && ipfs-cluster-service daemon \"")
					with open("/etc/systemd/system/ipfs-cluster.service", "w") as file:
						file.write(service_file)
					enable_cluster_service = "systemctl enable ipfs-cluster"
					enable_cluster_service_results = subprocess.check_output(enable_cluster_service, shell=True)
					enable_cluster_service_results = enable_cluster_service_results.decode()

					systemctl_daemon_reload = "systemctl daemon-reload"
					systemctl_daemon_reload_results = subprocess.check_output(systemctl_daemon_reload, shell=True)
					systemctl_daemon_reload_results = systemctl_daemon_reload_results.decode()
					pass
			except Exception as e:
				raise Exception(str(e))
			finally:
				pass
			pass
		try:
			run_daemon_results = ""
			get_euid = os.geteuid()
			if os.geteuid() == 0:
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
			else:
				run_daemon_cmd = self.path_string + " ipfs-cluster-service -d daemon "
				run_daemon_results = subprocess.Popen(run_daemon_cmd, shell=True)
				time.sleep(5)
				find_daemon_command = "ps -ef | grep ipfs-cluster-service | grep -v grep | wc -l"
				find_daemon_command_results = subprocess.check_output(find_daemon_command, shell=True)
				find_daemon_command_results = find_daemon_command_results.decode().strip()
				results["run_daemon"] = find_daemon_command_results

				if int(find_daemon_command_results) > 0:
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

		return results
	
	def config_ipfs_cluster_ctl(self, **kwargs):
		results = {}

		cluster_name = None
		secret = None
		disk_stats = None
		ipfs_path = None
		
		if "cluster_name" in list(kwargs.keys()):
			cluster_name = kwargs['cluster_name']
			self.cluster_name = cluster_name
		elif "cluster_name" in list(self.__dict__.keys()):
			cluster_name = self.cluster_name
		
		if "disk_stats" in list(kwargs.keys()):
			disk_stats = kwargs['disk_stats']
			self.disk_stats = disk_stats
		elif "disk_stats" in list(self.__dict__.keys()):
			disk_stats = self.disk_stats

		if "ipfs_path" in list(kwargs.keys()):
			ipfs_path = kwargs['ipfs_path']
			self.ipfs_path = ipfs_path
		elif "ipfs_path" in list(self.__dict__.keys()):
			ipfs_path = self.ipfs_path
		
		if "secret" in list(kwargs.keys()):
			secret = kwargs['secret']
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
			cluster_name = kwargs['cluster_name']
			self.cluster_name = cluster_name
		elif "cluster_name" in list(self.__dict__.keys()):
			cluster_name = self.cluster_name
		
		if "disk_stats" in list(kwargs.keys()):
			disk_stats = kwargs['disk_stats']
			self.disk_stats = disk_stats
		elif "disk_stats" in list(self.__dict__.keys()):
			disk_stats = self.disk_stats

		if "ipfs_path" in list(kwargs.keys()):
			ipfs_path = kwargs['ipfs_path']
			self.ipfs_path = ipfs_path
		elif "ipfs_path" in list(self.__dict__.keys()):
			ipfs_path = self.ipfs_path
		
		if "secret" in list(kwargs.keys()):
			secret = kwargs['secret']
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
		cluster_path = os.path.join(os.path.dirname(ipfs_path),'ipfs-cluster', cluster_name)
		follow_path = os.path.join(ipfs_path, "ipfs_cluster") + "/"		
		run_daemon = None
		follow_init_cmd_results = None
		worker_id = random.randbytes(32)
		worker_id = "worker-" + binascii.hexlify(worker_id).decode()
		follow_path = None
		if os.geteuid() == 0:
			follow_path = os.path.join("/root", ".ipfs-cluster-follow", cluster_name) + "/"
		else:
			follow_path = os.path.join(os.path.expanduser("~"), ".ipfs-cluster-follow", cluster_name)

		if (cluster_name is not None and ipfs_path is not None and disk_stats is not None):
			try:
				rm_command = "rm -rf " + follow_path
				rm_results = subprocess.check_output(rm_command, shell=True)
				rm_results = rm_results.decode()
				follow_init_cmd = "ipfs-cluster-follow " + cluster_name + " init " + ipfs_path
				follow_init_cmd_results = subprocess.check_output(follow_init_cmd, shell=True).decode()
				if not os.path.exists(cluster_path):
					os.makedirs(cluster_path)
					pass
				if not os.path.exists(follow_path):
					os.makedirs(follow_path)
					pass
				with open(os.path.join(this_dir, "service_follower.json"), "r") as file:
					service_config = file.read()
				service_config = service_config.replace('"cluster_name": "ipfs-cluster"', '"cluster_name": "'+cluster_name+'"')				
				service_config = service_config.replace('"peername": "worker"', '"peername": "'+worker_id+'"')
				service_config = service_config.replace('"secret": "96d5952479d0a2f9fbf55076e5ee04802f15ae5452b5faafc98e2bd48cf564d3"', '"secret": "'+ secret +'"')
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
						command2 = "rm -rf " + pebble_link
						results2 = subprocess.check_output(command2, shell=True)
						results2 = results2.decode()
						pass
					if not os.path.exists(pebble_dir):
						os.makedirs(pebble_dir)
						pass
					command3 = "ln -s " + pebble_dir + " " + pebble_link
					results3 = subprocess.check_output(command3, shell=True)
					results3 = results3.decode()
					pass
				if os.geteuid() == 0:
					with open(os.path.join(this_dir, "ipfs-cluster-follow.service"), "r") as file:
						service_file = file.read()
					# new_service = service_file.replace("ExecStart=/usr/local/bin/ipfs-cluster-follow run","ExecStart=/usr/local/bin/ipfs-cluster-follow "+ cluster_name + " run")
					new_service = service_file.replace("ExecStart=",'ExecStart= bash -c "export IPFS_PATH='+ ipfs_path + ' && export PATH=' + self.path + " && /usr/local/bin/ipfs-cluster-follow " + cluster_name + " run \"")
					new_service = new_service.replace("Description=IPFS Cluster Follow","Description=IPFS Cluster Follow "+ cluster_name)
					with open("/etc/systemd/system/ipfs-cluster-follow.service", "w") as file:
						file.write(new_service)
					enable_ipfs_cluster_follow_service = "systemctl enable ipfs-cluster-follow"
					enable_ipfs_cluster_follow_service_results = subprocess.check_output(enable_ipfs_cluster_follow_service, shell=True)
					enable_ipfs_cluster_follow_service_results = enable_ipfs_cluster_follow_service_results.decode()
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

		try:
			find_daemon = "ps -ef | grep ipfs-cluster-follow | grep -v grep | wc -l"
			find_daemon_results = subprocess.check_output(find_daemon, shell=True)
			find_daemon_results = find_daemon_results.decode().strip()
			if int(find_daemon_results) > 0:
				self.kill_process_by_pattern("ipfs-cluster-follow")
				pass
			run_daemon_results = None
			if os.geteuid() == 0:
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
			else:
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
		
		if "cluster_name" in list(kwargs.keys()):
			cluster_name = kwargs['cluster_name']
			self.cluster_name = cluster_name
		elif "cluster_name" in list(self.__dict__.keys()):
			cluster_name = self.cluster_name
		
		if "disk_stats" in list(kwargs.keys()):
			disk_stats = kwargs['disk_stats']
			self.disk_stats = disk_stats
		elif "disk_stats" in list(self.__dict__.keys()):
			disk_stats = self.disk_stats

		if "ipfs_path" in list(kwargs.keys()):
			ipfs_path = kwargs['ipfs_path']
			self.ipfs_path = ipfs_path
		elif "ipfs_path" in list(self.__dict__.keys()):
			ipfs_path = self.ipfs_path
		
		if "secret" in list(kwargs.keys()):
			secret = kwargs['secret']
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
			print("ipfs directory is not empty")
			for del_file in ipfs_dir_contents:
				if os.path.isfile(del_file):
					os.remove(del_file)
					pass
				elif os.path.isdir(del_file):
					shutil.rmtree(del_file)
					pass
				else:
					print("unknown file type " + del_file + " in ipfs directory")
					pass
			pass
		
			results = {
				"config" : None,
				"identity": None,
				"public_key": None
			}

		if disk_stats is not None and ipfs_path is not None:
			try:
				peer_id = None
				disk_available = None

				min_free_space = 32 * 1024 * 1024 * 1024
				allocate = None
				disk_available = self.disk_stats['disk_avail']

				ipfs_init_command = self.path_string + ' IPFS_PATH='+ self.ipfs_path + ' ipfs init --profile=badgerds'
				ipfs_init_results = subprocess.check_output(ipfs_init_command, shell=True)
				ipfs_init_results = ipfs_init_results.decode().strip()

				peer_id_command = self.path_string + ' IPFS_PATH='+ self.ipfs_path + ' ipfs id'
				peer_id_results = subprocess.check_output(peer_id_command, shell=True)
				peer_id_results = peer_id_results.decode()
				peer_id = json.loads(peer_id_results)

				ipfs_profile_apply = self.path_string + ' IPFS_PATH='+ self.ipfs_path + ' ipfs config profile apply badgerds'
				ipfs_profile_apply_results = subprocess.check_output(ipfs_profile_apply, shell=True)
				ipfs_profile_apply_results = ipfs_profile_apply_results.decode()
				ipfs_profile_apply_json = json.loads(ipfs_profile_apply_results)

				if disk_available > min_free_space:
					allocate = math.ceil((( disk_available - min_free_space) * 0.8) / 1024 / 1024 / 1024)
					datastore_command = self.path_string + " IPFS_PATH="+ self.ipfs_path +" ipfs config Datastore.StorageMax " + str(allocate) + "GB"
					datastore_command_results = subprocess.check_output(datastore_command, shell=True)
					datastore_command_results = datastore_command_results.decode()
					pass


				peer_list_path = os.path.join(this_dir, "peerstore")
				if os.path.exists(peer_list_path):
					with open(peer_list_path, "r") as file:
						peerlist = file.read()
					peerlist = peerlist.split("\n")
					for peer in peerlist:
						if peer != "":
							bootstrap_add_command = self.path_string + " IPFS_PATH="+ self.ipfs_path + " ipfs bootstrap add " + peer
							bootstrap_add_command_results = subprocess.check_output(bootstrap_add_command, shell=True)
							bootstrap_add_command_results = bootstrap_add_command_results.decode()
							pass
						pass

				if os.geteuid() == 0:
					with open(os.path.join(self.this_dir, "ipfs.service"), "r") as file:
						ipfs_service = file.read()
					ipfs_service_text = ipfs_service.replace("ExecStart=","ExecStart= bash -c \"export IPFS_PATH="+ ipfs_path + " && export PATH=" + self.path + " && ipfs daemon --enable-gc --enable-pubsub-experiment \"")
					with open("/etc/systemd/system/ipfs.service", "w") as file:
						file.write(ipfs_service_text)
					pass
				
				config_get_cmd = self.path_string + ' IPFS_PATH='+ self.ipfs_path + ' ipfs config show'
				config_data = subprocess.check_output(config_get_cmd, shell=True)
				config_data = config_data.decode()
				config_data = json.loads(config_data)
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
		if os.geteuid() == 0:
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
									
					test_daemon = 'bash -c "export IPFS_PATH='+ ipfs_path + ' && export PATH=' + self.path + ' && ipfs cat /ipfs/QmSgvgwxZGaBLqkGyWemEDqikCqU52XxsYLKtdy3vGZ8uq > /tmp/test.jpg"'
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
					find_daemon_results = subprocess.check_output(find_daemon_cmd, shell=True).decode().strip()
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
		else:
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
			run_daemon_cmd = self.path_string + ' IPFS_PATH='+ self.ipfs_path + ' ipfs daemon --enable-pubsub-experiment'
			run_daemon = subprocess.Popen(run_daemon_cmd, shell=True)
			time.sleep(5)
			find_daemon_results = subprocess.check_output(find_daemon_cmd, shell=True)	
			find_daemon_results = find_daemon_results.decode().strip()
			test_daemon_results = None
			try:
				if os.path.exists("/tmp/test.jpg"):
					os.remove("/tmp/test.jpg")
					pass

				test_daemon = 'bash -c "IPFS_PATH='+ self.ipfs_path + ' PATH='+ self.path +' ipfs cat /ipfs/QmSgvgwxZGaBLqkGyWemEDqikCqU52XxsYLKtdy3vGZ8uq > /tmp/test.jpg"'
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
			if results["identity"] is not None and results["identity"] != "" and len(results["identity"]) == 52:
				identity = results["identity"]
				config = results["config"]
				if "PrivKey" in list(config["Identity"].keys()):
					private_key = config["Identity"]["PrivKey"]
				ipfs_daemon = test_daemon_results
				pass

		self.kill_process_by_pattern("ipfs")
		results = {
				"config":config,
				"identity":identity,
				# "public_key":private_key,
				"public_key": None,
                "ipfs_daemon":ipfs_daemon
			}

		return results
		
	def run_ipfs_cluster_service(self, **kwargs):
		if "ipfs_path" in list(kwargs.keys()):
			ipfs_path = kwargs['ipfs_path']
		elif "ipfs_path" in list(self.__dict__.keys()):
			ipfs_path = self.ipfs_path
		try:			
			ipfs_path = os.path.join(ipfs_path, "ipfs")
			if not os.path.exists(ipfs_path):
				os.makedirs(ipfs_path, exist_ok=True)
			run_command = self.path_string + " ipfs-cluster-service -d daemon "
			# run_command = self.path_string + " IPFS_CLUSTER_PATH="+ self.ipfs_path +" ipfs-cluster-service daemon"
			run_command_results = subprocess.Popen(run_command, shell=True)
			time.sleep(2)
			find_daemon = "ps -ef | grep ipfs-cluster-service | grep -v grep | wc -l"
			find_daemon_results = subprocess.check_output(find_daemon, shell=True)
			find_daemon_results = find_daemon_results.decode().strip()
			if int(find_daemon_results) == 0:
				raise Exception("ipfs-cluster-service daemon did not start")
		except Exception as e:
			run_command_results = str(e)
			print("error running ipfs-cluster-service")
			print(e)
		finally:
			pass

		return run_command_results
	
	def run_ipfs_cluster_ctl(self, **kwargs):
		if "ipfs_path" in list(kwargs.keys()):
			ipfs_path = kwargs['ipfs_path']
		elif "ipfs_path" in list(self.__dict__.keys()):
			ipfs_path = self.ipfs_path          
		try:
			os.makedirs(ipfs_path, exist_ok=True)

			run_ipfs_cluster_command = self.path_string + " IPFS_CLUSTER_PATH="+ self.ipfs_path +" ipfs-cluster-ctl --version"
			run_ipfs_cluster_command_results = subprocess.check_output(run_ipfs_cluster_command, shell=True)
			run_ipfs_cluster_command_results = run_ipfs_cluster_command_results.decode()

			run = self.path_string + " IPFS_CLUSTER_PATH="+ self.ipfs_path +" ipfs-cluster-ctl peers ls"
			run_ipfs_cluster_command_results = subprocess.check_output(run, shell=True)
			run_ipfs_cluster_command_results = run_ipfs_cluster_command_results.decode()

		except Exception as e:
			run_ipfs_cluster_command_results = str(e)
			print("error running ipfs-cluster-ctl")
			print(e)
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
		if "ipfs_path" in list(kwargs.keys()):
			ipfs_path = kwargs['ipfs_path']
		elif "ipfs_path" in list(self.__dict__.keys()):
			ipfs_path = self.ipfs_path          
			
		if not os.path.exists(ipfs_path):
			os.makedirs(ipfs_path, exist_ok=True)
			pass
		run_ipfs_cluster_follow_results = None
		try:
			if os.geteuid() == 0:
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
			else:
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

		except Exception as e:
			run_ipfs_cluster_follow_results = str(e)
			print("error running ipfs-cluster-follow")
			print(e)
			return False
		finally:
			return True

	
	def run_ipfs_daemon(self, **kwargs):
		if "ipfs_path" in list(kwargs.keys()):
			ipfs_path = kwargs['ipfs_path']
		elif "ipfs_path" in list(self.__dict__.keys()):
			ipfs_path = self.ipfs_path
		try:
			if not os.path.exists(ipfs_path):
				os.makedirs(ipfs_path, exist_ok=True)
				pass
			run_ipfs_daemon_command = self.path_string + " IPFS_PATH="+ ipfs_path + " ipfs daemon --enable-pubsub-experiment"
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
			pid_cmds = 'ps -ef | grep ' + pattern + ' | grep -v grep | grep -v vscode | grep -v python3'
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

					if (this_pid != None and this_pid_user == current_username) or os.geteuid() == 0 and this_pid != None:
						kill_cmds = 'kill -9 ' + this_pid
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
		self.kill_process_by_pattern('ipfs')
		self.remove_directory(self.ipfs_path)
		self.remove_directory(os.path.join(home_dir, '.ipfs-cluster-follow' ))
		self.remove_directory(os.path.join(home_dir, '.ipfs-cluster' ))
		self.remove_directory(os.path.join(home_dir, '.ipfs' ))
		self.remove_binaries('/usr/local/bin', ['ipfs', 'ipget', 'ipfs-cluster-service', 'ipfs-cluster-ctl', 'ipfs-cluster-follow'])
		return True
	
	def uninstall_ipfs(self):
		try:
			self.kill_process_by_pattern('ipfs.daemon')
			which_command = "which ipfs"
			which_command_results = subprocess.check_output(which_command, shell=True)
			which_command_results = which_command_results.decode()
			self.remove_directory(which_command_results)			
			self.remove_binaries(self.bin_path, ['ipfs'])
			if os.geteuid() == 0:
				self.remove_binaries('/etc/systemd/system', ['ipfs.service'])			
			return True
		except Exception as e:
			results = str(e)
			return False
		finally:
			pass

	def uninstall_ipfs_cluster_service(self):
		try:
			self.kill_process_by_pattern('ipfs-cluster-service')			
			which_command = "which ipfs-cluster-service"
			which_command_results = subprocess.check_output(which_command, shell=True)
			which_command_results = which_command_results.decode()
			self.remove_directory(which_command_results)			
			self.remove_binaries(self.bin_path, ['ipfs-cluster-service'])
			if os.geteuid() == 0:
				self.remove_binaries('/etc/systemd/system', ['ipfs-cluster-service.service'])
			return True
		except Exception as e:
			results = str(e)
			return False
		finally:
			pass

	def uninstall_ipfs_cluster_follow(self):
		try:
			self.kill_process_by_pattern('ipfs-cluster-follow')
			which_command = "which ipfs-cluster-follow"
			which_command_results = subprocess.check_output(which_command, shell=True)
			which_command_results = which_command_results.decode()
			self.remove_directory(which_command_results)
			self.remove_binaries(self.bin_path, ['ipfs-cluster-follow'])
			if os.geteuid() == 0:
				self.remove_binaries('/etc/systemd/system', ['ipfs-cluster-follow.service'])
			return True
		except Exception as e:
			results = str(e)
			return False
		finally:
			pass


	def uninstall_ipfs_cluster_ctl(self):
		try:
			self.kill_process_by_pattern('ipfs-cluster-ctl')
			which_command = "which ipfs-cluster-ctl"
			which_command_results = subprocess.check_output(which_command, shell=True)
			which_command_results = which_command_results.decode()
			self.remove_directory(which_command_results)
			self.remove_binaries(self.bin_path, ['ipfs-cluster-ctl'])
			return True
		except Exception as e:
			results = str(e)
			return False
		finally:
			pass

	def uninstall_ipget(self):
		try:
			self.kill_process_by_pattern('ipget')
			which_command = "which ipget"
			which_command_results = subprocess.check_output(which_command, shell=True)
			which_command_results = which_command_results.decode()
			self.remove_directory(which_command_results)
			self.remove_binaries(self.bin_path, ['ipget'])
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
						my_user = os.getuid()
						my_group = os.getgid()
						parent_permissions = os.stat(bin_path)
						parent_user = parent_permissions.st_uid
						parent_group = parent_permissions.st_gid
						if user_id == my_user and os.access(file_path, os.W_OK) and parent_user == my_user and os.access(bin_path, os.W_OK):
							rm_command = "chmod 777 " +  file_path + " && rm -rf " + file_path
							rm_results = subprocess.check_output(rm_command, shell=True)
							rm_results = rm_results.decode()
							pass
						elif group_id == my_group and os.access(file_path, os.W_OK) and parent_group == my_group and os.access(bin_path, os.W_OK):
							rm_command = "chmod 777 " +  file_path + " && rm -rf " + file_path
							rm_results = subprocess.check_output(rm_command, shell=True)
							rm_results = rm_results.decode()
							pass
						elif os.geteuid() == 0:
							rm_command = "rm -rf " + file_path + " && rm -rf " + file_path
							rm_results = subprocess.check_output(rm_command, shell=True)
							rm_results = rm_results.decode()
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
		ipfs_kit = self.uninstall_ipfs_kit()
		if self.role == "leecher" or self.role == "worker" or self.role == "master":
			ipfs = self.uninstall_ipfs()
			ipget = self.uninstall_ipget()
			pass
		if self.role == "worker":
			cluster_follow = self.uninstall_ipfs_cluster_follow()
			pass
		if self.role == "master":
			cluster_service  = self.uninstall_ipfs_cluster_service()
			cluster_ctl = self.uninstall_ipfs_cluster_ctl()
			pass


	def install_executables(self, **kwargs):
		results = {}
		if self.role == "leecher" or self.role == "worker" or self.role == "master":
			ipfs = self.install_ipfs_daemon()
			results["ipfs"] = ipfs
		pass
		if self.role == "master":
			cluster_service  = self.install_ipfs_cluster_service()
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
			ipfs_config = self.config_ipfs(cluster_name = self.cluster_name, ipfs_path = self.ipfs_path)
			results["ipfs_config"] = ipfs_config["config"]
			pass
		if self.role == "master":
			cluster_service_config = self.config_ipfs_cluster_service(cluster_name = self.cluster_name, ipfs_path = self.ipfs_path)
			cluster_ctl_config = self.config_ipfs_cluster_ctl(cluster_name = self.cluster_name, ipfs_path = self.ipfs_path)
			results["cluster_service_config"] = cluster_service_config
			results["cluster_ctl_config"] = cluster_ctl_config
			pass
		if self.role == "worker":
			cluster_follow_config = self.config_ipfs_cluster_follow(cluster_name = self.cluster_name, ipfs_path =  self.ipfs_path)
			results["cluster_follow_config"] = cluster_follow_config
			pass
		return results
	
	def ipfs_test_install(self):
		detect = os.system("which ipfs")
		if len(detect) > 0:
			return True
		else:
			return False
		pass

	def ipfs_cluster_service_test_install(self):
		detect = os.system("which ipfs-cluster-service")
		if len(detect) > 0:
			return True
		else:
			return False
		pass

	def ipfs_cluster_follow_test_install(self):
		detect = os.system("which ipfs-cluster-follow")
		if len(detect) > 0:
			return True
		else:
			return False
		pass

	def ipfs_cluster_ctl_test_install(self):
		detect = os.system("which ipfs-cluster-ctl")
		if len(detect) > 0:
			return True
		else:
			return False
		pass

	def ipget_test_install(self):
		detect = os.system("which ipget")
		if len(detect) > 0:
			return True
		else:
			return False
		pass


	def install_and_configure(self, **kwargs):
		results = {}
		if self.role == "leecher" or self.role == "worker" or self.role == "master":
			ipget = self.install_ipget()
			ipfs = self.install_ipfs_daemon()
			ipfs_config = self.config_ipfs(cluster_name = self.cluster_name, ipfs_path = self.ipfs_path)
			ipfs_execute = self.run_ipfs_daemon()
			# NOTE: This fails some times but never when debugging so probably some sort of race issue 
			results["ipfs"] = ipfs
			results["ipfs_config"] = ipfs_config["config"]
			results["ipfs_execute"] = ipfs_execute
			pass
		if self.role == "master":
			cluster_service  = self.install_ipfs_cluster_service()
			cluster_ctl = self.install_ipfs_cluster_ctl()
			cluster_service_config = self.config_ipfs_cluster_service(cluster_name = self.cluster_name, ipfs_path = self.ipfs_path)
			cluster_ctl_config = self.config_ipfs_cluster_ctl(cluster_name = self.cluster_name, ipfs_path = self.ipfs_path)
			results["cluster_service"] = cluster_service
			results["cluster_ctl"] = cluster_ctl
			results["cluster_service_config"] = cluster_service_config
			results["cluster_ctl_config"] = cluster_ctl_config
			results["cluster_service_execute"] = self.run_ipfs_cluster_service()
			results["cluster_ctl_execute"] = self.run_ipfs_cluster_ctl()
			pass
		if self.role == "worker":
			cluster_follow = self.install_ipfs_cluster_follow()
			cluster_follow_config = self.config_ipfs_cluster_follow(cluster_name = self.cluster_name, ipfs_path =  self.ipfs_path)
			results["cluster_follow"] = cluster_follow
			results["cluster_follow_config"] = cluster_follow_config
			results["cluster_follow__execute"] = self.run_ipfs_cluster_follow()
			pass
		self.kill_process_by_pattern("ipfs")
		self.kill_process_by_pattern("ipfs-cluster-follow")
		self.kill_process_by_pattern("ipfs-cluster-service")
		self.kill_process_by_pattern("ipfs-cluster-ctl")
		if os.geteuid() == 0:
			systemctl_reload = "systemctl daemon-reload"
			results["systemctl_reload"] = subprocess.run(systemctl_reload, shell=True)
		return results

	def test():
		results = {}
		try:
			install = install_ipfs(None, metadata=metadata) 
			results = install.test_uninstall()
			results = install.install_and_configure()
			print(results)
		except Exception as e:
			print(e)
		pass

if __name__ == "__main__":
	metadata = {
		"role":"worker",
		"cluster_name":"cloudkit_storage",
		"cluster_location":"/ip4/167.99.96.231/tcp/9096/p2p/12D3KooWKw9XCkdfnf8CkAseryCgS3VVoGQ6HUAkY91Qc6Fvn4yv",
		#"cluster_location": "/ip4/167.99.96.231/udp/4001/quic-v1/p2p/12D3KooWS9pEXDb2FEsDv9TH4HicZgwhZtthHtSdSfyKKDnkDu8D",
		"config":None,
	}
	resources = {}
	install = install_ipfs(metadata, resources) 
	results = install.test()
	print(results)
	pass
