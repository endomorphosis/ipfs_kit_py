# Filecoin Pin Backend Configuration Example

## Basic Configuration

```yaml
# ~/.ipfs_kit/backends/filecoin_pin.yaml
type: filecoin_pin
enabled: true
api_endpoint: https://api.filecoin.cloud/v1
api_key: ${FILECOIN_PIN_API_KEY}
default_replication: 3
auto_renew: true
deal_duration_days: 540
```

## Advanced Configuration

```yaml
# ~/.ipfs_kit/backends/filecoin_pin.yaml
type: filecoin_pin
enabled: true

# API Configuration
api_endpoint: https://api.filecoin.cloud/v1
api_key: ${FILECOIN_PIN_API_KEY}
timeout: 60
max_retries: 3

# Replication Settings
default_replication: 3
min_replication: 2
max_replication: 5

# Deal Management
auto_renew: true
deal_duration_days: 540  # ~18 months
renewal_threshold_days: 30  # Renew 30 days before expiration

# Gateway Fallback Configuration
gateway_fallback:
  - url: http://localhost:8080/ipfs/
    priority: 1
    timeout: 5
  - url: https://ipfs.io/ipfs/
    priority: 2
    timeout: 30
  - url: https://w3s.link/ipfs/
    priority: 3
    timeout: 30
  - url: https://dweb.link/ipfs/
    priority: 4
    timeout: 30

# Cost Management
max_deal_cost_fil: 0.01  # Maximum cost per deal in FIL
budget_alert_threshold: 0.8  # Alert at 80% of budget

# Monitoring
health_check_interval: 300  # Check health every 5 minutes
metrics_enabled: true
log_level: INFO

# Integration Settings
arc_cache_enabled: true
replication_enabled: true
cdn_integration: true
```

## Environment Variables

```bash
# API Authentication
export FILECOIN_PIN_API_KEY="your_api_key_here"

# Optional Overrides
export FILECOIN_PIN_ENDPOINT="https://api.filecoin.cloud/v1"
export FILECOIN_PIN_TIMEOUT="60"
export FILECOIN_PIN_REPLICATION="3"
```

## Python Configuration

```python
from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
import os

# Load from environment
backend = FilecoinPinBackend(
    resources={
        "api_key": os.getenv("FILECOIN_PIN_API_KEY"),
        "api_endpoint": os.getenv("FILECOIN_PIN_ENDPOINT", "https://api.filecoin.cloud/v1"),
        "timeout": int(os.getenv("FILECOIN_PIN_TIMEOUT", "60")),
        "max_retries": 3
    },
    metadata={
        "default_replication": int(os.getenv("FILECOIN_PIN_REPLICATION", "3")),
        "auto_renew": True,
        "deal_duration_days": 540,
        "gateway_fallback": [
            "https://ipfs.io/ipfs/",
            "https://w3s.link/ipfs/",
            "https://dweb.link/ipfs/"
        ]
    }
)
```

## Tiered Cache Configuration

```yaml
# ~/.ipfs_kit/cache_config.yaml
tiers:
  memory:
    type: memory
    priority: 1
    size: 100MB
  
  disk:
    type: disk
    priority: 2
    size: 1GB
    path: ~/.ipfs_cache
  
  ipfs:
    type: ipfs
    priority: 3
    timeout: 30
  
  ipfs_cluster:
    type: ipfs_cluster
    priority: 4
    replication: 3
  
  filecoin_pin:
    type: filecoin_pin
    priority: 5
    replication: 3
    auto_renew: true

# ARC Cache Settings
arc:
  ghost_list_size: 1024
  frequency_weight: 0.7
  recency_weight: 0.3
  access_boost: 2.0
  heat_decay_hours: 1.0

# Promotion/Demotion Thresholds
promotion_threshold: 3  # Access count to promote to faster tier
demotion_threshold: 30  # Days of inactivity to demote

# Replication Policy
replication_policy:
  mode: selective  # selective, aggressive, minimal
  min_redundancy: 3
  max_redundancy: 5
  sync_interval: 300  # seconds
  
  # Disaster Recovery
  disaster_recovery:
    enabled: true
    wal_integration: true
    journal_integration: true
    checkpoint_interval: 3600
    recovery_backends:
      - ipfs_cluster
      - storacha
      - filecoin_pin
```

## Replication Infrastructure Configuration

```yaml
# ~/.ipfs_kit/replication_config.yaml
replication:
  # Replication Levels
  levels:
    SINGLE:
      backends: ["filecoin_pin"]
      redundancy: 1
    
    QUORUM:
      backends: ["ipfs", "ipfs_cluster", "filecoin_pin"]
      redundancy: 2
      quorum_size: 2
    
    ALL:
      backends: ["ipfs", "ipfs_cluster", "filecoin_pin", "storacha"]
      redundancy: 4
    
    TIERED:
      hot_tier: ["memory", "disk", "ipfs"]
      warm_tier: ["ipfs_cluster", "filecoin_pin"]
      cold_tier: ["storacha", "filecoin_pin"]
      auto_migrate: true
    
    PROGRESSIVE:
      stages:
        - backends: ["ipfs"]
          duration_days: 7
        - backends: ["ipfs", "filecoin_pin"]
          duration_days: 30
        - backends: ["filecoin_pin", "storacha"]
          duration_days: null  # permanent
  
  # Conflict Resolution
  conflict_resolution:
    strategy: vector_clock  # vector_clock, timestamp, manual
    auto_resolve: true
  
  # Monitoring
  health_check:
    interval: 300
    timeout: 30
    alert_on_failure: true
  
  # Performance
  batch_size: 100
  parallel_operations: 5
  retry_attempts: 3
  retry_delay: 10
```

## CDN Configuration

```yaml
# ~/.ipfs_kit/cdn_config.yaml
cdn:
  # Content Distribution
  distribution:
    # Primary tier (fastest, most expensive)
    primary:
      backends: ["memory", "disk"]
      cache_duration: 3600  # 1 hour
      max_size: 50MB
    
    # Secondary tier (balanced)
    secondary:
      backends: ["ipfs", "ipfs_cluster"]
      cache_duration: 86400  # 1 day
      max_size: 500MB
    
    # Tertiary tier (slowest, cheapest)
    tertiary:
      backends: ["filecoin_pin", "storacha"]
      cache_duration: 2592000  # 30 days
      max_size: unlimited
  
  # Routing Strategy
  routing:
    strategy: adaptive  # adaptive, round_robin, least_latency
    health_aware: true
    latency_threshold_ms: 1000
    
    # Geographic routing
    geo_routing:
      enabled: true
      prefer_local: true
      fallback_to_global: true
  
  # Caching Policy
  caching:
    algorithm: arc  # arc, lru, lfu
    eviction_policy: least_recently_used
    
    # Cache warming
    prefetch:
      enabled: true
      predictive: true
      threshold_access_count: 3
  
  # Gateway Configuration
  gateways:
    - url: http://localhost:8080/ipfs/
      type: local
      priority: 1
      timeout: 5
      weight: 10
    
    - url: https://ipfs.io/ipfs/
      type: public
      priority: 2
      timeout: 30
      weight: 5
    
    - url: https://w3s.link/ipfs/
      type: commercial
      priority: 3
      timeout: 30
      weight: 7
    
    - url: https://dweb.link/ipfs/
      type: public
      priority: 4
      timeout: 30
      weight: 5
  
  # Performance Monitoring
  monitoring:
    enabled: true
    metrics:
      - cache_hit_rate
      - average_latency
      - bandwidth_usage
      - error_rate
    alert_thresholds:
      cache_hit_rate_min: 0.7
      average_latency_max_ms: 2000
      error_rate_max: 0.05
```

## Docker Compose Configuration

```yaml
# docker-compose.yml
version: '3.8'

services:
  ipfs_kit:
    image: ipfs_kit_py:latest
    environment:
      - FILECOIN_PIN_API_KEY=${FILECOIN_PIN_API_KEY}
      - FILECOIN_PIN_ENDPOINT=https://api.filecoin.cloud/v1
      - FILECOIN_PIN_REPLICATION=3
    volumes:
      - ./config:/root/.ipfs_kit
      - ./cache:/root/.ipfs_cache
      - ./data:/data
    ports:
      - "5001:5001"  # IPFS API
      - "8080:8080"  # MCP Server
    restart: unless-stopped
```

## Kubernetes Configuration

```yaml
# deployment/k8s/filecoin-pin-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: filecoin-pin-config
data:
  config.yaml: |
    type: filecoin_pin
    enabled: true
    api_endpoint: https://api.filecoin.cloud/v1
    default_replication: 3
    auto_renew: true
    deal_duration_days: 540

---
apiVersion: v1
kind: Secret
metadata:
  name: filecoin-pin-secret
type: Opaque
stringData:
  api-key: your_api_key_here

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ipfs-kit
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
        image: ipfs_kit_py:latest
        env:
        - name: FILECOIN_PIN_API_KEY
          valueFrom:
            secretKeyRef:
              name: filecoin-pin-secret
              key: api-key
        volumeMounts:
        - name: config
          mountPath: /root/.ipfs_kit
        - name: cache
          mountPath: /root/.ipfs_cache
      volumes:
      - name: config
        configMap:
          name: filecoin-pin-config
      - name: cache
        persistentVolumeClaim:
          claimName: ipfs-kit-cache
```

## Testing Configuration

```yaml
# ~/.ipfs_kit/backends/filecoin_pin_test.yaml
type: filecoin_pin
enabled: true

# Use mock mode for testing (no API key)
api_key: null  # or omit this field
mock_mode: true

# Test settings
default_replication: 1
auto_renew: false
deal_duration_days: 1

# Fast timeouts for testing
timeout: 5
max_retries: 1

# Local gateway only
gateway_fallback:
  - http://localhost:8080/ipfs/
```

## Production Configuration

```yaml
# ~/.ipfs_kit/backends/filecoin_pin_prod.yaml
type: filecoin_pin
enabled: true

# Production API settings
api_endpoint: https://api.filecoin.cloud/v1
api_key: ${FILECOIN_PIN_API_KEY}
timeout: 120
max_retries: 5

# Production replication
default_replication: 5
min_replication: 3
max_replication: 7

# Long-term deals
auto_renew: true
deal_duration_days: 1080  # 3 years
renewal_threshold_days: 90

# Comprehensive gateway list
gateway_fallback:
  - http://localhost:8080/ipfs/
  - https://ipfs.io/ipfs/
  - https://w3s.link/ipfs/
  - https://dweb.link/ipfs/
  - https://cloudflare-ipfs.com/ipfs/
  - https://gateway.pinata.cloud/ipfs/

# Monitoring and alerting
metrics_enabled: true
alert_email: ops@example.com
log_level: WARNING

# Cost controls
max_deal_cost_fil: 0.1
budget_monthly_fil: 10.0
budget_alert_threshold: 0.9
```
