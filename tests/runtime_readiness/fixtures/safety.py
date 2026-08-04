"""Hermetic safety checks for runtime-readiness fixtures.

Fixtures must remain finite, offline, credential-free, and free of user paths
or executable payloads. Production side effects are never permitted.
"""

from __future__ import annotations

import re
from typing import Any, Final, Mapping, Sequence

from .schema import MAX_NESTING_DEPTH, MAX_STRING_LEN, FixtureValidationError

_NETWORK_HINTS: Final[tuple[str, ...]] = (
    "http://",
    "https://",
    "ws://",
    "wss://",
    "ftp://",
    "sftp://",
    "s3://",
    "ipfs://",
    "libp2p://",
)

_PATH_HINTS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"(^|/)home/"),
    re.compile(r"(^|/)Users/"),
    re.compile(r"^~(/|$)"),
    re.compile(r"\$HOME"),
    re.compile(r"\$\{HOME\}"),
    re.compile(r"[A-Za-z]:\\"),
)

_EXECUTABLE_HINTS: Final[tuple[str, ...]] = (
    "#!/",
    "\x7fELF",
    "MZ",
    "powershell",
    "cmd.exe",
    "/bin/sh",
    "/bin/bash",
)

_SECRET_HINTS: Final[tuple[str, ...]] = (
    "begin private key",
    "aws_secret",
    "api_key=",
    "password=",
    "bearer ",
)


class SafetyViolation(FixtureValidationError):
    """Raised when a fixture violates hermetic safety policy."""


def _walk(value: Any, path: str = "value", depth: int = 0) -> None:
    if depth > MAX_NESTING_DEPTH:
        raise SafetyViolation(
            f"{path} exceeds nesting bound",
            reason_codes=("bound_exceeded",),
        )
    if isinstance(value, str):
        if len(value) > MAX_STRING_LEN:
            raise SafetyViolation(
                f"{path} string exceeds max length",
                reason_codes=("bound_exceeded",),
            )
        lower = value.lower()
        for hint in _NETWORK_HINTS:
            if hint in lower:
                raise SafetyViolation(
                    f"{path} contains network locator {hint}",
                    reason_codes=("network_locator",),
                )
        for pattern in _PATH_HINTS:
            if pattern.search(value):
                raise SafetyViolation(
                    f"{path} contains user/home path material",
                    reason_codes=("user_path",),
                )
        for hint in _EXECUTABLE_HINTS:
            if hint.lower() in lower if hint.isascii() and hint.isalpha() else hint in value:
                raise SafetyViolation(
                    f"{path} looks like an executable payload",
                    reason_codes=("executable_payload",),
                )
        for hint in _SECRET_HINTS:
            if hint in lower:
                raise SafetyViolation(
                    f"{path} looks like a credential secret",
                    reason_codes=("credential",),
                )
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_s = str(key)
            key_l = key_s.lower()
            if any(
                frag in key_l
                for frag in (
                    "password",
                    "secret",
                    "private_key",
                    "api_key",
                    "credential",
                    "authorization_header",
                )
            ):
                raise SafetyViolation(
                    f"{path}.{key_s} is a forbidden secret-like key",
                    reason_codes=("credential",),
                )
            _walk(item, path=f"{path}.{key_s}", depth=depth + 1)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for idx, item in enumerate(value):
            _walk(item, path=f"{path}[{idx}]", depth=depth + 1)
        return
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise SafetyViolation(
                f"{path} is non-finite",
                reason_codes=("non_finite",),
            )


def validate_fixture_safety(fixture: Mapping[str, Any]) -> None:
    """Fail closed if the fixture is not finite/safe/hermetic."""
    safety = fixture.get("safety")
    if not isinstance(safety, Mapping):
        raise SafetyViolation(
            "fixture.safety missing",
            reason_codes=("unsafe_fixture",),
        )
    for flag in (
        "network",
        "credentials",
        "user_paths",
        "executable_payloads",
        "production_side_effects",
    ):
        if safety.get(flag) is not False:
            raise SafetyViolation(
                f"fixture.safety.{flag} must be false",
                reason_codes=("unsafe_fixture",),
            )
    if fixture.get("hermetic") is not True:
        raise SafetyViolation(
            "fixture.hermetic must be true",
            reason_codes=("unsafe_fixture",),
        )
    if fixture.get("finite") is not True:
        raise SafetyViolation(
            "fixture.finite must be true",
            reason_codes=("unbounded",),
        )
    for field in (
        "initial_state",
        "operations",
        "expected_trace",
        "fault_schedule",
        "description",
    ):
        if field in fixture and fixture[field] is not None:
            _walk(fixture[field], path=field)


def assert_fixture_safe(fixture: Mapping[str, Any]) -> Mapping[str, Any]:
    validate_fixture_safety(fixture)
    return fixture


def assert_corpus_safe(fixtures: Sequence[Mapping[str, Any]]) -> None:
    for fixture in fixtures:
        validate_fixture_safety(fixture)
