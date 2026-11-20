"""Play synthetic identity/memory checks through the real local brain and phone.

Uses disposable data. Requires Ollama with qwen2.5:1.5b-instruct already installed
and running on loopback, plus the patched Android Liquid runner and USB debugging.
"""
import argparse
import json
import os
from pathlib import Path
import tempfile
import threading
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True, help='Fresh diagnostic directory')
    parser.add_argument('--no-warmup', action='store_true')
    args = parser.parse_args()
    args.report.mkdir(parents=True, exist_ok=False)
    previous_data_dir = os.environ.get('DATA_DIR')
    # Import application modules only after binding the disposable data directory.
    try:
        with tempfile.TemporaryDirectory(prefix='sora-voice-verification-') as directory:
            os.environ['DATA_DIR'] = directory
            root = Path(directory)
            (root / '_admin').mkdir()
            (root / '_admin/ai_config.json').write_text(json.dumps({'tiers': {'chat': {
                'host': 'http://127.0.0.1:11434/v1', 'api_key': 'ollama',
                'model': 'qwen2.5:1.5b-instruct',
            }}}))
            (root / 'core_memory.json').write_text(json.dumps({
                'human': {'value': 'The user is Alex. Alex likes jasmine tea.'},
                'persona': {'value': 'We have a warm friendship.'},
            }))
            (root / 'identity.json').write_text(json.dumps({'name': 'Alex'}))
            (root / 'chat_history.json').write_text('[]')
            from voice_context import LocalVoiceContext
            from liquid_phone import PhoneRunner
            from live_liquid_voice import VoiceTurn
            from voice_brain import LocalVoiceBrain

            results = []
            if not args.no_warmup:
                start = time.monotonic()
                LocalVoiceContext().warmup(LocalVoiceBrain(threading.Event()))
                (args.report / 'warmup.json').write_text(json.dumps({
                    'warmup_s': time.monotonic() - start,
                    'history_after_warmup': json.loads((root / 'chat_history.json').read_text()),
                }, indent=2))
            with PhoneRunner(args.kit, args.report / 'server.log') as endpoint:
                for question, expected in (
                    ('What is your name?', 'sora'),
                    ('What tea do I like?', 'jasmine'),
                    ('My plant is called Juniper.', None),
                    ('What did I name my plant?', 'juniper'),
                ):
                    # Re-create the adapter each turn to exercise persisted history.
                    turn = VoiceTurn(endpoint, context=LocalVoiceContext())
                    turn.microphone.transcript = question
                    try:
                        turn.start(b'synthetic recognized input')
                        turn.thread.join(120)
                        if turn.thread.is_alive():
                            raise TimeoutError('Voice turn exceeded 120 seconds')
                        if turn.error:
                            raise turn.error
                        history = json.loads((root / 'chat_history.json').read_text())
                        answer = history[-1]['text']
                        if expected and expected not in answer.lower():
                            raise AssertionError(f'Reply did not recall {expected}: {answer}')
                        result = {'question': question, 'reply': answer, **turn.metrics}
                        results.append(result)
                        (args.report / 'results.json').write_text(json.dumps(results, indent=2))
                        print(json.dumps(result), flush=True)
                    finally:
                        turn.cancel()
                if len(json.loads((root / 'chat_history.json').read_text())) != 8:
                    raise AssertionError('Expected exactly four saved voice exchanges')
    finally:
        if previous_data_dir is None:
            os.environ.pop('DATA_DIR', None)
        else:
            os.environ['DATA_DIR'] = previous_data_dir


if __name__ == '__main__':
    main()
