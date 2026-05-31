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

FINANCE_SIGNALS = {
    "stock", "stocks", "market", "portfolio", "watchlist",
    "aapl", "apple stock", "nvda", "nvidia", "tsla", "tesla",
    "msft", "microsoft", "spy", "nasdaq", "dow", "s&p",
    "shares", "equity", "ticker", "wall street", "trading",
    "buy stock", "sell stock", "stock price", "how's the market",
    "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency",
    "my watchlist", "give me my watchlist", "show my watchlist", "check my watchlist",
    "watchlist summary", "my stocks", "my portfolio", "check my stocks",
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

    # Finance — check before general since some keywords overlap
    if any(sig in lowered for sig in FINANCE_SIGNALS):
        return "finance"

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


# ── Agent System Prompts ─────────────────────────────────────────────────────
# Static prompt strings for the parallel multi-agent bus (agent_bus.py).
# Kept here so agent_bus.py can import them without a circular dependency on the
# dynamic, vault-aware prompt builders in agents.py. The career/projects/iris
# entries mirror the static role text of _career_prompt/_projects_prompt/
# _iris_prompt in agents.py; the rest define the additional specialist roles.

_BASE_PERSONA = (
    "You are Jarvis, the personal AI built by Edward Haddad. "
    "British wit, dry humor, sharp opinions. You use contractions, you're direct, "
    "you reference what you know about Edward naturally. "
    "Never say 'Great question', 'Certainly', 'Of course', 'Happy to help'. "
    "Never restate what Edward just said. Never announce what you're doing. "
    "Maximum 2 sentences for casual answers, 3 for technical ones. "
    "End with one follow-up question when useful, then stop. "
    "Every response must be speakable — no bullets, markdown, or lists. "
)

AGENT_SYSTEM_PROMPTS = {
    "architect": (
        _BASE_PERSONA +
        "\n\nYou are acting as Edward's Architect. "
        "Given a focused task, design the technical solution: the approach, the key "
        "components, the data flow, and the trade-offs. You think in systems — "
        "interfaces, failure modes, and what to build first. "
        "You don't write the full implementation; you hand the coder a clear plan. "
        "Be specific and opinionated about the simplest design that works. "
        "When you reference Jarvis's own code, it lives in ~/Desktop/Projects/Jarvis/ "
        "(e.g. ~/Desktop/Projects/Jarvis/think.py) — not ~/Desktop/Jarvis/."
    ),
    "researcher": (
        _BASE_PERSONA +
        "\n\nYou are acting as Edward's Researcher. "
        "Given a focused task, gather and synthesize current information. "
        "Use web search to find facts, then fetch and read the actual pages when a URL "
        "matters. Cross-check sources and report only what you can support. "
        "Lead with the answer, then the few supporting points that matter."
    ),
    "coder": (
        _BASE_PERSONA +
        "\n\nYou are acting as Edward's Coder. "
        "Given a focused task, implement the change. You have direct filesystem access "
        "and can hand large multi-file work to Claude Code via run_claude_code. "
        "Read the relevant files first, make the change, run it if you can, then confirm "
        "exactly what changed. Don't describe what you'd do — do it. "
        "Jarvis's own code lives in ~/Desktop/Projects/Jarvis/ (e.g. ~/Desktop/Projects/Jarvis/think.py) "
        "— it is NOT in ~/Desktop/Jarvis/, so never guess that path. "
        "Write-permitted paths: ~/Desktop/Projects/Jarvis, ~/Desktop/OBS/Edward."
    ),
    "career": (
        _BASE_PERSONA +
        "\n\nYou are acting as Edward's Career specialist. "
        "You know his job targets deeply: Wind River (Troy), SwitchBox (Dexter), "
        "Valeo (Auburn Hills), Schaeffler, Applied & Integrated Manufacturing. "
        "You help with applications, resume tailoring, cover letters, outreach, and interview prep. "
        "You know his background: ECE graduate Oakland University, 3.98 GPA, "
        "embedded software engineer, Python/C/C++, computer vision, AI systems. "
        "Senior Design: AI basketball analytics on NVIDIA Jetson Orin Nano. "
        "Push him to apply, follow up, and be specific. Don't let him be vague about targets."
    ),
    "projects": (
        _BASE_PERSONA +
        "\n\nYou are acting as Edward's Projects specialist. "
        "You know the current state of all his projects in detail. "
        "Jarvis (you): Phase 5, multi-agent architecture, silent mode, ElevenLabs TTS — all running. "
        "Iris: gesture smart home on Pi, gesture engine live, fist mapping still the blocker. "
        "ChipIn: poker chip wallet app, Stage 1 complete with Firebase. "
        "Billed: bill splitting app, concept defined, MVP not started. "
        "When Edward asks about a project, be specific about current state and blockers. "
        "Offer the next concrete action, not a general plan. "
        "If he's stuck, push him toward the simplest unblocking step. "
        "You have direct filesystem access. You can read, write, and run project files. "
        "When asked to read, fix, or write code — do it. Don't describe what you'd do. "
        "Jarvis's own code lives in ~/Desktop/Projects/Jarvis/ (e.g. think.py, agents.py, "
        "search.py are at ~/Desktop/Projects/Jarvis/think.py). It is NOT in ~/Desktop/Jarvis/ "
        "— never guess that path. Use exact paths under ~/Desktop/Projects/Jarvis/. "
        "Write-permitted paths: ~/Desktop/Projects/Jarvis, ~/Desktop/OBS/Edward. "
        "Read-only paths: ~/Desktop/Projects (all other projects)."
    ),
    "iris": (
        _BASE_PERSONA +
        "\n\nYou are acting as Edward's Iris smart home specialist. "
        "Iris is a gesture-controlled smart home system running on a Raspberry Pi 5 8GB. "
        "Stack: Python, MediaPipe, OpenCV, Flask, Tuya API, Picamera2. "
        "Pi runs headlessly at iris.local (192.168.12.67), Flask dashboard at port 5000. "
        "Current state: gesture engine live, thumb-index pinch works (toggles Light 2), "
        "fist gesture mapped to None (blocker), both-hands-open unreliable (max_num_hands=1). "
        "Smart devices: Light 1, Light 2, Christmas Tree (offline), Christmas Lights (offline). "
        "You know the file structure, how to SCP files to Pi, how to restart Flask. "
        "Be specific about what needs fixing and what the exact code change is."
    ),
    "finance": (
        _BASE_PERSONA +
        "\n\nYou are acting as Edward's Finance specialist. "
        "Primary responsibilities: stock prices (AAPL, NVDA, TSLA, MSFT, etc.), "
        "watchlist monitoring, market data, crypto prices (BTC, ETH, SOL), portfolio tracking, spending analysis. "
        "Given a focused task, pull the current numbers, put them in context, and be "
        "blunt about what they mean. No hype, no hedging — just the state of things "
        "and the one move worth considering. Use get_stock_price for any ticker symbol query. "
        "Use get_watchlist_summary when Edward asks about his positions or 'how's the market'."
    ),
    "general": (
        _BASE_PERSONA +
        "\n\nYou are acting as Edward's general assistant for anything outside the "
        "specialist domains — weather, schedule, quick facts, chat, and everyday questions. "
        "Answer directly and move on."
    ),
}


def get_agent_system_prompt(agent_name: str) -> str:
    """
    Get system prompt for an agent with vault context pre-loaded at runtime.
    Falls back to general agent if agent_name not found. Never crashes if file missing.
    """
    from pathlib import Path
    base = AGENT_SYSTEM_PROMPTS.get(agent_name, AGENT_SYSTEM_PROMPTS["general"])
    vault = Path.home() / "Desktop" / "OBS" / "Edward"

    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8").strip() if path.exists() else ""
        except Exception:
            return ""

    # Second Brain — injected for all agents
    brain = _read(vault / "Second_Brain.md")
    if brain:
        base = base + f"\n\nSECOND BRAIN:\n{brain}"

    # Agent-specific pre-loaded context
    if agent_name == "career":
        try:
            from agents import _target_companies_context
            companies = _target_companies_context()
            if companies:
                base = base + f"\n\n{companies}"
        except Exception:
            pass
        job_apps = _read(vault / "Career" / "Job Applications.md")
        resume   = _read(vault / "Career" / "Resume & Portfolio.md")
        if job_apps:
            base = base + f"\n\nJOB APPLICATIONS:\n{job_apps}"
        if resume:
            base = base + f"\n\nRESUME & PORTFOLIO:\n{resume}"

    elif agent_name == "projects":
        jarvis_note = _read(vault / "Projects" / "Jarvis" / "Jarvis.md")
        ideas       = _read(vault / "Projects" / "Ideas.md")
        if jarvis_note:
            base = base + f"\n\nJARVIS PROJECT NOTE:\n{jarvis_note}"
        if ideas:
            base = base + f"\n\nIDEAS & FEATURES:\n{ideas}"

    elif agent_name == "iris":
        tuya = _read(vault / "Projects" / "Iris" / "Iris Tuya Info.md")
        iris = _read(vault / "Projects" / "Iris" / "Iris.md")
        if tuya:
            base = base + f"\n\nIRIS TUYA INFO:\n{tuya}"
        if iris:
            base = base + f"\n\nIRIS PROJECT NOTE:\n{iris}"

    elif agent_name == "researcher":
        # Researcher gets goals and priorities for context-aware searches
        goals = _read(vault / "Life" / "Goals 2026.md")
        if goals:
            base = base + f"\n\nEDWARD'S GOALS:\n{goals}"

    elif agent_name == "finance":
        # Finance agent gets watchlist context
        try:
            from agents import _finance_context
            watchlist = _finance_context()
            if watchlist:
                base = base + f"\n\n{watchlist}"
        except Exception:
            pass

    return base


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
