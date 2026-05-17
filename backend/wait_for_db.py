#!/usr/bin/env python3
"""Wait for database to be ready.

Uses DATABASE_URL when set (Docker Compose or local dev). Falls back to
POSTGRES_* env vars, then legacy defaults (host ``db``) for bare containers.
"""
import os
import sys
import time
from urllib.parse import urlparse, unquote

import psycopg2

max_attempts = 30


def _connect_kwargs_from_database_url() -> dict | None:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return None
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://"):
        if url.startswith(prefix):
            url = "postgresql://" + url.split("://", 1)[1]
            break
    parsed = urlparse(url)
    if not parsed.hostname:
        return None
    password = unquote(parsed.password) if parsed.password else ""
    dbname = (parsed.path or "/").lstrip("/").split("?")[0] or "postgres"
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "user": parsed.username or "postgres",
        "password": password,
        "dbname": dbname,
    }


def get_connect_kwargs() -> dict:
    from_url = _connect_kwargs_from_database_url()
    if from_url:
        return from_url
    return {
        "host": os.environ.get("POSTGRES_HOST", "db"),
        "port": int(os.environ.get("POSTGRES_PORT", "5432")),
        "user": os.environ.get("POSTGRES_USER", "fpi-admin"),
        "password": os.environ.get("POSTGRES_PASSWORD", "Fpi-c05b6q#"),
        "dbname": os.environ.get("POSTGRES_DB", "fpi_connect"),
    }


for i in range(max_attempts):
    try:
        conn = psycopg2.connect(**get_connect_kwargs())
        conn.close()
        print("Database is ready!")
        sys.exit(0)
    except psycopg2.OperationalError as e:
        if i < max_attempts - 1:
            print(f"Database not ready, attempt {i+1}/{max_attempts}...")
            time.sleep(2)
        else:
            print(f"Failed to connect to database: {e}")
            sys.exit(1)
