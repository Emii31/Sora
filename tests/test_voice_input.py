import io
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import wave

import pytest

import voice_input
import voice_output


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


def save_voice_history(headers, messages):
    import auth
    import storage

    token = headers["Authorization"].removeprefix("Bearer ")
    user_id, _ = auth.get_user_by_token(token)
    storage.write_json(str(Path(auth.get_user_data_dir(user_id)) / "chat_history.json"), messages)


def test_synthesis_returns_only_the_callers_saved_reply(voice_client, monkeypatch, tmp_path):
    import auth
    import storage

    client, headers = voice_client
    save_voice_history(headers, [
        {"id": "my-reply", "role": "assistant", "text": "Hello there."},
        {"id": "my-message", "role": "user", "text": "Do not read this."},
    ])
    other_dir = Path(auth.get_user_data_dir("u_other"))
    other_dir.mkdir()
    storage.write_json(str(other_dir / "chat_history.json"), [
        {"id": "other-reply", "role": "assistant", "text": "Other user's text."},
    ])
    seen = []
    monkeypatch.setattr(voice_output, "synthesize_wav", lambda text: seen.append(text) or wav_bytes())
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()}

    response = client.post("/api/voice/synthesize", headers=headers, json={"message_id": "my-reply", "text": "ignored"})
    assert response.status_code == 200
    assert response.mimetype == "audio/wav"
    assert response.cache_control.no_store
    assert response.data == wav_bytes()
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()} == before

    for message_id in ("my-message", "other-reply", "missing"):
        response = client.post("/api/voice/synthesize", headers=headers, json={"message_id": message_id})
        assert response.status_code == 404
    response = client.post("/api/voice/synthesize", json={"message_id": "my-reply"})
    assert response.status_code == 401
    assert seen == ["Hello there."]


@pytest.mark.parametrize("content_type, body, status", [
    ("audio/wav", b"{}", 415),
    ("application/json", b"{", 400),
    ("application/json", b"[]", 400),
    ("application/json", b'{"message_id": ""}', 400),
    ("application/json", b" " * 1025, 413),
])
def test_synthesis_validates_request(voice_client, content_type, body, status):
    client, headers = voice_client
    response = client.post("/api/voice/synthesize", headers=headers, data=body, content_type=content_type)
    assert response.status_code == status
    assert response.get_json()["error"]


def test_synthesis_checks_configuration_and_reply_length(voice_client, monkeypatch):
    client, headers = voice_client
    monkeypatch.delenv("SORA_PIPER_MODEL_PATH", raising=False)
    save_voice_history(headers, [
        {"id": "my-reply", "role": "assistant", "text": "Hello."},
        {"id": "long-reply", "role": "assistant", "text": "a" * 1001},
    ])
    response = client.post("/api/voice/synthesize", headers=headers, json={"message_id": "my-reply"})
    assert response.status_code == 503
    assert "not configured" in response.get_json()["error"]
    response = client.post("/api/voice/synthesize", headers=headers, json={"message_id": "long-reply"})
    assert response.status_code == 422


def test_synthesis_timeout_cleans_up_audio_and_releases_lock(monkeypatch, tmp_path):
    model_path = tmp_path / "voice.onnx"
    model_path.touch()
    model_path.with_suffix(".onnx.json").touch()
    monkeypatch.setenv("SORA_PIPER_MODEL_PATH", str(model_path))
    outputs = []

    def timeout(command, **kwargs):
        assert kwargs["input"] == b"Hello."
        assert "Hello." not in command
        path = Path(command[-1])
        path.write_bytes(wav_bytes())
        outputs.append(path)
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(voice_output.subprocess, "run", timeout)
    for _ in range(2):
        with pytest.raises(voice_output.VoiceOutputUnavailable, match="timed out"):
            voice_output.synthesize_wav("Hello.")
    assert len(outputs) == 2
    assert all(not path.parent.exists() for path in outputs)


def test_real_offline_speech_synthesis(voice_client, monkeypatch):
    model_path = os.environ.get("SORA_TEST_PIPER_MODEL_PATH")
    if not model_path:
        pytest.skip("Set SORA_TEST_PIPER_MODEL_PATH to run the Piper smoke test")
    monkeypatch.setenv("SORA_PIPER_MODEL_PATH", model_path)
    client, headers = voice_client
    save_voice_history(headers, [
        {"id": "hello-reply", "role": "assistant", "text": "Hi, I'm Sora. It's good to hear from you."},
    ])
    started = time.perf_counter()
    response = client.post("/api/voice/synthesize", headers=headers, json={"message_id": "hello-reply"})
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert response.mimetype == "audio/wav"
    with wave.open(io.BytesIO(response.data), "rb") as speech:
        assert speech.getnchannels() == 1
        assert speech.getsampwidth() == 2
        duration = speech.getnframes() / speech.getframerate()
        assert 1 < duration < 10
        samples = speech.readframes(speech.getnframes())
    assert any(samples)
    print(json.dumps({"synthesis_seconds": round(elapsed, 2), "audio_seconds": round(duration, 2)}))
