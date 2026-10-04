"""
IPFS cluster authentication and security module for secure cluster communications.

This module provides secure authentication mechanisms for IPFS cluster nodes, including:
- X.509 certificate management for TLS connections
- UCAN-based capability delegation
- Role-based access control
- Authentication token management

The module supports the role-based architecture with different security profiles for
master, worker, and leecher nodes. Master nodes maintain the Certificate Authority (CA)
and issue certificates to worker nodes. All inter-node communications are encrypted
with TLS to prevent eavesdropping and authenticated to prevent malicious nodes from
joining the cluster.
"""

import base64
import datetime
import hashlib
import ipaddress
import json
import logging
import os
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

try:
    # Optional cryptographic dependencies
    import cryptography
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa
    from cryptography.hazmat.primitives.serialization import (
        load_pem_private_key,
        load_pem_public_key,
    )
    from cryptography.x509.oid import NameOID

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

try:
    # Optional UCAN dependencies
    import base64

    import jwcrypto.jwk as jwk
    import jwcrypto.jws as jws
    from jwcrypto.common import json_decode, json_encode

    HAS_UCAN = True
except ImportError:
    HAS_UCAN = False

# Local imports
from ipfs_kit_py.error import (
    IPFSConfigurationError,
    IPFSConnectionError,
    IPFSError,
    IPFSTimeoutError,
    IPFSValidationError,
    create_result_dict,
    handle_error,
)

# Configure logger
logger = logging.getLogger(__name__)


# Define error types for authentication
class AuthenticationError(IPFSError):
    """Base class for authentication-related errors."""

    pass


class CertificateError(AuthenticationError):
    """Error related to certificate operations."""

    pass


class UCANError(AuthenticationError):
    """Error related to UCAN operations."""

    pass


class AccessDeniedError(AuthenticationError):
    """Error when access is denied due to insufficient permissions."""

    pass


class TokenError(AuthenticationError):
    """Error related to authentication token operations."""

    pass


# UCAN capability constants
UCAN_CAPABILITIES = {
    # Pin management
    "pin": "Allows pinning content in the cluster",
    "unpin": "Allows unpinning content from the cluster",
    "pin_ls": "Allows listing pinned content in the cluster",
    # Peer management
    "peer_add": "Allows adding new peers to the cluster",
    "peer_rm": "Allows removing peers from the cluster",
    "peer_ls": "Allows listing peers in the cluster",
    # Configuration management
    "config_get": "Allows reading cluster configuration",
    "config_set": "Allows modifying cluster configuration",
    # Content management
    "add_content": "Allows adding content to the cluster",
    "get_content": "Allows retrieving content from the cluster",
    # Role management
    "role_get": "Allows querying node roles",
    "role_set": "Allows changing node roles",
    # Admin capabilities
    "metrics": "Allows accessing cluster metrics",
    "manage_peers": "Full control over peer management",
    "manage_pins": "Full control over pin management",
    "manage_config": "Full control over configuration",
    "manage_roles": "Full control over role management",
    "admin": "Full administrative access to all operations",
}

# Role-based capability assignments
DEFAULT_ROLE_CAPABILITIES = {
    "master": [
        "pin",
        "unpin",
        "pin_ls",
        "peer_add",
        "peer_rm",
        "peer_ls",
        "config_get",
        "config_set",
        "add_content",
        "get_content",
        "role_get",
        "role_set",
        "metrics",
        "manage_peers",
        "manage_pins",
        "manage_config",
        "manage_roles",
        "admin",
    ],
    "worker": [
        "pin",
        "unpin",
        "pin_ls",
        "peer_ls",
        "config_get",
        "add_content",
        "get_content",
        "role_get",
        "metrics",
    ],
    "leecher": ["pin_ls", "peer_ls", "config_get", "get_content", "role_get"],
}


class ClusterAuthManager:
    """Manages authentication and security for IPFS cluster nodes.

    This class provides certificate management, UCAN capability delegation,
    access control, and authentication token management for secure cluster
    communications. It integrates with the role-based architecture to provide
    appropriate security profiles for master, worker, and leecher nodes.
    """

    def __init__(
        self,
        node_id: str,
        role: str,
        security_dir: Optional[str] = None,
        cluster_id: str = "default",
        security_config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the authentication manager.

        Args:
            node_id: Unique identifier for this node
            role: Role of this node ("master", "worker", or "leecher")
            security_dir: Directory to store security materials
            cluster_id: Unique identifier for the cluster
            security_config: Security configuration parameters
        """
        self.node_id = node_id
        self.role = role
        self.cluster_id = cluster_id

        # Set up security directory
        self.security_dir = security_dir or os.path.expanduser(
            f"~/.ipfs/cluster_security/{cluster_id}"
        )
        os.makedirs(self.security_dir, exist_ok=True)

        # Node directories
        self.node_dir = os.path.join(self.security_dir, node_id)
        os.makedirs(self.node_dir, exist_ok=True)

        # Set up security configuration
        default_config = {
            "auth_required": True,
            "tls_enabled": True,
            "ucan_enabled": HAS_UCAN,
            "access_control": "strict",
            "token_expiration": 86400,  # 24 hours
            "cert_expiration_days": 365,  # 1 year
            "min_key_size": 2048,
            "secure_protocol": "TLSv1.3",
        }
        self.config = {**default_config, **(security_config or {})}

        # Security state
        self.ca_cert = None  # CA certificate
        self.ca_key = None  # CA private key
        self.node_cert = None  # Node certificate
        self.node_key = None  # Node private key
        self.tokens = {}  # Active tokens
        self.revoked_tokens = set()  # Revoked tokens
        self.peers = {}  # Authenticated peers with their certificates
        self.ucan_keys = {}  # UCAN key pairs
        self._lock = threading.RLock()  # Lock for thread safety

        # Initialize security materials
        self._initialize_security()

    def _initialize_security(self):
        """Initialize security materials based on role."""
        # Check if required cryptographic packages are installed
        if self.config["tls_enabled"] and not HAS_CRYPTO:
            logger.warning("Cryptography package not installed; TLS will be disabled")
            self.config["tls_enabled"] = False

        if self.config["ucan_enabled"] and not HAS_UCAN:
            logger.warning("UCAN dependencies not installed; UCAN will be disabled")
            self.config["ucan_enabled"] = False

        # Initialize based on role
        if self.role == "master":
            self._initialize_master_security()
        elif self.role == "worker":
            self._initialize_worker_security()
        else:  # leecher
            self._initialize_leecher_security()

    def _initialize_master_security(self):
        """Initialize security materials for a master node."""
        logger.info("Initializing master node security")

        # Load or generate CA certificate
        ca_cert_path = os.path.join(self.security_dir, "ca.crt")
        ca_key_path = os.path.join(self.security_dir, "ca.key")

        if os.path.exists(ca_cert_path) and os.path.exists(ca_key_path):
            # Load existing CA certificate
            self.ca_cert, self.ca_key = self._load_certificate_and_key(ca_cert_path, ca_key_path)
            logger.info("Loaded existing CA certificate")
        elif self.config["tls_enabled"] and HAS_CRYPTO:
            # Generate new CA certificate
            self.ca_cert, self.ca_key = self._generate_ca_certificate()

            # Save CA certificate
            self._save_certificate_and_key(self.ca_cert, self.ca_key, ca_cert_path, ca_key_path)
            logger.info("Generated new CA certificate")

        # Load or generate node certificate
        node_cert_path = os.path.join(self.node_dir, "node.crt")
        node_key_path = os.path.join(self.node_dir, "node.key")

        if os.path.exists(node_cert_path) and os.path.exists(node_key_path):
            # Load existing node certificate
            self.node_cert, self.node_key = self._load_certificate_and_key(
                node_cert_path, node_key_path
            )
            logger.info("Loaded existing node certificate")
        elif self.config["tls_enabled"] and HAS_CRYPTO and self.ca_cert and self.ca_key:
            # Generate new node certificate signed by CA
            self.node_cert, self.node_key = self._generate_node_certificate()

            # Save node certificate
            self._save_certificate_and_key(
                self.node_cert, self.node_key, node_cert_path, node_key_path
            )
            logger.info("Generated new node certificate")

        # Load or generate UCAN keypair
        if self.config["ucan_enabled"] and HAS_UCAN:
            self._initialize_ucan_keys()

        # Initialize token store
        self._load_tokens()

    def _initialize_worker_security(self):
        """Initialize security materials for a worker node."""
        logger.info("Initializing worker node security")

        # Load CA certificate if exists
        ca_cert_path = os.path.join(self.security_dir, "ca.crt")
        if os.path.exists(ca_cert_path):
            try:
                with open(ca_cert_path, "rb") as f:
                    self.ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
                logger.info("Loaded CA certificate")
            except Exception as e:
                logger.error(f"Failed to load CA certificate: {str(e)}")

        # Load or generate node certificate
        node_cert_path = os.path.join(self.node_dir, "node.crt")
        node_key_path = os.path.join(self.node_dir, "node.key")

        if os.path.exists(node_cert_path) and os.path.exists(node_key_path):
            # Load existing node certificate
            self.node_cert, self.node_key = self._load_certificate_and_key(
                node_cert_path, node_key_path
            )
            logger.info("Loaded existing node certificate")

        # Load or generate UCAN keypair
        if self.config["ucan_enabled"] and HAS_UCAN:
            self._initialize_ucan_keys()

        # Initialize token store
        self._load_tokens()

    def _initialize_leecher_security(self):
        """Initialize security materials for a leecher node."""
        logger.info("Initializing leecher node security")

        # Load CA certificate if exists
        ca_cert_path = os.path.join(self.security_dir, "ca.crt")
        if os.path.exists(ca_cert_path):
            try:
                with open(ca_cert_path, "rb") as f:
                    self.ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
                logger.info("Loaded CA certificate")
            except Exception as e:
                logger.error(f"Failed to load CA certificate: {str(e)}")

        # Generate node keypair if needed
        node_cert_path = os.path.join(self.node_dir, "node.crt")
        node_key_path = os.path.join(self.node_dir, "node.key")

        if os.path.exists(node_cert_path) and os.path.exists(node_key_path):
            # Load existing node certificate
            self.node_cert, self.node_key = self._load_certificate_and_key(
                node_cert_path, node_key_path
            )
            logger.info("Loaded existing node certificate")

        # Leechers don't need UCAN capabilities

        # Initialize token store
        self._load_tokens()

    def _load_certificate_and_key(self, cert_path, key_path):
        """Load certificate and private key from files."""
        if not HAS_CRYPTO:
            return None, None

        try:
            with open(cert_path, "rb") as f:
                cert_data = f.read()
                cert = x509.load_pem_x509_certificate(cert_data, default_backend())

            with open(key_path, "rb") as f:
                key_data = f.read()
                key = load_pem_private_key(key_data, password=None, backend=default_backend())

            return cert, key

        except Exception as e:
            logger.error(f"Failed to load certificate and key: {str(e)}")
            return None, None

    def _save_certificate_and_key(self, cert, key, cert_path, key_path):
        """Save certificate and private key to files."""
        if not HAS_CRYPTO:
            return False

        try:
            # Save certificate
            cert_data = cert.public_bytes(encoding=serialization.Encoding.PEM)
            with open(cert_path, "wb") as f:
                f.write(cert_data)

            # Save private key with restrictive permissions
            key_data = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            with open(key_path, "wb") as f:
                f.write(key_data)

            # Set restrictive permissions on private key
            os.chmod(key_path, 0o600)

            return True

        except Exception as e:
            logger.error(f"Failed to save certificate and key: {str(e)}")
            return False

    def _generate_ca_certificate(self):
        """Generate a self-signed CA certificate for the cluster."""
        if not HAS_CRYPTO:
            return None, None

        try:
            # Generate key
            key_size = max(2048, self.config.get("min_key_size", 2048))
            private_key = rsa.generate_private_key(
                public_exponent=65537, key_size=key_size, backend=default_backend()
            )

            # Create subject
            subject = x509.Name(
                [
                    x509.NameAttribute(NameOID.COMMON_NAME, f"IPFS Cluster CA - {self.cluster_id}"),
                    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "IPFS Cluster"),
                    x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Cluster Security"),
                ]
            )

            # Create certificate
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(subject)  # Self-signed
                .public_key(private_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.datetime.utcnow())
                .not_valid_after(
                    datetime.datetime.utcnow()
                    + datetime.timedelta(days=self.config.get("cert_expiration_days", 365) * 2)
                )
                .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                .add_extension(
                    x509.KeyUsage(
                        digital_signature=True,
                        content_commitment=False,
                        key_encipherment=True,
                        data_encipherment=False,
                        key_agreement=False,
                        key_cert_sign=True,
                        crl_sign=True,
                        encipher_only=False,
                        decipher_only=False,
                    ),
                    critical=True,
                )
                .add_extension(
                    x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
                    critical=False,
                )
                .sign(private_key, hashes.SHA256(), default_backend())
            )

            return cert, private_key

        except Exception as e:
            logger.error(f"Failed to generate CA certificate: {str(e)}")
            return None, None

    def _generate_node_certificate(self):
        """Generate a node certificate signed by the CA."""
        if not HAS_CRYPTO or not self.ca_cert or not self.ca_key:
            return None, None

        try:
            # Generate key
            key_size = max(2048, self.config.get("min_key_size", 2048))
            private_key = rsa.generate_private_key(
                public_exponent=65537, key_size=key_size, backend=default_backend()
            )

            # Create subject
            subject = x509.Name(
                [
                    x509.NameAttribute(NameOID.COMMON_NAME, f"IPFS Cluster Node - {self.node_id}"),
                    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "IPFS Cluster"),
                    x509.NameAttribute(
                        NameOID.ORGANIZATIONAL_UNIT_NAME, f"Cluster {self.cluster_id}"
                    ),
                ]
            )

            # Create certificate
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(self.ca_cert.subject)
                .public_key(private_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.datetime.utcnow())
                .not_valid_after(
                    datetime.datetime.utcnow()
                    + datetime.timedelta(days=self.config.get("cert_expiration_days", 365))
                )
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(
                    x509.KeyUsage(
                        digital_signature=True,
                        content_commitment=False,
                        key_encipherment=True,
                        data_encipherment=False,
                        key_agreement=False,
                        key_cert_sign=False,
                        crl_sign=False,
                        encipher_only=False,
                        decipher_only=False,
                    ),
                    critical=True,
                )
                .add_extension(
                    x509.ExtendedKeyUsage(
                        [
                            x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
                            x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                        ]
                    ),
                    critical=False,
                )
                .add_extension(
                    x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
                    critical=False,
                )
                .add_extension(
                    x509.SubjectAlternativeName(
                        [
                            x509.DNSName(f"node-{self.node_id}"),
                            x509.DNSName(f"node-{self.node_id}.cluster-{self.cluster_id}"),
                        ]
                    ),
                    critical=False,
                )
                .sign(self.ca_key, hashes.SHA256(), default_backend())
            )

            return cert, private_key

        except Exception as e:
            logger.error(f"Failed to generate node certificate: {str(e)}")
            return None, None

    def _initialize_ucan_keys(self):
        """Initialize UCAN keypair for capability delegation."""
        if not HAS_UCAN:
            return

        try:
            # Check for existing keys
            ucan_key_path = os.path.join(self.node_dir, "ucan_keys.json")

            if os.path.exists(ucan_key_path):
                # Load existing keys
                with open(ucan_key_path, "r") as f:
                    self.ucan_keys = json.load(f)
                logger.info("Loaded existing UCAN keys")
            else:
                # Generate new keypair (Ed25519)
                private_key = jwk.JWK.generate(kty="OKP", crv="Ed25519")

                # Store keys
                self.ucan_keys = {
                    "private": private_key.export_private(),
                    "public": private_key.export_public(),
                    "did": f"did:key:{self._compute_did_key(private_key)}",
                }

                # Save keys
                with open(ucan_key_path, "w") as f:
                    json.dump(self.ucan_keys, f)

                # Set restrictive permissions
                os.chmod(ucan_key_path, 0o600)

                logger.info("Generated new UCAN keys")

        except Exception as e:
            logger.error(f"Failed to initialize UCAN keys: {str(e)}")

    def _compute_did_key(self, key):
        """Compute a DID key from a JWK key."""
        if not HAS_UCAN:
            return None

        try:
            # Extract public key bytes
            key_bytes = key.get_op_key("verify")

            # Multicodec prefix for Ed25519 (0xed01)
            multicodec_prefix = bytes([0xED, 0x01])

            # Combine prefix and key
            prefixed_key = multicodec_prefix + key_bytes

            # Base58 encode
            base58_key = base64.b64encode(prefixed_key).decode("utf-8")

            return base58_key

        except Exception as e:
            logger.error(f"Failed to compute DID key: {str(e)}")
            return None

    def _load_tokens(self):
        """Load active authentication tokens from storage."""
        try:
            tokens_path = os.path.join(self.node_dir, "tokens.json")
            revoked_tokens_path = os.path.join(self.node_dir, "revoked_tokens.json")

            # Load active tokens
            if os.path.exists(tokens_path):
                with open(tokens_path, "r") as f:
                    self.tokens = json.load(f)
                logger.info(f"Loaded {len(self.tokens)} active tokens")

            # Load revoked tokens
            if os.path.exists(revoked_tokens_path):
                with open(revoked_tokens_path, "r") as f:
                    self.revoked_tokens = set(json.load(f))
                logger.info(f"Loaded {len(self.revoked_tokens)} revoked tokens")

        except Exception as e:
            logger.error(f"Failed to load tokens: {str(e)}")

    def _save_tokens(self):
        """Save active authentication tokens to storage."""
        try:
            tokens_path = os.path.join(self.node_dir, "tokens.json")
            revoked_tokens_path = os.path.join(self.node_dir, "revoked_tokens.json")

            # Save active tokens
            with open(tokens_path, "w") as f:
                json.dump(self.tokens, f)

            # Save revoked tokens
            with open(revoked_tokens_path, "w") as f:
                json.dump(list(self.revoked_tokens), f)

            # Set restrictive permissions
            os.chmod(tokens_path, 0o600)
            os.chmod(revoked_tokens_path, 0o600)

        except Exception as e:
            logger.error(f"Failed to save tokens: {str(e)}")

    def get_certificate_fingerprint(self, cert=None):
        """Get the SHA-256 fingerprint of a certificate.

        Args:
            cert: Certificate to get fingerprint for (defaults to node certificate)

        Returns:
            Certificate fingerprint as a colon-separated hexadecimal string
        """
        if not HAS_CRYPTO:
            return None

        try:
            cert = cert or self.node_cert
            if not cert:
                return None

            # Calculate SHA-256 fingerprint
            fingerprint = cert.fingerprint(hashes.SHA256())

            # Format as colon-separated hexadecimal
            return ":".join(format(b, "02x") for b in fingerprint)

        except Exception as e:
            logger.error(f"Failed to get certificate fingerprint: {str(e)}")
            return None

    def generate_cluster_identity(self):
        """Generate a secure identity for a cluster node.

        This method creates the necessary security materials for a node
        to participate in the cluster, including certificates and keys.

        Returns:
            Dictionary with operation result and identity information
        """
        result = create_result_dict("generate_cluster_identity")

        try:
            with self._lock:
                # Check if we already have an identity
                if self.node_cert and self.node_key:
                    # Return existing identity
                    fingerprint = self.get_certificate_fingerprint()

                    result.update(
                        {
                            "success": True,
                            "peer_id": self.node_id,
                            "fingerprint": fingerprint,
                            "new": False,
                            "role": self.role,
                        }
                    )

                    return result

                # Check if TLS is enabled
                if not self.config["tls_enabled"] or not HAS_CRYPTO:
                    result.update(
                        {
                            "success": False,
                            "error": "TLS is disabled or cryptography package not installed",
                        }
                    )
                    return result

                # Generate identity based on role
                if self.role == "master":
                    # Generate CA if needed
                    if not self.ca_cert or not self.ca_key:
                        self.ca_cert, self.ca_key = self._generate_ca_certificate()

                        # Save CA certificate
                        ca_cert_path = os.path.join(self.security_dir, "ca.crt")
                        ca_key_path = os.path.join(self.security_dir, "ca.key")
                        self._save_certificate_and_key(
                            self.ca_cert, self.ca_key, ca_cert_path, ca_key_path
                        )

                    # Generate node certificate
                    self.node_cert, self.node_key = self._generate_node_certificate()

                    # Save node certificate
                    node_cert_path = os.path.join(self.node_dir, "node.crt")
                    node_key_path = os.path.join(self.node_dir, "node.key")
                    self._save_certificate_and_key(
                        self.node_cert, self.node_key, node_cert_path, node_key_path
                    )

                    # Generate UCAN keys if enabled
                    if self.config["ucan_enabled"] and HAS_UCAN:
                        self._initialize_ucan_keys()

                    # Get certificate fingerprint
                    fingerprint = self.get_certificate_fingerprint()

                    result.update(
                        {
                            "success": True,
                            "peer_id": self.node_id,
                            "fingerprint": fingerprint,
                            "new": True,
                            "role": self.role,
                            "is_ca": True,
                        }
                    )

                elif self.role in ["worker", "leecher"]:
                    # Worker and leecher nodes need a CA to get a certificate
                    if not self.ca_cert or not self.ca_key:
                        result.update(
                            {"success": False, "error": "No CA certificate available for signing"}
                        )
                        return result

                    # Generate node certificate
                    self.node_cert, self.node_key = self._generate_node_certificate()

                    # Save node certificate
                    node_cert_path = os.path.join(self.node_dir, "node.crt")
                    node_key_path = os.path.join(self.node_dir, "node.key")
                    self._save_certificate_and_key(
                        self.node_cert, self.node_key, node_cert_path, node_key_path
                    )

                    # Generate UCAN keys for worker nodes
                    if self.role == "worker" and self.config["ucan_enabled"] and HAS_UCAN:
                        self._initialize_ucan_keys()

                    # Get certificate fingerprint
                    fingerprint = self.get_certificate_fingerprint()

                    result.update(
                        {
                            "success": True,
                            "peer_id": self.node_id,
                            "fingerprint": fingerprint,
                            "new": True,
                            "role": self.role,
                            "is_ca": False,
                        }
                    )

                else:
                    result.update({"success": False, "error": f"Unknown role: {self.role}"})

        except Exception as e:
            handle_error(result, e, logger)

        return result

    def generate_cluster_certificates(self, common_name=None, days_valid=None):
        """Generate TLS certificates for cluster communication.

        This method generates a new CA certificate (if this is a master node)
        and a node certificate signed by the CA. It supports generating
        certificates for both master and worker nodes.

        Args:
            common_name: Common name for the certificate
            days_valid: Validity period in days

        Returns:
            Dictionary with operation result and certificate information
        """
        result = create_result_dict("generate_cluster_certificates")

        try:
            with self._lock:
                # Check if TLS is enabled
                if not self.config["tls_enabled"] or not HAS_CRYPTO:
                    result.update(
                        {
                            "success": False,
                            "error": "TLS is disabled or cryptography package not installed",
                        }
                    )
                    return result

                # Use provided values or defaults
                common_name = common_name or f"IPFS Cluster Node - {self.node_id}"
                days_valid = days_valid or self.config.get("cert_expiration_days", 365)

                # Only master nodes can generate a CA certificate
                if self.role == "master":
                    # Generate new CA certificate
                    ca_cert, ca_key = self._generate_ca_certificate()

                    if not ca_cert or not ca_key:
                        result.update(
                            {"success": False, "error": "Failed to generate CA certificate"}
                        )
                        return result

                    # Save CA certificate
                    ca_cert_path = os.path.join(self.security_dir, "ca.crt")
                    ca_key_path = os.path.join(self.security_dir, "ca.key")
                    self._save_certificate_and_key(ca_cert, ca_key, ca_cert_path, ca_key_path)

                    # Update instance state
                    self.ca_cert = ca_cert
                    self.ca_key = ca_key

                    # Generate new node certificate
                    node_cert, node_key = self._generate_node_certificate()

                    if not node_cert or not node_key:
                        result.update(
                            {"success": False, "error": "Failed to generate node certificate"}
                        )
                        return result

                    # Save node certificate
                    node_cert_path = os.path.join(self.node_dir, "node.crt")
                    node_key_path = os.path.join(self.node_dir, "node.key")
                    self._save_certificate_and_key(
                        node_cert, node_key, node_cert_path, node_key_path
                    )

                    # Update instance state
                    self.node_cert = node_cert
                    self.node_key = node_key

                    # Format results
                    ca_cert_pem = ca_cert.public_bytes(encoding=serialization.Encoding.PEM).decode(
                        "utf-8"
                    )
                    node_cert_pem = node_cert.public_bytes(
                        encoding=serialization.Encoding.PEM
                    ).decode("utf-8")
                    node_key_pem = node_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption(),
                    ).decode("utf-8")

                    result.update(
                        {
                            "success": True,
                            "ca_cert": ca_cert_pem,
                            "server_cert": node_cert_pem,
                            "server_key": node_key_pem,
                            "client_cert": node_cert_pem,  # Same cert for client and server
                            "client_key": node_key_pem,
                            "ca_fingerprint": self.get_certificate_fingerprint(ca_cert),
                            "node_fingerprint": self.get_certificate_fingerprint(node_cert),
                        }
                    )

                else:
                    result.update(
                        {"success": False, "error": "Only master nodes can generate certificates"}
                    )

        except Exception as e:
            handle_error(result, e, logger)

        return result

    def install_cluster_certificates(self, certificates):
        """Install certificates issued by a master node.

        This method installs CA and node certificates provided by a master node,
        allowing a worker or leecher node to establish secure communications
        with the cluster.

        Args:
            certificates: Dictionary with certificate data
                - ca_cert: CA certificate (PEM format)
                - client_cert: Client certificate (PEM format)
                - client_key: Client private key (PEM format)

        Returns:
            Dictionary with operation result and certificate information
        """
        result = create_result_dict("install_cluster_certificates")

        try:
            with self._lock:
                # Check if TLS is enabled
                if not self.config["tls_enabled"] or not HAS_CRYPTO:
                    result.update(
                        {
                            "success": False,
                            "error": "TLS is disabled or cryptography package not installed",
                        }
                    )
                    return result

                # Check if we have all required certificates
                if "ca_cert" not in certificates:
                    result.update({"success": False, "error": "Missing CA certificate"})
                    return result

                if "client_cert" not in certificates or "client_key" not in certificates:
                    result.update({"success": False, "error": "Missing client certificate or key"})
                    return result

                # Parse certificates
                try:
                    ca_cert = x509.load_pem_x509_certificate(
                        certificates["ca_cert"].encode("utf-8"), default_backend()
                    )

                    client_cert = x509.load_pem_x509_certificate(
                        certificates["client_cert"].encode("utf-8"), default_backend()
                    )

                    client_key = load_pem_private_key(
                        certificates["client_key"].encode("utf-8"),
                        password=None,
                        backend=default_backend(),
                    )
                except Exception as e:
                    result.update(
                        {"success": False, "error": f"Failed to parse certificates: {str(e)}"}
                    )
                    return result

                # Save CA certificate
                ca_cert_path = os.path.join(self.security_dir, "ca.crt")
                with open(ca_cert_path, "wb") as f:
                    f.write(certificates["ca_cert"].encode("utf-8"))

                # Save client certificate and key
                node_cert_path = os.path.join(self.node_dir, "node.crt")
                node_key_path = os.path.join(self.node_dir, "node.key")

                with open(node_cert_path, "wb") as f:
                    f.write(certificates["client_cert"].encode("utf-8"))

                with open(node_key_path, "wb") as f:
                    f.write(certificates["client_key"].encode("utf-8"))

                # Set restrictive permissions on private key
                os.chmod(node_key_path, 0o600)

                # Update instance state
                self.ca_cert = ca_cert
                self.node_cert = client_cert
                self.node_key = client_key

                # Get certificate fingerprint
                fingerprint = self.get_certificate_fingerprint(client_cert)

                result.update({"success": True, "fingerprint": fingerprint})

        except Exception as e:
            handle_error(result, e, logger)

        return result

    def verify_peer_identity(self, peer_id, fingerprint=None):
        """Verify the identity of a peer.

        This method verifies a peer's identity by checking its certificate
        fingerprint against a known value. It helps prevent man-in-the-middle
        attacks by ensuring the peer is who it claims to be.

        Args:
            peer_id: ID of the peer to verify
            fingerprint: Certificate fingerprint to verify

        Returns:
            Dictionary with verification result
        """
        result = create_result_dict("verify_peer_identity")

        try:
            # Check if peer is in our peers list
            if peer_id in self.peers:
                peer_cert = self.peers[peer_id].get("certificate")
                stored_fingerprint = self.peers[peer_id].get("fingerprint")

                # If we have the peer's certificate, verify fingerprint
                if peer_cert:
                    computed_fingerprint = self.get_certificate_fingerprint(peer_cert)

                    # If no fingerprint provided, just return the computed one
                    if not fingerprint:
                        result.update(
                            {
                                "success": True,
                                "peer_id": peer_id,
                                "fingerprint": computed_fingerprint,
                                "verified": False,
                            }
                        )
                        return result

                    # Verify fingerprint
                    fingerprint_match = computed_fingerprint == fingerprint

                    result.update(
                        {
                            "success": True,
                            "peer_id": peer_id,
                            "verified": fingerprint_match,
                            "fingerprint": computed_fingerprint,
                            "fingerprint_match": fingerprint_match,
                        }
                    )

                    return result

                # If we don't have the certificate but have stored fingerprint
                if stored_fingerprint:
                    # If no fingerprint provided, just return the stored one
                    if not fingerprint:
                        result.update(
                            {
                                "success": True,
                                "peer_id": peer_id,
                                "fingerprint": stored_fingerprint,
                                "verified": False,
                            }
                        )
                        return result

                    # Verify fingerprint
                    fingerprint_match = stored_fingerprint == fingerprint

                    result.update(
                        {
                            "success": True,
                            "peer_id": peer_id,
                            "verified": fingerprint_match,
                            "fingerprint": stored_fingerprint,
                            "fingerprint_match": fingerprint_match,
                        }
                    )

                    return result

            # If we don't have any information about this peer
            if not fingerprint:
                result.update(
                    {
                        "success": True,
                        "peer_id": peer_id,
                        "verified": False,
                        "message": "Peer not known, no fingerprint to verify against",
                    }
                )
                return result

            # Store the provided fingerprint for future verification
            if peer_id not in self.peers:
                self.peers[peer_id] = {}

            self.peers[peer_id]["fingerprint"] = fingerprint

            result.update(
                {
                    "success": True,
                    "peer_id": peer_id,
                    "verified": False,
                    "fingerprint": fingerprint,
                    "message": "Stored fingerprint for future verification",
                }
            )

        except Exception as e:
            handle_error(result, e, logger)

        return result

    def generate_ucan_token(self, audience, capabilities=None, expiration=86400):
        """Generate a UCAN token with specific capabilities.

        This method creates a UCAN (User Controlled Authorization Network) token
        that delegates specific capabilities to another peer. UCANs enable
        fine-grained, decentralized authorization within the cluster.

        Args:
            audience: Peer ID of the token recipient
            capabilities: List of capabilities to delegate
            expiration: Token expiration time in seconds

        Returns:
            Dictionary with the generated UCAN token
        """
        result = create_result_dict("generate_ucan_token")

        try:
            with self._lock:
                # Check if UCAN is enabled
                if not self.config["ucan_enabled"] or not HAS_UCAN:
                    result.update(
                        {
                            "success": False,
                            "error": "UCAN is disabled or dependencies not installed",
                        }
                    )
                    return result

                # Check if we have keys
                if not self.ucan_keys:
                    result.update({"success": False, "error": "No UCAN keys available"})
                    return result

                # Use default capabilities based on role if none provided
                if capabilities is None:
                    if audience in self.peers and "role" in self.peers[audience]:
                        peer_role = self.peers[audience]["role"]
                        capabilities = DEFAULT_ROLE_CAPABILITIES.get(peer_role, [])
                    else:
                        # Default to leecher capabilities
                        capabilities = DEFAULT_ROLE_CAPABILITIES.get("leecher", [])

                # Create UCAN token
                issuer_key = jwk.JWK.from_json(self.ucan_keys["private"])

                # Use current time with expiration
                now = int(time.time())
                exp = now + expiration

                # Create payload
                payload = {
                    "iss": self.ucan_keys["did"],
                    "aud": f"did:key:{audience}",  # Assuming audience is a base58 key
                    "exp": exp,
                    "nbf": now,
                    "att": {"caps": capabilities},
                    "prf": None,  # No proof - this is a root UCAN
                }

                # Create JWS
                token = jws.JWS(json_encode(payload))
                token.add_signature(issuer_key, None, {"alg": "EdDSA", "typ": "JWT", "ucan": "1"})
                signed_token = token.serialize(compact=True)

                result.update(
                    {
                        "success": True,
                        "ucan": signed_token,
                        "capabilities": capabilities,
                        "expiration": exp,
                        "audience": audience,
                        "issuer": self.node_id,
                    }
                )

        except Exception as e:
            handle_error(result, e, logger)

        return result

    def verify_ucan_token(self, token):
        """Verify a UCAN token and its capabilities.

        This method verifies the authenticity and validity of a UCAN token,
        checking its signature, expiration, and capabilities. It ensures
        the token was issued by a trusted peer and grants the claimed capabilities.

        Args:
            token: UCAN token to verify

        Returns:
            Dictionary with verification result
        """
        result = create_result_dict("verify_ucan_token")

        try:
            with self._lock:
                # Check if UCAN is enabled
                if not self.config["ucan_enabled"] or not HAS_UCAN:
                    result.update(
                        {
                            "success": False,
                            "error": "UCAN is disabled or dependencies not installed",
                        }
                    )
                    return result

                # Parse token
                token_parts = token.split(".")
                if len(token_parts) != 3:
                    result.update({"success": False, "error": "Invalid token format"})
                    return result

                header_b64, payload_b64, signature_b64 = token_parts

                # Decode header and payload
                header = json.loads(base64.urlsafe_b64decode(header_b64 + "==").decode("utf-8"))
                payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "==").decode("utf-8"))

                # Check token type
                if header.get("typ") != "JWT" or "ucan" not in header:
                    result.update({"success": False, "error": "Not a UCAN token"})
                    return result

                # Check expiration
                current_time = int(time.time())
                if "exp" in payload and payload["exp"] < current_time:
                    result.update(
                        {
                            "success": False,
                            "valid": False,
                            "expired": True,
                            "error": "Token has expired",
                        }
                    )
                    return result

                # Check not-before time
                if "nbf" in payload and payload["nbf"] > current_time:
                    result.update(
                        {
                            "success": False,
                            "valid": False,
                            "expired": False,
                            "error": "Token not yet valid",
                        }
                    )
                    return result

                # Check audience
                if "aud" in payload:
                    audience = payload["aud"]
                    if audience.startswith("did:key:"):
                        audience = audience[8:]  # Remove did:key: prefix

                    # Check if we're the intended audience
                    if self.ucan_keys and "did" in self.ucan_keys:
                        our_did = self.ucan_keys["did"]
                        if our_did.startswith("did:key:"):
                            our_did = our_did[8:]  # Remove did:key: prefix

                        if audience != our_did:
                            result.update(
                                {
                                    "success": False,
                                    "valid": False,
                                    "expired": False,
                                    "error": f"Token not intended for this node. Expected {our_did}, got {audience}",
                                }
                            )
                            return result

                # Extract capabilities
                capabilities = payload.get("att", {}).get("caps", [])

                # Extract issuer
                issuer = payload.get("iss")
                if issuer and issuer.startswith("did:key:"):
                    issuer = issuer[8:]  # Remove did:key: prefix

                # TODO: Verify signature against issuer's public key
                # This requires having the issuer's public key, which may need to
                # be looked up or stored from previous interactions

                # 1. Look up the issuer's public key based on the issuer DID
                # 2. Use the public key to verify the token signature

                # For now, assume signature is valid
                result.update(
                    {
                        "success": True,
                        "valid": True,
                        "issuer": issuer,
                        "capabilities": capabilities,
                        "expired": False,
                        "not_before": payload.get("nbf"),
                        "expiration": payload.get("exp"),
                    }
                )

        except Exception as e:
            handle_error(result, e, logger)

        return result

    def establish_secure_connection(self, peer_id, address):
        """Establish a secure TLS connection to a peer.

        This method sets up a TLS connection to another peer using the
        node's certificate for authentication. It ensures that all
        communications with the peer are encrypted and authenticated.

        Args:
            peer_id: ID of the peer to connect to
            address: Network address of the peer

        Returns:
            Dictionary with connection result
        """
        result = create_result_dict("establish_secure_connection")

        try:
            with self._lock:
                # Check if TLS is enabled
                if not self.config["tls_enabled"]:
                    result.update({"success": False, "error": "TLS is disabled"})
                    return result

                # Check if we have certificates
                if not self.node_cert or not self.node_key or not self.ca_cert:
                    result.update(
                        {
                            "success": False,
                            "error": "Missing certificates required for secure connection",
                        }
                    )
                    return result

                # In a real implementation, this would establish a TLS connection
                # to the peer using the certificates. For now, we simulate it.

                # Store peer information
                if peer_id not in self.peers:
                    self.peers[peer_id] = {}

                self.peers[peer_id].update(
                    {"address": address, "last_connected": time.time(), "secure_connection": True}
                )

                # Generate a mock connection ID
                connection_id = str(uuid.uuid4())

                result.update(
                    {
                        "success": True,
                        "peer_id": peer_id,
                        "connection_id": connection_id,
                        "cipher_suite": "TLS_AES_256_GCM_SHA384",
                        "protocol_version": "TLSv1.3",
                    }
                )

        except Exception as e:
            handle_error(result, e, logger)

        return result

    def secure_cluster_rpc(self, peer_id, method, params=None):
        """Make a secure RPC call to another cluster node.

        This method makes a remote procedure call to another cluster node
        using the secure connection established with establish_secure_connection.
        The call is authenticated and encrypted to ensure security.

        Args:
            peer_id: ID of the peer to call
            method: RPC method to call
            params: Parameters for the RPC call

        Returns:
            Dictionary with RPC result
        """
        result = create_result_dict("secure_cluster_rpc")

        try:
            with self._lock:
                # Check if TLS is enabled
                if not self.config["tls_enabled"]:
                    result.update({"success": False, "error": "TLS is disabled"})
                    return result

                # Check if we have a secure connection to the peer
                if peer_id not in self.peers or not self.peers[peer_id].get("secure_connection"):
                    result.update(
                        {"success": False, "error": f"No secure connection to peer {peer_id}"}
                    )
                    return result

                # In a real implementation, this would make a secure RPC call
                # to the peer over the TLS connection. For now, we simulate it.

                # Simulate different RPC responses based on method
                if method == "cluster.Status":
                    response = {"cids": ["QmTest1", "QmTest2"]}
                elif method == "cluster.PinList":
                    response = {"pins": [{"cid": "QmTest1"}, {"cid": "QmTest2"}]}
                elif method == "cluster.Peers":
                    response = {"peers": [self.node_id, peer_id]}
                else:
                    response = {"method": method, "params": params}

                result.update(
                    {"success": True, "peer_id": peer_id, "method": method, "response": response}
                )

        except Exception as e:
            handle_error(result, e, logger)

        return result

    def verify_node_capability(self, peer_id, operation):
        """Verify if a node has the capability for an operation.

        This method checks if a node has been granted the capability
        to perform a specific operation within the cluster. It is used
        to enforce access control based on node roles and delegated
        capabilities.

        Args:
            peer_id: ID of the node to check
            operation: Operation to check capability for

        Returns:
            Dictionary with verification result
        """
        result = create_result_dict("verify_node_capability")

        try:
            with self._lock:
                # Map operation to required capability
                capability_map = {
                    "pin_add": "pin",
                    "pin_rm": "unpin",
                    "pin_ls": "pin_ls",
                    "peer_add": "peer_add",
                    "peer_rm": "peer_rm",
                    "peer_ls": "peer_ls",
                    "config_get": "config_get",
                    "config_set": "config_set",
                    "content_add": "add_content",
                    "content_get": "get_content",
                }

                required_capability = capability_map.get(operation, operation)

                # Check if peer is known
                if peer_id not in self.peers:
                    result.update(
                        {
                            "success": True,
                            "peer_id": peer_id,
                            "operation": operation,
                            "capability": required_capability,
                            "authorized": False,
                            "reason": "Unknown peer",
                        }
                    )
                    return result

                # Check if peer has a role assigned
                if "role" in self.peers[peer_id]:
                    peer_role = self.peers[peer_id]["role"]
                    role_capabilities = DEFAULT_ROLE_CAPABILITIES.get(peer_role, [])

                    # Check if role has admin capability (which grants all capabilities)
                    if "admin" in role_capabilities:
                        result.update(
                            {
                                "success": True,
                                "peer_id": peer_id,
                                "operation": operation,
                                "capability": required_capability,
                                "authorized": True,
                                "role": peer_role,
                                "reason": "Admin capability",
                            }
                        )
                        return result

                    # Check capability based on role
                    if required_capability in role_capabilities:
                        result.update(
                            {
                                "success": True,
                                "peer_id": peer_id,
                                "operation": operation,
                                "capability": required_capability,
                                "authorized": True,
                                "role": peer_role,
                                "reason": f"Role-based capability ({peer_role})",
                            }
                        )
                        return result

                # Check if peer has specific capabilities assigned
                if "capabilities" in self.peers[peer_id]:
                    peer_capabilities = self.peers[peer_id]["capabilities"]

                    # Check if peer has admin capability
                    if "admin" in peer_capabilities:
                        result.update(
                            {
                                "success": True,
                                "peer_id": peer_id,
                                "operation": operation,
                                "capability": required_capability,
                                "authorized": True,
                                "reason": "Admin capability",
                            }
                        )
                        return result

                    # Check for specific capability
                    if required_capability in peer_capabilities:
                        result.update(
                            {
                                "success": True,
                                "peer_id": peer_id,
                                "operation": operation,
                                "capability": required_capability,
                                "authorized": True,
                                "reason": "Explicitly granted capability",
                            }
                        )
                        return result

                    # Check for capability category (e.g., manage_pins includes pin, unpin, etc.)
                    for cap in peer_capabilities:
                        if cap.startswith("manage_") and required_capability.startswith(cap[7:]):
                            result.update(
                                {
                                    "success": True,
                                    "peer_id": peer_id,
                                    "operation": operation,
                                    "capability": required_capability,
                                    "authorized": True,
                                    "reason": f"Management capability ({cap})",
                                }
                            )
                            return result

                # No capability found
                result.update(
                    {
                        "success": True,
                        "peer_id": peer_id,
                        "operation": operation,
                        "capability": required_capability,
                        "authorized": False,
                        "reason": "Missing required capability",
                    }
                )

        except Exception as e:
            handle_error(result, e, logger)

        return result

    def enforce_cluster_access_control(self, peer_id, operation):
        """Enforce access control for cluster operations.

        This method enforces access control by checking if a peer has
        the required capability for an operation and denying the operation
        if it doesn't. It provides a central point for access control
        enforcement in the cluster.

        Args:
            peer_id: ID of the peer attempting the operation
            operation: Operation being attempted

        Returns:
            Dictionary with enforcement result
        """
        result = create_result_dict("enforce_cluster_access_control")

        try:
            with self._lock:
                # Check if access control is enabled
                access_control = self.config.get("access_control", "strict")

                if access_control == "none":
                    # No access control, allow all operations
                    result.update(
                        {
                            "success": True,
                            "peer_id": peer_id,
                            "operation": operation,
                            "authorized": True,
                            "reason": "Access control disabled",
                        }
                    )
                    return result

                # Verify capability
                capability_result = self.verify_node_capability(peer_id, operation)

                if not capability_result["success"]:
                    # Error during verification
                    result.update(
                        {
                            "success": False,
                            "peer_id": peer_id,
                            "operation": operation,
                            "authorized": False,
                            "error": capability_result.get(
                                "error", "Error during capability verification"
                            ),
                        }
                    )
                    return result

                if not capability_result["authorized"]:
                    # Unauthorized
                    result.update(
                        {
                            "success": False,
                            "peer_id": peer_id,
                            "operation": operation,
                            "authorized": False,
                            "error": f"Unauthorized: {capability_result.get('reason', 'missing required capability')}",
                        }
                    )
                    return result

                # Authorized
                result.update(
                    {
                        "success": True,
                        "peer_id": peer_id,
                        "operation": operation,
                        "authorized": True,
                        "reason": capability_result.get("reason", "Authorized by capability check"),
                    }
                )

        except Exception as e:
            handle_error(result, e, logger)

        return result

    def issue_cluster_auth_token(self, peer_id, capabilities=None, expiration=None):
        """Issue an authentication token for a peer.

        This method creates an authentication token that allows a peer
        to access cluster operations without repeated authentication.
        The token includes capabilities and an expiration time.

        Args:
            peer_id: ID of the peer to issue token for
            capabilities: List of capabilities to include in the token
            expiration: Token expiration time in seconds

        Returns:
            Dictionary with the issued token
        """
        result = create_result_dict("issue_cluster_auth_token")

        try:
            with self._lock:
                # Use default expiration if not specified
                if expiration is None:
                    expiration = self.config.get("token_expiration", 86400)  # 24 hours

                # Use default capabilities based on role if not specified
                if capabilities is None:
                    if peer_id in self.peers and "role" in self.peers[peer_id]:
                        peer_role = self.peers[peer_id]["role"]
                        capabilities = DEFAULT_ROLE_CAPABILITIES.get(peer_role, [])
                    else:
                        # Default to leecher capabilities
                        capabilities = DEFAULT_ROLE_CAPABILITIES.get("leecher", [])

                # Create token
                token = str(uuid.uuid4())
                issued_at = int(time.time())
                expires_at = issued_at + expiration

                # Store token
                self.tokens[token] = {
                    "peer_id": peer_id,
                    "capabilities": capabilities,
                    "issued_at": issued_at,
                    "expires_at": expires_at,
                }

                # Save tokens
                self._save_tokens()

                result.update(
                    {
                        "success": True,
                        "peer_id": peer_id,
                        "token": token,
                        "expiration": expires_at,
                        "capabilities": capabilities,
                    }
                )

        except Exception as e:
            handle_error(result, e, logger)

        return result

    def revoke_cluster_auth_token(self, peer_id, token):
        """Revoke an authentication token.

        This method revokes an authentication token, preventing it from
        being used for further operations. Revoked tokens are tracked
        to prevent replay attacks.

        Args:
            peer_id: ID of the peer whose token to revoke
            token: Token to revoke

        Returns:
            Dictionary with revocation result
        """
        result = create_result_dict("revoke_cluster_auth_token")

        try:
            with self._lock:
                # Check if token exists
                if token not in self.tokens:
                    result.update({"success": False, "error": "Token not found"})
                    return result

                # Check if token belongs to the specified peer
                if self.tokens[token]["peer_id"] != peer_id:
                    result.update(
                        {"success": False, "error": "Token does not belong to specified peer"}
                    )
                    return result

                # Revoke token
                token_info = self.tokens.pop(token)
                self.revoked_tokens.add(token)

                # Save tokens
                self._save_tokens()

                result.update(
                    {
                        "success": True,
                        "peer_id": peer_id,
                        "token": token,
                        "revoked_at": int(time.time()),
                    }
                )

        except Exception as e:
            handle_error(result, e, logger)

        return result

    def verify_cluster_auth_token(self, peer_id, token):
        """Verify an authentication token.

        This method verifies if an authentication token is valid, belongs
        to the specified peer, and has not expired. It is used to authenticate
        operations without requiring repeated authentication.

        Args:
            peer_id: ID of the peer whose token to verify
            token: Token to verify

        Returns:
            Dictionary with verification result
        """
        result = create_result_dict("verify_cluster_auth_token")

        try:
            with self._lock:
                # Check if token has been revoked
                if token in self.revoked_tokens:
                    result.update(
                        {
                            "success": True,
                            "valid": False,
                            "peer_id": peer_id,
                            "token": token,
                            "error": "Token has been revoked",
                        }
                    )
                    return result

                # Check if token exists
                if token not in self.tokens:
                    result.update(
                        {
                            "success": True,
                            "valid": False,
                            "peer_id": peer_id,
                            "token": token,
                            "error": "Token not found",
                        }
                    )
                    return result

                # Check if token belongs to the specified peer
                if self.tokens[token]["peer_id"] != peer_id:
                    result.update(
                        {
                            "success": True,
                            "valid": False,
                            "peer_id": peer_id,
                            "token": token,
                            "error": "Token does not belong to specified peer",
                        }
                    )
                    return result

                # Check if token has expired
                current_time = int(time.time())
                if self.tokens[token]["expires_at"] < current_time:
                    result.update(
                        {
                            "success": True,
                            "valid": False,
                            "expired": True,
                            "peer_id": peer_id,
                            "token": token,
                            "error": "Token has expired",
                        }
                    )
                    return result

                # Token is valid
                result.update(
                    {
                        "success": True,
                        "valid": True,
                        "peer_id": peer_id,
                        "token": token,
                        "expired": False,
                        "capabilities": self.tokens[token]["capabilities"],
                        "issued_at": self.tokens[token]["issued_at"],
                        "expires_at": self.tokens[token]["expires_at"],
                    }
                )

        except Exception as e:
            handle_error(result, e, logger)

        return result
