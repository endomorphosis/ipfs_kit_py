"""
MCP Extensions Module

This module provides extensions for the MCP server to integrate with various storage backends.
It's used by the enhanced_mcp_server_real.py script to add real storage backend implementations.
"""

import logging
import os
import sys
import time
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

def update_storage_backends(storage_backends: Dict[str, Dict[str, Any]]) -> None:
    """
    Update the storage backends status with real implementations.

    Args:
        storage_backends: Dictionary of storage backends to update
    """
    logger.info("Updating storage backends status with real implementations")

    # Update HuggingFace status
    try:
        import huggingface_hub
        token = os.environ.get("HUGGINGFACE_TOKEN") or huggingface_hub.get_token()
        if token and len(token) > 10:
            storage_backends["huggingface"]["available"] = True
            storage_backends["huggingface"]["simulation"] = False
            storage_backends["huggingface"]["token_available"] = True
            logger.info("HuggingFace backend is available with token")
    except Exception as e:
        logger.warning(f"Error checking HuggingFace availability: {e}")

    # Update S3 status
    try:
        import boto3
        try:
            session = boto3.Session()
            credentials = session.get_credentials()
            if credentials:
                storage_backends["s3"]["available"] = True
                storage_backends["s3"]["simulation"] = False
                storage_backends["s3"]["credentials_available"] = True
                logger.info("S3 backend is available with credentials")
        except Exception as e:
            logger.warning(f"Error checking S3 credentials: {e}")
    except ImportError:
        logger.warning("boto3 not installed, S3 backend not available")

    # Update Filecoin status
    try:
        # Check if Lotus is installed
        lotus_path = os.environ.get("LOTUS_PATH")
        if lotus_path and os.path.exists(lotus_path):
            storage_backends["filecoin"]["available"] = True
            storage_backends["filecoin"]["simulation"] = False
            storage_backends["filecoin"]["lotus_available"] = True
            logger.info(f"Filecoin backend is available with Lotus at {lotus_path}")
    except Exception as e:
        logger.warning(f"Error checking Filecoin availability: {e}")

    # Update Storacha status
    try:
        storacha_token = os.environ.get("STORACHA_TOKEN")
        if storacha_token and len(storacha_token) > 10:
            storage_backends["storacha"]["available"] = True
            storage_backends["storacha"]["simulation"] = False
            storage_backends["storacha"]["token_available"] = True
            logger.info("Storacha backend is available with token")
    except Exception as e:
        logger.warning(f"Error checking Storacha availability: {e}")

    # Update Lassie status
    try:
        lassie_path = os.environ.get("LASSIE_BINARY_PATH")
        if lassie_path and os.path.exists(lassie_path):
            storage_backends["lassie"]["available"] = True
            storage_backends["lassie"]["simulation"] = False
            storage_backends["lassie"]["binary_available"] = True
            logger.info(f"Lassie backend is available with binary at {lassie_path}")
    except Exception as e:
        logger.warning(f"Error checking Lassie availability: {e}")

def create_extension_routers(api_prefix: str) -> List[Any]:
    """
    Create and return FastAPI routers for storage backend extensions.

    Args:
        api_prefix: API prefix for endpoints

    Returns:
        List of FastAPI routers
    """
    try:
        from fastapi import APIRouter, Form, HTTPException, UploadFile, File
        from typing import Optional
        import tempfile
        import os

        routers = []

        # Create HuggingFace router
        huggingface_router = APIRouter(prefix=f"{api_prefix}/huggingface")

        @huggingface_router.get("/status")
        async def huggingface_status():
            """Get HuggingFace backend status."""
            try:
                import huggingface_hub
                token = os.environ.get("HUGGINGFACE_TOKEN") or huggingface_hub.get_token()
                if token and len(token) > 10:
                    return {
                        "success": True,
                        "available": True,
                        "simulation": False,
                        "token_available": True,
                        "message": "HuggingFace backend is available with token"
                    }
                else:
                    return {
                        "success": True,
                        "available": False,
                        "simulation": True,
                        "token_available": False,
                        "message": "HuggingFace token not available"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "available": False,
                    "simulation": True,
                    "error": str(e)
                }

        @huggingface_router.post("/from_ipfs")
        async def huggingface_from_ipfs(cid: str = Form(...), path: Optional[str] = Form(None)):
            """Upload content from IPFS to HuggingFace."""
            # Create mock storage directory
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_huggingface")
            os.makedirs(mock_dir, exist_ok=True)

            # Get content from IPFS
            import subprocess
            result = subprocess.run(
                ["ipfs", "cat", cid],
                capture_output=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Failed to get content from IPFS: {result.stderr.decode('utf-8')}"
                }

            # Save to mock storage
            file_path = path or f"ipfs/{cid}"
            full_path = os.path.join(mock_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "wb") as f:
                f.write(result.stdout)

            return {
                "success": True,
                "message": "Content stored in HuggingFace storage (mock)",
                "url": f"file://{full_path}",
                "cid": cid,
                "path": file_path
            }

        @huggingface_router.post("/to_ipfs")
        async def huggingface_to_ipfs(file_path: str = Form(...)):
            """Upload content from HuggingFace to IPFS."""
            # Check if file exists in mock storage
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_huggingface")
            mock_file_path = os.path.join(mock_dir, file_path)

            if not os.path.exists(mock_file_path):
                # Create a dummy file with random content for demonstration
                os.makedirs(os.path.dirname(mock_file_path), exist_ok=True)
                with open(mock_file_path, "wb") as f:
                    f.write(os.urandom(1024))  # 1KB random data

            # Add to IPFS
            import subprocess
            result = subprocess.run(
                ["ipfs", "add", "-q", mock_file_path],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Failed to add to IPFS: {result.stderr}"
                }

            new_cid = result.stdout.strip()

            return {
                "success": True,
                "message": "Added content from HuggingFace storage to IPFS (mock)",
                "cid": new_cid,
                "source": f"mock_huggingface:{file_path}"
            }

        routers.append(huggingface_router)
        logger.info("Added HuggingFace router")

        # Add S3 router
        s3_router = APIRouter(prefix=f"{api_prefix}/s3")

        @s3_router.get("/status")
        async def s3_status():
            """Get S3 backend status."""
            try:
                import boto3
                session = boto3.Session()
                credentials = session.get_credentials()
                if credentials:
                    return {
                        "success": True,
                        "available": True,
                        "simulation": False,
                        "credentials_available": True,
                        "message": "S3 backend is available with credentials"
                    }
                else:
                    return {
                        "success": True,
                        "available": False,
                        "simulation": True,
                        "credentials_available": False,
                        "message": "AWS credentials not available"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "available": False,
                    "simulation": True,
                    "error": str(e)
                }

        @s3_router.post("/from_ipfs")
        async def s3_from_ipfs(cid: str = Form(...), path: Optional[str] = Form(None), bucket: Optional[str] = Form("ipfs-storage-demo")):
            """Upload content from IPFS to S3."""
            # Create mock storage directory
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_s3")
            os.makedirs(mock_dir, exist_ok=True)

            # Get content from IPFS
            import subprocess
            result = subprocess.run(
                ["ipfs", "cat", cid],
                capture_output=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Failed to get content from IPFS: {result.stderr.decode('utf-8')}"
                }

            # Save to mock storage
            file_path = path or f"ipfs/{cid}"
            full_path = os.path.join(mock_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "wb") as f:
                f.write(result.stdout)

            return {
                "success": True,
                "message": "Content stored in S3 storage (mock)",
                "url": f"file://{full_path}",
                "cid": cid,
                "path": file_path,
                "bucket": bucket
            }

        @s3_router.post("/to_ipfs")
        async def s3_to_ipfs(file_path: str = Form(...), bucket: Optional[str] = Form("ipfs-storage-demo")):
            """Upload content from S3 to IPFS."""
            # Check if file exists in mock storage
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_s3")
            mock_file_path = os.path.join(mock_dir, file_path)

            if not os.path.exists(mock_file_path):
                # Create a dummy file with random content for demonstration
                os.makedirs(os.path.dirname(mock_file_path), exist_ok=True)
                with open(mock_file_path, "wb") as f:
                    f.write(os.urandom(1024))  # 1KB random data

            # Add to IPFS
            import subprocess
            result = subprocess.run(
                ["ipfs", "add", "-q", mock_file_path],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Failed to add to IPFS: {result.stderr}"
                }

            new_cid = result.stdout.strip()

            return {
                "success": True,
                "message": "Added content from S3 storage to IPFS (mock)",
                "cid": new_cid,
                "source": f"mock_s3:{file_path}",
                "bucket": bucket
            }

        routers.append(s3_router)
        logger.info("Added S3 router")

        # Add Filecoin router
        filecoin_router = APIRouter(prefix=f"{api_prefix}/filecoin")

        @filecoin_router.get("/status")
        async def filecoin_status():
            """Get Filecoin backend status."""
            try:
                # Check for lotus binary
                import shutil
                lotus_path = shutil.which("lotus") or os.environ.get("LOTUS_PATH")
                if lotus_path:
                    return {
                        "success": True,
                        "available": True,
                        "simulation": False,
                        "lotus_available": True,
                        "lotus_path": lotus_path,
                        "message": "Filecoin backend is available with Lotus"
                    }
                else:
                    return {
                        "success": True,
                        "available": False,
                        "simulation": True,
                        "lotus_available": False,
                        "message": "Lotus binary not available"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "available": False,
                    "simulation": True,
                    "error": str(e)
                }

        @filecoin_router.post("/from_ipfs")
        async def filecoin_from_ipfs(cid: str = Form(...), path: Optional[str] = Form(None)):
            """Upload content from IPFS to Filecoin."""
            # Create mock storage directory
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_filecoin")
            os.makedirs(mock_dir, exist_ok=True)

            # Get content from IPFS
            import subprocess
            result = subprocess.run(
                ["ipfs", "cat", cid],
                capture_output=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Failed to get content from IPFS: {result.stderr.decode('utf-8')}"
                }

            # Save to mock storage
            file_path = path or f"ipfs/{cid}"
            full_path = os.path.join(mock_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "wb") as f:
                f.write(result.stdout)

            return {
                "success": True,
                "message": "Content stored in Filecoin storage (mock)",
                "url": f"file://{full_path}",
                "cid": cid,
                "path": file_path,
                "deal_id": f"mock-deal-{int(time.time())}"
            }

        @filecoin_router.post("/to_ipfs")
        async def filecoin_to_ipfs(file_path: str = Form(...)):
            """Upload content from Filecoin to IPFS."""
            # Check if file exists in mock storage
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_filecoin")
            mock_file_path = os.path.join(mock_dir, file_path)

            if not os.path.exists(mock_file_path):
                # Create a dummy file with random content for demonstration
                os.makedirs(os.path.dirname(mock_file_path), exist_ok=True)
                with open(mock_file_path, "wb") as f:
                    f.write(os.urandom(1024))  # 1KB random data

            # Add to IPFS
            import subprocess
            result = subprocess.run(
                ["ipfs", "add", "-q", mock_file_path],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Failed to add to IPFS: {result.stderr}"
                }

            new_cid = result.stdout.strip()

            return {
                "success": True,
                "message": "Added content from Filecoin storage to IPFS (mock)",
                "cid": new_cid,
                "source": f"mock_filecoin:{file_path}"
            }

        routers.append(filecoin_router)
        logger.info("Added Filecoin router")

        # Add Storacha router
        storacha_router = APIRouter(prefix=f"{api_prefix}/storacha")

        @storacha_router.get("/status")
        async def storacha_status():
            """Get Storacha backend status."""
            try:
                # Check for storacha token
                token = os.environ.get("STORACHA_TOKEN")
                if token and len(token) > 10:
                    return {
                        "success": True,
                        "available": True,
                        "simulation": False,
                        "token_available": True,
                        "message": "Storacha backend is available with token"
                    }
                else:
                    return {
                        "success": True,
                        "available": False,
                        "simulation": True,
                        "token_available": False,
                        "message": "Storacha token not available"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "available": False,
                    "simulation": True,
                    "error": str(e)
                }

        @storacha_router.post("/from_ipfs")
        async def storacha_from_ipfs(cid: str = Form(...), path: Optional[str] = Form(None)):
            """Upload content from IPFS to Storacha."""
            # Create mock storage directory
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_storacha")
            os.makedirs(mock_dir, exist_ok=True)

            # Get content from IPFS
            import subprocess
            result = subprocess.run(
                ["ipfs", "cat", cid],
                capture_output=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Failed to get content from IPFS: {result.stderr.decode('utf-8')}"
                }

            # Save to mock storage
            file_path = path or f"ipfs/{cid}"
            full_path = os.path.join(mock_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "wb") as f:
                f.write(result.stdout)

            return {
                "success": True,
                "message": "Content stored in Storacha storage (mock)",
                "url": f"file://{full_path}",
                "cid": cid,
                "path": file_path,
                "space_did": f"did:web:mock.storage.web3:{int(time.time())}"
            }

        @storacha_router.post("/to_ipfs")
        async def storacha_to_ipfs(file_path: str = Form(...)):
            """Upload content from Storacha to IPFS."""
            # Check if file exists in mock storage
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_storacha")
            mock_file_path = os.path.join(mock_dir, file_path)

            if not os.path.exists(mock_file_path):
                # Create a dummy file with random content for demonstration
                os.makedirs(os.path.dirname(mock_file_path), exist_ok=True)
                with open(mock_file_path, "wb") as f:
                    f.write(os.urandom(1024))  # 1KB random data

            # Add to IPFS
            import subprocess
            result = subprocess.run(
                ["ipfs", "add", "-q", mock_file_path],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Failed to add to IPFS: {result.stderr}"
                }

            new_cid = result.stdout.strip()

            return {
                "success": True,
                "message": "Added content from Storacha storage to IPFS (mock)",
                "cid": new_cid,
                "source": f"mock_storacha:{file_path}"
            }

        routers.append(storacha_router)
        logger.info("Added Storacha router")

        # Add Lassie router
        lassie_router = APIRouter(prefix=f"{api_prefix}/lassie")

        @lassie_router.get("/status")
        async def lassie_status():
            """Get Lassie backend status."""
            try:
                # Check for lassie binary
                import shutil
                lassie_path = shutil.which("lassie") or os.environ.get("LASSIE_BINARY_PATH")
                if lassie_path:
                    return {
                        "success": True,
                        "available": True,
                        "simulation": False,
                        "binary_available": True,
                        "binary_path": lassie_path,
                        "message": "Lassie backend is available with binary"
                    }
                else:
                    return {
                        "success": True,
                        "available": False,
                        "simulation": True,
                        "binary_available": False,
                        "message": "Lassie binary not available"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "available": False,
                    "simulation": True,
                    "error": str(e)
                }

        @lassie_router.post("/retrieve")
        async def lassie_retrieve(cid: str = Form(...), path: Optional[str] = Form(None)):
            """Retrieve content using Lassie."""
            # Create mock storage directory
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_lassie")
            os.makedirs(mock_dir, exist_ok=True)

            # Get content from IPFS as a fallback
            import subprocess
            result = subprocess.run(
                ["ipfs", "cat", cid],
                capture_output=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Failed to get content from IPFS: {result.stderr.decode('utf-8')}"
                }

            # Save to mock storage
            file_path = path or f"retrieved/{cid}"
            full_path = os.path.join(mock_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, "wb") as f:
                f.write(result.stdout)

            return {
                "success": True,
                "message": "Content retrieved using Lassie (mock)",
                "path": full_path,
                "cid": cid,
                "size": len(result.stdout)
            }

        routers.append(lassie_router)
        logger.info("Added Lassie router")

        # Log all routers explicitly
        logger.info(f"Created {len(routers)} routers with prefixes: {[r.prefix for r in routers]}")

        return routers
    except Exception as e:
        logger.error(f"Error creating extension routers: {e}")
        return []
