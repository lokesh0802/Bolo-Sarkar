"""Case-confirmation messaging via Vobiz.

Vobiz has no separate SMS product -- its messaging API sends WhatsApp
Business messages (confirmed against its live docs on 2026-08-23:
https://vobiz.ai/docs/whatsapp/api/send-message). This still gives the
citizen a message with their case reference number, it just arrives over
WhatsApp rather than classic SMS -- update docs/DEMO_SCRIPT.md if that
distinction matters for how you narrate the demo.

Needs a WhatsApp Business Account (WABA) connected as a channel in Vobiz
Console first -- see docs/VOBIZ_SETUP.md. Function name kept as `send_sms`
since that's what bolo/actions/cases.py calls; rename if you'd rather be
precise about the channel.
"""

from __future__ import annotations

import logging

import httpx

from bolo.config import settings

logger = logging.getLogger(__name__)

_SEND_MESSAGE_URL = "https://api.vobiz.ai/api/v1/messaging/messages"


def send_sms(to_number: str, message: str) -> bool:
    if not settings.vobiz_auth_id or not settings.vobiz_auth_token:
        logger.warning(
            "VOBIZ_AUTH_ID / VOBIZ_AUTH_TOKEN not configured -- "
            "would have messaged %s: %r",
            to_number,
            message,
        )
        return False
    if not settings.vobiz_whatsapp_channel_id or not settings.vobiz_whatsapp_waba_id:
        logger.warning(
            "VOBIZ_WHATSAPP_CHANNEL_ID / VOBIZ_WHATSAPP_WABA_ID not configured "
            "-- these come from connecting a WhatsApp Business Account as a "
            "channel in Vobiz Console. Would have messaged %s: %r",
            to_number,
            message,
        )
        return False
    try:
        resp = httpx.post(
            _SEND_MESSAGE_URL,
            headers={
                "X-Auth-ID": settings.vobiz_auth_id,
                "X-Auth-Token": settings.vobiz_auth_token,
                "Content-Type": "application/json",
            },
            json={
                "channel_id": settings.vobiz_whatsapp_channel_id,
                "waba_id": settings.vobiz_whatsapp_waba_id,
                "to": to_number,
                "type": "text",
                "text": {"body": message},
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return True
    except Exception:
        logger.exception("Vobiz message send failed for %s", to_number)
        return False
