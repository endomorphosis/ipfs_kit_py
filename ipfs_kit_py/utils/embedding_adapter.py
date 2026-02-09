"""Embedding adapter for local HF models or Gemini CLI.

Provides a fallback strategy for embeddings generation:
- Gemini CLI (if installed and enabled)
- Local HuggingFace transformers with mean pooling

Adapted for ipfs_kit_py from ipfs_datasets_py.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Iterable, List, Optional


def _truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _get_env(key: str, default: str = "") -> str:
    """Get environment variable with fallback to ipfs_datasets_py naming."""
    # Try ipfs_kit_py naming first, then ipfs_datasets_py naming
    return os.getenv(f"IPFS_KIT_{key}") or os.getenv(f"IPFS_DATASETS_PY_{key}") or default


def _gemini_available() -> bool:
    return shutil.which("gemini") is not None


def _select_backend() -> str:
    forced = _get_env("EMBEDDINGS_BACKEND", "").strip().lower()
    if forced:
        return forced
    if _truthy(_get_env("USE_GEMINI_FOR_EMBEDDINGS")) and _gemini_available():
        return "gemini"
    # Default to HF, not Gemini, unless explicitly enabled
    return "hf"


def _gemini_embed(texts: List[str]) -> List[List[float]]:
    """Attempt embeddings via Gemini CLI; fall back upstream on failure."""
    import shlex
    cmd = shlex.split(_get_env("GEMINI_EMBEDDINGS_CMD", "gemini embeddings --json"))
    results: List[List[float]] = []

    for text in texts:
        try:
            proc = subprocess.run(
                cmd,
                input=text,
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Gemini CLI not found") from exc

        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "Gemini embeddings command failed")

        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Gemini embeddings output was not valid JSON") from exc

        embedding = payload.get("embedding")
        if not isinstance(embedding, list):
            raise RuntimeError("Gemini embeddings response missing 'embedding' list")
        results.append([float(x) for x in embedding])

    return results


def _resolve_module(module_name: str, deps: Any = None) -> Any:
    """Resolve a module with optional dependency injection."""
    if deps is not None:
        cached = deps.get_cached(f"pip::{module_name}")
        if cached is not None:
            return cached
    
    try:
        import importlib
        module = importlib.import_module(module_name)
        if deps is not None:
            deps.set_cached(f"pip::{module_name}", module)
        return module
    except ImportError:
        return None


def _hf_embed(
    texts: List[str],
    model_name: str,
    device: str,
    *,
    deps: Any | None = None,
    torch_module: Any | None = None,
    transformers_module: Any | None = None,
) -> List[List[float]]:
    torch = torch_module or _resolve_module("torch", deps=deps)
    transformers = transformers_module or _resolve_module("transformers", deps=deps)

    if torch is None or transformers is None:
        raise RuntimeError("transformers/torch not available for HF embeddings")

    AutoTokenizer = getattr(transformers, "AutoTokenizer", None)
    AutoModel = getattr(transformers, "AutoModel", None)
    if AutoTokenizer is None or AutoModel is None:
        raise RuntimeError("transformers missing AutoTokenizer/AutoModel")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.to(device)
    model.eval()

    embeddings: List[List[float]] = []
    with torch.no_grad():
        for text in texts:
            inputs = tokenizer(
                text,
                padding=True,
                truncation=True,
                return_tensors="pt",
            )
            inputs = {k: v.to(device) for k, v in inputs.items()}
            outputs = model(**inputs)
            last_hidden = outputs.last_hidden_state
            mask = inputs.get("attention_mask")
            if mask is None:
                pooled = last_hidden.mean(dim=1)
            else:
                mask = mask.unsqueeze(-1).expand(last_hidden.size())
                masked = last_hidden * mask
                pooled = masked.sum(dim=1) / mask.sum(dim=1).clamp(min=1)
            embeddings.append(pooled[0].detach().cpu().tolist())

    return embeddings


def embed_texts(
    texts: Iterable[str],
    *,
    model_name: Optional[str] = None,
    device: Optional[str] = None,
    deps: Any | None = None,
    torch_module: Any | None = None,
    transformers_module: Any | None = None,
) -> List[List[float]]:
    """Embed texts using the selected backend."""
    text_list = [t for t in texts]
    backend = _select_backend()

    if backend == "gemini":
        try:
            return _gemini_embed(text_list)
        except Exception:
            # Fall back to HF if Gemini is unavailable or misconfigured.
            backend = "hf"

    if backend == "hf":
        model = model_name or _get_env(
            "EMBEDDINGS_MODEL",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        device_name = device or _get_env("EMBEDDINGS_DEVICE")
        if not device_name:
            torch = torch_module or _resolve_module("torch", deps=deps)
            try:
                device_name = "cuda" if (torch is not None and torch.cuda.is_available()) else "cpu"
            except Exception:
                device_name = "cpu"
        return _hf_embed(
            text_list,
            model,
            device_name,
            deps=deps,
            torch_module=torch_module,
            transformers_module=transformers_module,
        )

    raise RuntimeError(f"Unknown embeddings backend: {backend}")


def embed_text(
    text: str,
    *,
    model_name: Optional[str] = None,
    device: Optional[str] = None,
    deps: Any | None = None,
    torch_module: Any | None = None,
    transformers_module: Any | None = None,
) -> List[float]:
    """Embed a single text string."""
    return embed_texts(
        [text],
        model_name=model_name,
        device=device,
        deps=deps,
        torch_module=torch_module,
        transformers_module=transformers_module,
    )[0]
