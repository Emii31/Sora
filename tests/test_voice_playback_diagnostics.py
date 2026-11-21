"""Offline analysis calibration; no microphone, device or audio server required."""
import pytest
np = pytest.importorskip('numpy', reason='Install requirements/voice_diagnostics.txt for diagnostic tests')
from voice_playback_diagnostics import align_playback

RATE = 24000


def signal(seconds=2.5):
    rng = np.random.default_rng(431)
    audio = np.convolve(rng.normal(0, .2, round(seconds * RATE)), np.hanning(15) / np.hanning(15).sum(), mode='same')
    return (audio * 32767).astype('<i2')


def pcm(samples):
    return np.asarray(samples, dtype='<i2').tobytes()


def test_leading_buffering_is_not_a_playback_gap():
    reference = signal()
    captured = np.concatenate([np.zeros(12000, dtype='<i2'), reference, np.zeros(2400, dtype='<i2')])
    result = align_playback(pcm(reference), pcm(captured))
    assert result['reliable'], result.get('reason')
    assert result['added_time_between_anchors_s'] < .005
    assert not result['material_lag_jumps']
    assert result['anchors'][0]['lag_s'] == pytest.approx(.5, abs=.002)


def test_inserted_silence_is_measured_against_the_reference():
    reference = signal()
    captured = np.concatenate([np.zeros(4800, dtype='<i2'), reference[:RATE],
                               np.zeros(7200, dtype='<i2'), reference[RATE:]])
    result = align_playback(pcm(reference), pcm(captured))
    assert result['reliable'], result.get('reason')
    assert result['added_time_between_anchors_s'] == pytest.approx(.3, abs=.005)
    assert sum(row['added_s'] for row in result['material_lag_jumps']) == pytest.approx(.3, abs=.005)


def test_intentional_silence_in_the_model_waveform_is_not_an_underrun():
    audio = signal(2)
    reference = np.concatenate([audio[:RATE], np.zeros(7200, dtype='<i2'), audio[RATE:]])
    captured = np.concatenate([np.zeros(2400, dtype='<i2'), reference])
    result = align_playback(pcm(reference), pcm(captured))
    assert result['reliable'], result.get('reason')
    assert result['added_time_between_anchors_s'] < .005
    assert not result['material_lag_jumps']


def test_gain_change_does_not_create_false_gaps():
    reference = signal()
    captured = np.concatenate([np.zeros(2400, dtype='<i2'), (reference * .3).astype('<i2')])
    result = align_playback(pcm(reference), pcm(captured))
    assert result['reliable'] and result['added_time_between_anchors_s'] < .005


@pytest.mark.parametrize('capture', [b'', bytes(RATE * 2), pcm(signal()[RATE:])])
def test_missing_silent_or_clipped_capture_is_not_reported_as_gap_free(capture):
    result = align_playback(pcm(signal()), capture)
    assert not result['reliable']
