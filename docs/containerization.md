# Containerization and Deployment Guide

This guide provides comprehensive instructions for containerizing and deploying IPFS Kit in various environments, from single-node deployments to distributed cluster architectures on Kubernetes.

## Table of Contents

1. [Introduction](#introduction)
2. [Docker Containerization](#docker-containerization)
   - [Base Dockerfile](#base-dockerfile)
   - [Role-Specific Images](#role-specific-images)
   - [Environment Variables](#environment-variables)
   - [Volume Configuration](#volume-configuration)
   - [Multi-Stage Builds](#multi-stage-builds)
3. [Docker Compose Deployment](#docker-compose-deployment)
   - [Single-Node Setup](#single-node-setup)
   - [Multi-Node Setup](#multi-node-setup)
   - [Service Dependencies](#service-dependencies)
4. [Kubernetes Deployment](#kubernetes-deployment)
   - [StatefulSet for Master Node](#statefulset-for-master-node)
   - [Deployment for Worker Nodes](#deployment-for-worker-nodes)
   - [Deployment for Leecher Nodes](#deployment-for-leecher-nodes)
   - [Services and Networking](#services-and-networking)
   - [ConfigMaps and Secrets](#configmaps-and-secrets)
   - [Persistent Volume Claims](#persistent-volume-claims)
5. [Scaling Considerations](#scaling-considerations)
   - [Resource Requirements](#resource-requirements)
   - [Network Configuration](#network-configuration)
   - [Horizontal Scaling](#horizontal-scaling)
   - [Vertical Scaling](#vertical-scaling)
6. [Monitoring and Management](#monitoring-and-management)
   - [Healthchecks](#healthchecks)
   - [Metrics Collection](#metrics-collection)
   - [Log Management](#log-management)
   - [Backup Strategies](#backup-strategies)
7. [Production Deployment Checklist](#production-deployment-checklist)
8. [Troubleshooting](#troubleshooting)

## Introduction

IPFS Kit is designed to operate in different deployment models, from standalone instances to distributed clusters. This guide covers containerization and deployment strategies for various scenarios.

The role-based architecture (master/worker/leecher) is a key consideration when planning your deployment:

- **Master Node**: Orchestrates the cluster, maintains comprehensive metadata, and provides coordination
- **Worker Nodes**: Process content and contribute to the network, specialized for computation
- **Leecher Nodes**: Consume content with minimal resource contribution, optimized for edge devices

## Docker Containerization

IPFS Kit can be containerized to ensure consistent deployment across environments. This section covers various approaches for creating optimal Docker images.

### Base Dockerfile

Here's a basic Dockerfile for IPFS Kit:

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    jq \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY . /app/

# Install dependencies
RUN pip install -e .

# Create necessary directories
RUN mkdir -p /data/ipfs /data/ipfs-cluster

# Set environment variables
ENV IPFS_PATH=/data/ipfs
ENV IPFS_CLUSTER_PATH=/data/ipfs-cluster

# Expose ports for IPFS daemon, API, gateway, and Cluster
EXPOSE 4001 5001 8080 9094 9095 9096

# Entry point script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
# Default command starts the daemon based on role
CMD ["master"]
```

Create the entrypoint script at `docker/entrypoint.sh`:

```bash
#!/bin/bash
set -e

ROLE=${1:-master}
echo "Starting IPFS Kit with role: $ROLE"

# Initialize IPFS if not already initialized
if [ ! -f "$IPFS_PATH/config" ]; then
    echo "Initializing IPFS..."
    python -m ipfs_kit_py.install_ipfs init
fi

# Start IPFS Kit with the specified role
if [ "$ROLE" = "master" ]; then
    echo "Starting as master node..."
    python -m ipfs_kit_py.ipfs_kit_py --role master --resources '{"max_memory": "4G", "max_storage": "500G"}' --api
elif [ "$ROLE" = "worker" ]; then
    echo "Starting as worker node..."
    # If MASTER_NODE is set, connect to it
    if [ -n "$MASTER_NODE" ]; then
        echo "Connecting to master node: $MASTER_NODE"
        MASTER_ARG="--master $MASTER_NODE"
    else
        MASTER_ARG=""
    fi
    python -m ipfs_kit_py.ipfs_kit_py --role worker $MASTER_ARG --resources '{"max_memory": "2G", "max_storage": "100G"}' --api
elif [ "$ROLE" = "leecher" ]; then
    echo "Starting as leecher node..."
    # If MASTER_NODE is set, connect to it
    if [ -n "$MASTER_NODE" ]; then
        echo "Connecting to master node: $MASTER_NODE"
        MASTER_ARG="--master $MASTER_NODE"
    else
        MASTER_ARG=""
    fi
    python -m ipfs_kit_py.ipfs_kit_py --role leecher $MASTER_ARG --resources '{"max_memory": "1G", "max_storage": "10G"}' --api
else
    echo "Unknown role: $ROLE"
    echo "Valid roles: master, worker, leecher"
    exit 1
fi
```

### Role-Specific Images

For production deployments, consider building role-specific images:

#### Master Node Dockerfile

```dockerfile
FROM ipfs-kit-base:latest

# Install additional tools for master node
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy master-specific configuration
COPY config/master_config.json /app/config/config.json

# Expose additional ports for master services
EXPOSE 9096

# Set default role to master
CMD ["master"]
```

#### Worker Node Dockerfile

```dockerfile
FROM ipfs-kit-base:latest

# Install computational libraries
RUN apt-get update && apt-get install -y \
    python3-numpy \
    python3-scipy \
    python3-sklearn \
    && rm -rf /var/lib/apt/lists/*

# For GPU support (if needed)
# RUN pip install torch==2.0.1 torchvision==0.15.2

# Copy worker-specific configuration
COPY config/worker_config.json /app/config/config.json

# Set default role to worker
CMD ["worker"]
```

#### Leecher Node Dockerfile

```dockerfile
FROM ipfs-kit-base:latest

# Minimal installation for leecher nodes
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir ipfs_kit_py[minimal]

# Copy leecher-specific configuration
COPY config/leecher_config.json /app/config/config.json

# Set default role to leecher
CMD ["leecher"]
```

### Environment Variables

Configure IPFS Kit using environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `IPFS_PATH` | Path to IPFS config directory | `/data/ipfs` |
| `IPFS_CLUSTER_PATH` | Path to IPFS Cluster config directory | `/data/ipfs-cluster` |
| `IPFS_KIT_ROLE` | Node role (master, worker, leecher) | `leecher` |
| `IPFS_KIT_API_PORT` | Port for the API server | `8000` |
| `IPFS_KIT_API_HOST` | Host for the API server | `0.0.0.0` |
| `IPFS_KIT_LOG_LEVEL` | Logging level | `INFO` |
| `IPFS_KIT_CONFIG_FILE` | Path to config file | `/app/config/config.json` |
| `MASTER_NODE` | Address of master node (for worker/leecher) | `""` |
| `MAX_MEMORY` | Maximum memory allocation | `1G` |
| `MAX_STORAGE` | Maximum storage allocation | `10G` |

### Volume Configuration

Persistent data should be stored in volumes:

```dockerfile
VOLUME ["/data/ipfs", "/data/ipfs-cluster"]
```

In docker-compose or Kubernetes, map these volumes to persistent storage.

### Multi-Stage Builds

For optimized images, use multi-stage builds:

```dockerfile
# Build stage
FROM python:3.11 AS builder

WORKDIR /build
COPY . /build/

# Install build dependencies
RUN pip install --no-cache-dir build wheel
RUN python -m build

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy built package from builder stage
COPY --from=builder /build/dist/*.whl /app/

# Install the package
RUN pip install --no-cache-dir /app/*.whl

# Create data directories
RUN mkdir -p /data/ipfs /data/ipfs-cluster

# Set environment variables
ENV IPFS_PATH=/data/ipfs
ENV IPFS_CLUSTER_PATH=/data/ipfs-cluster

# Expose ports
EXPOSE 4001 5001 8080 9094 9095 9096

# Entry point script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["leecher"]
```

## Docker Compose Deployment

### Single-Node Setup

For a single-node deployment with all components:

```yaml
version: '3.8'

services:
  ipfs-kit:
    image: ipfs-kit:latest
    container_name: ipfs-kit
    environment:
      - IPFS_KIT_ROLE=master
      - IPFS_KIT_API_PORT=8000
      - IPFS_KIT_LOG_LEVEL=INFO
      - MAX_MEMORY=4G
      - MAX_STORAGE=500G
    ports:
      - "4001:4001"  # IPFS swarm
      - "5001:5001"  # IPFS API
      - "8080:8080"  # IPFS gateway
      - "9094:9094"  # IPFS Cluster API
      - "9095:9095"  # IPFS Cluster proxy
      - "9096:9096"  # IPFS Cluster swarm
      - "8000:8000"  # IPFS Kit API
    volumes:
      - ipfs-data:/data/ipfs
      - ipfs-cluster-data:/data/ipfs-cluster
      - ./config:/app/config
    restart: unless-stopped
    command: master

volumes:
  ipfs-data:
  ipfs-cluster-data:
```

### Multi-Node Setup

For a multi-node deployment:

```yaml
version: '3.8'

services:
  ipfs-master:
    image: ipfs-kit:latest
    container_name: ipfs-master
    environment:
      - IPFS_KIT_ROLE=master
      - IPFS_KIT_API_PORT=8000
      - MAX_MEMORY=4G
      - MAX_STORAGE=500G
    ports:
      - "4001:4001"  # IPFS swarm
      - "5001:5001"  # IPFS API
      - "8080:8080"  # IPFS gateway
      - "9096:9096"  # IPFS Cluster swarm
      - "8000:8000"  # IPFS Kit API
    volumes:
      - ipfs-master-data:/data/ipfs
      - ipfs-master-cluster:/data/ipfs-cluster
      - ./config/master:/app/config
    restart: unless-stopped
    command: master
    networks:
      - ipfs-network

  ipfs-worker-1:
    image: ipfs-kit:latest
    container_name: ipfs-worker-1
    environment:
      - IPFS_KIT_ROLE=worker
      - MASTER_NODE=ipfs-master:9096
      - MAX_MEMORY=2G
      - MAX_STORAGE=100G
    depends_on:
      - ipfs-master
    ports:
      - "4101:4001"  # IPFS swarm
      - "5101:5001"  # IPFS API
      - "8180:8080"  # IPFS gateway
    volumes:
      - ipfs-worker1-data:/data/ipfs
      - ipfs-worker1-cluster:/data/ipfs-cluster
      - ./config/worker:/app/config
    restart: unless-stopped
    command: worker
    networks:
      - ipfs-network

  ipfs-worker-2:
    image: ipfs-kit:latest
    container_name: ipfs-worker-2
    environment:
      - IPFS_KIT_ROLE=worker
      - MASTER_NODE=ipfs-master:9096
      - MAX_MEMORY=2G
      - MAX_STORAGE=100G
    depends_on:
      - ipfs-master
    ports:
      - "4102:4001"  # IPFS swarm
      - "5102:5001"  # IPFS API
      - "8182:8080"  # IPFS gateway
    volumes:
      - ipfs-worker2-data:/data/ipfs
      - ipfs-worker2-cluster:/data/ipfs-cluster
      - ./config/worker:/app/config
    restart: unless-stopped
    command: worker
    networks:
      - ipfs-network

  ipfs-leecher:
    image: ipfs-kit:latest
    container_name: ipfs-leecher
    environment:
      - IPFS_KIT_ROLE=leecher
      - MASTER_NODE=ipfs-master:9096
      - MAX_MEMORY=1G
      - MAX_STORAGE=10G
    depends_on:
      - ipfs-master
    ports:
      - "4103:4001"  # IPFS swarm
      - "5103:5001"  # IPFS API
      - "8183:8080"  # IPFS gateway
    volumes:
      - ipfs-leecher-data:/data/ipfs
      - ./config/leecher:/app/config
    restart: unless-stopped
    command: leecher
    networks:
      - ipfs-network

volumes:
  ipfs-master-data:
  ipfs-master-cluster:
  ipfs-worker1-data:
  ipfs-worker1-cluster:
  ipfs-worker2-data:
  ipfs-worker2-cluster:
  ipfs-leecher-data:

networks:
  ipfs-network:
    driver: bridge
```

### Service Dependencies

For production deployments, you might need additional services:

```yaml
version: '3.8'

services:
  # ... IPFS Kit services from above ...

  prometheus:
    image: prom/prometheus:v2.45.0
    container_name: prometheus
    volumes:
      - ./prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    ports:
      - "9090:9090"
    restart: unless-stopped
    networks:
      - ipfs-network

  grafana:
    image: grafana/grafana:10.0.3
    container_name: grafana
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    ports:
      - "3000:3000"
    restart: unless-stopped
    networks:
      - ipfs-network

volumes:
  # ... IPFS Kit volumes from above ...
  prometheus_data:
  grafana_data:
```

## Kubernetes Deployment

For production deployments, Kubernetes provides robust orchestration.

### StatefulSet for Master Node

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: ipfs-master
spec:
  serviceName: "ipfs-master"
  replicas: 1  # Only one master per cluster
  selector:
    matchLabels:
      app: ipfs-master
  template:
    metadata:
      labels:
        app: ipfs-master
    spec:
      containers:
      - name: ipfs-master
        image: ipfs-kit:latest
        args: ["master"]
        ports:
        - containerPort: 4001
          name: swarm
        - containerPort: 5001
          name: api
        - containerPort: 8080
          name: gateway
        - containerPort: 9096
          name: cluster
        - containerPort: 8000
          name: ipfs-kit-api
        env:
        - name: IPFS_PATH
          value: /data/ipfs
        - name: IPFS_CLUSTER_PATH
          value: /data/ipfs-cluster
        - name: IPFS_KIT_ROLE
          value: master
        - name: MAX_MEMORY
          value: "4G"
        - name: MAX_STORAGE
          value: "500G"
        volumeMounts:
        - name: ipfs-storage
          mountPath: /data
        - name: config-volume
          mountPath: /app/config
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /health
            port: ipfs-kit-api
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: ipfs-kit-api
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: config-volume
        configMap:
          name: ipfs-kit-config
  volumeClaimTemplates:
  - metadata:
      name: ipfs-storage
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 500Gi
```

### Deployment for Worker Nodes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ipfs-worker
spec:
  replicas: 3  # Adjust based on processing needs
  selector:
    matchLabels:
      app: ipfs-worker
  template:
    metadata:
      labels:
        app: ipfs-worker
    spec:
      containers:
      - name: ipfs-worker
        image: ipfs-kit:latest
        args: ["worker"]
        ports:
        - containerPort: 4001
          name: swarm
        - containerPort: 5001
          name: api
        - containerPort: 8080
          name: gateway
        env:
        - name: IPFS_PATH
          value: /data/ipfs
        - name: IPFS_CLUSTER_PATH
          value: /data/ipfs-cluster
        - name: IPFS_KIT_ROLE
          value: worker
        - name: MASTER_NODE
          value: "ipfs-master-0.ipfs-master:9096"
        - name: MAX_MEMORY
          value: "2G"
        - name: MAX_STORAGE
          value: "100G"
        volumeMounts:
        - name: ipfs-worker-storage
          mountPath: /data
        - name: config-volume
          mountPath: /app/config
        resources:
          requests:
            memory: "1Gi"
            cpu: "1"
          limits:
            memory: "2Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: config-volume
        configMap:
          name: ipfs-kit-config
      - name: ipfs-worker-storage
        persistentVolumeClaim:
          claimName: ipfs-worker-storage
```

### Deployment for Leecher Nodes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ipfs-leecher
spec:
  replicas: 1  # Adjust as needed
  selector:
    matchLabels:
      app: ipfs-leecher
  template:
    metadata:
      labels:
        app: ipfs-leecher
    spec:
      containers:
      - name: ipfs-leecher
        image: ipfs-kit:latest
        args: ["leecher"]
        ports:
        - containerPort: 4001
          name: swarm
        - containerPort: 5001
          name: api
        - containerPort: 8080
          name: gateway
        env:
        - name: IPFS_PATH
          value: /data/ipfs
        - name: IPFS_KIT_ROLE
          value: leecher
        - name: MASTER_NODE
          value: "ipfs-master-0.ipfs-master:9096"
        - name: MAX_MEMORY
          value: "1G"
        - name: MAX_STORAGE
          value: "10G"
        volumeMounts:
        - name: ipfs-leecher-storage
          mountPath: /data
        - name: config-volume
          mountPath: /app/config
        resources:
          requests:
            memory: "512Mi"
            cpu: "0.5"
          limits:
            memory: "1Gi"
            cpu: "1"
      volumes:
      - name: config-volume
        configMap:
          name: ipfs-kit-config
      - name: ipfs-leecher-storage
        persistentVolumeClaim:
          claimName: ipfs-leecher-storage
```

### Services and Networking

```yaml
apiVersion: v1
kind: Service
metadata:
  name: ipfs-master
spec:
  selector:
    app: ipfs-master
  ports:
  - name: swarm
    port: 4001
    targetPort: swarm
  - name: api
    port: 5001
    targetPort: api
  - name: gateway
    port: 8080
    targetPort: gateway
  - name: cluster
    port: 9096
    targetPort: cluster
  - name: ipfs-kit-api
    port: 8000
    targetPort: ipfs-kit-api
  clusterIP: None  # Headless service for StatefulSet
---
apiVersion: v1
kind: Service
metadata:
  name: ipfs-api
spec:
  selector:
    app: ipfs-master
  ports:
  - name: api
    port: 5001
    targetPort: api
  - name: gateway
    port: 8080
    targetPort: gateway
  type: ClusterIP
---
apiVersion: v1
kind: Service
metadata:
  name: ipfs-gateway
spec:
  selector:
    app: ipfs-master
  ports:
  - name: gateway
    port: 80
    targetPort: gateway
  type: LoadBalancer  # Expose gateway to external traffic
```

### ConfigMaps and Secrets

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ipfs-kit-config
data:
  config.json: |
    {
      "storage": {
        "tiers": {
          "memory": {
            "size_limit": "1GB",
            "eviction_policy": "LRU"
          },
          "disk": {
            "size_limit": "100GB",
            "path": "/data/ipfs/cache"
          }
        }
      },
      "networking": {
        "bootstrap_nodes": [
          "/dns4/node0.example.com/tcp/4001/p2p/QmNode0",
          "/dns4/node1.example.com/tcp/4001/p2p/QmNode1"
        ],
        "swarm_connection_limit": 1000
      },
      "api": {
        "enable": true,
        "port": 8000,
        "host": "0.0.0.0",
        "cors_origins": ["*"]
      },
      "logging": {
        "level": "INFO",
        "format": "json"
      }
    }
---
apiVersion: v1
kind: Secret
metadata:
  name: ipfs-cluster-secret
type: Opaque
data:
  cluster-secret: c2VjcmV0LWtleS1mb3ItdGVzdGluZy1vbmx5  # base64 encoded
```

### Persistent Volume Claims

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ipfs-worker-storage
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ipfs-leecher-storage
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

### Production-Ready Helm Charts

For production Kubernetes deployments, Helm charts provide a more maintainable and configurable approach. Here's a guide to creating Helm charts for IPFS Kit:

#### Chart Structure

Create this directory structure for your Helm chart:

```
ipfs-kit/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── configmap.yaml
│   ├── master-statefulset.yaml
│   ├── worker-deployment.yaml
│   ├── leecher-deployment.yaml
│   ├── services.yaml
│   ├── secrets.yaml
│   └── pvc.yaml
└── charts/
    └── [subcharts if needed]
```

#### Chart.yaml Example

```yaml
apiVersion: v2
name: ipfs-kit
description: A Helm chart for IPFS Kit with master/worker/leecher architecture
type: application
version: 0.1.0
appVersion: "1.0.0"
maintainers:
  - name: Your Name
    email: your.email@example.com
dependencies:
  - name: prometheus
    version: "15.10.1"
    repository: "https://prometheus-community.github.io/helm-charts"
    condition: prometheus.enabled
```

#### values.yaml Example

```yaml
# Global settings
global:
  environment: production
  clusterSecret: ""  # Set this via --set global.clusterSecret=xxx or via Secrets
  storageClass: standard

# Master node configuration
master:
  enabled: true
  replicas: 1
  image:
    repository: username/ipfs-kit
    tag: latest
    pullPolicy: IfNotPresent
  resources:
    requests:
      cpu: 1
      memory: 2Gi
    limits:
      cpu: 2
      memory: 4Gi
  persistence:
    enabled: true
    size: 500Gi
  service:
    type: ClusterIP
    annotations: {}
  configuration:
    maxMemory: 4G
    maxStorage: 500G
    apiPort: 8000
    gatewayPort: 8080
    swarmPort: 4001
    clusterPort: 9096

# Worker node configuration
worker:
  enabled: true
  replicas: 3
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 80
  image:
    repository: username/ipfs-kit
    tag: latest
    pullPolicy: IfNotPresent
  resources:
    requests:
      cpu: 1
      memory: 1Gi
    limits:
      cpu: 2
      memory: 2Gi
  persistence:
    enabled: true
    size: 100Gi
  configuration:
    maxMemory: 2G
    maxStorage: 100G

# Leecher node configuration
leecher:
  enabled: true
  replicas: 1
  image:
    repository: username/ipfs-kit
    tag: latest
    pullPolicy: IfNotPresent
  resources:
    requests:
      cpu: 0.5
      memory: 512Mi
    limits:
      cpu: 1
      memory: 1Gi
  persistence:
    enabled: true
    size: 10Gi
  configuration:
    maxMemory: 1G
    maxStorage: 10G

# Monitoring
prometheus:
  enabled: true

# Ingress configuration
ingress:
  enabled: false
  className: nginx
  annotations: {}
  hosts:
    - host: ipfs-kit.example.com
      paths:
        - path: /
          pathType: Prefix
  tls: []
```

#### Example Template: Master StatefulSet

Here's a snippet from `templates/master-statefulset.yaml`:

```yaml
{{- if .Values.master.enabled }}
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: {{ include "ipfs-kit.fullname" . }}-master
  labels:
    {{- include "ipfs-kit.labels" . | nindent 4 }}
    app.kubernetes.io/component: master
spec:
  serviceName: {{ include "ipfs-kit.fullname" . }}-master
  replicas: {{ .Values.master.replicas }}
  selector:
    matchLabels:
      {{- include "ipfs-kit.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: master
  template:
    metadata:
      labels:
        {{- include "ipfs-kit.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/component: master
    spec:
      containers:
        - name: ipfs-master
          image: "{{ .Values.master.image.repository }}:{{ .Values.master.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.master.image.pullPolicy }}
          args: ["master"]
          ports:
            - name: swarm
              containerPort: {{ .Values.master.configuration.swarmPort }}
            - name: api
              containerPort: 5001
            - name: gateway
              containerPort: {{ .Values.master.configuration.gatewayPort }}
            - name: cluster
              containerPort: {{ .Values.master.configuration.clusterPort }}
            - name: ipfs-kit-api
              containerPort: {{ .Values.master.configuration.apiPort }}
          env:
            - name: IPFS_PATH
              value: /data/ipfs
            - name: IPFS_CLUSTER_PATH
              value: /data/ipfs-cluster
            - name: IPFS_KIT_ROLE
              value: master
            - name: MAX_MEMORY
              value: {{ .Values.master.configuration.maxMemory | quote }}
            - name: MAX_STORAGE
              value: {{ .Values.master.configuration.maxStorage | quote }}
            - name: CLUSTER_SECRET
              valueFrom:
                secretKeyRef:
                  name: {{ include "ipfs-kit.fullname" . }}-cluster-secret
                  key: cluster-secret
          volumeMounts:
            - name: ipfs-storage
              mountPath: /data
            - name: config-volume
              mountPath: /app/config
          resources:
            {{- toYaml .Values.master.resources | nindent 12 }}
          livenessProbe:
            httpGet:
              path: /health
              port: ipfs-kit-api
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: ipfs-kit-api
            initialDelaySeconds: 5
            periodSeconds: 5
      volumes:
        - name: config-volume
          configMap:
            name: {{ include "ipfs-kit.fullname" . }}-config
  {{- if .Values.master.persistence.enabled }}
  volumeClaimTemplates:
    - metadata:
        name: ipfs-storage
      spec:
        accessModes: [ "ReadWriteOnce" ]
        storageClassName: {{ .Values.global.storageClass }}
        resources:
          requests:
            storage: {{ .Values.master.persistence.size }}
  {{- end }}
{{- end }}
```

#### Deploying with Helm

To deploy the IPFS Kit Helm chart:

```bash
# Add cluster secret from command line
helm install ipfs-kit ./ipfs-kit \
  --set global.clusterSecret=$(openssl rand -hex 32) \
  --namespace ipfs-kit \
  --create-namespace

# Or use a values file
helm install ipfs-kit ./ipfs-kit \
  -f my-values.yaml \
  --namespace ipfs-kit \
  --create-namespace
```

For production environments, consider using Helm's secrets management or external secrets providers like HashiCorp Vault, AWS Secrets Manager, or Kubernetes External Secrets.

## Scaling Considerations

### Resource Requirements

| Node Type | CPU | Memory | Storage | Network |
|-----------|-----|--------|---------|---------|
| Master | 2-4 cores | 4-8 GB | 500+ GB | High throughput, stable |
| Worker | 2-8 cores | 2-16 GB | 100-500 GB | Medium throughput |
| Leecher | 0.5-2 cores | 0.5-2 GB | 10-50 GB | Variable, can be intermittent |

For ML workloads, worker nodes may require additional resources:
- GPU access for embedding generation or model training
- Higher memory allocation (8-32 GB)
- More storage for large models or datasets

### Network Configuration

#### IPFS Swarm Port Exposure

Ensure proper connectivity for the IPFS swarm:

1. **Port Forwarding**: For non-NAT traversable networks, ensure port 4001 (TCP/UDP) is forwarded to the master node
2. **Security Groups**: Allow traffic on ports 4001 (swarm), 5001 (API), 8080 (gateway), and 9096 (cluster)
3. **External Connectivity**: For public IPFS nodes, make sure the swarm port is accessible from the internet

#### Cluster Communication

For IPFS Cluster communication:
1. **Private Network**: Cluster peers communicate over a separate private network
2. **Secret Key**: All peers share a common secret key
3. **Port**: Cluster communications use port 9096 by default

#### NAT Traversal

When deploying behind firewalls or NATs:
1. **Relay Nodes**: Use public relay nodes to facilitate connections
2. **Circuit Relay**: Configure circuit relay to enable connectivity between private nodes
3. **AutoNAT**: Enable AutoNAT for automatic NAT detection and mitigation

### Horizontal Scaling

Worker nodes are designed for horizontal scaling:

1. **Stateless Design**: Worker nodes can be added or removed without disrupting the cluster
2. **Automated Discovery**: New workers automatically join the cluster through the master node
3. **Workload Distribution**: Tasks are automatically distributed across available workers

For Kubernetes deployments, configure the HorizontalPodAutoscaler:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ipfs-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ipfs-worker
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 80
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Vertical Scaling

For master nodes, vertical scaling is often more appropriate:

1. **Resource Allocation**: Increase CPU, memory, and storage resources
2. **Storage Optimization**: Use high-performance SSDs for the datastore
3. **Connection Limits**: Adjust `Swarm.ConnMgr` settings to handle more connections

### GPU Support for ML Workloads

IPFS Kit's AI/ML integration capabilities may benefit from GPU acceleration, especially for worker nodes that perform embedding generation, vector search, or model training.

#### Docker with GPU Support

To enable GPU support in Docker:

```dockerfile
# GPU-enabled worker node
FROM nvidia/cuda:11.8.0-base-ubuntu22.04

# System dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install IPFS Kit with ML dependencies
COPY . /app/
RUN pip3 install -e ".[ml]"

# Create necessary directories
RUN mkdir -p /data/ipfs /data/ipfs-cluster

# Set environment variables
ENV IPFS_PATH=/data/ipfs
ENV IPFS_CLUSTER_PATH=/data/ipfs-cluster
ENV IPFS_KIT_ROLE=worker

# Entry point script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["worker"]
```

#### Kubernetes GPU Configuration

For Kubernetes, update the worker deployment to request GPU resources:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ipfs-worker-gpu
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ipfs-worker-gpu
  template:
    metadata:
      labels:
        app: ipfs-worker-gpu
    spec:
      containers:
      - name: ipfs-worker
        image: ipfs-kit-gpu:latest
        args: ["worker"]
        resources:
          limits:
            nvidia.com/gpu: 1  # Request 1 GPU
          requests:
            memory: "4Gi"
            cpu: "2"
        env:
        - name: IPFS_KIT_ROLE
          value: worker
        - name: USE_GPU
          value: "true"
        - name: MASTER_NODE
          value: "ipfs-master-0.ipfs-master:9096"
```

#### Helm Configuration for GPU Workers

In your Helm values, configure GPU support for workers:

```yaml
worker:
  # Standard workers configuration...
  
# GPU-enabled workers
gpuWorker:
  enabled: true
  replicas: 2
  image:
    repository: username/ipfs-kit-gpu
    tag: latest
    pullPolicy: IfNotPresent
  resources:
    requests:
      cpu: 2
      memory: 4Gi
    limits:
      cpu: 4
      memory: 8Gi
      nvidia.com/gpu: 1
  nodeSelector:
    cloud.google.com/gke-accelerator: nvidia-tesla-t4  # For GKE
  tolerations:
    - key: "nvidia.com/gpu"
      operator: "Exists"
      effect: "NoSchedule"
  configuration:
    maxMemory: 8G
    maxStorage: 200G
    useGpu: true
```

#### Performance Considerations for GPU Workloads

1. **Memory Management**: Ensure sufficient system memory for both IPFS and GPU operations
2. **Batch Processing**: Configure processing batch sizes based on GPU memory
3. **Storage I/O**: Use high-performance storage to prevent I/O bottlenecks for model loading
4. **Worker Specialization**: Consider dedicated GPU workers for specific ML tasks
5. **Multi-GPU Scaling**: For large-scale ML operations, configure multiple GPUs per node if available

## Monitoring and Management

### Healthchecks

IPFS Kit provides built-in health checks:

- **API Endpoint**: `/health` returns status of all components
- **Component Checks**: Individual checks for IPFS daemon, Cluster, and storage tiers
- **Readiness Probe**: `/ready` indicates when the service is fully operational

For Docker Compose:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

For Kubernetes:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

### Metrics Collection

IPFS Kit exposes Prometheus metrics:

- **Endpoint**: `/metrics` provides performance and operational metrics
- **Dimensions**: Metrics are tagged with node role and component
- **Categories**: Storage, network, cache, operations, errors

Prometheus configuration example:

```yaml
scrape_configs:
  - job_name: 'ipfs-kit'
    scrape_interval: 15s
    metrics_path: '/metrics'
    static_configs:
      - targets: ['ipfs-master:8000', 'ipfs-worker-1:8000', 'ipfs-worker-2:8000']
```

### Log Management

Centralized logging configuration:

- **JSON Format**: Structured logs for easier parsing
- **Log Levels**: Configurable verbosity (DEBUG, INFO, WARNING, ERROR)
- **Correlation IDs**: Track operations across components with correlation identifiers

For Kubernetes, use a logging sidecar:

```yaml
- name: logging-sidecar
  image: fluent/fluent-bit:1.9
  volumeMounts:
  - name: log-volume
    mountPath: /logs
  - name: fluent-bit-config
    mountPath: /fluent-bit/etc/
```

### Backup Strategies

Regular backups are essential:

1. **Configuration Backup**: Periodically back up IPFS and Cluster config
2. **Pinset Backup**: Export the list of pinned CIDs
3. **Datastore Backup**: Take snapshots of the IPFS datastore when idle
4. **Metadata Index Backup**: Export the Arrow metadata index periodically

Example backup script:

```bash
#!/bin/bash
# Backup script for IPFS Kit

# Set backup destination
BACKUP_DIR="/backup/ipfs-kit/$(date +%Y-%m-%d)"
mkdir -p "$BACKUP_DIR"

# Backup IPFS config
cp -r "$IPFS_PATH/config" "$BACKUP_DIR/ipfs_config"

# Backup Cluster config
cp -r "$IPFS_CLUSTER_PATH/service.json" "$BACKUP_DIR/cluster_service.json"
cp -r "$IPFS_CLUSTER_PATH/identity.json" "$BACKUP_DIR/cluster_identity.json"

# Export pinset
ipfs pin ls --type=recursive | awk '{print $1}' > "$BACKUP_DIR/pinset.txt"

# Export metadata index
curl -X GET "http://localhost:8000/api/v0/metadata/export" -o "$BACKUP_DIR/metadata_index.parquet"

# Compress backup
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"

# Clean up
rm -rf "$BACKUP_DIR"

echo "Backup completed: $BACKUP_DIR.tar.gz"
```

## Production Deployment Checklist

Before deploying to production, verify:

1. **Security**:
   - [x] Secure API endpoints with TLS
   - [x] Set appropriate file permissions
   - [x] Use secrets management for sensitive data
   - [x] Configure network security policies
   - [x] Enable authentication for APIs

2. **Performance**:
   - [x] Configure appropriate resource limits
   - [x] Tune GC parameters for IPFS daemon
   - [x] Optimize connection manager settings
   - [x] Configure tiered storage appropriately
   - [x] Set up monitoring alerts for performance issues

3. **Reliability**:
   - [x] Implement regular backups
   - [x] Set up monitoring and alerting
   - [x] Configure appropriate readiness/liveness probes
   - [x] Implement graceful shutdown handling
   - [x] Test recovery procedures

4. **Scalability**:
   - [x] Design for horizontal scaling of worker nodes
   - [x] Implement auto-scaling policies
   - [x] Ensure proper network configuration for growth
   - [x] Consider geographic distribution for global deployments
   - [x] Plan storage growth strategy

5. **Operational**:
   - [x] Document deployment procedures
   - [x] Create runbooks for common operations
   - [x] Set up logging and monitoring pipelines
   - [x] Establish update procedures
   - [x] Plan for disaster recovery

## Edge Deployment Patterns

IPFS Kit's role-based architecture is well-suited for edge computing scenarios, where leecher nodes can operate at the edge while maintaining connectivity to a centralized infrastructure of master and worker nodes.

### Raspberry Pi Deployment

IPFS Kit can be deployed on Raspberry Pi and other ARM-based edge devices:

```dockerfile
# ARM-based leecher node
FROM arm64v8/python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY . /app/

# Install minimal dependencies for leecher mode
RUN pip install -e ".[minimal]"

# Create necessary directories
RUN mkdir -p /data/ipfs

# Set environment variables
ENV IPFS_PATH=/data/ipfs
ENV IPFS_KIT_ROLE=leecher
ENV MAX_MEMORY=512M
ENV MAX_STORAGE=8G

# Expose only necessary ports
EXPOSE 4001 5001 8080

# Entry point script
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["leecher"]
```

### Balena.io Integration

For managing fleets of edge devices, [Balena.io](https://www.balena.io/) provides an excellent platform for deploying and managing IPFS Kit leecher nodes:

```yaml
# docker-compose.yml for Balena deployment
version: '2'
services:
  ipfs-leecher:
    build: .
    privileged: true  # May be needed for hardware access
    network_mode: host
    volumes:
      - ipfs-data:/data/ipfs
    environment:
      - IPFS_KIT_ROLE=leecher
      - MASTER_NODE=${MASTER_NODE}
      - MAX_MEMORY=512M
      - MAX_STORAGE=8G
      - OFFLINE_MODE=true  # Enable offline operation when disconnected
      - DEVICE_ID=${BALENA_DEVICE_UUID}  # Use Balena device ID

volumes:
  ipfs-data:
```

### Offline Operation

Configure leecher nodes for offline operation with periodic synchronization:

```yaml
# Kubernetes ConfigMap for offline leecher configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: ipfs-leecher-offline-config
data:
  config.json: |
    {
      "offline_mode": {
        "enabled": true,
        "sync_on_connect": true,
        "max_offline_queue": 100,
        "prioritized_cids": ["QmImportantContent1", "QmImportantContent2"],
        "sync_schedule": "0 */4 * * *"  # Sync every 4 hours
      },
      "network": {
        "bootstrap_nodes": ["ipfs-master:4001"],
        "swarm_connection_limit": 100
      },
      "storage": {
        "tiers": {
          "memory": {"size_limit": "256MB"},
          "disk": {"size_limit": "8GB"}
        }
      }
    }
```

### IoT Gateway Pattern

Use IPFS Kit as an IoT gateway, collecting data from sensors and publishing to the IPFS network:

```python
# Example IoT gateway integration
import time
import json
from ipfs_kit_py.ipfs_kit import ipfs_kit
import sensor_library  # Example IoT sensor library

# Initialize IPFS Kit in leecher mode with offline capabilities
kit = ipfs_kit(
    role="leecher",
    metadata={
        "enable_offline_mode": True,
        "sync_on_connect": True
    }
)

# Configure the sensors
sensors = sensor_library.initialize_sensors()

# Data collection loop
while True:
    # Collect data from sensors
    readings = {}
    for sensor_id, sensor in sensors.items():
        try:
            readings[sensor_id] = sensor.read()
        except Exception as e:
            print(f"Error reading sensor {sensor_id}: {e}")
    
    # Add metadata
    data = {
        "device_id": "gateway-123",
        "timestamp": time.time(),
        "readings": readings
    }
    
    # Store in IPFS
    result = kit.ipfs_add_json(data)
    
    if result["success"]:
        print(f"Data stored with CID: {result['cid']}")
        
        # Publish to data topic if online
        if kit.is_online():
            kit.ipfs_pubsub_publish(
                "iot/sensor/readings",
                json.dumps({"cid": result["cid"]})
            )
    else:
        print(f"Failed to store data: {result['error']}")
    
    # Sleep until next reading
    time.sleep(60)
```

### MicroK8s for Edge Deployment

For more capable edge devices, MicroK8s provides a lightweight Kubernetes distribution:

```bash
# Install MicroK8s on edge device
sudo snap install microk8s --classic

# Enable required add-ons
microk8s enable dns storage helm3

# Apply IPFS leecher deployment
microk8s kubectl apply -f ipfs-leecher-deployment.yaml

# Check deployment status
microk8s kubectl get pods
```

### Multi-Region Edge Deployment

For global edge deployments, combine IPFS Kit with a CDN or edge network:

1. **Master Nodes**: Deploy in primary data centers
2. **Worker Nodes**: Deploy in regional hubs
3. **Leecher Nodes**: Deploy at edge locations (CDN POPs, branch offices, etc.)
4. **Content Routing**: Configure content routing tables to prefer geographically closer nodes
5. **Replication Strategy**: Set up automated replication of critical content to edge locations

## Troubleshooting

### Common Deployment Issues

1. **Peer Connection Problems**:
   - Check network connectivity between containers/pods
   - Verify firewall rules allow required ports
   - Ensure bootstrap nodes are correct and accessible
   - Check for NAT traversal issues with `ipfs swarm nat`

2. **Storage Issues**:
   - Verify volume permissions
   - Check for sufficient disk space
   - Monitor for "out of space" errors
   - Ensure proper volume mounting in containers

3. **Performance Degradation**:
   - Check resource utilization (CPU, memory, disk I/O)
   - Look for network congestion
   - Monitor DHT query performance
   - Check for garbage collection issues

4. **Cluster Synchronization Problems**:
   - Verify cluster secret is consistent across nodes
   - Check cluster connectivity with `ipfs-cluster-ctl peers ls`
   - Monitor cluster state with `ipfs-cluster-ctl status`
   - Look for consensus errors in cluster logs

### Common Commands for Troubleshooting

```bash
# Check IPFS node status
ipfs id

# Check peer connections
ipfs swarm peers

# Check DHT status
ipfs dht stats

# Check pinned content
ipfs pin ls

# Check cluster status
ipfs-cluster-ctl status

# Check cluster peers
ipfs-cluster-ctl peers ls

# Check IPFS Kit health
curl http://localhost:8000/health

# Check IPFS daemon logs
docker logs ipfs-master

# Check resource usage
docker stats ipfs-master ipfs-worker-1
```

### Kubernetes-specific Troubleshooting

```bash
# Check pod status
kubectl get pods -l app=ipfs-master

# Check pod logs
kubectl logs -l app=ipfs-master

# Check pod events
kubectl describe pod ipfs-master-0

# Check service endpoints
kubectl get endpoints ipfs-master

# Check persistent volume claims
kubectl get pvc

# Execute commands in pod
kubectl exec -it ipfs-master-0 -- ipfs id

# Check ConfigMaps
kubectl get configmap ipfs-kit-config -o yaml
```