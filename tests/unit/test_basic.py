#!/usr/bin/env python3
"""
Basic Test Script
"""

print("Testing Python and modules...")
print(f"Python version: {__import__('sys').version}")

try:
    import fastapi
    print(f"✅ FastAPI version: {fastapi.__version__}")
except ImportError as e:
    print(f"❌ FastAPI import failed: {e}")

try:
    import uvicorn
    print("✅ Uvicorn available")
except ImportError as e:
    print(f"❌ Uvicorn import failed: {e}")

try:
    import requests
    print(f"✅ Requests version: {requests.__version__}")
except ImportError as e:
    print(f"❌ Requests import failed: {e}")

print("Test completed")
