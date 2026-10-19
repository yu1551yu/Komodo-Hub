from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def read_rows(filename: str) -> list[dict]:
    from database.store import read_rows as database_read_rows

    return database_read_rows(filename)


def write_rows(filename: str, rows: list[dict]) -> None:
    from database.store import write_rows as database_write_rows

    database_write_rows(filename, rows)
