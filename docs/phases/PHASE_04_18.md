# Phase 4.18 — Longer Audition and Vulkan Timing

The owner asked for a longer listening sample and further speed work on the approved Sora voice. This experiment uses the Phase 4.17 resident Qwen 0.6B Base Vulkan runtime and the original unmodified reference, whose WAV has SHA-256 `5ad5d7d8073ad5fb19c0abbf33373203600612f95d30e8432a53de0cb062946c`.

## Listening sample

`default-long.wav` was generated in one continuous synthesis from a 343-character English passage. The lines move from concern through delight and mild annoyance into quiet reassurance. The delivery can be judged by listening to the clip. It uses the production sampling parameters. The standalone audition used a larger frame allowance for the longer passage. It does not change the backend reply limit.

## Benchmark method

`audition.py` runs the prebuilt framed Vulkan CLI on Intel HD 620 with the exact Phase 4.17 embeddings, model weights, transcript and seed. Each setting has a separate process and one untimed warm-up turn, followed by two timed turns with byte-identical input text. Timings start when the text is submitted, and the first-audio metric measures the first 80 ms PCM chunk. Completion time includes all PCM and the end marker. These are standalone synthesis measurements and exclude chat inference. Listen to the audio before judging whether any sampling change sounds as natural as the original.

The long clip is exactly 20.00 seconds. It took 117.04 seconds to synthesize on the laptop, with the first frame arriving after 3.26 seconds. The audio is 24 kHz mono PCM16 and peaks at −3.67 dBFS, with no clipped samples. Local Vosk recognized the opening and ending and most of the text, with two word-level discrepancies. The WAV SHA-256 is `1f95dbcec9e18557e19873810b00f30220281c2d2c9ca96708d1b0d9248f0ff5`.

## GPU settings

`--no-fa` and `--sub-top-k 1` produced different WAVs with shorter audio. `GGML_VK_FORCE_MMVQ=1` was an ineffective control on this GPU. The runtime reported no integer dot-product support, and the pinned GGML implementation gates that path on hardware support. Its two test WAVs matched the defaults bit for bit. Its shorter wall-clock timings show run-to-run variability. [Pinned GGML Vulkan implementation](https://github.com/ggml-org/ggml/blob/0d403add5cb6329935290f02462e1072045aacd2/src/ggml-vulkan/ggml-vulkan.cpp#L7062)

| Vulkan setting | Warm short timings | Median | Audio duration |
| --- | --- | ---: | ---: |
| Initial defaults | 33.16 s, 22.55 s | 27.86 s | 3.68 s |
| Flash attention disabled | 24.39 s, 24.51 s | 24.45 s | 3.44 s |
| Forced quantized matrix-vector mode | 24.24 s, 23.34 s | 23.79 s | 3.68 s |
| Greedy acoustic sampling | 23.21 s, 23.62 s | 23.42 s | 3.52 s |
| 256 nodes per Vulkan submission | 22.47 s, 21.89 s | 22.18 s | 3.68 s |
| Defaults retested after 256 | 24.11 s, 24.91 s | 24.51 s | 3.68 s |

The 256-node trial was about 9.5% faster than the follow-up default pair. Both of its WAVs matched all default WAVs byte for byte. This small experiment does not establish the speedup across longer inputs or application traffic. The previous configuration remains the default. To reproduce the optional trial, set `GGML_VK_MAX_NODES_PER_SUBMIT=256` in the environment that launches the existing resident Vulkan backend. The long clip used the standard sampling and Vulkan settings.

The complete scripts, local logs, audio validation, and WAVs are stored outside Git under `sora-voice-latency/phase-4.18/`. Both benchmark passes and the local audio check exited 0. The 256-node output and retest baseline matched using `cmp`, exit 0.
