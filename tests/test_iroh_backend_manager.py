"""Contract tests for the validated named Iroh backend plugin."""

from __future__ import annotations

import copy
import json
import stat
from pathlib import Path

import pytest
import yaml

from ipfs_kit_py.backend_manager import BackendManager, list_supported_backends
from ipfs_kit_py.backend_registry import BackendConfigError, BackendTypeRegistry
from ipfs_kit_py.iroh.backend import IrohBackendPlugin


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "iroh" / "filesystem" / "backend-config-v1.json"


@pytest.fixture
def document() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _create(manager: BackendManager, document: dict) -> dict:
    settings = copy.deepcopy(document)
    return manager.create_backend(settings.pop("name"), settings.pop("type"), config=settings)


def test_iroh_is_a_registered_versioned_backend_without_startup(tmp_path: Path) -> None:
    registry = BackendTypeRegistry(load_entry_points=False)
    plugin = registry.get("iroh")
    assert isinstance(plugin, IrohBackendPlugin)
    assert plugin.schema_version == 1
    assert "iroh" in list_supported_backends()

    manager = BackendManager(tmp_path, registry=registry)
    schema = manager.get_backend_schema("iroh")
    assert schema["properties"]["type"]["const"] == "iroh"
    assert not (tmp_path / "iroh").exists()


def test_create_persists_refs_owner_only_and_redacts_all_public_results(
    tmp_path: Path, document: dict
) -> None:
    manager = BackendManager(tmp_path)
    created = _create(manager, document)
    assert created["status"] == "Backend created"
    assert created["backend"]["credentials"] == {
        "node_key_ref": "secretref:enhanced-secrets:<redacted>",
        "write_capability_ref": "secretref:enhanced-secrets:<redacted>",
    }

    path = tmp_path / "backends" / "team_archive.yaml"
    persisted = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert persisted["credentials"] == document["credentials"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    assert manager.show_backend("team_archive")["credentials"] == created["backend"]["credentials"]
    assert manager.list_backends()["backends"][0]["credentials"] == created["backend"]["credentials"]
    assert manager.get_backend_info("team_archive")["config"]["credentials"] == created["backend"]["credentials"]
    assert manager.get_backend_config("team_archive", redact=False)["credentials"] == document["credentials"]


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda value: value.update({"surprise": True}), "unknown settings"),
        (lambda value: value["credentials"].update({"token": "inline"}), "secret reference"),
        (lambda value: value["service"].update({"rpc_endpoint": "tcp://127.0.0.1:4919"}), "local"),
        (lambda value: value["namespace"].update({"id": "bafy-not-an-iroh-id"}), "namespace.id"),
        (lambda value: value["sync"].update({"conflict_policy": "last-write-wins"}), "conflict_policy"),
    ],
)
def test_invalid_or_unknown_iroh_settings_are_rejected_without_a_partial_file(
    tmp_path: Path, document: dict, mutator, message: str
) -> None:
    mutator(document)
    manager = BackendManager(tmp_path)
    result = _create(manager, document)
    assert result["code"] == "invalid_backend_config"
    assert message in result["error"]
    assert not (tmp_path / "backends" / "team_archive.yaml").exists()


def test_validation_api_raises_and_unknown_backend_type_is_rejected(
    tmp_path: Path, document: dict
) -> None:
    manager = BackendManager(tmp_path)
    document["namespace"]["access"] = "read-write"
    del document["credentials"]["write_capability_ref"]
    with pytest.raises(BackendConfigError, match="write_capability_ref"):
        manager.validate_backend_config(document)
    result = manager.create_backend("unknown", "made_up", config={})
    assert result["code"] == "unknown_backend_type"


def test_failed_update_does_not_replace_valid_configuration(tmp_path: Path, document: dict) -> None:
    manager = BackendManager(tmp_path)
    assert "error" not in _create(manager, document)
    path = tmp_path / "backends" / "team_archive.yaml"
    before = path.read_bytes()
    result = manager.update_backend("team_archive", extra_policy="unsafe")
    assert result["code"] == "invalid_backend_config"
    assert path.read_bytes() == before


def test_capabilities_reflect_access_and_health_is_structured_and_redacted(
    tmp_path: Path, document: dict
) -> None:
    document["namespace"]["access"] = "read-only"
    del document["credentials"]["write_capability_ref"]

    def probe(config):
        return {
            "healthy": True,
            "status": "ready",
            "credential": config["credentials"]["node_key_ref"],
        }

    manager = BackendManager(tmp_path, health_probes={"iroh": probe})
    assert "error" not in _create(manager, document)
    capabilities = manager.get_backend_capabilities("team_archive")
    assert capabilities["read"] is True
    assert capabilities["write"] is False
    assert capabilities["transactions"] is False
    health = manager.get_backend_health("team_archive")
    assert health == {
        "healthy": True,
        "status": "ready",
        "credential": "secretref:enhanced-secrets:<redacted>",
    }


def test_flat_legacy_iroh_config_is_read_compatibly_and_migrated_atomically(
    tmp_path: Path,
) -> None:
    backend_dir = tmp_path / "backends"
    backend_dir.mkdir(parents=True)
    namespace = "a" * 64
    legacy = {
        "name": "archive",
        "type": "iroh",
        "enabled": True,
        "namespace_id": namespace,
        "access": "read-write",
        "instance": "primary",
        "managed": True,
        "rpc_endpoint": "unix:///tmp/ipfs-kit-iroh-primary.sock",
        "node_key_ref": "secretref:environment:IROH_NODE_KEY",
        "write_capability_ref": "secretref:environment:IROH_WRITE_CAPABILITY",
        "sync_enabled": True,
    }
    path = backend_dir / "archive.yaml"
    path.write_text(yaml.safe_dump(legacy), encoding="utf-8")
    manager = BackendManager(tmp_path)

    # Compatibility reads normalize in memory but do not unexpectedly rewrite.
    shown = manager.show_backend("archive")
    assert shown["schema_version"] == 1
    assert shown["namespace"] == {"id": namespace, "access": "read-write"}
    assert "schema_version" not in yaml.safe_load(path.read_text())

    result = manager.migrate_backend("archive")
    assert result["changed"] is True
    assert Path(result["backup"]).is_file()
    persisted = yaml.safe_load(path.read_text())
    assert persisted["schema_version"] == 1
    assert persisted["service"]["rpc_endpoint"] == legacy["rpc_endpoint"]
    assert persisted["credentials"]["node_key_ref"] == legacy["node_key_ref"]
    assert manager.migrate_backend("archive")["changed"] is False


def test_legacy_non_iroh_backend_documents_remain_compatible(tmp_path: Path) -> None:
    manager = BackendManager(tmp_path)
    created = manager.create_backend(
        "old_s3", "s3", bucket_name="archive", endpoint="https://s3.example"
    )
    assert created["status"] == "Backend created"
    assert manager.show_backend("old_s3")["bucket_name"] == "archive"
    assert manager.migrate_backend("old_s3")["changed"] is False


def test_adapter_construction_is_lazy(tmp_path: Path, document: dict) -> None:
    manager = BackendManager(tmp_path)
    assert "error" not in _create(manager, document)
    filesystem = manager.get_backend_adapter("team_archive")
    assert filesystem.client is None
    assert callable(filesystem.client_factory)
    assert filesystem.read_only is False

    from ipfs_kit_py.backends import get_backend_adapter

    legacy_registry_filesystem = get_backend_adapter("iroh", "team_archive", manager)
    assert legacy_registry_filesystem.client is None
    assert callable(legacy_registry_filesystem.client_factory)
