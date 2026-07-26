#!/usr/bin/env python3
"""
Simple IPFS Kit Daemon - Minimal version that starts quickly
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleDaemon:
    """Minimal daemon that starts quickly and manages state through Parquet files."""
    
    def __init__(self, host="127.0.0.1", port=9999):
        self.host = host
        self.port = port
        self.data_dir = Path.home() / ".ipfs_kit"
        self.data_dir.mkdir(exist_ok=True)
        
        self.running = False
        self.start_time = None
        self.app = self._create_app()
        
        logger.info(f"🔧 Simple IPFS Kit Daemon initialized")
        logger.info(f"💾 Data directory: {self.data_dir}")
    
    def _create_app(self):
        """Create FastAPI application."""
        app = FastAPI(title="IPFS Kit Simple Daemon", version="1.0.0")
        
        @app.get("/health")
        async def health_check():
            """Basic health check."""
            return {
                "status": "healthy",
                "uptime": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
                "data_dir": str(self.data_dir)
            }
        
        @app.get("/status")
        async def daemon_status():
            """Get daemon status including state management."""
            return await self._get_daemon_status()
        
        @app.get("/pins")
        async def list_pins():
            """List pins from parquet storage."""
            return await self._get_pins_from_parquet()
        
        @app.post("/state/update")
        async def update_state():
            """Update program state in parquet files."""
            return await self._update_state_files()
        
        return app
    
    async def _get_daemon_status(self):
        """Get comprehensive daemon status."""
        try:
            # Check parquet directories
            pin_metadata_dir = self.data_dir / "pin_metadata"
            parquet_dir = pin_metadata_dir / "parquet_storage"
            
            status = {
                "daemon": {
                    "running": self.running,
                    "start_time": self.start_time.isoformat() if self.start_time else None,
                    "uptime_seconds": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
                },
                "storage": {
                    "data_dir": str(self.data_dir),
                    "data_dir_exists": self.data_dir.exists(),
                    "pin_metadata_dir": str(pin_metadata_dir),
                    "pin_metadata_exists": pin_metadata_dir.exists(),
                    "parquet_dir": str(parquet_dir),
                    "parquet_dir_exists": parquet_dir.exists()
                },
                "state_files": await self._check_state_files()
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting daemon status: {e}")
            return {"error": str(e)}
    
    async def _check_state_files(self):
        """Check status of parquet state files."""
        try:
            state_info = {}
            
            # Check pin metadata parquet
            pin_parquet = self.data_dir / "pin_metadata" / "parquet_storage" / "pins.parquet"
            state_info["pin_metadata"] = {
                "file": str(pin_parquet),
                "exists": pin_parquet.exists(),
                "size": pin_parquet.stat().st_size if pin_parquet.exists() else 0,
                "modified": datetime.fromtimestamp(pin_parquet.stat().st_mtime).isoformat() if pin_parquet.exists() else None
            }
            
            # Check for other state files
            for pattern in ["*.parquet", "**/state.parquet", "**/index.parquet"]:
                matches = list(self.data_dir.glob(pattern))
                if matches:
                    state_info[f"other_parquet_{pattern}"] = [str(f) for f in matches]
            
            return state_info
            
        except Exception as e:
            logger.error(f"Error checking state files: {e}")
            return {"error": str(e)}
    
    async def _get_pins_from_parquet(self):
        """Get pins from parquet storage."""
        try:
            pin_parquet = self.data_dir / "pin_metadata" / "parquet_storage" / "pins.parquet"
            
            if not pin_parquet.exists():
                return {"pins": [], "total": 0, "error": "No pin parquet file found"}
            
            # Use DuckDB to read parquet
            import duckdb
            
            conn = duckdb.connect(":memory:")
            result = conn.execute(f"SELECT * FROM read_parquet('{pin_parquet}')").fetchall()
            columns = [desc[0] for desc in conn.description]
            conn.close()
            
            pins = [dict(zip(columns, row)) for row in result]
            
            return {
                "pins": pins,
                "total": len(pins),
                "file": str(pin_parquet),
                "file_size": pin_parquet.stat().st_size,
                "last_modified": datetime.fromtimestamp(pin_parquet.stat().st_mtime).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error reading pins from parquet: {e}")
            return {"pins": [], "total": 0, "error": str(e)}
    
    async def _update_state_files(self):
        """Update/export state to parquet files."""
        try:
            # Try to update pin metadata if available
            try:
                import sys
                import os
                sys.path.insert(0, '/home/devel/ipfs_kit_py/ipfs_kit_py')
                
                # Import and use pin metadata index
                from pin_metadata_index import PinMetadataIndex
                
                pin_index = PinMetadataIndex()
                result = pin_index.export_to_parquet()
                pin_update_result = f"Pin metadata exported: {result}"
                
            except Exception as e:
                pin_update_result = f"Pin metadata update failed: {e}"
            
            # Basic state file info
            updates = {
                "pin_metadata_update": pin_update_result,
                "timestamp": datetime.now().isoformat(),
                "data_dir": str(self.data_dir)
            }
            
            # Check for WAL files to ingest
            wal_files = list(self.data_dir.glob("*.wal"))
            wal_files.extend(list(self.data_dir.glob("**/*.wal")))
            
            if wal_files:
                updates["wal_files_found"] = [str(f) for f in wal_files]
                updates["wal_ingestion_status"] = "WAL files found - ingestion functionality ready for implementation"
            else:
                updates["wal_files_found"] = []
                updates["wal_ingestion_status"] = "No WAL files found"
            
            # Check for bucket index metadata
            bucket_files = list(self.data_dir.glob("**/bucket*.parquet"))
            bucket_files.extend(list(self.data_dir.glob("**/index*.parquet")))
            
            if bucket_files:
                updates["bucket_index_files"] = [str(f) for f in bucket_files]
            else:
                updates["bucket_index_files"] = []
                updates["bucket_index_status"] = "No bucket index files found - ready for creation"
            
            return updates
            
        except Exception as e:
            logger.error(f"Error updating state files: {e}")
            return {"error": str(e)}
    
    async def start(self):
        """Start the simple daemon."""
        logger.info("🚀 Starting Simple IPFS Kit Daemon...")
        
        self.running = True
        self.start_time = datetime.now()
        
        logger.info(f"🌐 Starting API server on {self.host}:{self.port}")
        
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        try:
            await server.serve()
        except Exception as e:
            logger.error(f"❌ Error running daemon: {e}")
            return False
        
        return True

async def main():
    """Run the simple daemon."""
    daemon = SimpleDaemon()
    await daemon.start()

if __name__ == "__main__":
    asyncio.run(main())
