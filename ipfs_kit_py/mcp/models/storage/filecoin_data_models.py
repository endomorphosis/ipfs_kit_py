"""Filecoin Data Models

This module provides data models for Filecoin operations.
"""

from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field


class TipsetKeyModel(BaseModel):
    """Tipset key model for Filecoin operations."""
    
    cid: str = Field(..., description="The CID of the tipset")
    height: Optional[int] = Field(None, description="The height of the tipset")
    parents: Optional[List[str]] = Field(None, description="Parent tipset CIDs")


class FilecoinDeal(BaseModel):
    """Model for Filecoin storage deals."""
    
    deal_id: str = Field(..., description="The ID of the storage deal")
    status: str = Field(..., description="Current status of the deal")
    provider: str = Field(..., description="Storage provider address")
    start_epoch: int = Field(..., description="Deal start epoch")
    end_epoch: int = Field(..., description="Deal end epoch")
    price_per_epoch: float = Field(..., description="Price per epoch")
    verified: bool = Field(False, description="Whether this is a verified deal")
    client_address: str = Field(..., description="Client address")
    created_at: str = Field(..., description="Creation timestamp")
    message_cid: Optional[str] = Field(None, description="Message CID")
    cid: str = Field(..., description="The CID of the stored content")


class FilecoinTipset(BaseModel):
    """Model for Filecoin tipsets."""
    
    height: int = Field(..., description="The height of the tipset")
    key: List[str] = Field(..., description="The CIDs that form the tipset key")
    timestamp: int = Field(..., description="The timestamp of the tipset")
    blocks: List[Dict[str, Any]] = Field(..., description="The blocks in the tipset")