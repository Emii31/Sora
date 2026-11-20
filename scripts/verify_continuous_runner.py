"""Verify native continuous-text guards and PCM parity without recording a microphone."""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit
import wave

from liquid_phone import PhoneRunner
from voice_continuous import ContinuousLiquid
from voice_liquid_live import LiquidStream


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--text', default="I'm right here. Take a slow breath, Alex. Tell me what happened whenever you're ready.")
    parser.add_argument('--context', default="I'm feeling overwhelmed. Please reassure me.")
    args = parser.parse_args()
    args.report.mkdir(parents=True, exist_ok=False)
    text, user = args.text, args.context
    results = []
    guards = {}
    with PhoneRunner(args.kit, args.report / 'server.log') as endpoint:
        url = urlsplit(endpoint)
        def request(method, path, payload):
            connection = http.client.HTTPConnection(url.hostname, url.port, timeout=5)
            try:
                connection.request(method, path, json.dumps(payload), {'Content-Type': 'application/json'})
                response = connection.getresponse()
                response.read(4096)
                return response.status
            finally:
                connection.close()

        for continuous in (False, True):
            stopped = threading.Event()
            stream = (ContinuousLiquid if continuous else LiquidStream)(endpoint, stopped)
            words, audio, errors = [], [], []
            started = time.monotonic()
            timing = {}
            def consume():
                try:
                    options = {'text': user}
                    if not continuous:
                        options['spoken_text'] = text
                    for kind, data in stream.events(b'', **options):
                        if kind == 'text':
                            words.append(data)
                        else:
                            timing.setdefault('first_audio_s', time.monotonic() - started)
                            audio.append(data)
                except Exception as exc:
                    errors.append(exc)
            worker = threading.Thread(target=consume, daemon=True)
            worker.start()
            try:
                if continuous:
                    if not stream.ready.wait(10):
                        raise TimeoutError('Native speech input not ready')
                    path = '/v1/speech-input/' + stream.identifier
                    guards['unknown'] = request('POST', '/v1/speech-input/' + '0' * 32, {'text': 'Hi'})
                    guards['oversized'] = request('POST', path, {'text': 'a' * 2001})
                    guards['empty_final'] = request('POST', path, {'text': '', 'final': True})
                    guards['duplicate'] = request('POST', url.path, {
                        'stream': True, 'reset_context': True, 'max_tokens': 512,
                        'speech_input_id': stream.identifier, 'modalities': ['text', 'audio'],
                        'messages': [{'role': 'user', 'content': user}],
                    })
                    assert guards == {'unknown': 404, 'oversized': 400, 'empty_final': 400, 'duplicate': 409}, guards
                    for offset in range(0, len(text), 12):
                        stream.append(text[offset:offset + 12])
                        time.sleep(.1)
                    stream.append('', final=True)
                    guards['after_final'] = request('POST', path, {'text': 'More'})
                    assert guards['after_final'] in (404, 409)
                worker.join(45)
                if worker.is_alive():
                    raise TimeoutError('Native verification exceeded 45 seconds')
                if errors:
                    raise errors[0]
                assert ''.join(words) == text
                pcm = b''.join(audio)
                mode = 'continuous' if continuous else 'whole'
                result = {'mode': mode, **timing, 'finished_s': time.monotonic() - started,
                          'audio_s': len(pcm) / 48000, 'pcm_sha256': hashlib.sha256(pcm).hexdigest()}
                results.append(result)
                with wave.open(str(args.report / (mode + '.wav')), 'wb') as output:
                    output.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                    output.writeframes(pcm)
                print(json.dumps(result), flush=True)
            finally:
                stream.cancel()
                worker.join(5)
        assert results[0]['pcm_sha256'] == results[1]['pcm_sha256'], 'Continuous speech changed the generated waveform'
        (args.report / 'results.json').write_text(json.dumps({'results': results, 'guards': guards,
                                                           'identical_pcm': True}, indent=2))


if __name__ == '__main__':
    main()
