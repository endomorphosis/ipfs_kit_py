"""
P2P Workflow CLI Integration

This module provides CLI command registration and handlers for P2P workflow operations.
"""

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def register_p2p_workflow_commands(subparsers):
    """
    Register P2P workflow commands with the CLI argument parser.
    
    Args:
        subparsers: The subparsers object from argparse to add commands to
    """
    # Main P2P workflow command group
    p2p_parser = subparsers.add_parser(
        "p2p-workflow",
        help="P2P workflow scheduling operations",
        aliases=["p2p", "workflow"]
    )
    p2p_subparsers = p2p_parser.add_subparsers(
        dest="p2p_command",
        help="P2P workflow command",
        required=True
    )
    
    # Status command
    status_parser = p2p_subparsers.add_parser(
        "status",
        help="Get P2P workflow scheduler status"
    )
    status_parser.set_defaults(func=handle_p2p_status)
    
    # Submit task command
    submit_parser = p2p_subparsers.add_parser(
        "submit",
        help="Submit a task to the P2P scheduler"
    )
    submit_parser.add_argument(
        "task_id",
        help="Unique task identifier"
    )
    submit_parser.add_argument(
        "workflow_id",
        help="Workflow this task belongs to"
    )
    submit_parser.add_argument(
        "name",
        help="Human-readable task name"
    )
    submit_parser.add_argument(
        "--tags",
        "-t",
        nargs="+",
        default=[],
        help="Task tags (e.g., p2p-only, code-generation, web-scraping)"
    )
    submit_parser.add_argument(
        "--priority",
        "-p",
        type=int,
        default=5,
        help="Task priority (1-10, higher = more important)"
    )
    submit_parser.set_defaults(func=handle_p2p_submit)
    
    # Get next task command
    next_task_parser = p2p_subparsers.add_parser(
        "get-next",
        help="Get the next task assigned to this peer"
    )
    next_task_parser.set_defaults(func=handle_p2p_get_next)
    
    # Mark task complete command
    complete_parser = p2p_subparsers.add_parser(
        "mark-complete",
        help="Mark a task as completed",
        aliases=["complete", "done"]
    )
    complete_parser.add_argument(
        "task_id",
        help="Task identifier to mark as complete"
    )
    complete_parser.set_defaults(func=handle_p2p_mark_complete)
    
    # Check workflow tags command
    check_tags_parser = p2p_subparsers.add_parser(
        "check-tags",
        help="Check if workflow tags indicate P2P execution"
    )
    check_tags_parser.add_argument(
        "tags",
        nargs="+",
        help="Workflow tags to check"
    )
    check_tags_parser.set_defaults(func=handle_p2p_check_tags)
    
    # Get merkle clock command
    clock_parser = p2p_subparsers.add_parser(
        "get-clock",
        help="Get this peer's merkle clock state",
        aliases=["clock"]
    )
    clock_parser.set_defaults(func=handle_p2p_get_clock)
    
    # Update peer state command
    update_peer_parser = p2p_subparsers.add_parser(
        "update-peer",
        help="Update state for another peer"
    )
    update_peer_parser.add_argument(
        "peer_id",
        help="Peer identifier"
    )
    update_peer_parser.add_argument(
        "clock_data",
        help="Merkle clock data as JSON string"
    )
    update_peer_parser.set_defaults(func=handle_p2p_update_peer)
    
    logger.info("P2P workflow commands registered")


def handle_p2p_status(api, args, kwargs) -> Dict[str, Any]:
    """
    Handle the p2p-workflow status command.
    
    Args:
        api: The IPFS API instance
        args: Parsed command-line arguments
        kwargs: Additional keyword arguments
    
    Returns:
        Status information dictionary
    """
    try:
        # Import the controller
        from .mcp.controllers.p2p_workflow_controller import P2PWorkflowController
        
        # Create controller instance
        controller = P2PWorkflowController()
        
        # Create a simple request object
        class Request:
            pass
        
        request = Request()
        
        # Get status
        result = controller.get_status(request)
        return result
        
    except ImportError as e:
        logger.error(f"P2P workflow scheduler not available: {e}")
        return {
            "success": False,
            "message": f"P2P workflow scheduler not available: {e}"
        }
    except Exception as e:
        logger.error(f"Error getting P2P status: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


def handle_p2p_submit(api, args, kwargs) -> Dict[str, Any]:
    """
    Handle the p2p-workflow submit command.
    
    Args:
        api: The IPFS API instance
        args: Parsed command-line arguments
        kwargs: Additional keyword arguments
    
    Returns:
        Submission result dictionary
    """
    try:
        from .mcp.controllers.p2p_workflow_controller import P2PWorkflowController
        
        controller = P2PWorkflowController()
        
        # Create request object with task data
        class Request:
            def __init__(self, task_id, workflow_id, name, tags, priority):
                self.task_id = task_id
                self.workflow_id = workflow_id
                self.name = name
                self.tags = tags
                self.priority = priority
        
        request = Request(
            task_id=args.task_id,
            workflow_id=args.workflow_id,
            name=args.name,
            tags=args.tags,
            priority=args.priority
        )
        
        result = controller.submit_task(request)
        return result
        
    except ImportError as e:
        logger.error(f"P2P workflow scheduler not available: {e}")
        return {
            "success": False,
            "message": f"P2P workflow scheduler not available: {e}"
        }
    except Exception as e:
        logger.error(f"Error submitting task: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


def handle_p2p_get_next(api, args, kwargs) -> Dict[str, Any]:
    """
    Handle the p2p-workflow get-next command.
    
    Args:
        api: The IPFS API instance
        args: Parsed command-line arguments
        kwargs: Additional keyword arguments
    
    Returns:
        Next task dictionary
    """
    try:
        from .mcp.controllers.p2p_workflow_controller import P2PWorkflowController
        
        controller = P2PWorkflowController()
        
        class Request:
            pass
        
        request = Request()
        
        result = controller.get_next_task(request)
        return result
        
    except ImportError as e:
        logger.error(f"P2P workflow scheduler not available: {e}")
        return {
            "success": False,
            "message": f"P2P workflow scheduler not available: {e}"
        }
    except Exception as e:
        logger.error(f"Error getting next task: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


def handle_p2p_mark_complete(api, args, kwargs) -> Dict[str, Any]:
    """
    Handle the p2p-workflow mark-complete command.
    
    Args:
        api: The IPFS API instance
        args: Parsed command-line arguments
        kwargs: Additional keyword arguments
    
    Returns:
        Completion result dictionary
    """
    try:
        from .mcp.controllers.p2p_workflow_controller import P2PWorkflowController
        
        controller = P2PWorkflowController()
        
        class Request:
            def __init__(self, task_id):
                self.task_id = task_id
        
        request = Request(task_id=args.task_id)
        
        result = controller.mark_task_complete(request)
        return result
        
    except ImportError as e:
        logger.error(f"P2P workflow scheduler not available: {e}")
        return {
            "success": False,
            "message": f"P2P workflow scheduler not available: {e}"
        }
    except Exception as e:
        logger.error(f"Error marking task complete: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


def handle_p2p_check_tags(api, args, kwargs) -> Dict[str, Any]:
    """
    Handle the p2p-workflow check-tags command.
    
    Args:
        api: The IPFS API instance
        args: Parsed command-line arguments
        kwargs: Additional keyword arguments
    
    Returns:
        Tag check result dictionary
    """
    try:
        from .mcp.controllers.p2p_workflow_controller import P2PWorkflowController
        
        controller = P2PWorkflowController()
        
        class Request:
            def __init__(self, tags):
                self.tags = tags
        
        request = Request(tags=args.tags)
        
        result = controller.check_workflow_tags(request)
        return result
        
    except ImportError as e:
        logger.error(f"P2P workflow scheduler not available: {e}")
        return {
            "success": False,
            "message": f"P2P workflow scheduler not available: {e}"
        }
    except Exception as e:
        logger.error(f"Error checking tags: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


def handle_p2p_get_clock(api, args, kwargs) -> Dict[str, Any]:
    """
    Handle the p2p-workflow get-clock command.
    
    Args:
        api: The IPFS API instance
        args: Parsed command-line arguments
        kwargs: Additional keyword arguments
    
    Returns:
        Merkle clock data dictionary
    """
    try:
        from .mcp.controllers.p2p_workflow_controller import P2PWorkflowController
        
        controller = P2PWorkflowController()
        
        class Request:
            pass
        
        request = Request()
        
        result = controller.get_merkle_clock(request)
        return result
        
    except ImportError as e:
        logger.error(f"P2P workflow scheduler not available: {e}")
        return {
            "success": False,
            "message": f"P2P workflow scheduler not available: {e}"
        }
    except Exception as e:
        logger.error(f"Error getting merkle clock: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }


def handle_p2p_update_peer(api, args, kwargs) -> Dict[str, Any]:
    """
    Handle the p2p-workflow update-peer command.
    
    Args:
        api: The IPFS API instance
        args: Parsed command-line arguments
        kwargs: Additional keyword arguments
    
    Returns:
        Update result dictionary
    """
    try:
        from .mcp.controllers.p2p_workflow_controller import P2PWorkflowController
        
        controller = P2PWorkflowController()
        
        # Parse clock data from JSON string
        try:
            clock_data = json.loads(args.clock_data)
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "message": f"Invalid JSON for clock_data: {e}"
            }
        
        class Request:
            def __init__(self, peer_id, clock_data):
                self.peer_id = peer_id
                self.clock_data = clock_data
        
        request = Request(peer_id=args.peer_id, clock_data=clock_data)
        
        result = controller.update_peer_state(request)
        return result
        
    except ImportError as e:
        logger.error(f"P2P workflow scheduler not available: {e}")
        return {
            "success": False,
            "message": f"P2P workflow scheduler not available: {e}"
        }
    except Exception as e:
        logger.error(f"Error updating peer state: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }
