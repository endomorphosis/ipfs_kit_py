# IPFS MCP Cluster Deployment Guide

This guide provides comprehensive instructions for deploying the IPFS MCP server with cluster capabilities using Docker and Kubernetes.

## Quick Start

### Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- Kubernetes 1.20+ (for K8s deployment)
- kubectl configured for your cluster
- 8GB+ RAM recommended
- 50GB+ storage for IPFS data

### 1. Docker Compose Deployment (Recommended for Testing)

```bash
# Deploy 3-node cluster locally
./deploy-cluster.sh --docker-only

# Check cluster status
curl http://localhost:9998/health
curl http://localhost:9998/cluster/status
```

### 2. Kubernetes Deployment

```bash
# Deploy to Kubernetes cluster
./deploy-cluster.sh

# Access via port-forward
kubectl port-forward svc/ipfs-mcp-master 9998:9998 -n ipfs-cluster
```

## Architecture

### Cluster Roles

- **Master Node**: Can initiate replication, modify indexes, elect as leader
- **Worker Node**: Can receive replication, read indexes, potential leader
- **Leecher Node**: Read-only access, cannot be elected as leader

### 3-Node Cluster Configuration

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Master    │    │   Worker 1  │    │   Worker 2  │
│   Port: 9998│◄──►│   Port: 9999│◄──►│  Port: 10000│
│             │    │             │    │             │
│ Leader      │    │ Follower    │    │ Follower    │
│ Replication │    │ Replication │    │ Replication │
│ Indexing    │    │ Read-Only   │    │ Read-Only   │
└─────────────┘    └─────────────┘    └─────────────┘
```

## Docker Deployment

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_ID` | `ipfs-mcp-node` | Unique node identifier |
| `NODE_ROLE` | `worker` | Node role: master/worker/leecher |
| `SERVER_HOST` | `0.0.0.0` | Server bind address |
| `SERVER_PORT` | `9998` | Server port |
| `CLUSTER_PEERS` | `` | Comma-separated peer list |
| `LOG_LEVEL` | `INFO` | Logging level |
| `DEBUG` | `false` | Enable debug mode |
| `ENABLE_REPLICATION` | `true` | Enable replication features |
| `ENABLE_INDEXING` | `true` | Enable indexing features |
| `ENABLE_VFS` | `true` | Enable VFS integration |

### Build Custom Image

```bash
cd docker
docker build -t ipfs-kit-mcp:custom -f Dockerfile --target development ..
```

### Manual Docker Run

```bash
# Master node
docker run -d --name ipfs-master \
  -p 9998:9998 \
  -e NODE_ID=master-1 \
  -e NODE_ROLE=master \
  -e CLUSTER_PEERS=worker-1:9998,worker-2:9998 \
  ipfs-kit-mcp:latest

# Worker node
docker run -d --name ipfs-worker1 \
  -p 9999:9998 \
  -e NODE_ID=worker-1 \
  -e NODE_ROLE=worker \
  -e CLUSTER_PEERS=master-1:9998,worker-2:9998 \
  ipfs-kit-mcp:latest
```

### Docker Compose Services

- **ipfs-mcp-master**: Master node on port 9998
- **ipfs-mcp-worker1**: Worker node on port 9999  
- **ipfs-mcp-worker2**: Worker node on port 10000
- **cluster-tester**: Automated test runner

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f ipfs-mcp-master

# Scale workers
docker-compose up -d --scale ipfs-mcp-worker1=2

# Stop services
docker-compose down -v
```

## Kubernetes Deployment

### Namespace and Resources

The deployment creates:
- Namespace: `ipfs-cluster`
- StatefulSets for persistent storage
- Services for cluster communication
- ConfigMaps for configuration
- Secrets for cluster authentication
- Test Jobs for validation

### Storage Requirements

- **Master**: 50GB IPFS data + 10GB application data
- **Workers**: 30GB IPFS data + 10GB application data each

### Resource Limits

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-----------|-------------|-----------|----------------|--------------|
| Master | 250m | 1000m | 512Mi | 2Gi |
| Worker | 250m | 750m | 512Mi | 1.5Gi |

### Manual Kubernetes Deployment

```bash
# Create namespace
kubectl create namespace ipfs-cluster

# Apply manifests
kubectl apply -f deployments/k8s/00-services.yaml
kubectl apply -f deployments/k8s/01-master.yaml
kubectl apply -f deployments/k8s/02-workers.yaml

# Check status
kubectl get pods -n ipfs-cluster
kubectl get services -n ipfs-cluster

# Run tests
kubectl apply -f deployments/k8s/03-test-job.yaml
kubectl logs job/cluster-test-job -n ipfs-cluster
```

### Access Services

```bash
# Port forward master
kubectl port-forward svc/ipfs-mcp-master 9998:9998 -n ipfs-cluster

# Port forward workers
kubectl port-forward svc/ipfs-mcp-worker1 9999:9998 -n ipfs-cluster
kubectl port-forward svc/ipfs-mcp-worker2 10000:9998 -n ipfs-cluster

# Access from outside cluster (LoadBalancer)
kubectl get svc ipfs-mcp-master -n ipfs-cluster
```

## Testing

### Automated Test Suite

```bash
# Run comprehensive tests
./deploy-cluster.sh

# Docker only tests
./deploy-cluster.sh --docker-only

# Kubernetes only tests
./deploy-cluster.sh --k8s-only --no-build
```

### Manual Testing

```bash
# Health checks
curl http://localhost:9998/health
curl http://localhost:9999/health
curl http://localhost:10000/health

# Cluster status
curl http://localhost:9998/cluster/status | jq '.'

# Leader election
curl http://localhost:9998/cluster/leader | jq '.'

# Peer management
curl -X POST http://localhost:9998/cluster/peers \
  -H "Content-Type: application/json" \
  -d '{"id": "test-peer", "role": "worker", "address": "127.0.0.1", "port": 11000}'

# Replication status
curl http://localhost:9998/replication/status | jq '.'

# Indexing statistics
curl http://localhost:9998/indexing/stats | jq '.'
```

### Load Testing

```bash
# Install dependencies
pip install httpx anyio

# Run load test
python -c "
import anyio
import httpx

async def load_test():
    async with httpx.AsyncClient() as client:
    responses = []
    async def fetch_health():
      responses.append(await client.get('http://localhost:9998/health'))
    async with anyio.create_task_group() as task_group:
      for _ in range(100):
        task_group.start_soon(fetch_health)
        success_count = sum(1 for r in responses if r.status_code == 200)
        print(f'Success rate: {success_count}/100')

anyio.run(load_test)
"
```

## Cluster Operations

### Adding New Nodes

```bash
# Docker Compose
docker run -d --name ipfs-worker3 \
  --network docker_ipfs-cluster \
  -e NODE_ID=worker-3 \
  -e NODE_ROLE=worker \
  -e CLUSTER_PEERS=ipfs-mcp-master:9998,ipfs-mcp-worker1:9998,ipfs-mcp-worker2:9998 \
  ipfs-kit-mcp:latest

# Kubernetes
kubectl scale statefulset ipfs-mcp-worker1 --replicas=2 -n ipfs-cluster
```

### Leader Election Testing

```bash
# Force leader election
curl -X POST http://localhost:9998/cluster/election/trigger

# Check new leader
curl http://localhost:9998/cluster/leader

# Simulate node failure
docker-compose stop ipfs-mcp-master
curl http://localhost:9999/cluster/leader  # Should elect new leader
```

### Replication Testing

```bash
# Add content to replicate
curl -X POST http://localhost:9998/replication/replicate \
  -H "Content-Type: application/json" \
  -d '{
    "cid": "QmTestContent123",
    "target_peers": ["worker-1", "worker-2"]
  }'

# Check replication status
curl http://localhost:9998/replication/status
```

### Indexing Testing

```bash
# Add index data (master only)
curl -X POST http://localhost:9998/indexing/data \
  -H "Content-Type: application/json" \
  -d '{
    "index_type": "embeddings",
    "key": "test-doc",
    "data": {
      "vector": [0.1, 0.2, 0.3],
      "content": "test document"
    }
  }'

# Search embeddings
curl -X POST http://localhost:9998/indexing/search/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "query_vector": [0.1, 0.2, 0.3],
    "top_k": 5
  }'
```

## Monitoring and Logging

### Health Monitoring

```bash
# Kubernetes health checks
kubectl get pods -n ipfs-cluster -w

# Docker health checks
docker-compose ps

# Custom monitoring
while true; do
  curl -s http://localhost:9998/health | jq '.status'
  sleep 10
done
```

### Log Aggregation

```bash
# Docker logs
docker-compose logs -f --tail=100

# Kubernetes logs
kubectl logs -f statefulset/ipfs-mcp-master -n ipfs-cluster
kubectl logs -f statefulset/ipfs-mcp-worker1 -n ipfs-cluster
kubectl logs -f statefulset/ipfs-mcp-worker2 -n ipfs-cluster

# Structured logging
kubectl logs statefulset/ipfs-mcp-master -n ipfs-cluster | jq '.'
```

### Metrics Collection

Enable metrics collection by setting `ENABLE_METRICS=true`:

```bash
# Prometheus metrics endpoint
curl http://localhost:9998/metrics

# Custom metrics
curl http://localhost:9998/cluster/metrics
```

## Troubleshooting

### Common Issues

1. **Pods not starting**
   ```bash
   kubectl describe pod <pod-name> -n ipfs-cluster
   kubectl logs <pod-name> -n ipfs-cluster
   ```

2. **Cluster communication issues**
   ```bash
   # Check service DNS
   kubectl exec -it <pod-name> -n ipfs-cluster -- nslookup ipfs-mcp-master
   
   # Test connectivity
   kubectl exec -it <pod-name> -n ipfs-cluster -- curl http://ipfs-mcp-master:9998/health
   ```

3. **Storage issues**
   ```bash
   kubectl get pvc -n ipfs-cluster
   kubectl describe pvc <pvc-name> -n ipfs-cluster
   ```

4. **Performance issues**
   ```bash
   # Check resource usage
   kubectl top pods -n ipfs-cluster
   kubectl top nodes
   ```

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Docker
docker run -e DEBUG=true ipfs-kit-mcp:latest

# Kubernetes
kubectl set env statefulset/ipfs-mcp-master DEBUG=true -n ipfs-cluster
```

### Recovery Procedures

```bash
# Restart cluster
kubectl rollout restart statefulset/ipfs-mcp-master -n ipfs-cluster
kubectl rollout restart statefulset/ipfs-mcp-worker1 -n ipfs-cluster
kubectl rollout restart statefulset/ipfs-mcp-worker2 -n ipfs-cluster

# Reset cluster state
kubectl delete statefulset --all -n ipfs-cluster
kubectl apply -f deployments/k8s/01-master.yaml -f deployments/k8s/02-workers.yaml
```

## Security Considerations

### Production Deployment

1. **Update secrets**:
   ```bash
   kubectl create secret generic cluster-secrets \
     --from-literal=cluster-secret=$(openssl rand -base64 32) \
     -n ipfs-cluster
   ```

2. **Enable TLS**:
   ```yaml
   env:
   - name: ENABLE_TLS
     value: "true"
   - name: TLS_CERT_PATH
     value: "/app/certs/tls.crt"
   - name: TLS_KEY_PATH
     value: "/app/certs/tls.key"
   ```

3. **Network policies**:
   ```bash
   kubectl apply -f deployments/k8s/network-policy.yaml
   ```

4. **Resource limits**:
   - Ensure proper CPU/memory limits
   - Set up PodDisruptionBudgets
   - Configure horizontal pod autoscaling

### Backup and Recovery

```bash
# Backup persistent volumes
kubectl get pvc -n ipfs-cluster
# Create volume snapshots

# Backup cluster configuration
kubectl get configmap cluster-config -n ipfs-cluster -o yaml > cluster-config-backup.yaml
kubectl get secret cluster-secrets -n ipfs-cluster -o yaml > cluster-secrets-backup.yaml
```

## Performance Tuning

### Resource Optimization

```yaml
resources:
  requests:
    memory: "1Gi"      # Increase for better performance
    cpu: "500m"        # Increase for CPU-intensive operations
  limits:
    memory: "4Gi"      # Adjust based on workload
    cpu: "2000m"       # Allow bursting for peak loads
```

### Storage Optimization

```yaml
volumeClaimTemplates:
- metadata:
    name: ipfs-data
  spec:
    accessModes: ["ReadWriteOnce"]
    storageClassName: "fast-ssd"  # Use fast storage class
    resources:
      requests:
        storage: 100Gi              # Increase as needed
```

### Network Optimization

```yaml
env:
- name: MAX_CONNECTIONS
  value: "200"           # Increase connection limit
- name: REQUEST_TIMEOUT
  value: "60"            # Increase timeout for large requests
- name: KEEPALIVE_TIMEOUT
  value: "10"            # Adjust keepalive settings
```

## 📚 Complete Documentation

### Core Documentation
- **[Getting Started Guide](./docs/GETTING_STARTED.md)**: Step-by-step setup tutorial
- **[API Reference](./docs/API_REFERENCE.md)**: Complete REST API documentation
- **[Architecture Overview](./docs/ARCHITECTURE.md)**: System design and components
- **[Test Results](./CLUSTER_TEST_RESULTS.md)**: Comprehensive validation results

### Advanced Guides
- **[Cluster Management](./docs/CLUSTER_MANAGEMENT.md)**: Advanced cluster operations
- **[VFS Integration](./docs/VFS_INTEGRATION.md)**: Virtual filesystem usage
- **[Production Deployment](./docs/PRODUCTION_DEPLOYMENT.md)**: Production best practices
- **[Performance Tuning](./docs/PERFORMANCE_TUNING.md)**: Optimization guide
- **[Troubleshooting](./docs/TROUBLESHOOTING.md)**: Common issues and solutions

### Development Resources
- **[Contributing Guide](./CONTRIBUTING.md)**: How to contribute to the project
- **[Development Setup](./docs/DEVELOPMENT.md)**: Local development environment
- **[Testing Guide](./docs/TESTING.md)**: Testing procedures and automation
