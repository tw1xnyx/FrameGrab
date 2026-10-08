# FrameGrab v8 — Native Windows Desktop Source

This is a **Windows desktop application source package**, not an already-built EXE.
The requested NSIS installer and signed update artifacts require a Windows build/release
runner; they could not be compiled or tested from the Linux environment used here.

## Windows architecture

- **Electron** creates a real native Windows application window with the native window controls, shortcuts, taskbar integration, DPI handling, and Chromium optics/WebGL.
- **Python 3.12 embeddable + yt-dlp, FFmpeg, FFprobe and Deno** are included in the installer when compiled with the provided Windows build script. No Python/Node setup or console windows are required for end users after installation.
- The internal Python media engine binds a random **127.0.0.1** port and is started, authenticated, monitored, and terminated by the Electron executable. **No external browser or localhost URL** is presented to the user. The media service is an application implementation detail, not a separate website the user must launch.
- The user-facing app handles source analysis, multi-link queue, full-video or drag-handle section selection, supported formats, progress, retry and cancel, output verification, and history.
- Application state/history/logs live under `%APPDATA%\FrameGrab`, not the installation folder. The default download directory is `%USERPROFILE%\Downloads`; users can choose another directory from the GUI.

## Windows build (developer/release operator only)

Use a Windows 10/11 x64 computer or GitHub Actions `windows-latest`, with Node.js 22 LTS and internet access. In **Windows PowerShell**:

```powershell
cd path\to\FrameGrab_v8_Desktop_Source
.\scripts\Build-Windows.ps1
```

The build script downloads portable dependencies **once during packaging**, records their SHA-256 hashes, installs the pinned Electron packaging dependencies and runs NSIS.
Expected outputs (after a successful Windows build):

- `dist\FrameGrab_Setup_8.0.0.exe` — main graphical NSIS installer
- `dist\FrameGrab_Update_8.0.0.exe` — separately named compatible NSIS update installer (same full payload, not a differential patch)
- `dist\latest.yml` and matching `.blockmap` — Electron updater release metadata, where generated

An alternative `.github/workflows/windows-release.yml` can build the installer in a GitHub Windows runner and upload the resulting binaries as a CI artifact. These binaries **are not included in this source ZIP**.

**Important:** public distribution should be Authenticode-signed; otherwise Windows SmartScreen may warn. Inspect and verify all portable upstream dependencies and their licenses before distribution. The build command is intended for a release engineer, never an ordinary end user.

## End-user behavior after installation

Open FrameGrab using its Start menu/Desktop shortcut. No `.bat`, PowerShell or CMD launcher is used. The hidden engine and all bundled tools are started by the application. The main window has working Downloads, History, Queue and Settings sections. Output is not marked complete until FFprobe verifies the final media container and at least the required audio/video stream.

## Updates — ready for a hosted feed, not yet deployed

- App installer identity: `com.framegrab.desktop`, stable across versions.
- Update manager uses **electron-updater** (NSIS provider) and checks a configurable HTTPS generic release feed. It reports available version, release notes and progress and can restart into the verified downloaded installer.
- Set the production feed in Settings, then publish build outputs `latest.yml`, `.exe`, `.blockmap` in that HTTPS directory. The hardcoded `updates.example.invalid` build metadata is explicitly a **placeholder**, NOT a real live update server.
- For a local, controlled Windows test, start `npm run test:update-host`, and launch the installed app with `FRAMEGRAB_ALLOW_LOCAL_UPDATE_TEST=1`; you can then select `http://127.0.0.1:8990` as your test release feed.
- Future releases increment `package.json` semver, retain `appId`, rebuild the installer, and update the same installation using electron-updater or the separately named NSIS installer. User data stays in `%APPDATA%\FrameGrab` and is configured not to be deleted by uninstall.
- No code signing credentials, production hosting or successful installed Windows update run are present in this delivery. Do not treat the updater as deployed until these requirements are met and Windows lifecycle testing passes.

## Tests in this source package

```powershell
python -m unittest discover -s tests -v
npm run test:source
```

The Python integration tests use local FFmpeg-generated media plus a mock yt-dlp process to simulate post-processing and changed filenames. They do **not** establish reliable downloads from live YouTube, Instagram, or TikTok, nor do they prove runtime behavior on Windows.

## Selected section

Choose `Selected section`, Analyze the media, select Start and End from the interactive timeline, or enter HH:MM:SS timestamps. Fast cut favors speed (subject to keyframe alignment), while Accurate cut invokes yt-dlp's FFmpeg re-encoding around cut points. Some sources do not support partial range extraction; in that case the app reports the actual extractor error.

## Diagnostics and privacy

- Windows process calls use `windowsHide`; the desktop service uses `pythonw.exe`, and yt-dlp/FFmpeg use `CREATE_NO_WINDOW`.
- Each item has a `Copy Error` action. A native error dialog lets the user copy a sanitized report and open logs.
- Diagnostics check bundled versions, destination permissions, and free disk space.
- The engine is limited to loopback; an app-session token is required for HTTP API calls. The Electron window rejects external navigation and links open externally.
- Optional browser cookies are OFF by default, are used only if the user explicitly selects a browser, and are not uploaded to a cloud backend.

## Remaining limitations

- This **does not contain a Windows EXE installer**: compiling Electron/NSIS requires Windows dependencies and a Windows testing run unavailable in the execution environment.
- No Windows install/uninstall/shortcut/autoupdate life-cycle test was run here.
- The optical glass layer is an SVG displacement-enhanced live backdrop in supporting Chromium implementations, backed by an animated WebGL2 shader. It is **not** the native Apple compositor; support and visual fidelity vary by GPU/driver.
- Pause/resume of active network transfers is not implemented as a reliable native operation. Cancel and retry are functional backend operations in the local tests.
- A generic HTTPS update server is not provisioned, so Check for Updates explains that configuration is needed instead of displaying a fake success.
- Old portable v7 settings/history from a completely different extracted folder are not discovered automatically; migrating those files requires copying them into the new user-data folder.

Only download media that you own or are authorized to access. No DRM, paywall, or protected-video bypass is included.
