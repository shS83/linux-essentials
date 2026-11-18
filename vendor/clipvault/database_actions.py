"""Additional PostgreSQL operations for ClipVault's GUI.

Uses the same connection configuration as the existing database.py module.
The original database.py file does not need to be replaced.
"""

import psycopg
from database import CONNINFO


def delete_clipboard(entry_id: int) -> bool:
    """Permanently delete one row by its numeric ID. Returns True if deleted."""
    if not isinstance(entry_id, int) or entry_id <= 0:
        raise ValueError("entry_id must be a positive integer")

    with psycopg.connect(CONNINFO) as conn:
        row = conn.execute(
            "DELETE FROM clipboard WHERE id = %s RETURNING id",
            (entry_id,),
        ).fetchone()
    return row is not None
