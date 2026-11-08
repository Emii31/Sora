import sys
import os
import subprocess

def get_git_bytes(revision, file_path):
    try:
        # Use git show to retrieve file bytes at revision
        cmd = ["git", "show", f"{revision}:{file_path}"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to get {file_path} at revision {revision}: {e.stderr.decode().strip()}", file=sys.stderr)
        return None

def check_history(base_revision, file_paths):
    all_passed = True
    for file_path in file_paths:
        original_bytes = get_git_bytes(base_revision, file_path)
        if original_bytes is None:
            all_passed = False
            continue

        if not os.path.exists(file_path):
            print(f"ERROR: Current file does not exist: {file_path}", file=sys.stderr)
            all_passed = False
            continue

        with open(file_path, 'rb') as f:
            current_bytes = f.read()

        if not current_bytes.startswith(original_bytes):
            print(f"FAILED: {file_path} does not begin with exact bytes from {base_revision}")
            all_passed = False
        else:
            print(f"PASSED: {file_path} correctly preserves history from {base_revision}")

    return all_passed

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python check_history_append_only.py <base_revision>", file=sys.stderr)
        sys.exit(1)

    base_revision = sys.argv[1]
    files_to_check = ["docs/SESSION_LOG.md", "docs/VERIFICATION.md"]

    if not check_history(base_revision, files_to_check):
        sys.exit(1)
