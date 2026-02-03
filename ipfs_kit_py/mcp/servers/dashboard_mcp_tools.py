"""
Dashboard MCP Tools

Minimal MCP tool handlers for dashboard integration tests.
"""

from typing import Any, Dict
from ipfs_kit_py.dashboard_widgets import WidgetManager, WidgetConfig
from ipfs_kit_py.dashboard_charts import ChartGenerator, ChartConfig
from ipfs_kit_py.config_wizards import WizardManager

_widget_manager = WidgetManager()
_chart_generator = ChartGenerator()
_wizard_manager = WizardManager()


def dashboard_get_widget_data() -> Dict[str, Any]:
    return {"success": True, "widgets": _widget_manager.get_all_widget_data()}


def dashboard_get_chart_data() -> Dict[str, Any]:
    return {"success": True, "charts": []}


def dashboard_get_operations_history() -> Dict[str, Any]:
    return {"success": True, "operations": []}


def dashboard_run_wizard(wizard_type: str = "backend_setup") -> Dict[str, Any]:
    wizard = _wizard_manager.create_wizard(wizard_type)
    return {"success": True, "wizard_type": wizard.config.wizard_type, "steps": len(wizard.steps)}


def dashboard_get_status_summary() -> Dict[str, Any]:
    return {"success": True, "status": "ok"}


__all__ = [
    "dashboard_get_widget_data",
    "dashboard_get_chart_data",
    "dashboard_get_operations_history",
    "dashboard_run_wizard",
    "dashboard_get_status_summary",
]
