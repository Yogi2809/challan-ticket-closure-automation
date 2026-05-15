import os
import sys
import importlib
import pytest


def _reload_config():
    sys.modules.pop("config", None)
    import config as cfg
    return cfg


def test_missing_gmail_address_raises(monkeypatch):
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "testpass")
    monkeypatch.setenv("ZENDESK_BASE_URL", "https://example.zendesk.com")
    monkeypatch.setenv("ZENDESK_AUTH_TOKEN", "abc123")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123456")

    with pytest.raises(EnvironmentError, match="GMAIL_ADDRESS"):
        _reload_config()


def test_all_vars_present_returns_values(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "test@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "apppass")
    monkeypatch.setenv("ZENDESK_BASE_URL", "https://example.zendesk.com")
    monkeypatch.setenv("ZENDESK_AUTH_TOKEN", "abc123")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123456")

    cfg = _reload_config()
    assert cfg._require("GMAIL_ADDRESS") == "test@example.com"
    assert cfg._require("SLACK_CHANNEL_ID") == "C123456"


def test_empty_string_treated_as_missing(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "testpass")
    monkeypatch.setenv("ZENDESK_BASE_URL", "https://example.zendesk.com")
    monkeypatch.setenv("ZENDESK_AUTH_TOKEN", "abc123")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123456")

    with pytest.raises(EnvironmentError, match="GMAIL_ADDRESS"):
        _reload_config()
