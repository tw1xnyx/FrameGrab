# Free GitHub Releases distribution



The application source stays in private `tw1xnyx/FrameGrab`. Public `tw1xnyx/FrameGrab-Updates` contains distribution binaries only. The app uses the public GitHub provider without credentials, Pages, a domain or another hosting service.



## One-time account setup

1. Create empty **public** `tw1xnyx/FrameGrab-Updates`. Keep FrameGrab private. Grant the connected GitHub app access to the new repository if this chat will inspect it.

2. In GitHub Developer settings create a fine-grained token restricted to **FrameGrab-Updates only**, with repository **Contents: Read and write**. Store it as private FrameGrab repository Settings > Secrets and variables > Actions > **RELEASE_PUBLISH_TOKEN**. Never put it in source files, releases, the app or chat. The normal Actions GITHUB_TOKEN cannot write to another repository.

3. Open private FrameGrab > Actions > FrameGrab verified GitHub Releases > Run workflow. Enable **publish** only after setup. The workflow tests, stages a draft binary release and makes it latest only after successful asset upload.



## Future releases

Update package.json and package-lock.json version together. Add `docs/Release_<version>.md`. Push a matching `v<version>` tag, or run the workflow with publish selected. The workflow verifies the version, installer, latest.yml, SHA512, blockmap and SHA256 before publication. Only the setup EXE, blockmap, latest.yml and checksum file are uploaded. Source is never copied to the public repository. GitHub automatically provides archives of the binary repository itself; keep it empty of application source.



Installed clients check after launch and periodically. Download & Install is explicit; actual download progress is shown. Active or paused downloads must finish or be canceled before restart. Differential download is enabled, with a full download fallback when previous installer/blockmap data is missing or unsuitable. No promise is made that every update is tiny.



## Existing 8.0–8.2 users

Run the separately supplied small `FrameGrab_Update.exe` once. It locates the installation, checks recognized baseline hashes, verifies its embedded signed payload, backs up changed files and applies only the app/service changes. It preserves user data and existing runtime/tool binaries, and restarts FrameGrab. If installation cannot be located, select its existing folder in the updater. Replacement/startup failures roll back. Future online updates use standard Electron Updater + NSIS. Standard NSIS does not provide the same transactional rollback guarantee as this one-time patch.



## Cost and signing

No paid hosting or plan was enabled. Private-repository Actions consumes the account's included minutes/storage; it is not unlimited free compute. Caches and seven-day artifact retention reduce usage. Keep the account Actions spending budget blocked at $0 if no overage is acceptable. Current GitHub documentation: https://docs.github.com/en/billing/concepts/product-billing/github-actions



An Authenticode signing certificate was not available. The bootstrap payload has RSA signature verification, and online releases use HTTPS plus SHA512 verification. These do not constitute Windows publisher code signing; checksums do not protect a compromised publishing account. Keep token permissions narrow and GitHub account security enabled.



## Deployment status

FrameGrab 8.3.0 is published at https://github.com/tw1xnyx/FrameGrab-Updates/releases/tag/v8.3.0. Private-source Windows CI run 38010929841 passed build, download tests, installation to a path with spaces, launch/backend readiness, in-place reinstall, data preservation and checksum verification. Publication run 38011229173 verified the restricted publishing credential and uploaded only binary assets. A real Electron Updater transport detected 8.3.0, downloaded the published 196,971,058-byte installer with progress reaching 100%, and verified SHA512 and SHA256. It used a full fallback because no 8.2 blockmap is published. The patched packaged 8.3 app also reached the public feed through its native Check for Updates interface and reported current version. Actual new-version in-app restart/install and differential bytes saved remain unverified.

