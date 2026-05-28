# server.py
# FastAPI + WebSocket server for Jarvis HUD.
# Replaces PyQt6 signal wiring — browser connects to ws://localhost:8765/ws
#
# Run: python3.11 server.py
# HUD: http://localhost:8765

import asyncio
import json
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
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(data), self._loop)


manager = ConnectionManager()


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

@app.get("/spotify/now-playing")
async def spotify_now_playing():
    """Fetch currently playing track from Spotify via spotipy."""
    try:
        import os
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        from fastapi.responses import JSONResponse

        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=os.environ.get("SPOTIFY_CLIENT_ID"),
            client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET"),
            redirect_uri="http://localhost:8765/spotify/callback",
            scope="user-read-currently-playing user-read-playback-state user-modify-playback-state",
            cache_path=str(Path(__file__).parent / ".spotify_token"),
            open_browser=False,
        ))
        current = sp.currently_playing()
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

        return {"name": name, "artist": artist, "album": album, "art": art, "progress": progress, "duration": duration, "is_playing": current.get("is_playing", False)}
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(None)


@app.get("/spotify/callback")
async def spotify_callback(code: str = None):
    return {"status": "ok", "message": "Spotify authenticated. You can close this tab."}


@app.post("/spotify/pause")
async def spotify_pause():
    try:
        import os, spotipy
        from spotipy.oauth2 import SpotifyOAuth
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=os.environ.get("SPOTIFY_CLIENT_ID"),
            client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET"),
            redirect_uri="http://127.0.0.1:8765/spotify/callback",
            scope="user-read-currently-playing user-read-playback-state user-modify-playback-state",
            cache_path=str(Path(__file__).parent / ".spotify_token"),
            open_browser=False,
        ))
        sp.pause_playback()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/spotify/play")
async def spotify_play():
    try:
        import os, spotipy
        from spotipy.oauth2 import SpotifyOAuth
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=os.environ.get("SPOTIFY_CLIENT_ID"),
            client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET"),
            redirect_uri="http://127.0.0.1:8765/spotify/callback",
            scope="user-read-currently-playing user-read-playback-state user-modify-playback-state",
            cache_path=str(Path(__file__).parent / ".spotify_token"),
            open_browser=False,
        ))
        sp.start_playback()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/spotify/next")
async def spotify_next():
    try:
        import os, spotipy
        from spotipy.oauth2 import SpotifyOAuth
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=os.environ.get("SPOTIFY_CLIENT_ID"),
            client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET"),
            redirect_uri="http://127.0.0.1:8765/spotify/callback",
            scope="user-read-currently-playing user-read-playback-state user-modify-playback-state",
            cache_path=str(Path(__file__).parent / ".spotify_token"),
            open_browser=False,
        ))
        sp.next_track()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/spotify/previous")
async def spotify_previous():
    try:
        import os, spotipy
        from spotipy.oauth2 import SpotifyOAuth
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=os.environ.get("SPOTIFY_CLIENT_ID"),
            client_secret=os.environ.get("SPOTIFY_CLIENT_SECRET"),
            redirect_uri="http://127.0.0.1:8765/spotify/callback",
            scope="user-read-currently-playing user-read-playback-state user-modify-playback-state",
            cache_path=str(Path(__file__).parent / ".spotify_token"),
            open_browser=False,
        ))
        sp.previous_track()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/")
async def serve_hud():
    return FileResponse(HUD_FILE)


# ── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    manager.set_loop(asyncio.get_event_loop())


def start_server(host="0.0.0.0", port=8765):
    """Start uvicorn in a daemon thread — called from main.py."""
    def _run():
        uvicorn.run(app, host=host, port=port, log_level="warning")
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    print(f"[Jarvis] HUD → http://localhost:{port}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")
