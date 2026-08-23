# Vobiz setup (phone number, SIP trunk → Agora, WhatsApp messaging)

Sourced directly from Vobiz's live docs (`vobiz.ai/docs/...`), fetched
**2026-08-23**. Their real docs live at `vobiz.ai/docs/*` — `docs.vobiz.ai`
redirects there. Re-check the linked pages if something's changed since.

## 1. Sign up

[console.vobiz.ai/app/register](https://console.vobiz.ai/app/register) —
**₹25 free credit** on signup, no card required to start.

Your dashboard shows two credentials every API call needs:

```
X-Auth-ID: MA_XXXXXXXX
X-Auth-Token: <your-auth-token>
```

Put these in `.env` as `VOBIZ_AUTH_ID` / `VOBIZ_AUTH_TOKEN`. Treat the
Auth Token like a password — Vobiz's own docs say so explicitly, and it's
only shown once.

Source: [Quick Start](https://vobiz.ai/docs/quick-start), [Authentication](https://vobiz.ai/docs/api-reference/authentication)

## 2. Buy a phone number

In Vobiz Console, browse the DID inventory (India 140/1600/92 series, or
international) and purchase one. Put it in `.env` as `VOBIZ_DID_NUMBER`
(E.164 format, e.g. `+91XXXXXXXXXX`).

Source: [Phone Numbers](https://vobiz.ai/docs/account-phone-number)

## 3. Wire the phone number to Agora — there's a real integration guide

Agora is a **named, documented Vobiz integration** (confirmed — it's not
generic SIP guesswork). Full guide:
[vobiz.ai/docs/integrations/agora](https://vobiz.ai/docs/integrations/agora)

While Bolo is running, open the live checklist (paste values + "amanya"
fixes):

```bash
curl localhost:8080/telephony/sip-setup
curl localhost:8080/telephony/agent-blueprint
```

### Inbound (a citizen calling in — the path this project actually uses)

1. **Get the regional SBC address for India:**
   ```
   sbc-ap-south.viblinx.com
   ```
   (enter it *without* the `sip:` prefix wherever Vobiz asks for it;
   port `5060` / UDP is fine if the form accepts `host:port`)
2. In Vobiz Console → **Origination URIs**, create a URI with that host,
   Transport **UDP**, Active **On**.
3. Create an **inbound SIP trunk** with that URI as **Primary URI**, then
   **Link Numbers** → your DID. Status must be Enabled and
   **Linked Numbers (1)**.
4. In **Agora Console**:
   - **Agents** → create agent whose custom LLM URL is
     `{PUBLIC_BASE_URL}/v1/chat/completions` (see `/telephony/agent-blueprint`)
   - **Publish** the agent
   - **Phone Numbers** → import DID (Vendor = SIP Trunk) if not already
   - Edit number → **Inbound Settings** → assign that agent
     (Unassigned = call accepts then drops / sounds unavailable)
5. Keep `./scripts/dev.sh` + your tunnel up, then dial the Vobiz number.

### Outbound (only needed if you later add outbound reminder calls)

1. In Vobiz Console, create a **SIP credential** (username/password) —
   shown once, stored hashed after that. Put them in `.env` as
   `VOBIZ_SIP_USERNAME` / `VOBIZ_SIP_PASSWORD`.
2. Create an **outbound trunk** in Vobiz attaching that credential. Vobiz
   generates a SIP domain: `<trunk-id>.sip.vobiz.ai` → `VOBIZ_SIP_DOMAIN`.
3. In Agora Console, **Add Phone Number** with Vendor = SIP Trunk, using
   your Vobiz number, that SIP domain, UDP transport, and the credential
   from step 1.

### If the number says unavailable / "amanya hai"

That message is almost always **PSTN/SIP routing**, not Bolo's LLM:

| Check | Where |
|---|---|
| DID linked to inbound trunk, trunk Enabled | Vobiz → Inbound Trunks |
| Origination URI = `sbc-ap-south.viblinx.com` (no `sip:`) | Vobiz → Origination URIs |
| Number not stuck on an XML App with a dead webhook | Vobiz → Voice / DID routing |
| Inbound agent assigned + **published** | Agora → Phone Numbers → Inbound Settings |
| Tunnel + Bolo up | `curl $PUBLIC_BASE_URL/healthz` |

Vobiz Call Logs: [console.vobiz.ai/app/sip/logs](https://console.vobiz.ai/app/sip/logs)

This resolves what was an open question in earlier project notes ("how
does a Vobiz SIP trunk reach an Agora RTC channel") — it's a documented,
supported path, not something to negotiate with Agora Support.

## 4. Case-confirmation messages: WhatsApp, not classic SMS

**Vobiz has no separate SMS product.** Its messaging API sends WhatsApp
Business messages instead — confirmed against
[Send a Message](https://vobiz.ai/docs/whatsapp/api/send-message). This
project's `bolo/telephony/vobiz_sms.py` is written against that real API
(function kept named `send_sms` since that's what
[`bolo/actions/cases.py`](../bolo/actions/cases.py) calls — rename it if
the WhatsApp-vs-SMS distinction matters for how you narrate the demo).

```
POST https://api.vobiz.ai/api/v1/messaging/messages
Headers: X-Auth-ID, X-Auth-Token, Content-Type: application/json
Body:
{
  "channel_id": "<uuid>",
  "waba_id": "<whatsapp business account id>",
  "to": "+919876543210",
  "type": "text",
  "text": { "body": "..." }
}
```

Before this works you need a **WhatsApp Business Account connected as a
channel** in Vobiz Console — that's a separate onboarding step (Meta
Business verification) beyond just having a Vobiz account. Put the
resulting IDs in `.env` as `VOBIZ_WHATSAPP_CHANNEL_ID` /
`VOBIZ_WHATSAPP_WABA_ID` once you've done that.

**If that onboarding won't finish in the buildathon window:**
`send_sms()` degrades gracefully — it logs what it would have sent
instead of failing the call, so the demo still works end-to-end; you'd
just narrate "the SMS/WhatsApp confirmation is wired up, sending is
pending WABA verification" rather than showing a phone receiving it live.

## 5. What's still unverified

- Phone number purchase pricing (India series rates) — check Console if budget matters.
- End-to-end live call against *your* DID until inbound trunk + published agent are assigned
  (use `/telephony/sip-setup` + Vobiz Call Logs while testing).
