"""Optional offline speech synthesis for short saved replies."""

import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import wave


MAX_REPLY_CHARS = 1000
_MAX_WAV_BYTES = 8_000_000
_SYNTHESIS_TIMEOUT_SECONDS = 45
_QWEN_TIMEOUT_SECONDS = 180
_QWEN_MAX_REPLY_CHARS = 240
_QWEN_MAX_FRAMES = 320
_QWEN_FRAME_SAMPLES = 1920

VOICE_STYLES: dict[str, tuple[str, ...]] = {
    "neutral": (),
    "warm": ("--length-scale", "1.15", "--sentence-silence", "0.20"),
    "playful": ("--length-scale", "0.88", "--sentence-silence", "0.08"),
}
_synthesis_lock = threading.Lock()


class VoiceOutputUnavailable(RuntimeError):
    """The local synthesizer is unconfigured, busy, or unavailable."""


class VoiceOutputRequestError(ValueError):
    """The selected voice cannot render the requested text or preset."""


def _piper_arguments(style: str, wav_path: Path) -> list[str]:
    configured_path = os.environ.get("SORA_PIPER_MODEL_PATH", "").strip()
    if not configured_path:
        raise VoiceOutputUnavailable("Local speech synthesis is not configured.")
    model_path = Path(configured_path).expanduser()
    if not model_path.is_file() or not model_path.with_suffix(model_path.suffix + ".json").is_file():
        raise VoiceOutputUnavailable("The configured Piper voice model or its JSON configuration is unavailable.")
    return [
        sys.executable, "-B", "-m", "piper", "--model", str(model_path.resolve()),
        "--output-file", str(wav_path), *VOICE_STYLES[style],
    ]


def _qwen_arguments(directory: Path, wav_path: Path) -> list[str]:
    paths = {name: directory / name for name in (
        "qwen-tts", "sora-base.gguf", "sora-codec.gguf", "reference.spk", "reference.rvq", "reference.txt",
    )}
    if not all(path.is_file() for path in paths.values()):
        raise VoiceOutputUnavailable("The configured Qwen voice directory is missing required files.")
    return [
        str(paths["qwen-tts"]), "--model", str(paths["sora-base.gguf"]),
        "--codec", str(paths["sora-codec.gguf"]), "--device", "CPU", "--lang", "English",
        "--ref-spk", str(paths["reference.spk"]), "--ref-rvq", str(paths["reference.rvq"]),
        "--ref-text", str(paths["reference.txt"]), "--seed", "7",
        "--max-new", str(_QWEN_MAX_FRAMES), "-o", str(wav_path),
    ]


def synthesize_wav(text: str, *, style: str = "neutral") -> bytes:
    """Return an offline WAV using the configured Qwen voice or Piper."""
    qwen_dir = os.environ.get("SORA_QWEN_VOICE_DIR", "").strip()
    if qwen_dir:
        if style != "neutral":
            raise VoiceOutputRequestError(
                "The approved Sora voice uses its reference delivery. Choose the neutral preset."
            )
        if len(text) > _QWEN_MAX_REPLY_CHARS:
            raise VoiceOutputRequestError(
                f"Choose a reply of up to {_QWEN_MAX_REPLY_CHARS} characters for the approved Sora voice."
            )

    if not _synthesis_lock.acquire(blocking=False):
        raise VoiceOutputUnavailable("Local speech synthesis is busy. Try again shortly.")

    try:
        with tempfile.TemporaryDirectory(prefix="sora-voice-") as directory:
            wav_path = Path(directory) / "reply.wav"
            if qwen_dir:
                command = _qwen_arguments(Path(qwen_dir).expanduser().resolve(), wav_path)
                timeout = _QWEN_TIMEOUT_SECONDS
            else:
                command = _piper_arguments(style, wav_path)
                timeout = _SYNTHESIS_TIMEOUT_SECONDS

            subprocess.run(
                command,
                input=text.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=timeout,
            )
            with wav_path.open("rb") as speech:
                audio = speech.read(_MAX_WAV_BYTES + 1)
            if (len(audio) <= 44 or len(audio) > _MAX_WAV_BYTES
                    or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE"):
                raise VoiceOutputUnavailable("The local voice did not produce valid audio.")
            if qwen_dir:
                with wave.open(io.BytesIO(audio), "rb") as pcm:
                    if (pcm.getnchannels(), pcm.getsampwidth(), pcm.getframerate()) != (1, 2, 24000):
                        raise VoiceOutputUnavailable("The Qwen voice did not produce a valid mono WAV.")
                    frames = pcm.getnframes()
                    if frames >= _QWEN_MAX_FRAMES * _QWEN_FRAME_SAMPLES:
                        raise VoiceOutputRequestError("The approved voice reached its audio limit. Choose a shorter reply.")
                    if frames == 0 or len(pcm.readframes(frames)) != frames * pcm.getsampwidth():
                        raise VoiceOutputUnavailable("The Qwen voice produced incomplete audio.")
            return audio
    except subprocess.TimeoutExpired as exc:
        raise VoiceOutputUnavailable("Local speech synthesis timed out. Try a shorter reply.") from exc
    except (OSError, subprocess.CalledProcessError, UnicodeError, wave.Error, EOFError) as exc:
        engine = "Qwen" if qwen_dir else "Piper"
        raise VoiceOutputUnavailable(f"Local speech synthesis could not run. Check the installed {engine} runtime and voice.") from exc
    finally:
        _synthesis_lock.release()
