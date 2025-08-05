#!/usr/bin/env python3
"""
Replication Dashboard Panel Configuration

This module provides the frontend dashboard panel configuration for managing
pin replication across storage backends with data loss protection features.
"""

import json
from typing import Dict, List, Any

class ReplicationDashboardPanel:
    """Configuration for the replication management dashboard panel."""
    
    def __init__(self):
        """Initialize the dashboard panel configuration."""
        self.panel_config = self._create_panel_config()
    
    def _create_panel_config(self) -> Dict[str, Any]:
        """Create the complete dashboard panel configuration."""
        return {
            "panel_id": "replication_management",
            "title": "Pin Replication & Data Protection",
            "description": "Manage pin replication across storage backends with backup/restore capabilities",
            "icon": "shield-check",
            "layout": {
                "type": "grid",
                "columns": 2,
                "sections": [
                    self._create_status_section(),
                    self._create_settings_section(),
                    self._create_replication_section(),
                    self._create_backup_section()
                ]
            },
            "api_endpoints": self._get_api_endpoints(),
            "real_time_updates": True,
            "refresh_interval": 30
        }
    
    def _create_status_section(self) -> Dict[str, Any]:
        """Create the replication status overview section."""
        return {
            "id": "replication_status",
            "title": "Replication Overview",
            "type": "status_cards",
            "grid_position": {"row": 1, "col": 1, "span": 2},
            "components": [
                {
                    "type": "metric_card",
                    "id": "total_pins",
                    "title": "Total Pins",
                    "api_endpoint": "/api/dashboard/replication/status",
                    "data_path": "data.data.total_pins",
                    "format": "number",
                    "color": "blue"
                },
                {
                    "type": "metric_card", 
                    "id": "replication_efficiency",
                    "title": "Replication Efficiency",
                    "api_endpoint": "/api/dashboard/replication/status",
                    "data_path": "data.data.replication_efficiency",
                    "format": "percentage",
                    "color": "green",
                    "thresholds": {"warning": 80, "critical": 60}
                },
                {
                    "type": "metric_card",
                    "id": "under_replicated",
                    "title": "Under-Replicated",
                    "api_endpoint": "/api/dashboard/replication/status",
                    "data_path": "data.data.under_replicated",
                    "format": "number",
                    "color": "orange",
                    "alert_on_value": "> 0"
                },
                {
                    "type": "metric_card",
                    "id": "over_replicated",
                    "title": "Over-Replicated",
                    "api_endpoint": "/api/dashboard/replication/status",
                    "data_path": "data.data.over_replicated",
                    "format": "number",
                    "color": "yellow"
                }
            ]
        }
    
    def _create_settings_section(self) -> Dict[str, Any]:
        """Create the replication settings configuration section."""
        return {
            "id": "replication_settings",
            "title": "Replication Settings",
            "type": "form",
            "grid_position": {"row": 2, "col": 1},
            "components": [
                {
                    "type": "number_input",
                    "id": "min_replicas",
                    "label": "Minimum Replicas",
                    "api_endpoint": "/api/dashboard/replication/settings",
                    "data_path": "data.min_replicas",
                    "min": 1,
                    "max": 10,
                    "default": 2,
                    "description": "Minimum number of replicas to maintain"
                },
                {
                    "type": "number_input",
                    "id": "target_replicas",
                    "label": "Target Replicas",
                    "api_endpoint": "/api/dashboard/replication/settings",
                    "data_path": "data.target_replicas",
                    "min": 1,
                    "max": 10,
                    "default": 3,
                    "description": "Ideal number of replicas"
                },
                {
                    "type": "number_input",
                    "id": "max_replicas",
                    "label": "Maximum Replicas",
                    "api_endpoint": "/api/dashboard/replication/settings",
                    "data_path": "data.max_replicas",
                    "min": 1,
                    "max": 15,
                    "default": 5,
                    "description": "Maximum allowed replicas"
                },
                {
                    "type": "number_input",
                    "id": "max_size_gb",
                    "label": "Max Size (GB)",
                    "api_endpoint": "/api/dashboard/replication/settings",
                    "data_path": "data.max_size_gb",
                    "min": 1,
                    "max": 10000,
                    "default": 100,
                    "step": 10,
                    "description": "Maximum storage size per backend"
                },
                {
                    "type": "select",
                    "id": "replication_strategy",
                    "label": "Replication Strategy",
                    "api_endpoint": "/api/dashboard/replication/settings",
                    "data_path": "data.replication_strategy",
                    "options": [
                        {"value": "balanced", "label": "Balanced Distribution"},
                        {"value": "priority", "label": "Priority-Based"},
                        {"value": "size_based", "label": "Size-Based Selection"}
                    ],
                    "default": "balanced"
                },
                {
                    "type": "toggle",
                    "id": "auto_replication",
                    "label": "Auto-Replication",
                    "api_endpoint": "/api/dashboard/replication/settings",
                    "data_path": "data.auto_replication",
                    "default": True,
                    "description": "Automatically maintain target replica count"
                },
                {
                    "type": "button",
                    "id": "save_settings",
                    "label": "Save Settings",
                    "action": "POST",
                    "api_endpoint": "/api/dashboard/replication/settings",
                    "color": "primary"
                }
            ]
        }
    
    def _create_replication_section(self) -> Dict[str, Any]:
        """Create the pin replication management section."""
        return {
            "id": "pin_replication",
            "title": "Pin Replication Management",
            "type": "interactive_table",
            "grid_position": {"row": 2, "col": 2},
            "components": [
                {
                    "type": "search_input",
                    "id": "pin_search",
                    "placeholder": "Search by CID...",
                    "api_endpoint": "/api/dashboard/replication/status"
                },
                {
                    "type": "data_table",
                    "id": "pins_table",
                    "api_endpoint": "/api/dashboard/replication/status",
                    "columns": [
                        {
                            "key": "cid",
                            "label": "CID",
                            "type": "text",
                            "truncate": 16,
                            "copyable": True
                        },
                        {
                            "key": "replica_count",
                            "label": "Replicas",
                            "type": "badge",
                            "color_based_on": "replication_health"
                        },
                        {
                            "key": "backends",
                            "label": "Storage Backends", 
                            "type": "tag_list",
                            "max_visible": 3
                        },
                        {
                            "key": "size_mb",
                            "label": "Size (MB)",
                            "type": "number",
                            "format": "decimal"
                        },
                        {
                            "key": "last_check",
                            "label": "Last Check",
                            "type": "datetime",
                            "format": "relative"
                        },
                        {
                            "key": "actions",
                            "label": "Actions",
                            "type": "action_buttons",
                            "buttons": [
                                {
                                    "label": "Replicate",
                                    "action": "replicate_pin",
                                    "color": "blue",
                                    "icon": "copy"
                                },
                                {
                                    "label": "Analyze",
                                    "action": "analyze_pin",
                                    "color": "gray",
                                    "icon": "chart-bar"
                                }
                            ]
                        }
                    ],
                    "filters": [
                        {
                            "key": "replication_health",
                            "label": "Health Status",
                            "type": "select",
                            "options": ["all", "healthy", "warning", "critical", "excess"]
                        }
                    ],
                    "pagination": True,
                    "page_size": 20
                }
            ]
        }
    
    def _create_backup_section(self) -> Dict[str, Any]:
        """Create the backup and restore management section."""
        return {
            "id": "backup_restore",
            "title": "Backup & Data Protection",
            "type": "tabbed_panel",
            "grid_position": {"row": 3, "col": 1, "span": 2},
            "tabs": [
                {
                    "id": "backend_status",
                    "label": "Backend Status",
                    "components": [
                        {
                            "type": "backend_grid",
                            "id": "backends_overview",
                            "api_endpoint": "/api/dashboard/replication/backends",
                            "display_format": "cards",
                            "card_template": {
                                "title": "{{backend_name}}",
                                "subtitle": "{{backend_type}}",
                                "metrics": [
                                    {"label": "Pins", "value": "{{pin_count}}"},
                                    {"label": "Size", "value": "{{estimated_size_gb}}GB"},
                                    {"label": "Capacity", "value": "{{max_size_gb}}GB"},
                                    {"label": "Health", "value": "{{health_status}}"}
                                ],
                                "status_indicator": "{{health_status}}",
                                "actions": [
                                    {
                                        "label": "Export Backup",
                                        "action": "export_backend_backup",
                                        "icon": "download"
                                    },
                                    {
                                        "label": "Import Backup",
                                        "action": "import_backend_backup",
                                        "icon": "upload"
                                    }
                                ]
                            }
                        }
                    ]
                },
                {
                    "id": "backup_operations",
                    "label": "Backup Operations",
                    "components": [
                        {
                            "type": "form_section",
                            "title": "Export Backend Pins",
                            "components": [
                                {
                                    "type": "select",
                                    "id": "export_backend",
                                    "label": "Select Backend",
                                    "api_endpoint": "/api/dashboard/replication/backends",
                                    "data_path": "data.backends",
                                    "required": True
                                },
                                {
                                    "type": "text_input",
                                    "id": "backup_path",
                                    "label": "Backup Path",
                                    "placeholder": "/path/to/backup.json",
                                    "description": "Leave empty for auto-generated path"
                                },
                                {
                                    "type": "checkbox",
                                    "id": "include_metadata",
                                    "label": "Include Metadata",
                                    "default": True
                                },
                                {
                                    "type": "checkbox",
                                    "id": "compress_backup",
                                    "label": "Compress Backup",
                                    "default": True
                                },
                                {
                                    "type": "button",
                                    "id": "export_backup",
                                    "label": "Export Backup",
                                    "action": "POST",
                                    "api_endpoint": "/api/dashboard/backup/{export_backend}/export",
                                    "color": "primary",
                                    "icon": "download"
                                }
                            ]
                        },
                        {
                            "type": "form_section",
                            "title": "Import Backend Pins",
                            "components": [
                                {
                                    "type": "select",
                                    "id": "import_backend",
                                    "label": "Target Backend",
                                    "api_endpoint": "/api/dashboard/replication/backends",
                                    "data_path": "data.backends",
                                    "required": True
                                },
                                {
                                    "type": "file_input",
                                    "id": "restore_file",
                                    "label": "Backup File",
                                    "accept": ".json,.json.gz",
                                    "required": True
                                },
                                {
                                    "type": "button",
                                    "id": "verify_backup",
                                    "label": "Verify Backup",
                                    "action": "POST",
                                    "api_endpoint": "/api/dashboard/backup/verify",
                                    "color": "secondary",
                                    "icon": "check-circle"
                                },
                                {
                                    "type": "button",
                                    "id": "import_backup",
                                    "label": "Import Backup",
                                    "action": "POST",
                                    "api_endpoint": "/api/dashboard/backup/{import_backend}/import",
                                    "color": "primary",
                                    "icon": "upload",
                                    "confirm": "Are you sure you want to import this backup?"
                                }
                            ]
                        }
                    ]
                },
                {
                    "id": "backup_history",
                    "label": "Backup History",
                    "components": [
                        {
                            "type": "data_table",
                            "id": "backups_table",
                            "api_endpoint": "/api/dashboard/backup/{backend}/list",
                            "columns": [
                                {
                                    "key": "backup_path",
                                    "label": "Backup File",
                                    "type": "text"
                                },
                                {
                                    "key": "backend_name",
                                    "label": "Backend",
                                    "type": "badge"
                                },
                                {
                                    "key": "size_mb",
                                    "label": "Size (MB)",
                                    "type": "number"
                                },
                                {
                                    "key": "created_date",
                                    "label": "Created",
                                    "type": "datetime"
                                },
                                {
                                    "key": "actions",
                                    "label": "Actions",
                                    "type": "action_buttons",
                                    "buttons": [
                                        {
                                            "label": "Verify",
                                            "action": "verify_backup",
                                            "color": "blue",
                                            "icon": "check"
                                        },
                                        {
                                            "label": "Download",
                                            "action": "download_backup",
                                            "color": "green",
                                            "icon": "download"
                                        },
                                        {
                                            "label": "Delete",
                                            "action": "delete_backup",
                                            "color": "red",
                                            "icon": "trash",
                                            "confirm": "Delete this backup?"
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    
    def _get_api_endpoints(self) -> List[Dict[str, str]]:
        """Get list of API endpoints used by this panel."""
        return [
            {
                "endpoint": "/api/dashboard/replication/status",
                "method": "GET",
                "description": "Get replication status overview"
            },
            {
                "endpoint": "/api/dashboard/replication/settings",
                "method": "GET/POST",
                "description": "Get/update replication settings"
            },
            {
                "endpoint": "/api/dashboard/replication/pins/{cid}/replicate",
                "method": "POST",
                "description": "Replicate specific pin to backends"
            },
            {
                "endpoint": "/api/dashboard/replication/backends",
                "method": "GET",
                "description": "Get backend capabilities and status"
            },
            {
                "endpoint": "/api/dashboard/backup/{backend}/export",
                "method": "POST",
                "description": "Export pins from backend to backup"
            },
            {
                "endpoint": "/api/dashboard/backup/{backend}/import",
                "method": "POST",
                "description": "Import pins from backup to backend"
            },
            {
                "endpoint": "/api/dashboard/backup/verify",
                "method": "POST",
                "description": "Verify backup file integrity"
            }
        ]
    
    def get_panel_config(self) -> Dict[str, Any]:
        """Get the complete panel configuration."""
        return self.panel_config
    
    def export_config(self, file_path: str = None) -> str:
        """Export panel configuration to JSON file."""
        if not file_path:
            file_path = "/tmp/replication_dashboard_panel.json"
        
        with open(file_path, 'w') as f:
            json.dump(self.panel_config, f, indent=2)
        
        return file_path

# Usage example
if __name__ == "__main__":
    panel = ReplicationDashboardPanel()
    config_path = panel.export_config()
    print(f"✓ Replication dashboard panel configuration exported to: {config_path}")
    print("\n📋 Panel Features:")
    print("• Real-time replication status monitoring")
    print("• Configurable replication settings")
    print("• Interactive pin management table")
    print("• Backend health and capacity overview")
    print("• Backup/restore operations with verification")
    print("• Data loss protection mechanisms")
    print("• CID-to-backend mapping visualization")
