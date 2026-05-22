"""
voice.py — Voice I/O module.
  • speak_text()      — GPT text → speech (gTTS), plays audio
  • record_audio()    — captures microphone input to a WAV file
  • transcribe_audio() — Whisper STT on an audio file

All functions degrade gracefully: if audio hardware is unavailable
(e.g. running headless / in CI) they print a warning and continue.
"""

import os
import io
import sys
import tempfile
import threading
import time

# ── Optional imports ──────────────────────────────────────────────────────────
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

try:
    import sounddevice as sd
    import soundfile as sf
    import numpy as np
    AUDIO_AVAILABLE = True
except (ImportError, OSError):
    AUDIO_AVAILABLE = False

try:
    import openai
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

# Lazy initialization for Whisper client
def get_whisper_client():
    """Get or create OpenAI client for Whisper."""
    if not WHISPER_AVAILABLE:
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return openai.OpenAI(api_key=api_key)

try:
    from pydub import AudioSegment
    from pydub.playback import play as pydub_play
    PYDUB_AVAILABLE = True
except (ImportError, OSError):
    PYDUB_AVAILABLE = False

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
SAMPLE_RATE   = 16_000   # Hz — Whisper works well at 16 kHz
MAX_RECORDING = 60       # seconds — safety cap on recordings


# ─────────────────────────────────────────────
# Text → Speech
# ─────────────────────────────────────────────

def speak_text(text: str, lang: str = "en") -> bytes | None:
    """
    Convert text to speech using gTTS.

    Returns the raw MP3 bytes so the caller can play them, stream them,
    or save them. Also attempts immediate local playback via pydub.

    Returns None on failure (logs warning instead of crashing).
    """
    if not text:
        return None

    if not GTTS_AVAILABLE:
        print(f"[VOICE] gTTS not installed — would say: {text}")
        return None

    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        mp3_bytes = buf.getvalue()

        # Try to play locally if pydub is available
        if PYDUB_AVAILABLE:
            try:
                buf.seek(0)
                segment = AudioSegment.from_mp3(buf)
                pydub_play(segment)
            except Exception as e:
                print(f"[VOICE] Playback skipped: {e}")

        return mp3_bytes

    except Exception as e:
        print(f"[VOICE] TTS error: {e}")
        return None


def text_to_mp3_file(text: str, output_path: str | None = None) -> str | None:
    """
    Save TTS output to an MP3 file. Returns the file path or None.
    Useful for Streamlit's st.audio() widget.
    """
    if not GTTS_AVAILABLE:
        return None
    try:
        tts = gTTS(text=text, lang="en", slow=False)
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)
        tts.save(output_path)
        return output_path
    except Exception as e:
        print(f"[VOICE] TTS file save error: {e}")
        return None


# ─────────────────────────────────────────────
# Microphone recording
# ─────────────────────────────────────────────

def record_audio(
    duration: int = 30,
    sample_rate: int = SAMPLE_RATE,
    output_path: str | None = None,
) -> str | None:
    """
    Record audio from the default microphone.

    Args:
        duration:     Max seconds to record (user can stop early via Ctrl+C).
        sample_rate:  Sampling rate in Hz.
        output_path:  Where to save the WAV file. Temp file if None.

    Returns:
        Path to the saved WAV file, or None on failure.
    """
    if not AUDIO_AVAILABLE:
        print("[VOICE] sounddevice / soundfile not available — cannot record.")
        return None

    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

    print(f"[VOICE] Recording for up to {duration}s …  (press Ctrl+C to stop early)")
    try:
        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
        )
        sd.wait()  # Block until done
        sf.write(output_path, recording, sample_rate)
        print(f"[VOICE] Saved recording → {output_path}")
        return output_path
    except KeyboardInterrupt:
        sd.stop()
        sf.write(output_path, recording[: sd.get_stream().read_available], sample_rate)
        print(f"[VOICE] Recording stopped early → {output_path}")
        return output_path
    except Exception as e:
        print(f"[VOICE] Recording error: {e}")
        return None


# ─────────────────────────────────────────────
# Speech → Text  (Whisper via OpenAI API)
# ─────────────────────────────────────────────

def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe an audio file using OpenAI Whisper.

    Accepts WAV, MP3, MP4, MPEG, MPGA, M4A, WEBM, OGG.
    Returns the transcript string, or "" on failure.
    """
    if not WHISPER_AVAILABLE:
        print("[VOICE] openai not available — cannot transcribe.")
        return ""

    client = get_whisper_client()
    if not client:
        print("[VOICE] OPENAI_API_KEY not set — cannot transcribe.")
        return ""

    if not audio_path or not os.path.exists(audio_path):
        print(f"[VOICE] Audio file not found: {audio_path}")
        return ""

    try:
        with open(audio_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="en",
            )
        transcript = result.text.strip()
        print(f"[VOICE] Transcript: {transcript}")
        return transcript
    except Exception as e:
        print(f"[VOICE] Transcription error: {e}")
        return ""


def transcribe_bytes(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """
    Transcribe raw audio bytes (e.g. from Streamlit file uploader).
    Writes to a temp file, transcribes, then cleans up.
    """
    fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(filename)[-1] or ".wav")
    try:
        os.write(fd, audio_bytes)
        os.close(fd)
        return transcribe_audio(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
