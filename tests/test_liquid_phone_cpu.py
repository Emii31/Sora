"""Validate the parameters interpolated into the phone runner command."""
from pathlib import Path

import pytest


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'scripts'))
    from liquid_phone import PhoneRunner
    return PhoneRunner


@pytest.mark.parametrize('mask,threads', [
    (0, 1), (0x100, 1), ('f0; exit', 4), (True, 1), (0xf0, 5), (0xf0, '4'), (0xf0, 0),
])
def test_runner_rejects_invalid_cpu_profiles(runner, tmp_path, mask, threads):
    with pytest.raises(ValueError, match='CPU mask'):
        runner(tmp_path, tmp_path / 'runner.log', cpu_mask=mask, threads=threads)


def test_runner_preserves_default_and_formats_explicit_masks(runner, tmp_path):
    default = runner(tmp_path, tmp_path / 'default.log')
    assert (default.cpu_mask, default.threads) == ('f0', 4)
    mixed = runner(tmp_path, tmp_path / 'mixed.log', cpu_mask=0xf3, threads=6)
    assert (mixed.cpu_mask, mixed.threads) == ('f3', 6)
