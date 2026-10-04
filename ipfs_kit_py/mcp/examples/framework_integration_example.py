#!/usr/bin/env python
"""
Framework Integration Example

This example demonstrates how to use the framework_integration module to integrate
various AI frameworks with the MCP server infrastructure.

It shows how to:
1. Configure and initialize LangChain for LLM workflows
2. Set up LlamaIndex for document indexing and retrieval
3. Use HuggingFace for model hosting and inference
4. Create and manage model endpoints

This example requires the following packages:
- langchain
- llama-index
- huggingface_hub
- transformers
- torch

You can install these with:
pip install langchain llama-index huggingface_hub transformers torch
"""

import os
import sys
import logging
import tempfile
from pathlib import Path
import argparse
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to sys.path if running as script
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# Import the framework integration module
try:
    from ipfs_kit_py.mcp.ai.framework_integration import (
        FrameworkType, EndpointType, InferenceType,
        LangChainConfig, LlamaIndexConfig, HuggingFaceConfig, CustomFrameworkConfig,
        LangChainIntegration, LlamaIndexIntegration, HuggingFaceIntegration,
        ModelEndpoint, ModelEndpointManager
    )
except ImportError as e:
    logger.error(f"Error importing framework integration module: {e}")
    logger.error("Make sure you're running this script from the correct directory or the module is installed.")
    sys.exit(1)

# Try importing other AI modules for integration
try:
    from ipfs_kit_py.mcp.ai.model_registry import ModelRegistry, Model, ModelVersion, ModelFramework
    HAS_MODEL_REGISTRY = True
except ImportError:
    logger.warning("Model Registry module not found. Some features will be disabled.")
    HAS_MODEL_REGISTRY = False

try:
    from ipfs_kit_py.mcp.ai.dataset_manager import DatasetManager, Dataset, DatasetVersion
    HAS_DATASET_MANAGER = True
except ImportError:
    logger.warning("Dataset Manager module not found. Some features will be disabled.")
    HAS_DATASET_MANAGER = False


def setup_example_data(data_dir):
    """
    Set up example data for the demo.
    
    Args:
        data_dir: Directory to store example data
    """
    # Create sample documents for LlamaIndex
    docs_dir = os.path.join(data_dir, "documents")
    os.makedirs(docs_dir, exist_ok=True)
    
    # Create sample documents
    with open(os.path.join(docs_dir, "document1.txt"), "w") as f:
        f.write("""
        # IPFS Overview
        
        The InterPlanetary File System (IPFS) is a protocol and peer-to-peer network
        for storing and sharing data in a distributed file system. IPFS uses content-addressing
        to uniquely identify each file in a global namespace connecting all computing devices.
        
        IPFS allows users to host and receive content in a manner similar to BitTorrent.
        As opposed to a centrally located server, IPFS is built around a decentralized
        system of user-operators who hold a portion of the overall data, creating a resilient
        system of file storage and sharing.
        """)
    
    with open(os.path.join(docs_dir, "document2.txt"), "w") as f:
        f.write("""
        # MCP Server
        
        The Model-Controller-Persistence (MCP) server is a crucial component of the IPFS Kit
        ecosystem, providing a unified interface for interacting with various distributed
        storage systems. It offers advanced features like multi-backend integration,
        migration management, and AI/ML capabilities.
        
        Key features include:
        - Unified storage interface
        - Multi-backend support
        - Advanced search and indexing
        - AI/ML integration
        """)
    
    # Create sample model directory for ModelRegistry
    models_dir = os.path.join(data_dir, "models")
    os.makedirs(models_dir, exist_ok=True)
    
    # Create a dummy model file
    with open(os.path.join(models_dir, "simple_model.json"), "w") as f:
        f.write(json.dumps({
            "name": "simple_model",
            "version": "1.0.0",
            "parameters": {
                "layers": 2,
                "hidden_size": 128
            }
        }, indent=2))
    
    return {
        "docs_dir": docs_dir,
        "models_dir": models_dir
    }


def demo_langchain_integration():
    """
    Demonstrate LangChain integration.
    """
    logger.info("=== LangChain Integration Demo ===")
    
    # Check if OpenAI API key is available
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        logger.warning("OpenAI API key not found. Using mock mode for LangChain demo.")
        # For demo purposes, we'll continue with mock settings
    
    # Configure LangChain
    config = LangChainConfig(
        name="example_langchain",
        description="Example LangChain integration",
        llm_type="openai" if openai_api_key else "huggingface",
        llm_model="gpt-3.5-turbo" if openai_api_key else "google/flan-t5-small",
        llm_api_key=openai_api_key,
        prompt_templates={
            "ipfs_info": "Please provide information about IPFS. Question: {query}",
            "mcp_info": "Please provide information about MCP. Question: {query}"
        }
    )
    
    # Initialize LangChain integration
    langchain_integration = LangChainIntegration(config)
    
    try:
        # Initialize the integration
        if langchain_integration.initialize():
            logger.info("LangChain integration initialized successfully")
            
            # Add a new prompt template
            langchain_integration.create_prompt_template(
                name="general_info",
                template="Please provide information about distributed systems. Question: {query}",
                input_variables=["query"]
            )
            
            # Run a chain (in mock mode if no API key)
            if openai_api_key:
                try:
                    result = langchain_integration.run_chain("ipfs_info", query="What is IPFS?")
                    logger.info(f"LangChain result: {result}")
                except Exception as e:
                    logger.error(f"Error running LangChain: {e}")
            else:
                logger.info("Skipping LangChain execution in mock mode")
        else:
            logger.warning("Failed to initialize LangChain integration")
    except Exception as e:
        logger.error(f"Error in LangChain demo: {e}")


def demo_llama_index_integration(docs_dir):
    """
    Demonstrate LlamaIndex integration.
    
    Args:
        docs_dir: Directory containing documents
    """
    logger.info("=== LlamaIndex Integration Demo ===")
    
    # Check if OpenAI API key is available
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        logger.warning("OpenAI API key not found. Using mock mode for LlamaIndex demo.")
        # For demo purposes, we'll continue with mock settings
    
    # Configure LlamaIndex
    config = LlamaIndexConfig(
        name="example_llama_index",
        description="Example LlamaIndex integration",
        llm_type="openai" if openai_api_key else "mock",
        llm_model="gpt-3.5-turbo" if openai_api_key else "mock",
        llm_api_key=openai_api_key,
        index_type="vector",
        vector_store_type="simple"
    )
    
    # Initialize LlamaIndex integration
    llama_index_integration = LlamaIndexIntegration(config)
    
    try:
        # Initialize the integration
        if llama_index_integration.initialize():
            logger.info("LlamaIndex integration initialized successfully")
            
            # Create an index from documents directory
            if os.path.exists(docs_dir) and openai_api_key:
                try:
                    logger.info(f"Creating index from documents in {docs_dir}")
                    index = llama_index_integration.create_index_from_directory(
                        index_name="example_index",
                        directory_path=docs_dir
                    )
                    logger.info("Index created successfully")
                    
                    # Query the index
                    response = llama_index_integration.query_index(
                        index_name="example_index",
                        query="What is IPFS?"
                    )
                    logger.info(f"LlamaIndex query response: {response}")
                except Exception as e:
                    logger.error(f"Error creating or querying index: {e}")
            else:
                logger.info(f"Skipping index creation: Documents directory not found or no API key")
        else:
            logger.warning("Failed to initialize LlamaIndex integration")
    except Exception as e:
        logger.error(f"Error in LlamaIndex demo: {e}")


def demo_huggingface_integration():
    """
    Demonstrate HuggingFace integration.
    """
    logger.info("=== HuggingFace Integration Demo ===")
    
    # Configure HuggingFace
    config = HuggingFaceConfig(
        name="example_huggingface",
        description="Example HuggingFace integration",
        model_id="google/flan-t5-small",  # Using a small model for demo purposes
        use_local=False  # Using the Inference API
    )
    
    # Initialize HuggingFace integration
    huggingface_integration = HuggingFaceIntegration(config)
    
    try:
        # Initialize the integration
        if huggingface_integration.initialize():
            logger.info("HuggingFace integration initialized successfully")
            
            # Try text generation
            try:
                result = huggingface_integration.text_generation(
                    prompt="What is IPFS?",
                    max_length=100
                )
                logger.info(f"HuggingFace text generation result: {result}")
            except Exception as e:
                logger.error(f"Error performing text generation: {e}")
        else:
            logger.warning("Failed to initialize HuggingFace integration")
    except Exception as e:
        logger.error(f"Error in HuggingFace demo: {e}")


def demo_endpoint_management():
    """
    Demonstrate model endpoint management.
    """
    logger.info("=== Model Endpoint Management Demo ===")
    
    # Create a temporary directory for endpoint data
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Created temporary directory for endpoint data: {temp_dir}")
        
        # Initialize the endpoint manager
        endpoint_manager = ModelEndpointManager(storage_dir=temp_dir)
        
        # Create example endpoints
        endpoints = []
        
        # LangChain endpoint
        langchain_endpoint = ModelEndpoint(
            id="langchain-endpoint-1",
            name="LangChain GPT-3.5",
            description="OpenAI GPT-3.5 via LangChain",
            framework_type=FrameworkType.LANGCHAIN,
            endpoint_type=EndpointType.LOCAL,
            inference_type=InferenceType.TEXT_GENERATION,
            is_active=True,
            metadata={
                "model": "gpt-3.5-turbo",
                "provider": "openai"
            }
        )
        endpoints.append(langchain_endpoint)
        
        # HuggingFace endpoint
        huggingface_endpoint = ModelEndpoint(
            id="huggingface-endpoint-1",
            name="HuggingFace FLAN-T5",
            description="FLAN-T5 via HuggingFace",
            framework_type=FrameworkType.HUGGINGFACE,
            endpoint_type=EndpointType.REST,
            endpoint_url="https://api-inference.huggingface.co/models/google/flan-t5-small",
            inference_type=InferenceType.TEXT_GENERATION,
            is_active=True,
            metadata={
                "model": "google/flan-t5-small",
                "provider": "huggingface"
            }
        )
        endpoints.append(huggingface_endpoint)
        
        # Create the endpoints
        for endpoint in endpoints:
            try:
                created_endpoint = endpoint_manager.create_endpoint(endpoint)
                logger.info(f"Created endpoint: {created_endpoint.id} - {created_endpoint.name}")
            except Exception as e:
                logger.error(f"Error creating endpoint {endpoint.id}: {e}")
        
        # Retrieve and display an endpoint
        try:
            retrieved_endpoint = endpoint_manager.get_endpoint("langchain-endpoint-1")
            if retrieved_endpoint:
                logger.info(f"Retrieved endpoint: {retrieved_endpoint.id} - {retrieved_endpoint.name}")
                logger.info(f"Endpoint details: {json.dumps(retrieved_endpoint.to_dict(), indent=2)}")
            else:
                logger.warning("Failed to retrieve endpoint")
        except Exception as e:
            logger.error(f"Error retrieving endpoint: {e}")


def demo_comprehensive_integration(data_dir):
    """
    Demonstrate comprehensive integration with all frameworks and the model registry.
    
    Args:
        data_dir: Directory containing example data
    """
    logger.info("=== Comprehensive Integration Demo ===")
    
    if not (HAS_MODEL_REGISTRY and HAS_DATASET_MANAGER):
        logger.warning("Skipping comprehensive integration demo: Required modules not available")
        return
    
    models_dir = os.path.join(data_dir, "models")
    
    try:
        # Initialize model registry
        registry = ModelRegistry()
        
        # Create a model
        model = Model(
            id="multilingual-llm",
            name="Multilingual Language Model",
            description="A multilingual language model for text generation",
            task_type="text-generation",
            tags=["nlp", "text-generation", "multilingual"]
        )
        registry.save_model(model)
        logger.info(f"Created model: {model.id} - {model.name}")
        
        # Create a model version
        version = ModelVersion(
            id="v1",
            version="1.0.0",
            model_id=model.id,
            name="Initial version",
            description="First version of the multilingual model",
            framework=ModelFramework.HUGGINGFACE,
            status="staging"
        )
        registry.save_model_version(version)
        logger.info(f"Created model version: {version.id} - {version.version}")
        
        # Add model file
        model_file_path = os.path.join(models_dir, "simple_model.json")
        if os.path.exists(model_file_path):
            with open(model_file_path, "rb") as f:
                registry.add_model_file(model.id, version.id, "config.json", f)
                logger.info("Added model file: config.json")
        
        # Initialize endpoint manager
        endpoint_manager = ModelEndpointManager()
        
        # Create an endpoint for the registered model
        model_endpoint = ModelEndpoint(
            id="multilingual-llm-endpoint",
            name="Multilingual LLM API",
            description="API endpoint for the multilingual language model",
            model_id=model.id,
            model_version_id=version.id,
            framework_type=FrameworkType.HUGGINGFACE,
            endpoint_type=EndpointType.LOCAL,
            inference_type=InferenceType.TEXT_GENERATION,
            is_active=True
        )
        endpoint_manager.create_endpoint(model_endpoint)
        logger.info(f"Created endpoint for model: {model_endpoint.id}")
        
        # Configure HuggingFace integration for the model
        hf_config = HuggingFaceConfig(
            name=f"{model.id}-integration",
            description=f"HuggingFace integration for {model.name}",
            model_id="google/flan-t5-small",  # Using a standard model for the demo
            use_local=False
        )
        
        # Initialize HuggingFace integration
        huggingface_integration = HuggingFaceIntegration(hf_config)
        if huggingface_integration.initialize():
            logger.info("HuggingFace integration initialized for the model")
            
            # Simulate model serving
            logger.info("Model is now ready to serve inference requests")
            
            # Simulate an inference request
            try:
                result = huggingface_integration.text_generation(
                    prompt="Translate to Spanish: Hello world",
                    max_length=50
                )
                logger.info(f"Inference result: {result}")
                
                # Update request count in the endpoint
                model_endpoint.request_count += 1
                endpoint_manager.create_endpoint(model_endpoint)  # Save updated endpoint
                logger.info(f"Updated endpoint request count: {model_endpoint.request_count}")
            except Exception as e:
                logger.error(f"Error performing inference: {e}")
    except Exception as e:
        logger.error(f"Error in comprehensive integration demo: {e}")


def main():
    """
    Main function to run the example.
    """
    parser = argparse.ArgumentParser(description="Framework Integration Example")
    parser.add_argument("--data-dir", type=str, default=None, help="Directory for example data")
    args = parser.parse_args()
    
    # Create or use data directory
    data_dir = args.data_dir or tempfile.mkdtemp(prefix="mcp_framework_example_")
    logger.info(f"Using data directory: {data_dir}")
    
    # Set up example data
    data_paths = setup_example_data(data_dir)
    
    # Run demos
    demo_langchain_integration()
    demo_llama_index_integration(data_paths["docs_dir"])
    demo_huggingface_integration()
    demo_endpoint_management()
    demo_comprehensive_integration(data_dir)
    
    logger.info("Framework integration example completed")


if __name__ == "__main__":
    main()