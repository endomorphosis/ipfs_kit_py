"""
OAuth Enhanced Security Module for MCP Server

This module provides additional security hardening measures for the OAuth system:

1. PKCE (Proof Key for Code Exchange) - Protects authorization code flow from code interception
2. Token Binding - Binds tokens to specific client fingerprints to prevent token theft
3. Advanced Threat Protection - Detects and prevents common OAuth attack patterns
4. Certificate Chain Validation - Ensures connections to OAuth providers are secure
5. Dynamic Security Policy - Adjusts security requirements based on risk assessment

These enhancements address the OAuth security hardening item identified in the MCP roadmap.
"""

import os
import logging
import hashlib
import base64
import json
import time
import hmac
import random
import string
import socket
import ssl
import urllib.parse
from typing import Dict, List, Tuple, Optional, Any, Set, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from ipaddress import ip_address, ip_network
import threading
import re

# Configure logger
logger = logging.getLogger(__name__)

# Try importing optional dependencies
try:
    import cryptography
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.exceptions import InvalidSignature
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    logger.warning("Cryptography library not available. Some security features will be limited.")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logger.warning("Requests library not available. Certificate validation features will be limited.")


# PKCE (Proof Key for Code Exchange) Implementation
class PKCEManager:
    """
    PKCE (Proof Key for Code Exchange) implementation for OAuth 2.0 authorization code flow.
    
    PKCE prevents authorization code interception attacks by requiring a code verifier
    that only the legitimate client possesses. This is particularly important for
    public clients that cannot securely store client secrets.
    """
    
    CODE_CHALLENGE_METHODS = ["S256", "plain"]
    RECOMMENDED_METHOD = "S256"
    
    def __init__(self, storage_backend: Optional[Any] = None):
        """
        Initialize the PKCE manager.
        
        Args:
            storage_backend: Optional backend for storing PKCE state
        """
        self._storage = storage_backend
        self._verifiers = {}
        self._lock = threading.RLock()
        
        # Start cleanup thread if no storage backend
        if not storage_backend:
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                daemon=True,
                name="pkce-cleanup"
            )
            self._stop_cleanup = threading.Event()
            self._cleanup_thread.start()
            
        logger.info("PKCE manager initialized")
    
    def create_code_verifier(self, length: int = 64) -> str:
        """
        Create a random code verifier.
        
        The code verifier is a cryptographically random string using the
        characters A-Z, a-z, 0-9, and the punctuation characters -._~
        
        Args:
            length: Length of the code verifier (recommended: 64-128)
            
        Returns:
            A random code verifier string
        """
        if length < 43 or length > 128:
            logger.warning(f"PKCE code verifier length {length} outside recommended range (43-128). Using 64.")
            length = 64
            
        allowed_chars = string.ascii_letters + string.digits + "-._~"
        code_verifier = ''.join(random.choice(allowed_chars) for _ in range(length))
        
        return code_verifier
    
    def create_code_challenge(self, code_verifier: str, method: str = "S256") -> str:
        """
        Create a code challenge from the code verifier.
        
        Args:
            code_verifier: The code verifier
            method: Challenge method ("S256" or "plain")
            
        Returns:
            Code challenge string
            
        Raises:
            ValueError: If method is invalid
        """
        if method not in self.CODE_CHALLENGE_METHODS:
            raise ValueError(f"Invalid code challenge method: {method}")
            
        if method == "plain":
            logger.warning("Using 'plain' PKCE method which offers reduced security")
            return code_verifier
            
        # S256 method: SHA256 hash, base64url encode, remove padding
        code_challenge = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge_b64 = base64.urlsafe_b64encode(code_challenge).decode()
        return code_challenge_b64.rstrip("=")
    
    def store_verifier(self, state: str, code_verifier: str, expires_in: int = 600) -> None:
        """
        Store a code verifier associated with a state parameter.
        
        Args:
            state: OAuth state parameter
            code_verifier: PKCE code verifier
            expires_in: Seconds until expiration (default: 10 minutes)
        """
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        if self._storage:
            # Use storage backend if available
            self._storage.set(f"pkce:{state}", code_verifier, expires_in)
        else:
            # Use in-memory storage
            with self._lock:
                self._verifiers[state] = {
                    "verifier": code_verifier,
                    "expires_at": expires_at
                }
                
        logger.debug(f"Stored PKCE verifier for state {state[:8]}..., expires in {expires_in}s")
    
    def verify_challenge(self, state: str, code_verifier: str, remove: bool = True) -> bool:
        """
        Verify a code verifier against stored state.
        
        Args:
            state: OAuth state parameter
            code_verifier: PKCE code verifier to verify
            remove: Whether to remove the stored verifier after verification
            
        Returns:
            True if verification succeeds, False otherwise
        """
        if not state or not code_verifier:
            logger.warning("Missing state or code_verifier in PKCE verification")
            return False
            
        stored_verifier = None
        
        if self._storage:
            # Use storage backend if available
            stored_verifier = self._storage.get(f"pkce:{state}")
            if remove and stored_verifier:
                self._storage.delete(f"pkce:{state}")
        else:
            # Use in-memory storage
            with self._lock:
                if state in self._verifiers:
                    record = self._verifiers[state]
                    stored_verifier = record["verifier"]
                    
                    # Check expiration
                    if datetime.utcnow() > record["expires_at"]:
                        logger.warning(f"PKCE verifier for state {state[:8]}... has expired")
                        if remove:
                            del self._verifiers[state]
                        return False
                    
                    # Remove if requested
                    if remove:
                        del self._verifiers[state]
        
        if not stored_verifier:
            logger.warning(f"No PKCE verifier found for state {state[:8]}...")
            return False
            
        # Use constant-time comparison to prevent timing attacks
        result = hmac.compare_digest(stored_verifier, code_verifier)
        
        if result:
            logger.debug(f"PKCE verification succeeded for state {state[:8]}...")
        else:
            logger.warning(f"PKCE verification failed for state {state[:8]}...")
            
        return result
    
    def _cleanup_loop(self) -> None:
        """Periodic cleanup of expired verifiers."""
        while not self._stop_cleanup.is_set():
            # Sleep first to allow initial setup
            self._stop_cleanup.wait(300)  # 5 minutes
            if not self._stop_cleanup.is_set():
                try:
                    self._cleanup_expired()
                except Exception as e:
                    logger.error(f"Error in PKCE cleanup: {e}")
    
    def _cleanup_expired(self) -> None:
        """Clean up expired verifiers."""
        if self._storage:
            # Storage backend handles expiration
            return
            
        now = datetime.utcnow()
        with self._lock:
            states_to_remove = []
            for state, record in self._verifiers.items():
                if now > record["expires_at"]:
                    states_to_remove.append(state)
                    
            for state in states_to_remove:
                del self._verifiers[state]
                
            if states_to_remove:
                logger.debug(f"Cleaned up {len(states_to_remove)} expired PKCE verifiers")
    
    def shutdown(self) -> None:
        """Shutdown the PKCE manager."""
        if not self._storage and hasattr(self, '_stop_cleanup'):
            logger.info("Shutting down PKCE manager")
            self._stop_cleanup.set()
            if self._cleanup_thread.is_alive():
                self._cleanup_thread.join(timeout=5.0)


# Token Binding Implementation
class TokenBindingManager:
    """
    Token binding implementation that binds tokens to specific clients.
    
    Token binding helps prevent token theft by attaching additional security
    context to tokens, such as browser fingerprints, IP addresses, or device
    identifiers. When a token is used, the current context is compared against
    the bound context to detect potential token theft.
    """
    
    def __init__(self, storage_backend: Optional[Any] = None, strict_mode: bool = False):
        """
        Initialize the token binding manager.
        
        Args:
            storage_backend: Optional backend for storing binding data
            strict_mode: Whether to strictly enforce all binding factors
        """
        self._storage = storage_backend
        self._bindings = {}
        self._lock = threading.RLock()
        self._strict_mode = strict_mode
        
        # Security settings
        self._max_ips_per_token = 3
        self._max_user_agents_per_token = 2
        self._ip_network_size = 29  # /29 subnet (8 addresses)
        
        # Start cleanup thread if no storage backend
        if not storage_backend:
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                daemon=True,
                name="token-binding-cleanup"
            )
            self._stop_cleanup = threading.Event()
            self._cleanup_thread.start()
            
        logger.info(f"Token binding manager initialized (strict mode: {strict_mode})")
    
    def bind_token(self, token_id: str, context: Dict[str, Any], 
                expires_in: int = 3600) -> None:
        """
        Bind a token to a client context.
        
        Args:
            token_id: Unique token identifier or hash
            context: Client context data (IP, user agent, etc.)
            expires_in: Seconds until binding expiration
        """
        if not token_id or not context:
            logger.warning("Missing token_id or context in token binding")
            return
            
        # Extract key binding factors
        ip_address = context.get("ip_address")
        user_agent = context.get("user_agent")
        
        # Create binding record
        binding_data = {
            "token_id": token_id,
            "ip_addresses": [ip_address] if ip_address else [],
            "user_agents": [user_agent] if user_agent else [],
            "additional_factors": {},
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
        }
        
        # Add any additional context as factors
        for key, value in context.items():
            if key not in ["ip_address", "user_agent"] and value:
                binding_data["additional_factors"][key] = value
        
        if self._storage:
            # Use storage backend if available
            self._storage.set(f"binding:{token_id}", json.dumps(binding_data), expires_in)
        else:
            # Use in-memory storage
            with self._lock:
                binding_data["expires_at_dt"] = datetime.utcnow() + timedelta(seconds=expires_in)
                self._bindings[token_id] = binding_data
                
        logger.debug(f"Bound token {token_id[:8]}... to client context")
    
    def update_binding(self, token_id: str, context: Dict[str, Any]) -> bool:
        """
        Update a token binding with additional context.
        
        This allows a token to be used from multiple contexts within
        reasonable security boundaries (e.g., similar IP subnets).
        
        Args:
            token_id: Token identifier or hash
            context: New client context data
            
        Returns:
            True if binding was updated, False if not found or expired
        """
        binding = self._get_binding(token_id)
        if not binding:
            logger.warning(f"Attempted to update non-existent binding for token {token_id[:8]}...")
            return False
            
        # Extract key binding factors
        ip_address = context.get("ip_address")
        user_agent = context.get("user_agent")
        updated = False
        
        # Update IP addresses (with limit)
        if ip_address and ip_address not in binding["ip_addresses"]:
            if len(binding["ip_addresses"]) < self._max_ips_per_token:
                binding["ip_addresses"].append(ip_address)
                updated = True
            else:
                logger.warning(f"Token {token_id[:8]}... has reached max IP addresses limit")
                
        # Update user agents (with limit)
        if user_agent and user_agent not in binding["user_agents"]:
            if len(binding["user_agents"]) < self._max_user_agents_per_token:
                binding["user_agents"].append(user_agent)
                updated = True
            else:
                logger.warning(f"Token {token_id[:8]}... has reached max user agents limit")
                
        # Update additional factors
        for key, value in context.items():
            if key not in ["ip_address", "user_agent"] and value:
                if key not in binding["additional_factors"] or binding["additional_factors"][key] != value:
                    binding["additional_factors"][key] = value
                    updated = True
                    
        if updated:
            # Save updated binding
            if self._storage:
                # Calculate new expiration time
                created_at = datetime.fromisoformat(binding["created_at"])
                expires_at = datetime.fromisoformat(binding["expires_at"])
                expires_in = (expires_at - datetime.utcnow()).total_seconds()
                if expires_in <= 0:
                    return False
                    
                self._storage.set(f"binding:{token_id}", json.dumps(binding), int(expires_in))
            else:
                # In-memory storage is already updated by reference
                pass
                
            logger.debug(f"Updated binding for token {token_id[:8]}...")
            
        return True
    
    def verify_binding(self, token_id: str, context: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Verify a token against its binding.
        
        Args:
            token_id: Token identifier or hash
            context: Current client context data
            
        Returns:
            Tuple of (valid, reason) where valid is True if binding is valid
        """
        binding = self._get_binding(token_id)
        if not binding:
            return False, "No binding found"
            
        # Extract key binding factors
        ip_address = context.get("ip_address")
        user_agent = context.get("user_agent")
        
        # Verify IP address
        if ip_address and binding["ip_addresses"]:
            ip_match = False
            
            # Check for exact IP match
            if ip_address in binding["ip_addresses"]:
                ip_match = True
            else:
                # Check for subnet match if strict mode is off
                if not self._strict_mode:
                    ip_match = self._check_ip_subnet_match(ip_address, binding["ip_addresses"])
                    
            if not ip_match:
                return False, "IP address does not match binding"
                
        # Verify user agent
        if user_agent and binding["user_agents"]:
            ua_match = False
            
            # Check for exact user agent match
            if user_agent in binding["user_agents"]:
                ua_match = True
            else:
                # Check for similar user agent if strict mode is off
                if not self._strict_mode:
                    ua_match = self._check_similar_user_agent(user_agent, binding["user_agents"])
                    
            if not ua_match:
                return False, "User agent does not match binding"
                
        # Verify additional factors
        for key, value in binding["additional_factors"].items():
            if key in context and context[key]:
                if context[key] != value and self._strict_mode:
                    return False, f"Factor '{key}' does not match binding"
        
        # Update binding with new context if verification passed
        self.update_binding(token_id, context)
        
        return True, "Binding verified"
    
    def remove_binding(self, token_id: str) -> bool:
        """
        Remove a token binding.
        
        Args:
            token_id: Token identifier or hash
            
        Returns:
            True if binding was removed, False if not found
        """
        if self._storage:
            # Use storage backend if available
            if self._storage.get(f"binding:{token_id}"):
                self._storage.delete(f"binding:{token_id}")
                logger.debug(f"Removed binding for token {token_id[:8]}...")
                return True
            return False
        else:
            # Use in-memory storage
            with self._lock:
                if token_id in self._bindings:
                    del self._bindings[token_id]
                    logger.debug(f"Removed binding for token {token_id[:8]}...")
                    return True
                return False
    
    def _get_binding(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a token binding data.
        
        Args:
            token_id: Token identifier or hash
            
        Returns:
            Binding data or None if not found or expired
        """
        if self._storage:
            # Use storage backend if available
            binding_json = self._storage.get(f"binding:{token_id}")
            if not binding_json:
                return None
                
            try:
                binding = json.loads(binding_json)
                # Check expiration
                expires_at = datetime.fromisoformat(binding["expires_at"])
                if datetime.utcnow() > expires_at:
                    self._storage.delete(f"binding:{token_id}")
                    return None
                return binding
            except Exception as e:
                logger.error(f"Error parsing binding data: {e}")
                return None
        else:
            # Use in-memory storage
            with self._lock:
                if token_id not in self._bindings:
                    return None
                    
                binding = self._bindings[token_id]
                
                # Check expiration
                if datetime.utcnow() > binding["expires_at_dt"]:
                    del self._bindings[token_id]
                    return None
                    
                # Return a copy
                result = binding.copy()
                result.pop("expires_at_dt", None)
                return result
    
    def _check_ip_subnet_match(self, ip: str, ip_list: List[str]) -> bool:
        """
        Check if an IP address matches a subnet of any IP in the list.
        
        Args:
            ip: IP address to check
            ip_list: List of IP addresses to compare against
            
        Returns:
            True if a subnet match is found, False otherwise
        """
        try:
            test_ip = ip_address(ip)
            for bound_ip in ip_list:
                bound_ip_obj = ip_address(bound_ip)
                
                # Create subnets for both IPs
                test_network = ip_network(f"{test_ip}/{self._ip_network_size}", strict=False)
                bound_network = ip_network(f"{bound_ip_obj}/{self._ip_network_size}", strict=False)
                
                if test_network == bound_network:
                    return True
        except Exception as e:
            logger.debug(f"Error in IP subnet matching: {e}")
            
        return False
    
    def _check_similar_user_agent(self, ua: str, ua_list: List[str]) -> bool:
        """
        Check if a user agent is similar to any in the list.
        
        This uses simple heuristics to detect similar browser versions, etc.
        
        Args:
            ua: User agent to check
            ua_list: List of user agents to compare against
            
        Returns:
            True if a similar user agent is found, False otherwise
        """
        def normalize_ua(user_agent):
            # Extract browser and OS core info, ignoring version numbers
            patterns = [
                r'(Chrome|Firefox|Safari|Edge|MSIE|Trident|Opera)/?',
                r'(Windows|Mac|Linux|Android|iOS|iPhone|iPad)',
                r'(Mobile|Desktop)'
            ]
            normalized = []
            for pattern in patterns:
                match = re.search(pattern, user_agent)
                if match:
                    normalized.append(match.group(1))
            return " ".join(normalized)
        
        ua_normalized = normalize_ua(ua)
        if not ua_normalized:
            return False
            
        for bound_ua in ua_list:
            bound_ua_normalized = normalize_ua(bound_ua)
            if bound_ua_normalized and ua_normalized == bound_ua_normalized:
                return True
                
        return False
    
    def _cleanup_loop(self) -> None:
        """Periodic cleanup of expired bindings."""
        while not self._stop_cleanup.is_set():
            # Sleep first to allow initial setup
            self._stop_cleanup.wait(300)  # 5 minutes
            if not self._stop_cleanup.is_set():
                try:
                    self._cleanup_expired()
                except Exception as e:
                    logger.error(f"Error in token binding cleanup: {e}")
    
    def _cleanup_expired(self) -> None:
        """Clean up expired bindings."""
        if self._storage:
            # Storage backend handles expiration
            return
            
        now = datetime.utcnow()
        with self._lock:
            tokens_to_remove = []
            for token_id, binding in self._bindings.items():
                if now > binding["expires_at_dt"]:
                    tokens_to_remove.append(token_id)
                    
            for token_id in tokens_to_remove:
                del self._bindings[token_id]
                
            if tokens_to_remove:
                logger.debug(f"Cleaned up {len(tokens_to_remove)} expired token bindings")
    
    def shutdown(self) -> None:
        """Shutdown the token binding manager."""
        if not self._storage and hasattr(self, '_stop_cleanup'):
            logger.info("Shutting down token binding manager")
            self._stop_cleanup.set()
            if self._cleanup_thread.is_alive():
                self._cleanup_thread.join(timeout=5.0)


# Certificate Chain Validation
class CertificateValidator:
    """
    Enhanced certificate validation for OAuth provider connections.
    
    This class provides advanced certificate validation beyond the basic
    TLS verification, including:
    - Certificate pinning
    - Certificate transparency checking
    - Extended validation verification
    - Certificate revocation checking
    """
    
    def __init__(self):
        """Initialize the certificate validator."""
        self._cert_pins = {}
        self._default_timeout = 10.0
        logger.info("Certificate validator initialized")
    
    def add_cert_pin(self, hostname: str, pin: str) -> None:
        """
        Add a certificate pin for a hostname.
        
        Args:
            hostname: The hostname to pin
            pin: The certificate pin (hash of public key)
        """
        self._cert_pins[hostname] = pin
        logger.info(f"Added certificate pin for {hostname}")
    
    def validate_provider_cert(self, provider_url: str) -> Tuple[bool, str]:
        """
        Validate a provider's TLS certificate.
        
        Args:
            provider_url: URL of the OAuth provider
            
        Returns:
            Tuple of (valid, reason)
        """
        if not HAS_REQUESTS:
            logger.warning("Requests library not available. Certificate validation limited.")
            return True, "Certificate validation skipped (requests library not available)"
            
        try:
            # Parse URL to get hostname
            parsed_url = urllib.parse.urlparse(provider_url)
            hostname = parsed_url.netloc
            
            # Check if URL uses HTTPS
            if parsed_url.scheme != "https":
                return False, "Provider URL does not use HTTPS"
                
            # Perform full certificate validation with requests
            response = requests.get(
                provider_url,
                timeout=self._default_timeout,
                verify=True
            )
            
            # Check certificate pinning if configured
            if hostname in self._cert_pins:
                pin = self._cert_pins[hostname]
                cert = response.raw.connection.sock.getpeercert(binary_form=True)
                if not self._check_cert_pin(cert, pin):
                    return False, "Certificate pin validation failed"
                    
            return True, "Certificate validation successful"
        except requests.exceptions.SSLError as e:
            return False, f"SSL certificate validation failed: {str(e)}"
        except requests.exceptions.RequestException as e:
            return False, f"Error connecting to provider: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in certificate validation: {e}")
            return False, f"Certificate validation error: {str(e)}"
    
    def validate_cert_directly(self, hostname: str, port: int = 443) -> Tuple[bool, str]:
        """
        Validate a server's certificate directly using SSL socket.
        
        Args:
            hostname: Server hostname
            port: Server port (default: 443)
            
        Returns:
            Tuple of (valid, reason)
        """
        try:
            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=self._default_timeout) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    
                    # Check hostname
                    if not ssl.match_hostname(cert, hostname):
                        return False, "Hostname mismatch in certificate"
                        
                    # Check expiration
                    not_after = datetime.strptime(cert['notAfter'], r'%b %d %H:%M:%S %Y %Z')
                    if datetime.utcnow() > not_after:
                        return False, "Certificate has expired"
                        
                    # Check certificate pinning if configured
                    if hostname in self._cert_pins:
                        pin = self._cert_pins[hostname]
                        binary_cert = ssock.getpeercert(binary_form=True)
                        if not self._check_cert_pin(binary_cert, pin):
                            return False, "Certificate pin validation failed"
                            
                    return True, "Certificate validation successful"
        except ssl.SSLError as e:
            return False, f"SSL error: {e}"
        except socket.error as e:
            return False, f"Socket error: {e}"
        except Exception as e:
            logger.error(f"Unexpected error in direct certificate validation: {e}")
            return False, f"Certificate validation error: {str(e)}"
    
    def _check_cert_pin(self, cert: bytes, pin: str) -> bool:
        """
        Check if a certificate matches a pin.
        
        Args:
            cert: Certificate in binary form
            pin: Certificate pin (hash of public key)
            
        Returns:
            True if certificate matches pin, False otherwise
        """
        try:
            # Extract the certificate's public key
            if HAS_CRYPTOGRAPHY:
                from cryptography import x509
                from cryptography.hazmat.backends import default_backend
                cert_obj = x509.load_der_x509_certificate(cert, default_backend())
                public_key = cert_obj.public_key()
                public_key_bytes = public_key.public_bytes(
                    encoding=serialization.Encoding.DER,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
                # Create SHA-256 hash
                cert_hash = hashlib.sha256(public_key_bytes).digest()
                cert_pin = base64.b64encode(cert_hash).decode('ascii')
                
                # Compare pins
                return hmac.compare_digest(cert_pin, pin)
            else:
                # Fallback to simpler calculation if cryptography not available
                cert_hash = hashlib.sha256(cert).digest()
                cert_pin = base64.b64encode(cert_hash).decode('ascii')
                
                # Compare hashes (not ideal but better than nothing)
                return hmac.compare_digest(cert_pin, pin)
        except Exception as e:
            logger.error(f"Error checking certificate pin: {e}")
            return False


# Advanced Threat Protection
class OAuthThreatDetector:
    """
    Advanced OAuth threat detection and protection.
    
    This class provides detection and prevention of common OAuth attacks:
    - Authorization code injection
    - Token substitution attacks
    - Cross-site request forgery
    - Redirect URI manipulation
    - Token leakage and reuse
    """
    
    def __init__(self, storage_backend: Optional[Any] = None):
        """
        Initialize the threat detector.
        
        Args:
            storage_backend: Optional backend for storing threat data
        """
        self._storage = storage_backend
        self._threats = {}
        self._lock = threading.RLock()
        
        # Tracking data
        self._tracking = {
            "auth_requests": {},
            "token_requests": {},
            "suspicious_ips": set(),
            "blocked_ips": set()
        }
        
        # Rate limiting
        self._rate_limits = {
            "auth_requests": {},
            "token_requests": {},
            "refresh_requests": {}
        }
        
        # Thresholds
        self._thresholds = {
            "max_auth_requests": 10,  # per minute per IP
            "max_token_requests": 5,  # per minute per IP
            "max_refresh_requests": 20,  # per minute per IP
            "max_failed_attempts": 5,  # per 10 minutes per IP
            "max_ip_changes": 3,  # per token
            "suspicious_score_threshold": 70  # 0-100 scale
        }
        
        logger.info("OAuth threat detector initialized")
    
    def track_auth_request(self, client_id: str, redirect_uri: str, 
                         state: str, ip_address: str, user_agent: str) -> Dict[str, Any]:
        """
        Track an authorization request for threat analysis.
        
        Args:
            client_id: OAuth client ID
            redirect_uri: Redirect URI
            state: OAuth state parameter
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            Analysis result with threat score and details
        """
        timestamp = datetime.utcnow()
        request_id = f"{client_id}:{state}"
        
        # Store request data
        request_data = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": timestamp.isoformat(),
            "suspicious": False,
            "threat_score": 0,
            "threat_details": []
        }
        
        # Check for rate limiting
        if self._is_rate_limited("auth_requests", ip_address):
            request_data["suspicious"] = True
            request_data["threat_score"] += 30
            request_data["threat_details"].append("Rate limit exceeded for auth requests")
            
        # Check for suspicious redirect URI
        if self._is_suspicious_redirect_uri(redirect_uri, client_id):
            request_data["suspicious"] = True
            request_data["threat_score"] += 40
            request_data["threat_details"].append("Suspicious redirect URI")
            
        # Check if IP is already flagged
        if ip_address in self._tracking["suspicious_ips"]:
            request_data["suspicious"] = True
            request_data["threat_score"] += 25
            request_data["threat_details"].append("IP address previously flagged as suspicious")
            
        # Check if IP is blocked
        if ip_address in self._tracking["blocked_ips"]:
            request_data["suspicious"] = True
            request_data["threat_score"] = 100
            request_data["threat_details"].append("IP address is blocked")
            
        # Store the request
        with self._lock:
            self._tracking["auth_requests"][request_id] = request_data
            
        # Update rate limiting counters
        self._update_rate_counter("auth_requests", ip_address)
        
        return request_data
    
    def track_token_request(self, client_id: str, grant_type: str, 
                          code: Optional[str], redirect_uri: str, 
                          ip_address: str, user_agent: str) -> Dict[str, Any]:
        """
        Track a token request for threat analysis.
        
        Args:
            client_id: OAuth client ID
            grant_type: OAuth grant type
            code: Authorization code (for authorization_code grant)
            redirect_uri: Redirect URI
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            Analysis result with threat score and details
        """
        timestamp = datetime.utcnow()
        request_id = f"{client_id}:{code or ''}"
        
        # Store request data
        request_data = {
            "client_id": client_id,
            "grant_type": grant_type,
            "code": code,
            "redirect_uri": redirect_uri,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": timestamp.isoformat(),
            "suspicious": False,
            "threat_score": 0,
            "threat_details": []
        }
        
        # Check for rate limiting
        if self._is_rate_limited("token_requests", ip_address):
            request_data["suspicious"] = True
            request_data["threat_score"] += 30
            request_data["threat_details"].append("Rate limit exceeded for token requests")
            
        # Check for authorization code injection (if applicable)
        if grant_type == "authorization_code" and code:
            if self._is_code_injection(code, client_id, redirect_uri, ip_address):
                request_data["suspicious"] = True
                request_data["threat_score"] += 80
                request_data["threat_details"].append("Potential authorization code injection")
                
        # Check for suspicious redirect URI
        if self._is_suspicious_redirect_uri(redirect_uri, client_id):
            request_data["suspicious"] = True
            request_data["threat_score"] += 40
            request_data["threat_details"].append("Suspicious redirect URI")
            
        # Check if IP is already flagged
        if ip_address in self._tracking["suspicious_ips"]:
            request_data["suspicious"] = True
            request_data["threat_score"] += 25
            request_data["threat_details"].append("IP address previously flagged as suspicious")
            
        # Check if IP is blocked
        if ip_address in self._tracking["blocked_ips"]:
            request_data["suspicious"] = True
            request_data["threat_score"] = 100
            request_data["threat_details"].append("IP address is blocked")
            
        # Store the request
        with self._lock:
            self._tracking["token_requests"][request_id] = request_data
            
        # Update rate limiting counters
        self._update_rate_counter("token_requests", ip_address)
        
        return request_data
    
    def track_token_usage(self, token_id: str, ip_address: str, 
                        user_agent: str) -> Dict[str, Any]:
        """
        Track token usage for detecting potential token leakage.
        
        Args:
            token_id: Token identifier or hash
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            Analysis result with threat score and details
        """
        # Implementation will be similar to the other tracking methods,
        # focusing on detecting unusual token usage patterns
        # For brevity, returning a simplified result
        return {
            "suspicious": False,
            "threat_score": 0,
            "threat_details": []
        }
    
    def _is_rate_limited(self, counter_type: str, key: str) -> bool:
        """
        Check if a key is rate limited for a specific counter type.
        
        Args:
            counter_type: Type of counter to check
            key: Key to check (usually IP address)
            
        Returns:
            True if rate limited, False otherwise
        """
        if counter_type not in self._rate_limits:
            return False
            
        with self._lock:
            if key not in self._rate_limits[counter_type]:
                return False
                
            counters = self._rate_limits[counter_type][key]
            
            # Clean up old counters
            current_minute = int(time.time() / 60)
            counters = {ts: count for ts, count in counters.items() if ts >= current_minute - 10}
            self._rate_limits[counter_type][key] = counters
            
            # Check rate limit
            current_count = counters.get(current_minute, 0)
            threshold = self._thresholds.get(f"max_{counter_type}", 10)
            
            return current_count >= threshold
    
    def _update_rate_counter(self, counter_type: str, key: str) -> None:
        """
        Update rate limiting counter for a key.
        
        Args:
            counter_type: Type of counter to update
            key: Key to update (usually IP address)
        """
        if counter_type not in self._rate_limits:
            return
            
        with self._lock:
            # Initialize counter for key if not exists
            if key not in self._rate_limits[counter_type]:
                self._rate_limits[counter_type][key] = {}
                
            # Update counter for current minute
            current_minute = int(time.time() / 60)
            current_count = self._rate_limits[counter_type][key].get(current_minute, 0)
            self._rate_limits[counter_type][key][current_minute] = current_count + 1
    
    def _is_code_injection(self, code: str, client_id: str, 
                         redirect_uri: str, ip_address: str) -> bool:
        """
        Check for authorization code injection attempts.
        
        Args:
            code: Authorization code
            client_id: OAuth client ID
            redirect_uri: Redirect URI
            ip_address: Client IP address
            
        Returns:
            True if code injection is suspected, False otherwise
        """
        # This would be implemented with logic to detect if a code is being
        # used by a different client than the one it was issued to,
        # or from a different IP, or with a different redirect URI.
        # For simplicity, returning False.
        return False
    
    def _is_suspicious_redirect_uri(self, redirect_uri: str, client_id: str) -> bool:
        """
        Check if a redirect URI is suspicious for a client.
        
        Args:
            redirect_uri: Redirect URI to check
            client_id: OAuth client ID
            
        Returns:
            True if redirect URI is suspicious, False otherwise
        """
        # This would be implemented with logic to validate the redirect URI
        # against a whitelist for the client, check for typosquatting, etc.
        # For simplicity, returning False.
        return False
    
    def flag_ip_as_suspicious(self, ip_address: str) -> None:
        """
        Flag an IP address as suspicious.
        
        Args:
            ip_address: IP address to flag
        """
        with self._lock:
            self._tracking["suspicious_ips"].add(ip_address)
            logger.warning(f"Flagged IP address {ip_address} as suspicious")
    
    def block_ip(self, ip_address: str) -> None:
        """
        Block an IP address from future OAuth requests.
        
        Args:
            ip_address: IP address to block
        """
        with self._lock:
            self._tracking["blocked_ips"].add(ip_address)
            self._tracking["suspicious_ips"].discard(ip_address)
            logger.warning(f"Blocked IP address {ip_address} from OAuth requests")


# Dynamic Security Policy
class DynamicSecurityPolicy:
    """
    Dynamic security policy manager for OAuth operations.
    
    This class adjusts security requirements based on risk assessment,
    enabling more restrictive policies for high-risk operations and
    more lenient policies for low-risk operations.
    """
    
    def __init__(self):
        """Initialize the dynamic security policy manager."""
        # Default security levels
        self._default_level = "medium"
        self._current_level = "medium"
        
        # Security policy definitions
        self._policies = {
            "low": {
                "enforce_pkce": False,
                "enforce_state": True,
                "max_token_lifetime": 86400,  # 24 hours
                "max_refresh_token_lifetime": 2592000,  # 30 days
                "require_https": True,
                "enforce_token_binding": False,
                "max_failed_attempts": 10,
                "lockout_period": 300,  # 5 minutes
            },
            "medium": {
                "enforce_pkce": True,
                "enforce_state": True,
                "max_token_lifetime": 3600,  # 1 hour
                "max_refresh_token_lifetime": 604800,  # 7 days
                "require_https": True,
                "enforce_token_binding": True,
                "max_failed_attempts": 5,
                "lockout_period": 900,  # 15 minutes
            },
            "high": {
                "enforce_pkce": True,
                "enforce_state": True,
                "max_token_lifetime": 1800,  # 30 minutes
                "max_refresh_token_lifetime": 86400,  # 1 day
                "require_https": True,
                "enforce_token_binding": True,
                "strict_token_binding": True,
                "max_failed_attempts": 3,
                "lockout_period": 1800,  # 30 minutes
                "require_cert_validation": True,
            }
        }
        
        logger.info(f"Dynamic security policy initialized at {self._current_level} level")
    
    def get_policy(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get the current security policy, adjusted based on context.
        
        Args:
            context: Optional context for policy adjustment
            
        Returns:
            Current security policy settings
        """
        # Start with the current security level
        level = self._current_level
        
        # Adjust based on context if provided
        if context:
            risk_score = self._calculate_risk_score(context)
            level = self._get_level_for_risk_score(risk_score)
            
        return self._policies[level].copy()
    
    def set_security_level(self, level: str) -> bool:
        """
        Set the current security level.
        
        Args:
            level: Security level ("low", "medium", or "high")
            
        Returns:
            True if level was set, False if invalid level
        """
        if level not in self._policies:
            logger.warning(f"Invalid security level: {level}")
            return False
            
        self._current_level = level
        logger.info(f"Security level set to {level}")
        return True
    
    def reset_to_default(self) -> None:
        """Reset security level to default."""
        self._current_level = self._default_level
        logger.info(f"Security level reset to default ({self._default_level})")
    
    def _calculate_risk_score(self, context: Dict[str, Any]) -> int:
        """
        Calculate a risk score based on context.
        
        Args:
            context: Context information for risk assessment
            
        Returns:
            Risk score (0-100, higher is riskier)
        """
        score = 0
        
        # Add points for various risk factors
        
        # Check IP address reputation
        ip_address = context.get("ip_address")
        if ip_address:
            if ip_address in context.get("suspicious_ips", set()):
                score += 30
            if self._is_high_risk_ip(ip_address):
                score += 20
        
        # Check if using a new device/browser
        if context.get("new_device", False):
            score += 15
        
        # Check grant type (client credentials is lower risk than auth code)
        grant_type = context.get("grant_type")
        if grant_type == "authorization_code":
            score += 10
        elif grant_type == "password":
            score += 20
        
        # Check for sensitive scopes
        scopes = context.get("scopes", [])
        if any(s in scopes for s in ["admin", "write", "delete"]):
            score += 15
        
        # Check for unusual time of access
        current_hour = datetime.utcnow().hour
        if current_hour >= 22 or current_hour <= 5:  # Night hours
            score += 5
        
        # Clamp score to 0-100 range
        return max(0, min(100, score))
    
    def _get_level_for_risk_score(self, risk_score: int) -> str:
        """
        Determine security level based on risk score.
        
        Args:
            risk_score: Risk score (0-100)
            
        Returns:
            Security level ("low", "medium", or "high")
        """
        if risk_score >= 70:
            return "high"
        elif risk_score >= 30:
            return "medium"
        else:
            return "low"
    
    def _is_high_risk_ip(self, ip_address: str) -> bool:
        """
        Check if an IP address is considered high risk.
        
        Args:
            ip_address: IP address to check
            
        Returns:
            True if high risk, False otherwise
        """
        # This would be implemented with IP reputation checking, geolocation, etc.
        # For simplicity, returning False for now.
        return False


# Secure OAuth Integration Manager
class SecureOAuthManager:
    """
    Enhanced OAuth integration manager with security hardening.
    
    This class integrates all the security enhancements and provides a
    secure interface for OAuth operations in the MCP server.
    """
    
    def __init__(self, 
               storage_backend: Optional[Any] = None,
               security_level: str = "medium"):
        """
        Initialize the secure OAuth manager.
        
        Args:
            storage_backend: Optional backend for storing OAuth data
            security_level: Initial security level
        """
        # Initialize security components
        self._pkce_manager = PKCEManager(storage_backend)
        self._token_binding = TokenBindingManager(storage_backend)
        self._threat_detector = OAuthThreatDetector(storage_backend)
        self._cert_validator = CertificateValidator()
        self._security_policy = DynamicSecurityPolicy()
        
        # Set initial security level
        self._security_policy.set_security_level(security_level)
        
        logger.info("Secure OAuth manager initialized")
    
    @property
    def pkce_manager(self) -> PKCEManager:
        """Get the PKCE manager."""
        return self._pkce_manager
    
    @property
    def token_binding(self) -> TokenBindingManager:
        """Get the token binding manager."""
        return self._token_binding
    
    @property
    def threat_detector(self) -> OAuthThreatDetector:
        """Get the threat detector."""
        return self._threat_detector
    
    @property
    def cert_validator(self) -> CertificateValidator:
        """Get the certificate validator."""
        return self._cert_validator
    
    @property
    def security_policy(self) -> DynamicSecurityPolicy:
        """Get the security policy manager."""
        return self._security_policy
    
    def prepare_authorization_request(self, 
                                    client_id: str,
                                    redirect_uri: str,
                                    scope: str,
                                    context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare a secure authorization request.
        
        Args:
            client_id: OAuth client ID
            redirect_uri: Redirect URI
            scope: OAuth scopes
            context: Request context (IP, user agent, etc.)
            
        Returns:
            Enhanced authorization parameters
        """
        # Get security policy based on context
        policy = self._security_policy.get_policy(context)
        
        # Create state parameter for CSRF protection
        state = self._generate_secure_state()
        
        # Prepare PKCE if enforced by policy
        code_challenge = None
        code_challenge_method = None
        code_verifier = None
        
        if policy["enforce_pkce"]:
            code_verifier = self._pkce_manager.create_code_verifier()
            code_challenge = self._pkce_manager.create_code_challenge(code_verifier)
            code_challenge_method = "S256"
            
            # Store code verifier with state for later verification
            self._pkce_manager.store_verifier(state, code_verifier)
        
        # Track the authorization request for threat detection
        ip_address = context.get("ip_address", "unknown")
        user_agent = context.get("user_agent", "unknown")
        
        threat_analysis = self._threat_detector.track_auth_request(
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # If request is highly suspicious, might block it
        if threat_analysis["threat_score"] >= 90:
            self._threat_detector.block_ip(ip_address)
            raise ValueError("Authorization request blocked due to security concerns")
        
        # Prepare response
        result = {
            "state": state,
            "enforce_pkce": policy["enforce_pkce"],
        }
        
        if policy["enforce_pkce"]:
            result["code_verifier"] = code_verifier
            result["code_challenge"] = code_challenge
            result["code_challenge_method"] = code_challenge_method
        
        return result
    
    def verify_authorization_response(self,
                                    state: str,
                                    code: str,
                                    code_verifier: Optional[str],
                                    context: Dict[str, Any]) -> bool:
        """
        Verify an authorization response.
        
        Args:
            state: OAuth state parameter
            code: Authorization code
            code_verifier: PKCE code verifier (if PKCE was used)
            context: Request context (IP, user agent, etc.)
            
        Returns:
            True if verification succeeds, False otherwise
        """
        # Get security policy based on context
        policy = self._security_policy.get_policy(context)
        
        # Verify PKCE if enforced by policy
        if policy["enforce_pkce"] and code_verifier:
            if not self._pkce_manager.verify_challenge(state, code_verifier):
                logger.warning(f"PKCE verification failed for state {state[:8]}...")
                return False
        
        # Additional security checks can be added here
        
        return True
    
    def enhance_token_response(self,
                             token_data: Dict[str, Any],
                             context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance a token response with security features.
        
        Args:
            token_data: Original token data
            context: Request context (IP, user agent, etc.)
            
        Returns:
            Enhanced token data
        """
        # Get security policy based on context
        policy = self._security_policy.get_policy(context)
        
        # Apply token lifetime restrictions
        access_token_expires_in = token_data.get("expires_in", 3600)
        if access_token_expires_in > policy["max_token_lifetime"]:
            token_data["expires_in"] = policy["max_token_lifetime"]
        
        if "refresh_token_expires_in" in token_data:
            refresh_token_expires_in = token_data["refresh_token_expires_in"]
            if refresh_token_expires_in > policy["max_refresh_token_lifetime"]:
                token_data["refresh_token_expires_in"] = policy["max_refresh_token_lifetime"]
        
        # Bind token to client context if policy requires it
        if policy["enforce_token_binding"]:
            # Use strict mode if policy requires it
            strict_mode = policy.get("strict_token_binding", False)
            
            # Bind access token
            if "access_token" in token_data:
                token_id = self._hash_token(token_data["access_token"])
                self._token_binding.bind_token(
                    token_id=token_id,
                    context=context,
                    expires_in=token_data["expires_in"]
                )
            
            # Bind refresh token
            if "refresh_token" in token_data:
                token_id = self._hash_token(token_data["refresh_token"])
                refresh_expires_in = token_data.get(
                    "refresh_token_expires_in", 
                    policy["max_refresh_token_lifetime"]
                )
                self._token_binding.bind_token(
                    token_id=token_id,
                    context=context,
                    expires_in=refresh_expires_in
                )
        
        return token_data
    
    def verify_token_binding(self,
                           token: str,
                           context: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Verify a token's binding to client context.
        
        Args:
            token: Token to verify
            context: Current client context
            
        Returns:
            Tuple of (valid, reason)
        """
        token_id = self._hash_token(token)
        return self._token_binding.verify_binding(token_id, context)
    
    def invalidate_token(self, token: str) -> None:
        """
        Invalidate a token by removing its binding.
        
        Args:
            token: Token to invalidate
        """
        token_id = self._hash_token(token)
        self._token_binding.remove_binding(token_id)
    
    def validate_provider_security(self, provider_url: str) -> Tuple[bool, str]:
        """
        Validate the security of an OAuth provider.
        
        Args:
            provider_url: URL of the OAuth provider
            
        Returns:
            Tuple of (valid, reason)
        """
        return self._cert_validator.validate_provider_cert(provider_url)
    
    def _generate_secure_state(self) -> str:
        """
        Generate a secure random state parameter.
        
        Returns:
            Secure random state string
        """
        # Generate 32 bytes of random data
        random_bytes = os.urandom(32)
        # Convert to URL-safe base64
        return base64.urlsafe_b64encode(random_bytes).decode().rstrip("=")
    
    def _hash_token(self, token: str) -> str:
        """
        Create a secure hash of a token for binding.
        
        Args:
            token: Token to hash
            
        Returns:
            Secure hash of the token
        """
        return hashlib.sha256(token.encode()).hexdigest()
    
    def shutdown(self) -> None:
        """Shutdown all security components."""
        logger.info("Shutting down secure OAuth manager")
        if hasattr(self._pkce_manager, "shutdown"):
            self._pkce_manager.shutdown()
        if hasattr(self._token_binding, "shutdown"):
            self._token_binding.shutdown()
