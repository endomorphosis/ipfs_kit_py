"""
Health endpoints for API routes.
"""

import logging
import time
import psutil
from typing import Dict, Any

logger = logging.getLogger(__name__)


class HealthEndpoints:
    """Health-related API endpoints."""
    
    def __init__(self, backend_monitor):
        self.backend_monitor = backend_monitor
        self.start_time = time.time()
    
    async def get_all_backends_status(self) -> Dict[str, Any]:
        """Get all backends with their full status."""
        try:
            backends_status = {}
            for backend_name in self.backend_monitor.backends.keys():
                backends_status[backend_name] = await self.get_backend_detailed(backend_name)
            return backends_status
        except Exception as e:
            logger.error(f"Error getting all backends status: {e}")
            return {"error": str(e)}

    async def get_health(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        try:
            # Get system performance
            process = psutil.Process()
            performance = {
                "memory_usage_mb": process.memory_info().rss / 1024 / 1024,
                "cpu_usage_percent": process.cpu_percent(),
                "uptime_seconds": time.time() - self.start_time
            }
            
            # Get backend health
            backend_health = await self.backend_monitor.check_all_backends()
            
            return {
                "status": "running",
                "uptime_seconds": performance["uptime_seconds"],
                "memory_usage_mb": performance["memory_usage_mb"],
                "cpu_usage_percent": performance["cpu_usage_percent"],
                "backend_health": backend_health
            }
        except Exception as e:
            logger.error(f"Error getting health: {e}")
            return {"error": str(e)}
    
    async def get_all_backends(self) -> Dict[str, Any]:
        """Get all backends status."""
        try:
            return await self.backend_monitor.check_all_backends()
        except Exception as e:
            logger.error(f"Error getting backends: {e}")
            return {"error": str(e)}
    
    async def get_backend_status(self, backend_name: str) -> Dict[str, Any]:
        """Get specific backend status."""
        try:
            return await self.backend_monitor.check_backend_health(backend_name)
        except Exception as e:
            logger.error(f"Error getting backend {backend_name}: {e}")
            return {"error": str(e)}
    
    async def get_backend_detailed(self, backend_name: str) -> Dict[str, Any]:
        """Get detailed backend information."""
        try:
            basic_info = await self.backend_monitor.check_backend_health(backend_name)
            
            if backend_name in self.backend_monitor.backends:
                client = self.backend_monitor.backends[backend_name]
                async with client:
                    detailed_info = await client.get_status()
                    basic_info["detailed"] = detailed_info
            
            return basic_info
        except Exception as e:
            logger.error(f"Error getting detailed backend {backend_name}: {e}")
            return {"error": str(e)}
    
    async def get_backend_info(self, backend_name: str) -> Dict[str, Any]:
        """Get backend information."""
        try:
            return await self.get_backend_detailed(backend_name)
        except Exception as e:
            logger.error(f"Error getting backend info {backend_name}: {e}")
            return {"error": str(e)}
    
    async def restart_backend(self, backend_name: str) -> Dict[str, Any]:
        """Restart a backend."""
        try:
            success = await self.backend_monitor.restart_backend(backend_name)
            return {
                "success": success,
                "message": f"Backend {backend_name} restart {'successful' if success else 'failed'}"
            }
        except Exception as e:
            logger.error(f"Error restarting backend {backend_name}: {e}")
            return {"error": str(e)}
    
    async def get_comprehensive_monitoring(self) -> Dict[str, Any]:
        """Get comprehensive monitoring data."""
        try:
            # Get all backends with detailed status
            backends_status = await self.get_all_backends_status()
            
            # Get system performance
            process = psutil.Process()
            performance = {
                "memory_usage_mb": process.memory_info().rss / 1024 / 1024,
                "cpu_usage_percent": process.cpu_percent(),
                "uptime_seconds": time.time() - self.start_time
            }
            
            # Get VFS health if available
            vfs_health = {}
            if hasattr(self.backend_monitor, 'vfs_observability_manager'):
                vfs_health = await self.backend_monitor.vfs_observability_manager.get_vfs_health()
            
            return {
                "status": "ok",
                "timestamp": time.time(),
                "performance": performance,
                "backends": backends_status,
                "vfs_health": vfs_health
            }
        except Exception as e:
            logger.error(f"Error getting comprehensive monitoring: {e}")
            return {"error": str(e), "status": "error"}
    
    async def get_monitoring_metrics(self) -> Dict[str, Any]:
        """Get monitoring metrics."""
        try:
            # Get system metrics
            process = psutil.Process()
            metrics = {
                "memory_usage_mb": process.memory_info().rss / 1024 / 1024,
                "cpu_usage_percent": process.cpu_percent(),
                "uptime_seconds": time.time() - self.start_time,
                "timestamp": time.time()
            }
            
            # Get backend metrics
            backend_metrics = {}
            for backend_name in self.backend_monitor.backends.keys():
                backend_health = await self.backend_monitor.check_backend_health(backend_name)
                backend_metrics[backend_name] = {
                    "status": backend_health.get("status", "unknown"),
                    "response_time_ms": backend_health.get("response_time_ms", 0),
                    "last_check": backend_health.get("timestamp", 0)
                }
            
            metrics["backends"] = backend_metrics
            return metrics
        except Exception as e:
            logger.error(f"Error getting monitoring metrics: {e}")
            return {"error": str(e)}
    
    async def get_monitoring_alerts(self) -> Dict[str, Any]:
        """Get monitoring alerts."""
        try:
            alerts = []
            
            # Check for backend alerts
            for backend_name in self.backend_monitor.backends.keys():
                backend_health = await self.backend_monitor.check_backend_health(backend_name)
                if backend_health.get("status") != "healthy":
                    alerts.append({
                        "type": "backend_unhealthy",
                        "severity": "warning",
                        "message": f"Backend {backend_name} is {backend_health.get('status', 'unknown')}",
                        "timestamp": time.time(),
                        "backend": backend_name
                    })
            
            # Check for system alerts
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
            
            if memory_mb > 1000:  # Alert if memory usage > 1GB
                alerts.append({
                    "type": "high_memory_usage",
                    "severity": "warning",
                    "message": f"High memory usage: {memory_mb:.1f}MB",
                    "timestamp": time.time(),
                    "value": memory_mb
                })
            
            if cpu_percent > 80:  # Alert if CPU usage > 80%
                alerts.append({
                    "type": "high_cpu_usage",
                    "severity": "warning",
                    "message": f"High CPU usage: {cpu_percent:.1f}%",
                    "timestamp": time.time(),
                    "value": cpu_percent
                })
            
            return {
                "alerts": alerts,
                "count": len(alerts),
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error getting monitoring alerts: {e}")
            return {"error": str(e), "alerts": [], "count": 0}
    
    async def get_backend_logs(self, backend_name: str) -> Dict[str, Any]:
        """Get backend logs."""
        try:
            # For now, return metrics history as "logs"
            history = self.backend_monitor.get_metrics_history(backend_name, 20)
            logs = "\n".join([
                f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(m['timestamp']))}] "
                f"Health: {m['health']}, Status: {m['status']}"
                + (f", Error: {m['error']}" if 'error' in m else "")
                for m in history
            ])
            return {"logs": logs or "No logs available"}
        except Exception as e:
            logger.error(f"Error getting logs for {backend_name}: {e}")
            return {"error": str(e)}
    
    async def get_backend_metrics(self, backend_name: str) -> Dict[str, Any]:
        """Get backend metrics."""
        try:
            metrics = self.backend_monitor.get_metrics_history(backend_name, 50)
            return {"backend": backend_name, "metrics": metrics}
        except Exception as e:
            logger.error(f"Error getting metrics for {backend_name}: {e}")
            return {"error": str(e)}
    
    async def get_insights(self) -> Dict[str, Any]:
        """Get system insights."""
        try:
            backend_health = await self.backend_monitor.check_all_backends()
            insights = self._generate_insights(backend_health)
            return {"insights": insights}
        except Exception as e:
            logger.error(f"Error getting insights: {e}")
            return {"error": str(e)}
    
    async def get_system_logs(self) -> Dict[str, Any]:
        """Get system logs."""
        try:
            # Return recent activity across all backends
            all_logs = []
            for backend_name in self.backend_monitor.backends.keys():
                history = self.backend_monitor.get_metrics_history(backend_name, 10)
                for metric in history:
                    all_logs.append({
                        "timestamp": metric["timestamp"],
                        "backend": backend_name,
                        "message": f"Health: {metric['health']}, Status: {metric['status']}"
                    })
            
            # Sort by timestamp
            all_logs.sort(key=lambda x: x["timestamp"], reverse=True)
            
            # Format as text
            logs = "\n".join([
                f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(log['timestamp']))}] "
                f"{log['backend']}: {log['message']}"
                for log in all_logs[:50]  # Last 50 entries
            ])
            
            return {"logs": logs or "No system logs available"}
        except Exception as e:
            logger.error(f"Error getting system logs: {e}")
            return {"error": str(e)}
    
    def _generate_insights(self, backend_health: Dict[str, Any]) -> str:
        """Generate insights from backend health."""
        insights = []
        
        healthy_backends = [name for name, backend in backend_health.items() 
                          if backend.get("health") == "healthy"]
        unhealthy_backends = [name for name, backend in backend_health.items() 
                            if backend.get("health") == "unhealthy"]
        
        if healthy_backends:
            insights.append(f"✅ Healthy: {', '.join(healthy_backends)}")
        
        if unhealthy_backends:
            insights.append(f"❌ Unhealthy: {', '.join(unhealthy_backends)}")
        
        # Add specific recommendations
        if "ipfs" in healthy_backends and "ipfs_cluster" not in healthy_backends:
            insights.append("💡 Consider setting up IPFS Cluster for scalability")
        
        if len(healthy_backends) >= 3:
            insights.append("🎯 Multiple backends healthy - ready for production")
        
        return " | ".join(insights) if insights else "All systems operating normally"
