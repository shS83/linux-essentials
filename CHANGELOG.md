## 0.5.2 — 2026-11-23

- Add Taskman Neon to Desktop, Developer and All profiles.
- Bundle Taskman's C++20 source and steampunk logo; build and install `taskman` plus legacy `taskman-cli`.
- Select CMake, compiler, zlib, PostgreSQL client headers and Git when Taskman is selected.
- Document that PostgreSQL service/database setup remains user-managed.
- Add MusiK to Desktop, Developer and All with its source snapshot and locked uv environment.

## 0.5.1 — 2026-11-18

- Bundle the exact `cmdvault.png` from shS83/cmdvault/root, verified against Git blob SHA1.
- CmdVault uses the complete upstream installer; restore a missing PNG from the bundle without mutating the user's project checkout.
- Fetch full CmdVault GitHub source automatically if not in ~/Code or explicitly provided.
- Update Cmedia to V2 differential renderer: changed rows, cached metadata, atomic output and stable preview borders.
- Replace bundled Cmedia V1 patch, include V2 regression tests and installer tests.

## 0.5.0 — 2026-11-18

- Added Clipvault (PySide6 GUI + optional `--cli`) to Desktop, Developer and All.
- Bundled the November 16 Clipvault GUI statusbar hotfix, icon and DB action helper.
- Added `--latest`: fetch current sources for all personal tools into temporary
  directories without touching user-owned Git checkouts.
- Updated CmdVault integration to use its full upstream installer (src modules,
  image and shell support) rather than copying a single script.
- Updated SRVPULSE installation to include GUI extras and optional launchers.
- Added dotfiles-sync with user-local launcher and optional timer integration.
- Preserved existing configs and made Clipvault installation opt-in/no autostart.
- Existing CPROJ bulk `git pull --ff-only`, Cmedia flicker patch, NADAR and
  GitPublish remain available. An explicit `--latest --upgrade-tools` updates
  them from GitHub.

## v0.4.2 — CPROJ v0.2.1 (2026-11-10)
- Updated bundled CPROJ to v0.2.1.
- Bash wrapper now passes option-style commands through to the CPROJ executable.
- Active shell function needs reloading after install: `source ~/.config/cproj/cproj.bash`.
- CPROJ Git pull integration tests cover option forwarding.

# Changelog

## 0.4.1 — 2026-11-10

- Bundled CPROJ v0.2.0: `--pull-all` performs `git pull --ff-only` across clean, tracked Git project roots; `--dry-run` previews without pulling.
- Prevented CPROJ shell integration from interpreting bulk-pull output as a directory.

## 0.4.0 — 2026-11-10

- Added `cmedia` to Desktop, Developer, and All profiles and the personal tools catalog.
- Bundled the Cmedia differential browser-rendering patch and user installer under `vendor/cmedia/`.
- Added `--source cmedia=DIR` support and automatic use of `~/Code/cmedia` when available.
- When no local source exists, the installer clones `shS83/cmedia` (`root` branch) and patches it before installing.
- Cmedia always installs its CLI entry point to `~/.local/bin/cmedia` using `uv tool install`.
- Automatically selects `git`, `uv`, `python3`, `chafa`, `ffmpeg` when Cmedia is selected via import/profile.
- Added offline Cmedia integration tests; existing v0.3.0 tools and behavior are retained.

## 0.3.0 — 2026-11-10

- Added bundled GitPublish CLI and dependency detection for Git and GitHub CLI.
