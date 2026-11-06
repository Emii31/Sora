import os
import sys
import tempfile
import shutil
from pathlib import Path

# Resolve project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

def run_smoke_test():
    # Setup disposable data directory
    tmp_dir = tempfile.mkdtemp(prefix="sora_smoke_test_")
    print(f"[Smoke] Created disposable DATA_DIR: {tmp_dir}")

    try:
        # Set configuration before imports
        os.environ["DATA_DIR"] = tmp_dir
        os.environ["FLASK_ENV"] = "development"
        # Isolate provider config: set empty values to prevent inheritance
        for var in ["AI_VISION_HOST", "AI_VISION_KEY", "AI_CHAT_HOST", "AI_CHAT_KEY", "AI_MEMORY_HOST", "AI_MEMORY_KEY"]:
            os.environ[var] = ""

        import app

        # Enforce loopback-only binding
        print("[Smoke] Starting Flask server on http://127.0.0.1:5000 (Loopback only)")

        # Run server in the foreground to propagate errors immediately
        # Use simple run() without threading
        app.app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

    except KeyboardInterrupt:
        print("\n[Smoke] Stopping server...")
    except Exception as e:
        print(f"\n[Smoke] Server failed: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
            print(f"[Smoke] Cleaned up: {tmp_dir}")

if __name__ == "__main__":
    run_smoke_test()
