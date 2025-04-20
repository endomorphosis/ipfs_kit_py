"""
Type stubs for model_registry_router module.
These type annotations help with static type checking.
"""

from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, UploadFile, File, Form, Query, Path, Body
from .model_registry import ModelRegistry, Model, ModelVersion

def create_model_registry_router(model_registry: ModelRegistry) -> APIRouter:
    """Create a FastAPI router for the model registry."""
    ...
