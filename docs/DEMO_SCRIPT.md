# Demo script

~60–90 seconds, mirrors the buildathon brief's own example scenario.

1. Citizen calls the Vobiz number (or joins the Agora WebRTC test client
   if PSTN isn't approved yet). Speaks Hindi, mentions a farming problem.
2. Partway through, switches to English. The AI keeps following along —
   this is Agora's ASR + GovScheme's own language handling, not anything
   Bolo Sarkar adds.
3. AI asks one clarifying question instead of dumping a scheme list.
4. **Interrupt the AI mid-sentence.** It stops and adapts rather than
   restarting — this is the `interruptable: true` metadata chunk from
   `bolo/voice/llm_api.py`. This moment is worth more than any extra
   feature: it's the clearest proof this is a real voice interface.
5. AI retrieves matching real schemes from Chroma (4,112 real schemes,
   not fixtures) and walks through eligibility.
6. AI says it's not fully sure about one detail, offers escalation —
   pull up `data/escalations.jsonl` live to show the logged entry.
7. AI creates a structured case and reads back the key details before
   confirming — being explicit that this is a lead, not an approval.
8. Citizen gets an SMS with a case reference number
   (`bolo/actions/cases.py` → `bolo/telephony/vobiz_sms.py`) — show the
   phone receiving it.

## Fallback if PSTN isn't wired up in time
Demo over Agora's own WebRTC test client instead of a real phone call.
Still real Agora Conversational AI Engine, still hitting this same
`/v1/chat/completions` endpoint — say explicitly that telephony is wired
and pending Agora/Vobiz approval, per `docs/ARCHITECTURE.md`. Safer than a
live PSTN call breaking in front of judges.

## Before you're in front of judges
- [ ] `PUBLIC_BASE_URL` in `.env` points at a live tunnel, not a stale one
      (ngrok URLs rotate on restart).
- [ ] The sibling repo's Chroma index is built and `OPENAI_API_KEY` is
      valid there (`curl localhost:8080/healthz` — check `govscheme_bridge_ready`).
- [ ] Have 2–3 real scheme names ready to ask about that you've confirmed
      return good results, plus one you expect low confidence on.
