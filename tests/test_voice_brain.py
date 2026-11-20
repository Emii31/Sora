"""Provider binding and failure boundaries for local spoken replies."""
import json
import threading
from types import SimpleNamespace

import pytest

import voice_brain


@pytest.fixture
def provider(monkeypatch):
    seen = {}
    config = {'model': 'local-chat', 'api_key': 'local-placeholder'}
    monkeypatch.setattr(voice_brain.ai_config, 'get_tier_config', lambda tier: dict(config))
    monkeypatch.setattr(voice_brain.ai_config, 'get_tier_client',
                        lambda tier: SimpleNamespace(base_url='http://127.0.0.1:11434/v1/'))
    monkeypatch.setattr(voice_brain.ai_config, 'resolve_max_tokens', lambda *args: 96)
    class Response:
        status = 200
        lines = []
        def readline(self, limit):
            return self.lines.pop(0) if self.lines else b''
    response = Response()
    class Connection:
        sock = None
        def __init__(self, host, port, timeout):
            seen.update(host=host, port=port, timeout=timeout)
        def request(self, method, path, data, headers):
            seen.update(method=method, path=path, payload=json.loads(data), headers=headers)
        def getresponse(self):
            return response
        def close(self):
            seen['closed'] = True
    monkeypatch.setattr(voice_brain.http.client, 'HTTPConnection', Connection)
    return seen, response, config


def packet(text='', finish=None):
    return ('data: ' + json.dumps({'choices': [{'delta': {'content': text},
                                               'finish_reason': finish}]}) + '\n').encode()


def test_exact_local_connection_and_complete_reply(provider):
    seen, response, config = provider
    response.lines = [packet('Hello '), packet('Alex.', 'stop'), b'data: [DONE]\n']
    brain = voice_brain.LocalVoiceBrain(threading.Event())
    messages = [{'role': 'user', 'content': 'Hello'}]
    assert brain.reply(messages) == 'Hello Alex.'
    assert (seen['host'], seen['port'], seen['path']) == ('127.0.0.1', 11434, '/v1/chat/completions')
    assert seen['headers']['Authorization'] == 'Bearer local-placeholder'
    assert seen['payload']['messages'] == messages
    assert seen['payload']['model'] == 'local-chat'
    assert seen['payload']['max_tokens'] == 96
    assert seen['closed'] and brain.connection is None


@pytest.mark.parametrize('lines', [[], [packet('Partial')], [packet('Too long', 'length')],
                                   [packet('', 'stop')], [b'data: {"error": "failure"}\n']])
def test_incomplete_or_failed_reply_is_rejected(provider, lines):
    seen, response, _ = provider
    response.lines = lines
    with pytest.raises(RuntimeError):
        voice_brain.LocalVoiceBrain(threading.Event()).reply([])
    assert seen['closed']


def test_remote_provider_is_rejected_before_request(provider, monkeypatch):
    seen, _, _ = provider
    monkeypatch.setattr(voice_brain.ai_config, 'get_tier_client',
                        lambda tier: SimpleNamespace(base_url='https://example.com/v1'))
    with pytest.raises(RuntimeError, match='loopback'):
        voice_brain.LocalVoiceBrain(threading.Event()).reply([])
    assert not seen


def test_cancel_before_generation_sends_nothing(provider):
    seen, _, _ = provider
    stopped = threading.Event()
    brain = voice_brain.LocalVoiceBrain(stopped)
    brain.cancel()
    assert brain.reply([]) == ''
    assert 'payload' not in seen and seen['closed']


def test_cancel_shuts_down_active_socket():
    calls = []
    brain = voice_brain.LocalVoiceBrain(threading.Event())
    brain.connection = SimpleNamespace(sock=SimpleNamespace(shutdown=lambda how: calls.append(how)))
    brain.cancel()
    assert brain.stopped.is_set() and len(calls) == 1


@pytest.mark.parametrize('text', ['Hello', ' '])
def test_warmup_is_one_token_and_accepts_only_its_own_length_finish(provider, monkeypatch, text):
    seen, response, _ = provider
    monkeypatch.setattr(voice_brain.ai_config, 'resolve_max_tokens', lambda tier, limit: limit)
    response.lines = [packet(text, 'length')]
    brain = voice_brain.LocalVoiceBrain(threading.Event())
    assert brain.warmup([{'role': 'user', 'content': 'Hello'}]) is None
    assert seen['payload']['max_tokens'] == 1 and seen['closed']
    assert brain.metrics['finished_s'] >= brain.metrics['first_token_s'] >= 0
    response.lines = [packet('Partial', 'length')]
    with pytest.raises(RuntimeError, match='incomplete'):
        brain.reply([])


def test_warmup_rejects_missing_completion(provider):
    _, response, _ = provider
    response.lines = []
    with pytest.raises(RuntimeError, match='incomplete'):
        voice_brain.LocalVoiceBrain(threading.Event()).warmup([])


def test_sentence_callback_runs_before_provider_completion_and_preserves_exact_reply(provider):
    _, response, _ = provider
    response.lines = [packet('Hello. '), packet('How are '), packet('you?', 'stop')]
    emitted = []
    def receive(text):
        emitted.append(text)
        if len(emitted) == 1:
            assert len(response.lines) == 2, 'Callback waited until model completion'
    brain = voice_brain.LocalVoiceBrain(threading.Event())
    reply = brain.reply([], on_sentence=receive)
    assert reply == ''.join(emitted) == 'Hello. How are you?'


def test_incomplete_provider_does_not_release_unfinished_tail(provider):
    _, response, _ = provider
    response.lines = [packet('Hello. '), packet('Unfinished', 'length')]
    emitted = []
    with pytest.raises(RuntimeError, match='incomplete'):
        voice_brain.LocalVoiceBrain(threading.Event()).reply([], on_sentence=emitted.append)
    assert emitted == ['Hello. ']


def test_sentence_consumer_error_closes_provider_connection(provider):
    seen, response, _ = provider
    response.lines = [packet('Hello. '), packet('More', 'stop')]
    def fail(sentence):
        raise ValueError('Speech consumer failed')
    with pytest.raises(ValueError, match='Speech consumer'):
        voice_brain.LocalVoiceBrain(threading.Event()).reply([], on_sentence=fail)
    assert seen['closed']
