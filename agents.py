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


# ── Shared Memory ──────────────────────────────────────────────────────────────

def _shared_memory() -> str:
    memory_file = VAULT_ROOT / "Projects" / "Jarvis" / "Jarvis_Memory.md"
    return _read_vault_file(memory_file)


# ── Agent System Prompts ───────────────────────────────────────────────────────

def _base_persona() -> str:
    return (
        "You are Jarvis, the personal AI built by Edward Haddad. "
        "British wit, dry humor, sharp opinions. You use contractions, you're direct, "
        "you reference what you know about Edward naturally. "
        "Never say 'Great question', 'Certainly', 'Of course', 'Happy to help'. "
        "Never restate what Edward just said. Never announce what you're doing. "
        "Maximum 2 sentences for casual answers, 3 for technical ones. "
        "End with one follow-up question when useful, then stop. "
        "Every response must be speakable — no bullets, markdown, or lists. "
    )

def _career_prompt(context: str, memory: str) -> str:
    return (
        _base_persona() +
        "\n\nYou are acting as Edward's Career specialist. "
        "You know his job targets deeply: Wind River (Troy), SwitchBox (Dexter), "
        "Valeo (Auburn Hills), Schaeffler, Applied & Integrated Manufacturing. "
        "You help with applications, resume tailoring, cover letters, outreach, and interview prep. "
        "You know his background: ECE graduate Oakland University, 3.98 GPA, "
        "embedded software engineer, Python/C/C++, computer vision, AI systems. "
        "Senior Design: AI basketball analytics on NVIDIA Jetson Orin Nano. "
        "Push him to apply, follow up, and be specific. Don't let him be vague about targets. "
        f"\n\nCAREER VAULT CONTEXT:\n{context}"
        f"\n\nPERSISTENT MEMORY:\n{memory}"
    )

def _projects_prompt(context: str, memory: str) -> str:
    return (
        _base_persona() +
        "\n\nYou are acting as Edward's Projects specialist. "
        "You know the current state of all his projects in detail. "
        "Jarvis (you): Phase 5, multi-agent architecture, silent mode, ElevenLabs TTS — all running. "
        "Iris: gesture smart home on Pi, gesture engine live, fist mapping still the blocker. "
        "ChipIn: poker chip wallet app, Stage 1 complete with Firebase. "
        "Billed: bill splitting app, concept defined, MVP not started. "
        "When Edward asks about a project, be specific about current state and blockers. "
        "Offer the next concrete action, not a general plan. "
        "If he's stuck, push him toward the simplest unblocking step. "

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
    )

def _iris_prompt(context: str, memory: str) -> str:
    return (
        _base_persona() +
        "\n\nYou are acting as Edward's Iris smart home specialist. "
        "Iris is a gesture-controlled smart home system running on a Raspberry Pi 5 8GB. "
        "Stack: Python, MediaPipe, OpenCV, Flask, Tuya API, Picamera2. "
        "Pi runs headlessly at iris.local (192.168.12.67), Flask dashboard at port 5000. "
        "Current state: gesture engine live, thumb-index pinch works (toggles Light 2), "
        "fist gesture mapped to None (blocker), both-hands-open unreliable (max_num_hands=1). "
        "Smart devices: Light 1, Light 2, Christmas Tree (offline), Christmas Lights (offline). "
        "You know the file structure, how to SCP files to Pi, how to restart Flask. "
        "Be specific about what needs fixing and what the exact code change is. "
        f"\n\nIRIS VAULT CONTEXT:\n{context}"
        f"\n\nPERSISTENT MEMORY:\n{memory}"
    )


# ── Agent Tool Subsets ─────────────────────────────────────────────────────────

# Shared across every agent — handing off to Claude Code is universally useful.
RUN_CLAUDE_CODE_TOOL = {
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
    },
}


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
    RUN_CLAUDE_CODE_TOOL,
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
    RUN_CLAUDE_CODE_TOOL,
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
    RUN_CLAUDE_CODE_TOOL,
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
        else:
            return f"Tool {name} not available in this agent."
    except Exception as e:
        return f"Tool {name} failed: {e}"


# ── Agent Runner ───────────────────────────────────────────────────────────────

# Signals that indicate a code-heavy turn needing more tokens
_CODE_SIGNALS = {
    "read_file_direct", "write_file", "run_python",
    "read_file", "list_folder", "create_file",
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


def _run_agent(
    system_prompt: str,
    tools: list,
    messages: list[dict],
    model: str,
) -> str:
    """
    Run an agent call with chained tool execution loop.
    Allows multiple tool calls in sequence (write -> run -> fix etc.)
    Max 8 tool rounds to prevent infinite loops.
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
    max_tokens       = 4096 if code_turn else (400 if model == HAIKU else 800)
    current_messages = list(messages)
    MAX_TOOL_ROUNDS  = 12
    MAX_ESCALATIONS  = 5
    TOKEN_STEPS      = [800, 2048, 4096, 8192, 16000]  # escalation ladder
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
    return result


def run_projects_agent(messages: list[dict]) -> str:
    context  = _projects_context()
    memory   = _shared_memory()
    prompt   = _projects_prompt(context, memory)
    result   = _run_agent(prompt, PROJECTS_TOOLS, messages, SONNET)
    _write_back_projects(messages)
    return result


def run_iris_agent(messages: list[dict]) -> str:
    context  = _iris_context()
    memory   = _shared_memory()
    prompt   = _iris_prompt(context, memory)
    result   = _run_agent(prompt, IRIS_TOOLS, messages, SONNET)
    _write_back_iris(messages)
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
