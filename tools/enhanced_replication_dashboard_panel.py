#!/usr/bin/env python3
"""
Enhanced Replication Dashboard Panel Configuration

This module provides the frontend dashboard panel configuration for managing
pin replication across storage backends with comprehensive traffic monitoring,
VFS metadata linking, and data loss protection features.
"""

import json
from typing import Dict, List, Any

class EnhancedReplicationDashboardPanel:
    """Configuration for the enhanced replication management dashboard panel."""
    
    def __init__(self):
        """Initialize the enhanced replication dashboard panel."""
        self.panel_config = self._create_panel_config()
    
    def _create_panel_config(self) -> Dict[str, Any]:
        """Create the complete dashboard panel configuration."""
        return {
            "panel_id": "enhanced_replication_management",
            "title": "Enhanced Pin Replication & Traffic Analytics",
            "description": "Comprehensive replication management with traffic monitoring and VFS integration",
            "version": "2.0.0",
            "layout": {
                "type": "grid",
                "columns": 12,
                "rows": "auto",
                "gap": "1rem"
            },
            "sections": [
                self._create_overview_section(),
                self._create_traffic_monitoring_section(),
                self._create_vfs_integration_section(),
                self._create_settings_section(),
                self._create_backend_management_section(),
                self._create_replication_operations_section(),
                self._create_data_protection_section()
            ],
            "real_time_updates": {
                "enabled": True,
                "interval_seconds": 10,
                "endpoints": self._get_api_endpoints()
            },
            "styling": {
                "theme": "bootstrap",
                "color_scheme": "light",
                "charts": "chart.js",
                "icons": "fontawesome"
            }
        }
    
    def _create_overview_section(self) -> Dict[str, Any]:
        """Create the overview status section."""
        return {
            "id": "overview_section",
            "title": "Replication & Traffic Overview",
            "type": "status_cards",
            "grid": {"col_span": 12, "row_span": 2},
            "cards": [
                {
                    "id": "total_pins",
                    "title": "Total Pins",
                    "endpoint": "/api/dashboard/replication/status",
                    "value_path": "data.total_pins",
                    "icon": "fas fa-thumbtack",
                    "color": "primary"
                },
                {
                    "id": "replication_efficiency",
                    "title": "Replication Efficiency",
                    "endpoint": "/api/dashboard/replication/status",
                    "value_path": "data.replication_efficiency",
                    "suffix": "%",
                    "icon": "fas fa-shield-alt",
                    "color": "success"
                },
                {
                    "id": "total_traffic",
                    "title": "Total Traffic",
                    "endpoint": "/api/dashboard/analytics/traffic",
                    "value_path": "data.usage_statistics.summary.total_traffic_gb",
                    "suffix": " GB",
                    "icon": "fas fa-exchange-alt",
                    "color": "info"
                },
                {
                    "id": "active_backends",
                    "title": "Active Backends",
                    "endpoint": "/api/dashboard/analytics/traffic",
                    "value_path": "data.usage_statistics.summary.active_backends",
                    "icon": "fas fa-server",
                    "color": "warning"
                },
                {
                    "id": "vfs_linked_pins",
                    "title": "VFS Linked Pins",
                    "endpoint": "/api/dashboard/analytics/traffic",
                    "value_path": "data.usage_statistics.summary.vfs_linked_pins",
                    "icon": "fas fa-link",
                    "color": "secondary"
                },
                {
                    "id": "under_replicated",
                    "title": "Under Replicated",
                    "endpoint": "/api/dashboard/replication/status",
                    "value_path": "data.under_replicated",
                    "icon": "fas fa-exclamation-triangle",
                    "color": "danger",
                    "alert_threshold": 0
                }
            ]
        }
    
    def _create_traffic_monitoring_section(self) -> Dict[str, Any]:
        """Create the traffic monitoring section."""
        return {
            "id": "traffic_monitoring_section",
            "title": "Backend Traffic Analytics",
            "type": "mixed_layout",
            "grid": {"col_span": 12, "row_span": 4},
            "components": [
                {
                    "id": "traffic_chart",
                    "type": "chart",
                    "chart_type": "doughnut",
                    "title": "Traffic Distribution by Backend",
                    "grid": {"col_span": 6, "row_span": 2},
                    "endpoint": "/api/dashboard/analytics/traffic",
                    "data_transform": {
                        "labels_path": "data.usage_statistics",
                        "values_path": "data.usage_statistics",
                        "transform_function": "extract_backend_traffic"
                    },
                    "options": {
                        "responsive": True,
                        "plugins": {
                            "legend": {"position": "right"},
                            "tooltip": {"callbacks": {"label": "show_traffic_details"}}
                        }
                    }
                },
                {
                    "id": "backend_performance_table",
                    "type": "table",
                    "title": "Backend Performance Metrics",
                    "grid": {"col_span": 6, "row_span": 2},
                    "endpoint": "/api/dashboard/analytics/traffic",
                    "columns": [
                        {"key": "backend", "title": "Backend", "sortable": True},
                        {"key": "traffic_gb", "title": "Traffic (GB)", "sortable": True, "format": "decimal"},
                        {"key": "file_count", "title": "Files", "sortable": True},
                        {"key": "operations", "title": "Operations", "sortable": True},
                        {"key": "error_rate", "title": "Error Rate (%)", "sortable": True, "format": "percentage"},
                        {"key": "replication_efficiency", "title": "Efficiency (%)", "sortable": True, "format": "percentage"}
                    ],
                    "data_path": "data.usage_statistics",
                    "transform_function": "flatten_backend_stats"
                }
            ]
        }
    
    def _create_vfs_integration_section(self) -> Dict[str, Any]:
        """Create the VFS integration section."""
        return {
            "id": "vfs_integration_section",
            "title": "VFS Metadata Integration",
            "type": "mixed_layout",
            "grid": {"col_span": 12, "row_span": 3},
            "components": [
                {
                    "id": "vfs_mapping_summary",
                    "type": "info_panel",
                    "title": "VFS Backend Mapping Summary",
                    "grid": {"col_span": 4, "row_span": 1},
                    "endpoint": "/api/dashboard/vfs/backend_mapping",
                    "fields": [
                        {"label": "Total VFS Entries", "path": "data.summary.total_vfs_entries"},
                        {"label": "Storage Backends", "path": "data.summary.total_storage_backends"},
                        {"label": "Total Storage (GB)", "path": "data.summary.total_storage_size_gb", "format": "decimal"},
                        {"label": "Avg Replication Factor", "path": "data.summary.average_replication_factor", "format": "decimal"}
                    ]
                },
                {
                    "id": "vfs_mapping_table",
                    "type": "table",
                    "title": "VFS to Backend Mapping",
                    "grid": {"col_span": 8, "row_span": 3},
                    "endpoint": "/api/dashboard/vfs/backend_mapping",
                    "columns": [
                        {"key": "vfs_id", "title": "VFS Metadata ID", "sortable": True},
                        {"key": "cid", "title": "Content ID", "sortable": True, "truncate": 16},
                        {"key": "backends", "title": "Storage Backends", "type": "badges"},
                        {"key": "replication_count", "title": "Replicas", "sortable": True},
                        {"key": "storage_size_mb", "title": "Size (MB)", "sortable": True, "format": "decimal"},
                        {"key": "last_check", "title": "Last Check", "sortable": True, "format": "datetime"}
                    ],
                    "data_path": "data.vfs_backend_mapping",
                    "transform_function": "flatten_vfs_mapping",
                    "pagination": {"enabled": True, "page_size": 10},
                    "search": {"enabled": True, "fields": ["vfs_id", "cid"]}
                }
            ]
        }
    
    def _create_settings_section(self) -> Dict[str, Any]:
        """Create the replication settings section."""
        return {
            "id": "settings_section",
            "title": "Replication Settings",
            "type": "form",
            "grid": {"col_span": 6, "row_span": 3},
            "endpoint": "/api/dashboard/replication/settings",
            "method": "POST",
            "fields": [
                {
                    "name": "min_replicas",
                    "type": "number",
                    "label": "Minimum Replicas",
                    "default": 2,
                    "min": 1,
                    "max": 10,
                    "help": "Minimum number of replica copies to maintain"
                },
                {
                    "name": "target_replicas",
                    "type": "number",
                    "label": "Target Replicas",
                    "default": 3,
                    "min": 2,
                    "max": 10,
                    "help": "Preferred number of replica copies"
                },
                {
                    "name": "max_replicas",
                    "type": "number",
                    "label": "Maximum Replicas",
                    "default": 5,
                    "min": 3,
                    "max": 15,
                    "help": "Maximum number of replica copies allowed"
                },
                {
                    "name": "max_size_gb",
                    "type": "number",
                    "label": "Max Size per Backend (GB)",
                    "default": 100.0,
                    "min": 1.0,
                    "step": 0.1,
                    "help": "Maximum storage capacity per backend"
                },
                {
                    "name": "replication_strategy",
                    "type": "select",
                    "label": "Replication Strategy",
                    "default": "balanced",
                    "options": [
                        {"value": "balanced", "label": "Balanced"},
                        {"value": "priority", "label": "Priority-based"},
                        {"value": "size_based", "label": "Size-based"}
                    ],
                    "help": "Strategy for selecting target backends"
                },
                {
                    "name": "auto_replication",
                    "type": "checkbox",
                    "label": "Auto Replication",
                    "default": True,
                    "help": "Automatically maintain target replica counts"
                }
            ],
            "actions": [
                {"type": "submit", "label": "Update Settings", "class": "btn-primary"},
                {"type": "reset", "label": "Reset", "class": "btn-secondary"}
            ]
        }
    
    def _create_backend_management_section(self) -> Dict[str, Any]:
        """Create the backend management section."""
        return {
            "id": "backend_management_section",
            "title": "Storage Backend Management",
            "type": "mixed_layout",
            "grid": {"col_span": 6, "row_span": 3},
            "components": [
                {
                    "id": "backend_health_indicators",
                    "type": "status_grid",
                    "title": "Backend Health Status",
                    "grid": {"col_span": 6, "row_span": 1},
                    "endpoint": "/api/dashboard/replication/backends",
                    "items_path": "data.backends",
                    "status_field": "health",
                    "title_field": "name",
                    "subtitle_field": "type"
                },
                {
                    "id": "backend_capacity_chart",
                    "type": "chart",
                    "chart_type": "bar",
                    "title": "Backend Storage Utilization",
                    "grid": {"col_span": 6, "row_span": 2},
                    "endpoint": "/api/dashboard/analytics/backend_usage",
                    "data_transform": {
                        "labels_path": "data.traffic_analytics.usage_statistics",
                        "datasets": [
                            {
                                "label": "Used (GB)",
                                "data_path": "data.traffic_analytics.usage_statistics",
                                "transform": "extract_used_storage"
                            },
                            {
                                "label": "Capacity (GB)",
                                "data_path": "data.replication_status.backend_usage",
                                "transform": "extract_max_capacity"
                            }
                        ]
                    },
                    "options": {
                        "responsive": True,
                        "scales": {
                            "y": {"beginAtZero": True, "title": {"display": True, "text": "Storage (GB)"}}
                        }
                    }
                }
            ]
        }
    
    def _create_replication_operations_section(self) -> Dict[str, Any]:
        """Create the replication operations section."""
        return {
            "id": "replication_operations_section",
            "title": "Replication Operations",
            "type": "mixed_layout",
            "grid": {"col_span": 12, "row_span": 4},
            "components": [
                {
                    "id": "manual_replication_form",
                    "type": "form",
                    "title": "Manual Replication",
                    "grid": {"col_span": 4, "row_span": 2},
                    "endpoint": "/api/dashboard/replication/pins/{cid}/replicate",
                    "method": "POST",
                    "fields": [
                        {
                            "name": "cid",
                            "type": "text",
                            "label": "Content ID (CID)",
                            "required": True,
                            "placeholder": "Qm..."
                        },
                        {
                            "name": "vfs_metadata_id",
                            "type": "text",
                            "label": "VFS Metadata ID",
                            "placeholder": "Optional VFS linking"
                        },
                        {
                            "name": "target_backends",
                            "type": "multiselect",
                            "label": "Target Backends",
                            "options_endpoint": "/api/dashboard/replication/backends",
                            "value_field": "name",
                            "label_field": "name"
                        },
                        {
                            "name": "force",
                            "type": "checkbox",
                            "label": "Force Replication",
                            "help": "Override existing replications"
                        }
                    ],
                    "actions": [
                        {"type": "submit", "label": "Start Replication", "class": "btn-success"}
                    ]
                },
                {
                    "id": "pin_status_table",
                    "type": "table",
                    "title": "Pin Replication Status",
                    "grid": {"col_span": 8, "row_span": 4},
                    "endpoint": "/api/dashboard/replication/status",
                    "columns": [
                        {"key": "cid", "title": "Content ID", "sortable": True, "truncate": 16},
                        {"key": "vfs_metadata_id", "title": "VFS ID", "sortable": True},
                        {"key": "backends", "title": "Storage Backends", "type": "badges"},
                        {"key": "replication_health", "title": "Health", "type": "status_badge"},
                        {"key": "replica_count", "title": "Replicas", "sortable": True},
                        {"key": "last_check", "title": "Last Check", "sortable": True, "format": "datetime"},
                        {"key": "actions", "title": "Actions", "type": "actions"}
                    ],
                    "data_path": "data.pins",
                    "pagination": {"enabled": True, "page_size": 15},
                    "search": {"enabled": True, "fields": ["cid", "vfs_metadata_id"]},
                    "actions": [
                        {"type": "replicate", "label": "Replicate", "class": "btn-sm btn-primary"},
                        {"type": "analyze", "label": "Analyze", "class": "btn-sm btn-info"}
                    ]
                }
            ]
        }
    
    def _create_data_protection_section(self) -> Dict[str, Any]:
        """Create the data protection section."""
        return {
            "id": "data_protection_section",
            "title": "Data Protection & Backup",
            "type": "mixed_layout",
            "grid": {"col_span": 12, "row_span": 3},
            "components": [
                {
                    "id": "backup_operations",
                    "type": "form_group",
                    "title": "Backup Operations",
                    "grid": {"col_span": 6, "row_span": 3},
                    "forms": [
                        {
                            "id": "export_form",
                            "title": "Export Backend Pins",
                            "endpoint": "/api/dashboard/backup/{backend}/export",
                            "method": "POST",
                            "fields": [
                                {
                                    "name": "backend",
                                    "type": "select",
                                    "label": "Backend",
                                    "options_endpoint": "/api/dashboard/replication/backends",
                                    "value_field": "name",
                                    "label_field": "name",
                                    "required": True
                                },
                                {
                                    "name": "backup_path",
                                    "type": "text",
                                    "label": "Backup Path",
                                    "placeholder": "/path/to/backup.json"
                                },
                                {
                                    "name": "include_metadata",
                                    "type": "checkbox",
                                    "label": "Include Metadata",
                                    "default": True
                                }
                            ],
                            "actions": [
                                {"type": "submit", "label": "Export Backup", "class": "btn-warning"}
                            ]
                        },
                        {
                            "id": "import_form",
                            "title": "Import Backend Pins",
                            "endpoint": "/api/dashboard/backup/{backend}/import",
                            "method": "POST",
                            "fields": [
                                {
                                    "name": "backend",
                                    "type": "select",
                                    "label": "Target Backend",
                                    "options_endpoint": "/api/dashboard/replication/backends",
                                    "value_field": "name",
                                    "label_field": "name",
                                    "required": True
                                },
                                {
                                    "name": "backup_path",
                                    "type": "text",
                                    "label": "Backup File Path",
                                    "required": True,
                                    "placeholder": "/path/to/backup.json"
                                }
                            ],
                            "actions": [
                                {"type": "submit", "label": "Import Backup", "class": "btn-success"}
                            ]
                        }
                    ]
                },
                {
                    "id": "backup_list",
                    "type": "table",
                    "title": "Available Backups",
                    "grid": {"col_span": 6, "row_span": 3},
                    "endpoint": "/api/dashboard/backup/list",
                    "columns": [
                        {"key": "backend_name", "title": "Backend", "sortable": True},
                        {"key": "backup_path", "title": "Backup Path", "sortable": True, "truncate": 30},
                        {"key": "pins_count", "title": "Pins", "sortable": True},
                        {"key": "backup_size_mb", "title": "Size (MB)", "sortable": True, "format": "decimal"},
                        {"key": "created_date", "title": "Created", "sortable": True, "format": "datetime"},
                        {"key": "actions", "title": "Actions", "type": "actions"}
                    ],
                    "data_path": "data.backups",
                    "actions": [
                        {"type": "verify", "label": "Verify", "class": "btn-sm btn-info"},
                        {"type": "restore", "label": "Restore", "class": "btn-sm btn-success"}
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
                "description": "Get replication status overview with traffic analytics"
            },
            {
                "endpoint": "/api/dashboard/analytics/traffic",
                "method": "GET",
                "description": "Get comprehensive traffic analytics for all backends"
            },
            {
                "endpoint": "/api/dashboard/analytics/traffic/{backend}",
                "method": "GET",
                "description": "Get traffic analytics for specific backend"
            },
            {
                "endpoint": "/api/dashboard/vfs/backend_mapping",
                "method": "GET",
                "description": "Get VFS metadata to backend storage mapping"
            },
            {
                "endpoint": "/api/dashboard/analytics/backend_usage",
                "method": "GET",
                "description": "Get comprehensive backend usage summary"
            },
            {
                "endpoint": "/api/dashboard/vfs/link_backend",
                "method": "POST",
                "description": "Link VFS metadata to backend storage locations"
            },
            {
                "endpoint": "/api/dashboard/replication/settings",
                "method": "GET/POST",
                "description": "Get/update enhanced replication settings"
            },
            {
                "endpoint": "/api/dashboard/replication/pins/{cid}/replicate",
                "method": "POST",
                "description": "Replicate specific pin with VFS linking"
            },
            {
                "endpoint": "/api/dashboard/replication/backends",
                "method": "GET",
                "description": "Get backend capabilities and health status"
            },
            {
                "endpoint": "/api/dashboard/backup/{backend}/export",
                "method": "POST",
                "description": "Export pins from backend to backup with traffic tracking"
            },
            {
                "endpoint": "/api/dashboard/backup/{backend}/import",
                "method": "POST",
                "description": "Import pins from backup to backend with traffic tracking"
            },
            {
                "endpoint": "/api/dashboard/backup/verify",
                "method": "POST",
                "description": "Verify backup file integrity"
            }
        ]
    
    def export_config(self, file_path: str = "/tmp/enhanced_replication_dashboard_panel.json") -> str:
        """Export panel configuration to JSON file."""
        with open(file_path, 'w') as f:
            json.dump(self.panel_config, f, indent=2)
        return file_path
    
    def get_config(self) -> Dict[str, Any]:
        """Get the panel configuration dictionary."""
        return self.panel_config

# Usage example
if __name__ == "__main__":
    panel = EnhancedReplicationDashboardPanel()
    config_path = panel.export_config()
    print(f"✓ Enhanced replication dashboard panel configuration exported to: {config_path}")
    print("\n📋 Enhanced Panel Features:")
    print("• Real-time traffic monitoring and analytics")
    print("• VFS metadata to backend storage mapping")
    print("• Comprehensive backend usage tracking")
    print("• File transfer counters and operation statistics")
    print("• Enhanced replication settings with traffic insights")
    print("• Interactive pin management with VFS integration")
    print("• Backend health and capacity monitoring")
    print("• Data protection with traffic-aware backup/restore")
    print("• Cross-backend pin tracking with analytics")
    print("• Performance optimization recommendations")
