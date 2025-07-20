
import pytest
import subprocess
import time
import requests

from playwright.sync_api import Page, expect

import os
import sys
import re

# Add the project root to sys.path to ensure modules are found
sys.path.insert(0, os.getcwd())

    # Define the path to your MCP server script
MCP_SERVER_PATH = "mcp/ipfs_kit/modular_enhanced_mcp_server.py"
BASE_URL = "http://127.0.0.1:8000"  # Default port for FastAPI/Uvicorn

@pytest.fixture(scope="module")
def mcp_server():
    """Starts and stops the MCP server for tests."""
    print(f"Starting MCP server...")
    port = 8000 # You can make this dynamic later if needed
    process = None
    server_script_content = f"""
import os
import sys
import uvicorn
from mcp.ipfs_kit.modular_enhanced_mcp_server import ModularEnhancedMCPServer

# Add the project root to sys.path
sys.path.insert(0, os.getcwd())

# Instantiate the server and get the app instance
server_instance = ModularEnhancedMCPServer(host="127.0.0.1", port={port})
server_instance._setup_web_server() # Ensure the app is set up

if __name__ == "__main__":
    uvicorn.run(server_instance.app, host="127.0.0.1", port={port}, log_level="info", access_log=False)
"""
    
    # Create a temporary script file
    temp_script_path = "temp_mcp_server_runner.py"
    with open(temp_script_path, "w") as f:
        f.write(server_script_content)

    try:
        process = subprocess.Popen(
            ["python", temp_script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=dict(os.environ, PYTHONPATH=os.getcwd())
        )
        
        # Wait for the server to start, allowing at least 15 seconds
        health_check_url = f"{BASE_URL}/api/health"
        retries = 10 # Increased retries
        for i in range(retries):
            try:
                response = requests.get(health_check_url, timeout=5)
                if response.status_code == 200:
                    print("MCP server is up and running (health check passed).")
                    break
            except requests.exceptions.ConnectionError:
                print(f"Waiting for MCP server... (Attempt {i+1}/{retries})")
                time.sleep(5)  # Increased sleep time
        else:
            stdout, stderr = process.communicate()
            print(f"MCP Server STDOUT (after timeout):")
            print(stdout)
            print(f"MCP Server STDERR (after timeout):")
            print(stderr)
            raise RuntimeError("MCP server did not start within the expected time.")

        yield process, port  # Provide the process and port to the tests
    finally:
        if process:
            print("Stopping MCP server...")
            process.terminate()
            process.wait(timeout=10)
            if process.poll() is None:
                process.kill()
            print("MCP server stopped.")
        # Clean up the temporary script
        if os.path.exists(temp_script_path):
            os.remove(temp_script_path)

def test_dashboard_loads_correctly(page: Page, mcp_server):
    """
    Tests that the dashboard HTML loads correctly and has the expected title.
    """
    _, port = mcp_server
    dashboard_url = f"{BASE_URL}/"
    print(f"Navigating to dashboard at {dashboard_url}")
    page.goto(dashboard_url)

    # Print page content for debugging
    print("Page content:\n", page.content())

    # Assert that the page has the correct title
    expect(page).to_have_title("Enhanced IPFS Kit Backend Observatory")

    # Take a screenshot for visual verification
    page.screenshot(path="dashboard_loaded.png")
    print("Screenshot 'dashboard_loaded.png' taken.")

    # You can add more assertions here, e.g., check for specific elements
    expect(page.locator("h1")).to_have_text("🔭 Enhanced IPFS Kit Backend Observatory")
    expect(page.locator(".tab-button.active")).to_have_text("📊 Overview")
    print("Dashboard loaded correctly and basic elements are present.")

def test_dynamic_data_loading(page: Page, mcp_server):
    """
    Tests that the dashboard dynamically loads and displays data from the API.
    """
    _, port = mcp_server
    dashboard_url = f"{BASE_URL}/"
    print(f"Navigating to dashboard at {dashboard_url}")
    with page.expect_response(f"{BASE_URL}/api/health", timeout=60000) as response_info:
        page.goto(dashboard_url)
    response = response_info.value
    assert response.status == 200

    # Wait for the data to load and elements to be visible
    expect(page.locator("#systemStatus")).to_contain_text("Status:", timeout=10000)
    expect(page.locator("#backendSummary")).to_contain_text("Backends Healthy", timeout=10000)
    expect(page.locator("#performanceMetrics")).to_contain_text("Memory:", timeout=10000)

    # Fetch data directly from the API to compare
    api_health_response = requests.get(f"{BASE_URL}/api/health").json()
    data = api_health_response.get("data", {})

    # Assert System Status
    system_status_text = page.locator("#systemStatus").text_content()
    expect(page.locator("#systemStatus")).to_contain_text(f"Status: {data.get("status", "running")}")
    expect(page.locator("#systemStatus")).to_contain_text("Uptime:")

    # Assert Backend Summary
    backend_summary_text = page.locator("#backendSummary").text_content()
    # Extract healthy_count and total_count from the displayed text
    match = re.search(r'(\d+)/(\d+)', backend_summary_text)
    if match:
        healthy_count_displayed = int(match.group(1))
        total_count_displayed = int(match.group(2))
        expect(page.locator("#backendSummary")).to_contain_text(f"{healthy_count_displayed}/{total_count_displayed}")
    else:
        raise AssertionError(f"Could not extract healthy/total count from backend summary: {backend_summary_text}")
    expect(page.locator("#backendSummary")).to_contain_text("Backends Healthy")

    # Assert Performance Metrics
    performance_metrics_text = page.locator("#performanceMetrics").text_content()
    expect(page.locator("#performanceMetrics")).to_contain_text("Memory:")
    expect(page.locator("#performanceMetrics")).to_contain_text("CPU:")
    expect(page.locator("#performanceMetrics")).to_contain_text("Active Backends:")

    page.screenshot(path="dashboard_dynamic_data.png")
    print("Screenshot 'dashboard_dynamic_data.png' taken.")
    print("Dynamic data loaded and displayed correctly.")


