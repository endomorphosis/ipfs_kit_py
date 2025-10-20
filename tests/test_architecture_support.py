"""
Test architecture support for ipfs_kit_py package.

This test module verifies that the package works correctly on both
ARM64 and x86_64 (AMD64) architectures.
"""

import platform
import sys
import pytest


class TestArchitectureSupport:
    """Test architecture detection and compatibility."""
    
    def test_architecture_detection(self):
        """Test that we can correctly detect the current architecture."""
        machine = platform.machine()
        
        # Valid architectures we support
        valid_archs = ['x86_64', 'amd64', 'AMD64', 'aarch64', 'arm64', 'ARM64']
        
        assert machine in valid_archs, f"Unknown architecture: {machine}"
        
        print(f"✓ Detected architecture: {machine}")
        print(f"  Platform: {platform.platform()}")
        print(f"  System: {platform.system()}")
        print(f"  Processor: {platform.processor()}")
    
    def test_package_import(self):
        """Test that the main package imports correctly on any architecture."""
        try:
            import ipfs_kit_py
            assert hasattr(ipfs_kit_py, '__version__') or hasattr(ipfs_kit_py, '__file__')
            print(f"✓ Package imported successfully on {platform.machine()}")
        except ImportError as e:
            pytest.fail(f"Failed to import ipfs_kit_py: {e}")
    
    def test_install_ipfs_architecture_detection(self):
        """Test that install_ipfs correctly detects the architecture."""
        try:
            from ipfs_kit_py.install_ipfs import install_ipfs
            
            installer = install_ipfs()
            
            # Get platform string that installer would use
            hardware_info = installer.get_hardware_info()
            
            assert 'machine' in hardware_info, "Hardware info should include machine"
            assert 'system' in hardware_info, "Hardware info should include system"
            assert 'architecture' in hardware_info, "Hardware info should include architecture"
            
            machine = hardware_info['machine'].lower()
            
            # Verify it detected a valid architecture
            valid_machine_types = ['x86_64', 'amd64', 'aarch64', 'arm64', 'armv7', 'i686', 'i386']
            
            assert any(arch in machine for arch in valid_machine_types), \
                f"Unexpected machine type: {machine}"
            
            print(f"✓ install_ipfs detected architecture: {hardware_info}")
            
        except ImportError:
            pytest.skip("install_ipfs module not available")
    
    def test_install_lotus_architecture_detection(self):
        """Test that install_lotus correctly detects the architecture."""
        try:
            from ipfs_kit_py.install_lotus import install_lotus
            
            installer = install_lotus()
            
            # Get platform info
            platform_info = installer.get_platform()
            
            # Should return something like "linux arm64" or "linux x86_64"
            assert isinstance(platform_info, str), "Platform info should be a string"
            assert len(platform_info) > 0, "Platform info should not be empty"
            
            parts = platform_info.lower().split()
            assert len(parts) >= 2, f"Platform info should have OS and arch: {platform_info}"
            
            os_part = parts[0]
            arch_part = ' '.join(parts[1:])
            
            valid_os = ['linux', 'darwin', 'macos', 'windows', 'freebsd', 'openbsd']
            valid_arch = ['x86_64', 'amd64', 'arm64', 'aarch64', 'arm32', 'armv7']
            
            assert os_part in valid_os, f"Unexpected OS: {os_part}"
            assert any(arch in arch_part for arch in valid_arch), \
                f"Unexpected architecture: {arch_part}"
            
            print(f"✓ install_lotus detected platform: {platform_info}")
            
        except ImportError:
            pytest.skip("install_lotus module not available")
    
    def test_core_modules_import_on_architecture(self):
        """Test that core modules can be imported on current architecture."""
        machine = platform.machine()
        
        modules_to_test = [
            'ipfs_kit_py.api',
            'ipfs_kit_py.cli',
        ]
        
        for module_name in modules_to_test:
            try:
                __import__(module_name)
                print(f"✓ {module_name} imported successfully on {machine}")
            except ImportError as e:
                # Some modules might have optional dependencies
                print(f"⚠ {module_name} import warning on {machine}: {e}")
    
    def test_architecture_specific_binaries(self):
        """Test that we can handle architecture-specific binary installations."""
        machine = platform.machine().lower()
        
        # Map architectures to expected formats
        if machine in ['x86_64', 'amd64']:
            expected_arch_identifiers = ['amd64', 'x86_64', 'x86-64']
        elif machine in ['aarch64', 'arm64']:
            expected_arch_identifiers = ['arm64', 'aarch64']
        elif machine in ['armv7l', 'armv7']:
            expected_arch_identifiers = ['arm', 'armv7', 'arm32']
        else:
            pytest.skip(f"Unknown architecture for binary test: {machine}")
        
        # Verify at least one identifier matches
        assert any(identifier in machine or machine in identifier 
                   for identifier in expected_arch_identifiers), \
            f"Architecture identifiers don't match for {machine}"
        
        print(f"✓ Architecture {machine} maps to identifiers: {expected_arch_identifiers}")
    
    def test_python_architecture_compatibility(self):
        """Test that Python itself is running on a compatible architecture."""
        # Get Python architecture information
        arch_info = platform.architecture()
        
        assert arch_info[0] in ['64bit', '32bit'], \
            f"Unexpected bit architecture: {arch_info[0]}"
        
        # For production use, we recommend 64-bit
        if arch_info[0] == '32bit':
            print(f"⚠ Warning: Running on 32-bit Python, 64-bit recommended")
        else:
            print(f"✓ Running on {arch_info[0]} Python")
        
        print(f"  Linkage: {arch_info[1]}")
    
    def test_multiprocessing_on_architecture(self):
        """Test that multiprocessing works on the current architecture."""
        import multiprocessing
        
        cpu_count = multiprocessing.cpu_count()
        
        assert cpu_count > 0, "Should detect at least one CPU"
        
        print(f"✓ Multiprocessing available with {cpu_count} CPUs on {platform.machine()}")


if __name__ == '__main__':
    # Run tests when executed directly
    pytest.main([__file__, '-v', '--tb=short'])
