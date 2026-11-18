# Clipvault v0.1.0 (bundled snapshot + GUI hotfix)

Contains the core application source from shS83/Clipvault and the latest
November 16 GUI/statusbar fix, art and PostgreSQL row action. The app uses
PostgreSQL `dbname=clipvault user=clipvault host=localhost`. No database
or schema is created by Linux Essentials.

Install via `./install.sh --import clipvault.list --yes`; run `clipvault` in
a graphical session or `clipvault --cli` to use the terminal watcher.
Python >=3.15, uv, PostgreSQL setup, Qt/PySide6 dependencies required.
No autostart service is installed. Clipboard contents are stored in plaintext.
