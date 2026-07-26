#!/bin/bash
# Setup virtual environment for the final MCP server

echo "🚀 Setting up Python virtual environment..."

# Remove existing venv if present
if [ -d ".venv" ]; then
    echo "Removing existing .venv directory..."
    rm -rf .venv
fi

# Create new virtual environment
echo "Creating virtual environment..."
python3 -m venv .venv

# Activate and install dependencies
echo "Activating virtual environment and installing dependencies..."
source .venv/bin/activate

# Upgrade pip first
pip install --upgrade pip

# Install core MCP dependencies
echo "Installing core MCP dependencies..."
pip install fastapi uvicorn python-multipart

# Install IPFS and async dependencies
echo "Installing IPFS and async dependencies..."
pip install requests aiohttp base58 multiaddr

# Install the local ipfs_kit_py package in development mode
echo "Installing local ipfs_kit_py package..."
pip install -e .

# Install additional dependencies from requirements.txt
echo "Installing additional dependencies..."
pip install -r requirements.txt

echo "✅ Virtual environment setup complete!"
echo "To activate: source .venv/bin/activate"
echo "To test server: .venv/bin/python final_mcp_server.py --help"
