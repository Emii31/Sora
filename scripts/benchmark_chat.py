import sys
import os
import tempfile
import time
import json
import statistics
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

def run_benchmark_mode(fast_mode: bool, num_turns: int = 2):
    print(f"\n--- Running Benchmark (Fast Mode: {fast_mode}, Turns: {num_turns}) ---")
    storage._ensure_dirs()
    user_settings.update({"local_text_chat_enabled": fast_mode})

    base_url = "http://127.0.0.1:11434/v1"
    model = "qwen2.5:1.5b-instruct"
    client = OpenAI(base_url=base_url, api_key="ollama")

    direct_times = []
    sora_times = []
    successes = []

    for i in range(num_turns):
        prompt = f"Synthetic benchmark turn {i+1} for Sora local chat."

        # 1. Direct Ollama timing (warmed model)
        t_direct_start = time.monotonic()
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=60,
                temperature=0.7
            )
            direct_reply = resp.choices[0].message.content
        except Exception as e:
            direct_reply = f"ERROR: {e}"
        t_direct_end = time.monotonic()
        direct_time = t_direct_end - t_direct_start
        direct_times.append(direct_time)

        # 2. Sora /api/chat send-to-history timing matching exact reply ID
        unique_text = f"SynthMsg {i+1} {time.time()} (fast={fast_mode})"
        t_sora_start = time.monotonic()
        res = core.receive_chat_message(unique_text)
        user_msg_id = res.get("msg_id")
        expected_reply_id = user_msg_id + "_reply"

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
            time.sleep(0.3)

        t_sora_end = time.monotonic()
        sora_total_time = t_sora_end - t_sora_start

        if (
            not success
            or not assistant_reply
            or assistant_reply.lower().startswith("error:")
            or "i haven't configured my models yet" in assistant_reply.lower()
            or "i couldn't connect to the model service" in assistant_reply.lower()
            or "i ran into a small issue" in assistant_reply.lower()
            or "小问题" in assistant_reply
            or "我还没有配置好" in assistant_reply
        ):
            print(f"  Turn {i+1} FAILURE: Timeout or error reply received: {assistant_reply}")
            successes.append(False)
        else:
            print(f"  Turn {i+1} Success | Direct: {direct_time:.2f}s | Sora Send-to-History: {sora_total_time:.2f}s | Reply: {assistant_reply[:60]}...")
            sora_times.append(sora_total_time)
            successes.append(True)

        time.sleep(1.0)

    all_success = all(successes) and len(sora_times) > 0
    median_direct = statistics.median(direct_times) if direct_times else 0.0
    median_sora = statistics.median(sora_times) if sora_times else None

    py_rss = get_python_rss_mb()
    ollama_rss = get_ollama_rss_mb()
    ollama_str = f"{ollama_rss:.2f} MB" if ollama_rss is not None else "Unavailable"
    print(f"  Mode summary (fast={fast_mode}): Success={all_success} | Median Direct Latency={median_direct:.2f}s | Median Send-to-History={median_sora if median_sora is not None else 'TIMEOUT'}s | Python RSS={py_rss:.2f} MB | Ollama RSS={ollama_str}")

    return {
        "fast_mode": fast_mode,
        "direct_times": direct_times,
        "median_direct": median_direct,
        "sora_times": sora_times,
        "median_sora": median_sora,
        "success": all_success,
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
        res_full = run_benchmark_mode(fast_mode=False, num_turns=2)

        time.sleep(2.0)

        # 2. Fast Local Text Mode (fast_mode = True)
        res_fast = run_benchmark_mode(fast_mode=True, num_turns=2)

        print("\n=== Benchmark Summary ===")
        print(f"Full Mode  : Median Direct={res_full.get('median_direct', 0):.2f}s, Median Sora Total={res_full.get('median_sora', 'TIMEOUT')}s, Success={res_full.get('success')}")
        print(f"Fast Mode  : Median Direct={res_fast.get('median_direct', 0):.2f}s, Median Sora Total={res_fast.get('median_sora', 'TIMEOUT')}s, Success={res_fast.get('success')}")

        if not res_full.get('success') or not res_fast.get('success'):
            print("ERROR: Benchmark failed in one or more modes.", file=sys.stderr)
            sys.exit(1)

    _temp_dir.cleanup()

if __name__ == "__main__":
    main()
