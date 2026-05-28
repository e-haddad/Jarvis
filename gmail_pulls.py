# gmail_pulls.py
# Periodic external pulls for Jarvis.
#
# Gmail scan:    searches for job-related emails → extracts company/role/status
#                → appends new entries to Career/Job Applications.md
# Calendar scan: pulls next 7 days of events → writes ## Week Ahead section
#                in Life/Weekly Review.md
#
# Both run on startup and every SCAN_INTERVAL_HOURS hours via background thread.
# Uses the same OAuth token as jarvis_calendar.py (calendar + gmail.readonly scopes).

import os
import re
import base64
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import anthropic

VAULT_ROOT         = Path.home() / "Desktop" / "OBS" / "Edward"
JOB_APPS_NOTE      = VAULT_ROOT / "Career" / "Job Applications.md"
WEEKLY_REVIEW_NOTE = VAULT_ROOT / "Life" / "Weekly Review.md"
SEEN_IDS_FILE      = Path(__file__).parent / ".gmail_seen_ids.txt"

SCAN_INTERVAL_HOURS = 3
GMAIL_LOOKBACK_DAYS = 7
CALENDAR_LOOKAHEAD_DAYS = 7

HAIKU = "claude-haiku-4-5-20251001"

_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ── Gmail auth (reuses jarvis_calendar token) ──────────────────────────────────

def _get_gmail_service():
    from jarvis_calendar import _get_service as _get_cal_service
    from googleapiclient.discovery import build
    # Reuse the same credentials object that calendar uses
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from pathlib import Path as P

    SCOPES      = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/gmail.readonly",
    ]
    TOKEN_FILE  = Path(__file__).parent / "google_token.json"
    CREDS_FILE  = Path(__file__).parent / "google_credentials.json"

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow  = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# ── Seen IDs — avoid re-processing emails ─────────────────────────────────────

def _load_seen_ids() -> set:
    if not SEEN_IDS_FILE.exists():
        return set()
    return set(SEEN_IDS_FILE.read_text().splitlines())


def _save_seen_id(msg_id: str):
    with open(SEEN_IDS_FILE, "a") as f:
        f.write(msg_id + "\n")


# ── Email body extractor ───────────────────────────────────────────────────────

def _extract_body(payload: dict) -> str:
    """Recursively extract plain text body from Gmail message payload."""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    elif mime.startswith("multipart/"):
        for part in payload.get("parts", []):
            text = _extract_body(part)
            if text:
                return text
    return ""


# ── Haiku extraction ───────────────────────────────────────────────────────────

def _extract_job_info(subject: str, sender: str, body_snippet: str) -> dict | None:
    """
    Use Haiku to extract structured job info from an email.
    Returns dict with keys: company, role, status, notes
    Returns None if not actually a job-related email.
    """
    prompt = (
        f"Email subject: {subject}\n"
        f"From: {sender}\n"
        f"Body snippet: {body_snippet[:800]}\n\n"
        "Extract job application info. Respond with exactly these fields, one per line:\n"
        "COMPANY: <company name or UNKNOWN>\n"
        "ROLE: <job title or UNKNOWN>\n"
        "STATUS: <one of: applied / interview / offer / rejected / follow-up / recruiter / other>\n"
        "NOTES: <one sentence max — key detail worth remembering, or NONE>\n"
        "NOT_JOB: <YES if this is NOT actually a job email, NO if it is>\n"
        "Be conservative — only extract if this is clearly about a job application or recruitment."
    )
    try:
        resp = _client.messages.create(
            model=HAIKU,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        lines = {l.split(":", 1)[0].strip(): l.split(":", 1)[-1].strip()
                 for l in text.splitlines() if ":" in l}

        if lines.get("NOT_JOB", "NO").upper() == "YES":
            return None

        return {
            "company": lines.get("COMPANY", "Unknown"),
            "role":    lines.get("ROLE",    "Unknown"),
            "status":  lines.get("STATUS",  "other"),
            "notes":   lines.get("NOTES",   ""),
        }
    except Exception:
        return None


# ── Gmail scan ─────────────────────────────────────────────────────────────────

JOB_QUERY = (
    "subject:(application OR interview OR recruiter OR \"job offer\" OR "
    "\"your application\" OR \"position\" OR \"opportunity\" OR \"hiring\" OR "
    "\"we reviewed\" OR \"next steps\" OR \"moving forward\" OR \"unfortunately\")"
)

def scan_gmail_jobs() -> int:
    """
    Scan Gmail for job-related emails from the last GMAIL_LOOKBACK_DAYS days.
    Appends new structured entries to Job Applications.md.
    Returns count of new entries added.
    """
    try:
        service  = _get_gmail_service()
        seen_ids = _load_seen_ids()

        after_date = (datetime.now() - timedelta(days=GMAIL_LOOKBACK_DAYS)).strftime("%Y/%m/%d")
        query      = f"{JOB_QUERY} after:{after_date}"

        result   = service.users().messages().list(
            userId="me", q=query, maxResults=25
        ).execute()
        messages = result.get("messages", [])

        new_count = 0
        entries   = []

        for msg_ref in messages:
            msg_id = msg_ref["id"]
            if msg_id in seen_ids:
                continue

            msg = service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()

            headers = {h["name"]: h["value"]
                       for h in msg.get("payload", {}).get("headers", [])}
            subject = headers.get("Subject", "(no subject)")
            sender  = headers.get("From", "Unknown")
            date_hdr = headers.get("Date", "")
            body    = _extract_body(msg.get("payload", {}))

            info = _extract_job_info(subject, sender, body)
            if info is None:
                _save_seen_id(msg_id)
                continue

            # Parse date
            try:
                from email.utils import parsedate_to_datetime
                email_dt = parsedate_to_datetime(date_hdr)
                date_str = email_dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = datetime.now().strftime("%Y-%m-%d")

            entry = (
                f"| {date_str} | {info['company']} | {info['role']} | "
                f"{info['status'].capitalize()} | {info['notes'] if info['notes'] != 'NONE' else ''} |"
            )
            entries.append(entry)
            _save_seen_id(msg_id)
            new_count += 1

        if entries:
            _append_job_entries(entries)

        print(f"[Gmail] Scanned — {new_count} new job entries added.")
        return new_count

    except Exception as e:
        print(f"[Gmail] Scan failed: {e}")
        return 0


def _append_job_entries(entries: list[str]):
    """
    Append new job entries to Job Applications.md.
    Creates a table header if one doesn't exist yet.
    """
    JOB_APPS_NOTE.parent.mkdir(parents=True, exist_ok=True)

    content = JOB_APPS_NOTE.read_text(encoding="utf-8") if JOB_APPS_NOTE.exists() else ""

    table_header = (
        "\n\n## Auto-Captured Applications\n"
        "| Date | Company | Role | Status | Notes |\n"
        "|------|---------|------|--------|-------|\n"
    )

    if "## Auto-Captured Applications" not in content:
        content = content.rstrip("\n") + table_header
    else:
        # Ensure we're appending directly after existing rows — no blank line
        content = content.rstrip("\n") + "\n"

    content += "\n".join(entries) + "\n"
    JOB_APPS_NOTE.write_text(content, encoding="utf-8")


# ── Calendar weekly pull ───────────────────────────────────────────────────────

def scan_calendar_weekly() -> bool:
    """
    Pull next CALENDAR_LOOKAHEAD_DAYS days of events.
    Writes/overwrites ## Week Ahead section in Life/Weekly Review.md.
    Returns True on success.
    """
    try:
        from jarvis_calendar import _fetch, _format_event, _local_now
        from datetime import timedelta

        now    = _local_now()
        end    = now + timedelta(days=CALENDAR_LOOKAHEAD_DAYS)
        events = _fetch(now, end)

        # Group by date
        by_day: dict[str, list] = {}
        for e in events:
            start = e.get("start", {})
            if "dateTime" in start:
                dt      = datetime.fromisoformat(start["dateTime"])
                day_key = dt.strftime("%A %b %-d")
            elif "date" in start:
                dt      = datetime.strptime(start["date"], "%Y-%m-%d")
                day_key = dt.strftime("%A %b %-d")
            else:
                continue
            by_day.setdefault(day_key, []).append(_format_event(e))

        # Build section
        lines = [f"\n\n## Week Ahead — updated {now.strftime('%Y-%m-%d %H:%M')}\n"]
        if not by_day:
            lines.append("Nothing scheduled for the next 7 days.\n")
        else:
            for day, day_events in by_day.items():
                lines.append(f"\n### {day}")
                for ev in day_events:
                    lines.append(f"- {ev}")
        section = "\n".join(lines) + "\n"

        # Read existing note, replace or append Week Ahead section
        WEEKLY_REVIEW_NOTE.parent.mkdir(parents=True, exist_ok=True)
        content = WEEKLY_REVIEW_NOTE.read_text(encoding="utf-8") if WEEKLY_REVIEW_NOTE.exists() else "# Weekly Review\n"

        if "## Week Ahead" in content:
            # Replace everything from ## Week Ahead to next ## or end of file
            content = re.sub(
                r"\n\n## Week Ahead.*?(?=\n\n##|\Z)",
                section.rstrip("\n"),
                content,
                flags=re.DOTALL,
            )
        else:
            content = content.rstrip("\n") + section

        WEEKLY_REVIEW_NOTE.write_text(content, encoding="utf-8")
        print(f"[Calendar] Week Ahead updated — {sum(len(v) for v in by_day.values())} events.")
        return True

    except Exception as e:
        print(f"[Calendar] Weekly scan failed: {e}")
        return False


# ── Periodic runner ────────────────────────────────────────────────────────────

def _run_all_scans():
    """Run both scans. Called on startup and every SCAN_INTERVAL_HOURS hours."""
    print(f"[Pulls] Running scans at {datetime.now().strftime('%H:%M')}...")
    scan_gmail_jobs()
    scan_calendar_weekly()


def start_periodic_pulls():
    """
    Start background thread that runs scans on startup then every 3 hours.
    Call once from main.py after server starts.
    """
    def _loop():
        _run_all_scans()  # immediate scan on startup
        while True:
            time.sleep(SCAN_INTERVAL_HOURS * 3600)
            _run_all_scans()

    t = threading.Thread(target=_loop, daemon=True, name="jarvis-pulls")
    t.start()
    print(f"[Pulls] Periodic scans started — interval: {SCAN_INTERVAL_HOURS}h")


# ── Manual trigger ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running manual scan...")
    jobs = scan_gmail_jobs()
    cal  = scan_calendar_weekly()
    print(f"Done — {jobs} job entries, calendar {'updated' if cal else 'failed'}.")
