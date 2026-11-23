# Phase 4.60 — Native Sopro startup profile on the Motorola

Profiled fixed-text synthesis over USB on the Motorola with two CPU threads, q8_0 weights, one voice cache slot, 64-frame chunks and seed 9000. The stock build and two timing-only builds each ran one request before voice preparation and five with the cached voice. All 18 complete outputs matched the approved setup's Phase 4.59 replay PCM byte-for-byte. The test measured first PCM received on the host. It used synthetic text and did not open the microphone or play the audio.

| Build | First request to PCM | Median of five cached requests |
| --- | ---: | ---: |
| Stock | 6.57 s | 1.88 s |
| Session timings | 6.80 s | 2.01 s |
| Session and renderer timings | 6.21 s | 2.05 s |

Stock first-request measurements included 0.89 s to prepare the reference and 3.59 s to build the voice prompt state. Those operations did not recur in the five repeat requests. The initial phone server launch was measured separately and precedes all request timings.

In the detailed build, the largest measured warm stage was acoustic generation at 0.98 s median before first PCM. The median was 0.47 s for semantic model prefill, 0.26 s for subsequent speech-token generation, and 0.25 s for the vocoder, including its timed initialization work. Acoustic and vocoder work are contained within renderer or segment initialization timings. Component medians should not be added to the renderer total. The detailed trace records individual stage times and the calls needed to produce the first audio event.

## Verification and handoff

- From `/mnt/data/Companion/recovery/phase_04_60`, ran `python3 -B build-profile.py` and `python3 -B build-detailed.py` to compile the timing builds against the existing Android artifacts. Both exited 0.
- Ran `bash with-awake-phone.sh bash -c 'python3 -B native_phone.py stage && python3 -B profile.py stock ../phase_04_56/arm-optimized/bin/audiocpp_server'`, `bash with-awake-phone.sh python3 -B profile.py instrumented ./audiocpp_server-profile`, and `bash with-awake-phone.sh python3 -B profile.py detailed ./audiocpp_server-detailed`. All exited 0. The runner verified transferred files on the device before use.
- Ran `python3 -B collect.py`, exit 0. It checks every PCM hash against the earlier on-device replay and writes the structured [Motorola profile](../verification/phase_04_60/motorola-sopro-profile.json).
- Ran `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_voice_sopro_live.py tests/test_voice_playback_diagnostics.py` from the repository. 11 passed, exit 0.
- Removed this benchmark's temporary Android files, verified no forwarded ports remained and confirmed the prior stay-awake setting was restored to 0.

Keep the approved speech path as-is. Evaluate whether the first acoustic work can be reduced with audio parity across several lines, then measure any verified candidate on the speaker. This single-line synthesis profile does not establish end-to-end conversation time, and the two-second target remains open.
