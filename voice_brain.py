"""Cancellable local chat completion using Sora's existing provider configuration."""

import http.client
import json
import socket
from urllib.parse import urlsplit

import ai_config


class LocalVoiceBrain:
    def __init__(self, stopped):
        self.stopped = stopped
        self.connection = None

    def cancel(self):
        self.stopped.set()
        connection = self.connection
        if connection is not None and connection.sock is not None:
            try:
                connection.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def reply(self, messages):
        with ai_config._lock:
            config = ai_config.get_tier_config("chat")
            client = ai_config.get_tier_client("chat")
            base = str(client.base_url).rstrip("/")
            max_tokens = ai_config.resolve_max_tokens("chat", 96)
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
                        size += len(text.encode("utf-8"))
                        if size > 2000:
                            raise ValueError("Spoken reply exceeds 2,000 bytes")
                        words.append(text)
            if self.stopped.is_set():
                return ""
            reply = "".join(words).strip()
            if finish != "stop" or not reply:
                raise RuntimeError("Local chat returned an incomplete reply. Ask for a shorter response")
            return reply
        finally:
            connection.close()
            self.connection = None
