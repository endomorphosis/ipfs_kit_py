#!/bin/bash
set -e

# IPFS Kit Kubernetes Deployment Script
# This script deploys IPFS Kit to a Kubernetes cluster

# Default values
NAMESPACE="ipfs-kit"
DEPLOY_MODE="helm"
HELM_RELEASE_NAME="ipfs-kit"
WORKER_REPLICAS=3

# Help function
function show_help {
  echo "IPFS Kit Kubernetes Deployment Script"
  echo ""
  echo "Usage: $0 [options]"
  echo ""
  echo "Options:"
  echo "  --namespace NAME      Kubernetes namespace (default: ipfs-kit)"
  echo "  --manual              Use manual deployment instead of Helm"
  echo "  --release-name NAME   Helm release name (default: ipfs-kit)"
  echo "  --worker-replicas N   Number of worker replicas (default: 3)"
  echo "  --help                Display this help message"
  echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --namespace)
      NAMESPACE="$2"
      shift
      shift
      ;;
    --manual)
      DEPLOY_MODE="manual"
      shift
      ;;
    --release-name)
      HELM_RELEASE_NAME="$2"
      shift
      shift
      ;;
    --worker-replicas)
      WORKER_REPLICAS="$2"
      shift
      shift
      ;;
    --help)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      show_help
      exit 1
      ;;
  esac
done

# Generate cluster secret
CLUSTER_SECRET=$(openssl rand -base64 32)
echo "Generated cluster secret"

# Create namespace if it doesn't exist
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
  echo "Creating namespace: $NAMESPACE"
  kubectl create namespace $NAMESPACE
else
  echo "Namespace $NAMESPACE already exists"
fi

if [ "$DEPLOY_MODE" == "helm" ]; then
  echo "Deploying IPFS Kit using Helm..."
  helm upgrade --install $HELM_RELEASE_NAME ./helm/ipfs-kit \
    --namespace $NAMESPACE \
    --set global.clusterSecret=$CLUSTER_SECRET \
    --set workers.replicas=$WORKER_REPLICAS
  
  echo "Deployment complete!"
  echo "To check status: helm status $HELM_RELEASE_NAME -n $NAMESPACE"
else
  echo "Deploying IPFS Kit using kubectl..."
  
  # Create cluster secret
  kubectl create secret -n $NAMESPACE generic ipfs-cluster-secret \
    --from-literal=cluster-secret=$CLUSTER_SECRET
  
  # Apply Kubernetes manifests
  echo "Applying storage configuration..."
  kubectl apply -f kubernetes/storage.yaml
  
  echo "Applying configuration maps..."
  kubectl apply -f kubernetes/configmap.yaml
  
  echo "Deploying master node..."
  kubectl apply -f kubernetes/master-deployment.yaml
  
  echo "Setting up services..."
  kubectl apply -f kubernetes/services.yaml

  echo "Waiting for master node to be ready..."
  kubectl wait --namespace $NAMESPACE \
    --for=condition=ready pod \
    --selector=app=ipfs-kit,role=master \
    --timeout=300s
  
  echo "Deploying worker nodes..."
  kubectl apply -f kubernetes/worker-deployment.yaml
  
  echo "Deploying leecher node..."
  kubectl apply -f kubernetes/leecher-deployment.yaml
  
  echo "Configuring ingress..."
  kubectl apply -f kubernetes/ingress.yaml

  echo "Setting worker replicas to $WORKER_REPLICAS..."
  kubectl scale statefulset ipfs-worker -n $NAMESPACE --replicas=$WORKER_REPLICAS
  
  echo "Deployment complete!"
  echo "To check status: kubectl get pods -n $NAMESPACE"
fi

echo ""
echo "======================================================================================="
echo "IPFS Kit deployed successfully to namespace: $NAMESPACE"
echo ""
echo "Access the IPFS API:      http://ipfs-api.example.com (configure DNS or ingress)"
echo "Access the IPFS Gateway:  http://ipfs-gateway.example.com (configure DNS or ingress)"
echo ""
echo "Monitor pods with: kubectl get pods -n $NAMESPACE -w"
echo "View logs with:    kubectl logs -f -n $NAMESPACE <pod-name>"
echo "======================================================================================="