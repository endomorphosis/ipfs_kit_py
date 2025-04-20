#!/usr/bin/env python3
"""
Authentication & Authorization Verification Script

This script tests the core components of the Advanced Authentication & Authorization system
to verify proper functionality and integration with the MCP server.

Usage:
    python verify_auth_system.py [--url URL] [--output FILE] [--debug]
"""

import os
import sys
import json
import time
import asyncio
import argparse
import logging
import httpx
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("auth_verification")

# Default MCP server URL
DEFAULT_MCP_URL = "http://localhost:5000"

class AuthVerifier:
    """Authentication system verification tool."""
    
    def __init__(self, base_url: str, debug: bool = False):
        """Initialize auth verifier."""
        self.base_url = base_url
        self.debug = debug
        self.tokens = {}
        self.api_keys = {}
        self.test_users = {}
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=30.0,
            follow_redirects=True
        )
        
        # Set debug level if needed
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
        
        logger.info(f"Auth verifier initialized with base URL: {base_url}")
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    async def verify_all(self) -> Dict[str, Any]:
        """Run all verification tests."""
        results = {
            "success": True,
            "timestamp": time.time(),
            "tests": {}
        }
        
        try:
            # Verify system is running
            system_status = await self.verify_system_status()
            results["tests"]["system_status"] = system_status
            if not system_status.get("success", False):
                results["success"] = False
                return results
            
            # Get admin credentials if available
            admin_auth = await self.get_admin_auth()
            if admin_auth.get("success", False):
                self.tokens["admin"] = admin_auth.get("access_token")
            
            # Verify authentication components 
            auth_components = await self.verify_auth_components()
            results["tests"]["auth_components"] = auth_components
            
            # Verify user creation and authentication
            user_auth = await self.verify_user_auth()
            results["tests"]["user_auth"] = user_auth
            
            # Verify RBAC
            rbac = await self.verify_rbac()
            results["tests"]["rbac"] = rbac
            
            # Verify API key functionality
            api_keys = await self.verify_api_keys()
            results["tests"]["api_keys"] = api_keys
            
            # Verify OAuth endpoints
            oauth = await self.verify_oauth()
            results["tests"]["oauth"] = oauth
            
            # Clean up test data
            cleanup = await self.cleanup()
            results["tests"]["cleanup"] = cleanup
            
            # Set overall success
            for test_name, test_result in results["tests"].items():
                if not test_result.get("success", False):
                    results["success"] = False
                    break
            
            return results
        
        except Exception as e:
            logger.error(f"Error during verification: {e}")
            results["success"] = False
            results["error"] = str(e)
            return results
    
    async def verify_system_status(self) -> Dict[str, Any]:
        """Verify that the MCP server is running."""
        logger.info("Verifying system status...")
        
        try:
            response = await self.client.get("/api/v0/status")
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "details": response.text
                }
            
            data = response.json()
            if data.get("status") != "operational":
                return {
                    "success": False,
                    "error": f"System not operational: {data.get('status')}",
                    "details": data
                }
            
            return {
                "success": True,
                "details": data
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_admin_auth(self) -> Dict[str, Any]:
        """Authenticate as admin if credentials are available."""
        # Try to get admin credentials from environment
        admin_username = os.environ.get("MCP_ADMIN_USERNAME")
        admin_password = os.environ.get("MCP_ADMIN_PASSWORD")
        
        if not admin_username or not admin_password:
            return {
                "success": False,
                "error": "Admin credentials not available"
            }
        
        try:
            response = await self.client.post(
                "/api/v0/auth/login",
                json={
                    "username": admin_username,
                    "password": admin_password
                }
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "details": response.text
                }
            
            data = response.json()
            return {
                "success": True,
                "access_token": data.get("access_token"),
                "refresh_token": data.get("refresh_token")
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def verify_auth_components(self) -> Dict[str, Any]:
        """Verify that authentication components are initialized."""
        logger.info("Verifying authentication components...")
        
        if "admin" in self.tokens:
            # Use admin verification endpoint if available
            try:
                headers = {"Authorization": f"Bearer {self.tokens['admin']}"}
                response = await self.client.get("/api/v0/admin/auth/verify", headers=headers)
                
                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "details": response.text
                    }
                
                data = response.json()
                return {
                    "success": data.get("success", False),
                    "details": data.get("verification_result", {})
                }
            
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        else:
            # Check auth endpoints without admin token
            endpoints = [
                "/api/v0/auth/login",
                "/api/v0/rbac/roles",
                "/api/v0/auth/oauth/providers"
            ]
            
            failures = []
            for endpoint in endpoints:
                try:
                    response = await self.client.get(endpoint)
                    # For auth endpoints, 401 is expected when not authenticated
                    if response.status_code not in (200, 401):
                        failures.append({
                            "endpoint": endpoint,
                            "status_code": response.status_code
                        })
                except Exception as e:
                    failures.append({
                        "endpoint": endpoint,
                        "error": str(e)
                    })
            
            if failures:
                return {
                    "success": False,
                    "error": "Some auth endpoints are not available",
                    "failures": failures
                }
            
            return {
                "success": True,
                "details": "All core auth endpoints available"
            }
    
    async def verify_user_auth(self) -> Dict[str, Any]:
        """Verify user creation and authentication."""
        logger.info("Verifying user authentication...")
        
        # Only run if we have admin access
        if "admin" not in self.tokens:
            return {
                "success": False,
                "error": "Admin token required for user auth test"
            }
        
        try:
            admin_token = self.tokens["admin"]
            headers = {"Authorization": f"Bearer {admin_token}"}
            
            # 1. Create test user
            test_username = f"test_user_{int(time.time())}"
            test_password = "Test1234!"
            
            user_data = {
                "username": test_username,
                "password": test_password,
                "email": f"{test_username}@example.com",
                "role": "user"  # Use default user role
            }
            
            response = await self.client.post(
                "/api/v0/auth/users",
                json=user_data,
                headers=headers
            )
            
            if response.status_code not in (200, 201):
                return {
                    "success": False,
                    "error": f"User creation failed: HTTP {response.status_code}",
                    "details": response.text
                }
            
            # 2. Authenticate as new user
            auth_response = await self.client.post(
                "/api/v0/auth/login",
                json={
                    "username": test_username,
                    "password": test_password
                }
            )
            
            if auth_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"User authentication failed: HTTP {auth_response.status_code}",
                    "details": auth_response.text
                }
            
            auth_data = auth_response.json()
            access_token = auth_data.get("access_token")
            refresh_token = auth_data.get("refresh_token")
            
            if not access_token or not refresh_token:
                return {
                    "success": False,
                    "error": "Missing tokens in auth response",
                    "details": auth_data
                }
            
            # Store tokens for later tests
            self.tokens[test_username] = access_token
            self.tokens[f"{test_username}_refresh"] = refresh_token
            self.test_users[test_username] = {
                "username": test_username,
                "password": test_password
            }
            
            # 3. Test token by getting user info
            user_headers = {"Authorization": f"Bearer {access_token}"}
            me_response = await self.client.get("/api/v0/auth/users/me", headers=user_headers)
            
            if me_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"User info request failed: HTTP {me_response.status_code}",
                    "details": me_response.text
                }
            
            # 4. Test token refresh
            refresh_response = await self.client.post(
                "/api/v0/auth/refresh",
                json={"refresh_token": refresh_token}
            )
            
            refresh_success = refresh_response.status_code == 200
            
            return {
                "success": True,
                "details": {
                    "username": test_username,
                    "token_works": True,
                    "refresh_works": refresh_success
                }
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def verify_rbac(self) -> Dict[str, Any]:
        """Verify role-based access control."""
        logger.info("Verifying RBAC functionality...")
        
        # Need both admin token and a regular user token
        if "admin" not in self.tokens or not any(k for k in self.tokens.keys() if k != "admin" and not k.endswith("_refresh")):
            return {
                "success": False,
                "error": "Both admin and user tokens required for RBAC test"
            }
        
        try:
            admin_token = self.tokens["admin"]
            admin_headers = {"Authorization": f"Bearer {admin_token}"}
            
            # Get regular user
            test_user = next(k for k in self.tokens.keys() if k != "admin" and not k.endswith("_refresh"))
            user_token = self.tokens[test_user]
            user_headers = {"Authorization": f"Bearer {user_token}"}
            
            # 1. List roles
            roles_response = await self.client.get("/api/v0/rbac/roles", headers=user_headers)
            
            if roles_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Role listing failed: HTTP {roles_response.status_code}",
                    "details": roles_response.text
                }
            
            # 2. Check user permissions
            perm_response = await self.client.get(
                "/api/v0/rbac/check-permission?permission=read:ipfs",
                headers=user_headers
            )
            
            if perm_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Permission check failed: HTTP {perm_response.status_code}",
                    "details": perm_response.text
                }
            
            perm_data = perm_response.json()
            has_permission = perm_data.get("has_permission", False)
            
            # 3. Create custom role (admin only)
            custom_role = {
                "id": f"test_role_{int(time.time())}",
                "name": "Test Role",
                "description": "Role created by verification script",
                "permissions": ["read:ipfs", "read:search"],
                "parent_roles": ["user"]
            }
            
            role_response = await self.client.post(
                "/api/v0/rbac/roles",
                json=custom_role,
                headers=admin_headers
            )
            
            role_creation_success = role_response.status_code in (200, 201)
            
            return {
                "success": True,
                "details": {
                    "roles_listing_works": True,
                    "permission_check_works": True,
                    "has_read_ipfs": has_permission,
                    "role_creation_works": role_creation_success
                }
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def verify_api_keys(self) -> Dict[str, Any]:
        """Verify API key functionality."""
        logger.info("Verifying API key functionality...")
        
        # Need a regular user token
        user_token = None
        test_user = None
        for k, v in self.tokens.items():
            if k != "admin" and not k.endswith("_refresh"):
                test_user = k
                user_token = v
                break
        
        if not user_token:
            return {
                "success": False,
                "error": "User token required for API key test"
            }
        
        try:
            user_headers = {"Authorization": f"Bearer {user_token}"}
            
            # 1. Create API key
            key_data = {
                "name": f"Test Key {int(time.time())}",
                "permissions": "read:ipfs,read:search"
            }
            
            create_response = await self.client.post(
                "/api/v0/auth/apikeys",
                data=key_data,
                headers=user_headers
            )
            
            if create_response.status_code not in (200, 201):
                return {
                    "success": False,
                    "error": f"API key creation failed: HTTP {create_response.status_code}",
                    "details": create_response.text
                }
            
            key_result = create_response.json()
            
            # Extract API key (handle different response formats)
            api_key = None
            api_key_id = None
            
            if "api_key" in key_result:
                api_key = key_result["api_key"].get("key")
                api_key_id = key_result["api_key"].get("id")
            elif "key" in key_result:
                api_key = key_result["key"]
                api_key_id = key_result.get("id")
            
            if not api_key:
                return {
                    "success": False,
                    "error": "Missing API key in response",
                    "details": key_result
                }
            
            # Store API key
            self.api_keys[test_user] = {
                "key": api_key,
                "id": api_key_id
            }
            
            # 2. Use API key to authenticate
            api_headers = {"X-API-Key": api_key}
            me_response = await self.client.get("/api/v0/auth/users/me", headers=api_headers)
            
            api_key_works = me_response.status_code == 200
            
            # 3. List API keys
            list_response = await self.client.get("/api/v0/auth/apikeys", headers=user_headers)
            list_works = list_response.status_code == 200
            
            return {
                "success": True,
                "details": {
                    "key_creation_works": True,
                    "key_authentication_works": api_key_works,
                    "key_listing_works": list_works
                }
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def verify_oauth(self) -> Dict[str, Any]:
        """Verify OAuth endpoints."""
        logger.info("Verifying OAuth functionality...")
        
        try:
            # Check OAuth providers endpoint
            response = await self.client.get("/api/v0/auth/oauth/providers")
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"OAuth providers endpoint failed: HTTP {response.status_code}",
                    "details": response.text
                }
            
            providers_data = response.json()
            
            # Extract providers
            providers = []
            if "providers" in providers_data:
                providers = providers_data["providers"]
            elif isinstance(providers_data, list):
                providers = providers_data
            
            # Try to get login URL for first provider if available
            login_url_success = False
            if providers:
                provider_id = providers[0].get("id")
                if provider_id:
                    login_response = await self.client.get(f"/api/v0/auth/oauth/{provider_id}/login")
                    login_url_success = login_response.status_code == 200
            
            return {
                "success": True,
                "details": {
                    "providers_endpoint_works": True,
                    "providers_count": len(providers),
                    "login_url_endpoint_works": login_url_success
                }
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def cleanup(self) -> Dict[str, Any]:
        """Clean up test data."""
        logger.info("Cleaning up test data...")
        
        if "admin" not in self.tokens:
            return {
                "success": False,
                "error": "Admin token required for cleanup"
            }
        
        try:
            admin_headers = {"Authorization": f"Bearer {self.tokens['admin']}"}
            cleanup_results = {
                "users_deleted": [],
                "api_keys_deleted": [],
                "roles_deleted": []
            }
            
            # Delete test users
            for username, user in self.test_users.items():
                if "id" in user:
                    user_id = user["id"]
                    response = await self.client.delete(f"/api/v0/auth/users/{user_id}", headers=admin_headers)
                    if response.status_code in (200, 204):
                        cleanup_results["users_deleted"].append(username)
            
            # Delete API keys
            for user, api_key in self.api_keys.items():
                if user in self.tokens and "id" in api_key:
                    user_headers = {"Authorization": f"Bearer {self.tokens[user]}"}
                    response = await self.client.delete(
                        f"/api/v0/auth/apikeys/{api_key['id']}",
                        headers=user_headers
                    )
                    if response.status_code in (200, 204):
                        cleanup_results["api_keys_deleted"].append(api_key["id"])
            
            # Find and delete test roles
            roles_response = await self.client.get("/api/v0/rbac/roles", headers=admin_headers)
            if roles_response.status_code == 200:
                roles_data = roles_response.json()
                roles = []
                
                if "roles" in roles_data:
                    roles = roles_data["roles"]
                elif isinstance(roles_data, list):
                    roles = roles_data
                
                for role in roles:
                    role_id = role.get("id")
                    role_name = role.get("name", "")
                    
                    if role_id and ("test" in role_id.lower() or "test" in role_name.lower()):
                        response = await self.client.delete(f"/api/v0/rbac/roles/{role_id}", headers=admin_headers)
                        if response.status_code in (200, 204):
                            cleanup_results["roles_deleted"].append(role_id)
            
            return {
                "success": True,
                "details": cleanup_results
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


async def main():
    """Main function."""
    # Parse arguments
    parser = argparse.ArgumentParser(description="Auth System Verification")
    parser.add_argument("--url", default=DEFAULT_MCP_URL, help="MCP server URL")
    parser.add_argument("--output", help="Output file path for results")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    # Run verification
    verifier = AuthVerifier(args.url, args.debug)
    print("\n🔐 Starting Advanced Authentication & Authorization verification...")
    
    try:
        results = await verifier.verify_all()
        
        # Print summary
        print("\n✅ Verification complete.\n")
        print(f"Overall result: {'SUCCESS ✅' if results['success'] else 'FAILURE ❌'}")
        print("\nTest Results:")
        
        for test_name, test_result in results["tests"].items():
            test_success = test_result.get("success", False)
            status = "✅ PASS" if test_success else "❌ FAIL"
            print(f"  {status} - {test_name}")
            
            if not test_success and "error" in test_result:
                print(f"    Error: {test_result['error']}")
        
        # Save results if output file specified
        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\nDetailed results saved to: {args.output}")
        
        # Return exit code based on success
        return 0 if results["success"] else 1
    
    finally:
        await verifier.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))