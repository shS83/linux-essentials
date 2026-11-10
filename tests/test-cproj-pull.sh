#!/usr/bin/env bash
# Offline integration test for CPROJ bulk Git pulls.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
TEMP=$(mktemp -d)
trap 'rm -rf -- "$TEMP"' EXIT
export HOME="$TEMP/home" XDG_CONFIG_HOME="$TEMP/home/.config" XDG_CACHE_HOME="$TEMP/home/.cache" XDG_STATE_HOME="$TEMP/home/.local/state"
mkdir -p "$HOME/Code" "$XDG_CONFIG_HOME/cproj"
CATALOG="$ROOT/vendor/cproj/cproj"
cat > "$XDG_CONFIG_HOME/cproj/cproj.conf" <<'CONF'
CPROJ_ROOTS=("$HOME/Code")
CPROJ_MAX_DEPTH=5
CPROJ_CACHE_TTL=0
CPROJ_PREVIEW_LINES=10
CPROJ_AUTO_VENV=0
CONF
export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@example.invalid GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@example.invalid

create_repo() {
    local name=$1
    git init -q --bare "$TEMP/${name}.git"
    git clone -q "$TEMP/${name}.git" "$HOME/Code/$name"
    git -C "$HOME/Code/$name" -c user.name=test -c user.email=test@example.invalid commit -q --allow-empty -m init
    git -C "$HOME/Code/$name" push -q -u origin HEAD
    git clone -q "$TEMP/${name}.git" "$TEMP/${name}-other"
}
advance_remote() {
    local name=$1
    printf '%s\n' "new version: $name" > "$TEMP/${name}-other/changed.txt"
    git -C "$TEMP/${name}-other" add changed.txt
    git -C "$TEMP/${name}-other" commit -q -m update
    git -C "$TEMP/${name}-other" push -q origin HEAD
}
create_repo clean
create_repo dirty
create_repo detached
create_repo diverged
advance_remote clean
advance_remote dirty
advance_remote diverged
printf local > "$HOME/Code/dirty/untracked.txt"
git -C "$HOME/Code/detached" checkout -q --detach HEAD
git -C "$HOME/Code/diverged" commit -q --allow-empty -m local-commit
# Repo without upstream and a non-Git project should be skipped.
mkdir -p "$HOME/Code/nonrepo" "$HOME/Code/clean/nested"
printf 'all:\n\t@true\n' > "$HOME/Code/nonrepo/Makefile"
printf 'all:\n\t@true\n' > "$HOME/Code/clean/nested/Makefile"
printf 'nested/\n' >> "$HOME/Code/clean/.git/info/exclude"
git init -q "$HOME/Code/no-upstream"
git -C "$HOME/Code/no-upstream" commit -q --allow-empty -m local

"$CATALOG" --refresh > /dev/null
old_clean=$(git -C "$HOME/Code/clean" rev-parse HEAD)
preview=$("$CATALOG" --pull-all --dry-run)
grep -q 'PLAN.*clean' <<< "$preview"
grep -q 'SKIP.*dirty' <<< "$preview"
grep -q 'SKIP.*detached' <<< "$preview"
grep -q 'SKIP.*no-upstream' <<< "$preview"
[[ $(git -C "$HOME/Code/clean" rev-parse HEAD) == "$old_clean" ]]
[[ $(grep -c 'PLAN.*clean' <<< "$preview") == 1 ]]

if output=$("$CATALOG" --pull-all); then
    echo 'Expected divergent repository to cause nonzero result' >&2
    exit 1
fi
grep -q 'UPD.*clean' <<< "$output"
grep -q 'SKIP.*dirty' <<< "$output"
grep -q 'FAIL.*diverged' <<< "$output"
grep -q 'Repos: 5  updated: 1  current: 0  skipped: 3  errors: 1' <<< "$output"
[[ $(git -C "$HOME/Code/clean" rev-parse HEAD) != "$old_clean" ]]
[[ $(git -C "$HOME/Code/clean" rev-parse HEAD) == $(git -C "$TEMP/clean-other" rev-parse HEAD) ]]
[[ -e $HOME/Code/dirty/untracked.txt ]]

# The sourced Bash wrapper must not interpret status text as a cd destination.
export PATH="$ROOT/vendor/cproj:$PATH"
mkdir -p "$TEMP/bin" && ln -s "$CATALOG" "$TEMP/bin/cproj"
export PATH="$TEMP/bin:$PATH"
# Source in a child shell so command/builtin state is isolated.
bash -c 'source "$1"; before=$PWD; cproj --pull-all --dry-run >/dev/null; [[ $PWD == "$before" ]]' \
    bash "$ROOT/vendor/cproj/shell/cproj.bash"
[[ $("$CATALOG" --version) == 0.2.0 ]]
echo 'PASS: CPROJ --pull-all offline Git tests'
