#!/usr/bin/env python3
"""
Comprehensive IPFS Cluster Configuration Fix Script

This script will:
1. Validate and fix cluster configuration
2. Ensure all required sections exist
3. Start cluster service with proper configuration
4. Verify cluster health and API responsiveness
"""

import json
import os
import sys
import subprocess
import time
import signal
import psutil
from pathlib import Path
from typing import Dict, Any, Optional
import uuid


class ClusterConfigFixer:
    """Fix and manage IPFS Cluster configuration."""
    
    def __init__(self):
        self.cluster_path = Path.home() / '.ipfs-cluster'
        self.service_config_path = self.cluster_path / 'service.json'
        self.identity_path = self.cluster_path / 'identity.json'
        self.peerstore_path = self.cluster_path / 'peerstore'
        
        # Binary path
        self.cluster_bin = self._find_cluster_binary()
        
    def _find_cluster_binary(self) -> Optional[Path]:
        """Find the cluster binary."""
        possible_paths = [
            Path(__file__).parent / "ipfs_kit_py" / "bin" / "ipfs-cluster-service",
            Path("/home/devel/ipfs_kit_py/ipfs_kit_py/bin/ipfs-cluster-service"),
            Path("ipfs-cluster-service")  # System PATH
        ]
        
        for path in possible_paths:
            if path.exists() and path.is_file():
                return path
        
        # Check system PATH
        import shutil
        system_bin = shutil.which("ipfs-cluster-service")
        if system_bin:
            return Path(system_bin)
            
        return None
    
    def validate_and_fix_config(self) -> Dict[str, Any]:
        """Validate and fix cluster configuration."""
        result = {
            "success": False,
            "fixes_applied": [],
            "errors": [],
            "config_valid": False
        }
        
        try:
            print("🔧 Validating and fixing cluster configuration...")
            
            # Ensure cluster directory exists
            if not self.cluster_path.exists():
                self.cluster_path.mkdir(parents=True, exist_ok=True)
                result["fixes_applied"].append("Created cluster directory")
            
            # Load existing config or create new one
            if self.service_config_path.exists():
                with open(self.service_config_path, 'r') as f:
                    config = json.load(f)
                print("✓ Loaded existing configuration")
            else:
                print("⚠ No configuration found, creating default...")
                config = self._create_default_config()
                result["fixes_applied"].append("Created default configuration")
            
            # Fix missing or invalid sections
            fixes = self._fix_config_sections(config)
            result["fixes_applied"].extend(fixes)
            
            # Save fixed configuration
            with open(self.service_config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            result["fixes_applied"].append("Saved corrected configuration")
            
            # Validate final configuration
            validation_result = self._validate_config(config)
            result["config_valid"] = validation_result["valid"]
            
            if validation_result["valid"]:
                result["success"] = True
                print("✅ Configuration validated and fixed successfully")
            else:
                result["errors"].extend(validation_result["errors"])
                print("❌ Configuration still has issues after fixes")
                
        except Exception as e:
            error_msg = f"Error fixing configuration: {str(e)}"
            print(f"❌ {error_msg}")
            result["errors"].append(error_msg)
            
        return result
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create a default cluster configuration."""
        return {
            "id": str(uuid.uuid4()),
            "cluster": {
                "secret": "",
                "peers": [],
                "bootstrap": [],
                "leave_on_shutdown": False,
                "listen_multiaddress": "/ip4/0.0.0.0/tcp/9096",
                "state_sync_interval": "10m0s",
                "ipfs_sync_interval": "2m10s",
                "replication_factor_min": -1,
                "replication_factor_max": -1,
                "monitor_ping_interval": "15s",
                "peer_watch_interval": "5s",
                "mdns_interval": "10s",
                "disable_repinning": True,
                "connection_manager": {
                    "high_water": 400,
                    "low_water": 100,
                    "grace_period": "2m0s"
                }
            },
            "consensus": {
                "crdt": {
                    "cluster_name": "ipfs-cluster",
                    "trusted_peers": ["*"],
                    "batching": {
                        "max_batch_size": 0,
                        "max_batch_age": "0s"
                    },
                    "repair_interval": "1h0m0s"
                }
            },
            "api": {
                "ipfsproxy": {
                    "listen_multiaddress": "/ip4/127.0.0.1/tcp/9095",
                    "node_multiaddress": "/ip4/127.0.0.1/tcp/5001",
                    "log_level": "error",
                    "read_timeout": "0s",
                    "read_header_timeout": "5s",
                    "write_timeout": "0s",
                    "idle_timeout": "1m0s"
                },
                "restapi": {
                    "http_listen_multiaddress": "/ip4/127.0.0.1/tcp/9094",
                    "ssl_cert_file": "",
                    "ssl_key_file": "",
                    "log_level": "error",
                    "read_timeout": "0s",
                    "read_header_timeout": "5s",
                    "write_timeout": "0s",
                    "idle_timeout": "2m0s",
                    "max_header_bytes": 4096,
                    "basic_auth_credentials": {},
                    "headers": {},
                    "cors_allowed_origins": ["*"],
                    "cors_allowed_methods": ["GET"],
                    "cors_allowed_headers": [],
                    "cors_exposed_headers": ["Content-Type", "X-Stream-Output", "X-Chunked-Output", "X-Content-Length"],
                    "cors_allow_credentials": True,
                    "cors_max_age": "0s"
                }
            },
            "ipfs_connector": {
                "ipfshttp": {
                    "node_multiaddress": "/ip4/127.0.0.1/tcp/5001",
                    "connect_swarms_delay": "30s",
                    "ipfs_request_timeout": "5m0s",
                    "pin_timeout": "2m0s",
                    "unpin_timeout": "3h0m0s",
                    "repogc_timeout": "24h0m0s",
                    "informer_trigger_interval": 0
                }
            },
            "pin_tracker": {
                "stateless": {
                    "concurrent_pins": 10,
                    "priority_pin_max_age": "24h0m0s",
                    "priority_pin_max_retries": 5
                }
            },
            "monitor": {
                "pubsubmon": {
                    "check_interval": "15s"
                }
            },
            "allocator": {
                "balanced": {
                    "allocate_by": ["tag:group", "freespace"]
                }
            },
            "informer": {
                "disk": {
                    "metric_ttl": "30s",
                    "metric_type": "freespace"
                },
                "tags": {
                    "metric_ttl": "30s",
                    "tags": {
                        "group": "default"
                    }
                }
            },
            "observations": {
                "metrics": {
                    "enable_stats": False,
                    "prometheus_endpoint": "/ip4/127.0.0.1/tcp/8888",
                    "reporting_interval": "2s"
                },
                "tracing": {
                    "enable_tracing": False,
                    "jaeger_endpoint": "/ip4/127.0.0.1/udp/6831",
                    "sampling_prob": 0.3,
                    "service_name": "cluster-daemon"
                }
            },
            "datastore": {
                "badger": {
                    "badger_options": {
                        "dir": "",
                        "value_dir": "",
                        "sync_writes": False,
                        "table_loading_mode": 0,
                        "value_log_loading_mode": 0,
                        "num_versions_to_keep": 1,
                        "max_table_size": 67108864,
                        "level_size_multiplier": 10,
                        "max_levels": 7,
                        "value_threshold": 32,
                        "num_memtables": 5,
                        "num_level_zero_tables": 5,
                        "num_level_zero_tables_stall": 10,
                        "level_one_size": 268435456,
                        "value_log_file_size": 1073741823,
                        "value_log_max_entries": 1000000,
                        "num_compactors": 2,
                        "compact_l_0_on_close": True,
                        "lru_cache_size": 1073741824,
                        "max_cache_size": 0,
                        "z_std_compression_level": 1,
                        "verify_value_checksum": False,
                        "checksum_verification_mode": 0,
                        "block_cache_size": 0,
                        "index_cache_size": 0
                    }
                }
            }
        }
    
    def _fix_config_sections(self, config: Dict[str, Any]) -> list:
        """Fix missing or invalid configuration sections."""
        fixes_applied = []
        
        # Ensure ID exists
        if "id" not in config or not config["id"]:
            config["id"] = str(uuid.uuid4())
            fixes_applied.append("Added missing cluster ID")
            print("🔧 Added missing cluster ID")
        
        # Ensure required top-level sections exist
        required_sections = ["cluster", "consensus", "api", "ipfs_connector", "pin_tracker", "monitor", "allocator", "informer", "observations", "datastore"]
        default_config = self._create_default_config()
        
        for section in required_sections:
            if section not in config:
                config[section] = default_config[section]
                fixes_applied.append(f"Added missing {section} section")
                print(f"🔧 Added missing {section} section")
        
        # Fix IPFS connector if needed
        if "ipfs_connector" in config and "ipfshttp" in config["ipfs_connector"]:
            ipfs_config = config["ipfs_connector"]["ipfshttp"]
            if "node_multiaddress" not in ipfs_config:
                ipfs_config["node_multiaddress"] = "/ip4/127.0.0.1/tcp/5001"
                fixes_applied.append("Fixed IPFS connector node address")
                print("🔧 Fixed IPFS connector node address")
        
        return fixes_applied
    
    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate cluster configuration."""
        result = {"valid": True, "errors": []}
        
        # Check required fields
        required_fields = ["id", "cluster", "api", "ipfs_connector"]
        for field in required_fields:
            if field not in config:
                result["valid"] = False
                result["errors"].append(f"Missing required field: {field}")
        
        # Validate IPFS connector
        if "ipfs_connector" in config:
            ipfs_config = config["ipfs_connector"]
            if "ipfshttp" not in ipfs_config:
                result["valid"] = False
                result["errors"].append("Missing ipfshttp in ipfs_connector")
            elif "node_multiaddress" not in ipfs_config["ipfshttp"]:
                result["valid"] = False
                result["errors"].append("Missing node_multiaddress in ipfshttp")
        
        return result
    
    def cleanup_cluster_processes(self) -> Dict[str, Any]:
        """Clean up any existing cluster processes."""
        result = {
            "processes_killed": [],
            "errors": []
        }
        
        try:
            print("🧹 Cleaning up existing cluster processes...")
            
            # Find and kill cluster processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    pinfo = proc.info
                    if (pinfo['name'] and 'ipfs-cluster' in pinfo['name']) or \
                       (pinfo['cmdline'] and any('ipfs-cluster' in str(cmd) for cmd in pinfo['cmdline'])):
                        
                        print(f"🔄 Killing cluster process {pinfo['pid']}: {pinfo['name']}")
                        proc.terminate()
                        time.sleep(1)
                        
                        # Force kill if still running
                        if proc.is_running():
                            proc.kill()
                        
                        result["processes_killed"].append(pinfo['pid'])
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                except Exception as e:
                    result["errors"].append(f"Error killing process: {str(e)}")
            
            if result["processes_killed"]:
                print(f"✅ Killed {len(result['processes_killed'])} cluster processes")
            else:
                print("✅ No cluster processes to clean up")
                
        except Exception as e:
            error_msg = f"Error cleaning up processes: {str(e)}"
            print(f"❌ {error_msg}")
            result["errors"].append(error_msg)
            
        return result
    
    def start_cluster_service(self) -> Dict[str, Any]:
        """Start the IPFS Cluster service."""
        result = {
            "success": False,
            "pid": None,
            "errors": [],
            "api_responsive": False
        }
        
        try:
            if not self.cluster_bin:
                result["errors"].append("Cluster binary not found")
                return result
            
            print(f"🚀 Starting cluster service using: {self.cluster_bin}")
            
            # Set environment
            env = os.environ.copy()
            env["IPFS_CLUSTER_PATH"] = str(self.cluster_path)
            
            # Start daemon
            process = subprocess.Popen(
                [str(self.cluster_bin), "daemon"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            result["pid"] = process.pid
            print(f"✅ Started cluster daemon with PID {process.pid}")
            
            # Wait for startup
            print("⏳ Waiting for cluster API to become responsive...")
            api_ready = self._wait_for_cluster_api()
            
            if api_ready:
                result["success"] = True
                result["api_responsive"] = True
                print("✅ Cluster service started and API is responsive!")
            else:
                result["errors"].append("Service started but API not responsive")
                print("⚠ Cluster service started but API not responsive")
                
                # Get error output
                try:
                    stdout, stderr = process.communicate(timeout=1)
                    if stderr:
                        result["errors"].append(f"Stderr: {stderr.decode()}")
                except subprocess.TimeoutExpired:
                    pass
                    
        except Exception as e:
            error_msg = f"Error starting cluster service: {str(e)}"
            print(f"❌ {error_msg}")
            result["errors"].append(error_msg)
            
        return result
    
    def _wait_for_cluster_api(self, timeout: int = 30) -> bool:
        """Wait for cluster API to become responsive."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                import httpx
                with httpx.Client(timeout=2) as client:
                    response = client.post("http://127.0.0.1:9094/api/v0/version")
                    if response.status_code == 200:
                        return True
            except:
                pass
            
            time.sleep(1)
            print(".", end="", flush=True)
        
        print()
        return False
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """Get current cluster status."""
        status = {
            "running": False,
            "api_responsive": False,
            "processes": [],
            "version": None
        }
        
        try:
            # Check for running processes
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    pinfo = proc.info
                    if (pinfo['name'] and 'ipfs-cluster' in pinfo['name']) or \
                       (pinfo['cmdline'] and any('ipfs-cluster' in str(cmd) for cmd in pinfo['cmdline'])):
                        status["processes"].append({
                            "pid": pinfo['pid'],
                            "name": pinfo['name'],
                            "cmdline": pinfo['cmdline']
                        })
                        status["running"] = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Check API responsiveness
            if status["running"]:
                try:
                    import httpx
                    with httpx.Client(timeout=5) as client:
                        response = client.post("http://127.0.0.1:9094/api/v0/version")
                        if response.status_code == 200:
                            status["api_responsive"] = True
                            version_data = response.json()
                            status["version"] = version_data.get("version", "unknown")
                except:
                    pass
            
        except Exception as e:
            status["error"] = str(e)
            
        return status


def main():
    """Main function to fix cluster configuration and start service."""
    print("🔧 IPFS Cluster Configuration Fixer")
    print("=" * 50)
    
    fixer = ClusterConfigFixer()
    
    # Step 1: Validate and fix configuration
    print("\n📋 Step 1: Validating and fixing configuration...")
    config_result = fixer.validate_and_fix_config()
    
    if not config_result["success"]:
        print("❌ Failed to fix configuration:")
        for error in config_result["errors"]:
            print(f"  • {error}")
        return 1
    
    print("✅ Configuration validated and fixed")
    for fix in config_result["fixes_applied"]:
        print(f"  • {fix}")
    
    # Step 2: Clean up existing processes
    print("\n🧹 Step 2: Cleaning up existing processes...")
    cleanup_result = fixer.cleanup_cluster_processes()
    
    if cleanup_result["errors"]:
        print("⚠ Some cleanup errors occurred:")
        for error in cleanup_result["errors"]:
            print(f"  • {error}")
    
    # Step 3: Start cluster service
    print("\n🚀 Step 3: Starting cluster service...")
    start_result = fixer.start_cluster_service()
    
    if not start_result["success"]:
        print("❌ Failed to start cluster service:")
        for error in start_result["errors"]:
            print(f"  • {error}")
        return 1
    
    # Step 4: Verify status
    print("\n✅ Step 4: Verifying cluster status...")
    status = fixer.get_cluster_status()
    
    print(f"Running: {status['running']}")
    print(f"API Responsive: {status['api_responsive']}")
    print(f"Version: {status.get('version', 'unknown')}")
    print(f"Processes: {len(status['processes'])}")
    
    if status["api_responsive"]:
        print("\n🎉 SUCCESS! IPFS Cluster is now running and healthy!")
        return 0
    else:
        print("\n⚠ Cluster started but API may not be fully responsive yet")
        return 0


if __name__ == "__main__":
    exit(main())
