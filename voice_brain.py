"""Cancellable local chat completion using Sora's existing provider configuration."""

import http.client
import json
import socket
import time
from urllib.parse import urlsplit

import ai_config


class LocalVoiceBrain:
    def __init__(self, stopped):
        self.stopped = stopped
        self.connection = None
        self.metrics = {}

    def cancel(self):
        self.stopped.set()
        connection = self.connection
        if connection is not None and connection.sock is not None:
            try:
                connection.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def reply(self, messages):
        return self._complete(messages, token_limit=96)

    def warmup(self, messages):
        """Load/prefill before listening; never return a conversational reply."""
        self._complete(messages, token_limit=1, warming=True)

    def _complete(self, messages, *, token_limit, warming=False):
        started = time.monotonic()
        self.metrics = {}
        with ai_config._lock:
            config = ai_config.get_tier_config("chat")
            client = ai_config.get_tier_client("chat")
            base = str(client.base_url).rstrip("/")
            max_tokens = ai_config.resolve_max_tokens("chat", token_limit)
        url = urlsplit(base)
        if (url.scheme not in ("http", "https") or url.username or url.password
                or not ai_config._is_loopback(base)):
            raise RuntimeError("Live voice requires a configured loopback chat provider")
        if not config.get("model"):
            raise RuntimeError("Choose an installed local chat model in Sora settings")
        payload = {
            "model": config["model"], "messages": messages, "stream": True,
            "max_tokens": max_tokens, "temperature": 0.3,
        }
        headers = {"Content-Type": "application/json"}
        if config.get("api_key"):
            headers["Authorization"] = "Bearer " + config["api_key"]
        connection_type = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
        connection = connection_type(url.hostname, url.port, timeout=45)
        self.connection = connection
        words = []
        size = 0
        finish = None
        try:
            if self.stopped.is_set():
                return ""
            connection.request("POST", url.path + "/chat/completions", json.dumps(payload), headers)
            if self.stopped.is_set():
                return ""
            response = connection.getresponse()
            if response.status != 200:
                raise RuntimeError(f"Local chat provider returned HTTP {response.status}")
            while not self.stopped.is_set():
                line = response.readline(100001)
                if len(line) > 100000:
                    raise ValueError("Local chat event exceeds its size limit")
                if not line:
                    break
                if not line.startswith(b"data: "):
                    continue
                raw = line[6:].strip()
                if raw == b"[DONE]":
                    break
                event = json.loads(raw)
                if "error" in event:
                    raise RuntimeError("Local chat generation failed")
                for choice in event.get("choices", []):
                    finish = choice.get("finish_reason") or finish
                    text = (choice.get("delta") or {}).get("content") or ""
                    if text:
                        self.metrics.setdefault("first_token_s", time.monotonic() - started)
                        size += len(text.encode("utf-8"))
                        if size > 2000:
                            raise ValueError("Spoken reply exceeds 2,000 bytes")
                        words.append(text)
            if self.stopped.is_set():
                return ""
            reply = "".join(words).strip()
            if finish not in (("stop", "length") if warming else ("stop",)) or (not warming and not reply):
                raise RuntimeError("Local chat returned an incomplete reply. Ask for a shorter response")
            self.metrics["finished_s"] = time.monotonic() - started
            return reply
        finally:
            connection.close()
            self.connection = None
