"""Create the tested live profile for a Scylla's Band v2 LiteRT bundle."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Manifest from the original LiteRT bundle")
    parser.add_argument("destination", type=Path, help="New manifest, alongside the same speech assets")
    args = parser.parse_args()

    manifest = json.loads(args.source.read_text(encoding="utf-8"))
    controls = manifest.get("controls", {})
    buckets = controls.get("target_buckets", {}).get("buckets", [])
    if (
        manifest.get("architecture") != "scyllasband-duration-flow"
        or manifest.get("model_version") != "2"
        or not any(voice.get("id") == "gwen" for voice in manifest.get("voices", []))
        or not any(bucket.get("latent_frames") == 256 for bucket in buckets)
    ):
        parser.error("expected a Scylla's Band v2 bundle with Gwen and a 256-frame bucket")

    controls.setdefault("chunking", {})["max_target_frames"] = 256
    with args.destination.open("x", encoding="utf-8") as output:
        json.dump(manifest, output, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
