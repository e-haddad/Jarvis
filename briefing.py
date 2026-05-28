# briefing.py
# Startup anticipation for Jarvis.
# Runs once on activation — silently checks calendar, time, recent session, inbox.
# Also runs proactive second-brain checks: stale projects, weekly review,
# job application staleness, and no-events morning suggestion.
# Returns a short spoken brief if there's something worth surfacing.
# Returns empty string if nothing actionable — Jarvis stays silent.

from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from tzlocal import get_localzone
    _LOCAL_TZ = get_localzone()
except ImportError:
    _LOCAL_TZ = ZoneInfo("America/Detroit")

VAULT_ROOT    = Path.home() / "Desktop" / "OBS" / "Edward"
JARVIS_NOTE   = VAULT_ROOT / "Projects" / "Jarvis" / "Jarvis.md"
INBOX_DIR     = VAULT_ROOT / "Inbox"
PROJECTS_PATH = VAULT_ROOT / "Projects"
CAREER_PATH   = VAULT_ROOT / "Career" / "Job Applications"

MORNING   = range(5,  12)
AFTERNOON = range(12, 18)
EVENING   = range(18, 24)
NIGHT     = range(0,  5)

STALE_DAYS     = 14   # flag project note not modified in this many days
JOB_STALE_DAYS = 5    # flag if no new job app logged in this many days


# ── Helpers ────────────────────────────────────────────────────────────────────

def _time_of_day() -> str:
    hour = datetime.now(_LOCAL_TZ).hour
    if hour in MORNING:   return "morning"
    if hour in AFTERNOON: return "afternoon"
    if hour in EVENING:   return "evening"
    return "night"


def _trim_topic(text: str) -> str:
    """Trim to first clause — stop at em dash, comma if long, or 60 chars."""
    for sep in [" — ", " -- ", " – "]:
        if sep in text:
            text = text.split(sep)[0].strip()
            break
    if len(text) > 55 and "," in text:
        text = text.split(",")[0].strip()
    if len(text) > 60:
        text = text[:57] + "..."
    return text


def _inbox_count() -> int:
    try:
        return len(list(INBOX_DIR.glob("*.md")))
    except Exception:
        return 0


# ── Last session topic ─────────────────────────────────────────────────────────

def _last_session_topic() -> str:
    """
    Extract what was last worked on from Jarvis.md.
    Handles two formats:
      1. New format: ## Last Session Log section
      2. Legacy format: --- separators
    Returns a short spoken phrase, or empty string.
    """
    if not JARVIS_NOTE.exists():
        return ""
    try:
        content = JARVIS_NOTE.read_text(encoding="utf-8")
        lines   = content.split("\n")

        # ── New format: ## Last Session Log section ────────────────────────
        for i, line in enumerate(lines):
            if line.strip().startswith("## Last Session Log"):
                for j in range(i + 1, min(i + 30, len(lines))):
                    l = lines[j].strip()
                    if l.startswith("## "):
                        break
                    # "Current status:" is most concise
                    if l.lower().startswith("current status:"):
                        val = l.split(":", 1)[-1].strip().lstrip("-").strip()
                        if val:
                            return _trim_topic(val)
                    # First bullet under "Work completed:"
                    if l.lower().startswith("work completed:"):
                        for k in range(j + 1, min(j + 10, len(lines))):
                            item = lines[k].strip().lstrip("-").strip()
                            if item and not item.startswith("##"):
                                return _trim_topic(item)
                return ""

        # ── Legacy format: --- separators ─────────────────────────────────
        parts = content.rsplit("---", 1)
        if len(parts) < 2:
            return ""
        last_entry = parts[-1].strip()
        if not last_entry:
            return ""
        for line in last_entry.split("\n"):
            line = line.strip().lstrip("*").strip()
            if line and not line.startswith("*"):
                return _trim_topic(line.split(".")[0].strip())

        return ""
    except Exception:
        return ""


# ── Calendar check ─────────────────────────────────────────────────────────────

def _get_today_brief() -> str:
    """
    Get today's upcoming events using local timezone boundaries.
    Only surfaces events that haven't started yet.
    """
    try:
        from jarvis_calendar import _get_service, _format_event, MAX_RESULTS

        now_local   = datetime.now(_LOCAL_TZ)
        start_local = now_local.replace(hour=0,  minute=0,  second=0,  microsecond=0)
        end_local   = now_local.replace(hour=23, minute=59, second=59, microsecond=0)

        service = _get_service()
        result  = service.events().list(
            calendarId  = "primary",
            timeMin     = start_local.isoformat(),
            timeMax     = end_local.isoformat(),
            maxResults  = MAX_RESULTS,
            singleEvents= True,
            orderBy     = "startTime",
        ).execute()

        events = result.get("items", [])
        if not events:
            return ""

        upcoming = []
        for e in events:
            start = e.get("start", {})
            if "dateTime" in start:
                dt = datetime.fromisoformat(start["dateTime"]).astimezone(_LOCAL_TZ)
                if dt > now_local:
                    upcoming.append(e)
            else:
                upcoming.append(e)  # all-day always surface

        if not upcoming:
            return ""

        count     = len(upcoming)
        formatted = [_format_event(e) for e in upcoming]
        return f"Today you have {count} event{'s' if count > 1 else ''}: " + ", ".join(formatted) + "."

    except Exception:
        return ""


def _get_next_event_brief() -> str:
    """Get the next upcoming event if it's later today."""
    try:
        from jarvis_calendar import _get_service, _format_event

        now_local = datetime.now(_LOCAL_TZ)
        end_today = now_local.replace(hour=23, minute=59, second=59, microsecond=0)

        service = _get_service()
        result  = service.events().list(
            calendarId  = "primary",
            timeMin     = now_local.isoformat(),
            timeMax     = end_today.isoformat(),
            maxResults  = 1,
            singleEvents= True,
            orderBy     = "startTime",
        ).execute()

        events = result.get("items", [])
        if not events:
            return ""
        return f"Next up: {_format_event(events[0])}."
    except Exception:
        return ""


# ── Proactive second brain ─────────────────────────────────────────────────────

def stale_projects_check() -> str:
    """
    Walk Projects/, flag notes not modified in STALE_DAYS days.
    Skips Jarvis/ and Iris/ (infrastructure, not actionable projects).
    Returns a spoken sentence or ''.
    """
    if not PROJECTS_PATH.exists():
        return ""

    now    = datetime.now(tz=_LOCAL_TZ)
    cutoff = now - timedelta(days=STALE_DAYS)
    stale  = []
    SKIP   = {"Jarvis", "Iris"}

    for item in PROJECTS_PATH.iterdir():
        if item.is_file() and item.suffix == ".md":
            mtime = datetime.fromtimestamp(item.stat().st_mtime, tz=_LOCAL_TZ)
            if mtime < cutoff:
                stale.append((item.stem, (now - mtime).days))
        elif item.is_dir() and item.name not in SKIP:
            primary = item / f"{item.name}.md"
            if not primary.exists():
                mds = list(item.glob("*.md"))
                primary = max(mds, key=lambda p: p.stat().st_mtime) if mds else None
            if primary:
                mtime = datetime.fromtimestamp(primary.stat().st_mtime, tz=_LOCAL_TZ)
                if mtime < cutoff:
                    stale.append((item.name, (now - mtime).days))

    if not stale:
        return ""

    stale.sort(key=lambda x: x[1], reverse=True)
    if len(stale) == 1:
        name, days = stale[0]
        return f"{name} hasn't been touched in {days} days — worth a look today."
    names = ", ".join(n for n, _ in stale[:3])
    return f"{len(stale)} projects gone quiet — {names} haven't moved in over {stale[0][1]} days."


def weekly_review_prompt() -> str:
    """
    Returns a nudge on Sunday evenings at or after 17:00 local.
    Lockfile at ~/.jarvis_weekly_review_lock prevents repeat within the same day.
    """
    now = datetime.now(tz=_LOCAL_TZ)
    if not (now.weekday() == 6 and now.hour >= 17):
        return ""

    lock = Path.home() / ".jarvis_weekly_review_lock"
    if lock.exists():
        try:
            if date.fromisoformat(lock.read_text().strip()) == now.date():
                return ""
        except Exception:
            pass

    lock.write_text(now.date().isoformat())
    return "It's Sunday evening — good time for your weekly review. Want me to pull up the template?"


def job_application_staleness() -> str:
    """
    Scans Career/Job Applications/ — flags if no .md modified in JOB_STALE_DAYS days.
    Returns a spoken sentence or ''.
    """
    if not CAREER_PATH.exists():
        return ""

    now    = datetime.now(tz=_LOCAL_TZ)
    cutoff = now - timedelta(days=JOB_STALE_DAYS)
    recent = [
        p for p in CAREER_PATH.glob("*.md")
        if datetime.fromtimestamp(p.stat().st_mtime, tz=_LOCAL_TZ) > cutoff
    ]
    if recent:
        return ""

    all_apps = list(CAREER_PATH.glob("*.md"))
    if not all_apps:
        return "No job applications logged yet — worth starting the tracker."

    latest   = max(all_apps, key=lambda p: p.stat().st_mtime)
    days_ago = (now - datetime.fromtimestamp(latest.stat().st_mtime, tz=_LOCAL_TZ)).days
    return f"No new applications in {days_ago} days. Last one was {latest.stem}. Pipeline's going quiet."


def no_events_suggestion(has_calendar_events: bool) -> str:
    """
    If today's calendar is empty, surface the most recently touched project.
    Pass has_calendar_events=False when _get_today_brief() returns ''.
    """
    if has_calendar_events or not PROJECTS_PATH.exists():
        return ""

    SKIP       = {"Jarvis", "Iris"}
    candidates = []

    for item in PROJECTS_PATH.iterdir():
        if item.is_file() and item.suffix == ".md":
            candidates.append((item.stem, item.stat().st_mtime))
        elif item.is_dir() and item.name not in SKIP:
            primary = item / f"{item.name}.md"
            if primary.exists():
                candidates.append((item.name, primary.stat().st_mtime))

    if not candidates:
        return ""

    candidates.sort(key=lambda x: x[1], reverse=True)
    top_name, top_mtime = candidates[0]
    now      = datetime.now(tz=_LOCAL_TZ)
    days_ago = (now - datetime.fromtimestamp(top_mtime, tz=_LOCAL_TZ)).days

    if days_ago == 0:
        return f"Calendar's clear today. {top_name} was the last thing you were in — good day to push it forward."
    return f"Nothing on the calendar. {top_name} hasn't moved in {days_ago} days — might be worth picking back up."


# ── Brief composer ─────────────────────────────────────────────────────────────

def get_startup_brief() -> str:
    """
    Gather raw context, pass it to Claude, get back a natural spoken brief.
    Max 2 sentences. Returns '' if nothing actionable.
    """
    import os
    import anthropic

    tod        = _time_of_day()
    inbox      = _inbox_count()
    calendar   = _get_today_brief()
    next_event = _get_next_event_brief()
    last_topic = _last_session_topic()
    has_events = bool(calendar)

    proactive_items = [
        stale_projects_check(),
        weekly_review_prompt(),
        job_application_staleness(),
        no_events_suggestion(has_events),
    ]
    proactive = [p for p in proactive_items if p]

    # Build raw data block for Claude
    data_lines = [f"Time of day: {tod}"]
    if next_event:
        data_lines.append(f"Next calendar event: {next_event}")
    elif calendar:
        data_lines.append(f"Calendar: {calendar}")
    else:
        data_lines.append("Calendar: nothing today")
    if inbox > 0:
        data_lines.append(f"Inbox: {inbox} unread note{'s' if inbox > 1 else ''}")
    if proactive:
        data_lines.append(f"Proactive flags: {' | '.join(proactive)}")
    if last_topic and tod in ("evening", "night"):
        data_lines.append(f"Last session topic: {last_topic}")

    # Nothing worth surfacing — stay silent
    meaningful = any([next_event, calendar, inbox > 0, proactive,
                      (last_topic and tod in ("evening", "night"))])
    if not meaningful:
        return ""

    context = "\n".join(data_lines)

    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            system=(
                "You are Jarvis — a sharp, dry British AI assistant built by Edward Haddad. "
                "Edward is a recent ECE grad, job hunting for embedded roles in Michigan, "
                "working on Jarvis and other projects. "
                "You're given raw context data about his day. "
                "Write a spoken startup brief: 1-2 sentences max, natural and conversational. "
                "Prioritise time-sensitive info (calendar, next event) first. "
                "Surface one proactive flag if relevant — don't list everything. "
                "Sound like a colleague who actually knows him, not a notification. "
                "No bullet points, no markdown, no preamble. Plain spoken sentences only. "
                "If the only thing worth saying is trivial, return exactly: SILENT"
            ),
            messages=[{"role": "user", "content": context}],
        )
        result = resp.content[0].text.strip()
        if result == "SILENT" or not result:
            return ""
        return result
    except Exception:
        # Fallback to dumb assembly if Claude call fails
        parts = []
        if next_event:
            parts.append(next_event)
        elif calendar:
            parts.append(calendar.split(",")[0].rstrip(".") + ".")
        if inbox > 0:
            parts.append(f"{inbox} inbox {'note' if inbox == 1 else 'notes'} waiting.")
        if not parts and proactive:
            parts.append(proactive[0])
        return " ".join(parts[:2]).strip()


if __name__ == "__main__":
    now   = datetime.now(_LOCAL_TZ)
    tod   = _time_of_day()
    inbox = _inbox_count()
    topic = _last_session_topic()
    cal   = _get_today_brief()
    brief = get_startup_brief()

    print(f"Timezone:     {_LOCAL_TZ}")
    print(f"Local time:   {now.strftime('%I:%M %p')}")
    print(f"Time of day:  {tod}")
    print(f"Inbox count:  {inbox}")
    print(f"Last topic:   {topic}")
    print(f"Calendar:     {cal}")
    print(f"Brief output: '{brief}'")
