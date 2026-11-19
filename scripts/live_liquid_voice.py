"""Live terminal voice prototype using Liquid on the connected Android phone."""

import argparse
import json
from pathlib import Path
import select
import sys
import tempfile
import threading
import time

from liquid_phone import PhoneRunner
from voice_liquid_live import BufferedPlayer, LiquidStream, Microphone


class VoiceTurn:
    def __init__(self, endpoint, *, source=None, sink=None, threshold=0.015, buffer_seconds=1.5, vosk_model=None):
        self.stopped = threading.Event()
        self.microphone = Microphone(self.stopped, source=source, threshold=threshold, vosk_model=vosk_model)
        self.stream = LiquidStream(endpoint, self.stopped)
        self.sink = sink
        self.buffer_seconds = buffer_seconds
        self.player = None
        self.metrics = {}
        self.error = None
        self.thread = None

    def run(self, wav=None):
        try:
            if wav is None:
                print("Listening. Speak a sentence, then pause. Enter interrupts. q + Enter quits.", flush=True)
                wav = self.microphone.capture()
            if wav is None or self.stopped.is_set():
                if not self.stopped.is_set():
                    print("No utterance detected. Check the input device and speech threshold.", flush=True)
                return
            transcript = self.microphone.transcript
            if transcript:
                print("Heard: " + transcript, flush=True)
            started = time.monotonic()
            print("Thinking...", flush=True)
            self.player = BufferedPlayer(self.stopped, self.buffer_seconds, self.sink)
            text = []
            first_audio = None
            for kind, data in self.stream.events(wav, text=transcript):
                if self.stopped.is_set():
                    break
                if kind == "text":
                    text.append(data)
                    print(data, end="", flush=True)
                else:
                    if first_audio is None:
                        first_audio = time.monotonic() - started
                    self.player.feed(data)
            self.player.finish()
            if not self.stopped.is_set():
                self.metrics = {
                    "first_audio_s": first_audio,
                    "playback_started_s": self.player.started_at - started if self.player.started_at else None,
                    "turn_finished_s": time.monotonic() - started,
                    "estimated_gaps": self.player.estimated_gaps,
                    "audio_s": self.player.bytes_written / 48000,
                    "text_characters": len("".join(text)),
                }
                print("\n" + json.dumps(self.metrics), flush=True)
        except Exception as exc:
            if not self.stopped.is_set():
                self.error = exc
                print("\nVoice turn failed: " + str(exc), flush=True)
        finally:
            if self.player:
                self.player.cancel()

    def start(self, wav=None):
        self.thread = threading.Thread(target=self.run, args=(wav,), name="liquid-turn", daemon=True)
        self.thread.start()

    def cancel(self):
        self.stopped.set()
        self.stream.cancel()
        self.microphone.cancel()
        if self.player:
            self.player.cancel()
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                raise RuntimeError("Voice worker has not stopped. Close the session before retrying")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--source", help="PipeWire microphone node name")
    parser.add_argument("--vosk-model", type=Path, help="Use a local Vosk model to show and send the recognized text")
    parser.add_argument("--sink", help="PipeWire playback node name")
    parser.add_argument("--threshold", type=float, default=0.015, help="Microphone RMS threshold, default 0.015")
    parser.add_argument("--buffer-seconds", type=float, default=1.5)
    parser.add_argument("--replay", type=Path, help="Run one prerecorded input through real phone inference and playback")
    parser.add_argument("--once", action="store_true", help="Listen for one sentence and exit after its reply")
    parser.add_argument("--report", type=Path, help="Save diagnostic logs and timings in a fresh directory")
    args = parser.parse_args()
    if not 0 < args.threshold <= 1 or not 0 <= args.buffer_seconds <= 5:
        parser.error("Use a threshold between zero and one and a buffer from zero to five seconds")
    if not args.replay and not sys.stdin.isatty():
        parser.error("Live mode needs an interactive terminal")
    if args.vosk_model:
        from voice_input import _load_model

        print("Loading local speech recognition...", flush=True)
        _load_model(args.vosk_model.resolve())
    if args.report:
        args.report.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="sora-live-voice-") as temporary:
        directory = args.report or Path(temporary)
        with PhoneRunner(args.kit, directory / "server.log") as endpoint:
            def new_turn():
                return VoiceTurn(endpoint, source=args.source, sink=args.sink,
                                 threshold=args.threshold, buffer_seconds=args.buffer_seconds, vosk_model=args.vosk_model)
            turn = new_turn()
            try:
                turn.start(args.replay.read_bytes() if args.replay else None)
                while True:
                    if sys.stdin.isatty() and select.select([sys.stdin], [], [], 0.1)[0]:
                        command = sys.stdin.readline()
                        if not command or command.strip().lower() == "q":
                            break
                        print("\nInterrupted. Listening again...", flush=True)
                        turn.cancel()
                        if args.replay:
                            break
                        turn = new_turn()
                        turn.start()
                    if not sys.stdin.isatty():
                        time.sleep(0.05)
                    if not turn.thread.is_alive():
                        if turn.metrics and args.report:
                            with (directory / "turns.jsonl").open("a") as records:
                                records.write(json.dumps(turn.metrics) + "\n")
                        if args.replay or args.once:
                            if turn.error:
                                raise turn.error
                            break
                        if turn.error:
                            print("Press Enter to retry, or q + Enter to quit.", flush=True)
                            command = sys.stdin.readline()
                            if not command or command.strip().lower() == "q":
                                break
                        time.sleep(0.25)
                        turn = new_turn()
                        turn.start()
            finally:
                turn.cancel()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
