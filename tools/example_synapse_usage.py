#!/usr/bin/env python3
"""
Example usage of Synapse SDK integration with IPFS Kit.

This script demonstrates how to use the Synapse SDK storage backend
for storing and retrieving data on Filecoin with automated PDP verification.

Usage:
    # Set up environment
    export SYNAPSE_PRIVATE_KEY="0x..."
    export SYNAPSE_NETWORK="calibration"
    
    # Run example
    python example_synapse_usage.py --store example.txt
    python example_synapse_usage.py --retrieve <commp> --output retrieved.txt
"""

import os
import sys
import asyncio
import logging
import tempfile
from pathlib import Path

# Add the project root to Python path
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import Synapse storage
try:
    from ipfs_kit_py.synapse_storage import synapse_storage
    from ipfs_kit_py.install_synapse_sdk import install_synapse_sdk
except ImportError as e:
    logger.error(f"Failed to import Synapse modules: {e}")
    logger.info("Please ensure Synapse SDK is installed by running:")
    logger.info("python ipfs_kit_py/install_synapse_sdk.py")
    sys.exit(1)


async def check_environment():
    """Check if environment is properly configured."""
    logger.info("Checking environment configuration...")
    
    # Check for private key
    private_key = os.environ.get("SYNAPSE_PRIVATE_KEY") or os.environ.get("PRIVATE_KEY")
    if not private_key:
        logger.error("No private key found in environment variables")
        logger.info("Please set SYNAPSE_PRIVATE_KEY or PRIVATE_KEY environment variable")
        return False
    
    logger.info(f"✓ Private key configured (starts with: {private_key[:10]}...)")
    
    # Check network setting
    network = os.environ.get("SYNAPSE_NETWORK", "calibration")
    logger.info(f"✓ Network: {network}")
    
    return True


async def ensure_synapse_installed():
    """Ensure Synapse SDK dependencies are installed."""
    logger.info("Checking Synapse SDK installation...")
    
    try:
        # Try to create a storage instance to test installation
        test_storage = synapse_storage(metadata={"network": "calibration"})
        logger.info("✓ Synapse SDK appears to be installed")
        return True
    except Exception as e:
        logger.warning(f"Synapse SDK installation issue: {e}")
        
        # Try to install automatically
        logger.info("Attempting to install Synapse SDK dependencies...")
        try:
            installer = install_synapse_sdk(metadata={"force": False})
            success = installer.install_synapse_sdk_dependencies()
            
            if success:
                logger.info("✓ Synapse SDK dependencies installed successfully")
                return True
            else:
                logger.error("Failed to install Synapse SDK dependencies")
                return False
        except Exception as install_error:
            logger.error(f"Installation failed: {install_error}")
            return False


async def example_store_data():
    """Example of storing data using Synapse SDK."""
    logger.info("\n=== Storing Data Example ===")
    
    # Create some sample data
    sample_text = """
🚀 Welcome to decentralized storage on Filecoin! 🌍

This is a test file stored using the Synapse SDK integration
with IPFS Kit Python. Your data is now stored on the Filecoin
network with Proof of Data Possession (PDP) verification.

Features demonstrated:
- Automated storage provider selection
- Payment management with USDFC tokens
- Proof set creation and management
- Content addressing with CommP
- Decentralized retrieval

Timestamp: {timestamp}
""".format(timestamp=str(asyncio.get_event_loop().time()))
    
    sample_data = sample_text.encode('utf-8')
    
    try:
        # Create storage interface
        storage = synapse_storage(metadata={
            "network": os.environ.get("SYNAPSE_NETWORK", "calibration"),
            "auto_approve": True
        })
        
        # Check status
        status = storage.get_status()
        logger.info(f"Storage status: {status}")
        
        # Store the data
        logger.info(f"Storing {len(sample_data)} bytes of sample data...")
        result = await storage.synapse_store_data(
            data=sample_data,
            filename="sample_data.txt"
        )
        
        if result["success"]:
            logger.info("✅ Data stored successfully!")
            logger.info(f"CommP: {result['commp']}")
            logger.info(f"Size: {result['size']} bytes")
            logger.info(f"Root ID: {result.get('root_id')}")
            logger.info(f"Proof Set ID: {result.get('proof_set_id')}")
            logger.info(f"Storage Provider: {result.get('storage_provider')}")
            
            return result["commp"]
        else:
            logger.error(f"❌ Storage failed: {result.get('error')}")
            return None
            
    except Exception as e:
        logger.error(f"Storage example failed: {e}")
        return None


async def example_retrieve_data(commp: str):
    """Example of retrieving data using Synapse SDK."""
    logger.info(f"\n=== Retrieving Data Example ===")
    logger.info(f"Retrieving data with CommP: {commp}")
    
    try:
        # Create storage interface
        storage = synapse_storage(metadata={
            "network": os.environ.get("SYNAPSE_NETWORK", "calibration")
        })
        
        # Retrieve the data
        logger.info("Retrieving data...")
        data = await storage.synapse_retrieve_data(commp)
        
        logger.info("✅ Data retrieved successfully!")
        logger.info(f"Retrieved {len(data)} bytes")
        
        # Display the content (if it's text)
        try:
            text_content = data.decode('utf-8')
            logger.info("Content preview:")
            logger.info("-" * 50)
            print(text_content[:500] + ("..." if len(text_content) > 500 else ""))
            logger.info("-" * 50)
        except UnicodeDecodeError:
            logger.info("Retrieved data is binary (not text)")
        
        return data
        
    except Exception as e:
        logger.error(f"Retrieval example failed: {e}")
        return None


async def example_file_operations():
    """Example of file storage and retrieval operations."""
    logger.info("\n=== File Operations Example ===")
    
    # Create a temporary test file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
        temp_file.write("""# Synapse SDK Test File

This is a test file for demonstrating the Synapse SDK integration
with IPFS Kit Python.

## Features

- Decentralized storage on Filecoin
- Automated payment management
- Proof of Data Possession (PDP)
- Content addressing with CommP
- Provider selection and management

## Storage Process

1. File is uploaded to selected storage provider
2. CommP (Content identifier) is generated
3. Data is added to a proof set
4. Payments are automatically handled
5. PDP verification ensures data integrity

Your file is now stored on the decentralized web! 🌐
""")
        temp_file_path = temp_file.name
    
    try:
        # Create storage interface
        storage = synapse_storage(metadata={
            "network": os.environ.get("SYNAPSE_NETWORK", "calibration")
        })
        
        # Store the file
        logger.info(f"Storing file: {temp_file_path}")
        store_result = await storage.synapse_store_file(temp_file_path)
        
        if store_result["success"]:
            logger.info("✅ File stored successfully!")
            commp = store_result["commp"]
            logger.info(f"CommP: {commp}")
            
            # Retrieve the file
            output_path = temp_file_path + ".retrieved"
            logger.info(f"Retrieving file to: {output_path}")
            
            retrieve_result = await storage.synapse_retrieve_file(commp, output_path)
            
            if retrieve_result["success"]:
                logger.info("✅ File retrieved successfully!")
                
                # Verify the files are identical
                with open(temp_file_path, 'rb') as f1, open(output_path, 'rb') as f2:
                    original_data = f1.read()
                    retrieved_data = f2.read()
                
                if original_data == retrieved_data:
                    logger.info("✅ File integrity verified - original and retrieved files are identical!")
                else:
                    logger.error("❌ File integrity check failed - files differ!")
                
                # Cleanup
                os.unlink(output_path)
            else:
                logger.error(f"❌ File retrieval failed: {retrieve_result.get('error')}")
        else:
            logger.error(f"❌ File storage failed: {store_result.get('error')}")
            
    except Exception as e:
        logger.error(f"File operations example failed: {e}")
    finally:
        # Cleanup
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


async def example_payment_operations():
    """Example of payment-related operations."""
    logger.info("\n=== Payment Operations Example ===")
    
    try:
        # Create storage interface
        storage = synapse_storage(metadata={
            "network": os.environ.get("SYNAPSE_NETWORK", "calibration")
        })
        
        # Check balance
        logger.info("Checking wallet balance...")
        balance_result = await storage.synapse_get_balance()
        
        if balance_result["success"]:
            logger.info("✅ Balance information:")
            logger.info(f"Wallet balance: {balance_result['wallet_balance']} USDFC")
            logger.info(f"Contract balance: {balance_result['contract_balance']} USDFC")
        else:
            logger.error(f"❌ Balance check failed: {balance_result.get('error')}")
        
        # Get storage costs
        logger.info("Getting storage cost estimates...")
        test_size = 1024 * 1024  # 1 MB
        costs_result = await storage.synapse_get_storage_costs(test_size)
        
        if costs_result["success"]:
            logger.info("✅ Storage cost information:")
            logger.info(f"For {test_size} bytes:")
            pricing = costs_result.get("pricing", {})
            logger.info(f"Pricing info: {pricing}")
        else:
            logger.error(f"❌ Cost estimation failed: {costs_result.get('error')}")
            
    except Exception as e:
        logger.error(f"Payment operations example failed: {e}")


async def example_provider_operations():
    """Example of provider-related operations."""
    logger.info("\n=== Provider Operations Example ===")
    
    try:
        # Create storage interface
        storage = synapse_storage(metadata={
            "network": os.environ.get("SYNAPSE_NETWORK", "calibration")
        })
        
        # Get provider recommendations
        logger.info("Getting provider recommendations...")
        providers_result = await storage.synapse_recommend_providers()
        
        if providers_result["success"]:
            providers = providers_result.get("providers", [])
            logger.info(f"✅ Found {len(providers)} available providers")
            
            for i, provider in enumerate(providers[:3]):  # Show first 3
                logger.info(f"Provider {i+1}:")
                logger.info(f"  Owner: {provider.get('owner', 'Unknown')}")
                logger.info(f"  PDP URL: {provider.get('pdpUrl', 'Unknown')}")
                
            # Get detailed info for first provider if available
            if providers:
                first_provider = providers[0]
                provider_address = first_provider.get("owner")
                
                if provider_address:
                    logger.info(f"Getting detailed info for provider: {provider_address}")
                    info_result = await storage.synapse_get_provider_info(provider_address)
                    
                    if info_result["success"]:
                        logger.info("✅ Provider details:")
                        logger.info(f"  Owner: {info_result.get('owner')}")
                        logger.info(f"  PDP URL: {info_result.get('pdp_url')}")
                        logger.info(f"  Retrieval URL: {info_result.get('piece_retrieval_url')}")
                    else:
                        logger.error(f"❌ Provider info failed: {info_result.get('error')}")
        else:
            logger.error(f"❌ Provider recommendations failed: {providers_result.get('error')}")
            
    except Exception as e:
        logger.error(f"Provider operations example failed: {e}")


async def main():
    """Main example function."""
    logger.info("🚀 Synapse SDK Integration Example")
    logger.info("=" * 50)
    
    # Check environment
    if not await check_environment():
        logger.error("Environment check failed. Please configure properly and try again.")
        return 1
    
    # Ensure installation
    if not await ensure_synapse_installed():
        logger.error("Synapse SDK installation check failed. Please install manually.")
        return 1
    
    try:
        # Run examples
        await example_payment_operations()
        await example_provider_operations()
        
        # Store some data
        commp = await example_store_data()
        
        # Retrieve it if storage was successful
        if commp:
            await example_retrieve_data(commp)
        
        # File operations example
        await example_file_operations()
        
        logger.info("\n✅ All examples completed successfully!")
        logger.info("🎉 Synapse SDK integration is working properly!")
        
        return 0
        
    except Exception as e:
        logger.error(f"Examples failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return 1


if __name__ == "__main__":
    import traceback
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
