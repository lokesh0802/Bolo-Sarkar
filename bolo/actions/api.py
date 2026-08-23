"""HTTP endpoints for Agora Studio's "Custom Tools" function-calling.

Why this file exists: if the agent is Studio-native (Models tab = a
managed LLM + a Knowledge Base, no custom LLM backend -- see
docs/VOICE_AGENT_SYSTEM_PROMPT.md), nothing in that path creates a case
or logs an escalation on its own. Studio's Knowledge Base is retrieval
only. These two routes are what a Custom Tool in the Actions tab calls,
so the buildathon's mandatory "external action" and "human escalation"
requirements are still met even without routing through
bolo/voice/llm_api.py.

Exact Custom Tool config for each route is in
docs/VOICE_AGENT_SYSTEM_PROMPT.md, matched against Agora's documented
Custom Tool format (method, URL, headers, body template with {{}}
placeholders, JSON Schema parameters) -- fetched 2026-08-23:
https://docs.agora.io/en/ai/studio/build/custom-tools
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from bolo.actions.cases import create_case
from bolo.actions.escalation import maybe_escalate
from bolo.config import settings

router = APIRouter(prefix="/actions", tags=["actions"])


def _check_auth(authorization: Optional[str]) -> None:
    """Optional shared-secret check. Configure the same value as
    ACTIONS_API_KEY in .env and as the Custom Tool's `Authorization:
    Bearer <value>` header in Studio. Skipped entirely if unset."""
    if not settings.actions_api_key:
        return
    expected = f"Bearer {settings.actions_api_key}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")


class CreateCaseRequest(BaseModel):
    phone_number: str = Field(..., description="Caller's phone number in E.164 format, e.g. +919876543210")
    scheme_name: str = Field(..., description="Exact scheme name the caller wants to apply for")
    profile_summary: str = Field(
        "", description="Short summary of what the caller told you relevant to eligibility"
    )
    call_id: str = Field("", description="Any call/session identifier you have, else leave blank")


class CreateCaseResponse(BaseModel):
    case_id: str
    status: str
    confirmation_message: str


@router.post("/create-case", response_model=CreateCaseResponse)
def create_case_action(
    payload: CreateCaseRequest, authorization: Optional[str] = Header(default=None)
) -> CreateCaseResponse:
    """Log the caller's interest in a scheme and (if Vobiz WhatsApp
    messaging is configured) send them a confirmation with a case
    reference number. Never an approval or submission -- say so on the
    call regardless of what this returns."""
    _check_auth(authorization)
    chat_id = payload.call_id or f"studio-{payload.phone_number}"
    record = create_case(
        chat_id=chat_id,
        phone_number=payload.phone_number,
        scheme_name=payload.scheme_name,
        profile_summary=payload.profile_summary,
    )
    return CreateCaseResponse(
        case_id=record["case_id"],
        status=record["status"],
        confirmation_message=(
            f"Logged as {record['case_id']}, status pending review. This is not an approval."
        ),
    )


class EscalateRequest(BaseModel):
    reason: str = Field(..., description="Why you're escalating: e.g. 'caller asked for a human', 'no matching scheme found', 'ambiguous eligibility'")
    user_message: str = Field("", description="What the caller actually asked or said, in their words")
    call_id: str = Field("", description="Any call/session identifier you have, else leave blank")


class EscalateResponse(BaseModel):
    logged: bool
    message: str


@router.post("/escalate", response_model=EscalateResponse)
def escalate_action(
    payload: EscalateRequest, authorization: Optional[str] = Header(default=None)
) -> EscalateResponse:
    """Log that you couldn't fully resolve something on this call. Call
    this whenever RULE 10 in the system prompt applies -- genuine
    uncertainty, an explicit request for a human, or an out-of-scope
    query you've already redirected to WhatsApp but want on record."""
    _check_auth(authorization)
    chat_id = payload.call_id or "studio-unknown"
    maybe_escalate(chat_id=chat_id, user_message=payload.user_message, reason=payload.reason)
    return EscalateResponse(logged=True, message="Noted for follow-up.")
