"""
MCP Server Blue/Green Deployment Proxy - Enhanced Version

This module provides a comprehensive routing layer for blue/green deployment of the MCP server.
It integrates metrics collection, response validation, and intelligent traffic control
to enable safe, gradual migration between server implementations.
"""

import asyncio
import logging
import os
import json
import sys
import time
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, Union, List, Tuple, Callable

# Ensure parent directory is in path for imports
parent_dir = str(Path(__file__).parent.parent.absolute())
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import both server implementations
try:
    # Original "blue" implementation
    from ipfs_kit_py.mcp.server import MCPServer as BlueMCPServer
    from ipfs_kit_py.mcp.server_anyio import AsyncMCPServer as BlueAsyncMCPServer
    
    # Refactored "green" implementation
    from ipfs_kit_py.mcp_server.server import MCPServer as GreenMCPServer
    from ipfs_kit_py.mcp_server.server import AsyncMCPServer as GreenAsyncMCPServer
    
    BOTH_IMPLEMENTATIONS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Could not import both server implementations: {e}")
    
    # Try to import at least one implementation
    try:
        from ipfs_kit_py.mcp.server import MCPServer as BlueMCPServer
        from ipfs_kit_py.mcp.server_anyio import AsyncMCPServer as BlueAsyncMCPServer
        GreenMCPServer = BlueMCPServer
        GreenAsyncMCPServer = BlueAsyncMCPServer
        BOTH_IMPLEMENTATIONS_AVAILABLE = False
    except ImportError:
        try:
            from ipfs_kit_py.mcp_server.server import MCPServer as GreenMCPServer
            from ipfs_kit_py.mcp_server.server import AsyncMCPServer as GreenAsyncMCPServer
            BlueMCPServer = GreenMCPServer
            BlueAsyncMCPServer = GreenAsyncMCPServer
            BOTH_IMPLEMENTATIONS_AVAILABLE = False
        except ImportError:
            raise ImportError("Could not import any MCP server implementation")

# Import Blue/Green components
try:
    from ipfs_kit_py.mcp_server.metrics_collector import MetricsCollector, ServerType
    from ipfs_kit_py.mcp_server.response_validator import ResponseValidator
    from ipfs_kit_py.mcp_server.traffic_controller import TrafficController, TrafficAction

    COMPONENTS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Could not import Blue/Green components: {e}")
    COMPONENTS_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

class DeploymentMode(Enum):
    """Deployment mode for the MCP Server."""
    BLUE = "blue"  # Original implementation
    GREEN = "green"  # Refactored implementation
    GRADUAL = "gradual"  # Gradual transition (percentage-based)
    PARALLEL = "parallel"  # Run both in parallel and compare results
    AUTO = "auto"  # Automatically choose based on health checks and metrics

class MCPServerProxy:
    """
    Enhanced proxy for MCP Server that implements blue/green deployment.
    
    This proxy integrates metrics collection, response validation, and intelligent
    traffic control to enable safe, gradual migration between server implementations.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the MCP Server Proxy with the given configuration.
        
        Args:
            config: Dictionary containing configuration options
        """
        self.config = config or {}
        self.blue_config = self.config.get("blue", {})
        self.green_config = self.config.get("green", {})
        
        # Blue/green deployment settings
        self.deployment_config = self.config.get("deployment", {})
        self._setup_deployment_mode()
        
        # Server instances
        self.blue_server = None
        self.green_server = None
        
        # Health check state
        self.blue_healthy = False
        self.green_healthy = False
        
        # Start with no live servers
        self.running = False
        
        # Initialize Blue/Green components if available
        if COMPONENTS_AVAILABLE:
            self.metrics_collector = MetricsCollector(self.config.get("monitoring", {}))
            self.response_validator = ResponseValidator(self.config.get("validation", {}))
            self.traffic_controller = TrafficController(self.deployment_config)
        else:
            self.metrics_collector = None
            self.response_validator = None
            self.traffic_controller = None
            logger.warning("Blue/Green components not available. Using basic deployment only.")
        
        logger.info(f"MCP Server Proxy initialized in {self.mode.value} mode")
        
        # Verify implementations are available
        if not BOTH_IMPLEMENTATIONS_AVAILABLE and self.mode != DeploymentMode.BLUE and self.mode != DeploymentMode.GREEN:
            logger.warning("Not all server implementations are available. Falling back to available implementation.")
            self.mode = DeploymentMode.BLUE if BlueMCPServer != GreenMCPServer else DeploymentMode.GREEN
        
        # Initialize the servers
        self._init_servers()
        
        # Periodic evaluation task
        self._evaluation_task = None
    
    def _setup_deployment_mode(self) -> None:
        """Set up the deployment mode based on configuration."""
        mode_str = self.deployment_config.get("mode", "blue").lower()
        
        if mode_str == "blue":
            self.mode = DeploymentMode.BLUE
        elif mode_str == "green":
            self.mode = DeploymentMode.GREEN
        elif mode_str == "gradual":
            self.mode = DeploymentMode.GRADUAL
        elif mode_str == "parallel":
            self.mode = DeploymentMode.PARALLEL
        elif mode_str == "auto":
            self.mode = DeploymentMode.AUTO
        else:
            logger.warning(f"Unknown deployment mode: {mode_str}. Falling back to blue.")
            self.mode = DeploymentMode.BLUE
        
        # Configure gradual transition if needed
        if self.mode == DeploymentMode.GRADUAL:
            self.green_percentage = self.deployment_config.get("green_percentage", 0)
            
            # Update traffic controller if available
            if COMPONENTS_AVAILABLE and self.traffic_controller:
                self.traffic_controller.reset(self.green_percentage)
        else:
            self.green_percentage = 0 if self.mode == DeploymentMode.BLUE else 100
            
            # Update traffic controller if available
            if COMPONENTS_AVAILABLE and self.traffic_controller:
                self.traffic_controller.reset(self.green_percentage)
    
    def _init_servers(self) -> None:
        """Initialize the blue and green server instances."""
        # Only initialize the servers we'll actually use
        if self.mode in [DeploymentMode.BLUE, DeploymentMode.GRADUAL, DeploymentMode.PARALLEL, DeploymentMode.AUTO]:
            self.blue_server = BlueMCPServer(self.blue_config)
            logger.info("Blue server initialized")
        
        if self.mode in [DeploymentMode.GREEN, DeploymentMode.GRADUAL, DeploymentMode.PARALLEL, DeploymentMode.AUTO]:
            self.green_server = GreenMCPServer(self.green_config)
            logger.info("Green server initialized")
    
    async def start(self) -> Dict[str, Any]:
        """
        Start the MCP Server Proxy and required server instances.
        
        Returns:
            Dict containing status information
        """
        if self.running:
            return {"success": False, "message": "Proxy already running"}
        
        results = {}
        
        try:
            # Start the appropriate servers based on mode
            if self.blue_server:
                blue_result = await self.blue_server.start()
                results["blue"] = blue_result
                self.blue_healthy = blue_result.get("success", False)
                logger.info(f"Blue server started with result: {blue_result}")
                
                # Record health in metrics collector
                if COMPONENTS_AVAILABLE and self.metrics_collector:
                    self.metrics_collector.record_health_check(ServerType.BLUE, self.blue_healthy)
            
            if self.green_server:
                green_result = await self.green_server.start()
                results["green"] = green_result
                self.green_healthy = green_result.get("success", False)
                logger.info(f"Green server started with result: {green_result}")
                
                # Record health in metrics collector
                if COMPONENTS_AVAILABLE and self.metrics_collector:
                    self.metrics_collector.record_health_check(ServerType.GREEN, self.green_healthy)
            
            # Adjust mode if in AUTO and one server isn't healthy
            if self.mode == DeploymentMode.AUTO:
                if not self.blue_healthy and self.green_healthy:
                    logger.warning("Blue server unhealthy. Switching to GREEN mode.")
                    self.mode = DeploymentMode.GREEN
                elif not self.green_healthy and self.blue_healthy:
                    logger.warning("Green server unhealthy. Switching to BLUE mode.")
                    self.mode = DeploymentMode.BLUE
                elif not self.blue_healthy and not self.green_healthy:
                    logger.error("Both servers unhealthy. Cannot start proxy.")
                    return {"success": False, "message": "Both servers failed to start", "results": results}
            
            self.running = True
            logger.info(f"MCP Server Proxy started in {self.mode.value} mode")
            
            # Start periodic evaluation task if needed
            if self.mode in [DeploymentMode.AUTO, DeploymentMode.GRADUAL] and COMPONENTS_AVAILABLE:
                evaluation_interval = self.deployment_config.get("evaluation_interval", 60)
                self._start_evaluation_task(evaluation_interval)
            
            return {
                "success": True, 
                "message": f"Proxy started in {self.mode.value} mode",
                "results": results
            }
        
        except Exception as e:
            logger.error(f"Failed to start MCP Server Proxy: {e}")
            return {"success": False, "message": f"Failed to start proxy: {str(e)}", "results": results}
    
    def _start_evaluation_task(self, interval: int) -> None:
        """Start the periodic evaluation task."""
        async def evaluation_loop():
            while self.running:
                try:
                    await self._evaluate_and_adjust()
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in evaluation loop: {e}")
                    await asyncio.sleep(interval)
        
        self._evaluation_task = asyncio.create_task(evaluation_loop())
        logger.info(f"Started periodic evaluation task with interval {interval}s")
    
    async def _evaluate_and_adjust(self) -> None:
        """Evaluate metrics and adjust traffic if needed."""
        if not COMPONENTS_AVAILABLE:
            return
        
        try:
            # Get metrics summary
            metrics_summary = self.metrics_collector.get_metrics_summary()
            
            # Get validation stats
            validation_stats = self.response_validator.get_validation_stats()
            
            # Evaluate metrics and determine action
            action = self.traffic_controller.evaluate(
                metrics_summary, 
                validation_stats
            )
            
            # Adjust traffic based on action
            result = self.traffic_controller.adjust_traffic(action)
            
            # Update green percentage
            self.green_percentage = result["green_percentage"]
            
            if result["changed"]:
                logger.info(
                    f"Traffic adjusted: {action.value}, "
                    f"green percentage now {self.green_percentage}%"
                )
                
                # Update mode if needed
                if self.green_percentage <= 0:
                    if self.mode != DeploymentMode.BLUE:
                        logger.info("Switched to BLUE mode")
                        self.mode = DeploymentMode.BLUE
                elif self.green_percentage >= 100:
                    if self.mode != DeploymentMode.GREEN:
                        logger.info("Switched to GREEN mode")
                        self.mode = DeploymentMode.GREEN
                elif self.mode not in [DeploymentMode.GRADUAL, DeploymentMode.AUTO]:
                    logger.info("Switched to GRADUAL mode")
                    self.mode = DeploymentMode.GRADUAL
        
        except Exception as e:
            logger.error(f"Error evaluating and adjusting traffic: {e}")
    
    async def stop(self) -> Dict[str, Any]:
        """
        Stop the MCP Server Proxy and all server instances.
        
        Returns:
            Dict containing status information
        """
        if not self.running:
            return {"success": False, "message": "Proxy not running"}
        
        results = {}
        
        try:
            # Cancel evaluation task if running
            if self._evaluation_task and not self._evaluation_task.cancelled():
                self._evaluation_task.cancel()
                try:
                    await self._evaluation_task
                except asyncio.CancelledError:
                    pass
                
            # Stop all active servers
            if self.blue_server:
                blue_result = await self.blue_server.stop()
                results["blue"] = blue_result
                logger.info(f"Blue server stopped with result: {blue_result}")
            
            if self.green_server:
                green_result = await self.green_server.stop()
                results["green"] = green_result
                logger.info(f"Green server stopped with result: {green_result}")
            
            self.running = False
            logger.info("MCP Server Proxy stopped")
            
            # Save statistics if metrics collector is available
            if COMPONENTS_AVAILABLE and self.metrics_collector:
                self._save_statistics()
            
            return {
                "success": True, 
                "message": "Proxy stopped successfully",
                "results": results
            }
        
        except Exception as e:
            logger.error(f"Failed to stop MCP Server Proxy: {e}")
            return {"success": False, "message": f"Failed to stop proxy: {str(e)}", "results": results}
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an MCP request by routing it to the appropriate server(s).
        
        Args:
            request: Dictionary containing request data
            
        Returns:
            Dict containing response data
        """
        if not self.running:
            return {"success": False, "message": "Proxy not running"}
        
        # Determine which server(s) should handle the request
        if self.mode == DeploymentMode.BLUE:
            return await self._handle_blue(request)
        elif self.mode == DeploymentMode.GREEN:
            return await self._handle_green(request)
        elif self.mode in [DeploymentMode.GRADUAL, DeploymentMode.AUTO]:
            # Use traffic controller to determine routing if available
            if COMPONENTS_AVAILABLE and self.traffic_controller:
                if self.traffic_controller.should_route_to_green():
                    return await self._handle_green(request)
                else:
                    return await self._handle_blue(request)
            else:
                # Fallback to simple random routing
                if self._should_route_to_green():
                    return await self._handle_green(request)
                else:
                    return await self._handle_blue(request)
        elif self.mode == DeploymentMode.PARALLEL:
            # Run on both and return the green result (but record both)
            return await self._handle_parallel(request)
        
        # Fallback to blue
        logger.warning(f"Unknown mode {self.mode}. Falling back to blue.")
        return await self._handle_blue(request)
    
    async def _handle_blue(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle request with the blue server and record metrics."""
        if not self.blue_server:
            logger.error("Blue server not initialized")
            return {"success": False, "message": "Blue server not initialized"}
        
        endpoint = self._get_endpoint_from_request(request)
        start_time = time.time()
        
        try:
            result = await self.blue_server.handle_request(request)
            elapsed = time.time() - start_time
            
            # Record metrics if available
            if COMPONENTS_AVAILABLE and self.metrics_collector:
                success = result.get("success", False)
                self.metrics_collector.record_request(
                    ServerType.BLUE, 
                    success, 
                    elapsed,
                    endpoint
                )
            
            return result
        
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Error in blue server: {e}")
            
            # Record error metrics if available
            if COMPONENTS_AVAILABLE and self.metrics_collector:
                self.metrics_collector.record_request(
                    ServerType.BLUE, 
                    False, 
                    elapsed,
                    endpoint
                )
                self.metrics_collector.record_error(
                    ServerType.BLUE,
                    "exception",
                    str(e)
                )
            
            return {"success": False, "message": f"Error in blue server: {str(e)}"}
    
    async def _handle_green(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle request with the green server and record metrics."""
        if not self.green_server:
            logger.error("Green server not initialized")
            return {"success": False, "message": "Green server not initialized"}
        
        endpoint = self._get_endpoint_from_request(request)
        start_time = time.time()
        
        try:
            result = await self.green_server.handle_request(request)
            elapsed = time.time() - start_time
            
            # Record metrics if available
            if COMPONENTS_AVAILABLE and self.metrics_collector:
                success = result.get("success", False)
                self.metrics_collector.record_request(
                    ServerType.GREEN, 
                    success, 
                    elapsed,
                    endpoint
                )
            
            return result
        
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Error in green server: {e}")
            
            # Record error metrics if available
            if COMPONENTS_AVAILABLE and self.metrics_collector:
                self.metrics_collector.record_request(
                    ServerType.GREEN, 
                    False, 
                    elapsed,
                    endpoint
                )
                self.metrics_collector.record_error(
                    ServerType.GREEN,
                    "exception",
                    str(e)
                )
            
            return {"success": False, "message": f"Error in green server: {str(e)}"}
    
    async def _handle_parallel(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle request with both servers and compare results."""
        if not self.blue_server or not self.green_server:
            logger.error("Both servers must be initialized for parallel mode")
            return {"success": False, "message": "Both servers must be initialized for parallel mode"}
        
        endpoint = self._get_endpoint_from_request(request)
        
        # Start blue request
        blue_start_time = time.time()
        blue_future = asyncio.create_task(self.blue_server.handle_request(request))
        
        # Start green request
        green_start_time = time.time()
        green_future = asyncio.create_task(self.green_server.handle_request(request))
        
        # Wait for both to complete
        blue_result = None
        green_result = None
        blue_error = None
        green_error = None
        
        try:
            blue_result = await blue_future
            blue_elapsed = time.time() - blue_start_time
        except Exception as e:
            blue_elapsed = time.time() - blue_start_time
            blue_error = str(e)
            logger.error(f"Error in blue server: {e}")
        
        try:
            green_result = await green_future
            green_elapsed = time.time() - green_start_time
        except Exception as e:
            green_elapsed = time.time() - green_start_time
            green_error = str(e)
            logger.error(f"Error in green server: {e}")
        
        # Record metrics for both
        if COMPONENTS_AVAILABLE and self.metrics_collector:
            # Blue metrics
            if blue_result:
                blue_success = blue_result.get("success", False)
                self.metrics_collector.record_request(
                    ServerType.BLUE, 
                    blue_success, 
                    blue_elapsed,
                    endpoint
                )
            else:
                self.metrics_collector.record_request(
                    ServerType.BLUE, 
                    False, 
                    blue_elapsed,
                    endpoint
                )
                if blue_error:
                    self.metrics_collector.record_error(
                        ServerType.BLUE,
                        "exception",
                        blue_error
                    )
            
            # Green metrics
            if green_result:
                green_success = green_result.get("success", False)
                self.metrics_collector.record_request(
                    ServerType.GREEN, 
                    green_success, 
                    green_elapsed,
                    endpoint
                )
            else:
                self.metrics_collector.record_request(
                    ServerType.GREEN, 
                    False, 
                    green_elapsed,
                    endpoint
                )
                if green_error:
                    self.metrics_collector.record_error(
                        ServerType.GREEN,
                        "exception",
                        green_error
                    )
            
            # Validate and compare responses if both succeeded
            if blue_result and green_result and self.response_validator:
                try:
                    validation_result = self.response_validator.validate(blue_result, green_result)
                    identical = validation_result.get("identical", False)
                    self.metrics_collector.record_comparison(
                        identical, 
                        green_elapsed - blue_elapsed
                    )
                except Exception as e:
                    logger.error(f"Error validating responses: {e}")
        
        # Determine which result to return
        if green_result:
            return green_result
        elif blue_result:
            return blue_result
        else:
            return {
                "success": False, 
                "message": f"Both servers failed: Blue: {blue_error}, Green: {green_error}"
            }
    
    def _get_endpoint_from_request(self, request: Dict[str, Any]) -> str:
        """Extract endpoint name from request for metrics."""
        if "type" in request:
            endpoint = request["type"]
            if "command" in request:
                endpoint = f"{endpoint}.{request['command']}"
            return endpoint
        return "unknown"
    
    def _should_route_to_green(self) -> bool:
        """Determine if request should be routed to green based on configuration."""
        return (hash(str(time.time())) % 100) < self.green_percentage
    
    async def _health_check(self) -> Dict[str, Any]:
        """Perform health checks on active servers."""
        results = {"blue": False, "green": False}
        
        if self.blue_server:
            try:
                health = await self.blue_server.check_health()
                self.blue_healthy = health.get("success", False)
                results["blue"] = self.blue_healthy
                
                # Record health in metrics collector
                if COMPONENTS_AVAILABLE and self.metrics_collector:
                    self.metrics_collector.record_health_check(ServerType.BLUE, self.blue_healthy)
            except Exception as e:
                logger.error(f"Error checking blue server health: {e}")
                self.blue_healthy = False
                results["blue"] = False
                
                # Record health in metrics collector
                if COMPONENTS_AVAILABLE and self.metrics_collector:
                    self.metrics_collector.record_health_check(ServerType.BLUE, False)
                    self.metrics_collector.record_error(ServerType.BLUE, "health_check", str(e))
        
        if self.green_server:
            try:
                health = await self.green_server.check_health()
                self.green_healthy = health.get("success", False)
                results["green"] = self.green_healthy
                
                # Record health in metrics collector
                if COMPONENTS_AVAILABLE and self.metrics_collector:
                    self.metrics_collector.record_health_check(ServerType.GREEN, self.green_healthy)
            except Exception as e:
                logger.error(f"Error checking green server health: {e}")
                self.green_healthy = False
                results["green"] = False
                
                # Record health in metrics collector
                if COMPONENTS_AVAILABLE and self.metrics_collector:
                    self.metrics_collector.record_health_check(ServerType.GREEN, False)
                    self.metrics_collector.record_error(ServerType.GREEN, "health_check", str(e))
        
        return results
    
    def _save_statistics(self) -> None:
        """Save usage statistics to a file."""
        if not COMPONENTS_AVAILABLE:
            return
            
        stats_dir = self.config.get("stats_dir", "logs")
        os.makedirs(stats_dir, exist_ok=True)
        
        stats_file = os.path.join(stats_dir, f"mcp_proxy_stats_{int(time.time())}.json")
        
        # Get detailed metrics
        detailed_metrics = self.metrics_collector.get_detailed_metrics()
        
        # Get validation stats
        validation_stats = self.response_validator.get_validation_stats()
        
        # Get traffic history
        traffic_history = self.traffic_controller.get_adjustment_history()
        
        # Combine stats
        combined_stats = {
            "metrics": detailed_metrics,
            "validation": validation_stats,
            "traffic_history": traffic_history,
            "deployment_mode": self.mode.value,
            "timestamp": time.time()
        }
        
        # Write to file
        with open(stats_file, "w") as f:
            json.dump(combined_stats, f, indent=2)
        
        logger.info(f"Statistics saved to {stats_file}")
    
    async def check_health(self) -> Dict[str, Any]:
        """
        Check the health status of the MCP Server Proxy and its components.
        
        Returns:
            Dict containing health status information
        """
        if not self.running:
            return {"success": False, "status": "stopped"}
        
        # Perform health checks
        health_results = await self._health_check()
        
        results = {
            "success": True, 
            "status": "healthy", 
            "mode": self.mode.value,
            "components": {
                "blue": {"success": health_results["blue"]},
                "green": {"success": health_results["green"]}
            }
        }
        
        # Set overall status based on health check results
        if not health_results["blue"] and not health_results["green"]:
            results["success"] = False
            results["status"] = "unhealthy"
        elif not health_results["blue"] or not health_results["green"]:
            results["status"] = "degraded"
        
        # Include traffic split
        if self.mode in [DeploymentMode.GRADUAL, DeploymentMode.AUTO]:
            results["traffic_split"] = {
                "blue_percentage": 100 - self.green_percentage,
                "green_percentage": self.green_percentage
            }
        
        # Include metrics summary if available
        if COMPONENTS_AVAILABLE and self.metrics_collector:
            results["metrics"] = self.metrics_collector.get_metrics_summary()
        
        # Include validation summary if available
        if COMPONENTS_AVAILABLE and self.response_validator:
            results["validation"] = self.response_validator.get_validation_stats()
        
        return results
    
    def set_mode(
        self, 
        mode: Union[str, DeploymentMode], 
        green_percentage: int = None
    ) -> Dict[str, Any]:
        """
        Change the deployment mode.
        
        Args:
            mode: New deployment mode
            green_percentage: Percentage of traffic to route to green (for GRADUAL mode)
            
        Returns:
            Dict containing status information
        """
        if isinstance(mode, str):
            mode = mode.lower()
            if mode == "blue":
                new_mode = DeploymentMode.BLUE
            elif mode == "green":
                new_mode = DeploymentMode.GREEN
            elif mode == "gradual":
                new_mode = DeploymentMode.GRADUAL
            elif mode == "parallel":
                new_mode = DeploymentMode.PARALLEL
            elif mode == "auto":
                new_mode = DeploymentMode.AUTO
            else:
                return {"success": False, "message": f"Unknown mode: {mode}"}
        else:
            new_mode = mode
        
        # Check if we have the required servers for this mode
        if new_mode in [DeploymentMode.GREEN, DeploymentMode.GRADUAL, DeploymentMode.PARALLEL, DeploymentMode.AUTO] and not self.green_server:
            return {"success": False, "message": "Green server not available"}
        
        if new_mode in [DeploymentMode.BLUE, DeploymentMode.GRADUAL, DeploymentMode.PARALLEL, DeploymentMode.AUTO] and not self.blue_server:
            return {"success": False, "message": "Blue server not available"}
        
        # Update mode
        old_mode = self.mode
        self.mode = new_mode
        
        # Update traffic controller and green percentage
        if new_mode == DeploymentMode.BLUE:
            self.green_percentage = 0
            if COMPONENTS_AVAILABLE and self.traffic_controller:
                self.traffic_controller.reset(0)
        elif new_mode == DeploymentMode.GREEN:
            self.green_percentage = 100
            if COMPONENTS_AVAILABLE and self.traffic_controller:
                self.traffic_controller.reset(100)
        elif new_mode == DeploymentMode.GRADUAL:
            # Update gradual percentage if provided
            if green_percentage is not None:
                self.green_percentage = max(0, min(100, green_percentage))
            
            if COMPONENTS_AVAILABLE and self.traffic_controller:
                self.traffic_controller.reset(self.green_percentage)
        elif new_mode == DeploymentMode.AUTO:
            # Set initial traffic split for auto mode
            if green_percentage is not None:
                self.green_percentage = max(0, min(100, green_percentage))
            
            if COMPONENTS_AVAILABLE and self.traffic_controller:
                self.traffic_controller.reset(self.green_percentage)
        
        logger.info(f"Changed mode from {old_mode.value} to {self.mode.value}")
        if self.mode == DeploymentMode.GRADUAL:
            logger.info(f"Green percentage set to {self.green_percentage}%")
        
        return {"success": True, "message": f"Mode changed to {self.mode.value}"}


class AsyncMCPServerProxy(MCPServerProxy):
    """
    Asynchronous proxy for the MCP Server that implements blue/green deployment.
    
    This class extends the base MCPServerProxy to provide a fully asynchronous API
    with support for async context management.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the async proxy with the given configuration."""
        super().__init__(config)
        self.start_time = time.time()
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()