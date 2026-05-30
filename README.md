<div align="center">

# 🤖 Jarvis

**Personal AI built by Edward Haddad — inspired by Tony Stark's assistant.**

*Wake word → transcription → parallel agents → voice response. All local, all live.*

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Claude](https://img.shields.io/badge/Claude-Sonnet%20%26%20Haiku-D97706?style=flat-square&logo=anthropic&logoColor=white)](https://anthropic.com)
[![ElevenLabs](https://img.shields.io/badge/ElevenLabs-Flash%20v2.5-000000?style=flat-square)](https://elevenlabs.io)
[![Whisper](https://img.shields.io/badge/Whisper-Turbo-412991?style=flat-square&logo=openai&logoColor=white)](https://github.com/openai/whisper)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-macOS-lightgrey?style=flat-square&logo=apple)](https://www.apple.com/macos/)

</div>

---

## ✨ What Is Jarvis?

Jarvis is a fully voice-driven, locally-run personal AI assistant with a live browser HUD, parallel multi-agent architecture, and deep integration into my daily workflow.

It's not a chatbot wrapper. Every layer — wake word detection, transcription, intent routing, agent orchestration, tool execution, and voice synthesis — is purpose-built and wired together from scratch.

The pipeline runs end-to-end in **under two seconds**: wake word → Whisper transcription → intent classification → parallel specialist agents → streamed ElevenLabs voice response.

---

## 🎬 Pipeline Overview

```
🎤 Mic  →  OpenWakeWord  →  Whisper Turbo  →  MasterOrchestrator
                                                      │
                    ┌─────────────────────────────────┤
                    ▼         ▼          ▼             ▼
               Career      Coder    Researcher    Architect    …
                    │         │          │             │
                    └─────────┴──────────┴─────────────┘
                                    │
                            Synthesizer (Sonnet)
                                    │
                    ElevenLabs Flash v2.5  →  🔊 Speaker
                                    │
                            WebSocket HUD  →  🌐 Browser
```

---

## 🚀 Features

### Core Voice Pipeline
- **Always-on wake word** — "Hey Jarvis" via OpenWakeWord, zero-CPU standby
- **Whisper Turbo transcription** — fast, accurate, runs locally
- **Sentence-level streaming TTS** — ElevenLabs Flash v2.5 starts playing before the full response is generated; Kokoro ONNX offline fallback included
- **Silent mode** — disable voice, interact entirely through the browser HUD text input

### Multi-Agent Architecture
- **MasterOrchestrator** — Sonnet-powered router that fans a request out across multiple specialists in parallel, then synthesizes a unified response
- **8 specialist agents** — each with its own system prompt, tool subset, and vault context
- **Dual-model routing** — Haiku for fast/cheap turns (calendar, vault reads, quick Q&A); Sonnet for reasoning, coding, multi-step tasks
- **Per-agent timeouts** — one slow agent never stalls the rest

### Live Browser HUD
- Real-time pipeline status: standby → listening → thinking → speaking
- Parallel agent panel with pulse animations
- Full conversation log
- Text input for silent mode
- Accessible remotely via Tailscale: `http://<tailscale-ip>:8765`

### Tools & Integrations
- 🔍 **Web search** — live queries via search API
- 📅 **Google Calendar** — read today's events, upcoming schedule, create events by voice
- 📬 **Gmail** — periodic background pulls, inbox summaries, draft emails
- 🎵 **Spotify** — voice-controlled playback
- 💰 **Crypto** — live BTC price
- 📝 **Obsidian vault** — read notes, append to notes, add to inbox, list vault files
- 🧠 **Persistent memory** — cross-session facts, persona traits, second brain context
- 💻 **Terminal** — run shell commands and scripts by voice
- ⚡ **Claude Code** — hand heavy multi-file coding tasks to a capable sub-agent
- 🌐 **URL summarizer** — fetch and summarize any web page (job postings, articles)

### Intelligence Layer
- **Keyword-first intent classification** — fast path with zero API cost; LLM fallback only for ambiguous inputs
- **Vault-aware context injection** — each agent gets the relevant slice of the Obsidian vault before responding
- **Pushback protocol** — Jarvis has opinions and voices them; tunable pushback level
- **Startup brief** — weather, calendar, and news summary spoken at activation

---

## 🏗️ Architecture

### Specialist Agents

| Agent | Responsibility | Model |
|---|---|---|
| **Career** | Job applications, resume, cover letters, outreach, OPT/visa | Sonnet |
| **Coder** | Code implementation, file edits, debugging, Claude Code handoff | Sonnet |
| **Architect** | Technical design, system architecture, trade-off analysis | Sonnet |
| **Researcher** | Web search, URL summarization, fact gathering | Sonnet |
| **Projects** | Jarvis, Iris, ChipIn, Billed — project status and decisions | Sonnet |
| **Iris** | Smart home, gesture engine, Raspberry Pi, Tuya devices | Sonnet |
| **Finance** | Crypto prices, financial queries | Haiku |
| **General** | Weather, calendar, memory, Spotify, conversation | Haiku |

### Key Files

```
jarvis/
├── main.py              # Entry point — voice loop, text mode, server bootstrap
├── think.py             # Core reasoning — Claude API, tool calling, model routing
├── orchestrator.py      # Intent classifier — keyword fast path + Haiku fallback
├── agent_bus.py         # Parallel multi-agent bus — MasterOrchestrator + fan-out
├── agents.py            # Specialist agents — prompts, tool subsets, vault context
├── listen.py            # Wake word detection (OpenWakeWord) + command recording
├── transcribe.py        # Whisper Turbo transcription
├── speak.py             # TTS — ElevenLabs Flash v2.5 streaming + Kokoro fallback
├── server.py            # FastAPI server — WebSocket HUD, REST API
├── jarvis-hud.html      # Browser HUD — agent panel, status, conversation log
├── vault.py             # Obsidian vault tools — read/write notes, inbox
├── memory.py            # Persistent cross-session memory and persona traits
├── briefing.py          # Startup brief — weather + calendar + news
├── jarvis_calendar.py   # Google Calendar integration
├── gmail_pulls.py       # Background Gmail polling
├── search.py            # Web search, weather, crypto, Spotify, URL fetch, Claude Code
├── filesystem.py        # File system tools — list/read/create files, terminal
├── context.py           # Vault context builder — per-intent knowledge injection
├── usage_tracker.py     # API token and cost tracking
└── btc_price.py         # Live Bitcoin price
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | Anthropic Claude (Sonnet 4.6 + Haiku 4.5) |
| **Wake Word** | OpenWakeWord |
| **Transcription** | OpenAI Whisper Turbo (local) |
| **TTS (primary)** | ElevenLabs Flash v2.5 — custom British voice |
| **TTS (fallback)** | Kokoro ONNX — fully offline |
| **Audio I/O** | sounddevice, PyAudio, pydub |
| **Web Server** | FastAPI + WebSocket (uvicorn) |
| **Calendar** | Google Calendar API (oauth2) |
| **Email** | Gmail API (oauth2) |
| **Music** | Spotify Web API |
| **Smart Home** | Tuya Cloud API (via Iris) |
| **Vault** | Obsidian markdown files |
| **Hardware** | Mac Studio M4 Max 36GB |
| **Language** | Python 3.11 |

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.11
- macOS (tested on Mac Studio M4 Max; adaptable to Linux)
- A microphone for voice mode
- Accounts and API keys for: Anthropic, ElevenLabs, Google (Calendar + Gmail), Spotify

### 1. Clone the repo

```bash
git clone https://github.com/e-haddad/Jarvis.git
cd Jarvis
```

### 2. Install dependencies

```bash
pip install anthropic openai-whisper sounddevice numpy scipy pyaudio pydub \
            openwakeword fastapi uvicorn websockets requests \
            google-api-python-client google-auth-oauthlib \
            spotipy kokoro-onnx
```

> **Kokoro models** — download `kokoro-v1.0.onnx` and `voices-v1.0.bin` from the [Kokoro ONNX releases](https://github.com/thewh1teagle/kokoro-onnx/releases) and place them in the project root.

### 3. Set environment variables

Add to your `~/.zshrc` (or `.bashrc`):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export ELEVENLABS_API_KEY="..."
export SPOTIFY_CLIENT_ID="..."
export SPOTIFY_CLIENT_SECRET="..."
export SPOTIFY_REDIRECT_URI="http://localhost:8888/callback"
```

### 4. Google API credentials

- Create a project in [Google Cloud Console](https://console.cloud.google.com/)
- Enable Calendar API and Gmail API
- Download `credentials.json` and place it in the project root
- On first run, Jarvis will open a browser for OAuth — token saved as `google_token.json`

### 5. Run Jarvis

```bash
# Voice mode (microphone required)
python3.11 main.py

# Text mode (no mic needed)
python3.11 main.py --text

# Silent mode (HUD only — no voice output or mic)
python3.11 main.py --silent
```

Open the HUD at [http://localhost:8765](http://localhost:8765)

---

## 🔑 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | Claude API key |
| `ELEVENLABS_API_KEY` | ✅ | ElevenLabs TTS key (Kokoro fallback used if missing) |
| `SPOTIFY_CLIENT_ID` | ⚡ Optional | Spotify playback control |
| `SPOTIFY_CLIENT_SECRET` | ⚡ Optional | Spotify playback control |
| `SPOTIFY_REDIRECT_URI` | ⚡ Optional | Spotify OAuth redirect |

Google credentials are file-based (`google_credentials.json` + `google_token.json`).

---

## 💬 Usage Examples

```
"Hey Jarvis"                          → Activates, speaks startup brief

"What's on my calendar today?"        → Reads today's Google Calendar events
"Add a meeting Friday at 2pm"         → Creates a calendar event by voice

"Search for the latest on WWDC 2025"  → Live web search, spoken summary
"What's the Bitcoin price?"           → Live crypto price

"Play ma7kameh on Spotify"            → Starts playlist via Spotify API

"Read my Jarvis note"                 → Reads Obsidian vault note aloud
"Add to my inbox: fix the HUD agent pulse animation"  → Saves to Obsidian inbox

"Write a Python script that..."       → Coder agent + Claude Code for heavy tasks
"Help me tailor my resume for Wind River"  → Career agent with job context

"Turn on the living room lights"      → Routes to Iris agent → Tuya smart plugs
```

---

## 🔗 Related Projects

**Jarvis** is the central hub that integrates with two companion projects:

### 🖐️ Iris — Gesture Smart Home
Computer vision smart home controller running on Raspberry Pi 5. Uses MediaPipe hand tracking and a camera to detect gestures (fist, pinch, two-hand swipe) and map them to Tuya smart plug commands via a Flask dashboard. Jarvis routes all smart home queries to a dedicated Iris specialist agent with full project context.

### 🃏 ChipIn — Poker Chip Wallet
Mobile app for tracking poker chip balances across games with friends. Firebase backend, Stage 1 complete. Jarvis has a Projects agent with ChipIn context for development decisions.

### 🧾 Billed — Bill Splitting
Smart bill splitting app for groups. Concept fully defined. Tracked in the Projects agent context.

---

## 🗺️ Roadmap

- [ ] Jarvis demo video (wake word → query → HUD → voice response)
- [ ] Local LLM mode via Ollama (full offline fallback, no API dependency)
- [ ] Vision — screenshot analysis, screen reading, image queries
- [ ] Proactive alerts — "you have a meeting in 10 minutes" without being asked
- [ ] Tailscale remote wake — trigger Jarvis from phone, anywhere
- [ ] iOS/Android companion app
- [ ] Iris full integration — two-way state sync (Jarvis asks Iris for device status)
- [ ] ChipIn backend — Firebase rules, session persistence, live balance sync
- [ ] Billed MVP — group management and split calculation engine

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built by [Edward Haddad](https://github.com/e-haddad) · ECE Graduate · Oakland University

*"Sometimes you gotta run before you can walk."*

</div>
