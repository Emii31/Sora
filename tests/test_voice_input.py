import io
import json
import os
import socket
import subprocess
import time
import wave

import pytest

import voice_input


def wav_bytes(*, channels=1, sample_rate=16_000, frames=24):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setparams((channels, 2, sample_rate, 0, "NONE", "not compressed"))
        recording.writeframes(b"\0\0" * frames * channels)
    return buffer.getvalue()


@pytest.fixture
def voice_client(monkeypatch, tmp_path):
    import app as app_module
    import auth
    import curator

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(auth, "_BASE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(auth, "_ADMIN_DIR", str(tmp_path / "_admin"))
    monkeypatch.setattr(app_module, "_client_mode_config", {})
    monkeypatch.setattr(curator, "start_loop_for_user", lambda *args: None)
    user = auth.get_or_create_local_single_device_user()
    headers = {"Authorization": f"Bearer {user['token']}"}
    return app_module.app.test_client(), headers


def test_voice_route_uses_existing_authentication(voice_client, monkeypatch):
    client, _ = voice_client
    monkeypatch.setattr(voice_input, "transcribe_wav", lambda audio: pytest.fail("unauthenticated speech"))
    response = client.post("/api/voice/transcribe", data=wav_bytes(), content_type="audio/wav")
    assert response.status_code == 401


@pytest.mark.parametrize("content_type, body, status", [
    ("application/json", b"{}", 415),
    ("audio/wav", b"invalid", 400),
    ("audio/wav", wav_bytes(channels=2), 400),
    ("audio/wav", wav_bytes(sample_rate=8_000), 400),
    ("audio/wav", wav_bytes(frames=0), 400),
    ("audio/wav", wav_bytes(frames=480_001), 400),
    ("audio/wav", wav_bytes()[:-1], 400),
    ("audio/wav", b"\0" * (voice_input.MAX_UPLOAD_BYTES + 1), 413),
])
def test_voice_route_validates_recordings(voice_client, content_type, body, status):
    client, headers = voice_client
    response = client.post("/api/voice/transcribe", data=body, content_type=content_type, headers=headers)
    assert response.status_code == status
    assert response.get_json()["error"]


def test_voice_route_returns_a_transcript_without_sending_chat(voice_client, monkeypatch, tmp_path):
    import core

    client, headers = voice_client
    monkeypatch.setenv("SORA_VOSK_MODEL_DIR", str(tmp_path))
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()}
    monkeypatch.setattr(core, "receive_chat_message", lambda *args: pytest.fail("transcript was sent to chat"))

    class Recognizer:
        def __init__(self, model, sample_rate):
            assert sample_rate == 16_000

        def AcceptWaveform(self, pcm):
            assert pcm == b"\0" * 48
            return True

        def Result(self):
            return '{"text": "hello"}'

        def FinalResult(self):
            return '{"text": "there"}'

    monkeypatch.setattr(voice_input, "_load_model", lambda model_dir: (object(), Recognizer))
    response = client.post("/api/voice/transcribe", data=wav_bytes(), content_type="audio/wav", headers=headers)
    assert response.status_code == 200
    assert response.get_json() == {"text": "hello there"}
    assert response.cache_control.no_store
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()} == before


def test_voice_route_reports_disabled_and_busy(voice_client, monkeypatch, tmp_path):
    client, headers = voice_client
    monkeypatch.delenv("SORA_VOSK_MODEL_DIR", raising=False)
    response = client.post("/api/voice/transcribe", data=wav_bytes(), content_type="audio/wav", headers=headers)
    assert response.status_code == 503
    assert "not configured" in response.get_json()["error"]

    monkeypatch.setenv("SORA_VOSK_MODEL_DIR", str(tmp_path))
    with voice_input._recognition_lock:
        response = client.post("/api/voice/transcribe", data=wav_bytes(), content_type="audio/wav", headers=headers)
    assert response.status_code == 503
    assert "busy" in response.get_json()["error"]


def test_real_offline_voice_recognition(voice_client, monkeypatch, tmp_path):
    model_dir = os.environ.get("SORA_TEST_VOICE_MODEL_DIR")
    if not model_dir:
        pytest.skip("Set SORA_TEST_VOICE_MODEL_DIR to run the Vosk smoke test")
    monkeypatch.setenv("SORA_VOSK_MODEL_DIR", model_dir)
    source = tmp_path / "synthetic.wav"
    audio = tmp_path / "recording.wav"
    subprocess.run(["espeak-ng", "-v", "en-us", "-s", "125", "-w", str(source),
                    "the quick brown fox jumps over the lazy dog"], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(source),
                    "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio)], check=True)
    monkeypatch.setattr(socket.socket, "connect", lambda *args: pytest.fail("Speech attempted a network connection"))
    client, headers = voice_client
    started = time.perf_counter()
    response = client.post("/api/voice/transcribe", data=audio.read_bytes(), content_type="audio/wav", headers=headers)
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    result = response.get_json()
    print(json.dumps({"recognition_seconds": round(elapsed, 2), **result}))
    assert "quick brown fox" in result["text"]
    assert "lazy dog" in result["text"]

    silence = client.post("/api/voice/transcribe", data=wav_bytes(frames=16_000), content_type="audio/wav", headers=headers)
    assert silence.status_code == 200
    assert silence.get_json() == {"text": ""}
