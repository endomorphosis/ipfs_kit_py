    async def _check_libp2p_health(self, backend: Dict[str, Any]) -> Dict[str, Any]:
        """Check libp2p peer network health."""
        try:
            # Initialize peer manager if not already done
            if not backend.get("peer_manager"):
                from .libp2p_peer_manager import LibP2PPeerManager
                peer_manager = LibP2PPeerManager(self.config_dir / "libp2p")
                backend["peer_manager"] = peer_manager
                await peer_manager.initialize()
            else:
                peer_manager = backend["peer_manager"]
                
            # Get peer statistics
            stats = peer_manager.get_peer_statistics()
            
            # Update backend info
            backend["detailed_info"].update({
                "peer_id": str(peer_manager.host.get_id()) if peer_manager.host else "unknown",
                "total_peers": stats["total_peers"],
                "connected_peers": stats["connected_peers"],
                "bootstrap_peers": stats["bootstrap_peers"],
                "protocols": stats["protocols_supported"],
                "discovery_active": stats["discovery_active"],
                "files_accessible": stats["total_files"],
                "pins_accessible": stats["total_pins"]
            })
            
            # Get listen addresses if host is available
            if peer_manager.host:
                try:
                    listen_addrs = []
                    for addr in peer_manager.host.get_addrs():
                        listen_addrs.append(str(addr))
                    backend["detailed_info"]["listen_addresses"] = listen_addrs
                except Exception:
                    backend["detailed_info"]["listen_addresses"] = []
            
            # Update metrics
            backend["metrics"] = {
                "peer_discovery": {
                    "total_peers": stats["total_peers"],
                    "connected_peers": stats["connected_peers"],
                    "bootstrap_peers": stats["bootstrap_peers"],
                    "discovery_active": stats["discovery_active"]
                },
                "network_data": {
                    "files_accessible": stats["total_files"],
                    "pins_accessible": stats["total_pins"],
                    "protocols_count": len(stats["protocols_supported"])
                },
                "connectivity": {
                    "host_active": peer_manager.host is not None,
                    "protocols_supported": stats["protocols_supported"]
                }
            }
            
            # Determine status based on peer manager state
            if peer_manager.host and stats["total_peers"] > 0:
                backend["status"] = "running"
                backend["health"] = "healthy"
            elif peer_manager.host:
                backend["status"] = "running"
                backend["health"] = "degraded"  # Host running but no peers
            else:
                backend["status"] = "stopped"
                backend["health"] = "unhealthy"
                
        except Exception as e:
            backend["status"] = "error"
            backend["health"] = "unhealthy"
            backend["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            })
            logger.error(f"Error checking libp2p health: {e}")
            
        backend["last_check"] = datetime.now().isoformat()
        return backend
