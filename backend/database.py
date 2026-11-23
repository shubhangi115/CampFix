"""Connection and transaction management for MySQL."""

import os
from contextlib import contextmanager
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@contextmanager
def db():
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "campfix_app"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "campfix_db"),
        time_zone="+00:00",
        connection_timeout=5,
    )
    try:
        with connection.cursor(dictionary=True, buffered=True) as cursor:
            yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
