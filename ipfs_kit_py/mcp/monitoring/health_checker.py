"""
Health Checker for MCP Server.

This module provides health check functionality for the MCP server,
allowing for monitoring of component health and system status.
"""

import logging
import time
import asyncio
import threading
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Set, Union, Tuple

# Configure logger
logger = logging.getLogger(__name__)

class HealthStatus(str, Enum):
    """Enum representing the health status of a component."""
    OK = "ok"
    DEGRADED = "degraded"
    FAILING = "failing"
    UNKNOWN = "unknown"

class ComponentHealth:
    """
    Represents the health status of a component.
    
    Stores information about a component's health status, including
    status, details, last check time, and check duration.
    """
    
    def __init__(
        self,
        component: str,
        status: HealthStatus = HealthStatus.UNKNOWN,
        details: str = "",
        last_check_time: float = None,
        check_duration: float = 0.0,
    ):
        """
        Initialize a component health status.
        
        Args:
            component: Name of the component
            status: Health status enum value
            details: Additional details about the health status
            last_check_time: Unix timestamp of the last health check
            check_duration: Duration of the last health check in seconds
        """
        self.component = component
        self.status = status
        self.details = details
        self.last_check_time = last_check_time or time.time()
        self.check_duration = check_duration
    
    def update(
        self,
        status: HealthStatus,
        details: str = "",
        check_duration: float = 0.0,
    ) -> None:
        """
        Update the health status.
        
        Args:
            status: New health status
            details: Additional details about the health status
            check_duration: Duration of the health check in seconds
        """
        self.status = status
        self.details = details
        self.last_check_time = time.time()
        self.check_duration = check_duration
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to a dictionary representation.
        
        Returns:
            Dictionary representation of the health status
        """
        return {
            "component": self.component,
            "status": self.status.value,
            "details": self.details,
            "last_check_time": self.last_check_time,
            "check_duration": self.check_duration,
        }

class HealthChecker:
    """
    Health checker for the MCP server.
    
    Provides functionality to check and report the health status
    of various components in the MCP system.
    """
    
    def __init__(self, check_interval: int = 60):
        """
        Initialize the health checker.
        
        Args:
            check_interval: Interval in seconds between automatic health checks
        """
        self.check_interval = check_interval
        self._components: Dict[str, ComponentHealth] = {}
        self._check_functions: Dict[str, Callable] = {}
        self._async_check_functions: Dict[str, Callable] = {}
        self._check_lock = threading.RLock()
        self._auto_check_thread = None
        self._shutdown_event = threading.Event()
        self._last_system_status: HealthStatus = HealthStatus.UNKNOWN
    
    def register_component(
        self,
        component: str,
        check_function: Optional[Callable[[], Tuple[HealthStatus, str]]] = None,
        async_check_function: Optional[Callable[[], asyncio.coroutine]] = None,
        initial_status: HealthStatus = HealthStatus.UNKNOWN,
        initial_details: str = "Not checked yet",
    ) -> None:
        """
        Register a component for health checking.
        
        Args:
            component: Name of the component
            check_function: Function to check the component's health (synchronous)
            async_check_function: Function to check the component's health (asynchronous)
            initial_status: Initial health status
            initial_details: Initial health details
        """
        with self._check_lock:
            self._components[component] = ComponentHealth(
                component=component,
                status=initial_status,
                details=initial_details,
            )
            
            if check_function:
                self._check_functions[component] = check_function
                logger.debug(f"Registered sync check function for component {component}")
            
            if async_check_function:
                self._async_check_functions[component] = async_check_function
                logger.debug(f"Registered async check function for component {component}")
            
            logger.info(f"Registered component {component} for health checking")
    
    def update_component_health(
        self,
        component: str,
        status: HealthStatus,
        details: str = "",
        check_duration: float = 0.0,
    ) -> None:
        """
        Update the health status of a component.
        
        Args:
            component: Name of the component
            status: New health status
            details: Additional details about the health status
            check_duration: Duration of the health check in seconds
        """
        with self._check_lock:
            if component not in self._components:
                # Auto-register the component if it's not registered
                self.register_component(
                    component=component,
                    initial_status=status,
                    initial_details=details,
                )
            else:
                self._components[component].update(
                    status=status,
                    details=details,
                    check_duration=check_duration,
                )
            
            logger.debug(f"Updated health status for component {component}: {status.value}")
    
    def check_component_health(self, component: str) -> ComponentHealth:
        """
        Check the health of a specific component.
        
        Args:
            component: Name of the component to check
        
        Returns:
            Component health status
        
        Raises:
            ValueError: If the component is not registered
        """
        with self._check_lock:
            if component not in self._components:
                raise ValueError(f"Component {component} not registered")
            
            if component in self._check_functions:
                # Run synchronous health check
                check_function = self._check_functions[component]
                
                start_time = time.time()
                try:
                    status, details = check_function()
                    check_duration = time.time() - start_time
                    
                    self._components[component].update(
                        status=status,
                        details=details,
                        check_duration=check_duration,
                    )
                    
                    logger.debug(f"Checked health for component {component}: {status.value}")
                except Exception as e:
                    check_duration = time.time() - start_time
                    error_msg = f"Error checking health for component {component}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    
                    self._components[component].update(
                        status=HealthStatus.FAILING,
                        details=error_msg,
                        check_duration=check_duration,
                    )
            
            # If no check function or just returns the current status
            return self._components[component]
    
    async def check_component_health_async(self, component: str) -> ComponentHealth:
        """
        Check the health of a specific component asynchronously.
        
        Args:
            component: Name of the component to check
        
        Returns:
            Component health status
        
        Raises:
            ValueError: If the component is not registered
        """
        if component not in self._components:
            raise ValueError(f"Component {component} not registered")
        
        if component in self._async_check_functions:
            # Run asynchronous health check
            check_function = self._async_check_functions[component]
            
            start_time = time.time()
            try:
                status, details = await check_function()
                check_duration = time.time() - start_time
                
                with self._check_lock:
                    self._components[component].update(
                        status=status,
                        details=details,
                        check_duration=check_duration,
                    )
                
                logger.debug(f"Checked health for component {component} asynchronously: {status.value}")
            except Exception as e:
                check_duration = time.time() - start_time
                error_msg = f"Error checking health for component {component} asynchronously: {str(e)}"
                logger.error(error_msg, exc_info=True)
                
                with self._check_lock:
                    self._components[component].update(
                        status=HealthStatus.FAILING,
                        details=error_msg,
                        check_duration=check_duration,
                    )
        
        # If no async check function or just returns the current status
        with self._check_lock:
            return self._components[component]
    
    def check_all_health(self) -> Dict[str, ComponentHealth]:
        """
        Check the health of all registered components.
        
        Returns:
            Dictionary of component name to health status
        """
        # Make a copy of the components to avoid modification during iteration
        with self._check_lock:
            components = list(self._components.keys())
        
        # Check each component
        for component in components:
            try:
                self.check_component_health(component)
            except Exception as e:
                logger.error(f"Error checking health for component {component}: {str(e)}", exc_info=True)
        
        # Get updated health status
        with self._check_lock:
            return {component: health for component, health in self._components.items()}
    
    async def check_all_health_async(self) -> Dict[str, ComponentHealth]:
        """
        Check the health of all registered components asynchronously.
        
        Returns:
            Dictionary of component name to health status
        """
        # Make a copy of the components to avoid modification during iteration
        with self._check_lock:
            components = list(self._components.keys())
        
        # Check each component with async function
        async_tasks = []
        for component in components:
            if component in self._async_check_functions:
                task = asyncio.ensure_future(self.check_component_health_async(component))
                async_tasks.append(task)
        
        # Wait for all async checks to complete
        if async_tasks:
            await asyncio.gather(*async_tasks, return_exceptions=True)
        
        # Check remaining components with sync functions
        for component in components:
            if component not in self._async_check_functions and component in self._check_functions:
                try:
                    self.check_component_health(component)
                except Exception as e:
                    logger.error(f"Error checking health for component {component}: {str(e)}", exc_info=True)
        
        # Get updated health status
        with self._check_lock:
            return {component: health for component, health in self._components.items()}
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get the overall system health status.
        
        Aggregates the health status of all components and provides
        an overall system health status.
        
        Returns:
            Dictionary with system health information
        """
        with self._check_lock:
            components = {component: health.to_dict() for component, health in self._components.items()}
            
            # Determine system status based on component statuses
            system_status = HealthStatus.OK
            status_details = []
            
            for component, health in self._components.items():
                if health.status == HealthStatus.FAILING:
                    system_status = HealthStatus.FAILING
                    status_details.append(f"{component}: FAILING - {health.details}")
                elif health.status == HealthStatus.DEGRADED and system_status != HealthStatus.FAILING:
                    system_status = HealthStatus.DEGRADED
                    status_details.append(f"{component}: DEGRADED - {health.details}")
                elif health.status == HealthStatus.UNKNOWN and system_status not in (HealthStatus.FAILING, HealthStatus.DEGRADED):
                    system_status = HealthStatus.UNKNOWN
                    status_details.append(f"{component}: UNKNOWN - {health.details}")
            
            # Cache the system status for later use
            self._last_system_status = system_status
            
            return {
                "status": system_status.value,
                "details": "; ".join(status_details) if status_details else "All systems operational",
                "components": components,
                "timestamp": time.time(),
            }
    
    def get_component_health(self, component: str) -> Dict[str, Any]:
        """
        Get the health status of a specific component.
        
        Args:
            component: Name of the component
        
        Returns:
            Dictionary with component health information
        
        Raises:
            ValueError: If the component is not registered
        """
        with self._check_lock:
            if component not in self._components:
                raise ValueError(f"Component {component} not registered")
            
            return self._components[component].to_dict()
    
    def get_status_counts(self) -> Dict[str, int]:
        """
        Get counts of components by status.
        
        Returns:
            Dictionary with counts of components by status
        """
        status_counts = {status.value: 0 for status in HealthStatus}
        
        with self._check_lock:
            for health in self._components.values():
                status_counts[health.status.value] += 1
        
        return status_counts
    
    def is_system_healthy(self) -> bool:
        """
        Check if the system is healthy (status is OK).
        
        Returns:
            True if the system is healthy, False otherwise
        """
        return self._last_system_status == HealthStatus.OK
    
    def get_health_report(self) -> Dict[str, Any]:
        """
        Get a comprehensive health report.
        
        Returns:
            Dictionary with system health information and component details
        """
        # Get system health first to ensure all statuses are current
        system_health = self.get_system_health()
        status_counts = self.get_status_counts()
        
        return {
            "system": {
                "status": system_health["status"],
                "details": system_health["details"],
                "timestamp": system_health["timestamp"],
            },
            "status_counts": status_counts,
            "components": system_health["components"],
        }
    
    def register_with_fastapi(self, app: Any, path: str = "/health") -> None:
        """
        Register health check endpoints with a FastAPI application.
        
        Args:
            app: FastAPI application to register with
            path: Base path for health check endpoints
        """
        try:
            from fastapi import FastAPI, APIRouter, HTTPException
            
            # Ensure the app is a FastAPI instance
            if not isinstance(app, FastAPI):
                logger.error(f"Cannot register health check endpoints: app is not a FastAPI instance")
                return
            
            # Create a router for health check endpoints
            router = APIRouter(tags=["Health"])
            
            @router.get(path)
            async def health_check():
                """Get overall system health status."""
                health = self.get_system_health()
                if health["status"] != HealthStatus.OK.value:
                    return health
                return health
            
            @router.get(f"{path}/live")
            async def liveness_check():
                """Simple liveness check that always returns 200 if the server is running."""
                return {"status": "alive"}
            
            @router.get(f"{path}/ready")
            async def readiness_check():
                """Check if the system is ready to handle requests."""
                health = self.get_system_health()
                if health["status"] == HealthStatus.FAILING.value:
                    raise HTTPException(status_code=503, detail="Service unavailable")
                return health
            
            @router.get(f"{path}/components")
            async def components_health():
                """Get health status of all components."""
                return {"components": self.get_system_health()["components"]}
            
            @router.get(f"{path}/components/{{component}}")
            async def component_health(component: str):
                """Get health status of a specific component."""
                try:
                    return self.get_component_health(component)
                except ValueError:
                    raise HTTPException(status_code=404, detail=f"Component {component} not found")
            
            @router.post(f"{path}/check")
            async def run_health_check():
                """Run health checks for all components."""
                await self.check_all_health_async()
                return self.get_health_report()
            
            # Include the router in the app
            app.include_router(router)
            logger.info(f"Registered health check endpoints at {path}")
            
        except ImportError:
            logger.error("Cannot register health check endpoints: fastapi not available")
    
    def register_with_router(self, router: Any, path: str = "") -> None:
        """
        Register health check endpoints with a FastAPI router.
        
        Args:
            router: FastAPI router to register with
            path: Base path for health check endpoints (relative to router prefix)
        """
        try:
            from fastapi import APIRouter, HTTPException
            
            # Ensure the router is an APIRouter instance
            if not isinstance(router, APIRouter):
                logger.error(f"Cannot register health check endpoints with router: not an APIRouter instance")
                return
            
            @router.get(f"{path}")
            async def health_check():
                """Get overall system health status."""
                health = self.get_system_health()
                if health["status"] != HealthStatus.OK.value:
                    return health
                return health
            
            @router.get(f"{path}/live")
            async def liveness_check():
                """Simple liveness check that always returns 200 if the server is running."""
                return {"status": "alive"}
            
            @router.get(f"{path}/ready")
            async def readiness_check():
                """Check if the system is ready to handle requests."""
                health = self.get_system_health()
                if health["status"] == HealthStatus.FAILING.value:
                    raise HTTPException(status_code=503, detail="Service unavailable")
                return health
            
            @router.get(f"{path}/components")
            async def components_health():
                """Get health status of all components."""
                return {"components": self.get_system_health()["components"]}
            
            @router.get(f"{path}/components/{{component}}")
            async def component_health(component: str):
                """Get health status of a specific component."""
                try:
                    return self.get_component_health(component)
                except ValueError:
                    raise HTTPException(status_code=404, detail=f"Component {component} not found")
            
            @router.post(f"{path}/check")
            async def run_health_check():
                """Run health checks for all components."""
                await self.check_all_health_async()
                return self.get_health_report()
            
            logger.info(f"Registered health check endpoints with router at {path}")
            
        except ImportError:
            logger.error("Cannot register health check endpoints with router: fastapi not available")
    
    def _auto_check_loop(self) -> None:
        """Background thread function to periodically check health."""
        logger.info(f"Starting automatic health checks every {self.check_interval} seconds")
        
        while not self._shutdown_event.is_set():
            try:
                self.check_all_health()
                logger.debug("Completed automatic health check")
            except Exception as e:
                logger.error(f"Error running automatic health check: {str(e)}", exc_info=True)
            
            # Wait for the next check interval or until shutdown
            self._shutdown_event.wait(self.check_interval)
    
    def start_auto_checking(self) -> None:
        """Start automatic health checking in a background thread."""
        if self._auto_check_thread is not None and self._auto_check_thread.is_alive():
            logger.warning("Automatic health checking already running")
            return
        
        self._shutdown_event.clear()
        self._auto_check_thread = threading.Thread(
            target=self._auto_check_loop,
            daemon=True,
            name="health-checker",
        )
        self._auto_check_thread.start()
        logger.info("Started automatic health checking")
    
    def stop_auto_checking(self) -> None:
        """Stop automatic health checking."""
        if self._auto_check_thread is None or not self._auto_check_thread.is_alive():
            logger.warning("Automatic health checking not running")
            return
        
        self._shutdown_event.set()
        self._auto_check_thread.join(timeout=5.0)
        if self._auto_check_thread.is_alive():
            logger.warning("Health checker thread did not terminate gracefully")
        else:
            logger.info("Stopped automatic health checking")
        
        self._auto_check_thread = None

# Singleton instance for global access
_default_health_checker = None

def get_health_checker(check_interval: int = 60) -> HealthChecker:
    """
    Get or create the default health checker.
    
    Args:
        check_interval: Interval in seconds between automatic health checks
    
    Returns:
        HealthChecker instance
    """
    global _default_health_checker
    
    if _default_health_checker is None:
        _default_health_checker = HealthChecker(check_interval=check_interval)
    
    return _default_health_checker

def check_component_health(
    component: str,
    status: HealthStatus,
    details: str = "",
) -> None:
    """
    Update the health status of a component using the default health checker.
    
    Args:
        component: Name of the component
        status: Health status
        details: Additional details
    """
    checker = get_health_checker()
    checker.update_component_health(
        component=component,
        status=status,
        details=details,
    )

def register_component(
    component: str,
    check_function: Optional[Callable[[], Tuple[HealthStatus, str]]] = None,
    async_check_function: Optional[Callable[[], asyncio.coroutine]] = None,
) -> None:
    """
    Register a component with the default health checker.
    
    Args:
        component: Name of the component
        check_function: Function to check the component's health (synchronous)
        async_check_function: Function to check the component's health (asynchronous)
    """
    checker = get_health_checker()
    checker.register_component(
        component=component,
        check_function=check_function,
        async_check_function=async_check_function,
    )
