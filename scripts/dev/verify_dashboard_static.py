#!/usr/bin/env python3
import anyio
import threading
import time
import requests
import sys
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from uvicorn import Config, Server
from ipfs_kit_py.mcp.dashboard.refactored_unified_mcp_dashboard import RefactoredUnifiedMCPDashboard

HOST = "127.0.0.1"
PORT = 8004

def run_server():
    app = RefactoredUnifiedMCPDashboard({"host": HOST, "port": PORT}).app
    server = Server(Config(app=app, host=HOST, port=PORT, log_level="info"))
    anyio.run(server.serve)

def main():
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(1.5)

    def check(path, ok=(200,)):
        url = f"http://{HOST}:{PORT}{path}"
        r = requests.get(url, timeout=5)
        print(f"{path} -> {r.status_code}")
        assert r.status_code in ok, f"Failed GET {path}"

    # HTML
    check("/")
    # CSS
    check("/static/css/dashboard.css")
    # Core JS
    check("/static/js/dashboard-core.js")
    check("/static/js/data-loader.js")
    check("/static/js/config-manager.js")
    check("/static/js/pins-manager.js")

    print("All dashboard endpoints responding correctly.")

if __name__ == "__main__":
    main()