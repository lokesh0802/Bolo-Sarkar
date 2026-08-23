"""Human escalation -- mandatory requirement: the AI must know its limits
and hand off honestly instead of guessing.

For the buildathon demo this doesn't need a live human agent, just a real,
inspectable log entry every time the AI defers -- judges can open
data/escalations.jsonl and see it happening.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from bolo.config import settings

logger = logging.getLogger(__name__)

# Phrases GovScheme's own prompts already use when it isn't sure (it's
# instructed not to invent scheme names/amounts). Not exhaustive -- this
# is a cheap trigger for the demo, not a confidence model.
_LOW_CONFIDENCE_MARKERS = (
    "not sure",
    "not fully sure",
    "unable to confirm",
    "couldn't find",
    "could not find",
    "i don't have",
    "i do not have",
    "no data",
    "trouble reaching",
)


def looks_low_confidence(reply_text: str) -> bool:
    lowered = reply_text.lower()
    return any(marker in lowered for marker in _LOW_CONFIDENCE_MARKERS)


def maybe_escalate(chat_id: str, user_message: str, reason: str) -> dict:
    """Append a structured escalation record and return it.

    Always logs when called -- callers (bolo/voice/llm_api.py) decide
    *when* to call this: pipeline errors, low-confidence replies, or an
    explicit "talk to a human" request.
    """
    record = {
        "ts": time.time(),
        "chat_id": chat_id,
        "user_message": user_message,
        "reason": reason,
    }
    path: Path = settings.escalation_log_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.warning("Escalation logged (%s): chat_id=%s", reason, chat_id)
    return record
