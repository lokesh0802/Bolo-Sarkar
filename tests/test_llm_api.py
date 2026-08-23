"""Smoke tests for the /v1/chat/completions wrapper.

These stub out the GovScheme bridge so they run without the sibling repo's
.venv (langgraph/chromadb) installed -- they only check that this repo's
own request/response shape is correct.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from bolo.main import app

client = TestClient(app)


def test_healthz_ok():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert "govscheme_bridge_ready" in resp.json()


def test_chat_completions_streaming_shape():
    with patch("bolo.voice.llm_api.run_govscheme", return_value=["Namaste! *Yojana* found: PM-KISAN 🌾"]):
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "govscheme-voice",
                "messages": [{"role": "user", "content": "kisan yojana batao"}],
                "stream": True,
            },
        )
    assert resp.status_code == 200
    body = resp.text
    assert "chat.completion.custom_metadata" in body
    assert "PM-KISAN" in body
    assert "🌾" not in body  # emoji stripped for TTS
    assert body.strip().endswith("data: [DONE]")


def test_chat_completions_non_streaming_shape():
    with patch("bolo.voice.llm_api.run_govscheme", return_value=["Hello there"]):
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "govscheme-voice",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["choices"][0]["message"]["content"] == "Hello there."


def test_session_id_from_query_param_reaches_bridge():
    with patch("bolo.voice.llm_api.run_govscheme", return_value=["ok"]) as mock_run:
        client.post(
            "/v1/chat/completions?session_id=call-123",
            json={"messages": [{"role": "user", "content": "hi"}], "stream": False},
        )
    assert mock_run.call_args[0][0] == "call-123"
