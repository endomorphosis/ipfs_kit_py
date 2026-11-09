#!/usr/bin/env python3
"""
Synapse Kit for IPFS Kit.

This module provides comprehensive integration with Synapse SDK for Filecoin
with robust connection handling, dependency management, and service control.
"""

import json
import logging
import os
import platform
import subprocess
import sys
import tempfile
import time
import uuid
import socket
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

# Configure logger
logger = logging.getLogger(__name__)

class SynapseError(Exception):
    """Base class for Synapse-related exceptions."""
    pass

class SynapseConnectionError(SynapseError):
    """Error when connecting to Synapse services."""
    pass

class SynapseInstallationError(SynapseError):
    """Error during Synapse installation."""
    pass

class SynapseConfigurationError(SynapseError):
    """Error with Synapse configuration."""
    pass

def create_result_dict(operation, correlation_id=None):
    """Create a standardized result dictionary."""
    return {
        "success": False,
        "operation": operation,
        "timestamp": time.time(),
        "correlation_id": correlation_id,
    }

def handle_error(result, error, message=None):
    """Handle errors in a standardized way."""
    result["success"] = False
    result["error"] = message or str(error)
    result["error_type"] = type(error).__name__
    return result

class synapse_kit:
    def __init__(self, resources=None, metadata=None):
        """Initialize synapse_kit with resources and metadata.
        
        Args:
            resources: Optional resources like file handles or connections
            metadata: Optional metadata dictionary with configuration
        """
        # Store resources
        self.resources = resources or {}

        # Store metadata
        self.metadata = metadata or {}

        # Generate correlation ID for tracking operations
        self.correlation_id = str(uuid.uuid4())

        # Set up state variables
        self._node_available = None
        self._npm_package_installed = None
        self._js_wrapper_path = None
        
        # Initialize configuration
        self._init_config()
        
        logger.debug(f"Initialized synapse_kit with correlation_id: {self.correlation_id}")

    def _init_config(self):
        """Initialize configuration from metadata and environment."""
        # Default configuration
        self.config = {
            "network": "calibration",
            "rpc_url": None,
            "private_key": None,
            "auto_approve": True,
            "timeout": 30,
            "debug": False
        }
        
        # Update from metadata
        if self.metadata:
            if "synapse_config" in self.metadata:
                self.config.update(self.metadata["synapse_config"])
            
            # Check for direct config keys
            config_keys = ["network", "rpc_url", "private_key", "auto_approve", "timeout", "debug"]
            for key in config_keys:
                if key in self.metadata:
                    self.config[key] = self.metadata[key]
        
        # Update from environment variables
        env_mapping = {
            "SYNAPSE_NETWORK": "network",
            "SYNAPSE_RPC_URL": "rpc_url", 
            "SYNAPSE_PRIVATE_KEY": "private_key",
            "SYNAPSE_AUTO_APPROVE": "auto_approve",
            "SYNAPSE_TIMEOUT": "timeout",
            "SYNAPSE_DEBUG": "debug"
        }
        
        for env_key, config_key in env_mapping.items():
            env_value = os.getenv(env_key)
            if env_value:
                if config_key in ["auto_approve", "debug"]:
                    self.config[config_key] = env_value.lower() in ["true", "1", "yes", "on"]
                elif config_key == "timeout":
                    try:
                        self.config[config_key] = int(env_value)
                    except ValueError:
                        logger.warning(f"Invalid timeout value in {env_key}: {env_value}")
                else:
                    self.config[config_key] = env_value

    def install(self, **kwargs):
        """Install the required dependencies for synapse_kit.
        
        Returns:
            Dictionary with installation status
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("install", correlation_id)
        
        try:
            # Check if Node.js is installed
            node_check = self._check_node_js()
            if not node_check["success"]:
                result.update(node_check)
                return result
            
            # Install npm package
            npm_result = self._install_npm_package()
            if not npm_result["success"]:
                result.update(npm_result)
                return result
            
            # Verify JS wrapper exists
            wrapper_check = self._check_js_wrapper()
            if not wrapper_check["success"]:
                result.update(wrapper_check)
                return result
                
            result["success"] = True
            result["message"] = "Successfully installed synapse dependencies"
            result["details"] = {
                "node_version": node_check.get("node_version"),
                "npm_package": "@filoz/synapse-sdk",
                "js_wrapper": wrapper_check.get("js_wrapper_path")
            }
            
            logger.info("Synapse dependencies installed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error during synapse installation: {e}")
            return handle_error(result, e, "Failed to install synapse dependencies")

    def _check_node_js(self):
        """Check if Node.js is available."""
        result = {"success": False}
        
        try:
            node_result = subprocess.run(
                ["node", "--version"],
                capture_output=True, text=True, timeout=5
            )
            
            if node_result.returncode == 0:
                result["success"] = True
                result["node_version"] = node_result.stdout.strip()
                self._node_available = True
            else:
                result["error"] = "Node.js not found or not working"
                self._node_available = False
                
        except Exception as e:
            result["error"] = f"Failed to check Node.js: {str(e)}"
            self._node_available = False
            
        return result

    def _install_npm_package(self):
        """Install the Synapse SDK npm package."""
        result = {"success": False}
        
        try:
            # Check if package is already installed
            npm_list_result = subprocess.run(
                ["npm", "list", "@filoz/synapse-sdk"],
                capture_output=True, text=True, timeout=10
            )
            
            if npm_list_result.returncode == 0:
                result["success"] = True
                result["message"] = "Package already installed"
                self._npm_package_installed = True
                return result
            
            # Install the package
            npm_install_result = subprocess.run(
                ["npm", "install", "@filoz/synapse-sdk"],
                capture_output=True, text=True, timeout=60
            )
            
            if npm_install_result.returncode == 0:
                result["success"] = True
                result["message"] = "Package installed successfully"
                self._npm_package_installed = True
            else:
                result["error"] = f"npm install failed: {npm_install_result.stderr}"
                self._npm_package_installed = False
                
        except Exception as e:
            result["error"] = f"Failed to install npm package: {str(e)}"
            self._npm_package_installed = False
            
        return result

    def _check_js_wrapper(self):
        """Check if the JavaScript wrapper exists."""
        result = {"success": False}
        
        try:
            # Find the JS wrapper
            project_root = Path(__file__).parent
            js_wrapper_path = project_root / "js" / "synapse_wrapper.js"
            
            if js_wrapper_path.exists():
                result["success"] = True
                result["js_wrapper_path"] = str(js_wrapper_path)
                self._js_wrapper_path = str(js_wrapper_path)
            else:
                result["error"] = f"JS wrapper not found at {js_wrapper_path}"
                self._js_wrapper_path = None
                
        except Exception as e:
            result["error"] = f"Failed to check JS wrapper: {str(e)}"
            self._js_wrapper_path = None
            
        return result

    def start(self, **kwargs):
        """Start Synapse services.
        
        For Synapse, this mainly means verifying the environment is ready.
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("start", correlation_id)
        
        try:
            # Check installation status
            status = self.status()
            if not status["success"]:
                result.update(status)
                return result
            
            if status["status"] != "installed":
                result["error"] = f"Synapse not properly installed. Status: {status['status']}"
                return result
            
            # For Synapse, starting means the SDK is ready to use
            result["success"] = True
            result["message"] = "Synapse SDK is ready"
            result["status"] = "running"
            
            logger.info("Synapse service started successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error starting synapse service: {e}")
            return handle_error(result, e, "Failed to start synapse service")

    def stop(self, **kwargs):
        """Stop Synapse services.
        
        For Synapse SDK, this is mostly a no-op since it's a library.
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("stop", correlation_id)
        
        try:
            result["success"] = True
            result["message"] = "Synapse SDK stopped (no persistent processes)"
            result["status"] = "stopped"
            
            logger.info("Synapse service stopped")
            return result
            
        except Exception as e:
            logger.error(f"Error stopping synapse service: {e}")
            return handle_error(result, e, "Failed to stop synapse service")

    def restart(self, **kwargs):
        """Restart Synapse services."""
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("restart", correlation_id)
        
        try:
            # Stop first
            stop_result = self.stop(**kwargs)
            if not stop_result["success"]:
                result.update(stop_result)
                return result
            
            # Then start
            start_result = self.start(**kwargs)
            result.update(start_result)
            result["operation"] = "restart"
            
            if result["success"]:
                logger.info("Synapse service restarted successfully")
            
            return result
            
        except Exception as e:
            logger.error(f"Error restarting synapse service: {e}")
            return handle_error(result, e, "Failed to restart synapse service")

    def status(self, **kwargs):
        """Get the current status of Synapse installation and services."""
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("status", correlation_id)
        
        try:
            # Check Node.js
            node_check = self._check_node_js()
            
            # Check npm package
            npm_check = self._install_npm_package() if node_check["success"] else {"success": False}
            
            # Check JS wrapper
            wrapper_check = self._check_js_wrapper()
            
            # Determine overall status
            if node_check["success"] and npm_check["success"] and wrapper_check["success"]:
                status = "installed"
                health = "healthy"
            elif not node_check["success"]:
                status = "node_missing"
                health = "unhealthy"
            elif not npm_check["success"]:
                status = "not_installed" 
                health = "unhealthy"
            else:
                status = "partial"
                health = "degraded"
            
            result["success"] = True
            result["status"] = status
            result["health"] = health
            result["details"] = {
                "node_available": node_check["success"],
                "node_version": node_check.get("node_version"),
                "npm_package_installed": npm_check["success"],
                "js_wrapper_exists": wrapper_check["success"],
                "js_wrapper_path": wrapper_check.get("js_wrapper_path")
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking synapse status: {e}")
            return handle_error(result, e, "Failed to check synapse status")

    def configure(self, **kwargs):
        """Configure Synapse settings."""
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("configure", correlation_id)
        
        try:
            # Update configuration
            config_updates = kwargs.get("config", {})
            if config_updates:
                self.config.update(config_updates)
                
            # Save configuration if requested
            if kwargs.get("save", False):
                config_file = kwargs.get("config_file", "synapse_config.json")
                with open(config_file, 'w') as f:
                    json.dump(self.config, f, indent=2)
                    
            result["success"] = True
            result["message"] = "Configuration updated successfully"
            result["config"] = self.config.copy()
            
            logger.info("Synapse configuration updated")
            return result
            
        except Exception as e:
            logger.error(f"Error configuring synapse: {e}")
            return handle_error(result, e, "Failed to configure synapse")

    def get_logs(self, **kwargs):
        """Get Synapse logs.
        
        Since Synapse SDK doesn't have persistent logs, return status info.
        """
        correlation_id = kwargs.get("correlation_id", self.correlation_id)
        result = create_result_dict("get_logs", correlation_id)
        
        try:
            # Get current status as "logs"
            status_result = self.status()
            
            result["success"] = True
            result["logs"] = [
                {
                    "timestamp": time.time(),
                    "level": "INFO",
                    "message": f"Synapse status: {status_result.get('status', 'unknown')}",
                    "details": status_result.get("details", {})
                }
            ]
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting synapse logs: {e}")
            return handle_error(result, e, "Failed to get synapse logs")

    def __call__(self, method, **kwargs):
        """Make the kit callable with different methods."""
        method_map = {
            "install": self.install,
            "start": self.start,
            "stop": self.stop,
            "restart": self.restart,
            "status": self.status,
            "configure": self.configure,
            "get_logs": self.get_logs,
            "config": self.configure  # Alias for configure
        }
        
        if method in method_map:
            return method_map[method](**kwargs)
        else:
            correlation_id = kwargs.get("correlation_id", self.correlation_id)
            result = create_result_dict(method, correlation_id)
            result["error"] = f"Unknown method: {method}"
            return result
