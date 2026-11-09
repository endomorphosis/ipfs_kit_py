"""Release-gate coverage for the packaged Iroh diagnostic entry points."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import pytest

from ipfs_kit_py.iroh import diagnostics_cli, manifest_cli


class _Observer:
    def __init__(self, config) -> None:
        self.config = config

    async def diagnostics(self, *, persist: bool):
        return {"instance": self.config.instance, "persist": persist, "ready": False}

    async def prometheus(self, *, persist: bool):
        return f"iroh_ready 0\n# persist={str(persist).lower()}\n"


def test_diagnostics_run_supports_json_and_prometheus_without_a_service(tmp_path: Path) -> None:
    parser = diagnostics_cli.build_parser()
    common = ["--instance", "ci", "--state-root", str(tmp_path), "--no-persist"]
    document = json.loads(
        asyncio.run(
            diagnostics_cli.run(parser.parse_args(common), observability_factory=_Observer)
        )
    )
    assert document == {"instance": "ci", "persist": False, "ready": False}
    metrics = asyncio.run(
        diagnostics_cli.run(
            parser.parse_args([*common, "--format", "prometheus"]),
            observability_factory=_Observer,
        )
    )
    assert metrics.startswith("iroh_ready 0")


def test_diagnostics_main_writes_output_and_redacts_failures(monkeypatch, capsys) -> None:
    async def success(_args: argparse.Namespace) -> str:
        return '{"ready": false}\n'

    monkeypatch.setattr(diagnostics_cli, "run", success)
    assert diagnostics_cli.main([]) == 0
    assert json.loads(capsys.readouterr().out) == {"ready": False}

    async def failure(_args: argparse.Namespace) -> str:
        raise RuntimeError("ticket-secret-must-not-leak")

    monkeypatch.setattr(diagnostics_cli, "run", failure)
    with pytest.raises(SystemExit) as raised:
        diagnostics_cli.main([])
    assert raised.value.code == 1
    captured = capsys.readouterr()
    assert "ticket-secret" not in captured.err
    assert "diagnostics failed" in captured.err


def test_manifest_cli_migrates_and_reports_only_the_destination(
    tmp_path: Path, capsys
) -> None:
    source = tmp_path / "manifest.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": 0,
                "namespace": "a" * 64,
                "revision": 0,
                "mtime": "2026-07-13T00:00:00Z",
                "author": "b" * 64,
                "files": [],
            }
        ),
        encoding="utf-8",
    )
    assert manifest_cli.main(["migrate", str(source)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"path": str(source), "schema_version": 1}
    assert json.loads(source.read_text(encoding="utf-8"))["schema_version"] == 1


def test_manifest_recovery_cli_preserves_dry_run_default(monkeypatch, capsys) -> None:
    calls = []

    class Receipt:
        def to_dict(self):
            return {"status": "valid", "repaired": False}

    async def recover(client, namespace_id, *, dry_run, history_limit):
        calls.append((client, namespace_id, dry_run, history_limit))
        return Receipt()

    client = object()
    monkeypatch.setattr(manifest_cli, "recover_namespace", recover)
    assert manifest_cli.main(
        ["recover", "a" * 64, "--history-limit", "7"], client_factory=lambda: client
    ) == 0
    assert calls == [(client, "a" * 64, True, 7)]
    assert json.loads(capsys.readouterr().out) == {"status": "valid", "repaired": False}


def test_manifest_recovery_requires_an_authenticated_factory(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        manifest_cli.main(["recover", "a" * 64])
    assert raised.value.code == 2
    assert "authenticated application runtime" in capsys.readouterr().err


def test_legacy_backend_module_exports_the_canonical_types() -> None:
    from ipfs_kit_py.backends import iroh_backend
    from ipfs_kit_py.iroh_fsspec import IrohFileSystem
    from ipfs_kit_py.iroh_vfs import IrohVFSAdapter

    assert iroh_backend.IrohBackend is IrohFileSystem
    assert iroh_backend.IrohVFSAdapter is IrohVFSAdapter
