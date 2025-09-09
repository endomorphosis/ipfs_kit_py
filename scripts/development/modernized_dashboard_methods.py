#!/usr/bin/env python3
"""
Modernized Comprehensive Dashboard - Implementation Methods

This file contains the implementation methods for the modernized dashboard.
All methods use the new light initialization pattern with graceful fallbacks.
"""

# === Implementation Methods Continuation ===

async def _get_system_overview(self) -> Dict[str, Any]:
    """Get comprehensive system overview."""
    try:
        services_count = len(await self._get_services_status())
        backends_count = len(await self._get_backends_status())
        buckets_count = len(await self._get_buckets())
        
        # Get bucket files count
        buckets = await self._get_buckets()
        total_files = sum(bucket.get('file_count', 0) for bucket in buckets)
        
        uptime_seconds = (datetime.now() - self.start_time).total_seconds()
        uptime_str = f"{int(uptime_seconds // 3600):02d}:{int((uptime_seconds % 3600) // 60):02d}:{int(uptime_seconds % 60):02d}"
        
        return {
            "services": services_count,
            "backends": backends_count,
            "buckets": buckets_count,
            "total_files": total_files,
            "uptime": uptime_str,
            "status": "running",
            "component_status": self.component_status,
            "websocket_connections": len(self.websocket_connections),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logging.error(f"Error getting system overview: {e}")
        return {"error": str(e), "status": "error"}

async def _get_system_metrics(self) -> Dict[str, Any]:
    """Get detailed system metrics."""
    try:
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds()
        }
        
        if PSUTIL_AVAILABLE:
            metrics.update({
                "cpu_usage": psutil.cpu_percent(),
                "memory": {
                    "percent": psutil.virtual_memory().percent,
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available
                },
                "disk": {
                    "total": psutil.disk_usage('/').total,
                    "used": psutil.disk_usage('/').used,
                    "free": psutil.disk_usage('/').free,
                    "percent": psutil.disk_usage('/').percent
                }
            })
        else:
            metrics.update({
                "cpu_usage": 0.0,
                "memory": {"percent": 0.0, "total": 0, "available": 0},
                "disk": {"total": 0, "used": 0, "free": 0, "percent": 0.0}
            })
        
        return metrics
    except Exception as e:
        logging.error(f"Error getting system metrics: {e}")
        return {"error": str(e)}

async def _get_system_health(self) -> Dict[str, Any]:
    """Get comprehensive system health status."""
    health = {
        "status": "healthy",
        "checks": {},
        "timestamp": datetime.now().isoformat()
    }
    
    # Check IPFS connection
    try:
        if self.ipfs_api and hasattr(self.ipfs_api, 'available') and self.ipfs_api.available:
            ipfs_id = self.ipfs_api.id()
            health["checks"]["ipfs"] = {
                "status": "healthy",
                "details": {"connected": True, "id": ipfs_id.get("ID", "unknown")}
            }
        else:
            health["checks"]["ipfs"] = {
                "status": "degraded",
                "details": {"connected": False, "reason": "mock_mode"}
            }
    except Exception as e:
        health["checks"]["ipfs"] = {
            "status": "unhealthy",
            "details": {"error": str(e)}
        }
    
    # Check bucket manager
    try:
        buckets = self.bucket_manager.list_buckets()
        health["checks"]["bucket_manager"] = {
            "status": "healthy",
            "details": {"bucket_count": len(buckets)}
        }
    except Exception as e:
        health["checks"]["bucket_manager"] = {
            "status": "unhealthy",
            "details": {"error": str(e)}
        }
    
    # Check data directory
    try:
        if self.data_dir.exists():
            health["checks"]["data_dir"] = {
                "status": "healthy",
                "details": {"path": str(self.data_dir), "exists": True}
            }
        else:
            health["checks"]["data_dir"] = {
                "status": "warning",
                "details": {"path": str(self.data_dir), "exists": False}
            }
    except Exception as e:
        health["checks"]["data_dir"] = {
            "status": "unhealthy",
            "details": {"error": str(e)}
        }
    
    # Determine overall health
    unhealthy_checks = [name for name, check in health["checks"].items() if check["status"] == "unhealthy"]
    if unhealthy_checks:
        health["status"] = "unhealthy"
    elif any(check["status"] == "degraded" for check in health["checks"].values()):
        health["status"] = "degraded"
    
    return health

async def _get_services_status(self) -> List[Dict[str, Any]]:
    """Get status of all services."""
    services = []
    
    # IPFS service
    ipfs_status = "running" if (self.ipfs_api and getattr(self.ipfs_api, 'available', True)) else "stopped"
    services.append({
        "name": "IPFS Node",
        "type": "ipfs",
        "status": ipfs_status,
        "description": "IPFS node connection",
        "availability": IPFS_AVAILABLE
    })
    
    # MCP server
    services.append({
        "name": "MCP Server",
        "type": "mcp",
        "status": "running",
        "description": "Model Context Protocol server",
        "availability": True
    })
    
    # Dashboard
    services.append({
        "name": "Web Dashboard",
        "type": "web",
        "status": "running",
        "description": "Web-based management interface",
        "availability": True
    })
    
    # Bucket Manager
    bucket_status = "running" if BUCKET_MANAGER_AVAILABLE else "degraded"
    services.append({
        "name": "Bucket Manager",
        "type": "bucket",
        "status": bucket_status,
        "description": "Bucket-based VFS management",
        "availability": BUCKET_MANAGER_AVAILABLE
    })
    
    return services

async def _control_service(self, service_name: str, action: str) -> Dict[str, Any]:
    """Control service operations."""
    try:
        # This is a mock implementation - in a real system, this would
        # interface with actual service management
        if action not in ["start", "stop", "restart", "status"]:
            raise ValueError(f"Invalid action: {action}")
        
        return {
            "service": service_name,
            "action": action,
            "status": "completed",
            "message": f"Service {service_name} {action} completed (mock)",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logging.error(f"Service control error: {e}")
        return {"error": str(e), "service": service_name, "action": action}

async def _get_service_details(self, service_name: str) -> Dict[str, Any]:
    """Get detailed service information."""
    services = await self._get_services_status()
    
    if service_name == "all":
        return {"services": services}
    
    service = next((s for s in services if s["name"].lower() == service_name.lower()), None)
    if not service:
        return {"error": f"Service {service_name} not found"}
    
    # Add detailed information
    if service["type"] == "ipfs" and self.ipfs_api:
        try:
            if hasattr(self.ipfs_api, 'available') and self.ipfs_api.available:
                ipfs_id = self.ipfs_api.id()
                repo_stat = self.ipfs_api.repo_stat()
                peers = self.ipfs_api.swarm_peers()
                
                service["details"] = {
                    "id": ipfs_id.get("ID", "unknown"),
                    "repo_size": repo_stat.get("RepoSize", 0),
                    "objects": repo_stat.get("NumObjects", 0),
                    "peers": len(peers.get("Peers", []))
                }
        except Exception as e:
            service["details"] = {"error": str(e)}
    
    return service

async def _get_backends_status(self) -> List[Dict[str, Any]]:
    """Get status of storage backends."""
    backends = []
    
    # IPFS backend
    ipfs_status = "running" if (self.ipfs_api and getattr(self.ipfs_api, 'available', True)) else "stopped"
    backends.append({
        "name": "IPFS Local",
        "type": "ipfs",
        "status": ipfs_status,
        "url": "http://127.0.0.1:5001",
        "description": "Local IPFS node",
        "availability": IPFS_AVAILABLE
    })
    
    # Filesystem backend
    backends.append({
        "name": "File System",
        "type": "filesystem",
        "status": "available",
        "description": "Local file system storage",
        "availability": True
    })
    
    # Bucket backend
    bucket_status = "running" if BUCKET_MANAGER_AVAILABLE else "degraded"
    backends.append({
        "name": "Bucket Storage",
        "type": "bucket",
        "status": bucket_status,
        "description": "Bucket-based virtual filesystem",
        "availability": BUCKET_MANAGER_AVAILABLE
    })
    
    return backends

async def _get_backend_health(self) -> Dict[str, Any]:
    """Get detailed backend health information."""
    backends = await self._get_backends_status()
    health = {
        "overall_status": "healthy",
        "backends": {},
        "timestamp": datetime.now().isoformat()
    }
    
    for backend in backends:
        backend_health = {
            "status": backend["status"],
            "availability": backend["availability"],
            "last_check": datetime.now().isoformat()
        }
        
        if backend["type"] == "ipfs" and self.ipfs_api:
            try:
                if hasattr(self.ipfs_api, 'available') and self.ipfs_api.available:
                    repo_stat = self.ipfs_api.repo_stat()
                    backend_health["metrics"] = {
                        "repo_size": repo_stat.get("RepoSize", 0),
                        "objects": repo_stat.get("NumObjects", 0)
                    }
            except Exception as e:
                backend_health["error"] = str(e)
                backend_health["status"] = "unhealthy"
        
        health["backends"][backend["name"]] = backend_health
    
    # Determine overall health
    if any(b["status"] == "unhealthy" for b in health["backends"].values()):
        health["overall_status"] = "unhealthy"
    elif any(b["status"] in ["stopped", "degraded"] for b in health["backends"].values()):
        health["overall_status"] = "degraded"
    
    return health

async def _create_backend_config(self, config: BackendConfig) -> Dict[str, Any]:
    """Create backend configuration."""
    try:
        # Mock implementation - in real system this would save actual config
        config_path = self.data_dir / "backends" / f"{config.name}.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        config_data = {
            "name": config.name,
            "type": config.type,
            "config": config.config,
            "created": datetime.now().isoformat()
        }
        
        if YAML_AVAILABLE:
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f)
        
        return {
            "status": "created",
            "config": config_data,
            "path": str(config_path)
        }
    except Exception as e:
        logging.error(f"Backend config creation error: {e}")
        return {"error": str(e)}

async def _get_backend_config(self, backend_name: str) -> Dict[str, Any]:
    """Get backend configuration."""
    try:
        config_path = self.data_dir / "backends" / f"{backend_name}.yaml"
        
        if config_path.exists() and YAML_AVAILABLE:
            with open(config_path, 'r') as f:
                config_data = yaml.load(f, Loader=yaml.SafeLoader)
            return config_data
        else:
            return {
                "name": backend_name,
                "type": "unknown",
                "status": "not_found"
            }
    except Exception as e:
        logging.error(f"Backend config retrieval error: {e}")
        return {"error": str(e)}

async def _get_buckets(self) -> List[Dict[str, Any]]:
    """Get list of buckets using modern bucket manager."""
    try:
        buckets = self.bucket_manager.list_buckets()
        
        # Enhance bucket info
        enhanced_buckets = []
        for bucket in buckets:
            if isinstance(bucket, dict):
                enhanced_bucket = {
                    "name": bucket.get("name", "unknown"),
                    "file_count": bucket.get("files", 0),
                    "total_size": bucket.get("size", 0),
                    "status": "active",
                    "created": bucket.get("created", "unknown"),
                    "type": bucket.get("type", "default")
                }
            else:
                enhanced_bucket = {
                    "name": str(bucket),
                    "file_count": 0,
                    "total_size": 0,
                    "status": "active",
                    "type": "default"
                }
            enhanced_buckets.append(enhanced_bucket)
        
        return enhanced_buckets
    except Exception as e:
        logging.error(f"Error getting buckets: {e}")
        return []

async def _create_bucket(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new bucket."""
    try:
        bucket_name = data.get("name")
        bucket_type = data.get("type", "default")
        
        if not bucket_name:
            return {"error": "Bucket name is required"}
        
        result = self.bucket_manager.create_bucket(bucket_name, type=bucket_type)
        
        return {
            "status": "created",
            "bucket": {
                "name": bucket_name,
                "type": bucket_type,
                "created": datetime.now().isoformat()
            },
            "result": result
        }
    except Exception as e:
        logging.error(f"Bucket creation error: {e}")
        return {"error": str(e)}

async def _delete_bucket(self, bucket_name: str) -> Dict[str, Any]:
    """Delete a bucket."""
    try:
        result = self.bucket_manager.remove_bucket(bucket_name)
        return {
            "status": "deleted",
            "bucket": bucket_name,
            "result": result
        }
    except Exception as e:
        logging.error(f"Bucket deletion error: {e}")
        return {"error": str(e)}

async def _list_bucket_files(self, bucket_name: str) -> Dict[str, Any]:
    """List files in a bucket."""
    try:
        files = self.bucket_manager.list_files(bucket_name)
        return {
            "bucket": bucket_name,
            "files": files,
            "count": len(files)
        }
    except Exception as e:
        logging.error(f"Bucket file listing error: {e}")
        return {"error": str(e), "bucket": bucket_name}

async def _upload_to_bucket(self, bucket_name: str, file: UploadFile) -> Dict[str, Any]:
    """Upload file to bucket."""
    try:
        content = await file.read()
        result = self.bucket_manager.upload_file(bucket_name, file.filename, content)
        
        return {
            "status": "uploaded",
            "bucket": bucket_name,
            "filename": file.filename,
            "size": len(content),
            "result": result
        }
    except Exception as e:
        logging.error(f"Bucket upload error: {e}")
        return {"error": str(e)}

# === File Operations ===

async def _list_directory_files(self, path: str) -> List[str]:
    """List files in a directory."""
    try:
        path_obj = Path(path)
        if not path_obj.exists():
            return []
        
        if path_obj.is_file():
            return [str(path_obj)]
        
        files = []
        for item in path_obj.iterdir():
            files.append(str(item))
        
        return files
    except Exception as e:
        logging.error(f"Directory listing error: {e}")
        return []

async def _read_file(self, path: str) -> str:
    """Read file content."""
    try:
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"File {path} does not exist")
        
        return path_obj.read_text(encoding='utf-8')
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

async def _write_file(self, path: str, content: str) -> str:
    """Write file content."""
    try:
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        path_obj.write_text(content, encoding='utf-8')
        return f"Successfully wrote {len(content)} characters to {path}"
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

async def _read_bucket_file(self, bucket_name: str, file_path: str) -> str:
    """Read file from bucket."""
    # This would need bucket manager support for reading files
    return f"Reading {file_path} from bucket {bucket_name} (not implemented)"

async def _write_bucket_file(self, bucket_name: str, file_path: str, content: str) -> str:
    """Write file to bucket."""
    try:
        result = self.bucket_manager.upload_file(bucket_name, file_path, content.encode('utf-8'))
        return f"Successfully wrote to {file_path} in bucket {bucket_name}"
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# === IPFS Operations ===

async def _ipfs_add(self, content: str, pin: bool = False) -> Dict[str, Any]:
    """Add content to IPFS."""
    try:
        if not self.ipfs_api or not getattr(self.ipfs_api, 'available', True):
            return {"hash": "mock_hash", "status": "mock_mode"}
        
        result = self.ipfs_api.add(content)
        hash_value = result.get("Hash")
        
        if pin and hash_value:
            self.ipfs_api.pin_add(hash_value)
        
        return {
            "hash": hash_value,
            "size": len(content),
            "pinned": pin
        }
    except Exception as e:
        logging.error(f"IPFS add error: {e}")
        return {"error": str(e)}

async def _ipfs_get(self, cid: str) -> Dict[str, Any]:
    """Get content from IPFS."""
    try:
        if not self.ipfs_api or not getattr(self.ipfs_api, 'available', True):
            return {"content": f"mock content for {cid}", "status": "mock_mode"}
        
        # This would be implemented when IPFS get functionality is available
        return {"content": f"Content for {cid}", "cid": cid}
    except Exception as e:
        logging.error(f"IPFS get error: {e}")
        return {"error": str(e)}

# === Testing Methods ===

async def _test_all_components(self) -> Dict[str, Any]:
    """Test all system components."""
    test_results = {
        "timestamp": datetime.now().isoformat(),
        "overall_status": "pass",
        "tests": {}
    }
    
    # Test IPFS
    try:
        if self.ipfs_api and getattr(self.ipfs_api, 'available', True):
            ipfs_id = self.ipfs_api.id()
            test_results["tests"]["ipfs"] = {
                "status": "pass",
                "details": {"id": ipfs_id.get("ID", "unknown")}
            }
        else:
            test_results["tests"]["ipfs"] = {
                "status": "skip",
                "details": {"reason": "mock_mode"}
            }
    except Exception as e:
        test_results["tests"]["ipfs"] = {
            "status": "fail",
            "error": str(e)
        }
    
    # Test bucket manager
    try:
        buckets = self.bucket_manager.list_buckets()
        test_results["tests"]["bucket_manager"] = {
            "status": "pass",
            "details": {"bucket_count": len(buckets)}
        }
    except Exception as e:
        test_results["tests"]["bucket_manager"] = {
            "status": "fail",
            "error": str(e)
        }
    
    # Test logging
    try:
        logs = self.log_handler.get_logs(limit=1)
        test_results["tests"]["logging"] = {
            "status": "pass",
            "details": {"recent_logs": len(logs)}
        }
    except Exception as e:
        test_results["tests"]["logging"] = {
            "status": "fail",
            "error": str(e)
        }
    
    # Determine overall status
    failed_tests = [name for name, test in test_results["tests"].items() if test["status"] == "fail"]
    if failed_tests:
        test_results["overall_status"] = "fail"
        test_results["failed_tests"] = failed_tests
    
    return test_results

async def _test_mcp_tools(self) -> Dict[str, Any]:
    """Test all MCP tools."""
    test_results = {
        "timestamp": datetime.now().isoformat(),
        "overall_status": "pass",
        "tool_tests": {}
    }
    
    for tool_name in self.mcp_tools.keys():
        try:
            # Test with safe parameters
            if tool_name == "list_buckets":
                result = await self._execute_mcp_tool(tool_name, {})
                test_results["tool_tests"][tool_name] = {
                    "status": "pass",
                    "result_type": type(result).__name__
                }
            elif tool_name == "system_metrics":
                result = await self._execute_mcp_tool(tool_name, {})
                test_results["tool_tests"][tool_name] = {
                    "status": "pass",
                    "result_type": type(result).__name__
                }
            else:
                test_results["tool_tests"][tool_name] = {
                    "status": "skip",
                    "reason": "requires_parameters"
                }
        except Exception as e:
            test_results["tool_tests"][tool_name] = {
                "status": "fail",
                "error": str(e)
            }
    
    # Determine overall status
    failed_tools = [name for name, test in test_results["tool_tests"].items() if test["status"] == "fail"]
    if failed_tools:
        test_results["overall_status"] = "fail"
        test_results["failed_tools"] = failed_tools
    
    return test_results
