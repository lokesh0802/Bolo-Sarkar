"""All environment-driven settings for Bolo-Sarkar, in one place.

Mirrors the pattern used by the sibling Whatsapp-Chatbot-Gov project, but
lives entirely in this repo -- we never write to or import config from
that project. We only read its *code* at runtime (see bolo/bridge/govscheme.py).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def _default_govscheme_path() -> Path:
    # Sensible default: sibling checkout next to this repo, e.g.
    # ~/Documents/Projects/{Bolo-Sarkar, Whatsapp-Chatbot-Gov}
    return _PROJECT_ROOT.parent / "Whatsapp-Chatbot-Gov"


@dataclass(frozen=True)
class Settings:
    # --- Service ---
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8080")))
    public_base_url: str = field(default_factory=lambda: os.getenv("PUBLIC_BASE_URL", ""))
    llm_verification_api_key: str = field(
        default_factory=lambda: os.getenv("LLM_VERIFICATION_API_KEY", "")
    )
    # Shared secret for bolo/actions/api.py's Custom Tool endpoints
    # (POST /actions/create-case, /actions/escalate) -- these are called
    # directly by Agora Studio's "Custom Tools" function-calling feature
    # when the agent is Studio-native (managed LLM + Knowledge Base, no
    # custom LLM backend). Put the same value in the tool's Headers panel
    # in Studio (Authorization: Bearer <value>) -- Studio encrypts header
    # values, so this is safe to set even for a public tunnel URL. Leave
    # blank to skip verification (fine for a demo).
    actions_api_key: str = field(default_factory=lambda: os.getenv("ACTIONS_API_KEY", ""))

    # --- GovScheme bridge (read-only import of the sibling repo) ---
    govscheme_repo_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("GOVSCHEME_REPO_PATH") or str(_default_govscheme_path())
        )
    )

    # --- Agora Conversational AI Engine ---
    # App ID / App Certificate: from Agora Console > Project.
    agora_app_id: str = field(default_factory=lambda: os.getenv("AGORA_APP_ID", ""))
    agora_app_certificate: str = field(
        default_factory=lambda: os.getenv("AGORA_APP_CERTIFICATE", "")
    )
    # Customer ID / Secret: REST API credentials, Agora Console > RESTful API.
    # NOT the same as App ID/Certificate above.
    agora_customer_id: str = field(default_factory=lambda: os.getenv("AGORA_CUSTOMER_ID", ""))
    agora_customer_secret: str = field(
        default_factory=lambda: os.getenv("AGORA_CUSTOMER_SECRET", "")
    )
    # ASR/TTS vendor choice. Supported presets (see
    # bolo/telephony/agora_agent.py for the exact request bodies each
    # builds, and docs/AGORA_SETUP.md for how to set each one up):
    #   ASR "ares"     -- Agora's own managed ASR. Zero extra credentials,
    #                     part of the free 300 min/month, confirmed
    #                     hi-IN/en-IN support. Good default to get a demo
    #                     running fast.
    #   ASR/TTS "sarvam" -- Sarvam AI, BYOK (needs SARVAM_API_KEY below).
    #                     Built specifically for Indian languages with real
    #                     Hindi/English code-switching -- the better choice
    #                     once you have a key, since code-switching is this
    #                     project's core differentiator.
    #   TTS "minimax"  -- Agora-managed, zero extra credentials, part of
    #                     the free tier. Confirmed Hindi voices exist
    #                     (e.g. "Hindi Female 2 V1", speech-2.6-turbo) --
    #                     seen directly in Studio's voice picker, so this
    #                     is a real Hindi option now, not just a fallback.
    # No default for TTS vendor on purpose -- pick one explicitly.
    # NOTE: this whole preset system is for the REST agora_agent.py path
    # (bolo/telephony/agora_agent.py). The current build config's this
    # via Agora Studio's UI directly instead -- see
    # docs/VOICE_AGENT_SYSTEM_PROMPT.md -- so these settings aren't read
    # by that flow. Keeping them accurate anyway for whenever the REST
    # path (outbound calls, programmatic agents) gets used.
    agora_asr_vendor: str = field(default_factory=lambda: os.getenv("AGORA_ASR_VENDOR", "ares"))
    agora_asr_language: str = field(
        default_factory=lambda: os.getenv("AGORA_ASR_LANGUAGE", "hi-IN")
    )
    agora_tts_vendor: str = field(default_factory=lambda: os.getenv("AGORA_TTS_VENDOR", ""))
    agora_tts_voice_id: str = field(default_factory=lambda: os.getenv("AGORA_TTS_VOICE_ID", ""))
    # Sarvam credentials -- only needed if AGORA_ASR_VENDOR/AGORA_TTS_VENDOR
    # is "sarvam". Get a key from https://dashboard.sarvam.ai.
    sarvam_api_key: str = field(default_factory=lambda: os.getenv("SARVAM_API_KEY", ""))
    sarvam_tts_speaker: str = field(
        default_factory=lambda: os.getenv("SARVAM_TTS_SPEAKER", "anushka")
    )
    agora_greeting_message: str = field(
        default_factory=lambda: os.getenv(
            "AGORA_GREETING_MESSAGE",
            "Namaste! I can help you find government schemes you're eligible for. "
            "Aap Hindi ya English mein baat kar sakte hain.",
        )
    )
    # Optional SIP URI template for Vobiz <Dial><User> after REST start_agent.
    # Use Agora Media Gateway (or any SIP→RTC bridge). `{channel}` is replaced.
    # Example: sip:{channel}@your-media-gateway.example.com
    # Leave blank to Dial sip:{channel}@sbc-ap-south.viblinx.com (needs a
    # SIP→RTC bridge on that host — Phone Numbers Associate Agent is Studio
    # and is NOT used).
    agora_sip_bridge_uri: str = field(
        default_factory=lambda: os.getenv("AGORA_SIP_BRIDGE_URI", "")
    )

    # --- Vobiz (telephony: DID number, SIP trunk, messaging) ---
    # Auth ID looks like "MA_XXXXXXXX", from the Vobiz Console dashboard
    # after signup. See docs/VOBIZ_SETUP.md.
    vobiz_auth_id: str = field(default_factory=lambda: os.getenv("VOBIZ_AUTH_ID", ""))
    vobiz_auth_token: str = field(default_factory=lambda: os.getenv("VOBIZ_AUTH_TOKEN", ""))
    vobiz_did_number: str = field(default_factory=lambda: os.getenv("VOBIZ_DID_NUMBER", ""))
    # Outbound SIP trunk (Agora → Vobiz → PSTN). From Vobiz Outbound Trunks
    # SIP Domain + Credentials List. Used by GET /telephony/sip-setup and
    # when importing the number in Agora Console (Vendor = SIP Trunk).
    # See docs/VOBIZ_SETUP.md and https://vobiz.ai/docs/integrations/agora
    vobiz_sip_domain: str = field(default_factory=lambda: os.getenv("VOBIZ_SIP_DOMAIN", ""))
    vobiz_sip_username: str = field(default_factory=lambda: os.getenv("VOBIZ_SIP_USERNAME", ""))
    vobiz_sip_password: str = field(default_factory=lambda: os.getenv("VOBIZ_SIP_PASSWORD", ""))
    # Vobiz has no separate SMS product -- case confirmations go out over
    # WhatsApp via Vobiz's messaging API instead, which needs a WhatsApp
    # Business Account (WABA) connected as a channel in Vobiz Console.
    vobiz_whatsapp_channel_id: str = field(
        default_factory=lambda: os.getenv("VOBIZ_WHATSAPP_CHANNEL_ID", "")
    )
    vobiz_whatsapp_waba_id: str = field(
        default_factory=lambda: os.getenv("VOBIZ_WHATSAPP_WABA_ID", "")
    )

    # --- Local data (owned by Bolo-Sarkar only) ---
    # `os.getenv(NAME, default)` only falls back when the key is *unset* --
    # an .env line like `CASES_STORE_PATH=` sets it to an empty string,
    # which still counts as "set" and short-circuits the default, turning
    # into Path("") == Path(".") -- a directory, not a file. `or` treats
    # empty-string the same as unset.
    cases_store_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("CASES_STORE_PATH") or str(_PROJECT_ROOT / "data" / "cases.json")
        )
    )
    escalation_log_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("ESCALATION_LOG_PATH") or str(_PROJECT_ROOT / "data" / "escalations.jsonl")
        )
    )


settings = Settings()
