import logging
from datetime import date

import config  # noqa: F401 — validates env vars at startup
from gmail_client import AttachmentNotFoundError, EmailNotFoundError, fetch_csv_attachment
from processor import apply_results, build_report, load_and_filter
from slack_client import post_report
from zendesk_client import close_ticket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def run() -> None:
    today = date.today()
    logger.info("Challan closure run started for %s", today)

    try:
        csv_bytes = fetch_csv_attachment(today)
    except (EmailNotFoundError, AttachmentNotFoundError) as exc:
        logger.warning(str(exc))
        post_report({"total": 0, "solved": 0, "mismatch": 0, "error": 0, "mismatch_rows": [], "alert": str(exc)}, None)
        return

    df = load_and_filter(csv_bytes)
    if df.empty:
        msg = "No eligible rows after filtering"
        logger.warning(msg)
        post_report({"total": 0, "solved": 0, "mismatch": 0, "error": 0, "mismatch_rows": [], "alert": msg}, None)
        return

    results: dict[str, str] = {}
    for _, row in df.iterrows():
        appt_id = str(row["APPOINTMENT_ORDER_ID"])
        ticket_id = str(row["ID"])

        try:
            total = float(row["TOTAL_CHALLANS"])
            closed = float(row["CLOSED_CHALLANS"])
            is_match = total == closed
        except (ValueError, TypeError):
            is_match = False

        if is_match:
            success = close_ticket(ticket_id)
            results[appt_id] = "SOLVED" if success else "ERROR"
        else:
            results[appt_id] = "MISMATCH"

        logger.info("Ticket %s (%s): %s", ticket_id, appt_id, results[appt_id])

    df = apply_results(df, results)
    excel_path = f"Challan_Closure_{today}.xlsx"
    df.to_excel(excel_path, index=False)
    logger.info("Saved Excel: %s", excel_path)

    report = build_report(df)
    post_report(report, excel_path)
    logger.info("Run complete. Solved=%s Mismatch=%s Error=%s", report["solved"], report["mismatch"], report["error"])


if __name__ == "__main__":
    run()
