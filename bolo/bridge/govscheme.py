"""Read-only bridge into the sibling Whatsapp-Chatbot-Gov repository.

We never modify or vendor that repo. At call time we add its project root
to `sys.path` and import its compiled LangGraph pipeline
(`app.agents.graph.run_graph`) so it runs in-process -- the lowest-latency
option for a live voice call, no extra HTTP hop.

Important: the sibling repo's top-level package is literally named `app`.
Nothing in Bolo-Sarkar may use that same top-level package name (we use
`bolo`), or the two would collide in `sys.modules`.

Note: we deliberately call `app.agents.graph.run_graph` directly, not
`app.agents.orchestrator.Orchestrator.process` -- as of this writing the
orchestrator is stubbed to a fixed "mil gaya" reply for offline testing
and bypasses the graph entirely. Calling the graph directly gets the real
multi-agent behaviour. If that stub is later removed and the orchestrator
starts delegating to the graph again, both paths will behave the same.
"""

from __future__ import annotations

import logging
import sys
import threading
from typing import Callable, Optional

from bolo.config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_run_graph: Optional[Callable[[str, str], list]] = None
_ensure_index_loaded: Optional[Callable[[], None]] = None
_import_error: Optional[Exception] = None


def _ensure_loaded() -> None:
    global _run_graph, _ensure_index_loaded, _import_error
    if _run_graph is not None or _import_error is not None:
        return
    with _lock:
        if _run_graph is not None or _import_error is not None:
            return

        repo_path = settings.govscheme_repo_path
        if not repo_path.is_dir():
            _import_error = FileNotFoundError(
                f"GOVSCHEME_REPO_PATH does not exist: {repo_path}. "
                "Set it in .env to point at your Whatsapp-Chatbot-Gov checkout."
            )
            return

        repo_str = str(repo_path.resolve())
        if repo_str not in sys.path:
            sys.path.insert(0, repo_str)

        if "app" in sys.modules:
            existing = getattr(sys.modules["app"], "__file__", None)
            if existing and repo_str not in str(existing):
                logger.warning(
                    "A top-level `app` module was already imported from %s "
                    "before the GovScheme bridge loaded -- this will likely "
                    "import the wrong package. Make sure nothing else in "
                    "Bolo-Sarkar defines a top-level `app` package.",
                    existing,
                )

        try:
            from app.agents.graph import run_graph  # type: ignore  # noqa: PLC0415
            from app.rag.indexer import ensure_index_loaded  # type: ignore  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to import GovScheme LangGraph pipeline from %s", repo_str)
            _import_error = exc
            return

        _run_graph = run_graph
        _ensure_index_loaded = ensure_index_loaded
        logger.info("Loaded GovScheme LangGraph pipeline in-process from %s", repo_str)


def warm_up() -> None:
    """Build/load the Chroma index, same as the sibling repo's own FastAPI
    startup hook (app/main.py) does. We call their existing function
    in-process instead of duplicating its logic -- without this, the graph
    runs but every retrieval-backed reply says "search is not ready yet"
    until someone builds the index by hand.
    """
    _ensure_loaded()
    if _import_error is not None:
        logger.warning("Skipping GovScheme index warm-up: %s", _import_error)
        return
    assert _ensure_index_loaded is not None
    try:
        _ensure_index_loaded()
    except Exception:
        logger.exception(
            "GovScheme index warm-up failed -- voice replies will still work "
            "for static intents (welcome/help), but retrieval will be empty."
        )


def run_govscheme(chat_id: str, message: str) -> list[str]:
    """Invoke the GovScheme multi-agent graph in-process.

    Returns a list of WhatsApp-formatted reply parts, same as the sibling
    repo's `run_graph`. Raises RuntimeError if the sibling repo couldn't
    be found/imported -- callers should catch this and fail gracefully
    (see bolo/voice/llm_api.py), since a call is live on the other end.
    """
    _ensure_loaded()
    if _import_error is not None:
        raise RuntimeError(f"GovScheme bridge unavailable: {_import_error}") from _import_error
    assert _run_graph is not None
    return _run_graph(chat_id, message)


def is_ready() -> bool:
    """Best-effort readiness check for /healthz, without raising."""
    _ensure_loaded()
    return _import_error is None
