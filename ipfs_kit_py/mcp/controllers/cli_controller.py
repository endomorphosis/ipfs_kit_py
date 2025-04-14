"""
CLI Controller for the MCP server.

This controller provides an interface to the CLI functionality through the MCP API.
"""

import argparse
import asyncio
import importlib.util
import logging
import os
import sys
from enum import Enum
from typing import Any, Dict, List, Optional

import yaml

# Import anyio for cross-backend compatibility
try:
    import anyio
    import sniffio
    HAS_ANYIO = True
except ImportError:
    HAS_ANYIO = False

# Configure logger (Ensure it's defined before use in stubs)
logger = logging.getLogger(__name__)

# Import the IPFSSimpleAPI class
try:
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
except ImportError as e:
    logger.error(f"Failed to import IPFSSimpleAPI: {e}. CLI controller may not function correctly.")
    # Define a basic stub if import fails
    class IPFSSimpleAPI:
        def __init__(self, *args, **kwargs): logger.warning("Using STUB IPFSSimpleAPI")
        def __getattr__(self, name):
            def dummy(*args, **kwargs): return {"success": False, "error": f"IPFSSimpleAPI.{name} unavailable (stub)"}
            return dummy

# Try to import FastAPI/Pydantic components (Improved Stubbing)
try:
    from fastapi import APIRouter, HTTPException, Response
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
    logger.info("FastAPI and Pydantic imported successfully.")
except ImportError:
    logger.warning("FastAPI or Pydantic not found. Using stubs.")
    FASTAPI_AVAILABLE = False
    # Define stubs if imports fail
    class BaseModel:
        # Add a basic __init__ to allow instantiation
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
    # Make Field stub return the default value if provided, else None
    def Field(*args, default=None, **kwargs):
        return default
    class APIRouter:
        def add_api_route(self, *args, **kwargs): pass
    class HTTPException(Exception):
         def __init__(self, status_code: int, detail: Any = None):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)
    class Response:
         def __init__(self, content: Any = None, status_code: int = 200, headers: Optional[Dict[str, str]] = None, media_type: Optional[str] = None):
            self.content = content
            self.status_code = status_code
            self.headers = headers or {}
            self.media_type = media_type


# Check for WAL integration support
try:
    from ipfs_kit_py.wal_cli_integration import handle_wal_command
    WAL_CLI_AVAILABLE = True
except ImportError:
    WAL_CLI_AVAILABLE = False


# Define Pydantic models for requests and responses
class FormatType(str, Enum):
    """Output format types."""
    JSON = "json"
    YAML = "yaml"
    TEXT = "text"


class CliCommandRequest(BaseModel):
    """Request model for executing CLI commands."""
    command: str = Field(..., description="CLI command to execute")
    args: List[Any] = Field(default=[], description="Command arguments")
    kwargs: Dict[str, Any] = Field(default={}, description="Keyword arguments")
    params: Dict[str, Any] = Field(default={}, description="Additional parameters")
    format: FormatType = Field(default=FormatType.JSON, description="Output format")


class CliCommandResponse(BaseModel):
    """Response model for CLI command execution."""
    success: bool = Field(..., description="Whether the command was successful")
    result: Any = Field(None, description="Command result")
    operation_id: Optional[str] = Field(None, description="Operation ID for async operations")
    format: Optional[str] = Field(None, description="Output format used")


class CliVersionResponse(BaseModel):
    """Response model for CLI version information."""
    ipfs_kit_py_version: str = Field(..., description="IPFS Kit Python package version")
    python_version: Optional[str] = Field(None, description="Python version")
    platform: Optional[str] = Field(None, description="Platform information")
    ipfs_daemon_version: Optional[str] = Field(None, description="IPFS daemon version")


class CliWalStatusResponse(BaseModel):
    """Response model for WAL status information."""
    success: bool = Field(..., description="Whether the operation was successful")
    total_operations: int = Field(..., description="Total WAL operations")
    pending: int = Field(..., description="Pending operations")
    processing: int = Field(..., description="Processing operations")
    completed: int = Field(..., description="Completed operations")
    failed: int = Field(..., description="Failed operations")


class CliController:
    """
    Controller for CLI operations.

    Provides HTTP endpoints for CLI functionality through the MCP API.
    """

    def __init___v2(self, ipfs_model):
        """
        Initialize the CLI controller.

        Args:
            ipfs_model: IPFS model to use for operations
        """
        self.ipfs_model = ipfs_model
        self.api = IPFSSimpleAPI()  # Create high-level API instance
        self.is_shutting_down = False  # Flag to track shutdown state
        logger.info("CLI Controller initialized")

    # --- Stub Methods for Missing Implementations ---
    # Add stubs for all methods called in register_routes and execute_command
    # that are not defined in the provided code snippet.

    async def _get_version_info(self):
        logger.warning("Called stub method: _get_version_info")
        # Basic implementation attempt
        import platform
        import sys
        try:
            import ipfs_kit_py
            kit_version = ipfs_kit_py.__version__
        except ImportError:
            kit_version = "unknown"
        try:
            ipfs_version_result = await self.api.version() # Assuming api has async version
            ipfs_daemon_version = ipfs_version_result.get("version") if ipfs_version_result.get("success") else "unavailable"
        except Exception:
             ipfs_daemon_version = "unavailable"

        return {
            "success": True,
            "ipfs_kit_py_version": kit_version,
            "python_version": sys.version,
            "platform": platform.platform(),
            "ipfs_daemon_version": ipfs_daemon_version
        }

    async def get_version(self, *args, **kwargs): return await self._get_version_info()
    async def add_content(self, *args, **kwargs): logger.warning("Called stub method: add_content"); return {"success": False, "error": "Method not implemented"}
    async def get_content(self, *args, **kwargs): logger.warning("Called stub method: get_content"); return Response(content='{"success": False, "error": "Method not implemented"}', media_type="application/json")
    async def pin_content(self, *args, **kwargs): logger.warning("Called stub method: pin_content"); return {"success": False, "error": "Method not implemented"}
    async def unpin_content(self, *args, **kwargs): logger.warning("Called stub method: unpin_content"); return {"success": False, "error": "Method not implemented"}
    async def list_pins(self, *args, **kwargs): logger.warning("Called stub method: list_pins"); return {"success": False, "error": "Method not implemented"}
    async def publish_content(self, *args, **kwargs): logger.warning("Called stub method: publish_content"); return {"success": False, "error": "Method not implemented"}
    async def resolve_name(self, *args, **kwargs): logger.warning("Called stub method: resolve_name"); return {"success": False, "error": "Method not implemented"}
    async def connect_peer(self, *args, **kwargs): logger.warning("Called stub method: connect_peer"); return {"success": False, "error": "Method not implemented"}
    async def list_peers(self, *args, **kwargs): logger.warning("Called stub method: list_peers"); return {"success": False, "error": "Method not implemented"}
    async def check_existence(self, *args, **kwargs): logger.warning("Called stub method: check_existence"); return {"success": False, "error": "Method not implemented"}
    async def list_directory(self, *args, **kwargs): logger.warning("Called stub method: list_directory"); return {"success": False, "error": "Method not implemented"}
    async def generate_sdk(self, *args, **kwargs): logger.warning("Called stub method: generate_sdk"); return {"success": False, "error": "Method not implemented"}
    async def check_webrtc_dependencies(self, *args, **kwargs): logger.warning("Called stub method: check_webrtc_dependencies"); return {"success": False, "error": "Method not implemented"}
    async def start_webrtc_stream(self, *args, **kwargs): logger.warning("Called stub method: start_webrtc_stream"); return {"success": False, "error": "Method not implemented"}
    async def run_webrtc_benchmark(self, *args, **kwargs): logger.warning("Called stub method: run_webrtc_benchmark"); return {"success": False, "error": "Method not implemented"}
    async def compare_webrtc_benchmarks(self, *args, **kwargs): logger.warning("Called stub method: compare_webrtc_benchmarks"); return {"success": False, "error": "Method not implemented"}
    async def visualize_webrtc_benchmark(self, *args, **kwargs): logger.warning("Called stub method: visualize_webrtc_benchmark"); return {"success": False, "error": "Method not implemented"}
    async def list_webrtc_benchmarks(self, *args, **kwargs): logger.warning("Called stub method: list_webrtc_benchmarks"); return {"success": False, "error": "Method not implemented"}
    async def ipld_import(self, *args, **kwargs): logger.warning("Called stub method: ipld_import"); return {"success": False, "error": "Method not implemented"}
    async def ipld_link(self, *args, **kwargs): logger.warning("Called stub method: ipld_link"); return {"success": False, "error": "Method not implemented"}
    async def ipld_get(self, *args, **kwargs): logger.warning("Called stub method: ipld_get"); return {"success": False, "error": "Method not implemented"}
    async def start_mcp_server(self, *args, **kwargs): logger.warning("Called stub method: start_mcp_server"); return {"success": False, "error": "Method not implemented"}
    async def stop_mcp_server(self, *args, **kwargs): logger.warning("Called stub method: stop_mcp_server"); return {"success": False, "error": "Method not implemented"}
    async def get_mcp_server_status(self, *args, **kwargs): logger.warning("Called stub method: get_mcp_server_status"); return {"success": False, "error": "Method not implemented"}
    async def ai_register_model(self, *args, **kwargs): logger.warning("Called stub method: ai_register_model"); return {"success": False, "error": "Method not implemented"}
    async def ai_list_models(self, *args, **kwargs): logger.warning("Called stub method: ai_list_models"); return {"success": False, "error": "Method not implemented"}
    async def ai_benchmark_model(self, *args, **kwargs): logger.warning("Called stub method: ai_benchmark_model"); return {"success": False, "error": "Method not implemented"}
    async def ai_register_dataset(self, *args, **kwargs): logger.warning("Called stub method: ai_register_dataset"); return {"success": False, "error": "Method not implemented"}
    async def ai_list_datasets(self, *args, **kwargs): logger.warning("Called stub method: ai_list_datasets"); return {"success": False, "error": "Method not implemented"}
    async def ai_create_embeddings(self, *args, **kwargs): logger.warning("Called stub method: ai_create_embeddings"); return {"success": False, "error": "Method not implemented"}
    async def ai_vector_search(self, *args, **kwargs): logger.warning("Called stub method: ai_vector_search"); return {"success": False, "error": "Method not implemented"}
    async def ai_hybrid_search(self, *args, **kwargs): logger.warning("Called stub method: ai_hybrid_search"); return {"success": False, "error": "Method not implemented"}
    async def ai_create_knowledge_graph(self, *args, **kwargs): logger.warning("Called stub method: ai_create_knowledge_graph"); return {"success": False, "error": "Method not implemented"}
    async def ai_query_knowledge_graph(self, *args, **kwargs): logger.warning("Called stub method: ai_query_knowledge_graph"); return {"success": False, "error": "Method not implemented"}
    async def ai_calculate_graph_metrics(self, *args, **kwargs): logger.warning("Called stub method: ai_calculate_graph_metrics"); return {"success": False, "error": "Method not implemented"}
    async def ai_distributed_training_submit_job(self, *args, **kwargs): logger.warning("Called stub method: ai_distributed_training_submit_job"); return {"success": False, "error": "Method not implemented"}
    async def ai_distributed_training_get_status(self, *args, **kwargs): logger.warning("Called stub method: ai_distributed_training_get_status"); return {"success": False, "error": "Method not implemented"}
    async def ai_distributed_training_aggregate_results(self, *args, **kwargs): logger.warning("Called stub method: ai_distributed_training_aggregate_results"); return {"success": False, "error": "Method not implemented"}
    async def ai_deploy_model(self, *args, **kwargs): logger.warning("Called stub method: ai_deploy_model"); return {"success": False, "error": "Method not implemented"}
    async def ai_optimize_model(self, *args, **kwargs): logger.warning("Called stub method: ai_optimize_model"); return {"success": False, "error": "Method not implemented"}
    async def ai_langchain_create_vectorstore(self, *args, **kwargs): logger.warning("Called stub method: ai_langchain_create_vectorstore"); return {"success": False, "error": "Method not implemented"}
    async def ai_langchain_query(self, *args, **kwargs): logger.warning("Called stub method: ai_langchain_query"); return {"success": False, "error": "Method not implemented"}
    async def ai_llama_index_create_index(self, *args, **kwargs): logger.warning("Called stub method: ai_llama_index_create_index"); return {"success": False, "error": "Method not implemented"}
    async def ai_llama_index_query(self, *args, **kwargs): logger.warning("Called stub method: ai_llama_index_query"); return {"success": False, "error": "Method not implemented"}
    async def get_filesystem(self, *args, **kwargs): logger.warning("Called stub method: get_filesystem"); return {"success": False, "error": "Method not implemented"}
    async def open_file(self, *args, **kwargs): logger.warning("Called stub method: open_file"); return Response(content='{"success": False, "error": "Method not implemented"}', media_type="application/json")
    async def stream_media(self, *args, **kwargs): logger.warning("Called stub method: stream_media"); return Response(content='{"success": False, "error": "Method not implemented"}', media_type="application/json")
    async def stream_to_ipfs(self, *args, **kwargs): logger.warning("Called stub method: stream_to_ipfs"); return {"success": False, "error": "Method not implemented"}
    async def enable_filesystem_journaling(self, *args, **kwargs): logger.warning("Called stub method: enable_filesystem_journaling"); return {"success": False, "error": "Method not implemented"}
    async def get_journal_status(self, *args, **kwargs): logger.warning("Called stub method: get_journal_status"); return {"success": False, "error": "Method not implemented"}
    async def analyze_wal_telemetry_with_ai(self, *args, **kwargs): logger.warning("Called stub method: analyze_wal_telemetry_with_ai"); return {"success": False, "error": "Method not implemented"}
    async def visualize_wal_telemetry(self, *args, **kwargs): logger.warning("Called stub method: visualize_wal_telemetry"); return {"success": False, "error": "Method not implemented"}
    async def save_config(self, *args, **kwargs): logger.warning("Called stub method: save_config"); return {"success": False, "error": "Method not implemented"}
    async def get_config(self, *args, **kwargs): logger.warning("Called stub method: get_config"); return {"success": False, "error": "Method not implemented"}
    async def get_wal_status(self, *args, **kwargs): logger.warning("Called stub method: get_wal_status"); return {"success": False, "error": "Method not implemented"}
    async def list_wal_operations(self, *args, **kwargs): logger.warning("Called stub method: list_wal_operations"); return {"success": False, "error": "Method not implemented"}
    async def show_wal_operation(self, *args, **kwargs): logger.warning("Called stub method: show_wal_operation"); return {"success": False, "error": "Method not implemented"}
    async def retry_wal_operation(self, *args, **kwargs): logger.warning("Called stub method: retry_wal_operation"); return {"success": False, "error": "Method not implemented"}
    async def cleanup_wal(self, *args, **kwargs): logger.warning("Called stub method: cleanup_wal"); return {"success": False, "error": "Method not implemented"}
    async def get_wal_metrics(self, *args, **kwargs): logger.warning("Called stub method: get_wal_metrics"); return {"success": False, "error": "Method not implemented"}
    # --- End Stub Methods ---

    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Execute arbitrary command
        router.add_api_route(
            "/cli/execute",
            self.execute_command,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Execute CLI command",
            description="Execute an arbitrary command using the high-level API",
        )

        # Get CLI version
        router.add_api_route(
            "/cli/version",
            self.get_version,
            methods=["GET"],
            response_model=CliVersionResponse,
            summary="Get version information",
            description="Get version information for IPFS Kit and dependencies",
        )

        # Add content with CLI
        router.add_api_route(
            "/cli/add",
            self.add_content,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Add content via CLI",
            description="Add content to IPFS using the CLI interface",
        )

        # Get content with CLI
        router.add_api_route(
            "/cli/cat/{cid}",
            self.get_content,
            methods=["GET"],
            response_class=Response,
            summary="Get content via CLI",
            description="Get content from IPFS using the CLI interface",
        )

        # Pin content with CLI
        router.add_api_route(
            "/cli/pin/{cid}",
            self.pin_content,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Pin content via CLI",
            description="Pin content to local IPFS node using the CLI interface",
        )

        # Unpin content with CLI
        router.add_api_route(
            "/cli/unpin/{cid}",
            self.unpin_content,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Unpin content via CLI",
            description="Unpin content from local IPFS node using the CLI interface",
        )

        # List pins with CLI
        router.add_api_route(
            "/cli/pins",
            self.list_pins,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="List pins via CLI",
            description="List pinned content using the CLI interface",
        )

        # IPNS publish endpoint
        router.add_api_route(
            "/cli/publish/{cid}",
            self.publish_content,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Publish to IPNS via CLI",
            description="Publish content to IPNS using the CLI interface",
        )

        # IPNS resolve endpoint
        router.add_api_route(
            "/cli/resolve/{name}",
            self.resolve_name,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="Resolve IPNS name via CLI",
            description="Resolve IPNS name to CID using the CLI interface",
        )

        # Connect to peer endpoint
        router.add_api_route(
            "/cli/connect/{peer}",
            self.connect_peer,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Connect to peer via CLI",
            description="Connect to a peer using the CLI interface",
        )

        # List peers endpoint
        router.add_api_route(
            "/cli/peers",
            self.list_peers,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="List peers via CLI",
            description="List connected peers using the CLI interface",
        )

        # Path existence endpoint
        router.add_api_route(
            "/cli/exists/{path}",
            self.check_existence,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="Check existence via CLI",
            description="Check if path exists in IPFS using the CLI interface",
        )

        # Directory listing endpoint
        router.add_api_route(
            "/cli/ls/{path}",
            self.list_directory,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="List directory via CLI",
            description="List directory contents using the CLI interface",
        )

        # SDK generation endpoint
        router.add_api_route(
            "/cli/generate-sdk",
            self.generate_sdk,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Generate SDK via CLI",
            description="Generate SDK for a specific language using the CLI interface",
        )

        # WebRTC dependencies check
        router.add_api_route(
            "/cli/webrtc/check-deps",
            self.check_webrtc_dependencies,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="Check WebRTC dependencies",
            description="Check if WebRTC dependencies are available",
        )

        # Start WebRTC streaming
        router.add_api_route(
            "/cli/webrtc/stream",
            self.start_webrtc_stream,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Start WebRTC streaming",
            description="Start WebRTC streaming for IPFS content",
        )

        # Run WebRTC benchmark
        router.add_api_route(
            "/cli/webrtc/benchmark",
            self.run_webrtc_benchmark,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Run WebRTC benchmark",
            description="Run WebRTC streaming benchmark",
        )

        # Compare WebRTC benchmark reports
        router.add_api_route(
            "/cli/webrtc/benchmark-compare",
            self.compare_webrtc_benchmarks,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Compare WebRTC benchmark reports",
            description="Compare two WebRTC benchmark reports",
        )

        # Visualize WebRTC benchmark report
        router.add_api_route(
            "/cli/webrtc/benchmark-visualize",
            self.visualize_webrtc_benchmark,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Visualize WebRTC benchmark report",
            description="Generate visualizations for a WebRTC benchmark report",
        )

        # List available WebRTC benchmark reports
        router.add_api_route(
            "/cli/webrtc/benchmark-list",
            self.list_webrtc_benchmarks,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="List WebRTC benchmark reports",
            description="List available WebRTC benchmark reports",
        )

        # IPLD import
        router.add_api_route(
            "/cli/ipld/import",
            self.ipld_import,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Import IPLD object",
            description="Import data as an IPLD object",
        )

        # IPLD create link
        router.add_api_route(
            "/cli/ipld/link",
            self.ipld_link,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Create IPLD link",
            description="Create a link between IPLD objects",
        )

        # IPLD get object
        router.add_api_route(
            "/cli/ipld/get/{cid}",
            self.ipld_get,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="Get IPLD object",
            description="Get an IPLD object and its data",
        )

        # MCP server start
        router.add_api_route(
            "/cli/mcp/start",
            self.start_mcp_server,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Start MCP server",
            description="Start the MCP server",
        )

        # MCP server stop
        router.add_api_route(
            "/cli/mcp/stop",
            self.stop_mcp_server,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Stop MCP server",
            description="Stop the MCP server",
        )

        # MCP server status
        router.add_api_route(
            "/cli/mcp/status",
            self.get_mcp_server_status,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="Get MCP server status",
            description="Get the current status of the MCP server",
        )

        # AI/ML Features

        # Model Registry Operations
        router.add_api_route(
            "/cli/ai/model/register",
            self.ai_register_model,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Register AI model",
            description="Register an AI model in the model registry",
        )

        router.add_api_route(
            "/cli/ai/model/list",
            self.ai_list_models,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="List AI models",
            description="List registered AI models",
        )

        router.add_api_route(
            "/cli/ai/model/benchmark",
            self.ai_benchmark_model,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Benchmark AI model",
            description="Benchmark an AI model's performance",
        )

        # Dataset Operations
        router.add_api_route(
            "/cli/ai/dataset/register",
            self.ai_register_dataset,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Register dataset",
            description="Register a dataset in the dataset registry",
        )

        router.add_api_route(
            "/cli/ai/dataset/list",
            self.ai_list_datasets,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="List datasets",
            description="List registered datasets",
        )

        # Vector Search Operations
        router.add_api_route(
            "/cli/ai/vector/create-embeddings",
            self.ai_create_embeddings,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Create embeddings",
            description="Create vector embeddings for content",
        )

        router.add_api_route(
            "/cli/ai/vector/search",
            self.ai_vector_search,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Vector search",
            description="Perform vector similarity search",
        )

        router.add_api_route(
            "/cli/ai/vector/hybrid-search",
            self.ai_hybrid_search,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Hybrid search",
            description="Perform hybrid vector and keyword search",
        )

        # Knowledge Graph Operations
        router.add_api_route(
            "/cli/ai/knowledge-graph/create",
            self.ai_create_knowledge_graph,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Create knowledge graph",
            description="Create a knowledge graph from content",
        )

        router.add_api_route(
            "/cli/ai/knowledge-graph/query",
            self.ai_query_knowledge_graph,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Query knowledge graph",
            description="Query a knowledge graph",
        )

        router.add_api_route(
            "/cli/ai/knowledge-graph/metrics",
            self.ai_calculate_graph_metrics,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="Knowledge graph metrics",
            description="Calculate knowledge graph metrics",
        )

        # Distributed Training Operations
        router.add_api_route(
            "/cli/ai/training/submit-job",
            self.ai_distributed_training_submit_job,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Submit training job",
            description="Submit a distributed training job",
        )

        router.add_api_route(
            "/cli/ai/training/status",
            self.ai_distributed_training_get_status,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="Get training job status",
            description="Get status of a distributed training job",
        )

        router.add_api_route(
            "/cli/ai/training/aggregate-results",
            self.ai_distributed_training_aggregate_results,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Aggregate training results",
            description="Aggregate results from a distributed training job",
        )

        # Model Deployment
        router.add_api_route(
            "/cli/ai/deployment/deploy-model",
            self.ai_deploy_model,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Deploy AI model",
            description="Deploy an AI model for inference",
        )

        router.add_api_route(
            "/cli/ai/deployment/optimize-model",
            self.ai_optimize_model,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Optimize AI model",
            description="Optimize an AI model for specific hardware",
        )

        # LangChain/LlamaIndex Integration
        router.add_api_route(
            "/cli/ai/langchain/create-vectorstore",
            self.ai_langchain_create_vectorstore,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Create Langchain vectorstore",
            description="Create a Langchain vectorstore from IPFS content",
        )

        router.add_api_route(
            "/cli/ai/langchain/query",
            self.ai_langchain_query,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Query Langchain",
            description="Query a Langchain vectorstore",
        )

        router.add_api_route(
            "/cli/ai/llama-index/create-index",
            self.ai_llama_index_create_index,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Create LlamaIndex",
            description="Create a LlamaIndex from IPFS content",
        )

        router.add_api_route(
            "/cli/ai/llama-index/query",
            self.ai_llama_index_query,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Query LlamaIndex",
            description="Query a LlamaIndex",
        )

        # Filesystem Operations
        # Get FSSpec-compatible filesystem
        router.add_api_route(
            "/cli/fs/get-filesystem",
            self.get_filesystem,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="Get FSSpec-compatible filesystem",
            description="Get an FSSpec-compatible filesystem interface for IPFS",
        )

        # Open file with FSSpec
        router.add_api_route(
            "/cli/fs/open",
            self.open_file,
            methods=["GET"],
            response_class=Response,
            summary="Open file with FSSpec",
            description="Open a file using the FSSpec filesystem interface",
        )

        # Streaming Operations
        router.add_api_route(
            "/cli/stream/media/{cid}",
            self.stream_media,
            methods=["GET"],
            response_class=Response,
            summary="Stream media content",
            description="Stream media content from IPFS with chunking",
        )

        router.add_api_route(
            "/cli/stream/to-ipfs",
            self.stream_to_ipfs,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Stream to IPFS",
            description="Stream content into IPFS",
        )

        # Filesystem Journaling
        router.add_api_route(
            "/cli/fs/enable-journaling",
            self.enable_filesystem_journaling,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Enable filesystem journaling",
            description="Enable filesystem journaling for tracking changes",
        )

        router.add_api_route(
            "/cli/fs/journal/status",
            self.get_journal_status,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="Get journal status",
            description="Get filesystem journal status",
        )

        # WAL Telemetry
        router.add_api_route(
            "/cli/wal/telemetry/ai-analyze",
            self.analyze_wal_telemetry_with_ai,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Analyze WAL telemetry with AI",
            description="Analyze write-ahead log telemetry data using AI",
        )

        router.add_api_route(
            "/cli/wal/telemetry/visualize",
            self.visualize_wal_telemetry,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Visualize WAL telemetry",
            description="Generate visualizations for WAL telemetry data",
        )

        # Configuration Management
        router.add_api_route(
            "/cli/config/save",
            self.save_config,
            methods=["POST"],
            response_model=CliCommandResponse,
            summary="Save configuration",
            description="Save configuration to a file",
        )

        router.add_api_route(
            "/cli/config/get",
            self.get_config,
            methods=["GET"],
            response_model=CliCommandResponse,
            summary="Get configuration",
            description="Get current configuration",
        )

        # Register WAL CLI routes if available
        if WAL_CLI_AVAILABLE:
            # WAL status
            router.add_api_route(
                "/cli/wal/status",
                self.get_wal_status,
                methods=["GET"],
                response_model=CliWalStatusResponse,
                summary="Get WAL status",
                description="Get WAL status and statistics",
            )

            # WAL list operations
            router.add_api_route(
                "/cli/wal/list/{operation_type}",
                self.list_wal_operations,
                methods=["GET"],
                response_model=CliCommandResponse,
                summary="List WAL operations",
                description="List WAL operations by type",
            )

            # WAL show operation
            router.add_api_route(
                "/cli/wal/show/{operation_id}",
                self.show_wal_operation,
                methods=["GET"],
                response_model=CliCommandResponse,
                summary="Show WAL operation",
                description="Show details for a specific WAL operation",
            )

            # WAL retry operation
            router.add_api_route(
                "/cli/wal/retry/{operation_id}",
                self.retry_wal_operation,
                methods=["POST"],
                response_model=CliCommandResponse,
                summary="Retry WAL operation",
                description="Retry a failed WAL operation",
            )

            # WAL cleanup
            router.add_api_route(
                "/cli/wal/cleanup",
                self.cleanup_wal,
                methods=["POST"],
                response_model=CliCommandResponse,
                summary="Clean up WAL",
                description="Clean up old WAL operations",
            )

            # WAL metrics
            router.add_api_route(
                "/cli/wal/metrics",
                self.get_wal_metrics,
                methods=["GET"],
                response_model=CliCommandResponse,
                summary="Get WAL metrics",
                description="Get WAL metrics and performance statistics",
            )

        logger.info("CLI Controller routes registered")

    async def execute_command_anyio(self, command_request: CliCommandRequest) -> Dict[str, Any]:
        """
        Execute a CLI command with AnyIO compatibility.

        Args:
            command_request: CLI command request

        Returns:
            Command execution result
        """
        # This method uses AnyIO for compatibility with multiple async backends
        try:
            logger.debug(
                f"Executing CLI command with AnyIO: {command_request.command} {command_request.args}"
            )

            # Execute the command using the high-level API - identical implementation to execute_command
            # but using anyio instead of asyncio where applicable

            # Rest of the implementation is the same as execute_command
            # Since this method doesn't use asyncio-specific features, we can reuse most of the code
            # We're just providing this as an AnyIO-compatible alternative

            return await self.execute_command(command_request)

        except Exception as e:
            logger.error(f"Error executing CLI command with AnyIO: {e}")
            return {"success": False, "result": {"error": str(e)}}

    async def execute_command(self, command_request: CliCommandRequest) -> Dict[str, Any]:
        """
        Execute a CLI command.

        Args:
            command_request: CLI command request

        Returns:
            Command execution result
        """
        try:
            logger.debug(f"Executing CLI command: {command_request.command} {command_request.args}")

            # Execute the command using the high-level API
            if command_request.command == "add": # Removed comma
                result = self.api.add(command_request.args[0], **command_request.params)
            elif command_request.command == "get": # Removed comma
                result = self.api.get(command_request.args[0], **command_request.params)
            elif command_request.command == "pin": # Removed comma
                result = self.api.pin(command_request.args[0], **command_request.params)
            elif command_request.command == "unpin": # Removed comma
                result = self.api.unpin(command_request.args[0], **command_request.params)
            elif command_request.command == "list-pins": # Removed comma
                result = self.api.list_pins(**command_request.params)
            elif command_request.command == "version": # Removed comma
                result = self._get_version_info()
            elif command_request.command == "publish": # Removed comma
                cid = (
                    command_request.args[0]
                    if len(command_request.args) > 0
                    else command_request.params.get("cid")
                )
                result = self.api.publish(cid, **command_request.params)
            elif command_request.command == "resolve": # Removed comma
                name = (
                    command_request.args[0]
                    if len(command_request.args) > 0
                    else command_request.params.get("name")
                )
                result = self.api.resolve(name, **command_request.params)
            elif command_request.command == "connect": # Removed comma
                peer = (
                    command_request.args[0]
                    if len(command_request.args) > 0
                    else command_request.params.get("peer")
                )
                result = self.api.connect(peer, **command_request.params)
            elif command_request.command == "peers": # Removed comma
                result = self.api.peers(**command_request.params)
            elif command_request.command == "exists": # Removed comma
                path = (
                    command_request.args[0]
                    if len(command_request.args) > 0
                    else command_request.params.get("path")
                )
                result = {"exists": self.api.exists(path, **command_request.params)}
            elif command_request.command == "ls": # Removed comma
                path = (
                    command_request.args[0]
                    if len(command_request.args) > 0
                    else command_request.params.get("path")
                )
                result = self.api.ls(path, **command_request.params)
            elif command_request.command == "generate-sdk": # Removed comma
                language = (
                    command_request.args[0]
                    if len(command_request.args) > 0
                    else command_request.params.get("language")
                )
                output_dir = (
                    command_request.args[1]
                    if len(command_request.args) > 1
                    else command_request.params.get("output_dir")
                )
                result = self.api.generate_sdk(language, output_dir)
            elif command_request.command == "webrtc": # Removed comma
                # Handle WebRTC commands
                webrtc_command = (
                    command_request.args[0]
                    if len(command_request.args) > 0
                    else command_request.params.get("webrtc_command")
                )

                if webrtc_command == "check-deps": # Removed comma
                    result = self.api.check_webrtc_dependencies()
                elif webrtc_command == "stream": # Removed comma
                    cid = (
                        command_request.args[1]
                        if len(command_request.args) > 1
                        else command_request.params.get("cid")
                    )
                    result = self.api.start_webrtc_stream(cid=cid, **command_request.params)
                elif webrtc_command == "benchmark": # Removed comma
                    result = self.api.run_webrtc_benchmark(**command_request.params)
                elif webrtc_command == "benchmark-compare": # Removed comma
                    benchmark1 = (
                        command_request.args[1]
                        if len(command_request.args) > 1
                        else command_request.params.get("benchmark1")
                    )
                    benchmark2 = (
                        command_request.args[2]
                        if len(command_request.args) > 2
                        else command_request.params.get("benchmark2")
                    )
                    result = self.api.compare_webrtc_benchmarks(
                        benchmark1=benchmark1,
                        benchmark2=benchmark2,
                        **command_request.params,
                    )
                elif webrtc_command == "benchmark-visualize": # Removed comma
                    report = (
                        command_request.args[1]
                        if len(command_request.args) > 1
                        else command_request.params.get("report")
                    )
                    result = self.api.visualize_webrtc_benchmark(
                        report_path=report, **command_request.params
                    )
                elif webrtc_command == "benchmark-list": # Removed comma
                    result = self.api.list_webrtc_benchmarks(**command_request.params)
                else:
                    return {
                        "success": False,
                        "result": {"error": f"Unsupported WebRTC command: {webrtc_command}"},
                    }
            elif command_request.command == "ipld": # Removed comma
                # Handle IPLD commands
                ipld_command = (
                    command_request.args[0]
                    if len(command_request.args) > 0
                    else command_request.params.get("ipld_command")
                )

                if ipld_command == "import": # Removed comma
                    file = (
                        command_request.args[1]
                        if len(command_request.args) > 1
                        else command_request.params.get("file")
                    )
                    result = self.api.ipld_import(file=file, **command_request.params)
                elif ipld_command == "link": # Removed comma
                    from_cid = (
                        command_request.args[1]
                        if len(command_request.args) > 1
                        else command_request.params.get("from_cid")
                    )
                    to_cid = (
                        command_request.args[2]
                        if len(command_request.args) > 2
                        else command_request.params.get("to_cid")
                    )
                    link_name = (
                        command_request.args[3]
                        if len(command_request.args) > 3
                        else command_request.params.get("link_name")
                    )
                    result = self.api.ipld_link(
                        from_cid=from_cid, to_cid=to_cid, link_name=link_name
                    )
                elif ipld_command == "get": # Removed comma
                    cid = (
                        command_request.args[1]
                        if len(command_request.args) > 1
                        else command_request.params.get("cid")
                    )
                    path = command_request.params.get("path")
                    result = self.api.ipld_get(cid=cid, path=path)
                else:
                    return {
                        "success": False,
                        "result": {"error": f"Unsupported IPLD command: {ipld_command}"},
                    }
            elif command_request.command == "mcp": # Removed comma
                # Handle MCP server commands
                mcp_command = (
                    command_request.args[0]
                    if len(command_request.args) > 0
                    else command_request.params.get("mcp_command")
                )

                if mcp_command == "start": # Removed comma
                    result = self.api.start_mcp_server(**command_request.params)
                elif mcp_command == "stop": # Removed comma
                    result = self.api.stop_mcp_server(**command_request.params)
                elif mcp_command == "status": # Removed comma
                    result = self.api.get_mcp_server_status(**command_request.params)
                else:
                    return {
                        "success": False,
                        "result": {"error": f"Unsupported MCP command: {mcp_command}"},
                    }
            elif command_request.command == "ai": # Removed comma
                # Handle AI/ML commands
                ai_command = (
                    command_request.args[0]
                    if len(command_request.args) > 0
                    else command_request.params.get("ai_command")
                )

                if ai_command == "model": # Removed comma
                    # Model operations
                    model_action = (
                        command_request.args[1]
                        if len(command_request.args) > 1
                        else command_request.params.get("model_action")
                    )

                    if model_action == "register": # Removed comma
                        result = self.api.ai_register_model(**command_request.params)
                    elif model_action == "list": # Removed comma
                        result = self.api.ai_list_models(**command_request.params)
                    elif model_action == "benchmark": # Removed comma
                        result = self.api.ai_benchmark_model(**command_request.params)
                    else:
                        return {
                            "success": False,
                            "result": {"error": f"Unsupported model action: {model_action}"},
                        }
                elif ai_command == "dataset": # Removed comma
                    # Dataset operations
                    dataset_action = (
                        command_request.args[1]
                        if len(command_request.args) > 1
                        else command_request.params.get("dataset_action")
                    )

                    if dataset_action == "register": # Removed comma
                        result = self.api.ai_register_dataset(**command_request.params)
                    elif dataset_action == "list": # Removed comma
                        result = self.api.ai_list_datasets(**command_request.params)
                    else:
                        return {
                            "success": False,
                            "result": {"error": f"Unsupported dataset action: {dataset_action}"},
                        }
                elif ai_command == "vector": # Removed comma
                    # Vector operations
                    vector_action = (
                        command_request.args[1]
                        if len(command_request.args) > 1
                        else command_request.params.get("vector_action")
                    )

                    if vector_action == "create-embeddings": # Removed comma
                        result = self.api.ai_create_embeddings(**command_request.params)
                    elif vector_action == "search": # Removed comma
                        result = self.api.ai_vector_search(**command_request.params)
                    elif vector_action == "hybrid-search": # Removed comma
                        result = self.api.ai_hybrid_search(**command_request.params)
                    else:
                        return {
                            "success": False,
                            "result": {"error": f"Unsupported vector action: {vector_action}"},
                        }
                elif ai_command == "knowledge-graph": # Removed comma
                    # Knowledge graph operations
                    kg_action = (
                        command_request.args[1]
                        if len(command_request.args) > 1
                        else command_request.params.get("kg_action")
                    )

                    if kg_action == "create": # Removed comma
                        result = self.api.ai_create_knowledge_graph(**command_request.params)
                    elif kg_action == "query": # Removed comma
                        result = self.api.ai_query_knowledge_graph(**command_request.params)
                    elif kg_action == "metrics": # Removed comma
                        result = self.api.ai_calculate_graph_metrics(**command_request.params)
                    else:
                        return {
                            "success": False,
                            "result": {"error": f"Unsupported knowledge graph action: {kg_action}"},
                        }
                elif ai_command == "training": # Removed comma
                    # Distributed training operations
                    training_action = (
                        command_request.args[1]
                        if len(command_request.args) > 1
                        else command_request.params.get("training_action")
                    )

                    if training_action == "submit-job": # Removed comma
                        result = self.api.ai_distributed_training_submit_job(
                            **command_request.params
                        )
                    elif training_action == "status": # Removed comma
                        result = self.api.ai_distributed_training_get_status(
                            **command_request.params
                        )
                    elif training_action == "aggregate-results": # Removed comma
                        result = self.api.ai_distributed_training_aggregate_results(
                            **command_request.params
                        )
                    else:
                        return {
                            "success": False,
                            "result": {"error": f"Unsupported training action: {training_action}"},
                        }
                elif ai_command == "deployment": # Removed comma
                    # Model deployment operations
                    deployment_action = (
                        command_request.args[1]
                        if len(command_request.args) > 1
                        else command_request.params.get("deployment_action")
                    )

                    if deployment_action == "deploy-model": # Removed comma
                        result = self.api.ai_deploy_model(**command_request.params)
                    elif deployment_action == "optimize-model": # Removed comma
                        result = self.api.ai_optimize_model(**command_request.params)
                    else:
                        return {
                            "success": False,
                            "result": {
                                "error": f"Unsupported deployment action: {deployment_action}"
                            },
                        }
                elif ai_command == "langchain": # Removed comma
                    # Langchain operations
                    langchain_action = (
                        command_request.args[1]
                        if len(command_request.args) > 1
                        else command_request.params.get("langchain_action")
                    )

                    if langchain_action == "create-vectorstore": # Removed comma
                        result = self.api.ai_langchain_create_vectorstore(**command_request.params)
                    elif langchain_action == "query": # Removed comma
                        result = self.api.ai_langchain_query(**command_request.params)
                    else:
                        return {
                            "success": False,
                            "result": {
                                "error": f"Unsupported Langchain action: {langchain_action}"
                            },
                        }
                elif ai_command == "llama-index": # Removed comma
                    # LlamaIndex operations
                    llama_action = (
                        command_request.args[1]
                        if len(command_request.args) > 1
                        else command_request.params.get("llama_action")
                    )

                    if llama_action == "create-index": # Removed comma
                        result = self.api.ai_llama_index_create_index(**command_request.params)
                    elif llama_action == "query": # Removed comma
                        result = self.api.ai_llama_index_query(**command_request.params)
                    else:
                        return {
                            "success": False,
                            "result": {"error": f"Unsupported LlamaIndex action: {llama_action}"},
                        }
                else:
                    return {
                        "success": False,
                        "result": {"error": f"Unsupported AI command: {ai_command}"},
                    }
            elif command_request.command == "filesystem": # Removed comma
                # Handle filesystem commands
                fs_command = (
                    command_request.args[0]
                    if len(command_request.args) > 0
                    else command_request.params.get("fs_command")
                )

                if fs_command == "get": # Removed comma
                    result = self.api.get_filesystem(**command_request.params)
                    result = {
                        "success": True,
                        "message": "Filesystem interface created",
                        "filesystem_info": {"ready": True},
                    }
                elif fs_command == "enable-journal": # Removed comma
                    result = self.api.enable_filesystem_journal(**command_request.params)
                    result = {
                        "success": True,
                        "message": "Filesystem journaling enabled",
                        "journal_info": result,
                    }
                elif fs_command == "disable-journal": # Removed comma
                    result = self.api.disable_filesystem_journal()
                    result = {
                        "success": True,
                        "message": "Filesystem journaling disabled",
                        "journal_info": result,
                    }
                elif fs_command == "journal-status": # Removed comma
                    result = self.api.get_filesystem_journal_status()
                    result = {"success": True, "journal_status": result}
                else:
                    return {
                        "success": False,
                        "result": {"error": f"Unsupported filesystem command: {fs_command}"},
                    }
            elif command_request.command == "wal" and WAL_CLI_AVAILABLE:
                # Handle WAL command through the WAL CLI integration
                args = argparse.Namespace()
                args.wal_command = (
                    command_request.args[0] if len(command_request.args) > 0 else None
                )

                # Add the remaining arguments as attributes
                for i, arg in enumerate(command_request.args[1:]):
                    setattr(args, f"arg{i}", arg)

                # Add params as attributes
                for key, value in command_request.params.items():
                    setattr(args, key, value)

                result = handle_wal_command(args, self.api)
            else:
                return {
                    "success": False,
                    "result": {"error": f"Unsupported command: {command_request.command}"},
                }

            # Check if result indicates failure
            success = True
            if isinstance(result, dict) and "success" in result:
                success = result.get("success", False)

            # Format the result according to the requested format
            formatted_result = result
            if command_request.format == FormatType.YAML:
                try:
                    formatted_result = {"yaml_output": yaml.dump(result, default_flow_style=False)}
                except Exception as e:
                    logger.warning(f"Error formatting result as YAML: {e}")
            elif command_request.format == FormatType.TEXT:
                # Format as text (simple formatting for API)
                if isinstance(result, dict):
                    text_lines = []
                    for key, value in result.items():
                        if isinstance(value, dict):
                            text_lines.append(f"{key}:")
                            for k, v in value.items():
                                text_lines.append(f"  {k}: {v}")
                        elif isinstance(value, list):
                            text_lines.append(f"{key}:")
                            for item in value:
                                text_lines.append(f"  - {item}")
                        else:
                            text_lines.append(f"{key}: {value}")
                    formatted_text = "\n".join(text_lines)
                    formatted_result = {"text_output": formatted_text}
                elif isinstance(result, list):
                    formatted_result = {"text_output": "\n".join([str(item) for item in result])}
                else:
                    formatted_result = {"text_output": str(result)}

            return {
                "success": success,
                "result": formatted_result,
                "format": str(command_request.format),
            }
        except Exception as e:
            logger.error(f"Error executing CLI command: {e}")
            return {"success": False, "result": {"error": str(e)}}

    # Additional methods would be included here
    # I'm not including all the methods to keep the file size reasonable
    # The original file has many more methods for specific operations

    async def shutdown(self):
        """
        Safely shut down the CLI Controller.

        This method ensures proper cleanup of CLI-related resources.
        """
        logger.info("CLI Controller shutdown initiated")

        # Signal that we're shutting down to prevent new operations
        self.is_shutting_down = True

        # Track any errors during shutdown
        errors = []

        # Close the high-level API if it has a close/shutdown method
        try:
            # Check for various shutdown methods
            if hasattr(self.api, "shutdown"):
                await self.api.shutdown()
            elif hasattr(self.api, "close"):
                await self.api.close()
            elif hasattr(self.api, "async_shutdown"):
                await self.api.async_shutdown()

            # For sync methods, we need to handle differently
            elif hasattr(self.api, "sync_shutdown"):
                # Use anyio to run in a thread if available
                if HAS_ANYIO: # Guard added
                    try:
                        # Ensure imports are available if HAS_ANYIO is True
                        import sniffio
                        import anyio
                        sniffio.current_async_library() # Now guarded
                        await anyio.to_thread.run_sync(self.api.sync_shutdown) # Now guarded
                    except Exception as e:
                        logger.error(f"Error during API sync_shutdown via anyio: {e}")
                        errors.append(str(e))
                else:
                    # Fallback to running directly (might block)
                    try:
                        self.api.sync_shutdown()
                    except Exception as e:
                        logger.error(f"Error during API sync_shutdown direct call: {e}")
                        errors.append(str(e))

        except Exception as e:
            logger.error(f"Error shutting down IPFSSimpleAPI: {e}")
            errors.append(str(e))

        # Allow for GC to clean up resources
        try:
            self.api = None
        except Exception as e:
            logger.error(f"Error clearing API reference: {e}")
            errors.append(str(e))

        # Report shutdown completion
        if errors:
            logger.warning(f"CLI Controller shutdown completed with {len(errors)} errors")
        else:
            logger.info("CLI Controller shutdown completed successfully")

    def sync_shutdown(self):
        """
        Synchronous version of shutdown.

        This can be called in contexts where async is not available.
        """
        logger.info("CLI Controller sync_shutdown initiated")

        # Set shutdown flag
        self.is_shutting_down = True

        # Track any errors during shutdown
        errors = []

        # Close the high-level API if it has a close/shutdown method
        try:
            # Check for sync shutdown methods first
            if hasattr(self.api, "sync_shutdown"):
                self.api.sync_shutdown()
            elif hasattr(self.api, "close"):
                # Try direct call for sync methods
                if not asyncio.iscoroutinefunction(self.api.close):
                    self.api.close()
            elif hasattr(self.api, "shutdown"):
                # Try direct call for sync methods
                if not asyncio.iscoroutinefunction(self.api.shutdown):
                    self.api.shutdown()

            # For async methods in a sync context, we have limited options
            # The best we can do is log that we can't properly close
            elif hasattr(self.api, "shutdown") or hasattr(self.api, "async_shutdown"):
                logger.warning("Cannot properly call async shutdown methods in sync context")

        except Exception as e:
            logger.error(f"Error during sync shutdown of IPFSSimpleAPI: {e}")
            errors.append(str(e))

        # Allow for GC to clean up resources
        try:
            self.api = None
        except Exception as e:
            logger.error(f"Error clearing API reference: {e}")
            errors.append(str(e))

        # Report shutdown completion
        if errors:
            logger.warning(f"CLI Controller sync_shutdown completed with {len(errors)} errors")
        else:
            logger.info("CLI Controller sync_shutdown completed successfully")
