"""Turn GovScheme's WhatsApp-formatted replies into text fit for TTS.

We were explicitly asked not to touch the Whatsapp-Chatbot-Gov repo, so we
can't rewrite its prompts to be voice-native at the source. Instead we
clean up on the way out: strip emoji/markdown/links, and turn numbered or
bulleted lists into short spoken sentences. This is a best-effort layer,
not a substitute for voice-tuned prompts -- see docs/AI_LIMITATIONS_AND_SAFETY.md.
"""

from __future__ import annotations

import re

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001f300-\U0001faff"
    "\U00002600-\U000027bf"
    "\U0001f1e6-\U0001f1ff"
    "\U00002700-\U000027bf"
    "]+",
    flags=re.UNICODE,
)
_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BARE_URL = re.compile(r"https?://\S+")
_BULLET_PREFIX = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+", re.MULTILINE)
_WHITESPACE = re.compile(r"\s+")


def whatsapp_to_speech(text: str) -> str:
    """Clean up one WhatsApp-formatted reply chunk for TTS."""
    if not text:
        return ""

    cleaned = _MD_LINK.sub(r"\1", text)
    cleaned = _BARE_URL.sub("", cleaned)
    cleaned = _EMOJI_PATTERN.sub("", cleaned)
    cleaned = cleaned.replace("*", "").replace("_", "").replace("`", "")

    spoken_lines = []
    for line in cleaned.split("\n"):
        line = _BULLET_PREFIX.sub("", line).strip()
        if line:
            spoken_lines.append(line)

    joined = ". ".join(spoken_lines)
    joined = _WHITESPACE.sub(" ", joined).strip()
    if joined and not joined.endswith((".", "?", "!")):
        joined += "."
    return joined


def parts_to_speech(parts: list[str]) -> str:
    """Join GovScheme's `parts` list (already split for WhatsApp's 4000-char
    limit) back into one spoken response."""
    cleaned = [whatsapp_to_speech(p) for p in parts if p and p.strip()]
    return " ".join(c for c in cleaned if c)
