"""Governed HTTP API for implemented Iroh storage operations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import fastapi
from fastapi import Body, Request
from fastapi.responses import JSONResponse

from .iroh.governance import (
    IrohOperationController,
    IrohPermission,
    OPERATION_DEFINITIONS,
)


iroh_router = fastapi.APIRouter(prefix="/iroh", tags=["storage", "iroh"])


def _permissions(request: Request) -> Iterable[str | IrohPermission] | str | None:
    """Read permissions assigned by authentication middleware/server config.

    Client-controlled headers and request bodies are deliberately ignored.
    An unauthenticated embedding receives read-only access.
    """

    for owner in (request.state, request.app.state):
        value = getattr(owner, "iroh_permissions", None)
        if value is not None:
            return value
        value = getattr(owner, "permissions", None)
        if value is not None:
            return value
    return None


def _actor(request: Request) -> str:
    for owner in (request.state, request.app.state):
        value = getattr(owner, "actor", None) or getattr(owner, "user_id", None)
        if isinstance(value, str):
            return value
    return "api"


def _controller(request: Request) -> IrohOperationController:
    controller = getattr(request.app.state, "iroh_operation_controller", None)
    if controller is None:
        controller = IrohOperationController()
        request.app.state.iroh_operation_controller = controller
    return controller


def _descriptor(name: str) -> dict[str, Any]:
    definition = OPERATION_DEFINITIONS[name]
    return {
        "name": name,
        "description": definition.description,
        "permission": definition.permission.value,
        "destructive": definition.destructive,
        "input_schema": definition.input_schema,
    }


@iroh_router.get(
    "/operations",
    operation_id="listIrohOperations",
    summary="List governed Iroh operations",
)
async def list_iroh_operations() -> dict[str, Any]:
    """Return the implemented allowlist and its permission classification."""

    values = [_descriptor(name) for name in OPERATION_DEFINITIONS]
    return {"success": True, "operations": values, "count": len(values)}


@iroh_router.post(
    "/operations/{operation}",
    operation_id="executeIrohOperation",
    summary="Execute a governed Iroh operation",
    responses={
        400: {"description": "Invalid operation input"},
        403: {"description": "Required Iroh permission is absent"},
        409: {"description": "Destructive confirmation is required or state conflicts"},
        422: {"description": "Iroh integrity verification failed"},
        503: {"description": "Managed Iroh service is unavailable"},
    },
)
async def execute_iroh_operation(
    operation: str,
    request: Request,
    body: Any = Body(default=None),
) -> JSONResponse:
    """Execute one allowlisted operation with a transport-neutral envelope."""

    if not isinstance(body, Mapping):
        arguments: Any = body
        confirm = False
    else:
        document = dict(body)
        confirm = document.pop("confirm", False)
        nested = document.pop("arguments", document.pop("parameters", None))
        if nested is not None:
            if document:
                arguments = {"__invalid_envelope__": True}
            else:
                arguments = nested
        else:
            arguments = document
    result = await _controller(request).execute(
        operation,
        arguments,
        permissions=_permissions(request),
        confirm=confirm,
        actor=_actor(request),
    )
    status_code = 200 if result["success"] else int(result["error"]["status"])
    return JSONResponse(status_code=status_code, content=result)


__all__ = ["execute_iroh_operation", "iroh_router", "list_iroh_operations"]
