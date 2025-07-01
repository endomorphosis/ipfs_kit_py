"""
Storage backend controllers for MCP server.

This package provides controllers for different storage backends:
- S3 (AWS S3 and compatible services)
- Hugging Face Hub (model and dataset repository)
- Storacha (Web3.Storage)
- Filecoin (Lotus API integration)
- Lassie (Filecoin/IPFS content retrieval)

These controllers handle HTTP requests related to storage operations
and delegate the business logic to the corresponding storage models.
"""

import logging

# Configure logger
logger = logging.getLogger(__name__)
