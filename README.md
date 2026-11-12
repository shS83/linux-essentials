# Linux Essentials Bootstrap v0.4.1

A colorful, portable Bash toolkit installer for new **Arch Linux**, **Debian/Ubuntu** and **Fedora** installations. Its TrueColor **Summary** lists installed/missing/unavailable programs and lets you customize the selection before installing anything.

The expanded catalog includes `lsd`, `eza`, `fzf`, `fd`, `yazi`, `bat`, `ripgrep`, `pv`, `btop`, `fastfetch`, `hyfetch`, `zoxide`, `duf`, `dust`, `ncdu`, `jq`, `lazygit`, `git-delta`, `tmux`, **Byobu** and the six personal programs **CPROJ**, **CmdVault**, **NADAR**, **SRVPULSE**, **GitPublish** and **Cmedia**. It also catalogs `uv`, `python3`, `ffmpeg` and `chafa` for Cmedia installation. `bpytop` is superseded by `btop`.

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
| CPROJ v0.2.0 | `~/.local/bin/cproj` | `~/.config/cproj/{cproj.bash,cproj.conf}` |
| CmdVault | `~/.local/bin/cmdvault` | User-supplied source required (see below) |
| NADAR v0.7.0 | `~/.local/bin/nadar` | `~/.config/nadar/nadar.conf`, `~/.config/systemd/user/nadar*.service` and `nadar-remote-watch.timer` |
| GitPublish | `~/.local/bin/gitpublish` | Bundled Bash script; requires `git`, `gh` and `gh auth login` |
| Cmedia | `~/.local/bin/cmedia` | Bundled anti-flicker patch & installer; requires upstream source, `uv`, `git`, `python3`, `chafa` and `ffmpeg` |
| SRVPULSE v0.1.0 | `~/.local/bin/srvpulse` | Python environment `~/.local/share/linux-essentials/venvs/srvpulse/` and `~/.config/srvpulse/config.toml` |

The package *bundles source code* for CPROJ, NADAR, GitPublish and SRVPULSE under `vendor/`, so these can be installed offline **except for SRVPULSE's Python dependencies**, which need an available installer/cache or access to package repositories. For SRVPULSE/CmdVault Python projects, the script uses installed `uv` when available, otherwise `python3 -m venv` with pip. Cmedia specifically uses `uv tool install` and its upstream project requires Python 3.13+. On Debian/Ubuntu without `uv` you may need `python3-venv`/`python3-pip` first. **Run the installer as a normal user**, since it writes configuration under `$HOME` and invokes sudo only for operating-system packages.

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

The patch changes **only the file-list selection bars** to update the affected terminal rows instead of clearing the whole screen after ↑/↓. The image/preview rendering implementation is left intact. The patch writes `src/cmedia/app.py.bak` once if it modifies your checkout, and refuses unknown upstream code layouts. Changes to an existing checkout should be inspected with `git diff` and committed/pushed separately if desired. For upgrades, use `--upgrade-tools` to overwrite an already installed command.

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

### Bring your own CmdVault

The previous versions of the toolkit did not include CmdVault's source code, so this release does **not** silently replace it with a dummy application. Choose either of these methods:

```bash
# Install from an existing CmdVault checkout or script
./install.sh --profile developer --source cmdvault="$HOME/Code/cmdvault"

# Or bundle your own code in the Git repository (git commit it yourself)
mkdir -p vendor/cmdvault
cp /path/to/your/cmdvault.py vendor/cmdvault/cmdvault.py
./install.sh --profile developer
```

`--source cmdvault=PATH` accepts a standalone Bash/Python executable, or a directory containing `cmdvault`, `cmdvault.py` or a Python `pyproject.toml`. When no source is available, the Summary reports **source needed** and the installer reports the skipped personal tool explicitly (it does not invent a working app). If you have already installed CmdVault, it is treated as installed.

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

### dotfiles-sync: machine-specific dotfiles backup

`dotfiles-sync` is bundled under `vendor/dotfiles-sync/` and included in the
Desktop, Developer and All profiles. It installs the executable into
`/Tools/dotfiles-sync` and user units into `~/.config/systemd/user/`.

The installer initializes a bare repository at
`~/.dotfiles-sync-${HOSTNAME}.git` using `$HOME` as its work tree and sets
`status.showUntrackedFiles=no`. All new paths are ignored by default to prevent
accidental publication of SSH keys, tokens, and other private HOME files.
Track chosen files explicitly with `git --git-dir=... --work-tree="$HOME" add -f PATH`.

If `gh` is authenticated, the bootstrap checks for a matching private GitHub
repository, creates it only if missing, and publishes an empty initial commit.
It does *not* automatically upload the contents of `$HOME`. An authentication
or network failure does not trigger a duplicate repository creation.

```bash
./install.sh --profile developer --dry-run
./install.sh --profile developer --yes --enable-services
# Or install this tool alone:
printf 'dotfiles-sync\n' > /tmp/dotfiles-sync.list
./install.sh --import /tmp/dotfiles-sync.list --yes --enable-services
```

The timer is enabled only with `--enable-services`; otherwise its systemd
unit files are installed but left inactive. Use `--upgrade-tools` to reinstall
updated bundled files.

The bundled `dotfiles-sync` files can be refreshed from `~/Code/dotfiles-sync`. An optional `.dotfiles-sync` default manifest is installed only when `~/.dotfiles-sync` does not exist; existing selections are preserved. Enable only `dotfiles-sync.timer` via `--enable-services` because the timer starts the service on schedule.
