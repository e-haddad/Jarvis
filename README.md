# Jarvis

> A fully local, always-on AI assistant built for a Mac Studio. Voice-activated, multi-agent, with a live browser HUD and Obsidian vault integration.

---

## Overview

Jarvis is a personal AI system inspired by Tony Stark's assistant — built from scratch by [Edward Haddad](https://github.com/e-haddad). It runs entirely on a Mac Studio M4 Max, activates on a custom wake word, processes speech locally, routes queries through a parallel multi-agent architecture powered by Claude, and responds in a synthesized British voice via ElevenLabs.

It's not a wrapper around a chatbot. It's a second brain with memory, tools, opinions, and full access to a live Obsidian vault.

---

## Demo

> Wake word → transcription → parallel agents → spoken response → live HUD

*(Demo video coming soon)*

---

## Architecture

```
Microphone
    │
    ▼
OpenWakeWord  ─────────────────── "Hey Jarvis" detected
    │
    ▼
webrtcvad  ──────────────────────  VAD-based command recording (silence-terminated)
    │
    ▼
Whisper (turbo)  ────────────────  Local speech-to-text transcription
    │
    ▼
MasterOrchestrator  ─────────────  Sonnet 4.6 decides which agents to fan out to
    │
    ├─── Career Agent   ──────────  Job search, resume, applications, OPT/visa
    ├─── Projects Agent ──────────  Jarvis, Iris, ChipIn, Billed — code and architecture
    ├─── Iris Agent     ──────────  Gesture smart home, Raspberry Pi, Tuya devices
    ├─── Architect Agent ─────────  System design, technical planning
    ├─── Researcher Agent ────────  Web search, URL summarization
    └─── General Agent  ──────────  Weather, calendar, memory, Q&A, chat
    │
    ▼
Synthesizer  ────────────────────  Results merged into a single spoken response
    │
    ▼
ElevenLabs Flash v2.5  ──────────  Custom British voice (Jarvis 1.0)
    │                               Kokoro ONNX fallback if ElevenLabs is unavailable
    ▼
Browser HUD (port 8765)  ────────  Real-time status, agent panel, conversation log
```

---

## Features

**Voice Pipeline**
- Always-on wake word detection via OpenWakeWord (`hey_jarvis_v0.1`)
- VAD-based command recording — silence-terminated, no fixed duration, 30s hard cap
- Whisper turbo transcription (local, no cloud)
- ElevenLabs Flash v2.5 TTS — custom British male voice, sentence-level streaming
- Kokoro ONNX v1.0 local fallback (`bm_george`, `en-gb`)

**Multi-Agent Architecture**
- `MasterOrchestrator` uses Claude Sonnet to decide which specialists to spawn per turn
- Agents run in parallel via `asyncio` thread-pool fan-out
- Per-agent 60s timeout — one slow agent never stalls the batch
- Keyword-first intent classification (no API cost on obvious queries); Haiku fallback for ambiguous ones
- Model routing: Haiku 4.5 for fast/simple turns, Sonnet 4.6 for complex reasoning and code

**Tools**
- Web search via Brave Search API
- Real-time weather via Open-Meteo (no key required)
- News headlines via Brave Search
- Crypto prices via CoinGecko
- Google Calendar — read events, create events, daily briefing
- Gmail integration — background polling, new message summaries
- Spotify — play music, control playback by voice
- Reminders — spoken alerts with HUD timer panel
- App launcher — open any macOS app by voice
- URL summarization — fetch and summarize any URL (job postings, articles, etc.)
- Terminal command execution (whitelisted paths)
- Claude Code integration — hands off complex coding tasks to a sub-agent

**Obsidian Vault Integration**
- Full read/write access to `~/Desktop/OBS/Edward/` vault
- Add to inbox (LLM-generated note titles), read notes, append to notes, list folders
- Vault-backed memory for Career, Projects, Iris, and Second Brain context
- Each specialist agent loads its own vault section as live context

**Persistent Memory**
- Markdown-based memory across sessions (`Jarvis_Memory.md`)
- Categories: PROJECTS, PREFS, FACTS, GOALS, CORRECTIONS, PERSONA
- Auto-memory: detects `"I prefer"`, `"going forward"`, etc. and saves silently
- Explicit memory: `"Remember that..."` pins a fact with a 📌 tag
- Personality traits adjustable at runtime: sarcasm, length, formality, pushback

**Startup Briefing**
- On wake, silently checks calendar, inbox count, and last session topic
- Proactive checks: stale projects, job application staleness, weekly review nudge
- Surfaces only what's actionable — stays silent otherwise

**Browser HUD**
- FastAPI + WebSocket server at `localhost:8765`
- Real-time status indicator: standby → listening → thinking → speaking
- Live conversation log (user and Jarvis turns)
- Parallel agent panel with pulse animations and per-agent elapsed time
- Model indicator (Haiku vs Sonnet), token usage tracker
- Silent mode toggle — switch from voice to browser text input mid-session
- Spotify now-playing widget with album art
- Tailscale remote access: `100.75.165.120:8765`

**Modes**
- `python3.11 main.py` — full voice mode
- `python3.11 main.py --text` — terminal text mode, no HUD
- `python3.11 main.py --silent` — server-only mode, HUD text input only
- Auto-fallback to server-only if no microphone is detected

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| LLM | Anthropic Claude (Haiku 4.5 + Sonnet 4.6) |
| Wake Word | OpenWakeWord (`hey_jarvis_v0.1`, ONNX) |
| Voice Activity Detection | webrtcvad |
| Speech-to-Text | OpenAI Whisper (turbo, local) |
| Text-to-Speech | ElevenLabs Flash v2.5 + Kokoro ONNX v1.0 (fallback) |
| Backend Server | FastAPI + uvicorn |
| Real-time UI | WebSocket + vanilla JS browser HUD |
| Calendar | Google Calendar API |
| Email | Gmail API |
| Music | Spotipy (Spotify Web API) |
| Web Search | Brave Search API |
| Crypto | CoinGecko API (no key) |
| Weather | Open-Meteo API (no key) |
| Memory / Vault | Obsidian Markdown vault (read/write) |
| Audio | sounddevice, pydub, numpy |
| Hardware | Mac Studio M4 Max 36GB |

---

## Project Structure

```
Jarvis/
├── main.py              # Entry point — voice loop, text mode, silent mode
├── listen.py            # Wake word detection + VAD-based command recording
├── transcribe.py        # Whisper speech-to-text
├── think.py             # Core reasoning — tool calling, model routing, agent dispatch
├── speak.py             # ElevenLabs TTS with Kokoro ONNX fallback
├── orchestrator.py      # Intent classifier — keyword-first, Haiku fallback
├── agents.py            # Specialist agents — career, projects, iris, general
├── agent_bus.py         # Parallel agent execution — MasterOrchestrator, fan-out, merge
├── server.py            # FastAPI + WebSocket server — HUD, silent mode, Spotify endpoints
├── jarvis-hud.html      # Browser HUD — real-time status, agent panel, conversation log
├── vault.py             # Obsidian vault operations — read, write, append, list
├── memory.py            # Persistent cross-session memory
├── briefing.py          # Startup briefing — calendar, inbox, proactive checks
├── search.py            # Web search, news, crypto, weather, reminders, Spotify, apps
├── filesystem.py        # Permission-scoped filesystem access
├── jarvis_calendar.py   # Google Calendar read/write
├── gmail_pulls.py       # Background Gmail polling
├── context.py           # Per-intent vault context loader
├── usage_tracker.py     # Token usage tracking across sessions
├── btc_price.py         # Standalone crypto price utility
├── kokoro-v1.0.onnx     # Kokoro TTS model weights
├── voices-v1.0.bin      # Kokoro voice pack
└── permissions.json     # Filesystem permission envelope
```

---

## Setup

### Prerequisites

- macOS (tested on Mac Studio M4 Max)
- Python 3.11
- Homebrew

### Install dependencies

```bash
pip3.11 install anthropic openai-whisper sounddevice webrtcvad openwakeword \
               kokoro-onnx fastapi uvicorn spotipy google-api-python-client \
               google-auth-oauthlib requests pydub numpy scipy tzlocal
```

### Environment variables

Add to `~/.zshrc`:

```bash
export ANTHROPIC_API_KEY="your_key"
export ELEVENLABS_API_KEY="your_key"
export BRAVE_API_KEY="your_key"
export SPOTIFY_CLIENT_ID="your_id"
export SPOTIFY_CLIENT_SECRET="your_secret"
```

### Google Calendar / Gmail

Place `google_credentials.json` (OAuth 2.0 client credentials) in the project root. On first run, a browser window will open for authorization and cache the token locally.

### Run

```bash
cd ~/Desktop/Projects/Jarvis
python3.11 main.py
```

HUD available at `http://localhost:8765`

---

## Roadmap

| Phase | Status | Description |
|---|---|---|
| 1 — Voice Pipeline | ✅ Complete | Wake word, VAD recording, Whisper, Kokoro TTS |
| 2 — Vault Integration | ✅ Complete | Obsidian read/write, inbox, notes, folders |
| 3 — Filesystem Access | ✅ Complete | Permission-scoped file ops, Claude Code integration |
| 4 — Mac Studio Deployment | ✅ Complete | Always-on service, Claude API, model routing |
| 5 — Multi-Agent Architecture | ✅ Complete | Parallel agents, MasterOrchestrator, agent bus |
| 6 — Browser HUD | ✅ Complete | FastAPI server, WebSocket, agent panel, silent mode |
| 7 — Persistent Memory | ✅ Complete | Cross-session memory, auto-save, personality traits |
| 8 — Tool Integrations | ✅ Complete | Calendar, Gmail, Spotify, search, crypto, weather |
| 9 — ElevenLabs TTS | ✅ Complete | Custom voice, sentence streaming, Kokoro fallback |
| 10 — Proactive Briefing | ✅ Complete | Startup checks, stale project nudges, job staleness |
| iOS Companion App | 🔜 Planned | Remote voice input + HUD on iPhone |
| Kokoro Quality Pass | 🔜 Planned | Improve fallback prosody and latency |
| Agent Memory Write-back | 🔜 Planned | Agents write session summaries to vault automatically |

---

## About

Built by [Edward Haddad](https://github.com/e-haddad) — ECE graduate, Oakland University. Jarvis is both a daily productivity tool and a portfolio project demonstrating end-to-end AI systems engineering: local inference, cloud LLMs, real-time audio pipelines, multi-agent orchestration, and full-stack tooling.

> *"The suit and I are one."*
