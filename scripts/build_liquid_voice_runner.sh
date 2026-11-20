#!/usr/bin/env bash
# Private Sora runner extension; never publishes to the dependency's upstream.
set -euo pipefail
if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /path/to/sora-liquid-audition" >&2
  exit 2
fi
kit="$(cd "$1" && pwd)"
project="$(cd "$(dirname "$0")/.." && pwd)"
source_dir="$kit/android/source"
expected=ec9d1fdd9cc18643c5e161b65b8053f6f6f34a4b
if [ "$(git -C "$source_dir" rev-parse HEAD)" != "$expected" ]; then
  echo "Use the documented pinned Liquid runner source: $expected" >&2
  exit 1
fi
patch="$project/patches/liquid-forced-speech.patch"
if git -C "$source_dir" apply --check "$patch" 2>/dev/null; then
  git -C "$source_dir" apply "$patch"
elif ! git -C "$source_dir" apply --reverse --check "$patch" 2>/dev/null; then
  echo "Runner changes conflict with the Sora patch; preserve and review them before building." >&2
  exit 1
fi
bash "$kit/android/build-android.sh"
