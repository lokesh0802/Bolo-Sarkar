"""Smoke tests for SIP setup helpers (no live Vobiz/Agora needed)."""

from bolo.telephony.sip_setup import (
    AGORA_SBC_INDIA_HOST,
    agent_studio_blueprint,
    build_sip_setup,
)


def test_sip_setup_includes_india_sbc(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.devtunnels.ms")
    monkeypatch.setenv("VOBIZ_DID_NUMBER", "+911171366938")
    monkeypatch.setenv("AGORA_APP_ID", "test-app")
    monkeypatch.setenv("AGORA_TTS_VENDOR", "minimax")
    # Reload settings after env patches
    from bolo import config

    monkeypatch.setattr(
        config,
        "settings",
        config.Settings(
            public_base_url="https://example.devtunnels.ms",
            vobiz_did_number="+911171366938",
            agora_app_id="test-app",
            agora_tts_vendor="minimax",
        ),
    )
    from bolo.telephony import sip_setup

    monkeypatch.setattr(sip_setup, "settings", config.settings)

    guide = build_sip_setup()
    assert guide["inbound"]["vobiz_origination_uri"]["uri"] == AGORA_SBC_INDIA_HOST
    assert any("amanya" in t["symptom"].lower() for t in guide["troubleshooting_amanya"])
    assert guide["llm_url_for_agora_agent"].endswith("/v1/chat/completions")


def test_agent_blueprint_custom_llm(monkeypatch):
    from bolo import config
    from bolo.telephony import sip_setup

    monkeypatch.setattr(
        config,
        "settings",
        config.Settings(
            public_base_url="https://example.devtunnels.ms",
            agora_asr_vendor="ares",
            agora_tts_vendor="minimax",
            agora_greeting_message="Namaste",
        ),
    )
    monkeypatch.setattr(sip_setup, "settings", config.settings)
    # agora_agent reads settings at call time
    from bolo.telephony import agora_agent

    monkeypatch.setattr(agora_agent, "settings", config.settings)

    bp = agent_studio_blueprint()
    assert bp["llm"]["vendor"] == "custom"
    assert bp["llm"]["url"] == "https://example.devtunnels.ms/v1/chat/completions"
    assert bp["asr"]["vendor"] == "ares"
    assert bp["tts"]["vendor"] == "minimax"
