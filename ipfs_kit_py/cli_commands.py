
"""
This module contains the implementation of the CLI commands.
"""
import json

async def handle_daemon_command(args):
    """Handles the daemon command and its subcommands."""
    from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
    daemon_manager = EnhancedDaemonManager()
    if args.daemon_action == 'start':
        await daemon_manager.start_daemon_async(detach=args.detach, role=args.role, master_address=args.master_address, cluster_secret=args.cluster_secret)
    elif args.daemon_action == 'stop':
        await daemon_manager.stop_daemon_async()
    elif args.daemon_action == 'status':
        status = await daemon_manager.check_daemon_status_async()
        print(json.dumps(status, indent=2))
    elif args.daemon_action == 'restart':
        await daemon_manager.restart_daemon_async()

async def handle_pin_command(args):
    """Handles the pin command and its subcommands."""
    from ipfs_kit_py.pins import PinManager
    pin_manager = PinManager()
    if args.pin_action == 'add':
        result = await pin_manager.add_pin_async(args.cid_or_file, name=args.name, recursive=args.recursive, is_file=args.file)
        print(json.dumps(result, indent=2))
    elif args.pin_action == 'remove':
        result = await pin_manager.remove_pin_async(args.cid)
        print(json.dumps(result, indent=2))
    elif args.pin_action == 'list':
        pins = await pin_manager.list_pins_async(limit=args.limit, metadata=args.metadata)
        print(json.dumps(pins, indent=2))

async def handle_bucket_command(args, cli_instance):
    """Handles the bucket command and its subcommands."""
    if args.bucket_action == 'list':
        buckets = cli_instance.get_bucket_index()
        print(json.dumps(buckets, indent=2))
    elif args.bucket_action == 'generate-registry-car':
        result = cli_instance.generate_bucket_registry_car()
        print(json.dumps(result, indent=2))

async def handle_mcp_command(args):
    """Handles the mcp command and its subcommands."""
    if args.mcp_action == 'start':
        try:
            import importlib.util
            from pathlib import Path as _Path
            root = _Path(__file__).resolve().parents[1]  # repo root
            dash_path = root / 'consolidated_mcp_dashboard.py'
            if dash_path.exists():
                spec = importlib.util.spec_from_file_location('consolidated_mcp_dashboard', str(dash_path))
                mod = importlib.util.module_from_spec(spec)
                assert spec and spec.loader
                spec.loader.exec_module(mod)
                DashboardClass = getattr(mod, 'ConsolidatedMCPDashboard')
                cfg = {'host': args.host, 'port': args.port, 'debug': args.debug, 'data_dir': str((_Path.home() / '.ipfs_kit'))}
                dash = DashboardClass(cfg)
                await dash.run()
            else:
                raise ImportError('consolidated_mcp_dashboard.py not found')
        except Exception as e:
            try:
                from ipfs_kit_py.modernized_comprehensive_dashboard import ModernizedComprehensiveDashboard
                dashboard = ModernizedComprehensiveDashboard(config={'host': args.host, 'port': args.port, 'debug': args.debug})
                dashboard.run()
            except Exception as e2:
                print(f"❌ Failed to start any dashboard. Unified error: {e}. Legacy fallback error: {e2}")
