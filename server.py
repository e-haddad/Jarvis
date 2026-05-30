# server.py
# FastAPI + WebSocket server for Jarvis HUD.
# Replaces PyQt6 signal wiring — browser connects to ws://localhost:8765/ws
#
# Run: python3.11 server.py
# HUD: http://localhost:8765

import asyncio
import json
import os
import threading
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI()

# ── Static files ───────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent)), name="static")

# ── Connection manager ─────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self._clients: list[WebSocket] = []
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._clients.append(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            if ws in self._clients:
                self._clients.remove(ws)

    async def broadcast(self, data: dict):
        msg = json.dumps(data)
        async with self._lock:
            dead = []
            for ws in self._clients:
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.remove(ws)

    def emit(self, data: dict):
        """Thread-safe emit from worker threads."""
        loop = self._loop or _server_loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(data), loop)


manager = ConnectionManager()

_server_loop = None


# ── Event helpers (called from worker threads) ─────────────────────────────────

def emit_status(status: str):
    manager.emit({"type": "status", "value": status})

def emit_user_msg(text: str):
    manager.emit({"type": "user_msg", "text": text})

def emit_jarvis_msg(text: str):
    manager.emit({"type": "jarvis_msg", "text": text})

def emit_model(model: str):
    # model is "haiku" or "sonnet"
    manager.emit({"type": "model", "value": model})

def emit_agent(agent: str):
    # agent id or "" to clear
    manager.emit({"type": "agent", "value": agent})

def emit_agent_start(agent_name: str):
    manager.emit({"type": "agent_start", "agent": agent_name})

def emit_agent_done(agent_name: str, elapsed: float):
    manager.emit({"type": "agent_done", "agent": agent_name, "elapsed": round(elapsed, 1)})

def emit_agent_timeout(agent_name: str):
    manager.emit({"type": "agent_timeout", "agent": agent_name})

def emit_agents_clear():
    manager.emit({"type": "agents_clear"})

def emit_usage():
    try:
        from usage_tracker import get_usage
        u = get_usage()
        manager.emit({"type": "usage", **u})
    except Exception:
        pass

def emit_timer(message: str, seconds: int):
    """Emit a timer panel event to the HUD."""
    import time
    manager.emit({
        "type":    "set_timer",
        "id":      int(time.time() * 1000),
        "message": message,
        "seconds": seconds,
    })

def emit_clear_log():
    manager.emit({"type": "clear_log"})


# ── Test endpoint for parallel agent HUD animation ────────────────────────────

@app.post("/test-agent-emit")
async def test_agent_emit():
    import asyncio
    async def _run():
        emit_agents_clear()
        await asyncio.sleep(0.5)
        emit_agent_start("projects")
        emit_agent_start("finance")
        await asyncio.sleep(3)
        emit_agent_done("projects", 2.8)
        await asyncio.sleep(1.5)
        emit_agent_done("finance", 4.1)
    asyncio.create_task(_run())
    return {"status": "ok"}


# ── WebSocket endpoint ─────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    # Send current usage on connect
    try:
        from usage_tracker import get_usage
        u = get_usage()
        await ws.send_text(json.dumps({"type": "usage", **u}))
    except Exception:
        pass

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            # Silent mode text input from browser
            if msg.get("type") == "silent_input":
                _handle_silent_input(msg.get("text", "").strip())
            elif msg.get("type") == "set_mode":
                paused = msg.get("value") == "silent"
                set_voice_paused(paused)
                emit_status("standby")
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:
        await manager.disconnect(ws)


# ── Voice pause flag (toggled by HUD MODE button) ─────────────────────────────

_voice_paused = False

def is_voice_paused() -> bool:
    return _voice_paused

def set_voice_paused(paused: bool):
    global _voice_paused
    _voice_paused = paused
    print(f"[Server] Voice {'paused' if paused else 'resumed'}")


# ── Silent input handler (browser text field → think()) ───────────────────────

_silent_lock = threading.Lock()

def _handle_silent_input(text: str):
    if not text:
        return
    def _run():
        from think import think
        from main import VOICE_RESTORE_PHRASES, is_exit_command
        emit_status("thinking")

        if any(phrase in text.lower() for phrase in VOICE_RESTORE_PHRASES):
            emit_status("standby")
            # Voice restore is a no-op in browser mode
            return

        if is_exit_command(text):
            emit_status("standby")
            return

        response = think(text)
        emit_jarvis_msg(response)
        emit_status("standby")
        emit_usage()

    t = threading.Thread(target=_run, daemon=True)
    t.start()


# ── Serve HUD ──────────────────────────────────────────────────────────────────

HUD_FILE = Path(__file__).parent / "jarvis-hud.html"

# ── Spotify auth helper ────────────────────────────────────────────────────────

def _get_spotify():
    """Return an authenticated spotipy client. Raises on failure."""
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.environ.get("SPOTIFY_CLIENT_ID"),
        client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET"),
        redirect_uri="http://127.0.0.1:8765/spotify/callback",
        scope="user-read-currently-playing user-read-playback-state user-modify-playback-state playlist-read-private playlist-read-collaborative",
        cache_path=str(Path(__file__).parent / ".spotify_token"),
        open_browser=False,
    ))


# ── Spotify endpoints ──────────────────────────────────────────────────────────

@app.get("/spotify/now-playing")
async def spotify_now_playing():
    """Fetch currently playing track from Spotify via spotipy."""
    try:
        from fastapi.responses import JSONResponse
        sp      = _get_spotify()
        current = sp.current_playback()
        if not current or not current.get("item"):
            return JSONResponse(None)

        item     = current["item"]
        progress = current.get("progress_ms", 0)
        duration = item.get("duration_ms", 0)
        name     = item.get("name", "Unknown")
        artist   = ", ".join(a["name"] for a in item.get("artists", []))
        album    = item.get("album", {}).get("name", "")
        images   = item.get("album", {}).get("images", [])
        art      = images[0]["url"] if images else None

        return {
            "name": name, "artist": artist, "album": album, "art": art,
            "progress": progress, "duration": duration,
            "is_playing": current.get("is_playing", False),
        }
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(None)


@app.get("/spotify/callback")
async def spotify_callback(code: str = None):
    return {"status": "ok", "message": "Spotify authenticated. You can close this tab."}


@app.post("/spotify/pause")
async def spotify_pause():
    try:
        _get_spotify().pause_playback()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/spotify/play")
async def spotify_play():
    try:
        _get_spotify().start_playback()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/spotify/next")
async def spotify_next():
    try:
        _get_spotify().next_track()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/spotify/previous")
async def spotify_previous():
    try:
        _get_spotify().previous_track()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/calendar/next-event")
async def calendar_next_event():
    """Fetch the next Google Calendar event."""
    try:
        from fastapi.responses import JSONResponse
        from jarvis_calendar import get_next_event
        result = get_next_event()
        if not result or result == "No upcoming events found.":
            return JSONResponse(None)
        # get_next_event() returns a formatted string — return it as summary
        return {"summary": result}
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(None)


@app.get("/spotify/my-playlists")
async def spotify_my_playlists():
    """Return all of the user's playlists (name + uri)."""
    try:
        sp      = _get_spotify()
        results = sp.current_user_playlists(limit=50)
        playlists = []
        while results:
            for p in results["items"]:
                if p:
                    playlists.append({"name": p["name"], "uri": p["uri"]})
            results = sp.next(results) if results.get("next") else None
        return {"playlists": playlists}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/spotify/play-track")
async def spotify_play_track(body: dict):
    """
    Search for a track/artist/playlist and start playing it.
    Body: {"query": "Kendrick Lamar Not Like Us", "type": "track"}
    type can be: track, artist, album, playlist (default: track)
    For playlist type, checks user's own playlists first before public search.
    """
    try:
        query      = body.get("query", "").strip()
        media_type = body.get("type", "track")
        if not query:
            return {"status": "error", "message": "No query provided"}

        sp = _get_spotify()

        # ── Playlist: check user's own playlists first ─────────────────────────
        if media_type == "playlist":
            query_lower = query.lower()
            results     = sp.current_user_playlists(limit=50)
            matched_uri  = None
            matched_name = None

            while results and not matched_uri:
                for p in results["items"]:
                    if p and query_lower in p["name"].lower():
                        matched_uri  = p["uri"]
                        matched_name = p["name"]
                        break
                results = sp.next(results) if results.get("next") and not matched_uri else None

            if matched_uri:
                sp.start_playback(context_uri=matched_uri)
                return {"status": "ok", "playing": matched_name}

            # Fall through to public playlist search if not found in user's library
            results = sp.search(q=query, type="playlist", limit=1)
            items   = results.get("playlists", {}).get("items", [])
            if not items:
                return {"status": "error", "message": f"No playlist found for '{query}'"}
            item = items[0]
            sp.start_playback(context_uri=item["uri"])
            return {"status": "ok", "playing": item.get("name", query)}

        # ── Track / artist / album ─────────────────────────────────────────────
        results = sp.search(q=query, type=media_type, limit=1)
        items   = results.get(f"{media_type}s", {}).get("items", [])

        if not items:
            return {"status": "error", "message": f"Nothing found for '{query}'"}

        item = items[0]

        if media_type == "track":
            sp.start_playback(uris=[item["uri"]])
            name   = item.get("name", "")
            artist = ", ".join(a["name"] for a in item.get("artists", []))
            return {"status": "ok", "playing": f"{name} by {artist}"}

        elif media_type == "artist":
            sp.start_playback(context_uri=item["uri"])
            return {"status": "ok", "playing": f"Artist radio for {item.get('name', '')}"}

        elif media_type == "album":
            sp.start_playback(context_uri=item["uri"])
            return {"status": "ok", "playing": item.get("name", query)}

        return {"status": "error", "message": f"Unsupported type: {media_type}"}

    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/")
async def serve_hud():
    return FileResponse(HUD_FILE)


# ── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    global _server_loop
    _server_loop = asyncio.get_event_loop()
    manager.set_loop(_server_loop)


def start_server(host="0.0.0.0", port=8765):
    """Start uvicorn in a daemon thread — called from main.py."""
    def _run():
        uvicorn.run(app, host=host, port=port, log_level="warning")
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    print(f"[Jarvis] HUD → http://localhost:{port}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
