#!/usr/bin/env python3
"""
Comprehensive Backend Status Monitor
====================================

This module provides real-time monitoring of all IPFS Kit backends including:
- IPFS daemon and cluster services
- Lotus (Filecoin) daemon and API
- Lassie retrieval client
- Storacha/Web3.Storage integration
- S3 storage backends
- HuggingFace model repositories
- Arrow/Parquet data processing
- Multi-backend filesystem integration
- Daemon management systems
"""

import os
import sys
import time
import json
import asyncio
import logging
import subprocess
import psutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)

class BackendMonitor:
    """Comprehensive monitoring for all IPFS Kit backends and daemon systems."""
    
    def __init__(self):
        """Initialize the backend monitor."""
        self.backends = {}
        self.daemon_managers = {}
        self.multi_backend_fs = None
        self.startup_time = time.time()
        self.last_update = 0
        self.update_interval = 30  # Update every 30 seconds
        
        # Initialize monitoring data
        self.status_cache = {
            "backends": {},
            "daemons": {},
            "filesystem": {},
            "performance": {},
            "alerts": [],
            "last_updated": 0
        }
        
    async def initialize(self):
        """Initialize all backend connections and monitoring."""
        logger.info("🔧 Initializing comprehensive backend monitoring...")
        
        # Initialize multi-backend filesystem if available
        await self._init_multi_backend_fs()
        
        # Initialize daemon monitoring
        await self._init_daemon_monitoring()
        
        # Initialize storage backend monitoring
        await self._init_storage_monitoring()
        
        # Perform initial status check
        await self.update_all_status()
        
        logger.info("✅ Backend monitoring initialized successfully")
    
    async def _init_multi_backend_fs(self):
        """Initialize multi-backend filesystem integration."""
        try:
            # Try to import and initialize multi-backend filesystem
            from tools.development_tools.multi_backend_fs_integration import backend_manager
            self.multi_backend_fs = backend_manager
            logger.info("✅ Multi-backend filesystem integration loaded")
            
            # Get registered backends
            backends = self.multi_backend_fs.get_backends()
            for backend_id, backend_info in backends.items():
                self.backends[backend_id] = {
                    "type": backend_info.get("type", "unknown"),
                    "status": "unknown",
                    "last_check": 0,
                    "config": backend_info.get("config", {}),
                    "is_default": backend_id == self.multi_backend_fs.default_backend_id
                }
                
        except ImportError as e:
            logger.warning(f"Multi-backend filesystem not available: {e}")
            self.multi_backend_fs = None
    
    async def _init_daemon_monitoring(self):
        """Initialize daemon monitoring for IPFS, Lotus, etc."""
        try:
            # Try to get daemon status from IPFS Kit
            import ipfs_kit_py
            kit = ipfs_kit_py.ipfs_kit()
            
            # Monitor IPFS daemon
            self.daemon_managers["ipfs"] = {
                "kit": kit,
                "type": "ipfs",
                "status": "unknown",
                "pid": None,
                "last_check": 0
            }
            
            # Monitor Lotus daemon if available
            if hasattr(kit, 'lotus_kit') and kit.lotus_kit:
                self.daemon_managers["lotus"] = {
                    "kit": kit.lotus_kit,
                    "type": "lotus",
                    "status": "unknown",
                    "pid": None,
                    "last_check": 0
                }
            
            # Monitor Lassie if available
            if hasattr(kit, 'lassie_kit') and kit.lassie_kit:
                self.daemon_managers["lassie"] = {
                    "kit": kit.lassie_kit,
                    "type": "lassie",
                    "status": "available",
                    "pid": "on-demand",
                    "last_check": time.time()
                }
                
        except Exception as e:
            logger.warning(f"Daemon monitoring initialization failed: {e}")
    
    async def _init_storage_monitoring(self):
        """Initialize storage backend monitoring."""
        # Standard storage backends to monitor
        storage_backends = [
            ("ipfs", "IPFS Node", self._check_ipfs_status),
            ("ipfs_cluster", "IPFS Cluster", self._check_ipfs_cluster_status),
            ("lotus", "Lotus/Filecoin", self._check_lotus_status),
            ("lassie", "Lassie Retrieval", self._check_lassie_status),
            ("storacha", "Storacha/Web3.Storage", self._check_storacha_status),
            ("s3", "S3 Storage", self._check_s3_status),
            ("huggingface", "HuggingFace", self._check_huggingface_status),
            ("synapse", "Synapse", self._check_synapse_status),
            ("arrow", "Arrow/Parquet", self._check_arrow_status)
        ]
        
        for backend_id, name, check_func in storage_backends:
            if backend_id not in self.backends:
                self.backends[backend_id] = {
                    "name": name,
                    "type": backend_id,
                    "status": "unknown",
                    "last_check": 0,
                    "check_function": check_func,
                    "metrics": {}
                }
    
    async def update_all_status(self):
        """Update status for all monitored backends and daemons."""
        current_time = time.time()
        
        # Skip if too recent
        if current_time - self.last_update < self.update_interval:
            return self.status_cache
        
        logger.info("🔍 Updating all backend status...")
        
        # Update daemon status
        for daemon_id, daemon_info in self.daemon_managers.items():
            try:
                await self._update_daemon_status(daemon_id, daemon_info)
            except Exception as e:
                logger.error(f"Error updating {daemon_id} daemon status: {e}")
        
        # Update backend status
        for backend_id, backend_info in self.backends.items():
            try:
                await self._update_backend_status(backend_id, backend_info)
            except Exception as e:
                logger.error(f"Error updating {backend_id} backend status: {e}")
        
        # Update filesystem status
        await self._update_filesystem_status()
        
        # Update performance metrics
        await self._update_performance_metrics()
        
        # Generate alerts
        await self._generate_alerts()
        
        # Update cache
        self.status_cache["last_updated"] = current_time
        self.last_update = current_time
        
        logger.info("✅ Backend status update completed")
        return self.status_cache
    
    async def _update_daemon_status(self, daemon_id: str, daemon_info: Dict[str, Any]):
        """Update status for a specific daemon."""
        try:
            kit = daemon_info.get("kit")
            if not kit:
                return
            
            if daemon_id == "ipfs":
                # Check IPFS daemon status
                if hasattr(kit, 'check_daemon_status'):
                    status_result = kit.check_daemon_status()
                    ipfs_status = status_result.get("daemons", {}).get("ipfs", {})
                    daemon_info["status"] = "running" if ipfs_status.get("running", False) else "stopped"
                    daemon_info["pid"] = ipfs_status.get("pid")
                else:
                    # Fallback to process check
                    daemon_info["status"] = "unknown"
                    
            elif daemon_id == "lotus":
                # Check Lotus daemon status
                if hasattr(kit, 'daemon_status'):
                    lotus_status = kit.daemon_status()
                    daemon_info["status"] = "running" if lotus_status.get("process_running", False) else "stopped"
                    daemon_info["pid"] = lotus_status.get("pid")
                    daemon_info["api_available"] = lotus_status.get("api_available", False)
            
            daemon_info["last_check"] = time.time()
            
            # Store in cache
            self.status_cache["daemons"][daemon_id] = {
                "status": daemon_info["status"],
                "pid": daemon_info.get("pid"),
                "type": daemon_info["type"],
                "last_check": daemon_info["last_check"],
                "api_available": daemon_info.get("api_available", True)
            }
            
        except Exception as e:
            logger.error(f"Error updating daemon {daemon_id}: {e}")
            daemon_info["status"] = "error"
            daemon_info["error"] = str(e)
    
    async def _update_backend_status(self, backend_id: str, backend_info: Dict[str, Any]):
        """Update status for a specific backend."""
        try:
            check_func = backend_info.get("check_function")
            if check_func:
                status_result = await check_func()
                backend_info.update(status_result)
            
            backend_info["last_check"] = time.time()
            
            # Store in cache
            self.status_cache["backends"][backend_id] = {
                "name": backend_info.get("name", backend_id),
                "type": backend_info["type"],
                "status": backend_info["status"],
                "last_check": backend_info["last_check"],
                "metrics": backend_info.get("metrics", {}),
                "error": backend_info.get("error"),
                "is_default": backend_info.get("is_default", False)
            }
            
        except Exception as e:
            logger.error(f"Error updating backend {backend_id}: {e}")
            backend_info["status"] = "error"
            backend_info["error"] = str(e)
    
    # Backend-specific status check functions
    async def _check_ipfs_status(self) -> Dict[str, Any]:
        """Check IPFS node status."""
        try:
            # Try IPFS API call
            result = subprocess.run(["ipfs", "id"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                ipfs_id = json.loads(result.stdout)
                return {
                    "status": "running",
                    "metrics": {
                        "peer_id": ipfs_id.get("ID"),
                        "addresses": len(ipfs_id.get("Addresses", [])),
                        "agent_version": ipfs_id.get("AgentVersion")
                    }
                }
            else:
                return {"status": "stopped", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _check_ipfs_cluster_status(self) -> Dict[str, Any]:
        """Check IPFS Cluster status."""
        try:
            # Check cluster service
            result = subprocess.run(["ipfs-cluster-ctl", "id"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return {
                    "status": "running",
                    "metrics": {"cluster_connected": True}
                }
            else:
                return {"status": "stopped", "error": "Cluster not responding"}
        except Exception as e:
            return {"status": "unavailable", "error": str(e)}
    
    async def _check_lotus_status(self) -> Dict[str, Any]:
        """Check Lotus/Filecoin status."""
        try:
            # Check if lotus daemon is in our daemon managers
            if "lotus" in self.daemon_managers:
                daemon_info = self.daemon_managers["lotus"]
                if daemon_info["status"] == "running":
                    return {
                        "status": "running",
                        "metrics": {
                            "daemon_running": True,
                            "api_available": daemon_info.get("api_available", False)
                        }
                    }
            
            # Fallback to direct check
            result = subprocess.run(["lotus", "net", "id"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return {"status": "running", "metrics": {"api_responsive": True}}
            else:
                return {"status": "stopped", "error": "Lotus API not responding"}
        except Exception as e:
            return {"status": "unavailable", "error": str(e)}
    
    async def _check_lassie_status(self) -> Dict[str, Any]:
        """Check Lassie retrieval client status."""
        try:
            # Lassie is typically used on-demand, check if binary is available
            result = subprocess.run(["which", "lassie"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lassie_path = result.stdout.strip()
                return {
                    "status": "available",
                    "metrics": {
                        "binary_path": lassie_path,
                        "mode": "on-demand"
                    }
                }
            else:
                return {"status": "unavailable", "error": "Lassie binary not found"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _check_storacha_status(self) -> Dict[str, Any]:
        """Check Storacha/Web3.Storage status."""
        try:
            # Check if w3 CLI is available
            result = subprocess.run(["w3", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return {
                    "status": "available",
                    "metrics": {"cli_version": result.stdout.strip()}
                }
            else:
                # Check Python API availability
                try:
                    import w3storage
                    return {
                        "status": "available",
                        "metrics": {"python_api": True}
                    }
                except ImportError:
                    return {"status": "unavailable", "error": "Storacha not installed"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _check_s3_status(self) -> Dict[str, Any]:
        """Check S3 backend status."""
        try:
            # Check if boto3 is available
            import boto3
            return {
                "status": "available",
                "metrics": {"boto3_available": True}
            }
        except ImportError:
            return {"status": "unavailable", "error": "boto3 not installed"}
    
    async def _check_huggingface_status(self) -> Dict[str, Any]:
        """Check HuggingFace backend status."""
        try:
            # Check if transformers and datasets are available
            import transformers
            import datasets
            return {
                "status": "available",
                "metrics": {
                    "transformers_version": transformers.__version__,
                    "datasets_available": True
                }
            }
        except ImportError as e:
            return {"status": "unavailable", "error": f"HuggingFace libraries not available: {e}"}
    
    async def _check_synapse_status(self) -> Dict[str, Any]:
        """Check Synapse backend status."""
        try:
            # Check if any Synapse-related processes are running
            synapse_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if 'synapse' in proc.info['name'].lower():
                        synapse_processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            if synapse_processes:
                return {
                    "status": "running",
                    "metrics": {"processes": len(synapse_processes)}
                }
            else:
                return {"status": "stopped", "metrics": {"processes": 0}}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _check_arrow_status(self) -> Dict[str, Any]:
        """Check Arrow/Parquet processing status."""
        try:
            import pyarrow
            import pandas
            return {
                "status": "available",
                "metrics": {
                    "pyarrow_version": pyarrow.__version__,
                    "pandas_version": pandas.__version__
                }
            }
        except ImportError as e:
            return {"status": "unavailable", "error": f"Arrow/Parquet libraries not available: {e}"}
    
    async def _update_filesystem_status(self):
        """Update filesystem and VFS status."""
        try:
            # Get filesystem usage
            filesystem_stats = {}
            
            # Check main filesystem
            statvfs = os.statvfs('/')
            total_space = statvfs.f_frsize * statvfs.f_blocks
            free_space = statvfs.f_frsize * statvfs.f_avail
            used_space = total_space - free_space
            
            filesystem_stats = {
                "total_space_gb": round(total_space / (1024**3), 2),
                "free_space_gb": round(free_space / (1024**3), 2),
                "used_space_gb": round(used_space / (1024**3), 2),
                "usage_percent": round((used_space / total_space) * 100, 2) if total_space > 0 else 0
            }
            
            # Check IPFS repository if available
            ipfs_repo_path = os.path.expanduser("~/.ipfs")
            if os.path.exists(ipfs_repo_path):
                repo_size = sum(f.stat().st_size for f in Path(ipfs_repo_path).rglob('*') if f.is_file())
                filesystem_stats["ipfs_repo_size_mb"] = round(repo_size / (1024**2), 2)
            
            self.status_cache["filesystem"] = filesystem_stats
            
        except Exception as e:
            logger.error(f"Error updating filesystem status: {e}")
            self.status_cache["filesystem"] = {"error": str(e)}
    
    async def _update_performance_metrics(self):
        """Update system performance metrics."""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network stats
            network = psutil.net_io_counters()
            
            self.status_cache["performance"] = {
                "cpu_usage_percent": cpu_percent,
                "memory_usage_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_usage_percent": round((disk.used / disk.total) * 100, 2),
                "network_bytes_sent": network.bytes_sent,
                "network_bytes_recv": network.bytes_recv,
                "uptime_seconds": time.time() - self.startup_time
            }
            
        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}")
            self.status_cache["performance"] = {"error": str(e)}
    
    async def _generate_alerts(self):
        """Generate alerts based on current status."""
        alerts = []
        current_time = time.time()
        
        # Check for stopped daemons
        for daemon_id, daemon_info in self.status_cache["daemons"].items():
            if daemon_info["status"] == "stopped":
                alerts.append({
                    "level": "warning",
                    "type": "daemon_stopped",
                    "message": f"{daemon_id.upper()} daemon is not running",
                    "daemon": daemon_id,
                    "timestamp": current_time
                })
            elif daemon_info["status"] == "error":
                alerts.append({
                    "level": "error",
                    "type": "daemon_error",
                    "message": f"{daemon_id.upper()} daemon has errors",
                    "daemon": daemon_id,
                    "timestamp": current_time
                })
        
        # Check for backend issues
        for backend_id, backend_info in self.status_cache["backends"].items():
            if backend_info["status"] == "error":
                alerts.append({
                    "level": "error",
                    "type": "backend_error",
                    "message": f"{backend_info['name']} backend has errors",
                    "backend": backend_id,
                    "timestamp": current_time
                })
            elif backend_info["status"] == "unavailable":
                alerts.append({
                    "level": "info",
                    "type": "backend_unavailable",
                    "message": f"{backend_info['name']} backend is not available",
                    "backend": backend_id,
                    "timestamp": current_time
                })
        
        # Check performance thresholds
        performance = self.status_cache.get("performance", {})
        if performance.get("cpu_usage_percent", 0) > 80:
            alerts.append({
                "level": "warning",
                "type": "high_cpu",
                "message": f"High CPU usage: {performance['cpu_usage_percent']:.1f}%",
                "timestamp": current_time
            })
        
        if performance.get("memory_usage_percent", 0) > 85:
            alerts.append({
                "level": "warning",
                "type": "high_memory",
                "message": f"High memory usage: {performance['memory_usage_percent']:.1f}%",
                "timestamp": current_time
            })
        
        filesystem = self.status_cache.get("filesystem", {})
        if filesystem.get("usage_percent", 0) > 90:
            alerts.append({
                "level": "critical",
                "type": "disk_space",
                "message": f"Low disk space: {filesystem['usage_percent']:.1f}% used",
                "timestamp": current_time
            })
        
        self.status_cache["alerts"] = alerts
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive status of all backends and systems."""
        return {
            "timestamp": time.time(),
            "uptime_seconds": time.time() - self.startup_time,
            "daemons": self.status_cache["daemons"],
            "backends": self.status_cache["backends"],
            "filesystem": self.status_cache["filesystem"],
            "performance": self.status_cache["performance"],
            "alerts": self.status_cache["alerts"],
            "multi_backend_fs": {
                "available": self.multi_backend_fs is not None,
                "default_backend": getattr(self.multi_backend_fs, 'default_backend_id', None) if self.multi_backend_fs else None,
                "registered_backends": len(self.backends)
            },
            "last_updated": self.status_cache["last_updated"]
        }
    
    def get_backend_recommendations(self) -> List[Dict[str, Any]]:
        """Get recommendations for improving backend performance."""
        recommendations = []
        
        # Check for missing critical backends
        critical_backends = ["ipfs", "lotus"]
        for backend_id in critical_backends:
            if backend_id not in self.status_cache["backends"] or self.status_cache["backends"][backend_id]["status"] != "running":
                recommendations.append({
                    "type": "critical",
                    "category": "backend",
                    "title": f"Start {backend_id.upper()} Backend",
                    "description": f"The {backend_id.upper()} backend is not running. This is required for core functionality.",
                    "action": f"Start the {backend_id} daemon using the appropriate installer or daemon manager."
                })
        
        # Check for performance issues
        performance = self.status_cache.get("performance", {})
        if performance.get("memory_usage_percent", 0) > 80:
            recommendations.append({
                "type": "warning",
                "category": "performance",
                "title": "High Memory Usage",
                "description": f"System memory usage is at {performance['memory_usage_percent']:.1f}%",
                "action": "Consider stopping unnecessary services or adding more RAM."
            })
        
        # Check for optional but beneficial backends
        beneficial_backends = {
            "lassie": "Enable fast IPFS content retrieval",
            "storacha": "Enable Web3.Storage integration for decentralized backup",
            "s3": "Enable S3 storage for cloud backup and redundancy"
        }
        
        for backend_id, benefit in beneficial_backends.items():
            if backend_id not in self.status_cache["backends"] or self.status_cache["backends"][backend_id]["status"] == "unavailable":
                recommendations.append({
                    "type": "suggestion",
                    "category": "optimization",
                    "title": f"Enable {backend_id.upper()} Backend",
                    "description": benefit,
                    "action": f"Install and configure the {backend_id} backend for enhanced functionality."
                })
        
        return recommendations

# Global monitor instance
monitor = BackendMonitor()

async def get_comprehensive_backend_status() -> Dict[str, Any]:
    """Get comprehensive status of all backends - main entry point for dashboard."""
    try:
        # Initialize if not already done
        if not monitor.backends and not monitor.daemon_managers:
            await monitor.initialize()
        
        # Update status
        await monitor.update_all_status()
        
        # Return comprehensive status
        return monitor.get_comprehensive_status()
        
    except Exception as e:
        logger.error(f"Error getting backend status: {e}")
        return {
            "error": str(e),
            "timestamp": time.time(),
            "status": "error"
        }

async def get_backend_recommendations() -> List[Dict[str, Any]]:
    """Get recommendations for backend optimization."""
    try:
        if not monitor.status_cache["backends"]:
            await monitor.update_all_status()
        
        return monitor.get_backend_recommendations()
        
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        return [{
            "type": "error",
            "category": "system",
            "title": "Monitoring Error",
            "description": f"Failed to generate recommendations: {e}",
            "action": "Check system logs for details."
        }]

if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Test the backend monitor
        print("🔧 Testing Comprehensive Backend Monitor")
        print("=" * 60)
        
        # Initialize
        await monitor.initialize()
        
        # Get status
        status = await get_comprehensive_backend_status()
        
        print(f"📊 Found {len(status['backends'])} backends:")
        for backend_id, info in status['backends'].items():
            print(f"  • {info['name']}: {info['status']}")
        
        print(f"\n🔧 Found {len(status['daemons'])} daemons:")
        for daemon_id, info in status['daemons'].items():
            print(f"  • {daemon_id.upper()}: {info['status']}")
        
        print(f"\n⚡ Performance:")
        perf = status['performance']
        print(f"  • CPU: {perf.get('cpu_usage_percent', 0):.1f}%")
        print(f"  • Memory: {perf.get('memory_usage_percent', 0):.1f}%")
        print(f"  • Disk: {perf.get('disk_usage_percent', 0):.1f}%")
        
        print(f"\n🚨 Alerts: {len(status['alerts'])}")
        for alert in status['alerts']:
            print(f"  • {alert['level'].upper()}: {alert['message']}")
        
        # Get recommendations
        recommendations = await get_backend_recommendations()
        print(f"\n💡 Recommendations: {len(recommendations)}")
        for rec in recommendations[:3]:  # Show first 3
            print(f"  • {rec['title']}: {rec['description']}")
    
    asyncio.run(main())
