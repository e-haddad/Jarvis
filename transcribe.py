# transcribe.py
# Converts raw audio to text using Whisper large-v3-turbo.
# Includes a hallucination filter — Whisper commonly outputs filler phrases
# on silence or low-signal audio. These are caught and returned as empty string
# so the pipeline treats them as no input rather than a real command.

import warnings
import whisper

warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")

model = whisper.load_model("large-v3-turbo")

# Phrases Whisper hallucinates on silence or background noise.
# Comparison is case-insensitive and stripped of punctuation.
_HALLUCINATIONS = {
    "thank you",
    "thanks for watching",
    "thanks for watching!",
    "thank you for watching",
    "you're welcome",
    "you're welcome!",
    "please subscribe",
    "like and subscribe",
    "goodbye",
    "bye",
    "bye bye",
    "see you next time",
    "see you later",
    "have a good one",
    "have a nice day",
    "okay",
    "okay.",
    "ok",
    "um",
    "uh",
    "hmm",
    "hm",
    "you",
    "you.",
    "thank you.",
    "thanks.",
    "thanks",
    "sure",
    "sure.",
    "yes",
    "yes.",
    "no",
    "no.",
    "right",
    "right.",
    "oh",
    "oh.",
    "wow",
    "wow.",
    "well",
    "well.",
    "so",
    "so.",
    "i see",
    "i see.",
    "got it",
    "got it.",
    "alright",
    "alright.",
    "all right",
    "all right.",
    "okay, thank you",
    "okay, thanks",
    "thank you so much",
    ".",
    "",
}


def _is_hallucination(text: str) -> bool:
    """Return True if the transcription looks like a Whisper hallucination."""
    cleaned = text.strip().lower().rstrip(".")
    # Direct match
    if cleaned in _HALLUCINATIONS:
        return True
    # Very short output on its own is likely noise
    if len(cleaned) <= 2:
        return True
    return False


def transcribe(filename: str) -> str:
    """
    Transcribe audio file and return cleaned text.
    Returns empty string if transcription looks like a hallucination.
    """
    result = model.transcribe(filename, fp16=False)
    text   = result["text"].strip()

    # Whisper's own confidence that this segment is silence/noise
    segments = result.get("segments", [])
    if segments:
        avg_no_speech = sum(s.get("no_speech_prob", 0) for s in segments) / len(segments)
        if avg_no_speech > 0.6:
            return ""

    if _is_hallucination(text):
        return ""

    return text


if __name__ == "__main__":
    import sys
    f = sys.argv[1] if len(sys.argv) > 1 else "input.wav"
    print(repr(transcribe(f)))
