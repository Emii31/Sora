"""Optional synthetic-only playback measurement and waveform alignment.

Requires requirements/voice_diagnostics.txt. Never selects a default monitor or mic.
"""
import os
import selectors
import subprocess
import threading
import time
from uuid import uuid4

import numpy as np

RATE = 24000


def align_playback(reference_pcm, captured_pcm, *, rate=RATE, window_s=.02, step_s=.05, min_score=.94):
    """Track added playback time using matching waveform anchors, not silence counts."""
    ref = np.frombuffer(reference_pcm, dtype='<i2').astype(np.float64) / 32768
    cap = np.frombuffer(captured_pcm, dtype='<i2').astype(np.float64) / 32768
    # PipeWire can introduce a fractional-sample resampling offset. Suppress
    # near-Nyquist phase sensitivity equally in both signals; do not lower the
    # match threshold or count the model's own silence as a playback gap.
    kernel = np.hanning(9)
    kernel /= kernel.sum()
    ref = np.convolve(ref, kernel, mode='same') if len(ref) else ref
    cap = np.convolve(cap, kernel, mode='same') if len(cap) else cap
    width, step = round(window_s * rate), round(step_s * rate)
    if len(ref) < width or len(cap) < width:
        return {'reliable': False, 'reason': 'Recording too short', 'anchors': []}
    sums = np.concatenate(([0.], np.cumsum(cap)))
    squares = np.concatenate(([0.], np.cumsum(cap * cap)))
    anchors, attempted, first_eligible, last_eligible = [], 0, None, None
    for index in range(0, len(ref) - width + 1, step):
        template = ref[index:index + width]
        if np.sqrt(np.mean(template * template)) < .004:
            continue
        template = template - template.mean()
        energy = float(template @ template)
        if energy < 1e-9:
            continue
        attempted += 1
        if first_eligible is None:
            first_eligible = index / rate
        last_eligible = index / rate
        if anchors:
            expected = index + round(anchors[-1]['lag_s'] * rate)
            left = max(0, expected - round(.015 * rate))
            right = min(len(cap) - width, expected + round(5 * rate))
        else:
            left, right = 0, len(cap) - width
        if right < left:
            continue
        segment = cap[left:right + width]
        fft_size = 1 << (len(segment) + width - 2).bit_length()
        correlation = np.fft.irfft(np.fft.rfft(segment, fft_size) *
                                   np.fft.rfft(template[::-1], fft_size), fft_size)
        numerator = correlation[width - 1:len(segment)]
        starts = np.arange(left, right + 1)
        total = sums[starts + width] - sums[starts]
        local_energy = squares[starts + width] - squares[starts] - total * total / width
        scores = numerator / np.sqrt(np.maximum(local_energy * energy, 1e-20))
        peak = int(np.argmax(scores))
        score = float(scores[peak])
        if score < min_score:
            continue
        position = left + peak
        anchors.append({'reference_s': index / rate, 'monitor_s': position / rate,
                        'lag_s': (position - index) / rate, 'correlation': min(1., score)})
    result = {'anchors': anchors, 'attempted_anchors': attempted,
              'alignment_filter': 'symmetric_hann_9', 'window_s': window_s,
              'matched_fraction': len(anchors) / attempted if attempted else 0.}
    if len(anchors) < 3 or anchors[-1]['reference_s'] - anchors[0]['reference_s'] < .5:
        return {**result, 'reliable': False, 'reason': 'Insufficient matched speech span'}
    if result['matched_fraction'] < .65:
        return {**result, 'reliable': False, 'reason': 'Too few high-confidence waveform matches'}
    if anchors[0]['reference_s'] - first_eligible > .1 or last_eligible - anchors[-1]['reference_s'] > .1:
        return {**result, 'reliable': False, 'reason': 'Reference onset or tail was not matched'}
    if any(b['lag_s'] < a['lag_s'] - .025 for a, b in zip(anchors, anchors[1:])):
        return {**result, 'reliable': False, 'reason': 'Non-monotonic alignment'}
    jumps = [{'reference_s': b['reference_s'], 'added_s': b['lag_s'] - a['lag_s']}
             for a, b in zip(anchors, anchors[1:]) if b['lag_s'] - a['lag_s'] > .035]
    return {**result, 'reliable': True, 'anchored_span_s': anchors[-1]['reference_s'] - anchors[0]['reference_s'],
            'added_time_between_anchors_s': max(0., anchors[-1]['lag_s'] - anchors[0]['lag_s']),
            'material_lag_jumps': jumps}


class SyntheticMonitor:
    """Own one null sink and capture only its explicitly named monitor."""
    def __init__(self):
        self.sink = 'sora_probe_' + uuid4().hex[:12]
        self.module = None
        self.proc = None
        self.thread = None
        self.pcm = bytearray()
        self.error = None
        self.stopped = threading.Event()
        self.original_sink = None

    def pactl(self, *args):
        return subprocess.run(['pactl', *args], stdin=subprocess.DEVNULL, check=True,
                              capture_output=True, text=True, timeout=5).stdout.strip()

    def __enter__(self):
        try:
            self.original_sink = self.pactl('get-default-sink')
            self.module = self.pactl('load-module', 'module-null-sink', 'sink_name=' + self.sink,
                                     'rate=24000', 'channels=1', 'format=s16le')
            if self.pactl('get-default-sink') == self.sink:
                self.pactl('set-default-sink', self.original_sink)
            sinks = [line.split()[1] for line in self.pactl('list', 'short', 'sinks').splitlines()]
            sources = [line.split()[1] for line in self.pactl('list', 'short', 'sources').splitlines()]
            if self.sink not in sinks or self.sink + '.monitor' not in sources:
                raise RuntimeError('Synthetic sink/monitor not available; default audio capture is forbidden')
            self.proc = subprocess.Popen(['parec', '--device=' + self.sink + '.monitor', '--raw',
                                          '--rate=24000', '--channels=1', '--format=s16le',
                                          '--volume=65536', '--client-name=SoraSyntheticMonitor',
                                          '--latency-msec=20', '--process-time-msec=10'],
                                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.thread = threading.Thread(target=self._read, name='synthetic-monitor', daemon=True)
            self.thread.start()
            time.sleep(.2)
            if self.proc.poll() is not None:
                raise RuntimeError('Synthetic monitor recorder exited')
            return self
        except BaseException:
            self.close()
            raise

    def _read(self):
        deadline = time.monotonic() + 60
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(self.proc.stdout, selectors.EVENT_READ)
                while not self.stopped.is_set() and time.monotonic() < deadline:
                    if not selector.select(timeout=.1):
                        continue
                    data = os.read(self.proc.stdout.fileno(), 8192)
                    if not data:
                        return
                    self.pcm.extend(data)
                    if len(self.pcm) > RATE * 2 * 60:
                        raise ValueError('Synthetic recording exceeds 60 seconds')
            if not self.stopped.is_set():
                raise TimeoutError('Synthetic monitor exceeded 60 seconds')
        except Exception as exc:
            if not self.stopped.is_set():
                self.error = exc

    def close(self):
        self.stopped.set()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=2)
        if self.thread:
            self.thread.join(timeout=2)
        if self.proc and self.proc.stdout:
            self.proc.stdout.close()
        if self.module:
            module, self.module = self.module, None
            self.pactl('unload-module', module)

    def __exit__(self, *args):
        self.close()
