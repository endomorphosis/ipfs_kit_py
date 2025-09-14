#!/usr/bin/env python3
"""
Simple Chrome Screenshot Capture System
Uses system Chrome to capture actual PNG screenshots saved to disk.
"""

import subprocess
import sys
import time
import json
import socket
from pathlib import Path
from datetime import datetime

def is_dashboard_running(port=8004):
    """Check if dashboard is running on port"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except Exception:
        return False

def start_dashboard():
    """Start the dashboard in background"""
    print("Starting dashboard...")
    proc = subprocess.Popen([
        "python", "/home/runner/work/ipfs_kit_py/ipfs_kit_py/ipfs_kit_cli.py", 
        "mcp", "start", "--foreground"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for startup
    time.sleep(5)
    return proc

def capture_screenshot(url, output_file):
    """Capture screenshot using Chrome headless"""
    cmd = [
        '/usr/bin/google-chrome',
        '--headless',
        '--no-sandbox', 
        '--disable-gpu',
        '--window-size=1920,1080',
        f'--screenshot={output_file}',
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("Screenshot capture timed out")
        return False
    except Exception as e:
        print(f"Error capturing screenshot: {e}")
        return False

def get_page_source(url, output_file):
    """Get page source using curl"""
    cmd = ['curl', '-s', '-o', str(output_file), url]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        return result.returncode == 0
    except Exception as e:
        print(f"Error getting page source: {e}")
        return False

def main():
    """Main screenshot capture function"""
    print("=== Simple Chrome Screenshot Capture ===")
    
    # Ensure screenshots directory exists
    screenshots_dir = Path("screenshots")
    screenshots_dir.mkdir(exist_ok=True)
    
    # Check if dashboard is running, start if needed
    dashboard_proc = None
    if not is_dashboard_running():
        dashboard_proc = start_dashboard()
        
        # Wait for dashboard to start
        for i in range(12):  # 60 seconds total
            if is_dashboard_running():
                print("Dashboard is running!")
                break
            time.sleep(5)
            print(f"Waiting for dashboard... ({(i+1)*5}s)")
        else:
            print("Dashboard failed to start within 60 seconds")
            return False
    else:
        print("Dashboard is already running!")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    url = "http://127.0.0.1:8004"
    
    # Capture screenshot
    screenshot_path = screenshots_dir / f"dashboard_chrome_{timestamp}.png"
    print(f"Capturing screenshot to: {screenshot_path}")
    
    success = capture_screenshot(url, str(screenshot_path))
    
    if success and screenshot_path.exists():
        size = screenshot_path.stat().st_size
        print(f"✅ Screenshot saved: {screenshot_path} ({size:,} bytes)")
        
        # Get page source
        source_path = screenshots_dir / f"dashboard_source_{timestamp}.html"
        if get_page_source(url, source_path):
            print(f"✅ Page source saved: {source_path}")
            
            # Analyze source
            try:
                with open(source_path, 'r') as f:
                    source = f.read()
                    
                analysis = {
                    'timestamp': timestamp,
                    'url': url,
                    'screenshot': str(screenshot_path),
                    'source': str(source_path),
                    'analysis': {
                        'has_rocket_emoji': '🚀' in source,
                        'has_ipfs_kit': 'IPFS Kit' in source,
                        'has_dashboard': 'dashboard' in source.lower(),
                        'has_navigation': any(nav in source.lower() for nav in ['nav', 'menu', 'tab']),
                        'source_length': len(source)
                    }
                }
                
                # Save analysis
                analysis_path = screenshots_dir / f"analysis_{timestamp}.json"
                with open(analysis_path, 'w') as f:
                    json.dump(analysis, f, indent=2)
                
                print(f"✅ Analysis saved: {analysis_path}")
                
                # Print summary
                print("\n=== Analysis Summary ===")
                print(f"Rocket emoji (🚀): {analysis['analysis']['has_rocket_emoji']}")
                print(f"IPFS Kit text: {analysis['analysis']['has_ipfs_kit']}")
                print(f"Dashboard content: {analysis['analysis']['has_dashboard']}")
                print(f"Navigation elements: {analysis['analysis']['has_navigation']}")
                print(f"Source length: {analysis['analysis']['source_length']} chars")
                
                return True
                
            except Exception as e:
                print(f"Error analyzing source: {e}")
                return True
                
            except Exception as e:
                print(f"Error analyzing source: {e}")
                return False
        else:
            print("Failed to get page source")
            return False
    else:
        print(f"❌ Failed to capture screenshot")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)