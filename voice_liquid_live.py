"""Local Liquid streaming, bounded microphone capture, and cancellable playback."""

from array import array
import base64
from collections import deque
import http.client
import io
import json
import math
import os
from pathlib import Path
import queue
import selectors
import socket
import subprocess
import threading
import time
from urllib.parse import urlsplit
import wave

INPUT_RATE = 16000
OUTPUT_RATE = 24000
SYSTEM_PROMPT = "Respond with interleaved text and audio."


def voice_playback_buffer(text, *, smooth_long=False):
    """Prefer earlier short replies; optionally fully buffer long speech."""
    if text is None:
        return 1.5
    size = len(text.encode("utf-8"))
    words = len(text.split())
    if size <= 64 and words <= 8:
        return 0.5
    if size <= 100 and words <= 16:
        return 1.5
    return None if smooth_long else 1.5


def stop_process(proc):
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)


def pcm_from_delta(delta):
    packet = delta.get("audio") or delta.get("audio_chunk")
    if not packet:
        return b""
    raw = base64.b64decode(packet["data"], validate=True)
    if "audio" in delta:
        if packet.get("format") != "pcm" or packet.get("sample_rate") != OUTPUT_RATE:
            raise ValueError("Unexpected Liquid PCM format")
        if len(raw) % 2:
            raise ValueError("Incomplete Liquid PCM frame")
        return raw
    if not raw or len(raw) % 4:
        raise ValueError("Incomplete Liquid float PCM frame")
    samples = array("f")
    samples.frombytes(raw)
    if not all(map(math.isfinite, samples)):
        raise ValueError("Invalid Liquid float PCM samples")
    return array("h", (round(max(-1., min(1., x)) * 32767) for x in samples)).tobytes()


class LiquidStream:
    def __init__(self, endpoint, stopped):
        self.url = urlsplit(endpoint)
        if (self.url.scheme != "http" or self.url.hostname != "127.0.0.1"
                or self.url.username or self.url.password):
            raise ValueError("Liquid must use a loopback HTTP endpoint")
        self.stopped = stopped
        self.connection = None

    def cancel(self):
        self.stopped.set()
        self.abort()

    def abort(self):
        """Interrupt a pipeline failure without marking it as a user cancellation."""
        connection = self.connection
        if connection is not None and connection.sock is not None:
            try:
                connection.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def events(self, wav, *, text=None, system_prompt=SYSTEM_PROMPT, spoken_text=None,
               speech_input_id=None, on_ready=None):
        from voice_input import MAX_SECONDS, _read_pcm

        if text is None:
            _read_pcm(wav, MAX_SECONDS)
            content = [{"type": "input_audio", "input_audio": {
                "data": base64.b64encode(wav).decode("ascii"), "format": "wav"}}]
        else:
            text_limit = 2048 if spoken_text is not None else 2000
            if not isinstance(text, str) or not text.strip() or len(text) > text_limit:
                raise ValueError(f"Send a nonempty transcript of at most {text_limit:,} characters")
            content = text
        payload = {
            "stream": True, "reset_context": True, "max_tokens": 256,
            "modalities": ["text", "audio"],
            "messages": [{"role": "system", "content": system_prompt}, {
                "role": "user", "content": content}],
        }
        if spoken_text is not None:
            if not spoken_text.strip() or len(spoken_text.encode("utf-8")) > 2000:
                raise ValueError("Send a spoken reply of 1 to 2,000 bytes")
            payload["spoken_text"] = spoken_text
            payload["max_tokens"] = 512
        if speech_input_id is not None:
            if (spoken_text is not None or len(speech_input_id) != 32
                    or any(c not in '0123456789abcdef' for c in speech_input_id)):
                raise ValueError("Use a fresh continuous speech ID without fixed spoken text")
            payload["speech_input_id"] = speech_input_id
            payload["max_tokens"] = 512
        connection = http.client.HTTPConnection(self.url.hostname, self.url.port, timeout=45)
        self.connection = connection
        received = 0
        finish = None
        try:
            if self.stopped.is_set():
                return
            busy_deadline = time.monotonic() + 3
            while True:
                if self.stopped.is_set():
                    return
                connection.request("POST", self.url.path, json.dumps(payload), {"Content-Type": "application/json"})
                if self.stopped.is_set():
                    return
                response = connection.getresponse()
                if response.status != 409 or speech_input_id is None:
                    break
                response.read(4096)
                connection.close()
                if time.monotonic() >= busy_deadline:
                    raise RuntimeError("Continuous speech session is still busy after cancellation")
                time.sleep(.05)
                connection = http.client.HTTPConnection(self.url.hostname, self.url.port, timeout=45)
                self.connection = connection
            if response.status != 200:
                raise RuntimeError(f"Liquid returned HTTP {response.status}")
            while not self.stopped.is_set():
                line = response.readline(2_000_001)
                if len(line) > 2_000_000:
                    raise ValueError("Liquid stream event exceeds its size limit")
                if not line:
                    break
                if not line.startswith(b"data: "):
                    continue
                data = line[6:].strip()
                if data == b"[DONE]":
                    break
                event = json.loads(data)
                if event.get("speech_input_ready") and on_ready:
                    on_ready()
                if "error" in event:
                    raise RuntimeError("Liquid generation failed")
                for choice in event.get("choices", []):
                    finish = choice.get("finish_reason") or finish
                    delta = choice.get("delta") or {}
                    if delta.get("content"):
                        yield "text", delta["content"]
                    pcm = pcm_from_delta(delta)
                    if pcm:
                        received += len(pcm)
                        if received > OUTPUT_RATE * 2 * 30:
                            raise ValueError("Liquid reply exceeds 30 seconds")
                        yield "audio", pcm
            if not self.stopped.is_set() and (finish != "stop" or not received):
                raise RuntimeError("Liquid returned an incomplete reply")
        finally:
            connection.close()
            self.connection = None


class EndpointDetector:
    """Detect a bounded utterance from consecutive 20 ms PCM blocks."""

    def __init__(self, threshold=0.015, silence_ms=900, max_seconds=20):
        self.threshold = threshold
        self.silence_frames = math.ceil(silence_ms / 20)
        self.max_frames = max_seconds * 50
        self.preroll = deque(maxlen=18)
        self.frames = []
        self.voiced = 0
        self.quiet = 0

    def feed(self, pcm):
        if len(pcm) != 640:
            raise ValueError("Capture requires 20 ms, 16 kHz PCM16 frames")
        samples = array("h")
        samples.frombytes(pcm)
        energy = math.sqrt(sum(x*x for x in samples) / len(samples)) / 32768
        loud = energy >= self.threshold
        if not self.frames:
            self.preroll.append(pcm)
            self.voiced = self.voiced + 1 if loud else 0
            if self.voiced >= 8:
                self.frames.extend(self.preroll)
            return False
        self.frames.append(pcm)
        self.quiet = 0 if loud else self.quiet + 1
        return self.quiet >= self.silence_frames or len(self.frames) >= self.max_frames

    def wav(self):
        if not self.frames:
            raise ValueError("No utterance was detected")
        result = io.BytesIO()
        with wave.open(result, "wb") as recording:
            recording.setparams((1, 2, INPUT_RATE, 0, "NONE", "not compressed"))
            recording.writeframes(b"".join(self.frames))
        return result.getvalue()


class Microphone:
    def __init__(self, stopped, source=None, threshold=0.015, vosk_model=None, silence_ms=900):
        self.stopped = stopped
        self.source = source
        self.threshold = threshold
        self.silence_ms = silence_ms
        self.proc = None
        self.vosk_model = vosk_model
        self.transcript = None
        self.speech_ended_at = None
        self.timings = {}

    def cancel(self):
        self.stopped.set()
        stop_process(self.proc)

    def capture(self):
        self.transcript = None
        self.speech_ended_at = None
        self.timings = {}
        command = ["pw-record", "--raw", "--rate", "16000", "--channels", "1",
                   "--format", "s16", "--latency", "20ms"]
        if self.source:
            command.extend(["--target", self.source])
        command.append("-")
        detector = EndpointDetector(threshold=self.threshold, silence_ms=self.silence_ms)
        recognizer = None
        segments = []
        if self.vosk_model:
            from voice_input import _load_model

            model, factory = _load_model(Path(self.vosk_model))
            recognizer = factory(model, INPUT_RATE)
        self.proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        pending = bytearray()
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(self.proc.stdout, selectors.EVENT_READ)
                deadline = time.monotonic() + 45
                while not self.stopped.is_set() and time.monotonic() < deadline:
                    if not selector.select(timeout=0.1):
                        continue
                    data = os.read(self.proc.stdout.fileno(), 4096)
                    if not data:
                        raise RuntimeError("Microphone capture stopped unexpectedly")
                    pending.extend(data)
                    while len(pending) >= 640:
                        frame = bytes(pending[:640])
                        del pending[:640]
                        if recognizer and recognizer.AcceptWaveform(frame):
                            segments.append(json.loads(recognizer.Result()).get("text", ""))
                        if detector.feed(frame):
                            endpoint_at = time.monotonic()
                            self.timings["capture_end_reason"] = "limit"
                            if detector.quiet >= detector.silence_frames:
                                silence_s = detector.quiet * .02
                                self.speech_ended_at = endpoint_at - silence_s
                                self.timings.update(capture_end_reason="silence", endpoint_silence_s=silence_s)
                            if recognizer:
                                segments.append(json.loads(recognizer.FinalResult()).get("text", ""))
                                self.transcript = " ".join(segment.strip() for segment in segments if segment.strip())
                                self.timings["recognition_finalize_s"] = time.monotonic() - endpoint_at
                                if not self.transcript:
                                    return None
                            return detector.wav()
            return None
        finally:
            close_started = time.monotonic()
            stop_process(self.proc)
            self.proc.stdout.close()
            self.timings["capture_close_s"] = time.monotonic() - close_started


class BufferedPlayer:
    def __init__(self, stopped, buffer_seconds=1.5, sink=None):
        if buffer_seconds is not None and not 0 <= buffer_seconds <= 5:
            raise ValueError("Playback buffer must be between zero and five seconds")
        self.stopped = stopped
        self.buffer_bytes = None if buffer_seconds is None else round(buffer_seconds * OUTPUT_RATE) * 2
        self.sink = sink
        self.proc = None
        self.items = queue.Queue(maxsize=128)
        self.error = None
        self.started_at = None
        self.bytes_written = 0
        self.estimated_gaps = 0
        self.play_until = None
        self.thread = threading.Thread(target=self._run, name="liquid-playback", daemon=True)
        self.thread.start()

    def feed(self, pcm):
        while not self.stopped.is_set():
            if self.error:
                raise self.error
            try:
                self.items.put(pcm, timeout=0.1)
                return
            except queue.Full:
                pass

    def _write(self, pcm):
        now = time.monotonic()
        if self.started_at is None:
            command = ["pw-play", "--raw", "--rate", "24000", "--channels", "1",
                       "--format", "s16", "--latency", "40ms"]
            if self.sink:
                command.extend(["--target", self.sink])
            command.append("-")
            self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.started_at = time.monotonic()
            self.play_until = self.started_at
            now = self.started_at
        elif now > self.play_until + 0.05:
            self.estimated_gaps += 1
        if not self.stopped.is_set():
            self.proc.stdin.write(pcm)
            self.proc.stdin.flush()
            self.bytes_written += len(pcm)
            self.play_until = max(now, self.play_until) + len(pcm) / (OUTPUT_RATE * 2)

    def _run(self):
        pending = bytearray()
        try:
            while not self.stopped.is_set():
                try:
                    pcm = self.items.get(timeout=0.1)
                except queue.Empty:
                    continue
                if pcm is None:
                    if pending:
                        self._write(pending)
                    if self.proc:
                        self.proc.stdin.close()
                        if self.proc.wait(timeout=45) != 0 and not self.stopped.is_set():
                            raise RuntimeError("Speaker playback failed")
                    return
                if self.started_at is None:
                    pending.extend(pcm)
                    if self.buffer_bytes is None:
                        if len(pending) > OUTPUT_RATE * 2 * 30:
                            raise ValueError("Buffered speech exceeds 30 seconds")
                        continue
                    if len(pending) < self.buffer_bytes:
                        continue
                    self._write(pending)
                    pending.clear()
                else:
                    self._write(pcm)
        except Exception as exc:
            self.error = exc
        finally:
            stop_process(self.proc)
            if self.proc and self.proc.stdin and not self.proc.stdin.closed:
                try:
                    self.proc.stdin.close()
                except BrokenPipeError:
                    pass

    def finish(self):
        self.feed(None)
        while self.thread.is_alive() and not self.stopped.is_set():
            self.thread.join(timeout=0.1)
        if self.error and not self.stopped.is_set():
            raise self.error

    def cancel(self):
        self.stopped.set()
        stop_process(self.proc)
        self.thread.join(timeout=3)
