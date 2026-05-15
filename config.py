import os


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {name}")
    return value


GMAIL_ADDRESS = _require("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = _require("GMAIL_APP_PASSWORD")
ZENDESK_BASE_URL = _require("ZENDESK_BASE_URL")
ZENDESK_AUTH_TOKEN = _require("ZENDESK_AUTH_TOKEN")
SLACK_BOT_TOKEN = _require("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = _require("SLACK_CHANNEL_ID")
