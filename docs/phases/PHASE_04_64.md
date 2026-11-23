# Phase 4.64 — Faster whole-reply preparation with the existing Qwen model

Benchmarked the installed Qwen2.5 1.5B on the two-core, four-thread i5-7300U. The disposable native Ollama chat adapter used the same Sora prompt, history, model and output limit across settings. All measured replies had to finish normally. No prompt shortening or provider migration was applied to the application. The experiment used deterministic sampling to isolate timing with matched replies.

| Ollama CPU threads | Median first token | Median complete reply | Matched wins against automatic |
| --- | ---: | ---: | ---: |
| Automatic | 0.72 s | 2.18 s | Control |
| Two | 0.72 s | 2.28 s | 5/8 |
| Four | 0.55 s | 1.62 s | 8/8 |

Four threads saved 0.46 seconds at the median of the paired differences. The 0.56-second difference between group medians is a separate statistic. All 24 complete replies were identical within each of the four prompts. The recall fixture named Nimbus in every mode. The benchmark alternated forward and reverse setting order and excluded a one-token warmup when each setting took effect. First-token, prompt processing and generation timings are recorded in the evidence.

## Whole-reply phone playback

Used two prerecorded utterances, local Whisper, the same Sora context and a single native Sopro request per reply. All four turns used the Motorola's faster-core synthesis profile and the primed player with a 0.75-second buffer. The experimental adapter used Ollama's native chat API for both settings. It sent the thread count through the runtime options and required normal completion. See the [Ollama chat API](https://docs.ollama.com/api/chat) and [runner options](https://github.com/ollama/ollama/blob/main/api/types.go).

| Fixture | Qwen auto / four threads | Speaker onset auto / four threads |
| --- | ---: | ---: |
| Tea | 2.07 / 1.49 s | 6.45 / 5.78 s |
| Long day | 3.04 / 2.15 s | 7.89 / 6.79 s |
| Median | 2.56 / 1.82 s | 7.17 / 6.28 s |

Qwen timing begins at chat dispatch. Speaker onset is estimated from the end of fixture speech and Android's audio timestamp. Both matched pairs generated the same text and byte-identical audio. All four turns saved exactly one exchange in disposable history and drained all frames with zero reported underruns. CPU, ASR, and synthesis timings varied. The long-day replay produced different wording from the separate text benchmark, so exact matching is claimed within each paired experiment. The microphone stayed closed.

## Verification and handoff

- From `/mnt/data/Companion/recovery/phase_04_64`, ran `source ../phase_04_59/env.sh && /mnt/data/Companion/Miru/.venv/bin/python -B -u benchmark.py` and `source ../phase_04_59/env.sh && bash with-awake-phone.sh /mnt/data/Companion/Miru/.venv/bin/python -B -u whole_reply.py 4`. Both final runs exited 0. The first text-benchmark attempt exited before generation because the temporary admin directory was created in the wrong order. The final run initializes Ollama before the Sora context.
- Ran `PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_voice_brain.py tests/test_voice_context.py tests/test_voice_sopro_live.py tests/test_ai_config.py` in the Sora repo. 73 passed, exit 0.
- Removed the benchmark's temporary Android directory and port forwarding. The original stay-awake value was restored to 0.
- [Ollama timings](../verification/phase_04_64/ollama-thread-comparison.json) and [Motorola replay timings](../verification/phase_04_64/motorola-whole-reply.json) contain only synthetic inputs and responses.

The four-thread setting is a hardware-specific candidate. It has no production integration yet. The next iteration can expose a verified opt-in for the private local Ollama voice route and measure sustained response time with multiturn memory and playback continuity. The two-second live target remains open.
