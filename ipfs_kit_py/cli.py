#!/usr/bin/env python3
"""
Command-line interface for IPFS Kit.

This module provides a command-line interface for interacting with IPFS Kit.
"""

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

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

# Set up logging
logger = logging.getLogger("ipfs_kit_cli")

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
    # Skip colorization if stdout is not a terminal
    if not sys.stdout.isatty():
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
    Parse a key=value string into a dictionary.

    Args:
        value: Key-value string in format key=value

    Returns:
        Dictionary with parsed key-value pair
    """
    if "=" not in value:
        raise ValueError(f"Invalid key-value format: {value}. Expected format: key=value")

    key, val = value.split("=", 1)

    # Try to parse as JSON if possible
    try:
        val = json.loads(val)
    except json.JSONDecodeError:
        # Keep as string if not valid JSON
        pass

    return {key: val}


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
        help="Enable verbose output",
    )
    parser.add_argument(
        "--param",
        "-p",
        action="append",
        help="Additional parameter in format key=value (can be used multiple times)",
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

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Register WAL commands if available
    if WAL_CLI_AVAILABLE:
        register_wal_commands(subparsers)

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
        help="Chunking algorithm",
        default="size-262144",
    )
    add_parser.add_argument(
        "--hash",
        help="Hash algorithm",
        default="sha2-256",
    )

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
    )

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
        help="IPNS record TTL",
    )

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
    )

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
    )

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

    # Exists command
    exists_parser = subparsers.add_parser(
        "exists",
        help="Check if path exists in IPFS",
    )
    exists_parser.add_argument(
        "path",
        help="IPFS path or CID",
    )

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

    # Version command
    version_parser = subparsers.add_parser(
        "version",
        help="Show version information",
    )

    return parser.parse_args(args)


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
            # Format dictionary as key-value pairs
            lines = []
            for key, value in result.items():
                key_str = key
                if not no_color:
                    key_str = colorize(key, "BOLD")
                lines.append(f"{key_str}: {value}")
            return "\n".join(lines)
        elif isinstance(result, list):
            # Format list as numbered items
            lines = []
            for i, item in enumerate(result):
                prefix = f"{i+1}. "
                if not no_color:
                    prefix = colorize(prefix, "BOLD")
                if isinstance(item, dict):
                    # Handle dictionary items
                    item_lines = []
                    for key, value in item.items():
                        key_str = key
                        if not no_color:
                            key_str = colorize(key, "BOLD")
                        item_lines.append(f"  {key_str}: {value}")
                    lines.append(f"{prefix}\n" + "\n".join(item_lines))
                else:
                    lines.append(f"{prefix}{item}")
            return "\n".join(lines)
        else:
            # Format other types as string
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

    # Add command-specific arguments
    if args.command == "add":
        kwargs.update(
            {
                "pin": args.pin,
                "wrap_with_directory": args.wrap_with_directory,
                "chunker": args.chunker,
                "hash": args.hash,
            }
        )
    elif args.command == "get":
        kwargs.update(
            {
                "timeout": args.timeout,
            }
        )
    elif args.command == "pin":
        kwargs.update(
            {
                "recursive": args.recursive,
            }
        )
    elif args.command == "unpin":
        kwargs.update(
            {
                "recursive": args.recursive,
            }
        )
    elif args.command == "list-pins":
        kwargs.update(
            {
                "type": args.type,
                "quiet": args.quiet,
            }
        )
    elif args.command == "publish":
        kwargs.update(
            {
                "lifetime": args.lifetime,
                "ttl": args.ttl,
            }
        )
    elif args.command == "resolve":
        kwargs.update(
            {
                "recursive": args.recursive,
                "timeout": args.timeout,
            }
        )
    elif args.command == "connect":
        kwargs.update(
            {
                "timeout": args.timeout,
            }
        )
    elif args.command == "peers":
        kwargs.update(
            {
                "verbose": args.verbose,
                "latency": args.latency,
                "direction": args.direction,
            }
        )
    elif args.command == "ls":
        kwargs.update(
            {
                "detail": args.detail,
            }
        )

    # Add parameters from --param
    for param in args.param:
        try:
            kwargs.update(parse_key_value(param))
        except ValueError as e:
            logger.warning(f"Skipping invalid parameter: {e}")

    return kwargs


def run_command(args: argparse.Namespace) -> Any:
    """
    Run the specified command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Command result
    """
    # Create API client
    client = IPFSSimpleAPI(
        config_path=args.config,
    )

    # Parse command-specific parameters
    kwargs = parse_kwargs(args)

    # Handle WAL commands if available
    if WAL_CLI_AVAILABLE and args.command == "wal":
        return handle_wal_command(client, args)

    # Execute command
    if args.command == "add":
        # Add content to IPFS
        result = client.add(args.content, **kwargs)

        # Ensure result is a dictionary for CLI output formatting
        if not isinstance(result, dict):
            result = {"result": result}

        # Format the output to match expected format in tests
        if "cid" in result and "name" in result:
            result["Added"] = f"{result['name']} ({result['cid']})"

        return result
    elif args.command == "get":
        if not validate_cid(args.cid):
            raise IPFSValidationError(f"Invalid CID: {args.cid}")

        content = client.get(args.cid, **kwargs)

        # Ensure content is bytes
        if not isinstance(content, bytes):
            if isinstance(content, dict) and "data" in content:
                content = content["data"]  # Extract data field if it's a dict
            else:
                # Try to convert to bytes
                try:
                    content = str(content).encode("utf-8")
                except Exception:
                    raise IPFSError(f"Unable to process content returned from API: {type(content)}")

        # Save to file if output path is provided
        if args.output:
            with open(args.output, "wb") as f:
                f.write(content)
            return {"success": True, "message": f"Content saved to {args.output}"}
        else:
            # Return content as string (if it's UTF-8 decodable)
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                return {"success": True, "message": "Binary content (not displayed)"}
    elif args.command == "pin":
        if not validate_cid(args.cid):
            raise IPFSValidationError(f"Invalid CID: {args.cid}")

        return client.pin(args.cid, **kwargs)
    elif args.command == "unpin":
        if not validate_cid(args.cid):
            raise IPFSValidationError(f"Invalid CID: {args.cid}")

        return client.unpin(args.cid, **kwargs)
    elif args.command == "list-pins":
        return client.list_pins(**kwargs)
    elif args.command == "publish":
        if not validate_cid(args.cid):
            raise IPFSValidationError(f"Invalid CID: {args.cid}")

        return client.publish(args.cid, key=args.key, **kwargs)
    elif args.command == "resolve":
        return client.resolve(args.name, **kwargs)
    elif args.command == "connect":
        return client.connect(args.peer, **kwargs)
    elif args.command == "peers":
        return client.peers(**kwargs)
    elif args.command == "exists":
        return {"exists": client.exists(args.path, **kwargs)}
    elif args.command == "ls":
        return client.ls(args.path, **kwargs)
    elif args.command == "generate-sdk":
        return client.generate_sdk(args.language, args.output_dir)
    elif args.command == "version":
        import pkg_resources

        version = pkg_resources.get_distribution("ipfs_kit_py").version
        return {
            "version": version,
            "python": sys.version,
            "platform": sys.platform,
        }
    else:
        raise IPFSError(f"Unknown command: {args.command}")


def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code
    """
    try:
        # Parse arguments
        args = parse_args()

        # Set up logging
        setup_logging(args.verbose)

        # Run command if specified
        if args.command:
            result = run_command(args)

            # Format and print result
            output = format_output(result, args.format, args.no_color)
            print(output)

            return 0
        else:
            # No command specified, show help
            parse_args(["--help"])
            return 0

    except IPFSError as e:
        logger.error(str(e))
        print(colorize(f"Error: {str(e)}", "RED"), file=sys.stderr)
        return 1
    except Exception as e:
        logger.exception("Unexpected error")
        print(
            colorize(f"Unexpected error: {str(e)}", "RED"),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
