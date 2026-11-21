"""Measure synthetic playback on an isolated virtual monitor and profile the phone.

No microphone/default monitor is opened. Install requirements/voice_diagnostics.txt.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import wave

import numpy as np

from liquid_phone import PhoneRunner
from voice_continuous import ContinuousLiquid
from voice_liquid_live import BufferedPlayer
from voice_playback_diagnostics import SyntheticMonitor, align_playback


def save_wave(path, pcm):
    with wave.open(str(path), 'wb') as output:
        output.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        output.writeframes(pcm)


def calibrate(directory):
    rng = np.random.default_rng(431)
    signal = np.convolve(rng.normal(0, .2, 60000), np.hanning(15) / np.hanning(15).sum(), mode='same')
    pcm = (signal * 32767).astype('<i2').tobytes()
    results = []
    for name in ('clean', 'preloaded_chunks', 'delayed'):
        with SyntheticMonitor() as monitor:
            player = BufferedPlayer(threading.Event(), .2, monitor.sink)
            try:
                if name == 'clean':
                    player.feed(pcm)
                elif name == 'preloaded_chunks':
                    for offset in range(0, len(pcm), 960):
                        player.feed(pcm[offset:offset + 960])
                else:
                    player.feed(pcm[:48000])
                    deadline = time.monotonic() + 5
                    while player.started_at is None and time.monotonic() < deadline:
                        time.sleep(.005)
                    if player.started_at is None:
                        raise TimeoutError('Calibration playback did not start')
                    while time.monotonic() < player.started_at + 1.6:
                        time.sleep(.01)
                    player.feed(pcm[48000:])
                player.finish()
                time.sleep(.3)
            finally:
                player.cancel()
            if monitor.error:
                raise monitor.error
        analysis = align_playback(pcm, bytes(monitor.pcm))
        if not analysis['reliable']:
            raise RuntimeError('Calibration alignment failed: ' + analysis.get('reason', 'unknown'))
        added = analysis['added_time_between_anchors_s']
        if (name == 'delayed' and added < .3) or (name != 'delayed' and added > .02):
            raise AssertionError('Calibration did not distinguish clean and delayed playback')
        result = {'case': name, 'pipe_estimated_gaps': player.estimated_gaps, 'analysis': analysis}
        results.append(result)
        save_wave(directory / (name + '-reference.wav'), pcm)
        save_wave(directory / (name + '-monitor.wav'), bytes(monitor.pcm))
        print(json.dumps({'calibration': name, 'added_monitor_time_s': added,
                          'pipe_estimated_gaps': player.estimated_gaps}), flush=True)
    (directory / 'calibration.json').write_text(json.dumps(results, indent=2))


def process_ticks(phone):
    raw = phone.adb('shell', f'cat /proc/{phone.pid}/stat', check=False).stdout
    try:
        fields = raw.rsplit(') ', 1)[1].split()
        return int(fields[11]) + int(fields[12])
    except (IndexError, ValueError):
        return None


def telemetry(phone):
    battery = phone.adb('shell', 'dumpsys battery', check=False).stdout
    thermal = phone.adb('shell', 'dumpsys thermalservice', check=False).stdout
    temperature = re.search(r'^\s*temperature:\s*(\d+)', battery, re.M)
    status = re.search(r'Thermal Status:\s*(\d+)', thermal)
    cpu_temperatures = re.findall(r'mValue=([\d.]+), mType=0, mName=CPU\d+', thermal)
    frequencies = {}
    for core in (4, 5, 6, 7):
        value = phone.adb('shell', f'cat /sys/devices/system/cpu/cpu{core}/cpufreq/scaling_cur_freq', check=False).stdout.strip()
        frequencies[str(core)] = int(value) if value.isdigit() else None
    return {'battery_temperature_c': int(temperature[1]) / 10 if temperature else None,
            'thermal_status': int(status[1]) if status else None,
            'maximum_reported_cpu_temperature_c': max(map(float, cpu_temperatures)) if cpu_temperatures else None,
            'big_core_frequencies_khz': frequencies}


def measure(phone, endpoint, directory, name, text, user, reserve):
    before = telemetry(phone)
    tick_rate_raw = phone.adb('shell', 'getconf CLK_TCK', check=False).stdout.strip()
    tick_rate = int(tick_rate_raw) if tick_rate_raw.isdigit() else None
    cpu_before = process_ticks(phone)
    with SyntheticMonitor() as monitor:
        stopped = threading.Event()
        stream = ContinuousLiquid(endpoint, stopped)
        player = BufferedPlayer(stopped, reserve, monitor.sink)
        audio, arrivals, errors, words = [], [], [], []
        state = {}
        started = time.monotonic()
        def consume():
            try:
                for kind, data in stream.events(b'', text=user):
                    if kind == 'text':
                        words.append(data)
                    else:
                        arrival = time.monotonic() - started
                        audio.append(data)
                        player.feed(data)
                        arrivals.append({'at_s': arrival, 'audio_s': len(data) / 48000,
                                         'feed_blocked_s': time.monotonic() - started - arrival})
                state['generation_done_s'] = time.monotonic() - started
                state['cpu_after_ticks'] = process_ticks(phone)
                player.finish()
                state['finished_s'] = time.monotonic() - started
            except Exception as exc:
                errors.append(exc)
        worker = threading.Thread(target=consume, name='profile-speech', daemon=True)
        worker.start()
        try:
            stream.append(text, final=True)  # Full text ready: isolate speech generation from brain delay.
            worker.join(50)
            if worker.is_alive():
                raise TimeoutError('Speech profile exceeded 50 seconds')
            if errors:
                raise errors[0]
            if ''.join(words) != text:
                raise AssertionError('Generated text differs from the fixed profile fixture')
            time.sleep(.3)
        finally:
            stream.cancel()
            player.cancel()
            worker.join(5)
        if monitor.error:
            raise monitor.error
    pcm = b''.join(audio)
    analysis = align_playback(pcm, bytes(monitor.pcm))
    duration = len(pcm) / 48000
    first = arrivals[0]['at_s'] if arrivals else None
    cpu_after = state.get('cpu_after_ticks')
    result = {'case': name, 'reserve_s': reserve, 'generated_audio_s': duration,
              'reference_pcm_sha256': hashlib.sha256(pcm).hexdigest(),
              'first_chunk_s': first, **state,
              'generation_wall_rtf': state['generation_done_s'] / duration,
              'emission_rtf': (state['generation_done_s'] - first) / duration,
              'process_cpu_seconds': (cpu_after - cpu_before) / tick_rate
                  if cpu_after is not None and cpu_before is not None and tick_rate else None,
              'playback_pipe_start_s': player.started_at - started,
              'pipe_estimated_gaps': player.estimated_gaps,
              'maximum_feed_blocked_s': max(row['feed_blocked_s'] for row in arrivals),
              'before': before, 'after': telemetry(phone), 'analysis': analysis, 'arrivals': arrivals}
    save_wave(directory / (name + '-reference.wav'), pcm)
    save_wave(directory / (name + '-monitor.wav'), bytes(monitor.pcm))
    (directory / (name + '.json')).write_text(json.dumps(result, indent=2))
    print(json.dumps({key: result[key] for key in ('case', 'generated_audio_s', 'generation_done_s',
                                                  'generation_wall_rtf', 'pipe_estimated_gaps')}
                     | {'alignment_reliable': analysis['reliable'],
                        'added_monitor_time_s': analysis.get('added_time_between_anchors_s')}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--calibration-only', action='store_true')
    parser.add_argument('--include-full-buffer', action='store_true',
                        help='Also measure complete audio buffering for the long fixture')
    args = parser.parse_args()
    if not args.calibration_only and args.kit is None:
        parser.error('Supply --kit for phone profiling')
    args.report.mkdir(parents=True, exist_ok=False)
    calibrate(args.report)
    if not args.calibration_only:
        results = []
        runner = PhoneRunner(args.kit, args.report / 'server.log')
        with runner as endpoint:
            for name, text, user in (
                ('short', 'Juniper is a great name for a plant, Alex!', 'My plant is called Juniper.'),
                ('long', "I'm right here. Take a slow breath, Alex. Tell me what happened whenever you're ready.",
                 "I'm feeling overwhelmed. Please reassure me."),
            ):
                reserves = (.5, 1.5, None) if name == 'long' and args.include_full_buffer else (.5, 1.5)
                for reserve in reserves:
                    results.append(measure(phone=runner, endpoint=endpoint,
                                           directory=args.report, name=f'{name}-{reserve}',
                                           text=text, user=user, reserve=reserve))
        (args.report / 'results.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
