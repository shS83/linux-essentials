#!/usr/bin/env bash
set -Eeuo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/home" "$tmp/source/src/cmedia"
printf '[project]\nname="cmedia"\n' > "$tmp/source/pyproject.toml"
{
    printf 'from __future__ import annotations\n'
    cat "$root/tests/fixture_v1_draw.txt"
    printf '\nKITTY_PACKET = None\n'
} > "$tmp/source/src/cmedia/app.py"
cat > "$tmp/bin/uv" <<'MOCK'
#!/usr/bin/env bash
[[ "$1 $2" == 'tool install' ]] || exit 10
[[ $3 == --force ]] || exit 11
[[ -f $4/src/cmedia/app.py ]] || exit 12
[[ -n ${UV_TOOL_BIN_DIR:-} ]] || exit 13
printf '#!/usr/bin/env bash\necho cmedia test\n' > "$UV_TOOL_BIN_DIR/cmedia"
chmod +x "$UV_TOOL_BIN_DIR/cmedia"
MOCK
chmod +x "$tmp/bin/uv"
HOME="$tmp/home" PATH="$tmp/bin:$PATH" "$root/install.sh" "$tmp/source"
test -x "$tmp/home/.local/bin/cmedia"
grep -q CMEDIA_DIFF_RENDER_V2 "$tmp/source/src/cmedia/app.py"
test -f "$tmp/source/src/cmedia/app.py.before-diff-v2.bak"
HOME="$tmp/home" PATH="$tmp/bin:$PATH" "$root/install.sh" "$tmp/source" >/dev/null
echo 'PASS: installer creates launcher, preserves backup and is repeatable'
