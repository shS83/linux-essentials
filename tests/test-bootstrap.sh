#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
INSTALLER="$HERE/install.sh"
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/home"
cat > "$TMP/os-release" <<'EOF'
NAME="Arch Test"
ID=arch
EOF
cat > "$TMP/bin/pacman" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  -Qq) [[ $2 == git ]] ;;
  -Si) [[ $2 != byobu ]] ;;
  -S)
    printf 'pacman %s\n' "$*" >> "$LE_TEST_INSTALL_LOG"
    if [[ ${LE_TEST_FAIL_BATCH:-0} == 1 && " $* " == *' ncdu '* && " $* " == *' duf '* ]]; then exit 1; fi
    ;;
  *) exit 42 ;;
esac
EOF
cat > "$TMP/bin/yay" <<'EOF'
#!/usr/bin/env bash
printf 'yay %s\n' "$*" >> "$LE_TEST_INSTALL_LOG"
EOF
cat > "$TMP/bin/sudo" <<'EOF'
#!/usr/bin/env bash
"$@"
EOF
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH" HOME="$TMP/home" LE_OS_RELEASE="$TMP/os-release" LE_TEST_INSTALL_LOG="$TMP/install.log"
export NO_COLOR=1
passes=0
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
check() { "$@" || fail "$*"; ((++passes)); }

a=$("$INSTALLER" --profile minimal --summary)
check grep -q 'TOOLKIT SUMMARY  \[minimal\]' <<< "$a"
check grep -q 'AUR' < <("$INSTALLER" --profile desktop --summary)

b=$("$INSTALLER" --profile all --dry-run)
check grep -q 'DRY RUN: no changes' <<< "$b"
check grep -q 'Repository install' <<< "$b"
check grep -q 'AUR skipped' <<< "$b"
[[ ! -e $TMP/install.log ]] || fail 'Dry run installed a package'
((++passes))

c=$("$INSTALLER" --profile all --aur --dry-run)
check grep -q 'AUR:byobu\|AUR install:.*byobu' <<< "$c"

"$INSTALLER" --export "$TMP/catalog.list" >/dev/null
check test -f "$TMP/catalog.list"
check grep -q '^git$' "$TMP/catalog.list"

d=$("$INSTALLER" --import "$TMP/catalog.list" --summary)
check grep -q 'TOOLKIT SUMMARY  \[import\]' <<< "$d"

printf 'git\n' > "$TMP/existing.list"
if "$INSTALLER" --export "$TMP/existing.list" >/dev/null 2>&1; then fail 'Clobbered existing export'; fi
((++passes))
"$INSTALLER" --export "$TMP/existing.list" --force >/dev/null
check grep -q '^git$' "$TMP/existing.list"

cat > "$TMP/bad.list" <<EOF
\$(touch "$TMP/INJECTED")
EOF
if "$INSTALLER" --import "$TMP/bad.list" --dry-run >/dev/null 2>&1; then fail 'Accepted invalid tool id'; fi
[[ ! -e $TMP/INJECTED ]] || fail 'Executed imported text'
((passes+=2))

cat > "$TMP/choice.list" <<'EOF'
ncdu
byobu
EOF
if (( EUID == 0 )); then
  # AUR helpers intentionally refuse to run as root; test repository installs
  # and verify AUR remains opt-in through the dry-run assertion above.
  "$INSTALLER" --import "$TMP/choice.list" --yes > "$TMP/output"
  check grep -q 'ncdu' "$TMP/install.log"
else
  "$INSTALLER" --import "$TMP/choice.list" --yes --aur > "$TMP/output"
  check grep -q 'ncdu' "$TMP/install.log"
  check grep -q 'byobu' "$TMP/install.log"
fi


# One failed package batch should recover by retrying members individually.
printf 'ncdu\nduf\n' > "$TMP/retry.list"
LE_TEST_FAIL_BATCH=1 "$INSTALLER" --import "$TMP/retry.list" --yes > "$TMP/retry.log" 2>&1
check grep -q 'Batch installation failed' "$TMP/retry.log"
check grep -q 'Installation completed' "$TMP/retry.log"

# Invalid whitespace inside an ID must not become a valid tool by concatenation.
printf 'by obu\n' > "$TMP/spaces.list"
if "$INSTALLER" --import "$TMP/spaces.list" --summary >/dev/null 2>&1; then fail 'Accepted invalid embedded whitespace'; fi
((++passes))

# Do not allow a typo in a profile to silently select all tools.
if "$INSTALLER" --profile anything --summary >/dev/null 2>&1; then fail 'Accepted unknown profile'; fi
((++passes))

# OS detection for Debian and Fedora without performing real installs.
cat > "$TMP/os-release" <<'EOF'
ID=ubuntu
ID_LIKE="debian"
EOF
cat > "$TMP/bin/apt-get" <<'EOF'
#!/usr/bin/env bash
printf 'apt-get %s\n' "$*" >> "$LE_TEST_INSTALL_LOG"
EOF
cat > "$TMP/bin/apt-cache" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "$TMP/bin/apt-get" "$TMP/bin/apt-cache"
e=$("$INSTALLER" --profile minimal --summary)
check grep -q 'fd-find' <<< "$e"
check grep -q 'openssh-client' <<< "$e"

cat > "$TMP/os-release" <<'EOF'
ID=fedora
EOF
cat > "$TMP/bin/dnf" <<'EOF'
#!/usr/bin/env bash
printf 'dnf %s\n' "$*" >> "$LE_TEST_INSTALL_LOG"
EOF
chmod +x "$TMP/bin/dnf"
f=$("$INSTALLER" --profile server --summary)
check grep -q 'openssh-clients' <<< "$f"
check grep -q 'byobu' <<< "$f"

printf 'PASS: %d bootstrap assertions\n' "$passes"
