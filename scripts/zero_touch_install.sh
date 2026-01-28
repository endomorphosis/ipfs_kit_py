#!/usr/bin/env bash
set -euo pipefail

# Zero-touch installer for ipfs_kit_py
# - Creates/uses a local venv (.venv)
# - Installs the package with a complete dependency set via pyproject extras
# - Runs a quick import smoke test

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$REPO_DIR/.venv}"
EXTRAS="${IPFS_KIT_EXTRAS:-full}"
BINARIES="${IPFS_KIT_ZERO_TOUCH_BINARIES:-full}"

cd "$REPO_DIR"

choose_python() {
  # Prefer the active python (e.g., actions/setup-python) when present.
  if command -v python >/dev/null 2>&1; then
    echo python
  elif command -v python3.12 >/dev/null 2>&1; then
    echo python3.12
  elif command -v python3 >/dev/null 2>&1; then
    echo python3
  else
    echo ""
  fi
}

PYTHON_BIN="$(choose_python)"
if [ -z "$PYTHON_BIN" ]; then
  echo "ERROR: python3 is required but was not found in PATH" >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtualenv at $VENV_DIR using $PYTHON_BIN"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

# Persist venv for subsequent CI steps (GitHub Actions).
if [ -n "${GITHUB_PATH:-}" ]; then
  echo "$VENV_DIR/bin" >> "$GITHUB_PATH"
fi

python -m pip install --upgrade pip setuptools wheel

PACKAGE_REF="ipfs_kit_py"
REPO_URL="git+https://github.com/endomorphosis/ipfs_kit_py@known_good"
if [ -n "$EXTRAS" ]; then
  echo "Installing ipfs_kit_py from ${REPO_URL} with extras: [$EXTRAS]"
  python -m pip install "${PACKAGE_REF}[${EXTRAS}] @ ${REPO_URL}"
else
  echo "Installing ipfs_kit_py from ${REPO_URL} (no extras)"
  python -m pip install "${PACKAGE_REF} @ ${REPO_URL}"
fi

echo "Installing libp2p from git main"
python -m pip install "libp2p @ git+https://github.com/libp2p/py-libp2p@main"

# Test tooling: expected to be available after zero-touch.
# Opt out with: IPFS_KIT_INSTALL_TEST_DEPS=0
INSTALL_TEST_DEPS="${IPFS_KIT_INSTALL_TEST_DEPS:-1}"
if [ "$INSTALL_TEST_DEPS" != "0" ]; then
  python -m pip install --upgrade pytest pytest-anyio pytest-cov
fi

python - <<'PY'
import importlib

# Core import
import ipfs_kit_py
print("✅ ipfs_kit_py import ok")

# Optional: libp2p import (only fails if extras weren't installed)
try:
    importlib.import_module("libp2p")
    print("✅ libp2p import ok")
except Exception as e:
    print(f"⚠️  libp2p import not available ({e})")
PY

# Install external binaries via the shared zero-touch Python entry.
# Lotus system deps are opt-in; in CI/root contexts we auto-enable to keep the
# pathway truly "zero touch" for pipelines.
if [ -z "${IPFS_KIT_AUTO_INSTALL_LOTUS_DEPS:-}" ]; then
  if [ "${CI:-}" = "true" ] || [ "${GITHUB_ACTIONS:-}" = "true" ] || [ "$(id -u 2>/dev/null || echo 9999)" = "0" ]; then
    export IPFS_KIT_AUTO_INSTALL_LOTUS_DEPS=1
  fi
fi

echo "Installing external binaries (Kubo/IPFS Cluster/Lassie/Lotus) via zero-touch installers..."
OS_NAME="$(uname -s 2>/dev/null || echo unknown)"
if [ "$BINARIES" = "full" ] && [ "$(id -u 2>/dev/null || echo 9999)" != "0" ] && [ -z "${IPFS_KIT_AUTO_INSTALL_LOTUS_DEPS:-}" ]; then
  if [ "$OS_NAME" = "Linux" ] || [ "$OS_NAME" = "Darwin" ]; then
    echo "NOTE: Lotus is included in 'full' installs on $OS_NAME." >&2
    echo "      If Lotus system deps are missing, the installer will fail." >&2
    echo "      Fix by installing the listed packages manually, or rerun with IPFS_KIT_AUTO_INSTALL_LOTUS_DEPS=1 (requires sudo)." >&2
    echo "      To skip Lotus: set IPFS_KIT_ZERO_TOUCH_BINARIES=core" >&2
  fi
fi

python -m ipfs_kit_py.zero_touch --binaries "$BINARIES"

# Persist installed binaries for subsequent CI steps (GitHub Actions).
if [ -n "${GITHUB_PATH:-}" ]; then
  echo "$REPO_DIR/ipfs_kit_py/bin" >> "$GITHUB_PATH"
fi

echo "Done. To activate later: source $VENV_DIR/bin/activate"