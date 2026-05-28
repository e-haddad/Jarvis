# listen.py
# Audio capture with two modes:
#   1. wait_for_wake_word() — always-on wake word detection ("hey jarvis")
#   2. record_command()     — VAD-based recording, stops on silence
#
# record_command() uses webrtcvad instead of a fixed duration.
# It listens until SILENCE_DURATION seconds of silence after speech,
# so any length sentence is captured cleanly.
#
# Dependencies: pip3.11 install webrtcvad

import numpy as np
import sounddevice as sd
import webrtcvad
import collections
import wave
import io
from scipy.io.wavfile import write
from openwakeword.model import Model as OWWModel

SAMPLE_RATE    = 16000
FILENAME       = "input.wav"

# VAD settings
VAD_AGGRESSIVENESS = 2        # 0–3: higher = more aggressive filtering of non-speech
FRAME_DURATION_MS  = 30       # frame size for VAD (10, 20, or 30ms only)
FRAME_SIZE         = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # samples per frame

SILENCE_DURATION   = 1.2      # seconds of silence before stopping recording
SILENCE_FRAMES     = int(SILENCE_DURATION * 1000 / FRAME_DURATION_MS)

MIN_SPEECH_FRAMES  = 5        # ignore very short noises (< ~150ms)
MAX_RECORD_SECONDS = 30       # hard ceiling to prevent runaway recording

# Wake word settings
OWW_CHUNK_SIZE = 1280         # 80ms at 16kHz
THRESHOLD      = 0.5

# Load wake word model once at import time
oww_model = OWWModel(wakeword_models=["hey_jarvis_v0.1"], inference_framework="onnx")

# VAD instance
_vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)


# ── Wake Word ──────────────────────────────────────────────────────────────────

def wait_for_wake_word():
    """Continuously listen for 'hey jarvis'. Blocks until detected."""
    print("Standby — waiting for 'Hey Jarvis'...")
    detected = False

    def audio_callback(indata, frames, time_info, status):
        nonlocal detected
        if detected:
            return
        audio_chunk = indata[:, 0].astype(np.int16)
        prediction = oww_model.predict(audio_chunk)
        for model_name, score in prediction.items():
            if "jarvis" in model_name.lower() and score > THRESHOLD:
                detected = True

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=OWW_CHUNK_SIZE,
        callback=audio_callback,
    ):
        while not detected:
            sd.sleep(50)

    oww_model.reset()


# ── VAD-Based Command Recording ────────────────────────────────────────────────

def record_command() -> str:
    """
    Record a voice command using voice activity detection.
    Starts capturing immediately, stops after SILENCE_DURATION seconds of silence
    following detected speech. No fixed duration — captures full sentences.
    Returns path to saved WAV file.
    """
    print("Listening...")

    frames_collected = []
    speech_frames    = 0
    silence_ring     = collections.deque(maxlen=SILENCE_FRAMES)
    max_frames       = int(MAX_RECORD_SECONDS * 1000 / FRAME_DURATION_MS)
    speech_started   = False
    done             = False

    def callback(indata, frame_count, time_info, status):
        nonlocal speech_frames, speech_started, done

        if done:
            return

        # webrtcvad requires exactly FRAME_SIZE samples as bytes
        audio = indata[:, 0].astype(np.int16)

        # Process in VAD-sized chunks
        for i in range(0, len(audio) - FRAME_SIZE + 1, FRAME_SIZE):
            frame = audio[i:i + FRAME_SIZE]
            frame_bytes = frame.tobytes()

            try:
                is_speech = _vad.is_speech(frame_bytes, SAMPLE_RATE)
            except Exception:
                is_speech = False

            frames_collected.append(frame.copy())
            silence_ring.append(0 if is_speech else 1)

            if is_speech:
                speech_frames += 1
                if not speech_started and speech_frames >= MIN_SPEECH_FRAMES:
                    speech_started = True

            # Stop conditions
            if speech_started:
                # Enough silence after speech
                if len(silence_ring) == SILENCE_FRAMES and all(silence_ring):
                    done = True
                    return

            # Hard ceiling
            if len(frames_collected) >= max_frames:
                done = True
                return

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=FRAME_SIZE,
        callback=callback,
    ):
        while not done:
            sd.sleep(10)

    if not frames_collected:
        return FILENAME

    # Stitch frames and write WAV
    audio_data = np.concatenate(frames_collected)
    write(FILENAME, SAMPLE_RATE, audio_data)
    return FILENAME


if __name__ == "__main__":
    print("Testing VAD recording — speak a long sentence...")
    f = record_command()
    print(f"Saved to {f}")
