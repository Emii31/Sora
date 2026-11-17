# Phase 4.22 — Offline Liquid Audio Speech-to-Speech Trial

Tested LiquidAI LFM2.5-Audio-1.5B Q4_0 and its matching projector, vocoder, and tokenizer at revision `7d525f883a077e20afb782f2ff618edcae0e39e4`. The Linux x64 runner is build 7641 (`68d8edf2`). All four model files and the runner archive matched the publisher's checksums. The local test benchmarked CPU-only inference on the i5-7300U with four batch threads and up to four generation threads. It ran in a fresh Linux network namespace with only loopback and no route to the internet. [Model and runner instructions](https://huggingface.co/LiquidAI/LFM2.5-Audio-1.5B-GGUF/blob/main/README.md)

## Streaming results

The benchmark sent local spoken WAVs to `/v1/chat/completions` and captured arriving PCM chunks. Measurements start at request submission and exclude microphone capture. The estimated smooth start is based on timestamped chunks and the output rate. The audible metric uses the first 20 ms of PCM above −45 dBFS RMS. Peak server RSS was approximately 1.74 GiB. The default conversation voice was used throughout streaming chat.

| Test | Generation threads | First voiced chunk | Earliest smooth audible start | Output duration |
| --- | ---: | ---: | ---: | ---: |
| Cheerful reply | 4 | 5.67 s | 7.21 s | 2.78 s |
| Playful prompt, model asked for repetition | 4 | 4.78 s | 9.99 s | 7.58 s |
| Reassurance reply | 4 | 4.73 s | 10.77 s | 7.18 s |
| Same cheerful input | 2 | 6.27 s | 9.39 s | 2.78 s |
| Natural-sounding synthetic source WAV | 2 | 7.00 s | 24.68 s | 13.18 s |
| UK female text-to-speech | 4 | 1.15 s | 3.26 s | 3.50 s |

Both measured runs exited 0 and all selected responses received a stop event. The synthetic warm-up greeting produced an unrelated refusal, and the playful prompt triggered a request to repeat. The requested UK female voice was accepted only with the dedicated TTS system prompt. The runner rejected a voice selection appended to the interleaved chat system prompt. The dedicated TTS figure starts with complete input text and excludes the time needed to generate a chat reply.

## Listening

The 25.14-second reel contains the successful cheerful, reassurance and natural-input streaming replies, with one second between clips. Its SHA-256 is `81bb0e4c334b776048aac30ae7ec7aa963e420cca343baa71ea5e918b9a535f4`. The four listening samples decoded without clipping. Vosk recovered the main content, with minor recognition variations. The benchmark scripts, raw responses, timing traces, and standalone female TTS clip are in the conversation artifacts under `sora-liquid-audition/`. The verified local kit is under `/mnt/data/Companion/sora-liquid-audition/`.

The latency misses the roughly two-second smooth-start target on this laptop. These results come from standalone fixtures. Microphone capture, playback device latency, and interruption behavior remain unmeasured.

## Follow-up tone comparison

The owner preferred the sound of the first Liquid chat reel and was unsure whether its tone changed enough across situations. A second four-thread trial sent three different situations to the same default interleaved chat voice. Liquid's separate US male TTS produced the test prompts, which were fed back locally as audio. Only chat replies appear in the listening reel.

The celebration response acknowledged the job offer, and the reassurance response addressed the caller's embarrassment. An explicit request for playful teasing got an unrelated refusal. A retry without that instruction led to a literal reply to the cookie joke. These are the model's actual reactions. The estimated smooth audible start was 8.73 seconds for celebration, 14.93 seconds for the cookie retry, and 16.12 seconds for reassurance.

The offline runs exited 0. The 45.06-second comparison is mono 24 kHz PCM16 with one second between replies and no clipped samples. Vosk recovered the main replies, with uncertain words and a partial transcript of the final take. The reel, timestamps, and timing logs are in the conversation artifacts under `sora-liquid-audition/tone-comparison/`. Reel SHA-256 `3f009dd77536078b5ebdca19317831d2b2ead90295b24668ad56292145bc07eb`.
