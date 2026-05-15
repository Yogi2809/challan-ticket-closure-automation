# Challan Ticket Closure Automation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python cron worker that runs daily at 10 AM IST on Railway, reads a challan CSV from Gmail, validates and closes Zendesk tickets, then posts a summary report with an Excel attachment to Slack.

**Architecture:** A single-process Python script (`main.py`) orchestrates five focused modules — Gmail IMAP fetch, CSV filtering, Zendesk API calls, Excel export, and Slack reporting. Railway runs it on a daily cron schedule via `railway.toml`. All credentials are injected as environment variables.

**Tech Stack:** Python 3.11, pandas 2.2, openpyxl 3.1, requests 2.31, slack-sdk 3.27, imaplib (stdlib), pytest, unittest.mock

---

## File Map

| File | Responsibility |
|---|---|
| `config.py` | Read + validate all env vars at import time; fail fast if any missing |
| `gmail_client.py` | IMAP login, subject search, CSV attachment extraction |
| `processor.py` | DataFrame filtering, TOTAL vs CLOSED validation, UPDATED_RESULT, report dict |
| `zendesk_client.py` | PUT ticket API call, return True/False |
| `slack_client.py` | Build message text, post via chat.postMessage, 3-step Excel upload |
| `main.py` | Orchestrator — calls all modules in sequence |
| `requirements.txt` | Pinned dependencies |
| `railway.toml` | Cron schedule + build config |
| `tests/test_config.py` | Env var validation tests |
| `tests/test_processor.py` | Filtering and result logic tests |
| `tests/test_zendesk_client.py` | Mocked HTTP tests |
| `tests/test_slack_client.py` | Mocked Slack API tests |
| `tests/test_gmail_client.py` | Mocked IMAP tests |
| `tests/test_main.py` | Full orchestration test with all externals mocked |

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `railway.toml`
- Create: `tests/__init__.py`
- Create: `pytest.ini`

- [ ] **Step 1: Create `requirements.txt`**

```
pandas==2.2.2
openpyxl==3.1.2
requests==2.31.0
slack-sdk==3.27.1
pytest==8.2.0
```

- [ ] **Step 2: Create `railway.toml`**

```toml
[build]
builder = "nixpacks"

[[services]]
name = "challan-cron"

[services.deploy]
startCommand = "python main.py"
cronSchedule = "30 4 * * *"
```

- [ ] **Step 3: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
```

- [ ] **Step 4: Create `tests/__init__.py`**

Empty file — just needs to exist so pytest finds the tests directory.

```
(empty)
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 6: Verify pytest runs**

```bash
pytest
```

Expected output: `no tests ran` (zero tests yet, no errors).

- [ ] **Step 7: Commit**

```bash
git init
git add requirements.txt railway.toml pytest.ini tests/__init__.py
git commit -m "chore: project scaffold with dependencies and Railway config"
```

---

## Task 2: `config.py` — Environment Variable Validation

**Files:**
- Create: `config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_config.py`:

```python
import os
import pytest


def test_missing_gmail_address_raises(monkeypatch):
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "testpass")
    monkeypatch.setenv("ZENDESK_BASE_URL", "https://example.zendesk.com")
    monkeypatch.setenv("ZENDESK_AUTH_TOKEN", "abc123")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123456")

    import importlib
    import config as cfg
    importlib.reload(cfg)  # force re-read after monkeypatch

    # config module-level code runs on import; we check via direct call
    with pytest.raises(EnvironmentError, match="GMAIL_ADDRESS"):
        cfg._require("GMAIL_ADDRESS")


def test_all_vars_present_returns_values(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "test@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "apppass")
    monkeypatch.setenv("ZENDESK_BASE_URL", "https://example.zendesk.com")
    monkeypatch.setenv("ZENDESK_AUTH_TOKEN", "abc123")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123456")

    import config as cfg
    assert cfg._require("GMAIL_ADDRESS") == "test@example.com"
    assert cfg._require("SLACK_CHANNEL_ID") == "C123456"


def test_empty_string_treated_as_missing(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "")

    import config as cfg
    with pytest.raises(EnvironmentError, match="GMAIL_ADDRESS"):
        cfg._require("GMAIL_ADDRESS")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Create `config.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected:
```
tests/test_config.py::test_missing_gmail_address_raises PASSED
tests/test_config.py::test_all_vars_present_returns_values PASSED
tests/test_config.py::test_empty_string_treated_as_missing PASSED
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: config module with env var validation"
```

---

## Task 3: `processor.py` — Filtering, Validation, Results

**Files:**
- Create: `processor.py`
- Create: `tests/test_processor.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_processor.py`:

```python
import pandas as pd
import pytest
from io import BytesIO


CSV_CONTENT = b"""APPOINTMENT_ORDER_ID,TICKET_ID,TOTAL_CHALLANS,CLOSED_CHALLANS,UTF_CHALLANS,OPEN_CHALLANS
APT001,T001,3,3,,,
APT002,T002,3,2,,,
APT003,T003,2,2,1,,
APT004,T004,2,2,,1,
APT005,T005,,,,,
APT006,T006,4,4,,,
"""


def test_load_and_filter_keeps_valid_rows():
    from processor import load_and_filter
    df = load_and_filter(CSV_CONTENT)
    # APT003 has UTF_CHALLANS=1 → excluded
    # APT004 has OPEN_CHALLANS=1 → excluded
    # APT005 has blank CLOSED_CHALLANS → excluded
    assert list(df["APPOINTMENT_ORDER_ID"]) == ["APT001", "APT002", "APT006"]


def test_load_and_filter_normalises_column_names():
    from processor import load_and_filter
    csv = b"  appointment_order_id ,ticket_id,total_challans,closed_challans,utf_challans,open_challans\nAPT001,T001,3,3,,,\n"
    df = load_and_filter(csv)
    assert "APPOINTMENT_ORDER_ID" in df.columns
    assert "TICKET_ID" in df.columns


def test_load_and_filter_returns_empty_if_all_excluded():
    from processor import load_and_filter
    csv = b"APPOINTMENT_ORDER_ID,TICKET_ID,TOTAL_CHALLANS,CLOSED_CHALLANS,UTF_CHALLANS,OPEN_CHALLANS\nAPT001,T001,2,2,1,,\n"
    df = load_and_filter(csv)
    assert df.empty


def test_apply_results_adds_column():
    from processor import apply_results
    df = pd.DataFrame({"APPOINTMENT_ORDER_ID": ["APT001", "APT002"], "TICKET_ID": ["T001", "T002"]})
    results = {"APT001": "SOLVED", "APT002": "MISMATCH"}
    out = apply_results(df, results)
    assert list(out["UPDATED_RESULT"]) == ["SOLVED", "MISMATCH"]


def test_apply_results_does_not_mutate_input():
    from processor import apply_results
    df = pd.DataFrame({"APPOINTMENT_ORDER_ID": ["APT001"], "TICKET_ID": ["T001"]})
    apply_results(df, {"APT001": "SOLVED"})
    assert "UPDATED_RESULT" not in df.columns


def test_build_report_counts_correctly():
    from processor import build_report
    df = pd.DataFrame({
        "APPOINTMENT_ORDER_ID": ["APT001", "APT002", "APT003", "APT004"],
        "TICKET_ID": ["T001", "T002", "T003", "T004"],
        "TOTAL_CHALLANS": [3, 3, 2, 4],
        "CLOSED_CHALLANS": [3, 2, 2, 4],
        "UPDATED_RESULT": ["SOLVED", "MISMATCH", "ERROR", "SOLVED"],
    })
    report = build_report(df)
    assert report["total"] == 4
    assert report["solved"] == 2
    assert report["mismatch"] == 1
    assert report["error"] == 1
    assert len(report["mismatch_rows"]) == 2


def test_build_report_mismatch_rows_contain_required_fields():
    from processor import build_report
    df = pd.DataFrame({
        "APPOINTMENT_ORDER_ID": ["APT002"],
        "TICKET_ID": ["T002"],
        "TOTAL_CHALLANS": [3],
        "CLOSED_CHALLANS": [2],
        "UPDATED_RESULT": ["MISMATCH"],
    })
    report = build_report(df)
    row = report["mismatch_rows"][0]
    assert "APPOINTMENT_ORDER_ID" in row
    assert "TICKET_ID" in row
    assert "TOTAL_CHALLANS" in row
    assert "CLOSED_CHALLANS" in row
    assert "UPDATED_RESULT" in row
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_processor.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'processor'`

- [ ] **Step 3: Create `processor.py`**

```python
import pandas as pd
from io import BytesIO


def load_and_filter(csv_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(BytesIO(csv_bytes))
    df.columns = [col.strip().upper() for col in df.columns]

    def is_blank(series: pd.Series) -> pd.Series:
        return series.isna() | (series.astype(str).str.strip() == "") | (series.astype(str).str.strip() == "nan")

    def is_filled(series: pd.Series) -> pd.Series:
        return ~is_blank(series)

    mask = (
        is_blank(df["UTF_CHALLANS"])
        & is_blank(df["OPEN_CHALLANS"])
        & is_filled(df["APPOINTMENT_ORDER_ID"])
        & is_filled(df["CLOSED_CHALLANS"])
    )

    return df[mask].reset_index(drop=True)


def apply_results(df: pd.DataFrame, results: dict) -> pd.DataFrame:
    df = df.copy()
    df["UPDATED_RESULT"] = df["APPOINTMENT_ORDER_ID"].astype(str).map(results)
    return df


def build_report(df: pd.DataFrame) -> dict:
    total = len(df)
    solved = int((df["UPDATED_RESULT"] == "SOLVED").sum())
    mismatch = int((df["UPDATED_RESULT"] == "MISMATCH").sum())
    error = int((df["UPDATED_RESULT"] == "ERROR").sum())

    mismatch_rows = df[df["UPDATED_RESULT"].isin(["MISMATCH", "ERROR"])][
        ["APPOINTMENT_ORDER_ID", "TICKET_ID", "TOTAL_CHALLANS", "CLOSED_CHALLANS", "UPDATED_RESULT"]
    ].to_dict("records")

    return {
        "total": total,
        "solved": solved,
        "mismatch": mismatch,
        "error": error,
        "mismatch_rows": mismatch_rows,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_processor.py -v
```

Expected:
```
tests/test_processor.py::test_load_and_filter_keeps_valid_rows PASSED
tests/test_processor.py::test_load_and_filter_normalises_column_names PASSED
tests/test_processor.py::test_load_and_filter_returns_empty_if_all_excluded PASSED
tests/test_processor.py::test_apply_results_adds_column PASSED
tests/test_processor.py::test_apply_results_does_not_mutate_input PASSED
tests/test_processor.py::test_build_report_counts_correctly PASSED
tests/test_processor.py::test_build_report_mismatch_rows_contain_required_fields PASSED
7 passed
```

- [ ] **Step 5: Commit**

```bash
git add processor.py tests/test_processor.py
git commit -m "feat: processor module with filtering and result logic"
```

---

## Task 4: `zendesk_client.py` — Ticket Close API

**Files:**
- Create: `zendesk_client.py`
- Create: `tests/test_zendesk_client.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_zendesk_client.py`:

```python
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
    from zendesk_client import close_ticket
    mock_response = MagicMock()
    mock_response.status_code = 422
    mock_response.text = "Unprocessable Entity"

    with patch("zendesk_client.requests.put", return_value=mock_response):
        result = close_ticket("99999")

    assert result is False


@patch.dict(os.environ, ENV)
def test_close_ticket_sends_correct_payload():
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_zendesk_client.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'zendesk_client'`

- [ ] **Step 3: Create `zendesk_client.py`**

```python
import logging

import requests

import config

logger = logging.getLogger(__name__)

_TICKET_PAYLOAD = {
    "ticket": {
        "status": "solved",
        "comment": {
            "body": (
                "Dear Channel Partner,\n\n"
                "All pre-delivery challan has been cleared against this vehicle, "
                "same will be reflected on site within 24 hours.\n\n"
                "Thanks & Regards\nCars24"
            ),
            "public": True,
        },
        "custom_fields": [
            {"id": 9759821503503, "value": "sent_for_clearance"},
            {"id": 11876293100303, "value": "query_"},
        ],
    }
}


def close_ticket(ticket_id: str) -> bool:
    url = f"{config.ZENDESK_BASE_URL}/api/v2/tickets/{ticket_id}.json"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {config.ZENDESK_AUTH_TOKEN}",
    }

    response = requests.put(url, json=_TICKET_PAYLOAD, headers=headers)
    logger.info("Zendesk ticket %s → HTTP %s", ticket_id, response.status_code)

    if response.status_code != 200:
        logger.error("Zendesk error for ticket %s: %s", ticket_id, response.text)
        return False

    return True
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_zendesk_client.py -v
```

Expected:
```
tests/test_zendesk_client.py::test_close_ticket_returns_true_on_200 PASSED
tests/test_zendesk_client.py::test_close_ticket_returns_false_on_non_200 PASSED
tests/test_zendesk_client.py::test_close_ticket_sends_correct_payload PASSED
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add zendesk_client.py tests/test_zendesk_client.py
git commit -m "feat: zendesk client with ticket close API"
```

---

## Task 5: `slack_client.py` — Report Message + Excel Upload

**Files:**
- Create: `slack_client.py`
- Create: `tests/test_slack_client.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_slack_client.py`:

```python
import os
import pytest
from unittest.mock import patch, MagicMock, call


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


@patch.dict(os.environ, ENV)
def test_build_message_contains_all_counts():
    from slack_client import _build_message
    msg = _build_message(REPORT)
    assert "4" in msg   # total
    assert "2" in msg   # solved
    assert "1" in msg   # mismatch
    assert "Challan Ticket Closure Report" in msg


@patch.dict(os.environ, ENV)
def test_build_message_contains_mismatch_row_detail():
    from slack_client import _build_message
    msg = _build_message(REPORT)
    assert "APT002" in msg
    assert "T002" in msg


@patch.dict(os.environ, ENV)
def test_post_report_calls_chat_post_message(tmp_path):
    from slack_client import post_report

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
        post_report(REPORT, str(excel_file))

    assert mock_post.call_count == 3
    first_call_url = mock_post.call_args_list[0].args[0]
    assert "chat.postMessage" in first_call_url


@patch.dict(os.environ, ENV)
def test_post_report_completes_upload_to_correct_channel(tmp_path):
    from slack_client import post_report

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
        post_report(REPORT, str(excel_file))

    complete_call = mock_post.call_args_list[2]
    complete_payload = complete_call.kwargs["json"]
    assert complete_payload["files"][0]["id"] == "F999"
    assert complete_payload["channel_id"] == "C123456"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_slack_client.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'slack_client'`

- [ ] **Step 3: Create `slack_client.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_slack_client.py -v
```

Expected:
```
tests/test_slack_client.py::test_build_message_contains_all_counts PASSED
tests/test_slack_client.py::test_build_message_contains_mismatch_row_detail PASSED
tests/test_slack_client.py::test_post_report_calls_chat_post_message PASSED
tests/test_slack_client.py::test_post_report_completes_upload_to_correct_channel PASSED
4 passed
```

- [ ] **Step 5: Commit**

```bash
git add slack_client.py tests/test_slack_client.py
git commit -m "feat: slack client with message posting and 3-step Excel upload"
```

---

## Task 6: `gmail_client.py` — IMAP Email Fetch

**Files:**
- Create: `gmail_client.py`
- Create: `tests/test_gmail_client.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_gmail_client.py`:

```python
import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import date
import email as email_lib
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
    from gmail_client import fetch_csv_attachment
    csv_content = b"APPOINTMENT_ORDER_ID,TICKET_ID\nAPT001,T001"
    target_date = date(2026, 5, 15)
    email_bytes = _make_email_with_csv(csv_content, f"RAW - Challan OPS(VAS) closure_2026-05-15")
    mock_imap = _make_imap_mock(email_bytes)

    with patch("gmail_client.imaplib.IMAP4_SSL", return_value=mock_imap):
        result = fetch_csv_attachment(target_date)

    assert result == csv_content


@patch.dict(os.environ, ENV)
def test_fetch_csv_attachment_raises_when_no_email():
    from gmail_client import fetch_csv_attachment, EmailNotFoundError
    mock_imap = MagicMock()
    mock_imap.__enter__ = MagicMock(return_value=mock_imap)
    mock_imap.__exit__ = MagicMock(return_value=False)
    mock_imap.login.return_value = ("OK", [])
    mock_imap.select.return_value = ("OK", [b"0"])
    mock_imap.search.return_value = ("OK", [b""])  # no results

    with patch("gmail_client.imaplib.IMAP4_SSL", return_value=mock_imap):
        with pytest.raises(EmailNotFoundError):
            fetch_csv_attachment(date(2026, 5, 15))


@patch.dict(os.environ, ENV)
def test_fetch_csv_attachment_raises_when_no_csv_attachment():
    from gmail_client import fetch_csv_attachment, AttachmentNotFoundError
    msg = MIMEMultipart()
    msg["Subject"] = "RAW - Challan OPS(VAS) closure_2026-05-15"
    msg.attach(MIMEText("just text, no csv", "plain"))
    email_bytes = msg.as_bytes()
    mock_imap = _make_imap_mock(email_bytes)

    with patch("gmail_client.imaplib.IMAP4_SSL", return_value=mock_imap):
        with pytest.raises(AttachmentNotFoundError):
            fetch_csv_attachment(date(2026, 5, 15))


@patch.dict(os.environ, ENV)
def test_fetch_csv_searches_correct_subject():
    from gmail_client import fetch_csv_attachment
    csv_content = b"APPOINTMENT_ORDER_ID,TICKET_ID\nAPT001,T001"
    email_bytes = _make_email_with_csv(csv_content, "RAW - Challan OPS(VAS) closure_2026-05-15")
    mock_imap = _make_imap_mock(email_bytes)

    with patch("gmail_client.imaplib.IMAP4_SSL", return_value=mock_imap):
        fetch_csv_attachment(date(2026, 5, 15))

    search_call = mock_imap.search.call_args
    assert "closure_2026-05-15" in str(search_call)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_gmail_client.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'gmail_client'`

- [ ] **Step 3: Create `gmail_client.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_gmail_client.py -v
```

Expected:
```
tests/test_gmail_client.py::test_fetch_csv_attachment_returns_bytes PASSED
tests/test_gmail_client.py::test_fetch_csv_attachment_raises_when_no_email PASSED
tests/test_gmail_client.py::test_fetch_csv_attachment_raises_when_no_csv_attachment PASSED
tests/test_gmail_client.py::test_fetch_csv_searches_correct_subject PASSED
4 passed
```

- [ ] **Step 5: Commit**

```bash
git add gmail_client.py tests/test_gmail_client.py
git commit -m "feat: gmail IMAP client with CSV attachment extraction"
```

---

## Task 7: `main.py` — Orchestrator

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_main.py`:

```python
import os
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


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


@patch.dict(os.environ, ENV)
def test_run_closes_matching_tickets(tmp_path):
    from main import run

    with patch("main.fetch_csv_attachment", return_value=CSV_BYTES), \
         patch("main.close_ticket", return_value=True) as mock_close, \
         patch("main.post_report") as mock_slack, \
         patch("main.date") as mock_date:

        mock_date.today.return_value.__str__ = lambda s: "2026-05-15"
        mock_date.today.return_value.strftime = lambda f: "2026-05-15"

        run()

    # APT001: TOTAL==CLOSED → should call close_ticket
    # APT002: TOTAL!=CLOSED → should NOT call close_ticket
    mock_close.assert_called_once_with("T001")


@patch.dict(os.environ, ENV)
def test_run_marks_mismatch_when_totals_differ(tmp_path):
    from main import run

    with patch("main.fetch_csv_attachment", return_value=CSV_BYTES), \
         patch("main.close_ticket", return_value=True), \
         patch("main.post_report") as mock_slack, \
         patch("main.date"):

        run()

    report = mock_slack.call_args.args[0]
    assert report["mismatch"] == 1
    assert report["solved"] == 1


@patch.dict(os.environ, ENV)
def test_run_marks_error_when_zendesk_fails():
    from main import run

    with patch("main.fetch_csv_attachment", return_value=CSV_BYTES), \
         patch("main.close_ticket", return_value=False), \
         patch("main.post_report") as mock_slack, \
         patch("main.date"):

        run()

    report = mock_slack.call_args.args[0]
    assert report["error"] == 1


@patch.dict(os.environ, ENV)
def test_run_sends_slack_alert_when_email_not_found():
    from main import run
    from gmail_client import EmailNotFoundError

    with patch("main.fetch_csv_attachment", side_effect=EmailNotFoundError("not found")), \
         patch("main.post_report") as mock_slack:

        run()

    report = mock_slack.call_args.args[0]
    assert "alert" in report
    assert report["total"] == 0


@patch.dict(os.environ, ENV)
def test_run_sends_slack_alert_when_df_empty():
    from main import run

    empty_csv = b"APPOINTMENT_ORDER_ID,TICKET_ID,TOTAL_CHALLANS,CLOSED_CHALLANS,UTF_CHALLANS,OPEN_CHALLANS\nAPT001,T001,3,3,1,,\n"

    with patch("main.fetch_csv_attachment", return_value=empty_csv), \
         patch("main.post_report") as mock_slack, \
         patch("main.date"):

        run()

    report = mock_slack.call_args.args[0]
    assert report["total"] == 0
    assert "alert" in report
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_main.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'main'`

- [ ] **Step 3: Create `main.py`**

```python
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
        ticket_id = str(row["TICKET_ID"])

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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_main.py -v
```

Expected:
```
tests/test_main.py::test_run_closes_matching_tickets PASSED
tests/test_main.py::test_run_marks_mismatch_when_totals_differ PASSED
tests/test_main.py::test_run_marks_error_when_zendesk_fails PASSED
tests/test_main.py::test_run_sends_slack_alert_when_email_not_found PASSED
tests/test_main.py::test_run_sends_slack_alert_when_df_empty PASSED
5 passed
```

- [ ] **Step 5: Run the full test suite**

```bash
pytest -v
```

Expected: all tests pass (19 total across all modules).

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: main orchestrator with full end-to-end flow"
```

---

## Task 8: Railway Deploy + Env Var Setup

**Files:**
- No code changes — configuration only

- [ ] **Step 1: Create a Railway account and new project**

1. Go to [railway.app](https://railway.app) → sign up / log in
2. Click **New Project** → **Deploy from GitHub repo** (push your code to GitHub first) OR **Empty project**
3. Name it: `challan-ticket-closure`

- [ ] **Step 2: Push code to GitHub**

```bash
git remote add origin https://github.com/<your-username>/challan-ticket-closure-automation.git
git push -u origin main
```

- [ ] **Step 3: Connect GitHub repo in Railway**

In Railway dashboard → **New Service** → **GitHub Repo** → select your repo.

- [ ] **Step 4: Set environment variables in Railway**

In Railway dashboard → your service → **Variables** tab → add each:

| Key | Value |
|---|---|
| `GMAIL_ADDRESS` | your work email (e.g. `yogesh.mishra@cars24.com`) |
| `GMAIL_APP_PASSWORD` | 16-char App Password, no spaces |
| `ZENDESK_BASE_URL` | `https://cars24help.zendesk.com` |
| `ZENDESK_AUTH_TOKEN` | `c2h1YmhhbS5zaW5naDJAY2FyczI0LmNvbS90b2tlbjpZalRVTk9FZ2dFcWdIb0s3UWZDd1d3YWowYmd1eGFOaHo4RnQ0SzZr` |
| `SLACK_BOT_TOKEN` | `xoxb-...` from Slack app |
| `SLACK_CHANNEL_ID` | e.g. `C08XXXXXXX` |

- [ ] **Step 5: Verify Railway picks up `railway.toml` cron schedule**

In Railway dashboard → your service → **Settings** → confirm **Cron Schedule** shows `30 4 * * *`.

- [ ] **Step 6: Trigger a manual run to test**

In Railway dashboard → your service → **Deployments** → click **Deploy** to run immediately (outside of cron).  
Check **Logs** tab — you should see:
```
INFO main Challan closure run started for 2026-05-15
INFO gmail_client Searching Gmail for: RAW - Challan OPS(VAS) closure_2026-05-15
```

If the email doesn't exist for today you'll see:
```
WARNING main No email found with subject: RAW - Challan OPS(VAS) closure_2026-05-15
```
Plus a Slack alert — which confirms Slack is wired up correctly.

- [ ] **Step 7: Final commit**

```bash
git add .
git commit -m "chore: ready for Railway deployment"
git push
```

---

## Self-Review Against Spec

| Spec Requirement | Covered In |
|---|---|
| Download CSV via Gmail IMAP | Task 6 (`gmail_client.py`) |
| Subject format `RAW - Challan OPS(VAS) closure_YYYY-MM-DD` | Task 6 test + impl |
| Filter: UTF_CHALLANS blank | Task 3 (`processor.py`) |
| Filter: OPEN_CHALLANS blank | Task 3 |
| Filter: APPOINTMENT_ORDER_ID filled | Task 3 |
| Filter: CLOSED_CHALLANS filled | Task 3 |
| Validate TOTAL_CHALLANS == CLOSED_CHALLANS | Task 7 (`main.py`) |
| Call Zendesk PUT API on match | Task 4 + Task 7 |
| UPDATED_RESULT = SOLVED on HTTP 200 | Task 7 |
| UPDATED_RESULT = MISMATCH on totals mismatch | Task 7 |
| UPDATED_RESULT = ERROR on non-200 | Task 7 |
| Save Excel with UPDATED_RESULT column | Task 7 |
| Slack: chat.postMessage with report | Task 5 (`slack_client.py`) |
| Slack: 3-step Excel file upload | Task 5 |
| Slack message template (Total/Solved/Mismatch/Error) | Task 5 |
| Mismatch detail rows in Slack message | Task 5 |
| Alert on email not found | Task 7 |
| Alert on empty DataFrame after filter | Task 7 |
| Railway cron at 4:30 UTC | Task 1 (`railway.toml`) |
| All secrets as env vars | Task 2 (`config.py`) + Task 8 |
