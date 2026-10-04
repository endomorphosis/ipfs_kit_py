#!/usr/bin/env python3
"""
CLI commands for the Enhanced Intelligent Daemon Manager.

This provides CLI integration for the metadata-driven daemon operations.
"""

import click
import json
import time
from datetime import datetime
from pathlib import Path


@click.group()
def daemon():
    """Enhanced intelligent daemon management commands."""
    pass


@daemon.command()
@click.option('--detach', '-d', is_flag=True, help='Run daemon in background')
@click.option('--verbose', '-v', is_flag=True, help='Verbose logging')
def start(detach, verbose):
    """Start the enhanced intelligent daemon."""
    try:
        from ipfs_kit_py.intelligent_daemon_manager import get_daemon_manager
        import logging
        
        if verbose:
            logging.basicConfig(level=logging.DEBUG)
        
        daemon_manager = get_daemon_manager()
        
        if daemon_manager.get_status()['running']:
            click.echo("✅ Daemon is already running")
            return
        
        click.echo("🚀 Starting enhanced intelligent daemon...")
        daemon_manager.start()
        
        if detach:
            click.echo("✅ Daemon started in background")
            click.echo("Use 'ipfs-kit daemon status' to check status")
            click.echo("Use 'ipfs-kit daemon stop' to stop the daemon")
        else:
            click.echo("✅ Daemon started successfully")
            click.echo("Press Ctrl+C to stop the daemon...")
            
            try:
                while daemon_manager.get_status()['running']:
                    time.sleep(1)
            except KeyboardInterrupt:
                click.echo("\n🛑 Stopping daemon...")
                daemon_manager.stop()
                click.echo("✅ Daemon stopped")
                
    except Exception as e:
        click.echo(f"❌ Error starting daemon: {e}")


@daemon.command()
def stop():
    """Stop the intelligent daemon."""
    try:
        from ipfs_kit_py.intelligent_daemon_manager import get_daemon_manager
        
        daemon_manager = get_daemon_manager()
        
        if not daemon_manager.get_status()['running']:
            click.echo("ℹ️  Daemon is not running")
            return
        
        click.echo("🛑 Stopping daemon...")
        daemon_manager.stop()
        click.echo("✅ Daemon stopped successfully")
        
    except Exception as e:
        click.echo(f"❌ Error stopping daemon: {e}")


@daemon.command()
@click.option('--json-output', '-j', is_flag=True, help='Output as JSON')
@click.option('--detailed', '-d', is_flag=True, help='Show detailed status')
def status(json_output, detailed):
    """Show daemon status and metadata insights."""
    try:
        from ipfs_kit_py.intelligent_daemon_manager import get_daemon_manager
        
        daemon_manager = get_daemon_manager()
        status_info = daemon_manager.get_status()
        
        if json_output:
            click.echo(json.dumps(status_info, indent=2, default=str))
            return
        
        # Pretty print status
        running = status_info['running']
        click.echo(f"Daemon Status: {'🟢 Running' if running else '🔴 Stopped'}")
        
        if running:
            # Thread status
            thread_status = status_info['thread_status']
            active_threads = sum(thread_status.values())
            click.echo(f"Active Threads: {active_threads}/4")
            
            for thread_name, is_active in thread_status.items():
                status_icon = "✅" if is_active else "❌"
                click.echo(f"  {status_icon} {thread_name}")
            
            # Metadata stats
            metadata_stats = status_info['metadata_driven_stats']
            click.echo("\nMetadata-Driven Statistics:")
            click.echo(f"  📁 Total Buckets: {metadata_stats['total_buckets']}")
            click.echo(f"  🔧 Total Backends: {metadata_stats['total_backends']}")
            click.echo(f"  🔄 Dirty Backends: {metadata_stats['dirty_count']}")
            click.echo(f"  ❌ Unhealthy Backends: {metadata_stats['unhealthy_count']}")
            click.echo(f"  💾 Filesystem Backends: {len(metadata_stats['filesystem_backends'])}")
            
            # Task management
            task_info = status_info['task_management']
            click.echo("\nTask Management:")
            click.echo(f"  ⚡ Active Tasks: {task_info['active_tasks']}")
            click.echo(f"  📋 Queued Tasks: {task_info['queued_tasks']}")
            click.echo(f"  ✅ Completed Tasks: {task_info['completed_tasks']}")
            
            # Backend health summary
            health_summary = status_info['backend_health_summary']
            health_pct = health_summary['health_percentage']
            click.echo(f"\nBackend Health: {health_pct:.1f}% ({health_summary['healthy_backends']}/{health_summary['total_monitored']})")
            
            if detailed:
                # Show detailed backend status
                backend_details = status_info['backend_status_details']
                if backend_details:
                    click.echo("\nDetailed Backend Status:")
                    for backend_name, details in backend_details.items():
                        health_icon = "🟢" if details['healthy'] else "🔴"
                        sync_needed = "🔄" if details['needs_sync'] else ""
                        backup_needed = "💾" if details['needs_backup'] else ""
                        
                        click.echo(f"  {health_icon} {backend_name} {sync_needed}{backup_needed}")
                        if details['error']:
                            click.echo(f"    Error: {details['error']}")
                        if details['response_time_ms']:
                            click.echo(f"    Response: {details['response_time_ms']:.1f}ms")
        
        # Show intervals
        intervals = status_info['intervals']
        click.echo(f"\nMonitoring Intervals:")
        click.echo(f"  Metadata Scan: {intervals['bucket_scan_seconds']}s")
        click.echo(f"  Dirty Check: {intervals['dirty_check_seconds']}s")
        click.echo(f"  Health Check: {intervals['health_check_seconds']}s")
        
    except Exception as e:
        click.echo(f"❌ Error getting daemon status: {e}")


@daemon.command()
@click.option('--json-output', '-j', is_flag=True, help='Output as JSON')
def insights(json_output):
    """Show metadata insights and operational intelligence."""
    try:
        from ipfs_kit_py.intelligent_daemon_manager import get_daemon_manager
        
        daemon_manager = get_daemon_manager()
        insights_data = daemon_manager.get_metadata_insights()
        
        if json_output:
            click.echo(json.dumps(insights_data, indent=2, default=str))
            return
        
        click.echo("📊 Metadata Insights")
        click.echo("==================")
        
        # Bucket analysis
        bucket_analysis = insights_data['bucket_analysis']
        click.echo(f"\n📁 Bucket Analysis:")
        click.echo(f"  Total Buckets: {bucket_analysis['total_buckets']}")
        click.echo(f"  Need Backup: {bucket_analysis['buckets_needing_backup']}")
        click.echo(f"  Avg Pins per Bucket: {bucket_analysis['average_pins_per_bucket']:.1f}")
        
        # Backend analysis
        backend_analysis = insights_data['backend_analysis']
        click.echo(f"\n🔧 Backend Analysis:")
        click.echo(f"  Total Backends: {backend_analysis['total_backends']}")
        
        backend_types = backend_analysis.get('backend_types', {})
        if backend_types:
            click.echo("  Backend Types:")
            for backend_type, count in backend_types.items():
                click.echo(f"    {backend_type}: {count}")
        
        response_stats = backend_analysis.get('response_time_stats', {})
        if response_stats:
            click.echo(f"  Response Times (avg): {response_stats.get('average_ms', 0):.1f}ms")
        
        # Sync requirements
        sync_reqs = insights_data['sync_requirements']
        click.echo(f"\n🔄 Sync Requirements:")
        click.echo(f"  Backends Needing Pin Sync: {len(sync_reqs['backends_needing_pin_sync'])}")
        click.echo(f"  Metadata Backup Targets: {len(sync_reqs['metadata_backup_targets'])}")
        
        dirty_actions = sync_reqs.get('dirty_backend_actions', {})
        if dirty_actions:
            click.echo("  Dirty Backend Actions:")
            for backend_name, action_info in dirty_actions.items():
                unsynced = action_info['unsynced_actions']
                total = action_info['total_actions']
                is_dirty = action_info['is_dirty']
                dirty_icon = "🔄" if is_dirty else "✅"
                click.echo(f"    {dirty_icon} {backend_name}: {unsynced}/{total} unsynced")
        
        # Operational metrics
        ops_metrics = insights_data['operational_metrics']
        click.echo(f"\n⚡ Operational Metrics:")
        click.echo(f"  Metadata Freshness: {ops_metrics['metadata_freshness_seconds']:.1f}s")
        click.echo(f"  Avg Health Check Age: {ops_metrics['avg_backend_health_check_age']:.1f}s")
        click.echo(f"  Total Pending Actions: {ops_metrics['total_pending_actions']}")
        
    except Exception as e:
        click.echo(f"❌ Error getting insights: {e}")


@daemon.command()
def health():
    """Check overall system health based on metadata."""
    try:
        from ipfs_kit_py.intelligent_daemon_manager import get_daemon_manager
        
        daemon_manager = get_daemon_manager()
        status_info = daemon_manager.get_status()
        insights_data = daemon_manager.get_metadata_insights()
        
        click.echo("🏥 System Health Check")
        click.echo("=====================")
        
        # Overall health score
        health_issues = []
        
        # Check daemon status
        if not status_info['running']:
            health_issues.append("❌ Daemon is not running")
        else:
            thread_status = status_info['thread_status']
            inactive_threads = [name for name, active in thread_status.items() if not active]
            if inactive_threads:
                health_issues.append(f"⚠️  Inactive threads: {', '.join(inactive_threads)}")
        
        # Check dirty backends
        dirty_count = status_info['metadata_driven_stats']['dirty_count']
        if dirty_count > 0:
            health_issues.append(f"⚠️  {dirty_count} backends need synchronization")
        
        # Check unhealthy backends
        unhealthy_count = status_info['metadata_driven_stats']['unhealthy_count']
        if unhealthy_count > 0:
            health_issues.append(f"❌ {unhealthy_count} backends are unhealthy")
        
        # Check backup needs
        buckets_needing_backup = insights_data['bucket_analysis']['buckets_needing_backup']
        if buckets_needing_backup > 0:
            health_issues.append(f"⚠️  {buckets_needing_backup} buckets need backup")
        
        # Check pending actions
        pending_actions = insights_data['operational_metrics']['total_pending_actions']
        if pending_actions > 10:
            health_issues.append(f"⚠️  {pending_actions} pending actions (high load)")
        
        # Overall health
        if not health_issues:
            click.echo("🟢 System is healthy!")
            click.echo("All components are functioning normally.")
        else:
            click.echo(f"🟡 Found {len(health_issues)} health issues:")
            for issue in health_issues:
                click.echo(f"  {issue}")
        
        # Recommendations
        if health_issues:
            click.echo("\n💡 Recommendations:")
            if not status_info['running']:
                click.echo("  • Start the daemon with: ipfs-kit daemon start")
            if dirty_count > 0:
                click.echo("  • Wait for automatic sync or check backend configurations")
            if unhealthy_count > 0:
                click.echo("  • Check backend connectivity and configurations")
            if buckets_needing_backup > 0:
                click.echo("  • Ensure filesystem backends are configured for backups")
        
    except Exception as e:
        click.echo(f"❌ Error checking health: {e}")


@daemon.command()
@click.option('--backend', help='Force sync for specific backend')
def sync(backend):
    """Force synchronization of dirty backends."""
    try:
        from ipfs_kit_py.intelligent_daemon_manager import get_daemon_manager
        
        daemon_manager = get_daemon_manager()
        
        if not daemon_manager.get_status()['running']:
            click.echo("❌ Daemon is not running. Start it first with: ipfs-kit daemon start")
            return
        
        if backend:
            click.echo(f"🔄 Forcing sync for backend: {backend}")
            # Schedule immediate sync task
            from ipfs_kit_py.intelligent_daemon_manager import DaemonTask
            from datetime import datetime
            
            task = DaemonTask(
                task_id=f"manual_sync_{backend}_{int(datetime.now().timestamp())}",
                backend_name=backend,
                task_type='pin_sync',
                priority=1,  # Highest priority
                created_at=datetime.now(),
                scheduled_for=datetime.now()
            )
            daemon_manager.schedule_task(task)
            click.echo("✅ Sync task scheduled")
        else:
            # Get dirty backends and schedule sync for all
            status_info = daemon_manager.get_status()
            dirty_backends = status_info['metadata_driven_stats']['dirty_backends']
            
            if not dirty_backends:
                click.echo("ℹ️  No dirty backends found")
                return
            
            click.echo(f"🔄 Scheduling sync for {len(dirty_backends)} dirty backends...")
            for backend_name in dirty_backends:
                from ipfs_kit_py.intelligent_daemon_manager import DaemonTask
                from datetime import datetime
                
                task = DaemonTask(
                    task_id=f"manual_sync_{backend_name}_{int(datetime.now().timestamp())}",
                    backend_name=backend_name,
                    task_type='pin_sync',
                    priority=1,
                    created_at=datetime.now(),
                    scheduled_for=datetime.now()
                )
                daemon_manager.schedule_task(task)
            
            click.echo("✅ Sync tasks scheduled for all dirty backends")
        
    except Exception as e:
        click.echo(f"❌ Error forcing sync: {e}")


if __name__ == '__main__':
    daemon()
