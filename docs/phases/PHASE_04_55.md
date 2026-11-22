# Phase 4.55 — Owner-approved Motorola voice audition

The Motorola Moto G Stylus 5G (2024) generated and played reassurance, excitement, and teasing lines locally using Sopro V2 Turbo and LiteRT. The owner listened on the phone and described the delivery as “perfect.” Keep this as the phone quality baseline. The previously approved 42.5-second Liquid reel remains the original reference and its SHA-256 is unchanged.

## Phone result

| Line | Time to first PCM submission | Generated audio | Reference cache |
| --- | ---: | ---: | --- |
| Reassurance | 15.76 s | 3.74 s | Cold |
| Excitement | 13.16 s | 3.32 s | Warm |
| Teasing | 12.11 s | 3.53 s | Warm |

Android logged a completed playback for each line. Model setup reached ready after 3.26 s, outside the speech timing. The measured latency ends at first PCM delivery to the player and excludes hardware playback latency, chat generation and recognition. Offline Whisper matched all three lines word for word. This verifies synthesis from fixed text and playback with the owner's approval of delivery. Response speed for live conversation is open.

On both warm turns, autoregressive generation took about 5.5–6.4 s, followed by roughly 6.2 s for acoustic conditioning and the two solver steps. Test phone acceleration with the same text, seeds, reference, and owner listening comparison before changing the accepted build.

## Build and verification

- Downloaded the public Sopro Android sample at Hugging Face revision `a92f0dda86b17e3976756743af3a60fa81f7acc2`. The sparse fetch failed. The fallback fetched all 106 files directly by the pinned revision.
- Validated 20 model assets totaling 447,323,510 bytes with the upstream SHA-256 manifest, then verified each checksum in private storage on the phone.
- Created the debug-only `com.sopro.soraaudition` APK in recovery. Used an installed Android Build Tools version, gave the scratch app its own display name and package ID, verified that the merged APK requests neither microphone nor internet permission, and added a three-line test trigger. The fixed 10-second model input uses the 0.2–9.6 s excerpt from the prior Liquid reassurance take, padded to 10 seconds without altering the saved original.
- Used Gradle 8.11.1 with `:app:assembleDebug --no-daemon --max-workers=2` in the scratch sample. The first build rejected a backup file in the resource directory. The retry after moving backups exited 0. The first private copy using `adb exec-in` failed to create the destination. Retried through `adb shell -T` and verified all 20 destinations.
- Ran `python3 -B -u install-audition.py android-source/android/app/build/outputs/apk/debug/app-debug.apk`. Exit 0. Ran the app via `adb -d shell am start -W -n com.sopro.soraaudition/com.sopro.MainActivity --ez sora_audition true --es measurement_tag sora_moto_cpu` with the built APK hash. Collected all three WAVs and their JSON sidecars with `collect-audition.py motorola-cpu`, exit 0. Independent local recognition via `recognize-phone.py motorola-cpu` exited 0.
- The **Sora Voice Audition** app and offline weights are installed on the Motorola. The audition APK, patched sample source, model manifest, original generated WAVs, joined reel, measurements, and test scripts are recorded in `/mnt/data/Companion/recovery/phase_04_55` and `docs/verification/phase_04_55/motorola-audition.json`. No production Sora runtime code was changed.

[Sopro Android LiteRT sample and model files](https://huggingface.co/litert-community/sopro-v2-turbo/tree/a92f0dda86b17e3976756743af3a60fa81f7acc2)
