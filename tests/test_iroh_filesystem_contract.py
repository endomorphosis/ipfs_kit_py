"""Offline conformance tests for the frozen IROH-002 filesystem contract."""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import unquote_to_bytes, urlsplit

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "iroh" / "filesystem-contract.md"
RESOURCES = ROOT / "ipfs_kit_py" / "resources"
MANIFEST_SCHEMA_PATH = RESOURCES / "iroh-manifest.schema.json"
BACKEND_SCHEMA_PATH = RESOURCES / "iroh-backend-config.schema.json"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "iroh" / "filesystem"
MANIFEST_PATH = FIXTURE_DIR / "manifest-v1.json"
BACKEND_PATH = FIXTURE_DIR / "backend-config-v1.json"
CONTRACT_PATH = FIXTURE_DIR / "contract-v1.json"

HEX32 = re.compile(r"^[a-f0-9]{64}$")
TICKET_REF = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
BAD_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
ENCODED_SEPARATOR_OR_CONTROL = re.compile(
    r"%(?:2[fF]|5[cC]|0[0-9A-Fa-f]|1[0-9A-Fa-f]|7[fF])"
)

EXPECTED_ERROR_CODES = {
    "IROH_INVALID_URL",
    "IROH_INVALID_PATH",
    "IROH_INVALID_NAMESPACE",
    "IROH_INVALID_HASH",
    "IROH_UNSUPPORTED_SCHEMA",
    "IROH_CONFIG_INVALID",
    "IROH_CREDENTIAL_REQUIRED",
    "IROH_CREDENTIAL_INVALID",
    "IROH_PERMISSION_DENIED",
    "IROH_NOT_FOUND",
    "IROH_ALREADY_EXISTS",
    "IROH_NOT_DIRECTORY",
    "IROH_IS_DIRECTORY",
    "IROH_NOT_EMPTY",
    "IROH_CONFLICT",
    "IROH_SERVICE_UNAVAILABLE",
    "IROH_VERSION_MISMATCH",
    "IROH_TIMEOUT",
    "IROH_CANCELLED",
    "IROH_INTEGRITY_ERROR",
    "IROH_IO_ERROR",
    "IROH_UNSUPPORTED_OPERATION",
    "IROH_SYNC_FAILED",
}


class ContractURLValueError(ValueError):
    """A tiny fixture parser used to prove that the golden grammar is coherent."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    assert isinstance(value, dict), f"{path} must contain a JSON object"
    return value


@pytest.fixture(scope="module")
def manifest_schema() -> dict[str, Any]:
    return _read_json(MANIFEST_SCHEMA_PATH)


@pytest.fixture(scope="module")
def backend_schema() -> dict[str, Any]:
    return _read_json(BACKEND_SCHEMA_PATH)


@pytest.fixture(scope="module")
def manifest() -> dict[str, Any]:
    return _read_json(MANIFEST_PATH)


@pytest.fixture(scope="module")
def backend() -> dict[str, Any]:
    return _read_json(BACKEND_PATH)


@pytest.fixture(scope="module")
def contract() -> dict[str, Any]:
    return _read_json(CONTRACT_PATH)


def _validator(schema: dict[str, Any]) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _normalize_encoded_path(raw_path: str) -> str:
    if not raw_path.startswith("/"):
        raise ContractURLValueError("IROH_INVALID_URL")
    encoded = raw_path[1:]
    if not encoded:
        return ""
    if encoded.endswith("/") or BAD_PERCENT.search(encoded):
        raise ContractURLValueError("IROH_INVALID_PATH")

    normalized: list[str] = []
    for encoded_segment in encoded.split("/"):
        if not encoded_segment or ENCODED_SEPARATOR_OR_CONTROL.search(encoded_segment):
            raise ContractURLValueError("IROH_INVALID_PATH")
        try:
            segment = unquote_to_bytes(encoded_segment).decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ContractURLValueError("IROH_INVALID_PATH") from exc
        if segment in {".", ".."} or unicodedata.normalize("NFC", segment) != segment:
            raise ContractURLValueError("IROH_INVALID_PATH")
        if any(ord(char) < 32 or ord(char) == 127 for char in segment):
            raise ContractURLValueError("IROH_INVALID_PATH")
        if "/" in segment or "\\" in segment or len(segment.encode("utf-8")) > 255:
            raise ContractURLValueError("IROH_INVALID_PATH")
        normalized.append(segment)

    result = "/".join(normalized)
    if len(result.encode("utf-8")) > 4096:
        raise ContractURLValueError("IROH_INVALID_PATH")
    return result


def _parse_contract_url(value: str) -> tuple[str, str | None]:
    parsed = urlsplit(value)
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ContractURLValueError("IROH_INVALID_URL")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ContractURLValueError("IROH_INVALID_URL") from exc
    if port is not None:
        raise ContractURLValueError("IROH_INVALID_URL")

    if parsed.scheme == "iroh":
        if not HEX32.fullmatch(parsed.netloc):
            raise ContractURLValueError("IROH_INVALID_NAMESPACE")
        return "namespace", _normalize_encoded_path(parsed.path)

    if parsed.scheme == "iroh+blob":
        if parsed.path:
            raise ContractURLValueError("IROH_INVALID_URL")
        if not HEX32.fullmatch(parsed.netloc):
            raise ContractURLValueError("IROH_INVALID_HASH")
        return "blob", None

    if parsed.scheme == "iroh+ticket":
        if not TICKET_REF.fullmatch(parsed.netloc):
            raise ContractURLValueError("IROH_INVALID_URL")
        return "ticket-reference", _normalize_encoded_path(parsed.path)

    raise ContractURLValueError("IROH_INVALID_URL")


def test_schemas_are_valid_closed_draft_2020_12_documents(
    manifest_schema: dict[str, Any], backend_schema: dict[str, Any]
) -> None:
    for schema in (manifest_schema, backend_schema):
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["additionalProperties"] is False
        _validator(schema)


def test_golden_manifest_and_backend_validate(
    manifest: dict[str, Any],
    backend: dict[str, Any],
    manifest_schema: dict[str, Any],
    backend_schema: dict[str, Any],
) -> None:
    _validator(manifest_schema).validate(manifest)
    _validator(backend_schema).validate(backend)


def test_manifest_semantic_invariants(manifest: dict[str, Any]) -> None:
    assert manifest["revision"] > 0
    assert manifest["parent_revision"]["revision"] == manifest["revision"] - 1
    assert manifest["permissions"]["owner"] in manifest["permissions"]["writers"]
    assert (
        manifest["writer_id"] == manifest["permissions"]["owner"]
        or manifest["writer_id"] in manifest["permissions"]["writers"]
    )

    entries = manifest["entries"]
    paths = [entry["path"] for entry in entries]
    assert len(paths) == len(set(paths))
    assert paths == sorted(paths, key=lambda path: path.encode("utf-8"))
    assert paths[0] == ""

    live_directories = {
        entry["path"]
        for entry in entries
        if entry["kind"] == "directory" and not entry["tombstone"]
    }
    assert "" in live_directories
    for entry in entries[1:]:
        assert unicodedata.normalize("NFC", entry["path"]) == entry["path"]
        assert all(len(segment.encode("utf-8")) <= 255 for segment in entry["path"].split("/"))
        if not entry["tombstone"]:
            parent = entry["path"].rsplit("/", 1)[0] if "/" in entry["path"] else ""
            assert parent in live_directories


@pytest.mark.parametrize(
    "bad_hash",
    [
        "f" * 63,
        "F" * 64,
        "0x" + "f" * 64,
        "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3ocl3w6q",
        "g" * 64,
    ],
)
def test_schemas_reject_invalid_native_identifiers(
    bad_hash: str,
    manifest: dict[str, Any],
    backend: dict[str, Any],
    manifest_schema: dict[str, Any],
    backend_schema: dict[str, Any],
) -> None:
    bad_manifest = copy.deepcopy(manifest)
    live_file = next(entry for entry in bad_manifest["entries"] if "blob_hash" in entry)
    live_file["blob_hash"] = bad_hash
    with pytest.raises(ValidationError):
        _validator(manifest_schema).validate(bad_manifest)

    bad_backend = copy.deepcopy(backend)
    bad_backend["namespace"]["id"] = bad_hash
    with pytest.raises(ValidationError):
        _validator(backend_schema).validate(bad_backend)


@pytest.mark.parametrize("version", [None, 0, -1, "1", 2, 999])
def test_unsupported_or_malformed_schema_versions_fail_closed(
    version: object,
    manifest: dict[str, Any],
    backend: dict[str, Any],
    manifest_schema: dict[str, Any],
    backend_schema: dict[str, Any],
) -> None:
    for source, schema in ((manifest, manifest_schema), (backend, backend_schema)):
        invalid = copy.deepcopy(source)
        if version is None:
            del invalid["schema_version"]
        else:
            invalid["schema_version"] = version
        with pytest.raises(ValidationError):
            _validator(schema).validate(invalid)


def test_backend_rejects_inline_secrets_and_nonlocal_rpc(
    backend: dict[str, Any], backend_schema: dict[str, Any]
) -> None:
    validator = _validator(backend_schema)

    inline_property = copy.deepcopy(backend)
    inline_property["credentials"]["ticket"] = "iroh-doc-ticket-secret-material"
    with pytest.raises(ValidationError):
        validator.validate(inline_property)

    raw_node_key = copy.deepcopy(backend)
    raw_node_key["credentials"]["node_key_ref"] = "4d4f9a2b" * 8
    with pytest.raises(ValidationError):
        validator.validate(raw_node_key)

    raw_capability = copy.deepcopy(backend)
    raw_capability["credentials"]["write_capability_ref"] = "iroh-write-capability-value"
    with pytest.raises(ValidationError):
        validator.validate(raw_capability)

    remote_rpc = copy.deepcopy(backend)
    remote_rpc["service"]["rpc_endpoint"] = "tcp://0.0.0.0:4919"
    with pytest.raises(ValidationError):
        validator.validate(remote_rpc)


def test_read_write_and_synchronized_config_preconditions(
    backend: dict[str, Any], backend_schema: dict[str, Any]
) -> None:
    validator = _validator(backend_schema)

    no_write_capability = copy.deepcopy(backend)
    del no_write_capability["credentials"]["write_capability_ref"]
    with pytest.raises(ValidationError):
        validator.validate(no_write_capability)

    read_only = copy.deepcopy(no_write_capability)
    read_only["namespace"]["access"] = "read-only"
    validator.validate(read_only)

    impossible_barrier = copy.deepcopy(backend)
    impossible_barrier["sync"]["enabled"] = False
    impossible_barrier["sync"]["read_consistency"] = "synchronized"
    with pytest.raises(ValidationError):
        validator.validate(impossible_barrier)


def test_manifest_shape_rules_reject_ambiguous_entries(
    manifest: dict[str, Any], manifest_schema: dict[str, Any]
) -> None:
    validator = _validator(manifest_schema)

    duplicate_root = copy.deepcopy(manifest)
    duplicate_root["entries"].append(copy.deepcopy(duplicate_root["entries"][0]))
    duplicate_root["entries"][-1]["metadata"] = {"user.copy": True}
    with pytest.raises(ValidationError):
        validator.validate(duplicate_root)

    directory_blob = copy.deepcopy(manifest)
    directory_blob["entries"][1]["blob_hash"] = "a" * 64
    directory_blob["entries"][1]["size"] = 0
    with pytest.raises(ValidationError):
        validator.validate(directory_blob)

    tombstone_blob = copy.deepcopy(manifest)
    tombstone = next(entry for entry in tombstone_blob["entries"] if entry["tombstone"])
    tombstone["blob_hash"] = "a" * 64
    tombstone["size"] = 1
    with pytest.raises(ValidationError):
        validator.validate(tombstone_blob)

    unsafe_path = copy.deepcopy(manifest)
    unsafe_path["entries"][-1]["path"] = "reports/../escape"
    with pytest.raises(ValidationError):
        validator.validate(unsafe_path)


def test_url_fixture_matches_frozen_grammar(contract: dict[str, Any]) -> None:
    assert HEX32.fullmatch(contract["namespace_id"])
    assert HEX32.fullmatch(contract["blob_hash"])

    for case in contract["valid_urls"]:
        kind, path = _parse_contract_url(case["url"])
        assert kind == case["kind"]
        assert path == case["normalized_path"]

    for case in contract["invalid_urls"]:
        with pytest.raises(ContractURLValueError) as caught:
            _parse_contract_url(case["url"])
        assert caught.value.code == case["error"]


def test_error_vocabulary_and_document_are_complete(contract: dict[str, Any]) -> None:
    assert set(contract["error_codes"]) == EXPECTED_ERROR_CODES
    assert len(contract["error_codes"]) == len(EXPECTED_ERROR_CODES)

    document = DOC_PATH.read_text(encoding="utf-8")
    assert "Decision: IROH-002" in document
    for heading in (
        "## Identifier and URL grammar",
        "## Path normalization",
        "## Manifest version 1",
        "## Backend configuration version 1",
        "## Consistency and mutation model",
        "## Synchronous and asynchronous behavior",
        "## Stable error contract",
        "## Unsupported POSIX and filesystem features",
    ):
        assert heading in document
    for code in EXPECTED_ERROR_CODES:
        assert f"`{code}`" in document
    for artifact in (
        "iroh-manifest.schema.json",
        "iroh-backend-config.schema.json",
        "manifest-v1.json",
        "backend-config-v1.json",
        "contract-v1.json",
    ):
        assert artifact in document
