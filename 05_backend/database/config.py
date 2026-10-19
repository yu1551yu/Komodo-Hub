from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_ROOT / ".env", override=False)


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    pool_size: int


def get_database_config(database: bool = True) -> DatabaseConfig:
    name = os.getenv("DB_NAME", "komodo_hub").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise RuntimeError("DB_NAME may contain only letters, numbers, and underscores")
    password = os.getenv("DB_PASSWORD")
    if password is None:
        raise RuntimeError("DB_PASSWORD is required")
    return DatabaseConfig(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=password,
        database=name if database else "",
        pool_size=max(1, min(int(os.getenv("DB_POOL_SIZE", "8")), 32)),
    )
