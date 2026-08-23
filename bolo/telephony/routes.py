"""HTTP routes for telephony: SIP setup + non-Studio inbound (REST join).

Inbound path (no Agora Agent Studio / Associate Agent):
  Vobiz Voice XML App Answer URL → POST /telephony/vobiz/answer
    → mint RTC token + start_agent() with custom LLM
    → return Vobiz XML <Dial><User>sip:…</User></Dial> into the RTC bridge

Agora Phone Numbers → Associate Agent is Studio-only and is NOT used here.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from bolo.config import settings
from bolo.telephony import sip_setup
from bolo.telephony.inbound import launch_agent_on_channel, stop_agent_for

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telephony", tags=["telephony"])


class InboundStartBody(BaseModel):
    channel: Optional[str] = None
    session_id: Optional[str] = Field(default=None, description="GovScheme chat id")


@router.get("/sip-setup")
def sip_setup_guide() -> dict[str, Any]:
    """Paste values + checklist for Vobiz ↔ Agora (non-Studio inbound)."""
    return sip_setup.build_sip_setup()


@router.get("/agent-blueprint")
def agent_blueprint() -> dict[str, Any]:
    """ASR/LLM/TTS config used by REST start_agent (not Studio)."""
    try:
        return sip_setup.agent_studio_blueprint()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/inbound")
def start_inbound_agent(body: InboundStartBody = InboundStartBody()) -> dict[str, Any]:
    """Manual/test: create channel + RTC token + start_agent (custom LLM)."""
    try:
        return launch_agent_on_channel(
            channel_name=body.channel,
            session_id=body.session_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("inbound start_agent failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _sip_bridge_uri(channel: str) -> str:
    """SIP URI Vobiz should Dial so the PSTN leg joins the same RTC channel.

    Set AGORA_SIP_BRIDGE_URI in .env, e.g. from Agora Media Gateway:
      sip:{channel}@your-mgw.example.com
    `{channel}` is substituted. If unset, we Dial the India Agora SBC with
    the channel as the user — that only works if you have a SIP→RTC bridge
    (Media Gateway). Agora Phone Numbers + Associate Agent is Studio and
    is intentionally not used.
    """
    template = (settings.agora_sip_bridge_uri or "").strip()
    if template:
        return template.replace("{channel}", channel)
    host = sip_setup.AGORA_SBC_INDIA_HOST
    return f"sip:{channel}@{host}"


def _vobiz_params(request: Request, form: dict) -> dict[str, str]:
    q = request.query_params
    out: dict[str, str] = {}
    for key in ("CallUUID", "From", "To", "Direction", "call_uuid"):
        val = form.get(key) or q.get(key)
        if val is not None:
            out[key] = str(val)
    return out


def _vobiz_answer_xml(channel: str, sip_uri: str) -> str:
    # Vobiz Voice XML — Dial SIP User bridges A-leg into B-leg.
    # https://docs.vobiz.ai/xml/dial/user
    safe_uri = escape(sip_uri)
    hangup = f"{settings.public_base_url.rstrip('/')}/telephony/vobiz/hangup"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Response>\n"
        f'  <Dial timeout="45" timeLimit="3600" action="{escape(hangup)}" '
        'method="POST" redirect="false">\n'
        f"    <User>{safe_uri}</User>\n"
        "  </Dial>\n"
        "  <Hangup/>\n"
        "</Response>\n"
    )


@router.api_route("/vobiz/answer", methods=["GET", "POST"])
async def vobiz_answer(request: Request) -> Response:
    """Vobiz Voice XML Answer URL — start Bolo REST agent, return Dial XML.

    Console: Vobiz → Applications → Answer URL =
      POST {PUBLIC_BASE_URL}/telephony/vobiz/answer
    Attach that Application to DID +918071581370 (not the Agora SIP trunk).
    """
    form: dict = {}
    if request.method == "POST":
        try:
            form = dict(await request.form())
        except Exception:
            form = {}
    params = _vobiz_params(request, form)
    call_uuid = params.get("CallUUID") or params.get("call_uuid") or "unknown"
    call_id = str(call_uuid).replace(" ", "")
    channel = f"bolo-{call_id}"[:64]
    logger.info(
        "vobiz answer CallUUID=%s From=%s To=%s Direction=%s → channel=%s",
        params.get("CallUUID"),
        params.get("From"),
        params.get("To"),
        params.get("Direction"),
        channel,
    )

    try:
        launched = launch_agent_on_channel(channel_name=channel, session_id=channel)
        channel = launched["channel"]
    except Exception:
        logger.exception("failed to start_agent on Vobiz answer")
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<Response>\n"
            "  <Speak>Sorry, the helpline is temporarily unavailable. "
            "Please try again shortly.</Speak>\n"
            "  <Hangup/>\n"
            "</Response>\n"
        )
        return Response(content=xml, media_type="application/xml")

    sip_uri = _sip_bridge_uri(channel)
    xml = _vobiz_answer_xml(channel, sip_uri)
    logger.info("vobiz answer dialing %s (agent_id=%s)", sip_uri, launched.get("agent_id"))
    return Response(content=xml, media_type="application/xml")


@router.api_route("/vobiz/hangup", methods=["GET", "POST"])
async def vobiz_hangup(request: Request) -> Response:
    """Vobiz Hangup / Dial action URL — stop the REST agent if still up."""
    form: dict = {}
    if request.method == "POST":
        try:
            form = dict(await request.form())
        except Exception:
            form = {}
    params = _vobiz_params(request, form)
    call_uuid = params.get("CallUUID") or params.get("call_uuid") or ""
    channel = f"bolo-{str(call_uuid).replace(' ', '')}"[:64] if call_uuid else ""
    if channel:
        stop_agent_for(channel)
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?>\n<Response/>\n',
        media_type="application/xml",
    )
