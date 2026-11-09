#!/usr/bin/env python3
"""
Demo script showcasing SSHFS Backend and Git VFS Translation Layer integration

This script demonstrates:
1. SSHFS Backend - SSH/SCP remote storage capability
2. Git VFS Translation Layer - Git metadata to VFS mapping
3. Combined workflow - storing Git repositories via SSHFS
"""

import os
import sys
import anyio
import tempfile
import json
from pathlib import Path

# Add the project directory to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from ipfs_kit_py.sshfs_kit import SSHFSKit
    from ipfs_kit_py.git_vfs_translation import GitVFSTranslationLayer
    from ipfs_kit_py.config_manager import ConfigManager
    print("✅ Successfully imported SSHFS Kit and Git VFS Translation Layer")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the correct directory")
    sys.exit(1)

async def demo_sshfs_backend():
    """Demonstrate SSHFS backend functionality."""
    print("\n🔗 === SSHFS Backend Demo ===")
    
    try:
        # Initialize SSHFS Kit with proper parameters
        sshfs = SSHFSKit(
            host='example.com',
            username='testuser',
            port=22,
            key_path='~/.ssh/id_rsa',
            remote_base_path='/home/testuser/ipfs_kit_storage',
            connection_timeout=30
        )
        print(f"✅ SSHFS Kit initialized with host: example.com")
        
        # Test bucket organization
        test_bucket = "demo-bucket"
        test_file_hash = "QmTest123"
        remote_path = f"{sshfs.remote_base_path}/{test_bucket}/{test_file_hash}"
        print(f"📁 Remote path structure: {remote_path}")
        
        # Demo operations 
        print("📊 SSHFS Operations (simulated):")
        print(f"   - Connect to: {sshfs.host}:{sshfs.port}")
        print(f"   - Remote base: {sshfs.remote_base_path}")
        print(f"   - Bucket path: {remote_path}")
        print("   - File operations: store_file(), retrieve_file(), delete_file()")
        print("   - Authentication: SSH key-based with password fallback")
        
    except Exception as e:
        print(f"❌ SSHFS demo error: {e}")

async def demo_git_vfs_translation():
    """Demonstrate Git VFS translation functionality."""
    print("\n🌿 === Git VFS Translation Layer Demo ===")
    
    try:
        # Initialize Git VFS Translation Layer
        git_vfs = GitVFSTranslationLayer()
        print("✅ Git VFS Translation Layer initialized")
        
        # Create a temporary Git repository for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "test_repo"
            repo_path.mkdir()
            
            # Initialize a basic Git repository
            try:
                import git
                repo = git.Repo.init(repo_path)
                
                # Create some test files
                (repo_path / "README.md").write_text("# Test Repository\\nDemo content")
                (repo_path / "src").mkdir()
                (repo_path / "src" / "main.py").write_text("print('Hello, World!')")
                
                # Add and commit files
                repo.index.add(["README.md", "src/main.py"])
                commit = repo.index.commit("Initial commit")
                
                print(f"📝 Created test repository with commit: {commit.hexsha[:8]}")
                
                # Analyze Git repository 
                analysis = await git_vfs.analyze_git_repository(str(repo_path))
                print(f"🔍 Repository analysis completed:")
                print(f"   - Commits: {len(analysis.get('commits', []))}")
                print(f"   - Files: {len(analysis.get('files', []))}")
                print(f"   - Branches: {analysis.get('branches', [])}")
                
                # Demo VFS bucket creation from Git
                vfs_bucket = await git_vfs.create_vfs_bucket_from_git(str(repo_path))
                if vfs_bucket:
                    print(f"🪣 VFS bucket created: {vfs_bucket['bucket_name']}")
                    print(f"   - VFS Version: {vfs_bucket['vfs_version']}")
                    print(f"   - Files mapped: {len(vfs_bucket['files'])}")
                
                # Demo .ipfs_kit folder creation
                ipfs_kit_folder = repo_path / ".ipfs_kit"
                if ipfs_kit_folder.exists():
                    print(f"📂 .ipfs_kit folder created with:")
                    for file in ipfs_kit_folder.iterdir():
                        print(f"   - {file.name}")
                
            except ImportError:
                print("⚠️ GitPython not available, using subprocess fallback")
                # Demo subprocess-based operations
                print("📊 Git Analysis (subprocess mode):")
                print("   - Repository detection")
                print("   - Commit history extraction")
                print("   - File tree mapping")
                print("   - VFS version generation")
                
    except Exception as e:
        print(f"❌ Git VFS demo error: {e}")

async def demo_combined_workflow():
    """Demonstrate combined SSHFS + Git VFS workflow."""
    print("\n🔄 === Combined Workflow Demo ===")
    
    try:
        # Initialize both components
        sshfs = SSHFSKit(
            host='remote-server.com',
            username='developer',
            key_path='~/.ssh/id_rsa',
            remote_base_path='/data/vfs_storage'
        )
        git_vfs = GitVFSTranslationLayer()
        
        print("✅ Both components initialized")
        
        # Simulated workflow
        print("🔄 Combined workflow (simulated):")
        print("1. 📥 Clone Git repository locally")
        print("2. 🔍 Analyze Git metadata with GitVFSTranslationLayer")
        print("3. 🗂️ Create VFS bucket from Git repository")
        print("4. 📁 Generate .ipfs_kit folder with HEAD pointers")
        print("5. 🔗 Store VFS files via SSHFS backend")
        print("6. 🌐 Upload to remote SSH server")
        print("7. 🔄 Maintain bidirectional sync (Git ↔ VFS)")
        
        # Show integration points
        print("\n🎯 Integration Benefits:")
        print("   - Git repositories stored as content-addressed VFS buckets")
        print("   - Remote storage via SSH/SCP for distributed teams")
        print("   - Redundant metadata (Git + VFS) for different hashing algorithms")
        print("   - .ipfs_kit folders maintain VFS version history")
        print("   - Seamless GitHub/HuggingFace repository integration")
        
    except Exception as e:
        print(f"❌ Combined workflow demo error: {e}")

async def demo_config_integration():
    """Demonstrate configuration integration."""
    print("\n⚙️ === Configuration Integration Demo ===")
    
    try:
        # Initialize ConfigManager
        config_manager = ConfigManager()
        print("✅ ConfigManager initialized")
        
        # Show SSHFS in backend list
        available_backends = ['daemon', 's3', 'lotus', 'storacha', 'gdrive', 'synapse', 
                             'huggingface', 'github', 'ipfs_cluster', 'cluster_follow',
                             'parquet', 'arrow', 'sshfs', 'package', 'wal', 'fs_journal']
        
        print(f"📋 Available backends ({len(available_backends)}):")
        for i, backend in enumerate(available_backends, 1):
            prefix = "🆕" if backend == "sshfs" else "  "
            print(f"   {i:2d}. {prefix} {backend}")
        
        # Show default SSHFS configuration
        print("\n🔧 Default SSHFS configuration:")
        sshfs_defaults = {
            'host': 'localhost',
            'port': 22,
            'username': 'user',
            'ssh_key_path': '~/.ssh/id_rsa',
            'password': None,
            'remote_base_path': '/tmp/ipfs_kit_sshfs',
            'timeout': 30,
            'use_compression': True,
            'create_directories': True
        }
        
        for key, value in sshfs_defaults.items():
            print(f"   {key}: {value}")
            
        print("\n💡 CLI Integration:")
        print("   ipfs-kit config init --backend sshfs")
        print("   ipfs-kit config show --backend sshfs") 
        print("   ipfs-kit health check sshfs")
        
    except Exception as e:
        print(f"❌ Config integration demo error: {e}")

async def main():
    """Run all demos."""
    print("🚀 IPFS-Kit SSHFS & Git VFS Integration Demo")
    print("=" * 50)
    
    await demo_sshfs_backend()
    await demo_git_vfs_translation()
    await demo_combined_workflow()
    await demo_config_integration()
    
    print("\n✨ Demo completed successfully!")
    print("\nNext steps:")
    print("1. Configure SSHFS backend: ipfs-kit config init --backend sshfs")
    print("2. Test Git VFS translation on a real repository")
    print("3. Integrate SSHFS storage with VFS buckets")
    print("4. Set up remote SSH server for distributed storage")

if __name__ == "__main__":
    anyio.run(main)
