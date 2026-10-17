# Linux Essentials Bootstrap v0.2.0

A colorful, portable Bash toolkit installer for new **Arch Linux**, **Debian/Ubuntu** and **Fedora** installations. Its TrueColor **Summary** lists installed/missing/unavailable programs and lets you customize the selection before installing anything.

The 38-item catalog includes `lsd`, `eza`, `fzf`, `fd`, `yazi`, `bat`, `ripgrep`, `pv`, `btop`, `fastfetch`, `hyfetch`, `zoxide`, `duf`, `dust`, `ncdu`, `jq`, `lazygit`, `git-delta`, `tmux`, **Byobu** and the four personal programs **CPROJ**, **CmdVault**, **NADAR**, and **SRVPULSE**. `bpytop` is superseded by `btop`.

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

Five profiles: **Minimal** (Git, search and transfer), **Desktop** (file management, system-monitoring tools and personal tools), **Developer** (Desktop plus development utilities), **Server** (SSH, diagnostics, Byobu and SRVPULSE) and **All** (entire catalog). `lsd` now belongs even to **Minimal**. The `--summary`, `--dry-run`, `--list`, `--export` commands never install packages.

The Summary uses TrueColor on compatible TTYs and disables colors in pipes and when `NO_COLOR=1`. On Arch, Byobu is ordinarily an AUR package and is only selected for installation using **`--aur`** with a preinstalled `yay` or `paru` helper. Debian's `fd-find` and `batcat` naming differences are handled with user-local symlinks if needed.

## Personal tools and installation paths

The following tools are installed for the invoking *normal* user, not into `/usr/local/bin`:

| Tool | Executable | Additional files |
| --- | --- | --- |
| CPROJ v0.1.1 | `~/.local/bin/cproj` | `~/.config/cproj/{cproj.bash,cproj.conf}` |
| CmdVault v0.1.0 | `~/.local/bin/cmdvault` | Bundled upstream executable; Python >= 3.9 required |
| NADAR v0.7.0 | `~/.local/bin/nadar` | `~/.config/nadar/nadar.conf`, `~/.config/systemd/user/nadar*.service` and `nadar-remote-watch.timer` |
| SRVPULSE v0.1.0 | `~/.local/bin/srvpulse` | Python environment `~/.local/share/linux-essentials/venvs/srvpulse/` and `~/.config/srvpulse/config.toml` |

The package *bundles source code* for CPROJ, CmdVault, NADAR and SRVPULSE under `vendor/`, so these can be installed offline **except for SRVPULSE's Python dependencies**, which need an available installer/cache or access to package repositories. For Python projects, the script uses installed `uv` when available, otherwise `python3 -m venv` with pip. On Debian/Ubuntu without `uv` you may need `python3-venv`/`python3-pip` first. **Run the installer as a normal user**, since it writes configuration under `$HOME` and invokes sudo only for operating-system packages.

### CmdVault

CmdVault is bundled from [shS83/cmdvault](https://github.com/shS83/cmdvault), so no separate checkout or `--source` option is required. Its executable is copied directly, matching upstream's installer. You can still override the bundled snapshot:

```bash
# Install from an existing CmdVault checkout or script
./install.sh --profile developer --source cmdvault="$HOME/Code/cmdvault"

```

`--source cmdvault=PATH` accepts a standalone Bash/Python executable, or a directory containing `cmdvault`, `cmdvault.py` or a Python `pyproject.toml`. A standalone executable takes precedence over `pyproject.toml`, because upstream's metadata does not declare a packaged CLI. If you have already installed CmdVault, it is treated as installed; use `--upgrade-tools` to replace it. CmdVault needs Python >= 3.9; `fzf` enables interactive selection.

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
```

Both test scripts use fake package managers and isolated temporary HOME directories; they don't install real system packages.

## License

MIT; see `LICENSE`.
