# main.py
# Entry point for Jarvis.
# Flow: standby → "hey jarvis" → boot brief → conversation loop → exit
#
# Voice mode: python3.11 main.py
# Text mode:  python3.11 main.py --text
#
# HUD: http://localhost:8765  (or http://<tailscale-ip>:8765 from any device)
# Silent mode: type in the browser HUD text input

import sys
import threading

from think import think, close_session, reset_history, HAIKU, SONNET
from speak import speak, speak_sentence
from briefing import get_startup_brief
from server import start_server, emit_status, emit_user_msg, emit_jarvis_msg, \
                   emit_model, emit_agent, emit_usage, emit_clear_log

EXIT_TRIGGERS = {"bye", "goodbye", "stop", "exit", "quit", "shut down", "shutdown"}

VOICE_RESTORE_PHRASES = {
    "jarvis you can speak now",
    "you can speak now",
    "switch to voice",
    "voice mode",
    "turn voice on",
    "enable voice",
}


def is_exit_command(text: str) -> bool:
    lowered = text.lower()
    if "jarvis" not in lowered:
        return False
    return any(trigger in lowered for trigger in EXIT_TRIGGERS)


def _activate():
    import threading

    brief_result = [None]

    def _fetch_brief():
        try:
            brief_result[0] = get_startup_brief()
        except Exception:
            brief_result[0] = ""

    # Fetch brief in background while speaking activation phrase
    t = threading.Thread(target=_fetch_brief, daemon=True)
    t.start()

    speak("At your service, sir.")
    emit_jarvis_msg("At your service, sir.")

    # Wait for brief (should be ready or nearly ready by now)
    t.join(timeout=6)
    brief = brief_result[0] or ""
    if brief:
        speak(brief)
        emit_jarvis_msg(brief)


# ── Model / intent helpers ─────────────────────────────────────────────────────

def _route_and_emit(text: str) -> str:
    """Classify intent + model, emit to HUD, return intent string."""
    from think import _route_model
    from orchestrator import classify_intent
    intent = classify_intent(text)
    model  = _route_model(text)
    emit_model("sonnet" if model == SONNET else "haiku")
    emit_agent(intent if intent != "general" else "")
    return intent


# ── Text Mode (terminal fallback, no HUD) ─────────────────────────────────────

def run_text_mode():
    print("\nJarvis text mode. Type your message. 'bye jarvis' to exit.\n")
    _activate()
    reset_history()

    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            close_session()
            break
        if not text:
            continue
        if is_exit_command(text):
            speak("Jarvis offline.")
            print("Jarvis: Jarvis offline.")
            close_session()
            break
        response = think(text)
        print(f"Jarvis: {response}\n")
        speak(response)


# ── Voice loop ─────────────────────────────────────────────────────────────────

def run_voice_loop():
    from listen import wait_for_wake_word, record_command
    from transcribe import transcribe
    from server import is_voice_paused

    while True:
        emit_status("standby")
        wait_for_wake_word()

        # If silent mode is on, ignore the wake word
        if is_voice_paused():
            continue

        emit_status("listening")
        emit_clear_log()
        reset_history()
        _activate()

        while True:
            filename = record_command()

            # If mode was switched to silent mid-conversation, stop listening
            if is_voice_paused():
                emit_status("standby")
                break

            emit_status("thinking")

            text = transcribe(filename)
            if not text:
                emit_status("listening")
                continue

            emit_user_msg(text)

            if is_exit_command(text):
                emit_status("speaking")
                speak("Jarvis offline.")
                emit_jarvis_msg("Jarvis offline.")
                close_session()
                emit_model("haiku")
                emit_agent("")
                break

            _route_and_emit(text)
            response = think(text, on_sentence=speak_sentence)

            emit_status("speaking")
            emit_jarvis_msg(response)
            emit_usage()
            emit_agent("")
            emit_model("haiku")
            emit_status("listening")


# ── Main ───────────────────────────────────────────────────────────────────────

def _mic_available() -> bool:
    """Check if any input device is available before starting voice loop."""
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        count = pa.get_device_count()
        for i in range(count):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                pa.terminate()
                return True
        pa.terminate()
    except Exception:
        pass
    return False


def main():
    if "--text" in sys.argv:
        run_text_mode()
        return

    # Start FastAPI server (serves HUD + WebSocket)
    start_server(host="0.0.0.0", port=8765)

    # Start periodic Gmail + calendar pulls
    try:
        from gmail_pulls import start_periodic_pulls
        start_periodic_pulls()
    except Exception as e:
        print(f"[Pulls] Failed to start: {e}")

    # Start stock price monitoring
    try:
        from finance_monitor import get_monitor
        from speak import speak

        def handle_finance_alert(symbol: str, price: float, change_pct: float, direction: str):
            """Voice alert handler for stock price movements."""
            message = f"Alert: {symbol} {direction} {abs(change_pct):.1f}% to ${price:,.2f}"
            speak(message)
            emit_jarvis_msg(message)

        monitor = get_monitor()
        monitor.emit_alert = handle_finance_alert
        monitor.start()
    except Exception as e:
        print(f"[StockMonitor] Failed to start: {e}")

    # --silent flag or no mic → server-only mode (browser HUD + typing, no voice)
    if "--silent" in sys.argv or not _mic_available():
        if "--silent" not in sys.argv:
            print("[Jarvis] No microphone detected — running in server-only mode.")
            print("[Jarvis] HUD available at http://localhost:8765")
        else:
            print("[Jarvis] Silent mode — HUD available at http://localhost:8765")
        # Keep process alive
        try:
            import time
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n[Jarvis] Shutting down.")
            close_session()
        return

    # Voice loop runs on main thread
    try:
        run_voice_loop()
    except KeyboardInterrupt:
        print("\n[Jarvis] Shutting down.")
        close_session()


if __name__ == "__main__":
    main()
