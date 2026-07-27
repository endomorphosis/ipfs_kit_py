#!/usr/bin/env python3
"""
Standalone dashboard launcher - creates the dashboard without importing the module
"""
import sys
import os
import uvicorn
from pathlib import Path

# Add current directory to Python path for imports
sys.path.insert(0, os.path.abspath('.'))

# Set environment variables for the dashboard
os.environ['IPFS_KIT_DATA_DIR'] = os.path.expanduser('~/.ipfs_kit')

# Try importing all the required components directly
try:
    from fastapi import FastAPI, Request, HTTPException, Depends
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    import pandas as pd
    import json
    import aiohttp
    import yaml
    from datetime import datetime, timedelta
    import logging
    from typing import Optional, Dict, List, Any, Union
    import subprocess
    import psutil
    import time
    import glob
    from pathlib import Path
    
    print("✅ All imports successful")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def create_simple_dashboard():
    """Create a minimal FastAPI dashboard for testing."""
    app = FastAPI(title="IPFS Kit Dashboard", version="1.0.0")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/")
    async def root():
        return HTMLResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>IPFS Kit Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .status { padding: 20px; background: #f0f8ff; border-radius: 8px; }
                .success { color: #00aa00; }
                .info { color: #0066cc; }
            </style>
        </head>
        <body>
            <h1>🚀 IPFS Kit Dashboard</h1>
            <div class="status">
                <h2 class="success">✅ Dashboard is running!</h2>
                <p class="info">This is a direct uvicorn-launched instance bypassing package cache issues.</p>
                <p><strong>Data Directory:</strong> ~/.ipfs_kit/</p>
                <p><strong>Server Time:</strong> """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
            </div>
        </body>
        </html>
        """)
    
    @app.get("/api/health")
    async def health():
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    
    return app

if __name__ == "__main__":
    print("🔧 Creating simple dashboard for testing...")
    
    app = create_simple_dashboard()
    
    print("🚀 Starting dashboard on http://127.0.0.1:8085")
    print("🛑 Press Ctrl+C to stop")
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8085,
        reload=False,
        log_level="info"
    )
