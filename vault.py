# vault.py
# Obsidian vault integration for Jarvis.
# Handles all read/write operations on ~/Desktop/OBS/Edward/
#
# Vault structure:
#   Inbox/                  — timestamped idea notes (one file per entry)
#   Projects/               — Iris.md, Jarvis.md, ChipIn.md, Billed.md, Gesture Control.md
#   Career/                 — Job Applications.md, OPT & Visa.md, Resume & Portfolio.md
#   Knowledge/              — AI & LLMs.md, Computer Vision.md, Embedded Systems.md, Python.md
#   Life/                   — Goals 2026.md, Weekly Review.md

import os
from datetime import datetime
from pathlib import Path

VAULT_ROOT = Path.home() / "Desktop" / "OBS" / "Edward"

# Map of keywords to (folder, filename) for fuzzy note matching
NOTE_MAP = {
    "jarvis":           ("Projects",  "Jarvis.md"),
    "iris":             ("Projects",  "Iris.md"),
    "chipin":           ("Projects",  "ChipIn.md"),
    "chip in":          ("Projects",  "ChipIn.md"),
    "billed":           ("Projects",  "Billed.md"),
    "gesture":          ("Projects",  "Gesture Control.md"),
    "gesture control":  ("Projects",  "Gesture Control.md"),
    "job":              ("Career",    "Job Appllications.md"),
    "applications":     ("Career",    "Job Appllications.md"),
    "opt":              ("Career",    "OPT & Visa.md"),
    "visa":             ("Career",    "OPT & Visa.md"),
    "resume":           ("Career",    "Resume & Portfolio.md"),
    "portfolio":        ("Career",    "Resume & Portfolio.md"),
    "ai":               ("Knowledge", "AI & LLMs.md"),
    "llm":              ("Knowledge", "AI & LLMs.md"),
    "computer vision":  ("Knowledge", "Computer Vision.md"),
    "vision":           ("Knowledge", "Computer Vision.md"),
    "embedded":         ("Knowledge", "Embedded Systems.md"),
    "python":           ("Knowledge", "Python.md"),
    "goals":            ("Life",      "Goals 2026.md"),
    "weekly":           ("Life",      "Weekly Review.md"),
    "review":           ("Life",      "Weekly Review.md"),
}

# Folder display names for listing
FOLDER_MAP = {
    "inbox":     "Inbox",
    "projects":  "Projects",
    "career":    "Career",
    "knowledge": "Knowledge",
    "life":      "Life",
}


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _resolve_note(query: str) -> tuple[str, str] | None:
    """Fuzzy match a spoken note name to a (folder, filename) pair."""
    lowered = query.lower()
    for keyword, location in NOTE_MAP.items():
        if keyword in lowered:
            return location
    return None


# ── Inbox ──────────────────────────────────────────────────────────────────────

def add_to_inbox(content: str, title: str) -> str:
    """
    Create a new timestamped note in Inbox/.
    Title is LLM-generated and passed in from think.py.
    Returns the path of the created file.
    """
    timestamp = _timestamp()
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_prefix} {safe_title}.md"
    filepath = VAULT_ROOT / "Inbox" / filename

    note_body = f"# {title}\n*{timestamp}*\n\n{content}\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(note_body)

    return str(filepath)


# ── Read ───────────────────────────────────────────────────────────────────────

def read_note(query: str) -> str:
    """
    Read and return the contents of a note matched by query.
    Returns an error string if not found.
    """
    location = _resolve_note(query)
    if not location:
        return f"I couldn't find a note matching '{query}'."

    folder, filename = location
    filepath = VAULT_ROOT / folder / filename

    if not filepath.exists():
        return f"The note {filename} doesn't exist yet."

    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


# ── Append ─────────────────────────────────────────────────────────────────────

def append_to_note(query: str, content: str) -> str:
    """
    Append a timestamped entry to an existing note matched by query.
    Returns a confirmation string.
    """
    location = _resolve_note(query)
    if not location:
        return f"I couldn't find a note matching '{query}'."

    folder, filename = location
    filepath = VAULT_ROOT / folder / filename

    timestamp = _timestamp()
    entry = f"\n---\n*{timestamp}*\n{content}\n"

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(entry)

    return f"Added to {filename}."


# ── List ───────────────────────────────────────────────────────────────────────

def list_notes(query: str) -> str:
    """
    List all note filenames in a folder matched by query.
    Returns a readable string for Jarvis to speak aloud.
    """
    lowered = query.lower()
    folder_name = None
    for keyword, folder in FOLDER_MAP.items():
        if keyword in lowered:
            folder_name = folder
            break

    if not folder_name:
        return f"I couldn't find a folder matching '{query}'."

    folder_path = VAULT_ROOT / folder_name
    files = [f.stem for f in folder_path.glob("*.md")]

    if not files:
        return f"No notes found in {folder_name}."

    return f"Notes in {folder_name}: " + ", ".join(files) + "."


# ── Dispatch ───────────────────────────────────────────────────────────────────

def handle_vault_command(text: str, generated_title: str = "") -> str | None:
    """
    Check if text is a vault command. If so, execute and return a response string.
    Returns None if text is not a vault command — caller should pass to LLM.
    """
    lowered = text.lower()

    # Add to inbox
    if "add to inbox" in lowered:
        content = text.split(":", 1)[-1].strip() if ":" in text else text
        if not generated_title:
            generated_title = "Idea"
        path = add_to_inbox(content, generated_title)
        return f"Added to inbox: {generated_title}."

    # List notes in folder
    if "what notes" in lowered or "list" in lowered:
        return list_notes(lowered)

    # Read a note
    if "read" in lowered or "what's in" in lowered or "whats in" in lowered or "open" in lowered:
        content = read_note(lowered)
        return content

    # Append to a note
    if "add to my" in lowered or "update my" in lowered:
        content = text.split(":", 1)[-1].strip() if ":" in text else text
        return append_to_note(lowered, content)

    return None  # not a vault command
