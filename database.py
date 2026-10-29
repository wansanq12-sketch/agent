"""Transaction scopes always release SQLite file handles, including on Windows."""
from contextlib import contextmanager
import sqlite3

@contextmanager
def connection(path):
    database=sqlite3.connect(path)
    try:
        with database:
            yield database
    finally:
        database.close()
