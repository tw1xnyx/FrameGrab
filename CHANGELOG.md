# FrameGrab 8.0.0 (desktop source)

- Added Electron desktop shell and hidden internally managed Python downloader process; no external browser/windowed console needed after compiled installation.
- Added native folder chooser and Windows application update manager with configurable generic HTTPS feed.
- Added standalone NSIS installer/update artifact build source, Win x64 build automation and GitHub Actions workflow.
- Migrated state and logs to per-user app-data directory with rotating error logs.
- Added copyable detailed errors and diagnostics with credential masking.
- Retained the v7 selected-range editor, YouTube metadata analysis and local FFmpeg/yt-dlp verification pipeline.
- Added Windows theme-following preference, history clear without deleting media, Open File and Copy Path controls.
- Added token authentication to the internally managed loopback API.
- Preserved existing WebGL2 animated backdrop / Chromium SVG-displacement optical controls.
