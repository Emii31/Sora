import base64
from array import array
import io
import json
import sys
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
@pytest.mark.parametrize("spoken", [None, "Hello"])
def test_stream_completion_contract(monkeypatch, finish, has_audio, valid, transcript, spoken):
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
            if spoken is not None:
                assert payload["spoken_text"] == spoken
                assert payload["max_tokens"] == 512
            else:
                assert "spoken_text" not in payload
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
        received = list(stream.events(wav_input(), text=transcript, spoken_text=spoken))
        assert received == [("text", "Hello"), ("audio", b"\x00\x10" * 480)]
    else:
        with pytest.raises(RuntimeError):
            list(stream.events(wav_input(), text=transcript, spoken_text=spoken))
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


@pytest.mark.parametrize("silence_ms,includes_ending", [(900, False), (1200, True)])
def test_microphone_pause_and_stage_timings(monkeypatch, tmp_path, silence_ms, includes_ending):
    import voice_input

    prefix = array("h", [3000] * 320).tobytes()
    ending = array("h", [4000] * 320).tobytes()
    quiet = bytes(640)
    blocks = [prefix] * 20 + [quiet] * 50 + [ending] * 15 + [quiet] * 70
    fixture = tmp_path / "fixture.pcm"
    fixture.write_bytes(b"".join(blocks))
    command = [sys.executable, "-c",
               "from pathlib import Path; import sys; sys.stdout.buffer.write(Path(sys.argv[1]).read_bytes())",
               str(fixture)]

    class Recognizer:
        heard_ending = False

        def AcceptWaveform(self, pcm):
            self.heard_ending |= pcm == ending
            return False

        def FinalResult(self):
            return json.dumps({"text": "I had a long day" if self.heard_ending else "I had a long"})

    monkeypatch.setattr(voice_input, "_load_model", lambda _: (None, lambda *_: Recognizer()))
    popen = live.subprocess.Popen
    microphone = live.Microphone(threading.Event(), vosk_model="fixture", silence_ms=silence_ms)

    def start_fixture(_command, **kwargs):
        return popen(command, **kwargs)

    monkeypatch.setattr(live.subprocess, "Popen", start_fixture)
    recording = microphone.capture()

    assert recording
    assert microphone.transcript == ("I had a long day" if includes_ending else "I had a long")
    assert microphone.speech_ended_at is not None
    assert microphone.timings["capture_end_reason"] == "silence"
    assert microphone.timings["endpoint_silence_s"] == pytest.approx(silence_ms / 1000)
    assert microphone.timings["recognition_finalize_s"] >= 0
    assert microphone.timings["capture_close_s"] >= 0
    assert microphone.proc.poll() is not None


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


@pytest.mark.parametrize('buffer', [1.5, None])
def test_player_cancel_discards_prebuffer(monkeypatch, buffer):
    def forbidden(*a, **k):
        raise AssertionError("Cancelled prebuffer started speaker output")
    monkeypatch.setattr(live.subprocess, "Popen", forbidden)
    player = live.BufferedPlayer(threading.Event(), buffer_seconds=buffer)
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


@pytest.mark.parametrize('text,smooth,expected', [
    (None, False, 1.5), ('You named your plant Juniper.', False, 0.5),
    ('One two three four five six seven eight nine ten.', False, 1.5),
    ('A longer response ' * 12, False, 1.5), ('A longer response ' * 12, True, None),
    ('温' * 24, False, 1.5), ('温' * 40, True, None),
])
def test_reply_buffer_uses_words_and_utf8_size(text, smooth, expected):
    assert live.voice_playback_buffer(text, smooth_long=smooth) == expected


def test_complete_reply_waits_for_end_before_opening_speaker(monkeypatch):
    completed = threading.Event()
    received = []
    class Pipe(io.BytesIO):
        def close(self):
            received.append(self.getvalue())
            super().close()
    class Process:
        def __init__(self, *args, **kwargs):
            assert completed.is_set(), 'Speaker opened before audio generation finished'
            self.stdin = Pipe()
        def wait(self, timeout):
            return 0
        def poll(self):
            return 0
    monkeypatch.setattr(live.subprocess, 'Popen', Process)
    player = live.BufferedPlayer(threading.Event(), buffer_seconds=None)
    try:
        pcm = bytes(48000 * 6)
        player.feed(pcm)
        deadline = time.monotonic() + 1
        while not player.items.empty() and time.monotonic() < deadline:
            time.sleep(.001)
        assert player.proc is None
        completed.set()
        player.finish()
        assert received == [pcm]
    finally:
        player.cancel()


def test_complete_reply_buffer_remains_bounded(monkeypatch):
    player = live.BufferedPlayer(threading.Event(), buffer_seconds=None)
    try:
        player.feed(bytes(48000 * 31))
        with pytest.raises(ValueError, match='30 seconds'):
            player.finish()
    finally:
        player.cancel()


def test_forced_reading_context_has_bounded_headroom_without_truncating_reply(monkeypatch):
    seen = []
    class Response:
        status = 400
    class Connection:
        def request(self, method, path, body, headers):
            seen.append(json.loads(body))
        def getresponse(self):
            return Response()
        def close(self):
            pass
    monkeypatch.setattr(live.http.client, 'HTTPConnection', lambda *args, **kwargs: Connection())
    stream = live.LiquidStream('http://127.0.0.1:1234/v1/chat/completions', threading.Event())
    reply = 'a' * 2000
    text = 'Read this aloud: ' + reply
    with pytest.raises(RuntimeError, match='HTTP 400'):
        list(stream.events(b'', text=text, spoken_text=reply))
    assert seen[0]['messages'][1]['content'] == text
    assert seen[0]['spoken_text'] == reply
    with pytest.raises(ValueError, match='2,000'):
        list(stream.events(b'', text=text))
    with pytest.raises(ValueError, match='2,048'):
        list(stream.events(b'', text='a' * 2049, spoken_text='short'))
    assert len(seen) == 1


def test_continuous_ready_event_and_session_payload(monkeypatch):
    events = [{'speech_input_ready': True},
              {'choices': [{'delta': {'content': 'Hi'}}]},
              {'choices': [{'delta': audio_delta(b'\x00\x10' * 480)}]},
              {'choices': [{'delta': {}, 'finish_reason': 'stop'}]}]
    response = io.BytesIO(b''.join(b'data: ' + json.dumps(event).encode() + b'\n\n' for event in events))
    response.status = 200
    class Connection:
        def request(self, method, path, body, headers):
            payload = json.loads(body)
            assert payload['speech_input_id'] == 'a' * 32
            assert payload['max_tokens'] == 512 and 'spoken_text' not in payload
        def getresponse(self):
            return response
        def close(self):
            pass
    monkeypatch.setattr(live.http.client, 'HTTPConnection', lambda *args, **kwargs: Connection())
    ready = []
    stream = live.LiquidStream('http://127.0.0.1:1234/v1/chat/completions', threading.Event())
    received = list(stream.events(b'', text='Hello', speech_input_id='a' * 32, on_ready=lambda: ready.append(True)))
    assert ready == [True]
    assert received == [('text', 'Hi'), ('audio', b'\x00\x10' * 480)]
    with pytest.raises(ValueError, match='fresh continuous'):
        list(stream.events(b'', text='Hello', speech_input_id='a' * 32, spoken_text='Hi'))


def test_continuous_busy_retry_is_bounded_and_does_not_retry_other_modes(monkeypatch):
    attempts = []
    statuses = iter([409, 200])
    class Connection:
        def request(self, *args):
            attempts.append(args)
        def getresponse(self):
            status = next(statuses)
            if status == 409:
                response = io.BytesIO(b'busy')
            else:
                event = {'choices': [{'delta': audio_delta(bytes(480)), 'finish_reason': 'stop'}]}
                response = io.BytesIO(b'data: ' + json.dumps(event).encode() + b'\n\n')
            response.status = status
            return response
        def close(self):
            pass
    monkeypatch.setattr(live.http.client, 'HTTPConnection', lambda *args, **kwargs: Connection())
    monkeypatch.setattr(live.time, 'sleep', lambda delay: None)
    stream = live.LiquidStream('http://127.0.0.1:1234/v1/chat/completions', threading.Event())
    assert list(stream.events(b'', text='Hello', speech_input_id='b' * 32)) == [('audio', bytes(480))]
    assert len(attempts) == 2
    statuses = iter([409])
    with pytest.raises(RuntimeError, match='HTTP 409'):
        list(stream.events(b'', text='Hello'))
    statuses = iter([409])
    clock = iter([0., 4.])
    monkeypatch.setattr(live.time, 'monotonic', lambda: next(clock))
    with pytest.raises(RuntimeError, match='still busy'):
        list(stream.events(b'', text='Hello', speech_input_id='c' * 32))
