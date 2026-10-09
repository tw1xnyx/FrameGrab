# FrameGrab 8.2 incremental update

1. Run FrameGrab_Update.exe. It detects the existing FrameGrab installation, closes it, backs up the affected files, applies the patch and restarts FrameGrab.
2. Choose New Download, then Premiere Pro Optimized (MP4), paste your link and download. The selected mode is remembered.
3. Optional: enable Also create an editing proxy under More options. This adds a ProRes Proxy MOV beside the main MP4; attach the proxy manually in your editor if desired.

The update preserves settings, history and the download directory. It supports verified original v8 and v8.1 installations using the existing bundled runtime and media tools. Unknown modified application files are rejected. No full application, runtime or media-tool ZIP is required.

On processing failure, use Retry Conversion to reuse the retained source. Retry Download remains available if the source is incomplete or has changed. Copy Error includes the failure details.

Future update checking retains the signed HTTPS feed system and asks the user to download/install. A live publicly reachable update feed has not been configured; this standalone update works without it. No private GitHub token or publisher private key is included.

The package has a signed internal manifest and verifies payload/installed-file hashes. It does not carry an Authenticode certificate; Windows publisher reputation is not established. No Premiere Pro import or timeline playback test is claimed for 8.2, per your instruction.
