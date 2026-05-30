# agent_bus.py
# Parallel multi-agent architecture for Jarvis.
#
# Where orchestrator.py classifies a turn into ONE specialist agent, the bus runs
# SEVERAL specialists concurrently. A MasterOrchestrator makes a single Sonnet
# call to decide which agents to spawn and what focused task to hand each, then
# fans them out over a thread-pool executor (the existing _run_agent in agents.py
# is synchronous and blocking) and merges the results.
#
# This is gated behind USE_PARALLEL_AGENTS in think.py and off by default.

import os
import json
import time
import asyncio
import threading
from dataclasses import dataclass, field

import anthropic

# Agent runner + tool subsets live in agents.py.
# System prompts live in orchestrator.py (static strings, no circular import).
from agents import (
    _run_agent, CAREER_TOOLS, PROJECTS_TOOLS, IRIS_TOOLS,
    _write_back_career, _write_back_projects, _write_back_iris,
    _write_back_second_brain,
)
from orchestrator import AGENT_SYSTEM_PROMPTS, get_agent_system_prompt

# HUD live-status emitters. Imported with a fallback so the bus runs headless
# (tests, cron) when the server module / WebSocket isn't available.
try:
    from server import (
        emit_agent_start, emit_agent_done, emit_agent_timeout, emit_agents_clear,
    )
except Exception:
    def emit_agent_start(*a, **k):   pass
    def emit_agent_done(*a, **k):    pass
    def emit_agent_timeout(*a, **k): pass
    def emit_agents_clear(*a, **k):  pass

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

HAIKU  = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"

# Hard wall-clock cap per agent so one slow specialist can't stall the fan-out.
AGENT_TIMEOUT_SECONDS = 240

# Per-agent tool-round caps (overrides _run_agent's default of 12). Agents that
# tend to over-search get a tighter leash; everything else uses the default.
AGENT_MAX_ROUNDS = {
    "researcher": 5,
    "architect":  6,
}


# ── Shared State ─────────────────────────────────────────────────────────────

@dataclass
class AgentContext:
    """Shared state threaded through a fan-out of agents."""
    user_input: str
    intent: str
    results: dict[str, str] = field(default_factory=dict)      # agent_name -> output
    scratchpad: dict[str, str] = field(default_factory=dict)   # shared working memory
    spawned_by: str | None = None                              # None if from orchestrator


# ── Tool Subsets ─────────────────────────────────────────────────────────────
# Light-weight, executor-supported tools for the agents that don't have a
# dedicated subset in agents.py. Only tools _execute_agent_tool understands are
# listed here so a spawned agent never calls something that can't run.

_WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": "Search the web for current or uncertain info.",
    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
}

_READ_NOTE_TOOL = {
    "name": "read_note",
    "description": "Read a note from Edward's vault by query.",
    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
}

_READ_FILE_DIRECT_TOOL = {
    "name": "read_file_direct",
    "description": "Read any file by exact path.",
    "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
}

_FETCH_URL_TOOL = {
    "name": "fetch_url_summary",
    "description": (
        "Fetch a URL and summarize its content using AI. "
        "Use mode='job' for job postings, mode='article' for news/blog posts, "
        "mode='general' for anything else."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The full URL to fetch and summarize"},
            "mode": {
                "type": "string",
                "enum": ["general", "job", "article"],
                "description": "Summary mode. 'job' for job postings, 'article' for news/blogs, 'general' otherwise.",
            },
        },
        "required": ["url"],
    },
}

RESEARCH_TOOLS = [_WEB_SEARCH_TOOL, _READ_NOTE_TOOL, _FETCH_URL_TOOL]
ARCHITECT_TOOLS = [_READ_FILE_DIRECT_TOOL, _READ_NOTE_TOOL, _WEB_SEARCH_TOOL]
GENERAL_TOOLS = [_WEB_SEARCH_TOOL, _READ_NOTE_TOOL]

# agent name -> tool subset
TOOL_SETS = {
    "architect":  ARCHITECT_TOOLS,
    "researcher": RESEARCH_TOOLS,
    "coder":      PROJECTS_TOOLS,
    "career":     CAREER_TOOLS,
    "projects":   PROJECTS_TOOLS,
    "iris":       IRIS_TOOLS,
    "finance":    RESEARCH_TOOLS,
    "general":    GENERAL_TOOLS,
}

# Agents that should run on Haiku (cheap/fast) rather than Sonnet.
_HAIKU_AGENTS = {"general"}


# ── Async Runners ────────────────────────────────────────────────────────────

async def run_agent_async(name, task, context, model, system_prompt, tools,
                          max_rounds=None, messages=None):
    """
    Run a single agent without blocking the event loop.

    _run_agent is synchronous and makes blocking HTTP calls, so it's pushed onto
    the default thread-pool executor. Pass an explicit `messages` list to run a
    full conversation, or `task` for a single user turn. `max_rounds` caps the
    agent's tool loop (forwarded to _run_agent). Returns an (name, result) tuple.
    """
    loop = asyncio.get_running_loop()
    msgs = messages if messages is not None else [{"role": "user", "content": task}]
    emit_agent_start(name)
    started = time.time()
    try:
        result = await loop.run_in_executor(
            None, _run_agent, system_prompt, tools, msgs, model, max_rounds
        )
    except Exception as e:
        result = f"{name} agent failed: {e}"
    # NOTE: on timeout, wait_for cancels this coroutine — the await above raises
    # CancelledError (a BaseException), which skips this done-emit and propagates
    # to spawn_agents, where the timeout marker is emitted instead.
    emit_agent_done(name, time.time() - started)
    return (name, result)


async def spawn_agents(agent_tasks: list[dict]) -> dict:
    """
    Run a batch of agents concurrently, each behind a per-agent timeout.

    Each task: {"name", "system_prompt", "tools", "messages", "model",
                optional "max_rounds"}.
    Returns {name: result}. A timed-out agent yields a marker string instead of
    stalling the batch.

    Note: asyncio.wait_for cancels the awaiting coroutine on timeout, but the
    underlying executor thread keeps running to completion in the background —
    its result is simply discarded. With only a handful of agents this is fine.
    """
    async def _one(t):
        name = t["name"]
        coro = run_agent_async(
            name, None, None, t["model"], t["system_prompt"], t["tools"],
            max_rounds=t.get("max_rounds"), messages=t["messages"],
        )
        try:
            return await asyncio.wait_for(coro, timeout=AGENT_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            print(f"[AgentBus] {name} timed out after {AGENT_TIMEOUT_SECONDS}s")
            emit_agent_timeout(name)
            return (name, f"[{name} agent timed out after {AGENT_TIMEOUT_SECONDS}s]")
        except Exception as e:
            return (name, f"{name} agent failed: {e}")

    pairs = await asyncio.gather(*[_one(t) for t in agent_tasks])
    return {name: result for name, result in pairs}


def run_parallel(agent_tasks: list[dict]) -> dict[str, str]:
    """
    Synchronous wrapper around spawn_agents so it's callable from the existing
    sync think.py. Returns {name: result}.
    """
    if not agent_tasks:
        return {}
    return asyncio.run(spawn_agents(agent_tasks))


# ── Master Orchestrator ──────────────────────────────────────────────────────

_DISPATCH_SYSTEM = (
    "You are a master orchestrator for Jarvis, Edward Haddad's AI assistant. "
    "Given the user input decide which specialist agents to run in parallel and "
    "what focused task to give each. Available agents: "
    "architect (designs technical solutions), "
    "researcher (web search, URL fetch, synthesis), "
    "coder (implements code changes via Claude Code), "
    "career (job applications, cover letters, resume tailoring), "
    "projects (Jarvis/ChipIn/Billed/Iris status and planning), "
    "iris (smart home, Pi, gesture), "
    "finance (crypto, spending, portfolio), "
    "general (everything else). "
    'Return a JSON array of {"agent": name, "task": description} objects. '
    "Only spawn agents that are genuinely needed. For simple queries spawn only "
    "general. For complex multi-domain queries spawn multiple."
)


_SYNTH_SYSTEM = (
    "You are Jarvis, Edward Haddad's AI assistant. Multiple specialist agents have "
    "responded to his request. Synthesize their outputs into one concise, natural "
    "spoken response. No headers, no labels, no bullet points. Speak as Jarvis would "
    "— confident, direct, British butler tone. 2-4 sentences max unless the task "
    "genuinely requires more detail."
)


def _synthesize(user_input: str, results: dict[str, str]) -> str:
    """
    Fold multiple agent outputs into one clean spoken Jarvis response via Haiku.
    Falls back to labeled concatenation if the call fails.
    """
    labeled = "\n\n".join(
        f"[{name}] {out.strip()}" for name, out in results.items() if out and out.strip()
    )
    try:
        resp = client.messages.create(
            model=HAIKU,
            max_tokens=600,
            system=_SYNTH_SYSTEM,
            messages=[{
                "role": "user",
                "content": f'Edward asked: "{user_input}"\n\nAgent outputs:\n\n{labeled}',
            }],
        )
        for block in resp.content:
            if block.type == "text" and block.text.strip():
                return block.text.strip()
        return labeled
    except Exception:
        return labeled


class MasterOrchestrator:
    """Decides a fan-out of specialist agents and runs them in parallel."""

    def __init__(self):
        self.client = client
        self.model = SONNET

    def dispatch(self, text: str, history: list[dict]) -> str:
        emit_agents_clear()  # reset HUD agent rows to idle for this new turn
        plan = self._plan(text, history)
        agent_tasks = self._build_tasks(plan, text, history)
        print(f"[AgentBus] Spawning: {[t['name'] for t in agent_tasks]}")
        results = run_parallel(agent_tasks)

        # Persist session notes for any specialist that produced output — off the
        # hot path so the spoken reply isn't blocked by vault writes / Haiku calls.
        self._fire_write_backs(text, results, history)

        clean = {k: v for k, v in results.items() if v and v.strip()}
        if not clean:
            return "Nothing came back from the agents."
        # Single agent → no synthesis overhead, return its answer verbatim.
        if len(clean) == 1:
            return next(iter(clean.values()))
        # Multiple agents → fold their outputs into one clean spoken response.
        return _synthesize(text, clean)

    # ── planning ──
    def _plan(self, text: str, history: list[dict]) -> list[dict]:
        """Single Sonnet call → list of {"agent", "task"} dicts."""
        snippet = self._history_snippet(history)
        user_content = f"{snippet}User input: {text}" if snippet else f"User input: {text}"
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=_DISPATCH_SYSTEM,
                messages=[{"role": "user", "content": user_content}],
            )
            raw = ""
            for block in resp.content:
                if block.type == "text":
                    raw = block.text.strip()
                    break
            return self._parse_plan(raw, text)
        except Exception:
            # Any failure → safe single-agent fallback
            return [{"agent": "general", "task": text}]

    @staticmethod
    def _parse_plan(raw: str, text: str) -> list[dict]:
        """Parse the JSON array, tolerating code fences and stray prose."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            # drop an optional leading 'json' language tag
            if cleaned[:4].lower() == "json":
                cleaned = cleaned[4:]
        # Slice to the outermost JSON array if there's surrounding text
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start:end + 1]
        try:
            parsed = json.loads(cleaned)
        except Exception:
            return [{"agent": "general", "task": text}]
        if not isinstance(parsed, list):
            return [{"agent": "general", "task": text}]
        plan = []
        for item in parsed:
            if isinstance(item, dict) and item.get("agent"):
                plan.append({
                    "agent": str(item["agent"]).strip().lower(),
                    "task": str(item.get("task", text)).strip() or text,
                })
        return plan or [{"agent": "general", "task": text}]

    # ── task building ──
    def _build_tasks(self, plan: list[dict], text: str, history: list[dict]) -> list[dict]:
        """Map planned agents to system prompts + tools, skipping unknown names."""
        agent_tasks = []
        seen = set()
        for item in plan:
            name = item["agent"]
            if name not in AGENT_SYSTEM_PROMPTS or name not in TOOL_SETS:
                continue
            if name in seen:  # collapse duplicate agents into one
                continue
            seen.add(name)
            task = item["task"]
            content = f'{task}\n\nEdward\'s original message: "{text}"'
            agent_tasks.append({
                "name": name,
                "system_prompt": get_agent_system_prompt(name),
                "tools": TOOL_SETS[name],
                "messages": [{"role": "user", "content": content}],
                "model": HAIKU if name in _HAIKU_AGENTS else SONNET,
                "max_rounds": AGENT_MAX_ROUNDS.get(name),
            })
        if not agent_tasks:
            agent_tasks.append({
                "name": "general",
                "system_prompt": get_agent_system_prompt("general"),
                "tools": TOOL_SETS["general"],
                "messages": [{"role": "user", "content": text}],
                "model": HAIKU,
                "max_rounds": AGENT_MAX_ROUNDS.get("general"),
            })
        return agent_tasks

    # ── write-back ──
    @staticmethod
    def _fire_write_backs(text: str, results: dict[str, str], history: list[dict]) -> None:
        """
        Persist session notes for the career/projects/iris specialists in a
        daemon thread. Each write-back gets a minimal messages list (recent
        history for context + this turn's user input and the agent's result);
        agents with no result are skipped.
        """
        writers = {
            "career":   _write_back_career,
            "projects": _write_back_projects,
            "iris":     _write_back_iris,
        }
        base = [m for m in (history or []) if isinstance(m.get("content"), str)]

        def _run():
            for name, writer in writers.items():
                result = results.get(name)
                if not result or not result.strip():
                    continue
                messages = base + [
                    {"role": "user",      "content": text},
                    {"role": "assistant", "content": result},
                ]
                try:
                    writer(messages)
                except Exception as e:
                    print(f"[agent_bus] write-back {name} failed: {e}")
            # Cross-domain write-back for all agents that ran
            for agent_name in results:
                if results[agent_name]:
                    messages = base + [
                        {"role": "user",      "content": text},
                        {"role": "assistant", "content": results[agent_name]},
                    ]
                    try:
                        _write_back_second_brain(messages, agent_name)
                    except Exception as e:
                        print(f"[agent_bus] second brain write-back {agent_name} failed: {e}")

        if any(results.get(n) and results[n].strip() for n in writers):
            threading.Thread(target=_run, daemon=True).start()

    @staticmethod
    def _history_snippet(history: list[dict] | None) -> str:
        if not history:
            return ""
        lines = []
        for msg in history[-4:]:
            if isinstance(msg.get("content"), str):
                role = "Edward" if msg.get("role") == "user" else "Jarvis"
                lines.append(f"{role}: {msg['content'][:120]}")
        return ("Recent context:\n" + "\n".join(lines) + "\n\n") if lines else ""


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "What's the state of my projects and what jobs should I apply to this week?"
    print(MasterOrchestrator().dispatch(q, []))
