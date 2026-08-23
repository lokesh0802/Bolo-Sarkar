# Agora setup (CLI, credentials, free minutes, vendor choices)

Everything here is sourced directly from Agora's own docs, fetched while
building this project on **2026-08-23**. Sources are linked inline —
re-check them if something's changed since.

## 1. Install the CLI and log in

```bash
# macOS/Linux
curl -fsSL https://dl.agora.io/cli/install.sh | sh

# Windows (PowerShell)
irm https://dl.agora.io/cli/install.ps1 | iex
```

```bash
agora login
```

This opens a browser to authenticate the CLI against your Agora account
(sign up first at [agora.io](https://www.agora.io) if you don't have one —
no credit card needed to start).

Sources: [Introducing the Agora CLI](https://www.agora.io/en/blog/introducing-the-agora-cli/), [Agora CLI docs](https://docs.agora.io/en/introduction/agora-cli)

## 2. Create a project with Conversational AI enabled

```bash
agora project create bolo-sarkar --feature rtc --feature convoai
agora project use bolo-sarkar
```

## 3. Get credentials

```bash
agora project env --shell
```

**Corrected from an earlier version of this doc**, based on actually
running this: it only prints `AGORA_PROJECT_ID`, `AGORA_PROJECT_NAME`,
`AGORA_REGION`, `AGORA_APP_ID`, and the enabled-feature flags — **not**
`AGORA_APP_CERTIFICATE` or the `AGORA_CUSTOMER_ID`/`AGORA_CUSTOMER_SECRET`
pair. Those two still need a manual step in Agora Console:

- **App Certificate:** Console → your project's detail page → click
  **Enable** under Primary Certificate → copy it once enabled.
  ([Source](https://docs.agora.io/en/realtime-media/rtc/reference/console-overview))
- **Customer ID / Customer Secret** (used for the `join`/`leave` REST auth
  in `bolo/telephony/agora_agent.py`): Console → **Developer Toolkit** →
  **RESTful API** → **Add a secret**. The Customer Secret can only be
  downloaded **once** — save it somewhere safe immediately.
  ([Source](https://docs.agora.io/en/api-reference/api-ref/signaling/authentication))

Run `agora project doctor` any time to check the project is actually
ready (features enabled, credentials valid).

## 4. The free tier

**300 minutes free per month**, across all your projects, on the
Conversational AI Engine "Audio Task" — the combined ASR + LLM + TTS
pipeline for one call. This applies whether you use Agora-managed
credentials for the built-in vendors (Deepgram, OpenAI, MiniMax, etc.) or
bring your own key (BYOK) for another vendor — same $0.10/min rate once
the free minutes run out, either way. Plenty for an 8-hour buildathon.

Source: [Conversational AI Pricing](https://docs.agora.io/en/conversational-ai/overview/pricing)

## 5. ASR/TTS/LLM vendor choice — and why Hindi support drove ours

Agora's Conversational AI Engine is vendor-agnostic on all three legs of
the pipeline; you pick per-project. Full lists as documented:

- **ASR/STT vendors:** Amazon Transcribe, ARES (Agora's own), AssemblyAI,
  Deepgram, Google, Microsoft Azure, OpenAI, Sarvam, Speechmatics, xAI
- **TTS vendors:** Amazon Polly, Cartesia, Deepgram, ElevenLabs, Fish
  Audio, Google, Hume AI, Microsoft Azure, MiniMax, Mistral, Murf, OpenAI,
  Rime, Sarvam, Typecast, xAI
- **LLM vendors:** (only relevant if you're *not* using a custom LLM like
  this project does) Amazon Bedrock, Azure OpenAI, Claude/Anthropic, Dify,
  Google Gemini, Google Vertex AI, Groq, OpenAI, xAI Grok

Source: [docs.agora.io/llms/ai.txt index](https://docs.agora.io/llms/ai.txt)

Bolo Sarkar's target caller is a citizen who may only speak Hindi, only
English, or switch between the two mid-sentence — so ASR/TTS quality on
that specific case matters more than the vendor list's breadth. Two
presets are wired up in [`bolo/telephony/agora_agent.py`](../bolo/telephony/agora_agent.py)
(`_build_asr_config` / `_build_tts_config`); set `AGORA_ASR_VENDOR`
/ `AGORA_TTS_VENDOR` in `.env` to pick one:

| | Vendor | Setup | Why |
|---|---|---|---|
| ASR default | **`ares`** | Zero extra credentials, Agora-managed | Confirmed `hi-IN`/`en-IN` support among ARES's 36 languages, no separate account needed — fastest path to a working demo. [Source](https://docs.agora.io/en/conversational-ai/models/asr/ares) |
| ASR/TTS recommended | **`sarvam`** | BYOK — [dashboard.sarvam.ai](https://dashboard.sarvam.ai) key | Sarvam AI is built specifically for Indian languages. Its ASR (`language: "unknown"`) does automatic language detection, which is the practical way to handle a caller switching between Hindi and English mid-sentence without pinning one language per call. TTS has real Hindi voices (`speaker: "anushka"` etc.), unlike most Western vendors' Hindi support, which is often unconfirmed or absent. [ASR source](https://docs.agora.io/en/ai/models/asr/sarvam), [TTS source](https://docs.agora.io/en/ai/models/tts/sarvam) |
| TTS confirmed alternative | `minimax` | Zero extra credentials, Agora-managed | **Correction from an earlier version of this doc**: has real Hindi voices — confirmed directly in Studio's voice picker (`speech-2.6-turbo`, voice "Hindi Female 2 V1"), not just a doc claim. A solid zero-BYOK alternative to Sarvam for Hindi TTS. [Source](https://docs.agora.io/en/ai/models/tts/minimax) |

**Recommended combo for the actual demo:** `AGORA_ASR_VENDOR=sarvam` +
`AGORA_TTS_VENDOR=sarvam` once you have a Sarvam key — it's the only
combo here with confirmed Hindi support on both legs and genuine
code-switching handling. Use `ares` for ASR while waiting on that key;
it's a fine fallback and it's what's zero-config by default in
[`bolo/config.py`](../bolo/config.py).

## 6. Exact request shapes Bolo Sarkar builds

For reference, `bolo/telephony/agora_agent.py::start_agent` sends these on
`properties.asr` / `properties.tts` when calling `join`:

```json
// AGORA_ASR_VENDOR=ares
{ "vendor": "ares", "language": "hi-IN" }

// AGORA_ASR_VENDOR=sarvam
{ "vendor": "sarvam", "params": { "api_key": "...", "language": "unknown" } }

// AGORA_TTS_VENDOR=sarvam
{ "vendor": "sarvam", "params": { "api_subscription_key": "...", "speaker": "anushka", "target_language_code": "hi-IN" } }
```

These come from vendor-specific doc pages fetched through an automated
summarizer, not copy-pasted by hand — treat them as "verified starting
point," and cross-check against Agora Console's own agent config UI (or
`agora project doctor`) the first time you actually call `join`, in case
a field name has since changed.

## 7. Vobiz SIP trunk → Agora: resolved

There **is** a documented Vobiz↔Agora integration (Agora is a named
integration in Vobiz's docs, not generic SIP guesswork) — full steps,
including the exact India regional SBC address, are in
[VOBIZ_SETUP.md](VOBIZ_SETUP.md).
