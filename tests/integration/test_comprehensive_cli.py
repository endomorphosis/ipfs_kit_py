#!/usr/bin/env python3
"""
Comprehensive CLI Configuration Testing

This script demonstrates and tests the enhanced configuration management
system with real YAML persistence and interactive setup.
"""

import anyio
import subprocess
import sys
from pathlib import Path


async def test_config_system():
    """Test the comprehensive configuration system."""
    print("🧪 Testing Enhanced Configuration System")
    print("=" * 50)
    
    # Test 1: Initialize configuration directory
    print("\n1️⃣ Testing configuration initialization...")
    result = subprocess.run([
        sys.executable, '-m', 'ipfs_kit_py.cli', 
        'config', 'init', '--backend', 'daemon', '--non-interactive'
    ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    
    print(f"Exit code: {result.returncode}")
    print(f"Output: {result.stdout}")
    if result.stderr:
        print(f"Errors: {result.stderr}")
    
    # Test 2: Set configuration values
    print("\n2️⃣ Testing configuration value setting...")
    test_configs = [
        ('daemon.port', '9999'),
        ('daemon.role', 'local'),
        ('daemon.max_workers', '4'),
        ('s3.region', 'us-west-2'),
        ('s3.use_ssl', 'true'),
        ('lotus.node_url', 'http://localhost:1234/rpc/v1'),
        ('package.version', '0.2.8')
    ]
    
    for key, value in test_configs:
        print(f"\n   Setting {key} = {value}")
        result = subprocess.run([
            sys.executable, '-m', 'ipfs_kit_py.cli',
            'config', 'set', key, value
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        
        if result.returncode == 0:
            print(f"   ✅ Success")
        else:
            print(f"   ❌ Failed: {result.stderr}")
    
    # Test 3: Show configuration
    print("\n3️⃣ Testing configuration display...")
    result = subprocess.run([
        sys.executable, '-m', 'ipfs_kit_py.cli',
        'config', 'show'
    ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    
    print(f"Exit code: {result.returncode}")
    print(f"Configuration display:")
    print(result.stdout)
    if result.stderr:
        print(f"Errors: {result.stderr}")
    
    # Test 4: Validate configuration
    print("\n4️⃣ Testing configuration validation...")
    result = subprocess.run([
        sys.executable, '-m', 'ipfs_kit_py.cli',
        'config', 'validate'
    ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    
    print(f"Exit code: {result.returncode}")
    print(f"Validation results:")
    print(result.stdout)
    if result.stderr:
        print(f"Errors: {result.stderr}")
    
    # Test 5: Backup configuration
    print("\n5️⃣ Testing configuration backup...")
    result = subprocess.run([
        sys.executable, '-m', 'ipfs_kit_py.cli',
        'config', 'backup'
    ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    
    print(f"Exit code: {result.returncode}")
    print(f"Backup results:")
    print(result.stdout)
    if result.stderr:
        print(f"Errors: {result.stderr}")
    
    # Test 6: Test individual backend configuration views
    print("\n6️⃣ Testing individual backend views...")
    backends = ['daemon', 's3', 'lotus']
    
    for backend in backends:
        print(f"\n   Testing {backend} configuration view...")
        result = subprocess.run([
            sys.executable, '-m', 'ipfs_kit_py.cli',
            'config', 'show', '--backend', backend
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        
        if result.returncode == 0:
            print(f"   ✅ {backend} config displayed successfully")
            # Show first few lines of output
            lines = result.stdout.split('\n')[:5]
            for line in lines:
                if line.strip():
                    print(f"      {line}")
        else:
            print(f"   ❌ Failed to show {backend} config: {result.stderr}")


async def test_real_data_commands():
    """Test that CLI commands return real data, not mocked responses."""
    print("\n🔍 Testing Real Data vs Mocked Responses")
    print("=" * 50)
    
    # Test commands that should return real data
    test_commands = [
        (['daemon', 'status'], "Daemon status check"),
        (['pin', 'list', '--limit', '5'], "Pin listing"),
        (['bucket', 'list'], "Bucket listing"),
        (['health', 'check'], "Health check"),
        (['config', 'show'], "Configuration display"),
        (['backend', 'list'], "Backend listing")
    ]
    
    for cmd_args, description in test_commands:
        print(f"\n🧪 Testing: {description}")
        print(f"   Command: ipfs-kit {' '.join(cmd_args)}")
        
        result = subprocess.run([
            sys.executable, '-m', 'ipfs_kit_py.cli'
        ] + cmd_args, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        
        print(f"   Exit code: {result.returncode}")
        
        # Analyze output for indicators of real vs mocked data
        output = result.stdout.lower()
        
        real_data_indicators = [
            '~/.ipfs_kit/',
            'parquet',
            'yaml',
            'configuration directory',
            'real',
            'actual'
        ]
        
        mock_data_indicators = [
            'mock',
            'simulated',
            'placeholder',
            'example',
            'fake',
            'dummy'
        ]
        
        real_count = sum(1 for indicator in real_data_indicators if indicator in output)
        mock_count = sum(1 for indicator in mock_data_indicators if indicator in output)
        
        if real_count > mock_count:
            print(f"   ✅ Appears to use real data ({real_count} real indicators)")
        elif mock_count > 0:
            print(f"   ⚠️  May use mocked data ({mock_count} mock indicators)")
        else:
            print(f"   ℹ️  Unable to determine data source")
        
        # Show a sample of output
        if result.stdout:
            lines = result.stdout.split('\n')[:3]
            for line in lines:
                if line.strip():
                    print(f"      Sample: {line[:80]}{'...' if len(line) > 80 else ''}")


async def test_storage_backend_configuration():
    """Test storage backend configuration capabilities."""
    print("\n🔧 Testing Storage Backend Configuration")
    print("=" * 50)
    
    # Test initializing different backends
    backends = ['s3', 'lotus', 'storacha', 'gdrive', 'synapse', 'huggingface']
    
    for backend in backends:
        print(f"\n🔧 Testing {backend} backend initialization...")
        
        result = subprocess.run([
            sys.executable, '-m', 'ipfs_kit_py.cli',
            'config', 'init', '--backend', backend, '--non-interactive'
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        
        if result.returncode == 0:
            print(f"   ✅ {backend} initialized successfully")
        else:
            print(f"   ⚠️  {backend} initialization: {result.stderr.strip()}")
    
    # Test setting backend-specific values
    print(f"\n🔧 Testing backend-specific configuration...")
    
    backend_configs = [
        ('s3.bucket_name', 'test-bucket'),
        ('s3.access_key_id', 'test-key'),
        ('lotus.deal_duration', '518400'),
        ('storacha.chunk_size', '2097152'),
        ('gdrive.folder_id', 'test-folder-id'),
        ('huggingface.default_org', 'test-org')
    ]
    
    for key, value in backend_configs:
        result = subprocess.run([
            sys.executable, '-m', 'ipfs_kit_py.cli',
            'config', 'set', key, value
        ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        
        if result.returncode == 0:
            print(f"   ✅ Set {key} = {value}")
        else:
            print(f"   ❌ Failed to set {key}: {result.stderr.strip()}")


async def test_enhanced_vfs_extractor():
    """Test the enhanced VFS extractor functionality."""
    print("\n📦 Testing Enhanced VFS Extractor")
    print("=" * 50)
    
    # Test the download-vfs command
    print("🧪 Testing download-vfs command...")
    
    result = subprocess.run([
        sys.executable, '-m', 'ipfs_kit_py.cli',
        'bucket', 'download-vfs', '--help'
    ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    
    if result.returncode == 0:
        print("✅ download-vfs command is available")
        print("   Help output preview:")
        lines = result.stdout.split('\n')[:10]
        for line in lines:
            if line.strip():
                print(f"      {line}")
    else:
        print(f"❌ download-vfs command not available: {result.stderr}")
    
    # Test listing VFS sources
    print("\n🧪 Testing VFS source detection...")
    
    result = subprocess.run([
        sys.executable, '-c', '''
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from ipfs_kit_py.enhanced_vfs_extractor import EnhancedIPFSVFSExtractor

extractor = EnhancedIPFSVFSExtractor()
print("📊 Available VFS backends:")
for backend_id, backend_info in extractor.vfs_backends.items():
    print(f"   🔧 {backend_id}: {backend_info['name']}")
    print(f"      Priority: {backend_info['priority']}")
    print(f"      Enabled: {backend_info['enabled']}")
'''
    ], capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    
    if result.returncode == 0:
        print("✅ VFS extractor loaded successfully")
        print(result.stdout)
    else:
        print(f"❌ VFS extractor failed: {result.stderr}")


async def main():
    """Run comprehensive CLI testing."""
    print("🚀 Comprehensive IPFS-Kit CLI Testing")
    print("=" * 60)
    
    try:
        await test_config_system()
        await test_real_data_commands()
        await test_storage_backend_configuration()
        await test_enhanced_vfs_extractor()
        
        print("\n🎯 Testing Summary")
        print("=" * 50)
        print("✅ Configuration system tests completed")
        print("✅ Real data verification completed")
        print("✅ Storage backend tests completed")
        print("✅ Enhanced VFS extractor tests completed")
        print("\n📂 Check ~/.ipfs_kit/ for generated configuration files")
        print("🔍 Review output above for any issues or mock data indicators")
        
    except Exception as e:
        print(f"❌ Testing failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    anyio.run(main)
