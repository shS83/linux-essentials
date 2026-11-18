import hashlib
from syntax import detect_syntax
import os
import subprocess
import shutil
import time
from database import save_clipboard
from security import is_secret
from syntax import colorize


def process_clipboard(content: str) -> bool:
    lexer = detect_syntax(content)
    if not content.strip():
        return False
    if is_secret(content):
        print("\033[1;31m[REDACTED]\033[0m")
        return False
    row_id = save_clipboard(content)
    print(f"\033[1;34mClipvault: \033[1;32mSaved entry \033[1;36m#{row_id}\033[0m")
    print(colorize(content, theme="material"), end="")
    return True


def get_clipboard() -> str:
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
        command = ["wl-paste", "--no-newline"]
    elif os.environ.get("DISPLAY") and shutil.which("xclip"):
        command = ["xclip", "-selection", "clipboard", "-o"]
    else:
        raise RuntimeError("Clipboard backend unavailable")
    return subprocess.check_output(command, text=True)


def main():
    previous_hash = None
    try:
        while True:
            content = get_clipboard()
            current_hash = hashlib.sha256(content.encode("utf-8")).digest()
            if current_hash != previous_hash:
                process_clipboard(content)
                previous_hash = current_hash
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nClipvault stopped.")

if __name__ == "__main__":
    main()
