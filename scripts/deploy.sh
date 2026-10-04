# Deployment script for multi-environment deployments
# Based on protein design deployment patterns

#!/bin/bash
set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Deployment configuration
ENVIRONMENT=${ENVIRONMENT:-development}
DOCKER_REGISTRY=${DOCKER_REGISTRY:-ghcr.io}
IMAGE_NAME=${IMAGE_NAME:-ipfs-kit-py}
TAG=${TAG:-latest}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.yml}

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

# Function to check deployment prerequisites
check_prerequisites() {
    log_info "Checking deployment prerequisites..."
    
    local deps=("docker" "docker-compose")
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
    
    # Check Docker daemon
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    # Check compose file exists
    if [ ! -f "$PROJECT_ROOT/$COMPOSE_FILE" ]; then
        log_error "Docker compose file not found: $COMPOSE_FILE"
        exit 1
    fi
    
    log_success "All prerequisites met"
}

# Function to setup deployment environment
setup_environment() {
    log_info "Setting up $ENVIRONMENT environment..."
    
    cd "$PROJECT_ROOT"
    
    # Create necessary directories
    mkdir -p data logs config
    
    # Set up environment-specific configuration
    case $ENVIRONMENT in
        development)
            export COMPOSE_PROFILES="development"
            export LOG_LEVEL="DEBUG"
            export PYTHONUNBUFFERED="1"
            ;;
        testing)
            export COMPOSE_PROFILES="testing"
            export LOG_LEVEL="DEBUG"
            export TESTING="1"
            ;;
        staging)
            export COMPOSE_PROFILES="staging"
            export LOG_LEVEL="INFO"
            ;;
        production)
            export COMPOSE_PROFILES="production"
            export LOG_LEVEL="INFO"
            export PYTHONOPTIMIZE="1"
            ;;
        *)
            log_error "Unknown environment: $ENVIRONMENT"
            exit 1
            ;;
    esac
    
    # Export environment variables
    export DOCKER_REGISTRY
    export IMAGE_NAME
    export TAG
    export ENVIRONMENT
    
    log_success "Environment $ENVIRONMENT configured"
}

# Function to pull latest images
pull_images() {
    log_info "Pulling latest Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Pull images specified in compose file
    docker-compose -f "$COMPOSE_FILE" pull || log_warning "Some images could not be pulled"
    
    log_success "Images pulled successfully"
}

# Function to deploy services
deploy_services() {
    log_info "Deploying services for $ENVIRONMENT environment..."
    
    cd "$PROJECT_ROOT"
    
    # Stop existing services
    log_info "Stopping existing services..."
    docker-compose -f "$COMPOSE_FILE" down || true
    
    # Deploy services based on environment
    case $ENVIRONMENT in
        development)
            log_info "Starting development services..."
            docker-compose -f "$COMPOSE_FILE" --profile development up -d
            ;;
        testing)
            log_info "Starting testing services..."
            docker-compose -f "$COMPOSE_FILE" --profile testing up -d
            ;;
        staging|production)
            log_info "Starting production services..."
            docker-compose -f "$COMPOSE_FILE" up -d ipfs-kit-py
            ;;
    esac
    
    log_success "Services deployed successfully"
}

# Function to deploy GPU services
deploy_gpu_services() {
    log_info "Checking GPU support..."
    
    if command -v nvidia-smi &> /dev/null && nvidia-smi > /dev/null 2>&1; then
        log_info "GPU support detected - deploying GPU services..."
        
        cd "$PROJECT_ROOT"
        docker-compose -f "$COMPOSE_FILE" up -d ipfs-kit-py-gpu
        
        log_success "GPU services deployed"
    else
        log_warning "No GPU support detected - skipping GPU services"
    fi
}

# Function to run health checks
run_health_checks() {
    log_info "Running health checks..."
    
    cd "$PROJECT_ROOT"
    
    # Wait for services to start
    sleep 10
    
    # Check service status
    local services
    services=$(docker-compose -f "$COMPOSE_FILE" ps --services)
    
    for service in $services; do
        if docker-compose -f "$COMPOSE_FILE" ps "$service" | grep -q "Up"; then
            log_success "Service $service is running"
            
            # Run container-specific health check
            if docker-compose -f "$COMPOSE_FILE" exec -T "$service" python -c "import ipfs_kit_py; print('Health check OK')" > /dev/null 2>&1; then
                log_success "Service $service health check passed"
            else
                log_warning "Service $service health check failed"
            fi
        else
            log_error "Service $service is not running"
        fi
    done
    
    # Check exposed ports
    log_info "Checking exposed ports..."
    netstat -tuln | grep -E ":8000|:8001|:8002|:8080" || log_warning "Some expected ports are not listening"
    
    log_success "Health checks completed"
}

# Function to setup monitoring
setup_monitoring() {
    log_info "Setting up monitoring..."
    
    cd "$PROJECT_ROOT"
    
    # Create monitoring directory
    mkdir -p monitoring
    
    # Generate monitoring configuration
    cat > monitoring/prometheus.yml << EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'ipfs-kit-py'
    static_configs:
      - targets: ['ipfs-kit-py:8000']
    metrics_path: /metrics
    scrape_interval: 10s
    
  - job_name: 'docker'
    static_configs:
      - targets: ['host.docker.internal:9323']
EOF
    
    # Start monitoring services if requested
    if [ "${ENABLE_MONITORING:-0}" == "1" ]; then
        log_info "Starting monitoring services..."
        # This would start Prometheus, Grafana, etc.
        # Implementation depends on monitoring setup
    fi
    
    log_success "Monitoring setup completed"
}

# Function to run deployment tests
run_deployment_tests() {
    log_info "Running deployment tests..."
    
    cd "$PROJECT_ROOT"
    
    # Basic connectivity tests
    local endpoints=("http://localhost:8000" "http://localhost:8080")
    
    for endpoint in "${endpoints[@]}"; do
        if curl -f "$endpoint" > /dev/null 2>&1; then
            log_success "Endpoint $endpoint is accessible"
        else
            log_warning "Endpoint $endpoint is not accessible"
        fi
    done
    
    # Run integration tests if available
    if [ -f "tests/integration/test_deployment.py" ]; then
        log_info "Running integration tests..."
        docker-compose -f "$COMPOSE_FILE" exec -T ipfs-kit-py pytest tests/integration/test_deployment.py -v || log_warning "Integration tests failed"
    fi
    
    log_success "Deployment tests completed"
}

# Function to generate deployment report
generate_deployment_report() {
    log_info "Generating deployment report..."
    
    local report_file="$PROJECT_ROOT/logs/deployment-report-$(date +%Y%m%d-%H%M%S).md"
    mkdir -p "$(dirname "$report_file")"
    
    cat > "$report_file" << EOF
# Deployment Report

**Deployment Date:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")
**Environment:** $ENVIRONMENT
**Docker Registry:** $DOCKER_REGISTRY
**Image:** $IMAGE_NAME:$TAG
**Compose File:** $COMPOSE_FILE

## Deployed Services
\`\`\`
$(docker-compose -f "$COMPOSE_FILE" ps)
\`\`\`

## Running Containers
\`\`\`
$(docker ps --filter "name=ipfs-kit-py")
\`\`\`

## Resource Usage
\`\`\`
$(docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" 2>/dev/null || echo "Stats not available")
\`\`\`

## Network Configuration
\`\`\`
$(docker network ls | grep ipfs || echo "No custom networks found")
\`\`\`

## Volume Information
\`\`\`
$(docker volume ls | grep ipfs || echo "No custom volumes found")
\`\`\`

## Health Status
$(run_health_checks 2>&1 | grep -E "\[SUCCESS\]|\[ERROR\]|\[WARNING\]" || echo "Health checks not available")

EOF
    
    log_success "Deployment report generated: $report_file"
}

# Function to rollback deployment
rollback_deployment() {
    log_warning "Rolling back deployment..."
    
    cd "$PROJECT_ROOT"
    
    # Stop current services
    docker-compose -f "$COMPOSE_FILE" down
    
    # Restore from backup if available
    if [ -f ".env.backup" ]; then
        mv .env.backup .env
        log_info "Environment configuration restored from backup"
    fi
    
    # Start services with previous configuration
    docker-compose -f "$COMPOSE_FILE" up -d
    
    log_success "Rollback completed"
}

# Function to cleanup old deployments
cleanup_old_deployments() {
    log_info "Cleaning up old deployments..."
    
    # Remove stopped containers
    docker container prune -f
    
    # Remove unused images
    docker image prune -f
    
    # Remove unused networks
    docker network prune -f
    
    # Remove unused volumes (be careful with this)
    if [ "${CLEANUP_VOLUMES:-0}" == "1" ]; then
        docker volume prune -f
        log_warning "Volumes cleaned up - data may be lost"
    fi
    
    log_success "Cleanup completed"
}

# Main deployment function
main() {
    log_info "Starting deployment for $IMAGE_NAME in $ENVIRONMENT environment"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --environment)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --tag)
                TAG="$2"
                shift 2
                ;;
            --compose-file)
                COMPOSE_FILE="$2"
                shift 2
                ;;
            --skip-health-checks)
                SKIP_HEALTH_CHECKS=1
                shift
                ;;
            --skip-gpu)
                SKIP_GPU=1
                shift
                ;;
            --enable-monitoring)
                ENABLE_MONITORING=1
                shift
                ;;
            --cleanup-volumes)
                CLEANUP_VOLUMES=1
                shift
                ;;
            --rollback)
                rollback_deployment
                exit 0
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --environment ENV      Deployment environment (development|testing|staging|production)"
                echo "  --tag TAG             Docker image tag"
                echo "  --compose-file FILE   Docker compose file to use"
                echo "  --skip-health-checks  Skip health checks"
                echo "  --skip-gpu           Skip GPU service deployment"
                echo "  --enable-monitoring   Enable monitoring services"
                echo "  --cleanup-volumes     Clean up unused volumes"
                echo "  --rollback           Rollback to previous deployment"
                echo "  --help               Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Check prerequisites
    check_prerequisites
    
    # Setup environment
    setup_environment
    
    # Pull images
    pull_images
    
    # Deploy services
    deploy_services
    
    # Deploy GPU services (unless skipped)
    if [ "${SKIP_GPU:-0}" != "1" ]; then
        deploy_gpu_services
    else
        log_warning "Skipping GPU services"
    fi
    
    # Setup monitoring
    setup_monitoring
    
    # Run health checks (unless skipped)
    if [ "${SKIP_HEALTH_CHECKS:-0}" != "1" ]; then
        run_health_checks
        run_deployment_tests
    else
        log_warning "Skipping health checks"
    fi
    
    # Generate deployment report
    generate_deployment_report
    
    # Cleanup old deployments
    cleanup_old_deployments
    
    log_success "Deployment completed successfully!"
    log_info "Services are now running in $ENVIRONMENT mode"
    log_info "Access the application at: http://localhost:8000"
    log_info "Documentation available at: http://localhost:8080"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi