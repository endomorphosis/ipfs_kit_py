#!/usr/bin/env python3
"""
AI/ML Integrator for MCP Server

This module integrates the AI/ML components with the MCP server:
- Model Registry
- Dataset Manager
- Distributed Training
- Framework Integration

Part of the MCP Roadmap Phase 2: AI/ML Integration.
"""

import logging
import importlib
from typing import Optional, Dict, Any, List, Union, Callable
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp_ai_ml_integrator")

class AIMLIntegrator:
    """
    Integrator class for AI/ML functionality with MCP server.
    
    This class manages the initialization and registration of AI/ML
    components with the MCP server, including:
    - API routers for model registry and dataset management
    - Background workers for distributed training
    - Storage backends for model artifacts
    """
    
    def __init__(
        self,
        mcp_server = None,
        config: Optional[Dict[str, Any]] = None,
        storage_path: Optional[Union[str, Path]] = None,
        feature_flags: Optional[Dict[str, bool]] = None
    ):
        """
        Initialize the AI/ML integrator.
        
        Args:
            mcp_server: The MCP server instance to integrate with
            config: Configuration dictionary
            storage_path: Path for storing AI/ML artifacts
            feature_flags: Feature flags to enable/disable specific functionality
        """
        self.mcp_server = mcp_server
        self.config = config or {}
        
        # Ensure storage_path is a Path object
        if storage_path is None:
            self.storage_path = Path.home() / ".ipfs_kit" / "ai_ml"
        elif isinstance(storage_path, str):
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = storage_path
        self.feature_flags = feature_flags or {
            "model_registry": True,
            "dataset_manager": True,
            "distributed_training": False,
            "inference_service": False
        }
        
        # Components
        self.model_registry = None
        self.dataset_manager = None
        self.distributed_training = None
        self.framework_integration = None
        
        # API routers
        self.ai_api_router = None
        self.model_registry_router = None
        self.dataset_manager_router = None
        
        # Initialization status
        self.initialized = False
        
        logger.info("AI/ML Integrator created")

    def initialize(self) -> bool:
        """
        Initialize AI/ML components.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        logger.info("Initializing AI/ML components...")
        
        try:
            # Ensure storage path exists
            Path(self.storage_path).mkdir(parents=True, exist_ok=True)
            
            # Initialize components based on feature flags
            initialized_components = []
            
            # Initialize Model Registry if enabled
            if self.feature_flags.get("model_registry", True):
                self._init_model_registry()
                initialized_components.append("model_registry")
            
            # Initialize Dataset Manager if enabled
            if self.feature_flags.get("dataset_manager", True):
                self._init_dataset_manager()
                initialized_components.append("dataset_manager")
            
            # Initialize Distributed Training if enabled
            if self.feature_flags.get("distributed_training", False):
                self._init_distributed_training()
                initialized_components.append("distributed_training")
            
            # Initialize Framework Integration if any ML framework integration is enabled
            if self.feature_flags.get("framework_integration", False):
                self._init_framework_integration()
                initialized_components.append("framework_integration")
            
            # Initialize main AI API router that combines all endpoints
            self._init_api_router()
            initialized_components.append("ai_api_router")
            
            logger.info(f"AI/ML initialization complete. Components: {', '.join(initialized_components)}")
            self.initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Error initializing AI/ML components: {e}")
            self.initialized = False
            return False

    def _init_model_registry(self) -> bool:
        """Initialize the model registry component."""
        try:
            from .model_registry import ModelRegistry, get_instance
            
            # Get or create model registry instance
            model_registry_path = str(self.storage_path / "models")
            self.model_registry = get_instance(
                storage_path=model_registry_path,
                config=self.config.get("model_registry", {})
            )
            
            # Import router creation function if available
            try:
                from .model_registry_router import create_model_registry_router
                self.model_registry_router = create_model_registry_router(
                    model_registry=self.model_registry
                )
            except ImportError:
                logger.warning("Model Registry Router not available")
                self.model_registry_router = None
            
            logger.info("Model Registry initialized")
            return True
        except ImportError as e:
            logger.warning(f"Model Registry module not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Error initializing Model Registry: {e}")
            return False

    def _init_dataset_manager(self) -> bool:
        """Initialize the dataset manager component."""
        try:
            from .dataset_manager import DatasetManager, get_instance
            
            # Get or create dataset manager instance
            dataset_manager_path = str(self.storage_path / "datasets")
            self.dataset_manager = get_instance(
                storage_path=dataset_manager_path,
                config=self.config.get("dataset_manager", {})
            )
            
            # Import router creation function if available
            try:
                from .dataset_manager_router import create_dataset_manager_router
                self.dataset_manager_router = create_dataset_manager_router(
                    dataset_manager=self.dataset_manager
                )
            except ImportError:
                logger.warning("Dataset Manager Router not available")
                self.dataset_manager_router = None
            
            logger.info("Dataset Manager initialized")
            return True
        except ImportError as e:
            logger.warning(f"Dataset Manager module not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Error initializing Dataset Manager: {e}")
            return False

    def _init_distributed_training(self) -> bool:
        """Initialize the distributed training component."""
        try:
            # Create a stub implementation since the module may not exist yet
            class DistributedTraining:
                def __init__(self, config=None):
                    self.config = config or {}
                    logger.info("Initialized distributed training component (stub implementation)")
            
            # Initialize distributed training
            self.distributed_training = DistributedTraining(
                config=self.config.get("distributed_training", {})
            )
            
            logger.info("Distributed Training initialized")
            return True
        except ImportError as e:
            logger.warning(f"Distributed Training module not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Error initializing Distributed Training: {e}")
            return False

    def _init_framework_integration(self) -> bool:
        """Initialize the framework integration component."""
        try:
            # Create a stub implementation since the module may not exist yet
            class FrameworkIntegration:
                def __init__(self, config=None):
                    self.config = config or {}
                    logger.info("Initialized framework integration component (stub implementation)")
            
            # Initialize framework integration
            self.framework_integration = FrameworkIntegration(
                config=self.config.get("framework_integration", {})
            )
            
            logger.info("Framework Integration initialized")
            return True
        except ImportError as e:
            logger.warning(f"Framework Integration module not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Error initializing Framework Integration: {e}")
            return False

    def _init_api_router(self) -> bool:
        """Initialize the main AI API router."""
        try:
            from .api_router import create_ai_api_router
            
            # Create API router with model registry
            self.ai_api_router = create_ai_api_router(
                model_registry=self.model_registry
            )
            
            logger.info("AI API Router initialized")
            return True
        except ImportError as e:
            logger.warning(f"AI API Router module not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Error initializing AI API Router: {e}")
            return False

    def register_with_server(self, mcp_server=None, prefix="/ai") -> bool:
        """
        Register AI/ML components with the MCP server.
        
        Args:
            mcp_server: MCP server instance (uses self.mcp_server if None)
            prefix: URL prefix for AI/ML endpoints
            
        Returns:
            True if registration was successful, False otherwise
        """
        server = mcp_server or self.mcp_server
        if not server:
            logger.error("Cannot register AI/ML components: No MCP server provided")
            return False
        
        if not self.initialized:
            logger.warning("AI/ML components not initialized. Initializing now...")
            if not self.initialize():
                logger.error("Failed to initialize AI/ML components")
                return False
        
        try:
            # Register AI API router with server's FastAPI app
            if hasattr(server, "register_router") and self.ai_api_router:
                server.register_router(self.ai_api_router, prefix=prefix)
                logger.info(f"Registered AI API router with prefix {prefix}")
            elif hasattr(server, "app") and self.ai_api_router:
                # Direct registration with FastAPI app
                server.app.include_router(self.ai_api_router, prefix=prefix)
                logger.info(f"Registered AI API router directly with FastAPI app, prefix {prefix}")
            else:
                # Try to find a router attribute or register_with_app method
                if hasattr(server, "router") and self.ai_api_router:
                    server.router.include_router(self.ai_api_router, prefix=prefix)
                    logger.info(f"Registered AI API router with server router, prefix {prefix}")
                elif hasattr(server, "register_with_app") and self.ai_api_router:
                    server.register_with_app(app=server.app, prefix=prefix)
                    logger.info(f"Registered AI API router using register_with_app, prefix {prefix}")
                else:
                    logger.warning("Could not register AI API router with server, no compatible registration method found")
                    return False
            
            # Save reference to MCP server
            self.mcp_server = server
            
            # Add AI/ML features to server's feature set if it has one
            if hasattr(server, "feature_set") and hasattr(server.feature_set, "add_features"):
                ai_ml_features = [
                    "ai_ml",
                    "model_registry" if self.model_registry else None,
                    "dataset_manager" if self.dataset_manager else None,
                    "distributed_training" if self.distributed_training else None,
                    "framework_integration" if self.framework_integration else None
                ]
                server.feature_set.add_features([f for f in ai_ml_features if f])
                logger.info("Added AI/ML features to server feature set")
            
            # Register with server's models/controllers dictionaries if they exist
            if hasattr(server, "models") and isinstance(server.models, dict):
                if self.model_registry:
                    server.models["ai_model_registry"] = self.model_registry
                if self.dataset_manager:
                    server.models["ai_dataset_manager"] = self.dataset_manager
                logger.info("Registered AI/ML models with server models dictionary")
            
            # Register with server's controllers dictionary if it exists
            if hasattr(server, "controllers") and isinstance(server.controllers, dict):
                server.controllers["ai_ml"] = self
                logger.info("Registered AI/ML integrator with server controllers dictionary")
            
            logger.info("Successfully registered AI/ML components with MCP server")
            return True
            
        except Exception as e:
            logger.error(f"Error registering AI/ML components with MCP server: {e}")
            return False

# Singleton instance
_instance = None

def get_instance(
    mcp_server=None,
    config=None,
    storage_path=None,
    feature_flags=None
) -> AIMLIntegrator:
    """
    Get or create the singleton instance of the AIMLIntegrator.
    
    Args:
        mcp_server: MCP server instance
        config: Configuration dictionary
        storage_path: Path for storing AI/ML artifacts
        feature_flags: Feature flags to enable/disable specific functionality
        
    Returns:
        AIMLIntegrator instance
    """
    global _instance
    if _instance is None:
        _instance = AIMLIntegrator(
            mcp_server=mcp_server,
            config=config,
            storage_path=storage_path,
            feature_flags=feature_flags
        )
    return _instance
