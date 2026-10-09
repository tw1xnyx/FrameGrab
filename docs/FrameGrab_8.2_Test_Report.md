# FrameGrab 8.2 test results

Executed locally on Windows with the bundled FFmpeg, FFprobe, yt-dlp and Deno, and NVIDIA GTX 1660 SUPER (driver 617.14).

| Verification | Result |
|---|---|
| Existing original v8 and v8.1 installation copies upgraded and restarted | Passed; final file hashes match the signed manifest; bundled backend reached ready |
| Replacement failure rollback and abrupt interruption recovery | Passed; all baseline file hashes restored |
| Unknown installed application changes | Rejected before replacing files |
| Settings, previous history, download directory, custom preferences and update configuration during patching | Byte-identical |
| Suitable H.264/AAC CFR MP4 retained | Passed; exact original compressed file bytes retained with output naming |
| MKV lossless video remux | Passed; extracted H.264 streams byte-identical |
| VP9, AV1, VFR, PCM 44.1 kHz, 10-bit video, misleading extension | Converted; probed and fully decoded |
| Corrupt/truncated media and missing expected audio | Rejected; original preserved |
| WebP still image | Converted and decoded as PNG |
| 23.976, 25, 29.97, 30, 59.94 and 60 fps | Preserved as CFR |
| 1080p30, 1080p60, 1440p59.94 and 4K30 | Actual NVENC conversions passed dimension, frame-timing, duration, A/V consistency, GOP and full-decode checks |
| CPU-only path and injected GPU encoder failure | Actual x264 fallback passed |
| HDR/BT.2020 PQ | Explicit tone mapping to SDR BT.709 passed output checks |
| Duplicate frame timestamps and positive source timestamp offset | Repaired and verified |
| Separate downloaded video/audio stream fixture | Merged and processed successfully |
| Optional ProRes Proxy | Produced alongside MP4, probed and fully decoded |
| Existing-output collision | Existing file preserved; numbered new output |
| Remembered mode and unknown legacy setting | Passed authenticated API persistence checks |
| Failed conversion retry | Reused retained source without requesting download metadata/network again |
| Modified retained source | Retry rejected by SHA256 check |
| Selected section, full download, MP3, local API authentication, invalid range, missing output | Six Windows integration tests passed |
| Signed update feed/tampering/expiry/HTTPS/version checks and user-controlled download | Seven desktop tests passed |

The automated suites passed: 11 compatibility cases; 10 optimization test methods (including seven resolution/frame-rate subcases); six downloader integration tests; three additional mode/retry API tests; seven desktop tests; updater failure/recovery and successful application checks. Duplicate-timestamp and image-quality checks ran separately. Final cosmetic encoder-label cleanup did not change media processing behavior.

Real public YouTube verification used Blender Foundation's Big Buck Bunny, https://www.youtube.com/watch?v=aqz-KE-bpKQ, six-second excerpts. H.264 299 + AAC 140 and VP9 + Opus streams were actually downloaded/merged, processed using NVENC, and fully decoded. Both final outputs are 1080p60 H.264/AAC 48 kHz MP4 with two-second GOPs and durations approximately 6.04 seconds. No login or private browser cookies were used.

An actual 1080p synthetic reference transcode measured SSIM 0.998916 after aligning timestamps. This is a limited technical quality check, not a visual assessment of all possible videos.

Limitations: Premiere Pro testing was stopped at your request; no v8.2 import/timeline performance result is claimed. The native FrameGrab interface was not visually rechecked after Computer Use was stopped. High-resolution effects-heavy timelines may still benefit from the optional proxy. Damaged/incomplete inputs that cannot safely be repaired require downloading again. No live hosted update feed or Authenticode signing certificate is configured. Online availability and site changes can affect individual downloads.

Implementation references: NVIDIA FFmpeg/NVENC guide https://docs.nvidia.com/video-technologies/video-codec-sdk/13.1/ffmpeg-with-nvidia-gpu/index.html and FFprobe documentation https://ffmpeg.org/ffprobe.html .
