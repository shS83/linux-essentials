#!/usr/bin/env bash
# Offline end-to-end installer test for cmedia source checkout and GitHub fallback.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
mkdir -p "$TMP/home" "$TMP/bin" "$TMP/project cmedia/src/cmedia"
printf 'ID=arch\n' > "$TMP/os-release"
cat > "$TMP/bin/pacman" <<'SCRIPT'
#!/usr/bin/env bash
case "$1" in
  -Qq|-Si) exit 0;;
  -S) exit 0;;
esac
SCRIPT
cat > "$TMP/bin/uv" <<'SCRIPT'
#!/usr/bin/env bash
[[ "$1" == tool && "$2" == install && "$3" == --force ]] || exit 22
[[ -f "$4/src/cmedia/app.py" ]] || exit 23
mkdir -p "$UV_TOOL_BIN_DIR"
cat > "$UV_TOOL_BIN_DIR/cmedia" <<'EOF'
#!/usr/bin/env bash
printf 'MOCK-CMEDIA\n'
EOF
chmod +x "$UV_TOOL_BIN_DIR/cmedia"
SCRIPT
cat > "$TMP/bin/git" <<'SCRIPT'
#!/usr/bin/env bash
if [[ "$1" == clone ]]; then
  [[ "$*" == *'https://github.com/shS83/cmedia.git'* ]] || exit 24
  dest=${!#}
  mkdir -p "$dest"
  cp -a "$LE_TEST_SOURCE/." "$dest/"
  printf '%s\n' "$*" >> "$LE_TEST_GIT_LOG"
else
  exit 25
fi
SCRIPT
chmod +x "$TMP/bin/"*
cat > "$TMP/project cmedia/pyproject.toml" <<'TOML'
[project]
name = "cmedia"
version = "0.1.0"
[project.scripts]
cmedia = "cmedia:main"
TOML
cat > "$TMP/project cmedia/src/cmedia/app.py" <<'PY'
from pathlib import Path
ESC = "\033"
def safe_text(s): return s
class Terminal:
    def size(self): return (100, 30)
    def write(self, s): pass
    def screen(self, title: str, hint: str) -> tuple[int, int]:
        width, height = self.size()
        self.write(f'{ESC}[2J{title}{hint}')
        return width, height
    def park(self): pass
    def image(self, data, row, col): pass
class PreviewCache:
    def get(self, *args): return ([], None)
def media_kind(_item): return None
def box(*args): pass
def draw_browser(term: Terminal, directory: Path, paths: list[Path], index: int,
                 format_: str, cache: PreviewCache, video_window: bool = False, message: str = '') -> None:
    term.screen(str(directory), message)
KITTY_PACKET = None
def directory_dialog(term: Terminal, directory: Path) -> Path | None:
    """Read an absolute path or a path relative to the current directory."""
    return directory
def present_frame(term: Terminal, path: Path, frame: bytes, format_: str, hint: str,
                  _other: int = 0) -> None:
    """Keep the old frame visible until the complete replacement is ready."""
    term.screen(str(path), hint)
PY

export PATH="$TMP/bin:$PATH" HOME="$TMP/home" LE_OS_RELEASE="$TMP/os-release" NO_COLOR=1
export LE_TEST_SOURCE="$TMP/project cmedia" LE_TEST_GIT_LOG="$TMP/git.log"
passes=0
check() { "$@" || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; ((++passes)); }

printf 'cmedia\n' > "$TMP/only-cmedia.list"
summary=$("$ROOT/install.sh" --profile developer --summary)
check grep -q 'cmedia' <<< "$summary"
check grep -q 'Cmedia\|cmedia.*local pending' <<< "$summary"

out=$("$ROOT/install.sh" --import "$TMP/only-cmedia.list" --dry-run --source "cmedia=$TMP/project cmedia")
check grep -q 'Personal install:.*cmedia' <<< "$out"
check grep -q 'cmedia' <<< "$out"
[[ ! -e "$HOME/.local/bin/cmedia" ]] || { echo 'Dry run modified files' >&2; exit 1; }
((++passes))

"$ROOT/install.sh" --import "$TMP/only-cmedia.list" --yes --source "cmedia=$TMP/project cmedia" > "$TMP/install.out"
check test -x "$HOME/.local/bin/cmedia"
check grep -q 'MOCK-CMEDIA' <("$HOME/.local/bin/cmedia")
check grep -q 'CMEDIA_DIFF_RENDER_V1' "$TMP/project cmedia/src/cmedia/app.py"
check test -f "$TMP/project cmedia/src/cmedia/app.py.bak"
check grep -q '2J' "$TMP/project cmedia/src/cmedia/app.py.bak"
check python3 -m py_compile "$TMP/project cmedia/src/cmedia/app.py"

"$ROOT/install.sh" --import "$TMP/only-cmedia.list" --yes --upgrade-tools \
  --source "cmedia=$TMP/project cmedia" > "$TMP/upgrade.out"
check grep -q 'jo asennettu' "$TMP/upgrade.out"

# Without an explicit or conventional local source, fetch upstream into temp.
rm -f "$HOME/.local/bin/cmedia"
"$ROOT/install.sh" --import "$TMP/only-cmedia.list" --yes > "$TMP/fallback.out"
check test -x "$HOME/.local/bin/cmedia"
check test -s "$TMP/git.log"
check grep -q 'GitHubista' "$TMP/fallback.out"

printf 'PASS: %d cmedia installation assertions\n' "$passes"
