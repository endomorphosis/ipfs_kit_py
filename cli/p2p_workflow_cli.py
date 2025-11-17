#!/usr/bin/env python3
"""
CLI for P2P Workflow Management

This module provides command-line interface tools for managing peer-to-peer
workflow execution across the IPFS network.

Usage:
    ipfs-kit p2p workflow submit <workflow_file> [options]
    ipfs-kit p2p workflow assign
    ipfs-kit p2p workflow status <workflow_id>
    ipfs-kit p2p workflow list [options]
    ipfs-kit p2p workflow update <workflow_id> <status>
    ipfs-kit p2p peer add <peer_id>
    ipfs-kit p2p peer remove <peer_id>
    ipfs-kit p2p peer list
    ipfs-kit p2p stats
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ipfs_kit_py.p2p_workflow_coordinator import (
    P2PWorkflowCoordinator,
    WorkflowStatus
)

logger = logging.getLogger(__name__)


class P2PWorkflowCLI:
    """Command-line interface for P2P workflow management."""
    
    def __init__(self):
        """Initialize the CLI."""
        self.coordinator: Optional[P2PWorkflowCoordinator] = None
        self._peer_id = None
    
    def _get_coordinator(self) -> P2PWorkflowCoordinator:
        """Get or create the workflow coordinator."""
        if self.coordinator is None:
            # Try to determine peer ID from environment or config
            import os
            peer_id = os.environ.get('P2P_PEER_ID', 'cli-peer')
            self.coordinator = P2PWorkflowCoordinator(peer_id=peer_id)
        return self.coordinator
    
    def submit_workflow(self, args: argparse.Namespace) -> int:
        """Submit a workflow for P2P execution."""
        try:
            coordinator = self._get_coordinator()
            
            workflow_id = coordinator.submit_workflow(
                workflow_file=args.workflow_file,
                name=args.name,
                inputs=json.loads(args.inputs) if args.inputs else None,
                priority=args.priority
            )
            
            print(f"✓ Workflow submitted successfully")
            print(f"  Workflow ID: {workflow_id}")
            print(f"  Status: pending")
            
            if args.json:
                print(json.dumps({
                    "success": True,
                    "workflow_id": workflow_id,
                    "status": "pending"
                }, indent=2))
            
            return 0
        
        except Exception as e:
            print(f"✗ Failed to submit workflow: {e}", file=sys.stderr)
            if args.json:
                print(json.dumps({"success": False, "error": str(e)}, indent=2))
            return 1
    
    def assign_workflows(self, args: argparse.Namespace) -> int:
        """Assign pending workflows to peers."""
        try:
            coordinator = self._get_coordinator()
            assigned = coordinator.assign_workflows()
            
            print(f"✓ Assigned {len(assigned)} workflows to peers")
            if assigned:
                print("  Workflow IDs:")
                for wid in assigned:
                    print(f"    - {wid}")
            
            if args.json:
                print(json.dumps({
                    "success": True,
                    "assigned_count": len(assigned),
                    "workflow_ids": assigned
                }, indent=2))
            
            return 0
        
        except Exception as e:
            print(f"✗ Failed to assign workflows: {e}", file=sys.stderr)
            if args.json:
                print(json.dumps({"success": False, "error": str(e)}, indent=2))
            return 1
    
    def workflow_status(self, args: argparse.Namespace) -> int:
        """Get workflow status."""
        try:
            coordinator = self._get_coordinator()
            status = coordinator.get_workflow_status(args.workflow_id)
            
            if status is None:
                print(f"✗ Workflow not found: {args.workflow_id}", file=sys.stderr)
                return 1
            
            if args.json:
                print(json.dumps(status, indent=2))
            else:
                print(f"Workflow: {status['name']}")
                print(f"  ID: {status['workflow_id']}")
                print(f"  Status: {status['status']}")
                print(f"  Priority: {status['priority']}")
                if status.get('assigned_peer'):
                    print(f"  Assigned Peer: {status['assigned_peer']}")
                if status.get('tags'):
                    print(f"  Tags: {', '.join(status['tags'])}")
                if status.get('started_at'):
                    print(f"  Started: {status['started_at']}")
                if status.get('completed_at'):
                    print(f"  Completed: {status['completed_at']}")
            
            return 0
        
        except Exception as e:
            print(f"✗ Failed to get workflow status: {e}", file=sys.stderr)
            if args.json:
                print(json.dumps({"success": False, "error": str(e)}, indent=2))
            return 1
    
    def list_workflows(self, args: argparse.Namespace) -> int:
        """List workflows."""
        try:
            coordinator = self._get_coordinator()
            
            status_filter = None
            if args.status:
                try:
                    status_filter = WorkflowStatus(args.status)
                except ValueError:
                    print(f"✗ Invalid status: {args.status}", file=sys.stderr)
                    print(f"  Valid statuses: {', '.join(s.value for s in WorkflowStatus)}")
                    return 1
            
            workflows = coordinator.list_workflows(
                status=status_filter,
                peer_id=args.peer_id
            )
            
            if args.json:
                print(json.dumps(workflows, indent=2))
            else:
                print(f"Found {len(workflows)} workflows")
                if workflows:
                    print()
                    for wf in workflows:
                        print(f"  • {wf['name']}")
                        print(f"    ID: {wf['workflow_id']}")
                        print(f"    Status: {wf['status']}")
                        print(f"    Priority: {wf['priority']}")
                        if wf.get('assigned_peer'):
                            print(f"    Peer: {wf['assigned_peer']}")
                        print()
            
            return 0
        
        except Exception as e:
            print(f"✗ Failed to list workflows: {e}", file=sys.stderr)
            if args.json:
                print(json.dumps({"success": False, "error": str(e)}, indent=2))
            return 1
    
    def update_workflow(self, args: argparse.Namespace) -> int:
        """Update workflow status."""
        try:
            coordinator = self._get_coordinator()
            
            try:
                status = WorkflowStatus(args.status)
            except ValueError:
                print(f"✗ Invalid status: {args.status}", file=sys.stderr)
                print(f"  Valid statuses: {', '.join(s.value for s in WorkflowStatus)}")
                return 1
            
            result = json.loads(args.result) if args.result else None
            
            success = coordinator.update_workflow_status(
                workflow_id=args.workflow_id,
                status=status,
                result=result,
                error=args.error
            )
            
            if success:
                print(f"✓ Workflow status updated to: {args.status}")
                if args.json:
                    print(json.dumps({"success": True, "status": args.status}, indent=2))
                return 0
            else:
                print(f"✗ Failed to update workflow status", file=sys.stderr)
                return 1
        
        except Exception as e:
            print(f"✗ Failed to update workflow: {e}", file=sys.stderr)
            if args.json:
                print(json.dumps({"success": False, "error": str(e)}, indent=2))
            return 1
    
    def add_peer(self, args: argparse.Namespace) -> int:
        """Add a peer to the network."""
        try:
            coordinator = self._get_coordinator()
            coordinator.add_peer(args.peer_id)
            
            print(f"✓ Peer added: {args.peer_id}")
            if args.json:
                print(json.dumps({"success": True, "peer_id": args.peer_id}, indent=2))
            
            return 0
        
        except Exception as e:
            print(f"✗ Failed to add peer: {e}", file=sys.stderr)
            if args.json:
                print(json.dumps({"success": False, "error": str(e)}, indent=2))
            return 1
    
    def remove_peer(self, args: argparse.Namespace) -> int:
        """Remove a peer from the network."""
        try:
            coordinator = self._get_coordinator()
            coordinator.remove_peer(args.peer_id)
            
            print(f"✓ Peer removed: {args.peer_id}")
            if args.json:
                print(json.dumps({"success": True, "peer_id": args.peer_id}, indent=2))
            
            return 0
        
        except Exception as e:
            print(f"✗ Failed to remove peer: {e}", file=sys.stderr)
            if args.json:
                print(json.dumps({"success": False, "error": str(e)}, indent=2))
            return 1
    
    def list_peers(self, args: argparse.Namespace) -> int:
        """List peers in the network."""
        try:
            coordinator = self._get_coordinator()
            peers = coordinator.peer_list
            
            if args.json:
                print(json.dumps({"peers": peers, "count": len(peers)}, indent=2))
            else:
                print(f"P2P Network Peers ({len(peers)}):")
                for peer_id in peers:
                    marker = "→" if peer_id == coordinator.peer_id else " "
                    print(f"  {marker} {peer_id}")
            
            return 0
        
        except Exception as e:
            print(f"✗ Failed to list peers: {e}", file=sys.stderr)
            if args.json:
                print(json.dumps({"success": False, "error": str(e)}, indent=2))
            return 1
    
    def show_stats(self, args: argparse.Namespace) -> int:
        """Show coordinator statistics."""
        try:
            coordinator = self._get_coordinator()
            stats = coordinator.get_stats()
            
            if args.json:
                print(json.dumps(stats, indent=2))
            else:
                print("P2P Workflow Coordinator Statistics")
                print("=" * 50)
                print(f"Peer ID: {stats['peer_id']}")
                print(f"Total Workflows: {stats['total_workflows']}")
                print(f"Queue Size: {stats['queue_size']}")
                print(f"Peer Count: {stats['peer_count']}")
                print(f"Merkle Clock Height: {stats['merkle_clock_height']}")
                print(f"My Workflows: {stats['my_workflows']}")
                
                if stats.get('status_counts'):
                    print("\nWorkflow Status Counts:")
                    for status, count in stats['status_counts'].items():
                        print(f"  {status}: {count}")
            
            return 0
        
        except Exception as e:
            print(f"✗ Failed to get stats: {e}", file=sys.stderr)
            if args.json:
                print(json.dumps({"success": False, "error": str(e)}, indent=2))
            return 1


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        description="P2P Workflow Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Global options
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output in JSON format'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Workflow commands
    workflow_parser = subparsers.add_parser('workflow', help='Workflow management')
    workflow_sub = workflow_parser.add_subparsers(dest='workflow_cmd')
    
    # Submit workflow
    submit_parser = workflow_sub.add_parser('submit', help='Submit a workflow')
    submit_parser.add_argument('workflow_file', help='Path to workflow YAML file')
    submit_parser.add_argument('--name', help='Workflow name')
    submit_parser.add_argument('--inputs', help='Workflow inputs (JSON)')
    submit_parser.add_argument('--priority', type=float, default=5.0, help='Priority (default: 5.0)')
    
    # Assign workflows
    workflow_sub.add_parser('assign', help='Assign pending workflows to peers')
    
    # Workflow status
    status_parser = workflow_sub.add_parser('status', help='Get workflow status')
    status_parser.add_argument('workflow_id', help='Workflow ID')
    
    # List workflows
    list_parser = workflow_sub.add_parser('list', help='List workflows')
    list_parser.add_argument('--status', help='Filter by status')
    list_parser.add_argument('--peer-id', help='Filter by peer ID')
    
    # Update workflow
    update_parser = workflow_sub.add_parser('update', help='Update workflow status')
    update_parser.add_argument('workflow_id', help='Workflow ID')
    update_parser.add_argument('status', help='New status')
    update_parser.add_argument('--result', help='Result data (JSON)')
    update_parser.add_argument('--error', help='Error message')
    
    # Peer commands
    peer_parser = subparsers.add_parser('peer', help='Peer management')
    peer_sub = peer_parser.add_subparsers(dest='peer_cmd')
    
    # Add peer
    add_peer_parser = peer_sub.add_parser('add', help='Add a peer')
    add_peer_parser.add_argument('peer_id', help='Peer ID')
    
    # Remove peer
    remove_peer_parser = peer_sub.add_parser('remove', help='Remove a peer')
    remove_peer_parser.add_argument('peer_id', help='Peer ID')
    
    # List peers
    peer_sub.add_parser('list', help='List peers')
    
    # Stats
    subparsers.add_parser('stats', help='Show coordinator statistics')
    
    return parser


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    cli = P2PWorkflowCLI()
    
    # Route to appropriate handler
    if args.command == 'workflow':
        if args.workflow_cmd == 'submit':
            return cli.submit_workflow(args)
        elif args.workflow_cmd == 'assign':
            return cli.assign_workflows(args)
        elif args.workflow_cmd == 'status':
            return cli.workflow_status(args)
        elif args.workflow_cmd == 'list':
            return cli.list_workflows(args)
        elif args.workflow_cmd == 'update':
            return cli.update_workflow(args)
        else:
            parser.print_help()
            return 1
    
    elif args.command == 'peer':
        if args.peer_cmd == 'add':
            return cli.add_peer(args)
        elif args.peer_cmd == 'remove':
            return cli.remove_peer(args)
        elif args.peer_cmd == 'list':
            return cli.list_peers(args)
        else:
            parser.print_help()
            return 1
    
    elif args.command == 'stats':
        return cli.show_stats(args)
    
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
