# speak.py
# Text-to-speech using ElevenLabs Flash v2.5 (primary) with Kokoro ONNX fallback.
#
# Strategy:
#   - Sentence-level streaming: ElevenLabs generates and plays sentence by sentence
#   - Each sentence starts playing as soon as its first audio chunk arrives
#   - If ElevenLabs is unreachable or the key is missing, falls back to Kokoro silently
#
# Environment:
#   ELEVENLABS_API_KEY — in ~/.zshrc
#
# Voice: Jarvis 1.0 (dKNC4ONh2V6LGP0SDD4M) — custom British male, deep, conversational
# Model: eleven_flash_v2_5 — ultra low latency, conversational use case

import os
import re
import numpy as np
import sounddevice as sd
import requests

# ── Config ─────────────────────────────────────────────────────────────────────

ELEVENLABS_VOICE_ID = "dKNC4ONh2V6LGP0SDD4M"  # Jarvis 1.0 — custom British male
ELEVENLABS_MODEL    = "eleven_flash_v2_5"
ELEVENLABS_URL      = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream"

VOICE_SETTINGS = {
    "stability":         0.55,   # lower = more expressive, higher = more consistent
    "similarity_boost":  0.82,   # how closely to match the original voice
    "style":             0.0,   # style exaggeration — keep moderate for conversation
    "use_speaker_boost": True,
}

# Silence durations in seconds (kept from Kokoro implementation)
PAUSE_SENTENCE = 0.0
PAUSE_QUESTION = 0.05

# Hard cap on spoken sentences
MAX_SPOKEN_SENTENCES = 2

# Sample rate ElevenLabs streams at (mp3 decoded to PCM)
ELEVENLABS_SAMPLE_RATE = 44100


# ── Kokoro fallback ────────────────────────────────────────────────────────────

_kokoro = None

def _get_kokoro():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
        _kokoro.create("ready", voice="bm_george", speed=1.07, lang="en-gb")
    return _kokoro


# ── Text processing ────────────────────────────────────────────────────────────

def _sanitize(text: str) -> str:
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"`{1,3}[^`]*`{1,3}", "", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"\b\d+[\.\)]\s+", " ", text)
    text = re.sub(r"^\s*[-•*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s[-•*]\s", " ", text)
    text = text.replace("—", ",").replace("–", ",")
    text = re.sub(r"\s*,\s*,", ",", text)
    text = re.sub(r"\s+,", ",", text)
    text = text.replace("...", " ").replace("…", " ")
    text = re.sub(r"[,;]{2,}", ",", text)
    text = re.sub(r"\.{2,}", ".", text)

    def drop_long_parens(m):
        content = m.group(1)
        return content if len(content.split()) <= 8 else ""
    text = re.sub(r"\(([^)]+)\)", drop_long_parens, text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if text and text[-1] not in ".!?":
        text += "."
    return text if text else "Done."


def _split_sentences(text: str) -> list[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _limit_sentences(text: str) -> str:
    sentences = _split_sentences(text)
    if len(sentences) <= MAX_SPOKEN_SENTENCES:
        return text
    kept = sentences[:MAX_SPOKEN_SENTENCES - 1] + [sentences[-1]]
    return " ".join(kept[:MAX_SPOKEN_SENTENCES])


def _silence(seconds: float, sample_rate: int) -> np.ndarray:
    return np.zeros((int(seconds * sample_rate), 1), dtype=np.float32)


# ── ElevenLabs streaming ───────────────────────────────────────────────────────

def _stream_sentence_elevenlabs(sentence: str) -> np.ndarray | None:
    """
    Stream a single sentence from ElevenLabs, decode MP3 chunks on the fly,
    return as float32 numpy array. Returns None on any failure.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        return None

    headers = {
        "xi-api-key":   api_key,
        "Content-Type": "application/json",
        "Accept":       "audio/mpeg",
    }
    payload = {
        "text":           sentence,
        "model_id":       ELEVENLABS_MODEL,
        "voice_settings": VOICE_SETTINGS,
        "output_format":  "mp3_44100_128",
    }

    try:
        resp = requests.post(
            ELEVENLABS_URL,
            headers=headers,
            json=payload,
            stream=True,
            timeout=10,
        )
        if resp.status_code != 200:
            return None

        # Collect all MP3 chunks
        chunks = b"".join(resp.iter_content(chunk_size=4096))
        if not chunks:
            return None

        # Decode MP3 → float32 PCM
        return _decode_mp3(chunks)

    except Exception:
        return None


def _decode_mp3(data: bytes) -> np.ndarray | None:
    try:
        from pydub import AudioSegment
        import io
        seg = AudioSegment.from_mp3(io.BytesIO(data))
        seg = seg.set_channels(1).set_frame_rate(ELEVENLABS_SAMPLE_RATE)
        # Strip trailing silence ElevenLabs appends
        seg = seg.strip_silence(silence_len=100, silence_thresh=-40, padding=30)
        samples = np.array(seg.get_array_of_samples(), dtype=np.float32)
        samples /= 32768.0
        peak = np.max(np.abs(samples))
        if peak > 0:
            samples = samples / peak * 0.92
        return samples.reshape(-1, 1)
    except Exception:
        return None


def _play(audio: np.ndarray, sample_rate: int):
    """Play a float32 column-vector numpy array through sounddevice."""
    with sd.OutputStream(samplerate=sample_rate, channels=1, dtype="float32") as stream:
        chunk_size = 2048
        for i in range(0, len(audio), chunk_size):
            stream.write(audio[i:i + chunk_size])


# ── ElevenLabs speak ───────────────────────────────────────────────────────────

def _speak_elevenlabs(text: str) -> bool:
    """
    Synthesize and play text via ElevenLabs sentence by sentence.
    Returns True if successful, False if any sentence failed (triggers fallback).
    """
    sentences = _split_sentences(text)

    for i, sentence in enumerate(sentences):
        audio = _stream_sentence_elevenlabs(sentence)
        if audio is None:
            return False

        _play(audio, ELEVENLABS_SAMPLE_RATE)

        # Inter-sentence pause
        if i < len(sentences) - 1:
            pause = PAUSE_QUESTION if sentence.rstrip().endswith("?") else PAUSE_SENTENCE
            silence = _silence(pause, ELEVENLABS_SAMPLE_RATE)
            _play(silence, ELEVENLABS_SAMPLE_RATE)

    return True


# ── Kokoro fallback speak ──────────────────────────────────────────────────────

def _speak_kokoro(text: str):
    """Full Kokoro fallback — preserves original comma-pause prosody logic."""
    kokoro = _get_kokoro()
    VOICE  = "bm_george"
    SPEED  = 1.07
    LANG   = "en-gb"
    PAUSE_COMMA = 0.12

    def to_float32(samples):
        if samples.dtype != np.float32:
            samples = samples.astype(np.float32)
        peak = np.max(np.abs(samples))
        if peak > 0:
            samples = samples / peak * 0.92
        return samples.reshape(-1, 1) if samples.ndim == 1 else samples

    def synth_with_comma_pauses(sentence, sr):
        clauses = [c.strip() for c in sentence.split(",") if c.strip()]
        if len(clauses) <= 1:
            s, _ = kokoro.create(sentence, voice=VOICE, speed=SPEED, lang=LANG)
            return to_float32(s)
        parts = []
        for j, clause in enumerate(clauses):
            chunk = clause if j == len(clauses) - 1 else clause + ","
            s, _ = kokoro.create(chunk, voice=VOICE, speed=SPEED, lang=LANG)
            parts.append(to_float32(s))
            if j < len(clauses) - 1:
                parts.append(np.zeros((int(PAUSE_COMMA * sr), 1), dtype=np.float32))
        return np.concatenate(parts, axis=0)

    sentences   = _split_sentences(text)
    all_audio   = []
    sample_rate = None

    for i, sentence in enumerate(sentences):
        if not sentence:
            continue
        if sample_rate is None:
            _, sample_rate = kokoro.create(sentence, voice=VOICE, speed=SPEED, lang=LANG)
        chunk = synth_with_comma_pauses(sentence, sample_rate)
        all_audio.append(chunk)
        if i < len(sentences) - 1:
            pause = PAUSE_QUESTION if sentence.rstrip().endswith("?") else PAUSE_SENTENCE
            all_audio.append(np.zeros((int(pause * sample_rate), 1), dtype=np.float32))

    if not all_audio or sample_rate is None:
        return

    final = np.concatenate(all_audio, axis=0)
    _play(final, sample_rate)


# ── Public API ─────────────────────────────────────────────────────────────────

def speak_sentence(sentence: str) -> bool:
    """
    Speak a single pre-split sentence from the streaming pipeline.
    Caller is responsible for sentence splitting and the MAX_SPOKEN_SENTENCES cap.
    Sanitizes for TTS artifacts but does NOT re-split or re-limit.
    Returns True if ElevenLabs succeeded, False if Kokoro fallback was used.
    """
    clean = _sanitize(sentence)
    if not clean:
        return True  # nothing to say, not a failure

    audio = _stream_sentence_elevenlabs(clean)
    if audio is not None:
        _play(audio, ELEVENLABS_SAMPLE_RATE)
        try:
            from usage_tracker import record_elevenlabs_chars
            record_elevenlabs_chars(len(clean))
        except Exception:
            pass
        return True
    else:
        # Kokoro fallback for this sentence
        _speak_kokoro(clean)
        return False


def speak(text: str) -> None:
    """
    Sanitize, limit to MAX_SPOKEN_SENTENCES, then:
      1. Try ElevenLabs Flash v2.5 (streaming, sentence by sentence)
      2. Fall back to Kokoro ONNX if ElevenLabs fails or key is missing
    """
    clean   = _sanitize(text)
    limited = _limit_sentences(clean)
    if not limited:
        return

    success = _speak_elevenlabs(limited)
    if success:
        # Record chars sent to ElevenLabs for usage tracking
        try:
            from usage_tracker import record_elevenlabs_chars
            record_elevenlabs_chars(len(limited))
        except Exception:
            pass
    else:
        _speak_kokoro(limited)


# ── Test ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import time
    tests = [
        "At your service, sir.",
        "Solid work, honestly. Gesture engine's live on the Pi — that's not prototype territory anymore.",
        "Four hours is enough. Go touch grass, you've earned it.",
        "The fist gesture is still unmapped. Want to tackle that first, or sort the both-hands detection?",
        "Filed.",
    ]
    for t in tests:
        print(f"Speaking: {t}")
        speak(t)
        time.sleep(0.5)
