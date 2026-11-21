"""Manage the standalone Liquid runner on one explicitly connected Android phone."""

import hashlib
import http.client
import json
from pathlib import Path
import subprocess
import threading
import time

from voice_liquid_live import stop_process


class PhoneRunner:
    remote = "/data/local/tmp/sora-liquid-live"

    def __init__(self, kit, log_path, *, cpu_mask=0xf0, threads=4):
        if (type(cpu_mask) is not int or not 0 < cpu_mask <= 0xff
                or type(threads) is not int or not 1 <= threads <= cpu_mask.bit_count()):
            raise ValueError("Use a valid eight-core CPU mask and thread count")
        self.cpu_mask = format(cpu_mask, "x")
        self.threads = threads
        self.kit = Path(kit).resolve()
        self.log_path = Path(log_path)
        self.proc = None
        self.log = None
        self.serial = None
        self.port = None
        self.locked = False
        self.affinity_stop = threading.Event()
        self.affinity_thread = None
        self.pid = None

    def adb(self, *args, check=True):
        command = ["adb"]
        if self.serial:
            command.extend(["-s", self.serial])
        return subprocess.run(command + list(args), stdin=subprocess.DEVNULL,
                              check=check, capture_output=True, text=True, timeout=90)

    def __enter__(self):
        try:
            return self.start()
        except BaseException:
            self.close()
            raise

    def __exit__(self, *args):
        self.close()

    def start(self):
        devices = [line.split()[0] for line in self.adb("devices").stdout.splitlines()[1:]
                   if len(line.split()) >= 2 and line.split()[1] == "device"]
        if len(devices) != 1:
            raise RuntimeError("Connect and authorize exactly one Android phone")
        self.serial = devices[0]
        weights = "LFM2.5-Audio-1.5B-Q4_0.gguf"
        models = [self.kit / (prefix + weights) for prefix in ("", "mmproj-", "vocoder-", "tokenizer-")]
        binary = self.kit / "android/build/bin/llama-liquid-audio-server"
        for path in [binary, *models]:
            if not path.is_file():
                raise FileNotFoundError(f"Missing local runner or model: {path}")
        self.adb("shell", f"mkdir -p {self.remote} && chmod 700 {self.remote} && mkdir {self.remote}/session.lock")
        self.locked = True
        print("Checking the phone's local Liquid model cache...", flush=True)
        for path in [binary, *models]:
            with path.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            remote_path = self.remote + "/" + path.name
            saved = self.adb("shell", "sha256sum " + remote_path, check=False)
            if saved.returncode != 0 or saved.stdout.split()[0] != digest:
                print("Copying " + path.name, flush=True)
                self.adb("push", str(path), remote_path)
                verified = self.adb("shell", "sha256sum " + remote_path)
                if verified.stdout.split()[0] != digest:
                    raise RuntimeError("Phone model checksum mismatch")
        self.adb("shell", f"chmod 700 {self.remote}/llama-liquid-audio-server")
        self.port = self.adb("forward", "tcp:0", "tcp:18086").stdout.strip()
        if not self.port.isdigit():
            raise RuntimeError("ADB did not allocate a loopback port")
        command = (f"cd {self.remote} && echo $$ > session.lock/pid && "
                   f"exec taskset {self.cpu_mask} ./llama-liquid-audio-server --host 127.0.0.1 --port 18086 "
                   f"-ngl 0 --seed 7 -t {self.threads} -tb {self.threads} -c 2048 "
                   f"--cpu-mask {self.cpu_mask} --cpu-mask-batch {self.cpu_mask} "
                   f"-m {weights} -mm mmproj-{weights} -mv vocoder-{weights} "
                   f"--tts-speaker-file tokenizer-{weights}")
        self.log = self.log_path.open("wb")
        self.proc = subprocess.Popen(["adb", "-s", self.serial, "shell", command],
                                     stdin=subprocess.DEVNULL, stdout=self.log, stderr=self.log)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError("Phone runner exited. See its server log")
            connection = http.client.HTTPConnection("127.0.0.1", int(self.port), timeout=1)
            try:
                connection.request("GET", "/")
                if connection.getresponse().status == 404:
                    break
            except OSError:
                time.sleep(0.25)
            finally:
                connection.close()
        else:
            raise TimeoutError("Phone runner did not become ready")
        health = http.client.HTTPConnection("127.0.0.1", int(self.port), timeout=3)
        try:
            health.request("GET", "/health")
            response = health.getresponse()
            capabilities = json.loads(response.read(4096)) if response.status == 200 else {}
            if any(capabilities.get(key) != 1 for key in ('forced_text', 'turn_reset', 'continuous_text')):
                raise RuntimeError("Rebuild the Android runner with the repository's current continuous-speech patch")
        finally:
            health.close()
        self.adb("shell", f'cd {self.remote} && taskset -ap {self.cpu_mask} "$(cat session.lock/pid)"')
        self.pid = self.adb("shell", f"cat {self.remote}/session.lock/pid").stdout.strip()
        if not self.pid.isdigit():
            raise RuntimeError("Phone did not report a valid runner PID")
        self.affinity_thread = threading.Thread(target=self._maintain_affinity, name="liquid-phone-affinity", daemon=True)
        self.affinity_thread.start()
        return f"http://127.0.0.1:{self.port}/v1/chat/completions"

    def _maintain_affinity(self):
        # Android can narrow shell-process affinity again after model startup.
        while not self.affinity_stop.is_set():
            if self.proc.poll() is not None:
                return
            try:
                subprocess.run(["adb", "-s", self.serial, "shell", "taskset", "-ap", self.cpu_mask, self.pid],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            except subprocess.TimeoutExpired:
                pass
            self.affinity_stop.wait(1)

    def close(self):
        self.affinity_stop.set()
        if self.affinity_thread:
            self.affinity_thread.join(timeout=4)
        try:
            if self.locked:
                stopped = self.adb("shell", f'cd {self.remote} && '
                                   '{ if [ -f session.lock/pid ]; then kill "$(cat session.lock/pid)" 2>/dev/null; fi; '
                                   'rm -f session.lock/pid; rmdir session.lock; }', check=False)
                if stopped.returncode != 0:
                    print("Phone cleanup could not be confirmed. Reconnect it and check the live runner.", flush=True)
        finally:
            stop_process(self.proc)
            if self.port:
                self.adb("forward", "--remove", "tcp:" + self.port, check=False)
            if self.log:
                self.log.close()
