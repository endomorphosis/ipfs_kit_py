"""
Configuration Wizards for Dashboard Enhancements (Phase 10).

Lightweight wizard framework to support dashboard configuration flows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WizardConfig:
    """Configuration for a wizard instance."""

    wizard_id: str
    wizard_type: str
    title: str
    description: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WizardStep:
    """Represents a single wizard step."""

    step_id: str
    title: str
    description: str
    fields: Dict[str, Any] = field(default_factory=dict)
    validator: Optional[Callable[[Dict[str, Any]], bool]] = None


@dataclass
class WizardState:
    """State tracking for a wizard session."""

    wizard_id: str
    current_step_index: int
    completed: bool
    updated_at: datetime
    data: Dict[str, Any] = field(default_factory=dict)


class Wizard:
    """Base class for all configuration wizards."""

    def __init__(self, config: WizardConfig, steps: Optional[List[WizardStep]] = None):
        self.config = config
        self.steps: List[WizardStep] = steps or []
        self._current_step_index = 0
        self._data: Dict[str, Any] = {}

        logger.info("Wizard initialized: %s (%s)", config.wizard_id, config.wizard_type)

    def get_state(self) -> WizardState:
        """Return current wizard state."""

        return WizardState(
            wizard_id=self.config.wizard_id,
            current_step_index=self._current_step_index,
            completed=self._current_step_index >= max(len(self.steps) - 1, 0),
            updated_at=datetime.now(),
            data=dict(self._data),
        )

    def add_step(self, step: WizardStep) -> None:
        self.steps.append(step)

    def set_data(self, **values: Any) -> None:
        self._data.update(values)


class BackendSetupWizard(Wizard):
    """Wizard for storage backend setup."""

    def __init__(self):
        config = WizardConfig(
            wizard_id="backend_setup",
            wizard_type="backend_setup",
            title="Backend Setup",
            description="Configure IPFS storage backends",
        )
        steps = [
            WizardStep(
                step_id="select_backend",
                title="Select Backend",
                description="Choose the storage backend type",
            ),
            WizardStep(
                step_id="configure_backend",
                title="Configure Backend",
                description="Provide connection settings",
            ),
            WizardStep(
                step_id="validate_backend",
                title="Validate",
                description="Validate backend connectivity",
            ),
        ]
        super().__init__(config=config, steps=steps)


class VFSConfigurationWizard(Wizard):
    """Wizard for VFS configuration."""

    def __init__(self):
        config = WizardConfig(
            wizard_id="vfs_config",
            wizard_type="vfs_config",
            title="VFS Configuration",
            description="Configure VFS mounts and policies",
        )
        steps = [
            WizardStep(
                step_id="mount_points",
                title="Mount Points",
                description="Define mount points and paths",
            ),
            WizardStep(
                step_id="cache_policy",
                title="Cache Policy",
                description="Configure caching behavior",
            ),
        ]
        super().__init__(config=config, steps=steps)


class MonitoringSetupWizard(Wizard):
    """Wizard for monitoring setup."""

    def __init__(self):
        config = WizardConfig(
            wizard_id="monitoring_setup",
            wizard_type="monitoring_setup",
            title="Monitoring Setup",
            description="Configure monitoring and alerts",
        )
        steps = [
            WizardStep(
                step_id="metrics",
                title="Metrics",
                description="Enable metrics collection",
            ),
            WizardStep(
                step_id="alerts",
                title="Alerts",
                description="Configure alert thresholds",
            ),
        ]
        super().__init__(config=config, steps=steps)


class WizardManager:
    """Factory/manager for configuration wizards."""

    def __init__(self):
        self._registry = {
            "backend_setup": BackendSetupWizard,
            "vfs_config": VFSConfigurationWizard,
            "monitoring_setup": MonitoringSetupWizard,
        }

    def create_wizard(self, wizard_type: str) -> Wizard:
        """Create a wizard instance for a given type."""

        wizard_cls = self._registry.get(wizard_type)
        if not wizard_cls:
            raise ValueError(f"Unknown wizard type: {wizard_type}")
        return wizard_cls()


__all__ = [
    "WizardManager",
    "Wizard",
    "WizardStep",
    "WizardConfig",
    "WizardState",
    "BackendSetupWizard",
    "VFSConfigurationWizard",
    "MonitoringSetupWizard",
]
