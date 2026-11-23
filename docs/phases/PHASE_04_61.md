# Phase 4.61 — Less work before the first Sopro audio on the Motorola

Tested a bounded cache for the first two full acoustic graph shapes. The candidate retained graph allocations and reloaded inputs for each solve. Model weights, acoustic steps, chunk geometry, seeds and reference audio matched the timing baseline.

## Acoustic graph cache

Baseline and candidate each ran twice in baseline–candidate–candidate–baseline order. Each process warmed on the same line, then rendered four fixed replies. The cache reported two hits before first PCM on every measured candidate reply. All eight matched comparisons produced byte-identical complete PCM.

| Measurement | Median paired change |
| --- | ---: |
| Time to first PCM | 29 ms faster |
| Pre-output acoustic processing | 56 ms faster |
| End-of-run resident memory | 70 MiB higher |

The first-PCM changes ranged from 92 ms faster to 342 ms slower. The graph-cache candidate stays outside Sora because the median gain was small, the tail did not improve, and memory increased.

## Faster CPU cores

With the original timing build and two synthesis threads, alternated all-core access with access restricted to CPUs 4–7. On this Motorola, the maximum reported frequency is 2.208 GHz for CPUs 4–7 and 1.805 GHz for CPUs 0–3. Android can further restrict the process, so the benchmark recorded the observed per-thread masks before each request and required that every restricted mask fit within CPUs 4–7. All four replies produced identical PCM in both modes.

Restricting the worker to the faster cores reduced time to first PCM by **0.43 s** at the median and by **0.12–0.53 s** across the four lines. The median paired reduction in the measured acoustic stage was **0.18 s**. Two trial attempts initially required an exact mask that Android did not always expose. The final run accepted only observed masks within the intended core group. It also required at least two eligible faster cores and access to a lower-frequency core in the control.

## Speaker replay

The same fixed reply was played twice in each mode through the Motorola's built-in speaker. The AAudio timing estimates include about 24 ms of USB clock uncertainty.

| CPU access | Median text request to speaker | Android underruns across two runs |
| --- | ---: | ---: |
| All available cores | 2.48 s | 3, 3 |
| Faster cores only | 2.15 s | 3, 1 |

Both faster-core runs started sooner than their paired controls. The four playbacks all submitted identical PCM and drained every frame. Android still reported underruns, so this established a startup gain and left playback continuity open. No microphone was used.

## Verification and handoff

- From `/mnt/data/Companion/recovery/phase_04_61`, ran `python3 -B build-cache.py`, `bash with-awake-phone.sh python3 -B native_phone.py stage`, `bash with-awake-phone.sh python3 -B compare.py`, and `python3 -B collect.py`. The final commands exited 0. The graph-cache build links only temporary replacement objects. The Android transfer was verified by hash.
- From the Sora repo, ran `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_voice_sopro_live.py tests/test_voice_playback_diagnostics.py`. All 11 passed, exit 0.
- The measures begin with fixed reply text. They exclude speech recognition and chat generation. The two-second live response target remains open.
- Ran `bash with-awake-phone.sh python3 -B affinity.py` and `bash with-awake-phone.sh python3 -B speaker.py`. Both final runs exited 0. Cleanup removed the temporary Android files and forwarding. The stay-awake setting returned to 0.
- Evidence includes the [graph-cache comparison](../verification/phase_04_61/motorola-graph-cache.json), [affinity timings](../verification/phase_04_61/motorola-affinity.json), and [speaker measurements](../verification/phase_04_61/motorola-speaker.json).

Keep CPU affinity experimental and limited to the Motorola test worker. Next, verify continuous speaker playback and measure the faster profile in the full conversation pipeline. Production voice defaults were not modified.
