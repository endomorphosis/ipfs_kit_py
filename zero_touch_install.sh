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
IPFS_REPO_DIR="${CACHE_DIR}/ipfs-repo"

PROFILE="dev"            # core|api|dev|full
EXTRAS=""                # comma-separated extras override
INSTALL_SOURCE="github-main"   # local|github-main
INSTALL_NODE="auto"       # auto|yes|no
INSTALL_PLAYWRIGHT="auto" # auto|yes|no
ALLOW_SUDO="no"           # yes|no (default: no; zero-touch should not require sudo)
INSTALL_LIBMAGIC="auto"   # auto|yes|no
INSTALL_IPFS="auto"       # auto|yes|no
INSTALL_LASSIE="auto"     # auto|yes|no
INSTALL_LOTUS="auto"      # auto|yes|no
INSTALL_GO="auto"         # auto|yes|no (install Go into ./bin for source-build fallbacks)
INSTALL_JQ="auto"         # auto|yes|no (install jq into ./bin; useful for Lotus/source builds)
INSTALL_IPLD="auto"       # auto|yes|no (install vendored IPLD python pkgs from ./docs)
ALLOW_UNSUPPORTED_PYTHON="0"
ALLOW_UNSUPPORTED_PLATFORM="1"  # proceed with Python-only best-effort when OS/arch unsupported

NODE_VERSION="20.11.1"   # LTS-ish; pinned for reproducibility
UV_VERSION="0.5.13"      # pinned; used only when Python>=3.12 not available
GO_VERSION="1.24.1"      # pinned; used for source-build fallbacks (Lotus/Lassie/Kubo)
JQ_VERSION="1.7.1"       # pinned; tiny but commonly assumed by build/deploy scripts

log() { printf "%s\n" "$*"; }
err() { printf "%s\n" "$*" >&2; }

usage() {
  cat <<'EOF'
Usage: ./zero_touch_install.sh [options]

Options:
  --profile <core|api|dev|full>   Install profile (default: dev)
  --extras <comma,separated>      Explicit extras to install (overrides --profile)
  --source <local|github-main>    Install ipfs_kit_py from local checkout or endomorphosis/ipfs_kit_py@main (default: github-main)
  --node <auto|yes|no>            Ensure Node.js is available (default: auto)
  --playwright <auto|yes|no>      Install Playwright deps + browsers (default: auto)
  --sudo <yes|no>                 Allow using sudo for system deps (default: no)
  --strict-platform               Fail fast on unsupported OS/arch (default: best-effort)
  --libmagic <auto|yes|no>        Build/install libmagic locally if needed (default: auto)
  --ipfs <auto|yes|no>            Install IPFS/Kubo binaries into ./bin (default: auto)
  --lassie <auto|yes|no>          Install Lassie binary into ./bin (default: auto)
  --lotus <auto|yes|no>           Install Lotus binaries into ./bin (default: auto)
  --go <auto|yes|no>              Install Go toolchain into ./bin (default: auto)
  --jq <auto|yes|no>              Install jq into ./bin (default: auto)
  --ipld <auto|yes|no>            Install vendored IPLD python pkgs from ./docs (default: auto)
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
      --source) INSTALL_SOURCE="${2:-}"; shift 2 ;;
      --node) INSTALL_NODE="${2:-}"; shift 2 ;;
      --playwright) INSTALL_PLAYWRIGHT="${2:-}"; shift 2 ;;
      --sudo) ALLOW_SUDO="${2:-}"; shift 2 ;;
      --strict-platform) ALLOW_UNSUPPORTED_PLATFORM="0"; shift 1 ;;
      --libmagic) INSTALL_LIBMAGIC="${2:-}"; shift 2 ;;
      --ipfs) INSTALL_IPFS="${2:-}"; shift 2 ;;
      --lassie) INSTALL_LASSIE="${2:-}"; shift 2 ;;
      --lotus) INSTALL_LOTUS="${2:-}"; shift 2 ;;
      --go) INSTALL_GO="${2:-}"; shift 2 ;;
      --jq) INSTALL_JQ="${2:-}"; shift 2 ;;
      --ipld) INSTALL_IPLD="${2:-}"; shift 2 ;;
      --allow-unsupported-python) ALLOW_UNSUPPORTED_PYTHON="1"; shift 1 ;;
      -h|--help) usage; exit 0 ;;
      *) err "Unknown option: $1"; usage; exit 2 ;;
    esac
  done

  case "$PROFILE" in
    core|api|dev|full) : ;;
    *) err "Invalid --profile: $PROFILE"; exit 2 ;;
  esac
  case "$INSTALL_SOURCE" in local|github-main) : ;; *) err "Invalid --source: $INSTALL_SOURCE"; exit 2 ;; esac
  case "$INSTALL_NODE" in auto|yes|no) : ;; *) err "Invalid --node: $INSTALL_NODE"; exit 2 ;; esac
  case "$INSTALL_PLAYWRIGHT" in auto|yes|no) : ;; *) err "Invalid --playwright: $INSTALL_PLAYWRIGHT"; exit 2 ;; esac
  case "$ALLOW_SUDO" in yes|no) : ;; *) err "Invalid --sudo: $ALLOW_SUDO"; exit 2 ;; esac
  case "$INSTALL_LIBMAGIC" in auto|yes|no) : ;; *) err "Invalid --libmagic: $INSTALL_LIBMAGIC"; exit 2 ;; esac
  case "$INSTALL_IPFS" in auto|yes|no) : ;; *) err "Invalid --ipfs: $INSTALL_IPFS"; exit 2 ;; esac
  case "$INSTALL_LASSIE" in auto|yes|no) : ;; *) err "Invalid --lassie: $INSTALL_LASSIE"; exit 2 ;; esac
  case "$INSTALL_LOTUS" in auto|yes|no) : ;; *) err "Invalid --lotus: $INSTALL_LOTUS"; exit 2 ;; esac
  case "$INSTALL_GO" in auto|yes|no) : ;; *) err "Invalid --go: $INSTALL_GO"; exit 2 ;; esac
  case "$INSTALL_JQ" in auto|yes|no) : ;; *) err "Invalid --jq: $INSTALL_JQ"; exit 2 ;; esac
  case "$INSTALL_IPLD" in auto|yes|no) : ;; *) err "Invalid --ipld: $INSTALL_IPLD"; exit 2 ;; esac
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
    *)
      if [[ "${ALLOW_UNSUPPORTED_PLATFORM}" == "1" ]]; then
        err "WARNING: Unsupported OS: ${OS_RAW}. Proceeding with Python-only best-effort."
        OS="${OS}"
      else
        err "Unsupported OS: $OS_RAW"; exit 1
      fi
      ;;
  esac

  case "$ARCH_RAW" in
    x86_64|amd64) ARCH="x86_64"; NODE_ARCH="x64" ;;
    aarch64|arm64) ARCH="arm64"; NODE_ARCH="arm64" ;;
    armv7l|armv7|armv6l|armv6) ARCH="arm"; NODE_ARCH="armv7l" ;;
    i386|i686|x86) ARCH="x86"; NODE_ARCH="x86" ;;
    *)
      if [[ "${ALLOW_UNSUPPORTED_PLATFORM}" == "1" ]]; then
        err "WARNING: Unsupported architecture: ${ARCH_RAW}. Proceeding with Python-only best-effort."
        ARCH="${ARCH_RAW}"
        NODE_ARCH=""
      else
        err "Unsupported architecture: $ARCH_RAW"; exit 1
      fi
      ;;
  esac

  # Extra Linux diagnostics for better portability.
  DISTRO_ID=""
  DISTRO_VERSION_ID=""
  if [[ "$OS" == "linux" && -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release || true
    DISTRO_ID="${ID:-}"
    DISTRO_VERSION_ID="${VERSION_ID:-}"
  fi

  LIBC="gnu"
  if [[ "$OS" == "linux" ]]; then
    if have_cmd ldd; then
      if ldd --version 2>&1 | head -n 1 | grep -qi musl; then
        LIBC="musl"
      fi
    fi
  fi

  WSL="0"
  if [[ "$OS" == "linux" && -r /proc/version ]]; then
    if grep -qi microsoft /proc/version 2>/dev/null; then
      WSL="1"
    fi
  fi

  local extra=""
  if [[ "$WSL" == "1" ]]; then
    extra=" WSL=1"
  fi

  if [[ "$LIBC" == "musl" ]]; then
    err "WARNING: musl libc detected. Prebuilt binaries may not run; source-build fallbacks may be required."
  fi

  if [[ -n "${DISTRO_ID}" ]]; then
    log "Detected platform: OS=$OS ARCH=$ARCH LIBC=$LIBC DISTRO=${DISTRO_ID}-${DISTRO_VERSION_ID}${extra} (uname -m=$ARCH_RAW)"
  else
    log "Detected platform: OS=$OS ARCH=$ARCH LIBC=$LIBC${extra} (uname -m=$ARCH_RAW)"
  fi

  PLATFORM_TAG="${OS}-${ARCH}-${LIBC}"
}

supports_kubo() {
  case "$OS" in
    linux)
      case "$ARCH" in x86_64|arm64|arm|x86) return 0 ;; *) return 1 ;; esac
      ;;
    darwin)
      case "$ARCH" in x86_64|arm64) return 0 ;; *) return 1 ;; esac
      ;;
    *) return 1 ;;
  esac
}

supports_lassie() {
  case "$OS" in
    linux)
      case "$ARCH" in x86_64|arm64) return 0 ;; *) return 1 ;; esac
      ;;
    darwin)
      case "$ARCH" in x86_64|arm64) return 0 ;; *) return 1 ;; esac
      ;;
    *) return 1 ;;
  esac
}

supports_lotus() {
  case "$OS" in
    linux)
      case "$ARCH" in x86_64|arm64) return 0 ;; *) return 1 ;; esac
      ;;
    darwin)
      case "$ARCH" in x86_64|arm64) return 0 ;; *) return 1 ;; esac
      ;;
    *) return 1 ;;
  esac
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

python_for_helpers() {
  if have_cmd python3; then
    echo python3
    return 0
  fi
  if have_cmd python; then
    echo python
    return 0
  fi
  return 1
}

extract_tar_gz() {
  local tarball="$1"
  local out_dir="$2"
  mkdir -p "$out_dir"
  if have_cmd tar; then
    tar -xzf "$tarball" -C "$out_dir" && return 0
  fi
  local py
  py="$(python_for_helpers)" || { err "Need tar or python to extract: $tarball"; return 1; }
  "$py" - <<PY
import sys, tarfile
tarball, out_dir = sys.argv[1], sys.argv[2]
with tarfile.open(tarball, mode="r:gz") as tf:
    tf.extractall(out_dir)
PY
  return 0
}

extract_tar_xz() {
  local tarball="$1"
  local out_dir="$2"
  mkdir -p "$out_dir"
  if have_cmd tar; then
    tar -xJf "$tarball" -C "$out_dir" && return 0
  fi
  local py
  py="$(python_for_helpers)" || { err "Need tar or python to extract: $tarball"; return 1; }
  "$py" - <<PY
import sys, tarfile
tarball, out_dir = sys.argv[1], sys.argv[2]
with tarfile.open(tarball, mode="r:xz") as tf:
    tf.extractall(out_dir)
PY
  return 0
}

sudo_available() {
  if [[ "${ALLOW_SUDO}" != "yes" ]]; then
    return 1
  fi
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
  elif have_cmd python3; then
    python3 -c 'import sys,urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])' "$url" "$out"
  elif have_cmd python; then
    python -c 'import sys,urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])' "$url" "$out"
  else
    err "Need curl/wget or python to download: $url"
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
    if [[ "${LIBC}" == "musl" ]]; then target="x86_64-unknown-linux-musl"; else target="x86_64-unknown-linux-gnu"; fi
  elif [[ "$OS" == "linux" && "$ARCH" == "arm64" ]]; then
    if [[ "${LIBC}" == "musl" ]]; then target="aarch64-unknown-linux-musl"; else target="aarch64-unknown-linux-gnu"; fi
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
  extract_tar_gz "$tarball" "$uv_dir"

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

# Prefer the project-local virtualenv when present.
# This ensures python/pytest resolve to ./.venv and see all installed deps.
if [ -d "${VENV_DIR}/bin" ]; then
  export VIRTUAL_ENV="${VENV_DIR}"
  export PATH="${VENV_DIR}/bin:${BIN_DIR}:\$PATH"
else
  export PATH="${BIN_DIR}:\$PATH"
fi

# Vendored IPLD python packages (pure python, shipped in ./docs).
# This avoids needing git/network/build backends for ipld_unixfs in minimal environments.
if [ -d "${ROOT_DIR}/docs/py-ipld-car" ]; then
  export PYTHONPATH="${ROOT_DIR}/docs/py-ipld-car:\${PYTHONPATH:-}"
fi
if [ -d "${ROOT_DIR}/docs/py-ipld-dag-pb" ]; then
  export PYTHONPATH="${ROOT_DIR}/docs/py-ipld-dag-pb:\${PYTHONPATH:-}"
fi
if [ -d "${ROOT_DIR}/docs/py-ipld-unixfs" ]; then
  export PYTHONPATH="${ROOT_DIR}/docs/py-ipld-unixfs:\${PYTHONPATH:-}"
fi

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

# Keep IPFS repo project-local (avoid mutating ~/.ipfs)
export IPFS_PATH="${IPFS_REPO_DIR}"

# Go toolchain (when installed locally by zero-touch)
if [ -x "${BIN_DIR}/go" ]; then
  export GOPATH="${CACHE_DIR}/go-path"
  export GOMODCACHE="${CACHE_DIR}/go-path/pkg/mod"
  export GOCACHE="${CACHE_DIR}/go-build-cache"
fi
# Platform metadata (used by installer helpers)
export IPFS_KIT_PLATFORM_OS="${OS}"
export IPFS_KIT_PLATFORM_ARCH="${ARCH}"
export IPFS_KIT_PLATFORM_LIBC="${LIBC}"
export IPFS_KIT_PLATFORM_TAG="${PLATFORM_TAG}"
EOF
}

ensure_go_local() {
  if have_cmd go; then
    return 0
  fi

  local go_os="$OS"
  local go_arch=""
  case "$ARCH" in
    x86_64) go_arch="amd64" ;;
    arm64) go_arch="arm64" ;;
    arm) go_arch="armv6l" ;;
    *)
      err "WARNING: Go auto-install unsupported on this architecture (${ARCH_RAW}); skipping"
      return 0
      ;;
  esac

  case "$go_os" in
    linux|darwin) : ;;
    *)
      err "WARNING: Go auto-install unsupported on this OS (${OS_RAW}); skipping"
      return 0
      ;;
  esac

  local dest="${CACHE_DIR}/go-${GO_VERSION}-${go_os}-${go_arch}"
  local tarball="${CACHE_DIR}/go${GO_VERSION}.${go_os}-${go_arch}.tar.gz"
  local url="https://go.dev/dl/go${GO_VERSION}.${go_os}-${go_arch}.tar.gz"

  if [[ ! -x "${dest}/go/bin/go" ]]; then
    log "Installing Go locally (go${GO_VERSION})..."
    mkdir -p "$dest"
    download "$url" "$tarball"
    rm -rf "${dest}/go"
    extract_tar_gz "$tarball" "$dest"
  fi

  if [[ -x "${dest}/go/bin/go" ]]; then
    ln -sf "${dest}/go/bin/go" "${BIN_DIR}/go"
    ln -sf "${dest}/go/bin/gofmt" "${BIN_DIR}/gofmt" || true
  else
    err "WARNING: Go install did not produce expected binary; skipping"
  fi
}

warn_missing_toolchain_for_source_builds() {
  # We can't reliably build a full C toolchain without sudo; surface actionable warnings early.
  local missing=0
  for cmd in git make gcc pkg-config; do
    if ! have_cmd "$cmd"; then
      err "WARNING: Missing '$cmd' on PATH. Some source-build fallbacks may not work without it."
      missing=1
    fi
  done
  return $missing
}

ensure_jq_local() {
  if have_cmd jq; then
    return 0
  fi

  local jq_os=""
  local jq_arch=""

  case "$OS" in
    linux) jq_os="linux" ;;
    darwin) jq_os="macos" ;;
    *)
      err "WARNING: jq auto-install unsupported on this OS (${OS_RAW}); skipping"
      return 0
      ;;
  esac

  case "$ARCH" in
    x86_64) jq_arch="amd64" ;;
    arm64) jq_arch="arm64" ;;
    *)
      err "WARNING: jq auto-install unsupported on this architecture (${ARCH_RAW}); skipping"
      return 0
      ;;
  esac

  local url="https://github.com/jqlang/jq/releases/download/jq-${JQ_VERSION}/jq-${jq_os}-${jq_arch}"
  local tmp="${CACHE_DIR}/jq-${JQ_VERSION}-${jq_os}-${jq_arch}"

  log "Installing jq locally (jq-${JQ_VERSION})..."
  set +e
  download "$url" "$tmp"
  local dl_rc=$?
  set -e
  if [[ $dl_rc -ne 0 ]]; then
    err "WARNING: jq download failed (${url}); continuing"
    return 0
  fi

  cp "$tmp" "${BIN_DIR}/jq"
  chmod +x "${BIN_DIR}/jq"

  if ! "${BIN_DIR}/jq" --version >/dev/null 2>&1; then
    err "WARNING: Installed jq does not appear runnable; removing and continuing"
    rm -f "${BIN_DIR}/jq"
  fi
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
      # dev profile should include datasets integration so more tests run out of the box
      dev) spec=".[dev,api,ipfs_datasets]" ;;
      # full profile: enable datasets + accelerate integrations (heavy; opt-out via --extras)
      full) spec=".[full,dev,api,ipfs_datasets,ipfs_accelerate]" ;;
    esac
  fi

  # Choose install source: GitHub main (default) or local editable checkout.
  local pinned_source_cmd=""
  if [[ "${INSTALL_SOURCE}" == "github-main" ]]; then
    local pkg="ipfs_kit_py"
    # Use the GitHub branch zip archive to avoid VCS/submodule issues during install.
    local url="https://github.com/endomorphosis/ipfs_kit_py/archive/refs/heads/main.zip"

    # pip supports extras with direct URL requirements: "name[extra] @ <url>"
    local direct="${pkg}"
    if [[ -n "${EXTRAS}" ]]; then
      direct="${pkg}[${EXTRAS}]"
    else
      # Map profile -> extras for GitHub install.
      case "$PROFILE" in
        core) direct="${pkg}" ;;
        api) direct="${pkg}[api]" ;;
        dev) direct="${pkg}[dev,api,ipfs_datasets]" ;;
        full) direct="${pkg}[full,dev,api,ipfs_datasets,ipfs_accelerate]" ;;
      esac
    fi

    log "Installing ipfs_kit_py from GitHub main: pip install '${direct} @ ${url}'"
    python -m pip install "${direct} @ ${url}"
    pinned_source_cmd="python -m pip install '${direct} @ ${url}'"
  else
    log "Installing Python package + deps from local checkout: pip install -e '${spec}'"
    python -m pip install -e "${spec}"
    pinned_source_cmd="python -m pip install -e '${spec}'"
  fi

  # Ensure WASM runtime is present for dev/full test coverage.
  # Some environments can end up with stale editable metadata where newly-added
  # optional deps don't get pulled in on re-run; this keeps zero-touch resilient.
  if [[ "${PROFILE}" == "dev" || "${PROFILE}" == "full" || "${EXTRAS}" == *"dev"* ]]; then
    python -c 'import wasmtime' >/dev/null 2>&1 || pip_install_best_effort "wasmtime" "wasmtime"

    # Optional test dependencies: keep best-effort so ARM/minimal envs don't fail.
    python -c 'import rdflib' >/dev/null 2>&1 || pip_install_best_effort "rdflib" "rdflib"
    python -c 'import matplotlib' >/dev/null 2>&1 || pip_install_best_effort "matplotlib" "matplotlib"
  fi

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

    # Guardrail: re-assert the chosen source after requirements.txt (in case any future
    # requirements accidentally reference ipfs_kit_py and override it).
    if [[ -n "${pinned_source_cmd}" ]]; then
      set +e
      eval "${pinned_source_cmd}" >/dev/null 2>&1
      set -e
    fi
  fi
}

install_vendored_ipld_packages() {
  # Make vendored IPLD packages available via env.sh (PYTHONPATH).
  # Avoid PEP517 installs here to keep zero-touch resilient in offline/minimal environments.
  local any_present=0
  for p in "${ROOT_DIR}/docs/py-ipld-car" "${ROOT_DIR}/docs/py-ipld-dag-pb" "${ROOT_DIR}/docs/py-ipld-unixfs"; do
    if [[ -d "$p" ]]; then any_present=1; fi
  done
  if [[ $any_present -eq 1 ]]; then
    log "Enabled vendored IPLD packages via PYTHONPATH in ./bin/env.sh"
  else
    err "WARNING: Vendored IPLD packages not found under ./docs; skipping"
  fi
}

pip_install_best_effort() {
  local spec="$1"
  local label="$2"
  set +e
  python -m pip install "${spec}"
  local rc=$?
  set -e
  if [[ $rc -ne 0 ]]; then
    err "WARNING: Optional ${label} install failed; continuing"
    return 1
  fi
  return 0
}

github_main_url() {
  # Usage: github_main_url <owner> <repo>
  # Prefer VCS installs when git is available; otherwise fall back to a branch zip.
  local owner="$1"
  local repo="$2"
  if have_cmd git; then
    echo "git+https://github.com/${owner}/${repo}.git@main"
  else
    echo "https://github.com/${owner}/${repo}/archive/refs/heads/main.zip"
  fi
}

pip_install_from_github_main_best_effort() {
  # Usage: pip_install_from_github_main_best_effort <pip_name> <owner> <repo>
  local pip_name="$1"
  local owner="$2"
  local repo="$3"

  local vcs_url="git+https://github.com/${owner}/${repo}.git@main"
  local zip_url="https://github.com/${owner}/${repo}/archive/refs/heads/main.zip"

  if have_cmd git; then
    if pip_install_best_effort "${pip_name} @ ${vcs_url}" "${pip_name} (@main, git)"; then
      return 0
    fi
    err "WARNING: Optional ${pip_name} VCS install failed; retrying via GitHub zip archive"
  fi

  pip_install_best_effort "${pip_name} @ ${zip_url}" "${pip_name} (@main, zip)" || true
  return 0
}

ensure_optional_python_deps() {
  activate_venv

  local want_datasets="no"
  local want_accelerate="no"
  local want_ipld_unixfs="no"
  local want_cbor2="no"
  local want_wasmtime="no"

  if [[ -n "${EXTRAS}" ]]; then
    if [[ ",${EXTRAS}," == *",ipfs_datasets,"* ]]; then
      want_datasets="yes"
    fi
    if [[ ",${EXTRAS}," == *",ipfs_accelerate,"* ]]; then
      want_accelerate="yes"
    fi
    if [[ ",${EXTRAS}," == *",ipld-github,"* ]]; then
      want_ipld_unixfs="yes"
    fi
  else
    case "$PROFILE" in
      dev|full)
        want_datasets="yes"
        want_ipld_unixfs="yes"
        want_cbor2="yes"
        want_wasmtime="yes"
        ;;
    esac
  fi

  if [[ "${want_cbor2}" == "yes" ]]; then
    if ! python - <<'PY' >/dev/null 2>&1
try:
    import cbor2  # noqa: F401
except Exception:
    raise SystemExit(1)
PY
    then
      err "Optional dependency missing: cbor2. Attempting install."
      pip_install_best_effort "cbor2" "cbor2"
    fi
  fi

  if [[ "${want_wasmtime}" == "yes" ]]; then
    if ! python - <<'PY' >/dev/null 2>&1
try:
    import wasmtime  # noqa: F401
except Exception:
    raise SystemExit(1)
PY
    then
      err "Optional dependency missing: wasmtime. Attempting install."
      pip_install_best_effort "wasmtime" "wasmtime"
    fi
  fi

  if [[ "${want_datasets}" == "yes" ]]; then
    local datasets_freeze
    datasets_freeze="$(python -m pip freeze 2>/dev/null | grep -E '^ipfs_datasets_py(==| @ )' | head -n 1 || true)"

    local need_datasets_install="0"
    if [[ -z "${datasets_freeze}" ]]; then
      need_datasets_install="1"
    fi

    # Also treat import failures as a reason to reinstall.
    if ! python - <<'PY' >/dev/null 2>&1
try:
    import ipfs_datasets_py  # noqa: F401
except Exception:
    raise SystemExit(1)
PY
    then
      need_datasets_install="1"
    fi

    if [[ "${need_datasets_install}" == "1" ]]; then
      if [[ "${IPFS_KIT_USE_DATASETS_GITHUB_MAIN:-0}" == "1" ]]; then
        log "Ensuring ipfs_datasets_py is installed from endomorphosis/ipfs_datasets_py@main"
        pip_install_from_github_main_best_effort "ipfs_datasets_py" "endomorphosis" "ipfs_datasets_py"
      else
        log "Ensuring ipfs_datasets_py is installed from PyPI"
        pip_install_best_effort "ipfs_datasets_py" "ipfs_datasets_py"
      fi
    fi
  fi

  if [[ "${want_accelerate}" == "yes" ]]; then
    local accel_freeze
    accel_freeze="$(python -m pip freeze 2>/dev/null | grep -E '^ipfs_accelerate_py(==| @ )' | head -n 1 || true)"

    local need_accel_install="0"
    if [[ -z "${accel_freeze}" ]]; then
      need_accel_install="1"
    elif [[ "${accel_freeze}" != *"github.com/endomorphosis/ipfs_accelerate_py"* ]]; then
      need_accel_install="1"
    fi

    if ! python - <<'PY' >/dev/null 2>&1
try:
    import ipfs_accelerate_py  # noqa: F401
except Exception:
    raise SystemExit(1)
PY
    then
      need_accel_install="1"
    fi

    if [[ "${need_accel_install}" == "1" ]]; then
      log "Ensuring ipfs_accelerate_py is installed from endomorphosis/ipfs_accelerate_py@main"
      pip_install_from_github_main_best_effort "ipfs_accelerate_py" "endomorphosis" "ipfs_accelerate_py"
    fi
  fi

  if [[ "${want_ipld_unixfs}" == "yes" ]]; then
    if ! python - <<'PY' >/dev/null 2>&1
try:
    import ipld_unixfs  # noqa: F401
except Exception:
    raise SystemExit(1)
PY
    then
      err "Optional dependency missing: ipld_unixfs. Attempting GitHub zip install."
      pip_install_best_effort \
        "ipld-unixfs @ https://github.com/storacha/py-ipld-unixfs/archive/refs/heads/main.zip" \
        "ipld_unixfs"
    fi
  fi
}

ensure_node_local() {
  if have_cmd node && have_cmd npm; then
    return 0
  fi

  if [[ "$OS" == "linux" && "${LIBC}" == "musl" ]]; then
    err "WARNING: Detected musl libc; official Node.js tarballs may not run."
    err "If you have system node/npm, prefer: --node no"
  fi

  if [[ -z "${NODE_ARCH}" ]]; then
    err "WARNING: Node.js auto-install unsupported on this architecture (${ARCH_RAW}); skipping"
    return 0
  fi

  local dest="${CACHE_DIR}/node-v${NODE_VERSION}-${OS}-${NODE_ARCH}"
  local tarball="${CACHE_DIR}/node-v${NODE_VERSION}-${OS}-${NODE_ARCH}.tar.xz"
  local url="https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-${OS}-${NODE_ARCH}.tar.xz"

  log "Installing Node.js locally (v${NODE_VERSION})..."
  mkdir -p "$dest"

  if [[ ! -d "$dest/bin" ]]; then
    set +e
    download "$url" "$tarball"
    local dl_rc=$?
    set -e
    if [[ $dl_rc -ne 0 ]]; then
      err "WARNING: Node.js download failed for ${OS}/${NODE_ARCH}."
      err "If you already have node/npm, put them on PATH and rerun with --node no."
      return 0
    fi

    set +e
    extract_tar_xz "$tarball" "$CACHE_DIR"
    local tar_rc=$?
    set -e
    if [[ $tar_rc -ne 0 ]]; then
      err "WARNING: Node.js extraction failed; skipping"
      return 0
    fi

    # Extracted folder name matches node-vX-OS-ARCH
    if [[ -d "${CACHE_DIR}/node-v${NODE_VERSION}-${OS}-${NODE_ARCH}" ]]; then
      :
    else
      err "WARNING: Expected extracted Node directory not found; skipping"
      return 0
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

  # Zero-touch should not attempt to install OS deps (apt/yum/brew) via sudo.
  # Make this step best-effort so system package manager issues don't break install.
  log "Installing Playwright browsers (browser-only; no sudo)"
  set +e
  (cd "$ROOT_DIR" && npx playwright install)
  local rc=$?
  set -e
  if [[ $rc -ne 0 ]]; then
    err "WARNING: Playwright browser install failed."
    err "Retry later with: (cd $ROOT_DIR && npx playwright install)"
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

  # Go is only needed for source-build fallbacks. Auto-install it when Lotus is
  # requested and Go isn't already available.
  local do_go="$INSTALL_GO"
  if [[ "$do_go" == "auto" ]]; then
    if [[ "$do_lotus" == "yes" ]]; then do_go="yes"; else do_go="no"; fi
  fi
  if [[ "$do_go" == "yes" ]]; then
    set +e
    ensure_go_local
    set -e
  fi

  # jq is a small utility often assumed by deployment/source-build scripts.
  local do_jq="$INSTALL_JQ"
  if [[ "$do_jq" == "auto" ]]; then
    if [[ "$do_lotus" == "yes" || "$PROFILE" == "full" ]]; then do_jq="yes"; else do_jq="no"; fi
  fi
  if [[ "$do_jq" == "yes" ]]; then
    set +e
    ensure_jq_local
    set -e
  fi

  if [[ "$do_ipfs" == "yes" ]]; then
    if ! supports_kubo; then
      err "WARNING: Kubo/IPFS binaries not available for OS=$OS ARCH=$ARCH; skipping"
    else
      log "Installing IPFS/Kubo binaries into ./bin (no sudo)"
      mkdir -p "${IPFS_REPO_DIR}"
      export IPFS_PATH="${IPFS_REPO_DIR}"
      export IPFS_KIT_PLATFORM_OS="$OS"
      export IPFS_KIT_PLATFORM_ARCH="$ARCH"
      export IPFS_KIT_PLATFORM_LIBC="$LIBC"
      set +e
      python - <<PY
from ipfs_kit_py.install_ipfs import install_ipfs

inst = install_ipfs(metadata={"bin_dir": r"${BIN_DIR}", "ipfs_path": r"${IPFS_REPO_DIR}"})
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
      local rc=$?
      set -e
      if [[ $rc -ne 0 ]]; then
        err "WARNING: IPFS/Kubo install failed; continuing"
      fi

      # Initialize a project-local repo so IPFS CLI commands don't error out with
      # "no IPFS repo found". This does NOT start a daemon and never touches ~/.ipfs.
      if have_cmd ipfs; then
        if [[ ! -f "${IPFS_REPO_DIR}/config" ]]; then
          log "Initializing project-local IPFS repo at ${IPFS_REPO_DIR}"
          set +e
          IPFS_PATH="${IPFS_REPO_DIR}" ipfs init >/dev/null 2>&1
          local init_rc=$?
          set -e
          if [[ $init_rc -ne 0 ]]; then
            err "WARNING: ipfs init failed (repo may need manual init): IPFS_PATH=${IPFS_REPO_DIR} ipfs init"
          fi
        fi
      fi
    fi
  fi

  if [[ "$do_lassie" == "yes" ]]; then
    if ! supports_lassie; then
      err "WARNING: Lassie binaries not available for OS=$OS ARCH=$ARCH; skipping"
    else
      log "Installing Lassie into ./bin (no sudo)"
      set +e
      python - <<PY
from ipfs_kit_py.install_lassie import install_lassie

inst = install_lassie(metadata={"bin_dir": r"${BIN_DIR}"})
inst.install_lassie_daemon()
PY
      local rc=$?
      set -e
      if [[ $rc -ne 0 ]]; then
        err "WARNING: Lassie install failed; continuing"
      fi
    fi
  fi

  if [[ "$do_lotus" == "yes" ]]; then
    set +e
    warn_missing_toolchain_for_source_builds || true
    set -e
    if ! supports_lotus; then
      err "WARNING: Lotus binaries not available for OS=$OS ARCH=$ARCH; skipping"
    else
      log "Installing Lotus into ./bin (best-effort; no sudo by default)"
      set +e
      python - <<PY
from ipfs_kit_py.install_lotus import install_lotus

inst = install_lotus(metadata={
    "bin_dir": r"${BIN_DIR}",
    # Safer default: do not auto-install system deps (sudo) from zero-touch.
    "auto_install_deps": False,
    "allow_userspace_deps": True,
    "skip_params": True,
})
inst.install_lotus_daemon()
PY
      local rc=$?
      set -e
      if [[ $rc -ne 0 ]]; then
        err "WARNING: Lotus install failed; continuing"
      fi
    fi
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
  ensure_optional_python_deps

  # Optional: install vendored IPLD packages so tests can import ipld_car/ipld_dag_pb/ipld_unixfs
  # without git/network. Default to yes for dev/full profiles.
  local do_ipld="$INSTALL_IPLD"
  if [[ "$do_ipld" == "auto" ]]; then
    if [[ "$PROFILE" == "dev" || "$PROFILE" == "full" ]]; then do_ipld="yes"; else do_ipld="no"; fi
  fi
  if [[ "$do_ipld" == "yes" ]]; then
    install_vendored_ipld_packages
  fi

  # Native daemons/CLIs (optional)
  install_native_tools

  # Node/Playwright (optional)
  local do_node="$INSTALL_NODE"
  if [[ "$do_node" == "auto" ]]; then
    if [[ -f "${ROOT_DIR}/package.json" ]]; then do_node="yes"; else do_node="no"; fi
  fi
  if [[ "$do_node" == "yes" ]]; then
    set +e
    ensure_node_local
    local node_rc=$?
    set -e
    if [[ $node_rc -eq 0 ]]; then
      set +e
      install_node_deps
      local npm_rc=$?
      set -e
      if [[ $npm_rc -ne 0 ]]; then
        err "WARNING: npm dependency install failed; continuing"
      fi
    else
      err "WARNING: Node.js setup failed; skipping npm deps"
    fi
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

  # Provenance hint: show how ipfs_kit_py is installed (PyPI vs local editable vs direct URL).
  set +e
  activate_venv
  local installed_line
  installed_line="$(python -m pip freeze 2>/dev/null | grep -E '^(ipfs_kit_py|ipfs-kit-py)(==| @ )' | head -n 1)"
  if [[ -z "${installed_line}" ]]; then
    # Editable installs typically appear as '-e file:///...'; match those too.
    installed_line="$(python -m pip freeze 2>/dev/null | grep -E '^-e .*ipfs_kit_py' | head -n 1)"
  fi
  if [[ -n "${installed_line}" ]]; then
    log "- ipfs_kit_py: ${installed_line}"
  else
    log "- ipfs_kit_py: (not found in pip freeze)"
  fi

  # Fall back to pip show for additional clarity.
  local show_loc
  show_loc="$(python -m pip show ipfs_kit_py 2>/dev/null | grep -E '^(Editable project location|Location):' | head -n 1)"
  if [[ -n "${show_loc}" ]]; then
    log "- ipfs_kit_py ${show_loc}"
  fi
  local import_path
  # Avoid local-checkout shadowing: run the import from the cache dir so '.' is not the repo root.
  import_path="$(cd "${CACHE_DIR}" 2>/dev/null && python -c 'import inspect, ipfs_kit_py; print(inspect.getfile(ipfs_kit_py))' 2>/dev/null)"
  if [[ -n "${import_path}" ]]; then
    log "- ipfs_kit_py import: ${import_path}"
  fi
  set -e
}

main "$@"
