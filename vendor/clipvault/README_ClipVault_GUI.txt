ClipVault — Steampunk / Purple GUI
================================

Files:
  clipvault_gui.py     redesigned PySide6 interface (English)
  clipvault.png        transparent golden/purple ClipVault logo
  database_actions.py adds PostgreSQL row deletion

Place all three files in your ~/Code/Clipvault project directory,
next to your existing database.py, security.py and syntax.py.

The existing modules must expose:
  database.py: CONNINFO, get_history(limit), save_clipboard(content)
  security.py: is_secret(content)
  syntax.py: detect_syntax(content), sanitize_terminal(content)

Install/check dependencies:
  uv add pyside6 pygments 'psycopg[binary]'

Start:
  uv run python clipvault_gui.py

Features:
  - Full-width steampunk logo above the panes
  - Violet-gold gradient panels and highlighted history selection
  - Dynamic fuzzy subsequence search (Ctrl+F)
  - Add clipboard entry (Ctrl+N)
  - Copy selected entry (Ctrl+Shift+C or double-click)
  - Delete selected entry from PostgreSQL (Delete while history list focused)
  - English confirmation dialog showing the exact entry ID before deletion
    (Cancel is the default; Esc cancels)
  - Refresh history (F5)
  - Pause/resume monitoring (button or tray menu)
  - Syntax-highlighted preview with Auto / Python / Bash / C++ /
    Rust / JSON / Plain-text selection and material style
  - System tray minimization / restore / quit

Notes:
  - The GUI captures plain text only. No image capture or cloud sync.
  - Deleting a record always asks for confirmation, by button or keyboard.
  - Stored content is plaintext in PostgreSQL. The heuristic secret
    filter is not a complete security boundary. Avoid real passwords.
  - Clipboard availability on Wayland varies with compositor and session.
  - Only Python syntax was checked in the build environment; no Qt
    desktop runtime was available for an interactive GUI test.
  - Existing database.py/security.py/syntax.py are NOT overwritten.
