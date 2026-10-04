"""
Geographic Optimization Module for MCP Server

This module enhances the Optimized Data Routing feature with geographic awareness:
- Region-based routing decisions
- Latency optimization based on geographic proximity
- Multi-region replication recommendations
- Network topology awareness
- Geographic data distribution analytics

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements.
"""

import logging
import json
import os
import time
import math
from enum import Enum
from typing import Dict, List, Tuple, Set, Optional, Union, Any
from dataclasses import dataclass
from datetime import datetime
import ipaddress
import random
import threading

# Configure logging
logger = logging.getLogger("mcp.routing.geographic")

@dataclass
class GeoCoordinates:
    """Geographic coordinates (latitude/longitude)."""
    latitude: float
    longitude: float
    
    def distance_to(self, other: 'GeoCoordinates') -> float:
        """
        Calculate distance to another point in kilometers.
        
        Args:
            other: Other coordinates
            
        Returns:
            Distance in kilometers
        """
        # Haversine formula for calculating distance on a sphere
        earth_radius = 6371.0  # Earth radius in kilometers
        
        lat1_rad = math.radians(self.latitude)
        lon1_rad = math.radians(self.longitude)
        lat2_rad = math.radians(other.latitude)
        lon2_rad = math.radians(other.longitude)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return earth_radius * c
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude
        }


@dataclass
class GeoRegion:
    """Geographic region information."""
    id: str
    name: str
    coordinates: GeoCoordinates
    country_code: str
    continent: str
    provider: Optional[str] = None
    tier: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "coordinates": self.coordinates.to_dict(),
            "country_code": self.country_code,
            "continent": self.continent,
            "provider": self.provider,
            "tier": self.tier
        }


class GeographicRouter:
    """
    Geographic routing optimization for the MCP server.
    
    This class provides geographic-aware routing capabilities for selecting
    the optimal storage backend based on geographic proximity and network conditions.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the geographic router.
        
        Args:
            config_path: Path to geographic configuration
        """
        # Storage backends by region
        self.backends_by_region: Dict[str, List[str]] = {}
        
        # Region information
        self.regions: Dict[str, GeoRegion] = {}
        
        # Backend region mapping
        self.backend_regions: Dict[str, List[str]] = {}
        
        # Region latency matrix (region_a -> region_b -> latency_ms)
        self.region_latency: Dict[str, Dict[str, float]] = {}
        
        # IP range to region mapping for automatic detection
        self.ip_ranges: Dict[str, List[Tuple[str, str]]] = {}  # region -> [(start_ip, end_ip)]
        
        # Current client region (if detected)
        self.current_region: Optional[str] = None
        
        # Client location coordinates (for distance calculations)
        self.client_location: Optional[GeoCoordinates] = None
        
        # Load configuration
        if config_path:
            self.load_config(config_path)
        else:
            # Try default locations
            default_paths = [
                os.path.join(os.path.dirname(__file__), "geo_config.json"),
                os.path.join(os.path.expanduser("~"), ".ipfs_kit", "geo_config.json"),
                "/etc/ipfs_kit/geo_config.json"
            ]
            
            for path in default_paths:
                if os.path.exists(path):
                    self.load_config(path)
                    break
        
        logger.info(f"Geographic Router initialized with {len(self.regions)} regions")
    
    def load_config(self, config_path: str) -> bool:
        """
        Load geographic configuration from file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            True if configuration was loaded successfully
        """
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Load regions
            if "regions" in config:
                for region_data in config["regions"]:
                    region_id = region_data["id"]
                    
                    # Create GeoCoordinates
                    coords = GeoCoordinates(
                        latitude=float(region_data["coordinates"]["latitude"]),
                        longitude=float(region_data["coordinates"]["longitude"])
                    )
                    
                    # Create GeoRegion
                    region = GeoRegion(
                        id=region_id,
                        name=region_data["name"],
                        coordinates=coords,
                        country_code=region_data["country_code"],
                        continent=region_data["continent"],
                        provider=region_data.get("provider"),
                        tier=region_data.get("tier")
                    )
                    
                    self.regions[region_id] = region
            
            # Load backend-region mappings
            if "backend_regions" in config:
                for backend, regions in config["backend_regions"].items():
                    self.backend_regions[backend] = regions
                    
                    # Also add to regions-backends mapping
                    for region_id in regions:
                        if region_id not in self.backends_by_region:
                            self.backends_by_region[region_id] = []
                        
                        if backend not in self.backends_by_region[region_id]:
                            self.backends_by_region[region_id].append(backend)
            
            # Load region latency matrix
            if "region_latency" in config:
                self.region_latency = config["region_latency"]
            
            # Load IP ranges
            if "ip_ranges" in config:
                for region_id, ranges in config["ip_ranges"].items():
                    if region_id not in self.ip_ranges:
                        self.ip_ranges[region_id] = []
                    
                    for ip_range in ranges:
                        start_ip = ip_range["start_ip"]
                        end_ip = ip_range["end_ip"]
                        self.ip_ranges[region_id].append((start_ip, end_ip))
            
            # Set current region if specified
            if "current_region" in config:
                self.current_region = config["current_region"]
            
            logger.info(f"Loaded geographic configuration from {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading geographic configuration: {e}")
            return False
    
    def determine_client_region(self, client_ip: str) -> Optional[str]:
        """
        Determine the geographic region for a client IP address.
        
        Args:
            client_ip: Client IP address
            
        Returns:
            Region ID or None if region cannot be determined
        """
        if not client_ip or client_ip == "127.0.0.1" or client_ip == "localhost":
            # Local client, use current region
            return self.current_region
        
        try:
            # Convert client IP to integer for comparison
            client_ip_obj = ipaddress.ip_address(client_ip)
            client_ip_int = int(client_ip_obj)
            
            # Check IP ranges for each region
            for region_id, ranges in self.ip_ranges.items():
                for start_ip, end_ip in ranges:
                    start_ip_int = int(ipaddress.ip_address(start_ip))
                    end_ip_int = int(ipaddress.ip_address(end_ip))
                    
                    if start_ip_int <= client_ip_int <= end_ip_int:
                        return region_id
            
            # No match found
            return None
            
        except Exception as e:
            logger.warning(f"Error determining client region for IP {client_ip}: {e}")
            return None
    
    def get_region_for_backend(self, backend_id: str) -> List[str]:
        """
        Get the regions a backend is located in.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            List of region IDs
        """
        return self.backend_regions.get(backend_id, [])
    
    def get_backend_region(self, backend_id: str) -> Optional[str]:
        """
        Get the primary region for a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Primary region ID or None if backend is not registered
        """
        regions = self.backend_regions.get(backend_id, [])
        return regions[0] if regions else None
    
    def get_backend_location(self, backend_id: str) -> Optional[GeoCoordinates]:
        """
        Get the geographic location of a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            GeoCoordinates object or None if location is unknown
        """
        # Get the primary region for this backend
        region_id = self.get_backend_region(backend_id)
        if not region_id or region_id not in self.regions:
            return None
            
        # Return the region's coordinates
        return self.regions[region_id].coordinates
    
    def get_backends_for_region(self, region_id: str) -> List[str]:
        """
        Get backends available in a region.
        
        Args:
            region_id: Region identifier
            
        Returns:
            List of backend identifiers
        """
        return self.backends_by_region.get(region_id, [])
    
    def get_closest_region(self, coordinates: GeoCoordinates) -> Optional[str]:
        """
        Find the closest region to given coordinates.
        
        Args:
            coordinates: Geographic coordinates
            
        Returns:
            Region ID of closest region or None if no regions defined
        """
        if not self.regions:
            return None
        
        closest_region = None
        closest_distance = float('inf')
        
        for region_id, region in self.regions.items():
            distance = coordinates.distance_to(region.coordinates)
            
            if distance < closest_distance:
                closest_distance = distance
                closest_region = region_id
        
        return closest_region
    
    def get_regions_by_distance(self, 
                              from_region: str) -> List[Tuple[str, float]]:
        """
        Get regions sorted by distance from a source region.
        
        Args:
            from_region: Source region ID
            
        Returns:
            List of (region_id, distance) tuples sorted by distance
        """
        if from_region not in self.regions:
            return []
        
        source_coords = self.regions[from_region].coordinates
        
        # Calculate distances to all other regions
        distances = []
        for region_id, region in self.regions.items():
            if region_id == from_region:
                continue
                
            distance = source_coords.distance_to(region.coordinates)
            distances.append((region_id, distance))
        
        # Sort by distance
        return sorted(distances, key=lambda x: x[1])
    
    def get_region_latency(self, from_region: str, to_region: str) -> Optional[float]:
        """
        Get the latency between two regions.
        
        Args:
            from_region: Source region ID
            to_region: Destination region ID
            
        Returns:
            Latency in milliseconds or None if unknown
        """
        if from_region not in self.region_latency:
            return None
            
        return self.region_latency.get(from_region, {}).get(to_region)
    
    def get_distance(self, location1: GeoCoordinates, location2: GeoCoordinates) -> float:
        """
        Calculate distance between two geographic locations.
        
        Args:
            location1: First location
            location2: Second location
            
        Returns:
            Distance in kilometers
        """
        return location1.distance_to(location2)
    
    def select_backend_by_region(self, 
                               client_region: str,
                               available_backends: List[str],
                               fallback_strategy: str = "closest") -> Optional[str]:
        """
        Select a backend based on client region.
        
        Args:
            client_region: Client region ID
            available_backends: List of available backends
            fallback_strategy: Strategy to use if no backends in client region
                               ("closest", "random", or "first")
            
        Returns:
            Selected backend ID or None if no suitable backend found
        """
        if not available_backends:
            return None
        
        # Filter to backends that have specified regions
        region_backends = {
            backend: self.get_region_for_backend(backend)
            for backend in available_backends
            if backend in self.backend_regions
        }
        
        # Find backends in the client's region
        local_backends = [
            backend for backend, regions in region_backends.items()
            if client_region in regions
        ]
        
        if local_backends:
            # Return a random backend from the client's region
            return random.choice(local_backends)
        
        # No backends in the client's region, use fallback strategy
        if fallback_strategy == "random":
            return random.choice(available_backends)
            
        elif fallback_strategy == "first":
            return available_backends[0]
            
        elif fallback_strategy == "closest":
            # Find the closest region that has available backends
            if client_region in self.regions:
                # Get regions sorted by distance
                regions_by_distance = self.get_regions_by_distance(client_region)
                
                for region_id, _ in regions_by_distance:
                    # Find backends in this region
                    regional_backends = [
                        backend for backend, regions in region_backends.items()
                        if region_id in regions
                    ]
                    
                    if regional_backends:
                        return random.choice(regional_backends)
            
            # If no closest region found, return a random backend
            return random.choice(available_backends)
        
        # Unknown fallback strategy
        return available_backends[0]
    
    def get_multi_region_backends(self, 
                                min_regions: int = 2,
                                available_backends: Optional[List[str]] = None) -> List[str]:
        """
        Find backends available in multiple regions.
        
        Args:
            min_regions: Minimum number of regions required
            available_backends: Optional list of available backends to filter from
            
        Returns:
            List of backend IDs available in at least min_regions
        """
        multi_region_backends = []
        
        backends_to_check = available_backends or list(self.backend_regions.keys())
        
        for backend in backends_to_check:
            regions = self.get_region_for_backend(backend)
            if len(regions) >= min_regions:
                multi_region_backends.append(backend)
        
        return multi_region_backends
    
    def register_backend_region(self, backend_id: str, region_id: str) -> bool:
        """
        Register a backend as available in a region.
        
        Args:
            backend_id: Backend identifier
            region_id: Region identifier
            
        Returns:
            True if registration was successful
        """
        # Check if region exists
        if region_id not in self.regions:
            logger.warning(f"Region {region_id} not found")
            return False
        
        # Add to backend_regions
        if backend_id not in self.backend_regions:
            self.backend_regions[backend_id] = []
        
        if region_id not in self.backend_regions[backend_id]:
            self.backend_regions[backend_id].append(region_id)
        
        # Add to backends_by_region
        if region_id not in self.backends_by_region:
            self.backends_by_region[region_id] = []
        
        if backend_id not in self.backends_by_region[region_id]:
            self.backends_by_region[region_id].append(backend_id)
        
        logger.info(f"Registered backend {backend_id} in region {region_id}")
        return True
    
    def set_backend_region(self, backend_id: str, region_id: str) -> bool:
        """
        Set a backend's region (alias for register_backend_region for API compatibility).
        
        Args:
            backend_id: Backend identifier
            region_id: Region identifier
            
        Returns:
            True if registration was successful
        """
        return self.register_backend_region(backend_id, region_id)
    
    def set_client_location(self, coordinates: GeoCoordinates) -> None:
        """
        Set the client's geographic location.
        
        Args:
            coordinates: Geographic coordinates
        """
        self.client_location = coordinates
        
        # Determine closest region based on coordinates
        if coordinates:
            self.current_region = self.get_closest_region(coordinates)
    
    def update_region_latency(self, 
                            from_region: str, 
                            to_region: str, 
                            latency_ms: float) -> bool:
        """
        Update the latency between two regions.
        
        Args:
            from_region: Source region ID
            to_region: Destination region ID
            latency_ms: Latency in milliseconds
            
        Returns:
            True if update was successful
        """
        # Check if regions exist
        if from_region not in self.regions or to_region not in self.regions:
            logger.warning(f"Region {from_region} or {to_region} not found")
            return False
        
        # Update latency
        if from_region not in self.region_latency:
            self.region_latency[from_region] = {}
        
        self.region_latency[from_region][to_region] = latency_ms
        
        logger.debug(f"Updated latency from {from_region} to {to_region}: {latency_ms}ms")
        return True
    
    def get_regional_distribution_recommendation(self, 
                                              content_size_bytes: int,
                                              redundancy_factor: int = 2,
                                              available_backends: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get a recommendation for regional distribution of content.
        
        Args:
            content_size_bytes: Size of content in bytes
            redundancy_factor: Number of copies to maintain
            available_backends: Optional list of available backends
            
        Returns:
            Dictionary with distribution recommendation
        """
        backends_to_use = available_backends or list(self.backend_regions.keys())
        
        # Get multi-region backends
        multi_region_backends = self.get_multi_region_backends(
            min_regions=redundancy_factor,
            available_backends=backends_to_use
        )
        
        # If we have multi-region backends, prioritize those
        if multi_region_backends:
            result = {
                "recommended_backends": multi_region_backends[:redundancy_factor],
                "recommendation_type": "multi_region_backends",
                "redundancy_factor": redundancy_factor,
                "content_size_bytes": content_size_bytes
            }
        else:
            # Otherwise, select backends from different regions
            
            # Get all regions with available backends
            regions_with_backends = set()
            for backend in backends_to_use:
                regions = self.get_region_for_backend(backend)
                regions_with_backends.update(regions)
            
            # Sort regions by number of backends (more options is better)
            region_backend_counts = []
            for region in regions_with_backends:
                backends = self.get_backends_for_region(region)
                backends = [b for b in backends if b in backends_to_use]
                region_backend_counts.append((region, len(backends)))
            
            region_backend_counts.sort(key=lambda x: x[1], reverse=True)
            
            # Select top regions
            selected_regions = [r for r, _ in region_backend_counts[:redundancy_factor]]
            
            # Select a backend from each region
            selected_backends = []
            for region in selected_regions:
                backends = self.get_backends_for_region(region)
                backends = [b for b in backends if b in backends_to_use]
                if backends:
                    selected_backends.append(random.choice(backends))
            
            result = {
                "recommended_backends": selected_backends,
                "recommendation_type": "region_distribution",
                "selected_regions": selected_regions,
                "redundancy_factor": redundancy_factor,
                "content_size_bytes": content_size_bytes
            }
        
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the geographic router state to a dictionary."""
        return {
            "regions": {
                region_id: region.to_dict()
                for region_id, region in self.regions.items()
            },
            "backends_by_region": self.backends_by_region,
            "backend_regions": self.backend_regions,
            "region_latency": self.region_latency,
            "current_region": self.current_region
        }


# Default geographic router
_geographic_router = None

def get_geographic_router() -> GeographicRouter:
    """Get or create the default geographic router instance."""
    global _geographic_router
    if _geographic_router is None:
        _geographic_router = GeographicRouter()
    return _geographic_router
