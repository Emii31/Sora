import base64
from array import array
import io
import json
import threading
import time
import wave

import pytest

import voice_liquid_live as live


def wav_input():
    output = io.BytesIO()
    with wave.open(output, "wb") as recording:
        recording.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        recording.writeframes(bytes(3200))
    return output.getvalue()


def audio_delta(pcm):
    return {"audio": {"data": base64.b64encode(pcm).decode(), "format": "pcm", "sample_rate": 24000}}


def test_pcm_validation_and_empty_startup():
    assert live.pcm_from_delta(audio_delta(b"")) == b""
    assert live.pcm_from_delta(audio_delta(b"\x00\x10")) == b"\x00\x10"
    with pytest.raises(ValueError):
        live.pcm_from_delta(audio_delta(b"\x00"))
    packet = audio_delta(b"\x00\x10")
    packet["audio"]["sample_rate"] = 16000
    with pytest.raises(ValueError):
        live.pcm_from_delta(packet)


def test_legacy_float_pcm_validation():
    packet = {"audio_chunk": {"data": base64.b64encode(array("f", [0.5, -0.5]).tobytes()).decode()}}
    assert array("h", live.pcm_from_delta(packet)) == array("h", [16384, -16384])
    packet["audio_chunk"]["data"] = base64.b64encode(array("f", [float("nan")]).tobytes()).decode()
    with pytest.raises(ValueError):
        live.pcm_from_delta(packet)


@pytest.mark.parametrize("url", ["https://127.0.0.1/v1", "http://example.com/v1", "http://key@127.0.0.1/v1"])
def test_stream_requires_loopback_without_credentials(url):
    with pytest.raises(ValueError):
        live.LiquidStream(url, threading.Event())


@pytest.mark.parametrize("finish,has_audio,valid", [("stop", True, True), ("length", True, False), ("stop", False, False)])
@pytest.mark.parametrize("transcript", [None, "Hello Sora"])
def test_stream_completion_contract(monkeypatch, finish, has_audio, valid, transcript):
    events = [{"choices": [{"delta": {"content": "Hello"}, "finish_reason": None}]}]
    if has_audio:
        events.append({"choices": [{"delta": audio_delta(b"\x00\x10" * 480), "finish_reason": None}]})
    events.append({"choices": [{"delta": {}, "finish_reason": finish}]})
    response = io.BytesIO(b"".join(b"data: " + json.dumps(event).encode() + b"\n\n" for event in events) + b"data: [DONE]\n")
    response.status = 200
    class Connection:
        sock = None
        closed = False
        def request(self, method, path, body, headers):
            payload = json.loads(body)
            assert payload["reset_context"] is True
            assert payload["messages"][0]["content"] == live.SYSTEM_PROMPT
            assert payload["modalities"] == ["text", "audio"]
            if transcript:
                assert payload["messages"][1]["content"] == transcript
            else:
                assert payload["messages"][1]["content"][0]["type"] == "input_audio"
        def getresponse(self):
            return response
        def close(self):
            self.closed = True
    connection = Connection()
    monkeypatch.setattr(live.http.client, "HTTPConnection", lambda *a, **k: connection)
    stream = live.LiquidStream("http://127.0.0.1:1234/v1/chat/completions", threading.Event())
    if valid:
        received = list(stream.events(wav_input(), text=transcript))
        assert received == [("text", "Hello"), ("audio", b"\x00\x10" * 480)]
    else:
        with pytest.raises(RuntimeError):
            list(stream.events(wav_input(), text=transcript))
    assert connection.closed and stream.connection is None


def test_cancel_unblocks_stream_read(monkeypatch):
    reading = threading.Event()
    shutdown = threading.Event()
    class Socket:
        def shutdown(self, how):
            shutdown.set()
    class Response:
        status = 200
        def readline(self, size):
            reading.set()
            assert shutdown.wait(2)
            return b""
    class Connection:
        sock = Socket()
        closed = False
        def request(self, *args):
            pass
        def getresponse(self):
            return Response()
        def close(self):
            self.closed = True
    connection = Connection()
    monkeypatch.setattr(live.http.client, "HTTPConnection", lambda *a, **k: connection)
    stream = live.LiquidStream("http://127.0.0.1:1234/v1/chat/completions", threading.Event())
    worker = threading.Thread(target=lambda: list(stream.events(wav_input())))
    worker.start()
    assert reading.wait(1)
    stream.cancel()
    worker.join(1)
    assert not worker.is_alive() and connection.closed


def test_endpoint_ignores_noise_and_stops_after_pause():
    detector = live.EndpointDetector(silence_ms=650)
    quiet = bytes(640)
    voice = array("h", [3000] * 320).tobytes()
    for _ in range(100):
        assert not detector.feed(quiet)
    for _ in range(4):
        assert not detector.feed(voice)
    assert not detector.feed(quiet)
    assert not detector.frames
    for _ in range(15):
        assert not detector.feed(voice)
    for _ in range(32):
        assert not detector.feed(quiet)
    assert detector.feed(quiet)
    with wave.open(io.BytesIO(detector.wav())) as recording:
        assert recording.getframerate() == 16000
        assert recording.getnframes() <= 16000 * 20


def test_endpoint_bounds_long_utterance():
    detector = live.EndpointDetector(max_seconds=1)
    voice = array("h", [3000] * 320).tobytes()
    finished = [detector.feed(voice) for _ in range(50)]
    assert finished[-1] and not any(finished[:-1])


def test_endpoint_keeps_short_pause_inside_sentence():
    detector = live.EndpointDetector()
    voice = array("h", [3000] * 320).tobytes()
    for frame in [voice] * 15 + [bytes(640)] * 40 + [voice] * 15:
        assert not detector.feed(frame)
    for _ in range(44):
        assert not detector.feed(bytes(640))
    assert detector.feed(bytes(640))


def test_player_drains_short_reply_at_end(monkeypatch):
    received = []
    class Pipe(io.BytesIO):
        def close(self):
            received.append(self.getvalue())
            super().close()
    class Process:
        def __init__(self, *a, **k):
            self.stdin = Pipe()
        def wait(self, timeout):
            return 0
        def poll(self):
            return 0
    monkeypatch.setattr(live.subprocess, "Popen", Process)
    player = live.BufferedPlayer(threading.Event(), buffer_seconds=1.5)
    player.feed(b"\x00\x10" * 480)
    player.finish()
    assert not player.thread.is_alive()
    assert received == [b"\x00\x10" * 480]
    assert player.started_at is not None and player.bytes_written == 960


def test_player_cancel_discards_prebuffer(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("Cancelled prebuffer started speaker output")
    monkeypatch.setattr(live.subprocess, "Popen", forbidden)
    player = live.BufferedPlayer(threading.Event(), buffer_seconds=1.5)
    player.feed(bytes(4800))
    player.cancel()
    assert not player.thread.is_alive() and player.proc is None


def test_player_cancel_unblocks_active_speaker_write(monkeypatch):
    writing = threading.Event()
    terminated = threading.Event()
    class Pipe:
        closed = False
        def write(self, data):
            writing.set()
            assert terminated.wait(2)
            raise BrokenPipeError()
        def close(self):
            self.closed = True
    class Process:
        def __init__(self, *args, **kwargs):
            self.stdin = Pipe()
        def poll(self):
            return 0 if terminated.is_set() else None
        def terminate(self):
            terminated.set()
        def wait(self, timeout):
            assert terminated.wait(timeout)
            return 0
    monkeypatch.setattr(live.subprocess, "Popen", Process)
    player = live.BufferedPlayer(threading.Event(), buffer_seconds=0)
    player.feed(bytes(4800))
    assert writing.wait(1)
    started = time.monotonic()
    player.cancel()
    assert time.monotonic() - started < 1
    assert not player.thread.is_alive() and player.proc.stdin.closed


def test_gap_estimate_recovers_after_one_late_chunk(monkeypatch):
    class Process:
        def __init__(self, *args, **kwargs):
            self.stdin = io.BytesIO()
        def poll(self):
            return 0
    monkeypatch.setattr(live.subprocess, "Popen", Process)
    clock = iter([0., 0., .25, .3])
    monkeypatch.setattr(live.time, "monotonic", lambda: next(clock))
    player = live.BufferedPlayer(threading.Event(), buffer_seconds=0)
    try:
        player._write(bytes(4800))
        player._write(bytes(4800))
        player._write(bytes(4800))
        assert player.estimated_gaps == 1
        assert player.play_until == pytest.approx(.45)
    finally:
        player.cancel()
