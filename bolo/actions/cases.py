"""External action: create a structured scheme-application case and
notify the citizen by SMS.

This is Bolo-Sarkar's own case store (data/cases.json) -- separate from,
and never writing to, Whatsapp-Chatbot-Gov's storage/conversations.py.
Wire a call to `create_case(...)` in wherever your voice-side "finalize
application" turn is detected (e.g. from bolo/voice/llm_api.py once you
have a signal for "user confirmed, create the case").
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from bolo.config import settings
from bolo.telephony.vobiz_sms import send_sms


def create_case(chat_id: str, phone_number: str, scheme_name: str, profile_summary: str) -> dict[str, Any]:
    case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
    record = {
        "case_id": case_id,
        "chat_id": chat_id,
        "phone_number": phone_number,
        "scheme_name": scheme_name,
        "profile_summary": profile_summary,
        "created_at": time.time(),
        "status": "pending_review",
    }
    _append_case(record)
    if phone_number:
        send_sms(
            phone_number,
            f"Your reference for {scheme_name} is {case_id}. "
            "We'll follow up if anything else is needed. This is not a "
            "confirmation of approval.",
        )
    return record


def list_cases() -> list[dict[str, Any]]:
    path: Path = settings.cases_store_path
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _append_case(record: dict[str, Any]) -> None:
    path: Path = settings.cases_store_path
    path.parent.mkdir(parents=True, exist_ok=True)
    cases = list_cases()
    cases.append(record)
    path.write_text(json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8")
