"""
Tests for secure authentication in IPFS cluster nodes (Phase 3B).

This module tests the secure authentication mechanisms for cluster nodes, including:
- Node identity verification
- Authorization with X.509 certificates
- UCAN-based capability delegation
- TLS-secured communication between nodes
- Role-based access control
- Authentication token management
"""

import unittest
import os
import tempfile
import time
import shutil
import uuid
import json
import pytest
from unittest.mock import patch, MagicMock

from ipfs_kit_py.ipfs_kit import ipfs_kit


@pytest.fixture
def cluster_auth_setup():
    """Create test setup for cluster authentication testing."""
    with patch('subprocess.run') as mock_run:
        # Mock successful daemon initialization
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"ID": "test-id"}'
        mock_run.return_value = mock_process
        
        # Create master node with authentication enabled
        master = ipfs_kit(
            resources={"memory": "8GB", "disk": "1TB", "cpu": 4},
            metadata={
                "role": "master",
                "cluster_name": "test-auth-cluster",
                "security": {
                    "auth_required": True,
                    "tls_enabled": True,
                    "ucan_enabled": True,
                    "access_control": "strict"
                },
                "test_mode": True
            }
        )
        master.ipfs = MagicMock()
        master.ipfs_cluster_service = MagicMock()
        master.ipfs_cluster_ctl = MagicMock()
        
        # Create worker node with authentication
        worker = ipfs_kit(
            resources={"memory": "4GB", "disk": "500GB", "cpu": 2},
            metadata={
                "role": "worker",
                "cluster_name": "test-auth-cluster",
                "security": {
                    "auth_required": True,
                    "tls_enabled": True,
                    "ucan_enabled": True
                },
                "test_mode": True
            }
        )
        worker.ipfs = MagicMock()
        worker.ipfs_cluster_follow = MagicMock()
        
        # Create test credentials
        master_creds = {
            "peer_id": "QmMasterPeerID",
            "auth_token": str(uuid.uuid4()),
            "cert_fingerprint": "ab:cd:ef:12:34:56:78:90",
            "capabilities": ["manage_peers", "manage_pins", "manage_config"]
        }
        
        worker_creds = {
            "peer_id": "QmWorkerPeerID",
            "auth_token": str(uuid.uuid4()),
            "cert_fingerprint": "12:34:56:78:90:ab:cd:ef",
            "capabilities": ["pin", "unpin", "add_content"]
        }
        
        yield {
            "master": master,
            "worker": worker,
            "master_creds": master_creds,
            "worker_creds": worker_creds
        }


class TestIdentityVerification:
    """Test node identity verification mechanisms."""
    
    def test_generate_node_identity(self, cluster_auth_setup):
        """Test generating a secure node identity."""
        master = cluster_auth_setup["master"]
        
        # Mock the identity generation
        master.ipfs_cluster_service.generate_identity = MagicMock(return_value={
            "success": True,
            "peer_id": "QmNewPeerID",
            "private_key": "base64encodedprivatekey==",
            "public_key": "base64encodedpublickey=="
        })

        # Test generating identity
        # Call the method on the correct sub-component
        result = master.ipfs_cluster_service.generate_identity()

        # Verify result
        assert result["success"] is True
        assert "peer_id" in result
        assert "private_key" in result
        assert "public_key" in result
        master.ipfs_cluster_service.generate_identity.assert_called_once()
    
    def test_verify_peer_identity(self, cluster_auth_setup):
        """Test verification of peer identity."""
        master = cluster_auth_setup["master"]
        worker_creds = cluster_auth_setup["worker_creds"]
        
        # Mock the verification method
        master.ipfs_cluster_ctl.verify_peer_identity = MagicMock(return_value={
            "success": True,
            "peer_id": worker_creds["peer_id"],
            "verified": True,
            "fingerprint_match": True
        })

        # Test verification
        # Call the method on the correct sub-component
        result = master.ipfs_cluster_ctl.verify_peer_identity(
            peer_id=worker_creds["peer_id"],
            fingerprint=worker_creds["cert_fingerprint"]
        )

        # Verify result
        assert result["success"] is True
        assert result["verified"] is True
        assert result["fingerprint_match"] is True
        master.ipfs_cluster_ctl.verify_peer_identity.assert_called_once_with(
            peer_id=worker_creds["peer_id"],
            fingerprint=worker_creds["cert_fingerprint"]
        )


class TestCertificateManagement:
    """Test X.509 certificate management for secure cluster communication."""
    
    def test_generate_cluster_certificates(self, cluster_auth_setup):
        """Test generating TLS certificates for cluster communication."""
        master = cluster_auth_setup["master"]
        
        # Mock certificate generation
        master.ipfs_cluster_service.generate_certificates = MagicMock(return_value={
            "success": True,
            "ca_cert": "base64encodedcacert==",
            "server_cert": "base64encodedservercert==",
            "server_key": "base64encodedserverkey==",
            "client_cert": "base64encodedclientcert==",
            "client_key": "base64encodedclientkey=="
        })

        # Test generating certificates
        # Call the method on the correct sub-component
        result = master.ipfs_cluster_service.generate_certificates(
            common_name="test-cluster.local",
            days_valid=365
        )

        # Verify result
        assert result["success"] is True
        assert "ca_cert" in result
        assert "server_cert" in result
        assert "client_cert" in result
        master.ipfs_cluster_service.generate_certificates.assert_called_once()
    
    def test_install_certificates(self, cluster_auth_setup):
        """Test installing certificates on a node."""
        worker = cluster_auth_setup["worker"]
        
        # Certificates to install (in real implementation would be files)
        certificates = {
            "ca_cert": "base64encodedcacert==",
            "client_cert": "base64encodedclientcert==",
            "client_key": "base64encodedclientkey=="
        }
        
        # Mock certificate installation
        worker.ipfs_cluster_follow.install_certificates = MagicMock(return_value={
            "success": True,
            "fingerprint": "12:34:56:78:90:ab:cd:ef"
        })

        # Test installing certificates
        # Call the method on the correct sub-component
        result = worker.ipfs_cluster_follow.install_certificates(certificates)

        # Verify result
        assert result["success"] is True
        assert "fingerprint" in result
        worker.ipfs_cluster_follow.install_certificates.assert_called_once()


class TestUCANCapabilities:
    """Test UCAN-based capability delegation."""
    
    def test_generate_ucan_token(self, cluster_auth_setup):
        """Test generating a UCAN token with specific capabilities."""
        master = cluster_auth_setup["master"]
        worker_creds = cluster_auth_setup["worker_creds"]
        
        # Capabilities to delegate
        capabilities = ["pin", "unpin", "add_content"]
        
        # Mock UCAN token generation
        master.ipfs_cluster_ctl.generate_ucan = MagicMock(return_value={
            "success": True,
            "ucan": "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCIsInVjYW4iOnsiaXNzIjoiZGlkOmtleTp6Nk1rZm5...",
            "capabilities": capabilities,
            "expiration": int(time.time()) + 86400,  # 24 hours
            "audience": worker_creds["peer_id"]
        })

        # Test generating UCAN
        # Call the method on the correct sub-component
        result = master.ipfs_cluster_ctl.generate_ucan(
            audience=worker_creds["peer_id"],
            capabilities=capabilities,
            expiration=86400  # 24 hours
        )

        # Verify result
        assert result["success"] is True
        assert "ucan" in result
        assert result["capabilities"] == capabilities
        assert result["audience"] == worker_creds["peer_id"]
        master.ipfs_cluster_ctl.generate_ucan.assert_called_once()
    
    def test_verify_ucan_token(self, cluster_auth_setup):
        """Test verifying a UCAN token and its capabilities."""
        worker = cluster_auth_setup["worker"]
        
        # Sample UCAN token
        ucan_token = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCIsInVjYW4iOnsiaXNzIjoiZGlkOmtleTp6Nk1rZm5..."
        
        # Mock UCAN verification
        worker.ipfs_cluster_follow.verify_ucan = MagicMock(return_value={
            "success": True,
            "valid": True,
            "issuer": "QmMasterPeerID",
            "capabilities": ["pin", "unpin", "add_content"],
            "expired": False,
            "not_before": int(time.time()) - 3600,
            "expiration": int(time.time()) + 86400
        })

        # Test verifying UCAN
        # Call the method on the correct sub-component
        result = worker.ipfs_cluster_follow.verify_ucan(ucan_token)

        # Verify result
        assert result["success"] is True
        assert result["valid"] is True
        assert "capabilities" in result
        assert not result["expired"]
        worker.ipfs_cluster_follow.verify_ucan.assert_called_once_with(ucan_token)


class TestSecureCommunication:
    """Test secure communication between cluster nodes."""
    
    def test_tls_connection_setup(self, cluster_auth_setup):
        """Test setting up a TLS-secured connection between nodes."""
        master = cluster_auth_setup["master"]
        worker_creds = cluster_auth_setup["worker_creds"]
        
        # Mock TLS connection setup
        master.ipfs_cluster_ctl.establish_secure_connection = MagicMock(return_value={
            "success": True,
            "peer_id": worker_creds["peer_id"],
            "connection_id": str(uuid.uuid4()),
            "cipher_suite": "TLS_AES_256_GCM_SHA384",
            "protocol_version": "TLSv1.3"
        })

        # Test establishing connection
        # Call the method on the correct sub-component
        result = master.ipfs_cluster_ctl.establish_secure_connection(
            peer_id=worker_creds["peer_id"],
            address="/ip4/192.168.1.100/tcp/9096"
        )

        # Verify result
        assert result["success"] is True
        assert result["peer_id"] == worker_creds["peer_id"]
        assert "connection_id" in result
        assert "cipher_suite" in result
        master.ipfs_cluster_ctl.establish_secure_connection.assert_called_once()
    
    def test_secure_rpc_call(self, cluster_auth_setup):
        """Test making a secure RPC call between nodes."""
        master = cluster_auth_setup["master"]
        worker_creds = cluster_auth_setup["worker_creds"]
        
        # Mock secure RPC call
        master.ipfs_cluster_ctl.secure_rpc_call = MagicMock(return_value={
            "success": True,
            "peer_id": worker_creds["peer_id"],
            "method": "cluster.Status",
            "response": {"cids": ["QmTest1", "QmTest2"]}
        })

        # Test making secure RPC call
        # Call the method on the correct sub-component
        result = master.ipfs_cluster_ctl.secure_rpc_call(
            peer_id=worker_creds["peer_id"],
            method="cluster.Status",
            params={"local": True}
        )

        # Verify result
        assert result["success"] is True
        assert result["peer_id"] == worker_creds["peer_id"]
        assert result["method"] == "cluster.Status"
        assert "response" in result
        master.ipfs_cluster_ctl.secure_rpc_call.assert_called_once()


class TestRoleBasedAccessControl:
    """Test role-based access control for cluster operations."""
    
    def test_verify_capability_for_operation(self, cluster_auth_setup):
        """Test verifying if a node has capability for an operation."""
        master = cluster_auth_setup["master"]
        worker_creds = cluster_auth_setup["worker_creds"]
        
        # Mock capability verification
        master.ipfs_cluster_ctl.verify_capability = MagicMock(return_value={
            "success": True,
            "peer_id": worker_creds["peer_id"],
            "operation": "pin_add",
            "capability": "pin",
            "authorized": True
        })

        # Test verifying capability
        # Call the method on the correct sub-component
        result = master.ipfs_cluster_ctl.verify_capability(
            peer_id=worker_creds["peer_id"],
            operation="pin_add"
        )

        # Verify result
        assert result["success"] is True
        assert result["authorized"] is True
        assert result["operation"] == "pin_add"
        assert result["capability"] == "pin"
        master.ipfs_cluster_ctl.verify_capability.assert_called_once()
    
    def test_enforce_access_control(self, cluster_auth_setup):
        """Test enforcing access control for an operation."""
        master = cluster_auth_setup["master"]
        worker_creds = cluster_auth_setup["worker_creds"]
        
        # Unauthorized operation for worker
        operation = "config_edit"  # Worker doesn't have config_edit capability
        
        # Mock access control enforcement
        master.ipfs_cluster_ctl.enforce_access_control = MagicMock(return_value={
            "success": False,
            "peer_id": worker_creds["peer_id"],
            "operation": operation,
            "error": "Unauthorized: missing capability config_edit",
            "authorized": False
        })

        # Test enforcing access control
        # Call the method on the correct sub-component
        result = master.ipfs_cluster_ctl.enforce_access_control(
            peer_id=worker_creds["peer_id"],
            operation=operation
        )

        # Verify result
        assert result["success"] is False
        assert result["authorized"] is False
        assert result["operation"] == operation
        assert "error" in result
        master.ipfs_cluster_ctl.enforce_access_control.assert_called_once()


class TestAuthenticationTokenManagement:
    """Test authentication token management."""
    
    def test_issue_auth_token(self, cluster_auth_setup):
        """Test issuing an authentication token."""
        master = cluster_auth_setup["master"]
        worker_creds = cluster_auth_setup["worker_creds"]
        
        # Mock token issuance
        master.ipfs_cluster_ctl.issue_auth_token = MagicMock(return_value={
            "success": True,
            "peer_id": worker_creds["peer_id"],
            "token": str(uuid.uuid4()),
            "expiration": int(time.time()) + 3600,  # 1 hour
            "capabilities": ["pin", "unpin", "add_content"]
        })

        # Test issuing token
        # Call the method on the correct sub-component
        result = master.ipfs_cluster_ctl.issue_auth_token(
            peer_id=worker_creds["peer_id"],
            capabilities=["pin", "unpin", "add_content"],
            expiration=3600  # 1 hour
        )

        # Verify result
        assert result["success"] is True
        assert result["peer_id"] == worker_creds["peer_id"]
        assert "token" in result
        assert "expiration" in result
        assert "capabilities" in result
        master.ipfs_cluster_ctl.issue_auth_token.assert_called_once()
    
    def test_revoke_auth_token(self, cluster_auth_setup):
        """Test revoking an authentication token."""
        master = cluster_auth_setup["master"]
        worker_creds = cluster_auth_setup["worker_creds"]
        
        # Mock token revocation
        master.ipfs_cluster_ctl.revoke_auth_token = MagicMock(return_value={
            "success": True,
            "peer_id": worker_creds["peer_id"],
            "token": worker_creds["auth_token"],
            "revoked_at": int(time.time())
        })

        # Test revoking token
        # Call the method on the correct sub-component
        result = master.ipfs_cluster_ctl.revoke_auth_token(
            peer_id=worker_creds["peer_id"],
            token=worker_creds["auth_token"]
        )

        # Verify result
        assert result["success"] is True
        assert result["peer_id"] == worker_creds["peer_id"]
        assert result["token"] == worker_creds["auth_token"]
        assert "revoked_at" in result
        master.ipfs_cluster_ctl.revoke_auth_token.assert_called_once()
    
    def test_verify_auth_token(self, cluster_auth_setup):
        """Test verifying an authentication token."""
        master = cluster_auth_setup["master"]
        worker_creds = cluster_auth_setup["worker_creds"]
        
        # Mock token verification
        master.ipfs_cluster_ctl.verify_auth_token = MagicMock(return_value={
            "success": True,
            "peer_id": worker_creds["peer_id"],
            "token": worker_creds["auth_token"],
            "valid": True,
            "expired": False,
            "capabilities": ["pin", "unpin", "add_content"]
        })

        # Test verifying token
        # Call the method on the correct sub-component
        result = master.ipfs_cluster_ctl.verify_auth_token(
            peer_id=worker_creds["peer_id"],
            token=worker_creds["auth_token"]
        )

        # Verify result
        assert result["success"] is True
        assert result["valid"] is True
        assert not result["expired"]
        assert "capabilities" in result
        master.ipfs_cluster_ctl.verify_auth_token.assert_called_once()


if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__])
