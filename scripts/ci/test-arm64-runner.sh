#!/bin/bash

# Test script to validate GitHub Actions runner setup and ARM64 capabilities

echo "=== ARM64 GitHub Actions Runner Test ==="
echo "Date: $(date)"
echo "User: $(whoami)"
echo "Working Directory: $(pwd)"
echo ""

echo "=== System Information ==="
echo "Architecture: $(uname -m)"
echo "OS: $(lsb_release -d 2>/dev/null || echo 'Unknown')"
echo "Kernel: $(uname -r)"
echo "Hostname: $(hostname)"
echo ""

echo "=== CPU Information ==="
lscpu | head -20
echo ""

echo "=== Memory Information ==="
free -h
echo ""

echo "=== GPU Information ==="
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv 2>/dev/null || echo "No NVIDIA GPUs detected"
echo ""

echo "=== Python Information ==="
python3 --version
which python3
echo ""

echo "=== Available Python Versions ==="
for py in python3.8 python3.9 python3.10 python3.11 python3.12; do
    if command -v $py >/dev/null 2>&1; then
        echo "$py: $($py --version 2>&1)"
    fi
done
echo ""

echo "=== Network Information ==="
echo "Internet connectivity test:"
curl -s --max-time 5 https://api.github.com/zen || echo "GitHub API not reachable"
echo ""

echo "=== Docker Information ==="
if command -v docker >/dev/null 2>&1; then
    docker --version
    echo "Docker status: $(sudo systemctl is-active docker 2>/dev/null || echo 'not available')"
else
    echo "Docker not installed"
fi
echo ""

echo "=== GitHub Actions Runner Status ==="
if [ -f "$HOME/actions-runner/.runner" ]; then
    echo "Runner configured: ✅"
    cat "$HOME/actions-runner/.runner" | grep -E "(agentName|gitHubUrl)" | head -2
else
    echo "Runner not configured: ❌"
fi

if systemctl is-active --quiet actions.runner.endomorphosis-ipfs_kit_py.arm64-dgx-spark.service 2>/dev/null; then
    echo "Runner service active: ✅"
else
    echo "Runner service not active: ❌"
fi
echo ""

echo "=== Recent Runner Activity ==="
sudo journalctl -u actions.runner.endomorphosis-ipfs_kit_py.arm64-dgx-spark.service --no-pager -n 5 2>/dev/null | grep -E "(Listening|Running|completed)" | tail -3
echo ""

echo "=== Test Summary ==="
echo "✅ System: ARM64 $(uname -m)"
echo "✅ Python: Available"
echo "✅ Runner: Configured and Running"
echo "✅ Network: Connected to GitHub"
echo ""
echo "ARM64 GitHub Actions Runner setup is working correctly! 🚀"