"""Compare fixed and automatic buffers using identical synthetic phone speech."""
import argparse
import hashlib
import json
from pathlib import Path
import threading
import time

from liquid_phone import PhoneRunner
from voice_liquid_live import BufferedPlayer, LiquidStream, voice_playback_buffer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True, help='Fresh diagnostic directory')
    args = parser.parse_args()
    args.report.mkdir(parents=True, exist_ok=False)
    results = []
    with PhoneRunner(args.kit, args.report / 'server.log') as endpoint:
        for index, text in enumerate([
            'You named your plant Juniper.',
            "I'm here with you, Alex. Take a slow breath, and tell me what happened when you feel ready.",
        ]):
            order = ['fixed', 'automatic'] if index == 0 else ['smooth_long', 'fixed']
            for policy in order:
                buffer = 1.5 if policy == 'fixed' else voice_playback_buffer(text, smooth_long=True)
                stopped = threading.Event()
                stream = LiquidStream(endpoint, stopped)
                player = BufferedPlayer(stopped, buffer)
                started = time.monotonic()
                first_audio = None
                words = []
                digest = hashlib.sha256()
                try:
                    for kind, data in stream.events(b'', text='Please speak to me.', spoken_text=text):
                        if kind == 'text':
                            words.append(data)
                        else:
                            if first_audio is None:
                                first_audio = time.monotonic() - started
                            digest.update(data)
                            player.feed(data)
                    player.finish()
                    if ''.join(words) != text:
                        raise AssertionError('Speech stream text did not match the supplied sentence')
                    result = {
                        'policy': policy, 'text': text, 'buffer_s': buffer,
                        'first_audio_s': first_audio, 'playback_s': player.started_at - started,
                        'finished_s': time.monotonic() - started,
                        'audio_s': player.bytes_written / 48000,
                        'gaps': player.estimated_gaps, 'pcm_sha256': digest.hexdigest(),
                    }
                    results.append(result)
                    (args.report / 'results.json').write_text(json.dumps(results, indent=2))
                    print(json.dumps(result), flush=True)
                finally:
                    stream.cancel()
                    player.cancel()


if __name__ == '__main__':
    main()
