

#!/usr/bin/env python3
"""
IPFS-Kit CLI - Optimized for instant help

A command-line interface that loads heavy dependencies only when needed.
Designed to show help instantly without any heavy imports.
"""

import asyncio
import argparse
import json
import sys
import time
import os
import signal
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

# Rich imports for CLI display
try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress
except ImportError:
    # Fallback for when rich is not available
    Console = None
    Table = None
    Progress = None

# IPFS Kit imports (with fallbacks)
try:
    from .cluster.role_manager import RoleManager, NodeRole
except ImportError:
    RoleManager = None
    NodeRole = None

try:
    from .enhanced_daemon_manager import EnhancedDaemonManager
except ImportError:
    EnhancedDaemonManager = None

try:
    from .pin_metadata_index import get_global_pin_metadata_index
except ImportError:
    get_global_pin_metadata_index = None

try:
    from .vfs_manager import get_global_vfs_manager
except ImportError:
    get_global_vfs_manager = None

try:
    from .huggingface_kit import huggingface_kit
except ImportError:
    huggingface_kit = None

try:
    from .mcp.storage_manager.backends.s3_backend import S3Backend
except ImportError as e:
    # Handle multicodec compatibility issues
    if "multicodec status" in str(e) or "deprecated" in str(e):
        print(f"⚠️  S3Backend not available due to multicodec compatibility issue: {e}")
    S3Backend = None

try:
    from .mcp.storage_manager.backends.storacha_backend import StorachaBackend
except ImportError as e:
    # Handle multicodec compatibility issues  
    if "multicodec status" in str(e) or "deprecated" in str(e):
        print(f"⚠️  StorachaBackend not available due to multicodec compatibility issue: {e}")
    StorachaBackend = None

try:
    from .core import jit_manager
except ImportError as e:
    # Handle multicodec compatibility issues
    if "multicodec status" in str(e) or "deprecated" in str(e):
        print(f"⚠️  Core components not available due to multicodec compatibility issue: {e}")
    jit_manager = None

try:
    from .high_level_api import IPFSSimpleAPI
except ImportError as e:
    # Handle multicodec compatibility issues
    if "multicodec status" in str(e) or "deprecated" in str(e):
        print(f"⚠️  IPFSSimpleAPI not available due to multicodec compatibility issue: {e}")
    IPFSSimpleAPI = None

try:
    from .config_manager import ConfigManager
except ImportError:
    ConfigManager = None

try:
    from .backend_schemas import SCHEMAS as BACKEND_SCHEMAS
except ImportError:
    BACKEND_SCHEMAS = {} 

from typing import Dict, Any, List, Optional
import subprocess
import signal
import requests
import hashlib
import sqlite3
import pandas as pd

# Global flag to check if we've initialized heavy imports
_heavy_imports_initialized = False
_jit_manager = None

def initialize_heavy_imports():
    """Initialize heavy imports only when needed."""
    global _heavy_imports_initialized, _jit_manager
    
    if _heavy_imports_initialized:
        return _jit_manager
    
    try:
        from .core import jit_manager
        _jit_manager = jit_manager
        _heavy_imports_initialized = True
        print("✅ Core JIT system: Available")
        return _jit_manager
    except ImportError as e:
        print(f"❌ Core JIT system: Not available ({e})")
        _heavy_imports_initialized = True
        return None

def create_parser():
    """Create argument parser with minimal overhead."""
    parser = argparse.ArgumentParser(description="IPFS-Kit Enhanced CLI Tool")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Daemon management
    daemon_parser = subparsers.add_parser('daemon', help='Daemon management')
    daemon_subparsers = daemon_parser.add_subparsers(dest='daemon_action', help='Daemon actions')
    
    start_parser = daemon_subparsers.add_parser('start', help='Start the daemon')
    start_parser.add_argument('--detach', action='store_true', help='Run in background')
    start_parser.add_argument('--config', help='Config file path')
    start_parser.add_argument('--daemon-port', type=int, default=9999, help='Port for daemon API (default: 9999)')
    start_parser.add_argument('--role', choices=['master', 'worker', 'leecher', 'modular', 'local'], 
                             help='Daemon role: master (cluster coordinator), worker (content processing), leecher (minimal resources), modular (full features for testing), local (no networking)')
    start_parser.add_argument('--master-address', help='Master node address (required for worker role, ignored for leecher)')
    start_parser.add_argument('--cluster-secret', help='Cluster authentication secret')
    
    daemon_subparsers.add_parser('stop', help='Stop the daemon')
    daemon_subparsers.add_parser('status', help='Check daemon status')
    daemon_subparsers.add_parser('restart', help='Restart the daemon')
    
    # Individual service management (requires running daemon)
    ipfs_parser = daemon_subparsers.add_parser('ipfs', help='Manage IPFS service')
    ipfs_subparsers = ipfs_parser.add_subparsers(dest='ipfs_action', help='IPFS service actions')
    ipfs_subparsers.add_parser('start', help='Start IPFS service')
    ipfs_subparsers.add_parser('stop', help='Stop IPFS service')
    ipfs_subparsers.add_parser('status', help='Check IPFS service status')
    ipfs_subparsers.add_parser('restart', help='Restart IPFS service')
    
    lotus_parser = daemon_subparsers.add_parser('lotus', help='Manage Lotus service')
    lotus_subparsers = lotus_parser.add_subparsers(dest='lotus_action', help='Lotus service actions')
    lotus_subparsers.add_parser('start', help='Start Lotus service')
    lotus_subparsers.add_parser('stop', help='Stop Lotus service')
    lotus_subparsers.add_parser('status', help='Check Lotus service status')
    lotus_subparsers.add_parser('restart', help='Restart Lotus service')
    
    cluster_parser = daemon_subparsers.add_parser('cluster', help='Manage IPFS Cluster service')
    cluster_subparsers = cluster_parser.add_subparsers(dest='cluster_action', help='IPFS Cluster service actions')
    cluster_subparsers.add_parser('start', help='Start IPFS Cluster service')
    cluster_subparsers.add_parser('stop', help='Stop IPFS Cluster service')
    cluster_subparsers.add_parser('status', help='Check IPFS Cluster service status')
    cluster_subparsers.add_parser('restart', help='Restart IPFS Cluster service')
    
    lassie_parser = daemon_subparsers.add_parser('lassie', help='Manage Lassie service')
    lassie_subparsers = lassie_parser.add_subparsers(dest='lassie_action', help='Lassie service actions')
    lassie_subparsers.add_parser('start', help='Start Lassie service')
    lassie_subparsers.add_parser('stop', help='Stop Lassie service')
    lassie_subparsers.add_parser('status', help='Check Lassie service status')
    lassie_subparsers.add_parser('restart', help='Restart Lassie service')
    
    # Enhanced intelligent daemon commands
    intelligent_parser = daemon_subparsers.add_parser('intelligent', help='Enhanced intelligent daemon with metadata-driven operations')
    intelligent_subparsers = intelligent_parser.add_subparsers(dest='intelligent_action', help='Intelligent daemon actions')
    
    # Intelligent daemon start
    intelligent_start_parser = intelligent_subparsers.add_parser('start', help='Start enhanced intelligent daemon')
    intelligent_start_parser.add_argument('--detach', '-d', action='store_true', help='Run daemon in background')
    intelligent_start_parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    # Intelligent daemon control
    intelligent_subparsers.add_parser('stop', help='Stop intelligent daemon')
    
    # Status and insights
    status_parser = intelligent_subparsers.add_parser('status', help='Show daemon status and metadata insights')
    status_parser.add_argument('--json-output', '-j', action='store_true', help='Output as JSON')
    status_parser.add_argument('--detailed', '-d', action='store_true', help='Show detailed status')
    
    insights_parser = intelligent_subparsers.add_parser('insights', help='Show metadata insights and operational intelligence')
    insights_parser.add_argument('--json-output', '-j', action='store_true', help='Output as JSON')
    
    intelligent_subparsers.add_parser('health', help='Check overall system health based on metadata')
    
    # Sync control
    sync_parser = intelligent_subparsers.add_parser('sync', help='Force synchronization of dirty backends')
    sync_parser.add_argument('--backend', help='Force sync for specific backend')
    
    # Role management commands
    role_parser = daemon_subparsers.add_parser('set-role', help='Set daemon role')
    role_parser.add_argument('role', choices=['master', 'worker', 'leecher', 'modular', 'local'],
                           help='New daemon role')
    role_parser.add_argument('--force', action='store_true', help='Force role change without resource validation')
    role_parser.add_argument('--master-address', help='Master node address (required for worker role, ignored for leecher)')
    role_parser.add_argument('--cluster-secret', help='Cluster authentication secret')
    
    daemon_subparsers.add_parser('get-role', help='Get current daemon role')
    daemon_subparsers.add_parser('auto-role', help='Auto-detect optimal role based on resources')
    
    # Pin management
    pin_parser = subparsers.add_parser('pin', help='Pin management')
    pin_subparsers = pin_parser.add_subparsers(dest='pin_action', help='Pin actions')
    
    add_pin_parser = pin_subparsers.add_parser('add', help='Add a pin')
    add_pin_parser.add_argument('cid_or_file', help='CID to pin or file path to calculate CID and pin')
    add_pin_parser.add_argument('--name', help='Name for the pin')
    add_pin_parser.add_argument('--recursive', action='store_true', help='Recursive pin')
    add_pin_parser.add_argument('--file', action='store_true', help='Treat input as file path (auto-detected if file exists)')
    
    remove_pin_parser = pin_subparsers.add_parser('remove', help='Remove a pin')
    remove_pin_parser.add_argument('cid', help='CID to unpin')
    
    list_pin_parser = pin_subparsers.add_parser('list', help='List pins')
    list_pin_parser.add_argument('--limit', type=int, help='Limit results')
    list_pin_parser.add_argument('--metadata', action='store_true', help='Show metadata')
    
    pending_pin_parser = pin_subparsers.add_parser('pending', help='List pending pin operations in WAL')
    pending_pin_parser.add_argument('--limit', type=int, help='Limit results')
    pending_pin_parser.add_argument('--metadata', action='store_true', help='Show metadata')
    
    status_pin_parser = pin_subparsers.add_parser('status', help='Check pin status')
    status_pin_parser.add_argument('operation_id', help='Operation ID')
    
    get_pin_parser = pin_subparsers.add_parser('get', help='Download pinned content to file')
    get_pin_parser.add_argument('cid', help='CID to download')
    get_pin_parser.add_argument('--output', '-o', help='Output file path (default: uses CID as filename)')
    get_pin_parser.add_argument('--recursive', action='store_true', help='Download recursively for directories')
    
    cat_pin_parser = pin_subparsers.add_parser('cat', help='Stream pinned content to stdout')
    cat_pin_parser.add_argument('cid', help='CID to stream')
    cat_pin_parser.add_argument('--limit', type=int, help='Limit output size in bytes')
    
    init_pin_parser = pin_subparsers.add_parser('init', help='Initialize pin metadata index with sample data')
    
    # Pin metadata export command
    export_pin_metadata_parser = pin_subparsers.add_parser('export-metadata', help='Export pin metadata to sharded parquet and CAR files')
    export_pin_metadata_parser.add_argument('--max-shard-size', type=int, default=100, help='Maximum shard size in MB (default: 100)')
    
    # Backend management - interface to internal kit modules
    backend_parser = subparsers.add_parser('backend', help='Storage backend management (interface to kit modules)')
    backend_subparsers = backend_parser.add_subparsers(dest='backend_action', help='Backend actions')
    
    # Backend configuration commands
    backend_create_parser = backend_subparsers.add_parser('create', help='Create a backend configuration')
    backend_create_parser.add_argument('name', help='Backend name')
    backend_create_parser.add_argument('type', choices=['s3', 'huggingface', 'storacha', 'ipfs', 'filecoin', 'gdrive'], help='Backend type')
    backend_create_parser.add_argument('--endpoint', help='Backend endpoint URL')
    backend_create_parser.add_argument('--access-key', help='Access key for authentication')
    backend_create_parser.add_argument('--secret-key', help='Secret key for authentication')
    backend_create_parser.add_argument('--token', help='Authentication token')
    backend_create_parser.add_argument('--bucket', help='Bucket or container name')
    backend_create_parser.add_argument('--region', help='Region or location')
    
    backend_show_parser = backend_subparsers.add_parser('show', help='Show backend configuration')
    backend_show_parser.add_argument('name', help='Backend name')
    
    backend_update_parser = backend_subparsers.add_parser('update', help='Update backend configuration')
    backend_update_parser.add_argument('name', help='Backend name')
    backend_update_parser.add_argument('--enabled', type=bool, help='Enable/disable backend')
    backend_update_parser.add_argument('--endpoint', help='Backend endpoint URL')
    backend_update_parser.add_argument('--token', help='Authentication token')
    backend_update_parser.add_argument('--bucket', help='Bucket or container name')
    backend_update_parser.add_argument('--region', help='Region or location')
    
    backend_remove_parser = backend_subparsers.add_parser('remove', help='Remove backend configuration')
    backend_remove_parser.add_argument('name', help='Backend name')
    backend_remove_parser.add_argument('--force', action='store_true', help='Force removal without confirmation')
    
    # Backend pin mapping commands
    backend_pin_parser = backend_subparsers.add_parser('pin', help='Backend pin management')
    backend_pin_subparsers = backend_pin_parser.add_subparsers(dest='pin_action', help='Pin actions')
    
    backend_pin_add_parser = backend_pin_subparsers.add_parser('add', help='Add pin mapping to backend')
    backend_pin_add_parser.add_argument('backend', help='Backend name')
    backend_pin_add_parser.add_argument('cid', help='Content identifier')
    backend_pin_add_parser.add_argument('car_path', help='Path to CAR file on remote backend')
    backend_pin_add_parser.add_argument('--name', help='Pin name')
    backend_pin_add_parser.add_argument('--description', help='Pin description')
    
    backend_pin_list_parser = backend_pin_subparsers.add_parser('list', help='List pin mappings for backend')
    backend_pin_list_parser.add_argument('backend', help='Backend name')
    backend_pin_list_parser.add_argument('--limit', type=int, help='Maximum number of pins to show')
    
    backend_pin_find_parser = backend_pin_subparsers.add_parser('find', help='Find pin across all backends')
    backend_pin_find_parser.add_argument('cid', help='Content identifier to find')
    
    # Backend list command
    backend_list_parser = backend_subparsers.add_parser('list', help='List backends')
    backend_list_parser.add_argument('--configured', action='store_true', help='List configured backends instead of available types')
    
    # Backend test command  
    backend_test_parser = backend_subparsers.add_parser('test', help='Test backend connections')
    backend_test_parser.add_argument('--backend', help='Test specific backend')
    
    # Backend migration command
    backend_migrate_parser = backend_subparsers.add_parser('migrate-pin-mappings', help='Migrate backend pin storage to standardized format')
    backend_migrate_parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated without making changes')
    backend_migrate_parser.add_argument('--backend-filter', help='Only migrate backends whose names contain this string')
    backend_migrate_parser.add_argument('--ipfs-kit-path', help='Path to IPFS Kit data directory (default: ~/.ipfs_kit)')
    backend_migrate_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    # HuggingFace backend
    hf_parser = backend_subparsers.add_parser('huggingface', help='HuggingFace Hub operations')
    hf_subparsers = hf_parser.add_subparsers(dest='hf_action', help='HuggingFace actions')
    
    # HuggingFace login
    hf_login_parser = hf_subparsers.add_parser('login', help='Login to HuggingFace Hub')
    hf_login_parser.add_argument('--token', help='HuggingFace authentication token')
    
    # HuggingFace configure
    hf_configure_parser = hf_subparsers.add_parser('configure', help='Configure HuggingFace Hub integration and quotas')
    hf_configure_parser.add_argument('--token', help='HuggingFace authentication token')
    hf_configure_parser.add_argument('--default-org', help='Default organization for uploads')
    hf_configure_parser.add_argument('--cache-dir', help='Local cache directory for downloaded models')
    
    # HuggingFace backend characteristics: AI/ML FOCUSED, VERSION CONTROLLED, COMMUNITY-DRIVEN
    hf_configure_parser.add_argument('--storage-quota', help='Hub storage quota (e.g., 1GB free, unlimited pro)')
    hf_configure_parser.add_argument('--lfs-quota', help='Git LFS quota for large model files (e.g., 10GB, 1TB)')
    hf_configure_parser.add_argument('--quota-action', choices=['warn', 'block', 'upgrade-prompt'], default='warn', help='Action when quota is exceeded')
    hf_configure_parser.add_argument('--model-versioning', choices=['commit-based', 'tag-based', 'branch-based'], default='commit-based', help='Model versioning strategy')
    hf_configure_parser.add_argument('--cache-retention', type=int, default=30, help='Local cache retention days')
    hf_configure_parser.add_argument('--auto-update', action='store_true', help='Automatically update cached models')
    hf_configure_parser.add_argument('--collaboration-level', choices=['private', 'public'], default='private', help='Default repository visibility')
    
    # HuggingFace list repositories  
    hf_list_parser = hf_subparsers.add_parser('list', help='List repositories')
    hf_list_parser.add_argument('--type', choices=['model', 'dataset', 'space'], default='model', help='Repository type')
    hf_list_parser.add_argument('--limit', type=int, default=10, help='Maximum number of repositories to list')
    
    # HuggingFace download
    hf_download_parser = hf_subparsers.add_parser('download', help='Download file from repository')
    hf_download_parser.add_argument('repo_id', help='Repository ID (e.g., microsoft/DialoGPT-medium)')
    hf_download_parser.add_argument('filename', help='File to download')
    hf_download_parser.add_argument('--revision', default='main', help='Git revision (branch, tag, or commit)')
    hf_download_parser.add_argument('--type', choices=['model', 'dataset', 'space'], default='model', help='Repository type')
    
    # HuggingFace upload
    hf_upload_parser = hf_subparsers.add_parser('upload', help='Upload file to repository')
    hf_upload_parser.add_argument('repo_id', help='Repository ID')
    hf_upload_parser.add_argument('local_file', help='Local file to upload')
    hf_upload_parser.add_argument('remote_path', help='Path in repository')
    hf_upload_parser.add_argument('--message', help='Commit message')
    hf_upload_parser.add_argument('--revision', default='main', help='Git revision (branch, tag, or commit)')
    hf_upload_parser.add_argument('--type', choices=['model', 'dataset', 'space'], default='model', help='Repository type')
    
    # HuggingFace list files
    hf_files_parser = hf_subparsers.add_parser('files', help='List files in repository')
    hf_files_parser.add_argument('repo_id', help='Repository ID')
    hf_files_parser.add_argument('--path', default='', help='Path within repository')
    hf_files_parser.add_argument('--revision', default='main', help='Git revision (branch, tag, or commit)')
    hf_files_parser.add_argument('--type', choices=['model', 'dataset', 'space'], default='model', help='Repository type')
    
    # GitHub backend
    gh_parser = backend_subparsers.add_parser('github', help='GitHub repository operations')
    gh_subparsers = gh_parser.add_subparsers(dest='gh_action', help='GitHub actions')
    
    # GitHub login
    gh_login_parser = gh_subparsers.add_parser('login', help='Login to GitHub')
    gh_login_parser.add_argument('--token', help='GitHub personal access token')
    
    # GitHub configure
    gh_configure_parser = gh_subparsers.add_parser('configure', help='Configure GitHub integration and storage policies')
    gh_configure_parser.add_argument('--token', help='GitHub personal access token')
    gh_configure_parser.add_argument('--default-org', help='Default GitHub organization')
    gh_configure_parser.add_argument('--default-repo', help='Default repository for uploads')
    
    # GitHub backend characteristics: HIGH AVAILABILITY, VERSION CONTROL, COLLABORATION-FOCUSED
    gh_configure_parser.add_argument('--storage-quota', help='Repository storage limit (e.g., 1GB, 100GB, enterprise unlimited)')
    gh_configure_parser.add_argument('--lfs-quota', help='Git LFS storage quota (e.g., 1GB, 10GB for large files)')
    gh_configure_parser.add_argument('--quota-action', choices=['warn', 'block', 'lfs-migrate'], default='lfs-migrate', help='Action when quota is exceeded')
    gh_configure_parser.add_argument('--retention-policy', choices=['indefinite', 'branch-based', 'tag-based'], default='indefinite', help='Version retention policy')
    gh_configure_parser.add_argument('--auto-lfs', action='store_true', default=True, help='Automatically use Git LFS for large files')
    gh_configure_parser.add_argument('--collaboration-level', choices=['private', 'internal', 'public'], default='private', help='Default repository visibility')
    gh_configure_parser.add_argument('--branch-protection', action='store_true', help='Enable branch protection rules')
    
    # GitHub list repositories
    gh_list_parser = gh_subparsers.add_parser('list', help='List repositories')
    gh_list_parser.add_argument('--user', help='GitHub username (default: authenticated user)')
    gh_list_parser.add_argument('--type', choices=['all', 'owner', 'member'], default='owner', help='Repository type')
    gh_list_parser.add_argument('--limit', type=int, default=10, help='Maximum number of repositories to list')
    
    # GitHub clone/download
    gh_clone_parser = gh_subparsers.add_parser('clone', help='Clone repository locally')
    gh_clone_parser.add_argument('repo', help='Repository (owner/repo)')
    gh_clone_parser.add_argument('--path', help='Local path to clone to')
    gh_clone_parser.add_argument('--branch', default='main', help='Branch to clone')
    
    # GitHub upload
    gh_upload_parser = gh_subparsers.add_parser('upload', help='Upload file to repository')
    gh_upload_parser.add_argument('repo', help='Repository (owner/repo)')
    gh_upload_parser.add_argument('local_file', help='Local file to upload')
    gh_upload_parser.add_argument('remote_path', help='Path in repository')
    gh_upload_parser.add_argument('--message', help='Commit message')
    gh_upload_parser.add_argument('--branch', default='main', help='Branch to upload to')
    
    # GitHub files
    gh_files_parser = gh_subparsers.add_parser('files', help='List files in repository')
    gh_files_parser.add_argument('repo', help='Repository (owner/repo)')
    gh_files_parser.add_argument('--path', default='', help='Path within repository')
    gh_files_parser.add_argument('--branch', default='main', help='Branch to list')
    
    # S3 backend
    s3_parser = backend_subparsers.add_parser('s3', help='Amazon S3 operations')
    s3_subparsers = s3_parser.add_subparsers(dest='s3_action', help='S3 actions')
    
    # S3 configure
    s3_config_parser = s3_subparsers.add_parser('configure', help='Configure S3 credentials and policies')
    s3_config_parser.add_argument('--access-key', help='AWS access key ID')
    s3_config_parser.add_argument('--secret-key', help='AWS secret access key')
    s3_config_parser.add_argument('--region', default='us-east-1', help='AWS region')
    s3_config_parser.add_argument('--endpoint', help='S3-compatible endpoint URL')
    
    # S3 Replication Policies
    s3_config_parser.add_argument('--cross-region-replication', action='store_true', help='Enable cross-region replication')
    s3_config_parser.add_argument('--replication-regions', help='Comma-separated list of replication regions')
    s3_config_parser.add_argument('--versioning', action='store_true', help='Enable object versioning')
    
    # S3 Cache and Performance Policies
    s3_config_parser.add_argument('--cache-policy', choices=['lru', 'lfu', 'fifo', 'none'], default='lru', help='Local cache policy for S3 objects')
    s3_config_parser.add_argument('--cache-size', type=int, default=1000, help='Maximum cached objects')
    s3_config_parser.add_argument('--multipart-threshold', type=int, default=64, help='Multipart upload threshold in MB')
    s3_config_parser.add_argument('--concurrent-uploads', type=int, default=5, help='Maximum concurrent uploads')
    
    # S3 Storage Classes and Lifecycle
    s3_config_parser.add_argument('--default-storage-class', choices=['STANDARD', 'REDUCED_REDUNDANCY', 'STANDARD_IA', 'ONEZONE_IA', 'INTELLIGENT_TIERING', 'GLACIER', 'DEEP_ARCHIVE'], default='STANDARD', help='Default storage class')
    s3_config_parser.add_argument('--lifecycle-policy', choices=['none', 'auto-tier', 'auto-archive'], default='none', help='Automatic lifecycle management')
    
    # S3 Disaster Recovery
    s3_config_parser.add_argument('--backup-bucket', help='Backup bucket for disaster recovery')
    s3_config_parser.add_argument('--dr-sync-interval', type=int, default=3600, help='Disaster recovery sync interval in seconds')
    
    # S3 backend characteristics: MODERATE SPEED, HIGH PERSISTENCE, SCALABLE
    s3_config_parser.add_argument('--account-quota', help='Account-wide quota for S3 usage (e.g., 10TB, 50TB)')
    s3_config_parser.add_argument('--quota-action', choices=['warn', 'block', 'auto-tier', 'auto-delete'], default='auto-tier', help='Action when quota is exceeded')
    s3_config_parser.add_argument('--cost-optimization', action='store_true', help='Enable automatic cost optimization')
    s3_config_parser.add_argument('--retention-policy', choices=['indefinite', 'compliance', 'lifecycle'], default='lifecycle', help='Data retention policy')
    s3_config_parser.add_argument('--auto-delete-after', type=int, help='Auto-delete objects after N days')
    s3_config_parser.add_argument('--monitoring-enabled', action='store_true', default=True, help='Enable CloudWatch monitoring')
    s3_config_parser.add_argument('--transfer-acceleration', action='store_true', help='Enable transfer acceleration for faster uploads')
    
    # S3 list buckets
    s3_list_parser = s3_subparsers.add_parser('list', help='List S3 buckets')
    s3_list_parser.add_argument('bucket', nargs='?', help='Specific bucket to list objects')
    s3_list_parser.add_argument('--prefix', help='Object prefix filter')
    s3_list_parser.add_argument('--limit', type=int, default=100, help='Maximum number of objects to list')
    
    # S3 upload
    s3_upload_parser = s3_subparsers.add_parser('upload', help='Upload file to S3 with policies')
    s3_upload_parser.add_argument('local_file', help='Local file to upload')
    s3_upload_parser.add_argument('bucket', help='S3 bucket name')
    s3_upload_parser.add_argument('key', help='S3 object key')
    
    # S3 Upload Policies
    s3_upload_parser.add_argument('--storage-class', choices=['STANDARD', 'REDUCED_REDUNDANCY', 'STANDARD_IA', 'ONEZONE_IA', 'INTELLIGENT_TIERING', 'GLACIER', 'DEEP_ARCHIVE'], help='Storage class for this upload')
    s3_upload_parser.add_argument('--cache-control', help='Cache-Control header value')
    s3_upload_parser.add_argument('--expires', type=int, help='Object expiration in days')
    s3_upload_parser.add_argument('--replicate-to', help='Comma-separated list of regions to replicate to')
    s3_upload_parser.add_argument('--encryption', choices=['none', 'aes256', 'kms'], default='none', help='Server-side encryption')
    s3_upload_parser.add_argument('--backup', action='store_true', help='Also upload to backup bucket')
    s3_upload_parser.add_argument('--tags', help='Comma-separated tags (key=value pairs)')
    s3_upload_parser.add_argument('--priority', choices=['low', 'normal', 'high'], default='normal', help='Upload priority')
    
    # S3 download
    s3_download_parser = s3_subparsers.add_parser('download', help='Download file from S3')
    s3_download_parser.add_argument('bucket', help='S3 bucket name')
    s3_download_parser.add_argument('key', help='S3 object key')
    s3_download_parser.add_argument('local_file', help='Local file path')
    
    # Storacha backend
    storacha_parser = backend_subparsers.add_parser('storacha', help='Storacha/Web3.Storage operations')
    storacha_subparsers = storacha_parser.add_subparsers(dest='storacha_action', help='Storacha actions')
    
    # Storacha configure
    storacha_config_parser = storacha_subparsers.add_parser('configure', help='Configure Storacha API')
    storacha_config_parser.add_argument('--api-key', help='Storacha API key')
    storacha_config_parser.add_argument('--endpoint', help='Storacha endpoint URL')
    
    # Storacha backend characteristics: WEB3 STORAGE, DECENTRALIZED, FILECOIN-BACKED
    storacha_config_parser.add_argument('--storage-quota', help='Storacha storage quota (varies by plan)')
    storacha_config_parser.add_argument('--quota-action', choices=['warn', 'block', 'upgrade-prompt'], default='warn', help='Action when quota is exceeded')
    storacha_config_parser.add_argument('--retention-policy', choices=['permanent', 'deal-based', 'renewal'], default='deal-based', help='Data retention policy on Filecoin network')
    storacha_config_parser.add_argument('--deal-duration', type=int, default=180, help='Filecoin deal duration in days')
    storacha_config_parser.add_argument('--auto-renew', action='store_true', default=True, help='Automatically renew expiring deals')
    storacha_config_parser.add_argument('--redundancy-level', type=int, default=3, help='Number of storage providers for redundancy')
    storacha_config_parser.add_argument('--ipfs-gateway', help='Preferred IPFS gateway for retrievals')
    
    # Storacha upload
    storacha_upload_parser = storacha_subparsers.add_parser('upload', help='Upload content to Storacha')
    storacha_upload_parser.add_argument('file_path', help='File or directory to upload')
    storacha_upload_parser.add_argument('--name', help='Content name')
    
    # Storacha list
    storacha_list_parser = storacha_subparsers.add_parser('list', help='List stored content')
    storacha_list_parser.add_argument('--limit', type=int, default=100, help='Maximum number of items to list')
    
    # IPFS backend
    ipfs_parser = backend_subparsers.add_parser('ipfs', help='IPFS operations')
    ipfs_subparsers = ipfs_parser.add_subparsers(dest='ipfs_action', help='IPFS actions')
    
    # IPFS add
    ipfs_add_parser = ipfs_subparsers.add_parser('add', help='Add file to IPFS')
    ipfs_add_parser.add_argument('file_path', help='File or directory to add')
    ipfs_add_parser.add_argument('--recursive', action='store_true', help='Add directory recursively')
    ipfs_add_parser.add_argument('--pin', action='store_true', help='Pin the content after adding')
    
    # IPFS get
    ipfs_get_parser = ipfs_subparsers.add_parser('get', help='Get content from IPFS')
    ipfs_get_parser.add_argument('cid', help='IPFS Content ID')
    ipfs_get_parser.add_argument('--output', help='Output path')
    
    # IPFS pin
    ipfs_pin_parser = ipfs_subparsers.add_parser('pin', help='Pin content on IPFS')
    ipfs_pin_parser.add_argument('cid', help='IPFS Content ID')
    ipfs_pin_parser.add_argument('--name', help='Pin name')
    
    # Single-node replication settings (for local IPFS)
    ipfs_pin_parser.add_argument('--recursive', action='store_true', help='Pin recursively (default for directories)')
    ipfs_pin_parser.add_argument('--cache-policy', choices=['lru', 'lfu', 'fifo', 'mru', 'none'], default='lru', help='Local cache eviction policy')
    ipfs_pin_parser.add_argument('--cache-priority', choices=['low', 'normal', 'high'], default='normal', help='Cache priority level')
    ipfs_pin_parser.add_argument('--bucket', help='Assign pin to a bucket for organization')
    
    # Performance settings
    ipfs_pin_parser.add_argument('--timeout', type=int, default=60, help='Pin operation timeout in seconds')
    ipfs_pin_parser.add_argument('--priority', choices=['low', 'normal', 'high'], default='normal', help='Pin operation priority')
    
    # Metadata and organization
    ipfs_pin_parser.add_argument('--tags', help='Comma-separated tags for pin organization')
    ipfs_pin_parser.add_argument('--description', help='Description for this pin')
    
    # Google Drive backend
    gdrive_parser = backend_subparsers.add_parser('gdrive', help='Google Drive operations')
    gdrive_subparsers = gdrive_parser.add_subparsers(dest='gdrive_action', help='Google Drive actions')
    
    # Google Drive auth
    gdrive_auth_parser = gdrive_subparsers.add_parser('auth', help='Authenticate with Google Drive')
    gdrive_auth_parser.add_argument('--credentials', help='Path to credentials JSON file')
    
    # Google Drive configure
    gdrive_configure_parser = gdrive_subparsers.add_parser('configure', help='Configure Google Drive storage and quotas')
    gdrive_configure_parser.add_argument('--credentials', help='Path to credentials JSON file')
    gdrive_configure_parser.add_argument('--default-folder', help='Default folder ID for uploads')
    gdrive_configure_parser.add_argument('--shared-drive', help='Shared drive ID for team storage')
    
    # Google Drive backend characteristics: CLOUD STORAGE, PERSONAL/BUSINESS, COLLABORATION-FRIENDLY  
    gdrive_configure_parser.add_argument('--storage-quota', help='Google Drive storage quota (15GB free, unlimited business)')
    gdrive_configure_parser.add_argument('--quota-action', choices=['warn', 'block', 'upgrade-prompt'], default='warn', help='Action when quota is exceeded')
    gdrive_configure_parser.add_argument('--retention-policy', choices=['indefinite', 'auto-trash', 'version-limit'], default='indefinite', help='File retention policy')
    gdrive_configure_parser.add_argument('--version-retention', type=int, default=100, help='Number of versions to retain per file')
    gdrive_configure_parser.add_argument('--auto-trash-days', type=int, default=30, help='Days before auto-trashing unused files')
    gdrive_configure_parser.add_argument('--sharing-level', choices=['private', 'link-share', 'organization', 'public'], default='private', help='Default sharing level')
    gdrive_configure_parser.add_argument('--sync-offline', action='store_true', help='Enable offline sync for important files')
    
    # Google Drive list
    gdrive_list_parser = gdrive_subparsers.add_parser('list', help='List Google Drive files')
    gdrive_list_parser.add_argument('--folder', help='Folder ID to list')
    gdrive_list_parser.add_argument('--limit', type=int, default=100, help='Maximum number of files to list')
    
    # Google Drive upload
    gdrive_upload_parser = gdrive_subparsers.add_parser('upload', help='Upload file to Google Drive')
    gdrive_upload_parser.add_argument('local_file', help='Local file to upload')
    gdrive_upload_parser.add_argument('--folder', help='Destination folder ID')
    gdrive_upload_parser.add_argument('--name', help='Name for uploaded file')
    
    # Google Drive download
    gdrive_download_parser = gdrive_subparsers.add_parser('download', help='Download file from Google Drive')
    gdrive_download_parser.add_argument('file_id', help='Google Drive file ID')
    gdrive_download_parser.add_argument('local_path', help='Local path to save file')
    
    # Lotus backend
    lotus_parser = backend_subparsers.add_parser('lotus', help='Lotus/Filecoin operations')
    lotus_subparsers = lotus_parser.add_subparsers(dest='lotus_action', help='Lotus actions')
    
    # Lotus configure
    lotus_configure_parser = lotus_subparsers.add_parser('configure', help='Configure Lotus connection')
    lotus_configure_parser.add_argument('--endpoint', help='Lotus RPC endpoint URL')
    lotus_configure_parser.add_argument('--token', help='Lotus authentication token')
    
    # Filecoin backend characteristics: HIGH PERSISTENCE, LOW SPEED
    lotus_configure_parser.add_argument('--quota-size', help='Storage quota for Filecoin backend (e.g., 1TB, 500GB)')
    lotus_configure_parser.add_argument('--quota-action', choices=['warn', 'block', 'auto-cleanup'], default='warn', help='Action when quota is exceeded')
    lotus_configure_parser.add_argument('--retention-policy', choices=['permanent', 'deal-duration', 'custom'], default='permanent', help='Data retention policy')
    lotus_configure_parser.add_argument('--min-deal-duration', type=int, default=525600, help='Minimum deal duration in epochs (default: 1 year)')
    lotus_configure_parser.add_argument('--auto-renew', action='store_true', help='Automatically renew expiring deals')
    lotus_configure_parser.add_argument('--priority-fee', help='Priority fee for deal operations (FIL)')
    lotus_configure_parser.add_argument('--redundancy-level', type=int, default=1, help='Number of storage providers to use')
    lotus_configure_parser.add_argument('--cleanup-expired', action='store_true', help='Automatically clean up expired deals')
    
    # Lotus status
    lotus_subparsers.add_parser('status', help='Show Lotus node status')
    
    # Lotus store
    lotus_store_parser = lotus_subparsers.add_parser('store', help='Store data on Filecoin')
    lotus_store_parser.add_argument('local_file', help='Local file to store')
    lotus_store_parser.add_argument('--duration', type=int, default=525600, help='Storage duration in epochs')
    
    # Lotus retrieve
    lotus_retrieve_parser = lotus_subparsers.add_parser('retrieve', help='Retrieve data from Filecoin')
    lotus_retrieve_parser.add_argument('cid', help='Content identifier')
    lotus_retrieve_parser.add_argument('local_path', help='Local path to save retrieved data')
    
    # Synapse backend
    synapse_parser = backend_subparsers.add_parser('synapse', help='Synapse operations')
    synapse_subparsers = synapse_parser.add_subparsers(dest='synapse_action', help='Synapse actions')
    
    # Synapse configure
    synapse_configure_parser = synapse_subparsers.add_parser('configure', help='Configure Synapse connection')
    synapse_configure_parser.add_argument('--endpoint', help='Synapse endpoint URL')
    synapse_configure_parser.add_argument('--api-key', help='Synapse API key')
    
    # Synapse backend characteristics: RESEARCH-FOCUSED, BIOMEDICAL DATA, COLLABORATIVE SCIENCE
    synapse_configure_parser.add_argument('--storage-quota', help='Synapse project storage quota (varies by account type)')
    synapse_configure_parser.add_argument('--quota-action', choices=['warn', 'block', 'archive'], default='archive', help='Action when quota is exceeded')
    synapse_configure_parser.add_argument('--retention-policy', choices=['indefinite', 'project-based', 'compliance'], default='project-based', help='Data retention policy')
    synapse_configure_parser.add_argument('--version-limit', type=int, default=10, help='Maximum versions to retain per file')
    synapse_configure_parser.add_argument('--sharing-level', choices=['private', 'team', 'public'], default='team', help='Default sharing level for uploads')
    synapse_configure_parser.add_argument('--provenance-tracking', action='store_true', default=True, help='Enable provenance tracking for reproducibility')
    synapse_configure_parser.add_argument('--doi-minting', action='store_true', help='Enable DOI minting for datasets')
    
    # Synapse status
    synapse_subparsers.add_parser('status', help='Show Synapse status')
    
    # Synapse upload
    synapse_upload_parser = synapse_subparsers.add_parser('upload', help='Upload to Synapse')
    synapse_upload_parser.add_argument('local_file', help='Local file to upload')
    synapse_upload_parser.add_argument('--project', help='Synapse project ID')
    
    # Synapse download
    synapse_download_parser = synapse_subparsers.add_parser('download', help='Download from Synapse')
    synapse_download_parser.add_argument('synapse_id', help='Synapse entity ID')
    synapse_download_parser.add_argument('local_path', help='Local path to save file')
    
    # SSHFS backend
    sshfs_parser = backend_subparsers.add_parser('sshfs', help='SSHFS remote storage operations')
    sshfs_subparsers = sshfs_parser.add_subparsers(dest='sshfs_action', help='SSHFS actions')
    
    # SSHFS configure
    sshfs_configure_parser = sshfs_subparsers.add_parser('configure', help='Configure SSHFS connection')
    sshfs_configure_parser.add_argument('--hostname', required=True, help='SSH hostname or IP address')
    sshfs_configure_parser.add_argument('--username', required=True, help='SSH username')
    sshfs_configure_parser.add_argument('--port', type=int, default=22, help='SSH port (default: 22)')
    sshfs_configure_parser.add_argument('--password', help='SSH password (not recommended, use key auth)')
    sshfs_configure_parser.add_argument('--private-key', help='Path to SSH private key file')
    sshfs_configure_parser.add_argument('--remote-path', default='/tmp/ipfs_kit', help='Remote base path')
    
    # SSHFS backend characteristics: MODERATE SPEED, VARIABLE PERSISTENCE, NETWORK-DEPENDENT
    sshfs_configure_parser.add_argument('--storage-quota', help='Storage quota on remote filesystem (e.g., 100GB, 1TB)')
    sshfs_configure_parser.add_argument('--quota-action', choices=['warn', 'block', 'cleanup'], default='cleanup', help='Action when quota is exceeded')
    sshfs_configure_parser.add_argument('--cleanup-policy', choices=['lru', 'oldest', 'largest'], default='lru', help='Cleanup policy for quota enforcement')
    sshfs_configure_parser.add_argument('--retention-days', type=int, default=90, help='Retain files for N days before cleanup')
    sshfs_configure_parser.add_argument('--network-resilience', action='store_true', default=True, help='Enable network disconnection resilience')
    sshfs_configure_parser.add_argument('--auto-reconnect', action='store_true', default=True, help='Automatically reconnect on connection loss')
    sshfs_configure_parser.add_argument('--connection-timeout', type=int, default=30, help='Connection timeout in seconds')
    
    # SSHFS status
    sshfs_subparsers.add_parser('status', help='Show SSHFS connection status')
    
    # SSHFS test
    sshfs_subparsers.add_parser('test', help='Test SSHFS connection')
    
    # SSHFS upload
    sshfs_upload_parser = sshfs_subparsers.add_parser('upload', help='Upload file via SSHFS')
    sshfs_upload_parser.add_argument('local_file', help='Local file to upload')
    sshfs_upload_parser.add_argument('remote_path', help='Remote path destination')
    
    # SSHFS download
    sshfs_download_parser = sshfs_subparsers.add_parser('download', help='Download file via SSHFS')
    sshfs_download_parser.add_argument('remote_path', help='Remote file path')
    sshfs_download_parser.add_argument('local_path', help='Local path to save file')
    
    # SSHFS list
    sshfs_list_parser = sshfs_subparsers.add_parser('list', help='List remote files via SSHFS')
    sshfs_list_parser.add_argument('remote_path', nargs='?', default='/', help='Remote path to list')
    
    # FTP backend
    ftp_parser = backend_subparsers.add_parser('ftp', help='FTP storage operations')
    ftp_subparsers = ftp_parser.add_subparsers(dest='ftp_action', help='FTP actions')
    
    # FTP configure
    ftp_configure_parser = ftp_subparsers.add_parser('configure', help='Configure FTP connection')
    ftp_configure_parser.add_argument('--host', required=True, help='FTP hostname or IP address')
    ftp_configure_parser.add_argument('--username', required=True, help='FTP username')
    ftp_configure_parser.add_argument('--password', required=True, help='FTP password')
    ftp_configure_parser.add_argument('--port', type=int, default=21, help='FTP port (default: 21)')
    ftp_configure_parser.add_argument('--use-tls', action='store_true', help='Use FTP over TLS (FTPS)')
    ftp_configure_parser.add_argument('--passive', action='store_true', default=True, help='Use passive mode')
    ftp_configure_parser.add_argument('--remote-path', default='/', help='Remote base path')
    
    # FTP backend characteristics: LOW-MODERATE SPEED, VARIABLE PERSISTENCE, LEGACY PROTOCOL
    ftp_configure_parser.add_argument('--storage-quota', help='Storage quota on FTP server (e.g., 50GB, 500GB)')
    ftp_configure_parser.add_argument('--quota-action', choices=['warn', 'block', 'cleanup'], default='block', help='Action when quota is exceeded')
    ftp_configure_parser.add_argument('--retention-policy', choices=['manual', 'time-based', 'space-based'], default='time-based', help='Retention policy for files')
    ftp_configure_parser.add_argument('--retention-days', type=int, default=30, help='Retain files for N days (time-based policy)')
    ftp_configure_parser.add_argument('--max-file-age', type=int, default=180, help='Maximum file age before warning (days)')
    ftp_configure_parser.add_argument('--bandwidth-limit', help='Bandwidth limit for transfers (e.g., 1MB/s, 10MB/s)')
    ftp_configure_parser.add_argument('--legacy-compatibility', action='store_true', default=True, help='Enable legacy FTP compatibility mode')
    
    # FTP status
    ftp_subparsers.add_parser('status', help='Show FTP connection status')
    
    # FTP test
    ftp_subparsers.add_parser('test', help='Test FTP connection')
    
    # FTP upload
    ftp_upload_parser = ftp_subparsers.add_parser('upload', help='Upload file via FTP')
    ftp_upload_parser.add_argument('local_file', help='Local file to upload')
    ftp_upload_parser.add_argument('remote_path', help='Remote path destination')
    
    # FTP download
    ftp_download_parser = ftp_subparsers.add_parser('download', help='Download file via FTP')
    ftp_download_parser.add_argument('remote_path', help='Remote file path')
    ftp_download_parser.add_argument('local_path', help='Local path to save file')
    
    # FTP list
    ftp_list_parser = ftp_subparsers.add_parser('list', help='List remote files via FTP')
    ftp_list_parser.add_argument('remote_path', nargs='?', default='/', help='Remote path to list')
    
    # IPFS Cluster backend
    ipfs_cluster_parser = backend_subparsers.add_parser('ipfs-cluster', help='IPFS Cluster operations')
    ipfs_cluster_subparsers = ipfs_cluster_parser.add_subparsers(dest='ipfs_cluster_action', help='IPFS Cluster actions')
    
    # IPFS Cluster configure
    ipfs_cluster_configure_parser = ipfs_cluster_subparsers.add_parser('configure', help='Configure IPFS Cluster connection')
    ipfs_cluster_configure_parser.add_argument('--endpoint', required=True, help='IPFS Cluster API endpoint')
    ipfs_cluster_configure_parser.add_argument('--username', help='Basic auth username')
    ipfs_cluster_configure_parser.add_argument('--password', help='Basic auth password')
    ipfs_cluster_configure_parser.add_argument('--ssl-cert', help='Path to SSL certificate file')
    
    # Global Pinset Policies
    ipfs_cluster_configure_parser.add_argument('--global-replication-min', type=int, default=2, help='Global minimum replication factor for all pins')
    ipfs_cluster_configure_parser.add_argument('--global-replication-max', type=int, default=-1, help='Global maximum replication factor (-1 = cluster size)')
    ipfs_cluster_configure_parser.add_argument('--global-cache-policy', choices=['lru', 'lfu', 'fifo', 'mru', 'adaptive'], default='adaptive', help='Global cache eviction policy')
    ipfs_cluster_configure_parser.add_argument('--global-cache-size', type=int, default=10000, help='Global maximum cache entries')
    ipfs_cluster_configure_parser.add_argument('--global-pin-timeout', type=int, default=300, help='Global pin operation timeout in seconds')
    
    # Disaster Recovery Settings
    ipfs_cluster_configure_parser.add_argument('--dr-geo-distribution', choices=['none', 'region', 'continent', 'global'], default='region', help='Geographic distribution strategy for disaster recovery')
    ipfs_cluster_configure_parser.add_argument('--dr-backup-interval', type=int, default=3600, help='Disaster recovery backup interval in seconds')
    ipfs_cluster_configure_parser.add_argument('--dr-min-replicas-per-zone', type=int, default=1, help='Minimum replicas per availability zone')
    
    # Throughput Optimization
    ipfs_cluster_configure_parser.add_argument('--throughput-mode', choices=['balanced', 'high-throughput', 'low-latency', 'bandwidth-optimized'], default='balanced', help='Throughput optimization mode')
    ipfs_cluster_configure_parser.add_argument('--concurrent-pins', type=int, default=10, help='Maximum concurrent pin operations')
    ipfs_cluster_configure_parser.add_argument('--batch-size', type=int, default=100, help='Batch size for bulk operations')
    
    # IPFS Cluster status
    ipfs_cluster_subparsers.add_parser('status', help='Show IPFS Cluster status')
    
    # IPFS Cluster pin
    ipfs_cluster_pin_parser = ipfs_cluster_subparsers.add_parser('pin', help='Pin content to IPFS Cluster')
    ipfs_cluster_pin_parser.add_argument('cid', help='Content identifier to pin')
    ipfs_cluster_pin_parser.add_argument('--name', help='Pin name')
    
    # Per-Pin Replication Settings
    ipfs_cluster_pin_parser.add_argument('--replication-min', type=int, help='Minimum replication factor (overrides global)')
    ipfs_cluster_pin_parser.add_argument('--replication-max', type=int, help='Maximum replication factor (overrides global)')
    
    # Per-Pin Cache Settings
    ipfs_cluster_pin_parser.add_argument('--cache-policy', choices=['lru', 'lfu', 'fifo', 'mru', 'adaptive', 'inherit'], default='inherit', help='Cache eviction policy for this pin')
    ipfs_cluster_pin_parser.add_argument('--cache-priority', choices=['low', 'normal', 'high', 'critical'], default='normal', help='Cache priority level')
    ipfs_cluster_pin_parser.add_argument('--cache-ttl', type=int, help='Cache time-to-live in seconds (0 = permanent)')
    
    # Bucket-Level Settings
    ipfs_cluster_pin_parser.add_argument('--bucket', help='Assign pin to a specific bucket for policy inheritance')
    ipfs_cluster_pin_parser.add_argument('--bucket-policy', choices=['high-availability', 'balanced', 'performance', 'cost-optimized'], help='Bucket-level policy preset')
    
    # Disaster Recovery Per-Pin
    ipfs_cluster_pin_parser.add_argument('--dr-tier', choices=['critical', 'important', 'standard', 'archive'], default='standard', help='Disaster recovery tier')
    ipfs_cluster_pin_parser.add_argument('--dr-zones', help='Comma-separated list of required availability zones')
    
    # Performance Settings
    ipfs_cluster_pin_parser.add_argument('--pin-timeout', type=int, help='Pin operation timeout in seconds (overrides global)')
    ipfs_cluster_pin_parser.add_argument('--priority', choices=['low', 'normal', 'high', 'urgent'], default='normal', help='Pin operation priority')
    
    # IPFS Cluster unpin
    ipfs_cluster_unpin_parser = ipfs_cluster_subparsers.add_parser('unpin', help='Unpin content from IPFS Cluster')
    ipfs_cluster_unpin_parser.add_argument('cid', help='Content identifier to unpin')
    
    # IPFS Cluster list
    ipfs_cluster_subparsers.add_parser('list', help='List pinned content in IPFS Cluster')
    
    # IPFS Cluster bucket management
    ipfs_cluster_bucket_parser = ipfs_cluster_subparsers.add_parser('bucket', help='Manage cluster buckets and policies')
    ipfs_cluster_bucket_subparsers = ipfs_cluster_bucket_parser.add_subparsers(dest='bucket_action', help='Bucket actions')
    
    # Create bucket with policies
    ipfs_cluster_bucket_create_parser = ipfs_cluster_bucket_subparsers.add_parser('create', help='Create a new bucket with policies')
    ipfs_cluster_bucket_create_parser.add_argument('bucket_name', help='Name of the bucket to create')
    ipfs_cluster_bucket_create_parser.add_argument('--description', help='Bucket description')
    
    # Bucket Replication Policies
    ipfs_cluster_bucket_create_parser.add_argument('--replication-min', type=int, default=2, help='Minimum replication factor for bucket')
    ipfs_cluster_bucket_create_parser.add_argument('--replication-max', type=int, default=-1, help='Maximum replication factor for bucket')
    
    # Bucket Cache Policies
    ipfs_cluster_bucket_create_parser.add_argument('--cache-policy', choices=['lru', 'lfu', 'fifo', 'mru', 'adaptive'], default='lru', help='Cache eviction policy for bucket')
    ipfs_cluster_bucket_create_parser.add_argument('--cache-size', type=int, default=1000, help='Maximum cache entries for bucket')
    ipfs_cluster_bucket_create_parser.add_argument('--cache-ttl', type=int, default=86400, help='Default cache TTL in seconds')
    
    # Bucket Performance Policies
    ipfs_cluster_bucket_create_parser.add_argument('--throughput-mode', choices=['balanced', 'high-throughput', 'low-latency', 'bandwidth-optimized'], default='balanced', help='Throughput optimization for bucket')
    ipfs_cluster_bucket_create_parser.add_argument('--concurrent-ops', type=int, default=5, help='Maximum concurrent operations for bucket')
    
    # Bucket Disaster Recovery Policies
    ipfs_cluster_bucket_create_parser.add_argument('--dr-tier', choices=['critical', 'important', 'standard', 'archive'], default='standard', help='Disaster recovery tier for bucket')
    ipfs_cluster_bucket_create_parser.add_argument('--dr-zones', help='Required availability zones (comma-separated)')
    ipfs_cluster_bucket_create_parser.add_argument('--dr-backup-frequency', choices=['continuous', 'hourly', 'daily', 'weekly'], default='daily', help='Backup frequency for bucket')
    
    # Bucket Lifecycle Policies
    ipfs_cluster_bucket_create_parser.add_argument('--lifecycle-policy', choices=['none', 'auto-archive', 'auto-delete', 'custom'], default='none', help='Lifecycle management policy')
    ipfs_cluster_bucket_create_parser.add_argument('--archive-after-days', type=int, help='Archive content after N days')
    ipfs_cluster_bucket_create_parser.add_argument('--delete-after-days', type=int, help='Delete content after N days')
    
    # Update bucket policies
    ipfs_cluster_bucket_update_parser = ipfs_cluster_bucket_subparsers.add_parser('update', help='Update bucket policies')
    ipfs_cluster_bucket_update_parser.add_argument('bucket_name', help='Name of the bucket to update')
    ipfs_cluster_bucket_update_parser.add_argument('--replication-min', type=int, help='Update minimum replication factor')
    ipfs_cluster_bucket_update_parser.add_argument('--replication-max', type=int, help='Update maximum replication factor')
    ipfs_cluster_bucket_update_parser.add_argument('--cache-policy', choices=['lru', 'lfu', 'fifo', 'mru', 'adaptive'], help='Update cache policy')
    ipfs_cluster_bucket_update_parser.add_argument('--cache-size', type=int, help='Update cache size')
    ipfs_cluster_bucket_update_parser.add_argument('--throughput-mode', choices=['balanced', 'high-throughput', 'low-latency', 'bandwidth-optimized'], help='Update throughput mode')
    ipfs_cluster_bucket_update_parser.add_argument('--dr-tier', choices=['critical', 'important', 'standard', 'archive'], help='Update disaster recovery tier')
    
    # List buckets
    ipfs_cluster_bucket_list_parser = ipfs_cluster_bucket_subparsers.add_parser('list', help='List all buckets and their policies')
    ipfs_cluster_bucket_list_parser.add_argument('--detailed', action='store_true', help='Show detailed policy information')
    
    # Show bucket details
    ipfs_cluster_bucket_show_parser = ipfs_cluster_bucket_subparsers.add_parser('show', help='Show detailed bucket information')
    ipfs_cluster_bucket_show_parser.add_argument('bucket_name', help='Name of the bucket to show')
    
    # Delete bucket
    ipfs_cluster_bucket_delete_parser = ipfs_cluster_bucket_subparsers.add_parser('delete', help='Delete a bucket')
    ipfs_cluster_bucket_delete_parser.add_argument('bucket_name', help='Name of the bucket to delete')
    ipfs_cluster_bucket_delete_parser.add_argument('--force', action='store_true', help='Force deletion without confirmation')
    
    # Global pinset policy management
    ipfs_cluster_policy_parser = ipfs_cluster_subparsers.add_parser('policy', help='Manage global pinset policies')
    ipfs_cluster_policy_subparsers = ipfs_cluster_policy_parser.add_subparsers(dest='policy_action', help='Policy actions')
    
    # Show global policies
    ipfs_cluster_policy_show_parser = ipfs_cluster_policy_subparsers.add_parser('show', help='Show current global pinset policies')
    
    # Update global policies
    ipfs_cluster_policy_update_parser = ipfs_cluster_policy_subparsers.add_parser('update', help='Update global pinset policies')
    ipfs_cluster_policy_update_parser.add_argument('--global-replication-min', type=int, help='Update global minimum replication')
    ipfs_cluster_policy_update_parser.add_argument('--global-replication-max', type=int, help='Update global maximum replication')
    ipfs_cluster_policy_update_parser.add_argument('--global-cache-policy', choices=['lru', 'lfu', 'fifo', 'mru', 'adaptive'], help='Update global cache policy')
    ipfs_cluster_policy_update_parser.add_argument('--global-cache-size', type=int, help='Update global cache size')
    ipfs_cluster_policy_update_parser.add_argument('--throughput-mode', choices=['balanced', 'high-throughput', 'low-latency', 'bandwidth-optimized'], help='Update global throughput mode')
    ipfs_cluster_policy_update_parser.add_argument('--dr-geo-distribution', choices=['none', 'region', 'continent', 'global'], help='Update geographic distribution strategy')
    
    # Policy templates
    ipfs_cluster_policy_template_parser = ipfs_cluster_policy_subparsers.add_parser('template', help='Apply predefined policy templates')
    ipfs_cluster_policy_template_parser.add_argument('template', choices=['high-availability', 'performance', 'cost-optimized', 'disaster-recovery', 'balanced'], help='Policy template to apply')
    ipfs_cluster_policy_template_parser.add_argument('--scope', choices=['global', 'bucket'], default='global', help='Apply template globally or to bucket')
    ipfs_cluster_policy_template_parser.add_argument('--bucket', help='Bucket name when scope is bucket')
    
    # IPFS Cluster Follow backend
    ipfs_cluster_follow_parser = backend_subparsers.add_parser('ipfs-cluster-follow', help='IPFS Cluster Follow operations')
    ipfs_cluster_follow_subparsers = ipfs_cluster_follow_parser.add_subparsers(dest='ipfs_cluster_follow_action', help='IPFS Cluster Follow actions')
    
    # IPFS Cluster Follow configure
    ipfs_cluster_follow_configure_parser = ipfs_cluster_follow_subparsers.add_parser('configure', help='Configure IPFS Cluster Follow')
    ipfs_cluster_follow_configure_parser.add_argument('--name', required=True, help='Cluster name to follow')
    ipfs_cluster_follow_configure_parser.add_argument('--template', help='Cluster configuration template')
    ipfs_cluster_follow_configure_parser.add_argument('--trusted-peers', help='Trusted peer multiaddresses (comma-separated)')
    
    # IPFS Cluster Follow status
    ipfs_cluster_follow_subparsers.add_parser('status', help='Show IPFS Cluster Follow status')
    
    # IPFS Cluster Follow run
    ipfs_cluster_follow_run_parser = ipfs_cluster_follow_subparsers.add_parser('run', help='Run IPFS Cluster Follow')
    ipfs_cluster_follow_run_parser.add_argument('cluster_name', help='Name of cluster to follow')
    
    # IPFS Cluster Follow stop
    ipfs_cluster_follow_subparsers.add_parser('stop', help='Stop IPFS Cluster Follow')
    
    # IPFS Cluster Follow list
    ipfs_cluster_follow_subparsers.add_parser('list', help='List followed clusters')
    
    # Parquet backend
    parquet_parser = backend_subparsers.add_parser('parquet', help='Parquet data operations')
    parquet_subparsers = parquet_parser.add_subparsers(dest='parquet_action', help='Parquet actions')
    
    # Parquet configure
    parquet_configure_parser = parquet_subparsers.add_parser('configure', help='Configure Parquet storage settings')
    parquet_configure_parser.add_argument('--storage-path', help='Local storage path for parquet files')
    parquet_configure_parser.add_argument('--compression', choices=['snappy', 'gzip', 'brotli', 'lz4'], default='snappy', help='Compression algorithm')
    parquet_configure_parser.add_argument('--batch-size', type=int, default=10000, help='Batch size for writing')
    
    # Parquet backend characteristics: BALANCED SPEED/PERSISTENCE (columnar storage)
    parquet_configure_parser.add_argument('--storage-quota', help='Storage quota for Parquet files (e.g., 500GB, 1TB)')
    parquet_configure_parser.add_argument('--quota-action', choices=['warn', 'block', 'auto-archive', 'auto-compress'], default='auto-compress', help='Action when quota is exceeded')
    parquet_configure_parser.add_argument('--retention-policy', choices=['size-based', 'time-based', 'access-based', 'manual'], default='access-based', help='Data retention policy')
    parquet_configure_parser.add_argument('--max-file-age', type=int, default=2592000, help='Maximum file age in seconds (default: 30 days)')
    parquet_configure_parser.add_argument('--auto-compact', action='store_true', help='Automatically compact small files')
    parquet_configure_parser.add_argument('--compact-threshold', type=int, default=100, help='Number of small files to trigger compaction')
    parquet_configure_parser.add_argument('--archive-older-than', type=int, default=7776000, help='Archive files older than N seconds (default: 90 days)')
    parquet_configure_parser.add_argument('--cleanup-temp-files', action='store_true', default=True, help='Automatically cleanup temporary files')
    parquet_configure_parser.add_argument('--enable-versioning', action='store_true', help='Enable file versioning')
    
    # Parquet status
    parquet_subparsers.add_parser('status', help='Show Parquet storage status')
    
    # Parquet read
    parquet_read_parser = parquet_subparsers.add_parser('read', help='Read Parquet data')
    parquet_read_parser.add_argument('file_path', help='Path to Parquet file')
    parquet_read_parser.add_argument('--limit', type=int, help='Limit number of rows to read')
    parquet_read_parser.add_argument('--columns', help='Comma-separated list of columns to read')
    
    # Parquet write
    parquet_write_parser = parquet_subparsers.add_parser('write', help='Write data to Parquet')
    parquet_write_parser.add_argument('input_file', help='Input data file (CSV, JSON)')
    parquet_write_parser.add_argument('output_file', help='Output Parquet file path')
    parquet_write_parser.add_argument('--format', choices=['csv', 'json'], default='csv', help='Input file format')
    
    # Parquet query
    parquet_query_parser = parquet_subparsers.add_parser('query', help='Query Parquet data')
    parquet_query_parser.add_argument('file_path', help='Path to Parquet file')
    parquet_query_parser.add_argument('--filter', help='Filter expression')
    parquet_query_parser.add_argument('--sql', help='SQL query string')
    
    # Arrow backend
    arrow_parser = backend_subparsers.add_parser('arrow', help='Apache Arrow operations')
    arrow_subparsers = arrow_parser.add_subparsers(dest='arrow_action', help='Arrow actions')
    
    # Arrow configure
    arrow_configure_parser = arrow_subparsers.add_parser('configure', help='Configure Arrow settings')
    arrow_configure_parser.add_argument('--memory-pool', choices=['system', 'jemalloc'], default='system', help='Memory pool type')
    arrow_configure_parser.add_argument('--thread-count', type=int, help='Number of threads for parallel operations')
    
    # Arrow backend characteristics: HIGH SPEED, LOW PERSISTENCE (in-memory/temporary)
    arrow_configure_parser.add_argument('--memory-quota', help='Memory quota for Arrow operations (e.g., 8GB, 16GB)')
    arrow_configure_parser.add_argument('--memory-quota-action', choices=['warn', 'block', 'spill-to-disk', 'auto-cleanup'], default='spill-to-disk', help='Action when memory quota is exceeded')
    arrow_configure_parser.add_argument('--disk-cache-size', help='Disk cache size for spilled data (e.g., 100GB)')
    arrow_configure_parser.add_argument('--retention-policy', choices=['session', 'daily', 'weekly', 'manual'], default='daily', help='Data retention policy')
    arrow_configure_parser.add_argument('--auto-cleanup-age', type=int, default=86400, help='Auto cleanup age in seconds (default: 24 hours)')
    arrow_configure_parser.add_argument('--cleanup-threshold', type=float, default=0.8, help='Memory usage threshold to trigger cleanup (0.0-1.0)')
    arrow_configure_parser.add_argument('--compression', choices=['none', 'lz4', 'zstd', 'snappy'], default='lz4', help='Compression for cached data')
    arrow_configure_parser.add_argument('--enable-metrics', action='store_true', help='Enable performance metrics collection')
    
    # Arrow status
    arrow_subparsers.add_parser('status', help='Show Arrow configuration status')
    
    # Arrow convert
    arrow_convert_parser = arrow_subparsers.add_parser('convert', help='Convert data using Arrow')
    arrow_convert_parser.add_argument('input_file', help='Input file path')
    arrow_convert_parser.add_argument('output_file', help='Output file path')
    arrow_convert_parser.add_argument('--input-format', choices=['csv', 'json', 'parquet', 'feather'], required=True, help='Input format')
    arrow_convert_parser.add_argument('--output-format', choices=['csv', 'json', 'parquet', 'feather'], required=True, help='Output format')
    
    # Arrow schema
    arrow_schema_parser = arrow_subparsers.add_parser('schema', help='Analyze data schema')
    arrow_schema_parser.add_argument('file_path', help='Path to data file')
    arrow_schema_parser.add_argument('--format', choices=['csv', 'json', 'parquet', 'feather'], help='File format (auto-detected if not specified)')
    
    # Arrow compute
    arrow_compute_parser = arrow_subparsers.add_parser('compute', help='Perform compute operations')
    arrow_compute_parser.add_argument('file_path', help='Path to data file')
    arrow_compute_parser.add_argument('--operation', choices=['sum', 'mean', 'count', 'min', 'max'], required=True, help='Compute operation')
    arrow_compute_parser.add_argument('--column', help='Column name for operation')
    
    # Add examples in epilog
    backend_parser.epilog = """
examples:
  # HuggingFace operations
  ipfs-kit backend huggingface login --token <token>
  ipfs-kit backend huggingface list --type model --limit 5
  ipfs-kit backend huggingface files microsoft/DialoGPT-medium
  
  # GitHub operations (repos as buckets with username as peerID)
  ipfs-kit backend github login --token <token>
  ipfs-kit backend github list --user endomorphosis
  ipfs-kit backend github clone endomorphosis/ipfs_kit_py
  
  # S3 operations with replication and cache policies
  ipfs-kit backend s3 configure --access-key <key> --secret-key <secret> --cross-region-replication --replication-regions us-west-2,eu-west-1 --cache-policy lru --cache-size 5000
  ipfs-kit backend s3 list my-bucket
  ipfs-kit backend s3 upload file.txt my-bucket file.txt --storage-class STANDARD_IA --replicate-to us-west-2 --backup --priority high
  
  # Storacha operations
  ipfs-kit backend storacha configure --api-key <key>
  ipfs-kit backend storacha upload ./dataset --name "my-dataset"
  
  # IPFS operations with local caching
  ipfs-kit backend ipfs add ./model --recursive --pin
  ipfs-kit backend ipfs pin QmHash --cache-policy lru --cache-priority high --bucket critical-data --timeout 120
  ipfs-kit backend ipfs get QmHash --output ./downloaded
  
  # Google Drive operations  
  ipfs-kit backend gdrive auth --credentials creds.json
  ipfs-kit backend gdrive list --folder <folder_id>
  
  # Lotus/Filecoin operations
  ipfs-kit backend lotus configure --endpoint <rpc_url> --token <token>
  ipfs-kit backend lotus status
  ipfs-kit backend lotus store ./data.txt --duration 525600
  
  # Synapse operations
  ipfs-kit backend synapse configure --endpoint <url> --api-key <key>
  ipfs-kit backend synapse upload ./data.txt --project <project_id>
  ipfs-kit backend synapse download <synapse_id> ./local_file.txt
  
  # SSHFS operations
  ipfs-kit backend sshfs configure --hostname server.com --username user --private-key ~/.ssh/id_rsa
  ipfs-kit backend sshfs status
  ipfs-kit backend sshfs upload ./local_file.txt /remote/path/file.txt
  
  # FTP operations
  ipfs-kit backend ftp configure --host ftp.example.com --username user --password pass
  ipfs-kit backend ftp test
  ipfs-kit backend ftp upload ./local_file.txt /remote/file.txt
  
  # IPFS Cluster operations with global and bucket policies
  ipfs-kit backend ipfs-cluster configure --endpoint http://127.0.0.1:9094 --global-replication-min 3 --global-cache-policy adaptive --throughput-mode high-throughput --dr-geo-distribution region
  ipfs-kit backend ipfs-cluster status
  
  # Bucket management with disaster recovery policies
  ipfs-kit backend ipfs-cluster bucket create critical-data --replication-min 5 --cache-policy lru --throughput-mode low-latency --dr-tier critical --dr-zones us-east-1a,us-east-1b,us-west-2a
  ipfs-kit backend ipfs-cluster bucket create archive-data --replication-min 2 --cache-policy fifo --throughput-mode bandwidth-optimized --dr-tier archive --lifecycle-policy auto-archive --archive-after-days 90
  
  # Pin with bucket policies and per-pin overrides
  ipfs-kit backend ipfs-cluster pin QmHash --bucket critical-data --cache-priority critical --dr-tier critical --priority urgent
  ipfs-kit backend ipfs-cluster pin QmHash2 --bucket archive-data --replication-min 3 --cache-ttl 0 --dr-zones us-east-1a,eu-west-1a
  
  # Global policy management
  ipfs-kit backend ipfs-cluster policy show
  ipfs-kit backend ipfs-cluster policy update --global-replication-min 2 --throughput-mode balanced
  ipfs-kit backend ipfs-cluster policy template high-availability --scope global
  ipfs-kit backend ipfs-cluster policy template performance --scope bucket --bucket critical-data
  
  # IPFS Cluster Follow operations
  ipfs-kit backend ipfs-cluster-follow configure --name my-cluster --template default
  ipfs-kit backend ipfs-cluster-follow run my-cluster
  ipfs-kit backend ipfs-cluster-follow list
  
  # Parquet operations
  ipfs-kit backend parquet configure --storage-path ./parquet_data --compression snappy
  ipfs-kit backend parquet read ./data.parquet --limit 100 --columns id,name
  ipfs-kit backend parquet write ./data.csv ./output.parquet --format csv
  
  # Arrow operations
  ipfs-kit backend arrow configure --memory-pool jemalloc --thread-count 4
  ipfs-kit backend arrow convert ./data.csv ./data.parquet --input-format csv --output-format parquet
  ipfs-kit backend arrow compute ./data.parquet --operation mean --column price
  ipfs-kit backend sshfs download /remote/path/file.txt ./downloaded_file.txt
  ipfs-kit backend sshfs list /remote/directory
  
  # FTP operations
  ipfs-kit backend ftp configure --host ftp.server.com --username user --password pass --use-tls
  ipfs-kit backend ftp status
  ipfs-kit backend ftp upload ./local_file.txt /remote/path/file.txt
  ipfs-kit backend ftp download /remote/path/file.txt ./downloaded_file.txt
  ipfs-kit backend ftp list /remote/directory
"""
    
    # Health monitoring
    health_parser = subparsers.add_parser('health', help='Health monitoring (supports backend-specific checks)')
    health_subparsers = health_parser.add_subparsers(dest='health_action', help='Health actions')
    
    # Health check with optional backend filter
    health_check_parser = health_subparsers.add_parser('check', help='Run health check [backend]')
    health_check_parser.add_argument('backend', nargs='?',
                                    choices=['daemon', 's3', 'lotus', 'storacha', 'gdrive', 'synapse', 'huggingface', 'github', 'ipfs_cluster', 'cluster_follow', 'parquet', 'arrow', 'sshfs', 'ftp', 'package', 'all'],
                                    help='Check health of specific backend (optional)')    # Health status with optional backend filter  
    health_status_parser = health_subparsers.add_parser('status', help='Show health status [backend]')
    health_status_parser.add_argument('backend', nargs='?',
                                     choices=['daemon', 's3', 'lotus', 'storacha', 'gdrive', 'synapse', 'huggingface', 'github', 'ipfs_cluster', 'cluster_follow', 'parquet', 'arrow', 'sshfs', 'ftp', 'package', 'all'],
                                     help='Show status of specific backend (optional)')
    
    # Configuration
    # Enhanced config management with all storage backends
    config_parser = subparsers.add_parser('config', help='Configuration management for all storage backends')
    config_subparsers = config_parser.add_subparsers(dest='config_action', help='Config actions')

    # Config show command  
    show_config_parser = config_subparsers.add_parser('show', help='Show current configuration from ~/.ipfs_kit/')
    show_config_parser.add_argument('--backend', choices=['daemon', 's3', 'lotus', 'storacha', 'gdrive', 'synapse', 'huggingface', 'github', 'ipfs_cluster', 'cluster_follow', 'parquet', 'arrow', 'sshfs', 'ftp', 'package', 'all'],
                                   help='Show configuration for specific backend')
    
    # Config validate command
    validate_config_parser = config_subparsers.add_parser('validate', help='Validate all configuration files')
    validate_config_parser.add_argument('--backend', choices=['daemon', 's3', 'lotus', 'storacha', 'gdrive', 'synapse', 'huggingface', 'github', 'ipfs_cluster', 'cluster_follow', 'parquet', 'arrow', 'sshfs', 'ftp', 'package', 'all'],
                                      help='Validate specific backend configuration')
    
    # Config set command
    set_config_parser = config_subparsers.add_parser('set', help='Set configuration value')
    set_config_parser.add_argument('key', help='Configuration key (e.g., s3.region, daemon.port)')
    set_config_parser.add_argument('value', help='Configuration value')
    
    # Global pinset policy configuration
    pinset_policy_parser = config_subparsers.add_parser('pinset-policy', help='Configure global pinset replication and cache policies')
    pinset_policy_subparsers = pinset_policy_parser.add_subparsers(dest='pinset_policy_action', help='Pinset policy actions')
    
    # Show pinset policies
    pinset_policy_show_parser = pinset_policy_subparsers.add_parser('show', help='Show current global pinset policies')
    
    # Set pinset policies
    pinset_policy_set_parser = pinset_policy_subparsers.add_parser('set', help='Set global pinset policies')
    pinset_policy_set_parser.add_argument('--replication-strategy', choices=['single', 'multi-backend', 'tiered', 'adaptive'], default='adaptive', help='Global replication strategy across backends')
    pinset_policy_set_parser.add_argument('--min-replicas', type=int, default=2, help='Minimum replicas across all backends')
    pinset_policy_set_parser.add_argument('--max-replicas', type=int, default=5, help='Maximum replicas across all backends')
    pinset_policy_set_parser.add_argument('--cache-policy', choices=['lru', 'lfu', 'fifo', 'mru', 'adaptive', 'tiered'], default='adaptive', help='Global cache eviction policy')
    pinset_policy_set_parser.add_argument('--cache-size', type=int, default=10000, help='Global cache size (number of objects)')
    pinset_policy_set_parser.add_argument('--cache-memory-limit', help='Cache memory limit (e.g., 1GB, 500MB)')
    
    # Performance and distribution policies
    pinset_policy_set_parser.add_argument('--performance-tier', choices=['speed-optimized', 'balanced', 'persistence-optimized'], default='balanced', help='Global performance optimization strategy')
    pinset_policy_set_parser.add_argument('--geographic-distribution', choices=['local', 'regional', 'global'], default='regional', help='Geographic distribution preference')
    pinset_policy_set_parser.add_argument('--failover-strategy', choices=['immediate', 'delayed', 'manual'], default='immediate', help='Backend failover strategy')
    
    # Auto-tiering policies
    pinset_policy_set_parser.add_argument('--auto-tier', action='store_true', help='Enable automatic tiering based on access patterns')
    pinset_policy_set_parser.add_argument('--hot-tier-duration', type=int, default=86400, help='Time in seconds before moving to warm tier')
    pinset_policy_set_parser.add_argument('--warm-tier-duration', type=int, default=2592000, help='Time in seconds before moving to cold tier')
    pinset_policy_set_parser.add_argument('--auto-gc', action='store_true', help='Enable automatic garbage collection')
    pinset_policy_set_parser.add_argument('--gc-threshold', type=float, default=0.8, help='Storage threshold to trigger garbage collection (0.0-1.0)')
    
    # Backend selection preferences
    pinset_policy_set_parser.add_argument('--preferred-backends', help='Comma-separated list of preferred backends in order')
    pinset_policy_set_parser.add_argument('--exclude-backends', help='Comma-separated list of backends to exclude')
    pinset_policy_set_parser.add_argument('--backend-weights', help='Backend weighting (e.g., "arrow:0.3,s3:0.4,filecoin:0.3")')
    
    # Reset pinset policies to defaults
    pinset_policy_subparsers.add_parser('reset', help='Reset all pinset policies to defaults')
    
    # Config init command - interactive setup
    init_config_parser = config_subparsers.add_parser('init', help='Interactive configuration setup for all backends')
    init_config_parser.add_argument('--backend', choices=['daemon', 's3', 'lotus', 'storacha', 'gdrive', 'synapse', 'huggingface', 'github', 'ipfs_cluster', 'cluster_follow', 'parquet', 'arrow', 'sshfs', 'ftp', 'package', 'all'], 
                                   help='Configure specific backend or all backends')
    init_config_parser.add_argument('--non-interactive', action='store_true', help='Use defaults without prompts')
    
    # Config backup/restore
    config_subparsers.add_parser('backup', help='Backup configuration to a file')
    restore_config_parser = config_subparsers.add_parser('restore', help='Restore configuration from backup')
    restore_config_parser.add_argument('backup_file', help='Backup file to restore from')
    
    # Config reset command
    reset_config_parser = config_subparsers.add_parser('reset', help='Reset configuration to defaults')
    reset_config_parser.add_argument('--backend', choices=['daemon', 's3', 'lotus', 'storacha', 'gdrive', 'synapse', 'huggingface', 'github', 'ipfs_cluster', 'cluster_follow', 'parquet', 'arrow', 'sshfs', 'ftp', 'package', 'all'],
                                    help='Reset specific backend or all backends')
    reset_config_parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')    # Bucket management
    bucket_parser = subparsers.add_parser('bucket', help='Virtual filesystem (bucket) discovery and management')
    bucket_subparsers = bucket_parser.add_subparsers(dest='bucket_action', help='Bucket actions')
    
    bucket_subparsers.add_parser('list', help='List available buckets')
    bucket_subparsers.add_parser('discover', help='Discover new buckets')
    bucket_subparsers.add_parser('analytics', help='Show bucket analytics')
    bucket_subparsers.add_parser('refresh', help='Refresh bucket index')
    
    # New Parquet-based bucket commands
    bucket_files_parser = bucket_subparsers.add_parser('files', help='List files in a specific bucket')
    bucket_files_parser.add_argument('bucket_name', help='Name of the bucket to query')
    bucket_files_parser.add_argument('--limit', type=int, help='Limit number of results')
    
    bucket_find_parser = bucket_subparsers.add_parser('find-cid', help='Find bucket location for a CID')
    bucket_find_parser.add_argument('cid', help='Content ID to search for')
    
    bucket_snapshots_parser = bucket_subparsers.add_parser('snapshots', help='Show bucket snapshots and hashes')
    bucket_snapshots_parser.add_argument('--bucket', help='Show snapshot info for specific bucket')
    
    bucket_car_parser = bucket_subparsers.add_parser('prepare-car', help='Prepare bucket for CAR file generation')
    bucket_car_parser.add_argument('bucket_name', nargs='?', help='Name of the bucket to prepare')
    bucket_car_parser.add_argument('--all', action='store_true', help='Prepare all buckets for CAR generation')
    
    # Generate CAR files from VFS index (not content)
    bucket_index_car_parser = bucket_subparsers.add_parser('generate-index-car', help='Generate CAR files from VFS index metadata')
    bucket_index_car_parser.add_argument('bucket_name', nargs='?', help='Name of the bucket to generate CAR for')
    bucket_index_car_parser.add_argument('--all', action='store_true', help='Generate CAR files for all buckets')

    # Generate CAR from bucket registry
    bucket_registry_car_parser = bucket_subparsers.add_parser('generate-registry-car', help='Generate CAR file from bucket registry parquet')
    
    # Index management commands
    bucket_index_parser = bucket_subparsers.add_parser('index', help='Show comprehensive bucket index')
    bucket_index_parser.add_argument('--refresh', action='store_true', help='Force refresh of index')
    bucket_index_parser.add_argument('--format', choices=['table', 'json', 'yaml'], default='table', help='Output format')
    bucket_index_parser.add_argument('--export', help='Export index to file')
    
    # Backend index commands
    backend_index_parser = bucket_subparsers.add_parser('backends', help='Show comprehensive backend index')  
    backend_index_parser.add_argument('--refresh', action='store_true', help='Force refresh of backend index')
    backend_index_parser.add_argument('--format', choices=['table', 'json', 'yaml'], default='table', help='Output format')
    backend_index_parser.add_argument('--export', help='Export backend index to file')
    backend_index_parser.add_argument('--status', choices=['all', 'online', 'offline', 'configured'], default='all', help='Filter by status')
    
    # Pinset analysis and replica management
    pinset_analyze_parser = bucket_subparsers.add_parser('analyze-pinsets', help='Analyze pinsets and manage replicas for disaster recovery and caching')
    pinset_analyze_parser.add_argument('--execute', action='store_true', help='Execute recommended pin management actions')
    pinset_analyze_parser.add_argument('--dry-run', action='store_true', help='Show what would be done without executing actions')
    pinset_analyze_parser.add_argument('--priority-threshold', type=int, default=30, help='Priority threshold for cache candidates')
    pinset_analyze_parser.add_argument('--max-actions', type=int, default=100, help='Maximum number of actions to execute')
    pinset_analyze_parser.add_argument('--force-replication', action='store_true', help='Force replication even for healthy buckets')
    pinset_analyze_parser.add_argument('--cache-only', action='store_true', help='Only perform cache optimization actions')
    pinset_analyze_parser.add_argument('--replicate-only', action='store_true', help='Only perform replication actions')
    
    # Backend sync management
    backend_sync_parser = bucket_subparsers.add_parser('sync-backends', help='Manage backend synchronization and dirty state')
    backend_sync_parser.add_argument('--backend', help='Specific backend to sync (default: all dirty backends)')
    backend_sync_parser.add_argument('--dry-run', action='store_true', help='Show what would be synced without executing')
    backend_sync_parser.add_argument('--force', action='store_true', help='Force sync even for clean backends')
    backend_sync_parser.add_argument('--clear-dirty', action='store_true', help='Mark all backends as clean without syncing')
    backend_sync_parser.add_argument('--status', action='store_true', help='Show dirty state status for all backends')
    
    # List generated CAR files
    bucket_list_cars_parser = bucket_subparsers.add_parser('list-cars', help='List generated CAR files')
    
    # Bucket policy management commands
    bucket_policy_parser = bucket_subparsers.add_parser('policy', help='Manage bucket-level replication and cache policies')
    bucket_policy_subparsers = bucket_policy_parser.add_subparsers(dest='bucket_policy_action', help='Bucket policy actions')
    
    # Show bucket policies
    bucket_policy_show_parser = bucket_policy_subparsers.add_parser('show', help='Show policies for a bucket or all buckets')
    bucket_policy_show_parser.add_argument('bucket_name', nargs='?', help='Bucket name (optional, shows all if not provided)')
    
    # Set bucket policy
    bucket_policy_set_parser = bucket_policy_subparsers.add_parser('set', help='Set replication and cache policy for a bucket')
    bucket_policy_set_parser.add_argument('bucket_name', help='Name of the bucket to configure')
    
    # Replication policies for bucket
    bucket_policy_set_parser.add_argument('--replication-backends', help='Comma-separated list of backends for replication (e.g., "s3,filecoin,arrow")')
    bucket_policy_set_parser.add_argument('--min-replicas', type=int, help='Minimum replicas for this bucket (overrides global)')
    bucket_policy_set_parser.add_argument('--max-replicas', type=int, help='Maximum replicas for this bucket (overrides global)')
    bucket_policy_set_parser.add_argument('--primary-backend', choices=['s3', 'filecoin', 'arrow', 'parquet', 'ipfs', 'storacha', 'sshfs', 'ftp'], help='Primary backend for this bucket')
    
    # Cache policies for bucket
    bucket_policy_set_parser.add_argument('--cache-policy', choices=['lru', 'lfu', 'fifo', 'mru', 'adaptive', 'inherit'], default='inherit', help='Cache eviction policy for this bucket')
    bucket_policy_set_parser.add_argument('--cache-size', type=int, help='Cache size for this bucket (overrides global)')
    bucket_policy_set_parser.add_argument('--cache-priority', choices=['low', 'normal', 'high', 'critical'], default='normal', help='Cache priority for this bucket')
    bucket_policy_set_parser.add_argument('--cache-ttl', type=int, help='Cache TTL in seconds (0 = permanent)')
    
    # Performance characteristics
    bucket_policy_set_parser.add_argument('--performance-tier', choices=['speed-optimized', 'balanced', 'persistence-optimized', 'inherit'], default='inherit', help='Performance optimization for this bucket')
    bucket_policy_set_parser.add_argument('--access-pattern', choices=['random', 'sequential', 'write-heavy', 'read-heavy', 'mixed'], default='mixed', help='Expected access pattern for optimization')
    
    # Tiering and lifecycle
    bucket_policy_set_parser.add_argument('--auto-tier', action='store_true', help='Enable auto-tiering for this bucket')
    bucket_policy_set_parser.add_argument('--hot-backend', help='Backend for hot/frequently accessed data')
    bucket_policy_set_parser.add_argument('--warm-backend', help='Backend for warm/occasionally accessed data')  
    bucket_policy_set_parser.add_argument('--cold-backend', help='Backend for cold/rarely accessed data')
    bucket_policy_set_parser.add_argument('--archive-backend', help='Backend for archived data')
    
    # Retention and quota policies
    bucket_policy_set_parser.add_argument('--retention-days', type=int, help='Data retention period in days')
    bucket_policy_set_parser.add_argument('--max-size', help='Maximum bucket size (e.g., 100GB, 1TB)')
    bucket_policy_set_parser.add_argument('--quota-action', choices=['warn', 'block', 'auto-archive', 'auto-delete'], default='warn', help='Action when quota is exceeded')
    
    # Copy policy from another bucket
    bucket_policy_copy_parser = bucket_policy_subparsers.add_parser('copy', help='Copy policy from one bucket to another')
    bucket_policy_copy_parser.add_argument('source_bucket', help='Source bucket to copy policy from')
    bucket_policy_copy_parser.add_argument('target_bucket', help='Target bucket to copy policy to')
    
    # Apply policy template to bucket
    bucket_policy_template_parser = bucket_policy_subparsers.add_parser('template', help='Apply a predefined policy template to bucket')
    bucket_policy_template_parser.add_argument('bucket_name', help='Bucket to apply template to')
    bucket_policy_template_parser.add_argument('template', choices=['high-speed', 'high-persistence', 'balanced', 'cost-optimized', 'archive'], help='Policy template to apply')
    
    # Reset bucket policy to defaults
    bucket_policy_reset_parser = bucket_policy_subparsers.add_parser('reset', help='Reset bucket policy to global defaults')
    bucket_policy_reset_parser.add_argument('bucket_name', help='Bucket to reset policy for')
    
    # IPFS upload commands
    bucket_upload_ipfs_parser = bucket_subparsers.add_parser('upload-ipfs', help='Upload CAR files to IPFS')
    bucket_upload_ipfs_parser.add_argument('car_filename', nargs='?', help='CAR filename to upload')
    bucket_upload_ipfs_parser.add_argument('--all', action='store_true', help='Upload all CAR files to IPFS')
    
    # Show IPFS upload history
    bucket_ipfs_history_parser = bucket_subparsers.add_parser('ipfs-history', help='Show IPFS upload history')
    
    # Verify IPFS content
    bucket_verify_ipfs_parser = bucket_subparsers.add_parser('verify-ipfs', help='Verify content exists in IPFS')
    bucket_verify_ipfs_parser.add_argument('cid', help='CID to verify in IPFS')
    
    # Direct IPFS index upload (recommended approach)
    bucket_direct_ipfs_parser = bucket_subparsers.add_parser('upload-index', help='Upload VFS index directly to IPFS (recommended)')
    bucket_direct_ipfs_parser.add_argument('bucket_name', nargs='?', help='Bucket name to upload index for')
    bucket_direct_ipfs_parser.add_argument('--all', action='store_true', help='Upload indexes for all buckets')

    # Enhanced VFS Index Download with CLI Integration
    bucket_download_parser = bucket_subparsers.add_parser('download-vfs', help='Download and extract VFS indexes with optimized backend selection')
    bucket_download_parser.add_argument('hash_or_bucket', help='Master index hash, bucket index hash, or bucket name for local extraction')
    bucket_download_parser.add_argument('--bucket-name', help='Bucket name (required when providing bucket hash)')
    bucket_download_parser.add_argument('--workers', type=int, help='Number of parallel download workers')
    bucket_download_parser.add_argument('--output-dir', help='Output directory for downloads')
    bucket_download_parser.add_argument('--benchmark', action='store_true', help='Benchmark backend performance')
    bucket_download_parser.add_argument('--backend', choices=['auto', 'ipfs', 's3', 'lotus', 'cluster'], default='auto', help='Force specific backend')

    # Core bucket operations
    bucket_create_parser = bucket_subparsers.add_parser('create', help='Create a new bucket')
    bucket_create_parser.add_argument('bucket_name', help='Bucket name')
    bucket_create_parser.add_argument('--bucket-type', choices=['general', 'dataset', 'knowledge', 'media', 'archive', 'temp'], 
                                      default='general', help='Bucket type')
    bucket_create_parser.add_argument('--vfs-structure', choices=['unixfs', 'graph', 'vector', 'hybrid'], 
                                      default='hybrid', help='VFS structure type')
    bucket_create_parser.add_argument('--metadata', help='JSON metadata for the bucket')
    bucket_create_parser.add_argument('--description', help='Bucket description')
    
    # Replication settings
    bucket_create_parser.add_argument('--replication-min', type=int, default=2, help='Minimum replication factor')
    bucket_create_parser.add_argument('--replication-target', type=int, default=3, help='Target replication factor')
    bucket_create_parser.add_argument('--replication-max', type=int, default=5, help='Maximum replication factor')
    bucket_create_parser.add_argument('--replication-policy', choices=['balanced', 'performance', 'cost-optimized'], 
                                      default='balanced', help='Replication policy')
    
    # Disaster recovery
    bucket_create_parser.add_argument('--dr-tier', choices=['critical', 'important', 'standard', 'archive'], 
                                      default='standard', help='Disaster recovery tier')
    bucket_create_parser.add_argument('--dr-zones', help='Required availability zones (comma-separated)')
    bucket_create_parser.add_argument('--dr-backup-frequency', choices=['continuous', 'hourly', 'daily', 'weekly'], 
                                      default='daily', help='Backup frequency')
    
    # Cache settings
    bucket_create_parser.add_argument('--cache-policy', choices=['lru', 'lfu', 'fifo', 'mru', 'adaptive'], 
                                      default='lru', help='Cache eviction policy')
    bucket_create_parser.add_argument('--cache-size-mb', type=int, default=512, help='Cache size in MB')
    bucket_create_parser.add_argument('--cache-ttl', type=int, default=3600, help='Cache TTL in seconds')
    
    # Performance settings
    bucket_create_parser.add_argument('--throughput-mode', choices=['balanced', 'high-throughput', 'low-latency', 'bandwidth-optimized'], 
                                      default='balanced', help='Throughput optimization mode')
    bucket_create_parser.add_argument('--concurrent-ops', type=int, default=5, help='Maximum concurrent operations')
    bucket_create_parser.add_argument('--performance-tier', choices=['speed-optimized', 'balanced', 'persistence-optimized'], 
                                      default='balanced', help='Performance optimization tier')
    
    # Lifecycle management
    bucket_create_parser.add_argument('--lifecycle-policy', choices=['none', 'auto-archive', 'auto-delete', 'custom'], 
                                      default='none', help='Lifecycle management policy')
    bucket_create_parser.add_argument('--archive-after-days', type=int, help='Archive content after N days')
    bucket_create_parser.add_argument('--delete-after-days', type=int, help='Delete content after N days')
    
    # Resource limits
    bucket_create_parser.add_argument('--max-file-size-gb', type=int, default=10, help='Maximum file size in GB')
    bucket_create_parser.add_argument('--max-total-size-gb', type=int, default=1000, help='Maximum total bucket size in GB')
    bucket_create_parser.add_argument('--max-files', type=int, default=100000, help='Maximum number of files')
    
    # Access control
    bucket_create_parser.add_argument('--public-read', action='store_true', help='Enable public read access')
    bucket_create_parser.add_argument('--api-access', action='store_true', default=True, help='Enable API access')
    bucket_create_parser.add_argument('--web-interface', action='store_true', default=True, help='Enable web interface')
    
    bucket_rm_parser = bucket_subparsers.add_parser('rm', help='Remove a bucket')
    bucket_rm_parser.add_argument('bucket_name', help='Bucket name to remove')
    bucket_rm_parser.add_argument('--force', action='store_true', help='Force removal without confirmation')
    
    # File operations within buckets
    bucket_add_parser = bucket_subparsers.add_parser('add', help='Add file to bucket')
    bucket_add_parser.add_argument('bucket', help='Bucket name')
    bucket_add_parser.add_argument('source', help='Local path to file to add')
    bucket_add_parser.add_argument('path', help='Virtual path within bucket')
    bucket_add_parser.add_argument('--metadata', help='JSON metadata for the file')
    
    bucket_get_parser = bucket_subparsers.add_parser('get', help='Get file from bucket')
    bucket_get_parser.add_argument('bucket', help='Bucket name')
    bucket_get_parser.add_argument('path', help='Virtual path within bucket')
    bucket_get_parser.add_argument('--output', help='Output file path (defaults to original filename)')
    
    bucket_cat_parser = bucket_subparsers.add_parser('cat', help='Display file content from bucket')
    bucket_cat_parser.add_argument('bucket', help='Bucket name')
    bucket_cat_parser.add_argument('path', help='Virtual path within bucket')
    bucket_cat_parser.add_argument('--limit', type=int, help='Limit output to N bytes')
    
    bucket_rm_file_parser = bucket_subparsers.add_parser('rm-file', help='Remove file from bucket')
    bucket_rm_file_parser.add_argument('bucket', help='Bucket name')
    bucket_rm_file_parser.add_argument('path', help='Virtual path within bucket')
    
    # Pin operations
    bucket_pin_parser = bucket_subparsers.add_parser('pin', help='Pin operations for bucket content')
    bucket_pin_subparsers = bucket_pin_parser.add_subparsers(dest='pin_action', help='Pin actions')
    
    bucket_pin_ls_parser = bucket_pin_subparsers.add_parser('ls', help='List pinned content in bucket')
    bucket_pin_ls_parser.add_argument('bucket_name', help='Bucket name')
    bucket_pin_ls_parser.add_argument('--limit', type=int, help='Limit number of results')
    
    bucket_pin_add_parser = bucket_pin_subparsers.add_parser('add', help='Pin file in bucket')
    bucket_pin_add_parser.add_argument('bucket_name', help='Bucket name')
    bucket_pin_add_parser.add_argument('virtual_path', help='Virtual path within bucket')
    bucket_pin_add_parser.add_argument('--recursive', action='store_true', help='Pin recursively')
    
    bucket_pin_get_parser = bucket_pin_subparsers.add_parser('get', help='Get and pin file from bucket')
    bucket_pin_get_parser.add_argument('bucket_name', help='Bucket name')
    bucket_pin_get_parser.add_argument('virtual_path', help='Virtual path within bucket')
    bucket_pin_get_parser.add_argument('--output', help='Output file path')
    
    bucket_pin_cat_parser = bucket_pin_subparsers.add_parser('cat', help='Display pinned file content from bucket')
    bucket_pin_cat_parser.add_argument('bucket_name', help='Bucket name')
    bucket_pin_cat_parser.add_argument('virtual_path', help='Virtual path within bucket')
    bucket_pin_cat_parser.add_argument('--limit', type=int, help='Limit output to N bytes')
    
    bucket_pin_rm_parser = bucket_pin_subparsers.add_parser('rm', help='Unpin file in bucket')
    bucket_pin_rm_parser.add_argument('bucket_name', help='Bucket name')
    bucket_pin_rm_parser.add_argument('virtual_path', help='Virtual path within bucket')
    
    bucket_pin_tag_parser = bucket_pin_subparsers.add_parser('tag', help='Tag pinned content in bucket')
    bucket_pin_tag_parser.add_argument('bucket_name', help='Bucket name')
    bucket_pin_tag_parser.add_argument('virtual_path', help='Virtual path within bucket')
    bucket_pin_tag_parser.add_argument('tag', help='Tag to add')
    
    # Tag operations for files
    bucket_tag_parser = bucket_subparsers.add_parser('tag', help='Tag file in bucket')
    bucket_tag_parser.add_argument('bucket_name', help='Bucket name')
    bucket_tag_parser.add_argument('virtual_path', help='Virtual path within bucket')
    bucket_tag_parser.add_argument('tag', help='Tag to add')

    # MCP (Model Context Protocol) management
    mcp_parser = subparsers.add_parser('mcp', help='Model Context Protocol server and dashboard management')
    mcp_subparsers = mcp_parser.add_subparsers(dest='mcp_action', help='MCP actions')
    
    # Basic MCP server management
    start_parser = mcp_subparsers.add_parser('start', help='Start MCP server and dashboard')
    start_parser.add_argument('--port', type=int, default=8004, help='Port for unified MCP server + dashboard (default: 8004)')
    start_parser.add_argument('--host', default='127.0.0.1', help='Host for MCP server (default: 127.0.0.1)')
    start_parser.add_argument('--no-dashboard', action='store_true', help='Disabled in unified mode - dashboard is integrated')
    start_parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    stop_parser = mcp_subparsers.add_parser('stop', help='Stop MCP server and dashboard')
    stop_parser.add_argument('--port', type=int, default=8004, help='Port for MCP server (default: 8004)')
    stop_parser.add_argument('--host', default='127.0.0.1', help='Host for MCP server (default: 127.0.0.1)')
    
    status_parser = mcp_subparsers.add_parser('status', help='Check MCP server and dashboard status')
    status_parser.add_argument('--port', type=int, default=8004, help='Port for MCP server (default: 8004)')
    status_parser.add_argument('--host', default='127.0.0.1', help='Host for MCP server (default: 127.0.0.1)')
    status_parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    restart_parser = mcp_subparsers.add_parser('restart', help='Restart MCP server and dashboard')
    restart_parser.add_argument('--port', type=int, default=8004, help='Port for MCP server (default: 8004)')
    restart_parser.add_argument('--host', default='127.0.0.1', help='Host for MCP server (default: 127.0.0.1)')
    restart_parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    # MCP role configuration - simplified for dashboard integration
    mcp_role_parser = mcp_subparsers.add_parser('role', help='Configure MCP server role (for dashboard integration)')
    mcp_role_parser.add_argument('role', choices=['master', 'worker', 'leecher', 'modular', 'local'], 
                                 help='Role configuration: master (cluster coordinator), worker (content processing), leecher (minimal resources), modular (custom/kitchen sink), local (no networking)')
    mcp_role_parser.add_argument('--master-address', help='Master node address (required for worker role, ignored for leecher)')
    mcp_role_parser.add_argument('--cluster-secret', help='Cluster authentication secret')
    
    # MCP CLI bridge
    cli_parser = mcp_subparsers.add_parser('cli', help='Use MCP CLI tool')
    cli_parser.add_argument('mcp_args', nargs='*', help='Arguments to pass to mcp-cli')
    
    # Metrics
    metrics_parser = subparsers.add_parser('metrics', help='Show performance metrics')
    metrics_parser.add_argument('--detailed', action='store_true', help='Show detailed metrics')
    
    # Resource tracking commands - using fast index for bandwidth/storage monitoring
    try:
        from .resource_cli_fast import register_resource_commands
        register_resource_commands(subparsers)
    except ImportError:
        # If fast resource CLI not available, create basic stub
        resource_parser = subparsers.add_parser('resource', help='Resource tracking operations')
        resource_parser.add_argument('action', help='Resource action (requires fast index setup)')
    
    # Log aggregation commands - unified log viewing across all components
    log_parser = subparsers.add_parser('log', help='Unified log aggregation and viewing')
    log_subparsers = log_parser.add_subparsers(dest='log_action', help='Log actions')
    
    # Log show command
    show_log_parser = log_subparsers.add_parser('show', help='Show logs from various components')
    show_log_parser.add_argument('--component', 
                                choices=['all', 'daemon', 'wal', 'fs_journal', 'bucket', 'health', 'replication', 'backends', 'pin', 'config'],
                                default='all',
                                help='Component to show logs for')
    show_log_parser.add_argument('--level', 
                                choices=['debug', 'info', 'warning', 'error', 'critical'],
                                help='Filter by log level')
    show_log_parser.add_argument('--limit', type=int, default=50, help='Number of log entries to show')
    show_log_parser.add_argument('--since', help='Show logs since timestamp (ISO format) or relative time (1h, 30m, 1d)')
    show_log_parser.add_argument('--tail', action='store_true', help='Follow log output (like tail -f)')
    show_log_parser.add_argument('--grep', help='Filter log entries containing this text')
    
    # Log stats command
    stats_log_parser = log_subparsers.add_parser('stats', help='Show log statistics and summaries')
    stats_log_parser.add_argument('--component', 
                                 choices=['all', 'daemon', 'wal', 'fs_journal', 'bucket', 'health', 'replication', 'backends', 'pin', 'config'],
                                 default='all',
                                 help='Component to show stats for')
    stats_log_parser.add_argument('--hours', type=int, default=24, help='Hours of history to analyze')
    
    # Log clear command
    clear_log_parser = log_subparsers.add_parser('clear', help='Clear logs for specified components')
    clear_log_parser.add_argument('--component', 
                                 choices=['all', 'daemon', 'wal', 'fs_journal', 'bucket', 'health', 'replication', 'backends', 'pin', 'config'],
                                 default='all',
                                 help='Component to clear logs for')
    clear_log_parser.add_argument('--older-than', help='Clear logs older than specified time (e.g., 7d, 30d)')
    clear_log_parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    
    # Log export command
    export_log_parser = log_subparsers.add_parser('export', help='Export logs to file')
    export_log_parser.add_argument('--component', 
                                  choices=['all', 'daemon', 'wal', 'fs_journal', 'bucket', 'health', 'replication', 'backends', 'pin', 'config'],
                                  default='all',
                                  help='Component to export logs for')
    export_log_parser.add_argument('--format', 
                                  choices=['json', 'csv', 'text'],
                                  default='json',
                                  help='Export format')
    export_log_parser.add_argument('--output', '-o', required=True, help='Output file path')
    export_log_parser.add_argument('--since', help='Export logs since timestamp or relative time')

    return parser


# Health status update helper functions
def _is_health_data_stale(health_result: Dict[str, Any], max_age_minutes: int = 5) -> bool:
    """Check if health data is stale (older than max_age_minutes)."""
    try:
        if not health_result.get('success', False):
            return True
            
        timestamp_str = health_result.get('timestamp')
        if not timestamp_str:
            return True
            
        # Parse timestamp
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            return True
            
        # Check if older than max_age_minutes
        age = datetime.now() - timestamp.replace(tzinfo=None)
        return age > timedelta(minutes=max_age_minutes)
        
    except Exception:
        return True


def _is_program_state_stale(status_result: Dict[str, Any], max_age_minutes: int = 5) -> bool:
    """Check if program state is stale (older than max_age_minutes)."""
    try:
        if not status_result.get('success', False):
            return True
            
        timestamp_str = status_result.get('timestamp')
        if not timestamp_str:
            return True
            
        # Parse timestamp
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            return True
            
        # Check if older than max_age_minutes
        age = datetime.now() - timestamp.replace(tzinfo=None)
        return age > timedelta(minutes=max_age_minutes)
        
    except Exception:
        return True


def _update_health_status(reader) -> None:
    """Update health status by running health monitoring programs."""
    try:
        print("   🔄 Running health status collectors...")
        
        # Try to start daemon if not running to ensure health data collection
        try:
            from .enhanced_daemon_manager import EnhancedDaemonManager
            daemon_manager = EnhancedDaemonManager()
            # Check if daemon is running using available method
            try:
                if hasattr(daemon_manager, 'is_daemon_running'):
                    daemon_running = daemon_manager.is_daemon_running()
                elif hasattr(daemon_manager, 'check_daemon_status'):
                    status = daemon_manager.check_daemon_status()
                    daemon_running = status.get('running', False)
                else:
                    daemon_running = False
                    
                if not daemon_running:
                    print("   🚀 Starting daemon for health monitoring...")
                    daemon_manager.start_daemon()
            except Exception as start_e:
                print(f"   ⚠️  Could not start daemon: {start_e}")
        except Exception as e:
            print(f"   ⚠️  Could not access daemon manager: {e}")
        
        # Run health collection script if available
        health_collectors = [
            Path.home() / '.ipfs_kit' / 'scripts' / 'collect_health.py',
            Path(__file__).parent / 'scripts' / 'collect_health.py',
            Path(__file__).parent / 'health_collector.py'
        ]
        
        for collector in health_collectors:
            if collector.exists():
                try:
                    print(f"   📊 Running health collector: {collector.name}")
                    subprocess.run([sys.executable, str(collector)], 
                                 timeout=30, capture_output=True, check=False)
                    break
                except Exception as e:
                    print(f"   ⚠️  Health collector failed: {e}")
                    continue
        
        # Trigger IPFS status collection
        try:
            result = subprocess.run(['ipfs', 'id'], capture_output=True, timeout=10, text=True)
            if result.returncode == 0:
                print("   ✅ IPFS status collected")
        except Exception:
            pass
            
        print("   ✨ Health status update completed")
        
    except Exception as e:
        print(f"   ⚠️  Health status update failed: {e}")


def _update_program_state(reader) -> None:
    """Update program state by running state monitoring programs."""
    try:
        print("   🔄 Running program state collectors...")
        
        # Try to start daemon if not running to ensure state data collection  
        try:
            from .enhanced_daemon_manager import EnhancedDaemonManager
            daemon_manager = EnhancedDaemonManager()
            # Check if daemon is running using available method
            try:
                if hasattr(daemon_manager, 'is_daemon_running'):
                    daemon_running = daemon_manager.is_daemon_running()
                elif hasattr(daemon_manager, 'check_daemon_status'):
                    status = daemon_manager.check_daemon_status()
                    daemon_running = status.get('running', False)
                else:
                    daemon_running = False
                    
                if not daemon_running:
                    print("   🚀 Starting daemon for state monitoring...")
                    daemon_manager.start_daemon()
            except Exception as start_e:
                print(f"   ⚠️  Could not start daemon: {start_e}")
        except Exception as e:
            print(f"   ⚠️  Could not access daemon manager: {e}")
        
        # Update program state using the existing program_state module
        try:
            from .program_state import ProgramStateManager
            state_manager = ProgramStateManager()
            
            # Collect system metrics
            try:
                import psutil
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory() 
                disk = psutil.disk_usage('/')
                
                state_manager.update_system_state(
                    cpu_percent=cpu_percent,
                    memory_percent=memory.percent,
                    disk_percent=(disk.used / disk.total) * 100
                )
                print("   📊 System metrics updated")
            except Exception as e:
                print(f"   ⚠️  System metrics failed: {e}")
            
            # Collect network state
            try:
                result = subprocess.run(['ipfs', 'swarm', 'peers'], 
                                      capture_output=True, timeout=10, text=True)
                if result.returncode == 0:
                    peer_count = len(result.stdout.strip().split('\n'))
                    state_manager.update_network_state(ipfs_peers=peer_count)
                    print("   🌐 Network state updated")
            except Exception:
                print("   ⚠️  Network state failed (IPFS not running)")
            
            # Sync state to storage using available method
            try:
                if hasattr(state_manager, 'sync_to_db'):
                    state_manager.sync_to_db()
                elif hasattr(state_manager, 'save_state'):
                    state_manager.save_state()
                elif hasattr(state_manager, 'flush'):
                    state_manager.flush()
                print("   💾 Program state synced to storage")
            except Exception as e:
                print(f"   ⚠️  Program state sync failed: {e}")
            
        except Exception as e:
            print(f"   ⚠️  Program state manager failed: {e}")
        
        # Alternative: Update state files directly
        try:
            state_dir = Path.home() / '.ipfs_kit' / 'program_state' / 'parquet'
            state_dir.mkdir(parents=True, exist_ok=True)
            
            # Create a simple state update timestamp
            import pandas as pd
            timestamp_data = pd.DataFrame({
                'updated_at': [datetime.now().isoformat()],
                'status': ['updated'],
                'source': ['cli_health_check']
            })
            
            timestamp_file = state_dir / 'update_timestamp.parquet'
            timestamp_data.to_parquet(timestamp_file, index=False)
            print("   📅 State timestamp updated")
            
        except Exception as e:
            print(f"   ⚠️  Direct state update failed: {e}")
        
        print("   ✨ Program state update completed")
        
    except Exception as e:
        print(f"   ⚠️  Program state update failed: {e}")


class FastCLI:
    """Ultra-fast CLI that defers heavy imports and leverages centralized IPFS-Kit API."""
    
    def __init__(self):
        self.jit_manager = None
        self._ipfs_api = None  # Lazy-loaded centralized API instance
        self._vfs_manager = None  # Lazy-loaded VFS manager
        self._bucket_index_cache = None  # Cache for bucket index to minimize disk I/O
        self._backend_index_cache = None  # Cache for backend index
        self._config_cache = None  # Cache for config to minimize file reads
        
    def ensure_heavy_imports(self):
        """Ensure heavy imports are loaded when needed."""
        if self.jit_manager is None:
            self.jit_manager = initialize_heavy_imports()
        return self.jit_manager is not None
    
    def get_ipfs_api(self):
        """Get centralized IPFS API instance (lazy loaded)."""
        if self._ipfs_api is None:
            try:
                from .high_level_api import IPFSSimpleAPI
                self._ipfs_api = IPFSSimpleAPI()
                # The API will automatically initialize indices as needed
            except ImportError as e:
                print(f"❌ Failed to import IPFSSimpleAPI: {e}")
                return None
            except Exception as e:
                print(f"❌ Failed to initialize IPFSSimpleAPI: {e}")
                return None
        return self._ipfs_api
    
    def get_vfs_manager(self):
        """Get VFS manager instance (lazy loaded).""" 
        if self._vfs_manager is None:
            try:
                # Use the centralized VFS Manager from ipfs_kit_py
                from .vfs_manager import get_global_vfs_manager
                self._vfs_manager = get_global_vfs_manager()
            except ImportError as e:
                print(f"❌ Failed to import VFS components: {e}")
                return None
            except Exception as e:
                print(f"❌ Failed to initialize VFS manager: {e}")
                return None
        return self._vfs_manager
    
    def get_bucket_index(self, force_refresh=False):
        """Get comprehensive bucket index from both SQLite and file system sources."""
        if self._bucket_index_cache is None or force_refresh:
            try:
                import sqlite3
                import pandas as pd
                from pathlib import Path
                
                # Initialize bucket index storage paths
                index_dir = Path.home() / '.ipfs_kit' / 'bucket_index'
                index_dir.mkdir(parents=True, exist_ok=True)
                
                bucket_db_path = index_dir / 'bucket_analytics.db'
                bucket_parquet_path = index_dir / 'bucket_registry.parquet'
                
                buckets = []
                
                # Method 1: Try SQLite database first
                if bucket_db_path.exists():
                    try:
                        conn = sqlite3.connect(str(bucket_db_path))
                        cursor = conn.cursor()
                        
                        cursor.execute("""
                            SELECT name, type, backend, size_bytes, last_updated, metadata 
                            FROM buckets 
                            ORDER BY last_updated DESC
                        """)
                        
                        for row in cursor.fetchall():
                            bucket = {
                                'name': row[0],
                                'type': row[1], 
                                'backend': row[2],
                                'size_bytes': row[3],
                                'last_updated': row[4],
                                'metadata': json.loads(row[5] or '{}'),
                                'source': 'sqlite'
                            }
                            buckets.append(bucket)
                        
                        conn.close()
                    except Exception as e:
                        print(f"⚠️  SQLite bucket index failed: {e}")
                
                # Method 2: Scan actual bucket files and configs for comprehensive index
                buckets_dir = Path.home() / '.ipfs_kit' / 'buckets'
                configs_dir = Path.home() / '.ipfs_kit' / 'bucket_configs'
                
                if buckets_dir.exists():
                    for bucket_file in buckets_dir.glob('*.parquet'):
                        bucket_name = bucket_file.stem
                        
                        # Skip if already found in SQLite
                        if any(b['name'] == bucket_name for b in buckets):
                            continue
                        
                        try:
                            # Read bucket VFS index
                            df = pd.read_parquet(bucket_file)
                            
                            # Get bucket metadata from first row or default values
                            if len(df) > 0:
                                first_row = df.iloc[0]
                                bucket_type = first_row.get('bucket_type', 'general')
                                created_at = first_row.get('created_at', 'unknown')
                                metadata = json.loads(first_row.get('metadata', '{}'))
                            else:
                                bucket_type = 'general'
                                created_at = 'unknown'
                                metadata = {}
                            
                            # Calculate statistics
                            total_files = max(0, len(df) - 1)  # Subtract empty initial entry
                            total_size = df['file_size'].sum() if 'file_size' in df.columns else 0
                            
                            # Try to load YAML config for additional metadata
                            config_file = configs_dir / f"{bucket_name}.yaml"
                            backend_bindings = []
                            yaml_metadata = {}
                            
                            if config_file.exists():
                                try:
                                    import yaml
                                    with open(config_file, 'r') as f:
                                        config = yaml.safe_load(f)
                                        backend_bindings = config.get('backend_bindings', [])
                                        yaml_metadata = {
                                            'description': config.get('description'),
                                            'replication': config.get('replication', {}),
                                            'cache': config.get('cache', {}),
                                            'performance': config.get('performance', {}),
                                            'disaster_recovery': config.get('disaster_recovery', {}),
                                            'daemon_managed': config.get('daemon', {}).get('managed', False)
                                        }
                                except Exception:
                                    pass  # Continue without YAML config
                            
                            bucket = {
                                'name': bucket_name,
                                'type': bucket_type,
                                'backend': ', '.join(backend_bindings) if backend_bindings else 'local',
                                'backend_bindings': backend_bindings,
                                'size_bytes': int(total_size),
                                'file_count': total_files,
                                'last_updated': created_at,
                                'vfs_index_path': str(bucket_file),
                                'config_path': str(config_file) if config_file.exists() else None,
                                'metadata': {**metadata, **yaml_metadata},
                                'source': 'filesystem'
                            }
                            buckets.append(bucket)
                            
                        except Exception as e:
                            print(f"⚠️  Failed to read bucket {bucket_name}: {e}")
                            continue
                
                # Sort by last updated
                buckets.sort(key=lambda x: x.get('last_updated', ''), reverse=True)
                
                # Update comprehensive parquet index
                try:
                    if buckets:
                        # Convert to DataFrame and save
                        bucket_df = pd.DataFrame(buckets)
                        bucket_df.to_parquet(bucket_parquet_path, index=False)
                        
                        # Automatically generate CAR file from the updated registry
                        try:
                            car_result = self.generate_bucket_registry_car()
                            if car_result['success']:
                                print(f"📦 Generated registry CAR: {car_result['cid']}")
                        except Exception as e:
                            # Don't fail the whole operation if CAR generation fails
                            print(f"⚠️  Failed to generate registry CAR: {e}")
                            
                except Exception as e:
                    print(f"⚠️  Failed to save bucket index: {e}")
                
                self._bucket_index_cache = buckets
                    
            except Exception as e:
                print(f"⚠️  Failed to build bucket index: {e}")
                self._bucket_index_cache = []
                
        return self._bucket_index_cache

    def generate_bucket_registry_car(self):
        """Generate a CAR file from bucket_registry.parquet and store it with CID-based filename."""
        try:
            from pathlib import Path
            import json
            import pandas as pd
            from .ipfs_multiformats import ipfs_multiformats_py
            
            # Define paths
            bucket_index_dir = Path.home() / '.ipfs_kit' / 'bucket_index'
            bucket_index_dir.mkdir(parents=True, exist_ok=True)
            
            bucket_parquet_path = bucket_index_dir / 'bucket_registry.parquet'
            pinset_content_dir = Path.home() / '.ipfs_kit' / 'bucket_index' / 'pinset_content'
            pinset_content_dir.mkdir(parents=True, exist_ok=True)
            
            if not bucket_parquet_path.exists():
                print("⚠️  bucket_registry.parquet not found, generating bucket index first...")
                self.get_bucket_index(force_refresh=True)
                if not bucket_parquet_path.exists():
                    return {
                        'success': False,
                        'error': 'Failed to generate bucket registry'
                    }
            
            # Read the bucket registry parquet file
            bucket_df = pd.read_parquet(bucket_parquet_path)
            
            # Convert DataFrame to dictionary format for CAR content, handling numpy types
            def convert_value(value):
                """Convert numpy and pandas types to JSON-serializable types"""
                import numpy as np
                
                # Handle None first
                if value is None:
                    return None
                    
                # Handle numpy arrays
                if isinstance(value, np.ndarray):
                    return value.tolist()  # Convert numpy arrays to lists
                    
                # Handle numpy scalars
                if isinstance(value, (np.integer, np.floating)):
                    return value.item()  # Convert numpy scalars
                    
                # Handle pandas NA values (check for scalar NAs)
                try:
                    if pd.isna(value) and not isinstance(value, (np.ndarray, list, dict)):
                        return None
                except (TypeError, ValueError):
                    # pd.isna failed, continue with other checks
                    pass
                    
                # Handle dictionaries recursively
                if isinstance(value, dict):
                    return {k: convert_value(v) for k, v in value.items()}
                    
                # Handle lists
                if isinstance(value, list):
                    return [convert_value(item) for item in item]
                    
                return value
            
            bucket_records = []
            for _, row in bucket_df.iterrows():
                # Convert each row to dict with proper type conversion
                record = {}
                for col, value in row.items():
                    record[col] = convert_value(value)
                bucket_records.append(record)
            
            # Convert DataFrame to dictionary format for CAR content
            bucket_registry_data = {
                'version': '1.0',
                'type': 'bucket_registry',
                'generated_at': pd.Timestamp.now().isoformat(),
                'total_buckets': len(bucket_df),
                'buckets': bucket_records
            }
            
            # Convert to canonical JSON for CID generation
            registry_json = json.dumps(bucket_registry_data, sort_keys=True, separators=(',', ':'))
            registry_bytes = registry_json.encode('utf-8')
            
            # Generate CID using ipfs_multiformats
            multiformats = ipfs_multiformats_py()
            registry_cid = multiformats.get_cid(registry_bytes)
            
            # Create CAR structure (simplified JSON-based CAR)
            car_structure = {
                'header': {
                    'version': 1,
                    'roots': [registry_cid],
                    'format': 'bucket_registry_car'
                },
                'blocks': [
                    {
                        'cid': registry_cid,
                        'data': registry_bytes.hex()  # Hex-encoded for JSON compatibility
                    }
                ]
            }
            
            # Save CAR file with CID as filename
            car_filename = f"{registry_cid}.car"
            car_path = pinset_content_dir / car_filename
            
            with open(car_path, 'w') as f:
                json.dump(car_structure, f, indent=2)
            
            return {
                'success': True,
                'cid': registry_cid,
                'path': str(car_path)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_backend_index(self, force_refresh=False):
        """Get comprehensive backend index from config files and live status checks."""
        if self._backend_index_cache is None or force_refresh:
            try:
                import yaml
                from pathlib import Path
                
                # Initialize backend index storage paths
                index_dir = Path.home() / '.ipfs_kit' / 'backend_index'
                index_dir.mkdir(parents=True, exist_ok=True)
                
                backend_parquet_path = index_dir / 'backend_registry.parquet'
                
                backends = []
                configs_dir = Path.home() / '.ipfs_kit' / 'config' / 'backends'
                
                if configs_dir.exists():
                    for config_file in configs_dir.glob('*.yaml'):
                        backend_name = config_file.stem
                        
                        try:
                            with open(config_file, 'r') as f:
                                config = yaml.safe_load(f)
                                
                                # Basic backend info
                                backend_type = config.get('type', 'unknown')
                                enabled = config.get('enabled', True)
                                
                                # Get live status (if possible)
                                status = 'unknown'
                                try:
                                    # Placeholder for live status check
                                    # In a real implementation, this would ping the backend
                                    if enabled:
                                        status = 'online' 
                                    else:
                                        status = 'offline'
                                except Exception:
                                    status = 'error'
                                
                                # Get storage stats (placeholders)
                                storage_used = 'N/A'
                                storage_quota = config.get('storage_quota', 'N/A')
                                
                                backend = {
                                    'name': backend_name,
                                    'type': backend_type,
                                    'enabled': enabled,
                                    'status': status,
                                    'storage_used': storage_used,
                                    'storage_quota': storage_quota,
                                    'config_path': str(config_file)
                                }
                                backends.append(backend)
                                
                        except Exception as e:
                            print(f"⚠️  Failed to read backend config {backend_name}: {e}")
                            continue
                
                # Sort by name
                backends.sort(key=lambda x: x['name'])
                
                # Update comprehensive parquet index
                try:
                    if backends:
                        backend_df = pd.DataFrame(backends)
                        backend_df.to_parquet(backend_parquet_path, index=False)
                except Exception as e:
                    print(f"⚠️  Failed to save backend index: {e}")
                
                self._backend_index_cache = backends
                
            except Exception as e:
                print(f"⚠️  Failed to build backend index: {e}")
                self._backend_index_cache = []
                
        return self._backend_index_cache

    def get_config(self, force_refresh=False):
        """Get merged configuration from all YAML files."""
        if self._config_cache is None or force_refresh:
            try:
                import yaml
                from pathlib import Path
                
                config_dir = Path.home() / '.ipfs_kit' / 'config'
                merged_config = {}
                
                if config_dir.exists():
                    for config_file in config_dir.glob('**/*.yaml'):
                        try:
                            with open(config_file, 'r') as f:
                                config_data = yaml.safe_load(f)
                                if config_data:
                                    # Simple merge, could be improved with deep merge
                                    merged_config.update(config_data)
                        except Exception as e:
                            print(f"⚠️  Failed to read config {config_file.name}: {e}")
                            continue
                
                self._config_cache = merged_config
                
            except Exception as e:
                print(f"⚠️  Failed to load configuration: {e}")
                self._config_cache = {}
                
        return self._config_cache

    async def handle_mcp_command(self, args):
        """Handle MCP server and dashboard commands."""
        mcp_action = args.mcp_action

        if mcp_action == 'start':
            print("🚀 Starting unified MCP server + dashboard...")
            
            # Import the unified dashboard
            try:
                from .unified_mcp_dashboard import UnifiedMCPDashboard
            except ImportError:
                try:
                    # Fallback import path
                    import sys
                    import os
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    sys.path.insert(0, current_dir)
                    from unified_mcp_dashboard import UnifiedMCPDashboard
                except ImportError as e:
                    print(f"❌ Failed to import UnifiedMCPDashboard: {e}")
                    return 1
            
            # Create configuration for the unified dashboard
            config = {
                'host': args.host,
                'port': args.port,
                'data_dir': '~/.ipfs_kit',
                'debug': getattr(args, 'debug', False),
                'update_interval': 3
            }
            
            # Create and start the unified dashboard
            dashboard = UnifiedMCPDashboard(config)
            print(f"🚀 Starting unified MCP server + dashboard on http://{args.host}:{args.port}")
            print(f"📊 Dashboard available at: http://{args.host}:{args.port}")
            print(f"🔧 MCP endpoints available at: http://{args.host}:{args.port}/mcp/*")
            
            try:
                await dashboard.start()
            except KeyboardInterrupt:
                print("\n🛑 Shutting down MCP server and dashboard...")
                return 0
            except Exception as e:
                print(f"❌ Failed to start unified MCP dashboard: {e}")
                return 1

        elif mcp_action == 'stop':
            print("🛑 Stopping unified MCP server and dashboard...")
            # For now, we'll provide instructions since the server runs in blocking mode
            print("💡 To stop the server, use Ctrl+C in the terminal where it's running")
            print("   Or kill the process using: pkill -f 'unified_mcp_dashboard'")

        elif mcp_action == 'status':
            print("📊 Checking unified MCP server and dashboard status...")
            
            # Check if server is running by trying to connect
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"http://{args.host}:{args.port}/health", timeout=5.0)
                    if response.status_code == 200:
                        data = response.json()
                        print(f"✅ Unified MCP server and dashboard running on http://{args.host}:{args.port}")
                        print(f"   Status: {data.get('status', 'unknown')}")
                        print(f"   Version: {data.get('version', 'unknown')}")
                        print(f"   Unified mode: {data.get('unified_mode', False)}")
                        print(f"   Timestamp: {data.get('timestamp', 'unknown')}")
                    else:
                        print(f"❌ Server returned status code: {response.status_code}")
            except ImportError:
                print("❌ httpx not available for status check")
                print("   Install with: pip install httpx")
            except Exception as e:
                print(f"❌ Unified MCP server and dashboard not running on http://{args.host}:{args.port}")
                print(f"   Error: {e}")

        elif mcp_action == 'restart':
            print("🔄 Restarting unified MCP server and dashboard...")
            print("💡 To restart the server:")
            print("   1. Stop with Ctrl+C in the terminal where it's running")
            print("   2. Start again with: ipfs-kit mcp start")

        elif mcp_action == 'role':
            print(f"🔧 Setting MCP role to: {args.role}")
            print("💡 Role configuration will be implemented in future versions")

        elif mcp_action == 'cli':
            print(f"💻 Executing MCP CLI command: {' '.join(args.mcp_args) if hasattr(args, 'mcp_args') else 'No args'}")
            print("💡 MCP CLI bridge will be implemented in future versions")

        return 0
    async def handle_daemon_command(self, args):
        """Handle daemon management commands."""
        daemon_action = args.daemon_action
        
        # Lazy import daemon manager
        EnhancedDaemonManager = _lazy_import_daemon_manager()
        if not EnhancedDaemonManager:
            print("❌ Daemon manager not available. Please check your installation.")
            return 1
        
        daemon_manager = EnhancedDaemonManager()
        
        if daemon_action == 'start':
            print("🚀 Starting daemon...")
            try:
                daemon_manager.start_daemon(
                    detach=args.detach,
                    config_path=args.config,
                    port=args.daemon_port,
                    role=args.role,
                    master_address=args.master_address,
                    cluster_secret=args.cluster_secret
                )
            except Exception as e:
                print(f"❌ Failed to start daemon: {e}")
                return 1
        
        elif daemon_action == 'stop':
            print("🛑 Stopping daemon...")
            try:
                daemon_manager.stop_daemon()
            except Exception as e:
                print(f"❌ Failed to stop daemon: {e}")
                return 1
        
        elif daemon_action == 'status':
            print("📊 Checking daemon status...")
            try:
                status = daemon_manager.check_daemon_status()
                
                # Display status in a table
                console = Console()
                table = Table(title="Daemon Status")
                table.add_column("Service", style="cyan")
                table.add_column("Status", style="magenta")
                
                for service, is_running in status.items():
                    table.add_row(service, "✅ Running" if is_running else "❌ Stopped")
                
                console.print(table)
                
            except Exception as e:
                print(f"❌ Failed to get daemon status: {e}")
                return 1
        
        elif daemon_action == 'restart':
            print("🔄 Restarting daemon...")
            try:
                daemon_manager.restart_daemon()
            except Exception as e:
                print(f"❌ Failed to restart daemon: {e}")
                return 1
        
        # Handle individual service management
        elif args.daemon_action in ['ipfs', 'lotus', 'cluster', 'lassie']:
            service_name = args.daemon_action
            service_action = getattr(args, f"{service_name}_action")
            
            if service_action:
                print(f"🔧 Managing {service_name} service: {service_action}...")
                try:
                    # This assumes the daemon manager has methods like start_service, stop_service, etc.
                    method = getattr(daemon_manager, f"{service_action}_service")
                    method(service_name)
                except Exception as e:
                    print(f"❌ Failed to manage {service_name} service: {e}")
                    return 1
        
        # Handle intelligent daemon commands
        elif args.daemon_action == 'intelligent':
            await self.handle_intelligent_daemon_command(args)
        
        return 0

    async def handle_intelligent_daemon_command(self, args):
        """Handle intelligent daemon commands."""
        intelligent_action = args.intelligent_action
        
        # Lazy import daemon manager
        EnhancedDaemonManager = _lazy_import_daemon_manager()
        if not EnhancedDaemonManager:
            print("❌ Intelligent daemon manager not available.")
            return 1
        
        daemon_manager = EnhancedDaemonManager()
        
        if intelligent_action == 'start':
            print("🚀 Starting intelligent daemon...")
            try:
                daemon_manager.start_intelligent_daemon(
                    detach=args.detach,
                    verbose=args.verbose
                )
            except Exception as e:
                print(f"❌ Failed to start intelligent daemon: {e}")
                return 1
        
        elif intelligent_action == 'stop':
            print("🛑 Stopping intelligent daemon...")
            try:
                daemon_manager.stop_intelligent_daemon()
            except Exception as e:
                print(f"❌ Failed to stop intelligent daemon: {e}")
                return 1
        
        elif intelligent_action == 'status':
            print("📊 Getting intelligent daemon status...")
            try:
                status = daemon_manager.get_intelligent_daemon_status(
                    detailed=args.detailed
                )
                if args.json_output:
                    print(json.dumps(status, indent=2))
                else:
                    # Display status in a table
                    console = Console()
                    table = Table(title="Intelligent Daemon Status")
                    table.add_column("Metric", style="cyan")
                    table.add_column("Value", style="magenta")
                    
                    for key, value in status.items():
                        table.add_row(key, str(value))
                    
                    console.print(table)
            except Exception as e:
                print(f"❌ Failed to get status: {e}")
                return 1
        
        elif intelligent_action == 'insights':
            print("🧠 Getting operational insights...")
            try:
                insights = daemon_manager.get_operational_insights()
                if args.json_output:
                    print(json.dumps(insights, indent=2))
                else:
                    # Display insights in a formatted way
                    console = Console()
                    console.print(insights)
            except Exception as e:
                print(f"❌ Failed to get insights: {e}")
                return 1
        
        elif intelligent_action == 'health':
            print("❤️ Checking system health...")
            try:
                health = daemon_manager.check_system_health()
                # Display health in a formatted way
                console = Console()
                console.print(health)
            except Exception as e:
                print(f"❌ Failed to check health: {e}")
                return 1
        
        elif intelligent_action == 'sync':
            print("🔄 Forcing backend synchronization...")
            try:
                daemon_manager.force_backend_sync(backend=args.backend)
            except Exception as e:
                print(f"❌ Failed to force sync: {e}")
                return 1
        
        return 0

    async def handle_pin_command(self, args):
        """Handle pin management commands."""
        pin_action = args.pin_action
        
        # Use the high-level API for pin management
        ipfs_api = self.get_ipfs_api()
        if not ipfs_api:
            return 1
        
        if pin_action == 'add':
            print(f"📌 Adding pin for: {args.cid_or_file}")
            try:
                result = ipfs_api.pin_add(
                    cid_or_path=args.cid_or_file,
                    name=args.name,
                    recursive=args.recursive
                )
                print(f"✅ Pin added successfully: {result}")
            except Exception as e:
                print(f"❌ Failed to add pin: {e}")
                return 1
        
        elif pin_action == 'remove':
            print(f"🗑️ Removing pin: {args.cid}")
            try:
                result = ipfs_api.pin_rm(args.cid)
                print(f"✅ Pin removed successfully: {result}")
            except Exception as e:
                print(f"❌ Failed to remove pin: {e}")
                return 1
        
        elif pin_action == 'list':
            print("📋 Listing pins...")
            try:
                pins = ipfs_api.pin_ls(limit=args.limit, metadata=args.metadata)
                
                # Display pins in a table
                console = Console()
                table = Table(title="Pinned Content")
                table.add_column("CID", style="cyan")
                table.add_column("Name", style="magenta")
                if args.metadata:
                    table.add_column("Metadata", style="green")
                
                for pin in pins:
                    if args.metadata:
                        table.add_row(pin['cid'], pin.get('name', ''), json.dumps(pin.get('metadata', {}), indent=2))
                    else:
                        table.add_row(pin['cid'], pin.get('name', ''))
                
                console.print(table)
                
            except Exception as e:
                print(f"❌ Failed to list pins: {e}")
                return 1
        
        elif pin_action == 'pending':
            print("⏳ Listing pending pins...")
            # This requires a WAL (Write-Ahead Log) implementation, which is not part of the high-level API yet.
            print("Pending pin listing is not yet implemented.")
        
        elif pin_action == 'status':
            print(f"📊 Checking pin status for: {args.operation_id}")
            # This also requires a WAL or similar tracking mechanism.
            print("Pin status checking is not yet implemented.")
        
        elif pin_action == 'get':
            print(f"📥 Downloading pin: {args.cid}")
            try:
                ipfs_api.pin_get(args.cid, output_path=args.output, recursive=args.recursive)
                print("✅ Content downloaded successfully.")
            except Exception as e:
                print(f"❌ Failed to download pin: {e}")
                return 1
        
        elif pin_action == 'cat':
            print(f"📜 Streaming pin content: {args.cid}")
            try:
                for chunk in ipfs_api.pin_cat(args.cid, limit=args.limit):
                    sys.stdout.buffer.write(chunk)
            except Exception as e:
                print(f"❌ Failed to stream pin content: {e}")
                return 1
        
        elif pin_action == 'init':
            print("✨ Initializing pin metadata index...")
            # This is a placeholder for initializing the pin metadata index
            print("Pin metadata index initialization is not yet implemented.")
        
        elif pin_action == 'export-metadata':
            print("📦 Exporting pin metadata...")
            # This requires a more complex implementation to iterate through pins and export them.
            print("Pin metadata export is not yet implemented.\n")
        
        return 0

    async def handle_backend_command(self, args):
        """Handle backend management commands."""
        backend_action = args.backend_action
        
        # Use the high-level API for backend management
        ipfs_api = self.get_ipfs_api()
        if not ipfs_api:
            return 1
        
        if backend_action == 'list':
            print("📋 Listing backends...")
            try:
                backends = ipfs_api.backend_ls(configured=args.configured)
                
                # Display backends in a table
                console = Console()
                table = Table(title="Available Backends")
                table.add_column("Name", style="cyan")
                table.add_column("Type", style="magenta")
                table.add_column("Configured", style="green")
                
                for backend in backends:
                    table.add_row(backend['name'], backend['type'], "✅" if backend['configured'] else "❌")
                
                console.print(table)
                
            except Exception as e:
                print(f"❌ Failed to list backends: {e}")
                return 1
        
        elif backend_action == 'create':
            print(f"➕ Creating backend: {args.name}")
            try:
                config = {
                    'type': args.type,
                    'endpoint': args.endpoint,
                    'access_key': args.access_key,
                    'secret_key': args.secret_key,
                    'token': args.token,
                    'bucket': args.bucket,
                    'region': args.region
                }
                # Filter out None values
                config = {k: v for k, v in config.items() if v is not None}
                
                ipfs_api.backend_create(args.name, config)
                print(f"✅ Backend '{args.name}' created successfully.")
            except Exception as e:
                print(f"❌ Failed to create backend: {e}")
                return 1
        
        elif backend_action == 'show':
            print(f"ℹ️ Showing backend config: {args.name}")
            try:
                config = ipfs_api.backend_show(args.name)
                print(json.dumps(config, indent=2))
            except Exception as e:
                print(f"❌ Failed to show backend: {e}")
                return 1
        
        elif backend_action == 'update':
            print(f"🔄 Updating backend: {args.name}")
            try:
                updates = {
                    'enabled': args.enabled,
                    'endpoint': args.endpoint,
                    'token': args.token,
                    'bucket': args.bucket,
                    'region': args.region
                }
                # Filter out None values
                updates = {k: v for k, v in updates.items() if v is not None}
                
                ipfs_api.backend_update(args.name, updates)
                print(f"✅ Backend '{args.name}' updated successfully.")
            except Exception as e:
                print(f"❌ Failed to update backend: {e}")
                return 1
        
        elif backend_action == 'remove':
            print(f"🗑️ Removing backend: {args.name}")
            try:
                ipfs_api.backend_rm(args.name, force=args.force)
                print(f"✅ Backend '{args.name}' removed successfully.")
            except Exception as e:
                print(f"❌ Failed to remove backend: {e}")
                return 1
        
        elif backend_action == 'test':
            print("🧪 Testing backend connections...")
            try:
                results = ipfs_api.backend_test(backend=args.backend)
                
                # Display results in a table
                console = Console()
                table = Table(title="Backend Connection Test Results")
                table.add_column("Backend", style="cyan")
                table.add_column("Status", style="magenta")
                table.add_column("Details", style="green")
                
                for result in results:
                    table.add_row(result['backend'], "✅ OK" if result['success'] else "❌ Failed", result.get('error', ''))
                
                console.print(table)
                
            except Exception as e:
                print(f"❌ Failed to test backends: {e}")
                return 1
        
        elif backend_action == 'migrate-pin-mappings':
            print("🔄 Migrating pin mappings...")
            # This is a complex operation that requires careful implementation.
            print("Pin mapping migration is not yet implemented.")
        
        # Handle specific backend commands (huggingface, github, etc.)
        elif args.backend_action in ['huggingface', 'github', 's3', 'storacha', 'ipfs', 'gdrive', 'lotus', 'synapse', 'sshfs', 'ftp', 'ipfs-cluster', 'ipfs-cluster-follow', 'parquet', 'arrow']:
            # These commands are highly specific and would require dedicated handlers.
            print(f"Backend command '{args.backend_action}' is not fully implemented in this CLI version.")
        
        return 0

    async def handle_health_command(self, args):
        """Handle health monitoring commands."""
        health_action = args.health_action
        
        # Use the high-level API for health checks
        ipfs_api = self.get_ipfs_api()
        if not ipfs_api:
            return 1
        
        if health_action == 'check':
            print(f"❤️  Running health check for: {args.backend or 'all'}")
            try:
                results = ipfs_api.health_check(backend=args.backend)
                
                # Display results in a table
                console = Console()
                table = Table(title="Health Check Results")
                table.add_column("Component", style="cyan")
                table.add_column("Status", style="magenta")
                table.add_column("Details", style="green")
                
                for result in results:
                    table.add_row(result['component'], "✅ Healthy" if result['healthy'] else "❌ Unhealthy", result.get('details', ''))
                
                console.print(table)
                
            except Exception as e:
                print(f"❌ Failed to run health check: {e}")
                return 1
        
        elif health_action == 'status':
            print(f"📊 Showing health status for: {args.backend or 'all'}")
            try:
                status = ipfs_api.health_status(backend=args.backend)
                print(json.dumps(status, indent=2))
            except Exception as e:
                print(f"❌ Failed to get health status: {e}")
                return 1
        
        return 0

    async def handle_config_command(self, args):
        """Handle configuration management commands."""
        config_action = args.config_action
        
        # Use the high-level API for config management
        ipfs_api = self.get_ipfs_api()
        if not ipfs_api:
            return 1
        
        if config_action == 'show':
            print("📄 Showing configuration...")
            try:
                config = ipfs_api.config_show(backend=args.backend)
                print(json.dumps(config, indent=2))
            except Exception as e:
                print(f"❌ Failed to show configuration: {e}")
                return 1
        
        elif config_action == 'validate':
            print("✔️ Validating configuration...")
            try:
                results = ipfs_api.config_validate(backend=args.backend)
                
                # Display results in a table
                console = Console()
                table = Table(title="Configuration Validation Results")
                table.add_column("File", style="cyan")
                table.add_column("Status", style="magenta")
                table.add_column("Details", style="green")
                
                for result in results:
                    table.add_row(result['file'], "✅ Valid" if result['valid'] else "❌ Invalid", result.get('error', ''))
                
                console.print(table)
                
            except Exception as e:
                print(f"❌ Failed to validate configuration: {e}")
                return 1
        
        elif config_action == 'set':
            print(f"🔧 Setting config: {args.key} = {args.value}")
            try:
                ipfs_api.config_set(args.key, args.value)
                print("✅ Configuration updated successfully.")
            except Exception as e:
                print(f"❌ Failed to set configuration: {e}")
                return 1
        
        elif config_action == 'init':
            print("✨ Initializing configuration...")
            # This would be an interactive process.
            print("Interactive configuration setup is not yet implemented.")
        
        elif config_action == 'backup':
            print("💾 Backing up configuration...")
            # This would create a backup of the config files.n            print("Configuration backup is not yet implemented.")
        
        elif config_action == 'restore':
            print("🔄 Restoring configuration...")
            # This would restore from a backup.
            print("Configuration restore is not yet implemented.")
        
        elif config_action == 'reset':
            print("🗑️ Resetting configuration...")
            # This would reset the configuration to defaults.
            print("Configuration reset is not yet implemented.\n")
        
        return 0

    async def handle_bucket_command(self, args):
        """Handle bucket management commands."""
        bucket_action = args.bucket_action
        
        # Use the VFS manager for bucket operations
        vfs_manager = self.get_vfs_manager()
        if not vfs_manager:
            return 1
        
        if bucket_action == 'list':
            print("🪣 Listing buckets...")
            try:
                buckets = vfs_manager.list_buckets()
                
                # Display buckets in a table
                console = Console()
                table = Table(title="Available Buckets")
                table.add_column("Name", style="cyan")
                table.add_column("Type", style="magenta")
                table.add_column("Size", style="green")
                table.add_column("Files", style="yellow")
                
                for bucket in buckets:
                    table.add_row(
                        bucket['name'], 
                        bucket.get('type', 'N/A'), 
                        str(bucket.get('size_bytes', 'N/A')), 
                        str(bucket.get('file_count', 'N/A'))
                    )
                
                console.print(table)
                
            except Exception as e:
                print(f"❌ Failed to list buckets: {e}")
                return 1
        
        elif bucket_action == 'create':
            print(f"➕ Creating bucket: {args.bucket_name}")
            try:
                vfs_manager.create_bucket(args.bucket_name, metadata=json.loads(args.metadata or '{}'))
                print(f"✅ Bucket '{args.bucket_name}' created successfully.")
            except Exception as e:
                print(f"❌ Failed to create bucket: {e}")
                return 1
        
        elif bucket_action == 'rm':
            print(f"🗑️ Removing bucket: {args.bucket_name}")
            try:
                vfs_manager.remove_bucket(args.bucket_name, force=args.force)
                print(f"✅ Bucket '{args.bucket_name}' removed successfully.")
            except Exception as e:
                print(f"❌ Failed to remove bucket: {e}")
                return 1
        
        elif bucket_action == 'add':
            print(f"➕ Adding file to bucket '{args.bucket}': {args.source}")
            try:
                vfs_manager.add_file_to_bucket(args.bucket, args.source, args.path, metadata=json.loads(args.metadata or '{}'))
                print("✅ File added successfully.")
            except Exception as e:
                print(f"❌ Failed to add file: {e}")
                return 1
        
        elif bucket_action == 'get':
            print(f"📥 Getting file from bucket '{args.bucket}': {args.path}")
            try:
                vfs_manager.get_file_from_bucket(args.bucket, args.path, args.output)
                print("✅ File retrieved successfully.")
            except Exception as e:
                print(f"❌ Failed to get file: {e}")
                return 1
        
        # Other bucket commands would be handled here...
        else:
            print(f"Bucket command '{bucket_action}' is not fully implemented.")
        
        return 0

    async def run(self, args):
        """Main command dispatch method for FastCLI."""
        try:
            # Determine which command was called based on the subparser
            if hasattr(args, 'mcp_action') and args.mcp_action:
                return await self.handle_mcp_command(args)
            elif hasattr(args, 'daemon_action') and args.daemon_action:
                return await self.handle_daemon_command(args)
            elif hasattr(args, 'bucket_action') and args.bucket_action:
                return await self.handle_bucket_command(args)
            else:
                print("❌ No valid command specified. Use --help for usage information.")
                return 1
                
        except Exception as e:
            print(f"❌ Error executing command: {e}")
            return 1

async def main():
    """Asynchronous entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    cli = FastCLI()
    exit_code = await cli.run(args)
    return exit_code

def sync_main():
    """Synchronous entry point for the CLI with fallback."""
    try:
        # Try the normal async main
        return asyncio.run(main())
    except Exception as e:
        # Check if it's a multicodec compatibility issue
        error_str = str(e)
        if any(keyword in error_str for keyword in ['multicodec', 'deprecated', 'Invalid multicodec status']):
            print(f"⚠️  Using fallback CLI due to compatibility issue: {error_str}")
            print("📋 Loading simplified CLI...")
            
            # Use a simple CLI as fallback
            try:
                import subprocess
                import sys
                from pathlib import Path
                
                # Find the simple_cli.py file
                current_dir = Path(__file__).parent.parent
                simple_cli_path = current_dir / "simple_cli.py"
                
                if simple_cli_path.exists():
                    # Run the simple CLI with the same arguments
                    cmd = [sys.executable, str(simple_cli_path)] + sys.argv[1:]
                    result = subprocess.run(cmd, capture_output=False)
                    return result.returncode
                else:
                    print("❌ Simple CLI fallback not found")
                    return 1
                    
            except Exception as fallback_error:
                print(f"❌ Fallback CLI also failed: {fallback_error}")
                return 1
        else:
            # Re-raise other errors
            raise

if __name__ == "__main__":
    # This allows the script to be run directly
    # Note: The recommended entry point is via `ipfs-kit` script in pyproject.toml
    sys.exit(sync_main())
