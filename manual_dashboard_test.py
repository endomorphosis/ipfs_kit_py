#!/usr/bin/env python3
"""
Manual Dashboard Testing Script

Since Playwright installation is failing, this script creates a comprehensive
testing system using curl, manual HTML/CSS analysis, and browser inspection
to identify styling issues from PR #39 reorganization.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import requests
import time

class ManualDashboardTester:
    def __init__(self, url: str = "http://127.0.0.1:8004", output_dir: str = "screenshots"):
        self.url = url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def test_dashboard_accessibility(self):
        """Test if dashboard is accessible and responding"""
        print("🌐 Testing dashboard accessibility...")
        
        try:
            response = requests.get(self.url, timeout=10)
            print(f"   ✅ Dashboard accessible: HTTP {response.status_code}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Dashboard not accessible: {e}")
            return False

    def analyze_html_structure(self):
        """Analyze the HTML structure of the dashboard"""
        print("📄 Analyzing HTML structure...")
        
        try:
            response = requests.get(self.url, timeout=10)
            html = response.text
            
            # Save raw HTML
            html_file = self.output_dir / f"{self.timestamp}_dashboard.html"
            with open(html_file, 'w') as f:
                f.write(html)
            
            print(f"   📄 HTML saved: {html_file}")
            
            # Analyze structure
            analysis = {
                "title": self._extract_title(html),
                "has_loading_div": 'id="app"' in html and 'Loading' in html,
                "javascript_files": self._extract_js_files(html),
                "css_files": self._extract_css_files(html),
                "meta_viewport": 'name="viewport"' in html,
                "character_encoding": 'charset="utf-8"' in html
            }
            
            return analysis
            
        except Exception as e:
            print(f"   ❌ Error analyzing HTML: {e}")
            return {}

    def analyze_javascript_resources(self):
        """Analyze the JavaScript files that control the dashboard"""
        print("📜 Analyzing JavaScript resources...")
        
        results = {}
        
        # Check main JS files
        js_files = ["/mcp-client.js", "/app.js"]
        
        for js_file in js_files:
            try:
                js_url = f"{self.url}{js_file}"
                response = requests.get(js_url, timeout=10)
                
                if response.status_code == 200:
                    js_content = response.text
                    
                    # Save JS content
                    js_output_file = self.output_dir / f"{self.timestamp}_{js_file.replace('/', '_')}"
                    with open(js_output_file, 'w') as f:
                        f.write(js_content)
                    
                    # Analyze content
                    results[js_file] = {
                        "accessible": True,
                        "size": len(js_content),
                        "has_pr38_elements": self._check_pr38_elements(js_content),
                        "css_injection": "body{background:" in js_content,
                        "rocket_emoji": "🚀" in js_content,
                        "comprehensive_dashboard": "Comprehensive MCP Dashboard" in js_content,
                        "file_saved": str(js_output_file)
                    }
                    
                    print(f"   ✅ {js_file}: {len(js_content)} bytes")
                    if results[js_file]["rocket_emoji"]:
                        print(f"      🚀 Contains rocket emoji (PR #38 element)")
                    if results[js_file]["comprehensive_dashboard"]:
                        print(f"      📋 Contains 'Comprehensive MCP Dashboard' text")
                
                else:
                    results[js_file] = {"accessible": False, "status": response.status_code}
                    print(f"   ❌ {js_file}: HTTP {response.status_code}")
                    
            except Exception as e:
                results[js_file] = {"accessible": False, "error": str(e)}
                print(f"   ❌ {js_file}: {e}")
        
        return results

    def test_api_endpoints(self):
        """Test key API endpoints"""
        print("🔌 Testing API endpoints...")
        
        endpoints = [
            "/api/mcp/status",
            "/mcp/tools/list",
            "/api/health",
        ]
        
        results = {}
        
        for endpoint in endpoints:
            try:
                url = f"{self.url}{endpoint}"
                if endpoint == "/mcp/tools/list":
                    response = requests.post(url, timeout=10)
                else:
                    response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        results[endpoint] = {
                            "accessible": True,
                            "data": data,
                            "tools_count": len(data.get("tools", [])) if "tools" in data else None
                        }
                        print(f"   ✅ {endpoint}: OK")
                        if results[endpoint]["tools_count"]:
                            print(f"      🔧 {results[endpoint]['tools_count']} tools available")
                    except json.JSONDecodeError:
                        results[endpoint] = {"accessible": True, "data": "non-json", "content": response.text[:200]}
                        print(f"   ⚠️  {endpoint}: Non-JSON response")
                else:
                    results[endpoint] = {"accessible": False, "status": response.status_code}
                    print(f"   ❌ {endpoint}: HTTP {response.status_code}")
                    
            except Exception as e:
                results[endpoint] = {"accessible": False, "error": str(e)}
                print(f"   ❌ {endpoint}: {e}")
        
        return results

    def compare_with_pr38_expectations(self):
        """Compare current dashboard with PR #38 expectations"""
        print("📊 Comparing with PR #38 expectations...")
        
        # Expected elements from PR #38 screenshots
        pr38_expectations = {
            "header_text": "🚀 IPFS Kit",
            "subtitle_text": "Comprehensive MCP Dashboard", 
            "light_theme": True,
            "navigation_items": [
                "Overview", "Services", "Backends", "Pin Management",
                "Peer Management", "Logs", "Analytics", "Configuration"
            ],
            "no_vfs_browser": True,  # Should NOT have VFS Browser like deprecated dashboard
            "mcp_server_active_indicator": True
        }
        
        # Test current dashboard against expectations
        results = {}
        
        try:
            # Check if JS contains expected elements
            js_response = requests.get(f"{self.url}/app.js")
            if js_response.status_code == 200:
                js_content = js_response.text
                
                results["rocket_header"] = "🚀" in js_content
                results["comprehensive_title"] = "Comprehensive MCP Dashboard" in js_content  
                results["light_theme_css"] = "background:#f5f5f5" in js_content
                results["no_dark_theme"] = "dark" not in js_content.lower()
                
                # Check for navigation structure
                navigation_indicators = [
                    "Overview", "Services", "Backends", "Pin Management", 
                    "Analytics", "Configuration"
                ]
                results["navigation_elements"] = {}
                for nav_item in navigation_indicators:
                    results["navigation_elements"][nav_item] = nav_item in js_content
                
                # Check that it's NOT the deprecated VFS browser dashboard
                results["not_vfs_browser"] = "VFS Browser" not in js_content
                results["not_comprehensive_deprecated"] = "comprehensive_mcp_dashboard" not in js_content
                
            # Summary
            passed_checks = sum(1 for v in results.values() if (v is True or (isinstance(v, dict) and all(v.values()))))
            total_checks = len(results)
            
            print(f"   📋 PR #38 Compatibility: {passed_checks}/{total_checks} checks passed")
            
            for check, result in results.items():
                if isinstance(result, dict):
                    sub_passed = sum(1 for v in result.values() if v)
                    sub_total = len(result)
                    status = "✅" if sub_passed == sub_total else "⚠️" if sub_passed > 0 else "❌"
                    print(f"      {status} {check}: {sub_passed}/{sub_total}")
                else:
                    status = "✅" if result else "❌"
                    print(f"      {status} {check}")
            
        except Exception as e:
            print(f"   ❌ Error in comparison: {e}")
            results = {"error": str(e)}
        
        return results

    def check_file_reorganization_issues(self):
        """Check for issues caused by PR #39 file reorganization"""
        print("🔍 Checking for file reorganization issues...")
        
        issues = []
        
        # Check for missing resources (404s)
        test_resources = [
            "/static/css/dashboard.css",
            "/static/js/dashboard.js", 
            "/assets/css/style.css",
            "/css/main.css",
            "/js/main.js",
            "/favicon.ico"
        ]
        
        for resource in test_resources:
            try:
                response = requests.get(f"{self.url}{resource}", timeout=5)
                if response.status_code == 404:
                    issues.append(f"Missing resource: {resource} (404)")
                elif response.status_code != 200:
                    issues.append(f"Resource error: {resource} (HTTP {response.status_code})")
            except Exception:
                pass  # Expected for non-existent resources
        
        # Check if the current dashboard is using dynamic JS instead of static files
        try:
            html_response = requests.get(self.url)
            html = html_response.text
            
            if 'src="/app.js"' in html and 'src="/mcp-client.js"' in html:
                issues.append("Using dynamic JS generation instead of static files")
            
            if 'Loading…' in html:
                issues.append("Using JavaScript-only rendering (no fallback HTML)")
                
            if html.count('<script') < 2:
                issues.append("Very few JavaScript files - possible missing dependencies")
                
        except Exception as e:
            issues.append(f"Error checking reorganization: {e}")
        
        print(f"   📂 Found {len(issues)} potential reorganization issues:")
        for issue in issues:
            print(f"      ⚠️  {issue}")
        
        return issues

    def create_comprehensive_report(self):
        """Create a comprehensive diagnostic report"""
        print("📊 Creating comprehensive diagnostic report...")
        
        # Run all tests
        accessibility = self.test_dashboard_accessibility()
        if not accessibility:
            return None
        
        html_analysis = self.analyze_html_structure()
        js_analysis = self.analyze_javascript_resources()
        api_tests = self.test_api_endpoints()
        pr38_comparison = self.compare_with_pr38_expectations()
        reorganization_issues = self.check_file_reorganization_issues()
        
        # Create comprehensive report
        report = {
            "timestamp": self.timestamp,
            "dashboard_url": self.url,
            "accessibility": accessibility,
            "html_analysis": html_analysis,
            "javascript_analysis": js_analysis,
            "api_tests": api_tests,
            "pr38_comparison": pr38_comparison,
            "reorganization_issues": reorganization_issues,
            "summary": {
                "dashboard_accessible": accessibility,
                "has_pr38_styling": pr38_comparison.get("rocket_header", False) and pr38_comparison.get("comprehensive_title", False),
                "api_functional": any(test.get("accessible", False) for test in api_tests.values()),
                "reorganization_issues_count": len(reorganization_issues),
                "recommendation": self._generate_recommendation(pr38_comparison, reorganization_issues)
            }
        }
        
        # Save report
        report_file = self.output_dir / f"{self.timestamp}_dashboard_diagnostic_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 Report saved: {report_file}")
        
        # Print summary
        self.print_summary(report)
        
        return report_file

    def _extract_title(self, html):
        """Extract page title from HTML"""
        try:
            start = html.find('<title>') + 7
            end = html.find('</title>')
            return html[start:end] if start > 6 and end > start else "Unknown"
        except:
            return "Unknown"

    def _extract_js_files(self, html):
        """Extract JavaScript file references from HTML"""
        import re
        js_pattern = r'<script[^>]+src=["\']([^"\']+)["\']'
        return re.findall(js_pattern, html)

    def _extract_css_files(self, html):
        """Extract CSS file references from HTML"""
        import re
        css_pattern = r'<link[^>]+href=["\']([^"\']*\.css[^"\']*)["\']'
        return re.findall(css_pattern, html)

    def _check_pr38_elements(self, content):
        """Check if content contains PR #38 specific elements"""
        pr38_indicators = [
            "🚀", "Comprehensive MCP Dashboard", "MCP Server Active",
            "Overview", "Services", "Backends", "Pin Management"
        ]
        return {indicator: indicator in content for indicator in pr38_indicators}

    def _generate_recommendation(self, pr38_comparison, issues):
        """Generate a recommendation based on the analysis"""
        if pr38_comparison.get("rocket_header") and pr38_comparison.get("comprehensive_title"):
            if len(issues) == 0:
                return "Dashboard appears to be working correctly with PR #38 styling"
            else:
                return f"Dashboard has PR #38 styling but has {len(issues)} reorganization issues to address"
        else:
            return "Dashboard is missing key PR #38 elements - may be using wrong dashboard file"

    def print_summary(self, report):
        """Print a human-readable summary"""
        print("\n" + "="*60)
        print("📊 DASHBOARD DIAGNOSTIC SUMMARY")
        print("="*60)
        
        summary = report["summary"]
        print(f"🌐 Dashboard Accessible: {'✅' if summary['dashboard_accessible'] else '❌'}")
        print(f"🎨 PR #38 Styling: {'✅' if summary['has_pr38_styling'] else '❌'}")
        print(f"🔌 API Functional: {'✅' if summary['api_functional'] else '❌'}")
        print(f"📂 Reorganization Issues: {summary['reorganization_issues_count']}")
        
        print(f"\n💡 Recommendation: {summary['recommendation']}")
        
        # Show specific issues if any
        if report["reorganization_issues"]:
            print(f"\n⚠️  Issues to Address:")
            for issue in report["reorganization_issues"]:
                print(f"   • {issue}")
        
        print("="*60)

def main():
    tester = ManualDashboardTester()
    
    try:
        report_file = tester.create_comprehensive_report()
        if report_file:
            print(f"\n✅ Testing complete! Full report: {report_file}")
        else:
            print("\n❌ Testing failed - dashboard not accessible")
        return 0
    except Exception as e:
        print(f"❌ Testing failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())