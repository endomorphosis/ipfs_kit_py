#!/bin/bash

# Example: ARM64 Installation with Full Monitoring
# This script demonstrates how to use the monitoring tools during ARM64 installation

set -e

echo "=================================="
echo "ARM64 Installation Monitoring Demo"
echo "=================================="
echo ""

# Step 1: Initialize monitoring directories
echo "Step 1: Initializing monitoring directories..."
mkdir -p /tmp/arm64_monitor
mkdir -p /tmp/arm64_install_logs
echo "✅ Directories created"
echo ""

# Step 2: Run pre-installation verification
echo "Step 2: Running pre-installation dependency verification..."
python3 scripts/ci/verify_arm64_dependencies.py || echo "⚠️ Some dependencies missing (expected on fresh system)"
echo ""

# Step 3: Demonstrate installation wrapper
echo "Step 3: Testing installation wrapper..."
./scripts/ci/installation_wrapper.sh demo_test \
    bash -c "echo 'Installing dependencies...' && sleep 1 && echo 'Installation complete'"
echo ""

# Step 4: Run monitoring script
echo "Step 4: Running ARM64 installation monitor..."
python3 scripts/ci/monitor_arm64_installation.py
echo ""

# Step 5: Display generated reports
echo "Step 5: Displaying generated artifacts..."
echo ""
echo "📊 Monitoring Report:"
if [ -f /tmp/arm64_monitor/arm64_monitor_report.md ]; then
    echo "   Location: /tmp/arm64_monitor/arm64_monitor_report.md"
    echo "   Preview:"
    head -20 /tmp/arm64_monitor/arm64_monitor_report.md
    echo "   ..."
else
    echo "   ⚠️ Report not generated"
fi
echo ""

echo "📊 Metrics JSON:"
if [ -f /tmp/arm64_monitor/arm64_monitor_metrics.json ]; then
    echo "   Location: /tmp/arm64_monitor/arm64_monitor_metrics.json"
    echo "   Size: $(wc -c < /tmp/arm64_monitor/arm64_monitor_metrics.json) bytes"
else
    echo "   ⚠️ Metrics not generated"
fi
echo ""

echo "📊 Installation Logs:"
if [ -d /tmp/arm64_install_logs ]; then
    echo "   Directory: /tmp/arm64_install_logs"
    echo "   Files:"
    ls -lh /tmp/arm64_install_logs/ | tail -n +2
else
    echo "   ⚠️ No logs found"
fi
echo ""

# Step 6: Summary
echo "=================================="
echo "Monitoring Demo Complete"
echo "=================================="
echo ""
echo "Key Files Generated:"
echo "  - /tmp/arm64_monitor/arm64_monitor_report.md"
echo "  - /tmp/arm64_monitor/arm64_monitor_metrics.json"
echo "  - /tmp/arm64_install_logs/*_combined.log"
echo "  - /tmp/arm64_install_logs/*_metrics.json"
echo ""
echo "For GitHub Actions integration:"
echo "  1. Use these scripts in your workflow"
echo "  2. Upload artifacts with actions/upload-artifact@v3"
echo "  3. Check \$GITHUB_STEP_SUMMARY for inline reports"
echo ""
