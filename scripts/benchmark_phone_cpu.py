"""Compare per-process CPU settings for fixed synthetic Liquid speech on Android."""
import argparse
import json
from pathlib import Path
from statistics import median

from liquid_phone import PhoneRunner
from profile_voice_playback import calibrate, measure


PROFILES = {
    'four-big': (0xf0, 4),
    'three-big': (0xe0, 3),
    'six-mixed': (0xf3, 6),
    'three-wide': (0xf0, 3),
}
FIXTURES = {
    'short': ('Juniper is a great name for a plant, Alex!', 'My plant is called Juniper.'),
    'long': ("I'm right here. Take a slow breath, Alex. Tell me what happened whenever you're ready.",
             "I'm feeling overwhelmed. Please reassure me."),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--candidate', choices=tuple(PROFILES)[1:], action='append',
                        help='Choose an alternative profile. Can be repeated.')
    args = parser.parse_args()
    profiles = ('four-big', *dict.fromkeys(args.candidate or ('three-big', 'six-mixed')))
    args.report.mkdir(parents=True, exist_ok=False)
    calibrate(args.report)
    rows = []

    def affinity(runner):
        reported = runner.adb('shell', f'taskset -p {runner.pid}').stdout.strip().rsplit(maxsplit=1)[-1]
        return int(reported, 16)

    def run(profile, fixture, tag):
        case = f'{tag}-{fixture}-{profile}'
        mask, threads = PROFILES[profile]
        runner = PhoneRunner(args.kit, args.report / f'{case}.log', cpu_mask=mask, threads=threads)
        with runner as endpoint:
            before = affinity(runner)
            text, user = FIXTURES[fixture]
            result = measure(runner, endpoint, args.report, case, text, user, .5)
            after = affinity(runner)
        result.pop('arrivals')
        result['analysis'].pop('anchors')
        rows.append(dict(result, profile=profile, fixture=fixture, tag=tag,
                         requested_mask=f'{mask:x}', threads=threads,
                         observed_masks=[f'{before:x}', f'{after:x}'],
                         mask_checks_passed=before == after == mask))
        (args.report / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')

    for tag, order in [('first', profiles), ('reverse', tuple(reversed(profiles)))]:
        for profile in order:
            run(profile, 'short', tag)

    baseline_hashes = {row['reference_pcm_sha256'] for row in rows if row['profile'] == 'four-big'}
    if len(baseline_hashes) != 1:
        raise RuntimeError('Baseline short speech changed between runs')
    eligible = [profile for profile in profiles[1:] if
                all(row['mask_checks_passed'] and row['reference_pcm_sha256'] in baseline_hashes
                    for row in rows if row['profile'] == profile)]
    if eligible:
        fastest = min(eligible, key=lambda profile: median(row['generation_wall_rtf'] for row in rows
                                                           if row['profile'] == profile))
        for profile in (fastest, 'four-big'):
            run(profile, 'long', 'confirmation')


if __name__ == '__main__':
    main()
