#!/bin/bash
# Setup GitHub Actions Self-Hosted Runner for IPFS-Kit
# This script helps configure a self-hosted runner for building and testing Docker images

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}GitHub Actions Runner Setup for IPFS-Kit${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
  echo -e "${RED}ERROR: Do not run this script as root${NC}"
  echo "GitHub Actions runners should run as a regular user"
  exit 1
fi

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
  x86_64)
    RUNNER_ARCH="x64"
    LABEL_ARCH="amd64"
    ;;
  aarch64|arm64)
    RUNNER_ARCH="arm64"
    LABEL_ARCH="arm64"
    ;;
  *)
    echo -e "${RED}ERROR: Unsupported architecture: $ARCH${NC}"
    exit 1
    ;;
esac

echo -e "${GREEN}Detected architecture:${NC} $ARCH ($LABEL_ARCH)"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Docker
if ! command -v docker &> /dev/null; then
  echo -e "${RED}ERROR: Docker is not installed${NC}"
  echo "Please install Docker first: https://docs.docker.com/engine/install/"
  exit 1
fi
echo -e "${GREEN}✓${NC} Docker is installed"

# Check Docker permissions
if ! docker ps &> /dev/null; then
  echo -e "${YELLOW}⚠${NC}  Docker requires sudo or your user is not in the docker group"
  echo "Add your user to docker group with: sudo usermod -aG docker $USER"
  echo "Then log out and back in for changes to take effect"
fi

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
  echo -e "${YELLOW}⚠${NC}  GitHub CLI (gh) is not installed"
  echo "Install with: sudo apt install gh"
  echo "Or: sudo snap install gh"
  INSTALL_GH=1
else
  echo -e "${GREEN}✓${NC} GitHub CLI is installed"
  INSTALL_GH=0
fi

echo ""

# Runner directory
RUNNER_DIR="$HOME/actions-runner-${LABEL_ARCH}"
echo -e "${GREEN}Runner will be installed to:${NC} $RUNNER_DIR"
echo ""

# Check if runner already exists
if [ -d "$RUNNER_DIR" ]; then
  echo -e "${YELLOW}Runner directory already exists: $RUNNER_DIR${NC}"
  read -p "Do you want to remove it and reinstall? (y/N): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Stop the runner if it's running
    if [ -f "$RUNNER_DIR/svc.sh" ]; then
      echo "Stopping runner service..."
      cd "$RUNNER_DIR"
      sudo ./svc.sh stop || true
      sudo ./svc.sh uninstall || true
    fi
    rm -rf "$RUNNER_DIR"
  else
    echo "Exiting without changes"
    exit 0
  fi
fi

# Get latest runner version
echo -e "${YELLOW}Fetching latest runner version...${NC}"
RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | grep -oP '"tag_name": "v\K(.*)(?=")')
echo -e "${GREEN}Latest version:${NC} $RUNNER_VERSION"

# Download runner
RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz"
echo -e "${YELLOW}Downloading runner...${NC}"
echo "URL: $RUNNER_URL"

mkdir -p "$RUNNER_DIR"
cd "$RUNNER_DIR"

curl -o actions-runner-linux.tar.gz -L "$RUNNER_URL"
tar xzf actions-runner-linux.tar.gz
rm actions-runner-linux.tar.gz

echo -e "${GREEN}✓${NC} Runner downloaded and extracted"
echo ""

# Configuration instructions
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Next Steps:${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "1. Get a registration token from GitHub:"
echo "   ${YELLOW}https://github.com/endomorphosis/ipfs_kit_py/settings/actions/runners/new${NC}"
echo ""
echo "2. Configure the runner:"
echo "   ${YELLOW}cd $RUNNER_DIR${NC}"
echo "   ${YELLOW}./config.sh --url https://github.com/endomorphosis/ipfs_kit_py --token YOUR_TOKEN${NC}"
echo ""
echo "3. When prompted for labels, add: ${YELLOW}${LABEL_ARCH}${NC}"
echo ""
echo "4. Install as a service (recommended):"
echo "   ${YELLOW}cd $RUNNER_DIR${NC}"
echo "   ${YELLOW}sudo ./svc.sh install${NC}"
echo "   ${YELLOW}sudo ./svc.sh start${NC}"
echo ""
echo "5. Check status:"
echo "   ${YELLOW}sudo ./svc.sh status${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"
echo ""

# Offer to install GitHub CLI if needed
if [ $INSTALL_GH -eq 1 ]; then
  echo -e "${YELLOW}Would you like to install GitHub CLI now?${NC}"
  read -p "Install gh? (y/N): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v apt &> /dev/null; then
      sudo apt update
      sudo apt install -y gh
    elif command -v snap &> /dev/null; then
      sudo snap install gh
    else
      echo "Please install GitHub CLI manually from: https://cli.github.com/"
    fi
  fi
fi

# Create helper script for configuration
cat > "$RUNNER_DIR/configure-runner.sh" << 'EOF'
#!/bin/bash
# Helper script to configure the runner

echo "Please enter your GitHub Personal Access Token (PAT) with repo scope:"
echo "Create one at: https://github.com/settings/tokens"
read -s TOKEN
echo ""

# Get registration token
REG_TOKEN=$(curl -s -X POST \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/endomorphosis/ipfs_kit_py/actions/runners/registration-token \
  | grep -oP '"token": "\K(.*)(?=")')

if [ -z "$REG_TOKEN" ]; then
  echo "Failed to get registration token. Check your PAT."
  exit 1
fi

echo "Got registration token, configuring runner..."

ARCH=$(uname -m)
case $ARCH in
  x86_64) LABEL_ARCH="amd64" ;;
  aarch64|arm64) LABEL_ARCH="arm64" ;;
esac

./config.sh \
  --url https://github.com/endomorphosis/ipfs_kit_py \
  --token "$REG_TOKEN" \
  --labels "$LABEL_ARCH" \
  --name "$(hostname)-$LABEL_ARCH" \
  --work _work

echo ""
echo "Configuration complete! Install as service with:"
echo "  sudo ./svc.sh install"
echo "  sudo ./svc.sh start"
EOF

chmod +x "$RUNNER_DIR/configure-runner.sh"

echo -e "${GREEN}✓${NC} Created helper script: ${YELLOW}$RUNNER_DIR/configure-runner.sh${NC}"
echo ""
echo "You can run this script to automatically configure the runner with your GitHub token."
echo ""
echo -e "${GREEN}Setup complete!${NC}"
