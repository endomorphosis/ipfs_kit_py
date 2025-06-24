#!/usr/bin/env python3
"""
Explore the LibP2P crypto module structure to identify the correct key generation method.
"""

import sys
import inspect
import logging
import importlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("libp2p-explorer")

def explore_crypto_module():
    """Explore the libp2p.crypto module specifically for key generation."""
    try:
        import libp2p

        logger.info(f"LibP2P version: {libp2p.__version__ if hasattr(libp2p, '__version__') else 'unknown'}")

        # Import the crypto module
        from libp2p import crypto
        logger.info(f"Successfully imported libp2p.crypto")

        # Explore the keys module
        if hasattr(crypto, 'keys'):
            logger.info("Examining crypto.keys module...")
            for name in dir(crypto.keys):
                if name.startswith('_'):
                    continue

                attr = getattr(crypto.keys, name)
                if inspect.isclass(attr):
                    logger.info(f"Class: {name}")
                    # List all methods of the class
                    for method_name in dir(attr):
                        if method_name.startswith('_'):
                            continue
                        method = getattr(attr, method_name)
                        if inspect.ismethod(method) or inspect.isfunction(method):
                            logger.info(f"  Method: {method_name} - {inspect.signature(method)}")
                elif inspect.isfunction(attr):
                    logger.info(f"Function: {name} - {inspect.signature(attr)}")

        # Try to find all functions related to key generation
        for module_name in ['libp2p.crypto.keys', 'libp2p.crypto.ed25519', 'libp2p.crypto.secp256k1', 'libp2p.crypto.rsa']:
            try:
                module = importlib.import_module(module_name)
                logger.info(f"\nExploring {module_name}:")

                # Find all functions with "generate" in the name
                generate_funcs = [name for name in dir(module) if 'generate' in name.lower() and not name.startswith('_')]
                for func_name in generate_funcs:
                    func = getattr(module, func_name)
                    if inspect.isfunction(func):
                        logger.info(f"Found generator function: {func_name} - {inspect.signature(func)}")
                    elif inspect.isclass(func) and hasattr(func, 'generate'):
                        logger.info(f"Found class with generate method: {func_name}.generate")
            except ImportError:
                logger.warning(f"Could not import {module_name}")

        # Try specific key generation method based on documentation or examples
        logger.info("\nAttempting to generate keys using different methods:")

        try:
            logger.info("Trying: crypto.keys.KeyPair.generate()")
            key_pair = crypto.keys.KeyPair.generate()
            logger.info(f"Success! KeyPair.generate() works. Type: {type(key_pair)}")
        except Exception as e:
            logger.error(f"Failed with KeyPair.generate(): {str(e)}")

        try:
            logger.info("Trying: crypto.keys.generate_key_pair()")
            key_pair = crypto.keys.generate_key_pair()
            logger.info(f"Success! generate_key_pair() works. Type: {type(key_pair)}")
        except Exception as e:
            logger.error(f"Failed with generate_key_pair(): {str(e)}")

        # Try specific implementations
        from libp2p.crypto import rsa, ed25519, secp256k1

        try:
            logger.info("Trying: ed25519.Ed25519PrivateKey.generate()")
            key = ed25519.Ed25519PrivateKey.generate()
            logger.info(f"Success! Ed25519PrivateKey.generate() works. Type: {type(key)}")
        except Exception as e:
            logger.error(f"Failed with Ed25519PrivateKey.generate(): {str(e)}")

        try:
            logger.info("Trying: rsa.create_new_key_pair()")
            if hasattr(rsa, 'create_new_key_pair'):
                key_pair = rsa.create_new_key_pair()
                logger.info(f"Success! rsa.create_new_key_pair() works. Type: {type(key_pair)}")
        except Exception as e:
            logger.error(f"Failed with rsa.create_new_key_pair(): {str(e)}")

        try:
            logger.info("Trying: secp256k1.create_new_key_pair()")
            if hasattr(secp256k1, 'create_new_key_pair'):
                key_pair = secp256k1.create_new_key_pair()
                logger.info(f"Success! secp256k1.create_new_key_pair() works. Type: {type(key_pair)}")
        except Exception as e:
            logger.error(f"Failed with secp256k1.create_new_key_pair(): {str(e)}")

    except ImportError as e:
        logger.error(f"Failed to import libp2p: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    explore_crypto_module()
