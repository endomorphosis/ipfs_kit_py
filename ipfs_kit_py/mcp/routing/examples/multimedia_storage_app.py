#!/usr/bin/env python3
# ipfs_kit_py/mcp/routing/examples/multimedia_storage_app.py

"""
Advanced Example: Multimedia Storage Application

This example demonstrates how to use the Optimized Data Routing system in a
real-world multimedia storage application that handles various types of media
files with different storage requirements.

The application simulates:
1. User uploads of different media types
2. Intelligent backend selection based on content
3. Performance monitoring and adaptation
4. Cost optimization for different user tiers
5. Geographic routing for global users
"""

import os
import time
import random
import logging
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime

from ipfs_kit_py.mcp.routing.integration import (
    initialize_mcp_routing, select_backend
)
from ipfs_kit_py.mcp.routing.router import OperationType, ContentType

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Application Models
# -------------------------------------------------------------------------

@dataclass
class User:
    """User model for the multimedia application."""
    user_id: str
    username: str
    tier: str  # 'free', 'premium', 'enterprise'
    region: str
    storage_used: int = 0  # bytes
    storage_limit: int = 5 * 1024 * 1024 * 1024  # 5 GB default


@dataclass
class MediaFile:
    """Media file model."""
    file_id: str
    filename: str
    content_type: str
    size: int  # bytes
    user_id: str
    backend: str
    created_at: float
    metadata: Dict[str, Any] = None
    

class MediaStorage:
    """
    Multimedia storage application that uses intelligent routing
    to optimize storage operations across different backends.
    """
    
    def __init__(self):
        """Initialize the multimedia storage application."""
        # Initialize routing with custom configuration
        config = self._create_routing_config()
        self.routing = initialize_mcp_routing(config)
        
        # Register backends
        self._register_backends()
        
        # Application state
        self.users: Dict[str, User] = {}
        self.media_files: Dict[str, MediaFile] = {}
        
        # Performance tracking
        self.performance_history: List[Dict[str, Any]] = []
        
        # Backend allocation tracking
        self.backend_usage: Dict[str, int] = {backend: 0 for backend in self.routing.router.available_backends}
        
        logger.info("Multimedia storage application initialized")
    
    def _create_routing_config(self) -> Dict[str, Any]:
        """Create the routing configuration."""
        return {
            'default_backend': 'IPFS',
            'strategy_weights': {
                'content': 0.35,
                'cost': 0.25,
                'geo': 0.15,
                'performance': 0.25
            },
            'backend_costs': {
                'IPFS': {
                    'storage_cost': 0.02,    # $ per GB per month
                    'retrieval_cost': 0.01,  # $ per GB
                    'operation_cost': 0.0001  # $ per operation
                },
                'S3': {
                    'storage_cost': 0.023,   # $ per GB per month
                    'retrieval_cost': 0.09,  # $ per GB
                    'operation_cost': 0.0005  # $ per operation
                },
                'FILECOIN': {
                    'storage_cost': 0.005,   # $ per GB per month (long-term storage)
                    'retrieval_cost': 0.02,  # $ per GB
                    'operation_cost': 0.001  # $ per operation
                },
                'STORACHA': {
                    'storage_cost': 0.015,   # $ per GB per month
                    'retrieval_cost': 0.015,  # $ per GB
                    'operation_cost': 0.0002  # $ per operation
                },
                'LOCAL': {
                    'storage_cost': 0.001,   # $ per GB per month (minimal)
                    'retrieval_cost': 0.0,   # $ per GB (free)
                    'operation_cost': 0.0    # $ per operation (free)
                }
            },
            'geographic_regions': {
                'us-east': {'name': 'US East', 'location': 'Virginia', 'coordinates': (37.7749, -122.4194)},
                'us-west': {'name': 'US West', 'location': 'Oregon', 'coordinates': (45.5051, -122.6750)},
                'eu-west': {'name': 'EU West', 'location': 'Ireland', 'coordinates': (53.3498, -6.2603)},
                'eu-central': {'name': 'EU Central', 'location': 'Frankfurt', 'coordinates': (50.1109, 8.6821)},
                'ap-northeast': {'name': 'Asia Pacific Northeast', 'location': 'Tokyo', 'coordinates': (35.6762, 139.6503)},
                'ap-southeast': {'name': 'Asia Pacific Southeast', 'location': 'Singapore', 'coordinates': (1.3521, 103.8198)},
                'sa-east': {'name': 'South America East', 'location': 'São Paulo', 'coordinates': (-23.5505, -46.6333)}
            }
        }
    
    def _register_backends(self):
        """Register available storage backends."""
        # Register standard backends
        self.routing.register_backend('IPFS', {
            'type': 'ipfs',
            'version': '0.14.0',
            'regions': ['us-east', 'eu-west', 'ap-northeast'],
            'features': ['content-addressing', 'deduplication', 'peer-to-peer']
        })
        
        self.routing.register_backend('S3', {
            'type': 's3',
            'bucket': 'multimedia-storage',
            'regions': ['us-east', 'us-west', 'eu-west', 'eu-central', 'ap-northeast', 'ap-southeast'],
            'features': ['high-availability', 'versioning', 'lifecycle-policies']
        })
        
        self.routing.register_backend('FILECOIN', {
            'type': 'filecoin',
            'network': 'mainnet',
            'regions': ['us-east', 'eu-central', 'ap-southeast'],
            'features': ['long-term-storage', 'content-addressing', 'verifiable-storage']
        })
        
        self.routing.register_backend('STORACHA', {
            'type': 'storacha',
            'regions': ['us-east', 'eu-west'],
            'features': ['web3-storage', 'content-addressing', 'redundancy']
        })
        
        self.routing.register_backend('LOCAL', {
            'type': 'local',
            'path': '/data/local-storage',
            'regions': ['us-east'],  # Only available in one region
            'features': ['fast-access', 'low-cost', 'no-redundancy']
        })
    
    def create_user(self, username: str, tier: str = 'free', region: str = 'us-east') -> User:
        """
        Create a new user.
        
        Args:
            username: Username
            tier: User tier ('free', 'premium', 'enterprise')
            region: User's geographic region
            
        Returns:
            User: Created user
        """
        user_id = f"user_{int(time.time())}_{random.randint(1000, 9999)}"
        
        # Set storage limit based on tier
        storage_limit = {
            'free': 5 * 1024 * 1024 * 1024,      # 5 GB
            'premium': 50 * 1024 * 1024 * 1024,  # 50 GB
            'enterprise': 500 * 1024 * 1024 * 1024  # 500 GB
        }.get(tier, 5 * 1024 * 1024 * 1024)
        
        user = User(
            user_id=user_id,
            username=username,
            tier=tier,
            region=region,
            storage_used=0,
            storage_limit=storage_limit
        )
        
        self.users[user_id] = user
        logger.info(f"Created user {username} (ID: {user_id}, Tier: {tier}, Region: {region})")
        
        return user
    
    def upload_file(self, user_id: str, filename: str, content_type: str, 
                   size: int, content: Optional[bytes] = None) -> MediaFile:
        """
        Upload a media file with intelligent backend selection.
        
        Args:
            user_id: User ID
            filename: Filename
            content_type: Content type (mime type or general category)
            size: File size in bytes
            content: Optional file content (simulated)
            
        Returns:
            MediaFile: Uploaded file information
            
        Raises:
            ValueError: If user doesn't exist or storage limit is exceeded
        """
        # Check if user exists
        if user_id not in self.users:
            raise ValueError(f"User {user_id} does not exist")
        
        user = self.users[user_id]
        
        # Check storage limit
        if user.storage_used + size > user.storage_limit:
            raise ValueError(f"Storage limit exceeded for user {user_id}")
        
        # Prepare routing context metadata
        metadata = {
            'user_tier': user.tier,
            'file_extension': os.path.splitext(filename)[1],
            'priority': 5 if user.tier == 'enterprise' else 3 if user.tier == 'premium' else 1
        }
        
        # Measure upload start time
        start_time = time.time()
        
        # Select backend based on file characteristics and user properties
        result = self.routing.select_backend(
            operation_type='write',
            content_type=self._map_content_type(content_type),
            content_size=size,
            user_id=user_id,
            region=user.region,
            metadata=metadata
        )
        
        selected_backend = result['backend']
        
        # Create file record
        file_id = f"file_{int(time.time())}_{random.randint(1000, 9999)}"
        media_file = MediaFile(
            file_id=file_id,
            filename=filename,
            content_type=content_type,
            size=size,
            user_id=user_id,
            backend=selected_backend,
            created_at=time.time(),
            metadata={
                'routing_score': result['score'],
                'routing_reason': result['reason'],
                'content_category': self._map_content_type(content_type),
                **metadata
            }
        )
        
        self.media_files[file_id] = media_file
        
        # Update user storage usage
        user.storage_used += size
        
        # Update backend usage stats
        self.backend_usage[selected_backend] += size
        
        # Simulate actual upload by pausing briefly
        time.sleep(0.05)
        
        # Record performance metrics
        duration = time.time() - start_time
        self.routing.record_operation_performance(
            backend=selected_backend,
            operation_type='write',
            start_time=start_time,
            bytes_sent=size,
            bytes_received=0,
            success=True
        )
        
        # Add to performance history
        self.performance_history.append({
            'operation': 'upload',
            'file_id': file_id,
            'backend': selected_backend,
            'size': size,
            'duration': duration,
            'timestamp': time.time()
        })
        
        logger.info(
            f"Uploaded file {filename} (ID: {file_id}, Size: {size/1024/1024:.2f} MB) "
            f"to backend {selected_backend} for user {user_id}"
        )
        
        return media_file
    
    def download_file(self, file_id: str, user_id: Optional[str] = None) -> Tuple[MediaFile, float]:
        """
        Download a media file.
        
        Args:
            file_id: File ID
            user_id: Optional user ID for authorization
            
        Returns:
            Tuple[MediaFile, float]: File information and download time
            
        Raises:
            ValueError: If file doesn't exist or user is not authorized
        """
        # Check if file exists
        if file_id not in self.media_files:
            raise ValueError(f"File {file_id} does not exist")
        
        media_file = self.media_files[file_id]
        
        # Check authorization if user_id is provided
        if user_id and media_file.user_id != user_id:
            raise ValueError(f"User {user_id} is not authorized to download file {file_id}")
        
        # Get user's region (for metrics)
        region = None
        if user_id and user_id in self.users:
            region = self.users[user_id].region
        
        # Measure download start time
        start_time = time.time()
        
        # Simulate actual download by pausing based on file size
        # Larger files take longer to download
        simulated_download_time = min(0.5, media_file.size / (50 * 1024 * 1024))
        time.sleep(simulated_download_time)
        
        # Record performance metrics
        duration = time.time() - start_time
        self.routing.record_operation_performance(
            backend=media_file.backend,
            operation_type='read',
            start_time=start_time,
            bytes_sent=0,
            bytes_received=media_file.size,
            success=True
        )
        
        # Add to performance history
        self.performance_history.append({
            'operation': 'download',
            'file_id': file_id,
            'backend': media_file.backend,
            'size': media_file.size,
            'duration': duration,
            'region': region,
            'timestamp': time.time()
        })
        
        logger.info(
            f"Downloaded file {media_file.filename} (ID: {file_id}, "
            f"Size: {media_file.size/1024/1024:.2f} MB) from backend {media_file.backend}"
        )
        
        return media_file, duration
    
    def get_storage_report(self) -> Dict[str, Any]:
        """
        Get a report of storage usage across backends.
        
        Returns:
            Dict[str, Any]: Storage report
        """
        total_files = len(self.media_files)
        total_size = sum(file.size for file in self.media_files.values())
        
        # Group files by backend
        backend_files = {}
        backend_size = {}
        content_type_distribution = {}
        
        for file in self.media_files.values():
            # Count files by backend
            if file.backend not in backend_files:
                backend_files[file.backend] = 0
                backend_size[file.backend] = 0
            
            backend_files[file.backend] += 1
            backend_size[file.backend] += file.size
            
            # Count files by content type
            content_type = file.content_type
            if content_type not in content_type_distribution:
                content_type_distribution[content_type] = 0
            
            content_type_distribution[content_type] += 1
        
        # Calculate percentages
        backend_percentage = {
            backend: (count / total_files * 100 if total_files > 0 else 0)
            for backend, count in backend_files.items()
        }
        
        size_percentage = {
            backend: (size / total_size * 100 if total_size > 0 else 0)
            for backend, size in backend_size.items()
        }
        
        # Calculate backend performance metrics
        performance_metrics = {}
        for backend in self.routing.router.available_backends:
            metrics = self.routing.get_backend_metrics(backend)
            if 'performance' in metrics:
                performance_metrics[backend] = {
                    'throughput_mbps': metrics['performance'].get('throughput_mbps', 'N/A'),
                    'latency_ms': metrics['performance'].get('latency_ms', 'N/A'),
                    'success_rate': metrics['performance'].get('success_rate', 'N/A')
                }
        
        # Generate the report
        report = {
            'timestamp': time.time(),
            'total_files': total_files,
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'backend_distribution': {
                'files': backend_files,
                'size_bytes': backend_size,
                'file_percentage': backend_percentage,
                'size_percentage': size_percentage
            },
            'content_type_distribution': content_type_distribution,
            'performance_metrics': performance_metrics,
            'user_count': len(self.users),
            'active_backends': list(self.routing.router.available_backends)
        }
        
        return report
    
    def optimize_storage(self) -> List[Dict[str, Any]]:
        """
        Optimize storage by potentially migrating files between backends.
        
        This simulates a background process that might run periodically
        to optimize storage cost and performance.
        
        Returns:
            List[Dict[str, Any]]: Migration operations performed
        """
        logger.info("Running storage optimization")
        migrations = []
        
        # Get current cost metrics
        cost_calculator = self.routing.router.metrics_collectors.get('cost')
        if not cost_calculator:
            logger.warning("Cost calculator not available, skipping optimization")
            return migrations
        
        # Identify files that might benefit from migration
        for file_id, media_file in self.media_files.items():
            # Skip recently created files
            if time.time() - media_file.created_at < 86400:  # 1 day
                continue
            
            # For files older than 30 days, consider cost-optimized storage
            if time.time() - media_file.created_at > 30 * 86400:
                # Select backend with cost optimization
                result = self.routing.select_backend(
                    operation_type='archive',
                    content_type=self._map_content_type(media_file.content_type),
                    content_size=media_file.size,
                    strategy='cost_based'
                )
                
                target_backend = result['backend']
                
                # If the selected backend is different and has lower cost, migrate
                if target_backend != media_file.backend:
                    # Check if migration would save money
                    current_cost = cost_calculator.estimate_storage_cost(
                        backend=media_file.backend,
                        size_bytes=media_file.size,
                        months=6  # Estimate for next 6 months
                    )
                    
                    new_cost = cost_calculator.estimate_storage_cost(
                        backend=target_backend,
                        size_bytes=media_file.size,
                        months=6  # Estimate for next 6 months
                    )
                    
                    # Only migrate if it would save at least 10%
                    if new_cost < current_cost * 0.9:
                        # Simulate migration
                        logger.info(
                            f"Migrating file {file_id} from {media_file.backend} to {target_backend} "
                            f"for cost optimization. Estimated savings: ${current_cost - new_cost:.2f}"
                        )
                        
                        # Update backend statistics
                        self.backend_usage[media_file.backend] -= media_file.size
                        self.backend_usage[target_backend] += media_file.size
                        
                        # Record the migration
                        migrations.append({
                            'file_id': file_id,
                            'source_backend': media_file.backend,
                            'target_backend': target_backend,
                            'size_bytes': media_file.size,
                            'reason': 'cost_optimization',
                            'estimated_savings': current_cost - new_cost
                        })
                        
                        # Update the file record
                        old_backend = media_file.backend
                        media_file.backend = target_backend
                        media_file.metadata['migration_history'] = media_file.metadata.get('migration_history', [])
                        media_file.metadata['migration_history'].append({
                            'timestamp': time.time(),
                            'source': old_backend,
                            'target': target_backend,
                            'reason': 'cost_optimization'
                        })
        
        return migrations
    
    def _map_content_type(self, content_type: str) -> str:
        """
        Map a content type (MIME type or general category) to standard categories.
        
        Args:
            content_type: Content type string
            
        Returns:
            str: Mapped content type category
        """
        # Handle general categories
        if content_type in ['image', 'video', 'audio', 'document', 'model', 'dataset']:
            return content_type
        
        # Map MIME types
        if content_type.startswith('image/'):
            return 'image'
        elif content_type.startswith('video/'):
            return 'video'
        elif content_type.startswith('audio/'):
            return 'audio'
        elif content_type.startswith('text/') or content_type in ['application/pdf', 'application/msword']:
            return 'document'
        elif content_type in ['application/x-hdf5', 'application/x-parquet', 'text/csv']:
            return 'dataset'
        elif content_type in ['application/x-pytorch', 'application/x-tensorflow']:
            return 'model'
        else:
            return 'binary'  # Default category


def run_simulation():
    """Run a simulation of the multimedia storage application."""
    print("Multimedia Storage Application Demo")
    print("===================================")
    
    # Initialize the application
    app = MediaStorage()
    print(f"Initialized with backends: {', '.join(app.routing.router.available_backends)}")
    
    # Create users in different regions with different tiers
    users = [
        app.create_user("alice", "free", "us-east"),
        app.create_user("bob", "premium", "eu-west"),
        app.create_user("charlie", "enterprise", "ap-northeast"),
        app.create_user("diana", "premium", "us-west"),
        app.create_user("eduardo", "free", "sa-east")
    ]
    
    print(f"\nCreated {len(users)} users in different regions")
    
    # Sample media files to upload
    sample_files = [
        # Small images
        {"name": "vacation_photo1.jpg", "type": "image/jpeg", "size": 2 * 1024 * 1024},  # 2 MB
        {"name": "profile_picture.png", "type": "image/png", "size": 500 * 1024},  # 500 KB
        {"name": "screenshot.png", "type": "image/png", "size": 1 * 1024 * 1024},  # 1 MB
        
        # Videos
        {"name": "birthday_video.mp4", "type": "video/mp4", "size": 150 * 1024 * 1024},  # 150 MB
        {"name": "product_demo.mp4", "type": "video/mp4", "size": 80 * 1024 * 1024},  # 80 MB
        {"name": "conference_talk.mp4", "type": "video/mp4", "size": 500 * 1024 * 1024},  # 500 MB
        
        # Documents
        {"name": "research_paper.pdf", "type": "application/pdf", "size": 5 * 1024 * 1024},  # 5 MB
        {"name": "presentation.pptx", "type": "application/vnd.openxmlformats-officedocument.presentationml.presentation", "size": 15 * 1024 * 1024},  # 15 MB
        {"name": "contract.docx", "type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "size": 2 * 1024 * 1024},  # 2 MB
        
        # Datasets and models
        {"name": "training_data.csv", "type": "text/csv", "size": 50 * 1024 * 1024},  # 50 MB
        {"name": "image_classification.pt", "type": "application/x-pytorch", "size": 200 * 1024 * 1024},  # 200 MB
        {"name": "language_model.h5", "type": "application/x-hdf5", "size": 700 * 1024 * 1024},  # 700 MB
        
        # Audio
        {"name": "podcast_episode.mp3", "type": "audio/mpeg", "size": 45 * 1024 * 1024},  # 45 MB
        {"name": "music_track.flac", "type": "audio/flac", "size": 30 * 1024 * 1024},  # 30 MB
        
        # Archives
        {"name": "project_archive.zip", "type": "application/zip", "size": 120 * 1024 * 1024}  # 120 MB
    ]
    
    # Upload files for each user
    uploaded_files = []
    
    for user in users:
        # Select a subset of files for this user
        num_files = random.randint(3, 6)
        user_files = random.sample(sample_files, num_files)
        
        print(f"\nUploading {num_files} files for user {user.username} ({user.tier}, {user.region}):")
        
        for file in user_files:
            try:
                media_file = app.upload_file(
                    user_id=user.user_id,
                    filename=file["name"],
                    content_type=file["type"],
                    size=file["size"]
                )
                
                print(f"  - {file['name']} ({file['size']/1024/1024:.1f} MB) → {media_file.backend}")
                uploaded_files.append(media_file)
                
            except ValueError as e:
                print(f"  - Error uploading {file['name']}: {e}")
    
    print(f"\nUploaded {len(uploaded_files)} files in total")
    
    # Simulate downloads
    print("\nSimulating file downloads:")
    
    for _ in range(10):
        # Randomly select a file and user
        media_file = random.choice(uploaded_files)
        user_id = random.choice(users).user_id
        
        try:
            file, duration = app.download_file(media_file.file_id, user_id)
            print(f"  - {file.filename} from {file.backend} in {duration*1000:.0f}ms")
        except ValueError as e:
            print(f"  - Download error: {e}")
    
    # Run storage optimization
    print("\nRunning storage optimization:")
    migrations = app.optimize_storage()
    
    if migrations:
        print(f"Performed {len(migrations)} migrations:")
        for migration in migrations:
            print(f"  - File {migration['file_id']} moved from {migration['source_backend']} to {migration['target_backend']}")
            print(f"    Reason: {migration['reason']}, Savings: ${migration['estimated_savings']:.2f}")
    else:
        print("No migrations were necessary")
    
    # Generate and display storage report
    report = app.get_storage_report()
    
    print("\nStorage Report:")
    print(f"Total files: {report['total_files']}")
    print(f"Total size: {report['total_size_mb']:.2f} MB")
    
    print("\nBackend distribution (by file count):")
    for backend, percentage in sorted(report['backend_distribution']['file_percentage'].items(), key=lambda x: x[1], reverse=True):
        file_count = report['backend_distribution']['files'][backend]
        size_mb = report['backend_distribution']['size_bytes'][backend] / (1024 * 1024)
        print(f"  - {backend}: {file_count} files ({percentage:.1f}%), {size_mb:.2f} MB")
    
    print("\nContent type distribution:")
    for content_type, count in sorted(report['content_type_distribution'].items(), key=lambda x: x[1], reverse=True):
        percentage = count / report['total_files'] * 100
        print(f"  - {content_type}: {count} files ({percentage:.1f}%)")
    
    print("\nPerformance metrics:")
    for backend, metrics in report['performance_metrics'].items():
        print(f"  - {backend}:")
        for metric, value in metrics.items():
            if metric == 'throughput_mbps' and value != 'N/A':
                print(f"    • {metric}: {value:.2f} Mbps")
            elif metric == 'latency_ms' and value != 'N/A':
                print(f"    • {metric}: {value:.2f} ms")
            elif metric == 'success_rate' and value != 'N/A':
                print(f"    • {metric}: {value*100:.2f}%")
            else:
                print(f"    • {metric}: {value}")
    
    # Show routing decisions analysis
    routing_history = app.routing.get_routing_history(limit=50)
    
    print("\nRouting Decision Analysis:")
    backend_counts = {}
    for decision in routing_history:
        backend = decision['backend']
        if backend not in backend_counts:
            backend_counts[backend] = 0
        backend_counts[backend] += 1
    
    total_decisions = sum(backend_counts.values())
    for backend, count in sorted(backend_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = count / total_decisions * 100 if total_decisions > 0 else 0
        print(f"  - {backend}: {count} decisions ({percentage:.1f}%)")


if __name__ == "__main__":
    run_simulation()