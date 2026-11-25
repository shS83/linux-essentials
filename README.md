# Linux Essentials Bootstrap v0.5.2

A colorful, portable Bash toolkit installer for new **Arch Linux**, **Debian/Ubuntu** and **Fedora** installations. Its TrueColor **Summary** lists installed/missing/unavailable programs and lets you customize the selection before installing anything.

The expanded catalog includes `lsd`, `eza`, `fzf`, `fd`, `yazi`, `bat`, `ripgrep`, `pv`, `btop`, `fastfetch`, `hyfetch`, `zoxide`, `duf`, `dust`, `ncdu`, `jq`, `lazygit`, `git-delta`, `tmux`, **Byobu** and personal programs including **Taskman Neon**, **MusiK**, **CPROJ**, **CmdVault**, **NADAR**, **SRVPULSE**, **GitPublish** and **Cmedia**. It also catalogs `uv`, `python3`, `ffmpeg` and `chafa` for Cmedia installation. `bpytop` is superseded by `btop`.

## Fresh-install bootstrap

Install Git first if cloning a repository:

```bash
# Arch Linux
sudo pacman -Syu --needed git
# Debian or Ubuntu
sudo apt update && sudo apt install git
# Fedora
sudo dnf install git
```

Once *you* publish this project to GitHub, clone your repository:

```bash
git clone https://github.com/YOUR-USER/linux-essentials-bootstrap.git
cd linux-essentials-bootstrap
./install.sh --profile developer --summary
./install.sh --profile developer --dry-run
./install.sh --profile developer
```

The GitHub address is a placeholder, not a live project. You can also copy the entire directory without Git.

## Main commands

```bash
./install.sh                                # interactive profile selection
./install.sh --profile minimal --summary    # show the colorful summary only
./install.sh --profile all --dry-run        # preview, no installation
./install.sh --profile desktop             # ask for approval
./install.sh --profile developer --yes     # install without final confirmation
./install.sh --profile server --aur        # permit AUR Byobu through yay/paru
./install.sh --list                         # all tools and their current status
./install.sh --export ~/essentials.list     # save installed tool IDs
./install.sh --import ~/essentials.list     # install tools from the list
./install.sh --help
```

Five profiles: **Minimal** (Git, search and transfer), **Desktop** (file management, system-monitoring tools and personal tools, including Cmedia), **Developer** (Desktop plus development utilities), **Server** (SSH, diagnostics, Byobu and SRVPULSE) and **All** (entire catalog). `lsd` now belongs even to **Minimal**. The `--summary`, `--dry-run`, `--list`, `--export` commands never install packages.

The Summary uses TrueColor on compatible TTYs and disables colors in pipes and when `NO_COLOR=1`. On Arch, Byobu is ordinarily an AUR package and is only selected for installation using **`--aur`** with a preinstalled `yay` or `paru` helper. Debian's `fd-find` and `batcat` naming differences are handled with user-local symlinks if needed.

## Personal tools and installation paths

The following tools are installed for the invoking *normal* user, not into `/usr/local/bin`:

| Tool | Executable | Additional files |
| --- | --- | --- |
| CPROJ v0.2.1 | `~/.local/bin/cproj` | `~/.config/cproj/{cproj.bash,cproj.conf}` |
| CmdVault | `~/.local/bin/cmdvault` | User-supplied source required (see below) |
| Taskman Neon | `~/.local/bin/taskman` | C++20/FTXUI build; PostgreSQL connection configured separately |
| Taskman legacy CLI | `~/.local/bin/taskman-cli` | Built from the same Taskman source |
| MusiK | `~/.local/bin/musik` | Qt6 music player in an isolated uv environment |
| NADAR v0.7.0 | `~/.local/bin/nadar` | `~/.config/nadar/nadar.conf`, `~/.config/systemd/user/nadar*.service` and `nadar-remote-watch.timer` |
| GitPublish | `~/.local/bin/gitpublish` | Bundled Bash script; requires `git`, `gh` and `gh auth login` |
| Cmedia | `~/.local/bin/cmedia` | Bundled V2 incremental renderer patch & installer; requires upstream source, `uv`, `git`, `python3`, `chafa` and `ffmpeg` |
| SRVPULSE v0.1.0 | `~/.local/bin/srvpulse` | Python environment `~/.local/share/linux-essentials/venvs/srvpulse/` and `~/.config/srvpulse/config.toml` |

The package bundles source for its local tools under `vendor/`. Taskman builds with CMake and may fetch FTXUI if no system FTXUI package is installed. Selecting Taskman automatically selects CMake, a C++ compiler, zlib, PostgreSQL client headers and Git. Taskman requires an already running PostgreSQL server and a database; the installer does not initialize or alter PostgreSQL clusters. Set `TASKMAN_DATABASE_URL` if the default `dbname=taskman` connection is not appropriate. MusiK installs its locked Python dependencies through `uv` and needs a graphical desktop session with OpenGL support. **Run the installer as a normal user**, since it writes configuration under `$HOME` and invokes sudo only for operating-system packages.

### Cmedia: flicker-free browser and portable launcher

The **Desktop**, **Developer**, and **All** profiles now select Cmedia; Minimal and Server are unchanged. Selecting `cmedia` alone through `--import` also selects `git`, `uv`, `python3`, `ffmpeg` and `chafa`. Cmedia needs a functioning terminal and uses the original preview/media implementations.

`vendor/cmedia/` includes the tested patch/installer scripts, **not a full copy of the upstream Python source**. On a development machine, the bootstrap tries `~/Code/cmedia` first. Otherwise it downloads the `root` branch of [shS83/cmedia](https://github.com/shS83/cmedia) when installing (an Internet connection is needed). You can explicitly point to a source checkout (recommended if you have local changes):

```bash
# Install only Cmedia from a local checkout:
printf 'cmedia\n' > /tmp/cmedia-tools.list
./install.sh --import /tmp/cmedia-tools.list --dry-run --source "cmedia=$HOME/Code/cmedia"
./install.sh --import /tmp/cmedia-tools.list --yes --source "cmedia=$HOME/Code/cmedia"

# Or install/upgrade via the Desktop profile:
./install.sh --profile desktop --upgrade-tools --source "cmedia=$HOME/Code/cmedia"

# Command works everywhere when ~/.local/bin is in PATH:
cmedia ~/Pictures
```

The V2 patch updates **only changed file-list rows, status text and preview details** instead of clearing the whole screen after ↑/↓; one keyboard event is sent in a single write. The image/preview rendering implementation is left intact. The V2 patch writes `src/cmedia/app.py.before-diff-v2.bak` once if it modifies your checkout, and refuses unknown upstream code layouts. Changes to an existing checkout should be inspected with `git diff` and committed/pushed separately if desired. For upgrades, use `--upgrade-tools` to overwrite an already installed command.

**Dependency note:** `uv` must be available (some Debian/Ubuntu repositories may not package it), and the upstream project requires Python >=3.13. `uv` can obtain the required Python runtime when configured to download Python. `chafa` and `ffmpeg` also need to be installed for the media preview functionality. The patch itself is bundled, so a local-source install does not download patch code.

### GitPublish: create and publish your repository

GitPublish is included in `vendor/gitpublish/gitpublish` and installs into
`~/.local/bin/gitpublish`. The installer selects **Git** and **GitHub CLI (`gh`)**
automatically when GitPublish is selected, including `--import` with just `gitpublish`.
On Arch the package name is `github-cli`; on Ubuntu/Debian/Fedora it is `gh`.
To enable uploads, authenticate separately with `gh auth login` (not performed by the bootstrap).

```bash
./install.sh --profile developer --dry-run
./install.sh --profile developer
# One-time GitHub authorization:
gh auth login
# From the root of a new project:
gitpublish --dry-run
gitpublish --public
```

By default GitPublish creates a **private** repository. Review `git status` and
`.gitignore` before publishing; GitPublish asks for confirmation and refuses some
common secret file patterns. It can initialize Git and create the first commit.

`keyio` is deliberately **not bundled**: Python projects should install it directly
from `https://github.com/shS83/keyio`, using their own environment, when needed.

### CmdVault – bundled official logo, full source installation

The **exact GitHub `cmdvault.png`** is bundled with this release, but the
full CmdVault source tree is not shipped offline. The installer prefers
`~/Code/cmdvault`, then fetches `shS83/cmdvault` from GitHub when needed.
It installs all the app's visuals and sync modules via upstream `install.sh`.
You can also select a source explicitly:

```bash
# Install from an existing CmdVault checkout or script
./install.sh --profile developer --source cmdvault="$HOME/Code/cmdvault"

# Update only CmdVault (existing local source is used, otherwise GitHub)
printf 'cmdvault\n' > /tmp/le-cmdvault.list
./install.sh --import /tmp/le-cmdvault.list --yes --upgrade-tools
```

`--source cmdvault=PATH` accepts a standalone Bash/Python executable, or a directory containing `cmdvault`, `cmdvault.py` or a Python `pyproject.toml`. If no full local source is available, the installer fetches the CmdVault repository from GitHub (network required); `vendor/cmdvault/cmdvault.png` is included offline and used as a fallback for missing logos (it does not invent a working app). If CmdVault is already installed, use `--upgrade-tools` to reinstall and restore the PNG.

### Optional integration (requires approval)

```bash
./install.sh --profile developer --shell-integration --enable-services
```

* `--shell-integration` appends exactly one `source "$HOME/.config/cproj/cproj.bash"` line to `~/.bashrc`; needed for CPROJ to change the current shell directory and activate `.venv` automatically.
* `--enable-services` enables `nadar.service` and `nadar-remote-watch.timer` in your user systemd manager. Without it, unit files are only installed and the daemon is *not* automatically enabled.
* Existing `cproj.conf`, `nadar.conf` and `srvpulse/config.toml` are preserved. `--upgrade-tools` updates previously installed personal tools on request.
* Remote NADAR Ouroboros-side scanner/socket units are **not** deployed automatically. Those require a separate, explicit privileged installation on the server.

Ensure `~/.local/bin` is on your PATH, e.g. in `.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Import/export and safety

The `--export` output is a human-readable list of installed known tool IDs, not shell code. `--import` only accepts predefined known IDs and refuses unknown ones. Existing exports are not overwritten unless `--force` is given. The installer doesn't add package repositories, edit firewall rules, run arbitrary imported shell code or rewrite existing personal-tool configurations. If a repository batch installation fails, it retries packages individually and reports those that fail.

`--yes` skips the final interactive confirmation. Always check `--dry-run` on a new machine before installing; this does not guarantee every package is available in the distro's configured repositories.

## Tests

```bash
bash -n install.sh
bash tests/test-bootstrap.sh
bash tests/test-personal-tools.sh
bash tests/test-cmedia.sh
```

All test scripts use fake package managers and isolated temporary HOME directories; they do not install real system packages or access GitHub.

## License

MIT; see `LICENSE`.

### CPROJ: update all Git projects (v0.2.0)

```bash
cproj --refresh            # optional: refresh discovered projects
cproj --pull-all --dry-run # inspect Git projects without network changes
cproj --pull-all           # git pull --ff-only for every clean tracked project
```

Projects are read from CPROJ's indexed roots and manually added directories.
Only Git repository roots are processed, so nested subprojects are not pulled
twice. Repositories with local modifications or untracked files, a detached
HEAD, or no upstream branch are skipped. Diverged branches are not merged or
rebased; `--ff-only` reports an error and continues to the next repository.
This command does not change the current working directory.

To upgrade just CPROJ from Linux Essentials:

```bash
printf 'cproj\n' > /tmp/cproj.list
./install.sh --import /tmp/cproj.list --yes --upgrade-tools
```


### CPROJ bulk pull / shell reload

After upgrading bundled CPROJ, reload the Bash integration in each active shell:

```bash
source ~/.config/cproj/cproj.bash
cproj --pull-all --dry-run
cproj --pull-all
```

`command cproj --pull-all` bypasses a stale Bash function immediately.

## v0.5.0: refresh personal tools and Clipvault

The archive includes the original bootstrap and a complete Clipvault
source snapshot with its November 16 GUI/art hotfix. To update installed personal tools from the current GitHub sources:

```bash
./install.sh --profile developer --dry-run --upgrade-tools --latest
./install.sh --profile developer --yes --upgrade-tools --latest
```

`--latest` clones official `shS83` repositories into a temporary directory and
installs their latest default-branch contents. This requires internet and may
install newer versions than those available on archive creation day. It never
changes `~/Code` checkouts. `--source NAME=PATH` takes priority over `--latest`.
This is not an offline snapshot of every upstream repo. Without `--latest`,
older bundled versions are used where available; the Clipvault source snapshot
can be installed without cloning (Python packages still require uv/cache/network).

Clipvault is optional and available in Desktop, Developer, and All. Install only
Clipvault with:

```bash
printf 'clipvault\n' > /tmp/clipvault.list
./install.sh --import /tmp/clipvault.list --dry-run --latest
./install.sh --import /tmp/clipvault.list --yes --latest
clipvault  # GUI, requires DISPLAY or WAYLAND_DISPLAY
clipvault --cli  # explicit terminal clipboard watcher
```

Clipvault is NOT started automatically. It needs `uv`, Python >=3.15 (which
uv may download), PySide6, and an existing PostgreSQL `clipvault` database and
roles/schema. Its source uses `dbname=clipvault user=clipvault host=localhost`.
No PostgreSQL setup, credential changes, or clipboard capture is performed
by the installer. Entries are plaintext, and heuristic secret filtering is
not a complete confidentiality guarantee. Wayland clipboard monitoring depends
on the compositor.

Dotfiles-sync is also included. The upstream service expects its executable at `/Tools/dotfiles-sync`, but
this bundle adapts the user unit to `%h/.local/bin/dotfiles-sync` and repairs
bare-repository staging. Set up the local bare Git repository (and remote, if
used) before enabling the timer. The installer never creates GitHub
repositories or starts this timer by default; use `--enable-services` only
after verifying your dotfiles setup.

**Privacy:** This bundle's new dotfiles-sync sample intentionally does not
include `.bash_history`, because terminal history may contain private tokens.
If you already have `~/.dotfiles-sync`, the installer preserves it. Review
its tracked files and Git remotes before enabling the timer.

## v0.5.1 – CmdVault logo and Cmedia V2

- The exact current CmdVault logo is **included** in `vendor/cmdvault/cmdvault.png`.
  Git blob SHA1: `8cd4b766f396b2621de73e9d3f1aeb0d44b77d2b`.
  A complete CmdVault checkout is still needed and is fetched from GitHub when
  not found locally. The official CmdVault installer installs the PNG into
  `~/.local/share/cmdvault/app/cmdvault.png`.
- The bundled `vendor/cmedia/patch_cmedia.py` and its installer are now V2,
  replacing V1. This avoids redrawing backgrounds/frames on each navigation.
- Refresh just these tools with:

  ```bash
  printf 'cmdvault\ncmedia\n' > /tmp/le-update.list
  ./install.sh --import /tmp/le-update.list --upgrade-tools --yes
  ```

  The installer prefers `~/Code/` checkouts; `--latest` retrieves a fresh
  temporary checkout, never `git pull` in your working directory.
