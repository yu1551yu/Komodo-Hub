from __future__ import annotations

from contextlib import contextmanager
from threading import Lock

import mysql.connector
from mysql.connector import pooling

from database.config import get_database_config

_pool: pooling.MySQLConnectionPool | None = None
_lock = Lock()


def _server_args() -> dict:
    cfg = get_database_config(database=False)
    return {
        "host": cfg.host,
        "port": cfg.port,
        "user": cfg.user,
        "password": cfg.password,
        "charset": "utf8mb4",
        "use_unicode": True,
    }


def initialize_database() -> None:
    global _pool
    cfg = get_database_config()
    bootstrap = mysql.connector.connect(**_server_args())
    try:
        cursor = bootstrap.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{cfg.database}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        bootstrap.commit()
        cursor.close()
    finally:
        bootstrap.close()

    with _lock:
        if _pool is None:
            _pool = pooling.MySQLConnectionPool(
                pool_name="komodo_hub_pool",
                pool_size=cfg.pool_size,
                pool_reset_session=True,
                database=cfg.database,
                **_server_args(),
            )


def get_pool() -> pooling.MySQLConnectionPool:
    if _pool is None:
        initialize_database()
    assert _pool is not None
    return _pool


@contextmanager
def connection():
    conn = get_pool().get_connection()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def close_pool() -> None:
    global _pool
    _pool = None
