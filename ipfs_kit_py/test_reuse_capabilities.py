"""Lazy, bounded facts for optional Kubo, Lotus, and Iroh integrations.

Discovery is intentionally cold: it checks only whether explicitly named
executables are discoverable.  It never executes a binary, imports a provider,
connects to a service, starts a daemon, or examines a user's IPFS directory.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final

TEST_REUSE_CAPABILITY_REPORT_SCHEMA: Final = "TestReuseCapabilityReport@1"
TEST_REUSE_CAPABILITY_REPORT_SCHEMA_VERSION: Final = (
    TEST_REUSE_CAPABILITY_REPORT_SCHEMA
)
TEST_REUSE_CAPABILITY_REPORT_VERSION: Final = 1
DEFAULT_CAPABILITY_TIMEOUT_SECONDS: Final = 0.5
DEFAULT_CAPABILITY_MAX_CHECKS: Final = 3

_DISABLED_VALUES = frozenset({"0", "disabled", "false", "no", "off"})
_ENABLED_VALUES = frozenset({"1", "enabled", "on", "true", "yes"})


class KitTestReuseCapabilityStatus(str, Enum):
    AVAILABLE = "available"
    DISABLED = "disabled"
    MISSING = "missing"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


class KitTestReuseCapabilityName(str, Enum):
    KUBO = "kubo"
    LOTUS = "lotus"
    IROH = "iroh"


_CAPABILITY_ORDER: Final = tuple(KitTestReuseCapabilityName)
_EXECUTABLES: Final = {
    KitTestReuseCapabilityName.KUBO: "ipfs",
    KitTestReuseCapabilityName.LOTUS: "lotus",
    KitTestReuseCapabilityName.IROH: "iroh",
}


def _fingerprint(
    capability: KitTestReuseCapabilityName,
    status: KitTestReuseCapabilityStatus,
    executable: str,
    discovered_path: str | None,
) -> str:
    payload = json.dumps(
        {
            "capability_id": capability.value,
            "executable": executable,
            "path": discovered_path,
            "status": status.value,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class KitTestReuseCapabilityFact:
    capability_id: KitTestReuseCapabilityName
    status: KitTestReuseCapabilityStatus
    reason_code: str
    executable: str
    discovered_path: str | None = None
    fingerprint: str = ""
    optional: bool = field(default=True, init=False)
    blocking: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, KitTestReuseCapabilityName):
            object.__setattr__(
                self, "capability_id", KitTestReuseCapabilityName(self.capability_id)
            )
        if not isinstance(self.status, KitTestReuseCapabilityStatus):
            object.__setattr__(
                self, "status", KitTestReuseCapabilityStatus(self.status)
            )
        if type(self.reason_code) is not str or not self.reason_code.strip():
            raise ValueError("reason_code must be a nonempty string")
        if type(self.executable) is not str or not self.executable:
            raise ValueError("executable must be a nonempty string")
        if self.discovered_path is not None and type(self.discovered_path) is not str:
            raise ValueError("discovered_path must be a string or None")
        expected = _fingerprint(
            self.capability_id,
            self.status,
            self.executable,
            self.discovered_path,
        )
        if self.fingerprint and self.fingerprint != expected:
            raise ValueError("capability fingerprint does not match its facts")
        object.__setattr__(self, "fingerprint", expected)

    @property
    def name(self) -> str:
        return self.capability_id.value

    @property
    def available(self) -> bool:
        return self.status is KitTestReuseCapabilityStatus.AVAILABLE

    @property
    def test_action(self) -> str:
        return "continue" if self.available else "run"

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id.value,
            "status": self.status.value,
            "reason_code": self.reason_code,
            "executable": self.executable,
            "discovered_path": self.discovered_path,
            "fingerprint": self.fingerprint,
            "available": self.available,
            "optional": True,
            "blocking": False,
            "test_action": self.test_action,
        }


@dataclass(frozen=True)
class KitTestReuseCapabilityReport:
    capabilities: tuple[KitTestReuseCapabilityFact, ...]
    probe_count: int
    mode: str | None = None
    schema_version: str = TEST_REUSE_CAPABILITY_REPORT_SCHEMA
    report_version: int = TEST_REUSE_CAPABILITY_REPORT_VERSION
    lazy: bool = field(default=True, init=False)
    bounded: bool = field(default=True, init=False)
    side_effect_free: bool = field(default=True, init=False)
    network_attempted: bool = field(default=False, init=False)
    daemon_started: bool = field(default=False, init=False)
    user_ipfs_directory_touched: bool = field(default=False, init=False)
    cache_created: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        facts = tuple(self.capabilities)
        if tuple(fact.capability_id for fact in facts) != _CAPABILITY_ORDER:
            raise ValueError("capabilities must appear once in Kubo/Lotus/Iroh order")
        if (
            isinstance(self.probe_count, bool)
            or not isinstance(self.probe_count, int)
            or self.probe_count < 0
        ):
            raise ValueError("probe_count must be a non-negative integer")
        object.__setattr__(self, "capabilities", facts)
        normalized = self.mode.strip().lower() if type(self.mode) is str else None
        object.__setattr__(self, "mode", normalized or None)

    @property
    def facts(self) -> Mapping[str, KitTestReuseCapabilityFact]:
        return {fact.name: fact for fact in self.capabilities}

    def capability(
        self, capability_id: KitTestReuseCapabilityName | str
    ) -> KitTestReuseCapabilityFact:
        key = (
            capability_id.value
            if isinstance(capability_id, KitTestReuseCapabilityName)
            else str(capability_id)
        )
        try:
            return self.facts[key]
        except KeyError as exc:
            raise KeyError(f"unknown kit test-reuse capability: {key}") from exc

    @property
    def all_optional(self) -> bool:
        return all(fact.optional and not fact.blocking for fact in self.capabilities)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "report_version": self.report_version,
            "mode": self.mode,
            "probe_count": self.probe_count,
            "lazy": True,
            "bounded": True,
            "side_effect_free": True,
            "network_attempted": False,
            "daemon_started": False,
            "user_ipfs_directory_touched": False,
            "cache_created": False,
            "all_optional": self.all_optional,
            "capabilities": {fact.name: fact.to_dict() for fact in self.capabilities},
        }


@dataclass(frozen=True)
class KitTestReuseCapabilityConfig:
    timeout_seconds: float = DEFAULT_CAPABILITY_TIMEOUT_SECONDS
    max_checks: int = DEFAULT_CAPABILITY_MAX_CHECKS
    disabled_capabilities: frozenset[KitTestReuseCapabilityName | str] = frozenset()

    def __post_init__(self) -> None:
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not math.isfinite(float(self.timeout_seconds))
            or self.timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be finite and positive")
        if (
            isinstance(self.max_checks, bool)
            or not isinstance(self.max_checks, int)
            or self.max_checks < 1
        ):
            raise ValueError("max_checks must be a positive integer")
        disabled = frozenset(
            item
            if isinstance(item, KitTestReuseCapabilityName)
            else KitTestReuseCapabilityName(str(item))
            for item in self.disabled_capabilities
        )
        object.__setattr__(self, "timeout_seconds", float(self.timeout_seconds))
        object.__setattr__(self, "disabled_capabilities", disabled)


@dataclass
class _ProbeBudget:
    timeout_seconds: float
    max_checks: int
    monotonic: Callable[[], float]
    started: float = field(init=False)
    count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.started = self.monotonic()

    def call(self, function: Callable[[str], Any], argument: str) -> tuple[str, Any]:
        if self.count >= self.max_checks:
            return "exhausted", None
        elapsed = self.monotonic() - self.started
        remaining = self.timeout_seconds - elapsed
        if remaining <= 0:
            return "exhausted", None
        self.count += 1
        result: list[tuple[bool, Any]] = []

        def invoke() -> None:
            try:
                result.append((True, function(argument)))
            except BaseException:
                result.append((False, None))

        worker = threading.Thread(
            target=invoke,
            name="ipfs-kit-cold-capability-probe",
            daemon=True,
        )
        worker.start()
        worker.join(remaining)
        if worker.is_alive():
            return "timeout", None
        if not result or not result[0][0]:
            return "failed", None
        return "ok", result[0][1]


def _environment_value(source: Mapping[str, str], key: str) -> str:
    try:
        value = source[key]
    except KeyError:
        return ""
    if type(value) is not str:
        raise TypeError("environment values must be strings")
    return value.strip().lower()


class KitTestReuseCapabilities:
    """Lazy reporter; construction retains hooks but performs no checks."""

    __test__ = False

    def __init__(
        self,
        config: KitTestReuseCapabilityConfig | None = None,
        *,
        which: Callable[[str], str | None] | None = None,
        environ: Mapping[str, str] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self.config = config or KitTestReuseCapabilityConfig()
        self._which = which or shutil.which
        self._environ = os.environ if environ is None else environ
        self._monotonic = monotonic or time.monotonic

    def probe(self) -> KitTestReuseCapabilityReport:
        """Return one non-cached snapshot of cold executable facts."""

        try:
            mode = _environment_value(
                self._environ, "IPFS_TEST_PROOF_REUSE_MODE"
            )
        except BaseException:
            mode = ""
            mode_failed = True
        else:
            mode_failed = False

        if mode_failed:
            facts = tuple(
                self._fact(
                    capability,
                    KitTestReuseCapabilityStatus.UNKNOWN,
                    "configuration_probe_failed",
                )
                for capability in _CAPABILITY_ORDER
            )
            return KitTestReuseCapabilityReport(facts, 0)

        if mode in _DISABLED_VALUES:
            facts = tuple(
                self._fact(
                    capability,
                    KitTestReuseCapabilityStatus.DISABLED,
                    "proof_reuse_disabled",
                )
                for capability in _CAPABILITY_ORDER
            )
            return KitTestReuseCapabilityReport(facts, 0, mode)

        budget = _ProbeBudget(
            self.config.timeout_seconds, self.config.max_checks, self._monotonic
        )
        facts = tuple(self._probe_one(capability, budget) for capability in _CAPABILITY_ORDER)
        return KitTestReuseCapabilityReport(facts, budget.count, mode or None)

    report = probe
    snapshot = probe

    def _probe_one(
        self,
        capability: KitTestReuseCapabilityName,
        budget: _ProbeBudget,
    ) -> KitTestReuseCapabilityFact:
        if capability in self.config.disabled_capabilities:
            return self._fact(
                capability,
                KitTestReuseCapabilityStatus.DISABLED,
                "capability_disabled",
            )
        label = capability.value.upper()
        try:
            explicitly_disabled = _environment_value(
                self._environ, f"IPFS_TEST_PROOF_REUSE_DISABLE_{label}"
            )
            explicitly_enabled = _environment_value(
                self._environ, f"IPFS_TEST_PROOF_REUSE_{label}_ENABLED"
            )
        except BaseException:
            return self._fact(
                capability,
                KitTestReuseCapabilityStatus.UNKNOWN,
                "configuration_probe_failed",
            )
        if (
            explicitly_disabled in _ENABLED_VALUES
            or explicitly_enabled in _DISABLED_VALUES
        ):
            return self._fact(
                capability,
                KitTestReuseCapabilityStatus.DISABLED,
                "capability_disabled",
            )

        executable = _EXECUTABLES[capability]
        outcome, discovered = budget.call(self._which, executable)
        if outcome == "timeout":
            return self._fact(
                capability,
                KitTestReuseCapabilityStatus.UNKNOWN,
                "probe_timed_out",
            )
        if outcome != "ok":
            return self._fact(
                capability,
                KitTestReuseCapabilityStatus.UNKNOWN,
                "probe_budget_exhausted" if outcome == "exhausted" else "probe_failed",
            )
        if discovered is None:
            return self._fact(
                capability,
                KitTestReuseCapabilityStatus.MISSING,
                "executable_missing",
            )
        if type(discovered) is not str or not discovered.strip():
            return self._fact(
                capability,
                KitTestReuseCapabilityStatus.INCOMPATIBLE,
                "executable_finder_incompatible",
            )
        return self._fact(
            capability,
            KitTestReuseCapabilityStatus.AVAILABLE,
            "executable_discovered",
            discovered.strip(),
        )

    @staticmethod
    def _fact(
        capability: KitTestReuseCapabilityName,
        status: KitTestReuseCapabilityStatus,
        reason: str,
        path: str | None = None,
    ) -> KitTestReuseCapabilityFact:
        return KitTestReuseCapabilityFact(
            capability, status, reason, _EXECUTABLES[capability], path
        )


def probe_kit_test_reuse_capabilities(
    config: KitTestReuseCapabilityConfig | None = None,
    **kwargs: Any,
) -> KitTestReuseCapabilityReport:
    return KitTestReuseCapabilities(config, **kwargs).probe()


__all__ = [
    "DEFAULT_CAPABILITY_MAX_CHECKS",
    "DEFAULT_CAPABILITY_TIMEOUT_SECONDS",
    "KitTestReuseCapabilities",
    "KitTestReuseCapabilityConfig",
    "KitTestReuseCapabilityFact",
    "KitTestReuseCapabilityName",
    "KitTestReuseCapabilityReport",
    "KitTestReuseCapabilityStatus",
    "TEST_REUSE_CAPABILITY_REPORT_SCHEMA",
    "TEST_REUSE_CAPABILITY_REPORT_SCHEMA_VERSION",
    "TEST_REUSE_CAPABILITY_REPORT_VERSION",
    "probe_kit_test_reuse_capabilities",
]
