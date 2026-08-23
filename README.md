# Bolo Sarkar

**बोलो सरकार** — "speak to the government." A phone number any citizen
can call, in Hindi, English, or a mix of both, to discover government
schemes they're eligible for, get eligibility confirmed, and get a
structured application case created with SMS confirmation. Built for the
**Build with Agora Buildathon**, Problem Statement 3 (Civic & Government
Services).


## Whatsapp-Code->https://github.com/lokesh0802/Gov-scheme.git
No app to install, no data plan required, no literacy required — it works
on any phone that can receive a call.

Bolo Sarkar is the **voice layer**. It doesn't reimplement scheme search —
it wraps the existing [Whatsapp-Chatbot-Gov](../Whatsapp-Chatbot-Gov)
project (a working multi-agent RAG system: LangGraph + Chroma, 4,112 real
government schemes scraped from myscheme.gov.in) so it can be reached by
phone through **Agora's Conversational AI Engine** for the full
STT → LLM → TTS pipeline, with **Vobiz** supplying the Indian phone
number and SIP trunk. That sibling repo is never modified — see
[How this connects to Whatsapp-Chatbot-Gov](#how-this-connects-to-whatsapp-chatbot-gov)
for exactly how.

---

## Table of contents

- [Why this approach](#why-this-approach)
- [Architecture](#architecture)
- [How this connects to Whatsapp-Chatbot-Gov](#how-this-connects-to-whatsapp-chatbot-gov)
- [The Agora piece: STT, LLM, TTS](#the-agora-piece-stt-llm-tts)
- [Project layout](#project-layout)
- [Setup](#setup)
- [Running it](#running-it)
- [Testing](#testing)
- [What's built vs. what's still open](#whats-built-vs-whats-still-open)
- [Docs index](#docs-index)

---

## Why this approach

The buildathon's Problem Statement 3 wants a voice-native civic-services
agent with: dynamic (not scripted) conversation flow, session memory,
grounded answers, an external action, human escalation, and honest limits
about what the AI can't do. Rather than build a new scheme-search system
from scratch in 8 hours, Bolo Sarkar re-points a working one's "mouth and
ears" from WhatsApp text to a live phone call:

| Requirement | How it's met |
|---|---|
| Voice-native, not chatbot-with-TTS | Agora Conversational AI Engine — real ASR/TTS/turn-detection/barge-in, not a text bot piped through TTS |
| Session memory | Already exists in Whatsapp-Chatbot-Gov (`storage/conversations.py`), reused as-is |
| Dynamic conversation flow | Already exists — its LangGraph router picks intent per turn |
| External action | Case creation + SMS confirmation (`bolo/actions/cases.py`) |
| Human escalation | Logged, inspectable escalation trail (`bolo/actions/escalation.py`) |
| Defined AI limitations | Grounded retrieval, no invented scheme data, explicit "not an approval" disclaimer — see [`docs/AI_LIMITATIONS_AND_SAFETY.md`](docs/AI_LIMITATIONS_AND_SAFETY.md) |
| Multilingual / code-switching | Agora's ASR (Sarvam vendor, in particular) + the underlying LLM handle this; see [The Agora piece](#the-agora-piece-stt-llm-tts) |

The differentiator this leans on: **it works on a ₹500 keypad phone with
zero data plan.** Every other team at a hackathon like this will likely
build an app or a WebRTC-only demo — a real phone number reaches people
those can't.

---

## Architecture

```
 Citizen calls
 Vobiz DID (India number)
        │  PSTN
        ▼
 Vobiz SIP Trunk (termination/origination URIs)
        │  SIP/RTP
        ▼
 Agora Conversational AI Engine
   ├─ ASR (Sarvam or ARES — Hindi/English, code-switch capable)
   ├─ Turn detection, barge-in, VAD, noise suppression
   ├─ Custom LLM → HTTPS ──────────────┐
   └─ TTS (Sarvam — Hindi/English voice)│
                                       ▼
                     Bolo Sarkar: POST /v1/chat/completions
                     (bolo/voice/llm_api.py — OpenAI-compatible)
                                       │
                                       ▼
                     bolo/bridge/govscheme.py
                     (in-process call into the sibling repo's own
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

Agora is the primary interaction, not decorative — it owns ASR, TTS, turn
detection, and barge-in, everything that makes this a phone call instead
of a chatbot with a voice bolted on. Vobiz is carrier plumbing: it
supplies the actual number and SIP trunk, the same role a SIM card plays.
Full write-up, including the exact Agora REST contract this was built
against: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## How this connects to Whatsapp-Chatbot-Gov

**The sibling repo is never modified.** Every integration point lives in
this repo instead:

- [`bolo/bridge/govscheme.py`](bolo/bridge/govscheme.py) adds the sibling
  repo's root to `sys.path` at runtime and calls its
  `app.agents.graph.run_graph(chat_id, message)` **directly, in-process**
  — the lowest-latency option for a live call, no HTTP hop. It also calls
  that repo's own `app.rag.indexer.ensure_index_loaded()` on startup, the
  same way its own FastAPI app does, so the Chroma index gets built/loaded
  without duplicating that logic.
- This deliberately bypasses `Orchestrator.process()`, which — as of this
  writing — is stubbed to a fixed `"mil gaya"` reply for offline testing
  and skips the graph entirely. Calling `run_graph` directly gets the
  real multi-agent behaviour regardless of that stub.
- The sibling repo's own `.env`, Chroma index path, and CSV data path are
  all resolved by *its own* `app/core/config.py`, relative to its own
  files — so they're found correctly no matter what directory Bolo Sarkar
  runs from.
- One naming constraint this creates: the sibling repo's top-level
  package is literally named `app`. Bolo Sarkar's own package is
  therefore named `bolo`, not `app` — using the same name would collide
  in `sys.modules`.
- [`bolo/voice/format.py`](bolo/voice/format.py) cleans up GovScheme's
  WhatsApp-formatted replies (emoji, markdown links, numbered lists) into
  speech-friendly text **on the way out**, since the underlying prompts
  are WhatsApp-tuned and weren't rewritten for voice (that would mean
  editing the sibling repo, which was off-limits).

This was verified end-to-end while building it: the bridge was pointed at
a live query ("agricultural schemes for farmers in Gujarat"), it built the
missing Chroma index via the sibling repo's own function, and returned
real scheme results — not a mock.

---

## The Agora piece: STT, LLM, TTS

This project uses Agora's Conversational AI Engine for the **full audio
pipeline** — not just the LLM leg. Agora handles ASR (speech-to-text),
turn detection/barge-in, and TTS (text-to-speech); Bolo Sarkar only needs
to be a valid **custom LLM** behind an OpenAI-compatible endpoint.

### Getting credentials: the Agora CLI

```bash
curl -fsSL https://dl.agora.io/cli/install.sh | sh   # macOS/Linux
agora login                                           # opens a browser to authenticate
agora project create bolo-sarkar --feature rtc --feature convoai
agora project use bolo-sarkar
agora project env --shell    # prints AGORA_APP_ID, AGORA_APP_CERTIFICATE,
                              # AGORA_CUSTOMER_ID, AGORA_CUSTOMER_SECRET
```

**Free tier: 300 minutes/month** across all your projects on the combined
ASR+LLM+TTS pipeline, then $0.10/min — plenty for an 8-hour buildathon.
Full setup walkthrough, vendor comparison, and sources:
[`docs/AGORA_SETUP.md`](docs/AGORA_SETUP.md).

### Vendor choice: why Sarvam

Agora supports many ASR/TTS vendors (Deepgram, Azure, Google, ElevenLabs,
Amazon, and more — see [`docs/AGORA_SETUP.md`](docs/AGORA_SETUP.md) for
the full lists). This project's target caller may speak only Hindi, only
English, or switch mid-sentence, so Hindi support and code-switching
mattered more than vendor breadth:

- **ASR default: `ares`** — Agora's own managed ASR. Zero extra
  credentials, confirmed `hi-IN`/`en-IN` support, part of the free tier.
  Fastest path to a working demo.
- **Recommended for the real demo: `sarvam`** (both ASR and TTS) — Sarvam
  AI is built specifically for Indian languages. Its ASR supports
  automatic language detection (`language: "unknown"`), which is the
  practical way to handle a caller switching between Hindi and English
  mid-call. Its TTS has real Hindi voices. BYOK — needs a free key from
  [dashboard.sarvam.ai](https://dashboard.sarvam.ai).

Both are already wired up in
[`bolo/telephony/agora_agent.py`](bolo/telephony/agora_agent.py) — flip
between them with `AGORA_ASR_VENDOR` / `AGORA_TTS_VENDOR` in `.env`.

### The custom-LLM contract

Agora's Custom LLM integration expects a service compatible with the
OpenAI Chat Completions API. Bolo Sarkar implements that at
`POST /v1/chat/completions` ([`bolo/voice/llm_api.py`](bolo/voice/llm_api.py)):

- Streams back Server-Sent Events, ending in `data: [DONE]`.
- Sends a first `chat.completion.custom_metadata` chunk marking the reply
  `interruptable: true` — this is what makes barge-in (talking over the
  agent mid-sentence and having it stop and adapt) work.
- Reads a `?session_id=` query param off its own URL to know which
  GovScheme conversation to continue — Agora's custom-LLM request body
  carries no channel/session id of its own, so Bolo Sarkar threads one
  onto `llm.url` itself when it registers an agent for a given call
  (`agora_agent.start_agent`).

This contract was verified directly against Agora's live docs while
building it (not assumed) — see the source links in
[`bolo/voice/llm_api.py`](bolo/voice/llm_api.py) and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Project layout

```
bolo/
  main.py                FastAPI app: /v1/chat/completions, /healthz, /cases
  config.py                All env-driven settings, one place
  bridge/
    govscheme.py            In-process, read-only call into the sibling repo
  voice/
    llm_api.py                The OpenAI-compatible endpoint Agora talks to
    format.py                  WhatsApp-formatted text → speech-friendly text
  actions/
    cases.py                    External action: create case + trigger SMS
    escalation.py                 Human-escalation logging
  telephony/
    agora_agent.py                 Start/stop an Agora agent via REST
    vobiz_sms.py                     Vobiz SMS helper
docs/
  ARCHITECTURE.md          Full architecture write-up + open questions
  AGORA_SETUP.md            CLI login, free minutes, vendor choices, sources
  AI_LIMITATIONS_AND_SAFETY.md  What the AI won't do, and why
  DEMO_SCRIPT.md             ~90-second live demo walkthrough
  SUBMISSION_CHECKLIST.md      Buildathon asset checklist
tests/
  test_llm_api.py            Smoke tests for the /v1/chat/completions shape
scripts/
  dev.sh                    venv setup + run
data/                      Bolo Sarkar's own case/escalation logs (gitignored)
```

---

## Setup

```bash
git clone <this repo>
cd Bolo-Sarkar
cp .env.example .env
```

Fill in `.env`:
- `GOVSCHEME_REPO_PATH` — only if the sibling repo isn't at
  `../Whatsapp-Chatbot-Gov` relative to this one.
- `PUBLIC_BASE_URL` — your ngrok/Cloudflare Tunnel URL once you're testing
  against a real Agora agent (Agora needs to reach this service over the
  internet).
- `AGORA_*` and `SARVAM_API_KEY` — see
  [The Agora piece](#the-agora-piece-stt-llm-tts) above and
  [`docs/AGORA_SETUP.md`](docs/AGORA_SETUP.md) for the CLI flow and Console
  steps that get you these (note: the CLI only gives you `AGORA_APP_ID` —
  App Certificate and Customer ID/Secret need a manual Console step).
- `VOBIZ_*` — sign up, buy a number, and wire the Vobiz↔Agora SIP trunk
  (there's a real, documented integration guide for this — Agora isn't
  generic SIP guesswork here) via
  [`docs/VOBIZ_SETUP.md`](docs/VOBIZ_SETUP.md). Note: case confirmations
  go out over WhatsApp, not classic SMS — Vobiz doesn't have an SMS
  product, see that doc for why.

Also make sure the **sibling repo** has a valid `OPENAI_API_KEY` in *its
own* `.env` (unchanged by this project) — Bolo Sarkar's bridge calls that
repo's embedding/LLM client, which needs it.

## Running it

```bash
./scripts/dev.sh
```

First run creates a `.venv` and installs `requirements.txt` (pinned to
match the sibling repo's own dependency versions for the packages
imported in-process). Then it starts the FastAPI app on `:8080`.

Check it's alive and can reach the GovScheme pipeline:

```bash
curl localhost:8080/healthz
```

Send it a turn the way Agora would:

```bash
curl -N localhost:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"kisan yojana batao"}],"stream":true}'
```

Inspect created cases (handy for a demo, not a real admin API):

```bash
curl localhost:8080/cases
```

## Testing

```bash
.venv/bin/python -m pytest tests/ -q
```

Tests mock the GovScheme bridge, so they run without the sibling repo's
own dependencies (langgraph/chromadb) — they check this repo's own
request/response shape only.

---

## What's built vs. what's still open

**Built and verified:**
- The GovScheme bridge — tested end-to-end against the real LangGraph
  pipeline, including a live retrieval query.
- The OpenAI-compatible `/v1/chat/completions` endpoint, including the
  barge-in metadata chunk and session-id handling.
- Voice text formatting, case creation, confirmation-message trigger
  point, escalation logging.
- The Agora `join` REST request Bolo Sarkar builds, and the ASR/TTS
  vendor configs for `ares`/`sarvam`/`minimax` — matched against Agora's
  documentation.
- The Vobiz↔Agora SIP trunk path and the Vobiz WhatsApp-messaging API
  call in `bolo/telephony/vobiz_sms.py` — both matched against Vobiz's
  real docs, including a named Agora integration guide with the exact
  India SBC address (see [`docs/VOBIZ_SETUP.md`](docs/VOBIZ_SETUP.md)).

**Still open — be upfront about these, don't overstate them:**
- No live Agora or Vobiz credentials plugged in yet — `bolo/telephony/`
  hasn't been run against a real account.
- The Vobiz↔Agora trunk setup is documented but not yet walked through
  end-to-end against live accounts.
- Case-confirmation messages go out over **WhatsApp, not SMS** — Vobiz
  has no SMS product — and need a WhatsApp Business Account connected as
  a channel in Vobiz Console first (separate Meta verification step).

Full detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) → "Open
questions."

---

## Docs index

| Doc | What's in it |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Full architecture, component status table, verified Agora REST contract, open questions |
| [`docs/AGORA_SETUP.md`](docs/AGORA_SETUP.md) | Agora CLI install/login, free 300 min, ASR/TTS vendor comparison and why Sarvam, sources |
| [`docs/VOBIZ_SETUP.md`](docs/VOBIZ_SETUP.md) | Vobiz signup, phone number, the real Vobiz↔Agora SIP integration guide, WhatsApp messaging for case confirmations |
| [`docs/AI_LIMITATIONS_AND_SAFETY.md`](docs/AI_LIMITATIONS_AND_SAFETY.md) | What the AI can/can't do, known limitations, escalation policy |
| [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) | ~90-second live demo walkthrough + pre-demo checklist |
| [`docs/SUBMISSION_CHECKLIST.md`](docs/SUBMISSION_CHECKLIST.md) | Buildathon submission asset checklist, mapped to what exists here |
