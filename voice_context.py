"""Account-scoped personality, saved memory, and history for live voice."""

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from flask import Flask, g

import auth
import character
import core_memory
import prompt
import storage
import user_settings


@dataclass(frozen=True)
class VoiceSnapshot:
    system_prompt: str
    user_text: str
    turn_id: str
    timestamp: str
    user_id: str
    data_dir: str
    character_name: str
    messages: tuple


class LocalVoiceContext:
    """Trusted local CLI adapter using the same files as ordinary Sora chat."""

    def __init__(self, user_id=None):
        users = auth.list_users()
        active = [uid for uid, user in users.items() if user.get("status") == "active"]
        if user_id:
            if user_id not in active:
                raise ValueError("Choose an active Sora account")
        elif len(active) == 1:
            user_id = active[0]
        elif active:
            raise ValueError("Several accounts are active. Select one with --user-id")
        elif users:
            raise ValueError("No active Sora account is available")
        self.user_id = user_id or "_voice_legacy"
        self.data_dir = str(Path(auth.get_user_data_dir(user_id) if user_id else storage.DATA_DIR).resolve())
        self.flask = Flask("sora_live_voice_context")

    @contextmanager
    def _scope(self):
        if self.user_id == "_voice_legacy":
            if auth.list_users():
                raise RuntimeError("Account configuration changed. Restart voice with the active account")
        else:
            user = auth.get_user(self.user_id)
            if not user or user.get("status") != "active":
                raise RuntimeError("The selected Sora account is no longer active")
        with self.flask.app_context():
            g.user_id = self.user_id
            g.user_data_dir = self.data_dir
            g.is_admin = False
            storage.get_data_dir()
            yield

    def prepare(self, user_text=None):
        text = user_text if user_text is not None else "[Voice input]"
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError("Voice input text must contain 1 to 2,000 characters")
        with self._scope():
            cfg = character.reload_config()
            history = storage.get_chat_history(limit=prompt.FAST_LOCAL_HISTORY_MESSAGES)
            if not isinstance(history, list) or any(not isinstance(item, dict) for item in history):
                raise ValueError("Saved chat history is invalid")
            try:
                blocks = core_memory.get_all_blocks()
            except (OSError, ValueError, AttributeError):
                print("Saved core memory is unavailable for this turn.", flush=True)
                blocks = {}
            messages = prompt.build_fast_local_chat_messages(history, text, core_blocks=blocks, voice=True)
            return VoiceSnapshot(
                messages[0]["content"], text, "voice_" + uuid4().hex,
                user_settings.user_now().strftime("%Y-%m-%d %H:%M:%S"),
                self.user_id, self.data_dir, cfg.name, tuple(messages),
            )

    def respond(self, snapshot, brain, *, on_sentence=None):
        if (snapshot.user_id, snapshot.data_dir) != (self.user_id, self.data_dir):
            raise ValueError("Voice context belongs to another account")
        with self._scope():
            if on_sentence is not None:
                return brain.reply(list(snapshot.messages), on_sentence=on_sentence)
            return brain.reply(list(snapshot.messages))

    def warmup(self, brain):
        snapshot = self.prepare("Hello")
        with self._scope():
            brain.warmup(list(snapshot.messages))

    def commit(self, snapshot, reply_text):
        if (snapshot.user_id, snapshot.data_dir) != (self.user_id, self.data_dir):
            raise ValueError("Voice context belongs to another account")
        with self._scope():
            return storage.append_voice_exchange(snapshot.turn_id, snapshot.user_text, reply_text, snapshot.timestamp)
