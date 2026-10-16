# Bring your own CmdVault source

CmdVault was mentioned as an existing personal tool, but no CmdVault source
code is present in the conversation artifacts. The installer therefore
requires its existing source and does not generate a fake replacement.

Place `cmdvault`, `cmdvault.py`, or a Python project with `pyproject.toml`
under this directory, or use `--source cmdvault=/path/to/project`.

Do not put secrets or `.venv` directories into Git. Review your source before
publishing the repository.
