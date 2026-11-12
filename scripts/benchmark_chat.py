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
import auth
import app as app_mod

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

def verify_and_set_user_setting(client, auth_token: str, fast_mode: bool):
    headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    environ = {"REMOTE_ADDR": "127.0.0.1"}

    # Set setting via authenticated /api/user-settings route
    post_res = client.post(
        "/api/user-settings",
        json={"local_text_chat_enabled": fast_mode},
        headers=headers,
        environ_base=environ
    )
    if post_res.status_code != 200:
        raise RuntimeError(f"Failed to set user settings: {post_res.status_code} {post_res.get_data(as_text=True)}")

    # Read back setting to verify persistence
    get_res = client.get(
        "/api/user-settings",
        headers=headers,
        environ_base=environ
    )
    if get_res.status_code != 200:
        raise RuntimeError(f"Failed to read back user settings: {get_res.status_code}")

    data = get_res.get_json() or {}
    settings = data.get("settings", {})
    persisted_val = settings.get("local_text_chat_enabled")
    if persisted_val != fast_mode:
        raise AssertionError(f"Setting persistence failed: expected local_text_chat_enabled={fast_mode}, got {persisted_val}")

    # Verify policy in harness reaches reactive_fast in fast mode and v4_pro in full mode
    policy = core._resolve_chat_agent_policy(user_text="Matched test prompt")
    expected_mode = "reactive_fast" if fast_mode else "v4_pro"
    if policy.get("mode") != expected_mode:
        raise AssertionError(f"Harness mode mismatch for fast_mode={fast_mode}: expected {expected_mode}, got {policy.get('mode')}")

    print(f"[Benchmark] Verified setting persistence and policy mode={policy.get('mode')} for fast_mode={fast_mode}")

def run_benchmark_mode(client, auth_token: str, fast_mode: bool, num_turns: int = 2, prompt_text: str = "Synthetic benchmark prompt for Sora local chat."):
    print(f"\n--- Running Benchmark (Fast Mode: {fast_mode}, Turns: {num_turns}) ---")
    storage._ensure_dirs()

    # 1. Set and verify mode persistence through authenticated /api/user-settings route
    verify_and_set_user_setting(client, auth_token, fast_mode)

    base_url = "http://127.0.0.1:11434/v1"
    model = "qwen2.5:1.5b-instruct"
    openai_client = OpenAI(base_url=base_url, api_key="ollama")

    direct_times = []
    sora_times = []
    successes = []
    headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
    environ = {"REMOTE_ADDR": "127.0.0.1"}

    for i in range(num_turns):
        turn_prompt = f"{prompt_text} (Turn {i+1})"

        # 2. Direct model timing (warmed model / connection check) reported separately
        t_direct_start = time.monotonic()
        try:
            resp = openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": turn_prompt}],
                max_tokens=60,
                temperature=0.7
            )
            direct_reply = resp.choices[0].message.content
        except Exception as e:
            print(f"  Direct model connection error: {e}")
            raise ConnectionError(f"Direct Ollama connection failed: {e}") from e
        t_direct_end = time.monotonic()
        direct_time = t_direct_end - t_direct_start
        direct_times.append(direct_time)

        # 3. Sora POST /api/chat send-to-history timing matching exact reply ID via GET /api/chat/history
        unique_text = f"{turn_prompt} [{time.time()}]"
        t_sora_start = time.monotonic()

        res = client.post(
            "/api/chat",
            json={"text": unique_text},
            headers=headers,
            environ_base=environ
        )
        if res.status_code != 200:
            print(f"  Turn {i+1} FAILURE: POST /api/chat returned status {res.status_code}: {res.get_data(as_text=True)}")
            successes.append(False)
            continue

        post_data = res.get_json() or {}
        user_msg_id = post_data.get("msg_id")
        if not user_msg_id:
            print(f"  Turn {i+1} FAILURE: Missing msg_id in response: {post_data}")
            successes.append(False)
            continue

        expected_reply_id = user_msg_id + "_reply"

        assistant_reply = ""
        timeout = 120.0
        poll_start = time.monotonic()
        success = False

        while time.monotonic() - poll_start < timeout:
            hist_res = client.get(
                "/api/chat/history?limit=50",
                headers=headers,
                environ_base=environ
            )
            if hist_res.status_code == 200:
                history = hist_res.get_json() or []
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

        lower_reply = assistant_reply.lower()
        is_fallback = (
            not success
            or not assistant_reply
            or lower_reply.startswith("error:")
            or "i haven't configured my models yet" in lower_reply
            or "i couldn't connect to the model service" in lower_reply
            or "i ran into a small issue" in lower_reply
            or "小问题" in assistant_reply
            or "我还没有配置好" in assistant_reply
        )

        if is_fallback:
            print(f"  Turn {i+1} FAILURE: Timeout, missing reply, or error fallback received: {assistant_reply}")
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
    print("=== Sora Local Chat Matched Benchmark (Phase 3.1A) ===")
    app_mod.app.config["TESTING"] = True
    client = app_mod.app.test_client()

    local_user = auth.get_or_create_local_single_device_user()
    auth_token = local_user["token"]

    prompt_text = "Benchmark test prompt under matched conditions."

    # Alternate mode order across pairs (Full then Fast, with independent state)
    res_full = run_benchmark_mode(client, auth_token, fast_mode=False, num_turns=2, prompt_text=prompt_text)
    time.sleep(2.0)
    res_fast = run_benchmark_mode(client, auth_token, fast_mode=True, num_turns=2, prompt_text=prompt_text)

    print("\n=== Benchmark Summary ===")
    print(f"Full Mode  : Median Direct={res_full.get('median_direct', 0):.2f}s, Median Sora Total={res_full.get('median_sora', 'TIMEOUT')}s, Success={res_full.get('success')}")
    print(f"Fast Mode  : Median Direct={res_fast.get('median_direct', 0):.2f}s, Median Sora Total={res_fast.get('median_sora', 'TIMEOUT')}s, Success={res_fast.get('success')}")

    _temp_dir.cleanup()

    if not res_full.get('success') or not res_fast.get('success'):
        print("ERROR: Benchmark failed in one or more modes.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
