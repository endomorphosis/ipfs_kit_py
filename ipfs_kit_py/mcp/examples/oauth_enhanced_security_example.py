#!/usr/bin/env python3
"""
OAuth Enhanced Security Example

This example demonstrates how to use the enhanced security features for OAuth
integration in the MCP server, showing how to mitigate common OAuth vulnerabilities
and implement best practices for secure OAuth authentication.

Key features demonstrated:
1. PKCE implementation for secure authorization code flow
2. Token binding to prevent token theft and misuse
3. Advanced threat detection for common OAuth attacks
4. Certificate validation for OAuth providers
5. Dynamic security policies based on risk assessment

Usage:
  python oauth_enhanced_security_example.py
"""

import os
import sys
import asyncio
import json
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("oauth-security-example")

# Import OAuth enhanced security components
try:
    from ipfs_kit_py.mcp.auth.oauth_enhanced_security import (
        PKCEManager,
        TokenBindingManager,
        OAuthThreatDetector,
        CertificateValidator,
        DynamicSecurityPolicy,
        SecureOAuthManager
    )
except ImportError:
    logger.error("Failed to import OAuth enhanced security modules. Make sure ipfs_kit_py is installed")
    sys.exit(1)

# Try importing FastAPI for the web server example
try:
    from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
    from fastapi.responses import JSONResponse, RedirectResponse
    from fastapi.security import OAuth2PasswordBearer
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    logger.warning("FastAPI not available. Web server example will be skipped.")
    HAS_FASTAPI = False

# Try importing Redis for distributed storage
try:
    import redis
    HAS_REDIS = True
except ImportError:
    logger.warning("Redis not available. Using in-memory storage.")
    HAS_REDIS = False

# Mock storage backend for example purposes
class MemoryStorage:
    """Simple in-memory storage for example purposes."""
    
    def __init__(self):
        self._storage = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Any:
        """Get a value from storage."""
        async with self._lock:
            return self._storage.get(key)
    
    async def set(self, key: str, value: Any, expires_in: int = 0) -> None:
        """Set a value in storage with optional expiration."""
        expiry = None
        if expires_in > 0:
            expiry = datetime.utcnow() + timedelta(seconds=expires_in)
            
        async with self._lock:
            self._storage[key] = {
                "value": value,
                "expires_at": expiry
            }
    
    async def delete(self, key: str) -> None:
        """Delete a value from storage."""
        async with self._lock:
            if key in self._storage:
                del self._storage[key]
    
    async def cleanup(self) -> None:
        """Clean up expired entries."""
        now = datetime.utcnow()
        keys_to_delete = []
        
        async with self._lock:
            for key, item in self._storage.items():
                if item["expires_at"] and now > item["expires_at"]:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self._storage[key]


# Example scenarios and demonstrations
async def demonstrate_pkce():
    """Demonstrate PKCE (Proof Key for Code Exchange) for authorization code flow."""
    logger.info("=== PKCE (Proof Key for Code Exchange) Demonstration ===")
    
    # Create PKCE manager
    pkce = PKCEManager()
    
    # Step 1: Create a code verifier and challenge (client side)
    code_verifier = pkce.create_code_verifier(length=64)
    code_challenge = pkce.create_code_challenge(code_verifier, method="S256")
    
    logger.info(f"Generated code verifier: {code_verifier[:16]}... (length: {len(code_verifier)})")
    logger.info(f"Generated code challenge: {code_challenge[:16]}... (length: {len(code_challenge)})")
    
    # Step 2: Store verifier associated with state (server side)
    state = "abc123"  # In a real app, this would be a secure random value
    pkce.store_verifier(state, code_verifier, expires_in=600)
    logger.info(f"Stored code verifier for state: {state}")
    
    # Step 3: Verify the challenge (server side after callback)
    # Successful case
    valid = pkce.verify_challenge(state, code_verifier)
    logger.info(f"Verification with correct verifier: {'SUCCESS' if valid else 'FAILURE'}")
    
    # Failed case - wrong verifier
    wrong_verifier = pkce.create_code_verifier()
    pkce.store_verifier(state, code_verifier)  # Store again since it was removed in previous step
    valid = pkce.verify_challenge(state, wrong_verifier)
    logger.info(f"Verification with incorrect verifier: {'SUCCESS' if valid else 'FAILURE'}")
    
    # Show how this prevents authorization code injection attacks
    logger.info("\nPKCE prevents authorization code injection attacks by ensuring that only the")
    logger.info("original client that initiated the OAuth flow can exchange the authorization")
    logger.info("code for tokens, even if the code is somehow intercepted.")


async def demonstrate_token_binding():
    """Demonstrate token binding to prevent token theft and misuse."""
    logger.info("\n=== Token Binding Demonstration ===")
    
    # Create token binding manager
    binding_manager = TokenBindingManager(strict_mode=False)
    
    # Step 1: Bind a token to a client context
    token_id = "1234567890abcdef"
    original_context = {
        "ip_address": "192.168.1.100",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36",
        "device_id": "device123"
    }
    
    binding_manager.bind_token(token_id, original_context, expires_in=3600)
    logger.info(f"Bound token {token_id} to original context")
    
    # Step 2: Verify token with same context
    valid, reason = binding_manager.verify_binding(token_id, original_context)
    logger.info(f"Verification with same context: {'SUCCESS' if valid else 'FAILURE'} - {reason}")
    
    # Step 3: Verify token with different IP but same user agent (should succeed in non-strict mode)
    similar_context = original_context.copy()
    similar_context["ip_address"] = "192.168.1.101"  # Different IP in same subnet
    
    valid, reason = binding_manager.verify_binding(token_id, similar_context)
    logger.info(f"Verification with different IP in same subnet: {'SUCCESS' if valid else 'FAILURE'} - {reason}")
    
    # Step 4: Verify token with completely different context (should fail)
    different_context = {
        "ip_address": "10.0.0.1",
        "user_agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Safari/537.36",
        "device_id": "device456"
    }
    
    valid, reason = binding_manager.verify_binding(token_id, different_context)
    logger.info(f"Verification with completely different context: {'SUCCESS' if valid else 'FAILURE'} - {reason}")
    
    # Step 5: Demonstrate with strict mode
    strict_binding_manager = TokenBindingManager(strict_mode=True)
    strict_binding_manager.bind_token(token_id, original_context, expires_in=3600)
    
    # In strict mode, even minor changes should cause verification to fail
    valid, reason = strict_binding_manager.verify_binding(token_id, similar_context)
    logger.info(f"Strict mode - verification with slightly different context: {'SUCCESS' if valid else 'FAILURE'} - {reason}")
    
    logger.info("\nToken binding helps prevent token theft by ensuring that tokens can only")
    logger.info("be used from the same or similar contexts (devices, browsers, networks) as")
    logger.info("when they were originally issued.")


async def demonstrate_threat_detection():
    """Demonstrate OAuth threat detection features."""
    logger.info("\n=== OAuth Threat Detection Demonstration ===")
    
    # Create threat detector
    detector = OAuthThreatDetector()
    
    # Scenario 1: Normal authorization request
    normal_request = detector.track_auth_request(
        client_id="client123",
        redirect_uri="https://example.com/callback",
        state="abc123",
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"
    )
    
    logger.info(f"Normal authorization request:")
    logger.info(f"  Suspicious: {normal_request['suspicious']}")
    logger.info(f"  Threat score: {normal_request['threat_score']}")
    
    # Scenario 2: Excessive authorization requests from same IP
    # Simulate multiple requests to trigger rate limiting
    for _ in range(15):  # More than max_auth_requests threshold
        detector._update_rate_counter("auth_requests", "192.168.1.200")
    
    suspicious_request = detector.track_auth_request(
        client_id="client123",
        redirect_uri="https://example.com/callback",
        state="def456",
        ip_address="192.168.1.200",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"
    )
    
    logger.info(f"\nSuspicious authorization request (rate limited):")
    logger.info(f"  Suspicious: {suspicious_request['suspicious']}")
    logger.info(f"  Threat score: {suspicious_request['threat_score']}")
    logger.info(f"  Threat details: {suspicious_request['threat_details']}")
    
    # Scenario 3: Request from a blocked IP
    detector.block_ip("10.0.0.1")
    
    blocked_request = detector.track_auth_request(
        client_id="client123",
        redirect_uri="https://example.com/callback",
        state="ghi789",
        ip_address="10.0.0.1",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"
    )
    
    logger.info(f"\nRequest from blocked IP:")
    logger.info(f"  Suspicious: {blocked_request['suspicious']}")
    logger.info(f"  Threat score: {blocked_request['threat_score']}")
    logger.info(f"  Threat details: {blocked_request['threat_details']}")
    
    logger.info("\nThreat detection helps identify and prevent common OAuth attacks by")
    logger.info("monitoring patterns such as excessive requests, abnormal token usage,")
    logger.info("and suspicious redirect URIs.")


async def demonstrate_dynamic_security_policy():
    """Demonstrate dynamic security policies based on risk assessment."""
    logger.info("\n=== Dynamic Security Policy Demonstration ===")
    
    # Create policy manager
    policy_manager = DynamicSecurityPolicy()
    
    # Scenario 1: Low-risk context (trusted IP, non-sensitive scope)
    low_risk_context = {
        "ip_address": "192.168.1.100",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36",
        "new_device": False,
        "grant_type": "client_credentials",
        "scopes": ["read"]
    }
    
    low_risk_policy = policy_manager.get_policy(low_risk_context)
    logger.info("Low-risk context security policy:")
    for key, value in low_risk_policy.items():
        logger.info(f"  {key}: {value}")
    
    # Scenario 2: Medium-risk context (new device, authorization code flow)
    medium_risk_context = {
        "ip_address": "192.168.1.100",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36",
        "new_device": True,
        "grant_type": "authorization_code",
        "scopes": ["read", "write"]
    }
    
    medium_risk_policy = policy_manager.get_policy(medium_risk_context)
    logger.info("\nMedium-risk context security policy:")
    for key, value in medium_risk_policy.items():
        logger.info(f"  {key}: {value}")
    
    # Scenario 3: High-risk context (suspicious IP, sensitive scopes)
    high_risk_context = {
        "ip_address": "10.0.0.1",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36",
        "new_device": True,
        "grant_type": "password",
        "scopes": ["read", "write", "admin", "delete"],
        "suspicious_ips": set(["10.0.0.1"])
    }
    
    high_risk_policy = policy_manager.get_policy(high_risk_context)
    logger.info("\nHigh-risk context security policy:")
    for key, value in high_risk_policy.items():
        logger.info(f"  {key}: {value}")
    
    logger.info("\nDynamic security policies allow the system to adapt security requirements")
    logger.info("based on the risk level of each request, providing stronger protections")
    logger.info("for high-risk operations while maintaining usability for low-risk operations.")


async def demonstrate_integrated_security():
    """Demonstrate integrated OAuth security with all components."""
    logger.info("\n=== Integrated OAuth Security Demonstration ===")
    
    # Create secure OAuth manager
    oauth_manager = SecureOAuthManager()
    
    # Scenario: Secure authorization flow
    
    # Step 1: Prepare authorization request
    client_id = "client123"
    redirect_uri = "https://example.com/callback"
    scope = "read write"
    context = {
        "ip_address": "192.168.1.100",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36",
        "new_device": False
    }
    
    auth_params = oauth_manager.prepare_authorization_request(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        context=context
    )
    
    logger.info("Secure authorization request parameters:")
    for key, value in auth_params.items():
        if key == "code_verifier":
            logger.info(f"  {key}: {value[:16]}...")
        else:
            logger.info(f"  {key}: {value}")
    
    # Step 2: Verify authorization response
    state = auth_params["state"]
    code = "AUTHORIZATION_CODE"  # This would come from the OAuth provider
    code_verifier = auth_params.get("code_verifier")
    
    verification_result = oauth_manager.verify_authorization_response(
        state=state,
        code=code,
        code_verifier=code_verifier,
        context=context
    )
    
    logger.info(f"\nAuthorization response verification: {'SUCCESS' if verification_result else 'FAILURE'}")
    
    # Step 3: Enhance token response with security features
    token_data = {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
        "expires_in": 86400  # 24 hours
    }
    
    enhanced_token_data = oauth_manager.enhance_token_response(
        token_data=token_data,
        context=context
    )
    
    logger.info("\nEnhanced token response:")
    logger.info(f"  expires_in: {enhanced_token_data['expires_in']} seconds")
    
    # Step 4: Verify token binding
    valid, reason = oauth_manager.verify_token_binding(
        token=enhanced_token_data["access_token"],
        context=context
    )
    
    logger.info(f"\nToken binding verification: {'SUCCESS' if valid else 'FAILURE'} - {reason}")
    
    # Step 5: Verify with different context (simulating token theft)
    different_context = {
        "ip_address": "10.0.0.1",
        "user_agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Safari/537.36",
    }
    
    valid, reason = oauth_manager.verify_token_binding(
        token=enhanced_token_data["access_token"],
        context=different_context
    )
    
    logger.info(f"Token binding verification (different context): {'SUCCESS' if valid else 'FAILURE'} - {reason}")
    
    logger.info("\nThe integrated security approach combines all the protection mechanisms")
    logger.info("to provide comprehensive security for the entire OAuth flow, preventing")
    logger.info("various attacks and ensuring secure token handling.")


async def run_demo():
    """Run all the demonstrations."""
    logger.info("OAuth Enhanced Security Demonstrations")
    logger.info("=====================================")
    
    await demonstrate_pkce()
    await demonstrate_token_binding()
    await demonstrate_threat_detection()
    await demonstrate_dynamic_security_policy()
    await demonstrate_integrated_security()
    
    logger.info("\n=== Summary ===")
    logger.info("These demonstrations show how the enhanced OAuth security features")
    logger.info("protect against common OAuth vulnerabilities:")
    logger.info("1. PKCE prevents authorization code interception attacks")
    logger.info("2. Token binding prevents token theft and misuse")
    logger.info("3. Threat detection identifies and blocks suspicious activity")
    logger.info("4. Dynamic security policies adapt protection based on risk")
    logger.info("5. Certificate validation ensures secure provider connections")


def create_fastapi_app():
    """Create a FastAPI application demonstrating OAuth security integration."""
    if not HAS_FASTAPI:
        logger.error("FastAPI is not available. Cannot create web server example.")
        return None
    
    app = FastAPI(title="OAuth Enhanced Security Demo", version="1.0.0")
    
    # Create secure OAuth manager
    oauth_manager = SecureOAuthManager()
    
    # Store code verifiers and tokens (would use a database in production)
    verifiers = {}
    tokens = {}
    
    @app.get("/")
    async def home():
        """Home page with links to demo endpoints."""
        return {
            "message": "OAuth Enhanced Security Demo",
            "endpoints": {
                "/authorize": "Start OAuth flow with PKCE",
                "/callback": "OAuth callback (simulated)",
                "/token": "Exchange code for tokens",
                "/protected": "Protected resource requiring token",
                "/security-report": "View security status"
            }
        }
    
    @app.get("/authorize")
    async def authorize(
        client_id: str = "client123",
        redirect_uri: str = "http://localhost:8000/callback",
        scope: str = "read write",
        response_type: str = "code"
    ):
        """Initiate OAuth authorization with PKCE."""
        # Get client context from request
        context = {
            "ip_address": "192.168.1.100",  # Would extract from request in production
            "user_agent": "Example Browser/1.0",  # Would extract from request in production
            "new_device": False
        }
        
        try:
            # Prepare secure authorization request
            auth_params = oauth_manager.prepare_authorization_request(
                client_id=client_id,
                redirect_uri=redirect_uri,
                scope=scope,
                context=context
            )
            
            # Store state and code verifier for later verification
            verifiers[auth_params["state"]] = {
                "code_verifier": auth_params.get("code_verifier"),
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "expires_at": datetime.utcnow() + timedelta(minutes=10)
            }
            
            # In a real implementation, this would redirect to the OAuth provider
            # For this demo, we'll simulate by redirecting to our own callback
            # with a simulated authorization code
            
            # Generate a simulated authorization code
            auth_code = f"AUTH_CODE_{auth_params['state'][:8]}"
            
            # Redirect to callback with code and state
            callback_uri = f"{redirect_uri}?code={auth_code}&state={auth_params['state']}"
            return RedirectResponse(callback_uri)
            
        except ValueError as e:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": str(e)}
            )
    
    @app.get("/callback")
    async def callback(code: str, state: str):
        """Handle OAuth callback with PKCE verification."""
        # Check if state exists
        if state not in verifiers:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Invalid or expired state parameter"}
            )
        
        verifier_data = verifiers[state]
        
        # Check if expired
        if datetime.utcnow() > verifier_data["expires_at"]:
            del verifiers[state]
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "State parameter has expired"}
            )
        
        # In a real implementation, the code would be exchanged with the OAuth provider
        # For this demo, we'll simulate successful verification
        
        # Display a form to continue the flow with code_verifier
        html_content = f"""
        <html>
            <head><title>OAuth Callback</title></head>
            <body>
                <h1>OAuth Callback Received</h1>
                <p>Code: {code}</p>
                <p>State: {state}</p>
                <h2>Complete Authentication</h2>
                <p>In a real OAuth flow, the client would automatically exchange the code for tokens using the code_verifier.</p>
                <p>For this demo, click the button to simulate this process:</p>
                <form action="/token" method="post">
                    <input type="hidden" name="code" value="{code}">
                    <input type="hidden" name="state" value="{state}">
                    <input type="hidden" name="code_verifier" value="{verifier_data['code_verifier']}">
                    <input type="hidden" name="redirect_uri" value="{verifier_data['redirect_uri']}">
                    <input type="hidden" name="client_id" value="{verifier_data['client_id']}">
                    <input type="hidden" name="grant_type" value="authorization_code">
                    <button type="submit">Exchange Code for Tokens</button>
                </form>
            </body>
        </html>
        """
        
        return Response(content=html_content, media_type="text/html")
    
    @app.post("/token")
    async def token(request: Request):
        """Exchange authorization code for tokens with PKCE verification."""
        form_data = await request.form()
        code = form_data.get("code")
        state = form_data.get("state")
        code_verifier = form_data.get("code_verifier")
        redirect_uri = form_data.get("redirect_uri")
        client_id = form_data.get("client_id")
        grant_type = form_data.get("grant_type")
        
        # Check if state exists
        if state not in verifiers:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "Invalid or expired state parameter"}
            )
        
        verifier_data = verifiers[state]
        
        # Check if expired
        if datetime.utcnow() > verifier_data["expires_at"]:
            del verifiers[state]
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "State parameter has expired"}
            )
        
        # Get client context from request
        context = {
            "ip_address": "192.168.1.100",  # Would extract from request in production
            "user_agent": "Example Browser/1.0",  # Would extract from request in production
        }
        
        # Verify authorization response
        verification_result = oauth_manager.verify_authorization_response(
            state=state,
            code=code,
            code_verifier=code_verifier,
            context=context
        )
        
        if not verification_result:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "PKCE verification failed"}
            )
        
        # In a real implementation, the code would be exchanged with the OAuth provider
        # For this demo, we'll simulate successful token issuance
        
        # Generate simulated tokens
        token_data = {
            "access_token": f"ACCESS_TOKEN_{state[:8]}",
            "refresh_token": f"REFRESH_TOKEN_{state[:8]}",
            "token_type": "bearer",
            "expires_in": 3600  # 1 hour
        }
        
        # Enhance token response with security features
        enhanced_token_data = oauth_manager.enhance_token_response(
            token_data=token_data,
            context=context
        )
        
        # Store token for later use
        tokens[enhanced_token_data["access_token"]] = {
            "data": enhanced_token_data,
            "context": context
        }
        
        # Clean up verifier
        del verifiers[state]
        
        return enhanced_token_data
    
    @app.get("/protected")
    async def protected_resource(request: Request):
        """Access protected resource with token binding verification."""
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Missing or invalid Authorization header"}
            )
        
        token = auth_header.replace("Bearer ", "")
        
        # Check if token exists
        if token not in tokens:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Invalid token"}
            )
        
        # Get client context from request
        context = {
            "ip_address": "192.168.1.100",  # Would extract from request in production
            "user_agent": "Example Browser/1.0",  # Would extract from request in production
        }
        
        # Verify token binding
        valid, reason = oauth_manager.verify_token_binding(
            token=token,
            context=context
        )
        
        if not valid:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": f"Token binding verification failed: {reason}"}
            )
        
        # Success! Return protected resource
        return {
            "message": "You have accessed a protected resource",
            "token_info": {
                "expires_in": tokens[token]["data"]["expires_in"],
                "scope": "read write"
            }
        }
    
    @app.get("/security-report")
    async def security_report():
        """Get security status report."""
        return {
            "security_level": "high",
            "enabled_protections": {
                "pkce": True,
                "token_binding": True,
                "threat_detection": True,
                "certificate_validation": True
            },
            "active_sessions": len(tokens),
            "pending_authorizations": len(verifiers)
        }
    
    return app


def run_fastapi_example():
    """Run the FastAPI example server."""
    app = create_fastapi_app()
    if not app:
        return
    
    logger.info("\nStarting OAuth Enhanced Security Demo Server")
    logger.info("Visit http://localhost:8000/ to begin the demo")
    logger.info("Available endpoints:")
    logger.info("  GET /authorize - Start OAuth flow with PKCE")
    logger.info("  GET /callback - OAuth callback (simulated)")
    logger.info("  POST /token - Exchange code for tokens")
    logger.info("  GET /protected - Protected resource requiring token")
    logger.info("  GET /security-report - View security status")
    
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OAuth Enhanced Security Example")
    parser.add_argument("--server", action="store_true", help="Run FastAPI server example")
    args = parser.parse_args()
    
    if args.server and HAS_FASTAPI:
        run_fastapi_example()
    else:
        asyncio.run(run_demo())
