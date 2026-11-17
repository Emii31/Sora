# Phase 4.24 — Test Liquid Audio on the Intel HD 620

The test uses the same Q4_0 Liquid LFM2.5-Audio-1.5B model and default interleaved chat voice chosen in Phase 4.22. Both backends use the same runner build, the same three recorded inputs, four CPU threads and a 2,048-token context. Each backend is warmed before measurements. Each fixture is sent as audio and also as text transcribed by Vosk at capture speed. Both runs occur in a loopback-only network namespace.

## Runner and hardware

Built `llama-liquid-audio-server` from llama.cpp PR 18641 at `ec9d1fdd9cc18643c5e161b65b8053f6f6f34a4b`. The release build uses `GGML_VULKAN=ON`, `GGML_NATIVE=ON`, `BUILD_SHARED_LIBS=OFF`, and `LLAMA_OPENSSL=OFF`. The vendored HTTP library failed to compile against Arch's OpenSSL headers. Disabling TLS allowed the loopback-only build to complete without installing system packages. The runner binary and its license are stored alongside the local model kit.

The Mesa Intel driver identifies device `Vulkan0` as Intel HD Graphics 620 (KBL GT2). It loaded all 17 model layers onto the GPU. The audio decoder selected Vulkan with CPU fallback. Projector warmup reported operations unsupported by the Vulkan backend. The CPU baseline hides Vulkan devices and sets `-ngl 0`.

The benchmark now accepts an explicit runner path and decodes both the float PCM chunks from the packaged server and the signed 16-bit PCM chunks from this build. The initial hardware run exposed valid empty chunks during decoder startup. The harness now skips these chunks and still rejects misaligned PCM. Synthetic checks covered both formats, an empty startup chunk, and a malformed frame before rerunning both backends.

## Measured after input ends

| Fixture and path | First voiced chunk, CPU / Vulkan | Estimated smooth audible start, CPU / Vulkan |
| --- | ---: | ---: |
| Check-in, direct audio | 5.04 / 6.98 s | 14.83 / 34.87 s |
| Check-in, Vosk bridge | 1.48 / 1.92 s | 9.65 / 88.96 s |
| Good news, direct audio | 4.09 / 9.60 s | 9.51 / 44.02 s |
| Good news, Vosk bridge | 2.90 / 5.60 s | 9.50 / 31.05 s |
| Comfort, direct audio | 3.46 / 8.87 s | 12.23 / 26.61 s |
| Comfort, Vosk bridge | 4.59 / 9.18 s | 31.57 / 50.81 s |

CPU and GPU median smooth starts were 10.94 and 39.44 seconds, respectively. Both missed the two-second target on every turn. GPU offload took longer on every matched pair for both first voiced chunk and estimated smooth start. Reply wording and spoken length differed across backends. Some check-in replies were off-topic, and the GPU check-in bridge WAV had 525 near-full-scale samples. These are prerecorded measurements based on chunk arrival and an audible-onset threshold. Live microphone endpointing, speaker playback and hybrid model-only offload remain untested.

The corrected run exited 0 with six completed replies per backend. All 12 WAVs were verified as non-silent 24 kHz mono PCM16 with matching durations. The voice-input regression suite returned 40 passed and 6 skipped. The next candidate is an on-device Android benchmark with the same model and inputs.

## Reproduction

Use `PYTHONPATH=.` and a local Python environment with Vosk. Run the command within a network namespace with only loopback enabled. Input WAVs are 16 kHz mono PCM16. Use a fresh result directory per backend.

```bash
# GPU: add --vulkan below and set GGML_VK_VISIBLE_DEVICES=0
VK_DRIVER_FILES=/usr/share/vulkan/icd.d/intel_icd.json \
GGML_VK_VISIBLE_DEVICES='' PYTHONPATH=. \
python -B scripts/benchmark_liquid_text_bridge.py \
  --kit "$local_kit" --runner "$liquid_runner" \
  --vosk-model "$vosk_model" --output "$result_dir" \
  "$fixtures"/input-{check-in,good-news,comfort}.wav
```

Conversation artifacts under `sora-liquid-audition/vulkan-comparison/` contain the runner script, build log, per-backend server logs, exact `timings.jsonl` results and WAVs. `initial-run/` records the first attempt before empty-chunk handling was corrected.
