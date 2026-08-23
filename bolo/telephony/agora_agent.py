"""Start/stop an Agora Conversational AI Engine agent via REST, wired to
this service's /v1/chat/completions endpoint as its custom LLM.

Request shape and vendor configs verified against Agora's docs on
2026-08-23 (see docs/AGORA_SETUP.md for the full source list and the
CLI-based credential setup this depends on):
  https://docs.agora.io/en/conversational-ai/rest-api/agent/join
  https://docs.agora.io/en/conversational-ai/models/asr/ares
  https://docs.agora.io/en/ai/models/asr/sarvam
  https://docs.agora.io/en/ai/models/tts/sarvam

Inbound PSTN uses this REST join (NOT Agora Agent Studio / Associate Agent):
Vobiz Voice XML Answer URL → POST /telephony/vobiz/answer → start_agent()
with custom LLM = PUBLIC_BASE_URL/v1/chat/completions. See routes.py.
"""

from __future__ import annotations

import base64
import logging
import uuid
from typing import Any, Optional

import httpx

from bolo.config import settings

logger = logging.getLogger(__name__)

_JOIN_URL = "https://api.agora.io/api/conversational-ai-agent/v2/projects/{app_id}/join"
_LEAVE_URL = "https://api.agora.io/api/conversational-ai-agent/v2/projects/{app_id}/agents/{agent_id}/leave"


def _auth_header() -> dict[str, str]:
    # Customer ID/Secret are the REST API credentials from Agora Console >
    # RESTful API (or `agora project env --shell` via the CLI) -- NOT the
    # App ID/Certificate used for RTC tokens.
    if not settings.agora_customer_id or not settings.agora_customer_secret:
        raise RuntimeError(
            "AGORA_CUSTOMER_ID / AGORA_CUSTOMER_SECRET not set. Run "
            "`agora project env --shell` after `agora login` to get these -- "
            "see docs/AGORA_SETUP.md."
        )
    raw = f"{settings.agora_customer_id}:{settings.agora_customer_secret}".encode("utf-8")
    return {"Authorization": f"Basic {base64.b64encode(raw).decode('ascii')}"}


def _build_asr_config() -> dict[str, Any]:
    vendor = settings.agora_asr_vendor
    if vendor == "ares":
        # Agora-managed, zero extra credentials, part of the free 300
        # min/month. Confirmed hi-IN/en-IN support.
        return {"vendor": "ares", "language": settings.agora_asr_language}
    if vendor == "sarvam":
        # BYOK. `language: "unknown"` turns on Sarvam's automatic language
        # detection, which is the practical way to get Hindi/English
        # code-switching without pinning one language per call.
        if not settings.sarvam_api_key:
            raise RuntimeError("SARVAM_API_KEY not set -- required for AGORA_ASR_VENDOR=sarvam.")
        return {
            "vendor": "sarvam",
            "params": {
                "api_key": settings.sarvam_api_key,
                "language": settings.agora_asr_language or "unknown",
            },
        }
    raise RuntimeError(
        f"Unknown AGORA_ASR_VENDOR={vendor!r}. Supported presets here: 'ares', 'sarvam'. "
        "Other vendors exist (Deepgram, Azure, Google, ...) -- add a builder for them "
        "in bolo/telephony/agora_agent.py if you want to use one, matching its docs page "
        "under https://docs.agora.io/en/ai/models/asr/."
    )


def _build_tts_config() -> dict[str, Any]:
    vendor = settings.agora_tts_vendor
    if vendor == "sarvam":
        if not settings.sarvam_api_key:
            raise RuntimeError("SARVAM_API_KEY not set -- required for AGORA_TTS_VENDOR=sarvam.")
        return {
            "vendor": "sarvam",
            "params": {
                "api_subscription_key": settings.sarvam_api_key,
                "speaker": settings.agora_tts_voice_id or settings.sarvam_tts_speaker,
                "target_language_code": "hi-IN",
            },
        }
    if vendor == "minimax":
        # Agora-managed, zero extra credentials, part of the free tier.
        # Hindi voice support is unconfirmed -- fine for an English-only
        # smoke test, not the Hindi demo. See docs/AGORA_SETUP.md.
        return {
            "vendor": "minimax",
            "params": {"voice_setting": {"voice_id": settings.agora_tts_voice_id or "English_captivating_female1"}},
        }
    raise RuntimeError(
        f"Unknown AGORA_TTS_VENDOR={vendor!r}. Supported presets here: 'sarvam' (recommended "
        "for Hindi), 'minimax' (managed, English-confirmed only). Other vendors exist "
        "(Azure, ElevenLabs, Cartesia, ...) -- add a builder for them in "
        "bolo/telephony/agora_agent.py if you want to use one, matching its docs page under "
        "https://docs.agora.io/en/ai/models/tts/."
    )


def start_agent(
    channel_name: str,
    rtc_token: str,
    session_id: Optional[str] = None,
    agent_rtc_uid: str = "0",
) -> dict[str, Any]:
    """Join an Agora RTC channel with a Conversational AI agent.

    `session_id` gets threaded onto the llm.url query string as
    `?session_id=...` -- Agora's custom-LLM request body carries no
    channel/session identifier of its own (confirmed against their docs),
    so this is how bolo/voice/llm_api.py knows which GovScheme
    conversation to continue across turns of one call. Defaults to
    `channel_name` if not given.
    """
    if not settings.agora_app_id:
        raise RuntimeError("AGORA_APP_ID not set -- see docs/AGORA_SETUP.md.")
    if not settings.public_base_url:
        raise RuntimeError(
            "PUBLIC_BASE_URL not set -- point it at your ngrok/tunnel URL for "
            "this running service before starting an agent."
        )

    session_id = session_id or channel_name
    llm_url = f"{settings.public_base_url.rstrip('/')}/v1/chat/completions?session_id={session_id}"

    # remote_rtc_uids=["*"] — subscribe to whoever joins (SIP/PSTN bridge uid
    # is not known ahead of time). Required by the join API.
    body: dict[str, Any] = {
        "name": f"bolo-sarkar-{uuid.uuid4().hex[:8]}",
        "properties": {
            "channel": channel_name,
            "token": rtc_token,
            "agent_rtc_uid": agent_rtc_uid,
            "remote_rtc_uids": ["*"],
            "idle_timeout": 120,
            "asr": _build_asr_config(),
            "llm": {
                "vendor": "custom",
                "style": "openai",
                "url": llm_url,
                "api_key": settings.llm_verification_api_key or "",
                "system_messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are Bolo Sarkar, a voice helpline for Indian "
                            "government schemes. Keep replies short, speak "
                            "naturally, and mirror whatever mix of Hindi/English "
                            "the caller uses."
                        ),
                    }
                ],
                "greeting_message": settings.agora_greeting_message,
                "failure_message": (
                    "Sorry, I'm having trouble right now. I'm noting this down "
                    "so a helpline agent can call you back."
                ),
                "max_history": 20,
                "params": {"model": "govscheme-voice"},
            },
            "tts": _build_tts_config(),
        },
    }

    resp = httpx.post(
        _JOIN_URL.format(app_id=settings.agora_app_id),
        headers={**_auth_header(), "Content-Type": "application/json"},
        json=body,
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


def stop_agent(agent_id: str) -> None:
    if not settings.agora_app_id:
        raise RuntimeError("AGORA_APP_ID not set.")
    resp = httpx.post(
        _LEAVE_URL.format(app_id=settings.agora_app_id, agent_id=agent_id),
        headers=_auth_header(),
        timeout=15.0,
    )
    resp.raise_for_status()
