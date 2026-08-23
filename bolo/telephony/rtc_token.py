"""Generate Agora RTC tokens for Conversational AI agent join."""

from __future__ import annotations

import time

from agora_token_builder import RtcTokenBuilder

from bolo.config import settings

# Publisher — agent must publish TTS audio into the channel.
_ROLE_PUBLISHER = 1
_DEFAULT_TTL_SEC = 3600


def build_rtc_token(
    channel_name: str,
    uid: int = 0,
    ttl_sec: int = _DEFAULT_TTL_SEC,
) -> str:
    """RTC token for `uid` in `channel_name`. uid=0 lets Agora assign a UID."""
    if not settings.agora_app_id:
        raise RuntimeError("AGORA_APP_ID not set.")
    if not settings.agora_app_certificate:
        raise RuntimeError(
            "AGORA_APP_CERTIFICATE not set — enable Primary Certificate in "
            "Agora Console and put it in .env."
        )
    expire = int(time.time()) + ttl_sec
    return RtcTokenBuilder.buildTokenWithUid(
        settings.agora_app_id,
        settings.agora_app_certificate,
        channel_name,
        uid,
        _ROLE_PUBLISHER,
        expire,
    )
