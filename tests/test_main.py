import os
import sys
import pytest
from unittest.mock import patch, MagicMock


ENV = {
    "GMAIL_ADDRESS": "test@example.com",
    "GMAIL_APP_PASSWORD": "apppass",
    "ZENDESK_BASE_URL": "https://example.zendesk.com",
    "ZENDESK_AUTH_TOKEN": "abc",
    "SLACK_BOT_TOKEN": "xoxb-test",
    "SLACK_CHANNEL_ID": "C123",
}

CSV_BYTES = (
    b"APPOINTMENT_ORDER_ID,TICKET_ID,TOTAL_CHALLANS,CLOSED_CHALLANS,UTF_CHALLANS,OPEN_CHALLANS\n"
    b"APT001,T001,3,3,,,\n"
    b"APT002,T002,3,2,,,\n"
)


def _fresh_main():
    for mod in ["config", "gmail_client", "processor", "zendesk_client", "slack_client", "main"]:
        sys.modules.pop(mod, None)
    import main
    return main


@patch.dict(os.environ, ENV)
def test_run_closes_matching_tickets():
    m = _fresh_main()
    with patch("main.fetch_csv_attachment", return_value=CSV_BYTES), \
         patch("main.close_ticket", return_value=True) as mock_close, \
         patch("main.post_report"), \
         patch("main.date") as mock_date:
        mock_date.today.return_value = MagicMock(__str__=lambda s: "2026-05-15")
        m.run()
    # APT001: TOTAL==CLOSED (3==3) → close_ticket called
    # APT002: TOTAL!=CLOSED (3!=2) → close_ticket NOT called
    mock_close.assert_called_once_with("T001")


@patch.dict(os.environ, ENV)
def test_run_marks_mismatch_when_totals_differ():
    m = _fresh_main()
    with patch("main.fetch_csv_attachment", return_value=CSV_BYTES), \
         patch("main.close_ticket", return_value=True), \
         patch("main.post_report") as mock_slack, \
         patch("main.date"):
        m.run()
    report = mock_slack.call_args.args[0]
    assert report["mismatch"] == 1
    assert report["solved"] == 1


@patch.dict(os.environ, ENV)
def test_run_marks_error_when_zendesk_fails():
    m = _fresh_main()
    with patch("main.fetch_csv_attachment", return_value=CSV_BYTES), \
         patch("main.close_ticket", return_value=False), \
         patch("main.post_report") as mock_slack, \
         patch("main.date"):
        m.run()
    report = mock_slack.call_args.args[0]
    assert report["error"] == 1


@patch.dict(os.environ, ENV)
def test_run_sends_slack_alert_when_email_not_found():
    m = _fresh_main()
    from gmail_client import EmailNotFoundError
    with patch("main.fetch_csv_attachment", side_effect=EmailNotFoundError("not found")), \
         patch("main.post_report") as mock_slack:
        m.run()
    report = mock_slack.call_args.args[0]
    assert "alert" in report
    assert report["total"] == 0


@patch.dict(os.environ, ENV)
def test_run_sends_slack_alert_when_df_empty():
    m = _fresh_main()
    empty_csv = (
        b"APPOINTMENT_ORDER_ID,TICKET_ID,TOTAL_CHALLANS,CLOSED_CHALLANS,UTF_CHALLANS,OPEN_CHALLANS\n"
        b"APT001,T001,3,3,1,,\n"  # UTF_CHALLANS=1 → excluded
    )
    with patch("main.fetch_csv_attachment", return_value=empty_csv), \
         patch("main.post_report") as mock_slack, \
         patch("main.date"):
        m.run()
    report = mock_slack.call_args.args[0]
    assert report["total"] == 0
    assert "alert" in report
