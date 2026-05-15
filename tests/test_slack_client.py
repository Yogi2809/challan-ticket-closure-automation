import os
import sys
import pytest
from unittest.mock import patch, MagicMock


ENV = {
    "GMAIL_ADDRESS": "test@example.com",
    "GMAIL_APP_PASSWORD": "pass",
    "ZENDESK_BASE_URL": "https://example.zendesk.com",
    "ZENDESK_AUTH_TOKEN": "abc",
    "SLACK_BOT_TOKEN": "xoxb-test",
    "SLACK_CHANNEL_ID": "C123456",
}

REPORT = {
    "total": 4,
    "solved": 2,
    "mismatch": 1,
    "error": 1,
    "mismatch_rows": [
        {
            "APPOINTMENT_ORDER_ID": "APT002",
            "TICKET_ID": "T002",
            "TOTAL_CHALLANS": 3,
            "CLOSED_CHALLANS": 2,
            "UPDATED_RESULT": "MISMATCH",
        }
    ],
}


def _fresh_slack():
    sys.modules.pop("config", None)
    sys.modules.pop("slack_client", None)
    import slack_client
    return slack_client


@patch.dict(os.environ, ENV)
def test_build_message_contains_all_counts():
    sc = _fresh_slack()
    msg = sc._build_message(REPORT)
    assert "4" in msg
    assert "2" in msg
    assert "1" in msg
    assert "Challan Ticket Closure Report" in msg


@patch.dict(os.environ, ENV)
def test_build_message_contains_mismatch_row_detail():
    sc = _fresh_slack()
    msg = sc._build_message(REPORT)
    assert "APT002" in msg
    assert "T002" in msg


@patch.dict(os.environ, ENV)
def test_post_report_calls_chat_post_message(tmp_path):
    sc = _fresh_slack()

    excel_file = tmp_path / "test.xlsx"
    excel_file.write_bytes(b"fake excel bytes")

    ok_response = MagicMock()
    ok_response.json.return_value = {"ok": True}
    ok_response.status_code = 200

    upload_url_response = MagicMock()
    upload_url_response.json.return_value = {
        "ok": True,
        "upload_url": "https://files.slack.com/upload/v1/abc",
        "file_id": "F123",
    }

    complete_response = MagicMock()
    complete_response.json.return_value = {"ok": True}

    put_response = MagicMock()
    put_response.status_code = 200

    with patch("slack_client.requests.post") as mock_post, \
         patch("slack_client.requests.put", return_value=put_response):

        mock_post.side_effect = [ok_response, upload_url_response, complete_response]
        sc.post_report(REPORT, str(excel_file))

    assert mock_post.call_count == 3
    first_call_url = mock_post.call_args_list[0].args[0]
    assert "chat.postMessage" in first_call_url


@patch.dict(os.environ, ENV)
def test_post_report_completes_upload_to_correct_channel(tmp_path):
    sc = _fresh_slack()

    excel_file = tmp_path / "test.xlsx"
    excel_file.write_bytes(b"fake excel bytes")

    ok_response = MagicMock()
    ok_response.json.return_value = {"ok": True}

    upload_url_response = MagicMock()
    upload_url_response.json.return_value = {
        "ok": True,
        "upload_url": "https://files.slack.com/upload/v1/abc",
        "file_id": "F999",
    }

    complete_response = MagicMock()
    complete_response.json.return_value = {"ok": True}

    put_response = MagicMock()
    put_response.status_code = 200

    with patch("slack_client.requests.post") as mock_post, \
         patch("slack_client.requests.put", return_value=put_response):

        mock_post.side_effect = [ok_response, upload_url_response, complete_response]
        sc.post_report(REPORT, str(excel_file))

    complete_call = mock_post.call_args_list[2]
    complete_payload = complete_call.kwargs["json"]
    assert complete_payload["files"][0]["id"] == "F999"
    assert complete_payload["channel_id"] == "C123456"
