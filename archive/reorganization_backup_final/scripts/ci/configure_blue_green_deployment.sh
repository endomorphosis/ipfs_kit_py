#!/bin/bash
# configure_blue_green_deployment.sh
#
# Script to configure the blue/green deployment mode and traffic distribution
# Supports multiple environments and configurable parameters

set -e

# Default values
ENVIRONMENT="staging"
MODE="gradual"
GREEN_PERCENTAGE=10
NAMESPACE="mcp-system"
PROXY_SERVICE="mcp-proxy"
API_ENDPOINT="/api/set_mode"
RETRIES=5
RETRY_DELAY=5
DRY_RUN=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --mode)
      MODE="$2"
      shift 2
      ;;
    --green-percentage)
      GREEN_PERCENTAGE="$2"
      shift 2
      ;;
    --namespace)
      NAMESPACE="$2"
      shift 2
      ;;
    --proxy-service)
      PROXY_SERVICE="$2"
      shift 2
      ;;
    --api-endpoint)
      API_ENDPOINT="$2"
      shift 2
      ;;
    --retries)
      RETRIES="$2"
      shift 2
      ;;
    --retry-delay)
      RETRY_DELAY="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Validate parameters
if [[ ! "$MODE" =~ ^(blue|green|gradual|parallel|auto)$ ]]; then
  echo "Error: Invalid mode '$MODE'. Must be one of: blue, green, gradual, parallel, auto."
  exit 1
fi

if [ "$MODE" == "gradual" ] || [ "$MODE" == "auto" ]; then
  if ! [[ "$GREEN_PERCENTAGE" =~ ^[0-9]+$ ]] || [ "$GREEN_PERCENTAGE" -lt 0 ] || [ "$GREEN_PERCENTAGE" -gt 100 ]; then
    echo "Error: green-percentage must be an integer between 0 and 100."
    exit 1
  fi
fi

# Set environment-specific configuration
case $ENVIRONMENT in
  dev)
    NAMESPACE="mcp-dev"
    ;;
  staging)
    NAMESPACE="mcp-staging"
    ;;
  production)
    NAMESPACE="mcp-production"
    ;;
  *)
    echo "Error: Invalid environment '$ENVIRONMENT'. Must be 'dev', 'staging', or 'production'."
    exit 1
    ;;
esac

echo "Configuring blue/green deployment for environment: $ENVIRONMENT"
echo "Mode: $MODE"
if [ "$MODE" == "gradual" ] || [ "$MODE" == "auto" ]; then
  echo "Green percentage: $GREEN_PERCENTAGE%"
fi

# Check if proxy service is available
if ! kubectl get service $PROXY_SERVICE -n $NAMESPACE &>/dev/null; then
  echo "Error: Proxy service '$PROXY_SERVICE' not found in namespace '$NAMESPACE'."
  exit 1
fi

# Prepare JSON payload
if [ "$MODE" == "gradual" ] || [ "$MODE" == "auto" ]; then
  PAYLOAD="{\"mode\":\"$MODE\",\"green_percentage\":$GREEN_PERCENTAGE}"
else
  PAYLOAD="{\"mode\":\"$MODE\"}"
fi

if [ "$DRY_RUN" = true ]; then
  echo "Dry run mode: would configure blue/green deployment with payload:"
  echo "$PAYLOAD"
  exit 0
fi

# Function to set the deployment mode
set_deployment_mode() {
  local attempt=1
  local max_attempts=$RETRIES
  
  while [ $attempt -le $max_attempts ]; do
    echo "Attempt $attempt of $max_attempts to configure deployment mode..."
    
    # Port-forward to the proxy service
    PORT_FORWARD_PID=""
    kubectl port-forward service/$PROXY_SERVICE 8090:8090 -n $NAMESPACE &
    PORT_FORWARD_PID=$!
    
    # Wait for port-forward to establish
    sleep 3
    
    # Send configuration request
    if curl -s -X POST http://localhost:8090$API_ENDPOINT \
         -H "Content-Type: application/json" \
         -d "$PAYLOAD" \
         -o /tmp/response.json; then
      
      # Check for success
      if grep -q "\"success\":true" /tmp/response.json; then
        echo "Deployment mode set successfully!"
        cat /tmp/response.json
        
        # Clean up port-forward
        if [ -n "$PORT_FORWARD_PID" ]; then
          kill $PORT_FORWARD_PID || true
        fi
        
        return 0
      else
        echo "Request failed: $(cat /tmp/response.json)"
      fi
    else
      echo "Failed to connect to proxy service."
    fi
    
    # Clean up port-forward
    if [ -n "$PORT_FORWARD_PID" ]; then
      kill $PORT_FORWARD_PID || true
    fi
    
    # Retry after delay
    echo "Retrying in $RETRY_DELAY seconds..."
    sleep $RETRY_DELAY
    
    ((attempt++))
  done
  
  echo "Failed to configure deployment mode after $max_attempts attempts."
  return 1
}

# Configure the deployment
set_deployment_mode

# Verify the configuration was applied
echo "Verifying deployment configuration..."
kubectl port-forward service/$PROXY_SERVICE 8090:8090 -n $NAMESPACE &
VERIFY_PORT_FORWARD_PID=$!

# Wait for port-forward to establish
sleep 3

# Get current configuration
curl -s http://localhost:8090/api/health -o /tmp/health.json

# Clean up port-forward
if [ -n "$VERIFY_PORT_FORWARD_PID" ]; then
  kill $VERIFY_PORT_FORWARD_PID || true
fi

# Display configuration
echo "Current deployment configuration:"
cat /tmp/health.json

# Check if the mode matches what we set
if grep -q "\"mode\":\"$MODE\"" /tmp/health.json; then
  echo "Deployment configured successfully!"
else
  echo "Warning: Deployment configuration verification failed. Check logs for details."
  exit 1
fi