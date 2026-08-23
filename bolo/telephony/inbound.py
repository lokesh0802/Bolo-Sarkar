"""Launch a Bolo Conversational AI agent on a fresh RTC channel (REST join).

Used by POST /telephony/inbound and the Vobiz Answer URL webhook.
Studio / Associate Agent is NOT used — custom LLM is always
PUBLIC_BASE_URL/v1/chat/completions (GovScheme bridge).
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Optional

from bolo.telephony.agora_agent import start_agent, stop_agent
from bolo.telephony.rtc_token import build_rtc_token

logger = logging.getLogger(__name__)

# call_uuid / channel → agent_id (so hangup can leave)
_ACTIVE: dict[str, str] = {}

_AGENT_UID = 0  # token uid=0; join uses agent_rtc_uid="0"


def launch_agent_on_channel(
    channel_name: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create channel (if needed), mint RTC token, POST Agora /join."""
    channel = channel_name or f"bolo-{uuid.uuid4().hex[:12]}"
    channel = re.sub(r"[^a-zA-Z0-9_-]", "-", channel)[:64]
    session = session_id or channel
    token = build_rtc_token(channel, uid=_AGENT_UID)
    result = start_agent(
        channel_name=channel,
        rtc_token=token,
        session_id=session,
        agent_rtc_uid="0",
    )
    agent_id = (
        result.get("agent_id")
        or result.get("data", {}).get("agent_id")
        or result.get("id")
        or ""
    )
    if agent_id:
        _ACTIVE[channel] = str(agent_id)
        _ACTIVE[session] = str(agent_id)
    logger.info(
        "launched agent channel=%s session=%s agent_id=%s",
        channel,
        session,
        agent_id,
    )
    return {
        "channel": channel,
        "session_id": session,
        "agent_id": agent_id,
        "agora": result,
    }


def stop_agent_for(key: str) -> bool:
    """Leave agent for channel or session key. Returns True if stopped."""
    agent_id = _ACTIVE.pop(key, None)
    if not agent_id:
        return False
    for k, v in list(_ACTIVE.items()):
        if v == agent_id:
            _ACTIVE.pop(k, None)
    try:
        stop_agent(agent_id)
    except Exception:
        logger.exception("stop_agent failed for %s", agent_id)
        return False
    return True
