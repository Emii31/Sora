"""Resident Qwen speech over private, length-prefixed PCM subprocess pipes."""

import atexit
import os
import select
import struct
import subprocess
import time

_PCM_FRAME_BYTES = 1920 * 2
_MAX_CHUNK_BYTES = 8 * _PCM_FRAME_BYTES


class QwenWorker:
    """One Qwen process. The voice backend serializes requests to it."""

    def __init__(self, command: list[str], assets: tuple):
        self.command = command
        self.assets = assets
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()

    def _read_exactly(self, size: int, deadline: float) -> bytearray:
        pipe = self.process.stdout.fileno()
        data = bytearray()
        while len(data) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([pipe], [], [], remaining)[0]:
                raise subprocess.TimeoutExpired(self.command, remaining)
            block = os.read(pipe, size - len(data))
            if not block:
                raise EOFError("Qwen worker exited during synthesis")
            data.extend(block)
        return data

    def render(self, text: str, *, timeout: int, max_frames: int) -> bytes:
        line = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
        if not line.strip() or "\0" in line:
            raise ValueError("Qwen worker needs a nonempty line of text")
        deadline = time.monotonic() + timeout
        self.process.stdin.write((line + "\n").encode("utf-8"))
        pcm = bytearray()
        size = struct.unpack("<I", self._read_exactly(4, deadline))[0]
        while size:
            if size % _PCM_FRAME_BYTES or size > _MAX_CHUNK_BYTES or len(pcm) + size > max_frames * _PCM_FRAME_BYTES:
                raise EOFError("Invalid Qwen PCM chunk size")
            pcm.extend(self._read_exactly(size, deadline))
            size = struct.unpack("<I", self._read_exactly(4, deadline))[0]
        return bytes(pcm)


_worker: QwenWorker | None = None


@atexit.register
def close_worker():
    global _worker
    if _worker is not None:
        _worker.close()
        _worker = None


def render(command: list[str], text: str, *, timeout: int, max_frames: int, assets: tuple = ()) -> bytes:
    global _worker
    if (_worker is None or _worker.process.poll() is not None
            or _worker.command != command or _worker.assets != assets):
        close_worker()
        _worker = QwenWorker(command, assets)
    try:
        return _worker.render(text, timeout=timeout, max_frames=max_frames)
    except (OSError, subprocess.TimeoutExpired, EOFError):
        close_worker()
        raise
