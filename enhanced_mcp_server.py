#!/usr/bin/env python3
"""
MCP Server Roadmap Features Bootstrapper

This script adds the new roadmap features to the MCP server:
1. Create and configure a FastAPI app
2. Register all roadmap features
3. Start the server with the enhanced functionality

Implements Phase 1 of the MCP Roadmap:
- Advanced IPFS Operations
- Enhanced Metrics & Monitoring
- Optimized Data Routing
- Advanced Authentication & Authorization
"""

import os
import sys
import logging
import json
import uvicorn
from pathlib import Path
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_enhanced")

# Add a file handler for persistent logging
file_handler = logging.FileHandler('mcp_enhanced_server.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

def load_config() -> Dict[str, Any]:
    """Load configuration from file or environment."""
    config_path = os.environ.get("MCP_CONFIG_PATH", "config/mcp_config.json")
    
    # Default configuration
    default_config = {
        "server": {
            "host": "0.0.0.0",
            "port": 8000,
            "debug": False,
            "timeout": 60
        },
        "auth": {
            "jwt_expiry": 3600,
            "refresh_expiry": 2592000,
            "db_dir": "data/auth"
        },
        "metrics": {
            "enable_prometheus": True,
            "collection_interval": 10,
            "metric_retention_days": 7
        },
        "routing": {
            "default_strategy": "hybrid",
            "update_interval": 300,
            "current_region": "default"
        },
        "storage_backends": [
            "ipfs",
            "filecoin",
            "storacha",
            "s3",
            "lassie",
            "huggingface"
        ]
    }
    
    # Try to load from file
    config = default_config.copy()
    try:
        if os.path.isfile(config_path):
            with open(config_path, 'r') as f:
                file_config = json.load(f)
                # Merge configurations (update recursively)
                _deep_update(config, file_config)
            logger.info(f"Loaded configuration from {config_path}")
    except Exception as e:
        logger.warning(f"Error loading configuration from {config_path}: {e}")
        logger.warning("Using default configuration")
    
    # Override with environment variables
    # Example: MCP_SERVER_PORT=8080 would override config["server"]["port"]
    for key, value in os.environ.items():
        if key.startswith("MCP_"):
            # Remove MCP_ prefix and split by underscore
            parts = key[4:].lower().split("_")
            if len(parts) > 1:
                # Navigate through the config dictionary
                current = config
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                
                # Set the value with appropriate type conversion
                try:
                    # Try to parse as int, float, or bool
                    if value.isdigit():
                        current[parts[-1]] = int(value)
                    elif value.replace(".", "", 1).isdigit():
                        current[parts[-1]] = float(value)
                    elif value.lower() in ("true", "false"):
                        current[parts[-1]] = value.lower() == "true"
                    else:
                        current[parts[-1]] = value
                except Exception as e:
                    logger.warning(f"Error converting environment variable {key}: {e}")
                    current[parts[-1]] = value
    
    return config

def _deep_update(target, source):
    """Deep update target dict with source data."""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_update(target[key], value)
        else:
            target[key] = value

def create_app(config: Dict[str, Any]) -> Any:
    """Create and configure the FastAPI application."""
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        
        # Create FastAPI app
        app = FastAPI(
            title="MCP Enhanced Server",
            description="Model-Controller-Persistence Server with Enhanced Features",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json"
        )
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Register integrator to add all roadmap features
        from ipfs_kit_py.mcp.integrator import get_integrator
        integrator = get_integrator(app, config)
        integrator.register_all_features()
        
        # Add shutdown event handler
        @app.on_event("shutdown")
        def shutdown_event():
            logger.info("Shutting down MCP Enhanced Server")
            integrator.shutdown()
        
        # Add basic health check endpoint
        @app.get("/health")
        async def health_check():
            return {"status": "healthy", "version": "1.0.0"}
        
        return app
    
    except ImportError as e:
        logger.error(f"Failed to import FastAPI or MCP components: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error creating FastAPI app: {e}")
        sys.exit(1)

def main():
    """Main entry point for the MCP Enhanced Server."""
    # Load configuration
    config = load_config()
    
    # Create FastAPI app with roadmap features
    app = create_app(config)
    
    # Start server using Uvicorn
    server_config = config.get("server", {})
    host = server_config.get("host", "0.0.0.0")
    port = server_config.get("port", 8000)
    
    logger.info(f"Starting MCP Enhanced Server on {host}:{port}")
    logger.info(f"Registered features: {', '.join(app._integrator.registered_features)}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )

if __name__ == "__main__":
    main()