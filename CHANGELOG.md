## 0.4.2 — dotfiles-sync

- Add dotfiles-sync to Desktop, Developer and All profiles.
- Bundle its executable and systemd user units under vendor/.
- Set up a machine-specific bare Git repository and optional private GitHub publication.
- Keep systemd timer enablement opt-in via --enable-services.

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
