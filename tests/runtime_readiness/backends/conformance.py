"""Reusable, assertion-backed conformance checks for hermetic backend adapters."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from ipfs_kit_py.core.operation_contracts import (
    ErrorCode,
    OperationResult,
    OperationState,
)


CONFORMANCE_OPERATIONS = (
    "health",
    "put",
    "get",
    "stream",
    "read_range",
    "list",
    "get_metadata",
    "set_metadata",
    "delete",
    "close",
)


@dataclass(frozen=True)
class ConformanceReport:
    """Auditable record of the operations attempted by the shared suite."""

    executed: tuple[str, ...]
    skipped: tuple[str, ...]
    final_effect_count: int


class BackendConformanceKit:
    """Exercise a declared adapter surface without treating omissions as success."""

    def __init__(self, *, close_timeout: float = 0.5) -> None:
        self.close_timeout = close_timeout

    @staticmethod
    def _error(exception: BaseException) -> Any:
        error = getattr(exception, "error", None)
        assert error is not None, "adapter failures must expose a typed error"
        return error

    def _expect_error(
        self,
        exception: BaseException,
        code: ErrorCode,
        state: OperationState,
    ) -> None:
        error = self._error(exception)
        assert error.code == code
        assert error.state == state

    @staticmethod
    def _assert_result(result: Any, *, content_cid: str | None = None) -> None:
        canonical = getattr(result, "canonical_result", None)
        assert isinstance(canonical, OperationResult)
        assert canonical.success is True
        assert result.success is True
        if content_cid is not None:
            assert result.resulting_content_cid == content_cid
            assert content_cid.startswith("b")

    @staticmethod
    def _arguments(operation: str) -> dict[str, Any]:
        if operation == "put":
            return {"path": "conformance/unsupported", "data": b"x"}
        if operation in {"get", "stream", "get_metadata", "delete"}:
            return {"path": "conformance/unsupported"}
        if operation == "read_range":
            return {"path": "conformance/unsupported", "start": 0, "end": 0}
        if operation == "set_metadata":
            return {"path": "conformance/unsupported", "metadata": {}}
        return {}

    async def _assert_unsupported_has_no_effects(self, adapter: Any, operation: str) -> None:
        before = adapter.effect_count
        try:
            await adapter.invoke(operation, **self._arguments(operation))
        except BaseException as exception:
            self._expect_error(exception, ErrorCode.UNSUPPORTED, OperationState.UNSUPPORTED)
        else:
            raise AssertionError("undeclared operation unexpectedly succeeded")
        assert adapter.effect_count == before

    async def run(self, adapter: Any) -> ConformanceReport:
        declared = frozenset(adapter.declared_operations)
        unknown = declared.difference(CONFORMANCE_OPERATIONS)
        assert not unknown, f"adapter declares unknown operations: {sorted(unknown)}"
        executed: list[str] = []
        skipped: list[str] = []
        for operation in CONFORMANCE_OPERATIONS:
            if operation in declared:
                continue
            skipped.append(operation)
            await self._assert_unsupported_has_no_effects(adapter, operation)

        if "health" in declared:
            health = await adapter.health()
            self._assert_result(health)
            assert health.metadata["hermetic"] is True
            executed.append("health")

        seed_path = "conformance/seed.bin"
        seed = b"canonical hermetic payload"
        cid = ""
        if "put" in declared:
            first = await adapter.put(seed_path, seed, idempotency_key="conformance-put")
            self._assert_result(first, content_cid=first.resulting_content_cid)
            cid = first.resulting_content_cid
            effects_after_first = adapter.effect_count
            replay = await adapter.put(seed_path, seed, idempotency_key="conformance-put")
            self._assert_result(replay, content_cid=cid)
            assert replay.canonical_result == first.canonical_result
            assert adapter.effect_count == effects_after_first

            adapter.inject_transient_failure("put")
            before_retry = adapter.effect_count
            try:
                await adapter.put("conformance/retry.bin", b"retry", idempotency_key="retry")
            except BaseException as exception:
                self._expect_error(exception, ErrorCode.UNAVAILABLE, OperationState.UNAVAILABLE)
            else:
                raise AssertionError("injected transient failure did not fail")
            assert adapter.effect_count == before_retry
            retry = await adapter.put("conformance/retry.bin", b"retry", idempotency_key="retry")
            self._assert_result(retry)
            assert adapter.effect_count == before_retry + 1

            before_cancel = adapter.effect_count
            cancelled = asyncio.Event()
            cancelled.set()
            try:
                await adapter.put("conformance/cancelled.bin", b"cancel", cancel_event=cancelled)
            except BaseException as exception:
                self._expect_error(exception, ErrorCode.CANCELLED, OperationState.CANCELLED)
            else:
                raise AssertionError("cancelled request did not fail")
            assert adapter.effect_count == before_cancel

            before_boundary = adapter.effect_count
            try:
                await adapter.put("../outside", b"escape")
            except BaseException as exception:
                self._expect_error(exception, ErrorCode.INVALID_REQUEST, OperationState.REJECTED)
            else:
                raise AssertionError("path escape was accepted")
            assert adapter.effect_count == before_boundary
            executed.append("put")

        if "get" in declared:
            if cid:
                got = await adapter.get(seed_path)
                self._assert_result(got, content_cid=cid)
                assert got.data == seed
                if hasattr(adapter, "corrupt_for_test"):
                    before_integrity = adapter.effect_count
                    adapter.corrupt_for_test(seed_path, b"tampered")
                    try:
                        await adapter.get(seed_path)
                    except BaseException as exception:
                        self._expect_error(
                            exception, ErrorCode.INTEGRITY_FAILURE, OperationState.FAILED
                        )
                    else:
                        raise AssertionError("tampered content passed integrity verification")
                    assert adapter.effect_count == before_integrity
                    repaired = await adapter.put(
                        seed_path, seed, idempotency_key="conformance-integrity-repair"
                    )
                    self._assert_result(repaired, content_cid=cid)
            else:
                try:
                    await adapter.get(seed_path)
                except BaseException as exception:
                    self._expect_error(exception, ErrorCode.NOT_FOUND, OperationState.FAILED)
                else:
                    raise AssertionError("missing content unexpectedly resolved")
            executed.append("get")

        if "stream" in declared:
            if cid:
                stream = await adapter.stream(seed_path, chunk_size=5)
                assert b"".join([chunk async for chunk in stream]) == seed
            else:
                try:
                    stream = await adapter.stream(seed_path)
                    async for _chunk in stream:
                        pass
                except BaseException as exception:
                    self._expect_error(exception, ErrorCode.NOT_FOUND, OperationState.FAILED)
                else:
                    raise AssertionError("stream missing content unexpectedly resolved")
            executed.append("stream")

        if "read_range" in declared:
            if cid:
                ranged = await adapter.read_range(seed_path, 1, len(seed) - 1)
                self._assert_result(ranged, content_cid=cid)
                assert ranged.data == seed[1:-1]
            else:
                try:
                    await adapter.read_range(seed_path, 0, 0)
                except BaseException as exception:
                    self._expect_error(exception, ErrorCode.NOT_FOUND, OperationState.FAILED)
                else:
                    raise AssertionError("range missing content unexpectedly resolved")
            executed.append("read_range")

        if "list" in declared:
            listed = await adapter.list("conformance")
            self._assert_result(listed)
            if cid:
                assert seed_path in listed.items
            executed.append("list")

        if "get_metadata" in declared:
            if cid:
                metadata = await adapter.get_metadata(seed_path)
                self._assert_result(metadata, content_cid=cid)
                assert metadata.metadata["size"] == len(seed)
            else:
                try:
                    await adapter.get_metadata(seed_path)
                except BaseException as exception:
                    self._expect_error(exception, ErrorCode.NOT_FOUND, OperationState.FAILED)
                else:
                    raise AssertionError("missing metadata unexpectedly resolved")
            executed.append("get_metadata")

        if "set_metadata" in declared:
            if cid:
                before_metadata = adapter.effect_count
                changed = await adapter.set_metadata(seed_path, {"label": "conformance"})
                self._assert_result(changed, content_cid=cid)
                assert adapter.effect_count == before_metadata + 1
                try:
                    await adapter.set_metadata(seed_path, {"api_token": "not-retained"})
                except BaseException as exception:
                    self._expect_error(exception, ErrorCode.SECRET_MATERIAL, OperationState.REJECTED)
                else:
                    raise AssertionError("secret-bearing metadata was accepted")
                assert adapter.effect_count == before_metadata + 1
            else:
                try:
                    await adapter.set_metadata(seed_path, {})
                except BaseException as exception:
                    self._expect_error(exception, ErrorCode.NOT_FOUND, OperationState.FAILED)
                else:
                    raise AssertionError("metadata write to missing content succeeded")
            executed.append("set_metadata")

        if "delete" in declared:
            if cid:
                before_delete = adapter.effect_count
                try:
                    await adapter.delete(seed_path, if_match="bwrong")
                except BaseException as exception:
                    self._expect_error(
                        exception, ErrorCode.PRECONDITION_FAILED, OperationState.PRECONDITION_FAILED
                    )
                else:
                    raise AssertionError("incorrect delete precondition succeeded")
                assert adapter.effect_count == before_delete
                deleted = await adapter.delete(seed_path, if_match=cid, idempotency_key="delete")
                self._assert_result(deleted, content_cid=cid)
                assert adapter.effect_count == before_delete + 1
            else:
                try:
                    await adapter.delete(seed_path)
                except BaseException as exception:
                    self._expect_error(exception, ErrorCode.NOT_FOUND, OperationState.FAILED)
                else:
                    raise AssertionError("delete of missing content succeeded")
            executed.append("delete")

        if "close" in declared:
            closed = await asyncio.wait_for(adapter.close(), timeout=self.close_timeout)
            self._assert_result(closed)
            assert adapter.closed is True
            if "get" in declared:
                before_closed_read = adapter.effect_count
                try:
                    await adapter.get(seed_path)
                except BaseException as exception:
                    self._expect_error(exception, ErrorCode.UNAVAILABLE, OperationState.UNAVAILABLE)
                else:
                    raise AssertionError("closed adapter accepted a read")
                assert adapter.effect_count == before_closed_read
            executed.append("close")

        assert tuple(executed) == tuple(operation for operation in CONFORMANCE_OPERATIONS if operation in declared)
        return ConformanceReport(
            executed=tuple(executed),
            skipped=tuple(skipped),
            final_effect_count=adapter.effect_count,
        )
