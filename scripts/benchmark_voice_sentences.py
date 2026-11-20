"""Compare whole-reply and sentence-streamed speech with disposable user data."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import wave


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True, help='Fresh synthetic diagnostic directory')
    parser.add_argument('--save-audio', action='store_true', help='Save the fixed synthetic comparison WAVs')
    args = parser.parse_args()
    args.report.mkdir(parents=True, exist_ok=False)
    original = os.environ.get('DATA_DIR')
    try:
        with tempfile.TemporaryDirectory(prefix='sora-sentence-benchmark-') as directory:
            os.environ['DATA_DIR'] = directory
            root = Path(directory)
            (root / '_admin').mkdir()
            (root / '_admin/ai_config.json').write_text(json.dumps({'tiers': {'chat': {
                'host': 'http://127.0.0.1:11434/v1', 'api_key': 'ollama',
                'model': 'qwen2.5:1.5b-instruct',
            }}}))
            from voice_context import LocalVoiceContext
            from voice_brain import LocalVoiceBrain
            from liquid_phone import PhoneRunner
            from live_liquid_voice import VoiceTurn

            (root / 'chat_history.json').write_text('[]')
            start = time.monotonic()
            LocalVoiceContext().warmup(LocalVoiceBrain(threading.Event()))
            (args.report / 'warmup.json').write_text(json.dumps({'startup_s': time.monotonic() - start}))
            results = []
            with PhoneRunner(args.kit, args.report / 'server.log') as endpoint:
                phrase = "I'm right here. Take a slow breath, Alex. Tell me what happened whenever you're ready."
                for pair in range(2):
                    order = [False, True] if pair == 0 else [True, False]
                    for streaming in order:
                        (root / 'chat_history.json').write_text('[]')
                        context = LocalVoiceContext()
                        question = 'Repeat exactly these three sentences without quotation marks: ' + phrase
                        # Match prompt-cache conditions outside the measured interval.
                        prefill_started = time.monotonic()
                        with context._scope():
                            LocalVoiceBrain(threading.Event()).warmup(list(context.prepare(question).messages))
                        prefill_s = time.monotonic() - prefill_started
                        turn = VoiceTurn(endpoint, context=context, sentence_streaming=streaming, buffer_seconds=0.5)
                        turn.microphone.transcript = question
                        chunks = []
                        if args.save_audio:
                            original_events = turn.stream.events
                            def record(*arguments, **options):
                                for kind, data in original_events(*arguments, **options):
                                    if kind == 'audio':
                                        chunks.append(data)
                                    yield kind, data
                            turn.stream.events = record
                        try:
                            turn.start(b'synthetic recognized input')
                            turn.thread.join(120)
                            if turn.thread.is_alive():
                                raise TimeoutError('Voice comparison exceeded 120 seconds')
                            if turn.error:
                                raise turn.error
                            saved = json.loads((root / 'chat_history.json').read_text())
                            if len(saved) != 2:
                                raise AssertionError('Expected one completed exchange')
                            result = {
                                'pair': pair, 'mode': 'sentences' if streaming else 'whole_reply',
                                'prefill_outside_timer_s': prefill_s,
                                'requested': phrase, 'reply': saved[-1]['text'],
                                'exact_requested_reply': saved[-1]['text'] == phrase, **turn.metrics,
                            }
                            results.append(result)
                            (args.report / 'results.json').write_text(json.dumps(results, indent=2))
                            print(json.dumps(result), flush=True)
                        finally:
                            turn.cancel()
                            if args.save_audio and turn.metrics.get('history_saved'):
                                name = f'pair-{pair}-' + ('sentences' if streaming else 'whole') + '.wav'
                                with wave.open(str(args.report / name), 'wb') as recording:
                                    recording.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                                    recording.writeframes(b''.join(chunks))
            comparisons = []
            for pair in range(2):
                whole = next(row for row in results if row['pair'] == pair and row['mode'] == 'whole_reply')
                streamed = next(row for row in results if row['pair'] == pair and row['mode'] == 'sentences')
                matched = whole['reply'] == streamed['reply']
                comparisons.append({
                    'pair': pair, 'matched_text': matched,
                    'playback_saved_s': whole['playback_started_s'] - streamed['playback_started_s'] if matched else None,
                    'speech_before_brain_finish': streamed['playback_started_s'] < streamed['brain_ready_s'],
                })
            (args.report / 'comparisons.json').write_text(json.dumps(comparisons, indent=2))
    finally:
        if original is None:
            os.environ.pop('DATA_DIR', None)
        else:
            os.environ['DATA_DIR'] = original


if __name__ == '__main__':
    main()
