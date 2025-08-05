import psutil
import subprocess
import json
import time
import os
import logging

logger = logging.getLogger(__name__)

class EnhancedDaemonManager:
    def __init__(self, ipfs_path=None, api_port=5001):
        self.ipfs_path = ipfs_path or os.path.expanduser("~/.ipfs")
        self.api_port = api_port
        self.ipfs_daemon_process = None

    def _get_ipfs_daemon_process(self):
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'ipfs' in proc.name().lower() and 'daemon' in ' '.join(proc.cmdline()).lower():
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return None

    def start_daemon(self, detach=True):
        if self._get_ipfs_daemon_process():
            logger.info("IPFS daemon is already running.")
            return {"status": "already_running"}

        command = ["ipfs", "daemon"]
        if detach:
            # This will run the command in a new process group, detaching it
            # from the current shell. The output will not be captured here.
            try:
                subprocess.Popen(command, preexec_fn=os.setsid, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logger.info("IPFS daemon started in detached mode.")
                return {"status": "started", "detached": True}
            except Exception as e:
                logger.error(f"Error starting IPFS daemon in detached mode: {e}")
                return {"status": "error", "message": str(e)}
        else:
            # For non-detached mode, you might want to capture output or run in foreground
            logger.info("Starting IPFS daemon in foreground mode (not recommended for production)...")
            try:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.ipfs_daemon_process = process
                logger.info("IPFS daemon started in foreground.")
                return {"status": "started", "detached": False}
            except Exception as e:
                logger.error(f"Error starting IPFS daemon in foreground mode: {e}")
                return {"status": "error", "message": str(e)}

    def stop_daemon(self):
        proc = self._get_ipfs_daemon_process()
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=10)
                if proc.is_running():
                    proc.kill()
                    proc.wait(timeout=5)
                logger.info("IPFS daemon stopped.")
                return {"status": "stopped"}
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, psutil.TimeoutExpired) as e:
                logger.error(f"Error stopping IPFS daemon: {e}")
                return {"status": "error", "message": str(e)}
        else:
            logger.info("IPFS daemon is not running.")
            return {"status": "not_running"}

    def restart_daemon(self):
        self.stop_daemon()
        time.sleep(2)  # Give it a moment to fully stop
        return self.start_daemon()

    def check_daemon_status(self):
        status = {
            "running": False,
            "pid": None,
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "uptime": None,
            "api_reachable": False,
            "peer_count": 0,
            "repo_size": None,
            "ipfs_version": None,
            "error": None
        }

        proc = self._get_ipfs_daemon_process()
        if proc:
            status["running"] = True
            status["pid"] = proc.pid
            try:
                status["cpu_percent"] = proc.cpu_percent(interval=0.1)
                status["memory_percent"] = proc.memory_percent()
                status["uptime"] = time.time() - proc.create_time()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                status["error"] = f"Process metrics error: {e}"

            # Check IPFS API
            try:
                # Use subprocess to call `ipfs id` and `ipfs repo stat`
                # This assumes `ipfs` CLI is in the PATH and daemon is running
                id_output = subprocess.run(["ipfs", "id"], capture_output=True, text=True, check=True, timeout=5)
                id_data = json.loads(id_output.stdout)
                status["api_reachable"] = True
                status["peer_id"] = id_data.get("ID")
                status["addresses"] = id_data.get("Addresses")
                status["agent_version"] = id_data.get("AgentVersion")
                status["protocol_version"] = id_data.get("ProtocolVersion")

                repo_stat_output = subprocess.run(["ipfs", "repo", "stat"], capture_output=True, text=True, check=True, timeout=5)
                repo_stat_data = json.loads(repo_stat_output.stdout)
                status["repo_size"] = repo_stat_data.get("RepoSize")
                status["num_objects"] = repo_stat_data.get("NumObjects")

                # Get connected peers
                swarm_peers_output = subprocess.run(["ipfs", "swarm", "peers"], capture_output=True, text=True, check=True, timeout=5)
                # Each line is a peer address, count them
                status["peer_count"] = len([line for line in swarm_peers_output.stdout.strip().split('\n') if line])

                # Get IPFS version
                version_output = subprocess.run(["ipfs", "version", "--enc=json"], capture_output=True, text=True, check=True, timeout=5)
                version_data = json.loads(version_output.stdout)
                status["ipfs_version"] = version_data.get("Version")

            except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
                status["api_reachable"] = False
                status["error"] = f"IPFS API/CLI error: {e}"
        else:
            status["error"] = "IPFS daemon process not found."

        return status
