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

        # ON filter catches emails from any time today (9 AM, 9:30 AM, etc.)
        # regardless of what time the cron fires. IMAP date is DD-Mon-YYYY.
        imap_date = target_date.strftime("%d-%b-%Y")
        _, message_ids = mail.search(None, f'ON "{imap_date}" SUBJECT "{subject}"')
        ids = message_ids[0].split()

        # Fallback: timezone edge-case where IMAP date differs — retry subject-only.
        if not ids:
            _, message_ids = mail.search(None, f'SUBJECT "{subject}"')
            ids = message_ids[0].split()

        if not ids:
            raise EmailNotFoundError(f"No email found with subject: {subject}")

        _, msg_data = mail.fetch(ids[-1], "(RFC822)")
        raw_email = msg_data[0][1]

    msg = email_lib.message_from_bytes(raw_email, policy=policy.default)

    for part in msg.walk():
        filename = part.get_filename() or ""
        content_type = part.get_content_type()
        disposition = part.get_content_disposition() or ""

        is_csv_by_name = filename.lower().endswith(".csv")
        is_csv_by_type = content_type in ("text/csv", "application/csv", "application/octet-stream")
        is_attached = disposition in ("attachment", "inline") or filename != ""

        if is_attached and (is_csv_by_name or is_csv_by_type):
            logger.info("Found CSV attachment: %s (type=%s disposition=%s)", filename, content_type, disposition)
            return part.get_payload(decode=True)

    raise AttachmentNotFoundError(f"No CSV attachment in email with subject: {subject}")
