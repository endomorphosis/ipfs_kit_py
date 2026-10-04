#!/usr/bin/env python3
"""
Demo: Git VFS Translation Layer and SSHFS Backend

This demo showcases the new Git VFS translation layer functionality
and SSHFS backend integration in IPFS-Kit.

Features demonstrated:
1. Git VFS Translation Layer
   - Analysis of Git repository metadata
   - Translation between Git commits and VFS snapshots
   - Content-addressed mapping of Git content
   
2. GitHub Kit Integration
   - Git VFS translation for GitHub repositories
   - Repository content type detection
   - VFS bucket mapping for GitHub repos
   
3. HuggingFace Kit Integration
   - Git VFS translation for HuggingFace repositories
   - ML-specific metadata extraction
   - Model/dataset content addressing

4. SSHFS Backend
   - SSH-based remote storage
   - Connection pooling and management
   - Integration with VFS system

This is a demonstration of advanced VFS features for repositories
that exist as both Git repositories and content-addressed storage.
"""

import anyio
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def demo_git_vfs_translator():
    """Demonstrate Git VFS translation layer."""
    print("\n" + "="*60)
    print("🔧 Git VFS Translation Layer Demo")
    print("="*60)
    
    try:
        from ipfs_kit_py.git_vfs_translator import GitVFSTranslator
        
        # Create a temporary directory for demo
        with tempfile.TemporaryDirectory() as temp_dir:
            demo_repo_path = Path(temp_dir) / "demo_repo"
            demo_repo_path.mkdir()
            
            # Initialize a simple Git repository
            import subprocess
            import os
            
            os.chdir(demo_repo_path)
            subprocess.run(["git", "init"], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "demo@ipfs-kit.local"], check=True)
            subprocess.run(["git", "config", "user.name", "IPFS-Kit Demo"], check=True)
            
            # Create some demo files
            (demo_repo_path / "README.md").write_text("# Demo Repository\n\nThis is a demo for Git VFS translation.")
            (demo_repo_path / "config.json").write_text('{"demo": true, "version": "1.0"}')
            
            # Add and commit files
            subprocess.run(["git", "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], check=True, capture_output=True)
            
            # Create Git VFS translator
            translator = GitVFSTranslator(demo_repo_path)
            
            # Analyze Git metadata
            print("📊 Analyzing Git repository metadata...")
            analysis = translator.analyze_git_metadata()
            print(f"✅ Repository analysis completed:")
            print(f"   - Total commits: {analysis['repository_info'].get('total_commits', 0)}")
            print(f"   - Active branch: {analysis['repository_info'].get('active_branch', 'unknown')}")
            print(f"   - File types: {len(analysis['file_changes'].get('file_types', {}))}")
            
            # Sync Git to VFS
            print("\n🔄 Syncing Git metadata to VFS...")
            sync_result = translator.sync_git_to_vfs()
            print(f"✅ Sync completed:")
            print(f"   - Snapshots created: {sync_result.get('snapshots_created', 0)}")
            print(f"   - Errors: {len(sync_result.get('errors', []))}")
            
            # Export VFS metadata
            print("\n📤 Exporting VFS metadata...")
            export_result = translator.export_vfs_metadata()
            if export_result['success']:
                print(f"✅ Export successful:")
                print(f"   - Export path: {export_result['export_path']}")
                print(f"   - File size: {export_result['file_size']} bytes")
                print(f"   - Snapshots exported: {export_result['snapshots_exported']}")
            
    except ImportError as e:
        print(f"❌ Git VFS translator not available: {e}")
        print("💡 Install GitPython to enable Git VFS translation features")
    except Exception as e:
        print(f"❌ Error in Git VFS demo: {e}")

async def demo_github_git_vfs():
    """Demonstrate GitHub Kit with Git VFS translation."""
    print("\n" + "="*60)
    print("🐙 GitHub Kit Git VFS Translation Demo")
    print("="*60)
    
    try:
        from ipfs_kit_py.github_kit import GitHubKit
        
        # Create GitHub kit instance
        github_kit = GitHubKit()
        
        # Example repository analysis (simulated)
        print("📊 Analyzing GitHub repository for VFS translation...")
        
        # Simulate repository info
        repo_info = {
            'full_name': 'example/demo-repo',
            'name': 'demo-repo',
            'owner': {'login': 'example'},
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-15T12:00:00Z',
            'default_branch': 'main',
            'language': 'Python',
            'size': 1024,
            'description': 'A demo repository for machine learning models',
            'topics': ['machine-learning', 'python', 'demo'],
            'clone_url': 'https://github.com/example/demo-repo.git'
        }
        
        # Analyze repository metadata
        analysis = await github_kit.analyze_repository_git_metadata(repo_info)
        
        print(f"✅ GitHub repository analysis completed:")
        print(f"   - Repository: {analysis['repository']}")
        print(f"   - VFS bucket: {analysis['vfs_bucket']}")
        print(f"   - Peer ID: {analysis['peer_id']}")
        print(f"   - Content type: {analysis['content_addressing']['content_type']}")
        print(f"   - VFS mount point: {analysis['content_addressing']['vfs_mount_point']}")
        print(f"   - Estimated VFS blocks: {analysis['content_addressing']['estimated_vfs_blocks']}")
        
        # Demonstrate content type detection
        print(f"\n🏷️  Content Type Detection:")
        print(f"   - Detected type: {analysis['content_addressing']['content_type']}")
        print(f"   - Repository hash: {analysis['content_addressing']['github_repo_hash']}")
        
    except ImportError as e:
        print(f"❌ GitHub Kit not available: {e}")
    except Exception as e:
        print(f"❌ Error in GitHub VFS demo: {e}")

async def demo_huggingface_git_vfs():
    """Demonstrate HuggingFace Kit with Git VFS translation."""
    print("\n" + "="*60)
    print("🤗 HuggingFace Kit Git VFS Translation Demo")
    print("="*60)
    
    try:
        from ipfs_kit_py.huggingface_kit import huggingface_kit
        
        # Create HuggingFace kit instance
        hf_kit = huggingface_kit()
        
        print("📊 Analyzing HuggingFace repository for VFS translation...")
        
        # Simulate repository info (would normally come from HF Hub API)
        repo_info = {
            'id': 'example/demo-model',
            'name': 'demo-model',
            'owner': 'example',
            'url': 'https://huggingface.co/example/demo-model',
            'private': False,
            'type': 'model',
            'last_modified': '2024-01-15T12:00:00Z',
            'tags': ['pytorch', 'transformers', 'text-classification'],
            'card_data': {
                'library_name': 'transformers',
                'pipeline_tag': 'text-classification',
                'language': ['en'],
                'license': 'apache-2.0'
            },
            'default_branch': 'main',
            'siblings': [
                {'rfilename': 'config.json'},
                {'rfilename': 'pytorch_model.bin'},
                {'rfilename': 'tokenizer.json'},
                {'rfilename': 'README.md'}
            ]
        }
        
        # Analyze repository metadata
        analysis_result = hf_kit.analyze_huggingface_repo_metadata('example/demo-model', 'model')
        
        if analysis_result.get('success'):
            analysis = analysis_result['analysis']
            print(f"✅ HuggingFace repository analysis completed:")
            print(f"   - Repository: {analysis['repository']}")
            print(f"   - Repository type: {analysis['repo_type']}")
            print(f"   - VFS bucket: {analysis['vfs_bucket']}")
            print(f"   - Peer ID: {analysis['peer_id']}")
            print(f"   - Content type: {analysis['content_addressing']['content_type']}")
            print(f"   - VFS mount point: {analysis['content_addressing']['vfs_mount_point']}")
            print(f"   - Estimated VFS blocks: {analysis['content_addressing']['estimated_vfs_blocks']}")
            
            # Show HuggingFace-specific metadata
            hf_metadata = analysis['huggingface_metadata']
            print(f"\n🤗 HuggingFace-specific metadata:")
            print(f"   - Library: {hf_metadata.get('model_index', {}).get('library', 'N/A')}")
            print(f"   - Pipeline: {hf_metadata.get('model_index', {}).get('pipeline', 'N/A')}")
            print(f"   - Language: {hf_metadata.get('model_index', {}).get('language', 'N/A')}")
            print(f"   - File count: {len(hf_metadata.get('siblings', []))}")
        else:
            print(f"❌ Analysis failed: {analysis_result.get('error', 'Unknown error')}")
        
    except ImportError as e:
        print(f"❌ HuggingFace Kit not available: {e}")
    except Exception as e:
        print(f"❌ Error in HuggingFace VFS demo: {e}")

async def demo_sshfs_backend():
    """Demonstrate SSHFS backend functionality."""
    print("\n" + "="*60)
    print("🔐 SSHFS Backend Demo")
    print("="*60)
    
    try:
        from ipfs_kit_py.sshfs_backend import SSHFSConfig, create_sshfs_backend
        
        print("📊 SSHFS Backend Configuration Demo...")
        
        # Create example configuration
        config = {
            'hostname': 'example.com',
            'username': 'demo_user',
            'port': 22,
            'password': 'demo_password',  # In real use, use key-based auth
            'remote_base_path': '/tmp/ipfs_kit_demo',
            'connection_timeout': 30,
            'max_connections': 3
        }
        
        # Validate configuration
        sshfs_config = SSHFSConfig(**config)
        validation_errors = sshfs_config.validate()
        
        print(f"✅ SSHFS Configuration created:")
        print(f"   - Hostname: {sshfs_config.hostname}")
        print(f"   - Username: {sshfs_config.username}")
        print(f"   - Port: {sshfs_config.port}")
        print(f"   - Remote path: {sshfs_config.remote_base_path}")
        print(f"   - Max connections: {sshfs_config.max_connections}")
        
        if validation_errors:
            print(f"⚠️  Configuration validation errors:")
            for error in validation_errors:
                print(f"   - {error}")
        else:
            print(f"✅ Configuration validation passed")
        
        # Demonstrate backend creation (without actually connecting)
        print(f"\n🔧 Creating SSHFS backend instance...")
        try:
            backend = create_sshfs_backend(config)
            backend_info = await backend.get_info()
            print(f"✅ SSHFS backend created:")
            print(f"   - Backend type: {backend_info['backend_type']}")
            print(f"   - Hostname: {backend_info['hostname']}")
            print(f"   - Max connections: {backend_info['max_connections']}")
        except ImportError as ie:
            print(f"❌ Missing dependencies: {ie}")
            print("💡 Install paramiko and scp: pip install paramiko scp")
        except Exception as e:
            print(f"⚠️  Backend creation failed (expected without real SSH server): {e}")
        
    except ImportError as e:
        print(f"❌ SSHFS backend not available: {e}")
        print("💡 Install required dependencies: pip install paramiko scp")
    except Exception as e:
        print(f"❌ Error in SSHFS demo: {e}")

async def demo_storage_integration():
    """Demonstrate storage backend integration."""
    print("\n" + "="*60)
    print("🗄️  Storage Backend Integration Demo")
    print("="*60)
    
    try:
        from ipfs_kit_py.mcp.storage_types import StorageBackendType
        
        print("📊 Available Storage Backend Types:")
        for backend_type in StorageBackendType:
            print(f"   - {backend_type.value}")
        
        # Demonstrate tier mapping
        tier_mapping = {
            "ipfs": "ipfs",
            "s3": "s3", 
            "storacha": "storacha",
            "huggingface": "huggingface",
            "filecoin": "filecoin",
            "lassie": "ipfs",
            "sshfs": "sshfs",
            "gdrive": "gdrive"
        }
        
        print(f"\n🏷️  Storage Tier Mapping:")
        for backend, tier in tier_mapping.items():
            print(f"   - {backend} → {tier}")
        
        # Show SSHFS integration
        if StorageBackendType.SSHFS:
            print(f"\n✅ SSHFS successfully integrated into storage backend system")
            print(f"   - Backend type: {StorageBackendType.SSHFS}")
            print(f"   - Tier mapping: sshfs → {tier_mapping.get('sshfs', 'sshfs')}")
        
    except ImportError as e:
        print(f"❌ Storage types not available: {e}")
    except Exception as e:
        print(f"❌ Error in storage integration demo: {e}")

async def main():
    """Run the complete Git VFS and SSHFS demo."""
    print("🚀 IPFS-Kit Git VFS Translation & SSHFS Backend Demo")
    print("=" * 60)
    print("This demo showcases advanced Git repository integration")
    print("with content-addressed storage and SSH-based backends.")
    print()
    
    # Run all demo sections
    await demo_git_vfs_translator()
    await demo_github_git_vfs()
    await demo_huggingface_git_vfs()
    await demo_sshfs_backend()
    await demo_storage_integration()
    
    print("\n" + "="*60)
    print("✅ Demo completed!")
    print("="*60)
    print("\n🎯 Key Features Demonstrated:")
    print("   1. Git VFS Translation Layer")
    print("      - Converts Git commits to VFS snapshots")
    print("      - Maps Git content to content-addressed blocks")
    print("      - Maintains .ipfs_kit metadata alongside Git")
    print()
    print("   2. GitHub Kit Git Integration")
    print("      - Analyzes GitHub repositories for VFS mapping")
    print("      - Detects content types (ML models, datasets, etc.)")
    print("      - Creates VFS bucket representations")
    print()
    print("   3. HuggingFace Kit Git Integration")
    print("      - Specialized handling for ML repositories")
    print("      - Extracts model/dataset-specific metadata")
    print("      - Content-addressed ML model storage")
    print()
    print("   4. SSHFS Backend")
    print("      - SSH-based remote storage backend")
    print("      - Connection pooling and management")
    print("      - Integration with VFS tier system")
    print()
    print("   5. Storage System Integration")
    print("      - Added SSHFS to backend type enumeration")
    print("      - Integrated with storage manager")
    print("      - Tier mapping for analytics")
    print()
    print("💡 Next Steps:")
    print("   - Set up SSH server for SSHFS testing")
    print("   - Clone real repositories for VFS translation")
    print("   - Configure storage backends via environment variables")
    print("   - Explore VFS snapshots and content addressing")

if __name__ == "__main__":
    anyio.run(main)
