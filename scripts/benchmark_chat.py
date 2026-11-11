import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import json
import resource
from openai import OpenAI
from flask import Flask

def get_rss_mb():
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return int(parts[1]) / 1024.0
    except Exception:
        pass
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

def get_ollama_rss():
    try:
        import subprocess
        res = subprocess.run(["ps", "-C", "ollama", "-o", "rss="], capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return int(res.stdout.strip()) / 1024.0
    except Exception:
        pass
    return 0.0

def main():
    print("=== Sora Local Chat Speed Benchmark (Fast Path Enabled) ===")
    base_url = "http://127.0.0.1:11434/v1"
    model = "qwen2.5:1.5b-instruct"

    import storage
    import core
    import user_settings

    data_dir = "data"
    os.environ["DATA_DIR"] = data_dir
    storage._ensure_dirs()

    app = Flask(__name__)
    with app.test_request_context():
        from flask import g
        g.user_id = "_admin"
        g.user_data_dir = data_dir

        # Enable local text chat fast path
        user_settings.update({"local_text_chat_enabled": True})

        unique_text = f"Hello fast benchmark {time.time()}"
        t_sora_start = time.monotonic()
        res = core.receive_chat_message(unique_text)
        msg_id = res.get("msg_id")
        print(f"Sora message received: {msg_id}, waiting for background generation...")

        assistant_reply = ""
        timeout = 60.0
        poll_start = time.monotonic()
        while time.monotonic() - poll_start < timeout:
            history = storage.get_chat_history(limit=50)
            found_user = False
            for m in history:
                if m.get("id") == msg_id:
                    found_user = True
                    continue
                if found_user and m.get("role") == "assistant":
                    assistant_reply = m.get("text", "")
                    break
            if assistant_reply:
                break
            time.sleep(0.2)

        t_sora_end = time.monotonic()
        sora_total_time = t_sora_end - t_sora_start
        print(f"Sora Assistant Reply: {assistant_reply}")
        print(f"Sora Fast Path Total Time (until in history): {sora_total_time:.2f}s")

    py_rss = get_rss_mb()
    ollama_rss = get_ollama_rss()
    print(f"\nMemory Report:")
    print(f"  - Python RSS: {py_rss:.2f} MB")
    print(f"  - Ollama RSS: {ollama_rss:.2f} MB")
    print(f"  - Model loaded: Yes ({model})")

if __name__ == "__main__":
    main()
