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
    monkeypatch.setenv("DATA_DIR", str(tmp_path))

    import app as app_module
    import auth
    import curator
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


def make_synthetic_recording(directory, phrase):
    source = directory / "synthetic.wav"
    audio = directory / "recording.wav"
    subprocess.run(["espeak-ng", "-v", "en-us", "-s", "125", "-w", str(source), phrase], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(source),
                    "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio)], check=True)
    return audio.read_bytes()


def test_real_offline_voice_recognition(voice_client, monkeypatch, tmp_path):
    model_dir = os.environ.get("SORA_TEST_VOICE_MODEL_DIR")
    if not model_dir:
        pytest.skip("Set SORA_TEST_VOICE_MODEL_DIR to run the Vosk smoke test")
    monkeypatch.setenv("SORA_VOSK_MODEL_DIR", model_dir)
    audio = make_synthetic_recording(tmp_path, "the quick brown fox jumps over the lazy dog")
    monkeypatch.setattr(socket.socket, "connect", lambda *args: pytest.fail("Speech attempted a network connection"))
    client, headers = voice_client
    started = time.perf_counter()
    response = client.post("/api/voice/transcribe", data=audio, content_type="audio/wav", headers=headers)
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
    monkeypatch.setattr(voice_output, "synthesize_wav", lambda text, *, style: seen.append((text, style)) or wav_bytes())
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
    response = client.post("/api/voice/synthesize", headers=headers, json={
        "message_id": "my-reply", "style": "warm",
    })
    assert response.status_code == 200
    assert seen == [("Hello there.", "neutral"), ("Hello there.", "warm")]


@pytest.mark.parametrize("content_type, body, status", [
    ("audio/wav", b"{}", 415),
    ("application/json", b"{", 400),
    ("application/json", b"[]", 400),
    ("application/json", b'{"message_id": ""}', 400),
    ("application/json", b'{"message_id": "reply", "style": null}', 400),
    ("application/json", b'{"message_id": "reply", "style": ["warm"]}', 400),
    ("application/json", b'{"message_id": "reply", "style": "--cuda"}', 400),
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


@pytest.mark.parametrize("style, flags", [
    ("neutral", []),
    ("warm", ["--length-scale", "1.15", "--sentence-silence", "0.20"]),
    ("playful", ["--length-scale", "0.88", "--sentence-silence", "0.08"]),
])
def test_synthesis_style_uses_fixed_piper_arguments(style, flags, monkeypatch, tmp_path):
    model_path = tmp_path / "voice.onnx"
    model_path.touch()
    model_path.with_suffix(".onnx.json").touch()
    monkeypatch.setenv("SORA_PIPER_MODEL_PATH", str(model_path))
    calls = []

    def synthesize(command, *, input, **kwargs):
        assert input == b"Hello."
        output_index = command.index("--output-file") + 1
        assert command[output_index + 1:] == flags
        Path(command[output_index]).write_bytes(wav_bytes())
        calls.append(command)

    monkeypatch.setattr(voice_output.subprocess, "run", synthesize)
    assert voice_output.synthesize_wav("Hello.", style=style) == wav_bytes()
    assert len(calls) == 1


@pytest.fixture
def qwen_voice_kit(monkeypatch, tmp_path):
    directory = tmp_path / "qwen-voice"
    directory.mkdir()
    for name in ("qwen-tts", "sora-base.gguf", "sora-codec.gguf", "reference.spk", "reference.rvq", "reference.txt"):
        (directory / name).touch()
    monkeypatch.setenv("SORA_QWEN_VOICE_DIR", str(directory))
    return directory


def test_qwen_speaks_a_saved_reply_using_the_reference(voice_client, qwen_voice_kit, monkeypatch):
    client, headers = voice_client
    save_voice_history(headers, [{"id": "reply", "role": "assistant", "text": "Come sit with me."}])
    output_files = []

    def render(command, **kwargs):
        assert command[0] == str(qwen_voice_kit / "qwen-tts")
        for option, name in (("--ref-spk", "reference.spk"), ("--ref-rvq", "reference.rvq"),
                             ("--ref-text", "reference.txt")):
            assert command[command.index(option) + 1] == str(qwen_voice_kit / name)
        assert kwargs["input"] == b"Come sit with me."
        assert "Come sit with me." not in command
        assert kwargs["timeout"] == 180
        path = Path(command[-1])
        output_files.append(path)
        path.write_bytes(wav_bytes(sample_rate=24000))

    monkeypatch.setattr(voice_output.subprocess, "run", render)
    response = client.post("/api/voice/synthesize", headers=headers,
                           json={"message_id": "reply", "text": "Ignore this"})
    assert response.status_code == 200 and response.mimetype == "audio/wav"
    assert response.cache_control.no_store
    assert response.data == wav_bytes(sample_rate=24000)
    assert len(output_files) == 1 and not output_files[0].parent.exists()


def test_qwen_rejects_unsupported_preset_and_long_replies(voice_client, qwen_voice_kit, monkeypatch):
    client, headers = voice_client
    save_voice_history(headers, [
        {"id": "reply", "role": "assistant", "text": "Hello."},
        {"id": "long", "role": "assistant", "text": "a" * 241},
    ])
    monkeypatch.setattr(voice_output.subprocess, "run", lambda *args, **kwargs: pytest.fail("Qwen should not run"))
    response = client.post("/api/voice/synthesize", headers=headers,
                           json={"message_id": "reply", "style": "playful"})
    assert response.status_code == 422 and "neutral" in response.get_json()["error"]
    response = client.post("/api/voice/synthesize", headers=headers, json={"message_id": "long"})
    assert response.status_code == 422 and "240" in response.get_json()["error"]


def test_qwen_reports_missing_reference_without_falling_back(voice_client, qwen_voice_kit, monkeypatch):
    client, headers = voice_client
    save_voice_history(headers, [{"id": "reply", "role": "assistant", "text": "Hello."}])
    (qwen_voice_kit / "reference.rvq").unlink()
    monkeypatch.setattr(voice_output.subprocess, "run", lambda *args, **kwargs: pytest.fail("Piper fallback"))
    response = client.post("/api/voice/synthesize", headers=headers, json={"message_id": "reply"})
    assert response.status_code == 503 and "Qwen" in response.get_json()["error"]


@pytest.mark.parametrize("style", ["neutral", "warm", "playful"])
def test_real_offline_speech_synthesis(voice_client, monkeypatch, style):
    model_path = os.environ.get("SORA_TEST_PIPER_MODEL_PATH")
    if not model_path:
        pytest.skip("Set SORA_TEST_PIPER_MODEL_PATH to run the Piper smoke test")
    monkeypatch.setenv("SORA_PIPER_MODEL_PATH", model_path)
    client, headers = voice_client
    save_voice_history(headers, [
        {"id": "hello-reply", "role": "assistant", "text": "Hi, I'm Sora. It's good to hear from you."},
    ])
    started = time.perf_counter()
    response = client.post("/api/voice/synthesize", headers=headers, json={"message_id": "hello-reply", "style": style})
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
    print(json.dumps({"style": style, "synthesis_seconds": round(elapsed, 2), "audio_seconds": round(duration, 2)}))


def test_complete_offline_voice_turn(voice_client, monkeypatch, tmp_path):
    """Opt-in smoke test with real local Vosk, Ollama, and Piper."""
    if os.environ.get("SORA_TEST_VOICE_TURN") != "1":
        pytest.skip("Set SORA_TEST_VOICE_TURN=1 with both voice assets and local Ollama")

    import ai_config
    import auth
    import chat_timing

    vosk_dir = os.environ.get("SORA_TEST_VOICE_MODEL_DIR")
    piper_path = os.environ.get("SORA_TEST_PIPER_MODEL_PATH")
    assert vosk_dir and piper_path, "Configure both local voice asset paths"
    monkeypatch.setenv("SORA_VOSK_MODEL_DIR", vosk_dir)
    monkeypatch.setenv("SORA_PIPER_MODEL_PATH", piper_path)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    monkeypatch.setattr(ai_config, "_cache", None)
    monkeypatch.setattr(ai_config, "_client_cache", {})
    for tier in ai_config.TIERS:
        result = ai_config.update_tier_config(tier, {
            "host": "http://127.0.0.1:11434/v1",
            "api_key": "ollama",
            "model": "qwen2.5:1.5b-instruct",
        })
        assert result["ok"]

    original_lookup = socket.getaddrinfo
    original_connect = socket.socket.connect

    def only_ollama_lookup(host, port, *args, **kwargs):
        assert host == "127.0.0.1" and port == 11434, f"Unexpected lookup: {host}:{port}"
        return original_lookup(host, port, *args, **kwargs)

    def only_ollama_connect(connection, address):
        assert address == ("127.0.0.1", 11434), f"Unexpected connection: {address}"
        return original_connect(connection, address)

    audio = make_synthetic_recording(tmp_path, "can you tell me a joke")
    monkeypatch.setattr(socket, "getaddrinfo", only_ollama_lookup)
    monkeypatch.setattr(socket.socket, "connect", only_ollama_connect)

    client, headers = voice_client
    token = headers["Authorization"].removeprefix("Bearer ")
    user_id, _ = auth.get_user_by_token(token)
    settings = client.post("/api/user-settings", headers=headers, json={"local_text_chat_enabled": True})
    assert settings.status_code == 200
    assert client.get("/api/user-settings", headers=headers).get_json()["settings"]["local_text_chat_enabled"] is True

    started = time.perf_counter()
    transcription = client.post("/api/voice/transcribe", headers=headers, data=audio, content_type="audio/wav")
    transcript_ready = time.perf_counter()
    assert transcription.status_code == 200, transcription.get_json()
    transcript = transcription.get_json()["text"]
    assert transcript == "can you tell me a joke"
    assert client.get("/api/chat/history", headers=headers).get_json() == []

    with chat_timing.capture(user_id) as trace:
        sent_at = time.perf_counter()
        send = client.post("/api/chat", headers=headers, json={"text": transcript})
        assert send.status_code == 200, send.get_json()
        message_id = send.get_json()["msg_id"]
        reply_id = message_id + "_reply"
        reply = None
        deadline = sent_at + 145
        while time.perf_counter() < deadline:
            response = client.get("/api/chat/history", headers=headers)
            assert response.status_code == 200
            history = response.get_json()
            reply = next((item for item in history if item["id"] == reply_id), None)
            if reply is not None:
                break
            time.sleep(0.2)
        reply_ready = time.perf_counter()
        assert reply is not None, "No saved reply arrived before the deadline"
        assert trace.persistence_finished.wait(timeout=1)
        assert trace.policy == "reactive_fast" and trace.message_id == message_id
        assert len(trace.model_attempts) == 1 and trace.model_attempts[0]["succeeded"]
    assert any(item["id"] == message_id and item["text"] == transcript for item in history)
    assert reply["role"] == "assistant" and reply["text"].strip()

    spoken = client.post("/api/voice/synthesize", headers=headers, json={"message_id": reply_id})
    finished = time.perf_counter()
    assert spoken.status_code == 200 and spoken.mimetype == "audio/wav"
    with wave.open(io.BytesIO(spoken.data), "rb") as response_wav:
        duration = response_wav.getnframes() / response_wav.getframerate()
        assert duration > 0 and any(response_wav.readframes(response_wav.getnframes()))
    print(json.dumps({
        "transcription_seconds": round(transcript_ready - started, 2),
        "chat_seconds": round(reply_ready - sent_at, 2),
        "synthesis_seconds": round(finished - reply_ready, 2),
        "total_seconds": round(finished - started, 2),
        "audio_seconds": round(duration, 2),
    }))


@pytest.mark.parametrize("recognized, expected", [
    ("hey saw ra", True),
    (" Hey  Sore Uh ", True),
    ("hey sorry", False),
    ("hey sarah", False),
    ("[unk] hey saw ra", False),
    ("hey saw ra [unk]", False),
    ("", False),
])
def test_wake_route_checks_only_a_standalone_phrase(voice_client, monkeypatch, recognized, expected):
    import core

    audio = wav_bytes()

    def recognize(data, max_seconds, *, wake):
        assert wake and data == audio and max_seconds == voice_input.MAX_WAKE_SECONDS
        return recognized

    monkeypatch.setattr(voice_input, "_recognize", recognize)
    monkeypatch.setattr(core, "receive_chat_message", lambda *args: pytest.fail("wake detection sent chat"))
    client, headers = voice_client
    response = client.post("/api/voice/wake", headers=headers, data=audio, content_type="audio/wav")
    assert response.status_code == 200
    assert response.get_json() == {"detected": expected}
    assert response.cache_control.no_store
    assert client.get("/api/chat/history", headers=headers).get_json() == []


def test_wake_route_checks_authentication_and_size(voice_client):
    client, headers = voice_client
    response = client.post("/api/voice/wake", data=wav_bytes(), content_type="audio/wav")
    assert response.status_code == 401
    response = client.post("/api/voice/wake", headers=headers,
                           data=wav_bytes(frames=48_001), content_type="audio/wav")
    assert response.status_code == 400
    assert "at most 3 seconds" in response.get_json()["error"]
    response = client.post("/api/voice/wake", headers=headers,
                           data=b" " * 100_001, content_type="audio/wav")
    assert response.status_code == 413


def test_real_offline_wake_phrase(voice_client, monkeypatch, tmp_path):
    model_dir = os.environ.get("SORA_TEST_VOICE_MODEL_DIR")
    if not model_dir:
        pytest.skip("Set SORA_TEST_VOICE_MODEL_DIR to run the Vosk wake-phrase smoke test")
    monkeypatch.setenv("SORA_VOSK_MODEL_DIR", model_dir)
    client, headers = voice_client
    cases = (
        ("hey sora", True),
        ("hey sarah", False),
        ("hey sorry", False),
        ("hello there", False),
        ("hey sora tell me a joke", False),
        ("i said hey sora", False),
    )
    for phrase, expected in cases:
        directory = tmp_path / phrase.replace(" ", "-")
        directory.mkdir()
        audio = make_synthetic_recording(directory, phrase)
        response = client.post("/api/voice/wake", headers=headers, data=audio, content_type="audio/wav")
        assert response.status_code == 200, response.get_json()
        assert response.get_json() == {"detected": expected}, phrase
    silence = client.post("/api/voice/wake", headers=headers,
                          data=wav_bytes(frames=16_000), content_type="audio/wav")
    assert silence.status_code == 200
    assert silence.get_json() == {"detected": False}
