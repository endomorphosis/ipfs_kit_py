"""Headless regression tests for the ``/mcp/tools/call`` payload parser.

The kit MCP dashboard historically read a tool call's arguments only from the
``args``/``params`` keys in its non-JSON-RPC ("direct") branch.  A stock MCP
client that POSTs ``{"name": ..., "arguments": {...}}`` *without* a JSON-RPC
envelope therefore reached the tool with an *empty* argument dict — the
arguments were silently dropped, so only kit's own dashboard (which sends
``args``) worked.  These tests lock in that a top-level ``arguments`` key is now
honoured while every previously working shape (JSON-RPC envelope, ``args``, and a
non-dict ``params``) still behaves as before.

The dashboard module is loaded exactly the way the runtime loads it
(``importlib.util.spec_from_file_location`` — see ``ipfs_kit_py/cli.py``) so the
test exercises the real shipped ``_parse_tools_call_payload`` helper.

Runnable two ways::

    python3 tests/test_tools_call_payload_parsing.py          # standalone
    python3 -m pytest tests/test_tools_call_payload_parsing.py
"""

import importlib.util
from pathlib import Path

_DASH = (
    Path(__file__).resolve().parents[1]
    / "ipfs_kit_py" / "mcp" / "dashboard" / "consolidated_mcp_dashboard.py"
)


def _load_parser():
    spec = importlib.util.spec_from_file_location("cmd_dash_under_test", str(_DASH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._parse_tools_call_payload


_parse = _load_parser()


def test_direct_arguments_key_is_honoured():
    """THE regression: direct {name, arguments} must reach the tool with args."""
    name, args, rid = _parse({"name": "storage.pin_add", "arguments": {"cid": "bafy"}})
    assert name == "storage.pin_add"
    assert args == {"cid": "bafy"}
    assert rid is None


def test_direct_args_alias_still_works():
    """kit's own dashboard sends {name, args} — must keep working."""
    name, args, rid = _parse({"name": "storage.pin_add", "args": {"cid": "bafy"}})
    assert name == "storage.pin_add"
    assert args == {"cid": "bafy"}
    assert rid is None


def test_args_wins_over_arguments_when_both_present():
    """``args`` is checked first, preserving kit's historical precedence."""
    _, args, _ = _parse({"name": "x.y", "args": {"a": 1}, "arguments": {"b": 2}})
    assert args == {"a": 1}


def test_jsonrpc_envelope_is_unchanged():
    name, args, rid = _parse(
        {"jsonrpc": "2.0", "method": "tools/call",
         "params": {"name": "x.y", "arguments": {"a": 1}}, "id": 7}
    )
    assert name == "x.y"
    assert args == {"a": 1}
    assert rid == 7


def test_dict_params_is_the_jsonrpc_branch_not_direct_args():
    """A dict ``params`` is always the JSON-RPC envelope, so a stray top-level
    name/arguments alongside it is ignored in favour of ``params``."""
    name, args, rid = _parse(
        {"name": "IGNORED", "arguments": {"z": 9},
         "params": {"name": "real.tool", "arguments": {"a": 1}}, "id": 1}
    )
    assert name == "real.tool"
    assert args == {"a": 1}
    assert rid == 1


def test_missing_arguments_defaults_to_empty_dict():
    name, args, _ = _parse({"name": "x.y"})
    assert name == "x.y"
    assert args == {}


def test_tool_alias_for_name():
    name, _, _ = _parse({"tool": "x.y", "arguments": {"a": 1}})
    assert name == "x.y"


TESTS = [v for k, v in sorted(globals().items())
         if k.startswith("test_") and callable(v)]

if __name__ == "__main__":
    passed = 0
    for t in TESTS:
        t()
        print(f"  \u2714 {t.__name__}")
        passed += 1
    print(f"\n{passed}/{len(TESTS)} payload-parser tests passed")
