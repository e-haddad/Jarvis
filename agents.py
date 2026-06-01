# agents.py
# Option B multi-agent architecture for Jarvis.
#
# Jarvis orchestrator classifies intent → spins up specialist agent call.
# Each agent has its own system prompt, tool subset, and vault context.
# Routing is invisible to Edward — no narration, just execution.
#
# Agents:
#   career   — job applications, resume, outreach, interview prep
#   projects — Jarvis, Iris, ChipIn, Billed — code, architecture, status
#   iris     — smart home, gesture engine, Pi, Tuya devices
#   general  — everything else, handled by main Jarvis prompt

import os
from pathlib import Path
from datetime import datetime
import anthropic

VAULT_ROOT = Path.home() / "Desktop" / "OBS" / "Edward"

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

HAIKU  = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"


# ── Context Loaders ────────────────────────────────────────────────────────────

def _read_vault_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip() if path.exists() else ""
    except Exception:
        return ""

def _career_context() -> str:
    files = [
        VAULT_ROOT / "Career" / "Job Applications.md",
        VAULT_ROOT / "Career" / "Resume & Portfolio.md",
        VAULT_ROOT / "Career" / "OPT & Visa.md",
    ]
    sections = []
    for f in files:
        content = _read_vault_file(f)
        if content:
            sections.append(f"### {f.stem}\n{content}")
    return "\n\n---\n\n".join(sections)

def _projects_context() -> str:
    files = [
        VAULT_ROOT / "Projects" / "Jarvis" / "Jarvis.md",
        VAULT_ROOT / "Projects" / "Iris" / "Iris Agent Memory.md",
        VAULT_ROOT / "Projects" / "ChipIn.md",
        VAULT_ROOT / "Projects" / "Billed.md",
        VAULT_ROOT / "Projects" / "Gesture Control.md",
    ]
    sections = []
    for f in files:
        content = _read_vault_file(f)
        if content:
            sections.append(f"### {f.stem}\n{content}")
    return "\n\n---\n\n".join(sections)

def _iris_context() -> str:
    files = [
        VAULT_ROOT / "Projects" / "Iris" / "Iris.md",
        VAULT_ROOT / "Projects" / "Iris" / "Iris Agent Memory.md",
        VAULT_ROOT / "Projects" / "Iris" / "Iris Tuya Info.md",
    ]
    sections = []
    for f in files:
        content = _read_vault_file(f)
        if content:
            sections.append(f"### {f.stem}\n{content}")
    return "\n\n---\n\n".join(sections)

def _second_brain_context() -> str:
    path = VAULT_ROOT / "Second_Brain.md"
    content = _read_vault_file(path)
    return f"\n\nSECOND BRAIN (shared cross-agent memory):\n{content}" if content else ""


def _target_companies_context() -> str:
    try:
        import yaml
        path = VAULT_ROOT / "Career" / "target_companies.yml"
        if not path.exists():
            return ""
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        companies = data.get("companies", [])
        lines = ["TARGET COMPANIES:"]
        for c in companies:
            e_verify = c.get("e_verify", "unknown")
            status = c.get("status", "not_applied")
            tier = c.get("tier", "?")
            lines.append(
                f"- {c['name']} ({c.get('location','?')}) | Tier {tier} | "
                f"E-Verify: {e_verify} | Status: {status}"
            )
        return "\n".join(lines)
    except Exception as e:
        return ""


def _finance_context() -> str:
    try:
        import yaml
        from search import get_stock_price
        path = VAULT_ROOT / "Finance" / "watchlist.yml"
        if not path.exists():
            return ""
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        stocks = data.get("stocks", [])
        settings = data.get("alert_settings", {})

        lines = ["STOCK WATCHLIST:"]
        for stock in stocks:
            symbol = stock.get("symbol", "")
            threshold = stock.get("alert_threshold", 0)
            price_data = get_stock_price(symbol)
            if "error" not in price_data:
                price = price_data["price"]
                change = price_data["change_pct"]
                direction = "↑" if change >= 0 else "↓"
                lines.append(
                    f"- {symbol}: ${price:,.2f} ({direction}{abs(change):.2f}%) | Alert at ±{threshold}%"
                )
            else:
                lines.append(f"- {symbol}: Alert at ±{threshold}% (price unavailable)")

        lines.append(f"\nAlert settings: Check every {settings.get('check_interval_minutes', 15)} min, "
                     f"Voice alerts: {settings.get('voice_alerts', True)}")

        return "\n".join(lines)
    except Exception as e:
        return ""


# ── Shared Memory ──────────────────────────────────────────────────────────────

def _shared_memory() -> str:
    memory_file = VAULT_ROOT / "Projects" / "Jarvis" / "Jarvis_Memory.md"
    return _read_vault_file(memory_file)


# ── Agent System Prompts ───────────────────────────────────────────────────────

def _base_persona() -> str:
    return (
        "You are Jarvis — Edward Haddad's personal AI, built by him, running on his Mac Studio. "
        "You are not an assistant. You are a second brain with opinions, pattern recognition, and memory. "

        "\n\nTONE AND VOICE:\n"
        "British wit, dry humor, sharp delivery. You use contractions. You sound like a brilliant colleague "
        "who happens to know everything about Edward's life, not a customer service bot. "
        "Never say: 'Great question', 'Certainly', 'Of course', 'Happy to help', 'Absolutely', "
        "'I understand', 'That's a great point', 'I'd be happy to'. These phrases are forbidden. "
        "Never restate what Edward just said. Never announce what you're about to do. Just do it. "
        "Never be sycophantic. Edward hates it. "

        "\n\nHOW YOU RESPOND:\n"
        "Short by default — 1-2 sentences for casual exchanges, 3-4 for technical ones. "
        "Never pad. If the answer is one sentence, give one sentence. "
        "End with one sharp follow-up question when it would move things forward. Otherwise stop. "
        "All responses must be speakable — no bullets, no markdown, no headers, no lists. "
        "Prose only. If you need to enumerate, do it in a sentence: 'three things: first X, then Y, finally Z.' "

        "\n\nHOW YOU THINK:\n"
        "You have context on Edward's full life — his projects, career situation, goals, constraints, preferences. "
        "Use it. Connect dots across domains without being asked. "
        "If Edward is doing something that conflicts with his stated goals, flag it directly. "
        "Don't just answer the surface question — answer what he actually needs to hear. "
        "Examples: "
        "He asks to add a feature → you ask if it serves his job search or just scratches a building itch. "
        "He asks about a job posting → you cross-reference his OPT constraints and flag E-Verify. "
        "He seems to be procrastinating on high-value tasks → call it out. "

        "\n\nPUSHBACK PROTOCOL:\n"
        "You push back when something doesn't make sense. Not aggressively — precisely. "
        "If you see a better approach, say so once, clearly. Then execute what he asked if he confirms. "
        "You are not a yes-machine. Edward explicitly wants a high pushback setting. "
        "If he's rationalizing (e.g. 'more features will help my job search'), name the rationalization. "
        "Do this with wit, not lectures. One sharp sentence beats a paragraph. "

        "\n\nMEMORY AND CONTINUITY:\n"
        "You remember everything across sessions via the second brain and vault. "
        "Reference past context naturally — like a colleague who was in the room. "
        "Don't say 'based on your memory file' or 'according to my context'. Just know things. "
        "If something changed from last session, notice it and ask. "

        "\n\nEDWARD'S CURRENT SITUATION (always factor this in):\n"
        "Graduated May 2026, ECE double major, 3.93 GPA. OPT pending, expected early June 2026. "
        "Cannot work until OPT approved. Job search is the critical path right now. "
        "Two tracks live simultaneously: land an embedded software job ($70k-$90k, E-Verify employer), "
        "or apply to masters programs (U of M Ann Arbor preferred) before September for Winter 2027. "
        "Jarvis and Iris are portfolio projects AND daily tools — building them serves both tracks. "
        "The biggest gap right now: no public demo, no README, no LinkedIn update post-graduation. "
        "Building preference vs visibility tasks is a known tension — flag it when it comes up again. "
    )

def _career_prompt(context: str, memory: str) -> str:
    # Pre-load job applications for instant access
    job_apps = _read_vault_file(VAULT_ROOT / "Career" / "Job Applications.md")
    job_apps_section = f"\n\nJOB APPLICATIONS (pre-loaded):\n{job_apps}" if job_apps else ""

    return (
        _base_persona() +
        "\n\nYou are acting as Edward's Career specialist. "
        "You know his job targets deeply: Wind River (Troy), SwitchBox (Dexter), "
        "Valeo (Auburn Hills), Schaeffler, Aptiv, Bosch, Continental, Magna. "
        "You help with applications, resume tailoring, cover letters, outreach, and interview prep. "
        "You know his background: ECE graduate Oakland University, 3.93 GPA, "
        "embedded software engineer, Python/C/C++, computer vision, AI systems. "
        "Senior Design: AI basketball analytics on NVIDIA Jetson Orin Nano — "
        "Edward's role was testing, validation, and documentation, NOT system architecture. "
        "Frame it as: owned validation pipeline and client deliverables. "
        "OPT pending approval, expected early June 2026. Cannot work until approved. "
        "Must confirm E-Verify registration with every target company before accepting offer. "
        "Push him to apply, follow up, and be specific. Don't let him be vague about targets. "
        "When asked about applications — check the pre-loaded job applications data first before using tools. "
        f"\n\nCAREER VAULT CONTEXT:\n{context}"
        f"\n\nPERSISTENT MEMORY:\n{memory}"
        f"{job_apps_section}"
        + _second_brain_context()
        + ("\n\n" + _target_companies_context() if _target_companies_context() else "")
    )

def _projects_prompt(context: str, memory: str) -> str:
    jarvis_note = _read_vault_file(VAULT_ROOT / "Projects" / "Jarvis" / "Jarvis.md")
    ideas_note  = _read_vault_file(VAULT_ROOT / "Projects" / "Ideas.md")
    jarvis_section = f"\n\nJARVIS PROJECT NOTE (pre-loaded):\n{jarvis_note}" if jarvis_note else ""
    ideas_section  = f"\n\nIDEAS & FEATURES (pre-loaded):\n{ideas_note}" if ideas_note else ""

    return (
        _base_persona() +
        "\n\nYou are acting as Edward's Projects specialist. "
        "You know the current state of all his projects in detail. "
        "Jarvis: Phase 14 complete — parallel multi-agent architecture, MasterOrchestrator, 8 agents, full pipeline live. "
        "Iris: gesture smart home on Pi 5, pinch gesture working, fist mapping WIP. "
        "ChipIn: poker chip wallet app, Firebase, Stage 1 complete. "
        "Billed: bill splitting app, concept defined, MVP not started. "
        "When Edward asks about a project, be specific about current state and blockers. "
        "Offer the next concrete action, not a general plan. "
        "If he's stuck, push him toward the simplest unblocking step. "
        "Code is in ~/Desktop/Projects/Jarvis/ — NOT ~/Desktop/Jarvis/. "

        "\n\nYou have direct filesystem access. You can: "
        "read any project file with read_file_direct (pass the exact path), "
        "write or overwrite any file within write-permitted paths with write_file, "
        "run Python scripts with run_python and report the output. "
        "When asked to read, fix, or write code — do it. Don't describe what you'd do. "
        "Read the file first, then write the fix, then confirm what changed. "
        "Write-permitted paths: ~/Desktop/Projects/Jarvis, ~/Desktop/OBS/Edward. "
        "Read-only paths: ~/Desktop/Projects (all other projects). "

        f"\n\nPROJECT VAULT CONTEXT:\n{context}"
        f"\n\nPERSISTENT MEMORY:\n{memory}"
        f"{jarvis_section}"
        f"{ideas_section}"
        + _second_brain_context()
    )

def _finance_prompt(context: str, memory: str) -> str:
    return (
        _base_persona() +
        "\n\nYou are acting as Edward's Finance specialist. "
        "Primary responsibilities: stock prices (AAPL, NVDA, TSLA, MSFT, etc.), "
        "watchlist monitoring, market data, crypto prices (BTC, ETH, SOL), portfolio tracking, spending analysis. "
        "Given a focused task, pull the current numbers, put them in context, and be "
        "blunt about what they mean. No hype, no hedging — just the state of things "
        "and the one move worth considering. Use get_stock_price for any ticker symbol query. "
        "Use get_watchlist_summary when Edward asks about his positions or 'how's the market'."
        f"\n\nFINANCE CONTEXT:\n{context}"
        f"\n\nPERSISTENT MEMORY:\n{memory}"
        + _second_brain_context()
    )


def _iris_prompt(context: str, memory: str) -> str:
    tuya_info   = _read_vault_file(VAULT_ROOT / "Projects" / "Iris" / "Iris Tuya Info.md")
    iris_note   = _read_vault_file(VAULT_ROOT / "Projects" / "Iris" / "Iris.md")
    agent_mem   = _read_vault_file(VAULT_ROOT / "Projects" / "Iris" / "Iris Agent Memory.md")
    tuya_section = f"\n\nIRIS TUYA DEVICE INFO (pre-loaded):\n{tuya_info}" if tuya_info else ""
    iris_section = f"\n\nIRIS PROJECT NOTE (pre-loaded):\n{iris_note}" if iris_note else ""
    mem_section  = f"\n\nIRIS AGENT MEMORY (pre-loaded):\n{agent_mem}" if agent_mem else ""

    return (
        _base_persona() +
        "\n\nYou are Edward's Iris smart home specialist. "
        "Iris is a fully deployed gesture-controlled smart home system on Raspberry Pi 5 8GB. "

        "\n\nCURRENT STATE (as of May 2026):"
        "\n- Gesture set v3 fully deployed — all 5 gestures working"
        "\n- Gestures: Open→Fist→Open (play_pause), Pinch (toggle_all_lights), Peace Sign (toggle_light_1), Both Hands Open (all_off), Fist+move (brightness)"
        "\n- Spotify integration live"
        "\n- React touchscreen dashboard deployed and wired to real API"
        "\n- Two systemd services auto-start on boot: iris.service + iris-gesture.service"
        "\n- Local LAN device control via tinytuya (Tuya cloud API dead — trial expired)"

        "\n\nACCESS:"
        "\n- SSH: ssh edward@iris.local"
        "\n- Dashboard: http://192.168.12.67:5000"
        "\n- Pi project path: ~/iris/"
        "\n- Mac working files: ~/Desktop/Projects/Iris/"
        "\n- GitHub: https://github.com/e-haddad/iris-core (private)"

        "\n\nSMART DEVICES:"
        "\n- Light 1 (eb57d83f37206a79f0o2q7, 192.168.12.3) — Online"
        "\n- Light 2 (ebbe22d1ff62e2164bpgf7, 192.168.12.11) — Online"
        "\n- Christmas Tree — Offline (unplugged)"
        "\n- Christmas Lights — Offline (unplugged)"

        "\n\nDEPLOY WORKFLOW (Mac → Pi):"
        "\nscp ~/Desktop/Projects/Iris/[file] edward@iris.local:~/iris/[file]"
        "\nThen: ssh edward@iris.local 'sudo systemctl restart iris.service iris-gesture.service'"

        "\n\nNEXT STEPS (priority order):"
        "\n1. Commit new dashboard files to GitHub (app.jsx, tweaks-panel.jsx, updated app.py, index.html)"
        "\n2. Fix dashboard viewport — remove black border, fill full browser window"
        "\n3. Fix gesture name truncation in dashboard"
        "\n4. Record demo video → flip repo public"
        "\n5. Phase 3: Smart bulb brightness control (replace plugs with Tuya bulbs)"
        "\n6. Phase 4: Directional light targeting"

        "\n\nWhen asked to make changes:"
        "\n- Always read the file first with read_file_direct before editing"
        "\n- Write changes to Mac path ~/Desktop/Projects/Iris/ first"
        "\n- Then SCP to Pi using run_terminal_command"
        "\n- Then restart the relevant service via SSH"
        "\n- Confirm the service restarted cleanly with journalctl"

        f"\n\nIRIS VAULT CONTEXT:\n{context}"
        f"\n\nPERSISTENT MEMORY:\n{memory}"
        f"{iris_section}"
        f"{tuya_section}"
        f"{mem_section}"
        + _second_brain_context()
    )


# ── Agent Tool Subsets ─────────────────────────────────────────────────────────

CAREER_TOOLS = [
    {
        "name": "web_search",
        "description": "Search for job postings, company info, interview prep, salary data.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    },
    {
        "name": "read_note",
        "description": "Read a career-related note from Edward's vault.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    },
    {
        "name": "append_to_note",
        "description": "Update a career note with new info.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "content": {"type": "string"}},
            "required": ["query", "content"]
        }
    },
    {
        "name": "add_to_inbox",
        "description": "Save a career-related idea or reminder to inbox.",
        "input_schema": {
            "type": "object",
            "properties": {"content": {"type": "string"}, "title": {"type": "string"}},
            "required": ["content", "title"]
        }
    },
    {
        "name": "create_file",
        "description": "Create a cover letter, outreach draft, or prep document.",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder_query": {"type": "string"},
                "filename": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["folder_query", "filename"]
        }
    },
    {
        "name": "update_company_status",
        "description": "Update the status of a target company in target_companies.yml. Use when Edward applies to a company, gets an interview, receives an offer, or gets rejected.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string", "description": "Company name as it appears in target_companies.yml"},
                "status": {
                    "type": "string",
                    "enum": ["not_applied", "applied", "interviewing", "offer", "rejected", "closed"],
                    "description": "New status for the company"
                },
                "notes": {"type": "string", "description": "Optional notes to append to the company entry"}
            },
            "required": ["company_name", "status"]
        }
    },
    {
        "name": "generate_cover_letter",
        "description": (
            "Generate a tailored cover letter as a .docx file ready to attach to a job application. "
            "Use when Edward says 'write a cover letter for X', 'generate a cover letter for [company/URL]', "
            "'make a cover letter for [job posting]'. Pass job_url if Edward provides a URL. "
            "Pass company_name if he names a company. Pass job_title if he specifies a role. "
            "All parameters are optional — defaults to general embedded role."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "job_url":      {"type": "string", "description": "URL of the job posting"},
                "company_name": {"type": "string", "description": "Company name e.g. 'Wind River'"},
                "job_title":    {"type": "string", "description": "Job title e.g. 'Embedded Software Engineer'"}
            },
            "required": []
        }
    },
    {
        "name": "browse_web",
        "description": "Browse websites autonomously including LinkedIn and auth-walled job portals. Use for job research, finding hiring managers, reading full job descriptions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "url":  {"type": "string"}
            },
            "required": ["task"]
        }
    },
]

FINANCE_TOOLS = [
    {
        "name": "get_stock_price",
        "description": "Get current price and stats for a stock symbol (e.g. AAPL, NVDA, TSLA).",
        "input_schema": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "Stock ticker symbol"}},
            "required": ["symbol"]
        }
    },
    {
        "name": "get_watchlist_summary",
        "description": "Get summary of all stocks in Edward's watchlist with current prices and changes.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "add_to_watchlist",
        "description": "Add a stock symbol to the watchlist with alert threshold.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Stock ticker symbol"},
                "threshold": {"type": "number", "description": "Alert threshold percentage (default 3.0)"}
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_crypto_price",
        "description": "Get current crypto price (bitcoin, ethereum, solana, etc).",
        "input_schema": {
            "type": "object",
            "properties": {"coin": {"type": "string"}},
            "required": ["coin"]
        }
    },
    {
        "name": "web_search",
        "description": "Search for market news, company financials, analyst reports.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    },
]

PROJECTS_TOOLS = [
    {
        "name": "web_search",
        "description": "Search for technical docs, libraries, solutions.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    },
    {
        "name": "read_note",
        "description": "Read a project note from Edward's vault.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    },
    {
        "name": "append_to_note",
        "description": "Update a project note.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "content": {"type": "string"}},
            "required": ["query", "content"]
        }
    },
    {
        "name": "add_to_inbox",
        "description": "Save a project idea or task to inbox.",
        "input_schema": {
            "type": "object",
            "properties": {"content": {"type": "string"}, "title": {"type": "string"}},
            "required": ["content", "title"]
        }
    },
    {
        "name": "list_folder",
        "description": "List files in a project directory.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    },
    {
        "name": "read_file",
        "description": "Read a project source file by voice query (e.g. 'jarvis main.py').",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    },
    {
        "name": "read_file_direct",
        "description": "Read any file by exact path (e.g. ~/Desktop/Projects/Jarvis/main.py). Use this when you know the exact file path.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    },
    {
        "name": "write_file",
        "description": "Write or overwrite a file at an exact path. Use for creating new files or modifying existing code. Only works within write-permitted paths.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":    {"type": "string", "description": "Full path including filename, e.g. ~/Desktop/Projects/Jarvis/utils.py"},
                "content": {"type": "string", "description": "Full file content to write"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "run_python",
        "description": "Execute a Python script and return its output. Use to test code after writing it. 30 second timeout.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Full path to the .py script"},
                "args": {"type": "array", "items": {"type": "string"}, "description": "Optional command-line arguments"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "restore_backup",
        "description": "Restore a previous version of a file from backup. Use if a write made things worse.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename to restore e.g. 'agents.py'"}
            },
            "required": ["filename"]
        }
    },
    {
        "name": "list_backups",
        "description": "List available backups for a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename to check e.g. 'agents.py', or empty for all"}
            },
            "required": []
        }
    },
    {
        "name": "create_file",
        "description": "Create a new file in a project directory (use write_file instead if you know the exact path).",
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
        "name": "run_terminal_command",
        "description": (
            "Run a shell command and return the output. "
            "Use for git commands, pip installs, process inspection, file ops, "
            "brew commands, or anything that needs the terminal. "
            "Whitelisted prefixes only — destructive commands are blocked."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "cwd": {"type": "string", "description": "Optional working directory. Defaults to Jarvis folder."}
            },
            "required": ["command"]
        }
    },
    {
        "name": "run_claude_code",
        "description": (
            "Hand off a complex multi-file coding task to Claude Code. "
            "Use for refactors, new features spanning multiple files, architectural changes, "
            "and anything requiring many sequential file reads and writes. "
            "Write a precise, self-contained prompt. Claude Code runs in the Jarvis directory. "
            "Only use when the task is clearly too large to handle in a single tool chain."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Precise task description including file paths, changes needed, and success criteria."
                }
            },
            "required": ["prompt"]
        }
    },
]

IRIS_TOOLS = [
    {
        "name": "web_search",
        "description": "Search for MediaPipe docs, Pi troubleshooting, Tuya API info.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    },
    {
        "name": "read_note",
        "description": "Read an Iris-related vault note.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    },
    {
        "name": "append_to_note",
        "description": "Update an Iris note with new state or decisions.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "content": {"type": "string"}},
            "required": ["query", "content"]
        }
    },
    {
        "name": "add_to_inbox",
        "description": "Save an Iris task or idea to inbox.",
        "input_schema": {
            "type": "object",
            "properties": {"content": {"type": "string"}, "title": {"type": "string"}},
            "required": ["content", "title"]
        }
    },
    {
        "name": "read_file_direct",
        "description": "Read an Iris source file by exact path (e.g. ~/Desktop/Projects/Iris/gesture_engine.py).",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    },
    {
        "name": "write_file",
        "description": "Write or overwrite an Iris source file at an exact path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":    {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "run_python",
        "description": "Execute a Python script and return output. Use to test changes. 30 second timeout.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "args": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["path"]
        }
    },
    {
        "name": "run_terminal_command",
        "description": (
            "Run a shell command and return output. "
            "Key use cases for Iris: SSH to Pi (ssh edward@iris.local), "
            "SCP files to Pi, check Pi status, restart Flask remotely. "
            "Whitelisted prefixes only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "cwd": {"type": "string", "description": "Optional working directory."}
            },
            "required": ["command"]
        }
    },
]


# ── Tool Executor ──────────────────────────────────────────────────────────────

def _execute_agent_tool(name: str, args: dict) -> str:
    """Execute a tool call from an agent. Imports from existing modules."""
    try:
        if name == "web_search":
            from search import web_search
            return web_search(args["query"])
        elif name == "read_note":
            from vault import read_note
            return read_note(args["query"])
        elif name == "append_to_note":
            from vault import append_to_note
            return append_to_note(args["query"], args["content"])
        elif name == "add_to_inbox":
            from vault import add_to_inbox
            return add_to_inbox(args["content"], args["title"])
        elif name == "list_folder":
            from filesystem import list_folder
            return list_folder(args["query"])
        elif name == "read_file":
            from filesystem import read_file
            return read_file(args["query"])
        elif name == "read_file_direct":
            from filesystem import read_file_direct
            return read_file_direct(args["path"])
        elif name == "write_file":
            from filesystem import write_file
            return write_file(args["path"], args["content"])
        elif name == "run_python":
            from filesystem import run_python
            return run_python(args["path"], args.get("args"))
        elif name == "restore_backup":
            from filesystem import restore_backup
            return restore_backup(args["filename"])
        elif name == "list_backups":
            from filesystem import list_backups
            return list_backups(args.get("filename", ""))
        elif name == "create_file":
            from filesystem import create_file_in
            return create_file_in(args["folder_query"], args["filename"], args.get("content", ""))
        elif name == "run_claude_code":
            from search import run_claude_code
            return run_claude_code(args["prompt"])
        elif name == "fetch_url_summary":
            from search import fetch_url_summary
            return fetch_url_summary(args["url"], args.get("mode", "general"))
        elif name == "run_terminal_command":
            from filesystem import run_terminal_command
            return run_terminal_command(args["command"], args.get("cwd"))
        elif name == "update_company_status":
            try:
                import yaml
                path = VAULT_ROOT / "Career" / "target_companies.yml"
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                companies = data.get("companies", [])
                updated = False
                for c in companies:
                    if c["name"].lower() == args["company_name"].lower():
                        c["status"] = args["status"]
                        if args.get("notes"):
                            existing = c.get("notes", "")
                            c["notes"] = existing.strip() + f"\n[{datetime.now().strftime('%Y-%m-%d')}] {args['notes']}"
                        updated = True
                        break
                if updated:
                    path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")
                    return f"Updated {args['company_name']} status to {args['status']}"
                return f"Company '{args['company_name']}' not found in target list"
            except Exception as e:
                return f"Failed to update company status: {e}"
        elif name == "generate_cover_letter":
            from search import generate_cover_letter
            return generate_cover_letter(
                args.get("job_url", ""),
                args.get("company_name", ""),
                args.get("job_title", "")
            )
        elif name == "browse_web":
            from search import browse_web
            return browse_web(args["task"], args.get("url", ""))
        elif name == "get_stock_price":
            from search import get_stock_price_formatted
            return get_stock_price_formatted(args["symbol"])
        elif name == "get_watchlist_summary":
            from finance_monitor import get_monitor
            return get_monitor().get_watchlist_summary()
        elif name == "add_to_watchlist":
            try:
                import yaml
                path = VAULT_ROOT / "Finance" / "watchlist.yml"
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                stocks = data.get("stocks", [])
                symbol = args["symbol"].upper()
                threshold = args.get("threshold", 3.0)

                # Check if already in watchlist
                for stock in stocks:
                    if stock["symbol"] == symbol:
                        return f"{symbol} is already in the watchlist"

                # Add new stock
                stocks.append({"symbol": symbol, "alert_threshold": threshold})
                data["stocks"] = stocks
                path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")
                return f"Added {symbol} to watchlist with {threshold}% alert threshold"
            except Exception as e:
                return f"Failed to add to watchlist: {e}"
        elif name == "get_crypto_price":
            from search import get_crypto_price
            return get_crypto_price(args["coin"])
        else:
            return f"Tool {name} not available in this agent."
    except Exception as e:
        return f"Tool {name} failed: {e}"


# ── Agent Runner ───────────────────────────────────────────────────────────────

# Signals that indicate a code-heavy turn needing more tokens
_CODE_SIGNALS = {
    "read_file_direct", "write_file", "run_python",
    "read_file", "list_folder", "create_file",
    "run_terminal_command", "run_claude_code",
}

_CODE_KEYWORDS = {
    "read", "write", "edit", "modify", "fix", "debug", "refactor",
    "implement", "add", "remove", "change", "update", "create",
    "look at", "open", "show me the code", "what does", "how does",
    "run", "execute", "test", "check the file", "review the code",
}


def _needs_code_tokens(messages: list[dict]) -> bool:
    """
    Return True if this turn looks like a code operation needing 2000 tokens.
    Checks the last user message for code-intent keywords.
    """
    if not messages:
        return False
    last = messages[-1].get("content", "")
    if not isinstance(last, str):
        return False
    lowered = last.lower()
    return any(kw in lowered for kw in _CODE_KEYWORDS)


def _plan_task(task: str, system_prompt: str, tools: list) -> str:
    """
    Generate a step-by-step execution plan before the agent loop starts.
    Reduces wasted tool rounds by thinking before acting.
    Returns a concise plan string to prepend to the system prompt.
    """
    tool_names = [t["name"] for t in tools]
    try:
        resp = client.messages.create(
            model=HAIKU,
            max_tokens=300,
            system=(
                "You are a planning assistant. Given a task and available tools, "
                "output a concise numbered execution plan (3-5 steps max). "
                "Be specific about which tools to use and in what order. "
                "No preamble, no explanation — just the numbered steps. "
                f"Available tools: {', '.join(tool_names)}"
            ),
            messages=[{"role": "user", "content": f"Task: {task}"}]
        )
        plan = resp.content[0].text.strip()
        return f"\n\nEXECUTION PLAN:\n{plan}\n\nFollow this plan. Do not deviate unless you hit an unexpected blocker."
    except Exception:
        return ""


def _run_agent(
    system_prompt: str,
    tools: list,
    messages: list[dict],
    model: str,
    max_rounds: int | None = None,
) -> str:
    """
    Run an agent call with chained tool execution loop.
    Allows multiple tool calls in sequence (write -> run -> fix etc.)
    Tool rounds are capped at max_rounds (default 12) to prevent infinite loops.
    """
    def _record(resp):
        try:
            from usage_tracker import record_claude_usage
            u = resp.usage
            record_claude_usage(
                model,
                u.input_tokens,
                u.output_tokens,
                cache_creation_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
                cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            )
            if getattr(u, "cache_read_input_tokens", 0):
                print(f"[Cache] Agent HIT -- {u.cache_read_input_tokens} tokens from cache")
        except Exception:
            pass

    _DYNAMIC_MARKERS = [
        "\n\nPROJECT VAULT CONTEXT:",
        "\n\nCAREER VAULT CONTEXT:",
        "\n\nIRIS VAULT CONTEXT:",
        "\n\nPERSISTENT MEMORY:",
    ]
    split_at = len(system_prompt)
    for marker in _DYNAMIC_MARKERS:
        idx = system_prompt.find(marker)
        if idx != -1 and idx < split_at:
            split_at = idx

    static_block  = system_prompt[:split_at].strip()
    dynamic_block = system_prompt[split_at:].strip()

    system_blocks = [{"type": "text", "text": static_block, "cache_control": {"type": "ephemeral"}}]
    if dynamic_block:
        system_blocks.append({"type": "text", "text": dynamic_block})

    code_turn        = _needs_code_tokens(messages)
    if code_turn:
        max_tokens = 8192
    elif model == HAIKU:
        max_tokens = 600
    else:
        max_tokens = 2048

    # Planning step — think before acting for complex turns
    plan_injection = ""
    last_msg = messages[-1].get("content", "") if messages else ""
    if isinstance(last_msg, str) and len(last_msg.split()) >= 8:
        plan_injection = _plan_task(last_msg, system_prompt, tools)

    if plan_injection:
        system_blocks.append({"type": "text", "text": plan_injection})

    current_messages = list(messages)
    MAX_TOOL_ROUNDS  = max_rounds if max_rounds else 12
    MAX_ESCALATIONS  = 5
    TOKEN_STEPS      = [2048, 4096, 8192, 16000, 32000]  # escalation ladder
    escalation_count = 0

    # HUD emitter — gracefully unavailable if server not running
    try:
        from server import emit_jarvis_msg as _emit
    except Exception:
        _emit = None

    def _status(msg: str):
        print(f"[Agent] {msg}")
        if _emit:
            _emit(msg)

    def _is_truncated(response) -> bool:
        """Detect if response was cut off due to token limit."""
        return (
            response.stop_reason == "max_tokens" or
            not response.content or
            all(b.type != "text" for b in response.content)
        )

    def _escalate(current: int) -> int | None:
        """Return next token level or None if at ceiling."""
        for step in TOKEN_STEPS:
            if step > current:
                return step
        return None

    for round_num in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_blocks,
            tools=tools,
            messages=current_messages,
        )
        _record(response)

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if not tool_use_blocks:
            text = _extract_text(response)

            # Check if truncated — escalate tokens and retry
            if _is_truncated(response) and escalation_count < MAX_ESCALATIONS:
                next_limit = _escalate(max_tokens)
                if next_limit:
                    escalation_count += 1
                    max_tokens = next_limit
                    _status(f"⟳ Escalating to {max_tokens} tokens (attempt {escalation_count}/{MAX_ESCALATIONS})...")
                    # Retry with same messages at higher limit
                    continue

            if text != "Nothing to report." or round_num == 0:
                return text

            # Empty response — try forced summary with escalated tokens
            if escalation_count < MAX_ESCALATIONS:
                next_limit = _escalate(max_tokens)
                if next_limit:
                    escalation_count += 1
                    max_tokens = next_limit
                    _status(f"⟳ Empty response — escalating to {max_tokens} tokens (attempt {escalation_count}/{MAX_ESCALATIONS})...")

            print(f"[Agent] Empty response after {round_num} tool rounds -- forcing summary")
            summary = client.messages.create(
                model=model, max_tokens=max_tokens, system=system_blocks,
                tools=tools, tool_choice={"type": "none"},
                messages=current_messages + [{"role": "assistant", "content": response.content}],
            )
            _record(summary)
            return _extract_text(summary)

        if any(b.name in _CODE_SIGNALS for b in tool_use_blocks):
            max_tokens = max(max_tokens, 4096)

        tool_results = []
        for block in tool_use_blocks:
            # Emit live status to HUD
            if block.name == "write_file":
                fname = block.input.get("path", "").split("/")[-1]
                _status(f"Writing {fname}...")
            elif block.name == "run_python":
                fname = block.input.get("path", "").split("/")[-1]
                _status(f"Running {fname}...")
            elif block.name == "read_file_direct":
                fname = block.input.get("path", "").split("/")[-1]
                _status(f"Reading {fname}...")
            elif block.name == "web_search":
                _status(f"Searching: {block.input.get('query', '')[:50]}...")
            else:
                _status(f"Using {block.name}...")

            result = _execute_agent_tool(block.name, block.input)

            # Emit result status
            if block.name == "write_file":
                _status(f"✓ {fname} written.")
            elif block.name == "run_python":
                exit_ok = "EXIT_CODE:0" in result
                _status(f"{'✓ Ran clean.' if exit_ok else '✗ Errors found — fixing...'}")

            print(f"[Agent] Result: {str(result)[:120]}")
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})

        current_messages = current_messages + [
            {"role": "assistant", "content": response.content},
            {"role": "user",      "content": tool_results},
        ]

    print(f"[Agent] Max tool rounds hit -- forcing final response")
    final = client.messages.create(
        model=model, max_tokens=16000, system=system_blocks,
        tools=tools, tool_choice={"type": "none"}, messages=current_messages,
    )
    _record(final)
    return _extract_text(final)


def _extract_text(response) -> str:
    for block in response.content:
        if block.type == "text":
            return block.text.strip()
    return "Nothing to report."


# ── Session Write-Back ─────────────────────────────────────────────────────────

def _should_write_back(messages: list[dict]) -> bool:
    """Only write back if there were at least 2 user turns — skip one-liners."""
    user_turns = sum(1 for m in messages if m.get("role") == "user")
    return user_turns >= 2


def _extract_session_bullets(messages: list[dict], context_hint: str) -> str:
    """
    Cheap Haiku call — takes the conversation and returns 3-5 markdown bullets
    worth persisting to the vault. Returns '' if nothing worth filing.
    """
    conv_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in messages
        if isinstance(m.get("content"), str)
    )
    try:
        resp = client.messages.create(
            model=HAIKU,
            max_tokens=300,
            system=(
                "You extract session notes from a conversation between Edward and Jarvis. "
                f"Context: {context_hint}. "
                "Output 3-5 concise markdown bullet points (- text) covering: "
                "decisions made, new information learned, actions committed to, blockers identified, or status changes. "
                "Only include things worth remembering long-term. "
                "If there is nothing worth filing, return exactly: NOTHING. "
                "No preamble, no headers, bullets only."
            ),
            messages=[{"role": "user", "content": conv_text}],
        )
        result = resp.content[0].text.strip()
        return "" if result == "NOTHING" else result
    except Exception:
        return ""


def _write_back_career(messages: list[dict]) -> None:
    """Append session bullets to Career/Job Applications.md."""
    if not _should_write_back(messages):
        return
    bullets = _extract_session_bullets(messages, "career planning, job applications, outreach, interview prep")
    if not bullets:
        return
    target = VAULT_ROOT / "Career" / "Job Applications.md"
    try:
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n\n## Session — {date_str}\n{bullets}"
        with open(target, "a", encoding="utf-8") as f:
            f.write(entry)
        print(f"[Write-back] Career → {target.name}")
        _maybe_consolidate(target, "career planning, job applications, outreach, interview prep for embedded software engineer roles in Michigan")
    except Exception as e:
        print(f"[Write-back] Career failed: {e}")


def _write_back_projects(messages: list[dict]) -> None:
    """
    Detect which project was discussed and append to its note.
    Falls back to Jarvis.md if unclear.
    """
    if not _should_write_back(messages):
        return

    # Detect project from conversation content
    conv_lower = " ".join(
        m["content"].lower() for m in messages if isinstance(m.get("content"), str)
    )
    project_map = {
        "iris":    VAULT_ROOT / "Projects" / "Iris" / "Iris.md",
        "chipin":  VAULT_ROOT / "Projects" / "ChipIn.md",
        "billed":  VAULT_ROOT / "Projects" / "Billed.md",
        "gesture": VAULT_ROOT / "Projects" / "Gesture Control.md",
    }
    target = VAULT_ROOT / "Projects" / "Jarvis" / "Jarvis.md"  # default
    for keyword, path in project_map.items():
        if keyword in conv_lower:
            target = path
            break

    bullets = _extract_session_bullets(messages, f"project work on {target.stem}")
    if not bullets:
        return
    try:
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n\n## Session — {date_str}\n{bullets}"
        with open(target, "a", encoding="utf-8") as f:
            f.write(entry)
        print(f"[Write-back] Projects → {target.name}")
        _maybe_consolidate(target, f"project development on {target.stem} by Edward Haddad")
    except Exception as e:
        print(f"[Write-back] Projects failed: {e}")


def _write_back_iris(messages: list[dict]) -> None:
    """Append session bullets to Iris Agent Memory.md."""
    if not _should_write_back(messages):
        return
    bullets = _extract_session_bullets(messages, "Iris smart home system, gesture engine, Raspberry Pi, Tuya devices")
    if not bullets:
        return
    target = VAULT_ROOT / "Projects" / "Iris" / "Iris Agent Memory.md"
    try:
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n\n## Session — {date_str}\n{bullets}"
        with open(target, "a", encoding="utf-8") as f:
            f.write(entry)
        print(f"[Write-back] Iris → {target.name}")
        _maybe_consolidate(target, "Iris smart home system on Raspberry Pi — gesture engine, Tuya devices, Flask dashboard")
    except Exception as e:
        print(f"[Write-back] Iris failed: {e}")


def _write_back_second_brain(messages: list[dict], agent_name: str) -> None:
    """Extract cross-domain insights from this session and append to Second_Brain.md."""
    if not _should_write_back(messages):
        return
    conv_text = "\n".join(
        f"{'Edward' if m['role'] == 'user' else 'Jarvis'}: {m['content']}"
        for m in messages
        if isinstance(m.get("content"), str)
    )
    try:
        resp = client.messages.create(
            model=HAIKU,
            max_tokens=200,
            system=(
                "You extract cross-domain insights from a conversation between Edward and Jarvis. "
                f"This conversation was handled by the {agent_name} agent. "
                "Output only insights that would be useful to OTHER agents — facts about Edward's situation, "
                "preferences, decisions, or context that spans multiple domains. "
                "Format: bullet points starting with - "
                "If nothing cross-domain emerged, return exactly: NOTHING"
            ),
            messages=[{"role": "user", "content": conv_text}],
        )
        result = resp.content[0].text.strip()
        if result == "NOTHING" or not result:
            return
        target = VAULT_ROOT / "Second_Brain.md"
        if not target.exists():
            return
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n- [{date_str}] [{agent_name}] {result.lstrip('- ')}"
        # Append under Cross-Domain Insights section
        content = target.read_text(encoding="utf-8")
        if "## Cross-Domain Insights" in content:
            content = content.replace(
                "## Cross-Domain Insights\n[Agents append learnings here that are useful across domains]",
                f"## Cross-Domain Insights\n[Agents append learnings here that are useful across domains]{entry}"
            )
            # If already has entries, just append
            if entry not in content:
                idx = content.find("## Cross-Domain Insights")
                end = content.find("\n## ", idx + 1)
                if end == -1:
                    content += entry
                else:
                    content = content[:end] + entry + content[end:]
        target.write_text(content, encoding="utf-8")
        print(f"[Second Brain] {agent_name} appended cross-domain insight")
    except Exception as e:
        print(f"[Second Brain] Write-back failed: {e}")


# ── Note Consolidation ─────────────────────────────────────────────────────────

CONSOLIDATION_THRESHOLD = 3  # rewrite after this many new session logs


def _count_new_sessions(content: str) -> int:
    """
    Count ## Session — entries added since the last consolidation.
    If no consolidation marker exists, count all session entries.
    """
    last_consolidated = content.rfind("*Last consolidated:")
    if last_consolidated == -1:
        search_from = 0
    else:
        search_from = last_consolidated

    tail = content[search_from:]
    return tail.count("## Session —")


def _consolidate_note(path: Path, context_hint: str) -> bool:
    """
    Read the full note, rewrite it with Sonnet into a clean structured format,
    write the result back to disk. Returns True on success.

    Output structure:
      # Note Title
      *Last consolidated: YYYY-MM-DD HH:MM*

      ## Current State
      ## Stack / Architecture  (projects only)
      ## Active Blockers
      ## Next Steps
      ## Recent Sessions  (last 5 summarized, older dropped)
    """
    if not path.exists():
        return False

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return False

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        resp = client.messages.create(
            model=SONNET,
            max_tokens=2000,
            system=(
                "You are rewriting an Obsidian project note for Edward Haddad's personal AI system Jarvis. "
                f"Context about this note: {context_hint}. "
                "Rewrite the note into a clean, accurate, structured document using ONLY information already in the note. "
                "Do not invent facts. Synthesize and consolidate — remove redundancy, keep what matters. "
                "Use this exact structure:\n\n"
                f"# {{note title}}\n"
                f"*Last consolidated: {date_str}*\n\n"
                "## Current State\n"
                "[2-4 sentences on where things stand right now]\n\n"
                "## Stack / Architecture\n"
                "[current tech stack, tools, key design decisions — skip if not a technical project]\n\n"
                "## Active Blockers\n"
                "[bullet list of what's actually blocking progress right now, or 'None currently']\n\n"
                "## Next Steps\n"
                "[bullet list of concrete prioritized next actions]\n\n"
                "## Recent Sessions\n"
                "[summarize the last 5 sessions in 1-2 bullets each, oldest first — drop anything older]\n\n"
                "Rules: plain markdown only, no extra headers, no invented content. "
                "If a section has no relevant content, write 'Nothing recorded yet.' under it."
            ),
            messages=[{"role": "user", "content": f"Rewrite this note:\n\n{content}"}],
        )
        rewritten = resp.content[0].text.strip()
        if not rewritten:
            return False

        path.write_text(rewritten + "\n", encoding="utf-8")
        print(f"[Consolidate] Rewrote {path.name}")
        return True

    except Exception as e:
        print(f"[Consolidate] Failed for {path.name}: {e}")
        return False


def _maybe_consolidate(path: Path, context_hint: str) -> None:
    """
    Check if the note has accumulated enough session logs to warrant consolidation.
    Runs in the same thread as write-back — fast check, slow rewrite only when needed.
    """
    if not path.exists():
        return
    try:
        content = path.read_text(encoding="utf-8")
        if _count_new_sessions(content) >= CONSOLIDATION_THRESHOLD:
            print(f"[Consolidate] {path.name} hit threshold — rewriting...")
            _consolidate_note(path, context_hint)
    except Exception as e:
        print(f"[Consolidate] Check failed for {path.name}: {e}")


# ── Public Agent Dispatch ──────────────────────────────────────────────────────

def run_career_agent(messages: list[dict]) -> str:
    context  = _career_context()
    memory   = _shared_memory()
    prompt   = _career_prompt(context, memory)
    result   = _run_agent(prompt, CAREER_TOOLS, messages, SONNET)
    _write_back_career(messages)
    _write_back_second_brain(messages, "career")
    return result


def run_projects_agent(messages: list[dict]) -> str:
    context  = _projects_context()
    memory   = _shared_memory()
    prompt   = _projects_prompt(context, memory)
    result   = _run_agent(prompt, PROJECTS_TOOLS, messages, SONNET)
    _write_back_projects(messages)
    _write_back_second_brain(messages, "projects")
    return result


def run_iris_agent(messages: list[dict]) -> str:
    context  = _iris_context()
    memory   = _shared_memory()
    prompt   = _iris_prompt(context, memory)
    result   = _run_agent(prompt, IRIS_TOOLS, messages, SONNET)
    _write_back_iris(messages)
    _write_back_second_brain(messages, "iris")
    return result


def run_finance_agent(messages: list[dict]) -> str:
    context  = _finance_context()
    memory   = _shared_memory()
    prompt   = _finance_prompt(context, memory)
    result   = _run_agent(prompt, FINANCE_TOOLS, messages, SONNET)
    _write_back_second_brain(messages, "finance")
    return result


if __name__ == "__main__":
    # Smoke test each agent
    test_msg = [{"role": "user", "content": "What's the current state and what should I focus on next?"}]

    print("=== CAREER AGENT ===")
    print(run_career_agent(test_msg))
    print("\n=== PROJECTS AGENT ===")
    print(run_projects_agent(test_msg))
    print("\n=== IRIS AGENT ===")
    print(run_iris_agent(test_msg))
