# Jarvis — Project Roadmap

---

## Current Status

**Phase: Phase 2 — Obsidian Vault Integration**
Status: Functionally complete. Core vault operations (inbox creation, note reading, note appending, folder listing) are implemented and wired into the main pipeline. Known issues exist (see below) but the integration is live and working end-to-end.

---

## What's Working

- **Wake word detection** — `listen.py` — OpenWakeWord model (`hey_jarvis_v0.1`) runs a continuous always-on audio stream at 16 kHz and activates the session when "Hey Jarvis" is detected above a 0.5 confidence threshold.
- **Command recording** — `listen.py` — After wake word fires, records a 5-second audio window and writes it to `input.wav`.
- **Speech-to-text transcription** — `transcribe.py` — Whisper `small` model transcribes `input.wav` to text with FP16 warnings suppressed.
- **LLM reasoning** — `think.py` — Routes all non-vault queries to Ollama (`gemma3:1b`) with a persona-locked system prompt. Vault commands are intercepted before the LLM is called. Generates LLM titles for inbox notes via a dedicated `_generate_title()` call.
- **Text-to-speech** — `speak.py` — Kokoro ONNX v1.0 with `af_heart` voice at 1.0x speed, with a warmup inference run at import time to prevent the first response from being clipped.
- **Session lifecycle** — `main.py` — Full standby → wake → conversation loop → exit phrase → standby cycle. Exit triggers: "bye / goodbye / stop / exit / quit / shut down / shutdown" + "jarvis".
- **Vault: add to inbox** — `vault.py` — Creates a new timestamped Markdown note in `Inbox/` with an LLM-generated title. Filename format: `YYYY-MM-DD <Title>.md`.
- **Vault: read note** — `vault.py` — Fuzzy-matches a spoken keyword to a `(folder, filename)` pair via `NOTE_MAP` and reads the file contents aloud.
- **Vault: append to note** — `vault.py` — Appends a timestamped `---` entry to an existing matched note.
- **Vault: list notes** — `vault.py` — Lists all `.md` filenames in a matched vault folder (Inbox, Projects, Career, Knowledge, Life).

---

## Known Issues / Pending

- **Typo in NOTE_MAP** — `vault.py` line 29 — `"Job Appllications.md"` has a double `l`. Will silently fail to find or write that file unless the actual filename on disk also has the typo.
- **Fixed-length recording window** — `listen.py` — `COMMAND_DURATION = 5` seconds is hardcoded. No silence/VAD detection, so short commands waste time and anything longer than 5 seconds gets cut off. Needs voice activity detection (VAD).
- **No conversation memory** — `think.py` — Every query is sent to Ollama as a single-turn message. There is no message history passed between turns, so Jarvis cannot reference earlier parts of the conversation.
- **No Ollama error handling** — `think.py` — If Ollama is not running or the model is unavailable, the call will raise an unhandled exception and crash the session.
- **Overly broad vault command matching** — `vault.py` — The `"list"` keyword in `handle_vault_command()` will intercept any utterance that contains the word "list," even if the user is asking a general question (e.g., "list the pros and cons of X"). Needs tighter intent matching.
- **Vault search is keyword-only** — `vault.py` — `_resolve_note()` only matches against a fixed `NOTE_MAP`. There is no ability to search within note content or discover notes not in the map.
- **No requirements.txt enforcement** — Project root — `requirements.txt` exists but has not been verified against the current import surface (`openwakeword`, `kokoro_onnx`, `ollama`, `whisper`, `sounddevice`, `scipy`, `numpy`).

---

## How to Run

```bash
# Terminal 1 — start the Ollama backend
ollama serve

# Terminal 2 — navigate to the project and activate the environment if needed
cd ~/Desktop/Projects/Jarvis

# Terminal 2 — launch Jarvis
python main.py
```

---

## Phase 2 — Obsidian Vault Integration

**Goals:** Give Jarvis read/write access to the Obsidian vault so Edward can capture ideas, query notes, and update project logs entirely by voice.

**Target voice commands:**
- "Hey Jarvis, add to inbox: [idea]" → creates a new titled note in `Inbox/`
- "Hey Jarvis, read my Jarvis note" → reads `Projects/Jarvis.md` aloud
- "Hey Jarvis, update my goals note: [content]" → appends to `Life/Goals 2026.md`
- "Hey Jarvis, what notes are in Career?" → lists all files in `Career/`

**Implementation approach:** All vault logic lives in a single module. `think.py` intercepts vault-intent commands before they reach Ollama. The `handle_vault_command()` dispatcher pattern keeps routing logic clean. LLM title generation for inbox notes uses a dedicated low-cost Ollama call with `_generate_title()`.

**Vault location:** `~/Desktop/OBS/Edward/`

**Module:** `vault.py` *(built and active)*

**Remaining work:** Fix the `Job Applications` typo, tighten the `"list"` intent guard, add VAD-based recording to handle variable-length commands, and add basic error handling for missing files.

---

## Phase 3 — Permission-Scoped Filesystem Access

**Goals:** Allow Jarvis to read, write, move, and summarize files anywhere on disk — but only within folders the user has explicitly whitelisted. No action outside the permission envelope.

**Permission config file concept:** A YAML or JSON file (e.g., `permissions.yaml`) committed to the project root. Each entry declares a path and the allowed operations (`read`, `write`, `move`, `delete`). Jarvis loads this at startup and refuses any filesystem action that falls outside it.

```yaml
# Example permissions.yaml
allowed:
  - path: ~/Desktop/Projects/
    ops: [read, write]
  - path: ~/Downloads/
    ops: [read, move]
  - path: ~/Desktop/OBS/Edward/
    ops: [read, write]
```

**Target capabilities:**
- "Hey Jarvis, summarize the PDF in my Downloads folder"
- "Hey Jarvis, move all files older than 30 days from Downloads to Archive"
- "Hey Jarvis, what's in my Projects folder?"
- "Hey Jarvis, open the Jarvis project folder"

---

## Phase 4 — Mac Studio Deployment

**Hardware upgrade context:** Current development is on a MacBook. Target deployment platform is a Mac Studio, which provides significantly more RAM and sustained compute headroom for always-on inference without thermal throttling.

**Model upgrade:** Swap `gemma3:1b` for `gemma3:27b` or a 70B-class model via Ollama. Larger models will handle multi-step reasoning, code generation, and nuanced vault queries without needing to escalate to a cloud API.

**Always-on background service goal:** Jarvis runs as a persistent `launchd` service on the Mac Studio — starts on boot, survives log-outs, and is always ready to respond to the wake word without a terminal window open. No manual startup commands required.

---

## Phase 5 — Multi-Agent Architecture

**Full vision:** Jarvis becomes an orchestrator that dispatches intent to specialized subagents. Each subagent owns a domain and exposes a clean interface. The orchestrator (`main.py` / `think.py`) classifies the intent and routes accordingly.

**Subagents:**

- **Career agent** — tracks job applications, OPT/visa deadlines, resume versions, and interview prep. Reads/writes `Career/` in the vault.
- **Schedule agent** — reads and writes calendar events, sets reminders, surfaces upcoming deadlines. Integrates with Google Calendar or a local ICS file.
- **Obsidian agent** — extended vault operations: full-text search across all notes, cross-note linking, weekly review generation, summarizing recent inbox entries.
- **Iris smart home agent** — controls the Iris home automation system. Handles lights, sensors, and routines via local API calls.
- **Code generation agent** — handles coding tasks, debugging, and technical lookups. Has access to project directories under the permission config and can write files directly.

**Hybrid escalation design:**

Local models handle all routine, low-stakes tasks — fast, free, and private. The Claude API is invoked only when complexity exceeds what a local model can reliably handle (multi-step reasoning, long-context synthesis, code review, nuanced judgment).

```
Intent received
    │
    ├─ Routine (single-step, structured) ──► Local Gemma (27B / 70B on Mac Studio)
    │
    ├─ Moderate reasoning needed ──────────► Local Gemma with chain-of-thought prompt
    │
    └─ Complex / high-stakes ──────────────► Claude API (see Cost Architecture)
```

---

## Cost Architecture

**Tiered routing plan:**

| Tier | Model | Use case |
|------|-------|----------|
| 1 | Local Gemma 3 (27B or 70B) | All routine queries, vault ops, home automation, quick lookups |
| 2 | Claude Haiku | Simple cloud-escalated actions — fast, cheap classification or formatting tasks |
| 3 | Claude Sonnet | Reasoning-heavy tasks — code review, long-context summarization, career decisions |

**Design principles:**
- Local model handles the vast majority of daily volume (target: >90% of queries stay local).
- Prompt caching on the Claude API eliminates redundant token costs for repeated system prompts and long vault context.
- Haiku is the default escalation target; Sonnet is invoked only when Haiku's output is insufficient.

**Estimated monthly cost:** $5–15/month with prompt caching enabled, assuming typical daily usage patterns.

---

## Weekly Debrief Format

```
Jarvis — Week of [Date]

* What was worked on this week
* Key decisions made
* Current status / where things stand
* What's next
```

---

## Agent Instructions

Read this file at the start of every session before taking any action. Update the relevant section at the end of every session to reflect what changed.
