#!/usr/bin/env bash
# Linux Essentials Bootstrap - portable Bash CLI toolkit installer
# License: MIT
set -o pipefail
set -u

readonly VERSION='0.2.0'
readonly SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly SCRIPT_NAME=${0##*/}

declare -a TOOLS=(
  git curl wget openssh rsync unzip zip
  fzf fd ripgrep bat eza lsd yazi
  btop htop fastfetch hyfetch pv zoxide duf dust ncdu jq
  git-delta lazygit tmux byobu shellcheck shfmt tealdeer lsof nmap strace
  cproj cmdvault nadar srvpulse
)
declare -a PERSONAL_TOOLS=(cproj cmdvault nadar srvpulse)
declare -A TOOL_SOURCES=()
declare -A KNOWN=() SELECTED=() STATUS=() PACKAGE=()
for _tool in "${TOOLS[@]}"; do KNOWN[$_tool]=1; done

PM='' DISTRO=''
PROFILE='' FROM_FILE='' EXPORT_FILE='' SHOW_ALL=0
YES=0 DRY_RUN=0 AUR=0 FORCE=0 SUMMARY_ONLY=0
UPGRADE_TOOLS=0 SHELL_INTEGRATION=0 ENABLE_SERVICES=0
NO_COLOR=${NO_COLOR:-}
C_RESET='' C_PURPLE='' C_TEAL='' C_GREEN='' C_YELLOW='' C_RED='' C_MUTED='' C_BLUE=''

setup_colors() {
  if [[ -t 1 && -z $NO_COLOR && ${TERM:-dumb} != dumb ]]; then
    C_RESET=$'\033[0m'
    C_PURPLE=$'\033[38;2;194;156;255m'
    C_TEAL=$'\033[38;2;100;225;203m'
    C_GREEN=$'\033[38;2;111;226;168m'
    C_YELLOW=$'\033[38;2;255;201;123m'
    C_RED=$'\033[38;2;255;124;145m'
    C_MUTED=$'\033[38;2;145;156;185m'
    C_BLUE=$'\033[38;2;101;197;254m'
  fi
}
info() { printf '%b%s%b\n' "$C_TEAL" "$*" "$C_RESET"; }
warn() { printf '%b%s%b\n' "$C_YELLOW" "$*" "$C_RESET" >&2; }
error() { printf '%bError: %s%b\n' "$C_RED" "$*" "$C_RESET" >&2; }
die() { error "$*"; exit 1; }

usage() {
  cat <<EOF
LINUX ESSENTIALS BOOTSTRAP v$VERSION
Portable terminal toolkit installer for Arch, Debian, Ubuntu and Fedora.

Usage:
  $SCRIPT_NAME                         Interactive profile selection
  $SCRIPT_NAME --profile PROFILE       Select minimal|desktop|developer|server|all
  $SCRIPT_NAME --profile server --yes  Noninteractive installation
  $SCRIPT_NAME --profile all --dry-run Preview, never install
  $SCRIPT_NAME --profile developer --source cmdvault=/path/to/cmdvault
  $SCRIPT_NAME --profile all --summary Show status, never install
  $SCRIPT_NAME --list                  Show the complete toolkit catalog
  $SCRIPT_NAME --export [FILE]         Export detected installed tools to a list
  $SCRIPT_NAME --import FILE           Install tools from an exported list

Options:
  -p, --profile PROFILE   Select a predefined profile
  -i, --import FILE       Read tool IDs from a plain-text list
  -e, --export [FILE]     Write installed tool IDs (default: XDG config dir)
      --list              Display all available tool IDs and status
      --summary           Report only; install nothing
      --dry-run           Preview actions; install nothing
  -y, --yes               Approve installation without an extra prompt
      --aur               Permit AUR installs via existing yay/paru (Arch only)
      --force             Allow --export to overwrite an existing file
      --source NAME=DIR   Use a local project directory/file for a personal tool
      --upgrade-tools     Reinstall selected personal tools even if present
      --shell-integration  Add the CPROJ source line to ~/.bashrc (opt-in)
      --enable-services   Enable/start NADAR user systemd units (opt-in)
  -h, --help              Show this help

Notes:
  • Only known tool IDs are accepted in imports (never sourced as shell code).
  • Missing tools are installed from configured system repositories.
  • Arch's Byobu is normally an AUR package; --aur is opt-in.
  • On Debian/Ubuntu, the fd/bat binaries may be named fdfind/batcat.
  • Bundled: cproj, cmdvault, nadar and srvpulse.
  • Personal tools install under ~/.local/bin (srvpulse uses an isolated venv).
  • Shell integration and systemd activation are explicit opt-ins.
  • The script never adds package repositories.
EOF
}

parse_args() {
  while (( $# )); do
    case $1 in
      -p|--profile)
        (( $# >= 2 )) || die "$1 requires a profile"
        PROFILE=$2; shift 2 ;;
      -i|--import)
        (( $# >= 2 )) || die "$1 requires a file"
        FROM_FILE=$2; shift 2 ;;
      -e|--export)
        EXPORT_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/linux-essentials/tools.list"
        if (( $# >= 2 )) && [[ $2 != -* ]]; then EXPORT_FILE=$2; shift; fi
        shift ;;
      --list) SHOW_ALL=1; shift ;;
      --summary) SUMMARY_ONLY=1; shift ;;
      --dry-run) DRY_RUN=1; shift ;;
      -y|--yes) YES=1; shift ;;
      --aur) AUR=1; shift ;;
      --force) FORCE=1; shift ;;
      --upgrade-tools) UPGRADE_TOOLS=1; shift ;;
      --shell-integration) SHELL_INTEGRATION=1; shift ;;
      --enable-services) ENABLE_SERVICES=1; shift ;;
      --source)
        (( $# >= 2 )) || die '--source requires NAME=DIR'
        local spec=$2 name path
        [[ $spec == *=* ]] || die '--source requires NAME=DIR'
        name=${spec%%=*}; path=${spec#*=}
        case $name in cproj|cmdvault|nadar|srvpulse) ;; *) die "Unknown personal tool: $name" ;; esac
        [[ -n $path ]] || die '--source requires a nonempty directory or file path'
        TOOL_SOURCES[$name]=$path
        shift 2 ;;
      -h|--help) usage; exit 0 ;;
      *) die "Unknown option: $1 (see --help)" ;;
    esac
  done
  [[ -z $PROFILE || -z $FROM_FILE ]] || die '--profile and --import are mutually exclusive'
  if [[ -n $EXPORT_FILE ]]; then
    [[ -z $PROFILE && -z $FROM_FILE && $SHOW_ALL == 0 ]] || die '--export cannot be combined with profile/import/list'
  fi
}

detect_os() {
  local id='' like=''
  local os_release=${LE_OS_RELEASE:-/etc/os-release}
  [[ -r $os_release ]] || die "Cannot read $os_release"
  # /etc/os-release contains shell-style assignments (from the OS, not user input).
  # Parse just ID and ID_LIKE; do not source arbitrary text.
  local line val
  while IFS= read -r line || [[ -n $line ]]; do
    case $line in
      ID=*) val=${line#ID=}; id=${val//\"/}; id=${id//\'/} ;;
      ID_LIKE=*) val=${line#ID_LIKE=}; like=${val//\"/}; like=${like//\'/} ;;
    esac
  done < "$os_release"
  DISTRO=${id:-unknown}
  case " $id $like " in
    *' arch '*|*' manjaro '*|*' endeavouros '*) PM=pacman ;;
    *' debian '*|*' ubuntu '*|*' linuxmint '*|*' pop '*) PM=apt ;;
    *' fedora '*|*' rhel '*|*' centos '*) PM=dnf ;;
    *) die "Unsupported distribution: $DISTRO (ID_LIKE: $like)" ;;
  esac
  local bin
  case $PM in pacman) bin=pacman ;; apt) bin=apt-get ;; dnf) bin=dnf ;; esac
  command -v "$bin" >/dev/null 2>&1 || die "Package manager not found: $bin"
}

package_for() {
  local id=$1
  if is_personal_tool "$id"; then
    local source_dir
    if source_dir=$(personal_source "$id"); then
      if [[ $source_dir == "$SCRIPT_DIR/vendor/$id" ]]; then
        printf 'LOCAL:bundled'
      else
        printf 'LOCAL:source'
      fi
    else
      printf 'LOCAL:missing'
    fi
    return 0
  fi
  case "$PM:$id" in
    apt:fd) printf 'fd-find' ;;
    apt:git-delta|pacman:git-delta|dnf:git-delta) printf 'git-delta' ;;
    apt:openssh) printf 'openssh-client' ;;
    pacman:openssh) printf 'openssh' ;;
    dnf:openssh) printf 'openssh-clients' ;;
    pacman:byobu) printf 'AUR:byobu' ;;
    *) printf '%s' "$id" ;;
  esac
}

is_personal_tool() {
  case $1 in cproj|cmdvault|nadar|srvpulse) return 0 ;; *) return 1 ;; esac
}

personal_source() {
  local id=$1 base candidate
  if [[ -n ${TOOL_SOURCES[$id]:-} ]]; then
    candidate=${TOOL_SOURCES[$id]}
    candidate=${candidate/#\~/$HOME}
    [[ -e $candidate ]] || return 1
    printf '%s' "$candidate"
    return 0
  fi
  base="$SCRIPT_DIR/vendor/$id"
  if [[ -d $base ]]; then
    case $id in
      cmdvault) [[ -f $base/cmdvault || -f $base/cmdvault.py || -f $base/pyproject.toml ]] || return 1 ;;
    esac
    printf '%s' "$base"
    return 0
  fi
  # Reuse a local checkout for a tool without a bundled copy.
  for candidate in "$HOME/Code/$id" "/Tools/$id"; do
    if [[ -d $candidate ]]; then printf '%s' "$candidate"; return 0; fi
  done
  return 1
}

binary_present() {
  local id=$1; local names=()
  case $id in
    openssh) names=(ssh) ;;
    ripgrep) names=(rg) ;;
    fd) names=(fd fdfind) ;;
    bat) names=(bat batcat) ;;
    git-delta) names=(delta) ;;
    tealdeer) names=(tealdeer tldr) ;;
    *) names=("$id") ;;
  esac
  local n
  for n in "${names[@]}"; do
    if command -v "$n" >/dev/null 2>&1; then return 0; fi
  done
  return 1
}

package_installed() {
  local pkg=$1
  pkg=${pkg#AUR:}
  case $PM in
    pacman) pacman -Qq "$pkg" >/dev/null 2>&1 ;;
    apt) [[ $(dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null) == 'install ok installed' ]] ;;
    dnf) rpm -q "$pkg" >/dev/null 2>&1 ;;
  esac
}

package_available() {
  local pkg=$1
  case $PM in
    pacman) pacman -Si "$pkg" >/dev/null 2>&1 ;;
    apt) apt-cache show "$pkg" >/dev/null 2>&1 ;;
    dnf) return 0 ;; # DNF availability checked by the installer itself.
  esac
}

status_for() {
  local id=$1 pkg=${PACKAGE[$1]}
  if is_personal_tool "$id"; then
    # Personal tools are managed in ~/.local/bin even if an older copy
    # happens to be installed somewhere else on PATH.
    if [[ -x "$HOME/.local/bin/$id" ]]; then
      printf 'installed'
    elif personal_source "$id" >/dev/null; then
      printf 'local pending'
    else
      printf 'source needed'
    fi
    return 0
  fi
  if package_installed "$pkg" || binary_present "$id"; then
    printf 'installed'
  elif [[ $pkg == AUR:* ]]; then
    if (( AUR )) && { command -v yay >/dev/null || command -v paru >/dev/null; }; then
      printf 'AUR pending'
    else
      printf 'AUR skipped'
    fi
  elif package_available "$pkg"; then
    printf 'missing'
  else
    printf 'unavailable'
  fi
}

refresh_status() {
  local tool
  for tool in "${TOOLS[@]}"; do
    PACKAGE[$tool]=$(package_for "$tool")
    STATUS[$tool]=$(status_for "$tool")
  done
}

select_profile() {
  local name=$1; local pick=''
  case $name in
    minimal)
      pick='git curl wget unzip zip openssh fzf fd ripgrep bat eza lsd pv jq' ;;
    desktop)
      pick='git curl wget unzip zip openssh rsync fzf fd ripgrep bat eza lsd yazi btop htop fastfetch hyfetch pv zoxide duf dust ncdu jq tmux byobu tealdeer cproj cmdvault nadar srvpulse' ;;
    developer)
      pick='git curl wget openssh rsync unzip zip fzf fd ripgrep bat eza lsd yazi btop htop fastfetch hyfetch pv zoxide duf dust ncdu jq git-delta lazygit tmux byobu shellcheck shfmt tealdeer lsof nmap strace cproj cmdvault nadar srvpulse' ;;
    server)
      pick='git curl wget openssh rsync unzip zip fzf fd ripgrep bat lsd pv htop ncdu jq tmux byobu lsof nmap strace srvpulse' ;;
    all)
      pick="${TOOLS[*]}" ;;
    *) die "Unknown profile '$name' (minimal, desktop, developer, server, all)" ;;
  esac
  local tool
  for tool in $pick; do SELECTED[$tool]=1; done
}

import_tools() {
  local path=$1 line tool lineno=0
  [[ -r $path ]] || die "Cannot read import file: $path"
  while IFS= read -r line || [[ -n $line ]]; do
    ((++lineno))
    line=${line%%#*}
    line=${line//$'\r'/}
    tool=${line#"${line%%[![:space:]]*}"}
    tool=${tool%"${tool##*[![:space:]]}"}
    [[ -n $tool ]] || continue
    [[ -n ${KNOWN[$tool]:-} ]] || die "Unknown tool '$tool' in $path:$lineno"
    SELECTED[$tool]=1
  done < "$path"
  (( ${#SELECTED[@]} )) || die 'Import file contains no known tools'
}

export_tools() {
  local target=$1 tmp tool count=0
  if [[ -e $target && $FORCE -ne 1 ]]; then
    die "File exists: $target (use --force to overwrite)"
  fi
  mkdir -p -- "$(dirname -- "$target")" || die 'Cannot create export directory'
  tmp=$(mktemp "${target}.tmp.XXXXXX") || die 'Could not create temporary export file'
  {
    printf '# Linux Essentials Bootstrap v%s - installed tools\n' "$VERSION"
    printf '# Generated: %(%Y-%m-%dT%H:%M:%S%z)T\n' -1
    printf '# Reinstall with: ./install.sh --import this-file\n'
    for tool in "${TOOLS[@]}"; do
      if [[ ${STATUS[$tool]} == installed ]]; then
        printf '%s\n' "$tool"
        ((++count))
      fi
    done
  } > "$tmp"
  mv -f -- "$tmp" "$target" || die 'Could not write export file'
  info "Exported $count installed tools to $target"
}

show_banner() {
  printf '%b╭─────────────────────────────────────────────────────────╮%b\n' "$C_PURPLE" "$C_RESET"
  printf '%b│  ◈  LINUX ESSENTIALS  /  BOOTSTRAP v%-17s│%b\n' "$C_PURPLE" "$VERSION" "$C_RESET"
  printf '%b╰─────────────────────────────────────────────────────────╯%b\n' "$C_PURPLE" "$C_RESET"
  printf '%b  SYSTEM%b %-18s %bMANAGER%b %s\n' "$C_MUTED" "$C_RESET" "$DISTRO" "$C_MUTED" "$C_RESET" "$PM"
}

show_summary() {
  local all=${1:-0} tool stat pkg color selected=0 present=0 pending=0 unsupported=0
  printf '\n%b  ◈ TOOLKIT SUMMARY  [%s]%b\n' "$C_PURPLE" "${PROFILE:-custom}" "$C_RESET"
  printf '%b%-20s %-23s %-15s%b\n' "$C_MUTED" 'TOOL' 'SYSTEM PACKAGE' 'STATUS' "$C_RESET"
  printf '%b%s%b\n' "$C_MUTED" '───────────────────────────────────────────────────────────' "$C_RESET"
  for tool in "${TOOLS[@]}"; do
    if (( !all )) && [[ -z ${SELECTED[$tool]:-} ]]; then continue; fi
    ((++selected))
    stat=${STATUS[$tool]}; pkg=${PACKAGE[$tool]}
    color=$C_YELLOW
    case $stat in
      installed) color=$C_GREEN; ((++present)) ;;
      missing|'AUR pending'|'local pending') ((++pending)) ;;
      unavailable|'AUR skipped'|'source needed') color=$C_RED; ((++unsupported)) ;;
    esac
    printf '%b%-20s%b %-23s %b%-15s%b\n' "$C_BLUE" "$tool" "$C_RESET" "$pkg" "$color" "$stat" "$C_RESET"
  done
  printf '%b%s%b\n' "$C_MUTED" '───────────────────────────────────────────────────────────' "$C_RESET"
  printf '  %b%d selected%b   %b%d installed%b   %b%d to install%b   %b%d skipped%b\n' \
    "$C_BLUE" "$selected" "$C_RESET" "$C_GREEN" "$present" "$C_RESET" "$C_YELLOW" "$pending" "$C_RESET" "$C_RED" "$unsupported" "$C_RESET"
}

prompt_profile() {
  [[ -t 0 && -r /dev/tty ]] || die 'Interactive terminal required; use --profile and --yes or --dry-run'
  printf '\n%b  SELECT AN INSTALLATION PROFILE%b\n' "$C_PURPLE" "$C_RESET"
  cat <<'EOF'
  [1] Minimal     Core tools for any installation
  [2] Desktop     Colorful terminal, files and system monitoring
  [3] Developer   Desktop + Git, debugging and Bash utilities
  [4] Server      SSH, diagnostics, monitoring and Byobu
  [5] All         Every supported tool in the catalog
  [Q] Quit
EOF
  local selection
  while :; do
    printf '%b  Choice [3]: %b' "$C_TEAL" "$C_RESET"
    IFS= read -r selection </dev/tty || exit 130
    case ${selection:-3} in
      1) PROFILE=minimal; break ;; 2) PROFILE=desktop; break ;;
      3) PROFILE=developer; break ;; 4) PROFILE=server; break ;;
      5) PROFILE=all; break ;; [qQ]) exit 0 ;;
      *) warn 'Please select 1–5 or Q' ;;
    esac
  done
  select_profile "$PROFILE"
}

toggle_tool() {
  local item=$1
  [[ -n ${KNOWN[$item]:-} ]] || { warn "Unknown tool: $item"; return 1; }
  if [[ -n ${SELECTED[$item]:-} ]]; then unset 'SELECTED[$item]'; else SELECTED[$item]=1; fi
}

confirm_install() {
  (( YES || DRY_RUN || SUMMARY_ONLY )) && return 0
  [[ -r /dev/tty ]] || die 'No interactive terminal. Use --yes to approve or --dry-run.'
  local ans tool list
  while :; do
    printf '\n%b  [I] Install missing   [C] Customize   [Q] Quit  > %b' "$C_TEAL" "$C_RESET"
    IFS= read -r ans </dev/tty || exit 130
    case ${ans,,} in
      i|yes|y) return 0 ;;
      q|n|no) info 'No changes made.'; exit 0 ;;
      c)
        printf '  Toggle tools (comma-separated IDs, e.g. lsd,byobu): '
        IFS= read -r list </dev/tty || exit 130
        local -a parts=()
        IFS=',' read -r -a parts <<< "$list"
        for tool in "${parts[@]}"; do
          tool=${tool//[[:space:]]/}
          [[ -z $tool ]] || toggle_tool "$tool" || true
        done
        show_summary
        ;;
      *) warn 'Choose I, C or Q' ;;
    esac
  done
}

sudo_prefix() {
  if (( EUID == 0 )); then
    ROOT_CMD=()
  elif command -v sudo >/dev/null 2>&1; then
    ROOT_CMD=(sudo)
  else
    die 'Root access is required to install packages (install sudo or run as root).'
  fi
}

install_repo_packages() {
  local -a pkgs=("$@")
  (( ${#pkgs[@]} )) || return 0
  local -a cmd=()
  case $PM in
    pacman)
      cmd=("${ROOT_CMD[@]}" pacman -S --needed)
      (( YES )) && cmd+=(--noconfirm)
      cmd+=(-- "${pkgs[@]}") ;;
    apt)
      cmd=("${ROOT_CMD[@]}" apt-get install)
      (( YES )) && cmd+=(-y)
      cmd+=(-- "${pkgs[@]}") ;;
    dnf)
      cmd=("${ROOT_CMD[@]}" dnf install)
      (( YES )) && cmd+=(-y)
      cmd+=(-- "${pkgs[@]}") ;;
  esac
  "${cmd[@]}"
}

install_aur_package() {
  local pkg=$1 helper=''
  if command -v yay >/dev/null 2>&1; then helper=yay
  elif command -v paru >/dev/null 2>&1; then helper=paru
  else return 1; fi
  if (( EUID == 0 )); then error 'AUR helpers must not run as root'; return 1; fi
  local -a cmd=("$helper" -S --needed)
  (( YES )) && cmd+=(--noconfirm)
  cmd+=(-- "$pkg")
  "${cmd[@]}"
}

make_debian_aliases() {
  [[ $PM == apt ]] || return 0
  local dest="$HOME/.local/bin" name origin
  for name in fd bat; do
    [[ -n ${SELECTED[$name]:-} ]] || continue
    if command -v "$name" >/dev/null 2>&1 || [[ -e $dest/$name || -L $dest/$name ]]; then continue; fi
    case $name in fd) origin=$(command -v fdfind || :) ;; bat) origin=$(command -v batcat || :) ;; esac
    [[ -n $origin ]] || continue
    mkdir -p -- "$dest" || continue
    ln -s -- "$origin" "$dest/$name" && info "Created alias: $dest/$name → $origin"
  done
  case :$PATH: in *":$HOME/.local/bin:"*) ;; *) warn "Add $HOME/.local/bin to PATH to use the new fd/bat aliases." ;; esac
}

# Local/personal tool installation never needs root. Bundled sources are versioned
# within this repository; custom sources must be explicitly supplied by the user.
install_personal_tool() {
  local id=$1 src=$2 bindir="$HOME/.local/bin"
  mkdir -p -- "$bindir" || return 1
  case $id in
    cproj)
      [[ -d $src && -f $src/cproj && -f $src/shell/cproj.bash ]] || {
        error 'CPROJ source requires cproj and shell/cproj.bash'; return 1;
      }
      install -Dm755 -- "$src/cproj" "$bindir/cproj" || return 1
      install -Dm644 -- "$src/shell/cproj.bash" "$HOME/.config/cproj/cproj.bash" || return 1
      if [[ ! -e $HOME/.config/cproj/cproj.conf && -f $src/cproj.conf ]]; then
        install -Dm600 -- "$src/cproj.conf" "$HOME/.config/cproj/cproj.conf" || return 1
      fi
      if (( SHELL_INTEGRATION )); then
        local line='source "$HOME/.config/cproj/cproj.bash"'
        touch -- "$HOME/.bashrc" || return 1
        if ! grep -Fxq -- "$line" "$HOME/.bashrc"; then
          cp -p -- "$HOME/.bashrc" "$HOME/.bashrc.cproj-backup-$(date +%Y%m%d%H%M%S)" || return 1
          printf '\n# CPROJ: project teleportation and automatic venv activation\n%s\n' "$line" >> "$HOME/.bashrc" || return 1
        fi
      else
        warn 'CPROJ: to enable cd/venv in this Bash shell, source ~/.config/cproj/cproj.bash in ~/.bashrc (or use --shell-integration).'
      fi
      ;;
    nadar)
      [[ -d $src && -f $src/nadar && -f $src/nadar.service && -f $src/nadar-remote-watch.timer && -f $src/nadar-remote-watch.service ]] || {
        error 'NADAR source is missing the executable or systemd units'; return 1;
      }
      install -Dm755 -- "$src/nadar" "$bindir/nadar" || return 1
      for unit in nadar.service nadar-remote-watch.service nadar-remote-watch.timer; do
        install -Dm644 -- "$src/$unit" "$HOME/.config/systemd/user/$unit" || return 1
      done
      if [[ ! -e $HOME/.config/nadar/nadar.conf && -f $src/nadar.conf ]]; then
        install -Dm600 -- "$src/nadar.conf" "$HOME/.config/nadar/nadar.conf" || return 1
      fi
      if command -v systemctl >/dev/null 2>&1 && [[ -n ${XDG_RUNTIME_DIR:-} ]]; then
        systemctl --user daemon-reload || warn 'NADAR: could not reload the user systemd manager'
        if (( ENABLE_SERVICES )); then
          systemctl --user enable --now nadar.service nadar-remote-watch.timer || return 1
        fi
      elif (( ENABLE_SERVICES )); then
        warn 'NADAR: no active user systemd manager; units installed but not enabled.'
      fi
      ;;
    srvpulse|cmdvault)
      # CmdVault upstream ships a standalone executable alongside metadata-only
      # pyproject.toml (no packaged CLI entry point). Prefer that executable.
      if [[ -d $src && -f $src/pyproject.toml ]] &&
         ! [[ $id == cmdvault && ( -f $src/cmdvault || -f $src/cmdvault.py ) ]]; then
        install_python_tool "$id" "$src" || return 1
      elif [[ $id == cmdvault ]]; then
        local file=$src
        if [[ -d $src ]]; then
          if [[ -f $src/cmdvault ]]; then file=$src/cmdvault
          elif [[ -f $src/cmdvault.py ]]; then file=$src/cmdvault.py
          else error 'CmdVault source requires cmdvault, cmdvault.py or pyproject.toml'; return 1
          fi
        fi
        [[ -f $file ]] || { error 'CmdVault source is not a regular file'; return 1; }
        if [[ $file == *.py ]] && [[ $(head -c 2 -- "$file") != '#!' ]]; then
          local data_dir="$HOME/.local/share/linux-essentials/cmdvault"
          install -Dm644 -- "$file" "$data_dir/cmdvault.py" || return 1
          printf '#!/usr/bin/env bash\nexec python3 %q "$@"\n' "$data_dir/cmdvault.py" > "$bindir/cmdvault" || return 1
          chmod 755 "$bindir/cmdvault" || return 1
        else
          install -Dm755 -- "$file" "$bindir/cmdvault" || return 1
        fi
      else
        error 'SRVPULSE requires a Python project with pyproject.toml'; return 1
      fi
      ;;
  esac
  case :$PATH: in *":$bindir:"*) ;; *) warn "Add $bindir to PATH to run personal tools." ;; esac
}

install_python_tool() {
  local id=$1 src=$2 venv="$HOME/.local/share/linux-essentials/venvs/$1"
  command -v python3 >/dev/null 2>&1 || { error 'python3 is required'; return 1; }
  mkdir -p -- "$(dirname -- "$venv")" || return 1
  if command -v uv >/dev/null 2>&1; then
    uv venv --allow-existing "$venv" || return 1
    uv pip install --python "$venv/bin/python" -- "$src" || return 1
  else
    if [[ ! -x $venv/bin/python ]]; then
      python3 -m venv "$venv" || { error 'python3 -m venv failed; install python3-venv'; return 1; }
    fi
    "$venv/bin/python" -m pip install -- "$src" || { error 'pip missing in venv; install python3-pip/venv or uv'; return 1; }
  fi
  [[ -x $venv/bin/$id ]] || { error "Python project did not expose CLI '$id'"; return 1; }
  # The wrapper lives at ~/.local/bin; dependencies live in an isolated venv.
  printf '#!/usr/bin/env bash\nexec %q "$@"\n' "$venv/bin/$id" > "$HOME/.local/bin/$id" || return 1
  chmod 755 -- "$HOME/.local/bin/$id"
  if [[ $id == srvpulse && ! -e $HOME/.config/srvpulse/config.toml ]]; then
    if [[ -f $src/config.example.toml ]]; then
      install -Dm600 -- "$src/config.example.toml" "$HOME/.config/srvpulse/config.toml" || return 1
    else
      warn 'SRVPULSE: no config.example.toml in custom source; run srvpulse --init-config.'
    fi
  fi
}

run_install() {
  local -a repo_packages=() aur_packages=() failures=()
  local tool pkg status source
  for tool in "${TOOLS[@]}"; do
    [[ -n ${SELECTED[$tool]:-} ]] || continue
    pkg=${PACKAGE[$tool]}; status=${STATUS[$tool]}
    if is_personal_tool "$tool"; then continue; fi
    case $status in
      missing) repo_packages+=("$pkg") ;;
      'AUR pending') aur_packages+=("${pkg#AUR:}") ;;
      unavailable|'AUR skipped') warn "Skipping $tool ($status; package: $pkg)" ;;
    esac
  done
  if (( DRY_RUN )); then
    info 'DRY RUN: no changes will be made.'
    ((${#repo_packages[@]})) && printf '  Repository install: %s\n' "${repo_packages[*]}"
    ((${#aur_packages[@]})) && printf '  AUR install:        %s\n' "${aur_packages[*]}"
    for tool in "${PERSONAL_TOOLS[@]}"; do
      [[ -n ${SELECTED[$tool]:-} ]] || continue
      if [[ ${STATUS[$tool]} == installed && $UPGRADE_TOOLS != 1 ]]; then continue; fi
      if source=$(personal_source "$tool"); then
        printf '  Personal install:   %-12s from %s\n' "$tool" "$source"
      else
        printf '  Personal missing:   %-12s (provide --source %s=DIR)\n' "$tool" "$tool"
      fi
    done
    return 0
  fi
  if (( ${#repo_packages[@]} )); then
    sudo_prefix
    info "Installing ${#repo_packages[@]} repository packages via $PM..."
    if ! install_repo_packages "${repo_packages[@]}"; then
      warn 'Batch installation failed. Retrying individually to identify problem packages.'
      for pkg in "${repo_packages[@]}"; do
        info "  ↓ $pkg"
        if ! install_repo_packages "$pkg"; then
          failures+=("$pkg")
          error "Install failed: $pkg"
        fi
      done
    fi
  fi
  for pkg in "${aur_packages[@]}"; do
    info "  ↓ AUR:$pkg"
    if ! install_aur_package "$pkg"; then
      failures+=("AUR:$pkg")
      error "AUR install failed: $pkg"
    fi
  done
  make_debian_aliases
  for tool in "${PERSONAL_TOOLS[@]}"; do
    [[ -n ${SELECTED[$tool]:-} ]] || continue
    if [[ ${STATUS[$tool]} == installed && $UPGRADE_TOOLS != 1 ]] && \
       ! { [[ $tool == cproj && $SHELL_INTEGRATION == 1 ]] || [[ $tool == nadar && $ENABLE_SERVICES == 1 ]]; }; then
      continue
    fi
    if ! source=$(personal_source "$tool"); then
      failures+=("$tool:source")
      error "Source for $tool is missing; use --source $tool=/path/to/project (or add vendor/$tool)."
      continue
    fi
    info "Installing personal tool $tool from $source..."
    if ! install_personal_tool "$tool" "$source"; then
      failures+=("$tool:install")
      error "Personal tool installation failed: $tool"
    fi
  done
  refresh_status
  show_summary
  if (( ${#failures[@]} )); then
    error "${#failures[@]} package(s) failed: ${failures[*]}"
    return 1
  fi
  info 'Installation completed. Existing user configuration was preserved (except any requested shell integration).'
}

main() {
  setup_colors
  parse_args "$@"
  detect_os
  refresh_status
  show_banner
  if [[ -n $EXPORT_FILE ]]; then export_tools "$EXPORT_FILE"; return; fi
  if (( SHOW_ALL )); then PROFILE=catalog; show_summary 1; return; fi
  if [[ -n $FROM_FILE ]]; then PROFILE=import; import_tools "$FROM_FILE"
  elif [[ -n $PROFILE ]]; then select_profile "$PROFILE"
  else prompt_profile
  fi
  show_summary
  (( SUMMARY_ONLY )) && return 0
  confirm_install
  run_install
}
main "$@"
