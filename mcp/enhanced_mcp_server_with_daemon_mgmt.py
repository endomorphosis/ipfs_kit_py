"""Test-compatibility shim for `mcp.enhanced_mcp_server_with_daemon_mgmt`.

The repository's main MCP implementation lives under `ipfs_kit_py.mcp.*`.
Some tests import this legacy module path, so we provide a lightweight wrapper
that focuses on filesystem-backed read helpers (configs, parquet files) and a
minimal tool registry.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# GraphRAG feature tests expect this symbol to be available from this module.
try:
    from ipfs_kit_py.mcp.servers.enhanced_mcp_server_with_daemon_mgmt import (
        GraphRAGSearchEngine,
    )
except Exception:  # pragma: no cover
    try:
        from ipfs_kit_py.graphrag import GraphRAGSearchEngine  # type: ignore
    except Exception:
        GraphRAGSearchEngine = None  # type: ignore


def _read_simple_yaml(path: Path) -> Dict[str, Any]:
    """Best-effort YAML reader.

    Tests only rely on simple `key: value` pairs, so we keep a tiny fallback
    parser if PyYAML isn't available.
    """

    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        result: Dict[str, Any] = {}
        try:
            for raw_line in path.read_text().splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if value.isdigit():
                    result[key] = int(value)
                elif value.lower() in {"true", "false"}:
                    result[key] = value.lower() == "true"
                else:
                    result[key] = value
        except Exception as e:
            logger.debug("Failed to parse config %s: %s", path, e)
        return result


def _read_parquet_records(path: Path) -> List[Dict[str, Any]]:
    try:
        import pandas as pd  # type: ignore

        if not path.exists():
            return []
        return pd.read_parquet(path).to_dict(orient="records")
    except Exception as e:
        logger.debug("Failed to read parquet %s: %s", path, e)
        return []


class EnhancedMCPServerWithDaemonMgmt:
    """Lightweight MCP server facade used by tests."""

    DEFAULT_TOOL_NAMES = [
        # Core IPFS-ish tools
        "ipfs_add",
        "ipfs_cat",
        "ipfs_get",
        "ipfs_ls",
        "ipfs_pin_add",
        "ipfs_pin_rm",
        "ipfs_list_pins",
        "ipfs_version",
        "ipfs_id",
        "ipfs_stats",
        "ipfs_swarm_peers",
        "ipfs_pin_update",
        "ipfs_refs",
        "ipfs_refs_local",
        "ipfs_block_stat",
        "ipfs_block_get",
        "ipfs_dag_get",
        "ipfs_dag_put",
        "ipfs_dht_findpeer",
        "ipfs_dht_findprovs",
        "ipfs_dht_query",
        "ipfs_name_publish",
        "ipfs_name_resolve",
        "ipfs_pubsub_publish",
        "ipfs_pubsub_subscribe",
        "ipfs_pubsub_peers",
        "ipfs_files_mkdir",
        "ipfs_files_ls",
        "ipfs_files_stat",
        "ipfs_files_read",
        "ipfs_files_write",
        "ipfs_files_cp",
        "ipfs_files_mv",
        "ipfs_files_rm",
        "ipfs_files_flush",
        "ipfs_files_chcid",
        # VFS tools
        "vfs_mount",
        "vfs_unmount",
        "vfs_list_mounts",
        "vfs_read",
        "vfs_write",
        "vfs_copy",
        "vfs_move",
        "vfs_mkdir",
        "vfs_rmdir",
        "vfs_ls",
        "vfs_stat",
        "vfs_sync_to_ipfs",
        "vfs_sync_from_ipfs",
        "system_health",
    ]

    def __init__(self, **_kwargs: Any):
        self.ipfs_kit_path = Path.home() / ".ipfs_kit"
        self.ipfs_kit_path.mkdir(parents=True, exist_ok=True)

        # Minimal MCP tool registry surface.
        self.tools: Dict[str, Dict[str, Any]] = {
            name: {
                "name": name,
                "description": "",
                "inputSchema": {"type": "object", "properties": {}},
            }
            for name in self.DEFAULT_TOOL_NAMES
        }

    def get_all_configs(self) -> Dict[str, Any]:
        configs: Dict[str, Any] = {}
        config_dir = self.ipfs_kit_path

        config_files = [
            "package_config.yaml",
            "s3_config.yaml",
            "lotus_config.yaml",
            "storacha_config.yaml",
            "gdrive_config.yaml",
            "synapse_config.yaml",
            "huggingface_config.yaml",
            "github_config.yaml",
            "ipfs_cluster_config.yaml",
            "cluster_follow_config.yaml",
            "parquet_config.yaml",
            "arrow_config.yaml",
            "sshfs_config.yaml",
            "ftp_config.yaml",
            "daemon_config.yaml",
            "wal_config.yaml",
            "fs_journal_config.yaml",
            "pinset_policy_config.yaml",
            "bucket_config.yaml",
        ]

        for config_file in config_files:
            path = config_dir / config_file
            if not path.exists():
                continue
            configs[path.stem.replace("_config", "")] = _read_simple_yaml(path)

        return configs

    def get_pin_metadata(self) -> List[Dict[str, Any]]:
        pin_metadata_path = (
            self.ipfs_kit_path / "pin_metadata" / "parquet_storage" / "pins.parquet"
        )
        return _read_parquet_records(pin_metadata_path)

    def get_program_state_data(self) -> Dict[str, Any]:
        state_data: Dict[str, Any] = {}
        state_dir = self.ipfs_kit_path / "program_state" / "parquet"
        if not state_dir.exists():
            return state_data

        try:
            import pandas as pd  # type: ignore

            for state_file in state_dir.glob("*.parquet"):
                df = pd.read_parquet(state_file)
                if not df.empty:
                    state_data[state_file.stem] = df.iloc[-1].to_dict()
        except Exception as e:
            logger.debug("Failed reading program state data: %s", e)

        return state_data

    def get_bucket_registry(self) -> List[Dict[str, Any]]:
        bucket_registry_path = self.ipfs_kit_path / "bucket_index" / "bucket_registry.parquet"
        return _read_parquet_records(bucket_registry_path)

    def get_backend_status_data(self) -> Dict[str, Any]:
        configs = self.get_all_configs()
        bucket_cfg = configs.get("bucket") or {}
        daemon_cfg = configs.get("daemon") or {}

        return {
            "bucket": {
                "configured": bool(bucket_cfg),
                "details": bucket_cfg,
                "status": "configured" if bucket_cfg else "missing",
            },
            "daemon": {
                "configured": bool(daemon_cfg),
                "details": daemon_cfg,
                "status": "configured" if daemon_cfg else "missing",
            },
        }


# Re-export the real integration layer, but default to NOT auto-starting daemons.
try:
    from ipfs_kit_py.mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import (
        IPFSKitIntegration as _RealIPFSKitIntegration,
    )

    class IPFSKitIntegration(_RealIPFSKitIntegration):
        def __init__(self, auto_start_daemons: bool = False, auto_start_lotus_daemon: bool = False):
            super().__init__(
                auto_start_daemons=auto_start_daemons,
                auto_start_lotus_daemon=auto_start_lotus_daemon,
            )

except Exception:  # pragma: no cover

    class IPFSKitIntegration:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any):
            raise ImportError("IPFSKitIntegration is not available in this environment")


__all__ = [
    "EnhancedMCPServerWithDaemonMgmt",
    "GraphRAGSearchEngine",
    "IPFSKitIntegration",
]
