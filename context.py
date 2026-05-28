# context.py
# Selective project context loading for Jarvis.
# Detects which project(s) the user is talking about and loads
# the relevant vault notes into the conversation context.
#
# Context is loaded per-turn — if Edward switches topics mid-session,
# the right notes are surfaced automatically.
#
# Notes are injected as a supplementary user message before the LLM call
# so they don't bloat the cached system prompt.

from pathlib import Path

VAULT_ROOT = Path.home() / "Desktop" / "OBS" / "Edward"

# ── Project signal maps ────────────────────────────────────────────────────────
# Each entry: (set of trigger keywords, list of vault file paths to load)

PROJECT_CONTEXTS = [
    (
        # Iris — smart home, gesture control, Pi
        {
            "iris", "gesture", "raspberry", "flask", "tuya", "smart home",
            "smart plug", "mediapipe", "picamera", "pi 5", "pi5",
            "gesture engine", "hand tracking", "opencv", "arducam",
            "light 1", "light 2", "toggle light", "dashboard"
        },
        [
            VAULT_ROOT / "Projects" / "Iris" / "Iris.md",
            VAULT_ROOT / "Projects" / "Iris" / "Iris Agent Memory.md",
            VAULT_ROOT / "Projects" / "Iris" / "Iris Tuya Info.md",
        ]
    ),
    (
        # ChipIn — poker chip wallet app
        {
            "chipin", "chip in", "poker", "chip count", "firebase",
            "chip wallet", "poker app"
        },
        [
            VAULT_ROOT / "Projects" / "ChipIn.md",
        ]
    ),
    (
        # Billed — bill splitting app
        {
            "billed", "bill split", "bill splitting", "split expenses",
            "expense split", "split the bill"
        },
        [
            VAULT_ROOT / "Projects" / "Billed.md",
        ]
    ),
    (
        # Gesture Control — standalone gesture note
        {
            "gesture control", "gesture project", "gesture prototype",
            "mac gesture", "gesture mac"
        },
        [
            VAULT_ROOT / "Projects" / "Gesture Control.md",
        ]
    ),
    (
        # Career — job hunt, resume, applications
        {
            "career", "job", "resume", "application", "cover letter",
            "interview", "wind river", "valeo", "schaeffler", "switchbox",
            "cybernet", "tttech", "williams international", "observable",
            "embedded role", "job hunt", "opt", "visa", "offer letter",
            "linkedin", "recruiter", "hiring"
        },
        [
            VAULT_ROOT / "Career" / "Job Applications.md",
            VAULT_ROOT / "Career" / "Resume & Portfolio.md",
            VAULT_ROOT / "Career" / "OPT & Visa.md",
        ]
    ),
    (
        # Jarvis itself — development, phases, pipeline
        {
            "jarvis phase", "think.py", "speak.py", "listen.py",
            "main.py", "vault.py", "filesystem.py", "memory.py",
            "phase 4", "phase 5", "kokoro", "whisper", "wake word",
            "openwakeword", "pyqt", "hud", "tts pipeline",
            "brave search", "tool calling", "jarvis development"
        },
        [
            VAULT_ROOT / "Projects" / "Jarvis" / "Jarvis.md",
        ]
    ),
]

# Knowledge notes — loaded when relevant domain is mentioned
KNOWLEDGE_CONTEXTS = [
    (
        {"python", "decorator", "async", "asyncio", "pydantic", "typing"},
        [VAULT_ROOT / "Knowledge" / "Python.md"]
    ),
    (
        {"computer vision", "yolo", "opencv", "mediapipe", "object detection", "inference"},
        [VAULT_ROOT / "Knowledge" / "Computer Vision.md"]
    ),
    (
        {"embedded", "rtos", "uart", "i2c", "spi", "microcontroller", "firmware", "baremetal"},
        [VAULT_ROOT / "Knowledge" / "Embedded Systems.md"]
    ),
    (
        {"llm", "transformer", "fine-tune", "rag", "vector", "embedding", "prompt engineering"},
        [VAULT_ROOT / "Knowledge" / "AI & LLMs.md"]
    ),
]


# ── Detection ──────────────────────────────────────────────────────────────────

def detect_relevant_context(text: str) -> list[Path]:
    """
    Given user input text, return a list of vault file paths to load.
    Checks both project signals and knowledge signals.
    Returns empty list if no relevant context detected.
    """
    lowered = text.lower()
    paths   = []

    for signals, files in PROJECT_CONTEXTS + KNOWLEDGE_CONTEXTS:
        if any(signal in lowered for signal in signals):
            for f in files:
                if f.exists() and f not in paths:
                    paths.append(f)

    return paths


# ── Loader ─────────────────────────────────────────────────────────────────────

def load_context_files(paths: list[Path]) -> str:
    """
    Read and concatenate vault files into a context string.
    Returns empty string if no paths given or all files empty.
    """
    if not paths:
        return ""

    sections = []
    for path in paths:
        try:
            content = path.read_text(encoding="utf-8").strip()
            if content:
                sections.append(f"### {path.stem}\n{content}")
        except Exception as e:
            print(f"[context] Could not read {path.name}: {e}")

    if not sections:
        return ""

    return (
        "RELEVANT PROJECT CONTEXT — loaded based on current topic. "
        "Use this to give accurate, specific answers about Edward's projects:\n\n"
        + "\n\n---\n\n".join(sections)
    )


def get_context_for(text: str) -> str:
    """
    Main entry point — detect and load context for user input.
    Returns a context string ready to inject, or empty string.
    """
    paths = detect_relevant_context(text)
    return load_context_files(paths)


if __name__ == "__main__":
    # Smoke tests
    tests = [
        "what's the current state of Iris and the gesture engine",
        "help me with the ChipIn firebase integration",
        "what should I focus on for my Wind River application",
        "what's the weather today",
        "help me debug this Python async code",
    ]
    for t in tests:
        ctx = get_context_for(t)
        label = "LOADED" if ctx else "none"
        paths = detect_relevant_context(t)
        names = [p.name for p in paths]
        print(f"'{t[:50]}...' → {label}: {names}")
