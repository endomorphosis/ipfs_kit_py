#!/usr/bin/env python3
"""
Migration CLI - Command line interface for the MCP Migration Controller.

This tool provides command-line access to the Migration Controller for managing
cross-backend data migrations in the MCP system.
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("migration_cli")

try:
    from ipfs_kit_py.migration_tools.migration_controller import (
        MigrationController, 
        MigrationStatus, 
        MigrationPriority
    )
except ImportError:
    logger.error("Failed to import MigrationController. Make sure ipfs_kit_py is installed.")
    sys.exit(1)


def format_size(size_bytes: int) -> str:
    """Format byte size into human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_time(timestamp: Optional[float]) -> str:
    """Format timestamp into human-readable string."""
    if timestamp is None:
        return "N/A"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))


def format_duration(start: Optional[float], end: Optional[float]) -> str:
    """Format duration between two timestamps."""
    if start is None or end is None:
        return "N/A"
    
    duration = end - start
    if duration < 60:
        return f"{duration:.2f} seconds"
    elif duration < 3600:
        return f"{duration / 60:.2f} minutes"
    else:
        return f"{duration / 3600:.2f} hours"


def print_task_details(task: Dict[str, Any]):
    """Print detailed information about a migration task."""
    print("\n" + "=" * 60)
    print(f"Task ID: {task['id']}")
    print(f"Status: {task['status']}")
    print(f"Source: {task['source_backend']} -> Target: {task['target_backend']}")
    print(f"Content ID: {task['content_id']}")
    print(f"Policy: {task['policy_name'] or 'None'}")
    print(f"Priority: {task['priority']}")
    print(f"Created: {format_time(task['created_at'])}")
    print(f"Started: {format_time(task['started_at'])}")
    print(f"Completed: {format_time(task['completed_at'])}")
    
    if task.get('source_size'):
        print(f"Size: {format_size(task['source_size'])}")
    
    if task.get('transfer_speed'):
        print(f"Transfer Speed: {format_size(int(task['transfer_speed']))}/s")
    
    if task.get('started_at') and task.get('completed_at'):
        print(f"Duration: {format_duration(task['started_at'], task['completed_at'])}")
    
    if task.get('error'):
        print(f"Error: {task['error']}")
    
    if task.get('target_identifier'):
        print(f"Target Identifier: {task['target_identifier']}")
    
    if task.get('verification_result'):
        print(f"Verification: {task['verification_result'].get('success', False)}")
    
    print("-" * 60)
    print("Metadata:")
    for key, value in task.get('metadata', {}).items():
        print(f"  {key}: {value}")
    print("=" * 60 + "\n")


def list_tasks_cmd(controller, args):
    """Handle the list tasks command."""
    status = MigrationStatus[args.status.upper()] if args.status else None
    
    tasks = controller.list_tasks(
        status=status,
        source_backend=args.source,
        target_backend=args.target,
        policy_name=args.policy,
        limit=args.limit,
        offset=args.offset
    )
    
    if not tasks:
        print("No tasks found matching the criteria.")
        return
    
    print(f"\nFound {len(tasks)} tasks:")
    print("-" * 100)
    print(f"{'ID':<36} {'Status':<15} {'Source->Target':<25} {'Size':<10} {'Created':<20}")
    print("-" * 100)
    
    for task in tasks:
        size_str = format_size(task.get('source_size', 0)) if task.get('source_size') else "Unknown"
        source_target = f"{task['source_backend']} -> {task['target_backend']}"
        print(f"{task['id']:<36} {task['status']:<15} {source_target:<25} {size_str:<10} {format_time(task['created_at']):<20}")
    
    print("-" * 100)
    
    if args.verbose and len(tasks) > 0:
        for task in tasks:
            print_task_details(task)


def get_task_cmd(controller, args):
    """Handle the get task command."""
    task = controller.get_task(args.task_id)
    
    if not task:
        print(f"Task with ID {args.task_id} not found.")
        return
    
    print_task_details(task.to_dict())


def create_task_cmd(controller, args):
    """Handle the create task command."""
    # Parse metadata if provided
    metadata = {}
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError:
            print("Error: Metadata must be a valid JSON string.")
            return
    
    # Get priority enum
    try:
        priority = MigrationPriority[args.priority.upper()]
    except KeyError:
        print(f"Error: Invalid priority '{args.priority}'. Valid values are: LOW, NORMAL, HIGH, CRITICAL")
        return
    
    # Create the task
    task = controller.create_migration_task(
        source_backend=args.source,
        target_backend=args.target,
        content_id=args.content_id,
        policy_name=args.policy,
        priority=priority,
        metadata=metadata
    )
    
    print(f"Created migration task with ID: {task.id}")
    print_task_details(task.to_dict())


def cancel_task_cmd(controller, args):
    """Handle the cancel task command."""
    result = controller.cancel_task(args.task_id)
    
    if result:
        print(f"Successfully cancelled task {args.task_id}")
    else:
        print(f"Failed to cancel task {args.task_id}. It may not exist or is not in a cancellable state.")


def list_policies_cmd(controller, args):
    """Handle the list policies command."""
    policies = controller.list_policies()
    
    if not policies:
        print("No migration policies defined.")
        return
    
    print(f"\nFound {len(policies)} policies:")
    print("-" * 80)
    
    for policy in policies:
        name = policy['name']
        config = policy['config']
        source = config.get('source_backend', 'Unknown')
        target = config.get('target_backend', 'Unknown')
        verify = "Yes" if config.get('verification_required', True) else "No"
        retain = "Yes" if config.get('retention', True) else "No"
        
        print(f"Policy: {name}")
        print(f"  Source -> Target: {source} -> {target}")
        print(f"  Verification: {verify}, Retention: {retain}")
        
        if args.verbose:
            print(f"  Content Filters: {config.get('content_filters', {})}")
            print(f"  Cost Threshold: {config.get('cost_threshold', 'Unlimited')}")
            print(f"  Bandwidth Limit: {config.get('bandwidth_limit', 'Unlimited')}")
            print(f"  Schedule: {config.get('schedule', 'None')}")
        
        print("-" * 80)


def add_policy_cmd(controller, args):
    """Handle the add policy command."""
    # Parse config from file or JSON string
    config = {}
    
    if args.config_file:
        try:
            with open(args.config_file, 'r') as f:
                config = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error reading config file: {e}")
            return
    elif args.config:
        try:
            config = json.loads(args.config)
        except json.JSONDecodeError:
            print("Error: Config must be a valid JSON string.")
            return
    else:
        print("Error: Either --config or --config-file must be provided.")
        return
    
    # Validate minimal configuration
    if 'source_backend' not in config or 'target_backend' not in config:
        print("Error: Config must include at least 'source_backend' and 'target_backend'.")
        return
    
    # Add the policy
    policy = controller.add_policy(args.name, config)
    
    print(f"Added migration policy '{args.name}':")
    print(f"  Source -> Target: {policy.source_backend} -> {policy.target_backend}")
    print(f"  Verification: {'Yes' if policy.verification_required else 'No'}")
    print(f"  Retention: {'Yes' if policy.retention else 'No'}")


def remove_policy_cmd(controller, args):
    """Handle the remove policy command."""
    result = controller.remove_policy(args.name)
    
    if result:
        print(f"Successfully removed policy '{args.name}'")
    else:
        print(f"Failed to remove policy '{args.name}'. It may not exist.")


def apply_policy_cmd(controller, args):
    """Handle the apply policy command."""
    # Parse content list from file or JSON string
    content_list = []
    
    if args.content_file:
        try:
            with open(args.content_file, 'r') as f:
                content_list = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error reading content file: {e}")
            return
    elif args.content:
        try:
            content_list = json.loads(args.content)
        except json.JSONDecodeError:
            print("Error: Content must be a valid JSON array.")
            return
    else:
        print("Error: Either --content or --content-file must be provided.")
        return
    
    # Validate content list
    if not isinstance(content_list, list):
        print("Error: Content must be a JSON array of items.")
        return
    
    # Apply the policy
    task_ids = controller.apply_policy_to_content(args.policy, content_list)
    
    if task_ids:
        print(f"Successfully applied policy '{args.policy}' to {len(task_ids)} content items.")
        print(f"Created migration tasks: {', '.join(task_ids[:5])}" + 
              (f"... and {len(task_ids) - 5} more" if len(task_ids) > 5 else ""))
    else:
        print(f"No content items matched policy '{args.policy}' criteria or policy doesn't exist.")


def analyze_cost_cmd(controller, args):
    """Handle the analyze cost command."""
    # Parse content list from file or JSON string
    content_list = []
    
    if args.content_file:
        try:
            with open(args.content_file, 'r') as f:
                content_list = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error reading content file: {e}")
            return
    elif args.content:
        try:
            content_list = json.loads(args.content)
        except json.JSONDecodeError:
            print("Error: Content must be a valid JSON array.")
            return
    else:
        print("Error: Either --content or --content-file must be provided.")
        return
    
    # Analyze the cost
    cost_analysis = controller.analyze_migration_cost(
        args.source,
        args.target,
        content_list
    )
    
    print("\nMigration Cost Analysis:")
    print("=" * 60)
    print(f"Source Backend: {cost_analysis['source_backend']}")
    print(f"Target Backend: {cost_analysis['target_backend']}")
    print(f"Total Items: {cost_analysis['total_items']}")
    print(f"Total Size: {format_size(cost_analysis['total_size_bytes'])}")
    print(f"Total Estimated Cost: ${cost_analysis['total_cost']:.4f}")
    print(f"Average Cost Per Item: ${cost_analysis['avg_cost_per_item']:.4f}")
    print(f"Average Cost Per MB: ${cost_analysis['avg_cost_per_mb']:.4f}")
    print("=" * 60)


def get_stats_cmd(controller, args):
    """Handle the get statistics command."""
    stats = controller.get_statistics()
    
    print("\nMigration Controller Statistics:")
    print("=" * 60)
    print(f"Total Migrations: {stats['total_migrations']}")
    print(f"Successful Migrations: {stats['successful_migrations']}")
    print(f"Failed Migrations: {stats['failed_migrations']}")
    print(f"Total Data Transferred: {format_size(stats['bytes_transferred'])}")
    print(f"Pending Tasks: {stats['pending_tasks']}")
    print(f"In-Progress Tasks: {stats['in_progress_tasks']}")
    print(f"Completed Tasks: {stats['completed_tasks']}")
    print(f"Failed Tasks: {stats['failed_tasks']}")
    print(f"Number of Policies: {stats['policies']}")
    print(f"Supported Backend Pairs: {', '.join(stats['supported_backend_pairs'])}")
    
    if args.verbose:
        print("\nBackend Statistics:")
        for backend, backend_stats in stats['backend_stats'].items():
            print(f"  {backend}:")
            print(f"    Outgoing Migrations: {backend_stats.get('outgoing_migrations', 0)}")
            print(f"    Outgoing Bytes: {format_size(backend_stats.get('outgoing_bytes', 0))}")
            print(f"    Incoming Migrations: {backend_stats.get('incoming_migrations', 0)}")
            print(f"    Incoming Bytes: {format_size(backend_stats.get('incoming_bytes', 0))}")
    
    print("=" * 60)


def find_optimal_backend_cmd(controller, args):
    """Handle the find optimal backend command."""
    # Parse content metadata from JSON string
    try:
        metadata = json.loads(args.metadata)
    except json.JSONDecodeError:
        print("Error: Metadata must be a valid JSON string.")
        return
    
    # Parse available backends list
    backends = args.backends.split(",")
    
    # Find optimal backend
    optimal = controller.get_optimal_backend(metadata, backends)
    
    print(f"\nOptimal Backend Analysis for Content:")
    print("=" * 60)
    print(f"Content Size: {format_size(metadata.get('size', 0))}")
    print(f"Content Type: {metadata.get('content_type', 'Unknown')}")
    print(f"Access Frequency: {metadata.get('access_frequency', 'medium')}")
    print(f"Durability Requirement: {metadata.get('durability', 'medium')}")
    print(f"Latency Requirement: {metadata.get('latency', 'medium')}")
    print("-" * 60)
    print(f"Available Backends: {', '.join(backends)}")
    print(f"Recommended Backend: {optimal}")
    print("=" * 60)


def main():
    """Main entry point for the migration CLI."""
    parser = argparse.ArgumentParser(
        description="MCP Migration Controller CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all migration tasks
  migration_cli list-tasks
  
  # Get details of a specific task
  migration_cli get-task --task-id 123e4567-e89b-12d3-a456-426614174000
  
  # Create a new migration task
  migration_cli create-task --source ipfs --target s3 --content-id QmXYZ...
  
  # List all migration policies
  migration_cli list-policies
  
  # Get migration statistics
  migration_cli stats
        """
    )
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Global arguments
    parser.add_argument(
        "--config", 
        help="Path to configuration file",
        default=os.environ.get("MCP_CONFIG", None)
    )
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true", 
        help="Enable verbose output"
    )
    
    # List tasks command
    list_parser = subparsers.add_parser("list-tasks", help="List migration tasks")
    list_parser.add_argument("--status", help="Filter by status (e.g., PENDING, COMPLETED)")
    list_parser.add_argument("--source", help="Filter by source backend")
    list_parser.add_argument("--target", help="Filter by target backend")
    list_parser.add_argument("--policy", help="Filter by policy name")
    list_parser.add_argument("--limit", type=int, default=100, help="Maximum number of tasks to show")
    list_parser.add_argument("--offset", type=int, default=0, help="Number of tasks to skip")
    
    # Get task command
    get_parser = subparsers.add_parser("get-task", help="Get details of a specific task")
    get_parser.add_argument("--task-id", required=True, help="Task ID to retrieve")
    
    # Create task command
    create_parser = subparsers.add_parser("create-task", help="Create a new migration task")
    create_parser.add_argument("--source", required=True, help="Source backend name")
    create_parser.add_argument("--target", required=True, help="Target backend name")
    create_parser.add_argument("--content-id", required=True, help="Content ID to migrate")
    create_parser.add_argument("--policy", help="Policy name to apply")
    create_parser.add_argument("--priority", default="NORMAL", help="Task priority (LOW, NORMAL, HIGH, CRITICAL)")
    create_parser.add_argument("--metadata", help="Content metadata as JSON string")
    
    # Cancel task command
    cancel_parser = subparsers.add_parser("cancel-task", help="Cancel a pending migration task")
    cancel_parser.add_argument("--task-id", required=True, help="Task ID to cancel")
    
    # List policies command
    list_policies_parser = subparsers.add_parser("list-policies", help="List migration policies")
    
    # Add policy command
    add_policy_parser = subparsers.add_parser("add-policy", help="Add a new migration policy")
    add_policy_parser.add_argument("--name", required=True, help="Policy name")
    add_policy_parser.add_argument("--config", help="Policy configuration as JSON string")
    add_policy_parser.add_argument("--config-file", help="Path to policy configuration file")
    
    # Remove policy command
    remove_policy_parser = subparsers.add_parser("remove-policy", help="Remove a migration policy")
    remove_policy_parser.add_argument("--name", required=True, help="Policy name to remove")
    
    # Apply policy command
    apply_policy_parser = subparsers.add_parser("apply-policy", help="Apply a policy to content")
    apply_policy_parser.add_argument("--policy", required=True, help="Policy name to apply")
    apply_policy_parser.add_argument("--content", help="Content list as JSON string")
    apply_policy_parser.add_argument("--content-file", help="Path to content list file")
    
    # Analyze cost command
    analyze_cost_parser = subparsers.add_parser("analyze-cost", help="Analyze migration cost")
    analyze_cost_parser.add_argument("--source", required=True, help="Source backend name")
    analyze_cost_parser.add_argument("--target", required=True, help="Target backend name")
    analyze_cost_parser.add_argument("--content", help="Content list as JSON string")
    analyze_cost_parser.add_argument("--content-file", help="Path to content list file")
    
    # Get statistics command
    stats_parser = subparsers.add_parser("stats", help="Get migration statistics")
    
    # Find optimal backend command
    optimal_parser = subparsers.add_parser("find-optimal", help="Find optimal backend for content")
    optimal_parser.add_argument("--metadata", required=True, help="Content metadata as JSON string")
    optimal_parser.add_argument("--backends", required=True, help="Comma-separated list of available backends")
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize controller
    resources = {}
    metadata = {}
    
    if args.config:
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
                resources = config.get("resources", {})
                metadata = config.get("metadata", {})
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Warning: Could not load config file: {e}")
    
    controller = MigrationController(resources, metadata)
    
    # Execute command
    try:
        if args.command == "list-tasks":
            list_tasks_cmd(controller, args)
        elif args.command == "get-task":
            get_task_cmd(controller, args)
        elif args.command == "create-task":
            create_task_cmd(controller, args)
        elif args.command == "cancel-task":
            cancel_task_cmd(controller, args)
        elif args.command == "list-policies":
            list_policies_cmd(controller, args)
        elif args.command == "add-policy":
            add_policy_cmd(controller, args)
        elif args.command == "remove-policy":
            remove_policy_cmd(controller, args)
        elif args.command == "apply-policy":
            apply_policy_cmd(controller, args)
        elif args.command == "analyze-cost":
            analyze_cost_cmd(controller, args)
        elif args.command == "stats":
            get_stats_cmd(controller, args)
        elif args.command == "find-optimal":
            find_optimal_backend_cmd(controller, args)
    finally:
        # Clean up controller resources
        controller.cleanup()


if __name__ == "__main__":
    main()