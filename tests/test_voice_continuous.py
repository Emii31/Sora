"""Bounded continuous speech controls and complete-turn persistence."""
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import pytest

import voice_continuous


@pytest.fixture
def controls(monkeypatch):
    seen = []
    status = [200]
    class Connection:
        sock = None
        def __init__(self, *args, **kwargs):
            pass
        def request(self, method, path, body=None, headers=None):
            seen.append((method, path, json.loads(body) if body else None))
        def getresponse(self):
            return SimpleNamespace(status=status[0], read=lambda limit: b'{"ok":true}')
        def close(self):
            pass
    monkeypatch.setattr(voice_continuous.http.client, 'HTTPConnection', Connection)
    speech = voice_continuous.ContinuousLiquid('http://127.0.0.1:18086/v1/chat/completions', threading.Event())
    speech.ready.set()
    return speech, seen, status


def test_updates_are_exact_bounded_and_finalized_once(controls):
    speech, seen, _ = controls
    speech.append('Hello ')
    speech.append('温🙂', final=True)
    assert speech.accepted == 'Hello 温🙂' and speech.final
    assert all(row[1] == '/v1/speech-input/' + speech.identifier for row in seen)
    assert [row[2] for row in seen] == [{'text': 'Hello ', 'final': False}, {'text': '温🙂', 'final': True}]
    with pytest.raises(ValueError):
        speech.append('More')


def test_failed_update_does_not_advance_accepted_text(controls):
    speech, _, status = controls
    status[0] = 409
    with pytest.raises(RuntimeError, match='409'):
        speech.append('Hello')
    assert speech.accepted == '' and not speech.final


def test_empty_and_oversized_input_is_rejected_before_network(controls):
    speech, seen, _ = controls
    for text, final in [('', False), ('', True), ('温' * 667, False)]:
        with pytest.raises(ValueError):
            speech.append(text, final=final)
    assert not seen


def test_cancel_targets_only_owned_session_and_unblocks_waiter(controls):
    speech, seen, _ = controls
    speech.cancel()
    assert speech.stopped.is_set() and speech.closed.is_set()
    assert seen == [('DELETE', '/v1/speech-input/' + speech.identifier, None)]


def test_closed_stream_does_not_wait_for_readiness(controls):
    speech, _, _ = controls
    speech.ready.clear()
    speech.closed.set()
    with pytest.raises(RuntimeError, match='closed'):
        speech.append('Hello')


@pytest.mark.parametrize('outcome', ['complete', 'brain_error', 'speech_error', 'mismatch', 'cancel'])
@pytest.mark.parametrize('padded', [False, True])
def test_continuous_pipeline_speaks_before_completion_and_saves_only_complete(monkeypatch, tmp_path, outcome, padded):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    import live_liquid_voice as cli
    import auth
    import character
    import core_memory
    import storage
    from voice_context import LocalVoiceContext

    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setattr(storage, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(auth, '_BASE_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(auth, '_ADMIN_DIR', str(tmp_path / '_admin'))
    monkeypatch.setattr(core_memory, 'CORE_MEMORY_PATH', str(tmp_path / 'core_memory.json'))
    monkeypatch.setattr(character, '_configs', {})
    played = threading.Event()
    aborted = threading.Event()
    class Speech:
        def __init__(self, endpoint, stopped):
            self.stopped = stopped
            self.text = ''
            self.changed = threading.Event()
            self.final = False
        def append(self, text, *, final=False):
            self.text += text
            self.final = final
            self.changed.set()
        def events(self, wav, *, text):
            assert text == 'Hello', 'Speaker did not retain the actual user context'
            if outcome == 'speech_error':
                raise RuntimeError('Speech failed')
            offset = 0
            while not self.stopped.is_set():
                if self.changed.wait(.05):
                    self.changed.clear()
                    current = self.text[offset:]
                    offset = len(self.text)
                    if current:
                        yield 'text', 'Wrong reply' if outcome == 'mismatch' else current
                        yield 'audio', bytes(480)
                    if self.final:
                        return
        def cancel(self):
            self.stopped.set()
            self.changed.set()
        def abort(self):
            self.changed.set()
    class Brain:
        def __init__(self, stopped):
            self.stopped = stopped
            self.metrics = {'first_token_s': .01}
        def reply(self, messages, *, on_text):
            if outcome == 'speech_error':
                assert aborted.wait(2)
                raise RuntimeError('Read aborted')
            on_text(' \nHello from Sora. ' if padded else 'Hello from Sora. ')
            assert played.wait(2), 'Playback waited for the entire model reply'
            assert json.loads((tmp_path / 'chat_history.json').read_text()) == []
            if outcome == 'brain_error':
                raise RuntimeError('Incomplete brain reply')
            if outcome == 'cancel':
                self.stopped.set()
                return ''
            on_text('How are you?\n ' if padded else 'How are you?')
            return 'Hello from Sora. How are you?'
        def cancel(self):
            self.stopped.set()
        def abort(self):
            aborted.set()
    class Player:
        def __init__(self, stopped, *args):
            self.stopped = stopped
            self.started_at = time.monotonic()
            self.bytes_written = 0
            self.estimated_gaps = 0
        def feed(self, pcm):
            self.bytes_written += len(pcm)
            played.set()
        def finish(self):
            pass
        def cancel(self):
            self.stopped.set()
    monkeypatch.setattr(cli, 'ContinuousLiquid', Speech)
    monkeypatch.setattr(cli, 'LocalVoiceBrain', Brain)
    monkeypatch.setattr(cli, 'BufferedPlayer', Player)
    turn = cli.VoiceTurn('http://127.0.0.1', context=LocalVoiceContext(), continuous_speech=True)
    turn.microphone.transcript = 'Hello'
    try:
        turn.start(b'fixture')
        turn.thread.join(3)
        assert not turn.thread.is_alive() and not turn.speech_thread.is_alive()
        saved = json.loads((tmp_path / 'chat_history.json').read_text())
        if outcome == 'complete':
            assert turn.error is None
            assert len(saved) == 2 and saved[-1]['text'] == 'Hello from Sora. How are you?'
            assert turn.metrics['playback_started_s'] < turn.metrics['brain_ready_s']
        else:
            assert saved == []
            if outcome != 'cancel':
                assert isinstance(turn.error, RuntimeError)
    finally:
        turn.cancel()


def test_continuous_mode_requires_context(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    import live_liquid_voice as cli
    with pytest.raises(ValueError, match='requires account context'):
        cli.VoiceTurn('http://127.0.0.1', continuous_speech=True)
    with pytest.raises(ValueError, match='Choose'):
        cli.VoiceTurn('http://127.0.0.1', continuous_speech=True, sentence_streaming=True)
