import sys
import os
import tempfile
import time
import json
import resource
from openai import OpenAI
from flask import Flask

# 1. Create disposable DATA_DIR BEFORE importing application modules
_temp_dir = tempfile.TemporaryDirectory()
data_dir = _temp_dir.name
os.environ["DATA_DIR"] = data_dir

# Seed ai_config.json so LLM calls work out of the box in disposable dir
admin_dir = os.path.join(data_dir, "_admin")
os.makedirs(admin_dir, exist_ok=True)
config_path = os.path.join(admin_dir, "ai_config.json")
with open(config_path, "w", encoding="utf-8") as f:
    json.dump({
        "tiers": {
            "vision": {"host": "http://127.0.0.1:11434/v1", "api_key": "ollama", "model": "qwen2.5:1.5b-instruct"},
            "chat": {"host": "http://127.0.0.1:11434/v1", "api_key": "ollama", "model": "qwen2.5:1.5b-instruct"},
            "memory": {"host": "http://127.0.0.1:11434/v1", "api_key": "ollama", "model": "qwen2.5:1.5b-instruct"}
        }
    }, f, indent=2)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import storage
import core
import user_settings
import ai_config

def get_python_rss_mb():
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return int(parts[1]) / 1024.0
    except Exception:
        pass
    try:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    except Exception:
        return 0.0

def get_ollama_rss_mb():
    try:
        import subprocess
        res = subprocess.run(["ps", "-C", "ollama", "-o", "rss="], capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            vals = [int(x) for x in res.stdout.strip().split() if x.isdigit()]
            if vals:
                return sum(vals) / 1024.0
    except Exception:
        pass
    return None

def run_benchmark_mode(fast_mode: bool):
    print(f"\n--- Running Benchmark (Fast Mode: {fast_mode}) ---")
    storage._ensure_dirs()
    user_settings.update({"local_text_chat_enabled": fast_mode})

    base_url = "http://127.0.0.1:11434/v1"
    model = "qwen2.5:1.5b-instruct"
    client = OpenAI(base_url=base_url, api_key="ollama")

    prompt = "Hello, who are you? Give a brief reply."

    # 1. Direct Ollama timing (warm model)
    t_direct_start = time.monotonic()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.7
        )
        direct_reply = resp.choices[0].message.content
    except Exception as e:
        direct_reply = f"ERROR: {e}"
    t_direct_end = time.monotonic()
    direct_time = t_direct_end - t_direct_start
    print(f"  Direct Ollama Time: {direct_time:.2f}s | Reply: {direct_reply}")

    # 2. Sora /api/chat send-to-history timing matching exact reply ID
    unique_text = f"Benchmark msg {time.time()} (fast={fast_mode})"
    t_sora_start = time.monotonic()
    res = core.receive_chat_message(unique_text)
    user_msg_id = res.get("msg_id")
    expected_reply_id = user_msg_id + "_reply"
    print(f"  Sora message received: {user_msg_id}, expecting reply ID: {expected_reply_id}")

    assistant_reply = ""
    timeout = 120.0
    poll_start = time.monotonic()
    success = False

    while time.monotonic() - poll_start < timeout:
        history = storage.get_chat_history(limit=50)
        for m in history:
            if m.get("id") == expected_reply_id:
                assistant_reply = m.get("text", "")
                success = True
                break
        if success:
            break
        time.sleep(0.5)

    t_sora_end = time.monotonic()
    sora_total_time = t_sora_end - t_sora_start

    if not success or not assistant_reply or "error" in assistant_reply.lower() or "小问题" in assistant_reply or "我还没有配置好" in assistant_reply:
        print(f"  FAILURE: Timeout or error reply received: {assistant_reply}")
        return {
            "fast_mode": fast_mode,
            "direct_time": direct_time,
            "sora_time": None,
            "success": False,
            "reply": assistant_reply
        }

    print(f"  Sora Reply: {assistant_reply}")
    print(f"  Sora Send-to-History Time: {sora_total_time:.2f}s")

    py_rss = get_python_rss_mb()
    ollama_rss = get_ollama_rss_mb()
    ollama_str = f"{ollama_rss:.2f} MB" if ollama_rss is not None else "Unavailable (process query failed)"
    print(f"  Memory -> Python RSS: {py_rss:.2f} MB | Ollama RSS: {ollama_str}")

    return {
        "fast_mode": fast_mode,
        "direct_time": direct_time,
        "sora_time": sora_total_time,
        "success": True,
        "reply": assistant_reply,
        "py_rss": py_rss,
        "ollama_rss": ollama_rss
    }

def main():
    print("=== Sora Local Chat Comprehensive Benchmark ===")
    app = Flask(__name__)
    with app.test_request_context():
        from flask import g
        g.user_id = "_admin"
        g.user_data_dir = data_dir

        # 1. Full Agent Mode (fast_mode = False)
        res_full = run_benchmark_mode(fast_mode=False)

        # Wait a moment between tests to ensure quiet timer finishes
        time.sleep(3.0)

        # 2. Fast Local Text Mode (fast_mode = True)
        res_fast = run_benchmark_mode(fast_mode=True)

        print("\n=== Benchmark Summary ===")
        print(f"Full Mode  : Direct={res_full.get('direct_time', 0):.2f}s, Sora Total={res_full.get('sora_time', 'TIMEOUT')}s, Success={res_full.get('success')}")
        print(f"Fast Mode  : Direct={res_fast.get('direct_time', 0):.2f}s, Sora Total={res_fast.get('sora_time', 'TIMEOUT')}s, Success={res_fast.get('success')}")

    _temp_dir.cleanup()

if __name__ == "__main__":
    main()
