"""
api/dependencies.py — FastAPI Dependencies for APRS V6 Pro.

IMPORTANT PRODUCT ARCHITECTURE INVARIANT:
APRS V6 Pro is a completely free application with direct access.
No authentication, no authorization, no session, and no token dependencies exist.
All dependencies here are strictly for database access and request context.
"""
from typing import Generator
import sqlite3
from core.database import get_connection

def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    FastAPI dependency yielding a thread-safe connection to authoritative SQLite SSOT.
    Automatically closes the connection upon request completion.
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass
