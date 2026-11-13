import sys
import os
import tempfile
import time
import json
import statistics
import resource
import secrets
from datetime import datetime
from openai import OpenAI

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def _import_app_modules():
    import storage
    import core
    import user_settings
    import ai_config
    import auth
    import curator
    curator.start_loop_for_user = lambda uid, udir: None
    import app as app_mod
    return storage, core, user_settings, ai_config, auth, app_mod

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

    print(f"[Benchmark] Verified setting persistence local_text_chat_enabled={fast_mode}")

def create_fresh_disposable_user(auth) -> dict:
    """Create a fresh disposable local user with an isolated data directory."""
    with auth._lock:
        users = auth._load_json(auth._users_path())
        user_id = auth._new_user_id(users)
        token = secrets.token_urlsafe(32)
        created_at = datetime.now().isoformat()
        users[user_id] = {
            "token": token,
            "invitation_code": "",
            "full_invitation_code": "",
            "created_at": created_at,
            "status": "active",
            "account_type": getattr(auth, "LOCAL_SINGLE_DEVICE_ACCOUNT_TYPE", "local_single_device"),
        }
        user_dir = os.path.join(auth._BASE_DATA_DIR, "users", user_id)
        os.makedirs(user_dir, exist_ok=True)
        os.makedirs(os.path.join(user_dir, "uploads"), exist_ok=True)
        auth._write_account_manifest(user_id, users[user_id])
        auth._save_json(auth._users_path(), users)
    return {"token": token, "user_id": user_id, "is_new": True}

def run_benchmark_pair(client, prompt_text: str = "Benchmark test prompt under matched conditions.", order: str = "full_first"):
    """Run a matched pair of benchmark turns (one full mode, one fast mode) in specified order with fresh disposable user state."""
    storage, core, user_settings, ai_config, auth, app_mod = _import_app_modules()
    modes = [False, True] if order == "full_first" else [True, False]
    results = {}

    for fast_mode in modes:
        mode_label = "Fast Mode" if fast_mode else "Full Mode"
        print(f"\n--- Running Benchmark Turn ({mode_label}, Order: {order}) ---")

        # 1. Start each measured turn with fresh disposable user state
        local_user = create_fresh_disposable_user(auth)
        auth_token = local_user["token"]
        headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        environ = {"REMOTE_ADDR": "127.0.0.1"}

        # 2. Verify isolation through the authenticated history route before each turn (must be empty)
        hist_check = client.get("/api/chat/history?limit=10", headers=headers, environ_base=environ)
        if hist_check.status_code != 200:
            raise RuntimeError(f"Failed to verify history isolation: {hist_check.status_code}")
        history_data = hist_check.get_json() or []
        if history_data:
            raise AssertionError(f"History isolation failure: expected empty history, got {len(history_data)} items")

        verify_and_set_user_setting(client, auth_token, fast_mode)

        base_url = "http://127.0.0.1:11434/v1"
        model = "qwen2.5:1.5b-instruct"
        openai_client = OpenAI(base_url=base_url, api_key="ollama")

        # 3. Direct model timing (warmed model / connection check) reported separately
        t_direct_start = time.monotonic()
        try:
            print("  Direct model calling Ollama...")
            resp = openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt_text}],
                max_tokens=60,
                temperature=0.7
            )
            print("  Direct model call complete.")
            direct_reply = resp.choices[0].message.content
        except Exception as e:
            print(f"  Direct model connection error: {e}")
            raise ConnectionError(f"Direct Ollama connection failed: {e}") from e
        t_direct_end = time.monotonic()
        direct_time = t_direct_end - t_direct_start

        # 4. Sora POST /api/chat send-to-history timing matching exact reply ID via GET /api/chat/history
        core._last_resolved_chat_policy = None
        t_sora_start = time.monotonic()

        res = client.post(
            "/api/chat",
            json={"text": prompt_text},
            headers=headers,
            environ_base=environ
        )
        if res.status_code != 200:
            print(f"  FAILURE: POST /api/chat returned status {res.status_code}: {res.get_data(as_text=True)}")
            results[fast_mode] = {"success": False, "error": f"HTTP {res.status_code}"}
            continue

        post_data = res.get_json() or {}
        user_msg_id = post_data.get("msg_id")
        if not user_msg_id:
            print(f"  FAILURE: Missing msg_id in response: {post_data}")
            results[fast_mode] = {"success": False, "error": "Missing msg_id"}
            continue

        expected_reply_id = user_msg_id + "_reply"

        assistant_reply = ""
        timeout = 600.0
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

        # 5. Verify actual policy and exact saved reply for every turn
        observed_policy = getattr(core, "_last_resolved_chat_policy", None) or {}
        expected_mode = "reactive_fast" if fast_mode else "v4_pro"
        observed_mode = observed_policy.get("mode")

        # 5. Verify actual policy and exact saved reply for every turn

        if observed_mode != expected_mode:
            print(f"  FAILURE: Policy mismatch inside worker: expected {expected_mode}, got {observed_mode}")
            results[fast_mode] = {"success": False, "error": f"Policy mismatch: expected {expected_mode}, got {observed_mode}"}
            continue

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
            print(f"  FAILURE: Timeout, missing reply, or error fallback received: {assistant_reply}")
            results[fast_mode] = {"success": False, "error": f"Fallback/missing reply: {assistant_reply}"}
        else:
            print(f"  Success | Direct: {direct_time:.2f}s | Sora Send-to-History: {sora_total_time:.2f}s | Policy: {observed_mode} | Reply: {assistant_reply[:60]}...")
            results[fast_mode] = {
                "success": True,
                "direct_time": direct_time,
                "sora_time": sora_total_time,
                "policy_mode": observed_mode,
                "reply": assistant_reply
            }

        time.sleep(1.0)

    return results

def run_benchmark():
    storage, core, user_settings, ai_config, auth, app_mod = _import_app_modules()
    print("=== Sora Local Chat Matched Benchmark (Phase 3.3B) ===")
    app_mod.app.config["TESTING"] = True
    client = app_mod.app.test_client()

    prompt_text = "Benchmark test prompt under matched conditions."

    # Run at least two pairs with alternating orders (Pair 1: full_first, Pair 2: fast_first)
    print("\n--- Pair 1 (full_first) ---")
    pair1 = run_benchmark_pair(client, prompt_text=prompt_text, order="full_first")

    print("\n--- Pair 2 (fast_first) ---")
    pair2 = run_benchmark_pair(client, prompt_text=prompt_text, order="fast_first")

    print("\n=== Benchmark Summary ===")
    all_success = all(p.get("success", False) for p in list(pair1.values()) + list(pair2.values()))
    print(f"Overall Success: {all_success}")

    all_turns = list(pair1.items()) + list(pair2.items())
    direct_full = [p["direct_time"] for mode, p in all_turns if not mode and p.get("success") and "direct_time" in p]
    sora_full = [p["sora_time"] for mode, p in all_turns if not mode and p.get("success") and "sora_time" in p]
    direct_fast = [p["direct_time"] for mode, p in all_turns if mode and p.get("success") and "direct_time" in p]
    sora_fast = [p["sora_time"] for mode, p in all_turns if mode and p.get("success") and "sora_time" in p]

    if direct_full:
        print(f"Full Mode Direct Latency — Individual: {[f'{t:.2f}s' for t in direct_full]} | Median: {statistics.median(direct_full):.2f}s")
    if sora_full:
        print(f"Full Mode Sora Latency — Individual: {[f'{t:.2f}s' for t in sora_full]} | Median: {statistics.median(sora_full):.2f}s")
    if direct_fast:
        print(f"Fast Mode Direct Latency — Individual: {[f'{t:.2f}s' for t in direct_fast]} | Median: {statistics.median(direct_fast):.2f}s")
    if sora_fast:
        print(f"Fast Mode Sora Latency — Individual: {[f'{t:.2f}s' for t in sora_fast]} | Median: {statistics.median(sora_fast):.2f}s")

    return {
        "pair1": pair1,
        "pair2": pair2,
        "success": all_success
    }

def main():
    _temp_dir = tempfile.TemporaryDirectory()
    data_dir = _temp_dir.name
    os.environ["DATA_DIR"] = data_dir
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

    try:
        storage, core, user_settings, ai_config, auth, app_mod = _import_app_modules()
        storage.DATA_DIR = data_dir
        import importlib
        importlib.reload(storage)
        storage.DATA_DIR = data_dir
        auth._BASE_DATA_DIR = data_dir
        auth._ADMIN_DIR = admin_dir

        ai_config.invalidate_cache()
        storage._ensure_dirs()

        res = run_benchmark()
        if not res.get("success"):
            print("ERROR: Benchmark failed in one or more pairs.", file=sys.stderr)
            _temp_dir.cleanup()
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Benchmark execution error: {e}", file=sys.stderr)
        _temp_dir.cleanup()
        sys.exit(1)
    finally:
        try:
            _temp_dir.cleanup()
        except Exception:
            pass

if __name__ == "__main__":
    main()
