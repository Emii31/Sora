"""Live terminal voice prototype using Liquid on the connected Android phone."""

import argparse
import json
import os
from pathlib import Path
import queue
import select
import sys
import tempfile
import threading
import time

from liquid_phone import PhoneRunner
from voice_brain import LocalVoiceBrain
from voice_continuous import ContinuousLiquid
from voice_liquid_live import BufferedPlayer, LiquidStream, Microphone, voice_playback_buffer
from voice_sopro_live import SoproStream, sopro_session


class VoiceTurn:
    def __init__(self, endpoint, *, source=None, sink=None, threshold=0.015, buffer_seconds=None,
                 vosk_model=None, context=None, smooth_long_replies=False, sentence_streaming=False,
                 continuous_speech=False, sopro_reference=None):
        if sum((sentence_streaming, smooth_long_replies, continuous_speech)) > 1:
            raise ValueError("Choose one experimental playback mode")
        if continuous_speech and context is None:
            raise ValueError("Continuous speech requires account context")
        if sopro_reference is not None and (context is None or
                any((sentence_streaming, smooth_long_replies, continuous_speech))):
            raise ValueError("Sopro requires account context and the regular playback path")
        self.stopped = threading.Event()
        self.microphone = Microphone(self.stopped, source=source, threshold=threshold, vosk_model=vosk_model)
        self.sopro = sopro_reference is not None
        if self.sopro:
            self.stream = SoproStream(endpoint, self.stopped, sopro_reference)
        else:
            self.stream = (ContinuousLiquid if continuous_speech else LiquidStream)(endpoint, self.stopped)
        self.sink = sink
        self.buffer_seconds = buffer_seconds
        self.smooth_long_replies = smooth_long_replies
        self.sentence_streaming = sentence_streaming
        self.continuous_speech = continuous_speech
        self.speech_thread = None
        self.speech_error = None
        self.player = None
        self.metrics = {}
        self.error = None
        self.thread = None
        self.context = context
        self.brain = LocalVoiceBrain(self.stopped) if context else None

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
            if self.context and transcript is None:
                from voice_input import transcribe_wav

                transcript = transcribe_wav(wav)
                if not transcript:
                    raise RuntimeError("No speech was recognized in the voice input")
            if transcript:
                print("Heard: " + transcript, flush=True)
            started = time.monotonic()
            snapshot = self.context.prepare(transcript) if self.context else None
            print("Thinking...", flush=True)
            if snapshot and self.continuous_speech:
                self._run_continuous(wav, snapshot, started)
                return
            if snapshot and self.sentence_streaming:
                self._run_sentences(wav, snapshot, started)
                return
            reply_text = self.context.respond(snapshot, self.brain) if snapshot else None
            brain_ready = time.monotonic() - started if snapshot else None
            if self.stopped.is_set():
                return
            buffer_seconds = self.buffer_seconds
            if buffer_seconds is None:
                buffer_seconds = 0.25 if self.sopro else voice_playback_buffer(
                    reply_text, smooth_long=self.smooth_long_replies)
            self.player = BufferedPlayer(self.stopped, buffer_seconds, self.sink)
            text = []
            first_audio = None
            options = {"text": transcript}
            if snapshot:
                options["spoken_text"] = reply_text
                options["text"] = "Please speak to me."
            for kind, data in self.stream.events(wav, **options):
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
                    "brain_ready_s": brain_ready,
                    "brain_first_token_s": getattr(self.brain, "metrics", {}).get("first_token_s"),
                    "buffer_seconds": buffer_seconds,
                    "playback_policy": "complete_reply" if buffer_seconds is None else "streaming",
                    "playback_started_s": self.player.started_at - started if self.player.started_at else None,
                    "turn_finished_s": time.monotonic() - started,
                    "estimated_gaps": self.player.estimated_gaps,
                    "audio_s": self.player.bytes_written / 48000,
                    "text_characters": len("".join(text)),
                }
                if self.sopro:
                    self.metrics["speech_engine"] = "sopro"
                    ended = self.microphone.speech_ended_at
                    self.metrics["speech_end_to_playback_pipe_s"] = (
                        self.player.started_at - ended if ended and self.player.started_at else None)
                if snapshot:
                    if "".join(text).strip() != reply_text:
                        raise RuntimeError("Voice output text differs from Sora's reply")
                    self.context.commit(snapshot, reply_text)
                    self.metrics["character"] = snapshot.character_name
                    self.metrics["history_saved"] = True
                print("\n" + json.dumps(self.metrics), flush=True)
        except Exception as exc:
            if not self.stopped.is_set():
                self.error = exc
                print("\nVoice turn failed: " + str(exc), flush=True)
        finally:
            if self.speech_thread:
                self.stopped.set()
                self.stream.cancel()
                self.brain.cancel()
            if self.player:
                self.player.cancel()
            if self.speech_thread:
                self.speech_thread.join(timeout=5)
                if self.speech_thread.is_alive():
                    self.error = RuntimeError("Speech worker has not stopped. Close the session before retrying")

    def _run_sentences(self, wav, snapshot, started):
        pending = queue.Queue(maxsize=4)
        parts = []
        timing = {"first_sentence_s": None, "first_audio_s": None}
        audio_bytes = 0

        def put(part):
            while not self.stopped.is_set():
                if self.speech_error:
                    raise self.speech_error
                try:
                    pending.put(part, timeout=0.05)
                    return
                except queue.Full:
                    pass

        def receive(part):
            if not part.strip():
                return
            if len(parts) >= 16:
                raise ValueError("Spoken reply exceeds 16 sentence segments")
            if timing["first_sentence_s"] is None:
                timing["first_sentence_s"] = time.monotonic() - started
            parts.append(part)
            put(part)

        def speak():
            nonlocal audio_bytes
            try:
                while not self.stopped.is_set():
                    try:
                        part = pending.get(timeout=0.05)
                    except queue.Empty:
                        continue
                    if part is None:
                        return
                    requested = part.strip()
                    if self.player is None:
                        reserve = self.buffer_seconds if self.buffer_seconds is not None else voice_playback_buffer(requested)
                        timing["buffer_seconds"] = reserve
                        self.player = BufferedPlayer(self.stopped, reserve, self.sink)
                    spoken = []
                    for kind, data in self.stream.events(wav, text="Read this aloud: " + requested, spoken_text=requested):
                        if self.stopped.is_set():
                            return
                        if kind == "text":
                            spoken.append(data)
                            print(data, end="", flush=True)
                        else:
                            if timing["first_audio_s"] is None:
                                timing["first_audio_s"] = time.monotonic() - started
                            audio_bytes += len(data)
                            if audio_bytes > 48000 * 30:
                                raise ValueError("Spoken reply exceeds 30 seconds")
                            self.player.feed(data)
                    if not self.stopped.is_set() and "".join(spoken) != requested:
                        raise RuntimeError("Sentence speech text differs from Sora's reply")
                    print(" ", end="", flush=True)
            except Exception as exc:
                if not self.stopped.is_set():
                    self.speech_error = exc
                    self.brain.abort()

        self.speech_thread = threading.Thread(target=speak, name="liquid-sentences", daemon=True)
        self.speech_thread.start()
        try:
            reply = self.context.respond(snapshot, self.brain, on_sentence=receive)
        except Exception:
            if self.speech_error:
                raise self.speech_error
            raise
        brain_ready = time.monotonic() - started
        put(None)
        while self.speech_thread.is_alive() and not self.stopped.is_set():
            self.speech_thread.join(timeout=0.05)
        if self.speech_error:
            raise self.speech_error
        if self.stopped.is_set():
            return
        if not self.player or "".join(parts).strip() != reply:
            raise RuntimeError("Sentence segments do not match the completed reply")
        self.player.finish()
        if self.stopped.is_set():
            return
        self.context.commit(snapshot, reply)
        self.metrics = {
            **timing, "brain_ready_s": brain_ready,
            "brain_first_token_s": self.brain.metrics.get("first_token_s"),
            "playback_started_s": self.player.started_at - started if self.player.started_at else None,
            "turn_finished_s": time.monotonic() - started,
            "playback_policy": "sentence_streaming", "segments": len(parts),
            "estimated_gaps": self.player.estimated_gaps,
            "audio_s": self.player.bytes_written / 48000,
            "text_characters": len(reply), "character": snapshot.character_name, "history_saved": True,
        }
        print("\n" + json.dumps(self.metrics), flush=True)

    def _run_continuous(self, wav, snapshot, started):
        reserve = self.buffer_seconds if self.buffer_seconds is not None else 0.5
        self.player = BufferedPlayer(self.stopped, reserve, self.sink)
        spoken = []
        timing = {"first_audio_s": None, "first_text_sent_s": None}
        pending_text = ''
        updates = 0
        leading = True

        def speak():
            try:
                for kind, data in self.stream.events(wav, text=snapshot.user_text):
                    if self.stopped.is_set():
                        return
                    if kind == 'text':
                        spoken.append(data)
                        print(data, end='', flush=True)
                    else:
                        if timing['first_audio_s'] is None:
                            timing['first_audio_s'] = time.monotonic() - started
                        self.player.feed(data)
            except Exception as exc:
                if not self.stopped.is_set():
                    self.speech_error = exc
                    self.brain.abort()

        def receive(text):
            nonlocal pending_text, updates, leading
            if self.speech_error:
                raise self.speech_error
            if leading:
                text = text.lstrip()
                if not text:
                    return
                leading = False
            pending_text += text
            stable = pending_text.rstrip()
            if len(stable.encode('utf-8')) >= 12:
                self.stream.append(stable)
                updates += 1
                if timing['first_text_sent_s'] is None:
                    timing['first_text_sent_s'] = time.monotonic() - started
                pending_text = pending_text[len(stable):]

        self.speech_thread = threading.Thread(target=speak, name='liquid-continuous', daemon=True)
        self.speech_thread.start()
        try:
            reply = self.context.respond(snapshot, self.brain, on_text=receive)
            brain_ready = time.monotonic() - started
            if self.stopped.is_set():
                return
            self.stream.append(pending_text.rstrip(), final=True)
            if timing['first_text_sent_s'] is None:
                timing['first_text_sent_s'] = time.monotonic() - started
        except Exception:
            if self.speech_error:
                raise self.speech_error
            raise
        while self.speech_thread.is_alive() and not self.stopped.is_set():
            self.speech_thread.join(timeout=.05)
        if self.speech_error:
            raise self.speech_error
        if self.stopped.is_set():
            return
        if ''.join(spoken).strip() != reply:
            raise RuntimeError('Continuous speech text differs from the completed reply')
        self.player.finish()
        if self.stopped.is_set():
            return
        self.context.commit(snapshot, reply)
        self.metrics = {
            **timing, 'brain_ready_s': brain_ready,
            'brain_first_token_s': self.brain.metrics.get('first_token_s'),
            'buffer_seconds': reserve, 'playback_policy': 'continuous_speech', 'input_updates': updates + 1,
            'playback_started_s': self.player.started_at - started if self.player.started_at else None,
            'turn_finished_s': time.monotonic() - started, 'estimated_gaps': self.player.estimated_gaps,
            'audio_s': self.player.bytes_written / 48000, 'text_characters': len(reply),
            'character': snapshot.character_name, 'history_saved': True,
        }
        print('\n' + json.dumps(self.metrics), flush=True)

    def start(self, wav=None):
        self.thread = threading.Thread(target=self.run, args=(wav,), name="liquid-turn", daemon=True)
        self.thread.start()

    def cancel(self):
        self.stopped.set()
        if self.brain:
            self.brain.cancel()
        self.stream.cancel()
        self.microphone.cancel()
        if self.player:
            self.player.cancel()
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                raise RuntimeError("Voice worker has not stopped. Close the session before retrying")
        if self.speech_thread:
            self.speech_thread.join(timeout=5)
            if self.speech_thread.is_alive():
                raise RuntimeError("Speech worker has not stopped. Close the session before retrying")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    engines = parser.add_mutually_exclusive_group(required=True)
    engines.add_argument("--kit", type=Path, help="Liquid model and Android runner kit")
    engines.add_argument("--sopro-runtime", type=Path, help="Directory containing the native Sopro server")
    parser.add_argument("--sopro-model", type=Path, help="Local Sopro model directory")
    parser.add_argument("--sopro-reference", type=Path, help="Approved 5–20 second voice reference WAV")
    parser.add_argument("--source", help="PipeWire microphone node name")
    parser.add_argument("--vosk-model", type=Path, help="Use a local Vosk model to show and send the recognized text")
    parser.add_argument("--sink", help="PipeWire playback node name")
    parser.add_argument("--threshold", type=float, default=0.015, help="Microphone RMS threshold, default 0.015")
    parser.add_argument("--buffer-seconds", type=float, help="Override automatic reply-length buffering (0–5 seconds)")
    parser.add_argument("--no-warmup", action="store_true", help="Skip chat-model prefill before listening")
    playback_modes = parser.add_mutually_exclusive_group()
    playback_modes.add_argument("--smooth-long-replies", action="store_true",
                        help="Wait for complete long replies before playback; avoids generation gaps but starts later")
    playback_modes.add_argument("--sentence-streaming", action="store_true",
                                help="Speak completed sentences while the local brain continues (experimental)")
    playback_modes.add_argument("--continuous-speech", action="store_true",
                                help="Feed text into one continuous speech-model session (experimental)")
    parser.add_argument("--replay", type=Path, help="Run one prerecorded input through inference and playback")
    parser.add_argument("--once", action="store_true", help="Listen for one sentence and exit after its reply")
    parser.add_argument("--wait-to-listen", action="store_true", help="Wait for Enter after warmup before opening the microphone")
    parser.add_argument("--user-id", help="Select an active local Sora account when several exist")
    parser.add_argument("--report", type=Path, help="Save diagnostic logs and timings in a fresh directory")
    args = parser.parse_args()
    if args.sopro_runtime and (not args.sopro_model or not args.sopro_reference):
        parser.error("Sopro needs --sopro-model and --sopro-reference")
    if args.sopro_runtime and any((args.continuous_speech, args.sentence_streaming, args.smooth_long_replies)):
        parser.error("Those playback modes apply only to Liquid")
    if args.kit and (args.sopro_model or args.sopro_reference):
        parser.error("The Sopro model and reference options need --sopro-runtime")
    if args.replay and args.wait_to_listen:
        parser.error("--wait-to-listen is available only for microphone input")
    if not 0 < args.threshold <= 1 or (args.buffer_seconds is not None and not 0 <= args.buffer_seconds <= 5):
        parser.error("Use a threshold between zero and one and a buffer from zero to five seconds")
    if not args.replay and not sys.stdin.isatty():
        parser.error("Live mode needs an interactive terminal")
    from voice_context import LocalVoiceContext

    context = LocalVoiceContext(user_id=args.user_id)
    if not args.vosk_model:
        parser.error("Sora context needs local recognition. Supply --vosk-model to transcribe your input")
    print("Using Sora context from " + context.data_dir, flush=True)
    if args.vosk_model:
        from voice_input import _load_model

        print("Loading local speech recognition...", flush=True)
        os.environ["SORA_VOSK_MODEL_DIR"] = str(args.vosk_model.resolve())
        _load_model(args.vosk_model.resolve())
    warmup_seconds = None
    if not args.no_warmup:
        print("Warming Sora's local chat model before listening...", flush=True)
        warm_started = time.monotonic()
        context.warmup(LocalVoiceBrain(threading.Event()))
        warmup_seconds = time.monotonic() - warm_started
        print(f"Chat model ready after {warmup_seconds:.2f}s. No conversation was saved.", flush=True)
    if args.report:
        args.report.mkdir(parents=True, exist_ok=False)
        (args.report / "startup.json").write_text(json.dumps({"brain_warmup_s": warmup_seconds}) + "\n")
    with tempfile.TemporaryDirectory(prefix="sora-live-voice-") as temporary:
        directory = args.report or Path(temporary)
        session = (sopro_session(args.sopro_runtime, args.sopro_model, args.sopro_reference, directory)
                   if args.sopro_runtime else PhoneRunner(args.kit, directory / "server.log"))
        with session as endpoint:
            if args.wait_to_listen:
                print("Ready. Press Enter to open the microphone.", flush=True)
                start_command = sys.stdin.readline()
                if not start_command or start_command.strip().lower() == "q":
                    return
            def new_turn():
                return VoiceTurn(endpoint, source=args.source, sink=args.sink,
                                 threshold=args.threshold, buffer_seconds=args.buffer_seconds,
                                 vosk_model=args.vosk_model, context=context,
                                 smooth_long_replies=args.smooth_long_replies,
                                 sentence_streaming=args.sentence_streaming,
                                 continuous_speech=args.continuous_speech,
                                 sopro_reference=args.sopro_reference)
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
                        turn.cancel()
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
