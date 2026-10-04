#!/bin/bash
##
# Docker Entrypoint Script for IPFS Kit Python
#
# This script runs when the Docker container starts and:
# 1. Detects the architecture and OS
# 2. Verifies all dependencies are installed
# 3. Runs any initialization needed
# 4. Starts the requested service
#
# Usage:
#   docker run ipfs-kit-py [command] [args...]
#
# If no command is provided, defaults to running the main application.
##

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect architecture and OS
detect_platform() {
    local arch=$(uname -m)
    local os=$(uname -s)
    
    log_info "Platform: ${os}"
    log_info "Architecture: ${arch}"
    
    # Export for use by child processes
    export IPFS_KIT_PLATFORM="${os}"
    export IPFS_KIT_ARCH="${arch}"
    
    # Set architecture-specific variables
    case "${arch}" in
        x86_64|amd64)
            export IPFS_KIT_ARCH_NORMALIZED="amd64"
            ;;
        aarch64|arm64)
            export IPFS_KIT_ARCH_NORMALIZED="arm64"
            ;;
        armv7l|armv6l)
            export IPFS_KIT_ARCH_NORMALIZED="arm"
            ;;
        *)
            log_warn "Unknown architecture: ${arch}"
            export IPFS_KIT_ARCH_NORMALIZED="${arch}"
            ;;
    esac
    
    log_info "Normalized architecture: ${IPFS_KIT_ARCH_NORMALIZED}"
}

# Check Python version
check_python() {
    log_info "Checking Python..."
    
    if ! command -v python &> /dev/null; then
        log_error "Python not found!"
        return 1
    fi
    
    local python_version=$(python --version 2>&1 | awk '{print $2}')
    log_info "Python version: ${python_version}"
    
    # Check minimum version (3.8)
    local major=$(echo "${python_version}" | cut -d. -f1)
    local minor=$(echo "${python_version}" | cut -d. -f2)
    
    if [ "${major}" -lt 3 ] || ([ "${major}" -eq 3 ] && [ "${minor}" -lt 8 ]); then
        log_error "Python 3.8+ required, found ${python_version}"
        return 1
    fi
    
    log_info "✓ Python version OK"
    return 0
}

# Check if package is installed
check_package() {
    local package=$1
    python -c "import ${package}" 2>/dev/null
    return $?
}

# Verify core dependencies
verify_dependencies() {
    log_info "Verifying core dependencies..."
    
    local missing_deps=()
    local core_deps=(
        "requests"
        "httpx"
        "aiohttp"
        "yaml"
        "psutil"
    )
    
    for dep in "${core_deps[@]}"; do
        # Convert package names (pyyaml -> yaml)
        local import_name="${dep}"
        case "${dep}" in
            pyyaml) import_name="yaml" ;;
            python-magic) import_name="magic" ;;
        esac
        
        if check_package "${import_name}"; then
            log_info "✓ ${dep}"
        else
            log_warn "✗ ${dep} not found"
            missing_deps+=("${dep}")
        fi
    done
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_warn "Missing dependencies: ${missing_deps[*]}"
        log_info "These should have been installed during build..."
        return 1
    fi
    
    log_info "✓ All core dependencies present"
    return 0
}

# Check system libraries (for native dependencies)
check_system_libs() {
    log_info "Checking system libraries..."
    
    # Check for hwloc (needed by some IPFS components)
    if ldconfig -p 2>/dev/null | grep -q libhwloc; then
        log_info "✓ libhwloc found"
    else
        log_warn "✗ libhwloc not found (may affect some features)"
    fi
    
    # Check for OpenCL (optional, for GPU support)
    if ldconfig -p 2>/dev/null | grep -q libOpenCL; then
        log_info "✓ OpenCL found"
    else
        log_info "OpenCL not found (GPU features disabled)"
    fi
}

# Initialize configuration
initialize_config() {
    log_info "Initializing configuration..."
    
    # Create necessary directories
    mkdir -p /app/data /app/logs /app/config
    
    # Set default environment variables if not set
    export PYTHONUNBUFFERED=${PYTHONUNBUFFERED:-1}
    export PYTHONDONTWRITEBYTECODE=${PYTHONDONTWRITEBYTECODE:-1}
    export LOG_LEVEL=${LOG_LEVEL:-INFO}
    
    # IPFS Kit specific settings
    export IPFS_KIT_DATA_DIR=${IPFS_KIT_DATA_DIR:-/app/data}
    export IPFS_KIT_LOG_DIR=${IPFS_KIT_LOG_DIR:-/app/logs}
    export IPFS_KIT_CONFIG_DIR=${IPFS_KIT_CONFIG_DIR:-/app/config}
    
    log_info "Data directory: ${IPFS_KIT_DATA_DIR}"
    log_info "Log directory: ${IPFS_KIT_LOG_DIR}"
    log_info "Config directory: ${IPFS_KIT_CONFIG_DIR}"
}

# Run dependency checker if available
run_dependency_checker() {
    if [ -f "/app/scripts/check_and_install_dependencies.py" ]; then
        log_info "Running dependency checker..."
        python /app/scripts/check_and_install_dependencies.py --dry-run --verbose || {
            log_warn "Dependency checker reported issues (continuing anyway)"
        }
    fi
}

# Main initialization
main_init() {
    log_info "========================================"
    log_info "IPFS Kit Python - Docker Entrypoint"
    log_info "========================================"
    
    # Platform detection
    detect_platform
    
    # Python check
    if ! check_python; then
        log_error "Python check failed!"
        exit 1
    fi
    
    # System libraries (non-fatal)
    check_system_libs || true
    
    # Initialize config
    initialize_config
    
    # Verify dependencies (non-fatal in production)
    verify_dependencies || log_warn "Some dependencies missing (container may not have been built correctly)"
    
    # Run full dependency checker in verbose mode if requested
    if [ "${IPFS_KIT_VERIFY_DEPS}" = "1" ]; then
        run_dependency_checker
    fi
    
    log_info "Initialization complete!"
    log_info "========================================"
}

# Execute main initialization
main_init

# Execute the command passed to docker run
if [ $# -eq 0 ]; then
    # No command provided, run default
    log_info "Starting IPFS Kit Python (default command)..."
    exec python -m ipfs_kit_py
else
    # Run the provided command
    log_info "Executing: $@"
    exec "$@"
fi
