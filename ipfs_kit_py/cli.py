#!/usr/bin/env python3
"""
Command-line interface for IPFS Kit.

This module provides a command-line interface for interacting with IPFS Kit.
"""

import argparse
import importlib.metadata # Added
import json
import logging
import os
import platform # Added
import sys
from typing import Any, Dict, List, Optional, Union # Added Union

import yaml

try:
    # Use package imports when installed
    from .error import IPFSError, IPFSValidationError
    from .high_level_api import IPFSSimpleAPI
    from .validation import validate_cid
    # Import WAL CLI integration
    try:
        from .wal_cli_integration import register_wal_commands, handle_wal_command
        WAL_CLI_AVAILABLE = True
    except ImportError:
        WAL_CLI_AVAILABLE = False
    # Import Filesystem Journal CLI integration
    try:
        from .fs_journal_cli import register_fs_journal_commands
        FS_JOURNAL_CLI_AVAILABLE = True
    except ImportError:
        FS_JOURNAL_CLI_AVAILABLE = False
except ImportError:
    # Use relative imports when run directly
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from ipfs_kit_py.error import IPFSError, IPFSValidationError
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    from ipfs_kit_py.validation import validate_cid
    # Import WAL CLI integration
    try:
        from ipfs_kit_py.wal_cli_integration import register_wal_commands, handle_wal_command
        WAL_CLI_AVAILABLE = True
    except ImportError:
        WAL_CLI_AVAILABLE = False
    # Import Filesystem Journal CLI integration
    try:
        from ipfs_kit_py.fs_journal_cli import register_fs_journal_commands
        FS_JOURNAL_CLI_AVAILABLE = True
    except ImportError:
        FS_JOURNAL_CLI_AVAILABLE = False

# Set up logging
logger = logging.getLogger("ipfs_kit_cli")

# Global flag to control colorization
_enable_color = True

# Define colors for terminal output
COLORS = {
    "HEADER": "\033[95m",
    "BLUE": "\033[94m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "RED": "\033[91m",
    "ENDC": "\033[0m",
    "BOLD": "\033[1m",
    "UNDERLINE": "\033[4m",
}


def colorize(text: str, color: str) -> str:
    """
    Colorize text for terminal output.

    Args:
        text: Text to colorize
        color: Color name from COLORS dict

    Returns:
        Colorized text
    """
    # Skip colorization if stdout is not a terminal or if disabled
    if not _enable_color or not sys.stdout.isatty():
        return text

    color_code = COLORS.get(color.upper(), "")
    return f"{color_code}{text}{COLORS['ENDC']}"


def setup_logging(verbose: bool = False) -> None:
    """
    Set up logging configuration.

    Args:
        verbose: Whether to enable verbose logging
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def parse_key_value(value: str) -> Dict[str, Any]:
    """
    Parse a key=value string into a dictionary, with value type conversion.

    Args:
        value: Key-value string in format key=value

    Returns:
        Dictionary with parsed key-value pair
    """
    if "=" not in value:
        raise ValueError(f"Invalid key-value format: {value}. Expected format: key=value")

    key, val = value.split("=", 1)
    
    # Convert values appropriately
    if val.lower() == "true":
        val = True
    elif val.lower() == "false":
        val = False
    elif val.isdigit():
        val = int(val)
    elif "." in val and val.replace(".", "", 1).isdigit():
        val = float(val)
    else:
        # Try to parse as JSON if not a boolean or number
        try:
            val = json.loads(val)
        except json.JSONDecodeError:
            # Keep as string if not valid JSON
            pass
    
    return {key: val}


def handle_version_command(api, args, kwargs):
    """
    Handle the 'version' command to show version information.
    
    Args:
        api: The IPFS API instance
        args: Parsed command-line arguments
        kwargs: Additional keyword arguments
    
    Returns:
        Version information dictionary
    """
    # Get version information from the API
    try:
        # Try to get detailed version info if available
        version_info = api.version(**kwargs)
        return version_info
    except (AttributeError, NotImplementedError):
        # Fallback to package version if API doesn't support version command
        from importlib.metadata import version as pkg_version
        try:
            version = pkg_version("ipfs_kit_py")
        except:
            version = "unknown"
        return {
            "version": version,
            "api": "Simple API",
            "system": platform.system(),
            "python_version": platform.python_version()
        }


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Parse command-line arguments.

    Args:
        args: Command-line arguments

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="IPFS Kit CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        exit_on_error=False # Prevent SystemExit on error for better testing
    )

    # Global options
    parser.add_argument(
        "--config",
        "-c",
        help="Path to configuration file",
        default=None,
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output (sets logging to DEBUG)",
    )
    parser.add_argument(
        "--param",
        "-p",
        action="append",
        help="Additional parameter in format key=value (e.g., -p timeout=60)",
        default=[],
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "yaml"],
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )

    # Subcommands - make command required
    subparsers = parser.add_subparsers(dest="command", help="Command to execute", required=True)

    # Register WAL commands if available
    if WAL_CLI_AVAILABLE:
        try:
            register_wal_commands(subparsers)
            logger.debug("WAL commands registered.")
        except Exception as e:
            logger.warning(f"Could not register WAL commands: {e}")
    else:
        logger.debug("WAL CLI integration not available, skipping WAL command registration.")

    # Register Filesystem Journal commands if available
    if FS_JOURNAL_CLI_AVAILABLE:
        try:
            register_fs_journal_commands(subparsers)
            logger.debug("Filesystem Journal commands registered.")
        except Exception as e:
            logger.warning(f"Could not register Filesystem Journal commands: {e}")
    else:
        logger.debug("Filesystem Journal CLI integration not available, skipping command registration.")
        
    # Try to register WAL Telemetry commands
    try:
        from .wal_telemetry_cli import register_wal_telemetry_commands
        register_wal_telemetry_commands(subparsers)
        logger.debug("WAL Telemetry commands registered.")
    except Exception as e:
        logger.warning(f"Could not register WAL Telemetry commands: {e}")
        
    # Register additional advanced commands
    try:
        # Add parallel query execution commands
        add_parallel_query_commands(subparsers)
        logger.debug("Parallel query execution commands registered.")
        
        # Add unified dashboard commands
        add_dashboard_commands(subparsers)
        logger.debug("Unified dashboard commands registered.")
        
        # Add schema optimization commands
        add_schema_commands(subparsers)
        logger.debug("Schema optimization commands registered.")
    except Exception as e:
        logger.warning(f"Could not register some advanced commands: {e}")

    # Add command
    add_parser = subparsers.add_parser(
        "add",
        help="Add content to IPFS",
    )
    add_parser.add_argument(
        "content",
        help="Content to add (file path or content string)",
    )
    add_parser.add_argument(
        "--pin",
        action="store_true",
        help="Pin content after adding",
        default=True,
    )
    add_parser.add_argument(
        "--wrap-with-directory",
        action="store_true",
        help="Wrap content with a directory",
    )
    add_parser.add_argument(
        "--chunker",
        help="Chunking algorithm (e.g., size-262144)",
        default="size-262144",
    )
    add_parser.add_argument(
        "--hash",
        help="Hash algorithm (e.g., sha2-256)",
        default="sha2-256",
    )
    # Set the function to handle this command
    add_parser.set_defaults(func=lambda api, args, kwargs: api.add(args.content, **kwargs))


    # Get command
    get_parser = subparsers.add_parser(
        "get",
        help="Get content from IPFS",
    )
    get_parser.add_argument(
        "cid",
        help="Content identifier",
    )
    get_parser.add_argument(
        "--output",
        "-o",
        help="Output file path (if not provided, content is printed to stdout)",
    )
    get_parser.add_argument(
        "--timeout",
        type=int,
        help="Timeout in seconds",
        default=30,
        dest="timeout_get" # Use unique dest to avoid conflict
    )
    # Set the function to handle this command
    get_parser.set_defaults(func=lambda api, args, kwargs: handle_get_command(api, args, kwargs))


    # Pin command
    pin_parser = subparsers.add_parser(
        "pin",
        help="Pin content to local node",
    )
    pin_parser.add_argument(
        "cid",
        help="Content identifier",
    )
    pin_parser.add_argument(
        "--recursive",
        action="store_true",
        help="Pin recursively",
        default=True,
    )
    pin_parser.set_defaults(func=lambda api, args, kwargs: api.pin(args.cid, **kwargs))


    # Unpin command
    unpin_parser = subparsers.add_parser(
        "unpin",
        help="Unpin content from local node",
    )
    unpin_parser.add_argument(
        "cid",
        help="Content identifier",
    )
    unpin_parser.add_argument(
        "--recursive",
        action="store_true",
        help="Unpin recursively",
        default=True,
    )
    unpin_parser.set_defaults(func=lambda api, args, kwargs: api.unpin(args.cid, **kwargs))


    # List pins command
    list_pins_parser = subparsers.add_parser(
        "list-pins",
        help="List pinned content",
    )
    list_pins_parser.add_argument(
        "--type",
        choices=["all", "direct", "indirect", "recursive"],
        default="all",
        help="Pin type filter",
    )
    list_pins_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Return only CIDs",
    )
    list_pins_parser.set_defaults(func=lambda api, args, kwargs: api.list_pins(**kwargs))
    
    # WebRTC streaming commands
    webrtc_parser = subparsers.add_parser(
        "webrtc",
        help="WebRTC streaming operations",
    )
    webrtc_subparsers = webrtc_parser.add_subparsers(dest="webrtc_command", help="WebRTC command", required=True)
    
    # Check WebRTC dependencies
    webrtc_check_parser = webrtc_subparsers.add_parser(
        "check",
        help="Check WebRTC dependencies status",
        aliases=["check-deps"],  # Keep backward compatibility
    )
    webrtc_check_parser.set_defaults(func=lambda api, args, kwargs: api.check_webrtc_dependencies())
    
    # Start WebRTC stream from IPFS content
    webrtc_stream_parser = webrtc_subparsers.add_parser(
        "stream",
        help="Start WebRTC streaming for IPFS content",
    )
    webrtc_stream_parser.add_argument(
        "cid",
        help="Content identifier for media to stream",
    )
    webrtc_stream_parser.add_argument(
        "--address",
        default="127.0.0.1",
        help="Address to bind the WebRTC signaling server",
    )
    webrtc_stream_parser.add_argument(
        "--quality",
        choices=["low", "medium", "high", "auto"],
        default="medium",
        help="Streaming quality preset",
    )
    webrtc_stream_parser.add_argument(
        "--port",
        type=int,
        default=8083,
        help="Port for WebRTC signaling server",
    )
    webrtc_stream_parser.add_argument(
        "--ice-servers",
        help="JSON array of ICE servers (STUN/TURN)",
        default=json.dumps([{"urls": ["stun:stun.l.google.com:19302"]}])
    )
    webrtc_stream_parser.add_argument(
        "--adaptive-bitrate",
        action="store_true",
        help="Enable adaptive bitrate streaming",
        default=True
    )
    webrtc_stream_parser.add_argument(
        "--min-bitrate",
        type=int,
        default=100000,  # 100 Kbps
        help="Minimum bitrate in bps for adaptive streaming"
    )
    webrtc_stream_parser.add_argument(
        "--max-bitrate",
        type=int,
        default=5000000,  # 5 Mbps
        help="Maximum bitrate in bps for adaptive streaming"
    )
    webrtc_stream_parser.add_argument(
        "--frame-rate",
        type=int,
        default=30,
        help="Target frame rate for streaming"
    )
    webrtc_stream_parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Enable performance benchmarking during streaming",
    )
    webrtc_stream_parser.set_defaults(func=lambda api, args, kwargs: api.start_webrtc_stream(**kwargs))
    
    # Multi-peer streaming
    webrtc_multi_parser = webrtc_subparsers.add_parser(
        "multi-peer",
        help="Create multi-peer WebRTC streaming session",
    )
    webrtc_multi_parser.add_argument(
        "cid",
        help="Content identifier for media to stream",
    )
    webrtc_multi_parser.add_argument(
        "--max-peers",
        type=int,
        default=5,
        help="Maximum number of concurrent peers",
    )
    webrtc_multi_parser.add_argument(
        "--quality",
        choices=["low", "medium", "high", "auto"],
        default="medium",
        help="Streaming quality preset",
    )
    webrtc_multi_parser.add_argument(
        "--port",
        type=int,
        default=8083,
        help="Port for WebRTC signaling server",
    )
    webrtc_multi_parser.add_argument(
        "--ice-servers",
        help="JSON array of ICE servers (STUN/TURN)",
        default=json.dumps([{"urls": ["stun:stun.l.google.com:19302"]}])
    )
    webrtc_multi_parser.set_defaults(func=lambda api, args, kwargs: api.start_multi_peer_stream(**kwargs))
    
    # Get stream status
    webrtc_status_parser = webrtc_subparsers.add_parser(
        "status",
        help="Get status of active WebRTC streams",
    )
    webrtc_status_parser.add_argument(
        "--stream-id",
        help="Optional specific stream ID to check",
    )
    webrtc_status_parser.add_argument(
        "--detailed",
        action="store_true",
        help="Include detailed connection metrics",
    )
    webrtc_status_parser.set_defaults(func=lambda api, args, kwargs: api.get_webrtc_status(**kwargs))
    
    # WebRTC benchmark
    webrtc_benchmark_parser = webrtc_subparsers.add_parser(
        "benchmark",
        help="Run WebRTC streaming benchmark",
    )
    webrtc_benchmark_parser.add_argument(
        "cid",
        help="Content identifier for media to benchmark",
    )
    webrtc_benchmark_parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Benchmark duration in seconds",
    )
    webrtc_benchmark_parser.add_argument(
        "--bitrates",
        help="Comma-separated list of bitrates to test (in kbps)",
        default="500,1000,2000,5000"
    )
    webrtc_benchmark_parser.add_argument(
        "--output",
        help="Output file for benchmark results (JSON)",
        default="webrtc_benchmark_results.json"
    )
    webrtc_benchmark_parser.add_argument(
        "--enable-frame-stats",
        action="store_true",
        help="Enable detailed per-frame statistics",
        default=False
    )
    webrtc_benchmark_parser.add_argument(
        "--compare-with",
        help="Path to previous benchmark results for comparison",
    )
    webrtc_benchmark_parser.add_argument(
        "--track-resource-usage",
        action="store_true",
        help="Track CPU, memory and bandwidth usage",
        default=True
    )
    webrtc_benchmark_parser.add_argument(
        "--visualize",
        action="store_true",
        help="Generate visualizations of benchmark results",
        default=False
    )
    webrtc_benchmark_parser.set_defaults(func=lambda api, args, kwargs: api.run_webrtc_benchmark(args.cid, **kwargs))
    
    # WebRTC benchmark-compare command
    webrtc_compare_parser = webrtc_subparsers.add_parser(
        "benchmark-compare",
        help="Compare two WebRTC benchmark reports",
    )
    webrtc_compare_parser.add_argument(
        "--benchmark1",
        required=True,
        help="Path to first benchmark report file"
    )
    webrtc_compare_parser.add_argument(
        "--benchmark2",
        required=True,
        help="Path to second benchmark report file"
    )
    webrtc_compare_parser.add_argument(
        "--output",
        help="Output file for comparison results (JSON)"
    )
    webrtc_compare_parser.add_argument(
        "--visualize",
        action="store_true", 
        help="Generate visualizations of comparison results",
        default=False
    )
    webrtc_compare_parser.set_defaults(func=lambda api, args, kwargs: api.compare_webrtc_benchmarks(
        args.benchmark1, 
        args.benchmark2, 
        output=args.output,
        visualize=args.visualize,
        **kwargs
    ))
    
    # WebRTC benchmark-visualize command
    webrtc_visualize_parser = webrtc_subparsers.add_parser(
        "benchmark-visualize",
        help="Generate visualizations for a WebRTC benchmark report",
    )
    webrtc_visualize_parser.add_argument(
        "--report",
        required=True,
        help="Path to benchmark report file"
    )
    webrtc_visualize_parser.add_argument(
        "--output-dir",
        help="Output directory for visualizations (default: alongside report)"
    )
    webrtc_visualize_parser.set_defaults(func=lambda api, args, kwargs: api.visualize_webrtc_benchmark(
        args.report,
        output_dir=args.output_dir,
        **kwargs
    ))
    
    # WebRTC benchmark-list command
    webrtc_list_parser = webrtc_subparsers.add_parser(
        "benchmark-list",
        help="List available WebRTC benchmark reports",
    )
    webrtc_list_parser.add_argument(
        "--dir",
        help="Directory containing benchmark reports"
    )
    webrtc_list_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    webrtc_list_parser.set_defaults(func=lambda api, args, kwargs: api.list_webrtc_benchmarks(
        directory=args.dir,
        format=args.format,
        **kwargs
    ))
    
    # WebRTC connections management
    webrtc_conn_parser = webrtc_subparsers.add_parser(
        "connections",
        help="Manage WebRTC connections",
    )
    webrtc_conn_subparsers = webrtc_conn_parser.add_subparsers(
        dest="conn_action",
        help="Connection action to perform",
        required=True
    )
    
    # List connections
    webrtc_conn_list_parser = webrtc_conn_subparsers.add_parser(
        "list",
        help="List active WebRTC connections",
    )
    webrtc_conn_list_parser.set_defaults(func=lambda api, args, kwargs: api.list_webrtc_connections())
    
    # Connection stats
    webrtc_conn_stats_parser = webrtc_conn_subparsers.add_parser(
        "stats",
        help="Get statistics for a WebRTC connection",
    )
    webrtc_conn_stats_parser.add_argument(
        "--id",
        required=True,
        help="Connection ID",
    )
    webrtc_conn_stats_parser.set_defaults(func=lambda api, args, kwargs: api.get_webrtc_connection_stats(connection_id=args.id))
    
    # Close connection
    webrtc_conn_close_parser = webrtc_conn_subparsers.add_parser(
        "close",
        help="Close WebRTC connection(s)",
    )
    webrtc_conn_close_parser.add_argument(
        "--id",
        help="Connection ID (omit to close all connections)",
    )
    webrtc_conn_close_parser.set_defaults(func=lambda api, args, kwargs: 
        api.close_webrtc_connection(connection_id=args.id) if args.id else api.close_all_webrtc_connections())
    
    # Change quality
    webrtc_conn_quality_parser = webrtc_conn_subparsers.add_parser(
        "quality",
        help="Change streaming quality for a connection",
    )
    webrtc_conn_quality_parser.add_argument(
        "--id",
        required=True,
        help="Connection ID",
    )
    webrtc_conn_quality_parser.add_argument(
        "--quality",
        choices=["low", "medium", "high", "auto"],
        required=True,
        help="Quality preset to use",
    )
    webrtc_conn_quality_parser.set_defaults(func=lambda api, args, kwargs: api.set_webrtc_quality(connection_id=args.id, quality=args.quality))
    
    # IPLD commands
    ipld_parser = subparsers.add_parser(
        "ipld",
        help="IPLD operations for content-addressed data structures",
    )
    ipld_subparsers = ipld_parser.add_subparsers(dest="ipld_command", help="IPLD command", required=True)
    
    # Import IPLD object
    ipld_import_parser = ipld_subparsers.add_parser(
        "import",
        help="Import data as an IPLD object",
    )
    ipld_import_parser.add_argument(
        "file",
        help="File path to import",
    )
    ipld_import_parser.add_argument(
        "--format",
        choices=["json", "cbor", "raw"],
        default="json",
        help="IPLD format",
    )
    ipld_import_parser.add_argument(
        "--pin",
        action="store_true",
        default=True,
        help="Pin the imported object",
    )
    ipld_import_parser.set_defaults(func=lambda api, args, kwargs: api.ipld_import(args.file, **kwargs))
    
    # Create IPLD links
    ipld_link_parser = ipld_subparsers.add_parser(
        "link",
        help="Create links between IPLD objects",
    )
    ipld_link_parser.add_argument(
        "from_cid",
        help="Source CID",
    )
    ipld_link_parser.add_argument(
        "to_cid",
        help="Target CID",
    )
    ipld_link_parser.add_argument(
        "link_name",
        help="Link name",
    )
    ipld_link_parser.set_defaults(func=lambda api, args, kwargs: api.ipld_link(args.from_cid, args.to_cid, args.link_name))
    
    # Get IPLD object
    ipld_get_parser = ipld_subparsers.add_parser(
        "get",
        help="Get IPLD object",
    )
    ipld_get_parser.add_argument(
        "cid",
        help="Content identifier",
    )
    ipld_get_parser.add_argument(
        "--path",
        help="Optional path within the object",
    )
    ipld_get_parser.set_defaults(func=lambda api, args, kwargs: api.ipld_get(args.cid, path=args.path))
    
    # Knowledge Graph commands
    kg_parser = ipld_subparsers.add_parser(
        "knowledge-graph",
        help="Knowledge graph operations with IPLD",
        aliases=["kg"]
    )
    kg_subparsers = kg_parser.add_subparsers(dest="kg_command", help="Knowledge graph command", required=True)
    
    # Create entity
    kg_entity_parser = kg_subparsers.add_parser(
        "add-entity",
        help="Add an entity to the knowledge graph",
    )
    kg_entity_parser.add_argument(
        "entity_id",
        help="Unique entity identifier",
    )
    kg_entity_parser.add_argument(
        "--properties",
        help="Entity properties as JSON string",
        required=True
    )
    kg_entity_parser.add_argument(
        "--vector",
        help="Optional embedding vector as JSON array",
    )
    kg_entity_parser.set_defaults(func=lambda api, args, kwargs: api.kg_add_entity(
        args.entity_id,
        json.loads(args.properties),
        json.loads(args.vector) if args.vector else None,
        **kwargs
    ))
    
    # Add relationship
    kg_relation_parser = kg_subparsers.add_parser(
        "add-relationship",
        help="Add a relationship between entities",
    )
    kg_relation_parser.add_argument(
        "from_entity",
        help="Source entity ID",
    )
    kg_relation_parser.add_argument(
        "to_entity",
        help="Target entity ID",
    )
    kg_relation_parser.add_argument(
        "relationship_type",
        help="Type of relationship",
    )
    kg_relation_parser.add_argument(
        "--properties",
        help="Relationship properties as JSON string",
    )
    kg_relation_parser.set_defaults(func=lambda api, args, kwargs: api.kg_add_relationship(
        args.from_entity,
        args.to_entity,
        args.relationship_type,
        json.loads(args.properties) if args.properties else None,
        **kwargs
    ))
    
    # Query related entities
    kg_query_parser = kg_subparsers.add_parser(
        "query-related",
        help="Find entities related to a given entity",
    )
    kg_query_parser.add_argument(
        "entity_id",
        help="Entity ID to query",
    )
    kg_query_parser.add_argument(
        "--relationship-type",
        help="Filter by relationship type",
    )
    kg_query_parser.add_argument(
        "--direction",
        choices=["outgoing", "incoming", "both"],
        default="both",
        help="Relationship direction",
    )
    kg_query_parser.set_defaults(func=lambda api, args, kwargs: api.kg_query_related(
        args.entity_id,
        relationship_type=args.relationship_type,
        direction=args.direction,
        **kwargs
    ))
    
    # Vector search
    kg_vector_parser = kg_subparsers.add_parser(
        "vector-search",
        help="Find entities similar to a vector",
    )
    kg_vector_parser.add_argument(
        "vector",
        help="Embedding vector as JSON array",
    )
    kg_vector_parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of results to return",
    )
    kg_vector_parser.set_defaults(func=lambda api, args, kwargs: api.kg_vector_search(
        json.loads(args.vector),
        top_k=args.top_k,
        **kwargs
    ))
    
    # Graph-Vector Hybrid Search (GraphRAG)
    kg_graph_vector_parser = kg_subparsers.add_parser(
        "graph-vector-search",
        help="Combined graph and vector search",
        aliases=["graphrag"]
    )
    kg_graph_vector_parser.add_argument(
        "vector",
        help="Embedding vector as JSON array",
    )
    kg_graph_vector_parser.add_argument(
        "--hop-count",
        type=int,
        default=2,
        help="Number of hops to explore in the graph",
    )
    kg_graph_vector_parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of results to return",
    )
    kg_graph_vector_parser.set_defaults(func=lambda api, args, kwargs: api.kg_graph_vector_search(
        json.loads(args.vector),
        hop_count=args.hop_count,
        top_k=args.top_k,
        **kwargs
    ))
    
    # MCP server commands
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="MCP server operations",
    )
    mcp_subparsers = mcp_parser.add_subparsers(dest="mcp_command", help="MCP command", required=True)
    
    # Start MCP server
    mcp_start_parser = mcp_subparsers.add_parser(
        "start",
        help="Start the MCP server",
    )
    mcp_start_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind server",
    )
    mcp_start_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind server",
    )
    mcp_start_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )
    mcp_start_parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level",
    )
    mcp_start_parser.set_defaults(func=lambda api, args, kwargs: api.start_mcp_server(**kwargs))
    
    # Stop MCP server
    mcp_stop_parser = mcp_subparsers.add_parser(
        "stop",
        help="Stop the MCP server",
    )
    mcp_stop_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host of the server",
    )
    mcp_stop_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port of the server",
    )
    mcp_stop_parser.set_defaults(func=lambda api, args, kwargs: api.stop_mcp_server(**kwargs))
    
    # Get MCP server status
    mcp_status_parser = mcp_subparsers.add_parser(
        "status",
        help="Get MCP server status",
    )
    mcp_status_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host of the server",
    )
    mcp_status_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port of the server",
    )
    mcp_status_parser.set_defaults(func=lambda api, args, kwargs: api.get_mcp_server_status(**kwargs))
    
    # Credential management commands
    credential_parser = subparsers.add_parser(
        "credential",
        help="Credential management operations",
        aliases=["cred"]
    )
    credential_subparsers = credential_parser.add_subparsers(dest="credential_command", help="Credential command", required=True)
    
    # Add credential
    credential_add_parser = credential_subparsers.add_parser(
        "add",
        help="Add a new credential",
    )
    credential_add_parser.add_argument(
        "service",
        help="Service name (ipfs, s3, storacha, filecoin, etc.)",
    )
    credential_add_parser.add_argument(
        "name",
        help="Name for this credential set",
    )
    credential_add_parser.add_argument(
        "--key",
        required=True,
        help="API key or access key",
    )
    credential_add_parser.add_argument(
        "--secret",
        help="Secret key or access secret",
    )
    credential_add_parser.add_argument(
        "--token",
        help="Optional access token",
    )
    credential_add_parser.add_argument(
        "--endpoint",
        help="Optional service endpoint URL",
    )
    credential_add_parser.add_argument(
        "--region",
        help="Optional region (for S3-compatible services)",
    )
    credential_add_parser.add_argument(
        "--secure-storage",
        action="store_true",
        default=True,
        help="Use secure storage (keyring if available)",
    )
    credential_add_parser.set_defaults(func=lambda api, args, kwargs: api.add_credential(
        args.service,
        args.name,
        key=args.key,
        secret=args.secret,
        token=args.token,
        endpoint=args.endpoint,
        region=args.region,
        secure_storage=args.secure_storage,
        **kwargs
    ))
    
    # Remove credential
    credential_remove_parser = credential_subparsers.add_parser(
        "remove",
        help="Remove a credential",
    )
    credential_remove_parser.add_argument(
        "service",
        help="Service name",
    )
    credential_remove_parser.add_argument(
        "name",
        help="Credential name to remove",
    )
    credential_remove_parser.set_defaults(func=lambda api, args, kwargs: api.remove_credential(
        args.service,
        args.name,
        **kwargs
    ))
    
    # List credentials
    credential_list_parser = credential_subparsers.add_parser(
        "list",
        help="List available credentials",
    )
    credential_list_parser.add_argument(
        "--service",
        help="Filter by service name",
    )
    credential_list_parser.add_argument(
        "--show-secrets",
        action="store_true",
        help="Show secret values (use with caution)",
    )
    credential_list_parser.set_defaults(func=lambda api, args, kwargs: api.list_credentials(
        service=args.service,
        show_secrets=args.show_secrets,
        **kwargs
    ))
    
    # Filesystem commands
    filesystem_parser = subparsers.add_parser(
        "filesystem",
        help="Filesystem operations with IPFS content",
    )
    filesystem_subparsers = filesystem_parser.add_subparsers(dest="fs_command", help="Filesystem command", required=True)
    
    # Get filesystem command
    get_fs_parser = filesystem_subparsers.add_parser(
        "get",
        help="Get a FSSpec-compatible filesystem for IPFS content",
    )
    get_fs_parser.add_argument(
        "--cache-dir",
        help="Directory for caching filesystem data",
    )
    get_fs_parser.add_argument(
        "--cache-size",
        type=int,
        default=100 * 1024 * 1024,  # 100MB
        help="Size of the memory cache in bytes",
    )
    get_fs_parser.add_argument(
        "--use-mmap",
        action="store_true",
        default=True,
        help="Use memory mapping for large files",
    )
    get_fs_parser.add_argument(
        "--disk-cache-size",
        type=int,
        default=1024 * 1024 * 1024,  # 1GB
        help="Size of the disk cache in bytes",
    )
    get_fs_parser.set_defaults(func=lambda api, args, kwargs: {
        "success": True, 
        "message": "Filesystem interface created",
        "filesystem_info": api.get_filesystem(**kwargs) and {"ready": True}
    })
    
    # Tiered cache commands
    tiered_cache_parser = filesystem_subparsers.add_parser(
        "tiered-cache",
        help="Tiered cache operations",
        aliases=["cache"]
    )
    tiered_cache_subparsers = tiered_cache_parser.add_subparsers(dest="cache_command", help="Cache command", required=True)
    
    # Configure cache
    cache_configure_parser = tiered_cache_subparsers.add_parser(
        "configure",
        help="Configure tiered caching system",
    )
    cache_configure_parser.add_argument(
        "--memory-cache-size",
        type=int,
        default=100 * 1024 * 1024,  # 100MB
        help="Size of memory cache in bytes",
    )
    cache_configure_parser.add_argument(
        "--disk-cache-size",
        type=int,
        default=1024 * 1024 * 1024,  # 1GB
        help="Size of disk cache in bytes",
    )
    cache_configure_parser.add_argument(
        "--disk-cache-path",
        help="Path to disk cache location",
    )
    cache_configure_parser.add_argument(
        "--max-item-size",
        type=int,
        default=10 * 1024 * 1024,  # 10MB
        help="Maximum size for memory cache items in bytes",
    )
    cache_configure_parser.add_argument(
        "--min-access-count",
        type=int,
        default=2,
        help="Minimum access count for promotion to memory cache",
    )
    cache_configure_parser.add_argument(
        "--prefetch-enabled",
        action="store_true",
        default=True,
        help="Enable prefetching for sequential access patterns",
    )
    cache_configure_parser.set_defaults(func=lambda api, args, kwargs: api.configure_tiered_cache(**kwargs))
    
    # Get cache stats
    cache_stats_parser = tiered_cache_subparsers.add_parser(
        "stats",
        help="Get tiered cache statistics",
    )
    cache_stats_parser.add_argument(
        "--detailed",
        action="store_true",
        help="Include detailed tier-specific statistics",
    )
    cache_stats_parser.set_defaults(func=lambda api, args, kwargs: api.get_cache_stats(**kwargs))
    
    # Clear cache
    cache_clear_parser = tiered_cache_subparsers.add_parser(
        "clear",
        help="Clear cache contents",
    )
    cache_clear_parser.add_argument(
        "--tier",
        choices=["memory", "disk", "all"],
        default="all",
        help="Cache tier to clear",
    )
    cache_clear_parser.set_defaults(func=lambda api, args, kwargs: api.clear_cache(**kwargs))
    
    # Pin to cache tier
    cache_pin_parser = tiered_cache_subparsers.add_parser(
        "pin",
        help="Pin content to a specific cache tier",
    )
    cache_pin_parser.add_argument(
        "cid",
        help="Content ID to pin in cache",
    )
    cache_pin_parser.add_argument(
        "--tier",
        choices=["memory", "disk"],
        default="memory",
        help="Cache tier to pin content to",
    )
    cache_pin_parser.set_defaults(func=lambda api, args, kwargs: api.pin_to_cache_tier(args.cid, tier=args.tier, **kwargs))
    
    # Advanced partitioning
    partitioning_parser = filesystem_subparsers.add_parser(
        "partitioning",
        help="Advanced partitioning strategy configuration",
    )
    partitioning_parser.add_argument(
        "--strategy",
        choices=["time-based", "size-based", "content-type", "hybrid"],
        default="hybrid",
        help="Partitioning strategy",
    )
    partitioning_parser.add_argument(
        "--partition-size",
        type=int,
        default=1000000,
        help="Maximum records per partition",
    )
    partitioning_parser.set_defaults(func=lambda api, args, kwargs: api.configure_partitioning_strategy(**kwargs))
    
    # Enable journaling command
    journal_parser = filesystem_subparsers.add_parser(
        "enable-journal",
        help="Enable filesystem journaling for data consistency",
    )
    journal_parser.add_argument(
        "--journal-dir",
        help="Directory for journal files",
    )
    journal_parser.add_argument(
        "--sync-interval",
        type=int,
        default=60,
        help="Journal sync interval in seconds",
    )
    journal_parser.add_argument(
        "--max-entries",
        type=int,
        default=1000,
        help="Maximum entries per journal file",
    )
    journal_parser.add_argument(
        "--backend",
        choices=["file", "memory", "s3", "ipfs"],
        default="file",
        help="Journal storage backend",
    )
    journal_parser.add_argument(
        "--compression",
        choices=["none", "zlib", "lz4", "zstd"],
        default="zstd",
        help="Journal compression algorithm",
    )
    journal_parser.set_defaults(func=lambda api, args, kwargs: {
        "success": True,
        "message": "Filesystem journaling enabled",
        "journal_info": api.enable_filesystem_journal(**kwargs)
    })
    
    # Disable journaling command
    disable_journal_parser = filesystem_subparsers.add_parser(
        "disable-journal",
        help="Disable filesystem journaling",
    )
    disable_journal_parser.set_defaults(func=lambda api, args, kwargs: {
        "success": True,
        "message": "Filesystem journaling disabled",
        "journal_info": api.disable_filesystem_journal()
    })
    
    # Journal status command
    journal_status_parser = filesystem_subparsers.add_parser(
        "journal-status",
        help="Get filesystem journal status",
    )
    journal_status_parser.add_argument(
        "--detailed",
        action="store_true",
        help="Include detailed statistics",
    )
    journal_status_parser.set_defaults(func=lambda api, args, kwargs: {
        "success": True,
        "journal_status": api.get_filesystem_journal_status(**kwargs)
    })
    
    # Journal recovery command
    journal_recovery_parser = filesystem_subparsers.add_parser(
        "journal-recover",
        help="Recover from journal after failure",
    )
    journal_recovery_parser.add_argument(
        "--journal-file",
        help="Specific journal file to recover from",
    )
    journal_recovery_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate recovery without making changes",
    )
    journal_recovery_parser.set_defaults(func=lambda api, args, kwargs: api.recover_from_journal(**kwargs))
    
    # Probabilistic data structures commands
    pds_parser = filesystem_subparsers.add_parser(
        "probabilistic",
        help="Probabilistic data structure operations",
        aliases=["pds"]
    )
    pds_subparsers = pds_parser.add_subparsers(dest="pds_command", help="PDS command", required=True)
    
    # Bloom filter
    bloom_parser = pds_subparsers.add_parser(
        "bloom",
        help="Bloom filter operations",
    )
    bloom_parser.add_argument(
        "--operation",
        choices=["create", "add", "check", "info"],
        required=True,
        help="Operation to perform",
    )
    bloom_parser.add_argument(
        "--name",
        required=True,
        help="Name for the bloom filter",
    )
    bloom_parser.add_argument(
        "--item",
        help="Item to add or check (required for add/check operations)",
    )
    bloom_parser.add_argument(
        "--capacity",
        type=int,
        default=10000,
        help="Capacity for bloom filter (only for create operation)",
    )
    bloom_parser.add_argument(
        "--error-rate",
        type=float,
        default=0.01,
        help="Error rate for bloom filter (only for create operation)",
    )
    bloom_parser.set_defaults(func=lambda api, args, kwargs: api.bloom_filter_operation(
        args.operation,
        args.name,
        item=args.item,
        capacity=args.capacity,
        error_rate=args.error_rate,
        **kwargs
    ))
    
    # HyperLogLog
    hll_parser = pds_subparsers.add_parser(
        "hyperloglog",
        help="HyperLogLog operations",
        aliases=["hll"]
    )
    hll_parser.add_argument(
        "--operation",
        choices=["create", "add", "count", "merge"],
        required=True,
        help="Operation to perform",
    )
    hll_parser.add_argument(
        "--name",
        required=True,
        help="Name for the HyperLogLog counter",
    )
    hll_parser.add_argument(
        "--item",
        help="Item to add (required for add operation)",
    )
    hll_parser.add_argument(
        "--other",
        help="Other HLL to merge with (required for merge operation)",
    )
    hll_parser.add_argument(
        "--precision",
        type=int,
        default=14,
        help="Precision bits for HLL (only for create operation)",
    )
    hll_parser.set_defaults(func=lambda api, args, kwargs: api.hyperloglog_operation(
        args.operation,
        args.name,
        item=args.item,
        other=args.other,
        precision=args.precision,
        **kwargs
    ))
    
    # Arrow metadata index
    arrow_parser = filesystem_subparsers.add_parser(
        "arrow-index",
        help="Arrow-based metadata index operations",
        aliases=["arrow"]
    )
    arrow_subparsers = arrow_parser.add_subparsers(dest="arrow_command", help="Arrow index command", required=True)
    
    # Create index
    arrow_create_parser = arrow_subparsers.add_parser(
        "create",
        help="Create or initialize an Arrow metadata index",
    )
    arrow_create_parser.add_argument(
        "--base-path",
        help="Directory for index files",
    )
    arrow_create_parser.add_argument(
        "--partition-size",
        type=int,
        default=1000000,
        help="Max records per partition file",
    )
    arrow_create_parser.add_argument(
        "--sync-interval",
        type=int,
        default=300,
        help="Interval in seconds for syncing with peers",
    )
    arrow_create_parser.set_defaults(func=lambda api, args, kwargs: api.create_arrow_index(**kwargs))
    
    # Add record
    arrow_add_parser = arrow_subparsers.add_parser(
        "add",
        help="Add a record to the Arrow metadata index",
    )
    arrow_add_parser.add_argument(
        "record",
        help="JSON record to add to the index",
    )
    arrow_add_parser.set_defaults(func=lambda api, args, kwargs: api.add_to_arrow_index(json.loads(args.record), **kwargs))
    
    # Query index
    arrow_query_parser = arrow_subparsers.add_parser(
        "query",
        help="Query the Arrow metadata index",
    )
    arrow_query_parser.add_argument(
        "filters",
        help="JSON array of filter conditions [['field', 'op', 'value'], ...]",
    )
    arrow_query_parser.add_argument(
        "--columns",
        help="JSON array of columns to return",
    )
    arrow_query_parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of results to return",
    )
    arrow_query_parser.set_defaults(func=lambda api, args, kwargs: api.query_arrow_index(
        json.loads(args.filters),
        columns=json.loads(args.columns) if args.columns else None,
        limit=args.limit,
        **kwargs
    ))
    
    # Get by CID
    arrow_get_parser = arrow_subparsers.add_parser(
        "get-by-cid",
        help="Look up a record by CID",
    )
    arrow_get_parser.add_argument(
        "cid",
        help="Content identifier to look up",
    )
    arrow_get_parser.set_defaults(func=lambda api, args, kwargs: api.get_by_cid_from_arrow_index(args.cid, **kwargs))


    # Publish command
    publish_parser = subparsers.add_parser(
        "publish",
        help="Publish content to IPNS",
    )
    publish_parser.add_argument(
        "cid",
        help="Content identifier",
    )
    publish_parser.add_argument(
        "--key",
        default="self",
        help="IPNS key to use",
    )
    publish_parser.add_argument(
        "--lifetime",
        default="24h",
        help="IPNS record lifetime",
    )
    publish_parser.add_argument(
        "--ttl",
        default="1h",
        help="IPNS record TTL (e.g., 1h)",
    )
    publish_parser.set_defaults(func=lambda api, args, kwargs: api.publish(args.cid, key=args.key, lifetime=args.lifetime, ttl=args.ttl, **kwargs))


    # Resolve command
    resolve_parser = subparsers.add_parser(
        "resolve",
        help="Resolve IPNS name to CID",
    )
    resolve_parser.add_argument(
        "name",
        help="IPNS name to resolve",
    )
    resolve_parser.add_argument(
        "--recursive",
        action="store_true",
        help="Resolve recursively",
        default=True,
    )
    resolve_parser.add_argument(
        "--timeout",
        type=int,
        help="Timeout in seconds",
        default=30,
        dest="timeout_resolve" # Use unique dest
    )
    resolve_parser.set_defaults(func=lambda api, args, kwargs: api.resolve(args.name, **kwargs))


    # Connect command
    connect_parser = subparsers.add_parser(
        "connect",
        help="Connect to a peer",
    )
    connect_parser.add_argument(
        "peer",
        help="Peer multiaddress",
    )
    connect_parser.add_argument(
        "--timeout",
        type=int,
        help="Timeout in seconds",
        default=30,
        dest="timeout_connect" # Use unique dest
    )
    connect_parser.set_defaults(func=lambda api, args, kwargs: api.connect(args.peer, **kwargs))


    # Peers command
    peers_parser = subparsers.add_parser(
        "peers",
        help="List connected peers",
    )
    peers_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Return verbose information",
    )
    peers_parser.add_argument(
        "--latency",
        action="store_true",
        help="Include latency information",
    )
    peers_parser.add_argument(
        "--direction",
        action="store_true",
        help="Include connection direction",
    )
    peers_parser.set_defaults(func=lambda api, args, kwargs: api.peers(**kwargs))


    # Exists command
    exists_parser = subparsers.add_parser(
        "exists",
        help="Check if path exists in IPFS",
    )
    exists_parser.add_argument(
        "path",
        help="IPFS path or CID",
    )
    exists_parser.set_defaults(func=lambda api, args, kwargs: {"exists": api.exists(args.path, **kwargs)})


    # LS command
    ls_parser = subparsers.add_parser(
        "ls",
        help="List directory contents",
    )
    ls_parser.add_argument(
        "path",
        help="IPFS path or CID",
    )
    ls_parser.add_argument(
        "--detail",
        action="store_true",
        help="Return detailed information",
        default=True,
    )
    ls_parser.set_defaults(func=lambda api, args, kwargs: api.ls(args.path, **kwargs))


    # SDK command
    sdk_parser = subparsers.add_parser(
        "generate-sdk",
        help="Generate SDK for a specific language",
    )
    sdk_parser.add_argument(
        "language",
        choices=["python", "javascript", "rust"],
        help="Target language",
    )
    sdk_parser.add_argument(
        "output_dir",
        help="Output directory",
    )
    sdk_parser.set_defaults(func=lambda api, args, kwargs: api.generate_sdk(args.language, args.output_dir))
    
    
    # Cluster management commands
    cluster_parser = subparsers.add_parser(
        "cluster",
        help="IPFS cluster management operations",
    )
    cluster_subparsers = cluster_parser.add_subparsers(dest="cluster_command", help="Cluster command", required=True)
    
    # Create cluster command
    cluster_create_parser = cluster_subparsers.add_parser(
        "create",
        help="Create a new IPFS cluster with this node as master",
    )
    cluster_create_parser.add_argument(
        "--secret",
        help="Shared secret for cluster security (will be generated if not provided)",
    )
    cluster_create_parser.add_argument(
        "--listen-multiaddr",
        default="/ip4/0.0.0.0/tcp/9096",
        help="Multiaddress to listen on for cluster communication",
    )
    cluster_create_parser.add_argument(
        "--bootstrap-peers",
        help="Initial peers to connect with (comma-separated multiaddresses)",
    )
    cluster_create_parser.add_argument(
        "--replication-factor",
        type=int,
        default=2,
        help="Default replication factor for pinned content",
    )
    cluster_create_parser.set_defaults(func=lambda api, args, kwargs: api.create_cluster(
        secret=args.secret,
        listen_multiaddr=args.listen_multiaddr,
        bootstrap_peers=args.bootstrap_peers.split(",") if args.bootstrap_peers else None,
        replication_factor=args.replication_factor,
        **kwargs
    ))
    
    # Join cluster command
    cluster_join_parser = cluster_subparsers.add_parser(
        "join",
        help="Join an existing IPFS cluster",
    )
    cluster_join_parser.add_argument(
        "master_addr",
        help="Multiaddress of the cluster master node",
    )
    cluster_join_parser.add_argument(
        "--secret",
        required=True,
        help="Shared cluster secret",
    )
    cluster_join_parser.add_argument(
        "--role",
        choices=["worker", "leecher"],
        default="worker",
        help="Role to assume in the cluster",
    )
    cluster_join_parser.add_argument(
        "--listen-multiaddr",
        default="/ip4/0.0.0.0/tcp/9096",
        help="Multiaddress to listen on for cluster communication",
    )
    cluster_join_parser.set_defaults(func=lambda api, args, kwargs: api.join_cluster(
        args.master_addr,
        secret=args.secret,
        role=args.role,
        listen_multiaddr=args.listen_multiaddr,
        **kwargs
    ))
    
    # Leave cluster command
    cluster_leave_parser = cluster_subparsers.add_parser(
        "leave",
        help="Leave the current IPFS cluster",
    )
    cluster_leave_parser.add_argument(
        "--force",
        action="store_true",
        help="Force leave even if there are pending operations",
    )
    cluster_leave_parser.set_defaults(func=lambda api, args, kwargs: api.leave_cluster(
        force=args.force,
        **kwargs
    ))
    
    # List peers command
    cluster_peers_parser = cluster_subparsers.add_parser(
        "peers",
        help="List peers in the cluster",
    )
    cluster_peers_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed peer information",
    )
    cluster_peers_parser.set_defaults(func=lambda api, args, kwargs: api.list_cluster_peers(
        verbose=args.verbose,
        **kwargs
    ))
    
    # Cluster status command
    cluster_status_parser = cluster_subparsers.add_parser(
        "status",
        help="Get cluster status",
    )
    cluster_status_parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed cluster information",
    )
    cluster_status_parser.set_defaults(func=lambda api, args, kwargs: api.get_cluster_status(
        detailed=args.detailed,
        **kwargs
    ))
    
    # Set node role command
    cluster_role_parser = cluster_subparsers.add_parser(
        "set-role",
        help="Change role in the cluster",
    )
    cluster_role_parser.add_argument(
        "role",
        choices=["master", "worker", "leecher"],
        help="New role to assume",
    )
    cluster_role_parser.set_defaults(func=lambda api, args, kwargs: api.set_cluster_role(
        args.role,
        **kwargs
    ))
    
    # Cluster pin command
    cluster_pin_parser = cluster_subparsers.add_parser(
        "pin",
        help="Pin content across the cluster",
    )
    cluster_pin_parser.add_argument(
        "cid",
        help="Content identifier to pin",
    )
    cluster_pin_parser.add_argument(
        "--name",
        help="Human-readable name for this pin",
    )
    cluster_pin_parser.add_argument(
        "--replication-factor",
        type=int,
        help="Replication factor for this content (overrides cluster default)",
    )
    cluster_pin_parser.add_argument(
        "--allocations",
        help="Specific peer IDs for allocation (comma-separated)",
    )
    cluster_pin_parser.set_defaults(func=lambda api, args, kwargs: api.cluster_pin(
        args.cid,
        name=args.name,
        replication_factor=args.replication_factor,
        allocations=args.allocations.split(",") if args.allocations else None,
        **kwargs
    ))
    
    # Cluster unpin command
    cluster_unpin_parser = cluster_subparsers.add_parser(
        "unpin",
        help="Remove pin across the cluster",
    )
    cluster_unpin_parser.add_argument(
        "cid",
        help="Content identifier to unpin",
    )
    cluster_unpin_parser.set_defaults(func=lambda api, args, kwargs: api.cluster_unpin(
        args.cid,
        **kwargs
    ))
    
    # List cluster pins command
    cluster_ls_pins_parser = cluster_subparsers.add_parser(
        "ls-pins",
        help="List pins in the cluster",
    )
    cluster_ls_pins_parser.add_argument(
        "--status",
        choices=["all", "pinned", "pinning", "queued", "error"],
        default="all",
        help="Filter by pin status",
    )
    cluster_ls_pins_parser.add_argument(
        "--cid",
        help="Filter by specific CID",
    )
    cluster_ls_pins_parser.set_defaults(func=lambda api, args, kwargs: api.list_cluster_pins(
        status=args.status,
        cid=args.cid,
        **kwargs
    ))
    
    # Resource management commands
    resource_parser = subparsers.add_parser(
        "resource",
        help="Resource management operations",
    )
    resource_subparsers = resource_parser.add_subparsers(dest="resource_command", help="Resource command", required=True)
    
    # Resource status command
    resource_status_parser = resource_subparsers.add_parser(
        "status",
        help="Get current resource usage status",
    )
    resource_status_parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed resource information",
    )
    resource_status_parser.set_defaults(func=lambda api, args, kwargs: api.get_resource_status(
        detailed=args.detailed,
        **kwargs
    ))
    
    # Configure resource manager
    resource_config_parser = resource_subparsers.add_parser(
        "configure",
        help="Configure resource management parameters",
    )
    resource_config_parser.add_argument(
        "--enabled",
        type=lambda x: x.lower() in ("yes", "true", "t", "1"),
        help="Enable resource management (true/false)",
    )
    resource_config_parser.add_argument(
        "--monitor-interval",
        type=int,
        help="Resource monitoring interval in seconds",
    )
    resource_config_parser.add_argument(
        "--cpu-threshold",
        type=float,
        help="High CPU threshold percentage (0-100)",
    )
    resource_config_parser.add_argument(
        "--memory-threshold",
        type=float,
        help="High memory threshold percentage (0-100)",
    )
    resource_config_parser.add_argument(
        "--disk-threshold",
        type=float,
        help="High disk usage threshold percentage (0-100)",
    )
    resource_config_parser.add_argument(
        "--min-threads",
        type=int,
        help="Minimum thread count for adaptive thread pool",
    )
    resource_config_parser.add_argument(
        "--max-threads-factor",
        type=float,
        help="Maximum threads as a factor of CPU cores",
    )
    resource_config_parser.add_argument(
        "--config-file",
        help="JSON file with complete resource configuration",
    )
    resource_config_parser.set_defaults(func=lambda api, args, kwargs: api.configure_resource_management(
        **{k: v for k, v in vars(args).items() if k in [
            "enabled", "monitor_interval", "cpu_threshold", "memory_threshold", 
            "disk_threshold", "min_threads", "max_threads_factor", "config_file"
        ] and v is not None}
    ))
    
    # Resource monitoring command
    resource_monitor_parser = resource_subparsers.add_parser(
        "monitor",
        help="Start resource monitoring with periodic updates",
    )
    resource_monitor_parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Update interval in seconds",
    )
    resource_monitor_parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Total monitoring duration in seconds",
    )
    resource_monitor_parser.add_argument(
        "--output-file",
        help="Save monitoring data to file",
    )
    resource_monitor_parser.set_defaults(func=lambda api, args, kwargs: api.monitor_resources(
        interval=args.interval,
        duration=args.duration,
        output_file=args.output_file,
        **kwargs
    ))
    
    # Resource allocation command
    resource_allocate_parser = resource_subparsers.add_parser(
        "allocate",
        help="Get resource allocation recommendations",
    )
    resource_allocate_parser.add_argument(
        "--component",
        choices=["cache", "threadpool", "prefetch", "all"],
        default="all",
        help="Component to get allocation for",
    )
    resource_allocate_parser.set_defaults(func=lambda api, args, kwargs: api.get_resource_allocation(
        component=args.component,
        **kwargs
    ))
    
    # Health monitoring commands
    health_parser = subparsers.add_parser(
        "health",
        help="Health monitoring and diagnostics",
    )
    health_subparsers = health_parser.add_subparsers(dest="health_command", help="Health command", required=True)
    
    # Health check command
    health_check_parser = health_subparsers.add_parser(
        "check",
        help="Run health check diagnostics",
    )
    health_check_parser.add_argument(
        "--full",
        action="store_true",
        help="Run full diagnostic check",
    )
    health_check_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds for health checks",
    )
    health_check_parser.add_argument(
        "--components",
        help="Comma-separated list of components to check (default: all)",
    )
    health_check_parser.set_defaults(func=lambda api, args, kwargs: api.run_health_check(
        full=args.full,
        timeout=args.timeout,
        components=args.components.split(",") if args.components else None,
        **kwargs
    ))
    
    # System metrics command
    health_metrics_parser = health_subparsers.add_parser(
        "metrics",
        help="Get system health metrics",
    )
    health_metrics_parser.add_argument(
        "--format",
        choices=["text", "json", "prometheus"],
        default="text",
        help="Output format for metrics",
    )
    health_metrics_parser.add_argument(
        "--historical",
        action="store_true",
        help="Include historical metrics data",
    )
    health_metrics_parser.add_argument(
        "--time-range",
        help="Time range for historical data (e.g., 1h, 24h, 7d)",
        default="1h",
    )
    health_metrics_parser.set_defaults(func=lambda api, args, kwargs: api.get_health_metrics(
        format=args.format,
        historical=args.historical,
        time_range=args.time_range,
        **kwargs
    ))
    
    # Enable monitoring command
    health_monitor_parser = health_subparsers.add_parser(
        "monitor",
        help="Enable continuous health monitoring",
    )
    health_monitor_parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Monitoring interval in seconds",
    )
    health_monitor_parser.add_argument(
        "--alert-threshold",
        type=float,
        default=80.0,
        help="Alert threshold percentage",
    )
    health_monitor_parser.add_argument(
        "--alert-method",
        choices=["log", "stdout", "webhook"],
        default="log",
        help="Alert notification method",
    )
    health_monitor_parser.add_argument(
        "--webhook-url",
        help="Webhook URL for alerts (if alert-method=webhook)",
    )
    health_monitor_parser.set_defaults(func=lambda api, args, kwargs: api.enable_health_monitoring(
        interval=args.interval,
        alert_threshold=args.alert_threshold,
        alert_method=args.alert_method,
        webhook_url=args.webhook_url,
        **kwargs
    ))
    
    # Diagnostic tools command
    health_diagnostic_parser = health_subparsers.add_parser(
        "diagnostic",
        help="Run diagnostic tools",
    )
    health_diagnostic_parser.add_argument(
        "tool",
        choices=["network", "storage", "daemon", "api", "all"],
        help="Diagnostic tool to run",
    )
    health_diagnostic_parser.add_argument(
        "--output-dir",
        help="Directory to save diagnostic reports",
    )
    health_diagnostic_parser.add_argument(
        "--detailed",
        action="store_true",
        help="Include detailed information in reports",
    )
    health_diagnostic_parser.set_defaults(func=lambda api, args, kwargs: api.run_diagnostic_tool(
        args.tool,
        output_dir=args.output_dir,
        detailed=args.detailed,
        **kwargs
    ))
    
    # Network configuration commands
    network_parser = subparsers.add_parser(
        "network",
        help="Network configuration operations",
        aliases=["swarm"]
    )
    network_subparsers = network_parser.add_subparsers(dest="network_command", help="Network command", required=True)
    
    # Network info command
    network_info_parser = network_subparsers.add_parser(
        "info",
        help="Show network configuration information",
    )
    network_info_parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed network information",
    )
    network_info_parser.set_defaults(func=lambda api, args, kwargs: api.get_network_info(
        detailed=args.detailed,
        **kwargs
    ))
    
    # Network configuration command
    network_config_parser = network_subparsers.add_parser(
        "config",
        help="Configure network settings",
    )
    network_config_parser.add_argument(
        "--listen-addresses",
        help="Comma-separated list of multiaddresses to listen on",
    )
    network_config_parser.add_argument(
        "--announce-addresses",
        help="Comma-separated list of multiaddresses to announce",
    )
    network_config_parser.add_argument(
        "--connection-manager-low",
        type=int,
        help="Low watermark for connection manager",
    )
    network_config_parser.add_argument(
        "--connection-manager-high",
        type=int,
        help="High watermark for connection manager",
    )
    network_config_parser.add_argument(
        "--enable-relay",
        type=lambda x: x.lower() in ("yes", "true", "t", "1"),
        help="Enable relay functionality (true/false)",
    )
    network_config_parser.add_argument(
        "--enable-auto-relay",
        type=lambda x: x.lower() in ("yes", "true", "t", "1"),
        help="Enable auto relay client (true/false)",
    )
    network_config_parser.add_argument(
        "--enable-nat-traversal",
        type=lambda x: x.lower() in ("yes", "true", "t", "1"),
        help="Enable NAT traversal techniques (true/false)",
    )
    network_config_parser.add_argument(
        "--config-file",
        help="Path to JSON file with network configuration",
    )
    network_config_parser.set_defaults(func=lambda api, args, kwargs: api.configure_network(**{
        k: v for k, v in vars(args).items() 
        if k in ["listen_addresses", "announce_addresses", "connection_manager_low", 
                 "connection_manager_high", "enable_relay", "enable_auto_relay", 
                 "enable_nat_traversal", "config_file"] 
        and v is not None
    }))
    
    # Bootstrap commands
    bootstrap_parser = network_subparsers.add_parser(
        "bootstrap",
        help="Bootstrap node operations",
    )
    bootstrap_subparsers = bootstrap_parser.add_subparsers(dest="bootstrap_command", help="Bootstrap command", required=True)
    
    # List bootstrap nodes
    bootstrap_list_parser = bootstrap_subparsers.add_parser(
        "list",
        help="List bootstrap nodes",
    )
    bootstrap_list_parser.set_defaults(func=lambda api, args, kwargs: api.list_bootstrap_nodes(**kwargs))
    
    # Add bootstrap node
    bootstrap_add_parser = bootstrap_subparsers.add_parser(
        "add",
        help="Add a bootstrap node",
    )
    bootstrap_add_parser.add_argument(
        "peer",
        help="Peer multiaddress to add as bootstrap node",
    )
    bootstrap_add_parser.set_defaults(func=lambda api, args, kwargs: api.add_bootstrap_node(args.peer, **kwargs))
    
    # Remove bootstrap node
    bootstrap_remove_parser = bootstrap_subparsers.add_parser(
        "remove",
        help="Remove a bootstrap node",
    )
    bootstrap_remove_parser.add_argument(
        "peer",
        help="Peer multiaddress to remove from bootstrap nodes",
    )
    bootstrap_remove_parser.set_defaults(func=lambda api, args, kwargs: api.remove_bootstrap_node(args.peer, **kwargs))
    
    # Reset bootstrap nodes
    bootstrap_reset_parser = bootstrap_subparsers.add_parser(
        "reset",
        help="Reset to default bootstrap nodes",
    )
    bootstrap_reset_parser.set_defaults(func=lambda api, args, kwargs: api.reset_bootstrap_nodes(**kwargs))
    
    # Peer connection commands
    peer_parser = network_subparsers.add_parser(
        "peer",
        help="Peer connection operations",
    )
    peer_subparsers = peer_parser.add_subparsers(dest="peer_command", help="Peer command", required=True)
    
    # Connect to peer
    peer_connect_parser = peer_subparsers.add_parser(
        "connect",
        help="Connect to a peer",
    )
    peer_connect_parser.add_argument(
        "peer",
        help="Peer multiaddress to connect to",
    )
    peer_connect_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Connection timeout in seconds",
    )
    peer_connect_parser.set_defaults(func=lambda api, args, kwargs: api.connect_peer(args.peer, timeout=args.timeout, **kwargs))
    
    # Disconnect from peer
    peer_disconnect_parser = peer_subparsers.add_parser(
        "disconnect",
        help="Disconnect from a peer",
    )
    peer_disconnect_parser.add_argument(
        "peer",
        help="Peer ID to disconnect from",
    )
    peer_disconnect_parser.set_defaults(func=lambda api, args, kwargs: api.disconnect_peer(args.peer, **kwargs))
    
    # List peers
    peer_list_parser = peer_subparsers.add_parser(
        "list",
        help="List connected peers",
        aliases=["ls"]
    )
    peer_list_parser.add_argument(
        "--direction",
        choices=["all", "inbound", "outbound"],
        default="all",
        help="Filter by connection direction",
    )
    peer_list_parser.add_argument(
        "--latency",
        action="store_true",
        help="Show latency information",
    )
    peer_list_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show verbose peer information",
    )
    peer_list_parser.set_defaults(func=lambda api, args, kwargs: api.list_peers(
        direction=args.direction,
        latency=args.latency,
        verbose=args.verbose,
        **kwargs
    ))
    
    # Node addresses
    addresses_parser = network_subparsers.add_parser(
        "addresses",
        help="Show node address information",
        aliases=["addrs"]
    )
    addresses_parser.add_argument(
        "--peer-id",
        help="Show addresses for specific peer ID instead of local node",
    )
    addresses_parser.set_defaults(func=lambda api, args, kwargs: api.get_node_addresses(
        peer_id=args.peer_id,
        **kwargs
    ))


    # Plugin management commands
    plugin_parser = subparsers.add_parser(
        "plugin",
        help="Plugin management operations",
    )
    plugin_subparsers = plugin_parser.add_subparsers(dest="plugin_command", help="Plugin command", required=True)
    
    # List plugins
    plugin_list_parser = plugin_subparsers.add_parser(
        "list",
        help="List available plugins",
    )
    plugin_list_parser.add_argument(
        "--status",
        choices=["all", "enabled", "disabled"],
        default="all",
        help="Filter plugins by status",
    )
    plugin_list_parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed plugin information",
    )
    plugin_list_parser.set_defaults(func=lambda api, args, kwargs: api.list_plugins(
        status=args.status,
        detailed=args.detailed,
        **kwargs
    ))
    
    # Enable plugin
    plugin_enable_parser = plugin_subparsers.add_parser(
        "enable",
        help="Enable a plugin",
    )
    plugin_enable_parser.add_argument(
        "name",
        help="Plugin name to enable",
    )
    plugin_enable_parser.set_defaults(func=lambda api, args, kwargs: api.enable_plugin(
        args.name,
        **kwargs
    ))
    
    # Disable plugin
    plugin_disable_parser = plugin_subparsers.add_parser(
        "disable",
        help="Disable a plugin",
    )
    plugin_disable_parser.add_argument(
        "name",
        help="Plugin name to disable",
    )
    plugin_disable_parser.set_defaults(func=lambda api, args, kwargs: api.disable_plugin(
        args.name,
        **kwargs
    ))
    
    # Register plugin
    plugin_register_parser = plugin_subparsers.add_parser(
        "register",
        help="Register a new plugin",
    )
    plugin_register_parser.add_argument(
        "name",
        help="Plugin name",
    )
    plugin_register_parser.add_argument(
        "path",
        help="Module path where plugin is defined",
    )
    plugin_register_parser.add_argument(
        "--config",
        help="JSON string with plugin configuration",
    )
    plugin_register_parser.add_argument(
        "--enabled",
        action="store_true",
        default=True,
        help="Enable plugin after registration",
    )
    plugin_register_parser.set_defaults(func=lambda api, args, kwargs: api.register_plugin(
        args.name,
        args.path,
        config=json.loads(args.config) if args.config else None,
        enabled=args.enabled,
        **kwargs
    ))
    
    # AI/ML integration commands
    aiml_parser = subparsers.add_parser(
        "ai-ml",
        help="AI/ML integration operations",
        aliases=["aiml", "ai"]
    )
    aiml_subparsers = aiml_parser.add_subparsers(dest="aiml_command", help="AI/ML command", required=True)
    
    # Generate embeddings
    embedding_parser = aiml_subparsers.add_parser(
        "embed",
        help="Generate embeddings for content",
    )
    embedding_parser.add_argument(
        "content",
        help="Content or CID to generate embeddings for",
    )
    embedding_parser.add_argument(
        "--model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Embedding model to use",
    )
    embedding_parser.add_argument(
        "--is-cid",
        action="store_true",
        help="Treat content as a CID instead of raw text",
    )
    embedding_parser.add_argument(
        "--store",
        action="store_true",
        help="Store embedding in metadata index",
    )
    embedding_parser.set_defaults(func=lambda api, args, kwargs: api.generate_embedding(
        args.content,
        model=args.model,
        is_cid=args.is_cid,
        store=args.store,
        **kwargs
    ))
    
    # Distributed model training
    training_parser = aiml_subparsers.add_parser(
        "train",
        help="Distributed model training operations",
    )
    training_parser.add_argument(
        "--dataset-cid",
        required=True,
        help="CID of the dataset to use for training",
    )
    training_parser.add_argument(
        "--model-type",
        choices=["classification", "regression", "language-model"],
        required=True,
        help="Type of model to train",
    )
    training_parser.add_argument(
        "--role",
        choices=["master", "worker"],
        default="master",
        help="Role in distributed training",
    )
    training_parser.add_argument(
        "--output-dir",
        help="Directory to save the trained model",
    )
    training_parser.add_argument(
        "--parameters",
        help="JSON string of training parameters",
    )
    training_parser.set_defaults(func=lambda api, args, kwargs: api.train_model(
        args.dataset_cid,
        model_type=args.model_type,
        role=args.role,
        output_dir=args.output_dir,
        parameters=json.loads(args.parameters) if args.parameters else None,
        **kwargs
    ))
    
    # Model inference
    inference_parser = aiml_subparsers.add_parser(
        "inference",
        help="Run inference with a model",
    )
    inference_parser.add_argument(
        "--model-cid",
        required=True,
        help="CID of the model to use",
    )
    inference_parser.add_argument(
        "--input",
        required=True,
        help="Input data for inference (raw text or CID)",
    )
    inference_parser.add_argument(
        "--is-cid",
        action="store_true",
        help="Treat input as a CID instead of raw text",
    )
    inference_parser.add_argument(
        "--output-cid",
        action="store_true",
        help="Store results in IPFS and return CID",
    )
    inference_parser.set_defaults(func=lambda api, args, kwargs: api.run_inference(
        args.model_cid,
        args.input,
        is_cid=args.is_cid,
        output_cid=args.output_cid,
        **kwargs
    ))
    
    # LangChain/LlamaIndex integration
    llm_integration_parser = aiml_subparsers.add_parser(
        "llm-integration",
        help="LLM framework integration operations",
        aliases=["llm"]
    )
    llm_integration_parser.add_argument(
        "--operation",
        choices=["initialize", "build-index", "query"],
        required=True,
        help="Operation to perform",
    )
    llm_integration_parser.add_argument(
        "--framework",
        choices=["langchain", "llama-index"],
        default="langchain",
        help="LLM framework to use",
    )
    llm_integration_parser.add_argument(
        "--content-cid",
        help="CID of content to index (for build-index operation)",
    )
    llm_integration_parser.add_argument(
        "--query",
        help="Query to run (for query operation)",
    )
    llm_integration_parser.add_argument(
        "--index-cid",
        help="CID of the index to use (for query operation)",
    )
    llm_integration_parser.add_argument(
        "--options",
        help="JSON string of additional options",
    )
    llm_integration_parser.set_defaults(func=lambda api, args, kwargs: api.llm_integration(
        args.operation,
        framework=args.framework,
        content_cid=args.content_cid,
        query=args.query,
        index_cid=args.index_cid,
        options=json.loads(args.options) if args.options else None,
        **kwargs
    ))
    
    # AI model visualization
    visualization_parser = aiml_subparsers.add_parser(
        "visualize",
        help="AI/ML visualization operations",
    )
    visualization_parser.add_argument(
        "--data-cid",
        required=True,
        help="CID of data to visualize",
    )
    visualization_parser.add_argument(
        "--type",
        choices=["embedding", "training", "metrics", "similarity"],
        required=True,
        help="Type of visualization to generate",
    )
    visualization_parser.add_argument(
        "--output",
        help="File path to save visualization",
    )
    visualization_parser.add_argument(
        "--parameters",
        help="JSON string of visualization parameters",
    )
    visualization_parser.set_defaults(func=lambda api, args, kwargs: api.generate_visualization(
        args.data_cid,
        visualization_type=args.type,
        output=args.output,
        parameters=json.loads(args.parameters) if args.parameters else None,
        **kwargs
    ))
    
    # Metrics collection
    metrics_parser = aiml_subparsers.add_parser(
        "metrics",
        help="AI/ML metrics collection operations",
    )
    metrics_parser.add_argument(
        "--operation",
        choices=["start", "stop", "get", "export"],
        required=True,
        help="Operation to perform",
    )
    metrics_parser.add_argument(
        "--session-id",
        help="Session ID for metrics (required for stop/get/export operations)",
    )
    metrics_parser.add_argument(
        "--metrics",
        help="JSON array of metrics to collect (for start operation)",
    )
    metrics_parser.add_argument(
        "--output",
        help="File path to export metrics to (for export operation)",
    )
    metrics_parser.set_defaults(func=lambda api, args, kwargs: api.ai_ml_metrics(
        args.operation,
        session_id=args.session_id,
        metrics=json.loads(args.metrics) if args.metrics else None,
        output=args.output,
        **kwargs
    ))
    
    # Version command
    version_parser = subparsers.add_parser(
        "version",
        help="Show version information",
    )
    version_parser.set_defaults(func=handle_version_command) # Use a dedicated handler

    # Parse args
    # Use parse_known_args to allow flexibility if needed later, though not strictly required now
    parsed_args, unknown = parser.parse_known_args(args)

    # Check for unknown args if necessary (optional)
    # if unknown:
    #     logger.warning(f"Unrecognized arguments: {unknown}")

    return parsed_args


def handle_version_command(api, args, kwargs):
    """
    Handle the 'version' command to show version information.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Version information as a dictionary
    """
    # Get version information
    version_info = {
        "ipfs_kit_py": getattr(api, "version", "unknown"),
        "ipfs_daemon": "unknown",
    }
    
    # Try to get IPFS daemon version if available
    try:
        if hasattr(api, "ipfs") and hasattr(api.ipfs, "ipfs_version"):
            daemon_version = api.ipfs.ipfs_version()
            if isinstance(daemon_version, dict) and "version" in daemon_version:
                version_info["ipfs_daemon"] = daemon_version["version"]
            else:
                version_info["ipfs_daemon"] = str(daemon_version)
    except Exception as e:
        version_info["ipfs_daemon_error"] = str(e)
    
    return version_info

def handle_get_command(api, args, kwargs):
    """
    Handle the 'get' command with output file support.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Command result or content
    """
    # Extract timeout from kwargs or use default
    timeout = kwargs.pop('timeout', 30)
    
    # Get the content from IPFS
    content = api.get(args.cid, timeout=timeout, **kwargs)
    
    # If output file is specified, save content to file
    if hasattr(args, 'output') and args.output:
        # Handle both binary and string content
        if isinstance(content, str):
            with open(args.output, 'w') as f:
                f.write(content)
        else:
            with open(args.output, 'wb') as f:
                f.write(content)
        
        # Return success message instead of content
        return {
            "success": True,
            "message": f"Content saved to {args.output}",
            "size": len(content)
        }
    
    # If no output file, return content directly
    return content


def format_output(result: Any, output_format: str, no_color: bool = False) -> str:
    """
    Format output according to specified format.

    Args:
        result: Result to format
        output_format: Output format (text, json, yaml)
        no_color: Whether to disable colored output

    Returns:
        Formatted output
    """
    if output_format == "json":
        return json.dumps(result, indent=2)
    elif output_format == "yaml":
        return yaml.dump(result, default_flow_style=False)
    else:  # text format
        if isinstance(result, dict):
            formatted = []
            for key, value in result.items():
                if isinstance(value, dict):
                    formatted.append(f"{key}:")
                    for k, v in value.items():
                        formatted.append(f"  {k}: {v}")
                elif isinstance(value, list):
                    formatted.append(f"{key}:")
                    for item in value:
                        formatted.append(f"  - {item}")
                else:
                    formatted.append(f"{key}: {value}")
            formatted_str = "\n".join(formatted)
            # Add color for text output if enabled
            # Example: return colorize(formatted_str, "GREEN") if result.get("success", True) else colorize(formatted_str, "RED")
            return formatted_str
        elif isinstance(result, list):
            # Simple list formatting
            return "\n".join([str(item) for item in result])
        else:
            # Default string conversion
            return str(result)


def parse_kwargs(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Parse command-specific keyword arguments from command-line arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        Dictionary of keyword arguments
    """
    kwargs = {}

    # Process --param arguments if available
    if hasattr(args, 'param'):
        for param in args.param:
            try:
                kwargs.update(parse_key_value(param))
            except ValueError as e:
                logger.warning(f"Skipping invalid parameter: {e}")

    # Add timeout if present in args for specific commands
    if hasattr(args, 'timeout'):
        kwargs['timeout'] = args.timeout
    
    # Handle command-specific timeouts (e.g., timeout_get for get command)
    # Only apply command-specific timeouts if not already provided via --param
    if hasattr(args, 'command') and 'timeout' not in kwargs:
        timeout_attr = f'timeout_{args.command}'
        if hasattr(args, timeout_attr):
            kwargs['timeout'] = getattr(args, timeout_attr)

    # Merge command-specific args from the namespace into kwargs,
    # but only if the key wasn't already provided via --param.
    args_dict = vars(args)
    for key, value in args_dict.items():
        # Skip global args, the command itself, and the function handler
        # Also skip timeout attributes as they're handled separately
        if key not in ['config', 'verbose', 'param', 'format', 'no_color', 'command', 'func'] and not key.startswith('timeout_'):
            # If the arg has a value and wasn't set by --param, add it.
            if value is not None and key not in kwargs:
                kwargs[key] = value
            # Handle boolean flags specifically (like --pin, --recursive)
            # Try to access parser.get_default, but handle case where it's not available in tests
            try:
                if 'parser' in globals() and isinstance(getattr(parser.get_default(key), 'action', None), argparse.BooleanOptionalAction):
                    if value is not None and key not in kwargs:
                        kwargs[key] = value
            except (AttributeError, KeyError):
                # In tests, parser might not be available - just add the value if it's a boolean
                if isinstance(value, bool) and key not in kwargs:
                    kwargs[key] = value

    # Clean up kwargs that might have None values if not specified and not overridden by --param
    # This prevents passing None explicitly to the API methods unless intended
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    return kwargs


def run_command(args: argparse.Namespace) -> Any:
    """
    Run the specified command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Command result
    """
    # Create API client - moved to main() to handle initialization errors earlier
    # client = IPFSSimpleAPI(config_path=args.config)

    # Parse command-specific parameters - now handled within main() using parse_kwargs

    # Handle WAL commands if available - moved to main()

    # Execute command - logic moved to main() using args.func
    # ... (removed command execution logic from here) ...
    pass # Placeholder, actual execution happens in main()


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code
    """
    args = parse_args()

    # Set up logging level based on verbosity
    log_level = logging.DEBUG if args.verbose else logging.INFO
    # Use a more standard logging format
    logging.basicConfig(level=log_level, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    logger.debug(f"Parsed arguments: {args}")

    # Disable color if requested
    global _enable_color
    if args.no_color:
        _enable_color = False
        # Disable rich console if no_color is set
        # global HAS_RICH # Assuming HAS_RICH is defined elsewhere
        # HAS_RICH = False # This might need adjustment based on how rich is used

    # Initialize API with config if provided
    try:
        ipfs_api = IPFSSimpleAPI(config_path=args.config)
        logger.debug("IPFSSimpleAPI initialized successfully.")
    except Exception as e:
        print(colorize(f"Error initializing IPFS API: {e}", "RED"), file=sys.stderr)
        if args.verbose:
             import traceback
             traceback.print_exc()
        return 1

    # Execute the command function associated with the subparser
    if hasattr(args, 'func'):
        try:
            kwargs = parse_kwargs(args) # Parse --param arguments
            logger.debug(f"Executing command '{args.command}' with args: {vars(args)} and kwargs: {kwargs}")
            result = args.func(ipfs_api, args, kwargs) # Call the handler

            # Check if result indicates failure (common pattern is dict with success=False)
            is_error = isinstance(result, dict) and not result.get("success", True)

            # Format and print result unless it's None
            if result is not None:
                 # Use the updated format_output function
                 output_str = format_output(result, args.format, args.no_color)
                 print(output_str)
            elif not is_error:
                 logger.debug("Command executed successfully but returned no output.")


            return 1 if is_error else 0 # Return 1 on error, 0 on success

        except IPFSValidationError as e: # Catch specific validation errors
             print(colorize(f"Validation Error: {e}", "YELLOW"), file=sys.stderr)
             return 1
        except IPFSError as e: # Catch specific IPFS errors
             print(colorize(f"IPFS Error: {e}", "RED"), file=sys.stderr)
             return 1
        except Exception as e: # Catch unexpected errors
            print(colorize(f"Unexpected Error executing command '{args.command}': {e}", "RED"), file=sys.stderr)
            if args.verbose:
                 import traceback
                 traceback.print_exc()
            return 1
    else:
         # This case should be handled by argparse 'required=True'
         print(colorize("Error: No command specified. Use --help for usage information.", "RED"), file=sys.stderr)
         # parser.print_help() # Argparse should handle this
         return 1


if __name__ == "__main__":
    sys.exit(main())

# Parallel Query Execution commands
def add_parallel_query_commands(subparsers):
    """Add commands for parallel query execution."""
    query_parser = subparsers.add_parser(
        "query",
        help="Parallel query execution operations"
    )
    query_subparsers = query_parser.add_subparsers(dest="query_command", help="Query command", required=True)

    # Execute query command
    execute_parser = query_subparsers.add_parser(
        "execute",
        help="Execute a parallel query"
    )
    execute_parser.add_argument(
        "--predicates",
        required=True,
        help="JSON-formatted predicates array"
    )
    execute_parser.add_argument(
        "--projection",
        help="Comma-separated list of columns to return"
    )
    execute_parser.add_argument(
        "--aggregations",
        help="JSON-formatted aggregations array"
    )
    execute_parser.add_argument(
        "--group-by",
        help="Comma-separated list of columns to group by"
    )
    execute_parser.add_argument(
        "--order-by",
        help="Comma-separated list of column:direction pairs"
    )
    execute_parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of rows to return"
    )
    execute_parser.set_defaults(func=lambda api, args, kwargs: api.execute_parallel_query(
        predicates=json.loads(args.predicates),
        projection=args.projection.split(",") if args.projection else None,
        aggregations=json.loads(args.aggregations) if args.aggregations else None,
        group_by=args.group_by.split(",") if args.group_by else None,
        order_by=[tuple(pair.split(":")) for pair in args.order_by.split(",")] if args.order_by else None,
        limit=args.limit,
        **kwargs
    ))

    # Query stats command
    stats_parser = query_subparsers.add_parser(
        "stats",
        help="Get query execution statistics"
    )
    stats_parser.add_argument(
        "--query-id",
        help="Get statistics for a specific query"
    )
    stats_parser.set_defaults(func=lambda api, args, kwargs: api.get_query_statistics(
        query_id=args.query_id,
        **kwargs
    ))

    # Clear query cache command
    clear_cache_parser = query_subparsers.add_parser(
        "clear-cache",
        help="Clear the query cache"
    )
    clear_cache_parser.set_defaults(func=lambda api, args, kwargs: api.clear_query_cache(**kwargs))

    # Create query plan command
    plan_parser = query_subparsers.add_parser(
        "create-plan",
        help="Create a query execution plan without executing"
    )
    plan_parser.add_argument(
        "--predicates",
        required=True,
        help="JSON-formatted predicates array"
    )
    plan_parser.add_argument(
        "--projection",
        help="Comma-separated list of columns to return"
    )
    plan_parser.add_argument(
        "--aggregations",
        help="JSON-formatted aggregations array"
    )
    plan_parser.add_argument(
        "--group-by",
        help="Comma-separated list of columns to group by"
    )
    plan_parser.add_argument(
        "--order-by",
        help="Comma-separated list of column:direction pairs"
    )
    plan_parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of rows to return"
    )
    plan_parser.set_defaults(func=lambda api, args, kwargs: api.create_query_plan(
        predicates=json.loads(args.predicates),
        projection=args.projection.split(",") if args.projection else None,
        aggregations=json.loads(args.aggregations) if args.aggregations else None,
        group_by=args.group_by.split(",") if args.group_by else None,
        order_by=[tuple(pair.split(":")) for pair in args.order_by.split(",")] if args.order_by else None,
        limit=args.limit,
        **kwargs
    ))

# Unified Dashboard commands
def add_dashboard_commands(subparsers):
    """Add commands for unified dashboard operations."""
    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Unified dashboard operations"
    )
    dashboard_subparsers = dashboard_parser.add_subparsers(dest="dashboard_command", help="Dashboard command", required=True)

    # Start dashboard command
    dashboard_start_parser = dashboard_subparsers.add_parser(
        "start",
        help="Start the unified dashboard"
    )
    dashboard_start_parser.add_argument(
        "--port",
        type=int,
        default=8050,
        help="Port to run the dashboard on"
    )
    dashboard_start_parser.add_argument(
        "--components",
        help="Comma-separated list of components to include"
    )
    dashboard_start_parser.set_defaults(func=lambda api, args, kwargs: api.start_unified_dashboard(
        port=args.port,
        components=args.components.split(",") if args.components else None,
        **kwargs
    ))

    # Stop dashboard command
    dashboard_stop_parser = dashboard_subparsers.add_parser(
        "stop",
        help="Stop the unified dashboard"
    )
    dashboard_stop_parser.set_defaults(func=lambda api, args, kwargs: api.stop_unified_dashboard(**kwargs))

    # Dashboard status command
    dashboard_status_parser = dashboard_subparsers.add_parser(
        "status",
        help="Get dashboard status"
    )
    dashboard_status_parser.set_defaults(func=lambda api, args, kwargs: api.get_dashboard_status(**kwargs))

    # Dashboard configure command
    dashboard_configure_parser = dashboard_subparsers.add_parser(
        "configure",
        help="Configure dashboard settings"
    )
    dashboard_configure_parser.add_argument(
        "--config",
        help="Path to dashboard configuration file"
    )
    dashboard_configure_parser.set_defaults(func=lambda api, args, kwargs: api.configure_dashboard(
        config_file=args.config,
        **kwargs
    ))

# Schema/Column Optimization commands
def add_schema_commands(subparsers):
    """Add commands for schema and column optimization."""
    schema_parser = subparsers.add_parser(
        "schema",
        help="Schema and column optimization operations"
    )
    schema_subparsers = schema_parser.add_subparsers(dest="schema_command", help="Schema command", required=True)

    # Optimize schema command
    schema_optimize_parser = schema_subparsers.add_parser(
        "optimize",
        help="Optimize schema for better performance"
    )
    schema_optimize_parser.add_argument(
        "--path",
        required=True,
        help="Path to data directory or file"
    )
    schema_optimize_parser.add_argument(
        "--strategy",
        choices=["column_reordering", "type_optimization", "compression", "encoding", "auto"],
        default="auto",
        help="Optimization strategy"
    )
    schema_optimize_parser.add_argument(
        "--access-pattern",
        help="JSON-formatted access pattern description"
    )
    schema_optimize_parser.set_defaults(func=lambda api, args, kwargs: api.optimize_schema(
        path=args.path,
        strategy=args.strategy,
        access_pattern=json.loads(args.access_pattern) if args.access_pattern else None,
        **kwargs
    ))

    # Analyze schema command
    schema_analyze_parser = schema_subparsers.add_parser(
        "analyze",
        help="Analyze schema and generate recommendations"
    )
    schema_analyze_parser.add_argument(
        "--path",
        required=True,
        help="Path to data directory or file"
    )
    schema_analyze_parser.add_argument(
        "--output",
        help="Output file for recommendations"
    )
    schema_analyze_parser.set_defaults(func=lambda api, args, kwargs: api.analyze_schema(
        path=args.path,
        output=args.output,
        **kwargs
    ))

    # Apply schema recommendations command
    schema_apply_parser = schema_subparsers.add_parser(
        "apply",
        help="Apply schema optimization recommendations"
    )
    schema_apply_parser.add_argument(
        "--recommendations",
        required=True,
        help="Path to recommendations file"
    )
    schema_apply_parser.add_argument(
        "--path",
        required=True,
        help="Path to data directory or file"
    )
    schema_apply_parser.set_defaults(func=lambda api, args, kwargs: api.apply_schema_recommendations(
        recommendations=args.recommendations,
        path=args.path,
        **kwargs
    ))
def handle_version_command(api, args, kwargs):
    """
    Handle the 'version' command with platform information.
    
    Args:
        api: IPFS API instance
        args: Command line arguments
        kwargs: Additional keyword arguments
        
    Returns:
        Dictionary with version information
    """
    # Get package version
    try:
        package_version = importlib.metadata.version("ipfs_kit_py")
    except importlib.metadata.PackageNotFoundError:
        package_version = "unknown (development mode)"
    
    # Get Python version
    python_version = f"{platform.python_version()}"
    
    # Get platform information
    platform_info = f"{platform.system()} {platform.release()}"
    
    # Try to get IPFS daemon version (this might fail if daemon is not running)
    try:
        ipfs_version = api.ipfs.ipfs_version()["Version"]
    except Exception:
        ipfs_version = "unknown (daemon not running)"
    
    # Component availability
    components = {}
    if WAL_CLI_AVAILABLE:
        components["wal"] = True
    if FS_JOURNAL_CLI_AVAILABLE:
        components["filesystem_journal"] = True
    if hasattr(api, "check_webrtc_dependencies"):
        try:
            webrtc_available = api.check_webrtc_dependencies().get("available", False)
            components["webrtc"] = webrtc_available
        except Exception:
            components["webrtc"] = False
    
    # Return version information
    return {
        "ipfs_kit_py_version": package_version,
        "python_version": python_version,
        "platform": platform_info,
        "ipfs_daemon_version": ipfs_version,
        "components": components
    }