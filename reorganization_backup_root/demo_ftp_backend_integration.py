#!/usr/bin/env python3
"""
Demo script showcasing FTP Backend integration with IPFS-Kit

This script demonstrates:
1. FTP Backend - FTP/FTPS remote storage capability
2. SSHFS + FTP comparison - Two VFS remote storage options
3. Configuration management for both backends
"""

import os
import sys
import asyncio
import tempfile
import json
from pathlib import Path

# Add the project directory to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from ipfs_kit_py.ftp_kit import FTPKit, validate_ftp_config, test_ftp_connection
    from ipfs_kit_py.sshfs_kit import SSHFSKit
    from ipfs_kit_py.config_manager import ConfigManager
    print("✅ Successfully imported FTP Kit, SSHFS Kit, and ConfigManager")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the correct directory")
    sys.exit(1)

async def demo_ftp_backend():
    """Demonstrate FTP backend functionality."""
    print("\n📁 === FTP Backend Demo ===")
    
    try:
        # Initialize FTP Kit with mock configuration
        ftp = FTPKit(
            host='ftp.example.com',
            username='testuser',
            password='testpass',
            port=21,
            use_tls=False,
            passive_mode=True,
            remote_base_path='/ipfs_kit_storage',
            connection_timeout=30
        )
        print(f"✅ FTP Kit initialized with host: ftp.example.com")
        
        # Test bucket organization
        test_bucket = "demo-bucket"
        test_file_hash = "QmTest123"
        remote_path = f"{ftp.remote_base_path}/{test_bucket}/{test_file_hash[:2]}/{test_file_hash}"
        print(f"📁 Remote path structure: {remote_path}")
        
        # Demo FTP operations
        print("📊 FTP Operations (simulated):")
        print(f"   - Connect to: {ftp.host}:{ftp.port}")
        print(f"   - Protocol: {'FTPS (FTP over TLS)' if ftp.use_tls else 'FTP'}")
        print(f"   - Mode: {'Passive' if ftp.passive_mode else 'Active'}")
        print(f"   - Remote base: {ftp.remote_base_path}")
        print(f"   - File operations: store_file(), retrieve_file(), delete_file()")
        print("   - Authentication: Username/password based")
        
        # Demo server info structure
        print("\n🔧 FTP Server Info Structure:")
        server_info_example = {
            "connected": False,
            "host": ftp.host,
            "port": ftp.port,
            "username": ftp.username,
            "tls": ftp.use_tls,
            "passive_mode": ftp.passive_mode,
            "features": ["EPSV", "EPRT", "SIZE", "MDTM"],
            "remote_base_path": ftp.remote_base_path
        }
        
        for key, value in server_info_example.items():
            print(f"   {key}: {value}")
        
    except Exception as e:
        print(f"❌ FTP demo error: {e}")

async def demo_backend_comparison():
    """Demonstrate comparison between SSHFS and FTP backends."""
    print("\n⚖️ === SSHFS vs FTP Backend Comparison ===")
    
    try:
        print("📊 Feature Comparison:")
        
        comparison_table = [
            ("Feature", "SSHFS", "FTP"),
            ("=" * 30, "=" * 15, "=" * 15),
            ("Protocol", "SSH/SCP", "FTP/FTPS"),
            ("Authentication", "SSH Keys/Password", "Username/Password"),
            ("Encryption", "SSH (Always)", "Optional (FTPS)"),
            ("Port", "22 (SSH)", "21 (FTP)"),
            ("Connection Modes", "N/A", "Active/Passive"),
            ("Directory Management", "Full POSIX", "Basic FTP commands"),
            ("Compression", "SSH compression", "None"),
            ("Security", "High (SSH)", "Medium (FTPS) / Low (FTP)"),
            ("Firewall Friendly", "Yes", "Passive mode only"),
            ("Use Cases", "Secure admin access", "Legacy systems, bulk transfer")
        ]
        
        for row in comparison_table:
            print(f"   {row[0]:<30} {row[1]:<15} {row[2]:<15}")
        
        print("\n🎯 When to use each:")
        print("   📡 SSHFS:")
        print("     - High security requirements")
        print("     - SSH infrastructure available")
        print("     - Administrative/development use")
        print("     - Need full filesystem operations")
        
        print("   📁 FTP:")
        print("     - Legacy systems integration")
        print("     - Bulk file transfers")
        print("     - Simple upload/download operations")
        print("     - Web hosting environments")
        
    except Exception as e:
        print(f"❌ Backend comparison error: {e}")

async def demo_config_integration():
    """Demonstrate configuration integration for both backends."""
    print("\n⚙️ === Configuration Integration Demo ===")
    
    try:
        # Initialize ConfigManager
        config_manager = ConfigManager()
        print("✅ ConfigManager initialized")
        
        # Show updated backend list (now 17 backends)
        available_backends = ['daemon', 's3', 'lotus', 'storacha', 'gdrive', 'synapse', 
                             'huggingface', 'github', 'ipfs_cluster', 'cluster_follow',
                             'parquet', 'arrow', 'sshfs', 'ftp', 'package', 'wal', 'fs_journal']
        
        print(f"📋 Available backends ({len(available_backends)}):")
        for i, backend in enumerate(available_backends, 1):
            prefix = "🆕" if backend in ["sshfs", "ftp"] else "  "
            print(f"   {i:2d}. {prefix} {backend}")
        
        # Show default FTP configuration
        print("\n🔧 Default FTP configuration:")
        ftp_defaults = {
            'host': None,
            'username': None,
            'password': None,
            'port': 21,
            'use_tls': False,
            'passive_mode': True,
            'remote_base_path': '/ipfs_kit_ftp',
            'connection_timeout': 30,
            'retry_attempts': 3,
            'verify_ssl': True
        }
        
        for key, value in ftp_defaults.items():
            print(f"   {key}: {value}")
        
        # Show default SSHFS configuration for comparison
        print("\n🔧 Default SSHFS configuration:")
        sshfs_defaults = {
            'host': None,
            'username': None,
            'port': 22,
            'key_path': None,
            'password': None,
            'remote_base_path': '/tmp/ipfs_kit_sshfs',
            'connection_timeout': 30,
            'retry_attempts': 3,
            'compression': True
        }
        
        for key, value in sshfs_defaults.items():
            print(f"   {key}: {value}")
            
        print("\n💡 CLI Integration:")
        print("   # FTP Configuration")
        print("   ipfs-kit config init --backend ftp")
        print("   ipfs-kit config show --backend ftp") 
        print("   ipfs-kit health check ftp")
        print("")
        print("   # SSHFS Configuration")
        print("   ipfs-kit config init --backend sshfs")
        print("   ipfs-kit config show --backend sshfs")
        print("   ipfs-kit health check sshfs")
        
    except Exception as e:
        print(f"❌ Config integration demo error: {e}")

async def demo_validation_and_testing():
    """Demonstrate configuration validation and connection testing."""
    print("\n🧪 === Validation and Testing Demo ===")
    
    try:
        # Test FTP config validation
        print("🔧 FTP Configuration Validation:")
        
        # Valid config
        valid_ftp_config = {
            'host': 'ftp.example.com',
            'username': 'testuser',
            'password': 'testpass',
            'port': 21,
            'use_tls': False
        }
        
        is_valid = validate_ftp_config(valid_ftp_config)
        print(f"   Valid config: {'✅ PASS' if is_valid else '❌ FAIL'}")
        
        # Invalid config (missing required fields)
        invalid_ftp_config = {
            'host': 'ftp.example.com',
            # Missing username and password
            'port': 21
        }
        
        is_invalid = validate_ftp_config(invalid_ftp_config)
        print(f"   Invalid config: {'❌ FAIL' if not is_invalid else '✅ UNEXPECTED PASS'}")
        
        # Test connection (simulated)
        print("\n🔌 FTP Connection Test (simulated):")
        test_result = test_ftp_connection(valid_ftp_config)
        print(f"   Connection test: {test_result}")
        
        print("\n📊 FTP vs SSHFS Testing:")
        print("   FTP Testing:")
        print("     - validate_ftp_config() - Configuration validation")
        print("     - test_ftp_connection() - Connection testing")
        print("     - FTPKit.get_server_info() - Server capabilities")
        
        print("   SSHFS Testing:")  
        print("     - SSH key validation")
        print("     - Connection timeout testing")
        print("     - Remote directory accessibility")
        
    except Exception as e:
        print(f"❌ Validation demo error: {e}")

async def demo_combined_workflow():
    """Demonstrate combined FTP + SSHFS + VFS workflow."""
    print("\n🔄 === Combined Remote Storage Workflow ===")
    
    try:
        print("🔄 Multi-Backend VFS Storage Workflow:")
        print("1. 📥 Initialize both FTP and SSHFS backends")
        print("2. 🗂️ Create VFS buckets for different data types")
        print("3. 📁 Route data based on security requirements:")
        print("   - High-security data → SSHFS (SSH encryption)")
        print("   - Bulk transfers → FTP (high throughput)")
        print("   - Public data → FTP (simple access)")
        print("4. 🔄 Implement failover between backends")
        print("5. 📊 Monitor storage across both systems")
        
        print("\n🎯 Example Use Cases:")
        print("   📡 SSHFS Storage:")
        print("     - Configuration backups")
        print("     - Private keys and certificates")
        print("     - Development code repositories")
        print("     - Administrative logs")
        
        print("   📁 FTP Storage:")
        print("     - Public dataset distributions")
        print("     - Media file archives")
        print("     - Temporary file exchanges")
        print("     - Legacy system integration")
        
        print("\n🚀 Advanced Features:")
        print("   - Content-addressed storage on both backends")
        print("   - Automatic backend selection based on file type")
        print("   - Load balancing between FTP and SSHFS")
        print("   - Encryption at rest for FTP storage")
        print("   - Unified VFS interface for both backends")
        
    except Exception as e:
        print(f"❌ Combined workflow demo error: {e}")

async def main():
    """Run all demos."""
    print("🚀 IPFS-Kit FTP Backend Integration Demo")
    print("=" * 50)
    
    await demo_ftp_backend()
    await demo_backend_comparison()
    await demo_config_integration()
    await demo_validation_and_testing()
    await demo_combined_workflow()
    
    print("\n✨ Demo completed successfully!")
    print("\nNext steps:")
    print("1. Configure FTP backend: ipfs-kit config init --backend ftp")
    print("2. Test FTP connection with real server")
    print("3. Compare FTP vs SSHFS performance for your use case")
    print("4. Set up multi-backend VFS storage strategy")
    print("5. Implement failover between FTP and SSHFS backends")

if __name__ == "__main__":
    asyncio.run(main())
