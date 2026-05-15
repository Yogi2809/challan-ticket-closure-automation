import os
import pytest
from unittest.mock import patch, MagicMock


ENV = {
    "GMAIL_ADDRESS": "test@example.com",
    "GMAIL_APP_PASSWORD": "pass",
    "ZENDESK_BASE_URL": "https://cars24help.zendesk.com",
    "ZENDESK_AUTH_TOKEN": "abc123",
    "SLACK_BOT_TOKEN": "xoxb-test",
    "SLACK_CHANNEL_ID": "C123",
}


@patch.dict(os.environ, ENV)
def test_close_ticket_returns_true_on_200():
    import sys
    sys.modules.pop("config", None)
    sys.modules.pop("zendesk_client", None)
    from zendesk_client import close_ticket
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("zendesk_client.requests.put", return_value=mock_response) as mock_put:
        result = close_ticket("12345")

    assert result is True
    mock_put.assert_called_once()
    call_kwargs = mock_put.call_args
    assert "12345" in call_kwargs.args[0]
    assert call_kwargs.kwargs["headers"]["Authorization"] == "Basic abc123"


@patch.dict(os.environ, ENV)
def test_close_ticket_returns_false_on_non_200():
    import sys
    sys.modules.pop("config", None)
    sys.modules.pop("zendesk_client", None)
    from zendesk_client import close_ticket
    mock_response = MagicMock()
    mock_response.status_code = 422
    mock_response.text = "Unprocessable Entity"

    with patch("zendesk_client.requests.put", return_value=mock_response):
        result = close_ticket("99999")

    assert result is False


@patch.dict(os.environ, ENV)
def test_close_ticket_sends_correct_payload():
    import sys
    sys.modules.pop("config", None)
    sys.modules.pop("zendesk_client", None)
    from zendesk_client import close_ticket
    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("zendesk_client.requests.put", return_value=mock_response) as mock_put:
        close_ticket("T001")

    payload = mock_put.call_args.kwargs["json"]
    assert payload["ticket"]["status"] == "solved"
    assert payload["ticket"]["comment"]["public"] is True
    assert "Cars24" in payload["ticket"]["comment"]["body"]
    assert payload["ticket"]["custom_fields"][0]["id"] == 9759821503503
    assert payload["ticket"]["custom_fields"][0]["value"] == "sent_for_clearance"
    assert payload["ticket"]["custom_fields"][1]["id"] == 11876293100303
    assert payload["ticket"]["custom_fields"][1]["value"] == "query_"
