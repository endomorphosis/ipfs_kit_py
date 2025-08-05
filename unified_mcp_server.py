
import asyncio
import json
from pathlib import Path
import sys

# Add the package to the path if needed
sys.path.insert(0, str(Path(__file__).parent))

from ipfs_kit_py.mcp import MCP, Server, Message

class UnifiedMCPServer(Server):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mcp = MCP()

    async def handle_message(self, message: Message):
        command = message.command
        args = message.args
        
        if command == "health":
            await self.send_response(message.sender, {"status": "healthy"})
        elif command == "daemon":
            try:
                from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
                daemon_manager = EnhancedDaemonManager()
                if args[0] == "start":
                    result = daemon_manager.start_daemon(detach=True)
                elif args[0] == "stop":
                    result = daemon_manager.stop_daemon()
                elif args[0] == "status":
                    result = daemon_manager.check_daemon_status()
                elif args[0] == "restart":
                    result = daemon_manager.restart_daemon()
                else:
                    result = {"error": "Unknown daemon command"}
                await self.send_response(message.sender, result)
            except Exception as e:
                await self.send_response(message.sender, {"error": str(e)})
        elif command == "pin":
            try:
                from ipfs_kit_py.pin_manager import PinManager
                pin_manager = PinManager()
                if args[0] == "add":
                    result = pin_manager.add_pin(args[1], args[2] if len(args) > 2 else '')
                elif args[0] == "remove":
                    result = pin_manager.remove_pin(args[1])
                elif args[0] == "list":
                    result = pin_manager.list_pins()
                else:
                    result = {"error": "Unknown pin command"}
                await self.send_response(message.sender, result)
            except Exception as e:
                await self.send_response(message.sender, {"error": str(e)})
        elif command == "backend":
            try:
                from ipfs_kit_py.backend_manager import BackendManager
                backend_manager = BackendManager()
                if args[0] == "list":
                    result = backend_manager.list_backends()
                elif args[0] == "show":
                    result = backend_manager.show_backend(args[1])
                elif args[0] == "create":
                    result = backend_manager.create_backend(args[1], args[2], **json.loads(args[3]))
                elif args[0] == "update":
                    result = backend_manager.update_backend(args[1], **json.loads(args[2]))
                elif args[0] == "remove":
                    result = backend_manager.remove_backend(args[1])
                else:
                    result = {"error": "Unknown backend command"}
                await self.send_response(message.sender, result)
            except Exception as e:
                await self.send_response(message.sender, {"error": str(e)})
        elif command == "config":
            try:
                from ipfs_kit_py.config_manager import ConfigManager
                config_manager = ConfigManager()
                if args[0] == "show":
                    result = config_manager.get_config_json()
                elif args[0] == "set":
                    result = config_manager.save_config_json(args[1])
                else:
                    result = {"error": "Unknown config command"}
                await self.send_response(message.sender, result)
            except Exception as e:
                await self.send_response(message.sender, {"error": str(e)})
        elif command == "bucket":
            try:
                from ipfs_kit_py.bucket_manager import BucketManager
                bucket_manager = BucketManager()
                if args[0] == "list":
                    result = bucket_manager.list_buckets()
                elif args[0] == "create":
                    result = bucket_manager.create_bucket(args[1], **json.loads(args[2]))
                elif args[0] == "rm":
                    result = bucket_manager.remove_bucket(args[1])
                elif args[0] == "upload":
                    result = bucket_manager.upload_file(args[1], args[2], args[3])
                elif args[0] == "files":
                    result = bucket_manager.list_files(args[1])
                else:
                    result = {"error": "Unknown bucket command"}
                await self.send_response(message.sender, result)
            except Exception as e:
                await self.send_response(message.sender, {"error": str(e)})
        elif command == "metrics":
            try:
                from ipfs_kit_py.metrics_manager import MetricsManager
                metrics_manager = MetricsManager()
                result = metrics_manager.get_metrics()
                await self.send_response(message.sender, result)
            except Exception as e:
                await self.send_response(message.sender, {"error": str(e)})
        elif command == "log":
            try:
                from ipfs_kit_py.log_manager import LogManager
                log_manager = LogManager()
                result = log_manager.get_logs(component=args[0] if args else None)
                await self.send_response(message.sender, result)
            except Exception as e:
                await self.send_response(message.sender, {"error": str(e)})
        elif command == "peer":
            try:
                from ipfs_kit_py.peer_manager import PeerManager
                peer_manager = PeerManager()
                if args[0] == "list":
                    result = peer_manager.list_peers()
                elif args[0] == "connect":
                    result = peer_manager.connect_peer(json.loads(args[1]))
                elif args[0] == "disconnect":
                    result = peer_manager.disconnect_peer(args[1])
                elif args[0] == "info":
                    result = peer_manager.get_peer_info(args[1])
                else:
                    result = {"error": "Unknown peer command"}
                await self.send_response(message.sender, result)
            except Exception as e:
                await self.send_response(message.sender, {"error": str(e)})
        elif command == "content":
            try:
                from ipfs_kit_py.content_manager import ContentManager
                content_manager = ContentManager()
                if args[0] == "list":
                    result = content_manager.list_content()
                elif args[0] == "details":
                    result = content_manager.get_content_details(args[1])
                elif args[0] == "generate_address":
                    result = content_manager.generate_content_address(json.loads(args[1]))
                elif args[0] == "verify_integrity":
                    result = content_manager.verify_content_integrity(args[1], args[2])
                else:
                    result = {"error": "Unknown content command"}
                await self.send_response(message.sender, result)
            except Exception as e:
                await self.send_response(message.sender, {"error": str(e)})
        elif command == "service":
            try:
                from ipfs_kit_py.service_manager import ServiceManager
                service_manager = ServiceManager()
                if args[0] == "list":
                    result = service_manager.list_services()
                elif args[0] == "status":
                    result = service_manager.get_service_status(args[1])
                elif args[0] == "start":
                    result = service_manager.start_service(args[1])
                elif args[0] == "stop":
                    result = service_manager.stop_service(args[1])
                else:
                    result = {"error": "Unknown service command"}
                await self.send_response(message.sender, result)
            except Exception as e:
                await self.send_response(message.sender, {"error": str(e)})
        elif command == "vfs":
            try:
                from ipfs_kit_py.vfs_manager import VFSManager
                vfs_manager = VFSManager()
                if args[0] == "list":
                    result = await vfs_manager.list_files(path=args[1] if len(args) > 1 else "/")
                elif args[0] == "cat":
                    result = await vfs_manager.execute_vfs_operation("cat", path=args[1])
                elif args[0] == "info":
                    result = await vfs_manager.execute_vfs_operation("info", path=args[1])
                elif args[0] == "mkdir":
                    result = await vfs_manager.create_folder(path=args[1], name=args[2])
                elif args[0] == "rm":
                    result = await vfs_manager.delete_item(path=args[1])
                elif args[0] == "rename":
                    result = await vfs_manager.rename_item(old_path=args[1], new_name=args[2])
                elif args[0] == "move":
                    result = await vfs_manager.move_item(source_path=args[1], target_path=args[2])
                elif args[0] == "stats":
                    result = await vfs_manager.get_vfs_statistics()
                else:
                    result = {"error": "Unknown VFS command"}
                await self.send_response(message.sender, result)
            except Exception as e:
                await self.send_response(message.sender, {"error": str(e)})
        elif command == "parquet":
            try:
                from ipfs_kit_py.parquet_manager import ParquetManager
                parquet_manager = ParquetManager()
                if args[0] == "list_datasets":
                    result = parquet_manager.list_datasets()
                elif args[0] == "store_dataframe":
                    result = parquet_manager.store_dataframe(json.loads(args[1]))
                elif args[0] == "retrieve_dataframe":
                    result = parquet_manager.retrieve_dataframe(args[1], columns=json.loads(args[2]) if len(args) > 2 else None, format=args[3] if len(args) > 3 else "json")
                elif args[0] == "query_datasets":
                    result = parquet_manager.query_datasets(json.loads(args[1]))
                else:
                    result = {"error": "Unknown parquet command"}
                await self.send_response(message.sender, result)
            except Exception as e:
                await self.send_response(message.sender, {"error": str(e)})
        elif command == "mcp":
            if args[0] == "start" or args[0] == "restart":
                await self.stop()
                await self.start()
                await self.send_response(message.sender, {"status": "MCP server restarted"})
            elif args[0] == "stop":
                await self.stop()
                await self.send_response(message.sender, {"status": "MCP server stopped"})
            elif args[0] == "status":
                await self.send_response(message.sender, {"status": "MCP server is running"})
            else:
                await self.send_response(message.sender, {"error": "Unknown mcp command"})
        else:
            await self.send_response(message.sender, {"error": "Unknown command"})

async def main():
    server = UnifiedMCPServer()
    await server.start()

if __name__ == "__main__":
    asyncio.run(main())
