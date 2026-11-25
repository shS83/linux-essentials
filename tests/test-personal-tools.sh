#!/usr/bin/env bash
# Exercise bundled tools without installing system packages or connecting to servers.
set -euo pipefail
SOURCE_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
ROOT="$TMP/repo"
mkdir -p "$ROOT/vendor/cmdvault"
cp "$SOURCE_ROOT/install.sh" "$ROOT/install.sh"
for bundled in cproj nadar srvpulse gitpublish cmedia dotfiles-sync clipvault taskman musik; do
  cp -a "$SOURCE_ROOT/vendor/$bundled" "$ROOT/vendor/"
done
cp "$SOURCE_ROOT/vendor/cmdvault/cmdvault.png" "$ROOT/vendor/cmdvault/cmdvault.png"
mkdir -p "$TMP/home" "$TMP/bin" "$TMP/source cmdvault" "$TMP/runtime"
mkdir -p "$TMP/taskman-source"
cp "$ROOT/vendor/taskman/CMakeLists.txt" "$ROOT/vendor/taskman/main.cpp" \
  "$ROOT/vendor/taskman/neon.cpp" "$ROOT/vendor/taskman/logo.png" "$TMP/taskman-source/"
mkdir -p "$TMP/musik-source/musik"
cp "$ROOT/vendor/musik/pyproject.toml" "$ROOT/vendor/musik/uv.lock" \
  "$ROOT/vendor/musik/musik.py" "$TMP/musik-source/"
cp -a "$ROOT/vendor/musik/musik/." "$TMP/musik-source/musik/"
printf 'ID=arch\n' > "$TMP/os-release"
cat > "$TMP/bin/pacman" <<'SCRIPT'
#!/usr/bin/env bash
case $1 in
  -Qq) exit 1;;
  -Si) exit 0;;
  -S) printf '%s\n' "$*" >> "$LE_TEST_LOG"; exit 0;;
  *) echo 'Unexpected pacman invocation' >&2; exit 1;;
esac
SCRIPT
cat > "$TMP/bin/sudo" <<'SCRIPT'
#!/usr/bin/env bash
exec "$@"
SCRIPT
cat > "$TMP/bin/systemctl" <<'SCRIPT'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$LE_TEST_LOG"
SCRIPT
cat > "$TMP/bin/uv" <<'SCRIPT'
#!/usr/bin/env bash
if [[ $1 == sync ]]; then
  shift
  while (( $# )); do
    if [[ $1 == --project ]]; then project=$2; shift 2; else shift; fi
  done
  mkdir -p "$project/.venv/bin"
  printf '#!/usr/bin/env bash\necho MOCK-MUSIK\n' > "$project/.venv/bin/python"
  chmod +x "$project/.venv/bin/python"
  exit 0
fi
case "$1 $2" in
  'venv --allow-existing')
    mkdir -p "$3/bin"
    : > "$3/bin/python"
    ;;
  'pip install')
    p=$4
    v=${p%/bin/python}
    mkdir -p "$v/bin"
    printf '#!/usr/bin/env bash\necho MOCK-SRVPULSE\n' > "$v/bin/srvpulse"
    chmod +x "$v/bin/srvpulse"
    ;;
  *) echo "Unexpected uv: $*" >&2; exit 1;;
esac
SCRIPT
cat > "$TMP/bin/cmake" <<'SCRIPT'
#!/usr/bin/env bash
if [[ $1 == -S ]]; then
  shift
  while (( $# )); do
    if [[ $1 == -B ]]; then build=$2; shift 2; else shift; fi
  done
  mkdir -p "$build"
  for name in taskman taskman-cli; do
    printf '#!/usr/bin/env bash\necho %s\n' "$name" > "$build/$name"
    chmod +x "$build/$name"
  done
  printf 'mock logo\n' > "$build/logo.png"
  exit 0
fi
[[ $1 == --build ]] || { echo "Unexpected cmake args: $*" >&2; exit 1; }
SCRIPT
cat > "$TMP/source cmdvault/cmdvault" <<'SCRIPT'
#!/usr/bin/env bash
echo CMDVAULT
SCRIPT
chmod +x "$TMP/bin/"* "$TMP/source cmdvault/cmdvault"
export HOME="$TMP/home" PATH="$TMP/bin:$PATH" XDG_RUNTIME_DIR="$TMP/runtime"
export LE_OS_RELEASE="$TMP/os-release" LE_TEST_LOG="$TMP/actions.log" NO_COLOR=1
passes=0
check() { "$@" || { echo "FAIL: $*" >&2; exit 1; }; ((++passes)); }

summary=$("$ROOT/install.sh" --profile developer --summary)
check grep -q 'lsd' <<< "$summary"
check grep -q 'cproj' <<< "$summary"
check grep -q 'cmdvault.*source needed' <<< "$summary"
check grep -q 'nadar' <<< "$summary"
check grep -q 'srvpulse' <<< "$summary"
check grep -q 'gitpublish.*local pending' <<< "$summary"
check grep -q 'gh' <<< "$summary"
check grep -q 'taskman' <<< "$summary"

# Only local tool IDs; no attempt to install repository packages.
printf 'cproj\ncmdvault\nnadar\nsrvpulse\ngitpublish\ntaskman\nmusik\n' > "$TMP/local.list"
dry=$("$ROOT/install.sh" --import "$TMP/local.list" --dry-run --source "cmdvault=$TMP/source cmdvault" --source "taskman=$TMP/taskman-source" --source "musik=$TMP/musik-source")
check grep -q 'Personal install:.*cmdvault' <<< "$dry"
check grep -q 'Personal install:.*gitpublish' <<< "$dry"
check grep -q '^gh .*github-cli' <<< "$dry"
check grep -q 'cmake' <<< "$dry"
check grep -q 'postgresql-dev' <<< "$dry"
check grep -q 'uv' <<< "$dry"
[[ ! -e $HOME/.local/bin/cproj ]] || exit 1
((++passes))

"$ROOT/install.sh" --import "$TMP/local.list" --yes --shell-integration --enable-services \
  --source "cmdvault=$TMP/source cmdvault" --source "taskman=$TMP/taskman-source" \
  --source "musik=$TMP/musik-source" > "$TMP/install.out"
check test -x "$HOME/.local/bin/cproj"
check test -x "$HOME/.local/bin/cmdvault"
check test -x "$HOME/.local/bin/nadar"
check test -x "$HOME/.local/bin/srvpulse"
check test -x "$HOME/.local/bin/gitpublish"
check test -x "$HOME/.local/bin/taskman"
check test -x "$HOME/.local/bin/taskman-cli"
check grep -q 'taskman' <("$HOME/.local/bin/taskman")
check grep -q 'taskman-cli' <("$HOME/.local/bin/taskman-cli")
check test -x "$HOME/.local/bin/musik"
check grep -q 'MOCK-MUSIK' <("$HOME/.local/bin/musik")
check cmp "$ROOT/vendor/gitpublish/gitpublish" "$HOME/.local/bin/gitpublish"
check test -r "$HOME/.config/cproj/cproj.bash"
check test -r "$HOME/.config/cproj/cproj.conf"
check test -r "$HOME/.config/nadar/nadar.conf"
check test -r "$HOME/.config/systemd/user/nadar.service"
check test -r "$HOME/.config/systemd/user/nadar-remote-watch.timer"
check test -r "$HOME/.config/srvpulse/config.toml"
check grep -q 'nadar-remote-watch.timer' "$TMP/actions.log"
check grep -q 'source "\$HOME/.config/cproj/cproj.bash"' "$HOME/.bashrc"
check grep -q 'MOCK-SRVPULSE' <("$HOME/.local/bin/srvpulse")
check grep -q 'gitpublish' <("$HOME/.local/bin/gitpublish" --help)

# Do not overwrite configs or duplicate shell integration lines.
printf 'custom=true\n' > "$HOME/.config/cproj/cproj.conf"
"$ROOT/install.sh" --import "$TMP/local.list" --yes --shell-integration --enable-services \
  --upgrade-tools --source "cmdvault=$TMP/source cmdvault" --source "taskman=$TMP/taskman-source" \
  --source "musik=$TMP/musik-source" > /dev/null
check grep -q '^custom=true$' "$HOME/.config/cproj/cproj.conf"
[[ $(grep -cF 'source "$HOME/.config/cproj/cproj.bash"' "$HOME/.bashrc") == 1 ]] || exit 1
((++passes))

# New checkout without a cmdvault source must fail visibly, not install a fake.
rm -f "$HOME/.local/bin/cmdvault"
cat > "$TMP/only-vault.list" <<'EOF2'
cmdvault
EOF2
if "$ROOT/install.sh" --import "$TMP/only-vault.list" --yes > "$TMP/missing.out" 2>&1; then
  echo 'FAIL: missing cmdvault source was silently accepted' >&2; exit 1
fi
check grep -q 'Source for cmdvault is missing' "$TMP/missing.out"

printf 'PASS: %s personal-tool assertions\n' "$passes"
