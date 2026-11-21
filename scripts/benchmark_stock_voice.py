"""Audition published CPU voice models without changing their runtime settings."""
import argparse
import asyncio
import http.client
import importlib.metadata
import json
from pathlib import Path
import time
import wave

import numpy as np
LINES = (
    ("delight", "Wait, you made that? Come here, I want to see every little detail."),
    ("teasing", "You stole my blanket again. Look at you, pretending you had nothing to do with it."),
    ("comfort", "Hey. You can put that down for tonight. I'll sit with you for a little while."),
    ("firm", "No, that really upset me. Please listen before you tell me it was only a joke."),
    ("relief", "Oh, you're okay. I was trying to sound calm, but I can finally breathe now."),
    ("thoughtful", "I keep wondering what that little seaside town would sound like after sunset."),
)
LONG = ('I found an old blue notebook tucked behind the books. It had a list of tiny things '
        'someone wanted to remember. Rain on the kitchen window. Fresh bread at the station. '
        'The afternoon they took the long way home just to keep talking.')


def save(path, chunks, rate):
    with wave.open(str(path), 'wb') as wav:
        wav.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        for chunk in chunks:
            wav.writeframes((np.clip(chunk, -1, 1) * 32767).astype('<i2').tobytes())


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--engine', choices=('kokoro', 'kitten', 'piper'), default='kokoro')
    parser.add_argument('--chat', action='store_true', help='Also time loopback Ollama and virtual playback')
    args = parser.parse_args()
    args.report.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    if args.engine == 'kokoro':
        from kokoro_onnx import Kokoro
        model = Kokoro(str(args.assets / 'kokoro-v1.0.int8.onnx'), str(args.assets / 'voices-v1.0.bin'))
        voices = {'af_heart': 'af_heart', 'bf_lily': 'bf_lily'}
        package = 'kokoro-onnx'
        provider = model.sess.get_providers()[0]
    elif args.engine == 'kitten':
        import sherpa_onnx
        config = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
            kitten=sherpa_onnx.OfflineTtsKittenModelConfig(
                model=str(args.assets / 'model.int8.onnx'), voices=str(args.assets / 'voices.bin'),
                tokens=str(args.assets / 'tokens.txt'), data_dir=str(args.assets / 'espeak-ng-data'),
            )))
        if not config.validate():
            raise ValueError('Invalid released KittenTTS model directory')
        model = sherpa_onnx.OfflineTts(config)
        voices = {'bella': 1, 'luna': 3}
        package = 'sherpa-onnx'
        provider = config.model.provider
    else:
        from piper import PiperVoice
        model = PiperVoice.load(args.assets / 'en_US-amy-low.onnx')
        voices = {'amy': 'amy'}
        package = 'piper-tts'
        provider = model.session.get_providers()[0]
    results = {'engine': args.engine, 'package': importlib.metadata.version(package),
               'provider': provider, 'load_s': time.monotonic() - start, 'trials': []}
    if args.engine == 'kitten':
        results['threads'] = config.model.num_threads

    async def measure(text, voice, label):
        start = time.monotonic()
        first = None
        chunks = []
        rate = 24000
        if args.engine == 'kokoro':
            async for samples, rate in model.create_stream(text, voice=voice):
                if first is None:
                    first = time.monotonic() - start
                chunks.append(samples)
        elif args.engine == 'kitten':
            def receive(samples, progress):
                nonlocal first
                if len(samples) == 0:
                    return 1
                if not chunks:
                    first = time.monotonic() - start
                chunks.append(np.asarray(samples, dtype=np.float32).copy())
                return 1
            output = model.generate(text, sid=voice, callback=receive)
            rate = output.sample_rate
        else:
            for chunk in model.synthesize(text):
                if first is None:
                    first = time.monotonic() - start
                rate = chunk.sample_rate
                chunks.append(chunk.audio_float_array)
        finish = time.monotonic() - start
        if first is None or rate <= 0:
            raise RuntimeError('Voice engine returned no speech')
        duration = sum(len(chunk) for chunk in chunks) / rate
        if duration <= 0 or not all(np.isfinite(chunk).all() for chunk in chunks):
            raise RuntimeError('Voice engine returned invalid audio')
        if not any(np.any(np.abs(chunk) > .001) for chunk in chunks):
            raise RuntimeError('Voice engine returned silent audio')
        row = dict(voice=voice, case=label, first_pcm_s=first, synthesis_s=finish,
                   audio_s=duration, audio_chunks=len(chunks), rtf=finish / duration)
        results['trials'].append(row)
        print(json.dumps(row), flush=True)
        (args.report / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
        return chunks, rate

    for name, voice in voices.items():
        audition = []
        for label, text in LINES:
            chunks, rate = await measure(text, voice, label)
            audition.extend(chunks)
            audition.append(np.zeros(round(rate * .5), dtype=np.float32))
        save(args.report / f'{name}-audition.wav', audition, rate)
        for repeat in range(2):
            chunks, rate = await measure(LONG, voice, f'long-{repeat + 1}')
        save(args.report / f'{name}-long.wav', chunks, rate)

    if args.chat:
        from threading import Event
        from voice_liquid_live import BufferedPlayer
        from voice_playback_diagnostics import SyntheticMonitor, align_playback

        def reply(prompt, limit=96):
            connection = http.client.HTTPConnection('127.0.0.1', 11434, timeout=45)
            try:
                payload = {'model': 'qwen2.5:1.5b-instruct', 'stream': False, 'max_tokens': limit,
                           'messages': [{'role': 'system', 'content': 'You are Sora, a warm companion. Reply with one short sentence.'},
                                        {'role': 'user', 'content': prompt}]}
                connection.request('POST', '/v1/chat/completions', json.dumps(payload),
                                   {'Content-Type': 'application/json'})
                response = connection.getresponse()
                if response.status != 200:
                    raise RuntimeError(f'Local chat returned HTTP {response.status}')
                choice = json.loads(response.read())['choices'][0]
                answer = choice['message']['content'].strip()
                if not answer or (limit != 1 and choice['finish_reason'] != 'stop'):
                    raise RuntimeError('Local chat returned an incomplete reply')
                return answer
            finally:
                connection.close()

        start = time.monotonic()
        reply('Hello.', limit=1)
        results['chat_warmup_s'] = time.monotonic() - start
        results['chat'] = []
        for prompt in ('I finally finished the painting.', 'I could use a little reassurance.',
                       'You hid my favorite mug again!'):
            with SyntheticMonitor() as monitor:
                player = BufferedPlayer(Event(), .5, monitor.sink)
                start = time.monotonic()
                try:
                    answer = reply(prompt)
                    brain_s = time.monotonic() - start
                    chunks, rate = await measure(answer, next(iter(voices.values())), 'chat-reply')
                    pcm = b''.join((np.clip(chunk, -1, 1) * 32767).astype('<i2').tobytes()
                                   for chunk in chunks)
                    if rate != 24000:
                        # Match the virtual monitor format for exact waveform comparison.
                        import subprocess
                        pcm = subprocess.run(
                            ['ffmpeg', '-v', 'error', '-f', 's16le', '-ar', str(rate), '-ac', '1', '-i', '-',
                             '-f', 's16le', '-ar', '24000', '-'],
                            input=pcm, capture_output=True, check=True, timeout=5,
                        ).stdout
                    player.feed(pcm)
                    player.finish()
                    await asyncio.sleep(.3)
                finally:
                    player.cancel()
                if monitor.error:
                    raise monitor.error
            aligned = align_playback(pcm, bytes(monitor.pcm))
            row = {'prompt': prompt, 'reply': answer, 'brain_s': brain_s,
                   'pipe_start_s': player.started_at - start,
                   'alignment_reliable': aligned['reliable'],
                   'added_monitor_s': aligned.get('added_time_between_anchors_s')}
            results['chat'].append(row)
            print(json.dumps(row), flush=True)
            (args.report / 'results.json').write_text(json.dumps(results, indent=2) + '\n')


if __name__ == '__main__':
    asyncio.run(main())
