#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
mkdir -p "$TMP/home" "$TMP/bin" "$TMP/source cmdvault/src/visuals"
printf 'ID=arch\n' > "$TMP/os-release"
cat > "$TMP/bin/pacman" <<'SH'
#!/usr/bin/env bash
case "$1" in -Qq|-Si|-S) exit 0;; *) exit 1;; esac
SH
cat > "$TMP/source cmdvault/install.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
test -s cmdvault.png
mkdir -p "$HOME/.local/share/cmdvault/app" "$HOME/.local/bin"
install -m644 cmdvault.png "$HOME/.local/share/cmdvault/app/cmdvault.png"
cat > "$HOME/.local/bin/cmdvault" <<'EOF'
#!/bin/sh
exit 0
EOF
chmod +x "$HOME/.local/bin/cmdvault"
SH
printf '#!/bin/sh\n' > "$TMP/source cmdvault/cmdvault"
printf '# -*- python -*-\n' > "$TMP/source cmdvault/src/visuals/picker.py"
chmod +x "$TMP/bin/pacman" "$TMP/source cmdvault/install.sh"
export HOME="$TMP/home" PATH="$TMP/bin:$PATH" LE_OS_RELEASE="$TMP/os-release" NO_COLOR=1
printf 'cmdvault\n' > "$TMP/only.list"
"$ROOT/install.sh" --import "$TMP/only.list" --yes --source "cmdvault=$TMP/source cmdvault" > "$TMP/output"
test -s "$HOME/.local/share/cmdvault/app/cmdvault.png"
python3 - "$ROOT/vendor/cmdvault/cmdvault.png" "$HOME/.local/share/cmdvault/app/cmdvault.png" <<'CHECK_SHA'
import sys, pathlib, hashlib
p=pathlib.Path(sys.argv[1]); q=pathlib.Path(sys.argv[2]); a=p.read_bytes(); b=q.read_bytes()
assert a==b
assert hashlib.sha1(f'blob {len(a)}\0'.encode()+a).hexdigest() == '8cd4b766f396b2621de73e9d3f1aeb0d44b77d2b'
CHECK_SHA
test ! -e "$TMP/source cmdvault/cmdvault.png"
grep -q 'restored missing logo' "$TMP/output"
"$ROOT/install.sh" --import "$TMP/only.list" --yes --upgrade-tools \
  --source "cmdvault=$TMP/source cmdvault" > /dev/null
cmp "$ROOT/vendor/cmdvault/cmdvault.png" "$HOME/.local/share/cmdvault/app/cmdvault.png"
echo 'PASS: bundled CmdVault PNG SHA1, independent checkout, restored install, upgrade'
