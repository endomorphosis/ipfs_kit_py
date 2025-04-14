"""
Optimized Data Routing extension for MCP server.

This module provides intelligent data routing capabilities as specified
in the MCP roadmap Phase 1 Core Functionality Enhancements (Q3 2025).

Features:
- Content-aware backend selection
- Cost-based routing algorithms
- Geographic optimization
- Bandwidth and latency analysis
"""

import os
import time
import json
import random
import logging
import asyncio
import ipaddress
import math
from typing import Dict, List, Any, Optional
from fastapi import (
from pydantic import BaseModel, Field, validator

APIRouter,
    HTTPException,
    Query,
    BackgroundTasks,
    Request)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
ROUTING_CONFIG_FILE = "routing_config.json"
ROUTING_DATA_FILE = "routing_data.json"
ROUTING_POLICY_FILE = "routing_policies.json"
GEO_DATA_FILE = "geo_data.json"
PERFORMANCE_DATA_FILE = "performance_data.json"

# Directory for routing files
ROUTING_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "routing_data")
os.makedirs(ROUTING_DIR, exist_ok=True)

# Full paths
ROUTING_CONFIG_PATH = os.path.join(ROUTING_DIR, ROUTING_CONFIG_FILE)
ROUTING_DATA_PATH = os.path.join(ROUTING_DIR, ROUTING_DATA_FILE)
ROUTING_POLICY_PATH = os.path.join(ROUTING_DIR, ROUTING_POLICY_FILE)
GEO_DATA_PATH = os.path.join(ROUTING_DIR, GEO_DATA_FILE)
PERFORMANCE_DATA_PATH = os.path.join(ROUTING_DIR, PERFORMANCE_DATA_FILE)

# Storage backend attributes - will be populated from the MCP server
storage_backends = {
    "ipfs": {"available": True, "simulation": False},
    "local": {"available": True, "simulation": False},
    "huggingface": {"available": False, "simulation": True},
    "s3": {"available": False, "simulation": True},
    "filecoin": {"available": False, "simulation": True},
    "storacha": {"available": False, "simulation": True},
    "lassie": {"available": False, "simulation": True},
}

# Default routing configuration
DEFAULT_ROUTING_CONFIG = {
    "enabled": True,
    "default_policy": "balanced",
    "auto_detect_region": True,
    "preferred_regions": ["us-east", "eu-west"],
    "cost_weight": 0.3,
    "performance_weight": 0.4,
    "reliability_weight": 0.3,
    "max_backend_selection": 3,
    "minimum_backend_score": 0.5,
    "content_type_analysis": True,
    "bandwidth_tracking": True,
    "latency_tracking": True,
    "cold_start_estimation": True,
    "update_interval_seconds": 300,
    "adaptive_routing": True,
    "metrics_enabled": True,
}

# Default routing policies
DEFAULT_ROUTING_POLICIES = {
    "performance": {
        "name": "performance",
        "description": "Prioritize performance over cost",
        "cost_weight": 0.1,
        "performance_weight": 0.7,
        "reliability_weight": 0.2,
        "max_replicas": 2,
        "content_filters": {},
        "backend_preferences": {"s3": 1.2, "local": 1.1, "ipfs": 0.9, "filecoin": 0.5},
        "geo_preferences": {
            "same_region": 1.5,
            "same_continent": 1.2,
            "different_continent": 0.7,
        },
    },
    "cost-effective": {
        "name": "cost-effective",
        "description": "Prioritize cost over performance",
        "cost_weight": 0.7,
        "performance_weight": 0.1,
        "reliability_weight": 0.2,
        "max_replicas": 1,
        "content_filters": {},
        "backend_preferences": {"filecoin": 1.3, "ipfs": 1.0, "local": 0.9, "s3": 0.7},
        "geo_preferences": {
            "same_region": 1.1,
            "same_continent": 1.0,
            "different_continent": 0.9,
        },
    },
    "balanced": {
        "name": "balanced",
        "description": "Balance between cost, performance, and reliability",
        "cost_weight": 0.3,
        "performance_weight": 0.3,
        "reliability_weight": 0.4,
        "max_replicas": 2,
        "content_filters": {},
        "backend_preferences": {
            "s3": 1.0,
            "ipfs": 1.0,
            "local": 1.0,
            "filecoin": 1.0,
            "storacha": 1.0,
            "huggingface": 1.0,
            "lassie": 1.0,
        },
        "geo_preferences": {
            "same_region": 1.2,
            "same_continent": 1.0,
            "different_continent": 0.8,
        },
    },
    "archive": {
        "name": "archive",
        "description": "Optimize for long-term storage with multiple replicas",
        "cost_weight": 0.5,
        "performance_weight": 0.1,
        "reliability_weight": 0.4,
        "max_replicas": 3,
        "content_filters": {"min_size_mb": 10},
        "backend_preferences": {"filecoin": 1.5, "s3": 1.0, "ipfs": 0.8, "local": 0.5},
        "geo_preferences": {
            "same_region": 0.9,
            "same_continent": 1.0,
            "different_continent": 1.1,  # Prefer geographic diversity for archives
        },
    },
    "media-streaming": {
        "name": "media-streaming",
        "description": "Optimize for media streaming with low latency",
        "cost_weight": 0.2,
        "performance_weight": 0.6,
        "reliability_weight": 0.2,
        "max_replicas": 2,
        "content_filters": {"content_types": ["video/", "audio/"]},
        "backend_preferences": {"s3": 1.3, "ipfs": 1.1, "local": 1.0, "filecoin": 0.4},
        "geo_preferences": {
            "same_region": 1.5,
            "same_continent": 1.0,
            "different_continent": 0.5,
        },
    },
}

# Default geo data (region definitions and information)
DEFAULT_GEO_DATA = {
    "regions": {
        "us-east": {
            "name": "US East",
            "continent": "North America",
            "latency_ms": {
                "us-east": 10,
                "us-west": 65,
                "eu-west": 90,
                "eu-central": 110,
                "ap-east": 220,
                "ap-south": 180,
            },
            "ip_ranges": ["52.0.0.0/11", "54.160.0.0/12"],
            "available_backends": ["ipfs", "local", "s3", "filecoin"],
        },
        "us-west": {
            "name": "US West",
            "continent": "North America",
            "latency_ms": {
                "us-east": 65,
                "us-west": 10,
                "eu-west": 130,
                "eu-central": 150,
                "ap-east": 180,
                "ap-south": 190,
            },
            "ip_ranges": ["54.176.0.0/12", "52.8.0.0/13"],
            "available_backends": ["ipfs", "s3", "filecoin"],
        },
        "eu-west": {
            "name": "EU West",
            "continent": "Europe",
            "latency_ms": {
                "us-east": 90,
                "us-west": 130,
                "eu-west": 10,
                "eu-central": 25,
                "ap-east": 240,
                "ap-south": 140,
            },
            "ip_ranges": ["34.240.0.0/13", "54.72.0.0/13"],
            "available_backends": ["ipfs", "s3", "filecoin", "storacha"],
        },
        "eu-central": {
            "name": "EU Central",
            "continent": "Europe",
            "latency_ms": {
                "us-east": 110,
                "us-west": 150,
                "eu-west": 25,
                "eu-central": 10,
                "ap-east": 220,
                "ap-south": 120,
            },
            "ip_ranges": ["52.56.0.0/13", "35.156.0.0/14"],
            "available_backends": ["ipfs", "s3", "filecoin"],
        },
        "ap-east": {
            "name": "Asia Pacific East",
            "continent": "Asia",
            "latency_ms": {
                "us-east": 220,
                "us-west": 180,
                "eu-west": 240,
                "eu-central": 220,
                "ap-east": 10,
                "ap-south": 90,
            },
            "ip_ranges": ["54.248.0.0/13", "52.192.0.0/13"],
            "available_backends": ["ipfs", "s3", "lassie"],
        },
        "ap-south": {
            "name": "Asia Pacific South",
            "continent": "Asia",
            "latency_ms": {
                "us-east": 180,
                "us-west": 190,
                "eu-west": 140,
                "eu-central": 120,
                "ap-east": 90,
                "ap-south": 10,
            },
            "ip_ranges": ["52.66.0.0/13", "13.126.0.0/14"],
            "available_backends": ["ipfs", "s3", "filecoin"],
        },
    }
}

# Default performance data
DEFAULT_PERFORMANCE_DATA = {
    "backend_metrics": {
        "ipfs": {
            "avg_read_latency_ms": 85,
            "avg_write_latency_ms": 120,
            "read_throughput_mbps": 25,
            "write_throughput_mbps": 15,
            "availability_percent": 99.5,
            "error_rate_percent": 0.5,
            "cost_per_gb_usd": 0.005,
            "cold_start_latency_ms": 50,
        },
        "local": {
            "avg_read_latency_ms": 15,
            "avg_write_latency_ms": 30,
            "read_throughput_mbps": 100,
            "write_throughput_mbps": 80,
            "availability_percent": 99.9,
            "error_rate_percent": 0.1,
            "cost_per_gb_usd": 0.001,
            "cold_start_latency_ms": 0,
        },
        "s3": {
            "avg_read_latency_ms": 65,
            "avg_write_latency_ms": 90,
            "read_throughput_mbps": 40,
            "write_throughput_mbps": 35,
            "availability_percent": 99.95,
            "error_rate_percent": 0.2,
            "cost_per_gb_usd": 0.023,
            "cold_start_latency_ms": 0,
        },
        "filecoin": {
            "avg_read_latency_ms": 3500,
            "avg_write_latency_ms": 5000,
            "read_throughput_mbps": 10,
            "write_throughput_mbps": 8,
            "availability_percent": 98.0,
            "error_rate_percent": 1.5,
            "cost_per_gb_usd": 0.002,
            "cold_start_latency_ms": 1000,
        },
        "storacha": {
            "avg_read_latency_ms": 150,
            "avg_write_latency_ms": 180,
            "read_throughput_mbps": 20,
            "write_throughput_mbps": 18,
            "availability_percent": 99.0,
            "error_rate_percent": 0.8,
            "cost_per_gb_usd": 0.015,
            "cold_start_latency_ms": 100,
        },
        "huggingface": {
            "avg_read_latency_ms": 120,
            "avg_write_latency_ms": 150,
            "read_throughput_mbps": 30,
            "write_throughput_mbps": 20,
            "availability_percent": 99.3,
            "error_rate_percent": 0.7,
            "cost_per_gb_usd": 0.01,
            "cold_start_latency_ms": 200,
        },
        "lassie": {
            "avg_read_latency_ms": 100,
            "avg_write_latency_ms": 130,
            "read_throughput_mbps": 15,
            "write_throughput_mbps": 10,
            "availability_percent": 97.0,
            "error_rate_percent": 2.0,
            "cost_per_gb_usd": 0.003,
            "cold_start_latency_ms": 300,
        },
    },
    "regional_adjustments": {
        "us-east": {
            "ipfs": {
                "latency_factor": 0.9,
                "availability_factor": 1.0,
                "cost_factor": 1.0,
            },
            "s3": {
                "latency_factor": 0.8,
                "availability_factor": 1.0,
                "cost_factor": 1.0,
            },
            "filecoin": {
                "latency_factor": 0.9,
                "availability_factor": 1.0,
                "cost_factor": 1.0,
            },
        },
        "eu-west": {
            "ipfs": {
                "latency_factor": 0.95,
                "availability_factor": 1.0,
                "cost_factor": 1.1,
            },
            "s3": {
                "latency_factor": 0.85,
                "availability_factor": 1.0,
                "cost_factor": 1.2,
            },
            "filecoin": {
                "latency_factor": 1.0,
                "availability_factor": 0.99,
                "cost_factor": 1.1,
            },
        },
        "ap-east": {
            "ipfs": {
                "latency_factor": 1.1,
                "availability_factor": 0.98,
                "cost_factor": 1.2,
            },
            "s3": {
                "latency_factor": 1.0,
                "availability_factor": 0.99,
                "cost_factor": 1.3,
            },
            "filecoin": {
                "latency_factor": 1.2,
                "availability_factor": 0.97,
                "cost_factor": 1.1,
            },
        },
    },
    "content_type_metrics": {
        "image": {
            "ipfs": {"score": 0.9},
            "s3": {"score": 0.8},
            "filecoin": {"score": 0.7},
            "local": {"score": 0.9},
        },
        "video": {
            "ipfs": {"score": 0.7},
            "s3": {"score": 0.9},
            "filecoin": {"score": 0.6},
            "local": {"score": 0.8},
        },
        "document": {
            "ipfs": {"score": 0.8},
            "s3": {"score": 0.8},
            "filecoin": {"score": 0.9},
            "local": {"score": 0.8},
        },
        "audio": {
            "ipfs": {"score": 0.8},
            "s3": {"score": 0.9},
            "filecoin": {"score": 0.7},
            "local": {"score": 0.8},
        },
        "application": {
            "ipfs": {"score": 0.8},
            "s3": {"score": 0.8},
            "filecoin": {"score": 0.7},
            "local": {"score": 0.9},
        },
        "text": {
            "ipfs": {"score": 0.9},
            "s3": {"score": 0.8},
            "filecoin": {"score": 0.8},
            "local": {"score": 0.9},
        },
        "model": {
            "ipfs": {"score": 0.7},
            "s3": {"score": 0.8},
            "filecoin": {"score": 0.6},
            "huggingface": {"score": 1.0},
            "local": {"score": 0.7},
        },
        "dataset": {
            "ipfs": {"score": 0.8},
            "s3": {"score": 0.9},
            "filecoin": {"score": 0.7},
            "huggingface": {"score": 0.9},
            "local": {"score": 0.7},
        },
    },
}

# Data structures for runtime routing information
routing_config = DEFAULT_ROUTING_CONFIG.copy()
routing_policies = DEFAULT_ROUTING_POLICIES.copy()
geo_data = DEFAULT_GEO_DATA.copy()
performance_data = DEFAULT_PERFORMANCE_DATA.copy()
routing_cache = {}
routing_statistics = {
    "total_decisions": 0,
    "backend_selections": {},
    "policy_usage": {},
    "content_type_distribution": {},
    "avg_decision_time_ms": 0,
}


# Data models
class ContentAttributes(BaseModel):
    """Content attributes for routing decisions."""
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    filename: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    read_intensive: Optional[bool] = False
    write_intensive: Optional[bool] = False
    access_frequency: Optional[str] = None
    retention_period: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class RoutingConfig(BaseModel):
    """Global routing configuration."""
    enabled: bool = True
    default_policy: str = "balanced"
    auto_detect_region: bool = True
    preferred_regions: List[str] = ["us-east", "eu-west"]
    cost_weight: float = Field(0.3, ge=0.0, le=1.0)
    performance_weight: float = Field(0.4, ge=0.0, le=1.0)
    reliability_weight: float = Field(0.3, ge=0.0, le=1.0)
    max_backend_selection: int = Field(3, ge=1, le=10)
    minimum_backend_score: float = Field(0.5, ge=0.0, le=1.0)
    content_type_analysis: bool = True
    bandwidth_tracking: bool = True
    latency_tracking: bool = True
    cold_start_estimation: bool = True
    update_interval_seconds: int = 300
    adaptive_routing: bool = True
    metrics_enabled: bool = True

    @validator("cost_weight", "performance_weight", "reliability_weight")
    def weights_sum_to_one(cls, v, values):
        """Validate that weights sum to 1.0."""
        if "cost_weight" in values and "performance_weight" in values:
            total = values["cost_weight"] + values["performance_weight"] + v
            if not math.isclose(total, 1.0, abs_tol=0.01):
                raise ValueError("Weights must sum to 1.0")
        return v


class RoutingPolicy(BaseModel):
    """Routing policy definition."""
    name: str
    description: Optional[str] = None
    cost_weight: float = Field(0.33, ge=0.0, le=1.0)
    performance_weight: float = Field(0.33, ge=0.0, le=1.0)
    reliability_weight: float = Field(0.34, ge=0.0, le=1.0)
    max_replicas: int = Field(1, ge=1, le=5)
    content_filters: Dict[str, Any] = {}
    backend_preferences: Dict[str, float] = {}
    geo_preferences: Dict[str, float] = {}

    @validator("cost_weight", "performance_weight", "reliability_weight")
    def weights_sum_to_one_v2(cls, v, values):
        """Validate that weights sum to 1.0."""
        if "cost_weight" in values and "performance_weight" in values:
            total = values["cost_weight"] + values["performance_weight"] + v
            if not math.isclose(total, 1.0, abs_tol=0.01):
                raise ValueError("Weights must sum to 1.0")
        return v


class RoutingRequest(BaseModel):
    """Routing decision request."""
    operation: str = Field(..., description="Operation type (read, write, etc.)")
    content_attributes: Optional[ContentAttributes] = None
    policy_name: Optional[str] = None
    client_region: Optional[str] = None
    client_ip: Optional[str] = None
    replication_factor: Optional[int] = 1
    required_backends: Optional[List[str]] = []
    excluded_backends: Optional[List[str]] = []


class BackendScore(BaseModel):
    """Score and metrics for a backend."""
    backend: str
    score: float
    cost_score: float
    performance_score: float
    reliability_score: float
    region: Optional[str] = None
    metrics: Dict[str, Any] = {}


class RoutingDecision(BaseModel):
    """Routing decision result."""
    primary_backend: str
    replicas: List[str] = []
    backend_scores: List[BackendScore] = []
    applied_policy: str
    decision_time_ms: float
    client_region: Optional[str] = None
    content_type: Optional[str] = None
    operation: str
    decision_id: str
    timestamp: float


# Initialization functions
def initialize_routing_config():
    """Initialize routing configuration from file or defaults."""
    global routing_config
    try:
        if os.path.exists(ROUTING_CONFIG_PATH):
            with open(ROUTING_CONFIG_PATH, "r") as f:
                routing_config = json.load(f)
            logger.info(f"Loaded routing configuration from {ROUTING_CONFIG_PATH}")
        else:
            routing_config = DEFAULT_ROUTING_CONFIG.copy()
            with open(ROUTING_CONFIG_PATH, "w") as f:
                json.dump(routing_config, f, indent=2)
            logger.info(f"Created default routing configuration in {ROUTING_CONFIG_PATH}")
    except Exception as e:
        logger.error(f"Error initializing routing configuration: {e}")
        routing_config = DEFAULT_ROUTING_CONFIG.copy()


def initialize_routing_policies():
    """Initialize routing policies from file or defaults."""
    global routing_policies
    try:
        if os.path.exists(ROUTING_POLICY_PATH):
            with open(ROUTING_POLICY_PATH, "r") as f:
                routing_policies = json.load(f)
            logger.info(f"Loaded routing policies from {ROUTING_POLICY_PATH}")
        else:
            routing_policies = DEFAULT_ROUTING_POLICIES.copy()
            with open(ROUTING_POLICY_PATH, "w") as f:
                json.dump(routing_policies, f, indent=2)
            logger.info(f"Created default routing policies in {ROUTING_POLICY_PATH}")
    except Exception as e:
        logger.error(f"Error initializing routing policies: {e}")
        routing_policies = DEFAULT_ROUTING_POLICIES.copy()


def initialize_geo_data():
    """Initialize geo data from file or defaults."""
    global geo_data
    try:
        if os.path.exists(GEO_DATA_PATH):
            with open(GEO_DATA_PATH, "r") as f:
                geo_data = json.load(f)
            logger.info(f"Loaded geo data from {GEO_DATA_PATH}")
        else:
            geo_data = DEFAULT_GEO_DATA.copy()
            with open(GEO_DATA_PATH, "w") as f:
                json.dump(geo_data, f, indent=2)
            logger.info(f"Created default geo data in {GEO_DATA_PATH}")
    except Exception as e:
        logger.error(f"Error initializing geo data: {e}")
        geo_data = DEFAULT_GEO_DATA.copy()


def initialize_performance_data():
    """Initialize performance data from file or defaults."""
    global performance_data
    try:
        if os.path.exists(PERFORMANCE_DATA_PATH):
            with open(PERFORMANCE_DATA_PATH, "r") as f:
                performance_data = json.load(f)
            logger.info(f"Loaded performance data from {PERFORMANCE_DATA_PATH}")
        else:
            performance_data = DEFAULT_PERFORMANCE_DATA.copy()
            with open(PERFORMANCE_DATA_PATH, "w") as f:
                json.dump(performance_data, f, indent=2)
            logger.info(f"Created default performance data in {PERFORMANCE_DATA_PATH}")
    except Exception as e:
        logger.error(f"Error initializing performance data: {e}")
        performance_data = DEFAULT_PERFORMANCE_DATA.copy()


# Save functions
def save_routing_config():
    """Save routing configuration to file."""
    try:
        with open(ROUTING_CONFIG_PATH, "w") as f:
            json.dump(routing_config, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving routing configuration: {e}")


def save_routing_policies():
    """Save routing policies to file."""
    try:
        with open(ROUTING_POLICY_PATH, "w") as f:
            json.dump(routing_policies, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving routing policies: {e}")


def save_geo_data():
    """Save geo data to file."""
    try:
        with open(GEO_DATA_PATH, "w") as f:
            json.dump(geo_data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving geo data: {e}")


def save_performance_data():
    """Save performance data to file."""
    try:
        with open(PERFORMANCE_DATA_PATH, "w") as f:
            json.dump(performance_data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving performance data: {e}")


# Helper functions
def detect_region_from_ip(ip_address: str) -> Optional[str]:
    """Detect region from an IP address."""
    try:
        ip = ipaddress.ip_address(ip_address)

        # Check each region's IP ranges
        for region_id, region_info in geo_data["regions"].items():
            for ip_range_str in region_info.get("ip_ranges", []):
                ip_network = ipaddress.ip_network(ip_range_str)
                if ip in ip_network:
                    return region_id

        # If no specific match, use a simple geographic heuristic
        # In a real implementation, this would use a GeoIP database
        if ip.is_global:
            first_octet = int(ip_address.split(".")[0])
            if first_octet < 50:
                return "us-east"
            elif first_octet < 100:
                return "eu-west"
            elif first_octet < 150:
                return "ap-east"
            else:
                return "us-west"
    except Exception as e:
        logger.error(f"Error detecting region from IP {ip_address}: {e}")

    # Return default region if detection fails
    return routing_config["preferred_regions"][0] if routing_config["preferred_regions"] else None


def detect_content_type_category(content_type: str) -> str:
    """Detect content type category from MIME type."""
    if not content_type:
        return "unknown"

    main_type = content_type.split("/")[0].lower()

    # Map main types to categories
    if main_type in ["image"]:
        return "image"
    elif main_type in ["video"]:
        return "video"
    elif main_type in ["audio"]:
        return "audio"
    elif main_type in ["text"]:
        return "text"
    elif main_type in ["application"]:
        # Check for specific subtypes
        if any(
            subtype in content_type.lower()
            for subtype in ["pdf", "document", "word", "excel", "powerpoint"]
        ):
            return "document"
        elif any(subtype in content_type.lower() for subtype in ["json", "xml", "yaml"]):
            return "text"
        elif any(
            subtype in content_type.lower()
            for subtype in ["model", "tensorflow", "pytorch", "onnx"]
        ):
            return "model"
        elif any(subtype in content_type.lower() for subtype in ["dataset", "csv", "parquet"]):
            return "dataset"
        else:
            return "application"

    return "unknown"


def get_region_latency(source_region: str, target_region: str) -> int:
    """Get latency between two regions in milliseconds."""
    if source_region == target_region:
        return 0

    if source_region in geo_data["regions"] and target_region in geo_data["regions"].get(
        source_region, {}
    ).get("latency_ms", {}):
        return geo_data["regions"][source_region]["latency_ms"].get(target_region, 200)

    # Default latency if not specified
    return 200


def get_backend_metrics(backend: str, region: Optional[str] = None) -> Dict[str, Any]:
    """Get performance metrics for a backend, adjusted for region if specified."""
    metrics = performance_data["backend_metrics"].get(backend, {}).copy()

    # Apply regional adjustments if available
    if region and region in performance_data.get("regional_adjustments", {}):
        regional_adj = performance_data["regional_adjustments"][region].get(backend, {})

        for factor, value in regional_adj.items():
            if factor == "latency_factor": ,
                metrics["avg_read_latency_ms"] = metrics.get("avg_read_latency_ms", 100) * value
                metrics["avg_write_latency_ms"] = metrics.get("avg_write_latency_ms", 150) * value
            elif factor == "availability_factor": ,
                metrics["availability_percent"] = metrics.get("availability_percent", 99.0) * value
            elif factor == "cost_factor": ,
                metrics["cost_per_gb_usd"] = metrics.get("cost_per_gb_usd", 0.01) * value

    return metrics


def score_backend_for_content_type(backend: str, content_type_category: str) -> float:
    """Score a backend for a specific content type category."""
    if not content_type_category or content_type_category == "unknown": ,
        return 1.0

    type_metrics = performance_data.get("content_type_metrics", {}).get(content_type_category, {})
    return type_metrics.get(backend, {}).get("score", 0.7)


def evaluate_policy_match(
    policy: Dict[str, Any], content_attributes: Optional[ContentAttributes]
) -> bool:
    """Evaluate if a policy matches the content attributes."""
    if not content_attributes:
        return True

    content_filters = policy.get("content_filters", {})

    # Check min size filter
    min_size_mb = content_filters.get("min_size_mb")
    if min_size_mb is not None and content_attributes.size_bytes is not None:
        size_mb = content_attributes.size_bytes / (1024 * 1024)
        if size_mb < min_size_mb:
            return False

    # Check max size filter
    max_size_mb = content_filters.get("max_size_mb")
    if max_size_mb is not None and content_attributes.size_bytes is not None:
        size_mb = content_attributes.size_bytes / (1024 * 1024)
        if size_mb > max_size_mb:
            return False

    # Check content type filter
    content_types = content_filters.get("content_types")
    if content_types and content_attributes.content_type:
        matched = False
        for ct in content_types:
            if ct in content_attributes.content_type:
                matched = True
                break
        if not matched:
            return False

    return True


def calculate_backend_scores(
    available_backends: List[str]
    operation: str
    content_type_category: str
    policy: Dict[str, Any]
    client_region: Optional[str]
    excluded_backends: List[str] = [],
) -> List[BackendScore]:
    """Calculate scores for each available backend."""
    results = []

    # Get weights from policy
    cost_weight = policy.get("cost_weight", 0.33)
    performance_weight = policy.get("performance_weight", 0.33)
    reliability_weight = policy.get("reliability_weight", 0.34)

    # Get backend preferences from policy
    backend_preferences = policy.get("backend_preferences", {})

    # Geo preferences
    geo_preferences = policy.get("geo_preferences", {})

    for backend in available_backends:
        # Skip explicitly excluded backends
        if backend in excluded_backends:
            continue

        # Skip unavailable backends
        if not storage_backends.get(backend, {}).get("available", False):
            continue

        # Get base metrics for this backend
        metrics = get_backend_metrics(backend, client_region)
        if not metrics:
            continue

        # Determine backend region if geo data is available
        backend_region = None
        if client_region and client_region in geo_data["regions"]:
            # In a real implementation, this would be more sophisticated
            # For now, we'll use the client region and evaluate backends that are available there
            region_info = geo_data["regions"][client_region]
            if backend in region_info.get("available_backends", []):
                backend_region = client_region

        # Calculate cost score (lower is better -> invert)
        cost_per_gb = metrics.get("cost_per_gb_usd", 0.01)
        cost_score = 1.0 - min(cost_per_gb / 0.05, 1.0)  # Normalize to 0-1 range

        # Calculate performance score
        perf_score = 0.0
        if operation == "read": ,
            # For reads, lower latency and higher throughput is better
            read_latency = metrics.get("avg_read_latency_ms", 100)
            read_throughput = metrics.get("read_throughput_mbps", 20)

            # Normalize and combine
            latency_score = 1.0 - min(read_latency / 1000.0, 1.0)  # 0ms=1.0, 1000ms+=0.0
            throughput_score = min(read_throughput / 100.0, 1.0)  # 0=0.0, 100+=1.0

            perf_score = (latency_score * 0.7) + (throughput_score * 0.3)
        else:  # write
            # For writes, similar but with write metrics
            write_latency = metrics.get("avg_write_latency_ms", 150)
            write_throughput = metrics.get("write_throughput_mbps", 15)

            # Normalize and combine
            latency_score = 1.0 - min(write_latency / 1500.0, 1.0)  # 0ms=1.0, 1500ms+=0.0
            throughput_score = min(write_throughput / 80.0, 1.0)  # 0=0.0, 80+=1.0

            perf_score = (latency_score * 0.7) + (throughput_score * 0.3)

        # Calculate reliability score
        availability = metrics.get("availability_percent", 99.0)
        error_rate = metrics.get("error_rate_percent", 1.0)

        # Normalize and combine
        availability_score = min((availability - 90.0) / 10.0, 1.0)  # 90%=0.0, 100%=1.0
        error_score = 1.0 - min(error_rate / 5.0, 1.0)  # 0%=1.0, 5%+=0.0

        reliability_score = (availability_score * 0.7) + (error_score * 0.3)

        # Apply content type factor
        content_type_factor = score_backend_for_content_type(backend, content_type_category)

        # Apply backend preference factor
        backend_factor = backend_preferences.get(backend, 1.0)

        # Apply geo preference factor
        geo_factor = 1.0
        if client_region and backend_region:
            if client_region == backend_region:
                geo_factor = geo_preferences.get("same_region", 1.0)
            elif (
                client_region in geo_data["regions"]
                and backend_region in geo_data["regions"]
                and geo_data["regions"][client_region].get("continent")
                == geo_data["regions"][backend_region].get("continent")
            ):
                geo_factor = geo_preferences.get("same_continent", 1.0)
            else:
                geo_factor = geo_preferences.get("different_continent", 1.0)

        # Combine scores with weights
        final_score = (
            (
                (cost_score * cost_weight)
                + (perf_score * performance_weight)
                + (reliability_score * reliability_weight)
            )
            * content_type_factor
            * backend_factor
            * geo_factor
        )

        # Create result object
        result = BackendScore(
            backend=backend,
            score=final_score,
            cost_score=cost_score,
            performance_score=perf_score,
            reliability_score=reliability_score,
            region=backend_region,
            metrics={
                "cost_per_gb_usd": cost_per_gb,
                "latency_ms": metrics.get(,
                    "avg_read_latency_ms" if operation == "read" else "avg_write_latency_ms"
                ),
                "throughput_mbps": metrics.get(,
                    "read_throughput_mbps" if operation == "read" else "write_throughput_mbps"
                ),
                "availability_percent": availability,
                "error_rate_percent": error_rate,
                "content_type_factor": content_type_factor,
                "backend_factor": backend_factor,
                "geo_factor": geo_factor,
            },
        )

        results.append(result)

    # Sort by score, highest first
    results.sort(key=lambda x: x.score, reverse=True)
    return results


def make_routing_decision(request: RoutingRequest) -> RoutingDecision:
    """Make a routing decision based on the request parameters."""
    start_time = time.time()

    # Initialize decision ID and defaults
    decision_id = f"route_{int(time.time())}_{hash(str(request))}"
    client_region = request.client_region
    primary_backend = None
    replicas = []
    applied_policy = routing_config["default_policy"]

    # Simple caching for identical requests
    # In a real implementation, this would use a proper cache with TTL
    request_hash = hash(str(request))
    if request_hash in routing_cache:
        cached_decision = routing_cache[request_hash]
        # Check if cache is still valid (1 minute TTL)
        if time.time() - cached_decision.timestamp < 60:
            return cached_decision

    try:
        # Auto-detect region if enabled and not provided
        if routing_config["auto_detect_region"] and not client_region and request.client_ip:
            client_region = detect_region_from_ip(request.client_ip)

        # Default to first preferred region if no region detected
        if not client_region and routing_config["preferred_regions"]:
            client_region = routing_config["preferred_regions"][0]

        # Determine content type category for content-aware routing
        content_type_category = "unknown"
        if request.content_attributes and request.content_attributes.content_type:
            content_type_category = detect_content_type_category(
                request.content_attributes.content_type
            )

        # Select policy
        policy_name = request.policy_name or routing_config["default_policy"]
        if policy_name not in routing_policies:
            policy_name = routing_config["default_policy"]

        policy = routing_policies[policy_name]
        applied_policy = policy_name

        # Check if policy matches content attributes
        if not evaluate_policy_match(policy, request.content_attributes):
            # If policy doesn't match, fall back to default policy
            policy = routing_policies[routing_config["default_policy"]]
            applied_policy = routing_config["default_policy"]

        # Get list of available backends
        available_backends = [
            name for name, info in storage_backends.items() if info.get("available", False)
        ]

        # Add required backends if they're not already in the list
        for backend in request.required_backends or []:
            if backend not in available_backends and storage_backends.get(backend, {}).get(
                "available", False
            ):
                available_backends.append(backend)

        # Calculate backend scores
        backend_scores = calculate_backend_scores(
            available_backends=available_backends,
            operation=request.operation,
            content_type_category=content_type_category,
            policy=policy,
            client_region=client_region,
            excluded_backends=request.excluded_backends or [],
        )

        # Apply minimum score threshold
        qualified_backends = [
            b for b in backend_scores if b.score >= routing_config["minimum_backend_score"]
        ]

        # Ensure required backends are included, even if score is too low
        if request.required_backends:
            required_backends_set = set(request.required_backends)
            qualified_backends_set = {b.backend for b in qualified_backends}
            missing_required = required_backends_set - qualified_backends_set

            # Add missing required backends
            for backend in missing_required:
                if backend in [b.backend for b in backend_scores]:
                    # Get the backend from the original scores
                    for b in backend_scores:
                        if b.backend == backend:
                            qualified_backends.append(b)
                            break

        # Select primary backend and replicas
        if qualified_backends:
            # Primary backend is highest scored
            primary_backend = qualified_backends[0].backend

            # Determine replication factor
            replication_factor = min(
                request.replication_factor or 1,
                policy.get("max_replicas", 1),
                len(qualified_backends) - 1,
            )

            # Select replicas (next highest scores)
            replicas = [b.backend for b in qualified_backends[1 : 1 + replication_factor]]

        # If no backends qualified, use best available
        if not primary_backend and backend_scores:
            primary_backend = backend_scores[0].backend

        # If still no primary backend, use default fallback
        if not primary_backend:
            primary_backend = (
                "ipfs"
                if "ipfs" in storage_backends and storage_backends["ipfs"].get("available", False)
                else "local"
            )

        # Update statistics
        routing_statistics["total_decisions"] += 1

        if primary_backend not in routing_statistics["backend_selections"]:
            routing_statistics["backend_selections"][primary_backend] = 0
        routing_statistics["backend_selections"][primary_backend] += 1

        if applied_policy not in routing_statistics["policy_usage"]:
            routing_statistics["policy_usage"][applied_policy] = 0
        routing_statistics["policy_usage"][applied_policy] += 1

        if content_type_category not in routing_statistics["content_type_distribution"]:
            routing_statistics["content_type_distribution"][content_type_category] = 0
        routing_statistics["content_type_distribution"][content_type_category] += 1

        decision_time = (time.time() - start_time) * 1000
        routing_statistics["avg_decision_time_ms"] = (
            routing_statistics["avg_decision_time_ms"] * (routing_statistics["total_decisions"] - 1)
            + decision_time
        ) / routing_statistics["total_decisions"]

        # Create decision result
        decision = RoutingDecision(
            primary_backend=primary_backend,
            replicas=replicas,
            backend_scores=backend_scores,
            applied_policy=applied_policy,
            decision_time_ms=decision_time,
            client_region=client_region,
            content_type=content_type_category,
            operation=request.operation,
            decision_id=decision_id,
            timestamp=time.time(),
        )

        # Cache the decision
        routing_cache[request_hash] = decision

        return decision

    except Exception as e:
        logger.error(f"Error making routing decision: {e}")

        # Return a fallback decision
        fallback_backend = (
            "ipfs"
            if "ipfs" in storage_backends and storage_backends["ipfs"].get("available", False)
            else "local"
        )

        decision_time = (time.time() - start_time) * 1000
        return RoutingDecision(
            primary_backend=fallback_backend,
            replicas=[],
            backend_scores=[],
            applied_policy="fallback",
            decision_time_ms=decision_time,
            client_region=client_region,
            content_type=(
                request.content_attributes.content_type if request.content_attributes else None
            ),
            operation=request.operation,
            decision_id=decision_id,
            timestamp=time.time(),
        )


def update_performance_metrics():
    """Update performance metrics with real data."""
    # In a real implementation, this would collect and analyze real performance data
    # For this demo, we'll simulate some random variations
    for backend, metrics in performance_data["backend_metrics"].items():
        # Don't update unavailable backends
        if not storage_backends.get(backend, {}).get("available", False):
            continue

        # Add small random variations to simulate real-world fluctuations
        for metric in ["avg_read_latency_ms", "avg_write_latency_ms"]:
            if metric in metrics:
                # Variation of ±10%
                variation = 0.9 + (random.random() * 0.2)
                metrics[metric] *= variation

        for metric in ["read_throughput_mbps", "write_throughput_mbps"]:
            if metric in metrics:
                # Variation of ±15%
                variation = 0.85 + (random.random() * 0.3)
                metrics[metric] *= variation

        for metric in ["availability_percent"]:
            if metric in metrics:
                # Smaller variation for availability (±1%)
                variation = 0.99 + (random.random() * 0.02)
                metrics[metric] = min(metrics[metric] * variation, 100.0)

        for metric in ["error_rate_percent"]:
            if metric in metrics:
                # Variation of ±20%
                variation = 0.8 + (random.random() * 0.4)
                metrics[metric] *= variation


# Background task for periodic updates
async def periodic_metrics_update():
    """Periodically update metrics and performance data."""
    while True:
        try:
            # Update performance metrics
            update_performance_metrics()

            # Save performance data
            save_performance_data()

            # Wait for next update interval
            await asyncio.sleep(routing_config["update_interval_seconds"])
        except Exception as e:
            logger.error(f"Error in periodic metrics update: {e}")
            await asyncio.sleep(60)  # Wait a minute and try again


# Create router
def create_routing_router(api_prefix: str) -> APIRouter:
    """Create FastAPI router for routing endpoints."""
    router = APIRouter(prefix=f"{api_prefix}/routing", tags=["routing"])

    @router.get("/status")
    async def get_routing_status():
        """Get routing service status."""
        return {
            "success": True,
            "enabled": routing_config["enabled"],
            "default_policy": routing_config["default_policy"],
            "available_policies": list(routing_policies.keys()),
            "available_backends": [,
                name for name, info in storage_backends.items() if info.get("available", False)
            ],
            "regions": list(geo_data["regions"].keys()),
            "stats": {
                "total_decisions": routing_statistics["total_decisions"],
                "avg_decision_time_ms": routing_statistics["avg_decision_time_ms"],
                "top_backends": (,
                    sorted(
                        routing_statistics["backend_selections"].items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:3]
                    if routing_statistics["backend_selections"]
                    else []
                ),
                "top_policies": (,
                    sorted(
                        routing_statistics["policy_usage"].items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:3]
                    if routing_statistics["policy_usage"]
                    else []
                ),
            },
        }

    @router.post("/decision")
    async def get_routing_decision(request: RoutingRequest, client_request: Request = None):
        """Get a routing decision based on request parameters."""
        if not routing_config["enabled"]:
            # Return default backend if routing is disabled
            return {
                "success": True,
                "primary_backend": (,
                    "ipfs" if storage_backends.get("ipfs", {}).get("available", True) else "local"
                ),
                "replicas": [],
                "applied_policy": "disabled",
                "decision_id": f"route_{int(time.time())}",
                "timestamp": time.time(),
            }

        # If client_ip not provided in request but available in actual request, use it
        if not request.client_ip and client_request:
            request.client_ip = client_request.client.host

        # Make routing decision
        decision = make_routing_decision(request)

        # Return simplified response
        return {
            "success": True,
            "primary_backend": decision.primary_backend,
            "replicas": decision.replicas,
            "backend_scores": [,
                {
                    "backend": score.backend,
                    "score": round(score.score, 3),
                    "region": score.region,
                }
                for score in decision.backend_scores[:5]  # Top 5 backends
            ],
            "applied_policy": decision.applied_policy,
            "client_region": decision.client_region,
            "decision_time_ms": round(decision.decision_time_ms, 2),
            "decision_id": decision.decision_id,
            "timestamp": decision.timestamp,
        }

    @router.get("/config")
    async def get_routing_config():
        """Get current routing configuration."""
        return {"success": True, "config": routing_config}

    @router.put("/config")
    async def update_routing_config(config: RoutingConfig):
        """Update routing configuration."""
        global routing_config

        # Update config
        routing_config = config.dict()

        # Save to file
        save_routing_config()

        return {
            "success": True,
            "message": "Routing configuration updated successfully",
        }

    @router.get("/policies")
    async def list_routing_policies():
        """List all routing policies."""
        return {"success": True, "policies": routing_policies}

    @router.get("/policies/{name}")
    async def get_routing_policy(name: str):
        """Get a specific routing policy."""
        if name not in routing_policies:
            raise HTTPException(status_code=404, detail=f"Policy {name} not found")

        return {"success": True, "policy": routing_policies[name]}

    @router.post("/policies")
    async def create_routing_policy(policy: RoutingPolicy):
        """Create or update a routing policy."""
        # Store policy
        routing_policies[policy.name] = policy.dict()

        # Save to file
        save_routing_policies()

        return {
            "success": True,
            "message": f"Policy {policy.name} created/updated successfully",
        }

    @router.delete("/policies/{name}")
    async def delete_routing_policy(name: str):
        """Delete a routing policy."""
        if name not in routing_policies:
            raise HTTPException(status_code=404, detail=f"Policy {name} not found")

        # Don't allow deleting default policy
        if name == routing_config["default_policy"]:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the default policy. Change default_policy first.",
            )

        # Delete policy
        del routing_policies[name]

        # Save to file
        save_routing_policies()

        return {"success": True, "message": f"Policy {name} deleted successfully"}

    @router.get("/regions")
    async def list_regions():
        """List all geographic regions."""
        return {"success": True, "regions": geo_data["regions"]}

    @router.get("/metrics")
    async def get_performance_metrics():
        """Get performance metrics for all backends."""
        return {"success": True, "metrics": performance_data["backend_metrics"]}

    @router.get("/metrics/{backend}")
    async def get_backend_metrics_v2(backend: str):
        """Get performance metrics for a specific backend."""
        if backend not in performance_data["backend_metrics"]:
            raise HTTPException(status_code=404, detail=f"Metrics for backend {backend} not found")

        return {
            "success": True,
            "backend": backend,
            "metrics": performance_data["backend_metrics"][backend],
        }

    @router.post("/content-type-analysis")
    async def analyze_content_type(
        content_type: str, size_bytes: Optional[int] = None, operation: str = "read"
    ):
        """Analyze a content type to get optimal backend recommendations."""
        if not routing_config["content_type_analysis"]:
            return {"success": False, "message": "Content type analysis is disabled"}

        content_category = detect_content_type_category(content_type)

        # Get available backends
        [name for name, info in storage_backends.items() if info.get("available", False)]

        # Create a minimal request
        request = RoutingRequest(
            operation=operation,
            content_attributes=ContentAttributes(content_type=content_type, size_bytes=size_bytes),
        )

        # Make routing decision
        decision = make_routing_decision(request)

        return {
            "success": True,
            "content_type": content_type,
            "content_category": content_category,
            "recommended_backends": {
                "primary": decision.primary_backend,
                "alternatives": decision.replicas,
            },
            "backend_scores": [,
                {
                    "backend": score.backend,
                    "score": round(score.score, 3),
                    "cost_score": round(score.cost_score, 3),
                    "performance_score": round(score.performance_score, 3),
                    "reliability_score": round(score.reliability_score, 3),
                }
                for score in decision.backend_scores
            ],
            "applied_policy": decision.applied_policy,
        }

    @router.post("/simulate")
    async def simulate_routing(
        num_requests: int = Query(10, gt=0, le=100),
        operations: List[str] = Query(["read", "write"]),
        content_types: List[str] = Query(
            ["text/plain", "image/jpeg", "video/mp4", "application/pdf"]
        ),
        size_range_mb: List[int] = Query([1, 100]),
    ):
        """Simulate multiple routing decisions with random parameters."""
        if not routing_config["enabled"]:
            return {"success": False, "message": "Routing is disabled"}

        results = []
        size_min, size_max = size_range_mb

        for _ in range(num_requests):
            # Generate random request
            operation = random.choice(operations)
            content_type = random.choice(content_types)
            size_bytes = random.randint(size_min * 1024 * 1024, size_max * 1024 * 1024)

            # Create request
            request = RoutingRequest(
                operation=operation,
                content_attributes=ContentAttributes(
                    content_type=content_type, size_bytes=size_bytes
                ),
            )

            # Make routing decision
            decision = make_routing_decision(request)

            # Store result
            results.append(
                {
                    "content_type": content_type,
                    "size_bytes": size_bytes,
                    "operation": operation,
                    "primary_backend": decision.primary_backend,
                    "replicas": decision.replicas,
                    "applied_policy": decision.applied_policy,
                    "decision_time_ms": round(decision.decision_time_ms, 2),
                }
            )

        # Calculate summary
        backend_counts = {}
        for result in results:
            backend = result["primary_backend"]
            if backend not in backend_counts:
                backend_counts[backend] = 0
            backend_counts[backend] += 1

        return {
            "success": True,
            "simulation_results": results,
            "summary": {
                "total_requests": num_requests,
                "avg_decision_time_ms": round(,
                    sum(r["decision_time_ms"] for r in results) / len(results), 2
                ),
                "backend_distribution": {
                    backend: f"{count} ({round(count / num_requests * 100)}%)"
                    for backend, count in backend_counts.items()
                },
            },
        }

    @router.post("/start-background-tasks")
    async def start_background_tasks(background_tasks: BackgroundTasks):
        """Start background tasks for metrics collection and updates."""
        background_tasks.add_task(periodic_metrics_update)

        return {"success": True, "message": "Background tasks started"}

    @router.post("/update-metrics")
    async def trigger_metrics_update():
        """Manually trigger metrics update."""
        update_performance_metrics()
        save_performance_data()

        return {"success": True, "message": "Performance metrics updated"}

    @router.post("/clear-cache")
    async def clear_routing_cache():
        """Clear the routing decision cache."""
        routing_cache.clear()

        return {"success": True, "message": "Routing cache cleared"}

    return router


# Update storage backends status
def update_routing_status(storage_backends_info: Dict[str, Any]) -> None:
    """Update the reference to storage backends status."""
    global storage_backends
    storage_backends = storage_backends_info


# Initialize
def initialize():
    """Initialize the routing system."""
    initialize_routing_config()
    initialize_routing_policies()
    initialize_geo_data()
    initialize_performance_data()
    logger.info("Routing system initialized")


# Call initialization
initialize()
