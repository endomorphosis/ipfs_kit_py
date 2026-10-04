"""
Test suite for Phase 3: CAR File Support implementation.

This module tests the CAR Manager and file format handling.
"""

import pytest
import os
import tempfile
from pathlib import Path
from ipfs_kit_py.mcp.storage_manager.formats import CARManager


class TestCARManager:
    """Test CAR Manager implementation."""
    
    def test_initialization(self):
        """Test CAR manager initialization."""
        manager = CARManager()
        
        assert manager is not None
        assert manager.codec == "dag-pb"
    
    def test_initialization_custom_codec(self):
        """Test initialization with custom codec."""
        manager = CARManager(codec="dag-cbor")
        
        assert manager.codec == "dag-cbor"
    
    def test_create_car_from_file(self):
        """Test creating CAR file from a single file."""
        manager = CARManager()
        
        # Create temporary test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Test content for CAR file")
            test_file = f.name
        
        try:
            # Create CAR file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.car') as car_f:
                car_file = car_f.name
            
            result = manager.create_car(test_file, car_file)
            
            assert result["success"] is True
            assert "cid" in result
            assert result["blocks"] >= 1
            assert result["version"] == 1
            assert os.path.exists(car_file)
            
        finally:
            # Cleanup
            os.unlink(test_file)
            if os.path.exists(car_file):
                os.unlink(car_file)
    
    def test_create_car_from_directory(self):
        """Test creating CAR file from a directory."""
        manager = CARManager()
        
        # Create temporary directory with files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            for i in range(3):
                file_path = os.path.join(temp_dir, f"file{i}.txt")
                with open(file_path, 'w') as f:
                    f.write(f"Content of file {i}")
            
            # Create CAR file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.car') as car_f:
                car_file = car_f.name
            
            try:
                result = manager.create_car(temp_dir, car_file)
                
                assert result["success"] is True
                assert "cid" in result
                assert result["blocks"] >= 3  # At least one block per file
                assert os.path.exists(car_file)
                
            finally:
                if os.path.exists(car_file):
                    os.unlink(car_file)
    
    def test_extract_car(self):
        """Test extracting CAR file."""
        manager = CARManager()
        
        # Create a test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Test extraction content")
            test_file = f.name
        
        try:
            # Create CAR file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.car') as car_f:
                car_file = car_f.name
            
            create_result = manager.create_car(test_file, car_file)
            assert create_result["success"] is True
            
            # Extract CAR file
            with tempfile.TemporaryDirectory() as extract_dir:
                extract_result = manager.extract_car(car_file, extract_dir)
                
                assert extract_result["success"] is True
                assert extract_result["blocks_extracted"] >= 1
                assert extract_result["files_created"] >= 1
                
                # Check extracted files exist
                extracted_files = list(Path(extract_dir).glob('*.block'))
                assert len(extracted_files) >= 1
            
        finally:
            os.unlink(test_file)
            if os.path.exists(car_file):
                os.unlink(car_file)
    
    def test_verify_car(self):
        """Test verifying CAR file integrity."""
        manager = CARManager()
        
        # Create test file and CAR
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Test verification content")
            test_file = f.name
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.car') as car_f:
                car_file = car_f.name
            
            create_result = manager.create_car(test_file, car_file)
            assert create_result["success"] is True
            
            # Verify CAR file
            verify_result = manager.verify_car(car_file)
            
            assert verify_result["success"] is True
            assert verify_result["valid"] is True
            assert verify_result["blocks"] >= 1
            assert len(verify_result["errors"]) == 0
            
        finally:
            os.unlink(test_file)
            if os.path.exists(car_file):
                os.unlink(car_file)
    
    def test_get_info(self):
        """Test getting CAR file information."""
        manager = CARManager()
        
        # Create test file and CAR
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Test info content")
            test_file = f.name
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.car') as car_f:
                car_file = car_f.name
            
            create_result = manager.create_car(test_file, car_file)
            assert create_result["success"] is True
            
            # Get CAR info
            info_result = manager.get_info(car_file)
            
            assert info_result["success"] is True
            assert info_result["version"] == 1
            assert "roots" in info_result
            assert info_result["blocks"] >= 1
            assert info_result["file_size"] > 0
            
        finally:
            os.unlink(test_file)
            if os.path.exists(car_file):
                os.unlink(car_file)
    
    def test_create_car_nonexistent_path(self):
        """Test creating CAR from nonexistent path."""
        manager = CARManager()
        
        result = manager.create_car("/nonexistent/path", "/tmp/test.car")
        
        assert result["success"] is False
        assert "error" in result
    
    def test_extract_car_nonexistent(self):
        """Test extracting nonexistent CAR file."""
        manager = CARManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = manager.extract_car("/nonexistent.car", temp_dir)
            
            assert result["success"] is False
            assert "error" in result
    
    def test_verify_car_nonexistent(self):
        """Test verifying nonexistent CAR file."""
        manager = CARManager()
        
        result = manager.verify_car("/nonexistent.car")
        
        assert result["success"] is False
        assert "error" in result
    
    def test_get_info_nonexistent(self):
        """Test getting info for nonexistent CAR file."""
        manager = CARManager()
        
        result = manager.get_info("/nonexistent.car")
        
        assert result["success"] is False
        assert "error" in result


class TestCARManagerIntegration:
    """Integration tests for CAR Manager."""
    
    @pytest.mark.integration
    def test_roundtrip(self):
        """Test create -> extract -> verify roundtrip."""
        manager = CARManager()
        
        # Create test directory with multiple files
        with tempfile.TemporaryDirectory() as source_dir:
            # Create test files
            test_files = []
            for i in range(3):
                file_path = os.path.join(source_dir, f"test{i}.txt")
                with open(file_path, 'w') as f:
                    f.write(f"Test content {i}" * 100)  # Make it substantial
                test_files.append(file_path)
            
            # Create CAR file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.car') as car_f:
                car_file = car_f.name
            
            try:
                # Step 1: Create CAR
                create_result = manager.create_car(source_dir, car_file)
                assert create_result["success"] is True
                
                # Step 2: Verify CAR
                verify_result = manager.verify_car(car_file)
                assert verify_result["success"] is True
                assert verify_result["valid"] is True
                
                # Step 3: Extract CAR
                with tempfile.TemporaryDirectory() as extract_dir:
                    extract_result = manager.extract_car(car_file, extract_dir, verify=True)
                    assert extract_result["success"] is True
                    
                    # Verify extracted files exist
                    extracted_files = list(Path(extract_dir).glob('*.block'))
                    assert len(extracted_files) >= 3
                
            finally:
                if os.path.exists(car_file):
                    os.unlink(car_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-k", "not integration"])
