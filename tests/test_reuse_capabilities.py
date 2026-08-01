from __future__ import annotations

import json

from ipfs_kit_py.test_reuse_capabilities import (
    KitTestReuseCapabilities,
    KitTestReuseCapabilityConfig,
    KitTestReuseCapabilityStatus,
    TEST_REUSE_CAPABILITY_REPORT_SCHEMA,
)


def test_construction_is_lazy_and_off_mode_performs_no_discovery() -> None:
    calls: list[str] = []

    def which(name: str) -> str | None:
        calls.append(name)
        raise AssertionError("off mode must not discover executables")

    capabilities = KitTestReuseCapabilities(
        which=which, environ={"IPFS_TEST_PROOF_REUSE_MODE": "off"}
    )
    assert calls == []
    report = capabilities.probe()
    assert calls == []
    assert report.probe_count == 0
    assert all(
        fact.status is KitTestReuseCapabilityStatus.DISABLED
        for fact in report.capabilities
    )


def test_kubo_lotus_and_iroh_are_stable_lazy_facts() -> None:
    calls: list[str] = []
    paths = {"ipfs": "/opt/bin/ipfs", "lotus": None, "iroh": "/opt/bin/iroh"}

    def which(name: str) -> str | None:
        calls.append(name)
        return paths[name]

    capabilities = KitTestReuseCapabilities(which=which, environ={})
    assert calls == []
    report = capabilities.snapshot()
    assert calls == ["ipfs", "lotus", "iroh"]
    assert tuple(report.facts) == ("kubo", "lotus", "iroh")
    assert report.capability("kubo").status is KitTestReuseCapabilityStatus.AVAILABLE
    assert report.capability("lotus").status is KitTestReuseCapabilityStatus.MISSING
    assert report.capability("iroh").status is KitTestReuseCapabilityStatus.AVAILABLE
    assert all(fact.fingerprint.startswith("sha256:") for fact in report.capabilities)

    encoded = json.dumps(report.to_dict(), sort_keys=True)
    assert TEST_REUSE_CAPABILITY_REPORT_SCHEMA in encoded
    assert report.lazy and report.bounded and report.side_effect_free
    assert not report.network_attempted
    assert not report.daemon_started
    assert not report.user_ipfs_directory_touched
    assert not report.cache_created


def test_capabilities_never_execute_or_start_discovered_daemons(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("capability facts must not start or execute a daemon")

    monkeypatch.setattr("subprocess.Popen", forbidden)
    monkeypatch.setattr("subprocess.run", forbidden)
    report = KitTestReuseCapabilities(
        which=lambda name: f"/safe/{name}", environ={}
    ).probe()
    assert report.probe_count == 3
    assert all(fact.available for fact in report.capabilities)


def test_explicit_disables_are_optional_nonblocking_facts() -> None:
    calls: list[str] = []
    config = KitTestReuseCapabilityConfig(disabled_capabilities=frozenset({"lotus"}))
    report = KitTestReuseCapabilities(
        config,
        which=lambda name: calls.append(name) or f"/bin/{name}",
        environ={"IPFS_TEST_PROOF_REUSE_DISABLE_IROH": "true"},
    ).report()
    assert calls == ["ipfs"]
    assert report.capability("kubo").available
    assert report.capability("lotus").status is KitTestReuseCapabilityStatus.DISABLED
    assert report.capability("iroh").status is KitTestReuseCapabilityStatus.DISABLED
    assert all(fact.optional and not fact.blocking for fact in report.capabilities)
    assert report.capability("lotus").test_action == "run"


def test_probe_budget_fails_closed_without_extra_checks() -> None:
    calls: list[str] = []
    config = KitTestReuseCapabilityConfig(max_checks=1)
    report = KitTestReuseCapabilities(
        config,
        which=lambda name: calls.append(name) or None,
        environ={},
    ).probe()
    assert calls == ["ipfs"]
    assert report.probe_count == 1
    assert report.capability("kubo").status is KitTestReuseCapabilityStatus.MISSING
    assert report.capability("lotus").status is KitTestReuseCapabilityStatus.UNKNOWN
    assert report.capability("iroh").status is KitTestReuseCapabilityStatus.UNKNOWN
