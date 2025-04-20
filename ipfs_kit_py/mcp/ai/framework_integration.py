"""
AI Framework Integration Module for MCP Server

This module provides integration with popular AI frameworks and libraries,
enabling seamless use of external AI tools and services with the MCP server
infrastructure. It complements the model_registry, dataset_manager, and
distributed_training modules for complete ML lifecycle management.

Key integrations:
1. LangChain for LLM workflows and agents
2. LlamaIndex for data indexing and retrieval
3. HuggingFace for model hosting and inference
4. Custom model serving for specialized deployments

Part of the MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).
"""

import os
import json
import logging
import tempfile
import time
import uuid
import shutil
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Union, Callable, Iterator
from pathlib import Path

# Configure logger
logger = logging.getLogger(__name__)

# Try importing optional dependencies
try:
    import langchain
    from langchain.llms import HuggingFacePipeline, OpenAI
    from langchain.chains import LLMChain
    from langchain.prompts import PromptTemplate
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    logger.warning("LangChain not available. LangChain integration will be unavailable.")

try:
    from llama_index import GPTVectorStoreIndex, SimpleDirectoryReader, Document
    from llama_index.vector_stores import SimpleVectorStore, MetadataFilters
    HAS_LLAMA_INDEX = True
except ImportError:
    HAS_LLAMA_INDEX = False
    logger.warning("LlamaIndex not available. LlamaIndex integration will be unavailable.")

try:
    import huggingface_hub
    from huggingface_hub import InferenceClient, hf_hub_download, snapshot_download
    HAS_HF_HUB = True
except ImportError:
    HAS_HF_HUB = False
    logger.warning("HuggingFace Hub not available. HuggingFace integration will be limited.")

try:
    import torch
    from transformers import AutoTokenizer, AutoModel, pipeline
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
    logger.warning("Transformers not available. HuggingFace model integration will be unavailable.")

# Import from other MCP modules when available
try:
    from ipfs_kit_py.mcp.ai.model_registry import (
        ModelRegistry, Model, ModelVersion, ModelFramework
    )
    HAS_MODEL_REGISTRY = True
except ImportError:
    HAS_MODEL_REGISTRY = False
    logger.warning("Model Registry not available. Some integrations will be limited.")

try:
    from ipfs_kit_py.mcp.ai.dataset_manager import (
        Dataset, DatasetVersion, DatasetFile, DatasetSplit
    )
    HAS_DATASET_MANAGER = True
except ImportError:
    HAS_DATASET_MANAGER = False
    logger.warning("Dataset Manager not available. Some integrations will be limited.")


class FrameworkType(str, Enum):
    """Enum for supported AI frameworks."""
    LANGCHAIN = "langchain"
    LLAMA_INDEX = "llama_index"
    HUGGINGFACE = "huggingface"
    CUSTOM = "custom"


class EndpointType(str, Enum):
    """Enum for types of model endpoints."""
    REST = "rest"
    GRPC = "grpc"
    WEBSOCKET = "websocket"
    LOCAL = "local"
    CUSTOM = "custom"


class InferenceType(str, Enum):
    """Enum for types of inference tasks."""
    TEXT_GENERATION = "text-generation"
    CLASSIFICATION = "classification"
    EMBEDDING = "embedding"
    QUESTION_ANSWERING = "question-answering"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    IMAGE_CLASSIFICATION = "image-classification"
    IMAGE_GENERATION = "image-generation"
    OBJECT_DETECTION = "object-detection"
    SPEECH_RECOGNITION = "speech-recognition"
    SPEECH_SYNTHESIS = "speech-synthesis"
    CUSTOM = "custom"


@dataclass
class FrameworkConfig:
    """Base configuration for framework integrations."""
    name: str
    framework_type: FrameworkType
    description: Optional[str] = None
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class LangChainConfig(FrameworkConfig):
    """Configuration for LangChain integration."""
    # Framework type is fixed for this config
    framework_type: FrameworkType = FrameworkType.LANGCHAIN
    
    # LLM settings
    llm_type: str = "openai"  # openai, huggingface, etc.
    llm_model: str = "gpt-3.5-turbo"
    llm_api_key: Optional[str] = None
    llm_api_base: Optional[str] = None
    
    # Chain settings
    chain_type: Optional[str] = None
    prompt_templates: Dict[str, str] = field(default_factory=dict)
    
    # Tool settings
    enable_tools: bool = False
    tool_names: List[str] = field(default_factory=list)
    
    # Memory settings
    memory_type: Optional[str] = None
    memory_config: Dict[str, Any] = field(default_factory=dict)
    
    # Custom options
    custom_options: Dict[str, Any] = field(default_factory=dict)

    def get_llm(self) -> Any:
        """Get the configured LLM."""
        if not HAS_LANGCHAIN:
            raise ImportError("LangChain is not available. Please install it with `pip install langchain`")
        
        if self.llm_type == "openai":
            # OpenAI LLM
            api_key = self.llm_api_key or os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API key is required for OpenAI LLM")
            
            from langchain.llms import OpenAI
            return OpenAI(
                model_name=self.llm_model,
                openai_api_key=api_key,
                **self.custom_options
            )
        elif self.llm_type == "huggingface":
            # HuggingFace LLM
            if not HAS_TRANSFORMERS:
                raise ImportError("Transformers is not available. Please install it with `pip install transformers`")
            
            from langchain.llms import HuggingFacePipeline
            pipe = pipeline(
                "text-generation",
                model=self.llm_model,
                **self.custom_options
            )
            return HuggingFacePipeline(pipeline=pipe)
        else:
            raise ValueError(f"Unsupported LLM type: {self.llm_type}")


@dataclass
class LlamaIndexConfig(FrameworkConfig):
    """Configuration for LlamaIndex integration."""
    # Framework type is fixed for this config
    framework_type: FrameworkType = FrameworkType.LLAMA_INDEX
    
    # Index settings
    index_type: str = "vector"  # vector, keyword, etc.
    
    # Storage settings
    vector_store_type: str = "simple"  # simple, faiss, pinecone, etc.
    vector_store_config: Dict[str, Any] = field(default_factory=dict)
    
    # Document settings
    chunk_size: int = 1024
    chunk_overlap: int = 20
    
    # LLM settings (for query-time)
    llm_type: str = "openai"
    llm_model: str = "gpt-3.5-turbo"
    llm_api_key: Optional[str] = None
    
    # Embedding settings
    embedding_model: str = "text-embedding-ada-002"
    embedding_api_key: Optional[str] = None
    
    # Custom options
    custom_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HuggingFaceConfig(FrameworkConfig):
    """Configuration for HuggingFace integration."""
    # Framework type is fixed for this config
    framework_type: FrameworkType = FrameworkType.HUGGINGFACE
    
    # API settings
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    
    # Model settings
    model_id: str = "gpt2"
    revision: Optional[str] = None
    task: Optional[str] = None
    
    # Inference settings
    use_local: bool = False
    local_model_path: Optional[str] = None
    
    # Custom options
    custom_options: Dict[str, Any] = field(default_factory=dict)
    
    def get_client(self) -> Any:
        """Get a configured HuggingFace client."""
        if not HAS_HF_HUB:
            raise ImportError("HuggingFace Hub is not available. Please install it with `pip install huggingface_hub`")
        
        # Set up API token
        token = self.api_key or os.environ.get("HF_API_TOKEN")
        
        # Create client
        client = InferenceClient(
            model=self.model_id,
            token=token,
            **self.custom_options
        )
        
        return client


@dataclass
class CustomFrameworkConfig(FrameworkConfig):
    """Configuration for custom framework integration."""
    # Framework type is fixed for this config
    framework_type: FrameworkType = FrameworkType.CUSTOM
    
    # Custom framework settings
    module_path: Optional[str] = None
    class_name: Optional[str] = None
    
    # Model settings
    model_path: Optional[str] = None
    model_config: Dict[str, Any] = field(default_factory=dict)
    
    # Endpoint settings
    endpoint_type: Optional[EndpointType] = None
    endpoint_url: Optional[str] = None
    endpoint_config: Dict[str, Any] = field(default_factory=dict)
    
    # Custom options
    initialization_args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelEndpoint:
    """A deployed model endpoint for inference."""
    # Basic info
    id: str
    name: str
    description: Optional[str] = None
    
    # Model info
    model_id: Optional[str] = None  # Reference to Model in ModelRegistry
    model_version_id: Optional[str] = None  # Reference to ModelVersion
    framework_type: FrameworkType = FrameworkType.CUSTOM
    
    # Endpoint info
    endpoint_type: EndpointType = EndpointType.LOCAL
    endpoint_url: Optional[str] = None
    inference_type: InferenceType = InferenceType.CUSTOM
    
    # Status
    is_active: bool = True
    is_public: bool = False
    
    # Performance metrics
    request_count: int = 0
    avg_latency_ms: Optional[float] = None
    
    # Security
    authentication_required: bool = False
    api_key_required: bool = False
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    created_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class FrameworkIntegrationBase:
    """Base class for framework integrations."""
    
    def __init__(self, config: FrameworkConfig):
        """
        Initialize the framework integration.
        
        Args:
            config: Framework configuration
        """
        self.config = config
        self._initialized = False
        self._client = None
    
    def initialize(self) -> bool:
        """
        Initialize the framework integration.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def is_initialized(self) -> bool:
        """
        Check if the framework integration is initialized.
        
        Returns:
            True if initialized, False otherwise
        """
        return self._initialized
    
    def validate_config(self) -> bool:
        """
        Validate the framework configuration.
        
        Returns:
            True if the configuration is valid, False otherwise
        """
        raise NotImplementedError("Subclasses must implement this method")


class LangChainIntegration(FrameworkIntegrationBase):
    """LangChain framework integration."""
    
    def __init__(self, config: LangChainConfig):
        """
        Initialize the LangChain integration.
        
        Args:
            config: LangChain configuration
        """
        super().__init__(config)
        self.llm = None
        self.chains = {}
        self.agents = {}
        self.tools = {}
    
    def initialize(self) -> bool:
        """
        Initialize the LangChain integration.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        if not HAS_LANGCHAIN:
            logger.error("LangChain is not available. Please install it with `pip install langchain`")
            return False
        
        try:
            # Initialize LLM
            self.llm = self.config.get_llm()
            
            # Initialize chains if any prompt templates are provided
            for name, template in self.config.prompt_templates.items():
                prompt = PromptTemplate(
                    template=template,
                    input_variables=["query"]  # Simple default
                )
                self.chains[name] = LLMChain(llm=self.llm, prompt=prompt)
            
            # TODO: Initialize tools, agents, and memory
            
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Error initializing LangChain: {e}")
            return False
    
    def validate_config(self) -> bool:
        """
        Validate the LangChain configuration.
        
        Returns:
            True if the configuration is valid, False otherwise
        """
        if not self.config.llm_type:
            logger.error("LLM type is required")
            return False
        
        if not self.config.llm_model:
            logger.error("LLM model is required")
            return False
        
        if self.config.llm_type == "openai" and not (self.config.llm_api_key or os.environ.get("OPENAI_API_KEY")):
            logger.error("OpenAI API key is required for OpenAI LLM")
            return False
        
        return True
    
    def run_chain(self, chain_name: str, **inputs) -> Any:
        """
        Run a LangChain chain.
        
        Args:
            chain_name: Name of the chain to run
            **inputs: Inputs for the chain
            
        Returns:
            Chain output
        """
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("Failed to initialize LangChain")
        
        if chain_name not in self.chains:
            raise ValueError(f"Chain not found: {chain_name}")
        
        return self.chains[chain_name].run(**inputs)
    
    def create_prompt_template(self, name: str, template: str, input_variables: List[str]) -> None:
        """
        Create a new prompt template.
        
        Args:
            name: Name of the prompt template
            template: Prompt template string
            input_variables: Input variables for the template
        """
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("Failed to initialize LangChain")
        
        prompt = PromptTemplate(
            template=template,
            input_variables=input_variables
        )
        self.chains[name] = LLMChain(llm=self.llm, prompt=prompt)


class LlamaIndexIntegration(FrameworkIntegrationBase):
    """LlamaIndex framework integration."""
    
    def __init__(self, config: LlamaIndexConfig):
        """
        Initialize the LlamaIndex integration.
        
        Args:
            config: LlamaIndex configuration
        """
        super().__init__(config)
        self.indices = {}
        self.vector_store = None
        self.documents = {}
    
    def initialize(self) -> bool:
        """
        Initialize the LlamaIndex integration.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        if not HAS_LLAMA_INDEX:
            logger.error("LlamaIndex is not available. Please install it with `pip install llama-index`")
            return False
        
        try:
            # Initialize vector store
            if self.config.vector_store_type == "simple":
                self.vector_store = SimpleVectorStore()
            # Add other vector store types as needed
            
            # Set up LLM/embedding settings in the LlamaIndex context
            import llama_index
            
            # Set OpenAI API key if provided
            api_key = self.config.llm_api_key or os.environ.get("OPENAI_API_KEY")
            if api_key:
                llama_index.set_global_service_context(
                    llama_index.ServiceContext.from_defaults(
                        llm=llama_index.LLM(model_name=self.config.llm_model),
                        embed_model=llama_index.embeddings.OpenAIEmbedding(
                            model=self.config.embedding_model,
                            api_key=api_key
                        )
                    )
                )
            
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Error initializing LlamaIndex: {e}")
            return False
    
    def validate_config(self) -> bool:
        """
        Validate the LlamaIndex configuration.
        
        Returns:
            True if the configuration is valid, False otherwise
        """
        # Basic validation checks
        if not self.config.index_type:
            logger.error("Index type is required")
            return False
        
        if not self.config.vector_store_type:
            logger.error("Vector store type is required")
            return False
        
        return True
    
    def create_index_from_documents(self, index_name: str, documents: List[Any]) -> Any:
        """
        Create an index from documents.
        
        Args:
            index_name: Name of the index
            documents: List of documents to index
            
        Returns:
            The created index
        """
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("Failed to initialize LlamaIndex")
        
        # Create index
        index = GPTVectorStoreIndex.from_documents(
            documents=documents,
            service_context=llama_index.ServiceContext.from_defaults()
        )
        
        # Store the index
        self.indices[index_name] = index
        
        return index
    
    def create_index_from_directory(self, index_name: str, directory_path: str) -> Any:
        """
        Create an index from a directory of files.
        
        Args:
            index_name: Name of the index
            directory_path: Path to directory containing documents
            
        Returns:
            The created index
        """
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("Failed to initialize LlamaIndex")
        
        # Load documents
        documents = SimpleDirectoryReader(directory_path).load_data()
        
        # Create index
        index = GPTVectorStoreIndex.from_documents(
            documents=documents,
            service_context=llama_index.ServiceContext.from_defaults()
        )
        
        # Store the index
        self.indices[index_name] = index
        
        return index
    
    def query_index(self, index_name: str, query: str) -> Any:
        """
        Query an index.
        
        Args:
            index_name: Name of the index to query
            query: Query string
            
        Returns:
            Query response
        """
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("Failed to initialize LlamaIndex")
        
        if index_name not in self.indices:
            raise ValueError(f"Index not found: {index_name}")
        
        index = self.indices[index_name]
        query_engine = index.as_query_engine()
        
        return query_engine.query(query)
    
    def get_document_by_id(self, doc_id: str) -> Any:
        """
        Get a document by ID.
        
        Args:
            doc_id: Document ID
            
        Returns:
            The document
        """
        if doc_id not in self.documents:
            raise ValueError(f"Document not found: {doc_id}")
        
        return self.documents[doc_id]


class HuggingFaceIntegration(FrameworkIntegrationBase):
    """HuggingFace framework integration."""
    
    def __init__(self, config: HuggingFaceConfig):
        """
        Initialize the HuggingFace integration.
        
        Args:
            config: HuggingFace configuration
        """
        super().__init__(config)
        self.client = None
        self.model = None
        self.tokenizer = None
    
    def initialize(self) -> bool:
        """
        Initialize the HuggingFace integration.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        if not HAS_HF_HUB:
            logger.error("HuggingFace Hub is not available. Please install it with `pip install huggingface_hub`")
            return False
        
        try:
            # Set up API token
            token = self.config.api_key or os.environ.get("HF_API_TOKEN")
            if token:
                huggingface_hub.login(token=token)
            
            # Create client
            self.client = self.config.get_client()
            
            # Load local model if specified
            if self.config.use_local and HAS_TRANSFORMERS:
                if self.config.local_model_path:
                    model_path = self.config.local_model_path
                else:
                    # Download the model
                    model_path = snapshot_download(
                        repo_id=self.config.model_id,
                        revision=self.config.revision
                    )
                
                # Load the model and tokenizer
                self.tokenizer = AutoTokenizer.from_pretrained(model_path)
                self.model = AutoModel.from_pretrained(model_path)
            
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Error initializing HuggingFace: {e}")
            return False
    
    def validate_config(self) -> bool:
        """
        Validate the HuggingFace configuration.
        
        Returns:
            True if the configuration is valid, False otherwise
        """
        if not self.config.model_id:
            logger.error("Model ID is required")
            return False
        
        if self.config.use_local and not HAS_TRANSFORMERS:
            logger.error("Transformers is required for local model usage but is not available")
            return False
        
        return True
    
    def text_generation(self, prompt: str, **generation_args) -> str:
        """
        Generate text with the configured model.
        
        Args:
            prompt: Text prompt
            **generation_args: Generation arguments to pass to the model
            
        Returns:
            Generated text
        """
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("Failed to initialize HuggingFace")
        
        # Use local model if available
        if self.model and self.tokenizer:
            inputs = self.tokenizer(prompt, return_tensors="pt")
            with torch.no_grad():
                outputs = self.model.generate(**inputs, **generation_args)
            return self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Otherwise use the Inference API
        return self.client.text_generation(prompt, **generation_args)
    
    def get_embeddings(self, texts: List[str], **embedding_args) -> List[List[float]]:
        """
        Get embeddings for texts with the configured model.
        
        Args:
            texts: List of texts to embed
            **embedding_args: Embedding arguments to pass to the model
            
        Returns:
            List of embedding vectors
        """
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("Failed to initialize HuggingFace")
        
        # Use the Inference API
        return self.client.feature_extraction(texts, **embedding_args)


class CustomFrameworkIntegration(FrameworkIntegrationBase):
    """Custom framework integration."""
    
    def __init__(self, config: CustomFrameworkConfig):
        """
        Initialize the custom framework integration.
        
        Args:
            config: Custom framework configuration
        """
        super().__init__(config)
        self.instance = None
    
    def initialize(self) -> bool:
        """
        Initialize the custom framework integration.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            # Import the custom module
            if self.config.module_path and self.config.class_name:
                module_parts = self.config.module_path.split('.')
                module_name = '.'.join(module_parts)
                
                try:
                    module = __import__(module_name, fromlist=[module_parts[-1]])
                    cls = getattr(module, self.config.class_name)
                    
                    # Instantiate the class
                    self.instance = cls(**self.config.initialization_args)
                except (ImportError, AttributeError) as e:
                    logger.error(f"Error loading custom module: {e}")
                    return False
            
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Error initializing custom framework: {e}")
            return False
    
    def validate_config(self) -> bool:
        """
        Validate the custom framework configuration.
        
        Returns:
            True if the configuration is valid, False otherwise
        """
        if not self.config.module_path:
            logger.error("Module path is required for custom framework")
            return False
        
        if not self.config.class_name:
            logger.error("Class name is required for custom framework")
            return False
        
        return True
    
    def call_method(self, method_name: str, *args, **kwargs) -> Any:
        """
        Call a method on the custom framework instance.
        
        Args:
            method_name: Name of the method to call
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Method result
        """
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("Failed to initialize custom framework")
        
        if not self.instance:
            raise RuntimeError("Custom framework instance not initialized")
        
        if not hasattr(self.instance, method_name):
            raise ValueError(f"Method not found: {method_name}")
        
        method = getattr(self.instance, method_name)
        return method(*args, **kwargs)


class ModelEndpointManager:
    """Manager for model endpoints."""
    
    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize the model endpoint manager.
        
        Args:
            storage_dir: Directory for storing endpoint data
        """
        self.storage_dir = storage_dir or tempfile.mkdtemp(prefix="mcp_endpoints_")
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # In-memory cache of endpoints
        self._endpoints: Dict[str, ModelEndpoint] = {}
        
        # Framework integrations
        self._integrations: Dict[str, FrameworkIntegrationBase] = {}
        
        logger.info(f"Initialized model endpoint manager with storage directory: {self.storage_dir}")
    
    def _get_endpoint_path(self, endpoint_id: str) -> str:
        """Get the file path for an endpoint."""
        return os.path.join(self.storage_dir, f"{endpoint_id}.json")
    
    def create_endpoint(self, endpoint: ModelEndpoint) -> ModelEndpoint:
        """
        Create a new model endpoint.
        
        Args:
            endpoint: Model endpoint to create
            
        Returns:
            The created endpoint
        """
        # Save the endpoint
        endpoint_path = self._get_endpoint_path(endpoint.id)
        with open(endpoint_path, 'w') as f:
            json.dump(endpoint.to_dict(), f, indent=2)
        
        # Cache the endpoint
        self._endpoints[endpoint.id] = endpoint
        
        return endpoint
    
    def get_endpoint(self, endpoint_id: str) -> Optional[ModelEndpoint]:
        """
        Get a model endpoint.
        
        Args:
            endpoint_id: ID of the endpoint
            
        Returns:
            The endpoint or None if not found
        """
        # Check cache
        if endpoint_id in self._endpoints:
            return self._endpoints[endpoint_id]
        
        # Check storage
        endpoint_path = self._get_endpoint_path(endpoint_id)
        if not os.path.exists(endpoint_path):
            return None
        
        # Load from storage
        try:
            with open(endpoint_path, 'r') as f:
                endpoint_dict = json.load(f)
            
            # Convert to ModelEndpoint
            endpoint = ModelEndpoint(**endpoint_dict)
            
            # Cache the endpoint
            self._endpoints[endpoint_id] = endpoint
            
            return endpoint
        except Exception as e:
            logger.error(f"Error loading endpoint {endpoint_id}: {e}")
            return None


class FrameworkIntegrationManager:
    """
    Manager for framework integrations.
    
    This class provides functionality for managing various framework integrations,
    including LangChain, LlamaIndex, HuggingFace, and custom frameworks.
    """
    
    def __init__(
        self, 
        storage_path: Optional[Union[str, Path]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the framework integration manager.
        
        Args:
            storage_path: Path for storing framework data
            config: Configuration options
        """
        # Set default storage path if none provided
        if storage_path is None:
            self.storage_path = Path.home() / ".ipfs_kit" / "framework_integration"
        elif isinstance(storage_path, str):
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = storage_path
            
        # Ensure directories exist
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.config = config or {}
        
        # Framework integrations
        self.integrations: Dict[str, FrameworkIntegrationBase] = {}
        
        # Endpoint manager
        self.endpoint_manager = ModelEndpointManager(
            storage_dir=str(self.storage_path / "endpoints")
        )
        
        logger.info(f"Framework Integration Manager initialized at {self.storage_path}")
    
    def register_integration(self, name: str, integration: FrameworkIntegrationBase) -> bool:
        """
        Register a framework integration.
        
        Args:
            name: Name of the integration
            integration: Framework integration instance
            
        Returns:
            True if successful, False otherwise
        """
        if name in self.integrations:
            logger.warning(f"Integration '{name}' already exists and will be replaced")
        
        self.integrations[name] = integration
        logger.info(f"Registered framework integration: {name}")
        
        return True
    
    def get_integration(self, name: str) -> Optional[FrameworkIntegrationBase]:
        """
        Get a framework integration by name.
        
        Args:
            name: Name of the integration
            
        Returns:
            Framework integration instance, or None if not found
        """
        return self.integrations.get(name)
    
    def create_langchain_integration(
        self, 
        name: str,
        llm_type: str,
        llm_model: str,
        api_key: Optional[str] = None,
        prompt_templates: Optional[Dict[str, str]] = None,
        description: Optional[str] = None
    ) -> Optional[LangChainIntegration]:
        """
        Create a LangChain integration.
        
        Args:
            name: Name of the integration
            llm_type: Type of LLM (openai, huggingface, etc.)
            llm_model: Model name
            api_key: API key (optional, can be set via environment variables)
            prompt_templates: Dictionary of prompt templates
            description: Human-readable description
            
        Returns:
            LangChainIntegration instance, or None if creation failed
        """
        try:
            config = LangChainConfig(
                name=name,
                llm_type=llm_type,
                llm_model=llm_model,
                llm_api_key=api_key,
                prompt_templates=prompt_templates or {},
                description=description
            )
            
            integration = LangChainIntegration(config)
            
            if integration.validate_config():
                self.register_integration(name, integration)
                return integration
            else:
                logger.error(f"Invalid configuration for LangChain integration '{name}'")
                return None
                
        except Exception as e:
            logger.error(f"Error creating LangChain integration '{name}': {e}")
            return None
    
    def create_llama_index_integration(
        self,
        name: str,
        index_type: str = "vector",
        vector_store_type: str = "simple",
        llm_model: str = "gpt-3.5-turbo",
        api_key: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[LlamaIndexIntegration]:
        """
        Create a LlamaIndex integration.
        
        Args:
            name: Name of the integration
            index_type: Type of index (vector, keyword, etc.)
            vector_store_type: Type of vector store (simple, faiss, etc.)
            llm_model: Model name for query-time LLM
            api_key: API key (optional, can be set via environment variables)
            description: Human-readable description
            
        Returns:
            LlamaIndexIntegration instance, or None if creation failed
        """
        try:
            config = LlamaIndexConfig(
                name=name,
                index_type=index_type,
                vector_store_type=vector_store_type,
                llm_model=llm_model,
                llm_api_key=api_key,
                description=description
            )
            
            integration = LlamaIndexIntegration(config)
            
            if integration.validate_config():
                self.register_integration(name, integration)
                return integration
            else:
                logger.error(f"Invalid configuration for LlamaIndex integration '{name}'")
                return None
                
        except Exception as e:
            logger.error(f"Error creating LlamaIndex integration '{name}': {e}")
            return None
    
    def create_huggingface_integration(
        self,
        name: str,
        model_id: str,
        api_key: Optional[str] = None,
        use_local: bool = False,
        local_model_path: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[HuggingFaceIntegration]:
        """
        Create a HuggingFace integration.
        
        Args:
            name: Name of the integration
            model_id: HuggingFace model ID
            api_key: HuggingFace API token (optional, can be set via environment variables)
            use_local: Whether to use a local model
            local_model_path: Path to local model (if use_local is True)
            description: Human-readable description
            
        Returns:
            HuggingFaceIntegration instance, or None if creation failed
        """
        try:
            config = HuggingFaceConfig(
                name=name,
                model_id=model_id,
                api_key=api_key,
                use_local=use_local,
                local_model_path=local_model_path,
                description=description
            )
            
            integration = HuggingFaceIntegration(config)
            
            if integration.validate_config():
                self.register_integration(name, integration)
                return integration
            else:
                logger.error(f"Invalid configuration for HuggingFace integration '{name}'")
                return None
                
        except Exception as e:
            logger.error(f"Error creating HuggingFace integration '{name}': {e}")
            return None
    
    def create_model_endpoint(
        self,
        name: str,
        integration_name: str,
        model_id: Optional[str] = None,
        model_version_id: Optional[str] = None,
        endpoint_type: EndpointType = EndpointType.LOCAL,
        endpoint_url: Optional[str] = None,
        inference_type: InferenceType = InferenceType.TEXT_GENERATION,
        description: Optional[str] = None,
        is_public: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ModelEndpoint]:
        """
        Create a model endpoint.
        
        Args:
            name: Name of the endpoint
            integration_name: Name of the framework integration to use
            model_id: ID of the model in the model registry (optional)
            model_version_id: ID of the model version (optional)
            endpoint_type: Type of endpoint (REST, gRPC, etc.)
            endpoint_url: URL of the endpoint (for remote endpoints)
            inference_type: Type of inference task
            description: Human-readable description
            is_public: Whether the endpoint is public
            metadata: Additional metadata
            
        Returns:
            ModelEndpoint instance, or None if creation failed
        """
        try:
            # Check if integration exists
            integration = self.get_integration(integration_name)
            if not integration:
                logger.error(f"Integration '{integration_name}' not found")
                return None
            
            # Determine framework type
            framework_type = FrameworkType.CUSTOM
            if isinstance(integration, LangChainIntegration):
                framework_type = FrameworkType.LANGCHAIN
            elif isinstance(integration, LlamaIndexIntegration):
                framework_type = FrameworkType.LLAMA_INDEX
            elif isinstance(integration, HuggingFaceIntegration):
                framework_type = FrameworkType.HUGGINGFACE
            
            # Create endpoint ID
            endpoint_id = f"endpoint_{uuid.uuid4().hex[:8]}"
            
            # Create endpoint
            endpoint = ModelEndpoint(
                id=endpoint_id,
                name=name,
                description=description,
                model_id=model_id,
                model_version_id=model_version_id,
                framework_type=framework_type,
                endpoint_type=endpoint_type,
                endpoint_url=endpoint_url,
                inference_type=inference_type,
                is_public=is_public,
                metadata=metadata or {}
            )
            
            # Register with endpoint manager
            self.endpoint_manager.create_endpoint(endpoint)
            
            return endpoint
            
        except Exception as e:
            logger.error(f"Error creating model endpoint '{name}': {e}")
            return None
    
    def get_model_endpoint(self, endpoint_id: str) -> Optional[ModelEndpoint]:
        """
        Get a model endpoint by ID.
        
        Args:
            endpoint_id: ID of the endpoint
            
        Returns:
            ModelEndpoint instance, or None if not found
        """
        return self.endpoint_manager.get_endpoint(endpoint_id)


# Singleton instance
_instance = None

def get_instance(
    storage_path: Optional[Union[str, Path]] = None,
    config: Optional[Dict[str, Any]] = None
) -> FrameworkIntegrationManager:
    """
    Get or create the singleton instance of the FrameworkIntegrationManager.
    
    Args:
        storage_path: Path for storing framework data
        config: Configuration options
        
    Returns:
        FrameworkIntegrationManager instance
    """
    global _instance
    if _instance is None:
        _instance = FrameworkIntegrationManager(storage_path, config)
    return _instance
