"""
Migration API router for MCP server.

This module provides REST API endpoints for the cross-backend migration functionality
as specified in the MCP roadmap Q2 2025 priorities.
"""

import logging
from fastapi import APIRouter, Body, Depends, Query, Path
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from ...models.migration import (
    MigrationRequest,
    MigrationResponse,
    MigrationStatus
)

# Configure logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/migration", tags=["Migration"])
