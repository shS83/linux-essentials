#!/usr/bin/env bash
# cmedia V2 installer for shS83/cmedia (Kitty/Sixel/Chafa untouched).
set -Eeuo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
if (( EUID == 0 )); then echo 'Asenna tavallisena käyttäjänä, ei rootina.' >&2; exit 1; fi
for cmd in git uv python3; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "Puuttuva komento: $cmd" >&2; exit 1; }
done

project=${1:-}
if [[ -z $project && -f ./src/cmedia/app.py ]]; then
    project=$PWD
fi
if [[ -z $project ]]; then
    project=$(mktemp -d -t cmedia-v2-XXXXXXXX)
    trap 'rm -rf -- "$project"' EXIT
    echo 'Haetaan shS83/cmedia GitHubista...'
    git clone -q --depth 1 --branch root https://github.com/shS83/cmedia.git "$project"
else
    project=$(realpath -e -- "$project")
fi
[[ -f $project/src/cmedia/app.py && -f $project/pyproject.toml ]] || {
    echo "Virhe: ei cmedia-projektin juurihakemisto: $project" >&2; exit 1;
}

python3 "$here/patch_cmedia.py" "$project"
install -d -m 755 "$HOME/.local/bin"
UV_TOOL_BIN_DIR="$HOME/.local/bin" uv tool install --force "$project"
[[ -x $HOME/.local/bin/cmedia ]] || { echo 'cmedia-käynnistintä ei syntynyt' >&2; exit 1; }
echo "Asennettu: $HOME/.local/bin/cmedia"
echo 'Käynnistä: cmedia ~/Pictures'
echo 'Huom: omaan klooniin tehdyt muutokset voi tarkistaa git diff -komennolla.'
