# Architecture

Bolo Sarkar turns the existing [Whatsapp-Chatbot-Gov](../../Whatsapp-Chatbot-Gov)
project — a working multi-agent RAG system (LangGraph + Chroma, 4,112 real
government schemes from myscheme.gov.in) — into a phone line. A citizen
dials a number, talks in Hindi/English/mixed, and gets the same
eligibility checks, comparisons, and scheme search that project already
does for WhatsApp — spoken, with no app and no data plan required.

```
 Citizen calls
 Vobiz DID (India number)
        │  PSTN
        ▼
 Vobiz SIP Trunk (termination/origination URIs)
        │  SIP/RTP
        ▼
 Agora Conversational AI Engine
   ├─ ASR (Hindi/English)
   ├─ Turn detection, barge-in, VAD, noise suppression
   ├─ Custom LLM → HTTPS ──────────────┐
   └─ TTS (Hindi/English voice)        │
                                       ▼
                     Bolo Sarkar: POST /v1/chat/completions
                     (bolo/voice/llm_api.py — OpenAI-compatible)
                                       │
                                       ▼
                     bolo/bridge/govscheme.py
                     (in-process call, sibling repo's own
                      app.agents.graph.run_graph — unmodified)
                                       │
                                       ▼
                     Whatsapp-Chatbot-Gov's LangGraph pipeline
                     (router → retrieve → eligibility/compare/
                      search/detail/select → finalize)
                                       │
                                       ▼
                     Chroma (4,112 schemes) — that repo's own data/
```

## Why this shape

**Agora is the primary interaction, not decorative.** It owns ASR, TTS,
turn detection, and barge-in — everything that makes this a phone call
instead of a chatbot with a voice bolted on. Bolo Sarkar's only job is to
be a valid OpenAI-compatible "brain" behind Agora's Custom LLM contract.

**Vobiz is carrier plumbing.** It supplies the actual Indian phone number
and SIP trunk; Agora answers the call. Same role a SIM card plays.

**We never modify Whatsapp-Chatbot-Gov.** Per explicit instruction, that
repo stays untouched. Bolo Sarkar reads its code at runtime instead of
duplicating it:

- `bolo/bridge/govscheme.py` adds that repo's root to `sys.path` and calls
  its `app.agents.graph.run_graph(chat_id, message)` and
  `app.rag.indexer.ensure_index_loaded()` directly, in-process — lowest
  latency for a live call, no HTTP hop, and always the real behaviour
  (not the temporarily-stubbed `Orchestrator.process`, which currently
  bypasses the graph — see the comment at the top of that file).
- Its own `.env`, Chroma index, and CSV data are all resolved via that
  repo's own `app/core/config.py` (path-relative to its own files), so
  they're found correctly regardless of Bolo Sarkar's working directory.
- The one naming constraint this creates: Bolo Sarkar's own top-level
  package is `bolo`, not `app` — the sibling repo's top-level package
  really is named `app`, and importing two different `app` packages into
  one process would collide.

**Voice formatting happens on the way out, not by editing prompts.**
`bolo/voice/format.py` strips emoji/markdown/links from GovScheme's
WhatsApp-formatted replies and turns lists into short spoken sentences,
since the underlying prompts are tuned for WhatsApp and we can't change
them at the source. This is a real limitation, documented in
[AI_LIMITATIONS_AND_SAFETY.md](AI_LIMITATIONS_AND_SAFETY.md).

## Component map

| Piece | File | Status |
|---|---|---|
| OpenAI-compatible LLM endpoint | [`bolo/voice/llm_api.py`](../bolo/voice/llm_api.py) | Built, tested |
| Voice text cleanup | [`bolo/voice/format.py`](../bolo/voice/format.py) | Built, tested |
| In-process GovScheme bridge | [`bolo/bridge/govscheme.py`](../bolo/bridge/govscheme.py) | Built, verified against the real graph |
| Case creation + confirmation message (external action) | [`bolo/actions/cases.py`](../bolo/actions/cases.py), [`bolo/telephony/vobiz_sms.py`](../bolo/telephony/vobiz_sms.py) | Built against Vobiz's real WhatsApp-messaging API (Vobiz has no separate SMS product); unverified against a live WABA channel yet |
| Human escalation logging | [`bolo/actions/escalation.py`](../bolo/actions/escalation.py) | Built |
| Agora agent start/stop (REST) | [`bolo/telephony/agora_agent.py`](../bolo/telephony/agora_agent.py) | Built against Agora's documented `join` contract; not yet called against a live Agora project |
| Vobiz SIP trunk → Agora channel | [`docs/VOBIZ_SETUP.md`](VOBIZ_SETUP.md) | **Documented, not yet executed.** Agora is a named Vobiz integration with a real setup guide (exact India SBC address included) — no longer an open question, just not walked through end-to-end yet. |

## Contract with Agora (verified 2026-08-23)

Fetched directly from Agora's docs while building this:
- [Start a conversational AI agent (`join`)](https://docs.agora.io/en/conversational-ai/rest-api/agent/join)
- [Custom LLM](https://docs.agora.io/en/conversational-ai/develop/custom-llm)

Key points that shaped the code:
- `POST https://api.agora.io/api/conversational-ai-agent/v2/projects/:appid/join`,
  `Authorization: Basic base64(customer_id:customer_secret)` — these are
  separate REST credentials from the App ID/Certificate.
- The custom LLM request body is OpenAI-shaped (`messages`, `stream: true`)
  and **carries no channel/session identifier**. Since GovScheme's graph
  needs a stable `chat_id` per call, we thread a `?session_id=` query
  param onto `llm.url` ourselves when we call `join` for a given channel
  (see `agora_agent.start_agent`) — the endpoint reads it back on every
  turn (`bolo/voice/llm_api.py:_session_id`).
- The streamed SSE response's first chunk must be
  `object: "chat.completion.custom_metadata"` with a `metadata.interruptable`
  flag — that's the barge-in control mentioned in the brief.

## Open questions to resolve before the demo

1. **PSTN/SIP access.** Resolved — no need to contact Agora Support for
   this path. Vobiz has a named, documented Agora integration (exact
   India regional SBC address, trunk setup steps) — see
   [docs/VOBIZ_SETUP.md](VOBIZ_SETUP.md). Still needs to actually be
   walked through once against live accounts before demo day.
2. **Vobiz credentials + case-confirmation messaging.** Resolved — see
   [docs/VOBIZ_SETUP.md](VOBIZ_SETUP.md). One correction worth flagging:
   Vobiz has no separate SMS product, so confirmations go out over
   WhatsApp via Vobiz's messaging API instead, which needs a WhatsApp
   Business Account connected as a channel (a separate Meta verification
   step) before it can actually send.
3. **ASR/TTS vendor + credentials.** Resolved — see
   [docs/AGORA_SETUP.md](AGORA_SETUP.md) for the CLI login flow, the
   Console steps for App Certificate / Customer ID+Secret (not printed by
   the CLI, corrected from an earlier version of that doc), the free
   300 min/month, and why `ares` (ASR) / `sarvam` (ASR+TTS) were picked
   for Hindi/English code-switching specifically.
4. **Fallback plan**: if the Vobiz↔Agora trunk isn't wired up in time,
   demo over Agora's own WebRTC test client instead — still real Agora
   Conversational AI, still this same `/v1/chat/completions` endpoint,
   just no phone number yet.
