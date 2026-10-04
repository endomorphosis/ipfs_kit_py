import psutil
import subprocess
import json
import time
import os
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

class EnhancedDaemonManager:
    def __init__(self, ipfs_path=None, api_port=5001):
        self.ipfs_path = ipfs_path or os.path.expanduser("~/.ipfs")
        self.api_port = api_port
        self.ipfs_daemon_process = None
        self.index_update_running = False
        self.index_update_interval = 5
        self.ipfs_kit_path = Path.home() / ".ipfs_kit"
        self._index_stop_event = threading.Event()
        self._index_thread = None

    def _get_ipfs_daemon_process(self):
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'ipfs' in proc.name().lower() and 'daemon' in ' '.join(proc.cmdline()).lower():
                    return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return None

    def _is_ipfs_daemon_running(self):
        return self._get_ipfs_daemon_process() is not None

    def _get_pin_count(self):
        if not self._is_ipfs_daemon_running():
            return 0
        try:
            output = subprocess.run(
                ["ipfs", "pin", "ls", "--type=all"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            return len([line for line in output.stdout.splitlines() if line.strip()])
        except Exception:
            return 0

    def _get_real_ipfs_pins(self):
        pins = []
        if not self._is_ipfs_daemon_running():
            return pins
        try:
            output = subprocess.run(
                ["ipfs", "pin", "ls", "--type=all", "--quiet"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            for cid in output.stdout.splitlines():
                cid = cid.strip()
                if cid:
                    pins.append({"cid": cid, "size_bytes": 0, "pin_type": "all"})
        except Exception:
            return pins
        return pins

    def _ensure_index_paths(self):
        pin_dir = self.ipfs_kit_path / "pin_metadata" / "parquet_storage"
        state_dir = self.ipfs_kit_path / "program_state" / "parquet"
        pin_dir.mkdir(parents=True, exist_ok=True)
        state_dir.mkdir(parents=True, exist_ok=True)
        return pin_dir, state_dir

    def _index_update_loop(self):
        pin_dir, state_dir = self._ensure_index_paths()
        pin_file = pin_dir / "pins.parquet"
        state_file = state_dir / "daemon_state.parquet"
        while not self._index_stop_event.wait(self.index_update_interval):
            try:
                pin_file.write_text(f"updated={time.time()}\n")
                state_file.write_text(f"updated={time.time()}\n")
            except Exception:
                continue

    def start_background_indexing(self):
        if self.index_update_running:
            return
        self.index_update_running = True
        self._index_stop_event.clear()
        self._index_thread = threading.Thread(target=self._index_update_loop, daemon=True)
        self._index_thread.start()

    def stop_background_indexing(self):
        if not self.index_update_running:
            return
        self.index_update_running = False
        self._index_stop_event.set()
        if self._index_thread:
            self._index_thread.join(timeout=2)
        self._index_thread = None

    def _is_cluster_daemon_running(self):
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if "ipfs-cluster" in proc.name().lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False

    def _test_cluster_api_health(self):
        if not self._is_cluster_daemon_running():
            return False
        try:
            subprocess.run(
                ["ipfs-cluster-ctl", "id"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            return True
        except Exception:
            return False

    def _manage_cluster_lockfile_and_daemon(self):
        cluster_config_dir = Path.home() / ".ipfs-cluster"
        lockfile_path = cluster_config_dir / "cluster.lock"
        cluster_config_dir.mkdir(parents=True, exist_ok=True)

        if lockfile_path.exists() and not self._is_cluster_daemon_running():
            try:
                lockfile_path.unlink()
                return {"success": True, "action": "removed_stale_lock"}
            except Exception as e:
                return {"success": False, "action": "remove_failed", "error": str(e)}

        if self._is_cluster_daemon_running():
            return {"success": True, "action": "daemon_running"}

        return {"success": True, "action": "no_lockfile"}

    def _start_ipfs_cluster_service(self):
        if self._is_cluster_daemon_running():
            return {"success": True, "status": "already_running"}
        try:
            subprocess.Popen(
                ["ipfs-cluster-service", "daemon"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"success": True, "status": "started"}
        except Exception as e:
            return {"success": False, "status": "error", "error": str(e)}

    def start_daemon(self, detach=True, init_if_needed=True):
        if self._get_ipfs_daemon_process():
            logger.info("IPFS daemon is already running.")
            return {"status": "already_running"}

        command = ["ipfs", "daemon"]
        if init_if_needed:
            command.append("--init")
        if detach:
            # This will run the command in a new process group, detaching it
            # from the current shell. The output will not be captured here.
            try:
                env = os.environ.copy()
                env.setdefault("IPFS_PATH", self.ipfs_path)
                if os.name == "nt":
                    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
                    subprocess.Popen(
                        command,
                        creationflags=creationflags,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=env
                    )
                else:
                    subprocess.Popen(
                        command,
                        preexec_fn=os.setsid,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=env
                    )
                logger.info("IPFS daemon started in detached mode.")
                return {"status": "started", "detached": True}
            except Exception as e:
                logger.error(f"Error starting IPFS daemon in detached mode: {e}")
                return {"status": "error", "message": str(e)}
        else:
            # For non-detached mode, you might want to capture output or run in foreground
            logger.info("Starting IPFS daemon in foreground mode (not recommended for production)...")
            try:
                env = os.environ.copy()
                env.setdefault("IPFS_PATH", self.ipfs_path)
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
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
