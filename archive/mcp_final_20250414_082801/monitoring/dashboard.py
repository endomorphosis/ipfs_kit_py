"""
Dashboard API for MCP server monitoring.

This module implements the dashboard API component for metrics visualization
as specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TimeRange(BaseModel):
    """Time range for dashboard queries."""

    start: float = Field(..., description="Start timestamp in seconds")
    end: float = Field(..., description="End timestamp in seconds")
    step: str = Field("1m", description="Step size (e.g., 15s, 1m, 5m, 1h)")


class DashboardPanel(BaseModel):
    """Dashboard panel configuration."""

    id: str = Field(..., description="Panel ID")
    title: str = Field(..., description="Panel title")
    description: Optional[str] = Field(None, description="Panel description")
    type: str = Field(..., description="Panel type: chart, gauge, stat, table")
    queries: List[Dict[str, Any]] = Field(..., description="Panel queries")
    options: Dict[str, Any] = Field(default_factory=dict, description="Panel options")


class Dashboard(BaseModel):
    """Dashboard configuration."""

    id: str = Field(..., description="Dashboard ID")
    title: str = Field(..., description="Dashboard title")
    description: Optional[str] = Field(None, description="Dashboard description")
    panels: List[DashboardPanel] = Field(..., description="Dashboard panels")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Dashboard variables")
    refresh_interval: str = Field("1m", description="Dashboard refresh interval")
    time_range: Dict[str, Any] = Field(default_factory=dict, description="Default time range")


class DashboardService:
    """
    Service for managing dashboards and providing metrics data.

    This service provides APIs for creating, updating, and retrieving dashboards,
    as well as querying metrics data for dashboard visualization.
    """

    def __init__(self, prometheus_url: str = "http://localhost:9090/api/v1"):
        """
        Initialize the dashboard service.

        Args:
            prometheus_url: URL of the Prometheus API
        """
        self.prometheus_url = prometheus_url

        # Dashboard storage
        self.dashboards: Dict[str, Dashboard] = {}

        # Default dashboards
        self.default_dashboards_file = "/tmp/ipfs_kit/mcp/monitoring/dashboards.json"

        # Dashboard presets
        self._presets = {}

    async def start(self):
        """Start the dashboard service."""
        logger.info("Starting dashboard service")

        # Create data directories
        import os

        os.makedirs(os.path.dirname(self.default_dashboards_file), exist_ok=True)

        # Create default dashboards
        await self._create_default_dashboards()

        # Load existing dashboards
        await self.load_dashboards()

        logger.info("Dashboard service started")

    async def stop(self):
        """Stop the dashboard service."""
        logger.info("Stopping dashboard service")

        # Save dashboards
        await self.save_dashboards()

        logger.info("Dashboard service stopped")

    async def load_dashboards(self):
        """Load dashboards from storage."""
        try:
            import os

            if os.path.exists(self.default_dashboards_file):
                import aiofiles

                async with aiofiles.open(self.default_dashboards_file, "r") as f:
                    content = await f.read()
                    dashboards_data = json.loads(content)

                    for dashboard_data in dashboards_data:
                        dashboard = Dashboard(**dashboard_data)
                        self.dashboards[dashboard.id] = dashboard

                    logger.info(f"Loaded {len(self.dashboards)} dashboards")
            else:
                logger.info("No dashboards file found, using default dashboards")
        except Exception as e:
            logger.error(f"Error loading dashboards: {e}")

    async def save_dashboards(self):
        """Save dashboards to storage."""
        try:
            dashboards_data = [dashboard.dict() for dashboard in self.dashboards.values()]

            import aiofiles

            async with aiofiles.open(self.default_dashboards_file, "w") as f:
                await f.write(json.dumps(dashboards_data, indent=2))

            logger.info(f"Saved {len(dashboards_data)} dashboards")
        except Exception as e:
            logger.error(f"Error saving dashboards: {e}")

    async def _create_default_dashboards(self):
        """Create default dashboards if they don't exist."""
        try:
            # Create system overview dashboard
            self._presets["system_overview"] = Dashboard(
                id="system_overview",
                title="System Overview",
                description="Overview of system metrics",
                panels=[
                    DashboardPanel(
                        id="cpu_usage",
                        title="CPU Usage",
                        type="chart",
                        queries=[{"expr": "mcp_cpu_usage_percent", "legend": "CPU Usage (%)"}],
                        options={
                            "unit": "percent",
                            "min": 0
                            "max": 100
                            "thresholds": [
                                {"value": 80, "color": "red"},
                                {"value": 60, "color": "yellow"},
                                {"value": 0, "color": "green"},
                            ],
                        },
                    ),
                    DashboardPanel(
                        id="memory_usage",
                        title="Memory Usage",
                        type="chart",
                        queries=[
                            {
                                "expr": "mcp_memory_usage_bytes / mcp_memory_total_bytes * 100",
                                "legend": "Memory Usage (%)",
                            }
                        ],
                        options={"unit": "percent", "min": 0, "max": 100},
                    ),
                    DashboardPanel(
                        id="disk_usage",
                        title="Disk Usage",
                        type="chart",
                        queries=[
                            {
                                "expr": 'mcp_disk_usage_bytes{mountpoint="/"} / mcp_disk_total_bytes{mountpoint="/"} * 100',
                                "legend": "Disk Usage (%)",
                            }
                        ],
                        options={"unit": "percent", "min": 0, "max": 100},
                    ),
                    DashboardPanel(
                        id="http_requests",
                        title="HTTP Requests",
                        type="chart",
                        queries=[
                            {
                                "expr": "rate(mcp_http_requests_total[5m])",
                                "legend": "Requests/sec",
                            }
                        ],
                        options={"unit": "requests/s"},
                    ),
                ],
                time_range={"from": "now-1h", "to": "now"},
            )

            # Create backend overview dashboard
            self._presets["backend_overview"] = Dashboard(
                id="backend_overview",
                title="Storage Backend Overview",
                description="Overview of storage backend metrics",
                panels=[
                    DashboardPanel(
                        id="backend_status",
                        title="Backend Status",
                        type="stat",
                        queries=[{"expr": "mcp_backend_status", "legend": "Status"}],
                        options={
                            "colorMode": "value",
                            "thresholds": [
                                {"value": 0, "color": "red"},
                                {"value": 1, "color": "green"},
                            ],
                        },
                    ),
                    DashboardPanel(
                        id="backend_operations",
                        title="Backend Operations",
                        type="chart",
                        queries=[
                            {
                                "expr": "rate(mcp_backend_operations_total[5m])",
                                "legend": "{{backend}} - {{operation}}",
                            }
                        ],
                        options={"unit": "ops/s"},
                    ),
                    DashboardPanel(
                        id="backend_latency",
                        title="Backend Operation Latency",
                        type="chart",
                        queries=[
                            {
                                "expr": "rate(mcp_backend_operation_duration_seconds_sum[5m]) / rate(mcp_backend_operation_duration_seconds_count[5m])",
                                "legend": "{{backend}} - {{operation}}",
                            }
                        ],
                        options={"unit": "seconds"},
                    ),
                    DashboardPanel(
                        id="backend_items",
                        title="Items per Backend",
                        type="chart",
                        queries=[{"expr": "mcp_backend_items_count", "legend": "{{backend}}"}],
                        options={"unit": "items"},
                    ),
                ],
                variables={
                    "backend": {
                        "query": "label_values(mcp_backend_status, backend)",
                        "multi": True
                        "includeAll": True
                    }
                },
                time_range={"from": "now-6h", "to": "now"},
            )

            # Create migration dashboard
            self._presets["migration_dashboard"] = Dashboard(
                id="migration_dashboard",
                title="Data Migration",
                description="Migration metrics and statistics",
                panels=[
                    DashboardPanel(
                        id="migrations_in_progress",
                        title="Migrations In Progress",
                        type="stat",
                        queries=[
                            {
                                "expr": "mcp_migration_in_progress",
                                "legend": "In Progress",
                            }
                        ],
                        options={},
                    ),
                    DashboardPanel(
                        id="migration_operations",
                        title="Migration Operations",
                        type="chart",
                        queries=[
                            {
                                "expr": "sum(rate(mcp_migration_operations_total[5m])) by (operation, status)",
                                "legend": "{{operation}} - {{status}}",
                            }
                        ],
                        options={"unit": "ops/s"},
                    ),
                    DashboardPanel(
                        id="migration_bytes",
                        title="Data Migrated",
                        type="chart",
                        queries=[
                            {
                                "expr": "sum(rate(mcp_migration_bytes_total[5m])) by (source, target)",
                                "legend": "{{source}} → {{target}}",
                            }
                        ],
                        options={"unit": "bytes/s"},
                    ),
                    DashboardPanel(
                        id="migration_duration",
                        title="Migration Duration",
                        type="chart",
                        queries=[
                            {
                                "expr": "rate(mcp_migration_duration_seconds_sum[5m]) / rate(mcp_migration_duration_seconds_count[5m])",
                                "legend": "{{source}} → {{target}}",
                            }
                        ],
                        options={"unit": "seconds"},
                    ),
                ],
                time_range={"from": "now-24h", "to": "now"},
            )

            # Create cache overview dashboard
            self._presets["cache_dashboard"] = Dashboard(
                id="cache_dashboard",
                title="Cache Performance",
                description="Cache metrics and statistics",
                panels=[
                    DashboardPanel(
                        id="cache_hit_ratio",
                        title="Cache Hit Ratio",
                        type="chart",
                        queries=[
                            {
                                "expr": "sum(rate(mcp_cache_hit_total[5m])) by (cache_type) / (sum(rate(mcp_cache_hit_total[5m])) by (cache_type) + sum(rate(mcp_cache_miss_total[5m])) by (cache_type))",
                                "legend": "{{cache_type}}",
                            }
                        ],
                        options={"unit": "percentunit", "min": 0, "max": 1},
                    ),
                    DashboardPanel(
                        id="cache_size",
                        title="Cache Size",
                        type="chart",
                        queries=[{"expr": "mcp_cache_size", "legend": "{{cache_type}}"}],
                        options={"unit": "items"},
                    ),
                    DashboardPanel(
                        id="cache_bytes",
                        title="Cache Memory Usage",
                        type="chart",
                        queries=[{"expr": "mcp_cache_bytes", "legend": "{{cache_type}}"}],
                        options={"unit": "bytes"},
                    ),
                    DashboardPanel(
                        id="cache_operations",
                        title="Cache Operations",
                        type="chart",
                        queries=[
                            {
                                "expr": "sum(rate(mcp_cache_hit_total[5m])) by (cache_type)",
                                "legend": "{{cache_type}} Hits",
                            },
                            {
                                "expr": "sum(rate(mcp_cache_miss_total[5m])) by (cache_type)",
                                "legend": "{{cache_type}} Misses",
                            },
                        ],
                        options={"unit": "ops/s"},
                    ),
                ],
                variables={
                    "cache_type": {
                        "query": "label_values(mcp_cache_size, cache_type)",
                        "multi": True
                        "includeAll": True
                    }
                },
                time_range={"from": "now-6h", "to": "now"},
            )

            logger.info("Created default dashboard presets")
        except Exception as e:
            logger.error(f"Error creating default dashboards: {e}")

    async def create_dashboard(self, dashboard: Dashboard) -> Dashboard:
        """
        Create a new dashboard.

        Args:
            dashboard: Dashboard to create

        Returns:
            Created dashboard
        """
        if dashboard.id in self.dashboards:
            raise ValueError(f"Dashboard with ID {dashboard.id} already exists")

        self.dashboards[dashboard.id] = dashboard
        await self.save_dashboards()

        return dashboard

    async def update_dashboard(self, dashboard_id: str, dashboard: Dashboard) -> Dashboard:
        """
        Update an existing dashboard.

        Args:
            dashboard_id: ID of dashboard to update
            dashboard: Updated dashboard

        Returns:
            Updated dashboard
        """
        if dashboard_id not in self.dashboards:
            raise ValueError(f"Dashboard with ID {dashboard_id} not found")

        if dashboard_id != dashboard.id:
            # ID has changed, delete old dashboard
            del self.dashboards[dashboard_id]

        self.dashboards[dashboard.id] = dashboard
        await self.save_dashboards()

        return dashboard

    async def delete_dashboard(self, dashboard_id: str) -> bool:
        """
        Delete a dashboard.

        Args:
            dashboard_id: ID of dashboard to delete

        Returns:
            True if dashboard was deleted
        """
        if dashboard_id not in self.dashboards:
            return False

        del self.dashboards[dashboard_id]
        await self.save_dashboards()

        return True

    async def get_dashboard(self, dashboard_id: str) -> Optional[Dashboard]:
        """
        Get a dashboard by ID.

        Args:
            dashboard_id: Dashboard ID

        Returns:
            Dashboard or None if not found
        """
        # Check for preset dashboards
        if dashboard_id in self._presets and dashboard_id not in self.dashboards:
            self.dashboards[dashboard_id] = self._presets[dashboard_id]
            await self.save_dashboards()

        return self.dashboards.get(dashboard_id)

    async def list_dashboards(self) -> List[Dict[str, Any]]:
        """
        Get a list of all dashboards.

        Returns:
            List of dashboard summaries
        """
        # Add presets that aren't already in the dashboards
        for preset_id, preset in self._presets.items():
            if preset_id not in self.dashboards:
                self.dashboards[preset_id] = preset

        # Create dashboard summary list
        dashboard_list = []
        for dashboard in self.dashboards.values():
            dashboard_list.append(
                {
                    "id": dashboard.id,
                    "title": dashboard.title,
                    "description": dashboard.description,
                    "panel_count": len(dashboard.panels),
                }
            )

        return dashboard_list

    async def get_dashboard_data(
        self, dashboard_id: str, time_range: Optional[TimeRange] = None
    ) -> Dict[str, Any]:
        """
        Get data for a dashboard.

        Args:
            dashboard_id: Dashboard ID
            time_range: Optional time range for data

        Returns:
            Dashboard with panel data
        """
        dashboard = await self.get_dashboard(dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard with ID {dashboard_id} not found")

        # Convert dashboard to dict for modification
        dashboard_dict = dashboard.dict()

        # Set time range if provided
        if time_range:
            actual_time_range = {
                "start": time_range.start,
                "end": time_range.end,
                "step": time_range.step,
            }
        else:
            # Use dashboard's default time range
            default_range = dashboard.time_range

            # Parse dashboard time range
            now = time.time()
            if (
                isinstance(default_range, dict)
                and "from" in default_range
                and "to" in default_range
            ):
                from_str = default_range["from"]
                to_str = default_range["to"]

                # Parse relative time ranges
                start_time = self._parse_time_string(from_str, now)
                end_time = self._parse_time_string(to_str, now)

                actual_time_range = {
                    "start": start_time
                    "end": end_time
                    "step": "1m",  # Default step
                }
            else:
                # Default to last hour
                actual_time_range = {"start": now - 3600, "end": now, "step": "1m"}

        # Add data to each panel
        for i, panel in enumerate(dashboard_dict["panels"]):
            panel_data = await self._get_panel_data(panel, actual_time_range)
            dashboard_dict["panels"][i]["data"] = panel_data

        # Add time range to dashboard
        dashboard_dict["actual_time_range"] = actual_time_range

        return dashboard_dict

    def _parse_time_string(self, time_str: str, now: float) -> float:
        """
        Parse a time string into a timestamp.

        Args:
            time_str: Time string (e.g., "now-1h", "now+30m", or absolute timestamp)
            now: Current timestamp

        Returns:
            Timestamp in seconds
        """
        if time_str == "now":
            return now

        if time_str.startswith("now"):
            # Relative time
            if "+" in time_str:
                offset_str = time_str.split("+")[1]
                offset = self._parse_duration(offset_str)
                return now + offset
            elif "-" in time_str:
                offset_str = time_str.split("-")[1]
                offset = self._parse_duration(offset_str)
                return now - offset

        # Try to parse as absolute timestamp
        try:
            return float(time_str)
        except ValueError:
            # If all else fails, return now
            return now

    def _parse_duration(self, duration_str: str) -> float:
        """
        Parse a duration string into seconds.

        Args:
            duration_str: Duration string (e.g., "1h", "30m", "15s")

        Returns:
            Duration in seconds
        """
        if not duration_str:
            return 0

        # Extract number and unit
        num = ""
        unit = ""
        for char in duration_str:
            if char.isdigit() or char == ".":
                num += char
            else:
                unit += char

        if not num:
            return 0

        value = float(num)

        if unit == "s":
            return value
        elif unit == "m":
            return value * 60
        elif unit == "h":
            return value * 3600
        elif unit == "d":
            return value * 86400
        elif unit == "w":
            return value * 604800
        else:
            return value

    def _parse_step(self, step_str: str) -> int:
        """
        Parse a step string into seconds.

        Args:
            step_str: Step string (e.g., "15s", "1m", "5m")

        Returns:
            Step in seconds
        """
        return int(self._parse_duration(step_str))

    async def _get_panel_data(
        self, panel: Dict[str, Any], time_range: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get data for a dashboard panel.

        Args:
            panel: Panel configuration
            time_range: Time range for data

        Returns:
            Panel data
        """
        panel_data = {"series": []}

        # Process each query
        for query in panel["queries"]:
            # Get query expression
            expr = query.get("expr", "")
            if not expr:
                continue

            # Get legend format
            legend_format = query.get("legend", "")

            # Query Prometheus
            series_data = await self._query_prometheus_range(
                expr, time_range["start"], time_range["end"], time_range["step"]
            )

            # Add to panel data
            for series in series_data:
                # Format legend
                if legend_format:
                    # Replace label placeholders
                    legend = legend_format
                    for label, value in series["metric"].items():
                        legend = legend.replace(f"{{{{{label}}}}}", value)
                else:
                    # Default legend
                    metric_str = ""
                    for label, value in series["metric"].items():
                        if label != "__name__":
                            metric_str += f"{label}={value}, "
                    legend = metric_str.rstrip(", ")

                # Add series to panel data
                panel_data["series"].append(
                    {
                        "name": legend
                        "metric": series["metric"],
                        "values": series["values"],
                    }
                )

        return panel_data

    async def _query_prometheus_range(
        self, query: str, start: float, end: float, step: str
    ) -> List[Dict[str, Any]]:
        """
        Query Prometheus for a range of data.

        Args:
            query: PromQL query
            start: Start timestamp
            end: End timestamp
            step: Step size

        Returns:
            List of time series data
        """
        url = f"{self.prometheus_url}/query_range"

        # Convert step string to seconds
        step_seconds = self._parse_step(step)

        params = {"query": query, "start": start, "end": end, "step": step_seconds}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Prometheus range query error: {error_text}")
                        return []

                    data = await response.json()

                    if data["status"] != "success":
                        logger.error(
                            f"Prometheus range query failed: {data.get('error', 'Unknown error')}"
                        )
                        return []

                    # Process result
                    result_type = data["data"]["resultType"]

                    if result_type == "matrix":
                        return data["data"]["result"]
                    else:
                        logger.warning(f"Unsupported result type: {result_type}")
                        return []
        except Exception as e:
            logger.error(f"Error querying Prometheus range: {e}")
            return []

    async def _query_prometheus(self, query: str) -> List[Dict[str, Any]]:
        """
        Query Prometheus for instant data.

        Args:
            query: PromQL query

        Returns:
            List of instant data
        """
        url = f"{self.prometheus_url}/query"
        params = {"query": query}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Prometheus query error: {error_text}")
                        return []

                    data = await response.json()

                    if data["status"] != "success":
                        logger.error(
                            f"Prometheus query failed: {data.get('error', 'Unknown error')}"
                        )
                        return []

                    # Process result
                    result_type = data["data"]["resultType"]

                    if result_type == "vector":
                        return data["data"]["result"]
                    else:
                        logger.warning(f"Unsupported result type: {result_type}")
                        return []
        except Exception as e:
            logger.error(f"Error querying Prometheus: {e}")
            return []

    async def get_metric_labels(self, metric_name: str) -> List[str]:
        """
        Get all label names for a metric.

        Args:
            metric_name: Metric name

        Returns:
            List of label names
        """
        try:
            url = f"{self.prometheus_url}/labels"
            params = {"match[]": metric_name}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()

                    if data["status"] != "success":
                        return []

                    return data["data"]
        except Exception as e:
            logger.error(f"Error getting metric labels: {e}")
            return []

    async def get_label_values(
        self, label_name: str, metric_name: Optional[str] = None
    ) -> List[str]:
        """
        Get all values for a label.

        Args:
            label_name: Label name
            metric_name: Optional metric name to filter by

        Returns:
            List of label values
        """
        try:
            url = f"{self.prometheus_url}/label/{label_name}/values"
            params = {}

            if metric_name:
                params["match[]"] = metric_name

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()

                    if data["status"] != "success":
                        return []

                    return data["data"]
        except Exception as e:
            logger.error(f"Error getting label values: {e}")
            return []


def create_dashboard_router(dashboard_service: DashboardService) -> APIRouter:
    """
    Create a FastAPI router for dashboard endpoints.

    Args:
        dashboard_service: Dashboard service instance

    Returns:
        FastAPI router
    """
    router = APIRouter(prefix="/api/v0/dashboards", tags=["dashboards"])

    @router.get("/")
    async def list_dashboards_v2():
        """List all dashboards."""
        try:
            dashboards = await dashboard_service.list_dashboards()
            return {"success": True, "dashboards": dashboards}
        except Exception as e:
            logger.error(f"Error listing dashboards: {e}")
            return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

    @router.post("/")
    async def create_dashboard_v2(dashboard: Dashboard):
        """Create a new dashboard."""
        try:
            result = await dashboard_service.create_dashboard(dashboard)
            return {"success": True, "dashboard": result}
        except ValueError as e:
            return JSONResponse(status_code=400, content={"success": False, "error": str(e)})
        except Exception as e:
            logger.error(f"Error creating dashboard: {e}")
            return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

    @router.get("/{dashboard_id}")
    async def get_dashboard_v2(dashboard_id: str):
        """Get a dashboard by ID."""
        try:
            dashboard = await dashboard_service.get_dashboard(dashboard_id)
            if not dashboard:
                return JSONResponse(
                    status_code=404,
                    content={
                        "success": False
                        "error": f"Dashboard '{dashboard_id}' not found",
                    },
                )
            return {"success": True, "dashboard": dashboard}
        except Exception as e:
            logger.error(f"Error getting dashboard: {e}")
            return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

    @router.put("/{dashboard_id}")
    async def update_dashboard_v2(dashboard_id: str, dashboard: Dashboard):
        """Update a dashboard."""
        try:
            result = await dashboard_service.update_dashboard(dashboard_id, dashboard)
            return {"success": True, "dashboard": result}
        except ValueError as e:
            return JSONResponse(status_code=400, content={"success": False, "error": str(e)})
        except Exception as e:
            logger.error(f"Error updating dashboard: {e}")
            return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

    @router.delete("/{dashboard_id}")
    async def delete_dashboard_v2(dashboard_id: str):
        """Delete a dashboard."""
        try:
            result = await dashboard_service.delete_dashboard(dashboard_id)
            if not result:
                return JSONResponse(
                    status_code=404,
                    content={
                        "success": False
                        "error": f"Dashboard '{dashboard_id}' not found",
                    },
                )
            return {"success": True, "message": f"Dashboard '{dashboard_id}' deleted"}
        except Exception as e:
            logger.error(f"Error deleting dashboard: {e}")
            return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

    @router.get("/{dashboard_id}/data")
    async def get_dashboard_data_v2(
        dashboard_id: str
        start: Optional[float] = Query(None, description="Start timestamp"),
        end: Optional[float] = Query(None, description="End timestamp"),
        step: Optional[str] = Query("1m", description="Step size"),
    ):
        """Get data for a dashboard."""
        try:
            # Create time range if start and end are provided
            time_range = None
            if start is not None and end is not None:
                time_range = TimeRange(start=start, end=end, step=step)

            data = await dashboard_service.get_dashboard_data(dashboard_id, time_range)
            return {"success": True, "dashboard": data}
        except ValueError as e:
            return JSONResponse(status_code=404, content={"success": False, "error": str(e)})
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

    @router.get("/metrics/labels")
    async def get_metric_labels_v2(metric: str):
        """Get all label names for a metric."""
        try:
            labels = await dashboard_service.get_metric_labels(metric)
            return {"success": True, "labels": labels}
        except Exception as e:
            logger.error(f"Error getting metric labels: {e}")
            return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

    @router.get("/metrics/label-values/{label}")
    async def get_label_values_v2(
        label: str
        metric: Optional[str] = Query(None, description="Optional metric to filter by"),
    ):
        """Get all values for a label."""
        try:
            values = await dashboard_service.get_label_values(label, metric)
            return {"success": True, "values": values}
        except Exception as e:
            logger.error(f"Error getting label values: {e}")
            return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

    return router
