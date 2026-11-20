"""Bounded text input for one continuous, session-owned Liquid speech request."""
import http.client
import json
import socket
import threading
import time
from uuid import uuid4

from voice_liquid_live import LiquidStream


class ContinuousLiquid:
    def __init__(self, endpoint, stopped):
        self.stream = LiquidStream(endpoint, stopped)
        self.stopped = stopped
        self.identifier = uuid4().hex
        self.ready = threading.Event()
        self.closed = threading.Event()
        self.input_connection = None
        self.accepted = ''
        self.final = False

    def events(self, wav, *, text):
        try:
            yield from self.stream.events(wav, text=text, speech_input_id=self.identifier, on_ready=self.ready.set)
        finally:
            self.closed.set()

    def append(self, text, *, final=False):
        if self.stopped.is_set():
            return
        if self.closed.is_set():
            raise RuntimeError('Continuous speech session is closed')
        if (self.final or (not text and (not final or not self.accepted))
                or len((self.accepted + text).encode('utf-8')) > 2000):
            raise ValueError('Continuous speech input is closed, empty or over 2,000 bytes')
        deadline = time.monotonic() + 10
        while not self.ready.wait(.05):
            if self.stopped.is_set():
                return
            if self.closed.is_set() or time.monotonic() > deadline:
                raise RuntimeError('Continuous speech session did not become ready')
        if self.stopped.is_set():
            return
        connection = http.client.HTTPConnection(self.stream.url.hostname, self.stream.url.port, timeout=5)
        self.input_connection = connection
        try:
            connection.request('POST', '/v1/speech-input/' + self.identifier,
                               json.dumps({'text': text, 'final': final}), {'Content-Type': 'application/json'})
            response = connection.getresponse()
            response.read(4096)
            if response.status != 200:
                raise RuntimeError(f'Continuous speech input returned HTTP {response.status}')
            self.accepted += text
            self.final = final
        finally:
            connection.close()
            self.input_connection = None

    def abort(self):
        connection = self.input_connection
        if connection is not None and connection.sock is not None:
            try:
                connection.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        # Only this request's unpredictable session ID is cancelled.
        control = http.client.HTTPConnection(self.stream.url.hostname, self.stream.url.port, timeout=1)
        try:
            control.request('DELETE', '/v1/speech-input/' + self.identifier)
            control.getresponse().read(4096)
        except (OSError, http.client.HTTPException):
            pass
        finally:
            control.close()
        self.stream.abort()
        self.closed.set()

    def cancel(self):
        self.stopped.set()
        self.abort()
