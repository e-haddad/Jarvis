# usage_tracker.py
# Persistent usage tracking for Claude API and ElevenLabs TTS.
#
# Claude:      tracks input + output tokens per call, estimates cost
#              using Haiku 4.5 and Sonnet 4.6 pricing
# ElevenLabs:  tracks characters sent per speak() call
#
# Storage:     ~/Desktop/Projects/Jarvis/usage_data.json
# Reset:       auto-resets on the 1st of each month
# Seeded with: Claude $0.86, ElevenLabs 1311 chars used (as of session start)

import json
import os
from datetime import datetime
from pathlib import Path
from threading import Lock

USAGE_FILE = Path(__file__).parent / "usage_data.json"
_lock      = Lock()

# ── Pricing (as of May 2026) ───────────────────────────────────────────────────
# Haiku 4.5:  $0.80/M input,  $4.00/M output
# Sonnet 4.6: $3.00/M input, $15.00/M output

PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80 / 1_000_000, "output": 4.00 / 1_000_000},
    "claude-sonnet-4-6":         {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
}

# ── Limits ─────────────────────────────────────────────────────────────────────

CLAUDE_BUDGET_USD     = 20.00
ELEVENLABS_CHAR_LIMIT = 10_000

# ── Seed values (actual usage as of tracker install) ──────────────────────────

SEED_CLAUDE_USD   = 0.86
SEED_EL_CHARS     = 1_311   # 10000 - 8689 remaining


# ── Storage ────────────────────────────────────────────────────────────────────

def _default_data() -> dict:
    now = datetime.now()
    return {
        "month":          now.strftime("%Y-%m"),
        "claude_usd":     SEED_CLAUDE_USD,
        "claude_tokens":  {"input": 0, "output": 0},
        "el_chars":       SEED_EL_CHARS,
        "last_updated":   now.isoformat(),
    }


def _load() -> dict:
    try:
        if USAGE_FILE.exists():
            data = json.loads(USAGE_FILE.read_text())
            # Auto-reset on new month
            current_month = datetime.now().strftime("%Y-%m")
            if data.get("month") != current_month:
                data = _default_data()
                data["month"] = current_month
                _save(data)
            return data
    except Exception:
        pass
    data = _default_data()
    _save(data)
    return data


def _save(data: dict):
    try:
        data["last_updated"] = datetime.now().isoformat()
        USAGE_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


# ── Public API ─────────────────────────────────────────────────────────────────

def record_claude_usage(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
):
    """
    Call after every Claude API response.
    Cache-aware pricing:
      - cache_creation_tokens billed at 1.25x input rate (writing to cache)
      - cache_read_tokens billed at 0.10x input rate (reading from cache)
      - remaining input_tokens billed at full input rate
    """
    with _lock:
        data  = _load()
        rates = PRICING.get(model, PRICING["claude-sonnet-4-6"])

        # Regular input = total input minus tokens that came from cache
        regular_input = max(0, input_tokens - cache_read_tokens - cache_creation_tokens)

        cost = (
            regular_input       * rates["input"] +
            cache_creation_tokens * rates["input"] * 1.25 +
            cache_read_tokens     * rates["input"] * 0.10 +
            output_tokens         * rates["output"]
        )

        data["claude_usd"]               += cost
        data["claude_tokens"]["input"]   += input_tokens
        data["claude_tokens"]["output"]  += output_tokens
        _save(data)


def record_elevenlabs_chars(char_count: int):
    """Call after every successful ElevenLabs TTS call with character count."""
    with _lock:
        data = _load()
        data["el_chars"] += char_count
        _save(data)


def get_usage() -> dict:
    """
    Returns current usage snapshot:
    {
        "claude_usd":        float,   # dollars spent this month
        "claude_pct":        float,   # 0-100
        "claude_budget":     float,   # $20.00
        "el_chars_used":     int,
        "el_chars_limit":    int,     # 10000
        "el_pct":            float,   # 0-100
        "el_chars_remaining": int,
        "month":             str,
    }
    """
    with _lock:
        data = _load()

    claude_usd = data.get("claude_usd", SEED_CLAUDE_USD)
    el_chars   = data.get("el_chars",   SEED_EL_CHARS)

    return {
        "claude_usd":          round(claude_usd, 4),
        "claude_pct":          min(100.0, round(claude_usd / CLAUDE_BUDGET_USD * 100, 1)),
        "claude_budget":       CLAUDE_BUDGET_USD,
        "el_chars_used":       el_chars,
        "el_chars_limit":      ELEVENLABS_CHAR_LIMIT,
        "el_pct":              min(100.0, round(el_chars / ELEVENLABS_CHAR_LIMIT * 100, 1)),
        "el_chars_remaining":  max(0, ELEVENLABS_CHAR_LIMIT - el_chars),
        "month":               data.get("month", datetime.now().strftime("%Y-%m")),
    }


def fetch_elevenlabs_live() -> int | None:
    """
    Fetch current ElevenLabs character usage from their API.
    Returns chars_used or None on failure.
    Updates local tracker to stay in sync.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        return None
    try:
        import requests
        resp = requests.get(
            "https://api.elevenlabs.io/v1/user/subscription",
            headers={"xi-api-key": api_key},
            timeout=5,
        )
        if resp.status_code == 200:
            sub  = resp.json()
            used = sub.get("character_count", None)
            if used is not None:
                with _lock:
                    data = _load()
                    data["el_chars"] = used
                    _save(data)
                return used
    except Exception:
        pass
    return None


if __name__ == "__main__":
    u = get_usage()
    print(f"Claude:      ${u['claude_usd']:.4f} / ${u['claude_budget']:.2f}  ({u['claude_pct']}%)")
    print(f"ElevenLabs:  {u['el_chars_used']:,} / {u['el_chars_limit']:,} chars  ({u['el_pct']}%)")
    print(f"Month:       {u['month']}")
    live = fetch_elevenlabs_live()
    if live:
        print(f"ElevenLabs live: {live:,} chars used")
