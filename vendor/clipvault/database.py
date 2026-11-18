import psycopg


CONNINFO = "dbname=clipvault user=clipvault host=localhost"


def save_clipboard(content: str) -> int:
    """Tallentaa sisällön ja palauttaa tietueen ID:n."""
    with psycopg.connect(CONNINFO) as conn:
        result = conn.execute(
            """
            INSERT INTO clipboard (content)
            VALUES (%s)
            RETURNING id
            """,
            (content,),
        )
        return result.fetchone()[0]


def get_history(limit: int = 20):
    """Hakee viimeisimmät leikepöytämerkinnät."""
    if not 1 <= limit <= 1000:
        raise ValueError("Invalid history limit")
    with psycopg.connect(CONNINFO) as conn:
        return conn.execute(
            """
            SELECT id, content, created_at
            FROM clipboard
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
