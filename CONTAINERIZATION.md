# IPFS Kit Containerization Guide

This document provides comprehensive instructions for deploying IPFS Kit in containerized environments using Docker and Kubernetes. These deployment methods support all three node roles (master, worker, and leecher) with production-ready configurations.

## Table of Contents

- [Docker Deployment](#docker-deployment)
  - [Quick Start](#quick-start)
  - [Building the Image](#building-the-image)
  - [Role-based Configuration](#role-based-configuration)
  - [Docker Compose Deployment](#docker-compose-deployment)
  - [Environment Variables](#environment-variables)
  - [Volumes and Persistence](#volumes-and-persistence)
  - [Security Considerations](#security-considerations)
  - [Troubleshooting](#docker-troubleshooting)

- [Kubernetes Deployment](#kubernetes-deployment)
  - [Quick Start](#kubernetes-quick-start)
  - [Prerequisites](#prerequisites)
  - [Using Helm Chart](#using-helm-chart)
  - [Manual Deployment](#manual-deployment)
  - [Storage Configuration](#storage-configuration)
  - [Scaling Workers](#scaling-workers)
  - [Monitoring and Health Checks](#monitoring-and-health-checks)
  - [Troubleshooting](#kubernetes-troubleshooting)

- [Advanced Topics](#advanced-topics)
  - [Private Networks](#private-networks)
  - [Customizing Cache Settings](#customizing-cache-settings)
  - [Role-Specific Optimizations](#role-specific-optimizations)
  - [Cloud Provider Integration](#cloud-provider-integration)
  - [Production Recommendations](#production-recommendations)
  - [CI/CD Integration](#cicd-integration)

## Docker Deployment

IPFS Kit provides a Docker-based deployment solution with support for all three node roles: master, worker, and leecher.

### Quick Start

The fastest way to get started is using the provided setup script and Docker Compose:

```bash
# Clone the repository if you haven't already
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py

# Run the setup script (creates data directories and generates a cluster secret)
./docker-setup.sh --cluster-secret

# Start all services (master, workers, and leecher)
docker-compose up -d

# Check the status
docker-compose ps
```

### Building the Image

You can build the Docker image manually from the project root:

```bash
# Build the image with a specific tag
docker build -t ipfs-kit-py:0.1.0 .

# Build with build arguments (optional)
docker build \
  --build-arg PYTHON_VERSION=3.10 \
  --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
  -t ipfs-kit-py:latest .
```

The Dockerfile uses a multi-stage build to create a smaller, more secure image:

1. **Build Stage**:
   - Uses Python base image for building
   - Installs only necessary build dependencies
   - Builds the wheel package in an isolated environment

2. **Runtime Stage**:
   - Uses a minimal base image
   - Includes only necessary runtime dependencies
   - Installs the wheel from the build stage
   - Configures a non-root user for better security

3. **Security Features**:
   - Runs as a non-root user (`ipfs`)
   - Includes health check and monitoring
   - Uses the `tini` init system for proper signal handling
   - Minimizes the attack surface with a clean runtime environment

### Role-based Configuration

IPFS Kit containers can operate in three distinct roles, each with optimized settings:

#### Master Role

The master node coordinates the cluster and manages content pinning:

- **Resource Allocation**: Higher CPU and memory for coordination tasks
- **Networking**: Exposes API and gateway ports for external access
- **Storage**: Larger storage allocation for pinned content
- **Features**: Runs IPFS Cluster service in "master" mode

Configuration: `docker/config-master.yaml`

#### Worker Role

Worker nodes process data and participate in the cluster:

- **Resource Allocation**: Balanced CPU and memory for processing tasks
- **Networking**: Internal network access with limited exposure
- **Storage**: Moderate storage allocation focused on processing
- **Features**: Follows the master node for cluster coordination

Configuration: `docker/config-worker.yaml`

#### Leecher Role

Leechers provide lightweight consumption nodes:

- **Resource Allocation**: Minimal CPU and memory requirements
- **Networking**: Gateway exposure for content access
- **Storage**: Small storage allocation with cache-focused settings
- **Features**: Independent operation with limited cluster integration

Configuration: `docker/config-leecher.yaml`

### Docker Compose Deployment

The `docker-compose.yml` file provides a complete multi-node setup:

```yaml
version: '3.8'

services:
  ipfs-master:
    image: ipfs-kit-py:latest
    command: master
    environment:
      - ROLE=master
      - CONFIG_PATH=/etc/ipfs-kit/config.yaml
      - MAX_MEMORY=4G
      - MAX_STORAGE=100G
      - CLUSTER_SECRET=${CLUSTER_SECRET:-}
    volumes:
      - ipfs-master-data:/data
      - ./docker/config-master.yaml:/etc/ipfs-kit/config.yaml:ro
    ports:
      - "4001:4001"  # IPFS swarm
      - "5001:5001"  # IPFS API
      - "8080:8080"  # IPFS gateway
      - "9096:9096"  # IPFS Cluster
```

Key Docker Compose commands:

```bash
# Start all services
docker-compose up -d

# Start only specific services
docker-compose up -d ipfs-master ipfs-worker-1

# Scale specific services
docker-compose up -d --scale ipfs-worker-2=3

# View logs
docker-compose logs -f
docker-compose logs -f ipfs-master

# Stop all services
docker-compose down

# Stop and remove volumes (CAUTION: This deletes all data)
docker-compose down -v
```

### Environment Variables

The following environment variables can be used to customize the deployment:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `ROLE` | Node role (master, worker, leecher) | Yes | From command argument |
| `CONFIG_PATH` | Path to configuration file | No | `/etc/ipfs-kit/default-config.yaml` |
| `MAX_MEMORY` | Maximum memory allocation | No | From config file |
| `MAX_STORAGE` | Maximum storage allocation | No | From config file |
| `MASTER_ADDR` | Address of master node | For workers | None |
| `CLUSTER_SECRET` | Shared secret for cluster security | No | Random (if not set) |
| `SWARM_KEY` | Key for private IPFS networks | No | None (public network) |
| `BOOTSTRAP_PEERS` | Comma-separated list of bootstrap peers | No | Default IPFS bootstraps |
| `API_CORS` | CORS allowed origins for API | No | `*` |
| `GATEWAY_CORS` | CORS allowed origins for gateway | No | `*` |

Example setting environment variables:

```bash
# In docker-compose.yml
environment:
  - ROLE=master
  - MAX_MEMORY=8G
  - MAX_STORAGE=200G
  - CLUSTER_SECRET=${CLUSTER_SECRET}

# On command line
docker run -e MAX_MEMORY=4G -e ROLE=worker ipfs-kit-py
```

### Volumes and Persistence

Data persistence is managed through Docker volumes:

```yaml
volumes:
  ipfs-master-data:    # Master node data
  ipfs-worker-1-data:  # Worker 1 data
  ipfs-worker-2-data:  # Worker 2 data
  ipfs-leecher-data:   # Leecher node data
```

Directory structure inside the volumes:

```
/data/
├── ipfs/                 # IPFS node data
│   ├── blocks/           # Content blocks
│   ├── datastore/        # IPFS datastore
│   ├── config            # IPFS configuration
│   └── cache/            # Tiered cache data
├── ipfs-cluster/         # IPFS Cluster data
│   ├── identity.json     # Cluster identity
│   └── service.json      # Cluster configuration
└── metrics/              # Performance metrics data
```

For production deployments, use named volumes or bind mounts to specific host directories:

```yaml
volumes:
  ipfs-master-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ${PWD}/data/master
```

Backup recommendations:

```bash
# Stop services before backup for consistency
docker-compose stop

# Backup volume data
tar -czf ipfs-backup-$(date +%Y%m%d).tar.gz ./data

# Restart services
docker-compose start
```

### Security Considerations

The IPFS Kit Docker deployment includes several security enhancements:

1. **Non-root User**: Containers run as user `ipfs` (UID 1000) rather than root
2. **Multi-stage Build**: Reduces attack surface by excluding build tools from final image
3. **Health Checks**: Regular health monitoring to detect issues
4. **Resource Limits**: CPU and memory limits prevent resource exhaustion
5. **Secure Configuration**: Sensitive settings use environment variables
6. **Init System**: Uses `tini` for proper signal handling and zombie process reaping
7. **Read-only Mounts**: Configuration files are mounted read-only

Additional security measures to consider:

```yaml
# In docker-compose.yml
security_opt:
  - no-new-privileges:true  # Prevent privilege escalation
  - seccomp:default         # Apply default seccomp profile

# Apply read-only filesystem where possible
read_only: true
tmpfs:
  - /tmp:rw,noexec,nosuid   # Writable /tmp without execution rights
```

### Docker Troubleshooting

Common issues and their solutions:

#### 1. Container fails to start

```bash
# Check container logs
docker-compose logs ipfs-master

# Check if required environment variables are set
docker-compose config

# Verify volume permissions
ls -la ./data/master
```

#### 2. Network connectivity issues

```bash
# Check if containers can reach each other
docker-compose exec ipfs-worker-1 ping ipfs-master

# Verify exposed ports
docker-compose port ipfs-master 5001

# Check network configuration
docker network inspect ipfs-kit-py_ipfs-network
```

#### 3. Performance issues

```bash
# Check resource usage
docker stats

# View resource limits
docker inspect ipfs-master | grep -A 10 "HostConfig"

# Adjust resource limits in docker-compose.yml
```

## Kubernetes Deployment

IPFS Kit includes complete Kubernetes deployment manifests for production environments.

### Kubernetes Quick Start

Use the provided deployment script for easy setup:

```bash
# Clone the repository if you haven't already
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py

# Deploy using Helm (recommended)
./kubernetes-deploy.sh

# Check deployment status
kubectl get pods -n ipfs-kit
```

### Prerequisites

Before deploying to Kubernetes, ensure you have:

- Kubernetes cluster (v1.16+)
- `kubectl` configured to access your cluster
- Helm 3.0+ (for Helm-based deployment)
- Storage classes available for persistent volumes
- Optional: Ingress controller for external access (nginx-ingress, traefik, etc.)

Resource requirements:

| Component | CPU (requests) | Memory (requests) | Storage |
|-----------|----------------|-------------------|---------|
| Master node | 0.5 CPU | 1Gi | 100Gi |
| Worker node | 0.25 CPU | 512Mi | 50Gi |
| Leecher node | 0.1 CPU | 256Mi | 20Gi |

### Using Helm Chart

The easiest way to deploy IPFS Kit on Kubernetes is using the provided Helm chart:

```bash
# Generate a cluster secret
export CLUSTER_SECRET=$(openssl rand -base64 32)

# Install the chart with default values
helm install ipfs-kit ./helm/ipfs-kit \
  --set global.clusterSecret=$CLUSTER_SECRET \
  --namespace ipfs-kit \
  --create-namespace

# Upgrade an existing release
helm upgrade ipfs-kit ./helm/ipfs-kit \
  --set workers.replicas=5 \
  --namespace ipfs-kit

# Uninstall the release
helm uninstall ipfs-kit --namespace ipfs-kit
```

Customize the deployment using a values file:

```yaml
# custom-values.yaml
global:
  clusterSecret: "your-secure-cluster-secret"
  
master:
  resources:
    requests:
      memory: "2Gi"
      cpu: "1"
    limits:
      memory: "8Gi"
      cpu: "4"
  storage:
    size: 200Gi
    
workers:
  replicas: 5
  resources:
    limits:
      memory: "4Gi"
      cpu: "2"
```

Apply your custom values:

```bash
helm install ipfs-kit ./helm/ipfs-kit \
  -f custom-values.yaml \
  --namespace ipfs-kit \
  --create-namespace
```

### Manual Deployment

For manual Kubernetes deployment:

```bash
# Create the namespace
kubectl apply -f kubernetes/namespace.yaml

# Create a cluster secret
kubectl create secret -n ipfs-kit generic ipfs-cluster-secret \
  --from-literal=cluster-secret=$(openssl rand -base64 32)

# Create storage classes
kubectl apply -f kubernetes/storage.yaml

# Apply configuration
kubectl apply -f kubernetes/configmap.yaml

# Deploy master node and wait for it to be ready
kubectl apply -f kubernetes/master-deployment.yaml
kubectl wait --namespace ipfs-kit \
  --for=condition=ready pod \
  --selector=app=ipfs-kit,role=master \
  --timeout=300s

# Create services
kubectl apply -f kubernetes/services.yaml

# Deploy worker nodes
kubectl apply -f kubernetes/worker-deployment.yaml

# Deploy leecher node (optional)
kubectl apply -f kubernetes/leecher-deployment.yaml

# Configure ingress (optional)
kubectl apply -f kubernetes/ingress.yaml
```

For cleanup:

```bash
# Remove all IPFS Kit resources
kubectl delete namespace ipfs-kit
```

### Storage Configuration

Kubernetes deployments use persistent volumes for data storage. The manifests provide optimized storage classes for different node roles:

#### Master Node Storage (SSD)

For master nodes, high-performance SSD storage is recommended:

```yaml
# In storage.yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ipfs-ssd
provisioner: kubernetes.io/gce-pd  # Change for your cloud provider
parameters:
  type: pd-ssd
  fstype: ext4
reclaimPolicy: Retain
allowVolumeExpansion: true
```

#### Worker Node Storage (Standard)

For worker nodes, standard storage provides a better cost-performance balance:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ipfs-hdd
provisioner: kubernetes.io/gce-pd  # Change for your cloud provider
parameters:
  type: pd-standard
  fstype: ext4
reclaimPolicy: Retain
allowVolumeExpansion: true
```

#### Storage Configuration by Cloud Provider

Adjust the storage classes based on your cloud provider:

**AWS EKS**:
```yaml
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp3  # or io1 for higher performance
```

**Google GKE**:
```yaml
provisioner: kubernetes.io/gce-pd
parameters:
  type: pd-ssd  # or pd-standard for lower cost
```

**Azure AKS**:
```yaml
provisioner: kubernetes.io/azure-disk
parameters:
  storageaccounttype: Premium_LRS  # or Standard_LRS
```

### Scaling Workers

Worker nodes can be scaled horizontally to increase processing capacity:

```bash
# Scale worker deployment
kubectl scale statefulset ipfs-worker -n ipfs-kit --replicas=5

# Scale with Helm
helm upgrade ipfs-kit ./helm/ipfs-kit \
  --set workers.replicas=5 \
  --namespace ipfs-kit
```

For automatic scaling based on metrics:

```yaml
# Example HorizontalPodAutoscaler for worker nodes
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ipfs-worker-autoscaler
  namespace: ipfs-kit
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: StatefulSet
    name: ipfs-worker
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### Monitoring and Health Checks

The Kubernetes deployments include comprehensive health monitoring:

#### Liveness Probe

Verifies the node is running properly:

```yaml
livenessProbe:
  exec:
    command:
    - /health-check.sh
  initialDelaySeconds: 60
  periodSeconds: 30
  timeoutSeconds: 10
  failureThreshold: 3
```

#### Readiness Probe

Checks if the node is ready to accept requests:

```yaml
readinessProbe:
  httpGet:
    path: /api/v0/id
    port: 5001
  initialDelaySeconds: 30
  periodSeconds: 15
  timeoutSeconds: 5
```

#### Integration with Monitoring Systems

For advanced monitoring, consider integrating with:

**Prometheus Metrics**:

Add annotations to your pod template:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "5001"
  prometheus.io/path: "/debug/metrics/prometheus"
```

**Grafana Dashboards**:

Create dashboards that visualize:
- Content storage and retrieval rates
- Cache hit/miss ratios
- DHT query performance
- Network bandwidth usage

**ELK Stack Integration**:

Configure filebeat to collect container logs:

```yaml
filebeat.inputs:
- type: container
  paths:
    - /var/log/containers/ipfs-*.log
```

### Kubernetes Troubleshooting

Common Kubernetes deployment issues and solutions:

#### 1. Pods stuck in "Pending" state

```bash
# Check pod status details
kubectl describe pod -n ipfs-kit ipfs-master-0

# Check persistent volume claims
kubectl get pvc -n ipfs-kit

# Verify storage class exists
kubectl get storageclass
```

#### 2. Pod crashes or restarts

```bash
# Check container logs
kubectl logs -n ipfs-kit ipfs-master-0

# Check previous container logs if restarted
kubectl logs -n ipfs-kit ipfs-master-0 --previous

# Check events
kubectl get events -n ipfs-kit
```

#### 3. Service connectivity issues

```bash
# Verify service endpoint
kubectl get endpoints -n ipfs-kit ipfs-master

# Test service from another pod
kubectl run -n ipfs-kit test-connectivity --rm -i --tty --image=busybox -- wget -q -O- http://ipfs-master:5001/api/v0/id

# Check pod network policy
kubectl describe networkpolicy -n ipfs-kit
```

## Advanced Topics

### Private Networks

IPFS Kit supports private IPFS networks for enhanced security and performance:

1. Generate a swarm key:
   ```bash
   # Generate a random key
   od -vN 32 -An -tx1 /dev/urandom | tr -d ' \n' > swarm.key
   
   # The key should look like:
   # /key/swarm/psk/1.0.0/
   # /base16/
   # 7c08753c457a5578a4c4f9678b2c5f0c2794d56556de6489c89d25297bea471e
   ```

2. Provide the key to containers:
   ```bash
   # Docker direct method
   docker run -e SWARM_KEY="$(cat swarm.key)" ipfs-kit-py
   
   # Docker Compose method
   export SWARM_KEY=$(cat swarm.key)
   docker-compose up -d
   
   # Kubernetes method
   kubectl create secret generic ipfs-swarm-key \
     --from-file=swarm.key \
     --namespace ipfs-kit
   ```

3. Configure bootstrap nodes for your private network:
   ```yaml
   # In config.yaml
   peers:
     bootstrap:
       - "/ip4/192.168.1.100/tcp/4001/p2p/QmYourBootstrapNodeID"
   ```

### Customizing Cache Settings

The tiered cache system can be extensively customized for optimal performance:

```yaml
# Master node high-performance cache
cache:
  memory_size: "4GB"
  disk_size: "50GB"
  disk_path: "/data/ipfs/cache"
  eviction_policy: "arc"
  prefetch_enabled: true
  prefetch_threshold: 0.7
  compression_enabled: true
  compression_algorithm: "zstd"
  compression_level: 3

# Worker node processing-focused cache
cache:
  memory_size: "2GB"
  disk_size: "20GB"
  disk_path: "/data/ipfs/cache"
  eviction_policy: "arc"
  prefetch_enabled: false
  worker_optimized: true
  processing_buffer_size: "1GB"

# Leecher node minimal cache
cache:
  memory_size: "512MB"
  disk_size: "5GB"
  disk_path: "/data/ipfs/cache"
  eviction_policy: "lru"
  read_focused: true
  offline_mode_support: true
```

### Role-Specific Optimizations

Each node role can be optimized for its specific purpose:

#### Master Node Optimizations

```yaml
# Network tuning for master
network:
  swarm_connections: 1000
  max_bandwidth_in: "1G"
  max_bandwidth_out: "1G"
  connection_manager:
    high_water: 900
    low_water: 600
  
# DHT server mode
routing:
  type: "dhtserver"
  
# Enhanced replication
cluster:
  replication_factor_min: 2
  replication_factor_max: 5
```

#### Worker Node Optimizations

```yaml
# Processing optimizations
worker:
  task_concurrency: 8
  batch_size: 50
  max_memory_per_task: "512MB"
  
# Network tuning
network:
  swarm_connections: 200
  connection_manager:
    high_water: 300
    low_water: 150
```

#### Leecher Node Optimizations

```yaml
# Minimal resource usage
leecher:
  offline_mode_support: true
  minimal_dht_client: true
  connection_pruning: true
  
# Resource constraints
resources:
  max_memory: "512MB"
  max_storage: "10GB"
  cpu_limit: 0.5
```

### Cloud Provider Integration

IPFS Kit can be integrated with cloud provider services for enhanced capabilities:

#### AWS Integration

```yaml
# S3 storage backend
storage:
  backends:
    - name: "s3"
      enabled: true
      priority: 3
      config:
        region: "us-east-1"
        bucket: "ipfs-content-store"
        credentials:
          access_key: "${AWS_ACCESS_KEY}"
          secret_key: "${AWS_SECRET_KEY}"
```

#### Google Cloud Integration

```yaml
# GCS storage backend
storage:
  backends:
    - name: "gcs"
      enabled: true
      priority: 3
      config:
        bucket: "ipfs-content-store"
        project: "my-gcp-project"
```

#### Azure Integration

```yaml
# Azure Blob storage backend
storage:
  backends:
    - name: "azure"
      enabled: true
      priority: 3
      config:
        container: "ipfs-content"
        account_name: "${AZURE_STORAGE_ACCOUNT}"
        account_key: "${AZURE_STORAGE_KEY}"
```

### Production Recommendations

For production deployments, consider these best practices:

1. **Version Control**:
   - Pin container images to specific versions
   - Version configuration files
   - Use semantic versioning for release management

2. **Resource Planning**:
   - Size nodes based on workload characteristics
   - Allocate appropriate CPU, memory, and storage
   - Consider dedicated nodes for high-traffic operations

3. **High Availability**:
   - Deploy multiple master nodes with leader election
   - Use anti-affinity rules to distribute nodes across hosts
   - Implement automated failover mechanisms

4. **Security**:
   - Use network policies to restrict communication
   - Implement proper secrets management
   - Run regular security scans on images
   - Use read-only file systems where possible

5. **Monitoring and Alerting**:
   - Set up comprehensive monitoring with Prometheus/Grafana
   - Configure alerts for critical metrics
   - Implement log aggregation and analysis
   - Create dashboards for key performance indicators

6. **Backup and Recovery**:
   - Implement regular backup of persistent data
   - Test restoration procedures
   - Document disaster recovery processes

7. **Scaling Strategy**:
   - Develop horizontal scaling plan for worker nodes
   - Implement auto-scaling based on workload
   - Consider geographic distribution for global deployments

### CI/CD Integration

Automating deployment with CI/CD pipelines improves reliability and reduces manual effort:

#### GitHub Actions Workflow

The `.github/workflows/docker-build.yml` file provides CI/CD automation:

```yaml
name: Build and Publish Docker Image

on:
  push:
    branches: [ main, master ]
    tags: [ 'v*' ]
  pull_request:
    branches: [ main, master ]

jobs:
  build:
    name: Build Docker Image
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
        
      # Additional steps for testing, building, and publishing
```

This workflow:
1. Builds the Docker image on code changes
2. Runs tests to verify functionality
3. Publishes images to a container registry
4. Packages Helm charts for distribution

Additional CI/CD integrations you might want to implement:

```yaml
# Kubernetes deployment job
deploy-to-k8s:
  needs: build
  if: github.ref == 'refs/heads/main'
  runs-on: ubuntu-latest
  steps:
    - name: Set up kubectl
      uses: azure/setup-kubectl@v3
      
    - name: Deploy to Kubernetes
      run: |
        kubectl apply -f kubernetes/ --namespace ipfs-kit
```

Recommended CI/CD best practices:
- Implement automated testing for containers
- Use semantic versioning for image tags
- Create deployment environments (dev, staging, production)
- Automate security scanning with tools like Trivy or Clair
- Set up notifications for build and deployment status