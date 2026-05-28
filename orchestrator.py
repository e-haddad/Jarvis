# orchestrator.py
# Intent classifier for Jarvis multi-agent routing.
#
# Classifies user input into one of five intents:
#   career   → Career agent (job hunt, resume, outreach)
#   projects → Projects agent (Jarvis, ChipIn, Billed, general code)
#   iris     → Iris agent (smart home, gesture, Pi, Tuya)
#   general  → Main Jarvis prompt (everything else: weather, calendar, memory, chat)
#
# Classification uses keyword signals first (fast, free),
# falling back to a Haiku API call only when ambiguous.
# Routing is invisible to Edward — no narration.

import os
import re
from pathlib import Path
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
HAIKU  = "claude-haiku-4-5-20251001"


# ── Keyword Signal Maps ────────────────────────────────────────────────────────
# Fast path — no API call needed if clear signal found

CAREER_SIGNALS = {
    "resume", "cover letter", "application", "apply", "interview",
    "wind river", "valeo", "schaeffler", "switchbox", "cybernet",
    "tttech", "williams international", "job", "hiring", "recruiter",
    "linkedin", "outreach", "offer", "salary", "opt", "visa",
    "job hunt", "job search", "embedded role", "career",
}

PROJECTS_SIGNALS = {
    "chipin", "chip in", "poker", "billed", "bill split",
    "gesture control", "jarvis phase", "think.py", "speak.py",
    "listen.py", "main.py", "vault.py", "pipeline", "phase 4",
    "phase 5", "kokoro", "wake word", "whisper", "pyqt", "hud",
    "mobile app", "firebase", "project status", "what are we building",
    # Code writing/editing signals
    "write a script", "write a python", "python script", "write code",
    "write me a script", "write me a python", "fix the code",
    "debug", "refactor", "edit the file", "modify the file",
    "read the file", "show me the code", "look at the code",
    "run the script", "test the code", "check the file",
}

IRIS_SIGNALS = {
    "iris", "gesture", "raspberry", "raspberry pi", "flask",
    "tuya", "smart home", "smart plug", "mediapipe", "picamera",
    "gesture engine", "hand tracking", "opencv", "arducam",
    "light 1", "light 2", "toggle light", "dashboard", "fist",
    "pinch", "both hands", "pi 5", "pi5", "ssh", "iris.local",
}

GENERAL_SIGNALS = {
    "weather", "calendar", "schedule", "time", "what time",
    "remind", "remember", "inbox", "note", "search",
    "what do you think", "how are you", "hey", "hello",
    "what's up", "good morning", "good evening", "good night",
    # Activities and lifestyle — should never route to a specialist agent
    "play", "playing", "gym", "workout", "exercise", "run", "running",
    "sport", "sports", "pickleball", "basketball", "tennis", "golf",
    "food", "eat", "restaurant", "coffee", "drink", "lunch", "dinner",
    "movie", "music", "read", "book", "weekend", "today", "tonight",
    "tomorrow", "drive", "commute", "traffic", "sleep", "tired",
    "how do i", "what is", "who is", "when is", "where is", "why is",
    "tell me", "explain", "help me understand", "what are",
}


def _keyword_classify(text: str) -> str | None:
    """
    Fast keyword classification. Returns agent name or None if ambiguous.
    Checks more specific signals first to avoid false positives.
    """
    lowered = text.lower()

    # Iris is most specific — check first
    if any(sig in lowered for sig in IRIS_SIGNALS):
        return "iris"

    # Career
    if any(sig in lowered for sig in CAREER_SIGNALS):
        return "career"

    # Projects (after Iris since Iris is also a project)
    if any(sig in lowered for sig in PROJECTS_SIGNALS):
        return "projects"

    # General — explicit signals
    if any(sig in lowered for sig in GENERAL_SIGNALS):
        return "general"

    return None  # ambiguous — fall through to LLM


def _llm_classify(text: str, history_snippet: str = "") -> str:
    """
    Haiku-based intent classification for ambiguous inputs.
    Returns one of: career, projects, iris, general.
    """
    context = f"Recent context: {history_snippet}\n\n" if history_snippet else ""
    try:
        response = client.messages.create(
            model=HAIKU,
            max_tokens=10,
            system=(
                "Classify the user's intent into exactly one category. "
                "Reply with only the category word, nothing else.\n\n"
                "Categories:\n"
                "- career: job applications, resume, cover letter, outreach, interviews, "
                "specific company names (Wind River, Valeo, Schaeffler etc), OPT/visa\n"
                "- projects: Jarvis development, ChipIn app, Billed app, code files, "
                "architecture decisions, debugging specific project code\n"
                "- iris: smart home, gesture control, Raspberry Pi, Tuya smart plugs, "
                "MediaPipe, Flask dashboard, hand tracking\n"
                "- general: EVERYTHING ELSE — weather, sports, food, activities, "
                "lifestyle questions, factual questions, chat, calendar, search, "
                "anything not directly about Edward's specific work projects\n\n"
                "When in doubt, use 'general'. Only use specialist categories when "
                "the input is clearly and specifically about that domain."
            ),
            messages=[{
                "role": "user",
                "content": f"{context}User said: {text}"
            }]
        )
        result = response.content[0].text.strip().lower()
        if result in ("career", "projects", "iris", "general"):
            return result
        return "general"
    except Exception:
        return "general"


def classify_intent(text: str, recent_history: list[dict] | None = None) -> str:
    """
    Classify user intent. Returns: career | projects | iris | general.

    Fast path: keyword matching (no API cost).
    Slow path: Haiku call only if ambiguous (rare).
    """
    # Fast path
    keyword_result = _keyword_classify(text)
    if keyword_result is not None:
        return keyword_result

    # Slow path — build a history snippet for context
    snippet = ""
    if recent_history:
        lines = []
        for msg in recent_history[-4:]:
            if isinstance(msg.get("content"), str):
                role = "Edward" if msg["role"] == "user" else "Jarvis"
                lines.append(f"{role}: {msg['content'][:80]}")
        snippet = " | ".join(lines)

    return _llm_classify(text, snippet)


if __name__ == "__main__":
    tests = [
        ("Help me tailor my resume for Wind River", "career"),
        ("What's the current state of Iris?", "iris"),
        ("What should I focus on for ChipIn next?", "projects"),
        ("What's the weather in Detroit?", "general"),
        ("The fist gesture is still broken", "iris"),
        ("I need to write a cover letter", "career"),
        ("What do you think?", "general"),
        ("Help me debug the gesture engine", "iris"),
        ("What's my next calendar event?", "general"),
        ("How's the Billed app coming along?", "projects"),
    ]

    print("Intent classification test:\n")
    correct = 0
    for text, expected in tests:
        result = classify_intent(text)
        status = "✓" if result == expected else "✗"
        if result == expected:
            correct += 1
        print(f"{status} '{text[:50]}' → {result} (expected {expected})")

    print(f"\n{correct}/{len(tests)} correct")
