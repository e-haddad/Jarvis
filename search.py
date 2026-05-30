# search.py
# Web search for Jarvis using the Brave Search API.
# Returns clean, LLM-ready summaries — not raw JSON dumps.
# Jarvis decides when to search; results are fed back into Claude for a spoken response.

import os
import urllib.request
import urllib.parse
import json

BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY")
SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

# Max results to pull per query — 5 is enough for a voice response
MAX_RESULTS = 5


def web_search(query: str) -> str:
    """
    Search the web using Brave Search API.
    Returns a plain-text summary of the top results for Claude to reason over.
    """
    if not BRAVE_API_KEY:
        return "Search unavailable — BRAVE_API_KEY not set."

    params = urllib.parse.urlencode({
        "q":     query,
        "count": MAX_RESULTS,
        "text_decorations": False,
        "search_lang": "en",
        "country": "US",
    })

    url = f"{SEARCH_ENDPOINT}?{params}"
    req = urllib.request.Request(url, headers={
        "Accept":               "application/json",
        "Accept-Encoding":      "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
    })

    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            # Handle gzip encoding
            import io
            raw = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        return f"Search failed: HTTP {e.code} — {e.reason}"
    except urllib.error.URLError as e:
        return f"Search failed: {e.reason}"
    except Exception as e:
        return f"Search failed: {e}"

    # Extract web results
    results = data.get("web", {}).get("results", [])
    if not results:
        return "No results found."

    # Format as clean context for Claude
    lines = []
    for r in results:
        title       = r.get("title", "").strip()
        description = r.get("description", "").strip()
        url_str     = r.get("url", "").strip()
        if title and description:
            lines.append(f"- {title}: {description} ({url_str})")

    if not lines:
        return "No usable results found."

    return "\n".join(lines)


def get_news(topic: str = "technology", count: int = 5) -> str:
    """
    Get recent news headlines on a topic using Brave Search.
    Returns a plain-text list of headlines + descriptions for Claude to summarize.
    """
    if not BRAVE_API_KEY:
        return "Search unavailable — BRAVE_API_KEY not set."

    query = f"{topic} news today"
    params = urllib.parse.urlencode({
        "q":              query,
        "count":          count,
        "text_decorations": False,
        "search_lang":    "en",
        "country":        "US",
        "freshness":      "pd",  # past day
    })

    url = f"{SEARCH_ENDPOINT}?{params}"
    req = urllib.request.Request(url, headers={
        "Accept":               "application/json",
        "Accept-Encoding":      "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
    })

    try:
        import gzip
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        return f"News search failed: {e}"

    results = data.get("web", {}).get("results", [])
    if not results:
        return f"No recent news found for '{topic}'."

    lines = []
    for r in results[:count]:
        title = r.get("title", "").strip()
        desc  = r.get("description", "").strip()
        if title:
            lines.append(f"- {title}: {desc}" if desc else f"- {title}")

    return f"Recent news on '{topic}':\n" + "\n".join(lines) if lines else f"No news found for '{topic}'."


def get_crypto_price(coin: str = "bitcoin") -> str:
    """
    Get current price of a cryptocurrency using CoinGecko free API (no key needed).
    Returns price in USD and 24h change.
    """
    coin_ids = {
        "bitcoin": "bitcoin", "btc": "bitcoin",
        "ethereum": "ethereum", "eth": "ethereum",
        "solana": "solana", "sol": "solana",
        "cardano": "cardano", "ada": "cardano",
        "dogecoin": "dogecoin", "doge": "dogecoin",
        "xrp": "ripple", "ripple": "ripple",
        "bnb": "binancecoin", "binance": "binancecoin",
        "usdc": "usd-coin", "usdt": "tether",
    }
    coin_id = coin_ids.get(coin.lower(), coin.lower())

    try:
        params = urllib.parse.urlencode({
            "ids":           coin_id,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
        })
        url = f"https://api.coingecko.com/api/v3/simple/price?{params}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))

        if coin_id not in data:
            return f"Couldn't find price for '{coin}'. Try using the full name e.g. 'bitcoin'."

        price  = data[coin_id]["usd"]
        change = data[coin_id].get("usd_24h_change", None)

        result = f"{coin.capitalize()}: ${price:,.2f} USD"
        if change is not None:
            direction = "↑" if change >= 0 else "↓"
            result += f" ({direction}{abs(change):.2f}% in 24h)"
        return result

    except Exception as e:
        return f"Crypto price fetch failed: {e}"


def set_reminder(message: str, minutes: int) -> str:
    """
    Set a spoken reminder after N minutes using a background thread.
    Emits a timer panel event to the HUD immediately.
    Jarvis will speak the reminder when the timer fires.
    """
    import threading
    import time

    total_seconds = minutes * 60

    def _fire():
        time.sleep(total_seconds)
        try:
            from speak import speak
            speak(f"Reminder: {message}")
        except Exception as e:
            print(f"[Reminder] speak failed: {e}")
        try:
            import sys
            if "server" in sys.modules:
                from server import emit_jarvis_msg
                emit_jarvis_msg(f"Reminder: {message}")
        except Exception as e:
            print(f"[Reminder] emit failed: {e}")

    t = threading.Thread(target=_fire, daemon=True)
    t.start()

    if minutes == 1:
        return f"Reminder set — I'll remind you about '{message}' in 1 minute."
    return f"Reminder set — I'll remind you about '{message}' in {minutes} minutes."


def open_app(app_name: str) -> str:
    """
    Open a macOS application or file by name using the 'open' command.
    Works for apps (Xcode, Obsidian, Safari) and common shortcuts.
    """
    import subprocess

    APP_MAP = {
        "obsidian":     "Obsidian",
        "xcode":        "Xcode",
        "safari":       "Safari",
        "chrome":       "Google Chrome",
        "terminal":     "Terminal",
        "finder":       "Finder",
        "vscode":       "Visual Studio Code",
        "vs code":      "Visual Studio Code",
        "spotify":      "Spotify",
        "slack":        "Slack",
        "notion":       "Notion",
        "discord":      "Discord",
        "mail":         "Mail",
        "calendar":     "Calendar",
        "notes":        "Notes",
        "messages":     "Messages",
        "facetime":     "FaceTime",
        "photos":       "Photos",
        "music":        "Music",
        "github desktop": "GitHub Desktop",
    }

    resolved = APP_MAP.get(app_name.lower(), app_name)

    try:
        result = subprocess.run(
            ["open", "-a", resolved],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return f"Opened {resolved}."
        else:
            return f"Couldn't open '{resolved}': {result.stderr.strip()}"
    except Exception as e:
        return f"Open failed: {e}"


def draft_email(to: str, subject: str, body: str) -> str:
    """
    Create a draft email in Gmail using OAuth credentials.
    Uses the same google_token.json / google_credentials.json as the calendar integration.
    Requires gmail.compose scope — opens a browser re-auth flow if not present.
    """
    import base64
    import json as _json
    from email.mime.text import MIMEText
    from pathlib import Path

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
    except ImportError:
        return (
            "Gmail draft failed: google-auth packages not installed. "
            "Run: pip3.11 install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        )

    GMAIL_SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
    ]

    JARVIS_DIR       = Path(__file__).parent
    TOKEN_FILE       = JARVIS_DIR / "google_token.json"
    CREDENTIALS_FILE = JARVIS_DIR / "google_credentials.json"

    def _token_has_compose() -> bool:
        """Read the actual scopes granted in the saved token JSON."""
        if not TOKEN_FILE.exists():
            return False
        try:
            with open(TOKEN_FILE) as _f:
                data = _json.load(_f)
            scopes = data.get("scopes", [])
            return any(
                "gmail.compose" in s or "gmail.modify" in s or "mail.google.com" in s
                for s in scopes
            )
        except Exception:
            return False

    def _do_reauth() -> Credentials:
        """Run OAuth flow to get new credentials with gmail.compose scope."""
        if not CREDENTIALS_FILE.exists():
            raise FileNotFoundError(
                "google_credentials.json not found — can't authenticate."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), GMAIL_SCOPES)
        try:
            creds = flow.run_local_server(port=0, open_browser=True)
        except Exception as _e:
            raise RuntimeError(
                f"Re-auth needed for gmail.compose scope but browser flow failed: {_e}. "
                "Run: python3.11 reauth_gmail.py in the Jarvis folder to authenticate interactively."
            ) from _e
        with open(TOKEN_FILE, "w") as _f:
            _f.write(creds.to_json())
        return creds

    try:
        # 1. Check if token exists and has the right scope; re-auth if not
        if not _token_has_compose():
            creds = _do_reauth()
        else:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), GMAIL_SCOPES)
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open(TOKEN_FILE, "w") as _f:
                        _f.write(creds.to_json())
                else:
                    creds = _do_reauth()

        # 2. Build Gmail service and create the draft
        service = build("gmail", "v1", credentials=creds)

        message = MIMEText(body)
        message["to"]      = to
        message["subject"] = subject

        raw   = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        draft = service.users().drafts().create(
            userId="me",
            body={"message": {"raw": raw}},
        ).execute()

        draft_id = draft.get("id", "unknown")
        return f"Draft saved — subject: '{subject}', draft ID: {draft_id}."

    except RuntimeError as e:
        return str(e)
    except HttpError as e:
        if e.resp.status == 403:
            return (
                "Gmail draft failed: insufficient permissions (403). "
                "Run python3.11 reauth_gmail.py to grant gmail.compose access, then retry."
            )
        return f"Gmail API error {e.resp.status}: {e}"
    except Exception as e:
        return f"Draft email failed: {e}"


def get_weather(location: str = "Detroit, Michigan") -> str:
    """
    Get current and tomorrow's weather using Open-Meteo (free, no key needed).
    Returns a plain-text summary ready for Claude to reason over.
    """
    try:
        geo_params = urllib.parse.urlencode({
            "name":     location.split(",")[0].strip(),
            "count":    1,
            "language": "en",
            "format":   "json",
        })
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?{geo_params}"
        geo_req = urllib.request.Request(geo_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(geo_req, timeout=6) as r:
            geo_data = json.loads(r.read().decode("utf-8"))
        results = geo_data.get("results", [])
        if not results:
            return f"Couldn't find location: {location}"
        lat = results[0]["latitude"]
        lon = results[0]["longitude"]
        tz  = results[0].get("timezone", "America/Detroit")
    except Exception as e:
        return f"Geocoding failed: {e}"

    try:
        wx_params = urllib.parse.urlencode({
            "latitude":           lat,
            "longitude":          lon,
            "timezone":           tz,
            "current":            "temperature_2m,apparent_temperature,precipitation,weathercode,windspeed_10m,relativehumidity_2m",
            "daily":              "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode,windspeed_10m_max",
            "temperature_unit":   "celsius",
            "windspeed_unit":     "kmh",
            "precipitation_unit": "inch",
            "forecast_days":      2,
        })
        wx_url = f"https://api.open-meteo.com/v1/forecast?{wx_params}"
        wx_req = urllib.request.Request(wx_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(wx_req, timeout=6) as r:
            wx = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return f"Weather fetch failed: {e}"

    WX_CODES = {
        0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
        45: "foggy", 51: "light drizzle", 53: "moderate drizzle", 55: "heavy drizzle",
        61: "light rain", 63: "moderate rain", 65: "heavy rain",
        71: "light snow", 73: "moderate snow", 75: "heavy snow",
        80: "light showers", 81: "moderate showers", 82: "heavy showers",
        95: "thunderstorm", 96: "thunderstorm with hail",
    }

    cur   = wx.get("current", {})
    daily = wx.get("daily", {})

    cur_temp     = cur.get("temperature_2m", "?")
    cur_feels    = cur.get("apparent_temperature", "?")
    cur_humidity = cur.get("relativehumidity_2m", "?")
    cur_wind     = cur.get("windspeed_10m", "?")
    cur_code     = WX_CODES.get(cur.get("weathercode", -1), "unknown")

    tmr_max    = daily.get("temperature_2m_max",  [None, None])[1]
    tmr_min    = daily.get("temperature_2m_min",  [None, None])[1]
    tmr_precip = daily.get("precipitation_sum",   [None, None])[1]
    tmr_wind   = daily.get("windspeed_10m_max",   [None, None])[1]
    tmr_code   = WX_CODES.get((daily.get("weathercode") or [-1,-1])[1], "unknown")

    return (
        f"Current in {location}: {cur_temp}°C (feels {cur_feels}°C), {cur_code}, "
        f"humidity {cur_humidity}%, wind {cur_wind}km/h. "
        f"Tomorrow: high {tmr_max}°C / low {tmr_min}°C, {tmr_code}, "
        f"precip {tmr_precip}in, max wind {tmr_wind}km/h."
    )
# ── Spotify Playback ───────────────────────────────────────────────────────────

def play_on_spotify(query: str, media_type: str = "track") -> str:
    """
    Search Spotify and immediately start playing the best match.
    Requires Spotify Premium and an active device.

    media_type: "track" (default), "artist", "album", "playlist"

    Examples:
      play_on_spotify("Kendrick Lamar Not Like Us")           → plays the track
      play_on_spotify("Drake", "artist")                      → plays Drake's top tracks
      play_on_spotify("To Pimp a Butterfly", "album")         → plays the album
      play_on_spotify("lofi hip hop", "playlist")             → plays matching playlist
    """
    import urllib.request as _req
    import json as _json

    query      = query.strip()
    media_type = media_type.lower().strip()

    if media_type not in ("track", "artist", "album", "playlist"):
        media_type = "track"

    if not query:
        return "No search query provided."

    # Hit the Jarvis FastAPI endpoint — avoids duplicating spotipy auth here
    try:
        import urllib.request
        import json

        payload = json.dumps({"query": query, "type": media_type}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8765/spotify/play-track",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read().decode("utf-8"))

        if result.get("status") == "ok":
            playing = result.get("playing", query)
            return f"Playing {playing} on Spotify."
        else:
            msg = result.get("message", "unknown error")
            # Friendly handling for common errors
            if "No active device" in msg or "NO_ACTIVE_DEVICE" in msg:
                return "Spotify isn't active on any device — open Spotify on your Mac or phone first, then try again."
            if "Premium" in msg or "PREMIUM_REQUIRED" in msg:
                return "Spotify Premium is required for playback control."
            return f"Spotify playback failed: {msg}"

    except Exception as e:
        return f"Spotify playback failed: {e}"


# ── URL Summarization ──────────────────────────────────────────────────────────

def fetch_url_summary(url: str, mode: str = "general") -> str:
    """
    Fetch a URL and summarize its content using Haiku.

    mode:
      "general"  — general summary (default)
      "job"      — extract role, company, location, requirements, salary, deadline
      "article"  — extract key points and main argument

    Returns a clean text summary ready to be spoken or displayed.
    Handles paywalls and bot-blocked pages gracefully.
    """
    import urllib.request
    import urllib.error
    import json
    import re

    # ── Fetch the page ─────────────────────────────────────────────────────────
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return f"Couldn't fetch that page — HTTP {e.code}. It may require login or be paywalled."
    except urllib.error.URLError as e:
        return f"Couldn't reach {url}: {e.reason}"
    except Exception as e:
        return f"Failed to fetch URL: {e}"

    # ── Strip HTML to text ─────────────────────────────────────────────────────
    # Remove scripts, styles, nav, footer
    raw = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r"<[^>]+>", " ", raw)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Truncate to ~6000 chars — enough context for Haiku without blowing tokens
    text = text[:6000]

    if len(text) < 100:
        return "Page content was too short or empty — it may be JavaScript-rendered or paywalled."

    # ── Build prompt based on mode ─────────────────────────────────────────────
    if mode == "job":
        system = (
            "You are Jarvis, Edward Haddad's AI assistant. "
            "Extract the key details from this job posting and present them clearly. "
            "Cover: role title, company, location (remote/hybrid/onsite), "
            "key responsibilities (3-5 bullets), required qualifications, "
            "preferred qualifications, salary/compensation if mentioned, "
            "and application deadline if mentioned. "
            "Be concise — Edward will use this to decide whether to apply."
        )
    elif mode == "article":
        system = (
            "You are Jarvis, Edward Haddad's AI assistant. "
            "Summarize this article in 3-5 sentences. "
            "Cover the main argument, key findings, and any actionable takeaways. "
            "Be direct and concise."
        )
    else:
        system = (
            "You are Jarvis, Edward Haddad's AI assistant. "
            "Summarize the key information from this webpage in 3-5 sentences. "
            "Focus on what would be most useful to Edward. Be direct and concise."
        )

    # ── Call Haiku ─────────────────────────────────────────────────────────────
    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return "Anthropic API key not set — can't summarize."

        payload = json.dumps({
            "model": "claude-haiku-4-5",
            "max_tokens": 600,
            "system": system,
            "messages": [
                {"role": "user", "content": f"URL: {url}\n\nPage content:\n{text}"}
            ]
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read().decode("utf-8"))

        return result["content"][0]["text"].strip()

    except Exception as e:
        return f"Summary failed: {e}"


# ── Claude Code Integration ────────────────────────────────────────────────────
# Add these two functions to the bottom of search.py

import subprocess
from pathlib import Path

JARVIS_DIR = Path(__file__).parent  # ~/Desktop/Projects/Jarvis


def run_claude_code(prompt: str) -> str:
    """
    Hand off a coding task to Claude Code via `claude --print`.
    Runs in the Jarvis project directory. Captures stdout + stderr.
    Times out after 120 seconds.

    Returns the raw output from Claude Code, trimmed, ready to relay to Edward.
    """
    try:
        result = subprocess.run(
            ["claude", "--print", "--dangerously-skip-permissions", prompt],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(JARVIS_DIR),
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode != 0:
            # Claude Code signals an error
            error_detail = stderr or stdout or f"Exit code {result.returncode}"
            return f"Claude Code exited with error: {error_detail}"

        if not stdout:
            return "Claude Code ran but returned no output."

        return stdout

    except FileNotFoundError:
        return (
            "Claude Code not found — make sure it's installed and on PATH. "
            "Run: npm install -g @anthropic-ai/claude-code"
        )
    except subprocess.TimeoutExpired:
        return "Claude Code timed out after 120 seconds. Try breaking the task into smaller steps."
    except Exception as e:
        return f"Claude Code failed: {e}"


# ── Heavy Coding Task Detector ──────────────────────────────────────────────────

# Signals that suggest Claude Code is the right tool:
# — multi-file operations, refactors, new features, migrations
_HEAVY_CODING_SIGNALS = {
    # scale / scope keywords
    "refactor", "rewrite", "migrate", "overhaul", "redesign",
    "across all", "across every", "all files", "all modules",
    "multiple files", "every file",

    # architectural changes
    "add a new agent", "new agent", "new tool", "new module",
    "new feature", "new endpoint", "new pipeline", "new panel",
    "add support for", "integrate", "wire up",

    # complex operations
    "implement", "build out", "set up", "scaffold", "bootstrap",
    "port to", "convert to", "switch to",

    # debug-heavy tasks
    "find all", "hunt down", "trace through", "audit",
    "test end-to-end", "end to end test",
}

# Signals that strongly indicate Claude Code should be skipped
# (these are quick edits the Projects agent handles fine)
# NOTE: checked as whole words to avoid substring false positives (e.g. "read" inside "reads from")
_LIGHT_CODING_SIGNALS = {
    "add a comment", "fix this line", "rename this", "typo",
    "quick fix", "one liner", "small change", "minor",
    "what does", "explain", "show me",
    # "read" and "reads" handled separately via whole-word check below
}

_LIGHT_WORD_SIGNALS = {"read", "reads", "reading"}  # matched as whole words only

# Minimum word count to even consider routing to Claude Code
_MIN_WORDS_FOR_HEAVY = 6


def detect_heavy_coding_task(text: str) -> bool:
    """
    Returns True if the request looks like a multi-file / architectural coding
    task that should be handed off to Claude Code rather than handled inline
    by the Projects agent.

    Heuristics (all must pass):
    1. Text is long enough to be a real task (> _MIN_WORDS_FOR_HEAVY words)
    2. At least one heavy-coding signal present
    3. No light-coding override signals present
    """
    lowered = text.lower()
    words = lowered.split()

    if len(words) < _MIN_WORDS_FOR_HEAVY:
        return False

    # Phrase-level light signals (substring match is fine — they're multi-word)
    if any(signal in lowered for signal in _LIGHT_CODING_SIGNALS):
        return False

    # Word-level light signals — whole word only to avoid "reads" matching "read"
    word_set = set(words)
    if word_set & _LIGHT_WORD_SIGNALS:
        # Only bail if reading is the *primary* intent — not if it's incidental
        # (e.g. "reads from vault" in the middle of a complex implement task)
        # Heuristic: bail only if the sentence starts with a light word
        if words[0] in _LIGHT_WORD_SIGNALS:
            return False

    return any(signal in lowered for signal in _HEAVY_CODING_SIGNALS)
