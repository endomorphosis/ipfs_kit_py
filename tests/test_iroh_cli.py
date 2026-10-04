"""Contract tests for the safe unified Iroh operator CLI."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from ipfs_kit_py.iroh.cli import (
    CLIContext,
    EXIT_CONFIRMATION,
    EXIT_FAILED,
    EXIT_SUCCESS,
    build_parser,
    main,
)


ROOT = Path(__file__).resolve().parents[1]
BACKEND_FIXTURE = ROOT / "tests" / "fixtures" / "iroh" / "filesystem" / "backend-config-v1.json"


def invoke(argv: list[str], **context_values: Any) -> tuple[int, dict[str, Any], str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    context = CLIContext(
        stdin=context_values.pop("stdin", io.StringIO()),
        stdout=stdout,
        stderr=stderr,
        **context_values,
    )
    code = main(argv, context=context)
    output = stdout.getvalue() or stderr.getvalue()
    return code, json.loads(output), stderr.getvalue()


def test_parser_exposes_every_required_operation_family() -> None:
    parser = build_parser()
    choices = parser._subparsers._group_actions[0].choices  # type: ignore[union-attr]
    assert set(choices) == {
        "binary",
        "service",
        "backend",
        "namespace",
        "blob",
        "ticket",
        "mount",
        "sync",
        "gc",
    }


def test_safe_console_script_is_declared_without_replacing_installer_cli() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'ipfs-kit-iroh = "ipfs_kit_py.iroh_install_cli:main"' in pyproject
    assert 'ipfs-kit-iroh-ops = "ipfs_kit_py.iroh.cli:main"' in pyproject


def test_status_is_json_and_service_control_has_no_shell_boundary(tmp_path: Path) -> None:
    class Service:
        async def status(self) -> dict[str, Any]:
            return {"running": False, "ready": False, "status": "stopped"}

    seen: list[str] = []

    def factory(config: Any) -> Service:
        seen.append(config.instance)
        return Service()

    code, document, stderr = invoke(
        ["service", "status", "--instance", "portable_name", "--state-root", os.fspath(tmp_path)],
        service_factory=factory,
    )
    assert code == EXIT_SUCCESS
    assert stderr == ""
    assert document == {
        "ok": True,
        "operation": "service.status",
        "result": {"ready": False, "running": False, "status": "stopped"},
    }
    assert seen == ["portable_name"]


def test_destructive_service_action_refuses_before_calling_service(tmp_path: Path) -> None:
    calls: list[str] = []

    class Service:
        async def stop(self) -> bool:
            calls.append("stop")
            return True

    code, document, _ = invoke(
        ["service", "stop", "--state-root", os.fspath(tmp_path)],
        service_factory=lambda _config: Service(),
    )
    assert code == EXIT_CONFIRMATION
    assert document["error"]["code"] == "confirmation_required"
    assert calls == []

    code, document, _ = invoke(
        ["service", "stop", "--state-root", os.fspath(tmp_path), "--yes"],
        service_factory=lambda _config: Service(),
    )
    assert code == EXIT_SUCCESS
    assert document["result"]["changed"] is True
    assert calls == ["stop"]


def test_dry_run_never_calls_service_mutation(tmp_path: Path) -> None:
    class Service:
        async def restart(self) -> bool:  # pragma: no cover - must not run
            raise AssertionError("dry run executed restart")

    code, document, _ = invoke(
        ["service", "restart", "--state-root", os.fspath(tmp_path), "--dry-run"],
        service_factory=lambda _config: Service(),
    )
    assert code == EXIT_SUCCESS
    assert document["result"] == {
        "action": "restart",
        "confirmation_phrase": "RESTART IROH default",
        "dry_run": True,
        "instance": "default",
    }


def test_legacy_binary_commands_delegate_and_rollback_requires_confirmation() -> None:
    class Manager:
        def __init__(self, **_kwargs: Any) -> None:
            self.calls: list[str] = []

        def inspect(self, *, check: bool) -> dict[str, Any]:
            return {"installed": True, "check": check}

        def rollback(self, **_kwargs: Any) -> dict[str, Any]:
            raise AssertionError("unconfirmed rollback executed")

    code, document, _ = invoke(
        ["inspect", "--check"], install_manager_factory=Manager
    )
    assert code == EXIT_SUCCESS
    assert document["operation"] == "binary.inspect"
    assert document["result"] == {"check": True, "installed": True}

    code, document, _ = invoke(["rollback"], install_manager_factory=Manager)
    assert code == EXIT_CONFIRMATION
    assert document["error"]["code"] == "confirmation_required"


def test_backend_create_validate_show_and_remove_are_redacted(tmp_path: Path) -> None:
    document = json.loads(BACKEND_FIXTURE.read_text(encoding="utf-8"))
    config = tmp_path / "backend config with spaces.json"
    config.write_text(json.dumps(document), encoding="utf-8")
    backend_root = tmp_path / "state with spaces"

    code, created, _ = invoke(
        [
            "backend",
            "create",
            document["name"],
            "--file",
            os.fspath(config),
            "--backend-root",
            os.fspath(backend_root),
        ]
    )
    assert code == EXIT_SUCCESS
    credentials = created["result"]["backend"]["credentials"]
    assert all("<redacted>" in value for value in credentials.values())
    assert "IROH" not in json.dumps(created)

    code, refused, _ = invoke(
        ["backend", "remove", document["name"], "--backend-root", os.fspath(backend_root)]
    )
    assert code == EXIT_CONFIRMATION
    assert refused["error"]["code"] == "confirmation_required"
    assert (backend_root / "backends" / f"{document['name']}.yaml").is_file()

    code, removed, _ = invoke(
        [
            "backend",
            "remove",
            document["name"],
            "--backend-root",
            os.fspath(backend_root),
            "--yes",
        ]
    )
    assert code == EXIT_SUCCESS
    assert removed["result"]["status"] == "Backend removed"


def test_ticket_is_read_only_from_private_file_and_never_echoed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ticket = "iroh-secret-ticket-material"
    ticket_file = tmp_path / "ticket with spaces.txt"
    ticket_file.write_text(ticket, encoding="utf-8")
    ticket_file.chmod(0o600)

    code, document, stderr = invoke(
        [
            "ticket",
            "import",
            "a" * 64,
            "--ticket-file",
            os.fspath(ticket_file),
            "--state-root",
            os.fspath(tmp_path / "state"),
            "--dry-run",
        ]
    )
    rendered = json.dumps(document) + stderr
    assert code == EXIT_SUCCESS
    assert ticket not in rendered
    assert document["result"]["dry_run"] is True

    if os.name != "nt":
        ticket_file.chmod(0o644)
        code, document, stderr = invoke(
            [
                "ticket",
                "import",
                "a" * 64,
                "--ticket-file",
                os.fspath(ticket_file),
                "--dry-run",
            ]
        )
        assert code != EXIT_SUCCESS
        assert ticket not in json.dumps(document) + stderr


def test_exception_text_and_ticket_like_values_are_not_reflected(tmp_path: Path) -> None:
    secret = "ticket-super-secret-value"

    class Service:
        async def status(self) -> dict[str, Any]:
            raise RuntimeError(f"sidecar failed with {secret} at {tmp_path}")

    code, document, stderr = invoke(
        ["service", "status", "--state-root", os.fspath(tmp_path)],
        service_factory=lambda _config: Service(),
    )
    rendered = json.dumps(document) + stderr
    assert code == EXIT_FAILED
    assert document["error"] == {
        "code": "operation_failed",
        "message": "Iroh operation failed",
    }
    assert secret not in rendered
    assert os.fspath(tmp_path) not in rendered


def test_blob_dry_run_handles_spaces_without_shell_expansion(tmp_path: Path) -> None:
    source = tmp_path / "$(not-a-command) data file.bin"
    source.write_bytes(b"safe")
    code, document, _ = invoke(
        [
            "blob",
            "add",
            os.fspath(source),
            "--state-root",
            os.fspath(tmp_path / "state dir"),
            "--dry-run",
        ]
    )
    assert code == EXIT_SUCCESS
    assert document["result"]["size"] == 4


def test_mount_dry_run_validates_native_url_and_remove_is_confirmed(tmp_path: Path) -> None:
    mount_state = tmp_path / "mount state.json"
    target = f"iroh://{'b' * 64}/models"
    code, document, _ = invoke(
        [
            "mount",
            "add",
            "/models",
            "--target",
            target,
            "--mount-state",
            os.fspath(mount_state),
            "--dry-run",
        ]
    )
    assert code == EXIT_SUCCESS
    assert document["result"]["target"] == target
    assert not mount_state.exists()

    code, document, _ = invoke(
        ["mount", "add", "/models", "--target", target, "--mount-state", os.fspath(mount_state)]
    )
    assert code == EXIT_SUCCESS
    code, document, _ = invoke(
        ["mount", "add", "models", "--target", target, "--mount-state", os.fspath(mount_state)]
    )
    assert code != EXIT_SUCCESS
    assert document["error"]["code"] == "mount_exists"


def test_existing_blob_export_requires_confirmation_before_rpc(tmp_path: Path) -> None:
    destination = tmp_path / "existing output.bin"
    destination.write_bytes(b"keep")
    code, document, _ = invoke(
        [
            "blob",
            "export",
            "a" * 64,
            os.fspath(destination),
            "--overwrite",
            "--state-root",
            os.fspath(tmp_path / "state"),
        ]
    )
    assert code == EXIT_CONFIRMATION
    assert document["error"]["code"] == "confirmation_required"
    assert destination.read_bytes() == b"keep"


def test_sync_request_dry_run_preserves_hash_domains(tmp_path: Path) -> None:
    source = tmp_path / "payload.bin"
    source.write_bytes(b"payload")
    request = tmp_path / "sync request.json"
    request.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "logical_path": "payload.bin",
                        "source": "local",
                        "destination": "iroh",
                        "local_path": os.fspath(source),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    class Sync:
        async def reconcile(self, items: list[Any], **options: Any) -> dict[str, Any]:
            assert items[0].cid is None
            assert items[0].iroh_hash is None
            assert options["dry_run"] is True
            return {"status": "success", "dry_run": True, "cid": None, "iroh_hash": "c" * 64}

    code, document, _ = invoke(
        [
            "sync",
            "run",
            "--file",
            os.fspath(request),
            "--state-root",
            os.fspath(tmp_path / "state"),
            "--dry-run",
        ],
        sync_factory=lambda *_args, **_kwargs: Sync(),
    )
    assert code == EXIT_SUCCESS
    assert document["result"]["cid"] is None
    assert document["result"]["iroh_hash"] == "c" * 64


def test_partial_sync_receipt_is_a_stable_operational_failure(tmp_path: Path) -> None:
    source = tmp_path / "payload.bin"
    source.write_bytes(b"payload")
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "logical_path": "payload.bin",
                        "source": "local",
                        "destination": "iroh",
                        "local_path": os.fspath(source),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    class PartialSync:
        async def reconcile(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            return {"status": "partial", "entries": [], "errors": [{"code": "io_error"}]}

    code, document, stderr = invoke(
        ["sync", "run", "--file", os.fspath(request), "--dry-run"],
        sync_factory=lambda *_args, **_kwargs: PartialSync(),
    )
    assert code == EXIT_FAILED
    assert stderr
    assert document["ok"] is False
    assert document["error"]["code"] == "partial_failure"
    assert document["result"]["status"] == "partial"


def test_sync_delete_requires_confirmation_before_adapter_creation(tmp_path: Path) -> None:
    request = tmp_path / "delete.json"
    request.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "logical_path": "old.bin",
                        "source": "local",
                        "destination": "iroh",
                        "deleted": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    created: list[bool] = []

    def factory(*_args: Any, **_kwargs: Any) -> Any:
        created.append(True)
        raise AssertionError("unconfirmed sync constructed an adapter")

    code, document, _ = invoke(
        ["sync", "run", "--file", os.fspath(request)], sync_factory=factory
    )
    assert code == EXIT_CONFIRMATION
    assert document["error"]["code"] == "confirmation_required"
    assert created == []


def test_gc_apply_refuses_before_creating_index(tmp_path: Path) -> None:
    index = tmp_path / "gc" / "references.duckdb"
    code, document, _ = invoke(
        [
            "gc",
            "run",
            "--apply",
            "--index",
            os.fspath(index),
            "--state-root",
            os.fspath(tmp_path / "state"),
        ]
    )
    assert code == EXIT_CONFIRMATION
    assert document["error"]["code"] == "confirmation_required"
    assert not index.exists()


def test_module_entrypoint_emits_portable_json(tmp_path: Path) -> None:
    source = tmp_path / "file with spaces.bin"
    source.write_bytes(b"portable")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ipfs_kit_py.iroh.cli",
            "--compact",
            "blob",
            "add",
            os.fspath(source),
            "--state-root",
            os.fspath(tmp_path / "state with spaces"),
            "--dry-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout)["result"]["size"] == len(b"portable")
