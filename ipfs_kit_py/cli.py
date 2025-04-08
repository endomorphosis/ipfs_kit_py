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
        "check-deps",
        help="Check WebRTC dependencies status",
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
    webrtc_stream_parser.set_defaults(func=lambda api, args, kwargs: api.start_webrtc_stream(**kwargs))
    
    # WebRTC benchmark
    webrtc_benchmark_parser = webrtc_subparsers.add_parser(
        "benchmark",
        help="Run WebRTC streaming benchmark",
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
    webrtc_benchmark_parser.set_defaults(func=lambda api, args, kwargs: api.run_webrtc_benchmark(**kwargs))
    
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
    get_fs_parser.set_defaults(func=lambda api, args, kwargs: {
        "success": True, 
        "message": "Filesystem interface created",
        "filesystem_info": api.get_filesystem(**kwargs) and {"ready": True}
    })
    
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
    journal_status_parser.set_defaults(func=lambda api, args, kwargs: {
        "success": True,
        "journal_status": api.get_filesystem_journal_status()
    })


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
    if hasattr(args, 'command'):
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