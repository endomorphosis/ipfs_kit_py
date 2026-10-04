"""
System tools for MCP server.
"""

from typing import Dict, Any
import logging
import time
import psutil

logger = logging.getLogger(__name__)


class SystemTools:
    """Tools for system operations."""
    
    def __init__(self, backend_monitor):
        self.backend_monitor = backend_monitor
        self.start_time = time.time()
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health."""
        try:
            # Get backend health
            backend_health = await self.backend_monitor.check_all_backends()
            
            # Get system performance
            process = psutil.Process()
            performance = {
                "memory_usage_mb": process.memory_info().rss / 1024 / 1024,
                "cpu_usage_percent": process.cpu_percent(),
                "uptime_seconds": time.time() - self.start_time
            }
            
            # Count healthy backends
            healthy_count = sum(1 for backend in backend_health.values() 
                              if backend.get("health") == "healthy")
            total_count = len(backend_health)
            
            return {
                "status": "running",
                "uptime_seconds": performance["uptime_seconds"],
                "memory_usage_mb": performance["memory_usage_mb"],
                "cpu_usage_percent": performance["cpu_usage_percent"],
                "backend_health": backend_health,
                "healthy_backends": healthy_count,
                "total_backends": total_count,
                "health_percentage": (healthy_count / total_count * 100) if total_count > 0 else 0
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def get_development_insights(self) -> Dict[str, Any]:
        """Get development insights and recommendations."""
        try:
            backend_health = await self.backend_monitor.check_all_backends()
            insights = self._generate_development_insights(backend_health)
            
            return {
                "insights": insights,
                "backend_health": backend_health
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _generate_development_insights(self, backend_health: Dict[str, Any]) -> str:
        """Generate development insights based on backend status."""
        
        insights = []
        
        # Check for common issues
        unhealthy_backends = [name for name, backend in backend_health.items() 
                            if backend.get("health") == "unhealthy"]
        
        if unhealthy_backends:
            insights.append(f"⚠️ **Unhealthy Backends**: {', '.join(unhealthy_backends)}")
            
            for backend_name in unhealthy_backends:
                backend = backend_health[backend_name]
                error = backend.get("error", "Unknown error")
                
                if "connection" in error.lower() or "timeout" in error.lower():
                    insights.append(f"🔌 **{backend_name}**: Connection issue - check if service is running")
                elif "permission" in error.lower() or "auth" in error.lower():
                    insights.append(f"🔐 **{backend_name}**: Authentication issue - check credentials")
                elif "not found" in error.lower():
                    insights.append(f"📍 **{backend_name}**: Service not found - check endpoint configuration")
        
        # Check for partially working backends
        partial_backends = [name for name, backend in backend_health.items() 
                          if backend.get("health") == "partial"]
        
        if partial_backends:
            insights.append(f"⚠️ **Partially Working**: {', '.join(partial_backends)}")
        
        # Performance recommendations
        healthy_backends = [name for name, backend in backend_health.items() 
                          if backend.get("health") == "healthy"]
        
        if len(healthy_backends) > 0:
            insights.append(f"✅ **Healthy Backends**: {', '.join(healthy_backends)}")
        
        # Integration recommendations
        if "ipfs" in healthy_backends and "ipfs_cluster" not in healthy_backends:
            insights.append("💡 **Scaling**: Consider setting up IPFS Cluster for distributed storage")
        
        if "lotus" in healthy_backends and "synapse" in healthy_backends:
            insights.append("🚀 **Advanced**: You have both Lotus and Synapse - great for Filecoin integration!")
        
        if "huggingface" in healthy_backends and "s3" in healthy_backends:
            insights.append("🤖 **AI/ML**: HuggingFace + S3 setup is perfect for ML model storage")
        
        # Development suggestions
        if len(healthy_backends) >= 3:
            insights.append("🎯 **Ready for Production**: Multiple healthy backends - consider load balancing")
        
        return "<br>".join(insights) if insights else "All systems are running smoothly! 🎉"
