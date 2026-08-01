"""Schema identities and validators for runtime-readiness fixtures.

Interfaces (versioned, closed):
- RuntimeReadinessFixture@1
- FaultSchedule@1
- ExpectedStateTrace@1
- FixtureManifest@1
"""

from __future__ import annotations

from typing import Any, Final, Iterable, Mapping, Sequence

RUNTIME_READINESS_FIXTURE_SCHEMA: Final[str] = "ipfs_kit_py/runtime-readiness/fixture@1"
FAULT_SCHEDULE_SCHEMA: Final[str] = "ipfs_kit_py/runtime-readiness/fault-schedule@1"
EXPECTED_STATE_TRACE_SCHEMA: Final[str] = "ipfs_kit_py/runtime-readiness/expected-state-trace@1"
FIXTURE_MANIFEST_SCHEMA: Final[str] = "ipfs_kit_py/runtime-readiness/fixture-manifest@1"

MAX_TRACE_STEPS: Final[int] = 64
MAX_FAULTS: Final[int] = 32
MAX_OPERATIONS: Final[int] = 64
MAX_STATE_KEYS: Final[int] = 128
MAX_STRING_LEN: Final[int] = 512
MAX_NESTING_DEPTH: Final[int] = 8
MAX_FIXTURES: Final[int] = 256

ALLOWED_POLARITIES: Final[frozenset[str]] = frozenset(
    {"adversarial", "differential", "positive"}
)
ALLOWED_SUBSYSTEMS: Final[frozenset[str]] = frozenset(
    {
        "arc",
        "backend",
        "bucket",
        "graphrag",
        "interface",
        "mcp_plus",
        "ordering",
        "package",
        "replica",
        "resource",
        "ucan",
        "vfs",
        "wal",
    }
)
ALLOWED_FAULT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "absent_token",
        "backend_partial_effect",
        "backend_retryable_error",
        "backend_unavailable",
        "cancellation",
        "construction_failure",
        "corrupt_cache",
        "corrupt_record",
        "crash_after_commit",
        "crash_before_commit",
        "factory_missing",
        "forged_token",
        "invalid_token",
        "journal_missing_method",
        "mock_handler_injection",
        "nondeterministic_listing",
        "ordering_permutation",
        "path_escape",
        "policy_fail_open",
        "replayed_token",
        "resource_exhaustion",
        "revoked_token",
        "shadowed_method",
        "timeout",
        "torn_write",
        "unsafe_deserialize",
    }
)
ALLOWED_TRACE_STATES: Final[frozenset[str]] = frozenset(
    {
        "accepted",
        "checkpointed",
        "committed",
        "contract_violation",
        "converged",
        "denied",
        "exhausted",
        "failed",
        "initial",
        "partial_effect",
        "pending",
        "queued",
        "replayed",
        "rolled_back",
        "unavailable",
        "verified",
    }
)
ALLOWED_OUTCOMES: Final[frozenset[str]] = frozenset(
    {
        "contract_violation_observed",
        "denied",
        "exhausted",
        "failed",
        "indeterminate_ordering",
        "partial_effect",
        "success",
        "unavailable",
    }
)

_FORBIDDEN_KEY_FRAGMENTS: Final[tuple[str, ...]] = (
    "password",
    "secret",
    "token_value",
    "private_key",
    "api_key",
    "credential",
    "authorization_header",
    "bearer",
    "home_path",
    "user_home",
)


class FixtureValidationError(ValueError):
    """Raised when a fixture, fault schedule, or trace violates schema bounds."""

    def __init__(self, message: str, reason_codes: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.reason_codes = tuple(str(code) for code in reason_codes)


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FixtureValidationError(f"{label} must be a mapping", reason_codes=("type_error",))
    return value


def _require_str(value: Any, label: str, max_len: int = MAX_STRING_LEN) -> str:
    if not isinstance(value, str) or not value:
        raise FixtureValidationError(
            f"{label} must be a non-empty string", reason_codes=("type_error",)
        )
    if len(value) > max_len:
        raise FixtureValidationError(
            f"{label} exceeds max length {max_len}",
            reason_codes=("bound_exceeded",),
        )
    return value


def _require_sequence(value: Any, label: str, max_len: int) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise FixtureValidationError(f"{label} must be a sequence", reason_codes=("type_error",))
    if len(value) > max_len:
        raise FixtureValidationError(
            f"{label} exceeds max length {max_len}",
            reason_codes=("bound_exceeded",),
        )
    return value


def _check_finite_value(value: Any, path: str = "value", depth: int = 0) -> None:
    if depth > MAX_NESTING_DEPTH:
        raise FixtureValidationError(
            f"{path} exceeds max nesting depth",
            reason_codes=("bound_exceeded", "unbounded"),
        )
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, int):
        if abs(value) > 2**53:
            raise FixtureValidationError(
                f"{path} integer is non-finite for JSON safety",
                reason_codes=("non_finite",),
            )
        return
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise FixtureValidationError(
                f"{path} float is non-finite",
                reason_codes=("non_finite",),
            )
        return
    if isinstance(value, str):
        if len(value) > MAX_STRING_LEN:
            raise FixtureValidationError(
                f"{path} string exceeds max length",
                reason_codes=("bound_exceeded",),
            )
        lower = value.lower()
        for frag in _FORBIDDEN_KEY_FRAGMENTS:
            if frag in lower and path.lower().endswith(frag):
                raise FixtureValidationError(
                    f"{path} looks like a secret-bearing field",
                    reason_codes=("unsafe_secret_field",),
                )
        return
    if isinstance(value, Mapping):
        if len(value) > MAX_STATE_KEYS:
            raise FixtureValidationError(
                f"{path} mapping exceeds max keys",
                reason_codes=("bound_exceeded",),
            )
        for key, item in value.items():
            if not isinstance(key, str):
                raise FixtureValidationError(
                    f"{path} keys must be strings",
                    reason_codes=("type_error",),
                )
            key_l = key.lower()
            for frag in _FORBIDDEN_KEY_FRAGMENTS:
                if frag in key_l:
                    raise FixtureValidationError(
                        f"{path}.{key} is a forbidden secret-like key",
                        reason_codes=("unsafe_secret_field",),
                    )
            _check_finite_value(item, path=f"{path}.{key}", depth=depth + 1)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if len(value) > MAX_OPERATIONS:
            raise FixtureValidationError(
                f"{path} sequence exceeds max length",
                reason_codes=("bound_exceeded",),
            )
        for idx, item in enumerate(value):
            _check_finite_value(item, path=f"{path}[{idx}]", depth=depth + 1)
        return
    raise FixtureValidationError(
        f"{path} has unsupported type {type(value).__name__}",
        reason_codes=("type_error",),
    )


def validate_fault_schedule(schedule: Any) -> Mapping[str, Any]:
    """Validate a FaultSchedule@1 record."""
    data = _require_mapping(schedule, "fault_schedule")
    schema = _require_str(data.get("schema"), "fault_schedule.schema")
    if schema != FAULT_SCHEDULE_SCHEMA:
        raise FixtureValidationError(
            f"fault_schedule.schema must be {FAULT_SCHEDULE_SCHEMA}",
            reason_codes=("schema_mismatch",),
        )
    schedule_id = _require_str(data.get("schedule_id"), "fault_schedule.schedule_id")
    faults = _require_sequence(data.get("faults"), "fault_schedule.faults", max_len=MAX_FAULTS)
    if not faults:
        raise FixtureValidationError(
            "fault_schedule.faults must be non-empty when schedule is present",
            reason_codes=("empty_faults",),
        )
    seen_offsets: set[int] = set()
    normalized_faults: list[dict[str, Any]] = []
    for idx, fault in enumerate(faults):
        f = _require_mapping(fault, f"fault_schedule.faults[{idx}]")
        kind = _require_str(f.get("kind"), f"faults[{idx}].kind")
        if kind not in ALLOWED_FAULT_KINDS:
            raise FixtureValidationError(
                f"unknown fault kind {kind}",
                reason_codes=("unknown_fault_kind",),
            )
        offset = f.get("at_operation_index")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise FixtureValidationError(
                f"fault_schedule.faults[{idx}].at_operation_index must be a non-negative int",
                reason_codes=("type_error",),
            )
        if offset in seen_offsets:
            raise FixtureValidationError(
                f"duplicate fault offset {offset}",
                reason_codes=("duplicate_fault_offset",),
            )
        seen_offsets.add(offset)
        effects = f.get("effects", ())
        effects_seq = _require_sequence(
            effects, f"fault_schedule.faults[{idx}].effects", max_len=MAX_OPERATIONS
        )
        for e_idx, effect in enumerate(effects_seq):
            _require_str(effect, f"fault_schedule.faults[{idx}].effects[{e_idx}]")
        content_id = f.get("content_id")
        if content_id is not None:
            _require_str(content_id, f"fault_schedule.faults[{idx}].content_id")
        parameters = f.get("parameters", {})
        if parameters is not None:
            _check_finite_value(parameters, path=f"fault_schedule.faults[{idx}].parameters")
        entry = {
            "kind": kind,
            "at_operation_index": offset,
            "effects": tuple(str(e) for e in effects_seq),
            "parameters": dict(parameters) if isinstance(parameters, Mapping) else {},
        }
        if content_id is not None:
            entry["content_id"] = content_id
        normalized_faults.append(entry)
    content_id = data.get("content_id")
    if content_id is not None:
        _require_str(content_id, "fault_schedule.content_id")
    return {
        "schema": schema,
        "schedule_id": schedule_id,
        "faults": normalized_faults,
        "content_id": content_id,
        "finite": bool(data.get("finite", True)),
        "safe": bool(data.get("safe", True)),
    }


def validate_expected_state_trace(trace: Any) -> Mapping[str, Any]:
    """Validate an ExpectedStateTrace@1 record."""
    data = _require_mapping(trace, "expected_trace")
    schema = _require_str(data.get("schema"), "expected_trace.schema")
    if schema != EXPECTED_STATE_TRACE_SCHEMA:
        raise FixtureValidationError(
            f"expected_trace.schema must be {EXPECTED_STATE_TRACE_SCHEMA}",
            reason_codes=("schema_mismatch",),
        )
    trace_id = _require_str(data.get("trace_id"), "expected_trace.trace_id")
    steps = _require_sequence(data.get("steps"), "expected_trace.steps", max_len=MAX_TRACE_STEPS)
    if not steps:
        raise FixtureValidationError(
            "expected_trace.steps must be non-empty",
            reason_codes=("empty_trace",),
        )
    normalized_steps: list[dict[str, Any]] = []
    prev_index: int | None = None
    for idx, step in enumerate(steps):
        s = _require_mapping(step, f"expected_trace.steps[{idx}]")
        step_index = s.get("index")
        if not isinstance(step_index, int) or isinstance(step_index, bool):
            raise FixtureValidationError(
                f"expected_trace.steps[{idx}].index must be an int",
                reason_codes=("type_error",),
            )
        if prev_index is not None and step_index <= prev_index:
            raise FixtureValidationError(
                f"expected_trace.steps[{idx}].index must be strictly increasing",
                reason_codes=("trace_order",),
            )
        prev_index = step_index
        state = _require_str(s.get("state"), f"steps[{idx}].state")
        if state not in ALLOWED_TRACE_STATES:
            raise FixtureValidationError(
                f"unknown trace state {state}",
                reason_codes=("unknown_trace_state",),
            )
        op = s.get("operation")
        if op is not None:
            _require_str(op, f"steps[{idx}].operation")
        error_code = s.get("error_code")
        if error_code is not None:
            _require_str(error_code, f"steps[{idx}].error_code")
        observed = s.get("observed_effect", "none")
        _require_str(observed, f"steps[{idx}].observed_effect")
        snapshot = s.get("state_snapshot", {})
        if snapshot is None:
            snapshot = {}
        if not isinstance(snapshot, Mapping):
            raise FixtureValidationError(
                f"steps[{idx}].state_snapshot must be a mapping",
                reason_codes=("type_error",),
            )
        _check_finite_value(snapshot, path=f"steps[{idx}].state_snapshot")
        content_id = s.get("content_id")
        if content_id is not None:
            _require_str(content_id, f"steps[{idx}].content_id")
        entry = {
            "index": step_index,
            "state": state,
            "operation": op,
            "error_code": error_code,
            "observed_effect": observed,
            "state_snapshot": dict(snapshot),
        }
        if content_id is not None:
            entry["content_id"] = content_id
        normalized_steps.append(entry)
    terminal = _require_mapping(data.get("terminal"), "expected_trace.terminal")
    outcome = _require_str(terminal.get("outcome"), "expected_trace.terminal.outcome")
    if outcome not in ALLOWED_OUTCOMES:
        raise FixtureValidationError(
            f"unknown terminal outcome {outcome}",
            reason_codes=("unknown_outcome",),
        )
    namespace = terminal.get("namespace", {})
    if namespace is None:
        namespace = {}
    if not isinstance(namespace, Mapping):
        raise FixtureValidationError(
            "terminal.namespace must be a mapping",
            reason_codes=("type_error",),
        )
    _check_finite_value(namespace, path="terminal.namespace")
    evidence = terminal.get("evidence", {})
    if evidence is None:
        evidence = {}
    if not isinstance(evidence, Mapping):
        raise FixtureValidationError(
            "terminal.evidence must be a mapping",
            reason_codes=("type_error",),
        )
    _check_finite_value(evidence, path="terminal.evidence")
    content_id = data.get("content_id")
    if content_id is not None:
        _require_str(content_id, "expected_trace.content_id")
    return {
        "schema": schema,
        "trace_id": trace_id,
        "steps": normalized_steps,
        "terminal": {
            "outcome": outcome,
            "namespace": dict(namespace),
            "evidence": dict(evidence),
            "error_code": terminal.get("error_code"),
        },
        "content_id": content_id,
        "finite": bool(data.get("finite", True)),
        "safe": bool(data.get("safe", True)),
    }


def validate_fixture(fixture: Any) -> Mapping[str, Any]:
    """Validate a RuntimeReadinessFixture@1 record."""
    data = _require_mapping(fixture, "fixture")
    schema = _require_str(data.get("schema"), "fixture.schema")
    if schema != RUNTIME_READINESS_FIXTURE_SCHEMA:
        raise FixtureValidationError(
            f"fixture.schema must be {RUNTIME_READINESS_FIXTURE_SCHEMA}",
            reason_codes=("schema_mismatch",),
        )
    fixture_id = _require_str(data.get("fixture_id"), "fixture.fixture_id")
    if not fixture_id.startswith("fixture:"):
        raise FixtureValidationError(
            "fixture_id must start with 'fixture:'",
            reason_codes=("identity_error",),
        )
    subsystem = _require_str(data.get("subsystem"), "fixture.subsystem")
    if subsystem not in ALLOWED_SUBSYSTEMS:
        raise FixtureValidationError(
            f"unknown subsystem {subsystem}",
            reason_codes=("unknown_subsystem",),
        )
    polarity = _require_str(data.get("polarity"), "fixture.polarity")
    if polarity not in ALLOWED_POLARITIES:
        raise FixtureValidationError(
            f"unknown polarity {polarity}",
            reason_codes=("unknown_polarity",),
        )
    categories = _require_sequence(
        data.get("categories"), "fixture.categories", max_len=MAX_OPERATIONS
    )
    if not categories:
        raise FixtureValidationError(
            "fixture.categories must be non-empty",
            reason_codes=("empty_categories",),
        )
    for c_idx, cat in enumerate(categories):
        _require_str(cat, f"fixture.categories[{c_idx}]")
    blockers = data.get("blocker_refs", ())
    blockers_seq = _require_sequence(
        blockers, "fixture.blocker_refs", max_len=MAX_OPERATIONS
    )
    for b_idx, blocker in enumerate(blockers_seq):
        _require_str(blocker, f"fixture.blocker_refs[{b_idx}]")
    description = _require_str(data.get("description"), "fixture.description")
    initial_state = data.get("initial_state", {})
    if initial_state is None:
        initial_state = {}
    _check_finite_value(initial_state, path="fixture.initial_state")
    operations = _require_sequence(
        data.get("operations"), "fixture.operations", max_len=MAX_OPERATIONS
    )
    if not operations:
        raise FixtureValidationError(
            "fixture.operations must be non-empty",
            reason_codes=("empty_operations",),
        )
    for o_idx, op in enumerate(operations):
        om = _require_mapping(op, f"fixture.operations[{o_idx}]")
        _require_str(om.get("op"), f"operations[{o_idx}].op")
        _check_finite_value(om, path=f"fixture.operations[{o_idx}]")
    fault_schedule = data.get("fault_schedule")
    if fault_schedule is not None:
        validate_fault_schedule(fault_schedule)
    expected_trace = data.get("expected_trace")
    if expected_trace is None:
        raise FixtureValidationError(
            "fixture.expected_trace is required",
            reason_codes=("missing_trace",),
        )
    validate_expected_state_trace(expected_trace)
    safety = _require_mapping(data.get("safety"), "fixture.safety")
    for flag in (
        "network",
        "credentials",
        "user_paths",
        "executable_payloads",
        "production_side_effects",
    ):
        if safety.get(flag) is not False:
            raise FixtureValidationError(
                f"fixture.safety.{flag} must be false (hermetic)",
                reason_codes=("unsafe_fixture",),
            )
    content_id = _require_str(data.get("content_id"), "fixture.content_id")
    if not content_id.startswith("sha256:"):
        raise FixtureValidationError(
            "fixture.content_id must be sha256-prefixed",
            reason_codes=("identity_error",),
        )
    hermetic = data.get("hermetic")
    if hermetic is not True:
        raise FixtureValidationError(
            "fixture.hermetic must be true",
            reason_codes=("unsafe_fixture",),
        )
    finite = data.get("finite")
    if finite is not True:
        raise FixtureValidationError(
            "fixture.finite must be true",
            reason_codes=("unbounded",),
        )
    return data


def validate_manifest(manifest: Any) -> Mapping[str, Any]:
    """Validate a FixtureManifest@1 record."""
    data = _require_mapping(manifest, "manifest")
    schema = _require_str(data.get("schema"), "manifest.schema")
    if schema != FIXTURE_MANIFEST_SCHEMA:
        raise FixtureValidationError(
            f"manifest.schema must be {FIXTURE_MANIFEST_SCHEMA}",
            reason_codes=("schema_mismatch",),
        )
    _require_str(data.get("manifest_id"), "manifest.manifest_id")
    _require_str(data.get("interface"), "manifest.interface")
    fixtures = _require_sequence(
        data.get("fixtures"), "manifest.fixtures", max_len=MAX_FIXTURES
    )
    if not fixtures:
        raise FixtureValidationError(
            "manifest.fixtures must be non-empty",
            reason_codes=("empty_manifest",),
        )
    seen_ids: set[str] = set()
    for idx, entry in enumerate(fixtures):
        em = _require_mapping(entry, f"manifest.fixtures[{idx}]")
        fid = _require_str(em.get("fixture_id"), f"fixtures[{idx}].fixture_id")
        if fid in seen_ids:
            raise FixtureValidationError(
                f"duplicate fixture_id {fid}",
                reason_codes=("duplicate_fixture_id",),
            )
        seen_ids.add(fid)
        _require_str(em.get("content_id"), f"fixtures[{idx}].content_id")
        cats = em.get("categories", ())
        cats_seq = _require_sequence(
            cats, f"fixtures[{idx}].categories", max_len=MAX_OPERATIONS
        )
        for c_idx, cat in enumerate(cats_seq):
            _require_str(cat, f"fixtures[{idx}].categories[{c_idx}]")
    coverage = _require_mapping(data.get("coverage"), "manifest.coverage")
    required = _require_sequence(
        coverage.get("required_categories"),
        "coverage.required_categories",
        max_len=MAX_OPERATIONS,
    )
    covered = _require_sequence(
        coverage.get("covered_categories"),
        "coverage.covered_categories",
        max_len=MAX_OPERATIONS,
    )
    missing = sorted(set(str(c) for c in required) - set(str(c) for c in covered))
    if missing:
        raise FixtureValidationError(
            f"manifest coverage missing categories: {', '.join(missing)}",
            reason_codes=("coverage_gap",),
        )
    blockers = _require_sequence(
        data.get("confirmed_blockers"),
        "manifest.confirmed_blockers",
        max_len=MAX_OPERATIONS,
    )
    for b_idx, blocker in enumerate(blockers):
        _require_str(blocker, f"confirmed_blockers[{b_idx}]")
    content_id = _require_str(data.get("content_id"), "manifest.content_id")
    if not content_id.startswith("sha256:"):
        raise FixtureValidationError(
            "manifest.content_id must be sha256-prefixed",
            reason_codes=("identity_error",),
        )
    if data.get("finite") is not True or data.get("safe") is not True:
        raise FixtureValidationError(
            "manifest.finite and manifest.safe must be true",
            reason_codes=("unsafe_manifest",),
        )
    return data


def assert_all_content_identified(records: Iterable[Mapping[str, Any]]) -> None:
    """Every record must carry a sha256 content_id."""
    for idx, record in enumerate(records):
        cid = record.get("content_id")
        if not isinstance(cid, str) or not cid.startswith("sha256:"):
            raise FixtureValidationError(
                f"record[{idx}] missing sha256 content_id",
                reason_codes=("identity_error",),
            )
