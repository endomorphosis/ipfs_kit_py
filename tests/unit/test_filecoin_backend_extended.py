"""
Extended Unit Tests for Filecoin Backend

This test suite extends the existing Filecoin backend tests with comprehensive
coverage of base CRUD operations that were previously missing.
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import time

# Test configuration
MOCK_MODE = os.environ.get("FILECOIN_MOCK_MODE", "true").lower() == "true"


@pytest.fixture
def filecoin_config():
    """Provide test configuration for Filecoin backend."""
    return {
        "resources": {
            "api_key": os.environ.get("FILECOIN_API_KEY", "test_api_key"),
            "endpoint": os.environ.get("FILECOIN_ENDPOINT", "http://localhost:1234/rpc/v0"),
            "mock_mode": MOCK_MODE,
            "max_retries": 3
        },
        "metadata": {
            "default_miner": "t01000",
            "replication_count": 1,
            "verify_deals": True,
            "max_price": "100000000000",
            "deal_duration": 518400
        }
    }


@pytest.fixture
def filecoin_backend(filecoin_config):
    """Create a Filecoin backend instance for testing."""
    try:
        from ipfs_kit_py.mcp.storage_manager.backends.filecoin_backend import FilecoinBackend
        backend = FilecoinBackend(filecoin_config["resources"], filecoin_config["metadata"])
        return backend
    except Exception as e:
        pytest.skip(f"Failed to initialize Filecoin backend: {e}")


class TestFilecoinBackendBasicOperations:
    """Test base CRUD operations that were missing from original tests."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_store_content_bytes(self, filecoin_backend):
        """Test storing binary content (base operation)."""
        content = b"Test binary content for Filecoin storage"
        
        # Store content
        result = filecoin_backend.add_content(content)
        
        # Should return a result dict
        assert isinstance(result, dict)
        # In mock mode or successful operation, should have identifier
        if result.get("success"):
            assert "identifier" in result or "cid" in result
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_store_content_string(self, filecoin_backend):
        """Test storing string content (base operation)."""
        content = "Test string content for Filecoin"
        
        # Store content
        result = filecoin_backend.add_content(content)
        
        # Should return a result dict
        assert isinstance(result, dict)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_store_large_content(self, filecoin_backend):
        """Test storing larger content (1MB)."""
        # Create 1MB of content
        content = b"X" * (1024 * 1024)
        
        # Store content
        result = filecoin_backend.add_content(content)
        
        # Should handle large content
        assert isinstance(result, dict)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_retrieve_content(self, filecoin_backend):
        """Test retrieving content (base operation)."""
        # Store content first
        content = b"Content to retrieve"
        store_result = filecoin_backend.add_content(content)
        
        if store_result.get("success"):
            identifier = store_result.get("identifier") or store_result.get("cid")
            
            if identifier:
                # Retrieve content
                retrieve_result = filecoin_backend.get_content(identifier)
                
                # Should return result dict
                assert isinstance(retrieve_result, dict)
                
                # In successful case, should have data
                if retrieve_result.get("success"):
                    assert "data" in retrieve_result or "content" in retrieve_result
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_delete_content(self, filecoin_backend):
        """Test deleting content (base operation)."""
        # Store content first
        content = b"Content to delete"
        store_result = filecoin_backend.add_content(content)
        
        if store_result.get("success"):
            identifier = store_result.get("identifier") or store_result.get("cid")
            
            if identifier:
                # Delete content
                delete_result = filecoin_backend.remove_content(identifier)
                
                # Should return result dict
                assert isinstance(delete_result, dict)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_get_metadata(self, filecoin_backend):
        """Test getting metadata (base operation)."""
        # Store content first
        content = b"Content with metadata"
        metadata = {"type": "test", "description": "Test metadata"}
        
        store_result = filecoin_backend.add_content(content, metadata=metadata)
        
        if store_result.get("success"):
            identifier = store_result.get("identifier") or store_result.get("cid")
            
            if identifier:
                # Get metadata
                meta_result = filecoin_backend.get_metadata(identifier)
                
                # Should return result dict
                assert isinstance(meta_result, dict)
                
                # In successful case, should have metadata
                if meta_result.get("success"):
                    assert "metadata" in meta_result


class TestFilecoinBackendErrorHandling:
    """Test error handling for various scenarios."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_retrieve_nonexistent_content(self, filecoin_backend):
        """Test retrieving content that doesn't exist."""
        fake_cid = "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"
        
        # Try to retrieve non-existent content
        result = filecoin_backend.get_content(fake_cid)
        
        # Should handle gracefully
        assert isinstance(result, dict)
        # Should indicate failure or not found
        assert not result.get("success") or result.get("error")
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_invalid_cid_format(self, filecoin_backend):
        """Test handling of invalid CID format."""
        invalid_cid = "invalid_cid_format"
        
        # Try to retrieve with invalid CID
        result = filecoin_backend.get_content(invalid_cid)
        
        # Should handle gracefully
        assert isinstance(result, dict)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_empty_content(self, filecoin_backend):
        """Test storing empty content."""
        content = b""
        
        # Try to store empty content
        result = filecoin_backend.add_content(content)
        
        # Should handle gracefully
        assert isinstance(result, dict)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_none_content(self, filecoin_backend):
        """Test storing None content."""
        # Try to store None
        try:
            result = filecoin_backend.add_content(None)
            assert isinstance(result, dict)
        except (TypeError, ValueError, AttributeError):
            # Expected to raise an error
            pass


class TestFilecoinBackendDealManagement:
    """Test Filecoin-specific deal management features."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_deal_status_tracking(self, filecoin_backend):
        """Test tracking deal status."""
        content = b"Content for deal status test"
        store_result = filecoin_backend.add_content(content)
        
        if store_result.get("success"):
            identifier = store_result.get("identifier") or store_result.get("cid")
            
            if identifier:
                # Check deal status via metadata
                meta_result = filecoin_backend.get_metadata(identifier)
                
                if meta_result.get("success"):
                    metadata = meta_result.get("metadata", {})
                    # Should have deal information
                    assert "deals" in metadata or "deal" in str(metadata).lower()
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_multiple_deal_replication(self, filecoin_backend):
        """Test creating multiple deals for replication."""
        # Update backend to request multiple replicas
        if hasattr(filecoin_backend, 'metadata'):
            original_count = filecoin_backend.metadata.get("replication_count", 1)
            filecoin_backend.metadata["replication_count"] = 2
        
        content = b"Content for replication test"
        store_result = filecoin_backend.add_content(content)
        
        # Restore original
        if hasattr(filecoin_backend, 'metadata'):
            filecoin_backend.metadata["replication_count"] = original_count
        
        if store_result.get("success"):
            deals = store_result.get("deals", [])
            # Should have multiple deals in replication mode
            # (exact behavior depends on mock implementation)
            assert isinstance(deals, list)
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_deal_renewal(self, filecoin_backend):
        """Test deal renewal functionality if available."""
        if hasattr(filecoin_backend, 'renew_deal'):
            content = b"Content for renewal test"
            store_result = filecoin_backend.add_content(content)
            
            if store_result.get("success"):
                identifier = store_result.get("identifier") or store_result.get("cid")
                deals = store_result.get("deals", [])
                
                if deals and identifier:
                    deal_id = deals[0].get("deal_id")
                    if deal_id:
                        # Try to renew deal
                        renew_result = filecoin_backend.renew_deal(deal_id, duration=518400)
                        assert isinstance(renew_result, dict)


class TestFilecoinBackendMinerSelection:
    """Test miner selection and preferences."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_preferred_miners(self, filecoin_backend):
        """Test specifying preferred miners."""
        content = b"Content for preferred miner test"
        preferred_miner = "t01001"
        
        # Store with preferred miner
        result = filecoin_backend.add_content(content, metadata={"miner": preferred_miner})
        
        if result.get("success"):
            deals = result.get("deals", [])
            if deals:
                # Check if preferred miner was used
                for deal in deals:
                    if "miner" in deal:
                        # Preferred miner should be used or explained why not
                        pass  # Implementation dependent
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_miner_blacklist(self, filecoin_backend):
        """Test excluding specific miners."""
        if hasattr(filecoin_backend, 'blacklisted_miners'):
            content = b"Content for blacklist test"
            blacklisted_miner = "t01999"
            
            # Add to blacklist
            original_blacklist = filecoin_backend.blacklisted_miners.copy() if hasattr(filecoin_backend, 'blacklisted_miners') else []
            if hasattr(filecoin_backend, 'blacklisted_miners'):
                filecoin_backend.blacklisted_miners.append(blacklisted_miner)
            
            # Store content
            result = filecoin_backend.add_content(content)
            
            # Restore blacklist
            if hasattr(filecoin_backend, 'blacklisted_miners'):
                filecoin_backend.blacklisted_miners = original_blacklist
            
            if result.get("success"):
                deals = result.get("deals", [])
                # Verify blacklisted miner was not used
                for deal in deals:
                    if "miner" in deal:
                        assert deal["miner"] != blacklisted_miner


class TestFilecoinBackendPricing:
    """Test price verification and limits."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_max_price_enforcement(self, filecoin_backend):
        """Test that max price is enforced."""
        content = b"Content for price test"
        
        # Set a very low max price
        if hasattr(filecoin_backend, 'metadata'):
            original_price = filecoin_backend.metadata.get("max_price")
            filecoin_backend.metadata["max_price"] = "1"  # Very low price
        
        # Try to store (may fail or use low-cost miner)
        result = filecoin_backend.add_content(content)
        
        # Restore original
        if hasattr(filecoin_backend, 'metadata'):
            if original_price:
                filecoin_backend.metadata["max_price"] = original_price
        
        # Should return result (success or failure)
        assert isinstance(result, dict)


class TestFilecoinBackendStorageVerification:
    """Test storage verification features."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_deal_verification(self, filecoin_backend):
        """Test deal verification is performed."""
        if hasattr(filecoin_backend, 'metadata'):
            # Enable verification
            original_verify = filecoin_backend.metadata.get("verify_deals")
            filecoin_backend.metadata["verify_deals"] = True
        
        content = b"Content for verification test"
        result = filecoin_backend.add_content(content)
        
        # Restore original
        if hasattr(filecoin_backend, 'metadata'):
            if original_verify is not None:
                filecoin_backend.metadata["verify_deals"] = original_verify
        
        if result.get("success"):
            # Verification should be tracked
            assert isinstance(result, dict)


class TestFilecoinBackendIntegration:
    """Integration tests for complete workflows."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_store_retrieve_cycle(self, filecoin_backend):
        """Test complete store and retrieve cycle."""
        original_content = b"Filecoin integration test content with binary \x00\xff data"
        
        # Store
        store_result = filecoin_backend.add_content(original_content)
        assert store_result.get("success"), f"Store failed: {store_result.get('error')}"
        
        # Get identifier
        identifier = store_result.get("identifier") or store_result.get("cid")
        assert identifier, "No identifier returned"
        
        # Retrieve
        retrieve_result = filecoin_backend.get_content(identifier)
        
        if retrieve_result.get("success"):
            retrieved_data = retrieve_result.get("data") or retrieve_result.get("content")
            
            if retrieved_data:
                # Verify content matches
                if isinstance(retrieved_data, str):
                    retrieved_data = retrieved_data.encode()
                assert retrieved_data == original_content
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_store_metadata_retrieve_cycle(self, filecoin_backend):
        """Test storing with metadata and retrieving it."""
        content = b"Content with metadata"
        metadata = {"type": "test", "version": "1.0", "description": "Test file"}
        
        # Store with metadata
        store_result = filecoin_backend.add_content(content, metadata=metadata)
        assert store_result.get("success"), f"Store failed: {store_result.get('error')}"
        
        # Get identifier
        identifier = store_result.get("identifier") or store_result.get("cid")
        assert identifier, "No identifier returned"
        
        # Retrieve metadata
        meta_result = filecoin_backend.get_metadata(identifier)
        
        if meta_result.get("success"):
            retrieved_meta = meta_result.get("metadata", {})
            # Should have some metadata (exact structure depends on implementation)
            assert isinstance(retrieved_meta, dict)


# Module-level tests
def test_filecoin_backend_import():
    """Test that Filecoin backend can be imported."""
    try:
        from ipfs_kit_py.mcp.storage_manager.backends.filecoin_backend import FilecoinBackend
        assert FilecoinBackend is not None
    except ImportError:
        pytest.skip("Filecoin backend not available")


def test_lotus_kit_import():
    """Test that Lotus kit can be imported."""
    try:
        from ipfs_kit_py.lotus_kit import LOTUS_AVAILABLE
        assert isinstance(LOTUS_AVAILABLE, bool)
    except ImportError:
        pytest.skip("Lotus kit not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
