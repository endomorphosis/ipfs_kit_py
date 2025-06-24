#!/usr/bin/env python3
"""
MCP Server Initializer for AI/ML

This script initializes the AI/ML components for the MCP server,
setting up the necessary environment and configuration.
"""

import os
import sys
import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("mcp-ai-init")

class MCPAIMLInitializer:
    """
    Initializer for MCP server AI/ML components.

    This class handles the initialization of AI/ML components for the MCP server,
    including setting up the necessary environment, configuration, and integration.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the AI/ML components.

        Args:
            config_path: Path to the configuration file (optional)
        """
        self.config_path = config_path
        self.config = self._load_config()

        # Set base paths
        self.project_root = Path(__file__).parent.parent.absolute()
        self.ai_ml_dir = self.project_root / "ipfs_kit_py" / "mcp" / "ai"
        self.data_dir = self.project_root / "data" / "ai_ml"

        # Create necessary directories
        self._create_directories()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or use defaults."""
        default_config = {
            "enabled": True,
            "data_dir": "data/ai_ml",
            "model_registry": {
                "enabled": True,
                "storage_dir": "data/ai_ml/models"
            },
            "dataset_manager": {
                "enabled": True,
                "storage_dir": "data/ai_ml/datasets"
            },
            "framework_integration": {
                "enabled": True,
                "langchain": True,
                "llama_index": True,
                "huggingface": True
            },
            "distributed_training": {
                "enabled": True,
                "coordinator_role": "master",
                "worker_capability": "gpu",
                "sync_strategy": "parameter_server"
            }
        }

        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    loaded_config = json.load(f)
                    # Merge with default config
                    return self._merge_configs(default_config, loaded_config)
            except Exception as e:
                logger.error(f"Error loading config from {self.config_path}: {e}")
                return default_config

        return default_config

    def _merge_configs(self, default_config: Dict[str, Any], loaded_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge loaded config with default config, keeping loaded values."""
        merged_config = default_config.copy()

        for key, value in loaded_config.items():
            if key in merged_config and isinstance(merged_config[key], dict) and isinstance(value, dict):
                merged_config[key] = self._merge_configs(merged_config[key], value)
            else:
                merged_config[key] = value

        return merged_config

    def _create_directories(self) -> None:
        """Create necessary directories for AI/ML components."""
        dirs_to_create = [
            self.data_dir,
            self.data_dir / "models",
            self.data_dir / "datasets",
            self.data_dir / "metadata",
            self.data_dir / "cache"
        ]

        for dir_path in dirs_to_create:
            os.makedirs(dir_path, exist_ok=True)
            logger.debug(f"Created directory: {dir_path}")

    def initialize_components(self) -> Dict[str, bool]:
        """
        Initialize all AI/ML components based on configuration.

        Returns:
            Dictionary with initialization status for each component
        """
        if not self.config["enabled"]:
            logger.info("AI/ML integration is disabled in configuration")
            return {"enabled": False}

        results = {"enabled": True}

        # Initialize Model Registry
        if self.config["model_registry"]["enabled"]:
            results["model_registry"] = self._initialize_model_registry()
        else:
            logger.info("Model Registry is disabled in configuration")
            results["model_registry"] = False

        # Initialize Dataset Manager
        if self.config["dataset_manager"]["enabled"]:
            results["dataset_manager"] = self._initialize_dataset_manager()
        else:
            logger.info("Dataset Manager is disabled in configuration")
            results["dataset_manager"] = False

        # Initialize Framework Integration
        if self.config["framework_integration"]["enabled"]:
            results["framework_integration"] = self._initialize_framework_integration()
        else:
            logger.info("Framework Integration is disabled in configuration")
            results["framework_integration"] = False

        # Initialize Distributed Training
        if self.config["distributed_training"]["enabled"]:
            results["distributed_training"] = self._initialize_distributed_training()
        else:
            logger.info("Distributed Training is disabled in configuration")
            results["distributed_training"] = False

        return results

    def _initialize_model_registry(self) -> bool:
        """Initialize the Model Registry component."""
        logger.info("Initializing Model Registry...")

        try:
            # Add import path if needed
            if str(self.project_root) not in sys.path:
                sys.path.insert(0, str(self.project_root))

            # Import the Model Registry
            from ipfs_kit_py.mcp.ai.model_registry import ModelRegistry, get_instance, initialize

            # Initialize the Model Registry
            storage_dir = self.config["model_registry"]["storage_dir"]
            storage_path = self.project_root / storage_dir
            os.makedirs(storage_path, exist_ok=True)

            # Initialize the singleton instance
            initialize(storage_dir=str(storage_path))

            # Test if initialization was successful
            registry = get_instance()
            if registry is None:
                logger.error("Failed to get Model Registry instance after initialization")
                return False

            logger.info(f"Model Registry initialized successfully at {storage_path}")
            return True
        except ImportError as e:
            logger.error(f"Error importing Model Registry: {e}")
            return False
        except Exception as e:
            logger.error(f"Error initializing Model Registry: {e}")
            return False

    def _initialize_dataset_manager(self) -> bool:
        """Initialize the Dataset Manager component."""
        logger.info("Initializing Dataset Manager...")

        try:
            # Add import path if needed
            if str(self.project_root) not in sys.path:
                sys.path.insert(0, str(self.project_root))

            # Import the Dataset Manager
            from ipfs_kit_py.mcp.ai.dataset_manager import DatasetManager, get_instance, initialize

            # Initialize the Dataset Manager
            storage_dir = self.config["dataset_manager"]["storage_dir"]
            storage_path = self.project_root / storage_dir
            os.makedirs(storage_path, exist_ok=True)

            # Initialize the singleton instance
            initialize(storage_dir=str(storage_path))

            # Test if initialization was successful
            manager = get_instance()
            if manager is None:
                logger.error("Failed to get Dataset Manager instance after initialization")
                return False

            logger.info(f"Dataset Manager initialized successfully at {storage_path}")
            return True
        except ImportError as e:
            logger.error(f"Error importing Dataset Manager: {e}")
            return False
        except Exception as e:
            logger.error(f"Error initializing Dataset Manager: {e}")
            return False

    def _initialize_framework_integration(self) -> bool:
        """Initialize the Framework Integration component."""
        logger.info("Initializing Framework Integration...")

        try:
            # Add import path if needed
            if str(self.project_root) not in sys.path:
                sys.path.insert(0, str(self.project_root))

            # Import the Framework Integration
            from ipfs_kit_py.mcp.ai.framework_integration import (
                LangChainConfig, LlamaIndexConfig, HuggingFaceConfig,
                LangChainIntegration, LlamaIndexIntegration, HuggingFaceIntegration
            )

            success = True

            # Initialize LangChain integration if enabled
            if self.config["framework_integration"]["langchain"]:
                try:
                    config = LangChainConfig(
                        name="default_langchain",
                        description="Default LangChain integration"
                    )
                    integration = LangChainIntegration(config)
                    logger.info("LangChain integration initialized")
                except Exception as e:
                    logger.error(f"Error initializing LangChain integration: {e}")
                    success = False

            # Initialize LlamaIndex integration if enabled
            if self.config["framework_integration"]["llama_index"]:
                try:
                    config = LlamaIndexConfig(
                        name="default_llama_index",
                        description="Default LlamaIndex integration"
                    )
                    integration = LlamaIndexIntegration(config)
                    logger.info("LlamaIndex integration initialized")
                except Exception as e:
                    logger.error(f"Error initializing LlamaIndex integration: {e}")
                    success = False

            # Initialize HuggingFace integration if enabled
            if self.config["framework_integration"]["huggingface"]:
                try:
                    config = HuggingFaceConfig(
                        name="default_huggingface",
                        description="Default HuggingFace integration",
                        model_id="gpt2"  # Default model
                    )
                    integration = HuggingFaceIntegration(config)
                    logger.info("HuggingFace integration initialized")
                except Exception as e:
                    logger.error(f"Error initializing HuggingFace integration: {e}")
                    success = False

            logger.info("Framework Integration initialization complete")
            return success
        except ImportError as e:
            logger.error(f"Error importing Framework Integration: {e}")
            return False
        except Exception as e:
            logger.error(f"Error initializing Framework Integration: {e}")
            return False

    def _initialize_distributed_training(self) -> bool:
        """Initialize the Distributed Training component."""
        logger.info("Initializing Distributed Training...")

        try:
            # Add import path if needed
            if str(self.project_root) not in sys.path:
                sys.path.insert(0, str(self.project_root))

            # Import the Distributed Training
            from ipfs_kit_py.mcp.ai.distributed_training import DistributedTraining, get_instance, initialize

            # Initialize the Distributed Training
            initialize(
                coordinator_role=self.config["distributed_training"]["coordinator_role"],
                worker_capability=self.config["distributed_training"]["worker_capability"],
                sync_strategy=self.config["distributed_training"]["sync_strategy"]
            )

            # Test if initialization was successful
            training = get_instance()
            if training is None:
                logger.error("Failed to get Distributed Training instance after initialization")
                return False

            logger.info("Distributed Training initialized successfully")
            return True
        except ImportError as e:
            logger.error(f"Error importing Distributed Training: {e}")
            return False
        except Exception as e:
            logger.error(f"Error initializing Distributed Training: {e}")
            return False

    def generate_config_file(self, output_path: str) -> bool:
        """
        Generate a configuration file with current settings.

        Args:
            output_path: Path to write the configuration file

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(output_path, "w") as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Generated configuration file at {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error generating configuration file: {e}")
            return False

    def create_patch_script(self, output_path: str) -> bool:
        """
        Create a patch script to modify the direct_mcp_server.py file.

        Args:
            output_path: Path to write the patch script

        Returns:
            True if successful, False otherwise
        """
        script_content = """#!/usr/bin/env python3
\"\"\"
Patch script for adding AI/ML functionality to direct_mcp_server.py
\"\"\"

import os
import sys
import re
import shutil
from pathlib import Path

def patch_mcp_server(server_path):
    \"\"\"
    Patch the direct_mcp_server.py file to add AI/ML functionality.

    Args:
        server_path: Path to the direct_mcp_server.py file

    Returns:
        True if successful, False otherwise
    \"\"\"
    # Verify the file exists
    if not os.path.exists(server_path):
        print(f"Error: {server_path} does not exist")
        return False

    # Create a backup
    backup_path = f"{server_path}.bak"
    shutil.copy2(server_path, backup_path)
    print(f"Created backup at {backup_path}")

    # Read the server file
    with open(server_path, "r") as f:
        content = f.read()

    # Add import for AI/ML integrator
    import_pattern = r"import uvicorn"
    import_replacement = r"import uvicorn\\n\\n# Import AI/ML integrator\\ntry:\\n    from ipfs_kit_py.mcp.integrator import integrate_ai_ml_with_mcp_server\\n    HAS_AI_ML_INTEGRATOR = True\\nexcept ImportError:\\n    print(\\"AI/ML integrator not available\\")\\n    HAS_AI_ML_INTEGRATOR = False"
    content = re.sub(import_pattern, import_replacement, content)

    # Add AI/ML integration code to app initialization
    app_pattern = r"# Run with uvicorn"
    app_replacement = r"# Integrate AI/ML components if available\\n    if HAS_AI_ML_INTEGRATOR:\\n        try:\\n            print(\\"Integrating AI/ML components with MCP server...\\")\\n            success = integrate_ai_ml_with_mcp_server(app)\\n            if success:\\n                print(\\"AI/ML integration successful\\")\\n            else:\\n                print(\\"AI/ML integration failed\\")\\n        except Exception as e:\\n            print(f\\"Error integrating AI/ML components: {e}\\")\\n    \\n    # Run with uvicorn"
    content = re.sub(app_pattern, app_replacement, content)

    # Write the modified content back to the file
    with open(server_path, "w") as f:
        f.write(content)

    print(f"Successfully patched {server_path} with AI/ML functionality")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        server_path = sys.argv[1]
    else:
        server_path = Path(__file__).parent.parent / "direct_mcp_server.py"

    success = patch_mcp_server(str(server_path))
    sys.exit(0 if success else 1)
"""

        try:
            with open(output_path, "w") as f:
                f.write(script_content)

            # Make the script executable
            os.chmod(output_path, 0o755)

            logger.info(f"Created patch script at {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error creating patch script: {e}")
            return False

def main():
    """Main entry point for the AI/ML initializer."""
    import argparse

    parser = argparse.ArgumentParser(description="Initialize AI/ML components for MCP server")
    parser.add_argument("--config", "-c", type=str, help="Path to configuration file")
    parser.add_argument("--generate-config", "-g", type=str, help="Generate a configuration file at the specified path")
    parser.add_argument("--create-patch", "-p", type=str, help="Create a patch script at the specified path")
    args = parser.parse_args()

    # Initialize the AI/ML components
    initializer = MCPAIMLInitializer(config_path=args.config)

    # Generate config file if requested
    if args.generate_config:
        initializer.generate_config_file(args.generate_config)

    # Create patch script if requested
    if args.create_patch:
        initializer.create_patch_script(args.create_patch)

    # Initialize components
    results = initializer.initialize_components()

    # Print summary
    print("\nInitialization Summary:")
    print(f"AI/ML Integration: {'Enabled' if results['enabled'] else 'Disabled'}")

    if results["enabled"]:
        print(f"Model Registry: {'Initialized' if results.get('model_registry', False) else 'Failed'}")
        print(f"Dataset Manager: {'Initialized' if results.get('dataset_manager', False) else 'Failed'}")
        print(f"Framework Integration: {'Initialized' if results.get('framework_integration', False) else 'Failed'}")
        print(f"Distributed Training: {'Initialized' if results.get('distributed_training', False) else 'Failed'}")

    # Exit with appropriate status code
    all_success = results["enabled"] and all(results.get(component, True) for component in [
        "model_registry", "dataset_manager", "framework_integration", "distributed_training"
    ])

    sys.exit(0 if all_success else 1)

if __name__ == "__main__":
    main()
