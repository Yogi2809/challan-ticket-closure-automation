import logging

import requests

import config

logger = logging.getLogger(__name__)


def _build_message(report: dict) -> str:
    lines = [
        "*Challan Ticket Closure Report*",
        "",
        f"*Total Tickets:*    {report['total']}",
        f"*Solved Tickets:*   {report['solved']}",
        f"*Mismatch Tickets:* {report['mismatch']}",
        f"*Error Tickets:*    {report['error']}",
    ]

    if report.get("alert"):
        lines += ["", f":warning: *Alert:* {report['alert']}"]

    if report.get("mismatch_rows"):
        lines += [
            "",
            "*Mismatch / Error Details:*",
            "`APPOINTMENT_ORDER_ID | TICKET_ID | TOTAL_CHALLANS | CLOSED_CHALLANS | RESULT`",
        ]
        for row in report["mismatch_rows"]:
            lines.append(
                f"`{row['APPOINTMENT_ORDER_ID']} | {row['TICKET_ID']} | "
                f"{row['TOTAL_CHALLANS']} | {row['CLOSED_CHALLANS']} | {row['UPDATED_RESULT']}`"
            )

    lines += ["", ":paperclip: Excel sheet attached."]
    return "\n".join(lines)


def post_report(report: dict, excel_path: str | None) -> None:
    headers = {"Authorization": f"Bearer {config.SLACK_BOT_TOKEN}"}

    msg_resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers=headers,
        json={"channel": config.SLACK_CHANNEL_ID, "text": _build_message(report)},
    )
    if not msg_resp.json().get("ok"):
        logger.error("Slack chat.postMessage failed: %s", msg_resp.json())

    if not excel_path:
        return

    with open(excel_path, "rb") as f:
        file_bytes = f.read()

    filename = excel_path.split("/")[-1]

    url_resp = requests.post(
        "https://slack.com/api/files.getUploadURLExternal",
        headers=headers,
        json={"filename": filename, "length": len(file_bytes)},
    )
    url_data = url_resp.json()
    if not url_data.get("ok"):
        logger.error("Slack getUploadURLExternal failed: %s", url_data)
        return

    put_resp = requests.put(url_data["upload_url"], data=file_bytes)
    if put_resp.status_code not in (200, 201):
        logger.error("Slack file PUT failed with status %s", put_resp.status_code)
        return

    complete_resp = requests.post(
        "https://slack.com/api/files.completeUploadExternal",
        headers=headers,
        json={
            "files": [{"id": url_data["file_id"]}],
            "channel_id": config.SLACK_CHANNEL_ID,
        },
    )
    if not complete_resp.json().get("ok"):
        logger.error("Slack completeUploadExternal failed: %s", complete_resp.json())
