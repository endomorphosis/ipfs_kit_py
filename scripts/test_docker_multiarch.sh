#!/bin/bash
##
# Multi-Architecture Docker Test Script
#
# This script tests Docker builds and functionality across multiple architectures.
#
# Usage:
#   ./scripts/test_docker_multiarch.sh [--build-only] [--test-only]
##

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
IMAGE_NAME="ipfs-kit-py"
ARCHITECTURES=("linux/amd64" "linux/arm64")
BUILD_ONLY=false
TEST_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --build-only)
            BUILD_ONLY=true
            shift
            ;;
        --test-only)
            TEST_ONLY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--build-only] [--test-only]"
            exit 1
            ;;
    esac
done

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Check if buildx is available
check_buildx() {
    log_info "Checking Docker buildx support..."
    
    if ! docker buildx version >/dev/null 2>&1; then
        log_error "Docker buildx not available"
        log_error "Install with: docker buildx install"
        return 1
    fi
    
    log_info "✓ Docker buildx available"
    return 0
}

# Create buildx builder if needed
setup_builder() {
    log_info "Setting up multi-arch builder..."
    
    if ! docker buildx inspect multiarch >/dev/null 2>&1; then
        log_info "Creating new buildx builder 'multiarch'..."
        docker buildx create --name multiarch --use
        docker buildx inspect --bootstrap
    else
        log_info "Using existing buildx builder 'multiarch'"
        docker buildx use multiarch
    fi
}

# Build for specific architecture
build_arch() {
    local arch=$1
    local tag="${IMAGE_NAME}:${arch//\//-}"
    
    log_info "Building for ${arch}..."
    
    if docker buildx build \
        --platform="${arch}" \
        --target=production \
        --tag="${tag}" \
        --load \
        . ; then
        log_info "✓ Build successful for ${arch}"
        return 0
    else
        log_error "✗ Build failed for ${arch}"
        return 1
    fi
}

# Test Docker image
test_image() {
    local arch=$1
    local tag="${IMAGE_NAME}:${arch//\//-}"
    
    log_info "Testing image for ${arch}..."
    
    # Test 1: Basic import
    if ! timeout 30 docker run --rm --platform="${arch}" "${tag}" \
        python -c "import ipfs_kit_py; print('IPFS Kit: OK')" 2>&1 | grep -q "IPFS Kit: OK"; then
        log_error "✗ Basic import test failed for ${arch}"
        return 1
    fi
    log_info "  ✓ Basic import test passed"
    
    # Test 2: Dependency checker
    if ! timeout 30 docker run --rm --platform="${arch}" "${tag}" \
        python /app/scripts/check_and_install_dependencies.py --dry-run 2>&1 | grep -q "Dry run completed"; then
        log_error "✗ Dependency checker test failed for ${arch}"
        return 1
    fi
    log_info "  ✓ Dependency checker test passed"
    
    # Test 3: Architecture detection
    local detected_arch=$(timeout 30 docker run --rm --platform="${arch}" "${tag}" \
        python -c "import platform; print(platform.machine())" 2>&1 | tail -1)
    log_info "  Detected architecture: ${detected_arch}"
    
    log_info "✓ All tests passed for ${arch}"
    return 0
}

# Build for all architectures
build_all() {
    log_info "========================================"
    log_info "Building for all architectures"
    log_info "========================================"
    
    local failed_builds=()
    
    for arch in "${ARCHITECTURES[@]}"; do
        if ! build_arch "${arch}"; then
            failed_builds+=("${arch}")
        fi
        echo ""
    done
    
    if [ ${#failed_builds[@]} -eq 0 ]; then
        log_info "✓ All builds successful!"
        return 0
    else
        log_error "✗ Failed builds: ${failed_builds[*]}"
        return 1
    fi
}

# Test all architectures
test_all() {
    log_info "========================================"
    log_info "Testing all architectures"
    log_info "========================================"
    
    local failed_tests=()
    
    for arch in "${ARCHITECTURES[@]}"; do
        if ! test_image "${arch}"; then
            failed_tests+=("${arch}")
        fi
        echo ""
    done
    
    if [ ${#failed_tests[@]} -eq 0 ]; then
        log_info "✓ All tests passed!"
        return 0
    else
        log_error "✗ Failed tests: ${failed_tests[*]}"
        return 1
    fi
}

# Build multi-arch image (not loaded, for pushing)
build_multiarch() {
    log_info "========================================"
    log_info "Building multi-architecture image"
    log_info "========================================"
    
    local platforms=$(IFS=,; echo "${ARCHITECTURES[*]}")
    
    log_info "Platforms: ${platforms}"
    
    if docker buildx build \
        --platform="${platforms}" \
        --target=production \
        --tag="${IMAGE_NAME}:latest" \
        --tag="${IMAGE_NAME}:$(date +%Y%m%d)" \
        . ; then
        log_info "✓ Multi-arch build successful"
        log_info "Note: Image not loaded locally (use --load for single platform)"
        return 0
    else
        log_error "✗ Multi-arch build failed"
        return 1
    fi
}

# Main execution
main() {
    log_info "========================================"
    log_info "Multi-Architecture Docker Test"
    log_info "========================================"
    log_info "Date: $(date)"
    log_info "Current directory: $(pwd)"
    echo ""
    
    # Check requirements
    if ! check_buildx; then
        exit 1
    fi
    
    # Setup builder
    setup_builder
    echo ""
    
    # Execute based on flags
    if [ "$TEST_ONLY" = true ]; then
        log_info "Running tests only (skipping builds)..."
        test_all
        exit $?
    fi
    
    if [ "$BUILD_ONLY" = true ]; then
        log_info "Running builds only (skipping tests)..."
        build_all
        exit $?
    fi
    
    # Default: build and test
    if ! build_all; then
        log_error "Builds failed, skipping tests"
        exit 1
    fi
    
    echo ""
    if ! test_all; then
        log_error "Tests failed"
        exit 1
    fi
    
    log_info "========================================"
    log_info "All builds and tests successful!"
    log_info "========================================"
}

# Run main
main
