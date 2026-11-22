"""Experimental loopback speech backend for the native Sopro runtime."""

import base64
from contextlib import contextmanager
import http.client
import json
from pathlib import Path
import socket
import subprocess
import threading
import time
from urllib.parse import urlsplit
import wave

from voice_liquid_live import OUTPUT_RATE, stop_process


class SoproStream:
    def __init__(self, endpoint, stopped, reference):
        self.url = urlsplit(endpoint)
        if (self.url.scheme != "http" or self.url.hostname != "127.0.0.1"
                or self.url.username or self.url.password or self.url.query or self.url.fragment):
            raise ValueError("Sopro requires a loopback HTTP endpoint")
        self.stopped = stopped
        self.reference = str(Path(reference).resolve())
        self.connection = None

    def cancel(self):
        self.stopped.set()
        connection = self.connection
        if connection is not None and connection.sock is not None:
            try:
                connection.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def events(self, wav=None, *, text=None, spoken_text=None):
        if not spoken_text or len(spoken_text.encode("utf-8")) > 2000:
            raise ValueError("Sopro needs a complete reply of at most 2,000 bytes")
        body = json.dumps({
            "model": "sopro", "input": spoken_text, "voice_ref": self.reference,
            "response_format": "pcm", "stream_format": "sse",
            "options": {"language": "en"},
        })
        connection = http.client.HTTPConnection(self.url.hostname, self.url.port, timeout=30)
        self.connection = connection
        received = 0
        complete = False
        try:
            if self.stopped.is_set():
                return
            connection.request("POST", self.url.path, body, {"Content-Type": "application/json"})
            response = connection.getresponse()
            if response.status != 200:
                raise RuntimeError(f"Sopro returned HTTP {response.status}")
            while not self.stopped.is_set():
                line = response.readline(256001)
                if len(line) > 256000:
                    raise ValueError("Sopro event exceeds its size limit")
                if not line:
                    break
                if not line.startswith(b"data:"):
                    continue
                payload = line[5:].strip()
                if payload == b"[DONE]":
                    break
                event = json.loads(payload)
                kind = event.get("type")
                if kind == "speech.audio.done":
                    complete = True
                    break
                if kind != "speech.audio.delta":
                    raise RuntimeError("Sopro returned an unexpected speech event")
                if (event.get("sample_rate", OUTPUT_RATE) != OUTPUT_RATE
                        or event.get("channels", 1) != 1):
                    raise ValueError("Unexpected Sopro audio format")
                pcm = base64.b64decode(event["audio"], validate=True)
                received += len(pcm)
                if not pcm or len(pcm) % 2 or received > OUTPUT_RATE * 2 * 30:
                    raise ValueError("Sopro returned invalid or oversized speech")
                yield "audio", pcm
            if not self.stopped.is_set():
                if not complete or not received:
                    raise RuntimeError("Sopro returned incomplete speech")
                yield "text", spoken_text
        finally:
            connection.close()
            self.connection = None


@contextmanager
def sopro_session(runtime, model, reference, directory):
    runtime, model, reference = (Path(p).resolve(strict=True) for p in (runtime, model, reference))
    with wave.open(str(reference), "rb") as audio:
        if audio.getnchannels() != 1 or not 5 <= audio.getnframes() / audio.getframerate() <= 20:
            raise ValueError("Select a mono reference WAV containing 5–20 seconds of speech")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    config = directory / "sopro-config.json"
    config.write_text(json.dumps({"models": [{
        "id": "sopro", "path": str(model), "family": "sopro_tts",
        "task": "tts", "mode": "streaming",
        "session_options": {"sopro_tts.voice_cache_slots": 1, "sopro_tts.matmul_weight_type": "q8_0"},
    }]}))
    binary = runtime / "audiocpp_server"
    process = subprocess.Popen([
        str(binary), "--config", str(config.resolve()), "--no-ui",
        "--host", "127.0.0.1", "--port", str(port), "--backend", "cpu", "--threads", "4",
    ], cwd=runtime, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    endpoint = f"http://127.0.0.1:{port}/v1/audio/speech"
    try:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Sopro runtime exited during startup")
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            try:
                connection.request("GET", "/health")
                if connection.getresponse().status == 200:
                    break
            except OSError:
                time.sleep(.2)
            finally:
                connection.close()
        else:
            raise TimeoutError("Sopro runtime did not start")
        for _ in SoproStream(endpoint, threading.Event(), reference).events(spoken_text="I am right here."):
            pass
        yield endpoint
    finally:
        stop_process(process)
