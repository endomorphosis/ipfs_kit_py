#!/usr/bin/env python3
"""
Real Filesystem Monitor

Provides actual filesystem monitoring with real data including:
- IPFS node status and connectivity
- Filesystem backend health
- Storage usage and performance
- Real-time operation monitoring
- Network statistics
"""

import os
import json
import time
import psutil
import subprocess
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import shutil

logger = logging.getLogger(__name__)

class FilesystemMonitor:
    """Monitor real filesystem backends and provide actionable data."""
    
    def __init__(self):
        self.ipfs_path = os.path.expanduser("~/.ipfs")
        self.start_time = time.time()
        
    def get_ipfs_status(self) -> Dict[str, Any]:
        """Get real IPFS daemon status."""
        try:
            # Check if IPFS daemon is running
            result = subprocess.run(['ipfs', 'id'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                ipfs_id = json.loads(result.stdout)
                
                # Get additional stats
                version_result = subprocess.run(['ipfs', 'version'], capture_output=True, text=True, timeout=5)
                version = version_result.stdout.strip() if version_result.returncode == 0 else "unknown"
                
                # Get repo stats
                stats_result = subprocess.run(['ipfs', 'repo', 'stat'], capture_output=True, text=True, timeout=5)
                repo_stats = {}
                if stats_result.returncode == 0:
                    for line in stats_result.stdout.strip().split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            repo_stats[key.strip()] = value.strip()
                
                # Get swarm peers
                peers_result = subprocess.run(['ipfs', 'swarm', 'peers'], capture_output=True, text=True, timeout=5)
                peer_count = len(peers_result.stdout.strip().split('\n')) if peers_result.returncode == 0 and peers_result.stdout.strip() else 0
                
                return {
                    "status": "running",
                    "peer_id": ipfs_id.get("ID", "unknown"),
                    "version": version,
                    "addresses": ipfs_id.get("Addresses", []),
                    "connected_peers": peer_count,
                    "repo_stats": repo_stats,
                    "api_available": True
                }
            else:
                return {
                    "status": "stopped",
                    "error": result.stderr,
                    "api_available": False
                }
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "error": "IPFS command timed out",
                "api_available": False
            }
        except FileNotFoundError:
            return {
                "status": "not_installed",
                "error": "IPFS binary not found",
                "api_available": False
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "api_available": False
            }
    
    def get_filesystem_backends(self) -> Dict[str, Any]:
        """Get status of different filesystem backends."""
        backends = {}
        
        # IPFS backend
        ipfs_status = self.get_ipfs_status()
        backends["ipfs"] = {
            "type": "IPFS",
            "status": ipfs_status["status"],
            "healthy": ipfs_status["status"] == "running",
            "details": ipfs_status,
            "storage_path": self.ipfs_path
        }
        
        # Local filesystem backend
        try:
            local_stats = shutil.disk_usage("/")
            backends["local"] = {
                "type": "Local Filesystem",
                "status": "running",
                "healthy": True,
                "details": {
                    "total_bytes": local_stats.total,
                    "used_bytes": local_stats.used,
                    "free_bytes": local_stats.free,
                    "usage_percent": (local_stats.used / local_stats.total) * 100
                },
                "storage_path": "/"
            }
        except Exception as e:
            backends["local"] = {
                "type": "Local Filesystem",
                "status": "error",
                "healthy": False,
                "details": {"error": str(e)},
                "storage_path": "/"
            }
        
        # IPFS repository backend (if exists)
        if os.path.exists(self.ipfs_path):
            try:
                ipfs_stats = shutil.disk_usage(self.ipfs_path)
                backends["ipfs_repo"] = {
                    "type": "IPFS Repository",
                    "status": "available",
                    "healthy": True,
                    "details": {
                        "total_bytes": ipfs_stats.total,
                        "used_bytes": ipfs_stats.used,
                        "free_bytes": ipfs_stats.free,
                        "usage_percent": (ipfs_stats.used / ipfs_stats.total) * 100,
                        "repo_path": self.ipfs_path
                    },
                    "storage_path": self.ipfs_path
                }
            except Exception as e:
                backends["ipfs_repo"] = {
                    "type": "IPFS Repository",
                    "status": "error",
                    "healthy": False,
                    "details": {"error": str(e)},
                    "storage_path": self.ipfs_path
                }
        
        return backends
    
    def get_system_performance(self) -> Dict[str, Any]:
        """Get real system performance metrics."""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network I/O
            net_io = psutil.net_io_counters()
            
            # Process count
            process_count = len(psutil.pids())
            
            # Load average (Unix only)
            load_avg = None
            try:
                load_avg = os.getloadavg()
            except:
                pass
            
            return {
                "cpu_usage_percent": cpu_percent,
                "memory": {
                    "total_bytes": memory.total,
                    "available_bytes": memory.available,
                    "used_bytes": memory.used,
                    "usage_percent": memory.percent
                },
                "disk": {
                    "total_bytes": disk.total,
                    "used_bytes": disk.used,
                    "free_bytes": disk.free,
                    "usage_percent": (disk.used / disk.total) * 100
                },
                "network": {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv
                },
                "processes": process_count,
                "load_average": load_avg,
                "uptime_seconds": time.time() - self.start_time
            }
        except Exception as e:
            logger.error(f"Error getting system performance: {e}")
            return {"error": str(e)}
    
    def get_ipfs_operations(self) -> Dict[str, Any]:
        """Get recent IPFS operations and statistics."""
        try:
            operations = {
                "recent_operations": [],
                "operation_stats": {
                    "total_operations": 0,
                    "successful_operations": 0,
                    "failed_operations": 0,
                    "avg_response_time_ms": 0
                }
            }
            
            # Try to get some IPFS stats
            if self.get_ipfs_status()["status"] == "running":
                # Get repository version
                try:
                    version_result = subprocess.run(['ipfs', 'repo', 'version'], 
                                                  capture_output=True, text=True, timeout=5)
                    if version_result.returncode == 0:
                        operations["repo_version"] = version_result.stdout.strip()
                except:
                    pass
                
                # Get bandwidth stats if available
                try:
                    bw_result = subprocess.run(['ipfs', 'stats', 'bw'], 
                                             capture_output=True, text=True, timeout=5)
                    if bw_result.returncode == 0:
                        operations["bandwidth_stats"] = bw_result.stdout.strip()
                except:
                    pass
            
            return operations
            
        except Exception as e:
            logger.error(f"Error getting IPFS operations: {e}")
            return {"error": str(e)}
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive filesystem status."""
        return {
            "timestamp": time.time(),
            "ipfs_status": self.get_ipfs_status(),
            "filesystem_backends": self.get_filesystem_backends(),
            "system_performance": self.get_system_performance(),
            "ipfs_operations": self.get_ipfs_operations(),
            "health_summary": self._generate_health_summary()
        }
    
    def _generate_health_summary(self) -> Dict[str, Any]:
        """Generate overall health summary."""
        backends = self.get_filesystem_backends()
        ipfs_status = self.get_ipfs_status()
        system_perf = self.get_system_performance()
        
        healthy_backends = sum(1 for b in backends.values() if b.get("healthy", False))
        total_backends = len(backends)
        
        # Determine overall health
        health_score = 100
        issues = []
        
        if ipfs_status["status"] != "running":
            health_score -= 40
            issues.append("IPFS daemon not running")
        
        if healthy_backends < total_backends:
            health_score -= 20 * (total_backends - healthy_backends)
            issues.append(f"{total_backends - healthy_backends} backend(s) unhealthy")
        
        if "error" not in system_perf:
            if system_perf.get("cpu_usage_percent", 0) > 90:
                health_score -= 15
                issues.append("High CPU usage")
            
            if system_perf.get("memory", {}).get("usage_percent", 0) > 90:
                health_score -= 15
                issues.append("High memory usage")
            
            if system_perf.get("disk", {}).get("usage_percent", 0) > 90:
                health_score -= 10
                issues.append("High disk usage")
        
        # Categorize health
        if health_score >= 80:
            status = "healthy"
        elif health_score >= 60:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "overall_status": status,
            "health_score": max(0, health_score),
            "healthy_backends": healthy_backends,
            "total_backends": total_backends,
            "issues": issues,
            "recommendations": self._generate_recommendations(backends, ipfs_status, system_perf)
        }
    
    def _generate_recommendations(self, backends, ipfs_status, system_perf) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        if ipfs_status["status"] != "running":
            recommendations.append("Start IPFS daemon: 'ipfs daemon'")
        
        if ipfs_status["status"] == "running" and ipfs_status.get("connected_peers", 0) == 0:
            recommendations.append("IPFS has no connected peers - check network connectivity")
        
        if "error" not in system_perf:
            if system_perf.get("cpu_usage_percent", 0) > 90:
                recommendations.append("Consider reducing CPU-intensive operations")
            
            if system_perf.get("memory", {}).get("usage_percent", 0) > 90:
                recommendations.append("Consider freeing memory or adding more RAM")
            
            if system_perf.get("disk", {}).get("usage_percent", 0) > 90:
                recommendations.append("Free up disk space or add more storage")
        
        unhealthy_backends = [name for name, backend in backends.items() if not backend.get("healthy", False)]
        if unhealthy_backends:
            recommendations.append(f"Fix unhealthy backends: {', '.join(unhealthy_backends)}")
        
        if not recommendations:
            recommendations.append("System appears healthy - no immediate actions needed")
        
        return recommendations
