# jarvis_calendar.py
# Google Calendar integration for Jarvis — read and write.
# All time boundaries use local timezone (tzlocal) — no UTC drift on date queries.
#
# Dependencies: pip3.11 install google-auth-oauthlib google-auth-httplib2 google-api-python-client tzlocal

import os
import re
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

try:
    from tzlocal import get_localzone
    _LOCAL_TZ      = get_localzone()
    _LOCAL_TZ_NAME = str(_LOCAL_TZ)
except ImportError:
    import zoneinfo
    _LOCAL_TZ      = zoneinfo.ZoneInfo("America/Detroit")
    _LOCAL_TZ_NAME = "America/Detroit"

SCOPES           = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
]
JARVIS_DIR       = Path(__file__).parent
CREDENTIALS_FILE = JARVIS_DIR / "google_credentials.json"
TOKEN_FILE       = JARVIS_DIR / "google_token.json"
MAX_RESULTS      = 10


# ── Auth ───────────────────────────────────────────────────────────────────────

def _get_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"google_credentials.json not found at {CREDENTIALS_FILE}."
                )
            flow  = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


# ── Local time helpers ─────────────────────────────────────────────────────────

def _local_now() -> datetime:
    return datetime.now(_LOCAL_TZ)

def _local_today_start() -> datetime:
    n = _local_now()
    return n.replace(hour=0, minute=0, second=0, microsecond=0)

def _local_today_end() -> datetime:
    n = _local_now()
    return n.replace(hour=23, minute=59, second=59, microsecond=0)

def _local_day_start(target: date) -> datetime:
    return datetime(target.year, target.month, target.day, 0, 0, 0, tzinfo=_LOCAL_TZ)

def _local_day_end(target: date) -> datetime:
    return datetime(target.year, target.month, target.day, 23, 59, 59, tzinfo=_LOCAL_TZ)


# ── Time Parser ────────────────────────────────────────────────────────────────

def _parse_time(target_date: date, time_str: str) -> datetime | None:
    s = time_str.strip().upper().replace(".", "").replace(" ", "")
    s = re.sub(r"(\d)(AM|PM)$", r"\1 \2", s)
    formats = ["%I:%M %p", "%I %p", "%H:%M", "%H"]
    for fmt in formats:
        try:
            t  = datetime.strptime(s, fmt)
            return datetime(
                target_date.year, target_date.month, target_date.day,
                t.hour, t.minute, tzinfo=_LOCAL_TZ
            )
        except ValueError:
            continue
    return None


# ── Event formatter ────────────────────────────────────────────────────────────

def _format_event(event: dict) -> str:
    title    = event.get("summary", "Untitled event")
    start    = event.get("start", {})
    location = event.get("location", "")
    if "dateTime" in start:
        dt       = datetime.fromisoformat(start["dateTime"]).astimezone(_LOCAL_TZ)
        time_str = dt.strftime("%-I:%M %p")
        day_str  = dt.strftime("%A")
        if location:
            return f"{title} on {day_str} at {time_str} at {location}"
        return f"{title} on {day_str} at {time_str}"
    elif "date" in start:
        d       = datetime.strptime(start["date"], "%Y-%m-%d")
        day_str = d.strftime("%A %B %-d")
        return f"{title} — all day on {day_str}"
    return title


# ── Core fetch ─────────────────────────────────────────────────────────────────

def _fetch(time_min: datetime, time_max: datetime) -> list[dict]:
    try:
        service = _get_service()
        result  = service.events().list(
            calendarId  = "primary",
            timeMin     = time_min.isoformat(),
            timeMax     = time_max.isoformat(),
            maxResults  = MAX_RESULTS,
            singleEvents= True,
            orderBy     = "startTime",
        ).execute()
        return result.get("items", [])
    except Exception as e:
        print(f"[calendar] Error: {e}")
        return []


# ── Read ───────────────────────────────────────────────────────────────────────

def get_today_events() -> str:
    """Return today's remaining events (skips past ones)."""
    now    = _local_now()
    events = _fetch(_local_today_start(), _local_today_end())

    # Filter to only upcoming events today
    upcoming = []
    for e in events:
        start = e.get("start", {})
        if "dateTime" in start:
            dt = datetime.fromisoformat(start["dateTime"]).astimezone(_LOCAL_TZ)
            if dt >= now:
                upcoming.append(e)
        else:
            upcoming.append(e)  # all-day always included

    if not upcoming:
        return "Nothing left on the calendar today."

    count     = len(upcoming)
    formatted = [_format_event(e) for e in upcoming]
    return f"Today you have {count} event{'s' if count > 1 else ''}: " + ", ".join(formatted) + "."


def get_next_event() -> str:
    """Return the next upcoming event from now."""
    now    = _local_now()
    end    = now + timedelta(days=30)
    events = _fetch(now, end)
    if not events:
        return "Nothing scheduled coming up."
    return f"Next up: {_format_event(events[0])}."


def get_upcoming_events(days: int = 7) -> str:
    """Return upcoming events in the next N days from now."""
    now    = _local_now()
    end    = now + timedelta(days=days)
    events = _fetch(now, end)
    if not events:
        return f"Nothing coming up in the next {days} days."
    return "Coming up: " + ", ".join(_format_event(e) for e in events) + "."


def get_events_on_date(date_str: str) -> str:
    """Return all events on a specific date."""
    now = _local_now()
    if date_str.lower() == "today":
        target = now.date()
    elif date_str.lower() == "tomorrow":
        target = (now + timedelta(days=1)).date()
    else:
        try:
            target = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return "Couldn't parse that date. Try 'today', 'tomorrow', or YYYY-MM-DD."

    events = _fetch(_local_day_start(target), _local_day_end(target))
    if not events:
        return f"Nothing on the calendar for {date_str}."
    return f"On {date_str}: " + ", ".join(_format_event(e) for e in events) + "."


# ── Write ──────────────────────────────────────────────────────────────────────

def create_event(
    title: str,
    date_str: str,
    start_time: str | None = None,
    end_time: str | None   = None,
    duration_minutes: int  = 60,
    location: str          = "",
    description: str       = "",
) -> str:
    now = _local_now()

    if date_str.lower() == "today":
        target = now.date()
    elif date_str.lower() == "tomorrow":
        target = (now + timedelta(days=1)).date()
    else:
        try:
            target = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return f"Couldn't parse date '{date_str}'."

    event_body: dict = {"summary": title}
    if location:
        event_body["location"] = location
    if description:
        event_body["description"] = description

    if start_time:
        start_dt = _parse_time(target, start_time)
        if start_dt is None:
            return f"Couldn't parse start time '{start_time}'. Try '7pm' or '14:00'."
        end_dt = _parse_time(target, end_time) if end_time else start_dt + timedelta(minutes=duration_minutes)
        if end_time and end_dt is None:
            return f"Couldn't parse end time '{end_time}'."
        event_body["start"] = {"dateTime": start_dt.isoformat(), "timeZone": _LOCAL_TZ_NAME}
        event_body["end"]   = {"dateTime": end_dt.isoformat(),   "timeZone": _LOCAL_TZ_NAME}
    else:
        event_body["start"] = {"date": target.strftime("%Y-%m-%d")}
        event_body["end"]   = {"date": target.strftime("%Y-%m-%d")}

    try:
        service = _get_service()
        created = service.events().insert(calendarId="primary", body=event_body).execute()
        day_str = target.strftime("%A %B %-d")
        if start_time:
            start_local = datetime.fromisoformat(created["start"]["dateTime"]).astimezone(_LOCAL_TZ)
            return f"Done. {title} added for {day_str} at {start_local.strftime('%-I:%M %p')}."
        return f"Done. {title} added as an all-day event on {day_str}."
    except HttpError as e:
        return f"Calendar API error: {e}"
    except Exception as e:
        return f"Couldn't create event: {e}"


# ── Diagnostic ─────────────────────────────────────────────────────────────────

def check_calendar_access() -> str:
    try:
        _get_service()
        return f"Google Calendar access confirmed. Timezone: {_LOCAL_TZ_NAME}"
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"Calendar access failed: {e}"


if __name__ == "__main__":
    print(check_calendar_access())
    print(f"Local time: {_local_now().strftime('%A %B %-d, %I:%M %p')}")
    print(get_today_events())
    print(get_next_event())
    print(get_upcoming_events(7))
