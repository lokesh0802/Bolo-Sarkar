# AI Limitations & Safety

## What the AI can do
- Search and explain real government schemes (4,112 schemes scraped from
  myscheme.gov.in, indexed in Chroma by the sibling GovScheme project).
- Ask clarifying questions to narrow down eligibility.
- Compare schemes against each other.
- Create a structured "interest in applying" case and send an SMS
  reference number.

## What the AI cannot and must not do
- **It cannot approve, reject, or submit a government application.** Any
  "case" it creates is a lead for a human to review
  (`status: "pending_review"` in `bolo/actions/cases.py`), never a
  submission. The SMS sent after case creation says this explicitly.
- **It will not invent scheme names, amounts, or eligibility rules.**
  GovScheme's retrieval is grounded in the indexed CSV; if nothing
  relevant is retrieved, the underlying prompts are written to say so
  rather than guess (see the sibling repo's `app/agents/prompts.py`,
  which Bolo Sarkar does not modify).
- **It is not a licensed advisor.** It surfaces scheme information, not
  legal, financial, or medical advice.
- **It does not collect payment details, passwords, or ID numbers over
  the call.** Nothing in this codebase asks for or stores that.

## Known limitations (be upfront about these in the demo)
- **Voice formatting is a cleanup layer, not native.** GovScheme's prompts
  are WhatsApp-tuned (emoji, markdown links, numbered lists).
  `bolo/voice/format.py` strips/reflows that for TTS on the way out, but
  the underlying phrasing wasn't written for speech. This is a deliberate
  tradeoff from being told not to touch the sibling repo's code.
- **Session continuity depends on a query-param trick.** Agora's
  custom-LLM request carries no call/session id of its own; Bolo Sarkar
  injects one into `llm.url` when it starts an agent for a given channel
  (see `docs/ARCHITECTURE.md`). Until that's wired end-to-end against a
  live Agora project, concurrent calls would share one GovScheme session.
- **Telephony (Vobiz SIP trunk → Agora, and the Vobiz SMS API) is
  unverified** — built against documentation and placeholders, not a live
  account. See `docs/ARCHITECTURE.md` → Open Questions.
- **Confidence detection is a keyword heuristic**, not a real confidence
  model (`bolo/actions/escalation.py::looks_low_confidence`). It's honest
  about being cheap: good enough to demonstrate the escalation path
  exists and logs correctly, not a production safety system.
- **The RAG index must be built before answers work.** Bolo Sarkar calls
  the sibling repo's own `ensure_index_loaded()` on startup so this
  usually happens automatically, but it still needs a valid
  `OPENAI_API_KEY` in *that* repo's `.env` (unchanged by this project).

## Human escalation
Every pipeline error and every reply that looks low-confidence gets
logged to `data/escalations.jsonl` (`bolo/actions/escalation.py`) with the
caller's message and a reason. There's no live human agent wired up for
the buildathon demo — the point being demonstrated is that the AI knows
when to defer and leaves an inspectable trail when it does, not that a
callback actually happens within the demo window.
