# memory.py
# Persistent memory for Jarvis.
# Stores facts and personality traits across sessions.
#
# Memory file: ~/Desktop/OBS/Edward/Projects/Jarvis_Memory.md
#
# Categories:
#   PROJECTS    — current state, decisions, blockers per project
#   PREFS       — Edward's preferences, working style
#   FACTS       — personal facts, context
#   GOALS       — active priorities and targets
#   CORRECTIONS — explicit corrections
#   PERSONA     — Jarvis personality trait overrides

import os
import json
from datetime import datetime
from pathlib import Path

VAULT_ROOT  = Path.home() / "Desktop" / "OBS" / "Edward"
MEMORY_FILE = VAULT_ROOT / "Projects" / "Jarvis" / "Jarvis_Memory.md"

VALID_CATEGORIES = {"PROJECTS", "PREFS", "FACTS", "GOALS", "CORRECTIONS", "PERSONA"}

# ── Personality trait definitions ──────────────────────────────────────────────

PERSONA_TRAITS = {
    "sarcasm":    {"low", "medium", "high"},
    "length":     {"brief", "normal", "detailed"},
    "formality":  {"casual", "professional"},
    "pushback":   {"low", "medium", "high"},
}

PERSONA_DEFAULTS = {
    "sarcasm":   "medium",
    "length":    "normal",
    "formality": "casual",
    "pushback":  "medium",
}


# ── Init ───────────────────────────────────────────────────────────────────────

def _ensure_memory_file():
    if MEMORY_FILE.exists():
        return
    content = (
        "# Jarvis Persistent Memory\n"
        "Auto-maintained by Jarvis. Do not edit structure — add facts freely.\n\n"
        "## PROJECTS\n\n"
        "## PREFS\n\n"
        "## FACTS\n\n"
        "## GOALS\n\n"
        "## CORRECTIONS\n\n"
        "## PERSONA\n"
    )
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        print(f"[memory] Could not create memory file: {e}")


# ── Read ───────────────────────────────────────────────────────────────────────

def read_memory() -> str:
    _ensure_memory_file()
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return content if content else "Memory file is empty."
    except Exception as e:
        return f"Could not read memory: {e}"


def read_category(category: str) -> str:
    _ensure_memory_file()
    category = category.upper().strip()
    lines    = read_memory().split("\n")
    in_sec   = False
    result   = []
    for line in lines:
        if line.strip() == f"## {category}":
            in_sec = True
            continue
        if in_sec:
            if line.startswith("## "):
                break
            result.append(line)
    section = "\n".join(result).strip()
    return section if section else f"Nothing stored under {category} yet."


def read_persona() -> dict:
    """
    Return current personality traits as a dict.
    Merges stored PERSONA entries with defaults.
    """
    _ensure_memory_file()
    traits = dict(PERSONA_DEFAULTS)
    section = read_category("PERSONA")
    if section.startswith("Nothing stored"):
        return traits
    for line in section.split("\n"):
        line = line.strip().lstrip("·📌").strip()
        if ":" in line:
            # Strip timestamp prefix like [2026-05-15]
            if line.startswith("["):
                line = line.split("]", 1)[-1].strip()
            parts = line.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip().lower()
                val = parts[1].strip().lower()
                if key in PERSONA_TRAITS and val in PERSONA_TRAITS[key]:
                    traits[key] = val
    return traits


# ── Write ──────────────────────────────────────────────────────────────────────

def save_fact(fact: str, category: str = "FACTS", source: str = "auto") -> str:
    _ensure_memory_file()
    category = category.upper().strip()
    if category not in VALID_CATEGORIES:
        category = "FACTS"

    ts    = datetime.now().strftime("%Y-%m-%d")
    tag   = "📌" if source == "explicit" else "·"
    entry = f"{tag} [{ts}] {fact.strip()}\n"

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        heading = f"## {category}"
        if heading not in content:
            content += f"\n{heading}\n"

        insert_at = content.find(heading) + len(heading)
        next_nl   = content.find("\n", insert_at)
        if next_nl == -1:
            content += f"\n{entry}"
        else:
            content = content[:next_nl + 1] + entry + content[next_nl + 1:]

        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            f.write(content)

        return f"Remembered: {fact.strip()}"
    except Exception as e:
        return f"Could not save memory: {e}"


def set_persona_trait(trait: str, value: str) -> str:
    """
    Update a personality trait in the PERSONA section.
    Replaces any existing entry for that trait.
    Returns a confirmation string for Jarvis to speak.
    """
    _ensure_memory_file()
    trait = trait.lower().strip()
    value = value.lower().strip()

    if trait not in PERSONA_TRAITS:
        return f"I don't recognise '{trait}' as a personality trait."
    if value not in PERSONA_TRAITS[trait]:
        valid = ", ".join(PERSONA_TRAITS[trait])
        return f"'{value}' isn't a valid setting for {trait}. Options are: {valid}."

    ts    = datetime.now().strftime("%Y-%m-%d")
    entry = f"· [{ts}] {trait}: {value}\n"

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        heading = "## PERSONA"
        if heading not in content:
            content += f"\n{heading}\n"

        # Remove any existing line for this trait under PERSONA
        lines      = content.split("\n")
        in_persona = False
        new_lines  = []
        for line in lines:
            if line.strip() == heading:
                in_persona = True
                new_lines.append(line)
                continue
            if in_persona and line.startswith("## "):
                in_persona = False
            if in_persona and f"{trait}:" in line.lower():
                continue  # drop old entry
            new_lines.append(line)
        content = "\n".join(new_lines)

        # Insert new entry
        insert_at = content.find(heading) + len(heading)
        next_nl   = content.find("\n", insert_at)
        if next_nl == -1:
            content += f"\n{entry}"
        else:
            content = content[:next_nl + 1] + entry + content[next_nl + 1:]

        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            f.write(content)

        return f"Noted. {trait.capitalize()} set to {value}."
    except Exception as e:
        return f"Could not update persona: {e}"


def correct_memory(old_fact: str, new_fact: str) -> str:
    _ensure_memory_file()
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        if old_fact in content:
            content    = content.replace(old_fact, new_fact)
            ts         = datetime.now().strftime("%Y-%m-%d")
            correction = f"· [{ts}] Corrected: '{old_fact}' → '{new_fact}'\n"
            heading    = "## CORRECTIONS"
            insert_at  = content.find(heading) + len(heading)
            next_nl    = content.find("\n", insert_at)
            content    = content[:next_nl + 1] + correction + content[next_nl + 1:]
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                f.write(content)
            return "Corrected."
        else:
            save_fact(new_fact, "CORRECTIONS", source="explicit")
            return "Original not found — saved as new correction."
    except Exception as e:
        return f"Could not correct memory: {e}"


# ── Auto-memory signal detection ───────────────────────────────────────────────

_AUTO_SIGNALS = [
    "i prefer", "i like", "i don't like", "i hate", "i always",
    "i never", "i'm working on", "i decided", "we decided",
    "going forward", "from now on", "my goal", "i want to",
    "i need to", "i'm trying to", "my target", "i use",
    "i switched to", "i moved to", "i'm using",
]


def should_auto_remember(user_text: str) -> bool:
    lowered = user_text.lower()
    return any(signal in lowered for signal in _AUTO_SIGNALS)


# ── Persona prompt injection ───────────────────────────────────────────────────

def build_persona_instructions() -> str:
    """
    Generate system prompt instructions from stored persona traits.
    Called at import time — changes take effect next session,
    or immediately if think.py rebuilds its prompt mid-session.
    """
    traits = read_persona()

    sarcasm_map = {
        "low":    "Use minimal sarcasm. Keep tone warm and straightforward.",
        "medium": "Use dry, understated sarcasm when the situation earns it. Never excessive.",
        "high":   "Lean into the sarcasm. Sharp wit, dry delivery — Jarvis at his most sardonic. Still never mean.",
    }
    length_map = {
        "brief":    "Keep all responses as short as possible. One sentence where one sentence will do.",
        "normal":   "Match response length to the question. Concise by default.",
        "detailed": "Give thorough responses. Don't truncate explanations or skip context.",
    }
    formality_map = {
        "casual":       "Casual register. Talk like a sharp colleague, not a professional report.",
        "professional": "Professional register. Crisp and precise, minimal casual language.",
    }
    pushback_map = {
        "low":    "Execute requests without challenging them. Voice concerns only if something is clearly wrong.",
        "medium": "Push back when something doesn't make sense. Voice a better option if you see one.",
        "high":   "Challenge assumptions actively. Don't just execute — interrogate the approach first.",
    }

    lines = [
        sarcasm_map[traits["sarcasm"]],
        length_map[traits["length"]],
        formality_map[traits["formality"]],
        pushback_map[traits["pushback"]],
    ]

    non_default = {k: v for k, v in traits.items() if v != PERSONA_DEFAULTS[k]}
    if non_default:
        overrides = ", ".join(f"{k}: {v}" for k, v in non_default.items())
        lines.append(f"Active persona overrides: {overrides}.")

    return "\n".join(lines)


if __name__ == "__main__":
    print(set_persona_trait("sarcasm", "high"))
    print(set_persona_trait("length", "brief"))
    print(read_category("PERSONA"))
    print("---")
    print(build_persona_instructions())
