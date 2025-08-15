#!/usr/bin/env python3
"""
StateService - Shared lightweight service for MCP/CLI parity

Provides a unified, light-initialization API to read/write program and daemon
state from the IPFS Kit data directory (default: ~/.ipfs_kit). Avoids heavy
imports and focuses on file-based state and simple system introspection so it
can be safely used by both the CLI and the MCP server tools.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
import yaml


@dataclass
class StateService:
    data_dir: Path
    start_time: Optional[datetime] = None

    def __post_init__(self):
        self.data_dir = Path(self.data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_structure()
        if self.start_time is None:
            self.start_time = datetime.now()

    # Files
    @property
    def backends_dir(self) -> Path:
        return self.data_dir / "backend_configs"

    @property
    def buckets_file(self) -> Path:
        return self.data_dir / "buckets.json"

    @property
    def pins_file(self) -> Path:
        return self.data_dir / "pins.json"

    def _ensure_structure(self):
        self.backends_dir.mkdir(parents=True, exist_ok=True)
        # Initialize basic files if missing
        if not self.buckets_file.exists():
            self.buckets_file.write_text(json.dumps({"buckets": []}, indent=2))
        if not self.pins_file.exists():
            self.pins_file.write_text(json.dumps({"pins": []}, indent=2))

    # Utilities
    def _read_json(self, path: Path, default: Any) -> Any:
        try:
            if path.exists():
                return json.loads(path.read_text())
        except Exception:
            pass
        return default

    def _write_json(self, path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, indent=2))

    # System
    def get_system_status(self) -> Dict[str, Any]:
        uptime = datetime.now() - (self.start_time or datetime.now())
        mem = psutil.virtual_memory()
        status = {
            "timestamp": datetime.now().isoformat(),
            "uptime": str(uptime),
            # These can be wired to real checks later
            "ipfs_api": "unavailable",
            "bucket_manager": "unavailable",
            "unified_bucket_interface": "unavailable",
            "data_dir": str(self.data_dir),
            "data_dir_exists": self.data_dir.exists(),
            "component_status": {
                "ipfs": False,
                "bucket_manager": False,
                "unified_bucket_interface": False,
                "pin_metadata": False,
                "psutil": True,
                "yaml": True,
            },
            "cpu_percent": psutil.cpu_percent(interval=0.2),
            "memory_percent": mem.percent,
            "memory_available": mem.available,
            "memory_total": mem.total,
        }
        return status

    def get_system_overview(self) -> Dict[str, Any]:
        services_count = 3
        backends_count = len(self.list_backends())
        buckets_count = len(self.list_buckets())
        pins_count = len(self.list_pins())
        uptime = datetime.now() - (self.start_time or datetime.now())
        return {
            "services": services_count,
            "backends": backends_count,
            "buckets": buckets_count,
            "pins": pins_count,
            "uptime": str(uptime),
            "status": "running",
        }

    # Services (enhanced detection)
    def list_services(self) -> List[Dict[str, Any]]:
        """List all detected services using enhanced service detection."""
        try:
            # Import the enhanced service detector
            import sys
            from pathlib import Path
            
            # Add the parent directory to path so we can import the detector
            parent_dir = Path(__file__).parent.parent.parent
            if str(parent_dir) not in sys.path:
                sys.path.insert(0, str(parent_dir))
            
            from enhanced_service_detector import EnhancedServiceDetector
            
            detector = EnhancedServiceDetector(self.data_dir)
            services = detector.detect_all_services()
            
            # Convert ServiceInfo objects to dictionaries
            service_list = []
            for service in services:
                service_dict = {
                    "name": service.name,
                    "type": service.type,
                    "status": service.status,
                    "description": service.description,
                }
                
                # Add optional fields if available
                if service.pid:
                    service_dict["pid"] = service.pid
                if service.process_name:
                    service_dict["process_name"] = service.process_name
                if service.port:
                    service_dict["port"] = service.port
                if service.config_file:
                    service_dict["config_file"] = service.config_file
                if service.manager_class:
                    service_dict["manager_class"] = service.manager_class
                if service.command_line:
                    service_dict["command_line"] = service.command_line
                    
                # Get available control actions
                actions = detector.get_service_control_actions(service)
                service_dict["available_actions"] = actions
                
                service_list.append(service_dict)
            
            return service_list
            
        except Exception as e:
            # Fallback to basic services if enhanced detection fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Enhanced service detection failed: {e}, falling back to basic services")
            
            return [
                {"name": "IPFS Node", "type": "ipfs", "status": "stopped", "description": "IPFS node connection", "available_actions": ["start", "status", "configure"]},
                {"name": "Bucket Manager", "type": "bucket", "status": "stopped", "description": "Bucket VFS manager", "available_actions": ["enable", "status", "configure"]},
                {"name": "Unified Interface", "type": "interface", "status": "stopped", "description": "Unified bucket interface", "available_actions": ["enable", "status", "configure"]},
            ]

    def control_service(self, service: str, action: str) -> Dict[str, Any]:
        """Control service operations with enhanced capabilities."""
        try:
            # Import the enhanced service detector for more detailed control
            import sys
            from pathlib import Path
            
            parent_dir = Path(__file__).parent.parent.parent
            if str(parent_dir) not in sys.path:
                sys.path.insert(0, str(parent_dir))
            
            from enhanced_service_detector import EnhancedServiceDetector
            
            detector = EnhancedServiceDetector(self.data_dir)
            services = detector.detect_all_services()
            
            # Find the service
            target_service = None
            for svc in services:
                if svc.name == service:
                    target_service = svc
                    break
            
            if not target_service:
                return {
                    "service": service,
                    "action": action,
                    "status": "error",
                    "message": f"Service '{service}' not found",
                }
            
            # Get available actions for this service
            available_actions = detector.get_service_control_actions(target_service)
            
            if action not in available_actions:
                return {
                    "service": service,
                    "action": action,
                    "status": "error",
                    "message": f"Action '{action}' not available for service '{service}'. Available: {', '.join(available_actions)}",
                    "available_actions": available_actions
                }
            
            # Perform the action based on service type
            result = self._perform_service_action(target_service, action)
            
            return {
                "service": service,
                "action": action,
                "status": "success" if result.get("success", False) else "error",
                "message": result.get("message", f"Service '{service}' {action} command executed"),
                "details": result
            }
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error controlling service {service}: {e}")
            
            return {
                "service": service,
                "action": action,
                "status": "error",
                "message": f"Failed to {action} service '{service}': {str(e)}",
            }
    
    def _perform_service_action(self, service, action: str) -> Dict[str, Any]:
        """Perform the actual service action."""
        try:
            if service.type == "daemon":
                return self._control_daemon_service(service, action)
            elif service.type in ["kit", "backend", "vfs", "storage"]:
                return self._control_module_service(service, action)
            else:
                return {"success": False, "message": f"Unknown service type: {service.type}"}
                
        except Exception as e:
            return {"success": False, "message": f"Action failed: {str(e)}"}
    
    def _control_daemon_service(self, service, action: str) -> Dict[str, Any]:
        """Control daemon services like IPFS, Lotus, etc."""
        if action == "status":
            return {"success": True, "message": f"Status: {service.status}", "current_status": service.status}
        
        elif action == "start":
            if service.status == "running":
                return {"success": True, "message": f"{service.name} is already running"}
                
            # Attempt to start the daemon
            if "ipfs" in service.name.lower():
                return self._start_ipfs_daemon()
            elif "cluster service" in service.name.lower():
                return self._start_cluster_service()
            elif "cluster follow" in service.name.lower():
                return self._start_cluster_follow()
            elif "lotus" in service.name.lower():
                return self._start_lotus_daemon()
            else:
                return {"success": False, "message": f"Start action not implemented for {service.name}"}
        
        elif action == "stop":
            if service.status != "running":
                return {"success": True, "message": f"{service.name} is not running"}
                
            return self._stop_daemon_by_pid(service.pid, service.name)
        
        elif action == "restart":
            # Stop then start
            stop_result = self._control_daemon_service(service, "stop")
            if stop_result.get("success", False):
                import time
                time.sleep(2)  # Wait a moment between stop and start
                return self._control_daemon_service(service, "start")
            else:
                return stop_result
        
        elif action == "configure":
            return {"success": True, "message": f"Configuration interface for {service.name} (placeholder)"}
        
        else:
            return {"success": False, "message": f"Unknown action: {action}"}
    
    def _control_module_service(self, service, action: str) -> Dict[str, Any]:
        """Control module-based services."""
        if action == "status":
            return {"success": True, "message": f"Status: {service.status}", "current_status": service.status}
        
        elif action == "enable":
            return {"success": True, "message": f"Enabled {service.name} (placeholder)"}
        
        elif action == "disable":
            return {"success": True, "message": f"Disabled {service.name} (placeholder)"}
        
        elif action == "configure":
            return {"success": True, "message": f"Configuration interface for {service.name} (placeholder)"}
        
        elif action == "install":
            return {"success": True, "message": f"Installation interface for {service.name} (placeholder)"}
        
        else:
            return {"success": False, "message": f"Unknown action: {action}"}
    
    def _start_ipfs_daemon(self) -> Dict[str, Any]:
        """Start IPFS daemon."""
        try:
            import subprocess
            
            # Try to start IPFS daemon
            result = subprocess.run(
                ["ipfs", "daemon", "--enable-gc"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return {"success": True, "message": "IPFS daemon started successfully"}
            else:
                return {"success": False, "message": f"Failed to start IPFS daemon: {result.stderr}"}
                
        except subprocess.TimeoutExpired:
            # Daemon might be starting in background, consider it successful
            return {"success": True, "message": "IPFS daemon starting in background"}
        except Exception as e:
            return {"success": False, "message": f"Error starting IPFS daemon: {str(e)}"}
    
    def _start_cluster_service(self) -> Dict[str, Any]:
        """Start IPFS Cluster Service."""
        try:
            import subprocess
            
            result = subprocess.run(
                ["ipfs-cluster-service", "daemon"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return {"success": True, "message": "IPFS Cluster Service started successfully"}
            else:
                return {"success": False, "message": f"Failed to start IPFS Cluster Service: {result.stderr}"}
                
        except subprocess.TimeoutExpired:
            return {"success": True, "message": "IPFS Cluster Service starting in background"}
        except Exception as e:
            return {"success": False, "message": f"Error starting IPFS Cluster Service: {str(e)}"}
    
    def _start_cluster_follow(self) -> Dict[str, Any]:
        """Start IPFS Cluster Follow."""
        try:
            import subprocess
            
            result = subprocess.run(
                ["ipfs-cluster-follow", "run"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return {"success": True, "message": "IPFS Cluster Follow started successfully"}
            else:
                return {"success": False, "message": f"Failed to start IPFS Cluster Follow: {result.stderr}"}
                
        except subprocess.TimeoutExpired:
            return {"success": True, "message": "IPFS Cluster Follow starting in background"}
        except Exception as e:
            return {"success": False, "message": f"Error starting IPFS Cluster Follow: {str(e)}"}
    
    def _start_lotus_daemon(self) -> Dict[str, Any]:
        """Start Lotus daemon."""
        try:
            import subprocess
            
            result = subprocess.run(
                ["lotus", "daemon"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return {"success": True, "message": "Lotus daemon started successfully"}
            else:
                return {"success": False, "message": f"Failed to start Lotus daemon: {result.stderr}"}
                
        except subprocess.TimeoutExpired:
            return {"success": True, "message": "Lotus daemon starting in background"}
        except Exception as e:
            return {"success": False, "message": f"Error starting Lotus daemon: {str(e)}"}
    
    def _stop_daemon_by_pid(self, pid: Optional[int], service_name: str) -> Dict[str, Any]:
        """Stop a daemon by PID."""
        if not pid:
            return {"success": False, "message": f"No PID available for {service_name}"}
        
        try:
            import psutil
            
            proc = psutil.Process(pid)
            proc.terminate()
            
            # Wait for process to terminate gracefully
            try:
                proc.wait(timeout=5)
                return {"success": True, "message": f"{service_name} stopped successfully"}
            except psutil.TimeoutExpired:
                # Force kill if it doesn't terminate gracefully
                proc.kill()
                proc.wait(timeout=2)
                return {"success": True, "message": f"{service_name} force-stopped successfully"}
                
        except psutil.NoSuchProcess:
            return {"success": True, "message": f"{service_name} was not running"}
        except psutil.AccessDenied:
            return {"success": False, "message": f"Permission denied stopping {service_name}"}
        except Exception as e:
            return {"success": False, "message": f"Error stopping {service_name}: {str(e)}"}

    # Backends
    def list_backends(self) -> List[Dict[str, Any]]:
        backends: List[Dict[str, Any]] = []
        if self.backends_dir.exists():
            for config_file in sorted(self.backends_dir.glob("*.yaml")):
                try:
                    config = yaml.safe_load(config_file.read_text()) or {}
                    backends.append({
                        "name": config_file.stem,
                        "type": config.get("type", "unknown"),
                        "status": "configured",
                        "config_file": str(config_file),
                    })
                except Exception:
                    continue
        return backends

    # Buckets (file-based store)
    def list_buckets(self) -> List[Dict[str, Any]]:
        data = self._read_json(self.buckets_file, {"buckets": []})
        return data.get("buckets", [])

    def create_bucket(self, name: str, backend: str) -> Dict[str, Any]:
        data = self._read_json(self.buckets_file, {"buckets": []})
        bucket = {
            "name": name,
            "backend": backend,
            "status": "created",
            "created_at": datetime.now().isoformat(),
        }
        data.setdefault("buckets", []).append(bucket)
        self._write_json(self.buckets_file, data)
        return bucket

    # Pins (file-based store)
    def list_pins(self) -> List[Dict[str, Any]]:
        data = self._read_json(self.pins_file, {"pins": []})
        return data.get("pins", [])

    def create_pin(self, cid: str, name: str = "") -> Dict[str, Any]:
        data = self._read_json(self.pins_file, {"pins": []})
        pin = {
            "cid": cid,
            "name": name,
            "status": "pinned",
            "pinned_at": datetime.now().isoformat(),
        }
        data.setdefault("pins", []).append(pin)
        self._write_json(self.pins_file, data)
        return pin
