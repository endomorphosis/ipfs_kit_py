# IPFS-Kit Deployment Guide

## Overview

This guide covers various deployment scenarios for IPFS-Kit, from development environments to production clusters.

## Deployment Options

### 1. Local Development

#### Quick Setup
```bash
# Clone and install
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py
pip install -r requirements.txt
pip install -e .

# Start daemon
python ipfs_kit_enhanced_cli.py daemon start --detach

# Verify installation
python ipfs_kit_enhanced_cli.py daemon status
python ipfs_kit_enhanced_cli.py health check
```

#### Configuration
```bash
# Set custom configuration
python ipfs_kit_enhanced_cli.py config set daemon.health_check_interval 60
python ipfs_kit_enhanced_cli.py config set backends.ipfs.enabled true

# View configuration
python ipfs_kit_enhanced_cli.py config show
```

### 2. Docker Single Container

#### Basic Deployment
```bash
docker run -d \
  --name ipfs-kit \
  -p 4001:4001 \
  -p 5001:5001 \
  -p 8080:8080 \
  -p 9999:9999 \
  -v ipfs_data:/home/ipfs_user/.ipfs \
  -v config_data:/tmp/ipfs_kit_config \
  -v logs_data:/tmp/ipfs_kit_logs \
  --restart unless-stopped \
  ghcr.io/endomorphosis/ipfs_kit_py:latest
```

#### Production Configuration
```bash
# Create custom config
mkdir -p ./config
cat > ./config/daemon.json << 'EOF'
{
  "daemon": {
    "log_level": "INFO",
    "health_check_interval": 30
  },
  "backends": {
    "ipfs": {"enabled": true, "auto_start": true},
    "ipfs_cluster": {"enabled": true, "auto_start": true}
  },
  "replication": {
    "enabled": true,
    "min_replicas": 2,
    "max_replicas": 5
  }
}
EOF

# Run with custom config
docker run -d \
  --name ipfs-kit-prod \
  -p 4001:4001 \
  -p 5001:5001 \
  -p 8080:8080 \
  -p 9999:9999 \
  -v ./config:/tmp/ipfs_kit_config \
  -v ipfs_data:/home/ipfs_user/.ipfs \
  -v logs_data:/tmp/ipfs_kit_logs \
  --restart unless-stopped \
  ghcr.io/endomorphosis/ipfs_kit_py:latest
```

### 3. Docker Compose Cluster

#### Standard Cluster
```bash
# Download compose file
curl -O https://raw.githubusercontent.com/endomorphosis/ipfs_kit_py/main/docker/docker-compose.enhanced.yml

# Deploy cluster
docker-compose -f docker-compose.enhanced.yml up -d

# Services:
# - ipfs-kit: Main node (localhost:9999)
# - ipfs-kit-cluster: Cluster node (localhost:10000)
# - prometheus: Metrics (localhost:9090)
# - grafana: Dashboard (localhost:3000, admin/admin)
```

#### High Availability Cluster
```yaml
# docker-compose.ha.yml
version: '3.8'
services:
  ipfs-kit-1:
    image: ghcr.io/endomorphosis/ipfs_kit_py:latest
    ports:
      - "9999:9999"
      - "5001:5001"
    volumes:
      - ipfs_data_1:/home/ipfs_user/.ipfs
      - ./config:/tmp/ipfs_kit_config
    deploy:
      replicas: 1
      restart_policy:
        condition: on-failure
        max_attempts: 3
      
  ipfs-kit-2:
    image: ghcr.io/endomorphosis/ipfs_kit_py:latest
    ports:
      - "10000:9999"
      - "5002:5001"
    volumes:
      - ipfs_data_2:/home/ipfs_user/.ipfs
      - ./config:/tmp/ipfs_kit_config
    depends_on:
      - ipfs-kit-1

volumes:
  ipfs_data_1:
  ipfs_data_2:
```

### 4. Kubernetes Deployment

#### Namespace Setup
```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ipfs-kit
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: ipfs-kit-config
  namespace: ipfs-kit
data:
  daemon.json: |
    {
      "daemon": {
        "log_level": "INFO",
        "health_check_interval": 30
      },
      "backends": {
        "ipfs": {"enabled": true, "auto_start": true}
      },
      "replication": {
        "enabled": true,
        "min_replicas": 2
      }
    }
```

#### Deployment
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ipfs-kit
  namespace: ipfs-kit
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ipfs-kit
  template:
    metadata:
      labels:
        app: ipfs-kit
    spec:
      containers:
      - name: ipfs-kit
        image: ghcr.io/endomorphosis/ipfs_kit_py:latest
        ports:
        - containerPort: 9999
          name: daemon-api
        - containerPort: 5001
          name: ipfs-api
        - containerPort: 4001
          name: ipfs-swarm
        volumeMounts:
        - name: config
          mountPath: /tmp/ipfs_kit_config
        - name: data
          mountPath: /home/ipfs_user/.ipfs
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 9999
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /api/v1/status
            port: 9999
          initialDelaySeconds: 30
          periodSeconds: 10
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
      volumes:
      - name: config
        configMap:
          name: ipfs-kit-config
      - name: data
        persistentVolumeClaim:
          claimName: ipfs-kit-data
```

#### Service and Ingress
```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: ipfs-kit-service
  namespace: ipfs-kit
spec:
  selector:
    app: ipfs-kit
  ports:
  - name: daemon-api
    port: 9999
    targetPort: 9999
  - name: ipfs-api
    port: 5001
    targetPort: 5001
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ipfs-kit-ingress
  namespace: ipfs-kit
spec:
  rules:
  - host: ipfs-kit.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: ipfs-kit-service
            port:
              number: 9999
```

#### Persistent Storage
```yaml
# storage.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ipfs-kit-data
  namespace: ipfs-kit
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
  storageClassName: fast-ssd
```

### 5. Production Considerations

#### Security
```bash
# Create non-root user
useradd -m -s /bin/bash ipfs-user

# Set up proper permissions
chown -R ipfs-user:ipfs-user /opt/ipfs-kit
chmod 755 /opt/ipfs-kit

# Use secrets management
kubectl create secret generic ipfs-kit-secrets \
  --from-literal=api-key=your-secret-key \
  --namespace ipfs-kit
```

#### Monitoring
```yaml
# monitoring.yaml
apiVersion: v1
kind: Service
metadata:
  name: ipfs-kit-metrics
  namespace: ipfs-kit
  labels:
    app: ipfs-kit
spec:
  ports:
  - name: metrics
    port: 9090
    targetPort: 9090
  selector:
    app: ipfs-kit
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: ipfs-kit-monitor
  namespace: ipfs-kit
spec:
  selector:
    matchLabels:
      app: ipfs-kit
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics
```

#### Backup and Recovery
```bash
# Backup IPFS data
kubectl exec -n ipfs-kit pod/ipfs-kit-xxx -- \
  tar czf - /home/ipfs_user/.ipfs | \
  aws s3 cp - s3://backups/ipfs-kit-$(date +%Y%m%d).tar.gz

# Backup configuration
kubectl get configmap ipfs-kit-config -n ipfs-kit -o yaml > \
  config-backup-$(date +%Y%m%d).yaml
```

### 6. Scaling and Load Balancing

#### Horizontal Pod Autoscaler
```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ipfs-kit-hpa
  namespace: ipfs-kit
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ipfs-kit
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### Load Balancer Configuration
```bash
# AWS Application Load Balancer
aws elbv2 create-load-balancer \
  --name ipfs-kit-alb \
  --subnets subnet-xxx subnet-yyy \
  --security-groups sg-xxx \
  --type application \
  --scheme internet-facing

# Health check configuration
aws elbv2 create-target-group \
  --name ipfs-kit-targets \
  --protocol HTTP \
  --port 9999 \
  --vpc-id vpc-xxx \
  --health-check-path /api/v1/health \
  --health-check-interval-seconds 30
```

## Deployment Verification

### Health Checks
```bash
# Container health
docker exec ipfs-kit /healthcheck.sh

# API health
curl -f http://localhost:9999/api/v1/health

# Kubernetes health
kubectl get pods -n ipfs-kit
kubectl describe pod ipfs-kit-xxx -n ipfs-kit
```

### Performance Testing
```bash
# Load testing
curl -X POST http://localhost:9999/api/v1/pins \
  -H "Content-Type: application/json" \
  -d '{"cid": "QmTestHash", "name": "load-test"}'

# Benchmark testing
python test_performance_multiprocessing.py --benchmark
```

### Monitoring Setup
```bash
# Access monitoring dashboards
open http://localhost:3000    # Grafana
open http://localhost:9090    # Prometheus

# Check metrics
curl http://localhost:9999/api/v1/metrics
```

## Troubleshooting

### Common Issues

1. **Container won't start**
   ```bash
   docker logs ipfs-kit
   docker exec -it ipfs-kit /bin/bash
   ```

2. **API not responding**
   ```bash
   netstat -tlnp | grep 9999
   curl -v http://localhost:9999/api/v1/status
   ```

3. **Performance issues**
   ```bash
   python ipfs_kit_enhanced_cli.py metrics --detailed
   docker stats ipfs-kit
   ```

4. **Storage issues**
   ```bash
   df -h
   docker system df
   docker volume ls
   ```

### Support Resources

- [Complete Documentation](DOCUMENTATION.md)
- [Troubleshooting Guide](docs/troubleshooting.md)
- [GitHub Issues](https://github.com/endomorphosis/ipfs_kit_py/issues)
- [Community Discussions](https://github.com/endomorphosis/ipfs_kit_py/discussions)
