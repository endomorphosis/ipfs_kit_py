#!/usr/bin/env python3
"""
Enhanced Configuration Manager for IPFS-Kit

Manages YAML configuration files in ~/.ipfs_kit/ with interactive setup
and comprehensive backend configuration support.
"""

import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import getpass
import sys
from datetime import datetime


class ConfigManager:
    """Enhanced configuration manager with YAML storage and interactive setup."""
    
    def __init__(self):
        self.config_dir = Path.home() / '.ipfs_kit'
        self.config_dir.mkdir(exist_ok=True)
        
        # Configuration file mappings
        self.config_files = {
            'daemon': 'daemon_config.yaml',
            's3': 's3_config.yaml',
            'lotus': 'lotus_config.yaml',
            'storacha': 'storacha_config.yaml',
            'gdrive': 'gdrive_config.yaml',
            'synapse': 'synapse_config.yaml',
            'huggingface': 'huggingface_config.yaml',
            'github': 'github_config.yaml',
            'ipfs_cluster': 'ipfs_cluster_config.yaml',
            'cluster_follow': 'cluster_follow_config.yaml',
            'parquet': 'parquet_config.yaml',
            'arrow': 'arrow_config.yaml',
            'package': 'package_config.yaml',
            'wal': 'wal_config.yaml',
            'fs_journal': 'fs_journal_config.yaml'
        }
        
        # Default configurations
        self.defaults = {
            'daemon': {
                'port': 9999,
                'auto_start': True,
                'role': 'local',
                'max_workers': 4,
                'log_level': 'INFO',
                # Cache settings
                'cache': {
                    'enabled': True,
                    'type': 'lru',  # lru, lfu, ttl, redis
                    'max_size': '1GB',
                    'ttl': 3600,  # seconds
                    'persistence': True,
                    'storage_path': str(self.config_dir / 'cache'),
                    'compression': True,
                    'compression_type': 'gzip',  # gzip, lz4, zstd
                    'eviction_policy': 'lru',
                    'stats_enabled': True,
                    'cleanup_interval': 300  # seconds
                },
                # Semantic cache settings
                'semantic_cache': {
                    'enabled': True,
                    'embedding_model': 'sentence-transformers/all-MiniLM-L6-v2',
                    'similarity_threshold': 0.85,
                    'cache_size': 10000,
                    'vector_dimension': 384,
                    'index_type': 'faiss',  # faiss, annoy, hnswlib
                    'storage_path': str(self.config_dir / 'semantic_cache'),
                    'rebuild_interval': 86400,  # 24 hours
                    'query_expansion': True,
                    'semantic_search': True,
                    'clustering_enabled': False,
                    'cluster_count': 100
                },
                # Replication policy settings
                'replication': {
                    'enabled': True,
                    'strategy': 'eager',  # eager, lazy, hybrid
                    'min_replicas': 2,
                    'max_replicas': 5,
                    'target_replicas': 3,
                    'geographic_distribution': True,
                    'health_check_interval': 300,  # seconds
                    'failure_timeout': 600,  # seconds
                    'auto_repair': True,
                    'repair_threshold': 0.8,
                    'backup_schedule': 'daily',  # daily, weekly, manual
                    'encryption': True,
                    'compression': True,
                    'dedupe_enabled': True,
                    'consistency_level': 'eventual'  # strong, eventual, session
                },
                # Vector database settings
                'vector_db': {
                    'enabled': True,
                    'backend': 'chroma',  # chroma, pinecone, weaviate, qdrant, milvus
                    'host': 'localhost',
                    'port': 8000,
                    'collection_name': 'ipfs_kit_vectors',
                    'dimension': 1536,  # OpenAI embedding dimension
                    'metric': 'cosine',  # cosine, euclidean, dot_product
                    'index_type': 'hnsw',  # hnsw, ivf, flat
                    'storage_path': str(self.config_dir / 'vector_db'),
                    'batch_size': 100,
                    'max_connections': 10,
                    'timeout': 30,  # seconds
                    'persistence': True,
                    'embedding_cache': True,
                    'auto_indexing': True
                },
                # Knowledge graph settings
                'knowledge_graph': {
                    'enabled': True,
                    'backend': 'networkx',  # networkx, neo4j, rdflib, blazegraph
                    'database_url': None,  # For Neo4j: bolt://localhost:7687
                    'username': None,
                    'password': None,
                    'storage_path': str(self.config_dir / 'knowledge_graph'),
                    'max_nodes': 100000,
                    'max_edges': 500000,
                    'indexing': True,
                    'full_text_search': True,
                    'reasoning_engine': 'owl',  # owl, rdfs, custom
                    'graph_algorithms': ['pagerank', 'centrality', 'clustering'],
                    'visualization': True,
                    'export_formats': ['graphml', 'gexf', 'json-ld'],
                    'query_language': 'cypher',  # cypher, sparql, gremlin
                    'schema_validation': True,
                    'backup_enabled': True
                }
            },
            's3': {
                'region': 'us-east-1',
                'endpoint_url': None,
                'bucket_name': None,
                'access_key_id': None,
                'secret_access_key': None,
                'use_ssl': True
            },
            'lotus': {
                'node_url': 'http://localhost:1234/rpc/v1',
                'token': None,
                'wallet_address': None,
                'deal_duration': 518400,  # ~180 days
                'verified_deal': False
            },
            'storacha': {
                'api_key': None,
                'endpoint_url': 'https://up.web3.storage',
                'chunk_size': 1048576  # 1MB
            },
            'gdrive': {
                'credentials_file': None,
                'client_id': None,
                'client_secret': None,
                'folder_id': None
            },
            'synapse': {
                'homeserver_url': None,
                'access_token': None,
                'room_id': None,
                'device_id': None
            },
            'huggingface': {
                'token': None,
                'default_org': None,
                'cache_dir': None
            },
            'github': {
                'token': None,
                'username': None,
                'default_org': None,
                'api_endpoint': 'https://api.github.com',
                'clone_method': 'https'  # https or ssh
            },
            'ipfs_cluster': {
                'cluster_secret': None,
                'listen_multiaddress': '/ip4/0.0.0.0/tcp/9096',
                'api_listen_multiaddress': '/ip4/127.0.0.1/tcp/9094',
                'proxy_listen_multiaddress': '/ip4/127.0.0.1/tcp/9095',
                'bootstrap_peers': [],
                'consensus': 'crdt',
                'replication_factor_min': 1,
                'replication_factor_max': 3
            },
            'cluster_follow': {
                'bootstrap_peer': None,
                'cluster_secret': None,
                'listen_multiaddress': '/ip4/0.0.0.0/tcp/9097',
                'trusted_peers': [],
                'auto_join': True,
                'pin_tracker': 'stateless'
            },
            'parquet': {
                'compression': 'snappy',
                'batch_size': 10000,
                'row_group_size': 100000,
                'use_dictionary': True,
                'cache_size': '128MB',
                'parallel_read': True,
                'memory_map': True
            },
            'arrow': {
                'memory_pool_size': '1GB',
                'use_threads': True,
                'batch_size': 8192,
                'compression_level': 6,
                'enable_null_optimization': True,
                'pre_buffer': True
            },
            'package': {
                'version': '0.2.8',
                'ipfs_path': None,
                'data_dir': str(self.config_dir),
                'auto_update': False
            },
            'wal': {
                'enabled': True,
                'batch_size': 100,
                'flush_interval': 30,
                'storage_path': str(self.config_dir / 'wal')
            },
            'fs_journal': {
                'enabled': False,
                'monitor_path': None,
                'watch_patterns': ['*.txt', '*.md', '*.pdf'],
                'ignore_patterns': ['.git/*', '__pycache__/*']
            }
        }
    
    def load_config(self, backend: str) -> Dict[str, Any]:
        """Load configuration for a specific backend."""
        config_file = self.config_dir / self.config_files.get(backend, f'{backend}_config.yaml')
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f) or {}
                
                # Merge with defaults
                default_config = self.defaults.get(backend, {}).copy()
                default_config.update(config)
                return default_config
                
            except Exception as e:
                print(f"⚠️  Error loading {config_file}: {e}")
                return self.defaults.get(backend, {}).copy()
        else:
            return self.defaults.get(backend, {}).copy()
    
    def save_config(self, backend: str, config: Dict[str, Any]) -> bool:
        """Save configuration for a specific backend."""
        config_file = self.config_dir / self.config_files.get(backend, f'{backend}_config.yaml')
        
        try:
            # Add metadata
            config_with_meta = config.copy()
            config_with_meta['_meta'] = {
                'updated_at': datetime.now().isoformat(),
                'version': '1.0'
            }
            
            with open(config_file, 'w') as f:
                yaml.dump(config_with_meta, f, default_flow_style=False, indent=2)
            
            print(f"✅ Configuration saved to {config_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving {config_file}: {e}")
            return False
    
    def load_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """Load all configurations."""
        configs = {}
        for backend in self.config_files.keys():
            configs[backend] = self.load_config(backend)
        return configs
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get a specific configuration value using dot notation."""
        parts = key.split('.')
        if len(parts) < 2:
            return default
        
        backend = parts[0]
        config = self.load_config(backend)
        
        # Navigate through nested keys
        current = config
        for part in parts[1:]:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        
        return current
    
    def set_config_value(self, key: str, value: Any) -> bool:
        """Set a specific configuration value using dot notation."""
        parts = key.split('.')
        if len(parts) < 2:
            print(f"❌ Invalid config key format: {key}")
            print("   Use format: backend.setting (e.g., s3.region)")
            return False
        
        backend = parts[0]
        if backend not in self.config_files:
            print(f"❌ Unknown backend: {backend}")
            print(f"   Available backends: {', '.join(self.config_files.keys())}")
            return False
        
        # Load current config
        config = self.load_config(backend)
        
        # Navigate to the parent of the target key
        current = config
        for part in parts[1:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Set the value
        current[parts[-1]] = value
        
        return self.save_config(backend, config)
    
    def interactive_setup(self, backend: Optional[str] = None, non_interactive: bool = False) -> bool:
        """Interactive configuration setup for backends."""
        if backend == 'all' or backend is None:
            backends = ['daemon', 's3', 'lotus', 'storacha', 'gdrive', 'synapse', 'huggingface', 'github', 'ipfs_cluster', 'cluster_follow', 'parquet', 'arrow']
        else:
            backends = [backend]
        
        print("🔧 Interactive Configuration Setup")
        print("=" * 50)
        
        if not non_interactive:
            print("This will guide you through configuring your storage backends.")
            print("Press Enter to use default values shown in [brackets].")
            print("")
        
        success_count = 0
        
        for backend_name in backends:
            if not non_interactive:
                print(f"\n📦 Configuring {backend_name.upper()}...")
                should_configure = input(f"Configure {backend_name}? [y/N]: ").lower() in ['y', 'yes']
                if not should_configure:
                    print(f"⏭️  Skipping {backend_name}")
                    continue
            
            try:
                if backend_name == 'daemon':
                    success = self._configure_daemon(non_interactive)
                elif backend_name == 's3':
                    success = self._configure_s3(non_interactive)
                elif backend_name == 'lotus':
                    success = self._configure_lotus(non_interactive)
                elif backend_name == 'storacha':
                    success = self._configure_storacha(non_interactive)
                elif backend_name == 'gdrive':
                    success = self._configure_gdrive(non_interactive)
                elif backend_name == 'synapse':
                    success = self._configure_synapse(non_interactive)
                elif backend_name == 'huggingface':
                    success = self._configure_huggingface(non_interactive)
                elif backend_name == 'github':
                    success = self._configure_github(non_interactive)
                elif backend_name == 'ipfs_cluster':
                    success = self._configure_ipfs_cluster(non_interactive)
                elif backend_name == 'cluster_follow':
                    success = self._configure_cluster_follow(non_interactive)
                elif backend_name == 'parquet':
                    success = self._configure_parquet(non_interactive)
                elif backend_name == 'arrow':
                    success = self._configure_arrow(non_interactive)
                else:
                    print(f"⚠️  Configuration for {backend_name} not yet implemented")
                    success = False
                
                if success:
                    success_count += 1
                    
            except KeyboardInterrupt:
                print(f"\n⚠️  Configuration cancelled by user")
                break
            except Exception as e:
                print(f"❌ Error configuring {backend_name}: {e}")
        
        print(f"\n🎯 Configuration complete: {success_count}/{len(backends)} backends configured")
        return success_count > 0
    
    def _configure_daemon(self, non_interactive: bool = False) -> bool:
        """Configure daemon settings including advanced features."""
        config = self.load_config('daemon')
        
        if not non_interactive:
            print("🔧 Daemon Configuration")
            print("The daemon manages IPFS operations and storage backends.")
            print("=" * 50)
            
            # Basic daemon settings
            port = input(f"Daemon port [{config['port']}]: ").strip()
            if port:
                try:
                    config['port'] = int(port)
                except ValueError:
                    print("❌ Invalid port number, using default")
            
            role = input(f"Daemon role (local/master/worker/leecher) [{config['role']}]: ").strip()
            if role in ['local', 'master', 'worker', 'leecher']:
                config['role'] = role
            
            workers = input(f"Max workers [{config['max_workers']}]: ").strip()
            if workers:
                try:
                    config['max_workers'] = int(workers)
                except ValueError:
                    print("❌ Invalid worker count, using default")
            
            auto_start = input(f"Auto-start daemon [{config['auto_start']}]: ").strip()
            if auto_start.lower() in ['true', 'false']:
                config['auto_start'] = auto_start.lower() == 'true'
            
            log_level = input(f"Log level (DEBUG/INFO/WARNING/ERROR) [{config['log_level']}]: ").strip()
            if log_level.upper() in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
                config['log_level'] = log_level.upper()

            # Advanced daemon settings
            print("\n🧠 Advanced Daemon Settings")
            print("Configure caching, semantic search, replication, and knowledge graph features")
            
            configure_advanced = input("Configure advanced settings? [y/N]: ").strip().lower()
            if configure_advanced in ['y', 'yes']:
                
                # Cache configuration
                print("\n💾 Cache Settings")
                cache_enabled = input(f"Enable caching? [{'Y' if config['cache']['enabled'] else 'N'}]: ").strip().lower()
                if cache_enabled in ['y', 'yes']:
                    config['cache']['enabled'] = True
                elif cache_enabled in ['n', 'no']:
                    config['cache']['enabled'] = False
                
                if config['cache']['enabled']:
                    cache_type = input(f"Cache type (lru/lfu/ttl/redis) [{config['cache']['type']}]: ").strip()
                    if cache_type:
                        config['cache']['type'] = cache_type
                        
                    max_size = input(f"Max cache size [{config['cache']['max_size']}]: ").strip()
                    if max_size:
                        config['cache']['max_size'] = max_size
                
                # Semantic cache configuration
                print("\n🧠 Semantic Cache Settings")
                semantic_enabled = input(f"Enable semantic caching? [{'Y' if config['semantic_cache']['enabled'] else 'N'}]: ").strip().lower()
                if semantic_enabled in ['y', 'yes']:
                    config['semantic_cache']['enabled'] = True
                elif semantic_enabled in ['n', 'no']:
                    config['semantic_cache']['enabled'] = False
                
                if config['semantic_cache']['enabled']:
                    model = input(f"Embedding model [{config['semantic_cache']['embedding_model']}]: ").strip()
                    if model:
                        config['semantic_cache']['embedding_model'] = model
                        
                    threshold = input(f"Similarity threshold (0.0-1.0) [{config['semantic_cache']['similarity_threshold']}]: ").strip()
                    if threshold:
                        try:
                            config['semantic_cache']['similarity_threshold'] = float(threshold)
                        except ValueError:
                            print("⚠️  Invalid threshold value, keeping default")
                
                # Replication configuration  
                print("\n🔄 Replication Policy Settings")
                replication_enabled = input(f"Enable replication? [{'Y' if config['replication']['enabled'] else 'N'}]: ").strip().lower()
                if replication_enabled in ['y', 'yes']:
                    config['replication']['enabled'] = True
                elif replication_enabled in ['n', 'no']:
                    config['replication']['enabled'] = False
                
                if config['replication']['enabled']:
                    strategy = input(f"Replication strategy (eager/lazy/hybrid) [{config['replication']['strategy']}]: ").strip()
                    if strategy:
                        config['replication']['strategy'] = strategy
                        
                    target_replicas = input(f"Target replicas [{config['replication']['target_replicas']}]: ").strip()
                    if target_replicas.isdigit():
                        config['replication']['target_replicas'] = int(target_replicas)
                
                # Vector database configuration
                print("\n🔍 Vector Database Settings")
                vector_enabled = input(f"Enable vector database? [{'Y' if config['vector_db']['enabled'] else 'N'}]: ").strip().lower()
                if vector_enabled in ['y', 'yes']:
                    config['vector_db']['enabled'] = True
                elif vector_enabled in ['n', 'no']:
                    config['vector_db']['enabled'] = False
                
                if config['vector_db']['enabled']:
                    backend = input(f"Vector DB backend (chroma/pinecone/weaviate/qdrant/milvus) [{config['vector_db']['backend']}]: ").strip()
                    if backend:
                        config['vector_db']['backend'] = backend
                        
                    collection = input(f"Collection name [{config['vector_db']['collection_name']}]: ").strip()
                    if collection:
                        config['vector_db']['collection_name'] = collection
                
                # Knowledge graph configuration
                print("\n🕸️  Knowledge Graph Settings")
                kg_enabled = input(f"Enable knowledge graph? [{'Y' if config['knowledge_graph']['enabled'] else 'N'}]: ").strip().lower()
                if kg_enabled in ['y', 'yes']:
                    config['knowledge_graph']['enabled'] = True
                elif kg_enabled in ['n', 'no']:
                    config['knowledge_graph']['enabled'] = False
                
                if config['knowledge_graph']['enabled']:
                    kg_backend = input(f"Graph backend (networkx/neo4j/rdflib/blazegraph) [{config['knowledge_graph']['backend']}]: ").strip()
                    if kg_backend:
                        config['knowledge_graph']['backend'] = kg_backend
                        
                    if kg_backend in ['neo4j', 'blazegraph']:
                        database_url = input(f"Database URL [{config['knowledge_graph']['database_url'] or 'Not set'}]: ").strip()
                        if database_url:
                            config['knowledge_graph']['database_url'] = database_url
        
        return self.save_config('daemon', config)
    
    def _configure_s3(self, non_interactive: bool = False) -> bool:
        """Configure S3 settings."""
        config = self.load_config('s3')
        
        if not non_interactive:
            print("☁️  S3 Configuration")
            print("Configure AWS S3 or S3-compatible storage.")
            
            access_key = input(f"Access Key ID [{config.get('access_key_id', 'Not set')}]: ").strip()
            if access_key:
                config['access_key_id'] = access_key
            
            if config.get('access_key_id'):
                secret_key = getpass.getpass("Secret Access Key [Hidden]: ").strip()
                if secret_key:
                    config['secret_access_key'] = secret_key
            
            region = input(f"Region [{config['region']}]: ").strip()
            if region:
                config['region'] = region
            
            endpoint = input(f"Custom endpoint URL [{config.get('endpoint_url', 'Default AWS')}]: ").strip()
            if endpoint:
                config['endpoint_url'] = endpoint
            
            bucket = input(f"Default bucket name [{config.get('bucket_name', 'Not set')}]: ").strip()
            if bucket:
                config['bucket_name'] = bucket
            
            use_ssl = input(f"Use SSL [{config['use_ssl']}]: ").strip()
            if use_ssl.lower() in ['true', 'false']:
                config['use_ssl'] = use_ssl.lower() == 'true'
        
        return self.save_config('s3', config)
    
    def _configure_lotus(self, non_interactive: bool = False) -> bool:
        """Configure Lotus/Filecoin settings."""
        config = self.load_config('lotus')
        
        if not non_interactive:
            print("🪷 Lotus/Filecoin Configuration")
            print("Configure Filecoin storage via Lotus node.")
            
            node_url = input(f"Lotus node URL [{config['node_url']}]: ").strip()
            if node_url:
                config['node_url'] = node_url
            
            token = getpass.getpass("Lotus API token [Hidden]: ").strip()
            if token:
                config['token'] = token
            
            wallet = input(f"Wallet address [{config.get('wallet_address', 'Not set')}]: ").strip()
            if wallet:
                config['wallet_address'] = wallet
            
            duration = input(f"Deal duration in epochs [{config['deal_duration']}]: ").strip()
            if duration:
                try:
                    config['deal_duration'] = int(duration)
                except ValueError:
                    print("❌ Invalid duration, using default")
            
            verified = input(f"Verified deals [{config['verified_deal']}]: ").strip()
            if verified.lower() in ['true', 'false']:
                config['verified_deal'] = verified.lower() == 'true'
        
        return self.save_config('lotus', config)
    
    def _configure_storacha(self, non_interactive: bool = False) -> bool:
        """Configure Storacha/Web3.Storage settings."""
        config = self.load_config('storacha')
        
        if not non_interactive:
            print("🌐 Storacha/Web3.Storage Configuration")
            print("Configure decentralized storage via Storacha.")
            
            api_key = getpass.getpass("Storacha API key [Hidden]: ").strip()
            if api_key:
                config['api_key'] = api_key
            
            endpoint = input(f"Endpoint URL [{config['endpoint_url']}]: ").strip()
            if endpoint:
                config['endpoint_url'] = endpoint
            
            chunk_size = input(f"Chunk size in bytes [{config['chunk_size']}]: ").strip()
            if chunk_size:
                try:
                    config['chunk_size'] = int(chunk_size)
                except ValueError:
                    print("❌ Invalid chunk size, using default")
        
        return self.save_config('storacha', config)
    
    def _configure_gdrive(self, non_interactive: bool = False) -> bool:
        """Configure Google Drive settings."""
        config = self.load_config('gdrive')
        
        if not non_interactive:
            print("📁 Google Drive Configuration")
            print("Configure Google Drive storage backend.")
            
            creds_file = input(f"Credentials JSON file path [{config.get('credentials_file', 'Not set')}]: ").strip()
            if creds_file:
                config['credentials_file'] = creds_file
            
            client_id = input(f"Client ID [{config.get('client_id', 'Not set')}]: ").strip()
            if client_id:
                config['client_id'] = client_id
            
            client_secret = getpass.getpass("Client Secret [Hidden]: ").strip()
            if client_secret:
                config['client_secret'] = client_secret
            
            folder_id = input(f"Default folder ID [{config.get('folder_id', 'Not set')}]: ").strip()
            if folder_id:
                config['folder_id'] = folder_id
        
        return self.save_config('gdrive', config)
    
    def _configure_synapse(self, non_interactive: bool = False) -> bool:
        """Configure Matrix/Synapse settings."""
        config = self.load_config('synapse')
        
        if not non_interactive:
            print("💬 Matrix/Synapse Configuration")
            print("Configure Matrix communication backend.")
            
            homeserver = input(f"Homeserver URL [{config.get('homeserver_url', 'Not set')}]: ").strip()
            if homeserver:
                config['homeserver_url'] = homeserver
            
            access_token = getpass.getpass("Access token [Hidden]: ").strip()
            if access_token:
                config['access_token'] = access_token
            
            room_id = input(f"Default room ID [{config.get('room_id', 'Not set')}]: ").strip()
            if room_id:
                config['room_id'] = room_id
            
            device_id = input(f"Device ID [{config.get('device_id', 'Not set')}]: ").strip()
            if device_id:
                config['device_id'] = device_id
        
        return self.save_config('synapse', config)
    
    def _configure_huggingface(self, non_interactive: bool = False) -> bool:
        """Configure HuggingFace Hub settings."""
        config = self.load_config('huggingface')
        
        if not non_interactive:
            print("🤗 HuggingFace Hub Configuration")
            print("Configure HuggingFace model/dataset storage.")
            
            token = getpass.getpass("HuggingFace token [Hidden]: ").strip()
            if token:
                config['token'] = token
            
            org = input(f"Default organization [{config.get('default_org', 'Not set')}]: ").strip()
            if org:
                config['default_org'] = org
            
            cache_dir = input(f"Cache directory [{config.get('cache_dir', 'Not set')}]: ").strip()
            if cache_dir:
                config['cache_dir'] = cache_dir
        
        return self.save_config('huggingface', config)
    
    def _configure_github(self, non_interactive: bool = False) -> bool:
        """Configure GitHub settings."""
        config = self.load_config('github')
        
        if not non_interactive:
            print("🐙 GitHub Configuration")
            print("Configure GitHub repository operations and API access.")
            
            token = getpass.getpass("GitHub Personal Access Token [Hidden]: ").strip()
            if token:
                config['token'] = token
            
            username = input(f"GitHub username [{config.get('username', 'Not set')}]: ").strip()
            if username:
                config['username'] = username
            
            org = input(f"Default organization [{config.get('default_org', 'Not set')}]: ").strip()
            if org:
                config['default_org'] = org
            
            api_endpoint = input(f"API endpoint [{config['api_endpoint']}]: ").strip()
            if api_endpoint:
                config['api_endpoint'] = api_endpoint
            
            clone_method = input(f"Clone method (https/ssh) [{config['clone_method']}]: ").strip()
            if clone_method in ['https', 'ssh']:
                config['clone_method'] = clone_method
        
        return self.save_config('github', config)
    
    def _configure_ipfs_cluster(self, non_interactive: bool = False) -> bool:
        """Configure IPFS Cluster settings."""
        config = self.load_config('ipfs_cluster')
        
        if not non_interactive:
            print("🔗 IPFS Cluster Configuration")
            print("Configure IPFS Cluster for distributed pinning.")
            
            cluster_secret = getpass.getpass("Cluster secret [Hidden]: ").strip()
            if cluster_secret:
                config['cluster_secret'] = cluster_secret
            
            listen_addr = input(f"Listen multiaddress [{config['listen_multiaddress']}]: ").strip()
            if listen_addr:
                config['listen_multiaddress'] = listen_addr
            
            api_listen = input(f"API listen multiaddress [{config['api_listen_multiaddress']}]: ").strip()
            if api_listen:
                config['api_listen_multiaddress'] = api_listen
            
            consensus = input(f"Consensus algorithm (crdt/raft) [{config['consensus']}]: ").strip()
            if consensus in ['crdt', 'raft']:
                config['consensus'] = consensus
            
            repl_min = input(f"Replication factor min [{config['replication_factor_min']}]: ").strip()
            if repl_min:
                try:
                    config['replication_factor_min'] = int(repl_min)
                except ValueError:
                    print("❌ Invalid replication factor, using default")
            
            repl_max = input(f"Replication factor max [{config['replication_factor_max']}]: ").strip()
            if repl_max:
                try:
                    config['replication_factor_max'] = int(repl_max)
                except ValueError:
                    print("❌ Invalid replication factor, using default")
        
        return self.save_config('ipfs_cluster', config)
    
    def _configure_cluster_follow(self, non_interactive: bool = False) -> bool:
        """Configure IPFS Cluster Follow settings."""
        config = self.load_config('cluster_follow')
        
        if not non_interactive:
            print("👥 IPFS Cluster Follow Configuration")
            print("Configure cluster following for joining existing clusters.")
            
            bootstrap_peer = input(f"Bootstrap peer multiaddress [{config.get('bootstrap_peer', 'Not set')}]: ").strip()
            if bootstrap_peer:
                config['bootstrap_peer'] = bootstrap_peer
            
            cluster_secret = getpass.getpass("Cluster secret [Hidden]: ").strip()
            if cluster_secret:
                config['cluster_secret'] = cluster_secret
            
            listen_addr = input(f"Listen multiaddress [{config['listen_multiaddress']}]: ").strip()
            if listen_addr:
                config['listen_multiaddress'] = listen_addr
            
            auto_join = input(f"Auto-join cluster [{config['auto_join']}]: ").strip()
            if auto_join.lower() in ['true', 'false']:
                config['auto_join'] = auto_join.lower() == 'true'
            
            pin_tracker = input(f"Pin tracker (stateless/map) [{config['pin_tracker']}]: ").strip()
            if pin_tracker in ['stateless', 'map']:
                config['pin_tracker'] = pin_tracker
        
        return self.save_config('cluster_follow', config)
    
    def _configure_parquet(self, non_interactive: bool = False) -> bool:
        """Configure Parquet settings."""
        config = self.load_config('parquet')
        
        if not non_interactive:
            print("📊 Parquet Configuration")
            print("Configure Apache Parquet file format settings.")
            
            compression = input(f"Compression (snappy/gzip/lz4/brotli/zstd) [{config['compression']}]: ").strip()
            if compression in ['snappy', 'gzip', 'lz4', 'brotli', 'zstd']:
                config['compression'] = compression
            
            batch_size = input(f"Batch size [{config['batch_size']}]: ").strip()
            if batch_size:
                try:
                    config['batch_size'] = int(batch_size)
                except ValueError:
                    print("❌ Invalid batch size, using default")
            
            row_group_size = input(f"Row group size [{config['row_group_size']}]: ").strip()
            if row_group_size:
                try:
                    config['row_group_size'] = int(row_group_size)
                except ValueError:
                    print("❌ Invalid row group size, using default")
            
            cache_size = input(f"Cache size [{config['cache_size']}]: ").strip()
            if cache_size:
                config['cache_size'] = cache_size
            
            parallel_read = input(f"Parallel reading [{config['parallel_read']}]: ").strip()
            if parallel_read.lower() in ['true', 'false']:
                config['parallel_read'] = parallel_read.lower() == 'true'
            
            memory_map = input(f"Memory mapping [{config['memory_map']}]: ").strip()
            if memory_map.lower() in ['true', 'false']:
                config['memory_map'] = memory_map.lower() == 'true'
        
        return self.save_config('parquet', config)
    
    def _configure_arrow(self, non_interactive: bool = False) -> bool:
        """Configure Apache Arrow settings."""
        config = self.load_config('arrow')
        
        if not non_interactive:
            print("🏹 Apache Arrow Configuration")
            print("Configure Apache Arrow in-memory columnar format.")
            
            memory_pool = input(f"Memory pool size [{config['memory_pool_size']}]: ").strip()
            if memory_pool:
                config['memory_pool_size'] = memory_pool
            
            use_threads = input(f"Use threads [{config['use_threads']}]: ").strip()
            if use_threads.lower() in ['true', 'false']:
                config['use_threads'] = use_threads.lower() == 'true'
            
            batch_size = input(f"Batch size [{config['batch_size']}]: ").strip()
            if batch_size:
                try:
                    config['batch_size'] = int(batch_size)
                except ValueError:
                    print("❌ Invalid batch size, using default")
            
            compression_level = input(f"Compression level (0-9) [{config['compression_level']}]: ").strip()
            if compression_level:
                try:
                    level = int(compression_level)
                    if 0 <= level <= 9:
                        config['compression_level'] = level
                    else:
                        print("❌ Compression level must be 0-9, using default")
                except ValueError:
                    print("❌ Invalid compression level, using default")
            
            pre_buffer = input(f"Pre-buffer data [{config['pre_buffer']}]: ").strip()
            if pre_buffer.lower() in ['true', 'false']:
                config['pre_buffer'] = pre_buffer.lower() == 'true'
        
        return self.save_config('arrow', config)
    
    def backup_configs(self, backup_file: Optional[str] = None) -> bool:
        """Backup all configurations to a file."""
        if not backup_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = str(self.config_dir / f'config_backup_{timestamp}.yaml')
        
        try:
            all_configs = self.load_all_configs()
            
            backup_data = {
                'backup_metadata': {
                    'created_at': datetime.now().isoformat(),
                    'version': '1.0'
                },
                'configurations': all_configs
            }
            
            with open(backup_file, 'w') as f:
                yaml.dump(backup_data, f, default_flow_style=False, indent=2)
            
            print(f"✅ Configuration backed up to {backup_file}")
            return True
            
        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return False
    
    def restore_configs(self, backup_file: str) -> bool:
        """Restore configurations from a backup file."""
        try:
            with open(backup_file, 'r') as f:
                backup_data = yaml.safe_load(f)
            
            if 'configurations' not in backup_data:
                print("❌ Invalid backup file format")
                return False
            
            configs = backup_data['configurations']
            success_count = 0
            
            for backend, config in configs.items():
                if backend in self.config_files:
                    if self.save_config(backend, config):
                        success_count += 1
            
            print(f"✅ Restored {success_count}/{len(configs)} configurations")
            return success_count > 0
            
        except Exception as e:
            print(f"❌ Restore failed: {e}")
            return False
    
    def reset_config(self, backend: Optional[str] = None) -> bool:
        """Reset configuration to defaults."""
        if backend == 'all' or backend is None:
            backends = list(self.config_files.keys())
        else:
            backends = [backend]
        
        success_count = 0
        
        for backend_name in backends:
            if backend_name in self.defaults:
                if self.save_config(backend_name, self.defaults[backend_name].copy()):
                    success_count += 1
                    print(f"✅ Reset {backend_name} configuration")
                else:
                    print(f"❌ Failed to reset {backend_name} configuration")
        
        print(f"🎯 Reset complete: {success_count}/{len(backends)} configurations")
        return success_count > 0
    
    def validate_configs(self) -> Dict[str, Any]:
        """Validate all configuration files."""
        results = {
            'valid': [],
            'invalid': [],
            'missing': [],
            'total_files': 0,
            'valid_count': 0
        }
        
        for backend, filename in self.config_files.items():
            config_file = self.config_dir / filename
            results['total_files'] += 1
            
            if not config_file.exists():
                results['missing'].append({
                    'backend': backend,
                    'file': filename,
                    'status': 'missing'
                })
                continue
            
            try:
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)
                
                if config is not None:
                    results['valid'].append({
                        'backend': backend,
                        'file': filename,
                        'status': 'valid',
                        'keys': list(config.keys()) if isinstance(config, dict) else []
                    })
                    results['valid_count'] += 1
                else:
                    results['invalid'].append({
                        'backend': backend,
                        'file': filename,
                        'status': 'empty',
                        'error': 'Empty configuration file'
                    })
                    
            except Exception as e:
                results['invalid'].append({
                    'backend': backend,
                    'file': filename,
                    'status': 'invalid',
                    'error': str(e)
                })
        
        return results


def get_config_manager() -> ConfigManager:
    """Get a configured ConfigManager instance."""
    return ConfigManager()
