#!/usr/bin/env python3
"""
Minimal test to debug final_mcp_server import issues
"""

import sys
import logging

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("debug-import")

def test_import_line_by_line():
    """Import final_mcp_server.py line by line to find the hanging line."""
    
    logger.info("Starting line-by-line import test...")
    
    # Test basic imports first
    try:
        logger.info("Testing basic imports...")
        import os
        import json
        import logging
        import asyncio
        import signal
        import argparse
        import traceback
        import importlib.util
        from datetime import datetime
        from pathlib import Path
        from typing import Dict, List, Any, Optional, Union, Callable
        import shutil
        import re
        logger.info("✅ Basic imports successful")
    except Exception as e:
        logger.error(f"❌ Basic imports failed: {e}")
        return False

    # Test protobuf patch import
    try:
        logger.info("Testing protobuf compatibility import...")
        from ipfs_kit_py.tools.protobuf_compat import monkey_patch_message_factory
        monkey_patch_message_factory()
        logger.info("✅ Protobuf compatibility successful")
    except ImportError:
        logger.warning("⚠️ protobuf_compat module not found, skipping protobuf patching.")
    except Exception as e:
        logger.error(f"❌ Error applying protobuf compatibility patch: {e}")

    # Test multihash handling
    try:
        logger.info("Testing multihash handling...")
        import multihash
        if not hasattr(multihash, 'FuncReg'):
            class MockFuncReg:
                @staticmethod
                def register(*args, **kwargs):
                    pass
            multihash.FuncReg = MockFuncReg()
        logger.info("✅ Multihash handling successful")
    except ImportError:
        logger.info("Creating mock multihash module...")
        class MockFuncReg:
            @staticmethod
            def register(*args, **kwargs):
                pass
        class MockMultihash:
            FuncReg = MockFuncReg()
        sys.modules['multihash'] = MockMultihash()
        logger.info("✅ Mock multihash module created")

    # Test transformers import
    try:
        logger.info("Testing transformers import...")
        import transformers
        logger.info(f"✅ Transformers import successful. Version: {getattr(transformers, '__version__', 'unknown')}")
    except ImportError as e:
        logger.error(f"❌ Failed to import transformers: {e}")

    # Test FastAPI imports
    try:
        logger.info("Testing FastAPI imports...")
        import uvicorn
        from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
        from fastapi.responses import JSONResponse, StreamingResponse
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.staticfiles import StaticFiles
        from starlette.responses import Response as StarletteResponse
        from starlette.background import BackgroundTask as StarletteBackgroundTask
        logger.info("✅ FastAPI imports successful")
    except ImportError as e:
        logger.error(f"❌ FastAPI imports failed: {e}")
        return False

    # Test JSON-RPC imports
    try:
        logger.info("Testing JSON-RPC imports...")
        import jsonrpcserver
        from jsonrpcserver import dispatch, Success, Error
        from jsonrpcserver import method as jsonrpc_method
        logger.info("✅ JSON-RPC imports successful")
    except ImportError as e:
        logger.error(f"❌ JSON-RPC imports failed: {e}")
        return False

    logger.info("All core imports successful! The issue might be elsewhere.")
    return True

if __name__ == "__main__":
    test_import_line_by_line()
