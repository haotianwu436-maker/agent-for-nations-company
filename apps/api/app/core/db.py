from contextlib import contextmanager

import psycopg

from app.core.config import settings


def _to_psycopg_dsn(url: str) -> str:
    # SQLAlchemy 风格 DSN 转 psycopg 可识别 DSN
    return url.replace("postgresql+psycopg://", "postgresql://")


@contextmanager
def get_conn():
    conn = psycopg.connect(_to_psycopg_dsn(settings.database_url), autocommit=True)
    try:
        yield conn
    finally:
        conn.close()
