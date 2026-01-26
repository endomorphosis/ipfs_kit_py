#!/usr/bin/env bash

# Compatibility wrapper: prefer the repository zero-touch installer.
# This keeps all platform/arch detection and local (no-sudo) fallbacks in one place.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# Activate and install dependencies
echo "Activating virtual environment and installing dependencies..."
source .venv/bin/activate

# Upgrade pip first
python -m pip install --upgrade pip setuptools wheel

# Install the local package with a complete, maintained dependency set
# (includes MCP/API deps + py-libp2p tracking upstream main via extras)
echo "Installing ipfs_kit_py with recommended extras..."
python -m pip install -e ".[full]"

echo "✅ Virtual environment setup complete!"
echo "To activate: source .venv/bin/activate"
echo "To test server: .venv/bin/python final_mcp_server.py --help"
exec ./zero_touch_install.sh --profile dev --node no --playwright no "$@"
