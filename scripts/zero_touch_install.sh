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
CACHE_DIR="${REPO_DIR}/.cache"

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
REPO_URL="https://github.com/endomorphosis/ipfs_kit_py.git"
REPO_REF="known_good"
CLONE_DIR="${CACHE_DIR}/ipfs_kit_py_known_good"

mkdir -p "${CACHE_DIR}"
if [ ! -d "${CLONE_DIR}/.git" ]; then
  echo "Cloning ipfs_kit_py from ${REPO_URL} (${REPO_REF})..."
  GIT_TERMINAL_PROMPT=0 GIT_PROGRESS=0 \
    git -c core.progress=false clone --filter=blob:none --no-checkout --quiet "${REPO_URL}" "${CLONE_DIR}" || {
      rm -rf "${CLONE_DIR}"
      echo "Clone failed; cleaned cache directory." >&2
      exit 1
    }
fi

if ! git -C "${CLONE_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  rm -rf "${CLONE_DIR}"
  echo "Invalid clone cache; removed ${CLONE_DIR}." >&2
  exit 1
fi

git -C "${CLONE_DIR}" config submodule.recurse false
GIT_TERMINAL_PROMPT=0 GIT_PROGRESS=0 git -c core.progress=false -C "${CLONE_DIR}" fetch --depth 1 origin "${REPO_REF}"
git -C "${CLONE_DIR}" checkout -f "${REPO_REF}"

if [ -n "$EXTRAS" ]; then
  echo "Installing ipfs_kit_py from ${REPO_URL}@${REPO_REF} with extras: [$EXTRAS]"
  python -m pip install "${CLONE_DIR}[${EXTRAS}]"
else
  echo "Installing ipfs_kit_py from ${REPO_URL}@${REPO_REF} (no extras)"
  python -m pip install "${CLONE_DIR}"
fi

echo "Installing libp2p from git main"
python -m pip install "libp2p @ git+https://github.com/libp2p/py-libp2p@main"

# Test tooling: expected to be available after zero-touch.
# Opt out with: IPFS_KIT_INSTALL_TEST_DEPS=0
INSTALL_TEST_DEPS="${IPFS_KIT_INSTALL_TEST_DEPS:-1}"
if [ "$INSTALL_TEST_DEPS" != "0" ]; then
  python -m pip install --upgrade pytest pytest-anyio pytest-asyncio pytest-cov
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