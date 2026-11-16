# Phase 4.14 — NeuTTS-2E Emotion Comparison

The owner found the previous auditions flat. This test uses a dedicated emotion token and holds the sentence, seed, and main speaker constant. The spoken input is “I didn't think you'd come back.” The first four takes use Sophie. A happy take from Emily provides a second female voice. [NeuTTS-2E model card](https://huggingface.co/neuphonic/neutts-2e)

## Setup

- Public CPU ONNX INT8 backbone and tokenizer from Danny-Dasilva revision `e3ea12b860d75acf6903ddd4fbb7c72c0ed4eae3`. The original Neuphonic checkpoint requires account access. [Public conversion](https://huggingface.co/Danny-Dasilva/neutts-2e-onnx)
- ONNX codec and fixed-speaker codes from KitsuMate revision `f4e0a4f4186aaa72197e9735ac4ea7d0f555238e`. The decoder and backbone downloads were checked against their published SHA-256 digests. The codec and reference data retain their Apache-2.0 attribution. The backbone retains the NeuTTS Open License. [Codec and speaker notes](https://huggingface.co/KitsuMate/neutts-2e-onnx)
- Isolated Python 3.11 with ONNX Runtime 1.32.0, Tokenizers 0.23.3, and NumPy 2.4.6. The audition used a socket-denying Python audit hook and local files. The exported synthetic samples were decoded directly without the optional speech watermark.
- The temporary environment had been cleared between turns. Recovered the project through the cumulative Phase 4.13 bundle, finished the model decoder from its saved byte ranges, then regenerated the audio.

## Reproduce

The local `sora-neutts-assets` directory contains the pinned assets and `audition.py`. Set `HF_HUB_OFFLINE=1` and run `python -B audition.py tokenize` followed by `python -B audition.py decode` in the isolated environment. The two commands run generation and decoding in separate processes to limit memory use on the laptop. The generated WAVs are in `sora-neutts-audition/`.

## Verification

| Voice | Emotion | Audio | Token generation | Decoding |
| --- | --- | ---: | ---: | ---: |
| Sophie | Neutral | 3.62 s | 16.87 s | 1.04 s |
| Sophie | Happy | 2.64 s | 11.57 s | 0.69 s |
| Sophie | Sad | 2.36 s | 10.05 s | 0.67 s |
| Sophie | Angry | 3.24 s | 14.71 s | 0.93 s |
| Emily | Happy | 2.50 s | 19.09 s | 0.69 s |

- Both local processes exited 0. Peak RSS was 1,370 MiB for token generation and 1,051 MiB for decoding. These are per-process peaks. The test did not run chat and speech simultaneously.
- Ran `/tmp/sora-neutts-venv/bin/python -B /tmp/sora-neutts/verify.py`, exit 0. Vosk transcribed every clip as the original line. All five files were non-silent 24 kHz mono PCM16 without clipped exported samples. The raw angry waveform exceeded full scale, so its gain was reduced before conversion.
- The timing and transcription checks establish usable files with identical words. The owner still needs to judge the delivery. The slower CPU latency is a separate tradeoff from voice quality.

## Handoff

Import the cumulative Phase 4.14 Git bundle with `git fetch <bundle-path> main` and `git merge --ff-only FETCH_HEAD` into a checkout based on Phase 3.3B (`e69d08b67dd35e76d0457821e0b041e82a4cbf84`). The application synthesis backend was left on Piper. Record the owner's feedback before selecting a provider. Phase 5 remains deferred to app work. Phase 6 remains paused at 6.1.
