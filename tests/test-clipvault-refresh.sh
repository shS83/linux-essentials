#!/usr/bin/env bash
# Fully offline tests for Clipvault install and latest GitHub source selection.
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
mkdir -p "$TMP/home" "$TMP/bin" "$TMP/source" "$TMP/runtime"
cat > "$TMP/os-release" <<'EOF'
ID=arch
EOF
cat > "$TMP/bin/pacman" <<'EOF'
#!/usr/bin/env bash
case $1 in
  -Qq) exit 1;;
  -Si) exit 0;;
  -S) echo "PACMAN:$*" >> "$LE_TEST_LOG";;
esac
EOF
cat > "$TMP/bin/uv" <<'EOF'
#!/usr/bin/env bash
[[ $1 == sync && $2 == --project ]] || { echo "unexpected uv args: $*" >&2; exit 2; }
mkdir -p "$3/.venv/bin"
printf '#!/usr/bin/env bash\necho MOCK-CLIPVAULT "$@"\n' > "$3/.venv/bin/python"
chmod +x "$3/.venv/bin/python"
printf 'UV:%s\n' "$*" >> "$LE_TEST_LOG"
EOF
cat > "$TMP/bin/git" <<'EOF'
#!/usr/bin/env bash
if [[ ${1:-} == clone ]]; then
  printf 'GIT:%s\n' "$*" >> "$LE_TEST_LOG"
  repo=${@: -2:1}; dest=${@: -1}
  case $repo in
    *cproj.git) cp -a "$LE_TEST_ROOT/vendor/cproj" "$dest";;
    *Clipvault.git) cp -a "$LE_TEST_FIXTURE" "$dest";;
    *) echo "unexpected GitHub repo: $repo" >&2; exit 1;;
  esac
  mkdir -p "$dest/.git"
  exit 0
fi
if [[ $1 == -C && ${3:-} == rev-parse ]]; then
  echo 'aabbccddeeff'; exit 0
fi
exec "$REAL_GIT" "$@"
EOF
chmod +x "$TMP/bin/"*
export REAL_GIT=$(command -v git) LE_TEST_ROOT="$ROOT" LE_TEST_LOG="$TMP/actions.log" LE_TEST_FIXTURE="$TMP/source"
export LE_OS_RELEASE="$TMP/os-release" NO_COLOR=1
export HOME="$TMP/home" XDG_RUNTIME_DIR="$TMP/runtime" PATH="$TMP/bin:$PATH"
cat > "$TMP/source/database.py" <<'EOF'
CONNINFO = 'dbname=clipvault user=clipvault host=localhost'
EOF
cat > "$TMP/source/clipvault_gui.py" <<'EOF'
print('GUI')
EOF
cat > "$TMP/source/clipvault.py" <<'EOF'
print('CLI')
EOF
cat > "$TMP/source/pyproject.toml" <<'EOF'
[project]
name = 'clipvault'
version = '0.1.0'
requires-python = '>=3.15'
EOF
printf 'clipvault\n' > "$TMP/list"
result=$("$ROOT/install.sh" --import "$TMP/list" --dry-run --latest)
grep -q 'GitHub shS83/Clipvault' <<< "$result"
[[ ! -e $TMP/actions.log ]] || { echo 'dry-run caused a tool call' >&2; exit 1; }
result=$("$ROOT/install.sh" --import "$TMP/list" --yes --source "clipvault=$TMP/source")
[[ -x $HOME/.local/bin/clipvault ]]
[[ -x $HOME/.local/share/linux-essentials/clipvault/app/.venv/bin/python ]]
[[ $($HOME/.local/bin/clipvault) == MOCK-CLIPVAULT* ]]
[[ $($HOME/.local/bin/clipvault --cli) == MOCK-CLIPVAULT* ]]
# Existing database config is preserved during upgrades.
printf 'CONNINFO = "custom postgres credentials"\n' > "$HOME/.local/share/linux-essentials/clipvault/app/database.py"
"$ROOT/install.sh" --import "$TMP/list" --yes --upgrade-tools --source "clipvault=$TMP/source" >/dev/null
grep -q 'custom postgres' "$HOME/.local/share/linux-essentials/clipvault/app/database.py"
# Bundled overlay auto-clones its core source but installs the newer GUI patch.
rm -f "$HOME/.local/bin/clipvault"
"$ROOT/install.sh" --import "$TMP/list" --yes >/dev/null
cmp "$ROOT/vendor/clipvault/clipvault_gui.py" "$HOME/.local/share/linux-essentials/clipvault/app/clipvault_gui.py"
# GitHub latest must never change a local developer checkout.
printf 'cproj\n' > "$TMP/list"
mkdir -p "$HOME/Code/cproj"
printf 'ORIGINAL\n' > "$HOME/Code/cproj/not-pushed.txt"
"$ROOT/install.sh" --import "$TMP/list" --yes --latest >/dev/null
[[ -x $HOME/.local/bin/cproj ]]
grep -q 'GIT:clone' "$TMP/actions.log"
[[ $(cat "$HOME/Code/cproj/not-pushed.txt") == ORIGINAL ]]
# The CLI must use the fetched current source rather than bundled source.
[[ $("$HOME/.local/bin/cproj" --version) == 0.2.1 ]]
echo 'PASS: 12 Clipvault/--latest assertions'
