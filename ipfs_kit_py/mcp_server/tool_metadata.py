"""Tool metadata decorator + registry helpers.

A single tool definition feeds four surfaces — Python import, CLI, MCP server,
and the generated JavaScript SDK — so all metadata needed to drive those
surfaces lives on the function itself via ``@tool_metadata``.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolMeta:
    cache_ttl: Optional[float] = None
    deprecated: bool = False
    summary: str = ""
    tags: List[str] = field(default_factory=list)


def tool_metadata(
    *,
    cache_ttl: Optional[float] = None,
    deprecated: bool = False,
    summary: str = "",
    tags: Optional[List[str]] = None,
) -> Callable:
    """Attach MCP++ tool metadata to a tool callable."""

    def decorator(func: Callable) -> Callable:
        func._mcp_metadata = ToolMeta(  # type: ignore[attr-defined]
            cache_ttl=cache_ttl,
            deprecated=deprecated,
            summary=summary,
            tags=list(tags or []),
        )
        return func

    return decorator


_PY_TO_JSON = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "dict": "object",
    "list": "array",
    "Dict": "object",
    "List": "array",
}


def build_input_schema(func: Callable) -> Dict[str, Any]:
    """Derive a JSON-schema-ish inputSchema from a callable signature.

    Shared by MCP ``tools/list`` and the JS SDK generator so the wire contract
    is identical regardless of surface.
    """
    sig = inspect.signature(func)
    props: Dict[str, Any] = {}
    required: List[str] = []
    for name, param in sig.parameters.items():
        if name in ("self", "kwargs", "args"):
            continue
        if param.kind in (param.VAR_KEYWORD, param.VAR_POSITIONAL):
            continue
        ann = param.annotation
        ann_name = getattr(ann, "__name__", str(ann))
        json_type = _PY_TO_JSON.get(ann_name, "string")
        props[name] = {"type": json_type}
        if param.default is inspect.Parameter.empty:
            required.append(name)
        else:
            props[name]["default"] = param.default
    schema: Dict[str, Any] = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema
