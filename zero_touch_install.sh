#!/usr/bin/env bash

# Zero-touch installer for ipfs_kit_py
#
# Goals:
# - No sudo required by default
# - Detect OS/arch and install missing tooling locally into ./bin
# - Create ./.venv and install Python deps
# - Optionally install Node + Playwright deps for E2E

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${ROOT_DIR}/bin"
CACHE_DIR="${ROOT_DIR}/.cache"
VENV_DIR="${ROOT_DIR}/.venv"
LOCAL_DEPS_DIR="${BIN_DIR}/deps"

PROFILE="dev"            # core|api|dev|full
EXTRAS=""                # comma-separated extras override
INSTALL_NODE="auto"       # auto|yes|no
INSTALL_PLAYWRIGHT="auto" # auto|yes|no
INSTALL_LIBMAGIC="auto"   # auto|yes|no
ALLOW_UNSUPPORTED_PYTHON="0"

NODE_VERSION="20.11.1"   # LTS-ish; pinned for reproducibility
UV_VERSION="0.5.13"      # pinned; used only when Python>=3.12 not available

log() { printf "%s\n" "$*"; }
err() { printf "%s\n" "$*" >&2; }

usage() {
  cat <<'EOF'
Usage: ./zero_touch_install.sh [options]

Options:
  --profile <core|api|dev|full>   Install profile (default: dev)
  --extras <comma,separated>      Explicit extras to install (overrides --profile)
  --node <auto|yes|no>            Ensure Node.js is available (default: auto)
  --playwright <auto|yes|no>      Install Playwright deps + browsers (default: auto)
  --libmagic <auto|yes|no>        Build/install libmagic locally if needed (default: auto)
  --allow-unsupported-python      Proceed even if Python < 3.12 (best-effort)
  -h, --help                      Show this help

What it does (no sudo):
  - Creates ./bin, ./.cache, ./.venv
  - Ensures Python venv + pip deps for chosen profile
  - Optionally installs Node (downloaded to ./.cache, symlinked into ./bin)
  - Optionally installs Playwright (npm install + browsers into ./.cache)

Environment outputs:
  - Writes ./bin/env.sh that you can source to set PATH and library paths
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --profile) PROFILE="${2:-}"; shift 2 ;;
      --extras) EXTRAS="${2:-}"; shift 2 ;;
      --node) INSTALL_NODE="${2:-}"; shift 2 ;;
      --playwright) INSTALL_PLAYWRIGHT="${2:-}"; shift 2 ;;
      --libmagic) INSTALL_LIBMAGIC="${2:-}"; shift 2 ;;
      --allow-unsupported-python) ALLOW_UNSUPPORTED_PYTHON="1"; shift 1 ;;
      -h|--help) usage; exit 0 ;;
      *) err "Unknown option: $1"; usage; exit 2 ;;
    esac
  done

  case "$PROFILE" in
    core|api|dev|full) : ;;
    *) err "Invalid --profile: $PROFILE"; exit 2 ;;
  esac
  case "$INSTALL_NODE" in auto|yes|no) : ;; *) err "Invalid --node: $INSTALL_NODE"; exit 2 ;; esac
  case "$INSTALL_PLAYWRIGHT" in auto|yes|no) : ;; *) err "Invalid --playwright: $INSTALL_PLAYWRIGHT"; exit 2 ;; esac
  case "$INSTALL_LIBMAGIC" in auto|yes|no) : ;; *) err "Invalid --libmagic: $INSTALL_LIBMAGIC"; exit 2 ;; esac
}

ensure_dirs() {
  mkdir -p "$BIN_DIR" "$CACHE_DIR" "$LOCAL_DEPS_DIR"
}

detect_platform() {
  OS_RAW="$(uname -s)"
  ARCH_RAW="$(uname -m)"

  OS="$(echo "$OS_RAW" | tr '[:upper:]' '[:lower:]')"
  case "$OS" in
    linux*) OS="linux" ;;
    darwin*) OS="darwin" ;;
    *) err "Unsupported OS: $OS_RAW"; exit 1 ;;
  esac

  case "$ARCH_RAW" in
    x86_64|amd64) ARCH="x86_64"; NODE_ARCH="x64" ;;
    aarch64|arm64) ARCH="arm64"; NODE_ARCH="arm64" ;;
    *) err "Unsupported architecture: $ARCH_RAW"; exit 1 ;;
  esac

  log "Detected platform: OS=$OS ARCH=$ARCH (uname -m=$ARCH_RAW)"
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

sudo_available() {
  if have_cmd sudo && sudo -n true >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

python_version_ok() {
  # expects $1 as python executable
  local py="$1"
  "$py" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 12) else 1)
PY
}

pick_python() {
  if have_cmd python3.12 && python_version_ok python3.12; then
    PYTHON_EXE="python3.12"
    return 0
  fi
  if have_cmd python3 && python_version_ok python3; then
    PYTHON_EXE="python3"
    return 0
  fi
  if have_cmd python && python_version_ok python; then
    PYTHON_EXE="python"
    return 0
  fi

  # Allow non-3.12+ for best-effort if requested
  if [[ "$ALLOW_UNSUPPORTED_PYTHON" == "1" ]]; then
    if have_cmd python3; then PYTHON_EXE="python3"; return 0; fi
    if have_cmd python; then PYTHON_EXE="python"; return 0; fi
  fi

  return 1
}

download() {
  local url="$1"
  local out="$2"
  if have_cmd curl; then
    curl -fsSL "$url" -o "$out"
  elif have_cmd wget; then
    wget -q "$url" -O "$out"
  else
    err "Need curl or wget to download: $url"
    return 1
  fi
}

install_uv_local() {
  # Installs uv into ./bin/uv (used only for bootstrapping Python 3.12+ when missing)
  local uv_dir="${CACHE_DIR}/uv-${UV_VERSION}"
  local tarball="${uv_dir}/uv.tar.gz"

  mkdir -p "$uv_dir"

  local target=""
  if [[ "$OS" == "linux" && "$ARCH" == "x86_64" ]]; then
    target="x86_64-unknown-linux-gnu"
  elif [[ "$OS" == "linux" && "$ARCH" == "arm64" ]]; then
    target="aarch64-unknown-linux-gnu"
  elif [[ "$OS" == "darwin" && "$ARCH" == "x86_64" ]]; then
    target="x86_64-apple-darwin"
  elif [[ "$OS" == "darwin" && "$ARCH" == "arm64" ]]; then
    target="aarch64-apple-darwin"
  else
    err "uv bootstrap not supported for OS=$OS ARCH=$ARCH"
    return 1
  fi

  local url="https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-${target}.tar.gz"

  if [[ -x "${BIN_DIR}/uv" ]]; then
    return 0
  fi

  log "Installing uv locally (${UV_VERSION}) to bootstrap Python..."
  download "$url" "$tarball"
  tar -xzf "$tarball" -C "$uv_dir"

  # tar contains a single 'uv' binary
  if [[ -f "${uv_dir}/uv" ]]; then
    cp "${uv_dir}/uv" "${BIN_DIR}/uv"
    chmod +x "${BIN_DIR}/uv"
    return 0
  fi

  # Fallback: find uv within extracted dir
  local found
  found="$(find "$uv_dir" -maxdepth 3 -type f -name uv 2>/dev/null | head -n 1 || true)"
  if [[ -n "$found" ]]; then
    cp "$found" "${BIN_DIR}/uv"
    chmod +x "${BIN_DIR}/uv"
    return 0
  fi

  err "Failed to install uv"
  return 1
}

create_venv() {
  if [[ -d "$VENV_DIR" ]]; then
    log "Found existing .venv; reusing. (Delete $VENV_DIR to force rebuild)"
    return 0
  fi

  if pick_python; then
    log "Creating venv with: $PYTHON_EXE"
    "$PYTHON_EXE" -m venv "$VENV_DIR"
    return 0
  fi

  log "Python >= 3.12 not found; trying uv bootstrap (no sudo)..."
  install_uv_local

  if [[ ! -x "${BIN_DIR}/uv" ]]; then
    err "uv bootstrap failed, and no suitable Python found"
    err "Install Python 3.12+ or re-run with --allow-unsupported-python"
    exit 1
  fi

  export PATH="${BIN_DIR}:$PATH"
  "${BIN_DIR}/uv" python install 3.12 >/dev/null
  "${BIN_DIR}/uv" venv --python 3.12 "$VENV_DIR"
}

activate_venv() {
  # shellcheck disable=SC1090
  source "${VENV_DIR}/bin/activate"
  python -V
}

build_libmagic_local() {
  local prefix="${LOCAL_DEPS_DIR}/libmagic"

  if [[ -f "${prefix}/lib/libmagic.so" || -f "${prefix}/lib/libmagic.dylib" ]]; then
    log "libmagic already present at ${prefix}"
    return 0
  fi

  if ! have_cmd gcc || ! have_cmd make; then
    err "No gcc/make available to build libmagic locally; skipping"
    return 1
  fi

  local ver="5.45"
  local src_dir="${CACHE_DIR}/file-${ver}"
  local tarball="${CACHE_DIR}/file-${ver}.tar.gz"
  local url="https://astron.com/pub/file/file-${ver}.tar.gz"

  log "Building libmagic locally (file-${ver}) into ${prefix}..."
  download "$url" "$tarball"
  rm -rf "$src_dir"
  tar -xzf "$tarball" -C "$CACHE_DIR"

  pushd "$src_dir" >/dev/null
  ./configure --prefix="$prefix" >/dev/null
  make -j"$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)" >/dev/null
  make install >/dev/null
  popd >/dev/null
}

write_env_sh() {
  cat > "${BIN_DIR}/env.sh" <<EOF
# Source this to use locally installed tools
export PATH="${BIN_DIR}:\$PATH"

# Local native deps (best-effort)
if [ -d "${LOCAL_DEPS_DIR}/libmagic/lib" ]; then
  export LD_LIBRARY_PATH="${LOCAL_DEPS_DIR}/libmagic/lib:\${LD_LIBRARY_PATH:-}"
  export DYLD_LIBRARY_PATH="${LOCAL_DEPS_DIR}/libmagic/lib:\${DYLD_LIBRARY_PATH:-}"
fi

# Keep Playwright browser downloads local to the repo
export PLAYWRIGHT_BROWSERS_PATH="${CACHE_DIR}/ms-playwright"
EOF
}

install_python_deps() {
  activate_venv

  python -m pip install --upgrade pip setuptools wheel

  local spec=""
  if [[ -n "$EXTRAS" ]]; then
    spec=".[${EXTRAS}]"
  else
    case "$PROFILE" in
      core) spec="." ;;
      api) spec=".[api]" ;;
      dev) spec=".[dev,api]" ;;
      full) spec=".[full,dev,api]" ;;
    esac
  fi

  log "Installing Python package + deps: pip install -e '${spec}'"
  python -m pip install -e "${spec}"

  # Some parts of the repo still expect requirements.txt; install as a best-effort add-on
  # but avoid hard-failing the whole run when optional/heavy wheels are unavailable.
  if [[ -f "${ROOT_DIR}/requirements.txt" ]]; then
    log "Installing requirements.txt (best-effort; may skip some heavy deps on ARM)"
    set +e
    python -m pip install -r "${ROOT_DIR}/requirements.txt"
    local rc=$?
    set -e
    if [[ $rc -ne 0 ]]; then
      err "WARNING: requirements.txt install had failures. Core package install succeeded."
      err "If you want strict mode, run: .venv/bin/pip install -r requirements.txt"
    fi
  fi
}

ensure_node_local() {
  if have_cmd node && have_cmd npm; then
    return 0
  fi

  local dest="${CACHE_DIR}/node-v${NODE_VERSION}-${OS}-${NODE_ARCH}"
  local tarball="${CACHE_DIR}/node-v${NODE_VERSION}-${OS}-${NODE_ARCH}.tar.xz"
  local url="https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-${OS}-${NODE_ARCH}.tar.xz"

  log "Installing Node.js locally (v${NODE_VERSION})..."
  mkdir -p "$dest"

  if [[ ! -d "$dest/bin" ]]; then
    download "$url" "$tarball"
    tar -xJf "$tarball" -C "$CACHE_DIR"

    # Extracted folder name matches node-vX-OS-ARCH
    if [[ -d "${CACHE_DIR}/node-v${NODE_VERSION}-${OS}-${NODE_ARCH}" ]]; then
      :
    else
      err "Expected extracted Node directory not found"
      return 1
    fi

    # dest already points to extracted dir
    dest="${CACHE_DIR}/node-v${NODE_VERSION}-${OS}-${NODE_ARCH}"
  fi

  ln -sf "${dest}/bin/node" "${BIN_DIR}/node"
  ln -sf "${dest}/bin/npm" "${BIN_DIR}/npm"
  ln -sf "${dest}/bin/npx" "${BIN_DIR}/npx"
}

install_node_deps() {
  if [[ ! -f "${ROOT_DIR}/package.json" ]]; then
    return 0
  fi

  export PATH="${BIN_DIR}:$PATH"
  export npm_config_cache="${CACHE_DIR}/npm"

  local npm_cmd="npm"
  if [[ -f "${ROOT_DIR}/package-lock.json" ]]; then
    log "Installing Node deps via npm ci"
    (cd "$ROOT_DIR" && "$npm_cmd" ci --no-audit --no-fund)
  else
    log "Installing Node deps via npm install"
    (cd "$ROOT_DIR" && "$npm_cmd" install --no-audit --no-fund)
  fi
}

install_playwright_browsers() {
  export PATH="${BIN_DIR}:$PATH"
  export PLAYWRIGHT_BROWSERS_PATH="${CACHE_DIR}/ms-playwright"

  if [[ ! -f "${ROOT_DIR}/package.json" ]]; then
    err "No package.json found; cannot install Playwright"
    return 1
  fi

  # If sudo is available, Playwright can install OS deps; otherwise do browser-only.
  if sudo_available; then
    log "Installing Playwright browsers (+ system deps via sudo)"
    (cd "$ROOT_DIR" && npx playwright install --with-deps)
  else
    log "Installing Playwright browsers (no sudo; browser-only)"
    (cd "$ROOT_DIR" && npx playwright install)
  fi
}

main() {
  parse_args "$@"
  ensure_dirs
  detect_platform

  export PATH="${BIN_DIR}:$PATH"

  write_env_sh

  # Native deps: libmagic (needed by python-magic)
  local do_libmagic="$INSTALL_LIBMAGIC"
  if [[ "$do_libmagic" == "auto" ]]; then
    do_libmagic="yes"
  fi

  if [[ "$do_libmagic" == "yes" ]]; then
    set +e
    build_libmagic_local
    set -e

    if [[ -d "${LOCAL_DEPS_DIR}/libmagic/lib" ]]; then
      export LD_LIBRARY_PATH="${LOCAL_DEPS_DIR}/libmagic/lib:${LD_LIBRARY_PATH:-}"
      export DYLD_LIBRARY_PATH="${LOCAL_DEPS_DIR}/libmagic/lib:${DYLD_LIBRARY_PATH:-}"
    fi
  fi

  create_venv
  install_python_deps

  # Node/Playwright (optional)
  local do_node="$INSTALL_NODE"
  if [[ "$do_node" == "auto" ]]; then
    if [[ -f "${ROOT_DIR}/package.json" ]]; then do_node="yes"; else do_node="no"; fi
  fi
  if [[ "$do_node" == "yes" ]]; then
    ensure_node_local
    install_node_deps
  fi

  local do_pw="$INSTALL_PLAYWRIGHT"
  if [[ "$do_pw" == "auto" ]]; then
    if [[ -f "${ROOT_DIR}/package.json" ]]; then do_pw="yes"; else do_pw="no"; fi
  fi
  if [[ "$do_pw" == "yes" ]]; then
    install_playwright_browsers
  fi

  log ""
  log "✅ Zero-touch install complete"
  log "- Venv: ${VENV_DIR}"
  log "- Local tools: ${BIN_DIR}"
  log "- Source env:  source ${BIN_DIR}/env.sh"
}

main "$@"
