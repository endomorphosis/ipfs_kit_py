#!/usr/bin/env bash
set -euo pipefail

# Auto-update script for ipfs_kit_py
# - ensures repo is on `known_good` branch and up-to-date
# - installs python requirements and editable package
# - restarts the systemd service

REPO_DIR="${REPO_DIR:-/home/barberb/ipfs_kit_py}"
SERVICE_NAME="${SERVICE_NAME:-ipfs-kit-mcp.service}"
BRANCH="${BRANCH:-known_good}"
PYTHON="${PYTHON:-/home/barberb/miniforge3/bin/python}"
PIP="$PYTHON -m pip"
LOG_DIR="${LOG_DIR:-$REPO_DIR/logs}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/auto_update.log}"

mkdir -p "$LOG_DIR"
exec >> "$LOG_FILE" 2>&1

echo "----- $(date -u +'%Y-%m-%dT%H:%M:%SZ') Auto-update run starting -----"

# If running as root, switch to the unprivileged user for git/pip operations
if [ "$(id -u)" -eq 0 ]; then
  # When running as root, perform git/pip operations as the unprivileged user to
  # preserve file ownership. Allow overriding the username with SUDO_USER_VAR.
  RUN_AS_USER="${SUDO_USER_VAR:-barberb}"
  SUDO_PREFIX=(sudo -u "$RUN_AS_USER" -H)
else
  SUDO_PREFIX=()
fi

# Ensure git operations are performed from repo dir
cd "$REPO_DIR"

if [ "${SKIP_GIT:-0}" = "1" ]; then
  echo "SKIP_GIT=1 set; skipping git fetch/checkout/pull"
else
  echo "Fetching origin..."
  "${SUDO_PREFIX[@]}" git fetch origin --prune

  # Checkout or create branch tracking origin/known_good
  if "${SUDO_PREFIX[@]}" git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
    echo "Checking out $BRANCH"
    "${SUDO_PREFIX[@]}" git checkout "$BRANCH"
  else
    echo "Creating local branch $BRANCH tracking origin/$BRANCH"
    "${SUDO_PREFIX[@]}" git checkout -b "$BRANCH" --track "origin/$BRANCH" || {
      echo "Failed to create local branch $BRANCH; aborting"
      exit 1
    }
  fi

  echo "Pulling latest from origin/$BRANCH"
  "${SUDO_PREFIX[@]}" git pull --ff-only origin "$BRANCH" || {
    echo "Fast-forward pull failed, aborting to avoid merge commits"
    exit 1
  }
fi

# Install package (editable) with extras so deployments are zero-touch
# and do not miss optional runtime dependencies.
if [ -f "$REPO_DIR/pyproject.toml" ] || [ -f "$REPO_DIR/setup.py" ]; then
  echo "Installing package (editable) with extras: [full]"
  if [ "${SKIP_PIP:-0}" = "1" ]; then
    echo "SKIP_PIP=1 set; skipping package install"
  else
    "${SUDO_PREFIX[@]}" $PIP install --upgrade -U pip setuptools wheel
    "${SUDO_PREFIX[@]}" $PIP install --upgrade -e "$REPO_DIR[full]"
  fi
else
  echo "No setup.py or pyproject.toml found; skipping package install"
fi

# Optionally run any migrations or setup hooks here
# echo "Running deploy hooks..."

# Restart the service
echo "Restarting systemd service: $SERVICE_NAME"
if [ "${SKIP_SYSTEMCTL:-0}" = "1" ]; then
  echo "SKIP_SYSTEMCTL=1 set; skipping systemctl operations"
else
  if systemctl is-enabled --quiet "$SERVICE_NAME"; then
    systemctl restart "$SERVICE_NAME"
    systemctl status "$SERVICE_NAME" --no-pager
  else
    echo "Service $SERVICE_NAME is not enabled; attempting to start"
    systemctl start "$SERVICE_NAME"
    systemctl status "$SERVICE_NAME" --no-pager
  fi
fi

echo "----- $(date -u +'%Y-%m-%dT%H:%M:%SZ') Auto-update run finished -----"
