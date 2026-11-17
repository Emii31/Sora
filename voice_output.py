"""Optional offline speech synthesis for short saved replies."""

from collections import OrderedDict
from hashlib import sha256
import io
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import wave


MAX_REPLY_CHARS = 1000
_MAX_WAV_BYTES = 8_000_000
_SYNTHESIS_TIMEOUT_SECONDS = 45
_QWEN_TIMEOUT_SECONDS = 180
_QWEN_MAX_REPLY_CHARS = 240
_QWEN_MAX_FRAMES = 320
_QWEN_FRAME_SAMPLES = 1920
_QWEN_CACHE_MAX_REPLIES = 8
_QWEN_CACHE_TTL_SECONDS = 300

VOICE_STYLES: dict[str, tuple[str, ...]] = {
    "neutral": (),
    "warm": ("--length-scale", "1.15", "--sentence-silence", "0.20"),
    "playful": ("--length-scale", "0.88", "--sentence-silence", "0.08"),
}
_synthesis_lock = threading.Lock()
_reply_cache_lock = threading.Lock()
_reply_cache: OrderedDict[tuple, tuple[float, bytes]] = OrderedDict()
logger = logging.getLogger(__name__)


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


def _qwen_arguments(directory: Path, wav_path: Path | None, *, device: str = "CPU") -> list[str]:
    paths = {name: directory / name for name in (
        "sora-base.gguf", "sora-codec.gguf", "reference.spk", "reference.rvq", "reference.txt",
    )}
    executable = directory / "qwen-tts" if wav_path is not None else directory / "vulkan" / "qwen-tts-framed"
    if not executable.is_file() or not all(path.is_file() for path in paths.values()):
        raise VoiceOutputUnavailable("The configured Qwen voice directory is missing required files.")
    command = [
        str(executable), "--model", str(paths["sora-base.gguf"]),
        "--codec", str(paths["sora-codec.gguf"]), "--device", device, "--lang", "English",
        "--ref-spk", str(paths["reference.spk"]), "--ref-rvq", str(paths["reference.rvq"]),
        "--ref-text", str(paths["reference.txt"]), "--seed", "7",
        "--max-new", str(_QWEN_MAX_FRAMES), "-o",
    ]
    if wav_path is None:
        return command + ["-", "--stream-by-line", "--sora-frames"]
    return command + [str(wav_path)]


def _qwen_assets(command: list[str]) -> tuple:
    paths = [command[0]] + [
        command[command.index(flag) + 1] for flag in ("--model", "--codec", "--ref-spk", "--ref-rvq", "--ref-text")
    ]
    try:
        files = [Path(path).stat() for path in paths]
    except OSError as exc:
        raise VoiceOutputUnavailable("The configured Qwen voice directory is missing required files.") from exc
    return tuple((file.st_dev, file.st_ino, file.st_size, file.st_mtime_ns) for file in files)


def _resident_qwen_wav(directory: Path, device: str, text: str) -> bytes:
    import voice_qwen

    if "\0" in text:
        raise VoiceOutputRequestError("The reply contains an unsupported character.")
    command = _qwen_arguments(directory, None, device=device)
    pcm = voice_qwen.render(command, text, timeout=_QWEN_TIMEOUT_SECONDS, max_frames=_QWEN_MAX_FRAMES,
                            assets=_qwen_assets(command))
    if not pcm:
        raise VoiceOutputUnavailable("The Qwen voice produced no audio.")
    if len(pcm) >= 2 * _QWEN_MAX_FRAMES * _QWEN_FRAME_SAMPLES:
        raise VoiceOutputRequestError("The approved voice reached its audio limit. Choose a shorter reply.")
    file = io.BytesIO()
    with wave.open(file, "wb") as out:
        out.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        out.writeframes(pcm)
    return file.getvalue()


def warm_up_configured_voice():
    """Prime the opted-in worker without blocking application startup."""
    if not os.environ.get("SORA_QWEN_VOICE_DIR", "").strip() or not os.environ.get("SORA_QWEN_RESIDENT_DEVICE", "").strip():
        return

    def warm():
        try:
            synthesize_wav("Hi.")
        except VoiceOutputUnavailable as exc:
            logger.warning("Could not warm up the local voice: %s", exc)

    threading.Thread(target=warm, name="sora-voice-warm-up", daemon=True).start()


def synthesize_saved_reply(text: str, *, style: str, account: tuple[str, str]) -> bytes:
    """Reuse recent exact audio only within the same authenticated account."""
    directory = os.environ.get("SORA_QWEN_VOICE_DIR", "").strip()
    device = os.environ.get("SORA_QWEN_RESIDENT_DEVICE", "").strip()
    if not directory or not device or style != "neutral":
        return synthesize_wav(text, style=style)

    directory = Path(directory).expanduser().resolve()
    command = _qwen_arguments(directory, None, device=device)
    key = (account, tuple(command), _qwen_assets(command), sha256(text.encode()).digest())
    now = time.monotonic()
    with _reply_cache_lock:
        while _reply_cache and next(iter(_reply_cache.values()))[0] <= now:
            _reply_cache.popitem(last=False)
        found = _reply_cache.get(key)
        if found is not None:
            return found[1]

    audio = synthesize_wav(text, style=style)
    with _reply_cache_lock:
        _reply_cache.pop(key, None)
        _reply_cache[key] = (time.monotonic() + _QWEN_CACHE_TTL_SECONDS, audio)
        while len(_reply_cache) > _QWEN_CACHE_MAX_REPLIES:
            _reply_cache.popitem(last=False)
    return audio


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
        resident_device = os.environ.get("SORA_QWEN_RESIDENT_DEVICE", "").strip()
        if qwen_dir and resident_device:
            return _resident_qwen_wav(Path(qwen_dir).expanduser().resolve(), resident_device, text)
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
