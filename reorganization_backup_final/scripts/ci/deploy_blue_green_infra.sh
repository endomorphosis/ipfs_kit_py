#!/bin/bash
# deploy_blue_green_infra.sh
# 
# Script to deploy blue/green infrastructure to Kubernetes
# Supports multiple environments and configurable parameters

set -e

# Default values
ENVIRONMENT="staging"
REGISTRY="ghcr.io"
IMAGE_NAME=""
IMAGE_SHA=""
NAMESPACE="mcp-system"
BLUE_TAG="blue"
GREEN_TAG="green"
CONFIG_PATH=""
DRY_RUN=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --environment)
      ENVIRONMENT="$2"
      shift 2
      ;;
    --registry)
      REGISTRY="$2"
      shift 2
      ;;
    --image-name)
      IMAGE_NAME="$2"
      shift 2
      ;;
    --image-sha)
      IMAGE_SHA="$2"
      shift 2
      ;;
    --namespace)
      NAMESPACE="$2"
      shift 2
      ;;
    --blue-tag)
      BLUE_TAG="$2"
      shift 2
      ;;
    --green-tag)
      GREEN_TAG="$2"
      shift 2
      ;;
    --config)
      CONFIG_PATH="$2"
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

# Validate required parameters
if [ -z "$IMAGE_NAME" ]; then
  echo "Error: --image-name parameter is required"
  exit 1
fi

if [ -z "$IMAGE_SHA" ]; then
  echo "Error: --image-sha parameter is required"
  exit 1
fi

# Set environment-specific configuration
case $ENVIRONMENT in
  dev)
    NAMESPACE="mcp-dev"
    REPLICAS_BLUE=1
    REPLICAS_GREEN=1
    if [ -z "$CONFIG_PATH" ]; then
      CONFIG_PATH="./config/blue_green_config.dev.json"
    fi
    ;;
  staging)
    NAMESPACE="mcp-staging"
    REPLICAS_BLUE=2
    REPLICAS_GREEN=2
    if [ -z "$CONFIG_PATH" ]; then
      CONFIG_PATH="./config/blue_green_config.staging.json"
    fi
    ;;
  production)
    NAMESPACE="mcp-production"
    REPLICAS_BLUE=3
    REPLICAS_GREEN=3
    if [ -z "$CONFIG_PATH" ]; then
      CONFIG_PATH="./config/blue_green_config.production.json"
    fi
    ;;
  *)
    echo "Error: Invalid environment '$ENVIRONMENT'. Must be 'dev', 'staging', or 'production'."
    exit 1
    ;;
esac

# Ensure namespace exists
echo "Ensuring namespace $NAMESPACE exists..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Load configuration
if [ ! -f "$CONFIG_PATH" ]; then
  echo "Error: Configuration file not found at $CONFIG_PATH"
  exit 1
fi

# Create ConfigMap from configuration
echo "Creating ConfigMap from $CONFIG_PATH..."
kubectl create configmap mcp-blue-green-config \
  --from-file=config.json=$CONFIG_PATH \
  --namespace $NAMESPACE \
  --dry-run=client -o yaml | kubectl apply -f -

# Set image names
BLUE_IMAGE="$REGISTRY/$IMAGE_NAME:$BLUE_TAG"
GREEN_IMAGE="$REGISTRY/$IMAGE_NAME:$GREEN_TAG"

echo "Deploying with images:"
echo "Blue: $BLUE_IMAGE"
echo "Green: $GREEN_IMAGE"

# Apply Kubernetes resources
echo "Applying Kubernetes resources for blue/green deployment..."

# Create temporary directory for rendered templates
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Render Blue Deployment
cat <<EOF > $TEMP_DIR/blue-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-blue
  namespace: $NAMESPACE
  labels:
    app: mcp-server
    variant: blue
spec:
  replicas: $REPLICAS_BLUE
  selector:
    matchLabels:
      app: mcp-server
      variant: blue
  template:
    metadata:
      labels:
        app: mcp-server
        variant: blue
    spec:
      containers:
      - name: mcp-server
        image: $BLUE_IMAGE
        imagePullPolicy: Always
        ports:
        - containerPort: 8080
        volumeMounts:
        - name: config-volume
          mountPath: /app/config
        env:
        - name: DEPLOYMENT_VARIANT
          value: "blue"
        - name: ENVIRONMENT
          value: "$ENVIRONMENT"
        - name: LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            cpu: "100m"
            memory: "256Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 20
      volumes:
      - name: config-volume
        configMap:
          name: mcp-blue-green-config
EOF

# Render Green Deployment
cat <<EOF > $TEMP_DIR/green-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-green
  namespace: $NAMESPACE
  labels:
    app: mcp-server
    variant: green
spec:
  replicas: $REPLICAS_GREEN
  selector:
    matchLabels:
      app: mcp-server
      variant: green
  template:
    metadata:
      labels:
        app: mcp-server
        variant: green
    spec:
      containers:
      - name: mcp-server
        image: $GREEN_IMAGE
        imagePullPolicy: Always
        ports:
        - containerPort: 8080
        volumeMounts:
        - name: config-volume
          mountPath: /app/config
        env:
        - name: DEPLOYMENT_VARIANT
          value: "green"
        - name: ENVIRONMENT
          value: "$ENVIRONMENT"
        - name: LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            cpu: "100m"
            memory: "256Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 20
      volumes:
      - name: config-volume
        configMap:
          name: mcp-blue-green-config
EOF

# Render Blue/Green Proxy Deployment
cat <<EOF > $TEMP_DIR/proxy-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-proxy
  namespace: $NAMESPACE
  labels:
    app: mcp-proxy
spec:
  replicas: 2
  selector:
    matchLabels:
      app: mcp-proxy
  template:
    metadata:
      labels:
        app: mcp-proxy
    spec:
      containers:
      - name: mcp-proxy
        image: $REGISTRY/$IMAGE_NAME:proxy-$IMAGE_SHA
        imagePullPolicy: Always
        ports:
        - containerPort: 8080
          name: http
        - containerPort: 8090
          name: dashboard
        - containerPort: 9100
          name: metrics
        volumeMounts:
        - name: config-volume
          mountPath: /app/config
        env:
        - name: BLUE_SERVICE
          value: "mcp-blue.${NAMESPACE}.svc.cluster.local:8080"
        - name: GREEN_SERVICE
          value: "mcp-green.${NAMESPACE}.svc.cluster.local:8080"
        - name: ENVIRONMENT
          value: "$ENVIRONMENT"
        resources:
          requests:
            cpu: "200m"
            memory: "256Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 20
      volumes:
      - name: config-volume
        configMap:
          name: mcp-blue-green-config
EOF

# Render Services
cat <<EOF > $TEMP_DIR/services.yaml
apiVersion: v1
kind: Service
metadata:
  name: mcp-blue
  namespace: $NAMESPACE
  labels:
    app: mcp-server
    variant: blue
spec:
  selector:
    app: mcp-server
    variant: blue
  ports:
  - port: 8080
    targetPort: 8080
    name: http
---
apiVersion: v1
kind: Service
metadata:
  name: mcp-green
  namespace: $NAMESPACE
  labels:
    app: mcp-server
    variant: green
spec:
  selector:
    app: mcp-server
    variant: green
  ports:
  - port: 8080
    targetPort: 8080
    name: http
---
apiVersion: v1
kind: Service
metadata:
  name: mcp-proxy
  namespace: $NAMESPACE
  labels:
    app: mcp-proxy
spec:
  selector:
    app: mcp-proxy
  ports:
  - port: 8080
    targetPort: 8080
    name: http
  - port: 8090
    targetPort: 8090
    name: dashboard
  - port: 9100
    targetPort: 9100
    name: metrics
EOF

# Apply the rendered templates
if [ "$DRY_RUN" = true ]; then
  echo "Dry run mode: would apply the following configurations"
  cat $TEMP_DIR/blue-deployment.yaml
  cat $TEMP_DIR/green-deployment.yaml
  cat $TEMP_DIR/proxy-deployment.yaml
  cat $TEMP_DIR/services.yaml
else
  kubectl apply -f $TEMP_DIR/blue-deployment.yaml
  kubectl apply -f $TEMP_DIR/green-deployment.yaml
  kubectl apply -f $TEMP_DIR/proxy-deployment.yaml
  kubectl apply -f $TEMP_DIR/services.yaml
  
  echo "Waiting for deployments to be ready..."
  kubectl rollout status deployment/mcp-blue -n $NAMESPACE
  kubectl rollout status deployment/mcp-green -n $NAMESPACE
  kubectl rollout status deployment/mcp-proxy -n $NAMESPACE
fi

echo "Blue/Green infrastructure deployment complete for environment: $ENVIRONMENT"
echo "Deployed blue image: $BLUE_IMAGE"
echo "Deployed green image: $GREEN_IMAGE"
echo "Proxy configured with blue/green endpoints"