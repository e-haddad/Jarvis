# Jarvis

> *"At your service, sir."*

A fully local AI voice assistant built on Mac Studio M4 Max — wake word activation, real-time speech recognition, parallel multi-agent intelligence, and a live browser HUD. Every line written from scratch.

---

## Overview

Jarvis is a production-grade personal AI assistant running entirely on local hardware. It listens for a wake word, transcribes speech locally with Whisper, routes queries through a multi-agent orchestration layer powered by Claude, and responds via ElevenLabs neural TTS — all in real time.

The system has grown through 14 development phases from a simple voice loop into a parallel multi-agent architecture with 22+ integrations, a live browser HUD with real-time agent status, and remote access from any device on the network.

This is not a demo or a tutorial project. It runs 24/7, auto-starts on login, handles real tasks daily, and gets new capabilities every week.

---

## Architecture

```
Wake Word (OpenWakeWord)
        │
        ▼
Speech Recognition (Whisper turbo — local)
        │
        ▼
MasterOrchestrator (Claude Sonnet)
        │
        ├── Intent classification
        └── Dispatch plan → parallel agent spawn
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
Researcher   Coder      Career
  Agent       Agent      Agent
    └───────────┴───────────┘
                │
                ▼
       Synthesis (Claude Haiku)
                │
                ▼
     ElevenLabs Flash v2.5 TTS
      (Kokoro ONNX fallback)
```

**Voice pipeline:** OpenWakeWord → Whisper turbo (local, fp16) → VAD silence detection → orchestrator → parallel agents → sentence-level streaming TTS

**Agent routing:**
- Short commands → General Jarvis (Haiku, low latency)
- Complex queries (≥6 words) → MasterOrchestrator spawns specialist agents in parallel via `asyncio.gather`
- Single-agent results spoken directly — synthesis layer only fires for multi-agent turns

**Token routing:**
- Haiku: routine turns (400 tokens)
- Sonnet: agent turns and orchestration (800 tokens)
- Code turns: 4096 tokens

---

## Specialist Agents

| Agent | Role | Tools |
|---|---|---|
| **Researcher** | Web search, URL summarization, news, information gathering | `web_search`, `fetch_url_summary`, `get_news`, `get_crypto_price` |
| **Architect** | System design, technical planning, code review | `read_file_direct`, `list_folder`, `run_claude_code` |
| **Coder** | Code generation, file writes, execution, debugging | `read_file_direct`, `write_file`, `run_python`, `run_terminal_command`, `run_claude_code` |
| **Career** | Job search, resume, applications, cover letters | Vault reads, `web_search`, `fetch_url_summary`, `draft_email` |
| **Finance** | Market data, crypto, financial awareness | `get_crypto_price`, `web_search` |
| **Projects** | Project-specific context and code tasks | Full code tools + project vault |
| **Iris** | Iris smart home project on Raspberry Pi 5 | Code tools + SSH via terminal |
| **General** | Everything else — weather, calendar, email, Spotify | All general tools |

Each agent runs independently with its own tool executor loop (up to 8 rounds), a 60-second timeout, and live status updates streamed to the HUD.

---

## Integrations

| Category | Integration |
|---|---|
| **AI / LLM** | Claude API (Haiku + Sonnet), Claude Code subprocess |
| **Speech** | OpenWakeWord, Whisper turbo (local), ElevenLabs Flash v2.5, Kokoro ONNX v1.0 (fallback) |
| **Google** | Gmail API (read + draft), Google Calendar API (read + write) |
| **Music** | Spotify (now playing, playback controls, play by track/artist/album/playlist, personal playlist lookup) |
| **Smart Home** | Tuya API (via Iris project on Raspberry Pi 5) |
| **Search & Web** | Brave Search API, Open-Meteo weather, CoinGecko crypto |
| **Knowledge Base** | Obsidian vault — read, write, append, inbox, consolidation |
| **System** | Terminal runner (whitelisted), filesystem R/W, app launcher, browser launcher |
| **Infrastructure** | FastAPI + WebSocket HUD, Tailscale remote access, launchd auto-start, Git auto-commit + GitHub push |

---

## Browser HUD

A self-contained real-time dashboard served at `localhost:8765`. Panels are draggable, collapsible, and position-persistent via localStorage.

**Panels:**

- **System** — live status, mic detection, mode indicators
- **Conversation** — full transcript of voice turns, streaming output
- **Agents** — real-time parallel agent status with pulse animations; shows which agents are active, what tools they're calling, and when they complete
- **Spotify** — album art, track and artist, scrubbing progress bar, ⏮ ⏸/▶ ⏭ controls (polls every 5s)
- **Timer** — countdown ring stack; yellows at 60s, flashes green on completion, auto-removes
- **Usage** — Claude token spend, ElevenLabs character tracking

Mobile responsive — stacks vertically on screens ≤768px. Accessible remotely at `100.75.165.120:8765` via Tailscale from any device.

---

## Capabilities

**Voice control**
- Wake word always listening ("hey jarvis") — OpenWakeWord, fully local
- 30ms VAD frames, 1.2s silence detection, 30s recording ceiling
- Hallucination filter on Whisper output

**Information**
- Real-time web search via Brave Search
- Current weather — Open-Meteo (location-aware)
- Live news briefing with freshness filter
- Cryptocurrency prices via CoinGecko
- Startup brief generated in parallel thread on wake

**Calendar & Email**
- Read upcoming events, query by date, create events — Google Calendar
- Read Gmail, scan for job application emails
- Draft emails by voice — creates Gmail drafts via API (does not send without confirmation)

**Music**
- Spotify playback — play by track, artist, album, or playlist by voice
- Personal playlist lookup by name
- Full playback controls — pause, play, next, previous
- Now playing in HUD with album art and progress bar

**Code & Terminal**
- Voice-activated coding tasks routed to Coder/Architect agents
- `run_claude_code()` — hands off to Claude Code subprocess for complex refactors
- `run_terminal_command()` — whitelisted shell execution with 30s timeout and block-pattern safety model
- Auto-backup before every file write, auto-commit + auto-push to GitHub after every change

**Knowledge Base**
- Reads and writes to Obsidian vault
- Agent write-back: after multi-turn sessions, Haiku extracts 3–5 insight bullets automatically
- Note consolidation: Sonnet rewrites notes after 3 session logs accumulate
- Auto-capture: keyword-gated background thread adds voice captures to Obsidian Inbox

**Reminders & Timers**
- Set reminders by voice — fast-path intercept before Claude to minimize latency
- Timer panel in HUD with countdown ring, stacks multiple concurrent timers

**System**
- Open macOS applications by voice
- Open URLs and perform in-site searches (YouTube, Reddit, Amazon, GitHub, Spotify, Google)

---

## Technical Stack

| Layer | Technology |
|---|---|
| **Hardware** | Mac Studio M4 Max 36GB |
| **Language** | Python 3.11 |
| **LLM** | Anthropic Claude API — Haiku 3.5 / Sonnet 4.6 |
| **Wake Word** | OpenWakeWord |
| **STT** | Whisper turbo (local, fp16=False) |
| **TTS Primary** | ElevenLabs Flash v2.5 (streaming, sentence-level) |
| **TTS Fallback** | Kokoro ONNX v1.0 (local, bm_george voice) |
| **VAD** | webrtcvad |
| **Server** | FastAPI + WebSocket |
| **Spotify** | spotipy |
| **Search** | Brave Search API |
| **Weather** | Open-Meteo (free, no key) |
| **Crypto** | CoinGecko free API |
| **Google** | Google Calendar API + Gmail API (OAuth2) |
| **Vault** | Obsidian (filesystem read/write) |
| **Remote** | Tailscale |
| **Service** | launchd (auto-start on login) |
| **Version Control** | Git + GitHub (auto-commit on write) |

---

## File Structure

```
Jarvis/
├── main.py                  # Entry point — FastAPI + voice loop + daemon threads
├── server.py                # FastAPI routes + WebSocket + Spotify endpoints
├── listen.py                # VAD recording + OpenWakeWord
├── transcribe.py            # Whisper turbo + hallucination filter
├── think.py                 # Claude API + tool calling + streaming + auto-capture
├── speak.py                 # ElevenLabs + Kokoro fallback + sentence streaming
├── agents.py                # Four sequential agents + chained tool loop (8 rounds)
├── orchestrator.py          # Intent classifier + agent system prompts
├── agent_bus.py             # AgentBus + MasterOrchestrator + parallel async runner
├── vault.py                 # Obsidian read/write
├── filesystem.py            # File R/W + auto-backup + auto-commit + terminal runner
├── search.py                # Web search + weather + news + crypto + Spotify + email + Claude Code
├── memory.py                # Jarvis_Memory.md + personality traits
├── jarvis_calendar.py       # Google Calendar + Gmail OAuth2
├── context.py               # Selective project context loader
├── briefing.py              # Startup brief generation
├── gmail_pulls.py           # Gmail job scan + calendar pulls (every 3h)
├── usage_tracker.py         # Claude + ElevenLabs usage tracking
├── jarvis-hud.html          # Self-contained browser HUD
├── permissions.json         # Filesystem whitelist
├── com.edward.jarvis.plist  # launchd service config
├── btc_price.py             # Bitcoin price utility
├── .backups/                # Auto-backup directory
└── static/
    └── icon.png             # App icon
```

---

## Development Phases

| Phase | What Was Built |
|---|---|
| 1 | Wake word detection, Whisper STT, ElevenLabs TTS, voice pipeline |
| 2 | Obsidian vault integration — read/write/append |
| 3 | Permission-scoped filesystem access |
| 4 | Claude API, tool calling, web search, full pipeline |
| 5 | Memory system, personality, Google Calendar, context, startup brief, multi-agent foundation |
| 6 | Proactive second brain, ElevenLabs, silent mode, usage tracking, code tools |
| 6.5 | Streaming responses, natural briefing, browser HUD, Tailscale remote access |
| 7 | Agent write-back, note consolidation, auto-capture, Gmail + calendar pulls, launchd, desktop/phone apps |
| 8 | Agentic coding loop, chained tool calls, auto-backup, git integration, GitHub auto-push |
| 9 | News briefing, crypto prices, reminder/timer panel, app launcher, Spotify panel |
| 10 | Gmail draft creation via API |
| 11 | Claude Code pipeline — `run_claude_code()`, heavy coding task classifier |
| 12 | Terminal command runner — whitelist safety model, wired into all agents |
| 13 | Spotify voice playback — personal playlist lookup, in-site search |
| **14** | **Parallel multi-agent architecture — MasterOrchestrator, 8 specialist agents, async gather, per-agent timeouts, synthesis layer** |

---

## Running Jarvis

**Auto-start (launchd):** Starts automatically on login via `com.edward.jarvis.plist`.

**Manual start:**
```bash
cd ~/Desktop/Projects/Jarvis
source ~/.zshrc
python3.11 main.py
```

**Text-only mode (no mic):**
```bash
python3.11 main.py --text
```

**Server only (HUD without voice loop):**
```bash
python3.11 main.py --silent
```

**HUD:**
- Local: `http://localhost:8765`
- Remote: `http://100.75.165.120:8765` (Tailscale)

**Standard restart after file changes:**
```bash
launchctl unload ~/Library/LaunchAgents/com.edward.jarvis.plist
lsof -ti :8765 | xargs kill -9 2>/dev/null
sleep 2
source ~/.zshrc
python3.11 main.py
```

---

## Environment Variables

Required in `~/.zshrc` and `com.edward.jarvis.plist`:

```
ANTHROPIC_API_KEY
BRAVE_API_KEY
ELEVENLABS_API_KEY
SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET
GITHUB_TOKEN
```

Google OAuth credentials: `google_credentials.json` + `google_token.json` (not committed)
Spotify token cache: `.spotify_token` (not committed)

---

## What's Next

- Cover letter generator — feeds from vault resume + job posting URL
- Finance agent — stock watchlist, portfolio awareness
- Screenshot + Claude vision — `take_screenshot()` piped to Claude vision API
- ElevenLabs auto-fallback at low character balance
- People.md vault contact list for email drafting by name

---

*Built by Edward Haddad — ECE, Oakland University, Class of 2026.*
*Running 24/7 on Mac Studio M4 Max, Royal Oak, Michigan.*