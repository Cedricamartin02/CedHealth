
import sqlite3
from flask import g

DB_PATH = "cedhealth.db"

def get_db():
    if "db" not in g:
        conn = sqlite3.connect(
            DB_PATH,
            timeout=10,                # wait up to 10s if DB is busy
            isolation_level=None,      # autocommit mode
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        conn.row_factory = sqlite3.Row
        # Improve concurrency & locking behavior
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=10000;")
        g.db = conn
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def execute(query, params=()):
    db = get_db()
    return db.execute(query, params)

def executemany(query, seq):
    db = get_db()
    return db.executemany(query, seq)

def begin():
    execute("BEGIN")

def commit():
    execute("COMMIT")

def rollback():
    execute("ROLLBACK")
