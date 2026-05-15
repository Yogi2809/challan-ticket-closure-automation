import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders


ENV = {
    "GMAIL_ADDRESS": "test@example.com",
    "GMAIL_APP_PASSWORD": "apppass",
    "ZENDESK_BASE_URL": "https://example.zendesk.com",
    "ZENDESK_AUTH_TOKEN": "abc",
    "SLACK_BOT_TOKEN": "xoxb-test",
    "SLACK_CHANNEL_ID": "C123",
}


def _fresh():
    sys.modules.pop("config", None)
    sys.modules.pop("gmail_client", None)
    import gmail_client
    return gmail_client


def _make_email_with_csv(csv_content: bytes, subject: str) -> bytes:
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = "sender@example.com"
    msg["To"] = "test@example.com"
    msg.attach(MIMEText("body", "plain"))

    part = MIMEBase("application", "octet-stream")
    part.set_payload(csv_content)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", 'attachment; filename="data.csv"')
    msg.attach(part)

    return msg.as_bytes()


def _make_imap_mock(email_bytes: bytes):
    mock_imap = MagicMock()
    mock_imap.__enter__ = MagicMock(return_value=mock_imap)
    mock_imap.__exit__ = MagicMock(return_value=False)
    mock_imap.login.return_value = ("OK", [b"Logged in"])
    mock_imap.select.return_value = ("OK", [b"1"])
    mock_imap.search.return_value = ("OK", [b"1"])
    mock_imap.fetch.return_value = ("OK", [(b"1 (RFC822 {100})", email_bytes)])
    return mock_imap


@patch.dict(os.environ, ENV)
def test_fetch_csv_attachment_returns_bytes():
    gc = _fresh()
    csv_content = b"APPOINTMENT_ORDER_ID,TICKET_ID\nAPT001,T001"
    email_bytes = _make_email_with_csv(csv_content, "RAW - Challan OPS(VAS) closure_2026-05-15")
    mock_imap = _make_imap_mock(email_bytes)

    with patch("gmail_client.imaplib.IMAP4_SSL", return_value=mock_imap):
        result = gc.fetch_csv_attachment(date(2026, 5, 15))

    assert result == csv_content


@patch.dict(os.environ, ENV)
def test_fetch_csv_attachment_raises_when_no_email():
    gc = _fresh()
    mock_imap = MagicMock()
    mock_imap.__enter__ = MagicMock(return_value=mock_imap)
    mock_imap.__exit__ = MagicMock(return_value=False)
    mock_imap.login.return_value = ("OK", [])
    mock_imap.select.return_value = ("OK", [b"0"])
    mock_imap.search.return_value = ("OK", [b""])

    with patch("gmail_client.imaplib.IMAP4_SSL", return_value=mock_imap):
        with pytest.raises(gc.EmailNotFoundError):
            gc.fetch_csv_attachment(date(2026, 5, 15))


@patch.dict(os.environ, ENV)
def test_fetch_csv_attachment_raises_when_no_csv_attachment():
    gc = _fresh()
    msg = MIMEMultipart()
    msg["Subject"] = "RAW - Challan OPS(VAS) closure_2026-05-15"
    msg.attach(MIMEText("just text, no csv", "plain"))
    email_bytes = msg.as_bytes()
    mock_imap = _make_imap_mock(email_bytes)

    with patch("gmail_client.imaplib.IMAP4_SSL", return_value=mock_imap):
        with pytest.raises(gc.AttachmentNotFoundError):
            gc.fetch_csv_attachment(date(2026, 5, 15))


@patch.dict(os.environ, ENV)
def test_fetch_csv_searches_correct_subject():
    gc = _fresh()
    csv_content = b"APPOINTMENT_ORDER_ID,TICKET_ID\nAPT001,T001"
    email_bytes = _make_email_with_csv(csv_content, "RAW - Challan OPS(VAS) closure_2026-05-15")
    mock_imap = _make_imap_mock(email_bytes)

    with patch("gmail_client.imaplib.IMAP4_SSL", return_value=mock_imap):
        gc.fetch_csv_attachment(date(2026, 5, 15))

    search_call = mock_imap.search.call_args
    assert "closure_2026-05-15" in str(search_call)
