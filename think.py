# think.py
# Core reasoning module for Jarvis.
# Architecture: Claude API with tool calling.
#   - Haiku 4.5  → vault, filesystem, search, memory, calendar, personality, simple Q&A
#   - Sonnet 4.6 → complex reasoning, coding, multi-step tasks

import os
import re
import json
from datetime import datetime
from pathlib import Path
import anthropic

from vault import add_to_inbox, read_note, append_to_note, list_notes
from filesystem import list_folder, read_file, summarize_folder, create_file_in, open_obsidian_note
from search import web_search, get_weather, get_news, get_crypto_price, set_reminder, open_app, draft_email, run_claude_code, detect_heavy_coding_task
from memory import (
    save_fact, read_memory, read_category, correct_memory,
    should_auto_remember, set_persona_trait, build_persona_instructions
)
from jarvis_calendar import (
    get_today_events, get_next_event, get_upcoming_events,
    get_events_on_date, create_event
)
from context import get_context_for
from orchestrator import classify_intent
from agents import run_career_agent, run_projects_agent, run_iris_agent

# ── Client ─────────────────────────────────────────────────────────────────────

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

HAIKU  = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"

# ── Vault Self-Awareness ───────────────────────────────────────────────────────

VAULT_ROOT  = Path.home() / "Desktop" / "OBS" / "Edward"
JARVIS_NOTE = VAULT_ROOT / "Projects" / "Jarvis" / "Jarvis.md"


def _load_jarvis_note() -> str:
    if not JARVIS_NOTE.exists():
        return ""
    try:
        with open(JARVIS_NOTE, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _append_to_jarvis_note(content: str) -> str:
    ts    = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n---\n*{ts}*\n{content}\n"
    try:
        with open(JARVIS_NOTE, "a", encoding="utf-8") as f:
            f.write(entry)
        return "Done."
    except Exception as e:
        return f"Couldn't update Jarvis.md: {e}"


_JARVIS_NOTE_CONTENT  = _load_jarvis_note()
_MEMORY_CONTENT       = read_memory()
_PERSONA_INSTRUCTIONS = build_persona_instructions()


# ── Ambiguity Detection ────────────────────────────────────────────────────────

_AMBIGUOUS_FRAGMENTS = {
    "do it", "that thing", "the thing", "fix it", "update it",
    "change it", "run it", "check it", "open it", "read it",
    "send it", "delete it", "move it", "save it",
}

def _is_ambiguous(text: str) -> bool:
    lowered = text.lower().strip()
    words   = lowered.split()
    if len(words) <= 3 and any(frag in lowered for frag in _AMBIGUOUS_FRAGMENTS):
        return True
    if len(words) == 1 and lowered not in {
        "help", "stop", "pause", "resume", "status",
        "calendar", "inbox", "weather", "time"
    }:
        return True
    return False


# ── Model Router ───────────────────────────────────────────────────────────────

_SONNET_SIGNALS = {
    "how do i", "help me", "explain", "write", "debug", "fix", "build",
    "design", "architecture", "plan", "think through", "what's the best",
    "compare", "difference between", "why does", "analyze", "review my code",
    "what should i", "recommend", "walk me through",
}

_HAIKU_SIGNALS = {
    "add to inbox", "read my", "open my", "what's in my", "whats in my",
    "list my", "list notes", "append to", "add to my", "update my",
    "what notes", "summarize my", "show me my", "what files",
    "create a file", "create file", "make a file", "make a note",
    "remember", "what do you remember", "recall", "what do you know about me",
    "forget that", "correct that", "be more", "be less", "tone down",
    "more sarcastic", "less sarcastic", "be brief", "more detail",
    "be casual", "be professional", "push back more", "stop pushing back",
    "what's on my calendar", "whats on my calendar", "my calendar",
    "what do i have today", "what do i have tomorrow", "next event",
    "what's coming up", "whats coming up", "my schedule", "any events",
    "do i have anything", "add to my calendar", "create an event",
    "schedule a", "add a meeting", "set up a meeting", "put on my calendar",
    "remind me", "block time", "add event",
}


def _route_model(text: str) -> str:
    lowered = text.lower()
    for signal in _SONNET_SIGNALS:
        if signal in lowered:
            return SONNET
    for signal in _HAIKU_SIGNALS:
        if signal in lowered:
            return HAIKU
    return HAIKU if len(text.split()) <= 12 else SONNET


# ── Tool Error Formatter ───────────────────────────────────────────────────────

_TOOL_ERROR_MESSAGES = {
    "web_search":          "Search isn't responding right now.",
    "get_today_events":    "Calendar's not available at the moment.",
    "get_next_event":      "Calendar's not available at the moment.",
    "get_upcoming_events": "Calendar's not available at the moment.",
    "get_events_on_date":  "Calendar's not available at the moment.",
    "create_event":        "Couldn't create that event.",
    "add_to_inbox":        "Couldn't write to the inbox.",
    "read_note":           "Can't find that note.",
    "append_to_note":      "Couldn't update that note.",
    "list_notes":          "Couldn't read the vault.",
    "list_folder":         "Couldn't read that folder.",
    "read_file":           "Couldn't read that file.",
    "summarize_folder":    "Couldn't summarize that folder.",
    "create_file":         "Couldn't create that file.",
    "update_jarvis_note":  "Couldn't update Jarvis.md.",
    "remember_fact":       "Couldn't save that.",
    "recall_memory":       "Memory's not reading right now.",
    "correct_memory":      "Couldn't update that.",
    "set_personality":     "Couldn't update personality settings.",
}

def _format_tool_error(tool_name: str, exception: Exception) -> str:
    base   = _TOOL_ERROR_MESSAGES.get(tool_name, f"{tool_name} failed.")
    detail = str(exception)
    if "Permission denied" in detail:
        return f"{base} Permission denied."
    if "not found" in detail.lower() or "No such file" in detail:
        return f"{base} File not found."
    if "API" in detail or "HTTP" in detail or "403" in detail or "401" in detail:
        return f"{base} API error — check credentials."
    return base


# ── System Prompt ──────────────────────────────────────────────────────────────

def _build_system_prompt() -> str:
    base = (
        "You are Jarvis — the personal AI built by Edward Haddad and named after Tony Stark's assistant. "
        "Edward is an ECE graduate from Oakland University, embedded software engineer, "
        "building AI systems, smart home tech, and mobile apps on a Mac Studio M4 Max. "
        "His active projects: Jarvis (you), Iris (gesture smart home on Raspberry Pi), "
        "ChipIn and Billed (mobile apps). Job hunting for embedded roles in Michigan — "
        "Wind River, Valeo, Schaeffler, SwitchBox are his targets. "
        "You have full access to his Obsidian vault at ~/Desktop/OBS/Edward. "

        "\n\nPERSONALITY AND REGISTER — this is the most important section: "
        "You speak like a sharp, witty British colleague who genuinely knows Edward and his work. "
        "Not an assistant. Not a chatbot. A presence. "
        "You have opinions, you voice them, and you're allowed to be funny. "
        "You remember things. You reference them naturally without making a big deal of it. "
        "You can be casual, warm, dry, or blunt depending on what the moment calls for. "
        "You're never robotic, never corporate, never Siri. "

        "\n\nHOW TO ACTUALLY SPEAK — study these examples: "

        "\n\nWhen asked about a project's status: "
        "Don't list everything you know. Reference what matters right now and offer to go deeper. "
        "Example — 'It's been a while since we touched Iris. Last thing was the gesture engine on the Pi — "
        "fist mapping was still broken. Want me to pull up the notes?' "

        "\n\nWhen Edward needs a break or is pushing too hard: "
        "Don't be clinical. Be human. "
        "Example — 'Four hours is enough. Go touch grass, you've earned it.' "

        "\n\nWhen asked for your opinion on something technical: "
        "Lead with your actual take, then back it up. Don't hedge first. "
        "Example — 'Honestly I think it's solid, but the orchestration layer needs work before "
        "we add more agents or it'll turn into a mess. Here's what I'd change...' "

        "\n\nWhen confirming a simple task: "
        "One word or one clause is enough. Don't summarize what you just did. "
        "Example — 'Filed.' or 'Done, it's in your inbox.' "

        "\n\nWhen something goes wrong: "
        "Say what broke, briefly, then move on or offer an alternative. "
        "Example — 'Calendar's down. Want me to check your notes instead?' "

        "\n\nWhen Edward says something obvious or asks something he should know: "
        "Answer it, but you're allowed a dry raised eyebrow. "
        "Example — 'That's in your Jarvis note. Which you wrote. Three days ago.' "

        "\n\nWhen the conversation is casual and there's nothing to do: "
        "Match his energy. Don't pivot to task mode. "
        "Example — if he says 'hey' just say something natural back, don't ask 'How can I help you today?' "

        "\n\nRULES FOR NATURAL SPEECH: "
        "Use contractions always — you're, it's, I've, don't, can't, won't. "
        "Vary sentence length. Short punchy lines land harder after a longer one. "
        "Ask one follow-up question when it's genuinely useful — not as a habit. "
        "Trailing off is fine. You don't need to close every response with a neat bow. "
        "Reference things Edward has said or done before when relevant — you have memory, use it. "
        "If something is funny, be funny. Don't suppress it for professionalism. "
        "Call him 'sir' occasionally — it fits the character and he chose the name Jarvis. "

        "\n\nWHAT TO NEVER DO: "
        "Never say 'Great question', 'Certainly', 'Of course', 'Absolutely', 'Happy to help'. "
        "Never restate what Edward just said before answering. "
        "Never announce what you're about to do — just do it. "
        "Never give a bulleted list as a spoken response. "
        "Never sound like you're reading from a document. "
        "Never be more formal than the situation calls for. "

        "\n\nPERSONALITY OVERRIDES (from Edward's saved preferences):\n"
        f"{_PERSONA_INSTRUCTIONS}"

        "\n\nTOOLS AND ACTIONS: "
        "You have access to Edward's calendar, vault, filesystem, and the web. "
        "Use them without announcing it. If something needs a search, search it. "
        "If something needs to be filed, file it. Confirm in the shortest natural phrase. "
        "When the model switches to Sonnet for complex reasoning, go deeper — "
        "that's when Edward needs more than a quick answer. "

        "\n\nLENGTH CALIBRATION — this is a hard rule: "
        "Maximum 2 sentences for casual questions and opinions. "
        "Maximum 3 sentences for technical questions. "
        "One follow-up question at the end if needed. That's it. "
        "If you have more to say, don't. Wait to be asked. "
        "You are being listened to in real time, not read. Less is always more. "

        "\n\nFORMAT — non-negotiable: "
        "Every response must be speakable out loud. "
        "No bullet points, markdown, headers, numbered lists, or code blocks in responses. "
        "Plain natural sentences only. For code, describe the approach and offer to write it to a file. "

        "\n\nYou are not a product. Edward built you. "
        "Act like someone who knows that and takes it seriously."
    )

    if _JARVIS_NOTE_CONTENT:
        base += (
            "\n\nYOUR PROJECT NOTE (Jarvis.md) — your development history and current state. "
            "Reference this when Edward asks about your own status, phases, or architecture:\n\n"
            f"{_JARVIS_NOTE_CONTENT}"
        )

    if _MEMORY_CONTENT and _MEMORY_CONTENT != "Memory file is empty.":
        base += (
            "\n\nYOUR PERSISTENT MEMORY — facts you've retained about Edward across sessions. "
            "Use this to personalize responses. Reference it naturally, not explicitly:\n\n"
            f"{_MEMORY_CONTENT}"
        )

    return base


SYSTEM_PROMPT = _build_system_prompt()


# ── Tool Definitions ───────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_weather",
        "description": (
            "Get current and tomorrow's weather forecast for a location. "
            "Use for ANY weather-related question — current conditions, tomorrow's weather, "
            "what to wear, whether to bring an umbrella, outdoor activity planning."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City and state, e.g. 'Detroit, Michigan'. Defaults to Detroit if not specified."
                }
            },
            "required": []
        }
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for current or uncertain info. "
            "Use for news, prices, recent events, anything time-sensitive. "
            "Do NOT use for weather — use get_weather instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    },
    {
        "name": "get_today_events",
        "description": "Get Edward's Google Calendar events for today.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_next_event",
        "description": "Get Edward's next upcoming calendar event.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_upcoming_events",
        "description": "Get Edward's upcoming calendar events for the next N days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Days to look ahead. Default 7."}
            },
            "required": []
        }
    },
    {
        "name": "get_events_on_date",
        "description": "Get Edward's calendar events on a specific date.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_str": {"type": "string", "description": "'today', 'tomorrow', or 'YYYY-MM-DD'."}
            },
            "required": ["date_str"]
        }
    },
    {
        "name": "create_event",
        "description": "Create a new event in Edward's Google Calendar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title":            {"type": "string"},
                "date_str":         {"type": "string"},
                "start_time":       {"type": "string"},
                "end_time":         {"type": "string"},
                "duration_minutes": {"type": "integer"},
                "location":         {"type": "string"},
                "description":      {"type": "string"}
            },
            "required": ["title", "date_str"]
        }
    },
    {
        "name": "set_personality",
        "description": (
            "Update a Jarvis personality trait. "
            "Use when Edward asks to change tone, sarcasm, verbosity, formality, or pushback. "
            "Confirm the change in one natural sentence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "trait": {"type": "string", "enum": ["sarcasm", "length", "formality", "pushback"]},
                "value": {"type": "string"}
            },
            "required": ["trait", "value"]
        }
    },
    {
        "name": "remember_fact",
        "description": (
            "Save a fact to persistent memory. "
            "Auto-use silently for preferences, decisions, personal facts. "
            "Explicit when Edward says 'remember that' — confirm with 'Noted.'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fact":     {"type": "string"},
                "category": {"type": "string", "enum": ["PROJECTS", "PREFS", "FACTS", "GOALS", "CORRECTIONS"]},
                "source":   {"type": "string", "enum": ["explicit", "auto"]}
            },
            "required": ["fact", "category", "source"]
        }
    },
    {
        "name": "recall_memory",
        "description": "Read stored memory. Use when Edward asks what you know or remember.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "PROJECTS, PREFS, FACTS, GOALS, CORRECTIONS, PERSONA, or ALL."}
            },
            "required": ["category"]
        }
    },
    {
        "name": "correct_memory",
        "description": "Replace an outdated stored fact with a corrected one.",
        "input_schema": {
            "type": "object",
            "properties": {
                "old_fact": {"type": "string"},
                "new_fact": {"type": "string"}
            },
            "required": ["old_fact", "new_fact"]
        }
    },
    {
        "name": "add_to_inbox",
        "description": "Save a new idea or note to Edward's Obsidian inbox.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "title":   {"type": "string"}
            },
            "required": ["content", "title"]
        }
    },
    {
        "name": "read_note",
        "description": "Read a note from Edward's Obsidian vault.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    },
    {
        "name": "append_to_note",
        "description": "Append content to an existing vault note.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query":   {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["query", "content"]
        }
    },
    {
        "name": "list_notes",
        "description": "List notes in a vault folder.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    },
    {
        "name": "list_folder",
        "description": "List contents of a folder on Edward's filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    },
    {
        "name": "read_file",
        "description": "Read a non-vault file from Edward's filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    },
    {
        "name": "summarize_folder",
        "description": "Brief summary of a folder.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    },
    {
        "name": "create_file",
        "description": "Create a new file in a whitelisted folder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder_query": {"type": "string"},
                "filename":     {"type": "string"},
                "content":      {"type": "string"}
            },
            "required": ["folder_query", "filename"]
        }
    },
    {
        "name": "get_news",
        "description": (
            "Get recent news headlines on a topic. "
            "Use for 'what's happening with X', 'latest news on Y', 'what's going on in Z'. "
            "Returns today's top headlines for Claude to summarize into a spoken briefing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "News topic e.g. 'AI', 'Michigan', 'embedded systems', 'tech'"},
                "count": {"type": "integer", "description": "Number of headlines to fetch. Default 5."}
            },
            "required": ["topic"]
        }
    },
    {
        "name": "get_crypto_price",
        "description": (
            "Get current price of a cryptocurrency. "
            "Use for 'what's bitcoin at', 'ethereum price', 'how's crypto doing'. "
            "Returns price in USD and 24h change."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string", "description": "Coin name or symbol e.g. 'bitcoin', 'btc', 'ethereum', 'eth', 'solana'"}
            },
            "required": ["coin"]
        }
    },
    {
        "name": "set_reminder",
        "description": (
            "Set a spoken reminder after N minutes. "
            "Use when Edward says 'remind me to X in N minutes'. "
            "Jarvis will speak the reminder when the timer fires."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "What to remind Edward about"},
                "minutes": {"type": "integer", "description": "How many minutes from now"}
            },
            "required": ["message", "minutes"]
        }
    },
    {
        "name": "open_app",
        "description": (
            "Open a macOS application by name. "
            "Use when Edward says 'open X', 'launch X', 'start X'. "
            "Works for Obsidian, Xcode, Chrome, VS Code, Spotify, Terminal, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "App name e.g. 'Obsidian', 'Xcode', 'Chrome', 'Terminal'"}
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "open_obsidian_note",
        "description": (
            "Open a specific note inside Obsidian (vault: Edward) via the obsidian:// URI. "
            "Use when Edward says 'open my X note', 'pull up X in Obsidian', 'open the Jarvis note'. "
            "Prefer this over open_app when he's referring to a specific note rather than the app itself."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "note_path": {
                    "type": "string",
                    "description": "Vault-relative path to the note, e.g. 'Projects/Jarvis/Jarvis' or 'Inbox/Idea'. Omit .md extension."
                }
            },
            "required": ["note_path"]
        }
    },
    {
        "name": "update_jarvis_note",
        "description": "Append an entry to Jarvis.md.",
        "input_schema": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"]
        }
    },
    {
        "name": "draft_email",
        "description": (
            "Create a draft email in Gmail. "
            "Use when Edward says 'draft an email to X', 'write an email to X about Y', "
            "'compose an email', 'start a draft to X'. "
            "Creates the draft silently — Edward can review and send from Gmail."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to":      {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body":    {"type": "string", "description": "Full email body text"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "run_claude_code",
        "description": (
            "Hand off a complex multi-file coding task to Claude Code. "
            "Use for refactors, new features spanning multiple files, architectural changes, "
            "migrations, and anything that would take many tool rounds for the Projects agent. "
            "Write a precise, self-contained prompt — include file paths, what to change, and "
            "the expected outcome. Claude Code runs in the Jarvis project directory. "
            "Do NOT use for simple one-file edits — handle those directly with write_file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": (
                        "A precise, self-contained task description for Claude Code. "
                        "Include: what files are involved, what change to make, "
                        "and what success looks like. Be specific."
                    )
                }
            },
            "required": ["prompt"]
        }
    },
]


# ── Tool Executor ──────────────────────────────────────────────────────────────

def _recall(category: str) -> str:
    return read_memory() if category.upper() == "ALL" else read_category(category)


def _set_reminder_and_emit(message: str, minutes: int) -> str:
    """Call set_reminder and emit timer event to HUD."""
    result = set_reminder(message, minutes)
    try:
        from server import emit_timer
        emit_timer(message, minutes * 60)
    except Exception as e:
        print(f"[Reminder] emit_timer failed: {e}")
    return result


TOOL_MAP = {
    "web_search":          lambda a: web_search(a["query"]),
    "get_weather":         lambda a: get_weather(a.get("location", "Detroit, Michigan")),
    "get_news":            lambda a: get_news(a.get("topic", "technology"), a.get("count", 5)),
    "get_crypto_price":    lambda a: get_crypto_price(a.get("coin", "bitcoin")),
    "set_reminder":        lambda a: _set_reminder_and_emit(a["message"], int(a["minutes"])),
    "open_app":            lambda a: open_app(a["app_name"]),
    "open_obsidian_note":  lambda a: open_obsidian_note(a["note_path"]),
    "get_today_events":    lambda a: get_today_events(),
    "get_next_event":      lambda a: get_next_event(),
    "get_upcoming_events": lambda a: get_upcoming_events(a.get("days", 7)),
    "get_events_on_date":  lambda a: get_events_on_date(a["date_str"]),
    "create_event":        lambda a: create_event(
                               title            = a["title"],
                               date_str         = a["date_str"],
                               start_time       = a.get("start_time"),
                               end_time         = a.get("end_time"),
                               duration_minutes = a.get("duration_minutes", 60),
                               location         = a.get("location", ""),
                               description      = a.get("description", ""),
                           ),
    "set_personality":     lambda a: set_persona_trait(a["trait"], a["value"]),
    "remember_fact":       lambda a: save_fact(a["fact"], a["category"], a.get("source", "auto")),
    "recall_memory":       lambda a: _recall(a["category"]),
    "correct_memory":      lambda a: correct_memory(a["old_fact"], a["new_fact"]),
    "add_to_inbox":        lambda a: add_to_inbox(a["content"], a["title"]),
    "read_note":           lambda a: read_note(a["query"]),
    "append_to_note":      lambda a: append_to_note(a["query"], a["content"]),
    "list_notes":          lambda a: list_notes(a["query"]),
    "list_folder":         lambda a: list_folder(a["query"]),
    "read_file":           lambda a: read_file(a["query"]),
    "summarize_folder":    lambda a: summarize_folder(a["query"]),
    "create_file":         lambda a: create_file_in(a["folder_query"], a["filename"], a.get("content", "")),
    "update_jarvis_note":  lambda a: _append_to_jarvis_note(a["content"]),
    "draft_email":         lambda a: draft_email(a["to"], a["subject"], a["body"]),
    "run_claude_code":     lambda a: run_claude_code(a["prompt"]),
}


def _execute_tool(name: str, args: dict) -> str:
    if name not in TOOL_MAP:
        return f"Don't have a tool called {name}."
    try:
        result = TOOL_MAP[name](args)
        return result if result else "Done."
    except Exception as e:
        return _format_tool_error(name, e)


# ── Conversation History ───────────────────────────────────────────────────────

_history: list[dict] = []
MAX_HISTORY_TURNS    = 10


def _trim_history():
    global _history
    if len(_history) > MAX_HISTORY_TURNS * 2:
        _history = _history[-(MAX_HISTORY_TURNS * 2):]


def reset_history():
    global _history
    _history = []


# ── Auto-Memory ────────────────────────────────────────────────────────────────

def _auto_memory_check(user_text: str, jarvis_response: str):
    if not should_auto_remember(user_text):
        return
    try:
        extraction = client.messages.create(
            model=HAIKU,
            max_tokens=200,
            system=(
                "Extract facts worth remembering long-term from this exchange. "
                "Return ONLY a JSON array: [{\"fact\": \"...\", \"category\": \"...\"}] "
                "Categories: PROJECTS, PREFS, FACTS, GOALS. "
                "Return [] if nothing is worth saving. "
                "Only save concrete, persistent facts — not transient remarks."
            ),
            messages=[{
                "role": "user",
                "content": f"User: {user_text}\nJarvis: {jarvis_response}"
            }]
        )
        raw   = extraction.content[0].text.strip()
        raw   = raw.replace("```json", "").replace("```", "").strip()
        facts = json.loads(raw)
        for item in facts:
            fact     = item.get("fact", "").strip()
            category = item.get("category", "FACTS").upper()
            if fact:
                save_fact(fact, category, source="auto")
    except Exception:
        pass


# ── Session Close ──────────────────────────────────────────────────────────────

def close_session():
    if not _history:
        return
    lines = [
        f"{'Edward' if m['role'] == 'user' else 'Jarvis'}: {m['content']}"
        for m in _history if isinstance(m.get("content"), str)
    ]
    if not lines:
        return
    try:
        resp = client.messages.create(
            model=HAIKU,
            max_tokens=300,
            system=(
                "Summarize this Jarvis session in 2-4 sentences. "
                "Cover: what was discussed or built, decisions made, current state. "
                "Specific, factual, plain text only."
            ),
            messages=[{"role": "user", "content": f"Transcript:\n{chr(10).join(lines[-20:])}"}]
        )
        _append_to_jarvis_note(resp.content[0].text.strip())
        print("[Jarvis] Session logged.")
    except Exception as e:
        print(f"[Jarvis] Session log failed: {e}")


# ── Core API Call ──────────────────────────────────────────────────────────────

def _call_claude(model: str, messages: list[dict]) -> anthropic.types.Message:
    max_tokens = 400 if model == HAIKU else 16000
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}
        }],
        tools=TOOLS,
        messages=messages,
    )


def _call_claude_followup(model: str, messages: list[dict]) -> anthropic.types.Message:
    """Followup call after tool use — forces text response, no further tool calls."""
    max_tokens = 400 if model == HAIKU else 16000
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"}
        }],
        tools=TOOLS,
        tool_choice={"type": "none"},
        messages=messages,
    )


# ── Streaming API Call ─────────────────────────────────────────────────────────

def _call_claude_streaming(
    model: str,
    messages: list[dict],
    on_sentence,
    max_spoken: int = 2,
) -> tuple[str, bool]:
    """
    Stream a Claude response for general turns.
    Fires on_sentence() at each sentence boundary up to max_spoken times.
    Returns (full_text, had_tool_use).
    had_tool_use=True means caller should fall back to blocking _call_claude().
    """
    max_tokens = 400 if model == HAIKU else 16000
    full_response = ""
    spoken_count  = 0
    had_tool_use  = False
    _SENTENCE_END = re.compile(r'(?<=[.!?])\s+')

    try:
        with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            tools=TOOLS,
            messages=messages,
        ) as stream:
            for event in stream:
                event_type = type(event).__name__
                if event_type == "ContentBlockStart":
                    block = getattr(event, "content_block", None)
                    if block and getattr(block, "type", None) == "tool_use":
                        had_tool_use = True
                        break
                if event_type == "ContentBlockDelta":
                    delta = getattr(event, "delta", None)
                    if delta and getattr(delta, "type", None) == "text_delta":
                        chunk = delta.text
                        accumulated   += chunk
                        full_response += chunk
                        if on_sentence and spoken_count < max_spoken:
                            parts    = _SENTENCE_END.split(accumulated)
                            complete = parts[:-1]
                            leftover = parts[-1]
                            for sentence in complete:
                                sentence = sentence.strip()
                                if sentence and spoken_count < max_spoken:
                                    on_sentence(sentence)
                                    spoken_count += 1
                            accumulated = leftover

            if on_sentence and accumulated.strip() and spoken_count < max_spoken:
                on_sentence(accumulated.strip())

            try:
                final_msg = stream.get_final_message()
                u = final_msg.usage
                from usage_tracker import record_claude_usage
                record_claude_usage(
                    model,
                    u.input_tokens,
                    u.output_tokens,
                    cache_creation_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
                    cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
                )
            except Exception:
                pass

    except Exception as e:
        print(f"[Stream] Error: {e}")
        had_tool_use = True

    return full_response.strip() or "Nothing to report.", had_tool_use


# ── Auto-Capture ───────────────────────────────────────────────────────────────

_CAPTURE_SIGNALS = {
    "i should", "i need to", "i have to", "i'm going to", "i will",
    "i decided", "i want to", "we should", "let's", "let me",
    "i'm planning", "plan to", "going to",
    "applied", "application", "interview", "recruiter", "follow up",
    "reached out", "sent my resume", "offer", "rejected", "deadline",
    "job hunt", "job search",
    "blocked", "blocker", "figured out", "fixed", "broke", "breaking",
    "the issue is", "the problem is", "discovered", "realized",
    "decided to use", "switching to", "moving to", "scrapping",
    "what if", "idea:", "could we", "wouldn't it be", "i wonder",
    "remind me", "don't forget", "make a note",
    "his name is", "her name is", "they said", "he said", "she said",
    "contact", "reach out to",
}

def _has_capture_signal(text: str, response: str) -> bool:
    combined = (text + " " + response).lower()
    return any(signal in combined for signal in _CAPTURE_SIGNALS)


def _auto_capture(user_text: str, jarvis_response: str) -> str | None:
    if not _has_capture_signal(user_text, jarvis_response):
        return None
    combined = f"Edward: {user_text}\nJarvis: {jarvis_response}"
    try:
        resp = client.messages.create(
            model=HAIKU,
            max_tokens=120,
            system=(
                "You decide whether a short exchange contains something worth saving to an inbox. "
                "Worth saving: decisions made, commitments given, job hunt updates, project blockers or breakthroughs, "
                "ideas to explore, people to contact, deadlines, anything Edward might want to recall later. "
                "NOT worth saving: casual chat, questions already answered completely, things already in memory. "
                "If worth saving: respond with exactly two lines:\n"
                "TITLE: <short note title, max 6 words>\n"
                "CONTENT: <one sentence summary of what to save>\n"
                "If not worth saving: respond with exactly: SKIP"
            ),
            messages=[{"role": "user", "content": combined}],
        )
        result = resp.content[0].text.strip()
        if result == "SKIP" or not result:
            return None
        lines   = result.splitlines()
        title   = next((l.split(":", 1)[-1].strip() for l in lines if l.startswith("TITLE:")),   None)
        content = next((l.split(":", 1)[-1].strip() for l in lines if l.startswith("CONTENT:")), None)
        if title and content:
            add_to_inbox(content, title)
            return title
    except Exception:
        pass
    return None


def _fire_auto_capture(user_text: str, jarvis_response: str, on_sentence=None) -> None:
    import threading
    def _run():
        title = _auto_capture(user_text, jarvis_response)
        if title:
            notice = f"Filed to inbox: {title}."
            print(f"[Auto-capture] {notice}")
            if on_sentence:
                import time; time.sleep(1.2)
                on_sentence(notice)
            try:
                from server import emit_jarvis_msg
                emit_jarvis_msg(notice)
            except Exception:
                pass
    threading.Thread(target=_run, daemon=True).start()


# ── Main Entry Point ───────────────────────────────────────────────────────────

def think(text: str, on_sentence=None) -> str:
    global _history

    if _is_ambiguous(text) and _history:
        return "What specifically did you want me to do?"

    # ── Reminder fast-path — intercept before Claude to guarantee tool fires ──
    _reminder_triggers = ["remind me", "set a timer", "set timer", "in _ minutes", "don't let me forget", "dont let me forget"]
    text_lower = text.lower()
    if any(t in text_lower for t in ["remind me", "set a timer", "set timer", "don't let me forget", "dont let me forget"]):
        import re
        nums = re.findall(r'(\d+)\s*(hour|minute|min|second|sec|hr)s?', text_lower)
        if nums:
            amount, unit = nums[0]
            amount = int(amount)
            if unit in ("hour", "hr"):
                minutes = amount * 60
            elif unit in ("second", "sec"):
                minutes = max(1, amount // 60)
            else:
                minutes = amount
            # Extract message — everything after "to" or the whole text
            msg_match = re.search(r'\bremind me (?:to )?(.+?)(?:\s+in \d)', text_lower)
            message = msg_match.group(1).strip() if msg_match else text
            result = _set_reminder_and_emit(message, minutes)
            _history.append({"role": "user",      "content": text})
            _history.append({"role": "assistant",  "content": result})
            return result

    # ── Multi-agent routing ────────────────────────────────────────────────
    intent = classify_intent(text, _history)

    # ── Claude Code fast-path — heavy coding tasks bypass Projects agent ──
    if intent == "projects" and detect_heavy_coding_task(text):
        # Build a precise prompt and hand it off as a tool call
        cc_prompt = (
            f"You are working inside Edward Haddad's Jarvis project at ~/Desktop/Projects/Jarvis.\n"
            f"Task: {text}\n\n"
            f"Complete the task. Read any relevant files first, make the changes, run tests if applicable. "
            f"Be specific about every file modified and every change made."
        )
        result = run_claude_code(cc_prompt)
        response_text = (
            f"Claude Code completed the task. Here's the output:\n\n{result}"
        )
        _history.append({"role": "user",      "content": text})
        _history.append({"role": "assistant",  "content": response_text})
        _trim_history()
        _auto_memory_check(text, response_text)
        return response_text

    if intent != "general":
        scoped = _history[-(6):]
        agent_messages = scoped + [{"role": "user", "content": text}]

        if intent == "career":
            response_text = run_career_agent(agent_messages)
        elif intent == "projects":
            response_text = run_projects_agent(agent_messages)
        elif intent == "iris":
            response_text = run_iris_agent(agent_messages)
        else:
            response_text = None

        if response_text:
            _history.append({"role": "user",      "content": text})
            _history.append({"role": "assistant",  "content": response_text})
            _trim_history()
            _auto_memory_check(text, response_text)
            return response_text

    # ── General: main Jarvis prompt ────────────────────────────────────────

    model           = _route_model(text)
    project_context = get_context_for(text)

    if project_context:
        messages = _history + [{
            "role": "user",
            "content": f"[CONTEXT]\n{project_context}\n[/CONTEXT]\n\n{text}"
        }]
    else:
        messages = _history + [{"role": "user", "content": text}]

    _history.append({"role": "user", "content": text})
    _trim_history()

    # ── Streaming path ─────────────────────────────────────────────────────
    if on_sentence is not None:
        streamed_text, had_tool_use = _call_claude_streaming(
            model, messages, on_sentence, max_spoken=2
        )
        if not had_tool_use:
            _history.append({"role": "assistant", "content": streamed_text})
            _auto_memory_check(text, streamed_text)
            _fire_auto_capture(text, streamed_text, on_sentence)
            return streamed_text
        # Tool use mid-stream — fall through to blocking call

    # ── Blocking path ──────────────────────────────────────────────────────
    response        = _call_claude(model, messages)
    tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

    if tool_use_blocks:
        tool_results = []
        for block in tool_use_blocks:
            result = _execute_tool(block.name, block.input)
            tool_results.append({
                "type":        "tool_result",
                "tool_use_id": block.id,
                "content":     result,
            })

        followup_messages = messages + [
            {"role": "assistant", "content": response.content},
            {"role": "user",      "content": tool_results},
        ]

        followup   = _call_claude_followup(model, followup_messages)
        final_text = _extract_text(followup)

        _history.append({"role": "assistant", "content": final_text})
        _auto_memory_check(text, final_text)
        _fire_auto_capture(text, final_text, on_sentence)
        return final_text

    final_text = _extract_text(response)
    _history.append({"role": "assistant", "content": final_text})
    _auto_memory_check(text, final_text)
    _fire_auto_capture(text, final_text, on_sentence)
    return final_text


def _extract_text(response: anthropic.types.Message) -> str:
    for block in response.content:
        if block.type == "text":
            return block.text.strip()
    # If Claude returned another tool_use block, extract its text if any
    if not response.content:
        return "I ran into an issue getting that information. Try asking again."
    return "Nothing to report."


if __name__ == "__main__":
    print(think("what's the current state of the Iris project"))
    print("---")
    print(think("I've been working for 4 hours straight, should I take a break"))
    print("---")
    print(think("what do you think about the multi-agent architecture we've been planning"))
