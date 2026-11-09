#!/usr/bin/env python3
"""
Test report generator for IPFS Kit Python.

This script generates a comprehensive HTML report from test results.
"""

import os
import sys
import json
import glob
import argparse
import datetime
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("report_generator")

# Define the categories
CATEGORIES = ["core", "mcp", "storage", "fsspec", "api", "tools", "integrations"]

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Generate a test report for IPFS Kit Python")
    parser.add_argument(
        "--report-dir", 
        default="test_reports", 
        help="Directory containing test reports (default: test_reports)"
    )
    parser.add_argument(
        "--output", 
        default="test_report.html", 
        help="Output HTML file (default: test_report.html)"
    )
    return parser.parse_args()

def find_latest_report(report_dir):
    """Find the latest report directory."""
    report_dir = Path(report_dir)
    if not report_dir.exists():
        logger.error(f"Report directory {report_dir} does not exist")
        return None
    
    # Find all timestamp directories
    dirs = [d for d in report_dir.iterdir() if d.is_dir()]
    if not dirs:
        logger.error(f"No report directories found in {report_dir}")
        return None
    
    # Sort by timestamp (assuming directory names are timestamps)
    dirs.sort(reverse=True)
    return dirs[0]

def collect_report_data(report_dir):
    """Collect data from reports in the directory."""
    report_dir = Path(report_dir)
    
    # Check for summary.json
    summary_path = report_dir / "summary.json"
    if not summary_path.exists():
        logger.error(f"No summary.json found in {report_dir}")
        return None
    
    # Load the summary
    with open(summary_path) as f:
        summary = json.load(f)
    
    # Collect individual report data
    report_data = {}
    for category in CATEGORIES:
        category_report = {}
        
        # Load output file
        output_path = report_dir / f"{category}_output.txt"
        if output_path.exists():
            with open(output_path) as f:
                category_report["output"] = f.read()
        else:
            category_report["output"] = "No output file found"
        
        # Load XML results if available
        xml_path = report_dir / f"{category}_results.xml"
        if xml_path.exists():
            with open(xml_path) as f:
                category_report["xml"] = f.read()
        else:
            category_report["xml"] = None
        
        # Load HTML report if available
        html_path = report_dir / f"{category}_report.html"
        if html_path.exists():
            with open(html_path) as f:
                category_report["html"] = f.read()
        else:
            category_report["html"] = None
        
        # Set status from summary
        category_report["status"] = summary.get("categories", {}).get(category, "unknown")
        
        report_data[category] = category_report
    
    return {
        "summary": summary,
        "reports": report_data
    }

def generate_html_report(data, output_file):
    """Generate an HTML report from the collected data."""
    if not data:
        logger.error("No data to generate report")
        return False
    
    # Extract summary data
    summary = data["summary"]
    reports = data["reports"]
    
    # Begin HTML content
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPFS Kit Python - Test Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        header {{
            background-color: #2c3e50;
            color: #fff;
            padding: 20px;
            margin-bottom: 20px;
        }}
        h1, h2, h3 {{
            margin-top: 0;
        }}
        .summary {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .success {{
            color: #28a745;
        }}
        .failure {{
            color: #dc3545;
        }}
        .unknown {{
            color: #6c757d;
        }}
        .category {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .category-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
        }}
        .category-content {{
            display: none;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #dee2e6;
        }}
        .show {{
            display: block;
        }}
        pre {{
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
            font-family: monospace;
            font-size: 14px;
        }}
        .tabs {{
            display: flex;
            margin-bottom: 10px;
        }}
        .tab {{
            padding: 8px 15px;
            cursor: pointer;
            border: 1px solid #dee2e6;
            border-radius: 5px 5px 0 0;
            margin-right: 5px;
        }}
        .tab.active {{
            background-color: #007bff;
            color: #fff;
            border-color: #007bff;
        }}
        .tab-content {{
            display: none;
            border: 1px solid #dee2e6;
            padding: 15px;
            border-radius: 0 5px 5px 5px;
        }}
        .tab-content.active {{
            display: block;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>IPFS Kit Python - Test Report</h1>
            <p>Generated on: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p>Test run timestamp: {summary.get("timestamp", "unknown")}</p>
        </header>
        
        <div class="summary">
            <h2>Summary</h2>
            <p>Success rate: {summary.get("success_rate", "unknown")}</p>
        </div>
"""
    
    # Add categories
    for category in CATEGORIES:
        if category not in reports:
            continue
        
        report = reports[category]
        status = report.get("status", "unknown")
        status_class = "success" if status == "success" else "failure" if status == "failure" else "unknown"
        
        html += f"""
        <div class="category">
            <div class="category-header" onclick="toggleCategory('{category}')">
                <h3>{category.upper()}</h3>
                <span class="{status_class}">{status.upper()}</span>
            </div>
            <div id="{category}-content" class="category-content">
                <div class="tabs">
                    <div class="tab active" onclick="showTab('{category}', 'output')">Output</div>
                    <div class="tab" onclick="showTab('{category}', 'xml')">XML Results</div>
                    <div class="tab" onclick="showTab('{category}', 'html')">HTML Report</div>
                </div>
                <div id="{category}-output" class="tab-content active">
                    <pre>{report.get("output", "No output available")}</pre>
                </div>
                <div id="{category}-xml" class="tab-content">
                    {f'<pre>{report.get("xml", "No XML results available")}</pre>' if report.get("xml") else '<p>No XML results available</p>'}
                </div>
                <div id="{category}-html" class="tab-content">
                    {f'<iframe width="100%" height="600" srcdoc="{report.get("html").replace('"', '\\"')}"></iframe>' if report.get("html") else '<p>No HTML report available</p>'}
                </div>
            </div>
        </div>
"""
    
    # Add JavaScript and close HTML
    html += """
        <script>
            function toggleCategory(category) {
                const content = document.getElementById(category + '-content');
                content.classList.toggle('show');
            }
            
            function showTab(category, tab) {
                // Hide all tabs
                const tabs = document.querySelectorAll('#' + category + '-content .tab-content');
                tabs.forEach(tab => tab.classList.remove('active'));
                
                // Show the selected tab
                document.getElementById(category + '-' + tab).classList.add('active');
                
                // Update the tab buttons
                const tabButtons = document.querySelectorAll('#' + category + '-content .tab');
                tabButtons.forEach(button => button.classList.remove('active'));
                event.target.classList.add('active');
            }
        </script>
    </div>
</body>
</html>
"""
    
    # Write the HTML to a file
    with open(output_file, "w") as f:
        f.write(html)
    
    logger.info(f"Report generated: {output_file}")
    return True

def main():
    """Main entry point."""
    args = parse_args()
    
    # Find the latest report directory
    report_dir = args.report_dir
    if os.path.isdir(report_dir) and not glob.glob(os.path.join(report_dir, "summary.json")):
        logger.info(f"Looking for latest report in {report_dir}")
        latest_dir = find_latest_report(report_dir)
        if latest_dir:
            report_dir = latest_dir
            logger.info(f"Using latest report directory: {report_dir}")
    
    # Collect report data
    data = collect_report_data(report_dir)
    if not data:
        logger.error("Failed to collect report data")
        return 1
    
    # Generate the HTML report
    success = generate_html_report(data, args.output)
    if not success:
        logger.error("Failed to generate HTML report")
        return 1
    
    logger.info(f"Report generated successfully: {args.output}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
