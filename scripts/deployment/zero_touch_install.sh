#!/usr/bin/env bash

# Compatibility wrapper: keep older paths working.
# Prefer the repository root installer (creates ./.venv in the repo root).

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_DIR"

exec ./zero_touch_install.sh "$@"

usage() {
  cat <<'EOF'
Usage: ./zero_touch_install.sh [options]

Options:
  --profile <core|api|dev|full>   Install profile (default: dev)
  --extras <comma,separated>      Explicit extras to install (overrides --profile)
  --node <auto|yes|no>            Ensure Node.js is available (default: auto)
  --playwright <auto|yes|no>      Install Playwright deps + browsers (default: auto)
  --libmagic <auto|yes|no>        Build/install libmagic locally if needed (default: auto)
  --ipfs <auto|yes|no>            Install IPFS/Kubo binaries into ./bin (default: auto)
  --lassie <auto|yes|no>          Install Lassie binary into ./bin (default: auto)
  --lotus <auto|yes|no>           Install Lotus binaries into ./bin (default: auto)
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
      --ipfs) INSTALL_IPFS="${2:-}"; shift 2 ;;
      --lassie) INSTALL_LASSIE="${2:-}"; shift 2 ;;
      --lotus) INSTALL_LOTUS="${2:-}"; shift 2 ;;
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
  case "$INSTALL_IPFS" in auto|yes|no) : ;; *) err "Invalid --ipfs: $INSTALL_IPFS"; exit 2 ;; esac
  case "$INSTALL_LASSIE" in auto|yes|no) : ;; *) err "Invalid --lassie: $INSTALL_LASSIE"; exit 2 ;; esac
  case "$INSTALL_LOTUS" in auto|yes|no) : ;; *) err "Invalid --lotus: $INSTALL_LOTUS"; exit 2 ;; esac
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
    if [[ -f "${VENV_DIR}/bin/activate" ]]; then
      log "Found existing .venv; reusing. (Delete $VENV_DIR to force rebuild)"
      return 0
    fi
    log "Found existing .venv without activation script; rebuilding"
    rm -rf "$VENV_DIR"
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

# Some installers (e.g., Lotus user-space deps) place runtime libs in ./bin/lib
if [ -d "${BIN_DIR}/lib" ]; then
  export LD_LIBRARY_PATH="${BIN_DIR}/lib:\${LD_LIBRARY_PATH:-}"
  export DYLD_LIBRARY_PATH="${BIN_DIR}/lib:\${DYLD_LIBRARY_PATH:-}"
fi

# OpenCL ICD vendor search path (when present)
if [ -d "${BIN_DIR}/opencl/vendors" ]; then
  export OCL_ICD_VENDORS="${BIN_DIR}/opencl/vendors"
fi

# Keep Playwright browser downloads local to the repo
export PLAYWRIGHT_BROWSERS_PATH="${CACHE_DIR}/ms-playwright"
EOF
}

install_python_deps() {
  activate_venv

  python -m pip install --upgrade pip setuptools wheel

  # Clean up partial installs from interrupted runs
  python - <<'PY'
import sys
from pathlib import Path

site_paths = [Path(p) for p in sys.path if p and 'site-packages' in p]
for site in site_paths:
    for path in site.glob('~pfs-kit-py*'):
        try:
            if path.is_dir():
                for child in path.rglob('*'):
                    if child.is_file() or child.is_symlink():
                        child.unlink(missing_ok=True)
                path.rmdir()
            else:
                path.unlink(missing_ok=True)
        except Exception:
            pass
PY

  local spec=""
  local repo_url="https://github.com/endomorphosis/ipfs_kit_py.git"
  local repo_ref="known_good"
  local clone_dir="${CACHE_DIR}/ipfs_kit_py_known_good"

  if [[ ! -d "${clone_dir}/.git" ]]; then
    log "Cloning ipfs_kit_py from ${repo_url} (${repo_ref})..."
    GIT_TERMINAL_PROMPT=0 GIT_PROGRESS=0 \
      git -c core.progress=false clone --filter=blob:none --no-checkout --quiet "${repo_url}" "${clone_dir}" || {
        rm -rf "${clone_dir}"
        err "Clone failed; cleaned cache directory."
        exit 1
      }
  fi

  if ! git -C "${clone_dir}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    rm -rf "${clone_dir}"
    err "Invalid clone cache; removed ${clone_dir}."
    exit 1
  fi

  git -C "${clone_dir}" config submodule.recurse false
  GIT_TERMINAL_PROMPT=0 GIT_PROGRESS=0 git -c core.progress=false -C "${clone_dir}" fetch --depth 1 origin "${repo_ref}"
  git -C "${clone_dir}" checkout -f "${repo_ref}"
  if [[ -n "$EXTRAS" ]]; then
    spec="${clone_dir}[${EXTRAS}]"
  else
    case "$PROFILE" in
      core) spec="${clone_dir}" ;;
      api) spec="${clone_dir}[api]" ;;
      dev) spec="${clone_dir}[dev,api]" ;;
      full) spec="${clone_dir}[full,dev,api]" ;;
    esac
  fi

  log "Installing Python package + deps from ${repo_url}@${repo_ref}: pip install '${spec}'"
  python -m pip install "${spec}"

  log "Installing libp2p from git main"
  python -m pip install "libp2p @ git+https://github.com/libp2p/py-libp2p@main"

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

  log "Installing test dependencies (pytest-anyio, pytest-asyncio, pytest-cov)"
  python -m pip install --upgrade pytest pytest-anyio pytest-asyncio pytest-cov
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
    set +e
    (cd "$ROOT_DIR" && npx playwright install --with-deps)
    local rc=$?
    set -e
    if [[ $rc -ne 0 ]]; then
      err "WARNING: Playwright --with-deps failed (likely system package manager issues)."
      err "Retrying browser-only install..."
      (cd "$ROOT_DIR" && npx playwright install)
    fi
  else
    log "Installing Playwright browsers (no sudo; browser-only)"
    (cd "$ROOT_DIR" && npx playwright install)
  fi
}

install_native_tools() {
  # Assumes venv already exists; re-activate to ensure we're using venv python.
  activate_venv >/dev/null

  local do_ipfs="$INSTALL_IPFS"
  local do_lassie="$INSTALL_LASSIE"
  local do_lotus="$INSTALL_LOTUS"

  if [[ "$do_ipfs" == "auto" ]]; then
    if [[ "$PROFILE" == "full" ]]; then do_ipfs="yes"; else do_ipfs="no"; fi
  fi
  if [[ "$do_lassie" == "auto" ]]; then
    if [[ "$PROFILE" == "full" ]]; then do_lassie="yes"; else do_lassie="no"; fi
  fi
  if [[ "$do_lotus" == "auto" ]]; then
    if [[ "$PROFILE" == "full" ]]; then do_lotus="yes"; else do_lotus="no"; fi
  fi

  if [[ "$do_ipfs" == "yes" ]]; then
    log "Installing IPFS/Kubo binaries into ./bin (no sudo)"
    python - <<PY
from ipfs_kit_py.install_ipfs import install_ipfs

inst = install_ipfs(metadata={"bin_dir": r"${BIN_DIR}"})
inst.install_ipfs_daemon()

# Cluster helper binaries are useful, but avoid systemd/service setup in zero-touch.
try:
    inst.install_ipfs_cluster_ctl()
except Exception as e:
    print(f"WARNING: ipfs-cluster-ctl install failed: {e}")
try:
    inst.install_ipfs_cluster_follow()
except Exception as e:
    print(f"WARNING: ipfs-cluster-follow install failed: {e}")
PY
  fi

  if [[ "$do_lassie" == "yes" ]]; then
    log "Installing Lassie into ./bin (no sudo)"
    python - <<PY
from ipfs_kit_py.install_lassie import install_lassie

inst = install_lassie(metadata={"bin_dir": r"${BIN_DIR}"})
inst.install_lassie_daemon()
PY
  fi

  if [[ "$do_lotus" == "yes" ]]; then
    log "Installing Lotus into ./bin (best-effort; may use sudo if available)"
    python - <<PY
try:
    import glob as _glob
    import ipfs_kit_py.install_lotus as _lotus_mod
    _lotus_mod.glob = _glob
    from ipfs_kit_py.install_lotus import install_lotus

    inst = install_lotus(metadata={
        "bin_dir": r"${BIN_DIR}",
        # Opt in: will use sudo when available, otherwise attempt user-space deps.
        "auto_install_deps": True,
        "allow_userspace_deps": True,
        "skip_params": True,
    })
    inst.install_lotus_daemon()
except Exception as e:
    print(f"WARNING: Lotus install failed: {e}")
PY
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

  # Native daemons/CLIs (optional)
  install_native_tools

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
