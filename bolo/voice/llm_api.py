"""OpenAI-compatible /v1/chat/completions endpoint.

This is what you set as `llm.url` when starting an Agora Conversational AI
Engine agent (see bolo/telephony/agora_agent.py). Agora's engine handles
ASR/TTS/turn-detection/barge-in and calls this endpoint like any OpenAI
chat-completions server; we translate that into a call into the GovScheme
LangGraph pipeline and stream back a spoken-friendly reply.

Contract verified against Agora's docs on 2026-08-23:
  https://docs.agora.io/en/conversational-ai/develop/custom-llm
  https://docs.agora.io/en/conversational-ai/rest-api/agent/join

Two things from that contract that shape this file:
  1. `stream` will be true and a response MUST be SSE `data: {...}` chunks
     ending in `data: [DONE]`.
  2. The request body carries NO channel/session identifier. GovScheme's
     graph needs a stable `chat_id` per call to keep conversation state
     (see storage/conversations.py in the sibling repo), so we thread a
     `session_id` query param onto `llm.url` ourselves when we register
     the agent for a given call (see agora_agent.start_agent). Until a
     real call comes in with that query param wired up, everything falls
     back to a single shared "voice-default" session -- fine for a
     WebRTC test-client demo, not for concurrent real calls.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Iterator, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from bolo.actions.escalation import looks_low_confidence, maybe_escalate
from bolo.bridge.govscheme import run_govscheme
from bolo.voice.format import parts_to_speech

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="allow")
    role: str = "user"
    content: Any = ""

    def text(self) -> str:
        """Content is usually a string, but the OpenAI schema also allows a
        list of content parts (e.g. for multimodal input) -- flatten to text."""
        if isinstance(self.content, str):
            return self.content
        if isinstance(self.content, list):
            parts = []
            for part in self.content:
                if isinstance(part, dict) and "text" in part:
                    parts.append(str(part["text"]))
            return " ".join(parts)
        return str(self.content) if self.content else ""


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str = "govscheme-voice"
    messages: list[ChatMessage] = Field(default_factory=list)
    stream: bool = True
    user: Optional[str] = None


def _session_id(payload: ChatCompletionRequest, http_request: Request) -> str:
    """Best-effort per-call session id. Checked in priority order:

    1. `?session_id=` query param -- set by us in agora_agent.start_agent,
       this is the reliable path once telephony is wired up.
    2. OpenAI-style `user` field, in case a given Agora config populates it.
    3. `X-Session-Id` header, in case a proxy/tunnel injects one.
    4. A fixed fallback -- fine for solo WebRTC testing, NOT safe for
       multiple concurrent real calls (they'd share one GovScheme session).
    """
    qp = http_request.query_params.get("session_id")
    if qp:
        return qp
    if payload.user:
        return payload.user
    header_val = http_request.headers.get("x-session-id")
    if header_val:
        return header_val
    return "voice-default"


def _last_user_message(messages: list[ChatMessage]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            text = m.text()
            if text:
                return text
    return ""


def _sse(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


def _stream_reply(completion_id: str, model: str, text: str, interruptable: bool) -> Iterator[bytes]:
    created = int(time.time())

    # Agora-specific first chunk: only the `metadata` field is read from
    # this one, `choices` is ignored. Marks whether this response can be
    # cut off mid-utterance (barge-in) -- true by default since our
    # replies are short; flip to false around irreversible confirmations
    # if you want those read out in full.
    yield _sse(
        {
            "id": completion_id,
            "object": "chat.completion.custom_metadata",
            "choices": [],
            "metadata": {"interruptable": interruptable},
        }
    )
    yield _sse(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}],
        }
    )
    yield _sse(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
    )
    yield b"data: [DONE]\n\n"


@router.post("/v1/chat/completions")
async def chat_completions(payload: ChatCompletionRequest, http_request: Request):
    chat_id = _session_id(payload, http_request)
    user_message = _last_user_message(payload.messages)

    try:
        parts = run_govscheme(chat_id, user_message)
    except Exception:
        logger.exception("GovScheme pipeline failed for chat_id=%s", chat_id)
        parts = [
            "Sorry, I'm having trouble reaching the schemes database right now. "
            "I'm noting this down so a helpline agent can call you back."
        ]
        maybe_escalate(chat_id, user_message, reason="govscheme_pipeline_error")

    speech_text = parts_to_speech(parts) or "Sorry, could you say that again?"

    if looks_low_confidence(speech_text):
        maybe_escalate(chat_id, user_message, reason="low_confidence_reply")

    completion_id = f"chatcmpl-{uuid.uuid4().hex}"

    if payload.stream:
        return StreamingResponse(
            _stream_reply(completion_id, payload.model, speech_text, interruptable=True),
            media_type="text/event-stream",
        )

    return JSONResponse(
        {
            "id": completion_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": payload.model,
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": speech_text}, "finish_reason": "stop"}
            ],
        }
    )
