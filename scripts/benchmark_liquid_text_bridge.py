"""Benchmark incremental Vosk recognition feeding Liquid's default chat voice."""

import argparse
from array import array
import base64
import io
import json
import math
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
import wave

from voice_input import MAX_SECONDS, SAMPLE_RATE, _load_model, _read_pcm

OUTPUT_RATE = 24000
SYSTEM_PROMPT = "Respond with interleaved text and audio."


def transcribe_at_capture_speed(wav: bytes, model, recognizer_factory):
    pcm = _read_pcm(wav, MAX_SECONDS)
    recognizer = recognizer_factory(model, SAMPLE_RATE)
    started = time.monotonic()
    segments = []
    # Deliver each 80 ms block just as it would become available from capture.
    block_bytes = SAMPLE_RATE * 2 * 80 // 1000
    for offset in range(0, len(pcm), block_bytes):
        block = pcm[offset:offset + block_bytes]
        due = started + (offset + len(block)) / (2 * SAMPLE_RATE)
        time.sleep(max(0.0, due - time.monotonic()))
        if recognizer.AcceptWaveform(block):
            segments.append(json.loads(recognizer.Result()).get("text", ""))
    end_of_input = started + len(pcm) / (2 * SAMPLE_RATE)
    segments.append(json.loads(recognizer.FinalResult()).get("text", ""))
    transcript = " ".join(segment.strip() for segment in segments if segment.strip())
    if not transcript:
        raise RuntimeError("Vosk returned an empty transcript")
    return transcript, end_of_input


def generate(opener, endpoint, content, started):
    payload = {
        "model": "", "stream": True, "reset_context": True, "seed": 7, "max_tokens": 256,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": content}],
    }
    request = urllib.request.Request(endpoint, json.dumps(payload).encode(),
                                     {"Content-Type": "application/json"})
    samples, words, chunks = array("f"), [], []
    finish = None
    with opener.open(request, timeout=90) as response:
        for line in response:
            if not line.startswith(b"data: "):
                continue
            body = line[6:].strip()
            if body == b"[DONE]":
                break
            timestamp = time.monotonic() - started
            event = json.loads(body)
            if "error" in event:
                raise RuntimeError(event["error"])
            for choice in event.get("choices", []):
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    words.append(delta["content"])
                if delta.get("audio_chunk"):
                    data = base64.b64decode(delta["audio_chunk"]["data"], validate=True)
                    if not data or len(data) % 4:
                        raise ValueError("Liquid returned an invalid PCM block")
                    chunks.append((timestamp, len(samples), len(data) // 4))
                    samples.frombytes(data)
                finish = choice.get("finish_reason") or finish
    if finish != "stop" or not chunks or not all(map(math.isfinite, samples)):
        raise RuntimeError(f"Incomplete or invalid Liquid reply (finish={finish})")
    # At each chunk arrival, its predecessors must cover playback up to that
    # point. The largest deficit determines the earliest gap-free start.
    smooth_start = max(timestamp - prior / OUTPUT_RATE for timestamp, prior, _ in chunks)
    window = OUTPUT_RATE // 50
    onset = next((i for i in range(0, len(samples) - window + 1, window)
                  if sum(x*x for x in samples[i:i + window]) / window >= 10**(-4.5)), None)
    if onset is None:
        raise RuntimeError("Liquid returned no measurable speech")
    first_voiced = next(timestamp for timestamp, prior, size in chunks if prior + size >= onset + window)
    stats = {"text": "".join(words), "first_voiced_s": round(first_voiced, 3),
             "smooth_audible_s": round(smooth_start + onset / OUTPUT_RATE, 3),
             "audio_s": round(len(samples) / OUTPUT_RATE, 3)}
    pcm = array("h", (round(max(-1., min(1., value))*32767) for value in samples))
    out = io.BytesIO()
    with wave.open(out, "wb") as recording:
        recording.setparams((1, 2, OUTPUT_RATE, 0, "NONE", "not compressed"))
        recording.writeframes(pcm.tobytes())
    return stats, out.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", required=True, type=Path)
    parser.add_argument("--vosk-model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("inputs", nargs="+", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    # The existing voice_input loader selects the model path without a download.
    model, recognizer = _load_model(args.vosk_model)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    kit = args.kit.resolve()
    binary = kit / "llama-liquid-audio-ubuntu-x64" / "llama-liquid-audio-server"
    weights = "LFM2.5-Audio-1.5B-Q4_0.gguf"
    command = [str(binary), "--host", "127.0.0.1", "--port", str(port),
               "-ngl", "0", "-t", "4", "-tb", "4", "-c", "2048",
               "-m", str(kit / weights), "-mm", str(kit / ("mmproj-" + weights)),
               "-mv", str(kit / ("vocoder-" + weights)),
               "--tts-speaker-file", str(kit / ("tokenizer-" + weights))]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    endpoint = f"http://127.0.0.1:{port}/v1/chat/completions"
    with (args.output / "server.log").open("wb") as log:
        proc = subprocess.Popen(command, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError("Liquid exited during startup. See server.log")
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        break
                except OSError:
                    time.sleep(0.25)
            else:
                raise TimeoutError("Liquid did not start")
            generate(opener, endpoint, "Hello. In one sentence, say hello back.", time.monotonic())
            for index, path in enumerate(args.inputs):
                wav = path.read_bytes()
                audio_content = [{"type": "input_audio", "input_audio": {
                    "data": base64.b64encode(wav).decode("ascii"), "format": "wav"}}]
                order = ("bridge", "direct") if index % 2 == 0 else ("direct", "bridge")
                for mode in order:
                    if mode == "bridge":
                        content, started = transcribe_at_capture_speed(wav, model, recognizer)
                        finalized = time.monotonic() - started
                        transcript = content
                    else:
                        content, started, finalized, transcript = audio_content, time.monotonic(), None, None
                    stats, audio = generate(opener, endpoint, content, started)
                    if transcript is not None:
                        stats.update(transcript=transcript, recognition_finalize_s=round(finalized, 3))
                    (args.output / f"{path.stem}-{mode}.wav").write_bytes(audio)
                    print(json.dumps({"fixture": path.stem, "mode": mode, **stats}), flush=True)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


if __name__ == "__main__":
    main()
