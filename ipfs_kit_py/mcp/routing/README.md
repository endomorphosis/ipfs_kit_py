# Optimized Data Routing System

## Overview

The Optimized Data Routing system is a core component of the MCP server that intelligently routes content to the most appropriate storage backends based on multiple factors:

- **Content characteristics** (size, type, format)
- **Cost optimization** (storage costs, retrieval costs)
- **Geographic proximity** (user location, backend regions)
- **Network performance** (bandwidth, latency, reliability)

This feature satisfies the requirements in Phase 1 of the MCP roadmap by providing content-aware backend selection, cost-based routing algorithms, geographic optimization, and bandwidth/latency analysis.

## Architecture

The Optimized Data Routing system consists of the following components:

1. **Core Data Router** (`data_router.py`)
   - Content analysis and categorization
   - Configurable routing rules
   - Strategy-based backend selection
   - Cost optimization algorithms

2. **Bandwidth-Aware Router** (`bandwidth_aware_router.py`)
   - Network performance monitoring
   - Latency-based routing decisions
   - Transfer time estimation
   - Network quality classification

3. **Router API** (`router_api.py`)
   - RESTful endpoints for routing operations
   - Configuration and management interfaces
   - Metrics and analysis endpoints

## Routing Strategies

The system supports multiple routing strategies that can be selected based on your specific requirements:

- **Content Type** (`CONTENT_TYPE`): Routes based on content characteristics (file type, size).
- **Cost** (`COST`): Optimizes for lowest storage and retrieval costs.
- **Latency** (`LATENCY`): Prioritizes backends with lowest latency.
- **Geographic** (`GEOGRAPHIC`): Routes to backends closest to the user's location.
- **Reliability** (`RELIABILITY`): Selects backends with highest uptime and reliability.
- **Bandwidth** (`BANDWIDTH`): Chooses backends with highest available bandwidth.
- **Network Aware** (`NETWORK_AWARE`): Considers all network metrics for optimal transfer times.
- **Balanced** (`BALANCED`): Considers multiple factors with equal weighting.
- **Hybrid** (`HYBRID`): Adaptively balances multiple factors based on content characteristics.

## Content Categories

The router categorizes content to apply appropriate routing rules:

- **Small Files** (< 1MB): Typically routed to IPFS for fast access.
- **Medium Files** (1MB - 100MB): Balanced across backends based on other factors.
- **Large Files** (> 100MB): Often routed to Filecoin for cost-effective storage.
- **Media Files**: Images, video, and audio files.
- **Documents**: Text, PDF, and office documents.
- **Structured Data**: JSON, XML, and other structured formats.
- **Encrypted Content**: Content with encryption headers or extensions.
- **Binary Data**: Executable files and other binary formats.

## Configuration

The routing system can be configured through:

1. **Environment Variables**:
   - `ROUTER_DEFAULT_STRATEGY`: Default routing strategy (e.g., "balanced")
   - `ROUTER_UPDATE_INTERVAL`: Frequency of metrics updates in seconds
   - `ROUTER_CURRENT_REGION`: Geographic region where server is deployed
   - `ROUTER_AUTO_UPDATES`: Enable/disable automatic metric updates (1/0)
   - `ROUTER_BACKEND_COSTS_PATH`: Path to JSON file with backend costs
   - `ROUTER_GEO_REGIONS_PATH`: Path to JSON file with geographic regions

2. **Custom Routing Rules**:
   - Create and manage routing rules through the API
   - Define content patterns, size constraints, and backend preferences
   - Specify routing strategies and priorities for different content types

## API Usage

### 1. Routing Content

To route content to the optimal backend:

```bash
curl -X POST "http://localhost:5000/api/v0/routing/route" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/your/file.jpg" \
  -F "strategy=balanced" \
  -F "client_latitude=37.7749" \
  -F "client_longitude=-122.4194"
```

### 2. Analyzing Content Routing

To analyze how content would be routed without actually storing it:

```bash
curl -X POST "http://localhost:5000/api/v0/routing/analyze" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/your/file.jpg" \
  -F "client_latitude=37.7749" \
  -F "client_longitude=-122.4194"
```

### 3. Managing Routing Rules

To create a custom routing rule:

```bash
curl -X POST "http://localhost:5000/api/v0/routing/rules" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "large_media_files",
    "name": "Large Media Routing",
    "content_categories": ["media", "large_file"],
    "min_size_bytes": 104857600,
    "preferred_backends": ["filecoin", "s3"],
    "strategy": "cost",
    "priority": "cost",
    "active": true
  }'
```

### 4. Network Metrics

To view network performance metrics for backends:

```bash
curl -X GET "http://localhost:5000/api/v0/routing/metrics" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Best Practices

1. **Configure Geographic Regions**:
   - Set up geographic regions with accurate coordinates for your storage backends
   - Include client location in routing requests for location-aware decisions

2. **Optimize for Content Types**:
   - Create specific routing rules for different content types
   - Consider size, access patterns, and cost-performance tradeoffs

3. **Monitor Network Performance**:
   - Review network metrics regularly to identify bottlenecks
   - Adjust routing strategies based on observed performance

4. **Balance Cost and Performance**:
   - Use cost-optimized routing for archival content
   - Use performance-optimized routing for frequently accessed content

5. **Implement Client-Side Location Detection**:
   - Use browser geolocation or IP-based location services
   - Pass client location to routing endpoints for optimal decisions

## Example Scenarios

### 1. Media Streaming Platform

**Optimal Configuration**:
- Small thumbnails: IPFS (low latency, fast access)
- Medium-resolution videos: S3 or IPFS (balance of performance and cost)
- High-resolution videos: Filecoin with hot cache on IPFS (cost-effective with good performance)

### 2. Document Management System

**Optimal Configuration**:
- Frequently accessed documents: IPFS or S3 (fast retrieval)
- Archival documents: Filecoin (cost-effective long-term storage)
- Sensitive documents: Encrypted and stored on private IPFS nodes

### 3. Data Analytics Platform

**Optimal Configuration**:
- Raw data: Filecoin (cost-effective bulk storage)
- Processed results: IPFS (fast access for visualization)
- Shared datasets: Replicated across multiple backends for reliability

## Advanced Features

### Content-Aware Migration

The routing system works with the Migration Controller to recommend content migration based on:

- Access patterns (frequently vs. rarely accessed)
- Cost optimization opportunities
- Performance improvements

### Dynamic Adaptation

The system automatically adjusts routing decisions based on:

- Measured network performance
- Backend health and reliability
- Cost changes and budget constraints

### Multi-Region Optimization

For global deployments, the system can:

- Route to region-specific backends for better performance
- Replicate content across regions for faster access
- Balance traffic based on regional network conditions

## Troubleshooting

### Common Issues

1. **Content Routed to Unexpected Backend**:
   - Check routing rules and their priority order
   - Verify content category detection is accurate
   - Examine network metrics that might affect decisions

2. **Slow Routing Decisions**:
   - Ensure metrics are being updated regularly
   - Check for bottlenecks in network measurement
   - Simplify complex routing rules

3. **Geographic Routing Not Working**:
   - Verify client location is being properly passed
   - Check that backend regions are correctly configured
   - Ensure the geographic router has regions defined

### Diagnosis Tools

- Use `/api/v0/routing/analyze` to see detailed routing analysis
- Check `/api/v0/routing/metrics` to view current network performance
- Review `/api/v0/routing/status` for overall system status

## Further Reading

- [MCP Server Architecture](../architecture.md)
- [Storage Backend Integration](../storage/backends.md)
- [Migration Controller Documentation](../migration/readme.md)
- [Advanced Configuration Options](../configuration.md)