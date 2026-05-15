import os
import pytest


def test_missing_gmail_address_raises(monkeypatch):
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "testpass")
    monkeypatch.setenv("ZENDESK_BASE_URL", "https://example.zendesk.com")
    monkeypatch.setenv("ZENDESK_AUTH_TOKEN", "abc123")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123456")

    import importlib
    import sys
    # Remove config from cache if present to force fresh import
    if 'config' in sys.modules:
        del sys.modules['config']

    # config module-level code runs on import; the _require call will fail
    with pytest.raises(EnvironmentError, match="GMAIL_ADDRESS"):
        import config as cfg


def test_all_vars_present_returns_values(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "test@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "apppass")
    monkeypatch.setenv("ZENDESK_BASE_URL", "https://example.zendesk.com")
    monkeypatch.setenv("ZENDESK_AUTH_TOKEN", "abc123")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123456")

    import config as cfg
    assert cfg._require("GMAIL_ADDRESS") == "test@example.com"
    assert cfg._require("SLACK_CHANNEL_ID") == "C123456"


def test_empty_string_treated_as_missing(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "")

    import config as cfg
    with pytest.raises(EnvironmentError, match="GMAIL_ADDRESS"):
        cfg._require("GMAIL_ADDRESS")
