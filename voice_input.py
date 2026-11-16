"""Offline recognition of short, explicitly submitted WAV recordings."""

import io
import json
import os
import struct
import threading
import wave
from functools import lru_cache
from pathlib import Path


SAMPLE_RATE = 16_000
MAX_SECONDS = 30
MAX_UPLOAD_BYTES = 1_000_000
MAX_WAKE_SECONDS = 3
MAX_WAKE_UPLOAD_BYTES = 100_000
# The small English Vosk model does not contain the name Sora.
_WAKE_MATCHES = ("hey sore uh", "hey saw ra", "hey so ra")
_WAKE_GRAMMAR = (*_WAKE_MATCHES, "hey sarah", "hey sorry", "hey sore", "hey sir",
                 "hey there", "hello there", "[unk]")

_recognition_lock = threading.Lock()


class InvalidAudio(ValueError):
    """The recording does not meet the input contract."""


class VoiceUnavailable(RuntimeError):
    """The local recognizer is unconfigured, busy, or unavailable."""


def _read_pcm(audio: bytes, max_seconds: int) -> bytes:
    try:
        with wave.open(io.BytesIO(audio), "rb") as recording:
            if (recording.getnchannels(), recording.getsampwidth(), recording.getframerate()) != (
                1, 2, SAMPLE_RATE,
            ):
                raise InvalidAudio("Send a 16 kHz mono WAV recording with 16-bit PCM samples.")

            frames = recording.getnframes()
            if not 0 < frames <= SAMPLE_RATE * max_seconds:
                raise InvalidAudio(f"Send a recording longer than zero and at most {max_seconds} seconds.")
            pcm = recording.readframes(frames)
            if len(pcm) != frames * 2:
                raise InvalidAudio("The WAV recording is incomplete.")
    except (wave.Error, EOFError, struct.error) as exc:
        raise InvalidAudio("Send a valid PCM WAV recording.") from exc
    return pcm


@lru_cache(maxsize=1)
def _load_model(model_dir: Path):
    from vosk import KaldiRecognizer, Model, SetLogLevel

    SetLogLevel(-1)
    # model_path selects local files only, unlike Vosk's model name/language lookup.
    return Model(model_path=str(model_dir)), KaldiRecognizer


def transcribe_wav(audio: bytes) -> str:
    return _recognize(audio, MAX_SECONDS)


def detect_wake_phrase(audio: bytes) -> bool:
    text = _recognize(audio, MAX_WAKE_SECONDS, wake=True)
    return " ".join(text.lower().split()) in _WAKE_MATCHES


def _recognize(audio: bytes, max_seconds: int, *, wake: bool = False) -> str:
    pcm = _read_pcm(audio, max_seconds)
    configured_dir = os.environ.get("SORA_VOSK_MODEL_DIR", "").strip()
    if not configured_dir:
        raise VoiceUnavailable("Local speech recognition is not configured.")
    if not _recognition_lock.acquire(blocking=False):
        raise VoiceUnavailable("Local speech recognition is busy. Try again shortly.")
    try:
        model_dir = Path(configured_dir).expanduser().resolve()
        if not model_dir.is_dir():
            raise VoiceUnavailable("The configured local speech model directory is unavailable.")
        model, recognizer_factory = _load_model(model_dir)
        if wake:
            graph = model_dir / "graph"
            words = set(" ".join(_WAKE_GRAMMAR).split())
            if not (graph / "HCLr.fst").is_file() or any(model.vosk_model_find_word(word) < 0 for word in words):
                raise VoiceUnavailable("Wake detection requires a compatible small English Vosk model.")
            recognizer = recognizer_factory(model, SAMPLE_RATE, json.dumps(_WAKE_GRAMMAR))
        else:
            recognizer = recognizer_factory(model, SAMPLE_RATE)
        segments = []
        for start in range(0, len(pcm), 8000):
            if recognizer.AcceptWaveform(pcm[start:start + 8000]):
                segments.append(json.loads(recognizer.Result()).get("text", ""))
        segments.append(json.loads(recognizer.FinalResult()).get("text", ""))
        return " ".join(segment.strip() for segment in segments if segment.strip())
    except VoiceUnavailable:
        raise
    except Exception as exc:
        raise VoiceUnavailable("Local speech recognition could not run. Check the installed model and runtime.") from exc
    finally:
        _recognition_lock.release()
