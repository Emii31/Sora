"""Measure a phone-hosted Liquid server through a loopback ADB forward.

Uses the existing Liquid timing and PCM validation code. Text inputs are saved
transcripts from the laptop baseline, so this measures phone inference without
claiming on-device speech recognition or microphone endpoint detection.
"""

import argparse
import base64
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

from benchmark_liquid_text_bridge import generate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--transcripts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("inputs", type=Path, nargs="+")
    args = parser.parse_args()
    endpoint = urllib.parse.urlsplit(args.endpoint)
    if endpoint.scheme != "http" or endpoint.hostname != "127.0.0.1":
        parser.error("Use a loopback HTTP endpoint forwarded from the phone")
    transcripts = {}
    for line in args.transcripts.read_text().splitlines():
        row = json.loads(line)
        if row.get("mode") == "bridge" and row.get("transcript"):
            transcripts[row["fixture"]] = row["transcript"]
    for path in args.inputs:
        if path.stem not in transcripts:
            parser.error(f"Missing baseline transcript for {path.name}")
        if not path.is_file():
            parser.error(f"Missing WAV input {path}")
    args.output.mkdir(parents=True, exist_ok=True)
    result_path = args.output / "timings.jsonl"
    if result_path.exists():
        parser.error("Choose a fresh output directory to preserve earlier results")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    generate(opener, args.endpoint, "Hello. In one sentence, say hello back.", time.monotonic())
    with result_path.open("x") as results:
        for index, path in enumerate(args.inputs):
            audio = [{"type": "input_audio", "input_audio": {
                "data": base64.b64encode(path.read_bytes()).decode("ascii"), "format": "wav"}}]
            order = ("text", "direct") if index % 2 == 0 else ("direct", "text")
            for mode in order:
                content = transcripts[path.stem] if mode == "text" else audio
                started = time.monotonic()
                stats, wav = generate(opener, args.endpoint, content, started)
                stats["total_s"] = round(time.monotonic() - started, 3)
                row = {"fixture": path.stem, "mode": mode, **stats}
                if mode == "text":
                    row["transcript"] = content
                (args.output / f"{path.stem}-{mode}.wav").write_bytes(wav)
                line = json.dumps(row)
                results.write(line + "\n")
                results.flush()
                print(line, flush=True)


if __name__ == "__main__":
    main()
