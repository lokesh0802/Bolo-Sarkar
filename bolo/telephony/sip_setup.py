"""Vobiz ↔ Agora telephony wiring for inbound/outbound phone calls.

Inbound (non-Studio): Vobiz Voice XML Answer URL → Bolo
POST /telephony/vobiz/answer → start_agent() with custom LLM.
Studio / Phone Numbers Associate Agent is NOT required.

Sources (fetched 2026-08-23):
  https://vobiz.ai/docs/integrations/agora
  https://vobiz.ai/docs/xml/overview/how-it-works
  https://docs.agora.io/en/ai/studio/deploy/sip-trunk
"""

from __future__ import annotations

from typing import Any

from bolo.config import settings
from bolo.telephony.agora_agent import _build_asr_config, _build_tts_config

# India (+91) and APAC — Agora regional SBC for inbound (Vobiz → Agora).
# Paste into Vobiz Origination URI *without* the sip: prefix.
AGORA_SBC_INDIA_UDP = "sbc-ap-south.viblinx.com:5060"
AGORA_SBC_INDIA_TLS = "sbc-ap-south.viblinx.com:5061"
AGORA_SBC_INDIA_HOST = "sbc-ap-south.viblinx.com"

# Agora SIP egress IPs for India (+91) — whitelist on Vobiz outbound ACL
# if you prefer IP auth instead of (or alongside) SIP credentials.
AGORA_SIP_EGRESS_IPS_INDIA = [
    "3.111.249.176",
    "15.207.132.164",
    "13.205.109.117",
    "13.127.230.35",
    "13.200.127.200",
    "13.205.242.117",
    "13.232.246.98",
    "13.235.159.216",
    "43.204.61.200",
    "52.66.173.52",
    "65.1.195.82",
    "65.1.38.21",
]


def llm_url_for_studio() -> str:
    """Custom-LLM URL to paste into Agora Agent Studio (no session_id —
    Studio assigns its own session; Bolo falls back gracefully)."""
    base = (settings.public_base_url or "").rstrip("/")
    if not base:
        return ""
    return f"{base}/v1/chat/completions"


def agent_studio_blueprint() -> dict[str, Any]:
    """Exact ASR / LLM / TTS blocks to configure on the published Agora agent
    that answers inbound SIP calls to the Vobiz DID."""
    llm_url = llm_url_for_studio()
    return {
        "name": "bolo-sarkar",
        "asr": _build_asr_config(),
        "llm": {
            "vendor": "custom",
            "style": "openai",
            "url": llm_url,
            "api_key": settings.llm_verification_api_key or "",
            "greeting_message": settings.agora_greeting_message,
            "failure_message": (
                "Sorry, I'm having trouble right now. I'm noting this down "
                "so a helpline agent can call you back."
            ),
            "max_history": 20,
            "params": {"model": "govscheme-voice"},
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
        },
        "tts": _build_tts_config() if settings.agora_tts_vendor else None,
        "notes": [
            "Studio NOT required. Inbound uses Bolo REST start_agent via Vobiz Answer URL.",
            "Vobiz → Voice App Answer URL = {PUBLIC_BASE_URL}/telephony/vobiz/answer",
            "POST /telephony/inbound to smoke-test start_agent without a phone call.",
            "Keep PUBLIC_BASE_URL tunnel up while testing.",
        ],
    }


def build_sip_setup() -> dict[str, Any]:
    """Checklist + paste values for Vobiz inbound/outbound ↔ Agora SIP."""
    did = settings.vobiz_did_number or "+91XXXXXXXXXX"
    missing: list[str] = []
    if not settings.public_base_url:
        missing.append("PUBLIC_BASE_URL")
    if not settings.vobiz_did_number:
        missing.append("VOBIZ_DID_NUMBER")
    if not settings.agora_app_id:
        missing.append("AGORA_APP_ID")
    if not settings.agora_tts_vendor:
        missing.append("AGORA_TTS_VENDOR")

    inbound_ready_hints = [
        "Vobiz: Voice XML Application Answer URL = PUBLIC_BASE_URL/telephony/vobiz/answer (NOT Agora SIP trunk)",
        "Vobiz: Attach that Application to DID +918071581370 (unlink from Agora-bound inbound trunk)",
        "Bolo: REST start_agent on answer — Studio / Phone Numbers Associate Agent NOT required",
        "Optional: AGORA_SIP_BRIDGE_URI=sip:{channel}@your-media-gateway (SIP→RTC audio bridge)",
        "Bolo: ./scripts/dev.sh running and tunnel PUBLIC_BASE_URL reachable",
    ]

    unavailable_fix = [
        {
            "symptom": "Number unavailable / amanya / dead air on dial",
            "likely_cause": "DID still on Agora SIP inbound trunk, or Voice App not attached",
            "fix": (
                "Vobiz → unlink DID from Agora inbound trunk; attach Voice XML App "
                "with Answer URL = PUBLIC_BASE_URL/telephony/vobiz/answer"
            ),
        },
        {
            "symptom": "Call connects, agent starts in Agora logs, but no two-way audio",
            "likely_cause": "No SIP→RTC bridge (Media Gateway). Dial URI alone is not enough.",
            "fix": (
                "Set AGORA_SIP_BRIDGE_URI to an Agora Media Gateway SIP URI that joins "
                "the same RTC channel. Phone Numbers Associate Agent is Studio — not used."
            ),
        },
        {
            "symptom": "Connects but no speech / one-way audio",
            "likely_cause": "Wrong regional SBC or TLS/UDP mismatch on bridge leg",
            "fix": f"Use {AGORA_SBC_INDIA_UDP} (UDP) for +91; match Transport on both sides",
        },
        {
            "symptom": "Agent silent after connect",
            "likely_cause": "Custom LLM URL unreachable from Agora",
            "fix": (
                "Keep tunnel up; curl PUBLIC_BASE_URL/healthz then confirm "
                "start_agent llm.url matches llm_url_for_studio()"
            ),
        },
    ]

    return {
        "status": "incomplete" if missing else "configured_locally",
        "missing_env": missing,
        "your_did": did,
        "inbound": {
            "direction": (
                "Caller → Vobiz DID → Voice XML Answer URL → Bolo start_agent "
                "(custom LLM) → Dial SIP bridge into RTC channel"
            ),
            "studio_required": False,
            "vobiz_voice_app": {
                "answer_url": f"{(settings.public_base_url or '').rstrip('/')}/telephony/vobiz/answer",
                "hangup_url": f"{(settings.public_base_url or '').rstrip('/')}/telephony/vobiz/hangup",
                "steps": [
                    "Vobiz Console → Applications → Create Voice XML App",
                    "Answer URL = POST answer_url above; Hangup URL = hangup_url",
                    f"Attach Application to {did}",
                    "Unlink this DID from any inbound SIP trunk pointing at Agora SBC "
                    "(that path needs Studio Associate Agent — we do not use it)",
                ],
            },
            "bolo_rest": {
                "start": "POST /telephony/inbound",
                "answer_webhook": "POST /telephony/vobiz/answer",
                "custom_llm": llm_url_for_studio(),
            },
            "agora_console_leftovers": [
                "App ID + Certificate + Customer ID/Secret in .env (already)",
                "Do NOT Associate Agent on Agora Phone Numbers (Studio path)",
                "Optional Media Gateway SIP URI → AGORA_SIP_BRIDGE_URI for audio bridge",
            ],
            "checklist": inbound_ready_hints,
        },
        "outbound": {
            "direction": "Agora agent/campaign → Vobiz outbound trunk → PSTN",
            "vobiz_steps": [
                "Credentials List → Add Credential (save password once)",
                "Outbound Trunks → Create → attach credential → copy SIP Domain (<id>.sip.vobiz.ai)",
            ],
            "agora_import_fields": {
                "Phone Number": did,
                "Vendor": "SIP Trunk",
                "SIP Trunk Address": settings.vobiz_sip_domain or "<trunk-id>.sip.vobiz.ai",
                "Transport Protocol": "UDP",
                "SIP Trunk Username": settings.vobiz_sip_username or "<credential username>",
                "SIP Trunk Password": "(set VOBIZ_SIP_PASSWORD — never returned by this API)",
            },
            "agora_egress_ips_india": AGORA_SIP_EGRESS_IPS_INDIA,
            "console_credentials": "https://console.vobiz.ai/app/sip/out/credentials",
            "console_trunks": "https://console.vobiz.ai/app/sip/out/trunks",
        },
        "llm_url_for_agora_agent": llm_url_for_studio(),
        "troubleshooting_amanya": unavailable_fix,
        "docs": {
            "vobiz_agora": "https://vobiz.ai/docs/integrations/agora",
            "agora_sip": "https://docs.agora.io/en/ai/studio/deploy/sip-trunk",
            "vobiz_xml": "https://vobiz.ai/docs/xml/overview/how-it-works",
            "vobiz_quickstart": "https://www.vobiz.ai/docs/quick-start",
        },
    }
