# Submission checklist

Mapping the buildathon's asset list to what's here (or what's still open).

| Asset | Where |
|---|---|
| Working prototype | The live call itself, once telephony is wired (see Open Questions in `ARCHITECTURE.md`) |
| GitHub repo | This repo. Sibling `Whatsapp-Chatbot-Gov` repo is unmodified and referenced, not forked. |
| README + architecture diagram | [`README.md`](../README.md), [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) |
| Demo video | *(record after telephony is wired)* |
| Live-demo plan | [`docs/DEMO_SCRIPT.md`](DEMO_SCRIPT.md) |
| Agora usage explanation | [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — "Why this shape" + "Contract with Agora" |
| API/LLM/speech providers list | Vobiz (SIP trunk + WhatsApp messaging), Agora (ASR: `ares`/`sarvam`, TTS: `sarvam`), Sarvam AI (Hindi ASR/TTS), OpenAI (`gpt-4o-mini` by default, via the sibling repo's own config) |
| Conversational AI capabilities list | Barge-in (`interruptable` metadata), per-call session memory (query-param session id + GovScheme's own conversation storage), dynamic LangGraph-driven flow (not scripted), grounded retrieval (4,112 real schemes), human escalation |
| AI limitations / safety doc | [`docs/AI_LIMITATIONS_AND_SAFETY.md`](AI_LIMITATIONS_AND_SAFETY.md) |
| Target user description | Rural/semi-urban citizens without smartphones or a reliable data plan — works on any phone, no app required |
| Problem statement | Civic & Government Services — schemes discovery, eligibility, application leads |
| External action description | Structured case creation + SMS confirmation (`bolo/actions/cases.py`) |
| Future evolution | Outbound reminder calls, IVR digit fallback for very noisy lines, more schemes, real human-handoff queue instead of a log file |

## Still open (be honest about these, don't overstate)
- No live Agora or Vobiz credentials plugged in yet — everything in
  `bolo/telephony/` is built against documentation, not tested against a
  real account.
- Demo video and a real end-to-end phone call recording come after
  telephony is wired.
