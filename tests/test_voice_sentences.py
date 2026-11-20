"""Sentence boundaries and concurrent speech failure/cancellation behavior."""
import json
from pathlib import Path
import threading
import time

import pytest

from voice_sentences import SentenceBuffer


@pytest.mark.parametrize('text,early', [
    ('Hello. How are you?', ['Hello. ']),
    ('Dr. Lee likes 3.5 cups. That is plenty.', ['Dr. Lee likes 3.5 cups. ']),
    ('Ask Mr. Smith or J. Lee. They know.', ['Ask Mr. Smith or J. Lee. ']),
    ('For example, e.g. a plant. Yes!', ['For example, e.g. a plant. ']),
    ('Visit example.com first. Thanks.', ['Visit example.com first. ']),
    ('She said "Hello!" Then smiled.', ['She said "Hello!" ']),
    ('你好。很高兴见你！', ['你好。']),
    ('No sentence terminator yet', []),
    ("Wait... it's okay. I'm here.", ["Wait... it's okay. "]),
])
def test_boundaries_preserve_text_across_arbitrary_chunks(text, early):
    buffer = SentenceBuffer()
    emitted = []
    for character in text:
        emitted.extend(buffer.feed(character))
    assert emitted == early
    remaining = buffer.finish()
    assert ''.join(emitted + remaining) == text
    assert buffer.finish() == []


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
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
    class Player:
        def __init__(self, stopped, *args):
            self.stopped = stopped
            self.started_at = time.monotonic()
            self.bytes_written = 0
            self.estimated_gaps = 0
        def feed(self, data):
            self.bytes_written += len(data)
            played.set()
        def finish(self):
            pass
        def cancel(self):
            self.stopped.set()
    monkeypatch.setattr(cli, 'BufferedPlayer', Player)
    return cli, LocalVoiceContext(), tmp_path, played, aborted


@pytest.mark.parametrize('outcome', ['complete', 'brain_error', 'speech_error', 'mismatch', 'cancel', 'oversize', 'too_many'])
def test_speech_starts_before_brain_finishes_and_only_complete_turn_is_saved(pipeline, monkeypatch, outcome):
    cli, context, root, played, aborted = pipeline
    class Brain:
        def __init__(self, stopped):
            self.stopped = stopped
            self.metrics = {'first_token_s': 0.01}
        def reply(self, messages, *, on_sentence):
            assert 'You are Sora' in messages[0]['content']
            if outcome == 'too_many':
                for _ in range(17):
                    on_sentence('A sentence. ')
                return 'A sentence. ' * 17
            on_sentence('Hello. ')
            if outcome in ('speech_error', 'mismatch', 'oversize'):
                assert aborted.wait(2)
                raise RuntimeError('Reader aborted')
            assert played.wait(2), 'Speech did not start while brain was still generating'
            assert json.loads((root / 'chat_history.json').read_text()) == []
            if outcome == 'brain_error':
                raise RuntimeError('Incomplete brain reply')
            if outcome == 'cancel':
                self.stopped.set()
                return ''
            on_sentence('How are you?')
            return 'Hello. How are you?'
        def abort(self):
            aborted.set()
        def cancel(self):
            self.stopped.set()
            aborted.set()
    class Stream:
        def __init__(self, endpoint, stopped):
            self.stopped = stopped
        def events(self, wav, **options):
            assert options['text'] == 'Read this aloud: ' + options['spoken_text']
            if outcome == 'speech_error':
                raise RuntimeError('Audio failed')
            yield 'text', 'Wrong words' if outcome == 'mismatch' else options['spoken_text']
            yield 'audio', bytes(48000 * 31) if outcome == 'oversize' else bytes(480)
        def cancel(self):
            self.stopped.set()
        def abort(self):
            pass
    monkeypatch.setattr(cli, 'LocalVoiceBrain', Brain)
    monkeypatch.setattr(cli, 'LiquidStream', Stream)
    turn = cli.VoiceTurn('http://127.0.0.1', context=context, sentence_streaming=True)
    turn.microphone.transcript = 'Hello'
    turn.start(b'fixture')
    turn.thread.join(3)
    try:
        assert not turn.thread.is_alive()
        assert not turn.speech_thread.is_alive()
        saved = json.loads((root / 'chat_history.json').read_text())
        if outcome == 'complete':
            assert turn.error is None
            assert len(saved) == 2 and saved[1]['text'] == 'Hello. How are you?'
            assert turn.metrics['segments'] == 2
            assert turn.metrics['playback_started_s'] < turn.metrics['brain_ready_s']
        else:
            assert saved == []
            if outcome != 'cancel':
                assert isinstance(turn.error, ValueError if outcome in ('oversize', 'too_many') else RuntimeError)
    finally:
        turn.cancel()


def test_playback_modes_are_mutually_exclusive(pipeline):
    cli, context, *_ = pipeline
    with pytest.raises(ValueError, match='Choose'):
        cli.VoiceTurn('http://127.0.0.1', context=context,
                      sentence_streaming=True, smooth_long_replies=True)


def test_cancellation_unblocks_sentence_queue_backpressure(pipeline, monkeypatch):
    cli, context, root, _, _ = pipeline
    entered = threading.Event()
    backpressure = threading.Event()
    class Brain:
        def __init__(self, stopped):
            self.stopped = stopped
            self.metrics = {}
        def reply(self, messages, *, on_sentence):
            for index in range(12):
                if self.stopped.is_set():
                    return ''
                if index == 5:
                    backpressure.set()
                on_sentence('A sentence. ')
            return 'A sentence. ' * 12
        def cancel(self):
            self.stopped.set()
        def abort(self):
            pass
    class Stream:
        def __init__(self, endpoint, stopped):
            self.stopped = stopped
        def events(self, *args, **kwargs):
            entered.set()
            self.stopped.wait(2)
            return
            yield
        def cancel(self):
            self.stopped.set()
        def abort(self):
            pass
    monkeypatch.setattr(cli, 'LocalVoiceBrain', Brain)
    monkeypatch.setattr(cli, 'LiquidStream', Stream)
    turn = cli.VoiceTurn('http://127.0.0.1', context=context, sentence_streaming=True)
    turn.microphone.transcript = 'Hello'
    turn.start(b'fixture')
    try:
        assert entered.wait(1)
        assert backpressure.wait(1)
        time.sleep(.02)  # Let the sixth callback wait on the full four-slot queue.
        start = time.monotonic()
        turn.cancel()
        assert time.monotonic() - start < 1
        assert not turn.thread.is_alive() and not turn.speech_thread.is_alive()
        assert json.loads((root / 'chat_history.json').read_text()) == []
    finally:
        turn.cancel()
