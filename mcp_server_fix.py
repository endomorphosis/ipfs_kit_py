#!/usr/bin/env python3
"""
MCP Server Fix - Add missing list_bucket_files tool
=================================================

This script fixes the "Unknown tool: list_bucket_files" error by providing
a minimal MCP server with the missing tool implementation.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="MCP Server Fix", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data directory for buckets (same as the comprehensive dashboard)
data_dir = Path.home() / ".ipfs_kit"

@app.post("/mcp/tools/call")
async def handle_mcp_tool_call(request: Request):
    """Handle MCP tool calls including the missing list_bucket_files tool."""
    try:
        data = await request.json()
        logger.info(f"MCP tool call: {data}")
        
        method = data.get("method")
        params = data.get("params", {})
        request_id = data.get("id", 1)
        
        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name == "list_bucket_files":
                result = await handle_list_bucket_files(arguments)
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id
                })
            elif tool_name == "health_check":
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "result": {
                        "status": "healthy",
                        "timestamp": datetime.now().isoformat()
                    },
                    "id": request_id
                })
            elif tool_name == "list_buckets":
                result = await handle_list_buckets(arguments)
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id
                })
            else:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    },
                    "id": request_id
                })
        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Unknown method: {method}"
                },
                "id": request_id
            })
            
    except Exception as e:
        logger.error(f"Error handling MCP tool call: {e}")
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": str(e)
            },
            "id": data.get("id", 1) if isinstance(data, dict) else 1
        })

async def handle_list_bucket_files(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle the list_bucket_files tool call."""
    bucket_name = arguments.get("bucket")
    path = arguments.get("path", "")
    metadata_first = arguments.get("metadata_first", False)
    
    if not bucket_name:
        return {"error": "bucket parameter is required"}
    
    bucket_dir = data_dir / "buckets" / bucket_name
    
    if not bucket_dir.exists():
        return {
            "files": [],
            "directories": [],
            "total_count": 0
        }
    
    # Build the full path within the bucket
    if path and path != "/":
        target_dir = bucket_dir / path.lstrip("/")
    else:
        target_dir = bucket_dir
    
    if not target_dir.exists():
        return {
            "files": [],
            "directories": [],
            "total_count": 0
        }
    
    files = []
    directories = []
    
    try:
        for item in target_dir.iterdir():
            if item.name == "metadata.json":
                continue
                
            relative_path = str(item.relative_to(bucket_dir))
            
            if item.is_file():
                file_info = {
                    "name": item.name,
                    "path": relative_path,
                    "size": item.stat().st_size,
                    "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat(),
                    "type": "file"
                }
                files.append(file_info)
            elif item.is_dir():
                dir_info = {
                    "name": item.name,
                    "path": relative_path,
                    "type": "directory"
                }
                directories.append(dir_info)
                
    except Exception as e:
        logger.error(f"Error listing files in bucket {bucket_name}: {e}")
        return {"error": f"Failed to list files: {str(e)}"}
    
    return {
        "files": files,
        "directories": directories,
        "total_count": len(files) + len(directories),
        "bucket": bucket_name,
        "path": path
    }

async def handle_list_buckets(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Handle the list_buckets tool call."""
    buckets = []
    buckets_dir = data_dir / "buckets"
    
    if buckets_dir.exists():
        for bucket_dir in buckets_dir.iterdir():
            if bucket_dir.is_dir():
                # Read metadata
                metadata_file = bucket_dir / "metadata.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            bucket_info = json.load(f)
                    except:
                        bucket_info = {"name": bucket_dir.name, "type": "unknown"}
                else:
                    bucket_info = {"name": bucket_dir.name, "type": "unknown"}
                
                # Add file count
                file_count = len([f for f in bucket_dir.rglob("*") if f.is_file() and f.name != "metadata.json"])
                bucket_info["file_count"] = file_count
                
                buckets.append(bucket_info)
    
    return {"items": buckets}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })

@app.get("/")
async def root():
    """Root endpoint with server info."""
    return JSONResponse({
        "message": "MCP Server Fix is running",
        "version": "1.0.0",
        "tools": ["list_bucket_files", "list_buckets", "health_check"]
    })

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Server Fix")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8004, help="Port to bind to")
    args = parser.parse_args()
    
    logger.info(f"Starting MCP Server Fix on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)