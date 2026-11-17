# Phase 4.21 — Varied Nano Dialogue and CPU Timing

A 33.80-second Chatterbox Nano audition uses eight different lines with the approved Sora reference. The intended deliveries are cute, excited, concerned, sad, annoyed, thoughtful, tender and surprised. The reel uses the official floating-point model and two decoder steps, with four CPU threads. Each section has 0.8 seconds of silence before the next. The provided guide lists the lines and start times. The audio is 24 kHz mono PCM16. No sample clipped in the individual WAVs. The reel SHA-256 is `bb204bb9a8f14932787722263865cf6bf8e94571297cb432b477ee11a3bc60fc`.

## Short-reply timing

The warmed comparison used “Hey, you went quiet. Are you okay?” with fixed seed and input. Four threads gave a 9.69 s median for the 2.72 s take, compared with 12.59 s on two threads. In a separate four-thread comparison, a one-step floating-point decoder rendered it in 8.00 s median, compared with 9.02 s median for the stock two steps. Vosk recovered the ending question in both floating-point variants, and misrecognized the same earlier words in both.

Full GPT-2 projection quantization at four threads produced a 1.84 s clip in 5.94 s median. Quantizing the feed-forward layers alone took 4.69 s median with one decoder step for a 1.36 s clip. Vosk only recovered the first clause in both int8 paths. The missing question disqualifies these faster times as complete replies. Original reference conditioning and offline settings were shared across the runs.

The reel, listening guide, scripts, logs and per-clip verification are in the conversation artifacts under `sora-nano-expressive/`. These standalone recordings and CPU measurements await owner listening. Fresh-response speed remains below real-time, and end-to-end chat latency was outside the audition.
