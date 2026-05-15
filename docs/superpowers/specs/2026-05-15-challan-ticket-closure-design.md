# Challan Ticket Closure Automation — Design Spec

**Date:** 2026-05-15  
**Author:** Yogesh Mishra  
**Status:** Approved for implementation

---

## 1. Overview

A Python automation that runs daily at 10:00 AM IST on Railway. It reads a CSV file from Gmail, validates challan data, closes matching Zendesk tickets, and posts a closure report (with an Excel attachment) to Slack.

---

## 2. Trigger & Schedule

- **Platform:** Railway (cron worker — no web server needed)
- **Schedule:** Daily at `4:30 AM UTC` (= 10:00 AM IST)
- **Railway config:** Set as a cron job in `railway.toml` with `schedule = "30 4 * * *"`

---

## 3. System Architecture

```
Railway Cron (daily @ 4:30 UTC / 10:00 AM IST)
        │
        ▼
   main.py runs
        │
   ┌────┴────────────────────────────────────────────┐
   │ Step 1: Gmail IMAP                              │
   │  - Connect via IMAP (imap.gmail.com:993)        │
   │  - Auth: work Gmail + App Password              │
   │  - Search INBOX for today's subject:            │
   │    "RAW - Challan OPS(VAS) closure_YYYY-MM-DD"  │
   │  - Download CSV attachment                      │
   └────┬────────────────────────────────────────────┘
        │
   ┌────┴────────────────────────────────────────────┐
   │ Step 2: Load & Filter                           │
   │  - Load CSV into pandas DataFrame               │
   │  - Keep rows where:                             │
   │      UTF_CHALLANS        == blank/NaN           │
   │      OPEN_CHALLANS       == blank/NaN           │
   │      APPOINTMENT_ORDER_ID != blank              │
   │      CLOSED_CHALLANS     != blank               │
   └────┬────────────────────────────────────────────┘
        │
   ┌────┴────────────────────────────────────────────┐
   │ Step 3: Validate & Call Zendesk (per row)       │
   │                                                 │
   │  TOTAL_CHALLANS == CLOSED_CHALLANS?             │
   │    YES → PUT /api/v2/tickets/{TICKET_ID}.json   │
   │           → HTTP 200  → UPDATED_RESULT = SOLVED │
   │           → non-200   → UPDATED_RESULT = ERROR  │
   │    NO  → skip API     → UPDATED_RESULT = MISMATCH│
   └────┬────────────────────────────────────────────┘
        │
   ┌────┴────────────────────────────────────────────┐
   │ Step 4: Save Excel                              │
   │  - Add UPDATED_RESULT column to DataFrame       │
   │  - Save as: Challan_Closure_YYYY-MM-DD.xlsx     │
   └────┬────────────────────────────────────────────┘
        │
   ┌────┴────────────────────────────────────────────┐
   │ Step 5: Slack Report                            │
   │  - chat.postMessage         → summary report    │
   │  - getUploadURLExternal     → get upload URL    │
   │  - PUT file to upload URL   → send bytes        │
   │  - completeUploadExternal   → attach to channel │
   └─────────────────────────────────────────────────┘
```

---

## 4. Project File Structure

```
challan-ticket-closure-automation/
├── main.py               # Orchestrator — runs all steps in order
├── gmail_client.py       # IMAP connection, email search, CSV download
├── processor.py          # DataFrame filtering, validation, UPDATED_RESULT logic
├── zendesk_client.py     # Zendesk PUT ticket API wrapper
├── slack_client.py       # Slack message post + Excel file upload
├── config.py             # Reads all env vars, fails fast if any are missing
├── requirements.txt      # Python dependencies
├── railway.toml          # Railway cron schedule config
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-05-15-challan-ticket-closure-design.md
```

---

## 5. Module Specifications

### 5.1 `config.py`
Reads environment variables at import time. Raises `EnvironmentError` immediately if any required variable is missing so Railway logs show the problem on startup.

Required variables:
- `GMAIL_ADDRESS` — work Gmail address (e.g., `yogesh.mishra@cars24.com`)
- `GMAIL_APP_PASSWORD` — 16-character App Password (spaces removed)
- `ZENDESK_BASE_URL` — `https://cars24help.zendesk.com`
- `ZENDESK_AUTH_TOKEN` — Base64 auth string (from the curl command header)
- `SLACK_BOT_TOKEN` — Slack bot OAuth token (starts with `xoxb-`)
- `SLACK_CHANNEL_ID` — Slack channel ID (e.g., `C0XXXXXXX`)

---

### 5.2 `gmail_client.py`

**`fetch_csv_attachment(target_date: date) -> bytes`**

1. Connect to `imap.gmail.com:993` over SSL using `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD`
2. Select INBOX
3. Search for emails with subject: `RAW - Challan OPS(VAS) closure_<target_date as YYYY-MM-DD>`
4. If no email found → raise `EmailNotFoundError` (caught by `main.py`, sends Slack alert)
5. Take the most recent matching email
6. Find the first `.csv` attachment and return its raw bytes
7. If no CSV attachment → raise `AttachmentNotFoundError`

---

### 5.3 `processor.py`

**`load_and_filter(csv_bytes: bytes) -> DataFrame`**

1. Read CSV bytes into a pandas DataFrame
2. Normalise column names: strip whitespace, uppercase
3. Apply filters — keep only rows where ALL of:
   - `UTF_CHALLANS` is `NaN` or empty string
   - `OPEN_CHALLANS` is `NaN` or empty string
   - `APPOINTMENT_ORDER_ID` is not `NaN` and not empty
   - `CLOSED_CHALLANS` is not `NaN` and not empty
4. Return the filtered DataFrame

**`apply_results(df: DataFrame, results: dict[str, str]) -> DataFrame`**

Adds `UPDATED_RESULT` column from the `results` dict keyed by `APPOINTMENT_ORDER_ID`. Returns updated DataFrame.

---

### 5.4 `zendesk_client.py`

**`close_ticket(ticket_id: str) -> bool`**

Sends PUT request to:
```
PUT https://cars24help.zendesk.com/api/v2/tickets/{ticket_id}.json
```

Request body (exact payload from spec):
```json
{
  "ticket": {
    "status": "solved",
    "comment": {
      "body": "Dear Channel Partner,\n\nAll pre-delivery challan has been cleared against this vehicle, same will be reflected on site within 24 hours.\n\nThanks & Regards\nCars24",
      "public": true
    },
    "custom_fields": [
      {"id": 9759821503503, "value": "sent_for_clearance"},
      {"id": 11876293100303, "value": "query_"}
    ]
  }
}
```

Headers:
- `Content-Type: application/json`
- `Authorization: Basic <ZENDESK_AUTH_TOKEN>`

Returns `True` if HTTP status == 200, `False` otherwise.  
Logs the status code and response body on every call (for Railway log visibility).

**Note on auth token:** The `Authorization` header value from the curl command is:
```
Basic c2h1YmhhbS5zaW5naDJAY2FyczI0LmNvbS90b2tlbjpZalRVTk9FZ2dFcWdIb0s3UWZDd1d3YWowYmd1eGFOaHo4RnQ0SzZr
```
Store only the base64 part (`c2h1...`) as `ZENDESK_AUTH_TOKEN`. The code prepends `Basic `.

---

### 5.5 `slack_client.py`

**`post_report(report: dict, excel_path: str)`**

Step 1 — Post text message via `chat.postMessage`:
```
*Challan Ticket Closure Report*

*Total Tickets:*   {total}
*Solved Tickets:*  {solved}
*Mismatch Tickets:* {mismatch}
*Error Tickets:*   {error}

*Mismatch / Error Details:*
{table of APPOINTMENT_ORDER_ID | TICKET_ID | TOTAL_CHALLANS | CLOSED_CHALLANS | UPDATED_RESULT}
```

Step 2 — Upload Excel file using Slack's current upload API (3-step process):
1. `files.getUploadURLExternal` — get a pre-signed upload URL
2. HTTP PUT to the pre-signed URL with file bytes
3. `files.completeUploadExternal` — finalize and share to `SLACK_CHANNEL_ID`

Uses `SLACK_BOT_TOKEN` for all Slack calls.

**Required Slack bot scopes:** `chat:write`, `files:write`

> Note: The older `files.upload` API is deprecated by Slack as of 2025. The 3-step method above is the current supported approach.

---

### 5.6 `main.py`

Orchestrator — calls each module in sequence:

```python
def run():
    today = date.today()
    
    # Step 1: Gmail
    csv_bytes = fetch_csv_attachment(today)   # raises on failure → Slack alert
    
    # Step 2: Filter
    df = load_and_filter(csv_bytes)
    
    # Step 3: Zendesk calls
    results = {}
    for _, row in df.iterrows():
        appt_id = row["APPOINTMENT_ORDER_ID"]
        ticket_id = str(row["TICKET_ID"])
        if row["TOTAL_CHALLANS"] == row["CLOSED_CHALLANS"]:
            success = close_ticket(ticket_id)
            results[appt_id] = "SOLVED" if success else "ERROR"
        else:
            results[appt_id] = "MISMATCH"
    
    # Step 4: Save Excel
    df = apply_results(df, results)
    excel_path = f"Challan_Closure_{today}.xlsx"
    df.to_excel(excel_path, index=False)
    
    # Step 5: Slack report
    post_report(build_report(df, results), excel_path)
```

---

## 6. UPDATED_RESULT Values

| Value | When set |
|---|---|
| `SOLVED` | Zendesk API returned HTTP 200 |
| `MISMATCH` | `TOTAL_CHALLANS != CLOSED_CHALLANS` — Zendesk not called |
| `ERROR` | Zendesk API returned non-200 response |

---

## 7. Slack Message Template

```
*Challan Ticket Closure Report*

*Total Tickets:*    <count of eligible rows after filtering>
*Solved Tickets:*   <count where UPDATED_RESULT = SOLVED>
*Mismatch Tickets:* <count where UPDATED_RESULT = MISMATCH>
*Error Tickets:*    <count where UPDATED_RESULT = ERROR>

*Mismatch / Error Details:*
APPOINTMENT_ORDER_ID | TICKET_ID | TOTAL_CHALLANS | CLOSED_CHALLANS | RESULT
------------------------------------------------------------------
<row 1>
<row 2>
...

📎 Excel sheet attached.
```

---

## 8. Error Handling

| Scenario | Behavior |
|---|---|
| Email not found for today | Log warning + post Slack alert: "No challan email found for {date}" |
| No CSV attachment in email | Log warning + post Slack alert: "Email found but no CSV attachment" |
| Zendesk returns non-200 | Log status code + body, mark row as `ERROR`, continue processing remaining rows |
| Slack API fails | Log error to Railway logs — do not crash (report is already processed) |
| Missing env variable | Raise `EnvironmentError` at startup — Railway logs show missing var name |
| Filtered DataFrame is empty | Post Slack alert: "No eligible rows after filtering" |

---

## 9. Dependencies (`requirements.txt`)

```
pandas==2.2.2
openpyxl==3.1.2
requests==2.31.0
slack-sdk==3.27.1
```

Standard library only for IMAP: `imaplib`, `email` (no extra packages needed).

---

## 10. Railway Setup

**`railway.toml`:**
```toml
[build]
builder = "nixpacks"

[[services]]
name = "challan-cron"

[services.deploy]
startCommand = "python main.py"
cronSchedule = "30 4 * * *"
```

**Environment variables to set in Railway dashboard:**
- `GMAIL_ADDRESS`
- `GMAIL_APP_PASSWORD`
- `ZENDESK_BASE_URL`
- `ZENDESK_AUTH_TOKEN`
- `SLACK_BOT_TOKEN`
- `SLACK_CHANNEL_ID`

---

## 11. Slack App Setup (Step-by-Step)

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Name it: `Challan Closure Bot` → select your workspace → Create
3. In left sidebar: **OAuth & Permissions**
4. Under **Scopes → Bot Token Scopes**, add:
   - `chat:write`
   - `files:write`
5. Click **Install to Workspace** → Allow
6. Copy the **Bot User OAuth Token** (starts with `xoxb-`) → this is `SLACK_BOT_TOKEN`
7. Invite the bot to your target Slack channel: `/invite @Challan Closure Bot`
8. Get the channel ID: right-click channel name → **View channel details** → copy ID at the bottom (starts with `C`)

---

## 12. What I Need From You (Checklist)

Before implementation starts, gather these values to set as Railway env vars:

- [ ] `GMAIL_ADDRESS` — your work email address
- [ ] `GMAIL_APP_PASSWORD` — the 16-char App Password you generated (remove spaces)
- [ ] `SLACK_BOT_TOKEN` — from Slack app setup (Step 11 above)
- [ ] `SLACK_CHANNEL_ID` — the channel where reports should be posted
- [ ] Confirm `ZENDESK_AUTH_TOKEN` = `c2h1YmhhbS5zaW5naDJAY2FyczI0LmNvbS90b2tlbjpZalRVTk9FZ2dFcWdIb0s3UWZDd1d3YWowYmd1eGFOaHo4RnQ0SzZr` (taken from your curl command — confirm this is correct and current)

---

## 13. Out of Scope

- Retry logic on Zendesk API failures (mark as ERROR and move on)
- Historical reprocessing of past dates
- Multiple CSV attachments in a single email (first `.csv` found is used)
- Authentication token refresh for Zendesk (token is long-lived Basic auth)
