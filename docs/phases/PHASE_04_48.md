# Phase 4.48 — Native Sopro streaming audition

Tested audio.cpp v0.9.6 portable CPU (`04a37f2e`) with the same Sopro V2 Turbo checkpoint and five fixtures as Phase 4.47. The GitHub release metadata listed the SHA-256 of the downloaded artifact, which matched. The server ran in a loopback-only network namespace. The native CPU session used Q8_0 matrix weights, the published two solver steps, and a warmed three-reference cache. Calls used three individual Liquid replies from the owner-approved recording. Latencies start when complete text is submitted.

| Laptop profile | First PCM | Estimated continuous audible start | Turns within 1.2 s |
| --- | --- | --- | --- |
| Four threads | 0.64–1.26 s | 0.96–1.30 s | 3/5 |
| Two pinned physical cores | 1.15–1.32 s | 1.19–2.60 s | 1/5 |

The four-thread median continuous start was 1.16 s, down from 5.02 s in the prior four-thread Python trial on the same text. The four-thread native output completed faster than playback in all five turns. Initial voice preparation was excluded from warm turns. The first requests for each voice needed 4.46–6.35 seconds to emit PCM, including lazy runtime initialization on the first request. Server logs recorded reference-cache hits on all measured requests.

The 24.80 s sample contains the native model’s four emotion-oriented replies. Whisper tiny.en made two word edits in 81 reference words across the five test turns. The owner has not yet evaluated whether the delivery matches the approved Liquid reference. The phone, physical speaker, recognition-to-reply path and microphone-to-speaker latency were not measured.

The executable, `warm-native.py`, cache traces, WAVs and detailed timings are under `/mnt/data/Companion/recovery/phase_04_48`. The sample is `warm/native-sopro-voice-sample.wav`. The approved Liquid file passed its checksum check. Sora’s runtime settings were unchanged.

[Native Sopro runtime and voice cache](https://github.com/0xShug0/audio.cpp/blob/main/docs/models/sopro_tts.md) · [Sopro model](https://huggingface.co/samuel-vitorino/sopro-v2-turbo)
