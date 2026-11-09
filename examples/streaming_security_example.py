import logging
import os
import tempfile
from ipfs_kit_py.high_level_api import IPFSSimpleAPI
# Assuming StreamingSecurityManager might be accessible or its logic testable
# If not directly exposed, this example shows the intended concepts.
# from ipfs_kit_py.streaming_security import StreamingSecurityManager # For type hinting if needed

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
# !! IMPORTANT: Use environment variables or a secure method for secrets in production !!
SECRET_KEY = os.environ.get("IPFS_KIT_SECRET_KEY", "a_weak_default_secret_key_for_example_only")
if SECRET_KEY == "a_weak_default_secret_key_for_example_only":
    logging.warning("Using a default weak secret key. Set IPFS_KIT_SECRET_KEY environment variable for security.")

config = {
    'streaming_security': {
        'enabled': True,
        'secret_key': SECRET_KEY,
        'token_expiry_seconds': 600, # 10 minutes for example
        'rate_limits': {
            'default': {'limit': 50, 'period': 60},
        },
        'encryption': {
            'enabled': True,
        }
        # Add 'allowed_origins' if needed for WebSocket testing
    },
    # API might be needed if testing actual endpoints, but this example focuses on the manager logic
    # 'api': { 'enabled': True, 'port': 8081 },
    # Add other necessary configurations for IPFS connection if needed
    # 'ipfs': { ... }
}

def main():
    logging.info("Initializing IPFSSimpleAPI with Streaming Security enabled.")
    try:
        kit = IPFSSimpleAPI(config=config)
        logging.info("IPFSSimpleAPI initialized.")

        # --- Accessing the Security Manager (Hypothetical) ---
        # NOTE: Direct access to the manager might not be exposed in the public API.
        # This example assumes access for demonstration or that these operations
        # happen internally when using secured endpoints.
        # Replace with actual access method if available.
        security_manager = getattr(kit, '_streaming_security_manager', None) # Attempt internal access

        if not security_manager:
            logging.warning("Could not directly access StreamingSecurityManager. Proceeding with conceptual demonstration.")
            # In a real scenario without direct access, you'd test security by interacting
            # with secured API endpoints (e.g., WebSocket connections with tokens).
            # We'll simulate the manager's expected behavior here.
            from ipfs_kit_py.streaming_security import StreamingSecurityManager
            security_manager = StreamingSecurityManager(**config['streaming_security'])


        # --- Token Generation ---
        user_id = "alice@example.com"
        user_role = "premium_user"
        permissions = ["read_data", "stream_video"]
        # Let's assume we have a CID for a specific video Alice should access
        allowed_cid = "QmVideoCIDPlaceholderForAlice"

        logging.info(f"Generating token for user: {user_id}, role: {user_role}")
        token = security_manager.create_token(
            user_id=user_id,
            user_role=user_role,
            permissions=permissions,
            cid_access=[allowed_cid] # Embed specific CID access directly in token if needed
        )
        logging.info(f"Generated Token: {token[:15]}...") # Show only prefix

        # --- Token Verification ---
        logging.info("Verifying the generated token...")
        try:
            claims = security_manager.verify_token(token)
            logging.info(f"Token verified successfully. Claims: {claims}")
        except Exception as e:
            logging.error(f"Token verification failed: {e}")
            return

        # --- Content Policy ---
        restricted_cid = "QmRestrictedContentCIDPlaceholder"
        logging.info(f"Setting content policy for CID: {restricted_cid}")
        security_manager.set_content_policy(
            cid=restricted_cid,
            allowed_roles=["admin", "editor"], # Only admins or editors can access
            required_permissions=["view_restricted"]
        )
        logging.info("Content policy set.")

        # --- Access Check ---
        logging.info(f"Checking Alice's access to {allowed_cid} (should pass based on token)...")
        can_access_allowed = security_manager.check_content_access(allowed_cid, claims)
        logging.info(f"Access to {allowed_cid}: {can_access_allowed}")

        logging.info(f"Checking Alice's access to {restricted_cid} (should fail based on policy)...")
        can_access_restricted = security_manager.check_content_access(restricted_cid, claims)
        logging.info(f"Access to {restricted_cid}: {can_access_restricted}")

        # --- Encryption ---
        if config.get('streaming_security', {}).get('encryption', {}).get('enabled'):
            logging.info("Demonstrating encryption...")
            original_data = b"This is sensitive streaming data."
            logging.info(f"Original data: {original_data}")

            encrypted_data = security_manager.encrypt_content(original_data)
            logging.info(f"Encrypted data: {encrypted_data[:20]}...") # Show prefix

            decrypted_data = security_manager.decrypt_content(encrypted_data)
            logging.info(f"Decrypted data: {decrypted_data}")

            assert original_data == decrypted_data
            logging.info("Encryption/Decryption successful.")
        else:
            logging.info("Encryption is disabled in config, skipping demo.")

        # --- Rate Limiting (Conceptual) ---
        # Rate limiting is typically checked within endpoint handlers.
        # Example check:
        client_ip = "192.168.1.100" # Example client identifier
        logging.info(f"Simulating rate limit check for client: {client_ip}")
        for i in range(5): # Simulate 5 quick requests
            allowed = security_manager.check_rate_limit(client_ip, action_type="default")
            logging.info(f"Request {i+1} allowed: {allowed}")
            if not allowed:
                logging.warning("Rate limit potentially exceeded.")
                # time.sleep(1) # Wait if needed

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)

    finally:
        logging.info("Streaming security example finished.")

if __name__ == "__main__":
    main()
