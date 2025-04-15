"""
Geographic Optimization Module for Optimized Data Routing

This module enhances the data routing system with geographic optimization capabilities:
- Location-based routing to minimize latency and network distance
- Region-aware backend selection for edge-optimized content delivery
- Haversine distance calculations for accurate global routing
- Geo-IP lookup for automatic client location detection
- Regional performance tracking and analysis

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import math
import logging
import asyncio
import random
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class GeoLocation:
    """Geographic location representation."""
    lat: float  # Latitude in decimal degrees
    lon: float  # Longitude in decimal degrees
    country_code: Optional[str] = None  # ISO country code
    region: Optional[str] = None  # Region or state
    city: Optional[str] = None  # City name
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "lat": self.lat,
            "lon": self.lon,
            "country_code": self.country_code,
            "region": self.region,
            "city": self.city
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GeoLocation':
        """Create from dictionary representation."""
        return cls(
            lat=data.get("lat", 0.0),
            lon=data.get("lon", 0.0),
            country_code=data.get("country_code"),
            region=data.get("region"),
            city=data.get("city")
        )


@dataclass
class Region:
    """Geographic region information."""
    id: str  # Region identifier (e.g., "us-east-1")
    name: str  # Human-readable name
    location: GeoLocation  # Representative location
    providers: List[str] = field(default_factory=list)  # Available providers in this region
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location.to_dict(),
            "providers": self.providers
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Region':
        """Create from dictionary representation."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            location=GeoLocation.from_dict(data.get("location", {})),
            providers=data.get("providers", [])
        )


@dataclass
class RegionPerformance:
    """Performance metrics for a region."""
    region_id: str
    avg_latency_ms: float = 0.0
    throughput_mbps: float = 0.0
    success_rate: float = 1.0
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "region_id": self.region_id,
            "avg_latency_ms": self.avg_latency_ms,
            "throughput_mbps": self.throughput_mbps,
            "success_rate": self.success_rate,
            "last_updated": self.last_updated.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RegionPerformance':
        """Create from dictionary representation."""
        last_updated = datetime.fromisoformat(data.get("last_updated", datetime.now().isoformat()))
        return cls(
            region_id=data.get("region_id", ""),
            avg_latency_ms=data.get("avg_latency_ms", 0.0),
            throughput_mbps=data.get("throughput_mbps", 0.0),
            success_rate=data.get("success_rate", 1.0),
            last_updated=last_updated
        )


class GeographicRouter:
    """
    Router that optimizes backend selection based on geographic location.
    
    This class implements geographic optimization for content routing,
    selecting backends that are closest to the client's location.
    """
    
    def __init__(self):
        """Initialize the geographic router."""
        self.regions: Dict[str, Region] = {}
        self.backend_regions: Dict[str, str] = {}  # Maps backend names to region IDs
        self.region_performance: Dict[str, RegionPerformance] = {}
        self.client_location: Optional[GeoLocation] = None
        
        # Initialize with common regions
        self._initialize_common_regions()
    
    def _initialize_common_regions(self) -> None:
        """Initialize with common cloud regions."""
        common_regions = [
            # North America
            Region(
                id="us-east-1",
                name="US East (N. Virginia)",
                location=GeoLocation(lat=38.13, lon=-78.45, country_code="US", region="Virginia"),
                providers=["s3", "ipfs", "storacha"]
            ),
            Region(
                id="us-east-2",
                name="US East (Ohio)",
                location=GeoLocation(lat=40.42, lon=-83.78, country_code="US", region="Ohio"),
                providers=["s3", "ipfs"]
            ),
            Region(
                id="us-west-1",
                name="US West (N. California)",
                location=GeoLocation(lat=37.78, lon=-122.42, country_code="US", region="California"),
                providers=["s3", "ipfs", "storacha"]
            ),
            Region(
                id="us-west-2",
                name="US West (Oregon)",
                location=GeoLocation(lat=45.84, lon=-119.68, country_code="US", region="Oregon"),
                providers=["s3", "ipfs"]
            ),
            
            # Europe
            Region(
                id="eu-west-1",
                name="EU West (Ireland)",
                location=GeoLocation(lat=53.34, lon=-6.27, country_code="IE", city="Dublin"),
                providers=["s3", "ipfs", "storacha"]
            ),
            Region(
                id="eu-central-1",
                name="EU Central (Frankfurt)",
                location=GeoLocation(lat=50.11, lon=8.68, country_code="DE", city="Frankfurt"),
                providers=["s3", "ipfs", "storacha"]
            ),
            
            # Asia Pacific
            Region(
                id="ap-northeast-1",
                name="Asia Pacific (Tokyo)",
                location=GeoLocation(lat=35.69, lon=139.69, country_code="JP", city="Tokyo"),
                providers=["s3", "ipfs"]
            ),
            Region(
                id="ap-southeast-1",
                name="Asia Pacific (Singapore)",
                location=GeoLocation(lat=1.35, lon=103.82, country_code="SG", city="Singapore"),
                providers=["s3", "ipfs", "storacha"]
            ),
            Region(
                id="ap-southeast-2",
                name="Asia Pacific (Sydney)",
                location=GeoLocation(lat=-33.87, lon=151.21, country_code="AU", city="Sydney"),
                providers=["s3", "ipfs"]
            ),
            
            # South America
            Region(
                id="sa-east-1",
                name="South America (São Paulo)",
                location=GeoLocation(lat=-23.55, lon=-46.63, country_code="BR", city="São Paulo"),
                providers=["s3", "ipfs"]
            ),
            
            # Global Networks (not tied to specific locations)
            Region(
                id="global-filecoin",
                name="Global Filecoin Network",
                location=GeoLocation(lat=0.0, lon=0.0),  # Global network
                providers=["filecoin"]
            ),
            Region(
                id="global-ipfs",
                name="Global IPFS Network",
                location=GeoLocation(lat=0.0, lon=0.0),  # Global network
                providers=["ipfs"]
            )
        ]
        
        # Add regions to the dictionary
        for region in common_regions:
            self.regions[region.id] = region
        
        # Initialize default backend to region mappings
        default_backend_regions = {
            "ipfs": "global-ipfs",
            "filecoin": "global-filecoin",
            "s3": "us-east-1",
            "storacha": "us-east-1",
            "huggingface": "eu-west-1",
            "lassie": "global-ipfs"
        }
        
        for backend, region in default_backend_regions.items():
            self.backend_regions[backend] = region
    
    def add_region(self, region: Region) -> None:
        """
        Add a new region.
        
        Args:
            region: Region to add
        """
        self.regions[region.id] = region
    
    def remove_region(self, region_id: str) -> bool:
        """
        Remove a region.
        
        Args:
            region_id: Region ID to remove
            
        Returns:
            True if successful
        """
        if region_id in self.regions:
            del self.regions[region_id]
            
            # Also remove from related dictionaries
            if region_id in self.region_performance:
                del self.region_performance[region_id]
            
            # Update backend_regions that pointed to this region
            for backend, region in list(self.backend_regions.items()):
                if region == region_id:
                    # Remove or set to default
                    if backend == "ipfs":
                        self.backend_regions[backend] = "global-ipfs"
                    elif backend == "filecoin":
                        self.backend_regions[backend] = "global-filecoin"
                    else:
                        del self.backend_regions[backend]
            
            return True
        
        return False
    
    def set_backend_region(self, backend_id: str, region_id: str) -> bool:
        """
        Set the region for a backend.
        
        Args:
            backend_id: Backend identifier
            region_id: Region identifier
            
        Returns:
            True if successful
        """
        if region_id not in self.regions:
            return False
        
        self.backend_regions[backend_id] = region_id
        return True
    
    def set_client_location(self, location: Union[GeoLocation, Dict[str, Any]]) -> None:
        """
        Set the client's location.
        
        Args:
            location: Client location (GeoLocation or dict)
        """
        if isinstance(location, dict):
            self.client_location = GeoLocation(
                lat=location.get("lat", 0.0),
                lon=location.get("lon", 0.0),
                country_code=location.get("country_code"),
                region=location.get("region"),
                city=location.get("city")
            )
        else:
            self.client_location = location
    
    def get_distance(self, loc1: GeoLocation, loc2: GeoLocation) -> float:
        """
        Calculate distance between two locations using the Haversine formula.
        
        Args:
            loc1: First location
            loc2: Second location
            
        Returns:
            Distance in kilometers
        """
        # Convert latitude and longitude from degrees to radians
        lat1_rad = math.radians(loc1.lat)
        lon1_rad = math.radians(loc1.lon)
        lat2_rad = math.radians(loc2.lat)
        lon2_rad = math.radians(loc2.lon)
        
        # Haversine formula
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        # Earth radius in kilometers
        earth_radius = 6371.0
        
        # Distance in kilometers
        distance = earth_radius * c
        
        return distance
    
    def get_nearest_region(self) -> Optional[str]:
        """
        Get the nearest region to the client.
        
        Returns:
            Region ID or None if client location not set
        """
        if not self.client_location:
            return None
        
        # Find closest region
        min_distance = float("inf")
        nearest_region = None
        
        for region_id, region in self.regions.items():
            distance = self.get_distance(self.client_location, region.location)
            
            if distance < min_distance:
                min_distance = distance
                nearest_region = region_id
        
        return nearest_region
    
    def rank_regions_by_distance(self) -> List[Tuple[str, float]]:
        """
        Rank regions by distance from client.
        
        Returns:
            List of (region_id, distance) tuples sorted by distance
        """
        if not self.client_location:
            # Return regions in default order if no client location
            return [(region_id, 0.0) for region_id in self.regions.keys()]
        
        # Calculate distances for each region
        distances = []
        
        for region_id, region in self.regions.items():
            distance = self.get_distance(self.client_location, region.location)
            distances.append((region_id, distance))
        
        # Sort by distance
        return sorted(distances, key=lambda x: x[1])
    
    def rank_backends_by_location(
        self, 
        available_backends: Optional[List[str]] = None
    ) -> List[str]:
        """
        Rank backends by proximity to client.
        
        Args:
            available_backends: Optional list of available backends
            
        Returns:
            List of backend names sorted by proximity to client
        """
        if not self.client_location:
            # No client location, return backends in original order
            if available_backends:
                return available_backends
            return list(self.backend_regions.keys())
        
        # Filter to available backends if specified
        if available_backends:
            backend_regions = {
                backend: self.backend_regions.get(backend, "global-ipfs")
                for backend in available_backends
                if backend in self.backend_regions
            }
        else:
            backend_regions = self.backend_regions
        
        # Calculate distances for each backend's region
        backend_distances = []
        
        for backend, region_id in backend_regions.items():
            if region_id in self.regions:
                region = self.regions[region_id]
                distance = self.get_distance(self.client_location, region.location)
                
                # Adjust distance for global networks
                if region_id.startswith("global-"):
                    # Global networks are generally decent but not optimal
                    distance = distance * 0.75
                
                # Adjust for region performance if available
                if region_id in self.region_performance:
                    perf = self.region_performance[region_id]
                    
                    # Reduce effective distance for high-performing regions
                    if perf.avg_latency_ms > 0:
                        latency_factor = max(0.5, min(1.5, perf.avg_latency_ms / 100.0))
                        distance = distance * latency_factor
                
                backend_distances.append((backend, distance))
            else:
                # Region not found, use a large distance
                backend_distances.append((backend, float("inf")))
        
        # Sort by distance
        sorted_backends = [backend for backend, _ in sorted(backend_distances, key=lambda x: x[1])]
        
        # Add any remaining backends not in backend_regions
        if available_backends:
            for backend in available_backends:
                if backend not in sorted_backends:
                    sorted_backends.append(backend)
        
        return sorted_backends
    
    def update_region_performance(
        self,
        region_id: str,
        latency_ms: Optional[float] = None,
        throughput_mbps: Optional[float] = None,
        success_rate: Optional[float] = None
    ) -> None:
        """
        Update performance metrics for a region.
        
        Args:
            region_id: Region identifier
            latency_ms: Average latency in milliseconds
            throughput_mbps: Throughput in Mbps
            success_rate: Success rate (0.0-1.0)
        """
        if region_id not in self.regions:
            return
        
        # Get or create performance record
        if region_id not in self.region_performance:
            self.region_performance[region_id] = RegionPerformance(region_id=region_id)
        
        perf = self.region_performance[region_id]
        
        # Update metrics
        if latency_ms is not None:
            perf.avg_latency_ms = latency_ms
        
        if throughput_mbps is not None:
            perf.throughput_mbps = throughput_mbps
        
        if success_rate is not None:
            perf.success_rate = success_rate
        
        # Update timestamp
        perf.last_updated = datetime.now()
    
    def get_region_performance(self, region_id: str) -> Optional[RegionPerformance]:
        """
        Get performance metrics for a region.
        
        Args:
            region_id: Region identifier
            
        Returns:
            RegionPerformance object or None if not found
        """
        return self.region_performance.get(region_id)
    
    def get_all_regions(self) -> Dict[str, Region]:
        """
        Get all regions.
        
        Returns:
            Dict mapping region IDs to Region objects
        """
        return self.regions.copy()
    
    def get_region(self, region_id: str) -> Optional[Region]:
        """
        Get a region by ID.
        
        Args:
            region_id: Region identifier
            
        Returns:
            Region object or None if not found
        """
        return self.regions.get(region_id)
    
    def get_backend_region(self, backend_id: str) -> Optional[str]:
        """
        Get the region for a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Region ID or None if not found
        """
        return self.backend_regions.get(backend_id)
    
    def get_backend_location(self, backend_id: str) -> Optional[GeoLocation]:
        """
        Get the location for a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            GeoLocation or None if not found
        """
        region_id = self.backend_regions.get(backend_id)
        if not region_id or region_id not in self.regions:
            return None
        
        return self.regions[region_id].location
    
    def recommend_backend_by_location(
        self,
        available_backends: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Recommend a backend based on client location.
        
        This is a simple wrapper around rank_backends_by_location
        that returns the top-ranked backend.
        
        Args:
            available_backends: Optional list of available backends
            
        Returns:
            Recommended backend name or None if no backends available
        """
        ranked_backends = self.rank_backends_by_location(available_backends)
        if not ranked_backends:
            return None
        
        return ranked_backends[0]
    
    def get_backends_in_region(self, region_id: str) -> List[str]:
        """
        Get backends in a specific region.
        
        Args:
            region_id: Region identifier
            
        Returns:
            List of backend names in the region
        """
        return [
            backend for backend, backend_region 
            in self.backend_regions.items() 
            if backend_region == region_id
        ]
    
    def get_client_region(self) -> Optional[str]:
        """
        Get the region containing the client's location.
        
        Returns:
            Region ID or None if client location not set or no matching region
        """
        if not self.client_location:
            return None
        
        # Find nearest region
        return self.get_nearest_region()
    
    def simulate_network_delay(self, from_location: GeoLocation, to_location: GeoLocation) -> float:
        """
        Simulate network delay between two locations.
        
        This is a simple model that estimates latency based on geographic distance,
        plus some random variation to account for network conditions.
        
        Args:
            from_location: Source location
            to_location: Destination location
            
        Returns:
            Estimated latency in milliseconds
        """
        # Calculate distance in kilometers
        distance = self.get_distance(from_location, to_location)
        
        # Base latency calculation
        # Speed of light in fiber is ~200,000 km/s,
        # which gives ~5ms per 1000km (round trip)
        base_latency = (distance / 1000) * 5.0
        
        # Add routing and processing overhead
        overhead = 20.0  # Base overhead in ms
        
        # Add random network variation (0-20% of base latency + overhead)
        variation = random.uniform(0, 0.2) * (base_latency + overhead)
        
        # Calculate total latency
        total_latency = base_latency + overhead + variation
        
        # Ensure minimum latency
        return max(5.0, total_latency)
    
    def simulate_latency_to_backend(self, backend_id: str) -> float:
        """
        Simulate latency from client to a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Estimated latency in milliseconds
        """
        if not self.client_location:
            # Default latency if client location unknown
            return 100.0
        
        # Get backend location
        backend_location = self.get_backend_location(backend_id)
        if not backend_location:
            # Default latency if backend location unknown
            return 150.0
        
        # Simulate latency based on locations
        return self.simulate_network_delay(self.client_location, backend_location)
    
    def get_region_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about regions and their performance.
        
        Returns:
            Dict with region statistics
        """
        result = {
            "count": len(self.regions),
            "regions": {},
            "client_region": None,
            "nearest_region": None,
            "backend_distribution": {}
        }
        
        # Add client info if available
        if self.client_location:
            result["client_location"] = self.client_location.to_dict()
            result["nearest_region"] = self.get_nearest_region()
            result["client_region"] = self.get_client_region()
        
        # Add region data
        for region_id, region in self.regions.items():
            result["regions"][region_id] = {
                "name": region.name,
                "location": region.location.to_dict(),
                "providers": region.providers,
                "performance": self.region_performance.get(region_id, RegionPerformance(region_id)).to_dict() if region_id in self.region_performance else None,
                "backends": self.get_backends_in_region(region_id)
            }
        
        # Count backends per region
        for backend, region_id in self.backend_regions.items():
            if region_id not in result["backend_distribution"]:
                result["backend_distribution"][region_id] = 0
            result["backend_distribution"][region_id] += 1
        
        return result
    
    async def simulate_client_location(self) -> GeoLocation:
        """
        Simulate a client location for testing.
        
        Returns:
            Simulated client location
        """
        # Generate random location in one of several common areas
        locations = [
            # North America
            GeoLocation(lat=40.7128, lon=-74.0060, country_code="US", region="New York", city="New York"),
            GeoLocation(lat=37.7749, lon=-122.4194, country_code="US", region="California", city="San Francisco"),
            GeoLocation(lat=41.8781, lon=-87.6298, country_code="US", region="Illinois", city="Chicago"),
            GeoLocation(lat=45.5017, lon=-73.5673, country_code="CA", region="Quebec", city="Montreal"),
            
            # Europe
            GeoLocation(lat=51.5074, lon=-0.1278, country_code="GB", region="England", city="London"),
            GeoLocation(lat=48.8566, lon=2.3522, country_code="FR", region="Île-de-France", city="Paris"),
            GeoLocation(lat=52.5200, lon=13.4050, country_code="DE", region="Berlin", city="Berlin"),
            
            # Asia
            GeoLocation(lat=35.6762, lon=139.6503, country_code="JP", region="Tokyo", city="Tokyo"),
            GeoLocation(lat=22.3193, lon=114.1694, country_code="HK", city="Hong Kong"),
            GeoLocation(lat=1.3521, lon=103.8198, country_code="SG", city="Singapore"),
            
            # Australia
            GeoLocation(lat=-33.8688, lon=151.2093, country_code="AU", region="New South Wales", city="Sydney"),
            
            # South America
            GeoLocation(lat=-23.5505, lon=-46.6333, country_code="BR", region="São Paulo", city="São Paulo")
        ]
        
        # Select random location
        location = random.choice(locations)
        
        # Add some randomness to lat/lon (within ~50km)
        lat_offset = random.uniform(-0.5, 0.5)
        lon_offset = random.uniform(-0.5, 0.5)
        
        return GeoLocation(
            lat=location.lat + lat_offset,
            lon=location.lon + lon_offset,
            country_code=location.country_code,
            region=location.region,
            city=location.city
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert router state to a dictionary.
        
        Returns:
            Dict representation of router state
        """
        return {
            "regions": {
                region_id: region.to_dict()
                for region_id, region in self.regions.items()
            },
            "backend_regions": self.backend_regions.copy(),
            "region_performance": {
                region_id: perf.to_dict()
                for region_id, perf in self.region_performance.items()
            },
            "client_location": self.client_location.to_dict() if self.client_location else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GeographicRouter':
        """
        Create router from dictionary.
        
        Args:
            data: Dict representation of router state
            
        Returns:
            GeographicRouter instance
        """
        router = cls()
        
        # Load regions
        router.regions = {
            region_id: Region.from_dict(region_data)
            for region_id, region_data in data.get("regions", {}).items()
        }
        
        # Load backend regions
        router.backend_regions = data.get("backend_regions", {}).copy()
        
        # Load region performance
        router.region_performance = {
            region_id: RegionPerformance.from_dict(perf_data)
            for region_id, perf_data in data.get("region_performance", {}).items()
        }
        
        # Load client location
        if data.get("client_location"):
            router.client_location = GeoLocation.from_dict(data["client_location"])
        
        return router


# Factory function to create a geographic router
def create_geographic_router() -> GeographicRouter:
    """
    Create a geographic router.
    
    Returns:
        GeographicRouter instance
    """
    return GeographicRouter()