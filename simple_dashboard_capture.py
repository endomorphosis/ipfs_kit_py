#!/usr/bin/env python3
"""
Simple Dashboard Analysis and Basic Screenshot Capture
"""

import asyncio
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional

class SimpleDashboardAnalyzer:
    def __init__(self, base_url: str = "http://127.0.0.1:8004"):
        self.base_url = base_url
        self.results = {}
        self.screenshots_dir = Path("screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)
        
    def test_dashboard_accessibility(self) -> Dict[str, Any]:
        """Test if dashboard is accessible and get basic info"""
        results = {
            "accessible": False,
            "response_code": None,
            "html_content": None,
            "content_length": 0,
            "headers": {}
        }
        
        try:
            print(f"Testing accessibility of {self.base_url}")
            req = urllib.request.Request(self.base_url)
            with urllib.request.urlopen(req, timeout=10) as response:
                results["response_code"] = response.getcode()
                results["headers"] = dict(response.headers)
                
                # Read HTML content
                content = response.read().decode('utf-8', errors='ignore')
                results["html_content"] = content
                results["content_length"] = len(content)
                
                if response.getcode() == 200:
                    results["accessible"] = True
                    print(f"✅ Dashboard accessible - HTTP {response.getcode()}")
                else:
                    print(f"⚠️ Dashboard returned HTTP {response.getcode()}")
                    
        except urllib.error.URLError as e:
            results["error"] = str(e)
            print(f"❌ Dashboard not accessible: {e}")
        except Exception as e:
            results["error"] = str(e)
            print(f"❌ Error testing dashboard: {e}")
            
        return results
    
    def analyze_html_content(self, html_content: str) -> Dict[str, Any]:
        """Analyze the HTML content for key features"""
        if not html_content:
            return {"error": "No HTML content to analyze"}
            
        analysis = {
            "title": None,
            "has_rocket_emoji": False,
            "has_ipfs_kit": False,
            "navigation_items": [],
            "component_counts": [],
            "theme_analysis": {},
            "script_tags": 0,
            "style_tags": 0,
            "estimated_functionality": {}
        }
        
        # Basic HTML analysis
        html_lower = html_content.lower()
        
        # Extract title
        import re
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE)
        if title_match:
            analysis["title"] = title_match.group(1).strip()
        
        # Check for rocket emoji and IPFS Kit
        analysis["has_rocket_emoji"] = "🚀" in html_content
        analysis["has_ipfs_kit"] = "ipfs kit" in html_lower or "ipfskit" in html_lower
        
        # Look for navigation items
        nav_patterns = [
            r'(?:nav|menu|tab)[^>]*>([^<]*(?:overview|services|backends|buckets|pins|logs|files|tools|ipfs|cars|analytics|configuration)[^<]*)',
            r'>([^<]*(?:overview|services|backends|buckets|pins|logs|files|tools|ipfs|cars|analytics|configuration)[^<]*)</[^>]*(?:nav|menu|tab|button|link)',
            r'(?:href|onclick)[^>]*["\']#?([^"\']*(?:overview|services|backends|buckets|pins|logs|files|tools|ipfs|cars|analytics|configuration)[^"\']*)'
        ]
        
        for pattern in nav_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                cleaned = re.sub(r'[^\w\s]', ' ', match).strip()
                if cleaned and len(cleaned) < 50:
                    analysis["navigation_items"].append(cleaned)
        
        # Remove duplicates and clean up
        analysis["navigation_items"] = list(set(analysis["navigation_items"]))
        
        # Look for component counts (numbers followed by relevant terms)
        count_patterns = [
            r'(\d+)\s*(?:tools?|backends?|services?|buckets?|pins?|files?)',
            r'(?:tools?|backends?|services?|buckets?|pins?|files?)[\s:]*(\d+)',
        ]
        
        for pattern in count_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            analysis["component_counts"].extend([int(match) for match in matches if match.isdigit()])
        
        # Count script and style tags
        analysis["script_tags"] = len(re.findall(r'<script[^>]*>', html_content, re.IGNORECASE))
        analysis["style_tags"] = len(re.findall(r'<style[^>]*>', html_content, re.IGNORECASE))
        
        # Theme analysis
        if "dark" in html_lower:
            analysis["theme_analysis"]["likely_dark"] = True
        if any(color in html_lower for color in ["#f5f5f5", "background-color: #f5f5f5", "bg-gray-50"]):
            analysis["theme_analysis"]["likely_light"] = True
        
        # Functionality estimation
        analysis["estimated_functionality"]["has_mcp_tools"] = "mcp" in html_lower and "tool" in html_lower
        analysis["estimated_functionality"]["has_backend_management"] = "backend" in html_lower and any(word in html_lower for word in ["manage", "config", "storage"])
        analysis["estimated_functionality"]["has_system_metrics"] = any(term in html_lower for term in ["cpu", "memory", "disk", "usage", "metric"])
        analysis["estimated_functionality"]["has_websocket"] = "websocket" in html_lower or "ws://" in html_lower
        
        return analysis
    
    def compare_with_pr38_expectations(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Compare current dashboard with PR #38 expectations"""
        pr38_checks = {
            "rocket_emoji_header": {
                "expected": True,
                "actual": analysis.get("has_rocket_emoji", False),
                "status": "✅" if analysis.get("has_rocket_emoji", False) else "❌"
            },
            "ipfs_kit_branding": {
                "expected": True,
                "actual": analysis.get("has_ipfs_kit", False),
                "status": "✅" if analysis.get("has_ipfs_kit", False) else "❌"
            },
            "expected_navigation": {
                "expected": ["Overview", "Services", "Backends", "Pin Management", "Peer Management", "Logs", "Analytics", "Configuration"],
                "actual": analysis.get("navigation_items", []),
                "matching_count": 0,
                "status": "❓"
            },
            "system_metrics": {
                "expected": True,
                "actual": analysis.get("estimated_functionality", {}).get("has_system_metrics", False),
                "status": "✅" if analysis.get("estimated_functionality", {}).get("has_system_metrics", False) else "❌"
            },
            "mcp_integration": {
                "expected": True,
                "actual": analysis.get("estimated_functionality", {}).get("has_mcp_tools", False),
                "status": "✅" if analysis.get("estimated_functionality", {}).get("has_mcp_tools", False) else "❌"
            }
        }
        
        # Count navigation matches
        expected_nav = pr38_checks["expected_navigation"]["expected"]
        actual_nav = pr38_checks["expected_navigation"]["actual"]
        matches = 0
        for expected_item in expected_nav:
            for actual_item in actual_nav:
                if expected_item.lower() in actual_item.lower() or actual_item.lower() in expected_item.lower():
                    matches += 1
                    break
        
        pr38_checks["expected_navigation"]["matching_count"] = matches
        pr38_checks["expected_navigation"]["status"] = "✅" if matches >= 6 else "⚠️" if matches >= 3 else "❌"
        
        return pr38_checks
    
    def try_simple_screenshot(self) -> Optional[str]:
        """Try to take a screenshot using available tools"""
        screenshot_path = None
        
        # Try different screenshot methods
        methods = [
            # Method 1: wkhtmltopdf with image output (if available)
            lambda: self._try_wkhtmltoimage(),
            # Method 2: Headless Chrome (if available)
            lambda: self._try_chrome_screenshot(),
            # Method 3: Firefox screenshot (if available)
            lambda: self._try_firefox_screenshot(),
            # Method 4: Save HTML for manual inspection
            lambda: self._save_html_snapshot()
        ]
        
        for method in methods:
            try:
                result = method()
                if result:
                    screenshot_path = result
                    break
            except Exception as e:
                print(f"Screenshot method failed: {e}")
                continue
        
        return screenshot_path
    
    def _try_chrome_screenshot(self) -> Optional[str]:
        """Try screenshot with headless Chrome"""
        screenshot_path = self.screenshots_dir / "dashboard_chrome.png"
        
        cmd = [
            "google-chrome", "--headless", "--no-sandbox", "--disable-gpu",
            "--window-size=1920,1080", "--screenshot=" + str(screenshot_path),
            self.base_url
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and screenshot_path.exists():
                print(f"✅ Chrome screenshot saved: {screenshot_path}")
                return str(screenshot_path)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
            
        return None
    
    def _try_firefox_screenshot(self) -> Optional[str]:
        """Try screenshot with headless Firefox"""
        screenshot_path = self.screenshots_dir / "dashboard_firefox.png"
        
        cmd = [
            "firefox", "--headless", "--screenshot=" + str(screenshot_path),
            "--window-size=1920,1080", self.base_url
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and screenshot_path.exists():
                print(f"✅ Firefox screenshot saved: {screenshot_path}")
                return str(screenshot_path)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
            
        return None
    
    def _try_wkhtmltoimage(self) -> Optional[str]:
        """Try screenshot with wkhtmltoimage"""
        screenshot_path = self.screenshots_dir / "dashboard_wkhtml.png"
        
        cmd = [
            "wkhtmltoimage", "--width", "1920", "--height", "1080",
            "--format", "png", self.base_url, str(screenshot_path)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and screenshot_path.exists():
                print(f"✅ wkhtmltoimage screenshot saved: {screenshot_path}")
                return str(screenshot_path)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
            
        return None
    
    def _save_html_snapshot(self) -> Optional[str]:
        """Save HTML content for manual inspection"""
        html_path = self.screenshots_dir / "dashboard_snapshot.html"
        
        try:
            with urllib.request.urlopen(self.base_url, timeout=10) as response:
                html_content = response.read().decode('utf-8', errors='ignore')
                
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
            print(f"✅ HTML snapshot saved: {html_path}")
            return str(html_path)
        except Exception as e:
            print(f"❌ Failed to save HTML snapshot: {e}")
            
        return None
    
    def generate_comprehensive_report(self) -> str:
        """Generate a comprehensive dashboard analysis report"""
        print("=== DASHBOARD ANALYSIS REPORT ===")
        
        # Test accessibility
        access_test = self.test_dashboard_accessibility()
        
        report_lines = []
        report_lines.append("=== DASHBOARD ANALYSIS REPORT ===\n")
        
        # Accessibility
        if access_test["accessible"]:
            report_lines.append(f"✅ Dashboard Accessible: HTTP {access_test['response_code']}")
            report_lines.append(f"📄 Content Length: {access_test['content_length']} bytes")
        else:
            report_lines.append(f"❌ Dashboard Not Accessible: {access_test.get('error', 'Unknown error')}")
            return "\n".join(report_lines)
        
        # Analyze HTML content
        html_analysis = self.analyze_html_content(access_test.get("html_content", ""))
        
        # Basic info
        if html_analysis.get("title"):
            report_lines.append(f"📝 Page Title: {html_analysis['title']}")
        
        # PR #38 compatibility check
        pr38_check = self.compare_with_pr38_expectations(html_analysis)
        
        report_lines.append("\n🔍 PR #38 Compatibility Check:")
        for check_name, check_data in pr38_check.items():
            status = check_data["status"]
            if check_name == "expected_navigation":
                report_lines.append(f"   {status} Navigation Items: {check_data['matching_count']}/{len(check_data['expected'])} matches")
                if check_data["actual"]:
                    report_lines.append(f"       Found: {', '.join(check_data['actual'])}")
            else:
                check_display = check_name.replace("_", " ").title()
                report_lines.append(f"   {status} {check_display}: {check_data['actual']}")
        
        # Functionality analysis
        functionality = html_analysis.get("estimated_functionality", {})
        if functionality:
            report_lines.append("\n⚙️ Functionality Analysis:")
            for feature, present in functionality.items():
                status = "✅" if present else "❌"
                feature_name = feature.replace("_", " ").replace("has ", "").title()
                report_lines.append(f"   {status} {feature_name}")
        
        # Technical details
        report_lines.append(f"\n🔧 Technical Details:")
        report_lines.append(f"   Script Tags: {html_analysis.get('script_tags', 0)}")
        report_lines.append(f"   Style Tags: {html_analysis.get('style_tags', 0)}")
        
        if html_analysis.get("component_counts"):
            report_lines.append(f"   Component Counts Found: {html_analysis['component_counts']}")
        
        # Try to take screenshot
        report_lines.append(f"\n📸 Screenshot Attempt:")
        screenshot_path = self.try_simple_screenshot()
        if screenshot_path:
            report_lines.append(f"   ✅ Saved: {screenshot_path}")
        else:
            report_lines.append(f"   ❌ No screenshot tools available")
        
        # Save detailed results
        results_file = self.screenshots_dir / "analysis_results.json"
        detailed_results = {
            "accessibility_test": access_test,
            "html_analysis": html_analysis,
            "pr38_compatibility": pr38_check,
            "screenshot_path": screenshot_path,
            "timestamp": time.time()
        }
        
        # Remove HTML content from JSON to keep file manageable
        if "html_content" in detailed_results["accessibility_test"]:
            del detailed_results["accessibility_test"]["html_content"]
        
        with open(results_file, 'w') as f:
            json.dump(detailed_results, f, indent=2, default=str)
        
        report_lines.append(f"\n📊 Detailed results saved to: {results_file}")
        
        full_report = "\n".join(report_lines)
        print("\n" + full_report)
        return full_report

def main():
    """Main function"""
    analyzer = SimpleDashboardAnalyzer()
    report = analyzer.generate_comprehensive_report()
    return 0

if __name__ == "__main__":
    sys.exit(main())