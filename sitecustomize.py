"""Interpreter bootstrap for a Kit source checkout. Never injects a sibling tree.

Python automatically imports sitecustomize when this file's directory is already
on sys.path. Installed wheels do not ship this module. This file must not
prepend parent directories, sibling checkouts, or tests/ trees onto sys.path.
Installed packages resolve through the ordinary import path and packaged
vectors (PCPR-025).
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


KIT_ROOT = Path(__file__).resolve().parent


def _bootstrap_symai_engines() -> None:
    if not _truthy(os.environ.get("IPFS_DATASETS_PY_SYMAI_SITEBOOT")):
        return

    # Keep this best-effort and lazy to avoid affecting normal imports.
    # Do not insert sibling checkouts onto sys.path; use the installed package.
    try:
        import symai  # noqa: F401
        from symai.functional import EngineRepository
    except Exception:
        return

    use_codex = _truthy(os.environ.get("IPFS_DATASETS_PY_USE_CODEX_FOR_SYMAI"))
    model_value = os.environ.get("NEUROSYMBOLIC_ENGINE_MODEL", "")
    if str(model_value).startswith("codex:"):
        use_codex = True

    if use_codex:
        try:
            from ipfs_datasets_py.utils.symai_codex_engine import CodexExecNeurosymbolicEngine

            EngineRepository.register(
                "neurosymbolic",
                CodexExecNeurosymbolicEngine(),
                allow_engine_override=True,
            )
        except Exception:
            # Never fail interpreter startup due to registration issues.
            return

    if _truthy(os.environ.get("IPFS_DATASETS_PY_USE_SYMAI_ENGINE_ROUTER")):
        try:
            from ipfs_datasets_py.utils.symai_ipfs_engine import register_ipfs_symai_engines

            register_ipfs_symai_engines()
        except Exception:
            return


_bootstrap_symai_engines()

# If a third-party `mcp` was already imported, drop it so the local checkout
# module (already visible because this file was found) can resolve. Do not
# insert a parent or sibling directory onto sys.path to achieve that.
mod = sys.modules.get("mcp")
if mod is not None:
    mod_path = getattr(mod, "__file__", "") or ""
    local_mcp = KIT_ROOT / "mcp"
    if local_mcp.exists() and str(KIT_ROOT) not in mod_path:
        sys.modules.pop("mcp", None)

# Provide a lightweight stub for legacy MCP imports during pytest to avoid
# slow, dependency-heavy imports in subprocess-based tests.
if os.environ.get("PYTEST_CURRENT_TEST"):
    stub_name = "enhanced_mcp_server_with_daemon_mgmt"
    if stub_name not in sys.modules:
        stub = types.ModuleType(stub_name)

        class GraphRAGSearchEngine:  # type: ignore
            def __init__(self, *args, **kwargs):
                self._indexed = []

            def get_search_stats(self):
                return {
                    "vector_search_available": False,
                    "graph_search_available": False,
                    "sparql_available": False,
                    "total_indexed_content": len(self._indexed),
                    "knowledge_graph_nodes": 0,
                    "knowledge_graph_edges": 0,
                    "rdf_triples": 0,
                }

            async def index_content(self, **kwargs):
                self._indexed.append(kwargs)
                return {"success": True, "indexed": len(self._indexed)}

            async def text_search(self, *args, **kwargs):
                return {"success": False, "error": "text_search not implemented", "results": []}

        stub.GraphRAGSearchEngine = GraphRAGSearchEngine
        sys.modules[stub_name] = stub
