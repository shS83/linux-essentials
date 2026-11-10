#!/usr/bin/env bash
# cmedia-user installer: patch existing sources, install command in ~/.local/bin
set -Eeuo pipefail

fail() { printf 'Virhe: %s\n' "$*" >&2; exit 1; }
command -v git >/dev/null || fail 'git puuttuu (Arch: sudo pacman -S git)'
command -v uv >/dev/null || fail 'uv puuttuu (Arch: sudo pacman -S uv)'
command -v python3 >/dev/null || fail 'python3 puuttuu'

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
project="${1:-}"
if [[ -n "$project" ]]; then
    [[ -f "$project/src/cmedia/app.py" ]] || fail 'Anna cmedia-projektin juurihakemisto.'
elif [[ -f "./src/cmedia/app.py" ]]; then
    project="$PWD"
else
    project="$(mktemp -d -t cmedia-install-XXXXXXXX)"
    trap 'rm -rf -- "$project"' EXIT
    printf 'Ladataan cmedia (root-haara) GitHubista...\n'
    git clone --quiet --depth=1 --branch root https://github.com/shS83/cmedia.git "$project" \
        || fail 'GitHubin lataus epäonnistui. Käytä asenninta oman kloonisi kanssa: ./install.sh ~/Code/cmedia'
fi

printf 'Korjataan listapalkkien piirtäminen...\n'
python3 "$script_dir/patch_cmedia.py" "$project"

mkdir -p "$HOME/.local/bin"
printf 'Asennetaan cmedia-käynnistin polkuun %s/.local/bin/cmedia ...\n' "$HOME"
UV_TOOL_BIN_DIR="$HOME/.local/bin" uv tool install --force "$project" \
    || fail 'uv tool install epäonnistui; lähdekoodi on silti korjattu.'

[[ -x "$HOME/.local/bin/cmedia" ]] || fail 'Käynnistin puuttuu asennuksen jälkeen.'
printf '\nValmis! Käynnistä missä tahansa hakemistossa: cmedia\n'
if [[ ":${PATH:-}:" != *":$HOME/.local/bin:"* ]]; then
    printf 'Lisää PATHiin: export PATH="$HOME/.local/bin:$PATH"\n'
fi
printf '\nMuistutus: tarkista muutokset ja tee Git-commit/push, jos asensit oman projektikloonin kautta.\n'
