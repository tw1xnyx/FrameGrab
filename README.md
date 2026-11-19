# FrameGrab v8 — Free Windows Video Downloader

FrameGrab is a free, open-source Windows desktop application built for content creators, video editors, and anyone who needs a simple way to download and prepare video footage.

Powered by yt-dlp and FFmpeg, FrameGrab supports video downloads at resolutions up to 4K when available from the original source, with built-in tools for extracting specific sections of videos.

Instead of downloading an entire 30-minute video just to use a 20-second clip, you can select the exact section you need and download only that footage when supported by the source.

## Features

- Up to 4K Video Downloads: Download videos at the highest available quality supported by the source.
- High-Speed Downloads: Efficient downloading powered by yt-dlp, with speeds depending on the source and internet connection.
- Selected Section Downloads: Choose specific start and end timestamps to extract the footage you need instead of downloading the entire video.
- Accurate Trimming: Choose between fast cuts and accurate FFmpeg-based extraction.
- Video Editor Compatibility: Prepare downloaded footage for use in Adobe Premiere Pro and other compatible video editing applications.
- Multiple Downloads: Manage multiple video links through a single download queue.
- Progress Tracking: Monitor download progress and check the status of each task.
- Retry and Cancel: Retry failed downloads or cancel active tasks.
- Download History: Keep track of previous downloads and completed files.
- Output Verification: Verify the final media file before marking a download as complete.
- Native Windows Interface: Use a dedicated desktop application without manually running command-line tools.

## Built for Video Editors

FrameGrab is designed to make the video editing workflow easier.

Whether you are creating YouTube videos, documentaries, social media content, tutorials, or other projects, you can use FrameGrab to collect the footage you need without unnecessarily downloading entire videos.

Select the source, analyze the media, choose your start and end points, and download the required section.

Your downloaded footage can then be imported into Adobe Premiere Pro or another compatible video editor.

Download less. Edit faster.

## Windows Architecture

FrameGrab is built using Electron and a Python-based internal media engine.

- Electron provides the Windows desktop application, including native window controls, shortcuts, taskbar integration, DPI handling, and Chromium-based rendering.
- Python 3.12 embeddable provides the internal media engine.
- yt-dlp handles supported media extraction and downloading.
- FFmpeg and FFprobe handle media processing, trimming, and output verification.
- Deno is included as a supporting runtime for compatible yt-dlp extraction workflows.

The media engine runs internally and communicates with the desktop application through a randomly assigned 127.0.0.1 port.

The application starts, authenticates, monitors, and terminates the internal service automatically.

Users do not need to open a browser, enter a localhost address, or manually start a separate server.

Application state, download history, and logs are stored under:

%APPDATA%\FrameGrab

The default download directory is:

%USERPROFILE%\Downloads

Users can choose another destination from the application settings.

## Installation

FrameGrab is intended to be distributed as a Windows desktop installer.

The current source package does not include a prebuilt Windows EXE installer.

A Windows installer must first be generated using the provided Windows build script or GitHub Actions workflow.

Once a compatible installer has been built and distributed:

1. Download the FrameGrab Windows installer.
2. Run the installer.
3. Choose your preferred installation directory.
4. Complete the installation.
5. Open FrameGrab using its Start Menu or Desktop shortcut.

End users do not need to install Python or Node.js separately.

No BAT, PowerShell, or CMD launcher is required to start the installed application.

## Building FrameGrab on Windows

This section is intended for developers and release maintainers, not ordinary users.

### Requirements

- Windows 10 or Windows 11 x64
- Node.js 22 LTS
- npm
- Internet connection
- Windows PowerShell 5.1 or later

### Build Instructions

Open Windows PowerShell and navigate to the project directory.

```powershell
cd path\to\FrameGrab
```

Run the Windows build script:

```powershell
.\scripts\Build-Windows.ps1
```

The build script prepares the required portable dependencies, including:

- Python embeddable runtime
- yt-dlp
- FFmpeg
- FFprobe
- Deno

It also generates SHA-256 hashes for the downloaded executable dependencies, installs the required Node.js packages using the package lockfile, and runs the Electron Windows packaging process.

Dependencies are downloaded during packaging rather than installed separately on end-user computers.

### Build Outputs

After a successful Windows build, the dist directory should contain:

- FrameGrab_Setup_8.3.0.exe — Main Windows installer.
- FrameGrab_Update_8.3.0.exe — Separately named installer for updating existing installations. This contains the same full application payload and is not a differential update patch.
- latest.yml — Release metadata for supported in-app updates, when generated.
- Corresponding .blockmap files, when generated.

The filenames use the application version configured in package.json. Future versions will automatically use their updated version numbers.

The build also generates a build-dependency-hashes.json file containing SHA-256 hashes and file sizes for the downloaded runtime dependencies.

### Alternative Build Using GitHub Actions

The project also includes a GitHub Actions workflow:

.github/workflows/windows-release.yml

The workflow can be triggered manually using workflow_dispatch.

It is configured to use a Windows runner and perform the following steps:

1. Check out the repository.
2. Set up Node.js and Python.
3. Run desktop source tests.
4. Build the Windows installer.
5. Run real media pipeline tests.
6. Install and launch the packaged application.
7. Generate SHA-256 checksums.
8. Upload the resulting build artifacts.

The workflow uploads build artifacts to GitHub Actions. Publishing an actual GitHub Release remains a separate release step.

## Automatic Updates

FrameGrab includes an update manager powered by electron-updater.

The application uses a stable application identifier:

com.framegrab.desktop

This identifier should remain unchanged across future versions to preserve the existing installation identity.

### Default Update Source

The application is configured to use GitHub Releases from:

https://github.com/tw1xnyx/FrameGrab-Updates

The repository is intended to host the published Windows update releases.

The update manager supports:

- Checking for available versions.
- Displaying the available version number.
- Showing release notes.
- Downloading update packages.
- Reporting download progress.
- Installing a downloaded update.
- Restarting the application after installation.

A generic HTTPS update feed can also be configured through the application settings.

### Update Release Requirements

Before the automatic update system can be considered production-ready:

- Build the Windows installer.
- Publish compatible release artifacts.
- Provide the required update metadata.
- Verify the download and installation process.
- Test the update process using an installed Windows application.

The GitHub update repository and production release hosting must be maintained separately from the main application source.

No production code-signing credentials or completed installed Windows update lifecycle test are included with this source package.

Public Windows releases should be Authenticode-signed where possible to reduce Windows SmartScreen warnings.

## Testing

The project includes Python integration tests and JavaScript desktop application tests.

### Python Tests

Run:

```powershell
python -m unittest discover -s tests -v
```

### Desktop Source Tests

Run:

```powershell
npm run test:source
```

The Python integration tests use locally generated FFmpeg media and a mock yt-dlp process to simulate media post-processing and changed output filenames.

These tests do not establish reliable live downloading from YouTube, Instagram, or TikTok.

They also do not independently establish that the application works correctly on every Windows configuration.

The GitHub Actions workflow includes additional Windows media pipeline and installer verification steps.

## Selected Section Downloads

One of FrameGrab's main features is the ability to extract a specific part of a video.

Instead of processing an entire video, users can choose the exact section they need.

### How It Works

1. Add a supported video URL.
2. Select Selected Section.
3. Analyze the media.
4. Choose the desired start and end points using the interactive timeline or enter timestamps manually.
5. Select the extraction method.
6. Start the download.

Timestamps use the HH:MM:SS format.

### Fast Cut

Fast Cut prioritizes speed and works subject to keyframe alignment.

The resulting start and end points may vary slightly depending on the original media.

### Accurate Cut

Accurate Cut uses yt-dlp and FFmpeg-based re-encoding around the requested cut points for more precise extraction.

Some sources do not support partial section extraction. When this happens, FrameGrab reports the actual extraction error instead of reporting a false successful download.

## Diagnostics and Privacy

FrameGrab includes built-in diagnostic and error-reporting features.

- Windows processes are launched with hidden console windows.
- The internal desktop service uses pythonw.exe.
- yt-dlp and FFmpeg processes use CREATE_NO_WINDOW.
- Each download item includes a Copy Error action.
- Native error dialogs allow users to copy sanitized diagnostic information.
- Application logs are stored in the user's application data directory.
- Diagnostics check bundled tool versions, destination permissions, and available disk space.

### Local Service Security

The internal media engine listens only on the local loopback interface.

An application-session authentication token is required for its HTTP API calls.

The Electron window prevents untrusted external navigation and opens external links through the system browser.

The application does not require a cloud backend to process local download tasks.

### Browser Cookies

Optional browser cookies are disabled by default.

Users must explicitly select a browser if they want to use browser cookies for supported sources.

Selected cookies are used locally and are not uploaded to a cloud backend by FrameGrab.

## Known Limitations

FrameGrab is still under development, and some features require additional testing and release preparation.

- The source package does not currently contain a prebuilt Windows EXE installer.
- No completed Windows installation, uninstallation, shortcut, or automatic update lifecycle test is included in this delivery.
- Public Windows distribution requires appropriate code signing to avoid some Windows security warnings.
- Automatic updates require compatible published release artifacts.
- Pause and resume of active network transfers are not implemented as reliable native operations.
- Cancel and retry are implemented backend operations covered by local tests.
- Live download reliability depends on the supported source, extractor behavior, and platform changes.
- Accurate section extraction may not be available for every source.
- The optical glass interface uses SVG displacement effects and animated WebGL2 rendering. It is not the native Apple compositor, and visual results may vary depending on the GPU and graphics drivers.
- Previous portable v7 settings and history from a different extracted folder are not automatically discovered. Manual migration may be required.

The application should not be considered fully production-tested until the Windows installer, download workflows, and update lifecycle have been successfully verified.

## Third-Party Software and Licenses

FrameGrab uses third-party software and dependencies, including:

- Electron
- Python
- yt-dlp
- FFmpeg
- Deno

These components are distributed under their respective licenses.

The MIT License included with FrameGrab applies to the original project code and does not replace or override the licenses of third-party dependencies.

Developers and release maintainers should inspect the licenses of all bundled dependencies and include the required copyright notices and license documentation before redistributing the application.

## Contributing

Contributions, bug reports, suggestions, and improvements are welcome.

Before submitting changes:

1. Check the existing issues and discussions.
2. Explain the problem or proposed improvement.
3. Test your changes where possible.
4. Provide clear reproduction steps for reported bugs.
5. Submit a pull request with a description of your changes.

Contributions should focus on improving application reliability, compatibility, security, usability, and media-processing workflows.

## License

FrameGrab is distributed under the MIT License.

You are free to use, copy, modify, distribute, and redistribute the original MIT-licensed project code, subject to the conditions in the LICENSE file.

The license does not remove the separate licensing requirements of bundled third-party software.

See the LICENSE file for the complete terms.

## Responsible Use

FrameGrab is a media downloading and processing tool.

Only download media that you own, have permission to access, or are otherwise legally authorized to download.

Respect copyright, platform terms of service, and the rights of content creators.

FrameGrab does not include DRM, paywall, or protected-video bypass functionality.

## Project Information

Project Name: FrameGrab

Current Version: 8.3.0

Platform: Windows 10 / Windows 11 x64

Application Framework: Electron

Media Processing: Python, yt-dlp, FFmpeg and FFprobe

Additional Runtime: Deno

License: MIT

Source Repository:
https://github.com/tw1xnyx/FrameGrab

Update Repository:
https://github.com/tw1xnyx/FrameGrab-Updates

Made for video editors and creators who want a simpler way to find, download, and prepare the footage they need.
