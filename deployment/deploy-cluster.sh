#!/bin/bash
# IPFS MCP Cluster Deployment Script
set -e

echo "=== IPFS MCP Cluster Deployment ==="
echo

# Configuration
NAMESPACE="ipfs-cluster"
IMAGE_TAG="latest"
BUILD_IMAGE=${BUILD_IMAGE:-true}
DEPLOY_TO_K8S=${DEPLOY_TO_K8S:-true}
RUN_TESTS=${RUN_TESTS:-true}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to build Docker image
build_image() {
    log "Building Docker image..."
    
    cd docker
    docker build -t ipfs-kit-mcp:${IMAGE_TAG} -f Dockerfile --target development ..
    
    if [ $? -eq 0 ]; then
        success "Docker image built successfully"
    else
        error "Failed to build Docker image"
        exit 1
    fi
    
    cd ..
}

# Function to deploy with Docker Compose (for local testing)
deploy_docker_compose() {
    log "Deploying with Docker Compose..."
    
    cd docker
    
    # Stop any existing containers
    docker-compose down -v 2>/dev/null || true
    
    # Start the cluster
    docker-compose up -d
    
    if [ $? -eq 0 ]; then
        success "Docker Compose deployment successful"
        
        log "Waiting for services to be ready..."
        sleep 30
        
        log "Checking service health..."
        docker-compose ps
        
        # Check if services are healthy
        if curl -f http://localhost:9998/health >/dev/null 2>&1; then
            success "Master node is healthy"
        else
            warning "Master node health check failed"
        fi
        
        if curl -f http://localhost:9999/health >/dev/null 2>&1; then
            success "Worker1 node is healthy"
        else
            warning "Worker1 node health check failed"
        fi
        
        if curl -f http://localhost:10000/health >/dev/null 2>&1; then
            success "Worker2 node is healthy"
        else
            warning "Worker2 node health check failed"
        fi
        
    else
        error "Docker Compose deployment failed"
        exit 1
    fi
    
    cd ..
}

# Function to deploy to Kubernetes
deploy_kubernetes() {
    log "Deploying to Kubernetes..."
    
    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    # Check if cluster is accessible
    if ! kubectl cluster-info &> /dev/null; then
        error "Kubernetes cluster is not accessible"
        exit 1
    fi
    
    # Create namespace if it doesn't exist
    kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
    
    # Apply Kubernetes manifests
    log "Applying Kubernetes manifests..."
    kubectl apply -f deployment/k8s/00-services.yaml
    kubectl apply -f deployment/k8s/01-master.yaml
    kubectl apply -f deployment/k8s/02-workers.yaml
    
    success "Kubernetes manifests applied"
    
    # Wait for deployments to be ready
    log "Waiting for deployments to be ready..."
    kubectl wait --for=condition=ready pod -l app=ipfs-mcp -n ${NAMESPACE} --timeout=300s
    
    if [ $? -eq 0 ]; then
        success "All pods are ready"
    else
        warning "Some pods may not be ready yet"
    fi
    
    # Show cluster status
    log "Cluster status:"
    kubectl get pods -n ${NAMESPACE}
    kubectl get services -n ${NAMESPACE}
}

# Function to run tests
run_tests() {
    log "Running cluster tests..."
    
    if [ "$DEPLOY_TO_K8S" = true ]; then
        # Run Kubernetes test job
        kubectl apply -f deployment/k8s/03-test-job.yaml
        
        log "Waiting for test job to complete..."
        kubectl wait --for=condition=complete job/cluster-test-job -n ${NAMESPACE} --timeout=300s
        
        if [ $? -eq 0 ]; then
            success "Test job completed successfully"
            log "Test logs:"
            kubectl logs job/cluster-test-job -n ${NAMESPACE}
        else
            warning "Test job may have failed or timed out"
            kubectl describe job/cluster-test-job -n ${NAMESPACE}
        fi
    else
        # Run Docker Compose tests
        cd docker
        docker-compose exec cluster-tester python comprehensive_cluster_demonstration.py
        cd ..
    fi
}

# Function to show usage information
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    --docker-only       Deploy only with Docker Compose (skip Kubernetes)
    --k8s-only         Deploy only to Kubernetes (skip Docker Compose)
    --no-build         Skip building Docker image
    --no-tests         Skip running tests
    --help             Show this help message

Environment Variables:
    BUILD_IMAGE        Set to false to skip image building (default: true)
    DEPLOY_TO_K8S      Set to false to skip Kubernetes deployment (default: true)
    RUN_TESTS          Set to false to skip tests (default: true)

Examples:
    $0                              # Full deployment (Docker + K8s + tests)
    $0 --docker-only               # Docker Compose only
    $0 --k8s-only --no-build       # Kubernetes only, use existing image
    BUILD_IMAGE=false $0            # Skip building, use existing image

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --docker-only)
            DEPLOY_TO_K8S=false
            shift
            ;;
        --k8s-only)
            BUILD_IMAGE=false
            shift
            ;;
        --no-build)
            BUILD_IMAGE=false
            shift
            ;;
        --no-tests)
            RUN_TESTS=false
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main deployment flow
main() {
    log "Starting IPFS MCP Cluster deployment..."
    log "Configuration:"
    log "  Build Image: $BUILD_IMAGE"
    log "  Deploy to K8s: $DEPLOY_TO_K8S"
    log "  Run Tests: $RUN_TESTS"
    echo
    
    # Build Docker image if requested
    if [ "$BUILD_IMAGE" = true ]; then
        build_image
    fi
    
    # Deploy with Docker Compose for local testing
    if [ "$DEPLOY_TO_K8S" = false ]; then
        deploy_docker_compose
    fi
    
    # Deploy to Kubernetes
    if [ "$DEPLOY_TO_K8S" = true ]; then
        deploy_kubernetes
    fi
    
    # Run tests if requested
    if [ "$RUN_TESTS" = true ]; then
        run_tests
    fi
    
    success "Deployment completed successfully!"
    
    # Show access information
    echo
    log "Access Information:"
    if [ "$DEPLOY_TO_K8S" = false ]; then
        echo "  Master Node:  http://localhost:9998"
        echo "  Worker1 Node: http://localhost:9999"
        echo "  Worker2 Node: http://localhost:10000"
    else
        echo "  Use kubectl port-forward to access services:"
        echo "  kubectl port-forward svc/ipfs-mcp-master 9998:9998 -n ${NAMESPACE}"
    fi
    echo
    log "Health Check:"
    echo "  curl http://localhost:9998/health"
    echo
    log "Cluster Status:"
    echo "  curl http://localhost:9998/cluster/status"
}

# Run main function
main
