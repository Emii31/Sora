import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import auth
import character
import core_memory
import storage
from voice_context import LocalVoiceContext


@pytest.fixture
def local_data(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(storage, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(auth, "_BASE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(auth, "_ADMIN_DIR", str(tmp_path / "_admin"))
    monkeypatch.setattr(core_memory, "CORE_MEMORY_PATH", str(tmp_path / "core_memory.json"))
    monkeypatch.setattr(character, "_configs", {})
    (tmp_path / "_admin").mkdir()
    return tmp_path


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def make_account(root, uid, name, memory):
    directory = root / "users" / uid
    directory.mkdir(parents=True)
    soul = directory / "personas" / "selected" / "soul.md"
    soul.parent.mkdir(parents=True)
    soul.write_text(f"# Identity\n- **Name**: {name}\n- **User Address**: you\n"
                    "# Personality\nWarm and playful.\n# Prompt Hints\n- archetype: A gentle girl\n")
    save_json(directory / "model_library.json", {"active_model_id": "selected", "models": [{"id": "selected"}]})
    save_json(directory / "core_memory.json", {"human": {"value": memory}, "persona": {"value": "We enjoy chatting."}})
    save_json(directory / "identity.json", {"name": uid + "-name"})
    save_json(directory / "chat_history.json", [])
    return directory


def test_account_persona_memory_and_identity_are_isolated(local_data):
    save_json(local_data / "_admin/users.json", {"a": {"status": "active"}, "b": {"status": "active"}})
    make_account(local_data, "a", "Lumen", "Likes jasmine tea.")
    make_account(local_data, "b", "Nova", "Other-user secret: peppermint.")
    save_json(local_data / "core_memory.json", {"human": {"value": "Root secret must stay out."}})
    snapshot = LocalVoiceContext("a").prepare("Who are you?")
    assert snapshot.character_name == "Lumen"
    assert snapshot.system_prompt.startswith("You are Lumen")
    for text in ("Lumen", "jasmine", "a-name", "Warm and playful", "live voice", "one short sentence"):
        assert text in snapshot.system_prompt
    for text in ("peppermint", "Root secret", "text-only chat", "Nova", "b-name"):
        assert text not in snapshot.system_prompt
    with pytest.raises(ValueError, match="Several accounts"):
        LocalVoiceContext()
    with pytest.raises(ValueError, match="active"):
        LocalVoiceContext("missing")


def test_legacy_memory_and_restart_history_are_shared(local_data):
    save_json(local_data / "core_memory.json", {"human": {"value": "The user likes jasmine."}})
    context = LocalVoiceContext()
    snapshot = context.prepare("My plant is Juniper.")
    assert "jasmine" in snapshot.system_prompt and snapshot.character_name == "Sora"
    assert context.commit(snapshot, "Juniper is a lovely name.")
    assert context.commit(snapshot, "Juniper is a lovely name.") is False
    saved = json.loads((local_data / "chat_history.json").read_text())
    assert len(saved) == 2 and saved[1]["id"] == saved[0]["id"] + "_reply"
    restarted = LocalVoiceContext().prepare("What did I name my plant?")
    assert "My plant is Juniper." in str(restarted.messages)
    assert "Juniper is a lovely name." in str(restarted.messages)
    assert "What did I name my plant?" not in restarted.system_prompt
    with pytest.raises(ValueError, match="conflicts"):
        context.commit(snapshot, "A different reply")
    assert len(json.loads((local_data / "chat_history.json").read_text())) == 2


def test_dangling_user_turn_and_bounded_history_are_preserved(local_data):
    history = [{"role": "user", "text": "Discard old turn"}] + [
        {"role": role, "text": label + "🙂" * 500}
        for role, label in (("assistant", "reply1"), ("user", "question2"), ("assistant", "reply2"),
                            ("assistant", "reply3"), ("user", "unanswered question"))
    ]
    save_json(local_data / "chat_history.json", history)
    snapshot = LocalVoiceContext().prepare("New message")
    assert "Discard old turn" not in snapshot.system_prompt
    assert "unanswered question" in str(snapshot.messages)
    assert "�" not in snapshot.system_prompt
    assert snapshot.user_text == "New message"
    assert len(str(snapshot.messages).encode()) < 6500


def test_context_reload_respects_selected_character_changes(local_data):
    save_json(local_data / "_admin/users.json", {"a": {"status": "active"}})
    directory = make_account(local_data, "a", "Lumen", "Likes jasmine.")
    context = LocalVoiceContext()
    assert context.prepare("Hi").character_name == "Lumen"
    soul = directory / "personas/selected/soul.md"
    soul.write_text(soul.read_text().replace("Lumen", "Nova"))
    assert context.prepare("Hi again").character_name == "Nova"


def test_account_deletion_blocks_commit_and_recreation(local_data):
    import shutil

    save_json(local_data / "_admin/users.json", {"a": {"status": "active"}})
    directory = make_account(local_data, "a", "Lumen", "Saved fact")
    context = LocalVoiceContext()
    snapshot = context.prepare("Hello")
    save_json(local_data / "_admin/users.json", {})
    shutil.rmtree(directory)
    with pytest.raises(RuntimeError, match="no longer active"):
        context.commit(snapshot, "Hello back")
    assert not directory.exists()


def test_snapshot_cannot_cross_accounts(local_data):
    save_json(local_data / "_admin/users.json", {"a": {"status": "active"}, "b": {"status": "active"}})
    make_account(local_data, "a", "Lumen", "A fact")
    make_account(local_data, "b", "Nova", "B fact")
    snapshot = LocalVoiceContext("a").prepare("Hi")
    with pytest.raises(ValueError, match="another account"):
        LocalVoiceContext("b").commit(snapshot, "Hello")


def test_legacy_context_stops_when_account_configuration_changes(local_data):
    context = LocalVoiceContext()
    snapshot = context.prepare("Hi")
    save_json(local_data / "_admin/users.json", {"a": {"status": "active"}})
    with pytest.raises(RuntimeError, match="configuration changed"):
        context.commit(snapshot, "Hello")


def test_corrupt_history_is_preserved(local_data):
    history = local_data / "chat_history.json"
    history.write_text("{broken")
    with pytest.raises(ValueError):
        LocalVoiceContext().prepare("Hi")
    assert history.read_text() == "{broken"


def test_chat_append_is_serialized_across_processes(local_data):
    code = """
import storage,sys
for i in range(8):
    storage.append_chat_message({'id': sys.argv[1]+str(i), 'role': 'user', 'text': 'ordinary chat', 'time': '2026-01-01 12:00:00'})
    storage.append_voice_exchange('voice_'+sys.argv[1]+str(i), 'hello', 'hello back', '2026-01-01 12:00:00')
    storage.archive_old_chat_messages(4)
"""
    processes = [subprocess.Popen([sys.executable, "-B", "-c", code, str(i)],
                                 env=dict(os.environ, DATA_DIR=str(local_data)),
                                 cwd=str(Path(__file__).resolve().parents[1]),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                 for i in range(3)]
    for process in processes:
        _, error = process.communicate(timeout=20)
        assert process.returncode == 0, error
    active = json.loads((local_data / "chat_history.json").read_text())
    archived = json.loads((local_data / "archive/chat_history_2026-01.json").read_text())
    ids = [item["id"] for item in active + archived]
    assert len(ids) == len(set(ids)) == 72


@pytest.mark.parametrize("outcome", ["complete", "cancel", "error", "mismatch"])
def test_live_turn_persists_only_completed_exchange(local_data, monkeypatch, outcome):
    import time

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import live_liquid_voice as cli

    class Stream:
        def __init__(self, endpoint, stopped):
            self.stopped = stopped
        def events(self, wav, **options):
            assert options["text"] == "Please speak to me."
            assert options["spoken_text"] == "Hello from Sora"
            yield "text", "Different reply" if outcome == "mismatch" else "Hello from Sora"
            if outcome == "cancel":
                self.stopped.set()
            yield "audio", bytes(480)
            if outcome == "error":
                raise RuntimeError("Generation failed")
    class Player:
        def __init__(self, stopped, *args):
            self.stopped = stopped
            self.started_at = time.monotonic()
            self.bytes_written = 0
            self.estimated_gaps = 0
        def feed(self, pcm):
            self.bytes_written += len(pcm)
        def finish(self):
            pass
        def cancel(self):
            self.stopped.set()
    class Brain:
        def __init__(self, stopped):
            pass
        def reply(self, messages):
            assert "Your conversational name is Sora" in messages[0]["content"]
            assert messages[-1]["content"] == "Hello"
            return "Hello from Sora"
    monkeypatch.setattr(cli, "LiquidStream", Stream)
    monkeypatch.setattr(cli, "BufferedPlayer", Player)
    monkeypatch.setattr(cli, "LocalVoiceBrain", Brain)
    turn = cli.VoiceTurn("http://127.0.0.1", context=LocalVoiceContext())
    turn.microphone.transcript = "Hello"
    turn.run(b"fixture")
    saved = json.loads((local_data / "chat_history.json").read_text())
    if outcome == "complete":
        assert len(saved) == 2 and saved[1]["text"] == "Hello from Sora"
        assert turn.metrics["history_saved"] is True
    else:
        assert saved == []
        if outcome in ("error", "mismatch"):
            assert turn.error is not None
