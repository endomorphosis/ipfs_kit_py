"""Contract tests for managed Iroh service configuration and state."""

from __future__ import annotations

import copy
import json
import os
import stat
from pathlib import Path

import pytest

from ipfs_kit_py.iroh.config import (
    CONFIG_SCHEMA_VERSION,
    IrohServiceConfig,
    atomic_write_config,
    default_config,
    ensure_state_layout,
    load_config,
    loads_config,
    migrate_config,
    migrate_config_file,
    validate_instance_isolation,
    validate_instance_name,
)
from ipfs_kit_py.iroh.errors import (
    IrohConflictError,
    IrohInvalidConfigError,
    IrohUnsupportedVersionError,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "config" / "iroh-service.example.json"


def test_example_is_current_valid_and_contains_references_only() -> None:
    config = load_config(EXAMPLE)
    assert config.instance == "default"
    assert config.enabled is False
    assert config.node_identity_ref.startswith("credential://iroh/")
    serialized = EXAMPLE.read_text(encoding="utf-8")
    for forbidden in ('"node_key"', '"private_key"', '"secret"', '"token"'):
        assert forbidden not in serialized


def test_named_instances_have_disjoint_state_and_rpc_paths(tmp_path: Path) -> None:
    first = default_config("first", state_root=tmp_path)
    second = default_config("second", state_root=tmp_path)
    assert first.layout.root != second.layout.root
    assert first.rpc_endpoint != second.rpc_endpoint


@pytest.mark.parametrize(
    "name", ["", "UPPER", "has.dot", "../escape", "trailing-", "a" * 65]
)
def test_invalid_instance_names_are_rejected(name: str) -> None:
    with pytest.raises(IrohInvalidConfigError):
        validate_instance_name(name)


def test_duplicate_instance_does_not_collide_silently(tmp_path: Path) -> None:
    first = default_config("same", state_root=tmp_path, enabled=True)
    second = default_config("same", state_root=tmp_path, enabled=True)
    with pytest.raises(IrohConflictError):
        validate_instance_isolation([first, second])


def test_wildcard_and_specific_endpoint_binds_collide(tmp_path: Path) -> None:
    first_document = default_config("first", state_root=tmp_path, enabled=True).to_dict()
    second_document = default_config("second", state_root=tmp_path, enabled=True).to_dict()
    first_document["network"]["endpoint_bind"] = ["0.0.0.0:4919"]
    second_document["network"]["endpoint_bind"] = ["127.0.0.1:4919"]
    with pytest.raises(IrohConflictError, match="colliding"):
        validate_instance_isolation(
            [IrohServiceConfig.from_dict(first_document), IrohServiceConfig.from_dict(second_document)]
        )


def test_state_layout_is_owner_only_and_idempotent(tmp_path: Path) -> None:
    config = default_config("private", state_root=tmp_path)
    layout = ensure_state_layout(config)
    assert ensure_state_layout(config) == layout
    for directory in layout.directories:
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(layout.owner_path.stat().st_mode) == 0o600
    marker = json.loads(layout.owner_path.read_text(encoding="utf-8"))
    assert marker["instance"] == "private"


def test_layout_rejects_symlinked_state(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "unsafe"
    linked.symlink_to(real, target_is_directory=True)
    config = default_config("linked", state_root=linked)
    with pytest.raises(IrohInvalidConfigError, match="symlink"):
        ensure_state_layout(config)


@pytest.mark.parametrize(
    ("location", "key", "value"),
    [
        ("identity", "node_identity_ref", "private material"),
        ("identity", "node_key", "inline"),
        ("identity", "private_key", "inline"),
        ("identity", "token", "inline"),
    ],
)
def test_inline_secrets_are_rejected(
    tmp_path: Path, location: str, key: str, value: str
) -> None:
    document = default_config("secret-test", state_root=tmp_path).to_dict()
    document[location][key] = value
    if key != "node_identity_ref":
        document[location].pop("node_identity_ref", None)
    with pytest.raises(IrohInvalidConfigError):
        IrohServiceConfig.from_dict(document)


def test_remote_rpc_and_logging_escape_are_rejected(tmp_path: Path) -> None:
    document = default_config(state_root=tmp_path).to_dict()
    document["rpc"]["endpoint"] = "tcp://127.0.0.1:4919"
    with pytest.raises(IrohInvalidConfigError):
        IrohServiceConfig.from_dict(document)

    document = default_config(state_root=tmp_path).to_dict()
    document["logging"]["log_path"] = os.fspath(tmp_path / "other.log")
    with pytest.raises(IrohInvalidConfigError):
        IrohServiceConfig.from_dict(document)


def test_unknown_and_future_versions_fail_closed(tmp_path: Path) -> None:
    document = default_config(state_root=tmp_path).to_dict()
    document["schema_version"] = 2
    with pytest.raises(IrohUnsupportedVersionError):
        IrohServiceConfig.from_dict(document)

    document = default_config(state_root=tmp_path).to_dict()
    document["mystery"] = True
    with pytest.raises(IrohInvalidConfigError):
        IrohServiceConfig.from_dict(document)


@pytest.mark.parametrize("version", [True, False, None, "1", 0, -1])
def test_malformed_schema_versions_fail_closed(tmp_path: Path, version: object) -> None:
    document = default_config(state_root=tmp_path).to_dict()
    document["schema_version"] = version
    with pytest.raises(IrohInvalidConfigError):
        IrohServiceConfig.from_dict(document)


def test_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    document = default_config(state_root=tmp_path).to_dict()
    text = json.dumps(document).replace('"enabled": false', '"enabled": false, "enabled": true')
    with pytest.raises(IrohInvalidConfigError, match="duplicate"):
        loads_config(text)


def test_atomic_round_trip_uses_private_file_mode(tmp_path: Path) -> None:
    config = default_config(state_root=tmp_path)
    atomic_write_config(config.layout.config_path, config)
    assert load_config(config.layout.config_path) == config
    assert stat.S_IMODE(config.layout.config_path.stat().st_mode) == 0o600


def test_legacy_migration_is_complete_and_pure(tmp_path: Path) -> None:
    legacy = {
        "version": 0,
        "name": "legacy",
        "state_dir": os.fspath(tmp_path),
        "enabled": True,
        "node_identity_ref": "credential://iroh/legacy/node-key",
        "bind": "127.0.0.1:11204",
        "relay_mode": "disabled",
        "discovery": False,
        "resource_limits": {"max_connections": 32},
    }
    original = copy.deepcopy(legacy)
    migrated = migrate_config(legacy)
    assert legacy == original
    assert migrated["schema_version"] == CONFIG_SCHEMA_VERSION
    assert migrated["instance"] == "legacy"
    assert migrated["network"]["endpoint_bind"] == ["127.0.0.1:11204"]
    assert migrated["network"]["discovery"]["policy"] == "disabled"


def test_migration_rejects_inline_legacy_identity(tmp_path: Path) -> None:
    legacy = {"version": 0, "state_dir": os.fspath(tmp_path), "node_key": "secret material"}
    with pytest.raises(IrohInvalidConfigError):
        migrate_config(legacy)


def test_file_migration_replaces_only_after_validation(tmp_path: Path) -> None:
    path = tmp_path / "iroh.json"
    legacy = {
        "version": 0,
        "name": "legacy",
        "state_dir": os.fspath(tmp_path / "state"),
        "node_identity_ref": "credential://iroh/legacy/node-key",
    }
    path.write_text(json.dumps(legacy), encoding="utf-8")
    config = migrate_config_file(path, backup=True)
    assert load_config(path) == config
    assert json.loads(path.with_suffix(".json.v0.bak").read_text())["version"] == 0


def test_failed_migration_does_not_modify_source(tmp_path: Path) -> None:
    path = tmp_path / "iroh.json"
    original = b'{"version": 0, "node_key": "inline-secret"}\n'
    path.write_bytes(original)
    with pytest.raises(IrohInvalidConfigError):
        migrate_config_file(path)
    assert path.read_bytes() == original
