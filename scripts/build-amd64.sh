# Build and deployment scripts for AMD64 architecture
# Based on generative-protein-binder-design build patterns

#!/bin/bash
set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="${PROJECT_ROOT}/build"
DIST_DIR="${PROJECT_ROOT}/dist"

# Build configuration
PYTHON_VERSION=${PYTHON_VERSION:-3.11}
BUILD_TYPE=${BUILD_TYPE:-production}
DOCKER_REGISTRY=${DOCKER_REGISTRY:-ghcr.io}
IMAGE_NAME=${IMAGE_NAME:-ipfs-kit-py}
TAG=${TAG:-latest}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check dependencies
check_dependencies() {
    log_info "Checking build dependencies..."
    
    local deps=("python3" "pip" "docker" "git")
    local missing_deps=()
    
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            missing_deps+=("$dep")
        fi
    done
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        exit 1
    fi
    
    log_success "All dependencies found"
}

# Function to setup build environment
setup_build_env() {
    log_info "Setting up build environment..."
    
    # Create build directories
    mkdir -p "$BUILD_DIR" "$DIST_DIR"
    
    # Clean previous builds
    rm -rf "${BUILD_DIR:?}"/* "${DIST_DIR:?}"/* || true
    
    # Set up Python virtual environment for building
    if [ ! -d "${BUILD_DIR}/venv" ]; then
        python3 -m venv "${BUILD_DIR}/venv"
    fi
    
    # Activate virtual environment and install build tools
    source "${BUILD_DIR}/venv/bin/activate"
    pip install --upgrade pip setuptools wheel build twine
    
    log_success "Build environment ready"
}

# Function to run tests
run_tests() {
    log_info "Running test suite..."
    
    source "${BUILD_DIR}/venv/bin/activate"
    cd "$PROJECT_ROOT"
    
    # Install package in development mode
    pip install -e ".[dev,test]"
    
    # Run linting
    log_info "Running code quality checks..."
    flake8 ipfs_kit_py/ tests/ || log_warning "Linting issues found"
    black --check ipfs_kit_py/ tests/ || log_warning "Code formatting issues found"
    isort --check-only ipfs_kit_py/ tests/ || log_warning "Import sorting issues found"
    
    # Run type checking
    log_info "Running type checks..."
    mypy ipfs_kit_py/ || log_warning "Type checking issues found"
    
    # Run security checks
    log_info "Running security checks..."
    bandit -r ipfs_kit_py/ || log_warning "Security issues found"
    safety check || log_warning "Dependency security issues found"
    
    # Run unit tests
    log_info "Running unit tests..."
    pytest tests/ \
        --verbose \
        --cov=ipfs_kit_py \
        --cov-report=term-missing \
        --cov-report=html:"${BUILD_DIR}/coverage-html" \
        --cov-report=xml:"${BUILD_DIR}/coverage.xml" \
        --junit-xml="${BUILD_DIR}/junit.xml" \
        --timeout=300
    
    log_success "All tests completed"
}

# Function to build Python package
build_python_package() {
    log_info "Building Python package..."
    
    source "${BUILD_DIR}/venv/bin/activate"
    cd "$PROJECT_ROOT"
    
    # Build source distribution and wheel
    python -m build --outdir "$DIST_DIR"
    
    # Check distribution
    twine check "${DIST_DIR}"/*
    
    log_success "Python package built successfully"
    ls -la "$DIST_DIR"
}

# Function to build Docker images
build_docker_images() {
    log_info "Building Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Build production image
    log_info "Building production image..."
    docker build \
        --tag "${IMAGE_NAME}:${TAG}" \
        --tag "${IMAGE_NAME}:latest" \
        --target production \
        --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
        --build-arg BUILD_TYPE="$BUILD_TYPE" \
        --platform linux/amd64 \
        .
    
    # Build development image
    log_info "Building development image..."
    docker build \
        --tag "${IMAGE_NAME}:dev" \
        --file Dockerfile.dev \
        --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
        --platform linux/amd64 \
        .
    
    # Build testing image
    log_info "Building testing image..."
    docker build \
        --tag "${IMAGE_NAME}:test" \
        --file Dockerfile.test \
        --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
        --platform linux/amd64 \
        .
    
    # Build documentation image
    log_info "Building documentation image..."
    docker build \
        --tag "${IMAGE_NAME}:docs" \
        --file Dockerfile.docs \
        --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
        --platform linux/amd64 \
        .
    
    log_success "All Docker images built successfully"
    docker images | grep "$IMAGE_NAME"
}

# Function to build GPU Docker image (if supported)
build_gpu_docker_image() {
    if command -v nvidia-smi &> /dev/null; then
        log_info "Building GPU Docker image..."
        
        docker build \
            --tag "${IMAGE_NAME}:gpu" \
            --file Dockerfile.gpu \
            --target gpu-production \
            --build-arg CUDA_VERSION=12.1 \
            --build-arg PYTHON_VERSION="$PYTHON_VERSION" \
            --build-arg BUILD_TYPE="$BUILD_TYPE" \
            --platform linux/amd64 \
            .
        
        log_success "GPU Docker image built successfully"
    else
        log_warning "NVIDIA drivers not found - skipping GPU image build"
    fi
}

# Function to test Docker images
test_docker_images() {
    log_info "Testing Docker images..."
    
    # Test production image
    log_info "Testing production image..."
    docker run --rm "${IMAGE_NAME}:${TAG}" python -c "import ipfs_kit_py; print('Production image OK')"
    
    # Test development image
    log_info "Testing development image..."
    docker run --rm "${IMAGE_NAME}:dev" python -c "import ipfs_kit_py; print('Development image OK')"
    
    # Test testing image
    log_info "Testing testing image..."
    docker run --rm "${IMAGE_NAME}:test" python -c "import pytest; print('Testing image OK')"
    
    # Test documentation image (if port is available)
    if ! netstat -tuln | grep -q ":8080 "; then
        log_info "Testing documentation image..."
        timeout 30s docker run --rm -p 8080:8080 "${IMAGE_NAME}:docs" &
        sleep 10
        if curl -f http://localhost:8080/ > /dev/null 2>&1; then
            log_success "Documentation image OK"
        else
            log_warning "Documentation image test failed"
        fi
        pkill -f "docker.*${IMAGE_NAME}:docs" || true
    else
        log_warning "Port 8080 in use - skipping documentation image test"
    fi
    
    log_success "Docker image tests completed"
}

# Function to generate build report
generate_build_report() {
    log_info "Generating build report..."
    
    local report_file="${BUILD_DIR}/build-report.md"
    
    cat > "$report_file" << EOF
# Build Report

**Build Date:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")
**Build Type:** $BUILD_TYPE
**Python Version:** $PYTHON_VERSION
**Git Commit:** $(git rev-parse HEAD)
**Git Branch:** $(git branch --show-current)

## Build Artifacts

### Python Package
$(ls -la "$DIST_DIR" 2>/dev/null || echo "No Python packages built")

### Docker Images
\`\`\`
$(docker images | grep "$IMAGE_NAME" | head -10)
\`\`\`

## Test Results
- Unit Tests: $([ -f "${BUILD_DIR}/junit.xml" ] && echo "✅ Passed" || echo "❌ Failed/Skipped")
- Coverage Report: $([ -f "${BUILD_DIR}/coverage.xml" ] && echo "✅ Generated" || echo "❌ Missing")
- Security Scan: $(command -v bandit &> /dev/null && echo "✅ Completed" || echo "⚠️ Skipped")

## Build Environment
- OS: $(uname -s) $(uname -r)
- Architecture: $(uname -m)
- Docker Version: $(docker --version 2>/dev/null || echo "Not available")
- Python Version: $(python3 --version)

EOF
    
    log_success "Build report generated: $report_file"
}

# Function to cleanup build environment
cleanup() {
    log_info "Cleaning up build environment..."
    
    # Remove build virtual environment
    rm -rf "${BUILD_DIR}/venv" || true
    
    # Prune Docker images
    docker system prune -f || true
    
    log_success "Cleanup completed"
}

# Main build function
main() {
    log_info "Starting AMD64 build process for $IMAGE_NAME"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-tests)
                SKIP_TESTS=1
                shift
                ;;
            --skip-docker)
                SKIP_DOCKER=1
                shift
                ;;
            --skip-gpu)
                SKIP_GPU=1
                shift
                ;;
            --python-version)
                PYTHON_VERSION="$2"
                shift 2
                ;;
            --build-type)
                BUILD_TYPE="$2"
                shift 2
                ;;
            --tag)
                TAG="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --skip-tests        Skip running tests"
                echo "  --skip-docker       Skip Docker image builds"
                echo "  --skip-gpu          Skip GPU Docker image build"
                echo "  --python-version    Python version to use (default: 3.11)"
                echo "  --build-type        Build type (default: production)"
                echo "  --tag              Docker image tag (default: latest)"
                echo "  --help             Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Check dependencies
    check_dependencies
    
    # Setup build environment
    setup_build_env
    
    # Run tests (unless skipped)
    if [ "${SKIP_TESTS:-0}" != "1" ]; then
        run_tests
    else
        log_warning "Skipping tests"
    fi
    
    # Build Python package
    build_python_package
    
    # Build Docker images (unless skipped)
    if [ "${SKIP_DOCKER:-0}" != "1" ]; then
        build_docker_images
        test_docker_images
        
        # Build GPU image (unless skipped)
        if [ "${SKIP_GPU:-0}" != "1" ]; then
            build_gpu_docker_image
        else
            log_warning "Skipping GPU Docker image build"
        fi
    else
        log_warning "Skipping Docker builds"
    fi
    
    # Generate build report
    generate_build_report
    
    log_success "Build process completed successfully!"
    log_info "Build artifacts available in: $DIST_DIR"
    log_info "Build report available at: ${BUILD_DIR}/build-report.md"
}

# Trap cleanup on exit
trap cleanup EXIT

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi