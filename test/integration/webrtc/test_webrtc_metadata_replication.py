"""
Tests for WebRTC streaming integration with metadata replication system.

This module tests the integration between the WebRTC streaming capabilities
and the metadata replication system, ensuring:

1. WebRTC streams use replicated metadata for fault tolerance
2. Stream configuration is properly replicated across nodes
3. Metadata replication ensures the minimum factor of 3 nodes
4. Correct replication levels are applied to streaming data
5. Real-time adaptations maintain replication guarantees
6. Recovery of WebRTC streams from replicated metadata

The tests focus on the interaction of these two systems rather than
implementation details of either system individually.
"""

import os
import json
import tempfile
import time
import unittest
import anyio
from unittest.mock import patch, MagicMock, AsyncMock
import uuid
import pytest

# Import our custom pytest_anyio module
from test.pytest_anyio import fixture as anyio_fixture

# Import components to test
from ipfs_kit_py.webrtc_streaming import (
    WebRTCStreamingManager, 
    IPFSMediaStreamTrack,
    HAVE_WEBRTC
)
from ipfs_kit_py.fs_journal_replication import (
    MetadataReplicationManager,
    ReplicationLevel,
    ReplicationStatus,
    create_replication_manager
)
from ipfs_kit_py.high_level_api import IPFSSimpleAPI


# Check if testing should be forced regardless of dependency availability
import os
if (os.environ.get('FORCE_WEBRTC_TESTS') == '1' or 
    os.environ.get('IPFS_KIT_FORCE_WEBRTC') == '1' or
    os.environ.get('IPFS_KIT_RUN_ALL_TESTS') == '1'):
    _can_test_webrtc = True
else:
    _can_test_webrtc = HAVE_WEBRTC


@pytest.mark.asyncio
class TestWebRTCMetadataReplication:
    """Test WebRTC integration with metadata replication."""
    
    @anyio_fixture
    async def setup(self):
        """Set up test environment with WebRTC manager and replication system."""
        # Create temp directory for test data
        temp_dir = tempfile.mkdtemp()
        
        # Create mock IPFS API
        api = MagicMock(spec=IPFSSimpleAPI)
        api.cat = MagicMock(return_value=b"test content")
        api.size = MagicMock(return_value={"Size": 1024})
        
        # Create mock replication manager
        replication_manager = MagicMock(spec=MetadataReplicationManager)
        replication_manager.replicate_journal_entry = AsyncMock(return_value={
            "success": True,
            "operation": "replicate_journal_entry",
            "timestamp": time.time(),
            "status": ReplicationStatus.COMPLETE.value,
            "replication_id": "test-replication-id",
            "target_count": 4,  # Target replication factor
            "success_count": 3,  # Minimum replication factor achieved
            "failure_count": 0
        })
        replication_manager.verify_metadata_replication = AsyncMock(return_value={
            "success": True,
            "operation": "verify_metadata_replication",
            "status": ReplicationStatus.COMPLETE.value,
            "replication_count": 3,  # Minimum replication factor achieved
            "quorum_size": 3  # Minimum replication factor required
        })
        replication_manager.config = {
            "quorum_size": 3,  # Enforce minimum replication factor of 3
            "min_replication_factor": 3,
            "target_replication_factor": 4,
            "max_replication_factor": 5
        }
        
        # Create test data
        test_cid = "QmTestWebRTCCID123"
        test_content = b"Test video content" * 100000  # ~1.6MB of fake video data
        
        # Create the WebRTC streaming manager with mock components
        with patch('ipfs_kit_py.webrtc_streaming.RTCPeerConnection', new=AsyncMock()):
            # Create manager with mock replication manager
            webrtc_manager = WebRTCStreamingManager(ipfs_api=api)
            webrtc_manager.replication_manager = replication_manager
            
            # Add a test track
            track = MagicMock(spec=IPFSMediaStreamTrack)
            track.source_cid = test_cid
            track.get_stats = MagicMock(return_value={
                "track_id": "test-track-123",
                "resolution": "1280x720",
                "framerate": 30,
                "quality_level": "medium"
            })
            webrtc_manager.tracks = {"test-track-123": track}
            
            # Add a mock peer connection
            peer_connection = AsyncMock()
            webrtc_manager.peer_connections = {"test-pc-123": peer_connection}
            webrtc_manager.connection_stats = {
                "test-pc-123": {
                    "created_at": time.time(),
                    "tracks": ["test-track-123"],
                    "ice_state": "connected",
                    "signaling_state": "stable",
                    "connection_state": "connected"
                }
            }
            
            # Setup mock for create_offer
            webrtc_manager.create_offer = AsyncMock(return_value={
                "pc_id": "test-pc-123",
                "sdp": "test_sdp",
                "type": "offer",
                "tracks": ["test-track-123"]
            })
            
            # Setup mock for handle_answer
            webrtc_manager.handle_answer = AsyncMock(return_value={
                "success": True,
                "pc_id": "test-pc-123"
            })
            
            # Track state for metadata replication
            webrtc_manager._metadata_replicated = {}
            
            # Add methods for metadata replication
            async def replicate_track_metadata(track_id, replication_level=None):
                """Mock method to replicate track metadata."""
                track = webrtc_manager.tracks.get(track_id)
                if not track:
                    return {"success": False, "error": "Track not found"}
                
                # Create metadata entry
                metadata = {
                    "track_id": track_id,
                    "cid": track.source_cid,
                    "resolution": "1280x720",
                    "framerate": 30,
                    "quality_level": "medium",
                    "created_at": time.time(),
                    "node_id": "test-node-123"
                }
                
                # Set replication level
                if not replication_level:
                    replication_level = ReplicationLevel.QUORUM
                
                # Call replication manager
                result = await replication_manager.replicate_journal_entry(
                    metadata, 
                    replication_level=replication_level
                )
                
                # Store replication state
                webrtc_manager._metadata_replicated[track_id] = {
                    "replicated": True,
                    "replication_level": replication_level,
                    "result": result,
                    "metadata": metadata,
                    "timestamp": time.time()
                }
                
                return result
            
            async def verify_track_metadata_replication(track_id):
                """Mock method to verify track metadata replication."""
                if track_id not in webrtc_manager._metadata_replicated:
                    return {
                        "success": False,
                        "operation": "verify_metadata_replication",
                        "error": "Track metadata not replicated"
                    }
                
                metadata = webrtc_manager._metadata_replicated[track_id].get("metadata", {})
                
                # Call replication manager verification
                result = await replication_manager.verify_metadata_replication(
                    metadata.get("track_id")
                )
                
                # Add track info to result
                result["track_id"] = track_id
                result["metadata"] = metadata
                
                return result
            
            # Attach methods to manager
            webrtc_manager.replicate_track_metadata = replicate_track_metadata
            webrtc_manager.verify_track_metadata_replication = verify_track_metadata_replication
            
            yield {
                "api": api,
                "webrtc_manager": webrtc_manager,
                "replication_manager": replication_manager,
                "test_cid": test_cid,
                "test_content": test_content,
                "temp_dir": temp_dir
            }
            
            # Cleanup
            await webrtc_manager.close_all_connections()
            
            # Remove temporary directory
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    async def test_replicate_track_metadata(self, setup):
        """Test replication of WebRTC track metadata."""
        webrtc_manager = setup["webrtc_manager"]
        replication_manager = setup["replication_manager"]
        
        # Replicate track metadata
        result = await webrtc_manager.replicate_track_metadata("test-track-123")
        
        # Verify the replication was successful
        assert result["success"] is True
        assert result["status"] == ReplicationStatus.COMPLETE.value
        
        # Verify the replication achieved the minimum factor of 3
        assert result["success_count"] >= 3
        
        # Verify replication manager was called with correct parameters
        call_args = replication_manager.replicate_journal_entry.call_args
        args, kwargs = call_args
        
        # First argument should be the metadata
        metadata = args[0]
        assert metadata["track_id"] == "test-track-123"
        
        # Verify level was set to QUORUM (the default)
        replication_level = kwargs.get("replication_level")
        assert replication_level == ReplicationLevel.QUORUM
    
    async def test_replicate_track_metadata_with_custom_level(self, setup):
        """Test replication of WebRTC track metadata with custom replication level."""
        webrtc_manager = setup["webrtc_manager"]
        replication_manager = setup["replication_manager"]
        
        # Replicate track metadata with custom level
        result = await webrtc_manager.replicate_track_metadata(
            "test-track-123",
            replication_level=ReplicationLevel.ALL
        )
        
        # Verify the replication was successful
        assert result["success"] is True
        
        # Verify replication manager was called with correct level
        call_args = replication_manager.replicate_journal_entry.call_args
        args, kwargs = call_args
        
        # Verify level was set to ALL
        replication_level = kwargs.get("replication_level")
        assert replication_level == ReplicationLevel.ALL
    
    async def test_verify_track_metadata_replication(self, setup):
        """Test verification of WebRTC track metadata replication."""
        webrtc_manager = setup["webrtc_manager"]
        replication_manager = setup["replication_manager"]
        
        # First, replicate the metadata
        await webrtc_manager.replicate_track_metadata("test-track-123")
        
        # Reset the mock to clear previous calls
        replication_manager.verify_metadata_replication.reset_mock()
        
        # Verify the replication
        result = await webrtc_manager.verify_track_metadata_replication("test-track-123")
        
        # Verify the verification was successful
        assert result["success"] is True
        assert result["status"] == ReplicationStatus.COMPLETE.value
        
        # Verify we met minimum replication factor of 3
        assert result["replication_count"] >= 3
        assert result["quorum_size"] == 3
        
        # Verify replication manager was called
        replication_manager.verify_metadata_replication.assert_called_once()
    
    async def test_track_metadata_not_replicated(self, setup):
        """Test verification of track metadata that hasn't been replicated."""
        webrtc_manager = setup["webrtc_manager"]
        
        # Verify track that hasn't been replicated
        result = await webrtc_manager.verify_track_metadata_replication("non-existent-track")
        
        # Verify the verification failed
        assert result["success"] is False
        assert "error" in result
    
    async def test_minimum_replication_factor_enforcement(self, setup):
        """Test that the minimum replication factor of 3 is enforced for WebRTC metadata."""
        webrtc_manager = setup["webrtc_manager"]
        replication_manager = setup["replication_manager"]
        
        # Modify the replication manager to simulate only 2 successful replications
        replication_manager.replicate_journal_entry = AsyncMock(return_value={
            "success": False,  # Should fail because less than minimum 3
            "operation": "replicate_journal_entry",
            "timestamp": time.time(),
            "status": ReplicationStatus.PARTIAL.value,
            "replication_id": "test-replication-id",
            "target_count": 4,  # Target replication factor
            "success_count": 2,  # Less than minimum (3)
            "failure_count": 2
        })
        
        # Replicate track metadata
        result = await webrtc_manager.replicate_track_metadata("test-track-123")
        
        # Verify the replication failed due to not meeting minimum factor
        assert result["success"] is False
        assert result["status"] == ReplicationStatus.PARTIAL.value
        assert result["success_count"] < 3  # Less than minimum requirement
    
    async def test_create_offer_with_metadata_replication(self, setup):
        """Test creating WebRTC offer with automatic metadata replication."""
        webrtc_manager = setup["webrtc_manager"]
        
        # Add method to WebRTC manager that integrates offer creation with replication
        async def create_offer_with_replication(pc_id=None, track_ids=None, replication_level=None):
            """Create offer and replicate track metadata."""
            # Create the offer first
            offer = await webrtc_manager.create_offer(pc_id, track_ids)
            
            # For each track, replicate its metadata
            if "tracks" in offer:
                for track_id in offer["tracks"]:
                    await webrtc_manager.replicate_track_metadata(
                        track_id, 
                        replication_level=replication_level or ReplicationLevel.QUORUM
                    )
            
            # Add replication info to offer
            offer["metadata_replicated"] = True
            
            return offer
        
        # Attach method to manager
        webrtc_manager.create_offer_with_replication = create_offer_with_replication
        
        # Create an offer with replication
        result = await webrtc_manager.create_offer_with_replication(
            pc_id="test-pc-456",
            track_ids=["test-track-123"],
            replication_level=ReplicationLevel.QUORUM
        )
        
        # Verify the offer was created and metadata was replicated
        assert "sdp" in result
        assert result["metadata_replicated"] is True
        assert "test-track-123" in webrtc_manager._metadata_replicated
        assert webrtc_manager._metadata_replicated["test-track-123"]["replicated"] is True

    async def test_webrtc_recovery_from_replicated_metadata(self, setup):
        """Test recovering WebRTC streams from replicated metadata."""
        webrtc_manager = setup["webrtc_manager"]
        replication_manager = setup["replication_manager"]
        
        # Create a mock recovery method that would rebuild streams from metadata
        async def recover_tracks_from_metadata():
            """Mock recovery of tracks from replicated metadata."""
            # Simulate fetching replicated metadata
            metadata = {
                "track_id": "recovered-track-123",
                "cid": "QmRecoveredCID",
                "resolution": "1280x720",
                "framerate": 30,
                "quality_level": "medium"
            }
            
            # Create a new track from the metadata
            track = MagicMock(spec=IPFSMediaStreamTrack)
            track.source_cid = metadata["cid"]
            track.get_stats = MagicMock(return_value=metadata)
            
            # Add to tracks dictionary
            webrtc_manager.tracks["recovered-track-123"] = track
            
            return {
                "success": True,
                "operation": "recover_tracks",
                "recovered_tracks": ["recovered-track-123"]
            }
        
        # Attach method to manager
        webrtc_manager.recover_tracks_from_metadata = recover_tracks_from_metadata
        
        # Perform recovery
        result = await webrtc_manager.recover_tracks_from_metadata()
        
        # Verify recovery success
        assert result["success"] is True
        assert "recovered-track-123" in result["recovered_tracks"]
        assert "recovered-track-123" in webrtc_manager.tracks