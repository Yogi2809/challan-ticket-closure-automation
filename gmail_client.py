import email as email_lib
import imaplib
import logging
from datetime import date
from email import policy

import config

logger = logging.getLogger(__name__)


class EmailNotFoundError(Exception):
    pass


class AttachmentNotFoundError(Exception):
    pass


def fetch_csv_attachment(target_date: date) -> bytes:
    subject = f"RAW - Challan OPS(VAS) closure_{target_date.strftime('%Y-%m-%d')}"
    logger.info("Searching Gmail for: %s", subject)

    with imaplib.IMAP4_SSL("imap.gmail.com", 993) as mail:
        mail.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        mail.select("INBOX")

        _, message_ids = mail.search(None, f'SUBJECT "{subject}"')
        ids = message_ids[0].split()

        if not ids:
            raise EmailNotFoundError(f"No email found with subject: {subject}")

        _, msg_data = mail.fetch(ids[-1], "(RFC822)")
        raw_email = msg_data[0][1]

    msg = email_lib.message_from_bytes(raw_email, policy=policy.default)

    for part in msg.walk():
        if part.get_content_disposition() == "attachment":
            filename = part.get_filename() or ""
            if filename.endswith(".csv"):
                logger.info("Found CSV attachment: %s", filename)
                return part.get_payload(decode=True)

    raise AttachmentNotFoundError(f"No CSV attachment in email with subject: {subject}")
