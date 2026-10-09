# FrameGrab 8.2 changes

- Adds a remembered Standard Download / Premiere Pro Optimized (MP4) selector while preserving the existing interface and features.
- Uses real NVENC capability testing, high-quality H.264 hardware encoding, and automatic x264 fallback.
- Detects actual frame timing, normalizes VFR/irregular timestamps, preserves intended fractional/integer frame rates, and limits keyframe intervals to about two seconds.
- Produces H.264 High, 8-bit YUV 4:2:0 MP4, AAC-LC 48 kHz when conversion is needed. Retains suitable original streams or remuxes without video re-encoding when safe.
- Handles supported HDR through explicit BT.709 tone mapping; rejects ambiguous HDR color metadata instead of silently relabeling it.
- Adds per-stage progress, conversion speed and GPU/CPU status; operations without measured progress show an indeterminate status.
- Saves collision-safe _Premiere.mp4 files after stream/timestamp/duration/aspect/full-decode validation.
- Adds retained-source Retry Conversion and optional separate ProRes editing proxies.
- Preserves the incremental updater, backups, interrupted-update recovery and rollback.
