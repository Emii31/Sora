# Phase 4.46 — Approved Liquid voice on Motorola

Replayed the three synthetic spoken prompts from the owner-approved Phase 4.45 reference through the existing Android Liquid runner. The model cache was hash-verified. Each turn reset the conversation context and used four threads on the four performance cores. Tested two additional turns with the same prompts provided as complete text to separate speech input from generation.

| Stock path | First voiced PCM | Estimated audible start without gaps |
| --- | ---: | ---: |
| Spoken, celebration | 4.12 s | 25.07 s |
| Spoken, cookie joke | 4.35 s | 17.24 s |
| Spoken, reassurance | 2.59 s | 14.98 s |
| Text, celebration | 2.09 s | 21.59 s |
| Text, reassurance | 4.34 s | 41.78 s |

Times start when the test submits the completed input, exclude microphone capture and include the local USB transport. Continuous playback time is estimated from PCM arrival and cumulative audio duration. Phone replies used the same model and conversation mode. Reply words and waveforms varied compared with the approved laptop reel. No claim of perceptual equivalence is made. The exact approved reel passed its checksum check.

## ARM kernel experiment

Built the pinned llama.cpp CPU backend with `GGML_CPU_KLEIDIAI=ON` and KleidiAI v1.22.0, verified using the archive hash pinned in the checkout. Linked the new CPU archive against the existing Android objects to isolate the backend change. The experimental binary loaded the model into `CPU_KLEIDIAI` buffers and ran from a separate filename on the phone. Stock executable and model weights were untouched.

The experimental build produced identical PCM SHA-256 `14fb950688c6f0ccb4664f8af35c0a0864fadbbcf90b04f99a1c2e2d0cf8be9f` for celebration and the cookie prompt. Both text streams were empty and local Whisper recognized only a sound in both. The third spoken case also emitted no response text. Its apparent speed gain is invalid for speech. The comparison stopped during the later text test once the failure was confirmed.

## Handoff and verification

- No live-chat voice change. The temporary phone server stopped and its lock and ADB forward were removed.
- Targeted tests passed with 122 passed and 6 skipped. The stock/experimental filename test verifies that choosing a new benchmark binary uses a separate Android cache path.
- The optional `PhoneRunner(..., runner=...)` argument is for isolated tests. Default behavior retains the existing runner path.
- Reproduction scripts, the staged build, and raw data are under `/mnt/data/Companion/recovery/phase_04_46`. Use `bash build-kleidi.sh` then `python3 link-kleidi.py` to stage the alternative ARM64 runner. From the repo, run `PYTHONPATH=.:scripts .venv/bin/python -B /mnt/data/Companion/recovery/phase_04_46/compare.py`. The `--runner` and `--out` options allow a separate experimental run. [Timing evidence](../verification/phase_04_46/timings.json)
