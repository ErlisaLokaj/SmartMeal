from __future__ import annotations

import os
from functools import lru_cache
from typing import Set, List, Optional, Dict

import psycopg2
from psycopg2.extras import RealDictCursor


PGHOST = os.getenv("PGHOST", "db")
PGPORT = int(os.getenv("PGPORT", "5432"))
PGDATABASE = os.getenv("PGDATABASE", "smartmeal")
PGUSER = os.getenv("PGUSER", "postgres")
PGPASSWORD = os.getenv("PGPASSWORD", "postgres")


@lru_cache(maxsize=1)
def _dsn() -> str:
    # psycopg2 DSN string
    return (
        f"dbname={PGDATABASE} "
        f"user={PGUSER} "
        f"password={PGPASSWORD} "
        f"host={PGHOST} "
        f"port={PGPORT}"
    )


def _query(sql: str, params: tuple | None = None) -> List[dict]:
    try:
        with psycopg2.connect(_dsn()) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params or ())
                return list(cur.fetchall())
    except Exception:
        return []


def get_user_allergy_ingredient_ids(user_id: str) -> Set[str]:
    rows = _query(
        "SELECT ingredient_id::text AS ingredient_id "
        "FROM user_allergy "
        "WHERE user_id = %s",
        (user_id,),
    )
    return {row["ingredient_id"] for row in rows if "ingredient_id" in row}


def get_user_by_id(user_id: str) -> Optional[Dict[str, str]]:
    rows = _query(
        "SELECT user_id::text, email, full_name, created_at "
        "FROM app_user "
        "WHERE user_id = %s",
        (user_id,),
    )

    if not rows:
        return None

    row = rows[0]
    return {
        "user_id": row.get("user_id"),
        "email": row.get("email"),
        "full_name": row.get("full_name"),
        "created_at": row.get("created_at"),
    }
