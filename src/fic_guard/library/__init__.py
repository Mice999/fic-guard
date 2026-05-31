"""Local work library — persistent SQLite registry of tracked works and monitoring findings."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_DB_FILE = Path.home() / ".fic_guard" / "library.db"


@dataclass
class Work:
    id: int
    title: str
    work_id: str
    fingerprint_json: str
    notes: str
    created_at: str
    last_checked: Optional[str]
    finding_count: int = 0


@dataclass
class LibraryFinding:
    id: int
    work_id: int
    sentence: str
    provider: str
    query_url: str
    snippet: str
    result_url: str
    status: str
    found_at: str


def _get_conn() -> sqlite3.Connection:
    _DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _create_tables(conn)
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS works (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        work_id TEXT NOT NULL,
        fingerprint_json TEXT NOT NULL,
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        last_checked TEXT
    );
    CREATE TABLE IF NOT EXISTS findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        work_id INTEGER NOT NULL REFERENCES works(id) ON DELETE CASCADE,
        sentence TEXT NOT NULL,
        provider TEXT NOT NULL,
        query_url TEXT NOT NULL,
        snippet TEXT DEFAULT '',
        result_url TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        found_at TEXT NOT NULL,
        UNIQUE(work_id, query_url)
    );
    """)
    conn.commit()


def dashboard_stats() -> dict:
    conn = _get_conn()
    try:
        work_count = conn.execute("SELECT COUNT(*) FROM works").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM findings WHERE status='pending'").fetchone()[0]
        confirmed = conn.execute("SELECT COUNT(*) FROM findings WHERE status='confirmed'").fetchone()[0]
        return {"works": work_count, "pending": pending, "confirmed": confirmed}
    finally:
        conn.close()


def list_works() -> list[Work]:
    conn = _get_conn()
    try:
        rows = conn.execute("""
            SELECT w.id, w.title, w.work_id, w.fingerprint_json, w.notes,
                   w.created_at, w.last_checked,
                   COUNT(CASE WHEN f.status='pending' THEN 1 END) AS finding_count
            FROM works w
            LEFT JOIN findings f ON f.work_id = w.id
            GROUP BY w.id
            ORDER BY w.created_at DESC
        """).fetchall()
        return [Work(**dict(r)) for r in rows]
    finally:
        conn.close()


def add_work(title: str, work_id: str, fingerprint_json: str, notes: str = "") -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn = _get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO works (title, work_id, fingerprint_json, notes, created_at) VALUES (?,?,?,?,?)",
            (title, work_id, fingerprint_json, notes, now),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]
    finally:
        conn.close()


def get_work(work_id: int) -> Optional[Work]:
    conn = _get_conn()
    try:
        r = conn.execute(
            "SELECT *, 0 AS finding_count FROM works WHERE id=?", (work_id,)
        ).fetchone()
        return Work(**dict(r)) if r else None
    finally:
        conn.close()


def list_findings(work_id: int) -> list[LibraryFinding]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM findings WHERE work_id=? ORDER BY found_at DESC",
            (work_id,),
        ).fetchall()
        return [LibraryFinding(**dict(r)) for r in rows]
    finally:
        conn.close()


def add_finding(
    work_id: int,
    sentence: str,
    provider: str,
    query_url: str,
    snippet: str = "",
    result_url: str = "",
) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO findings
               (work_id, sentence, provider, query_url, snippet, result_url, found_at)
               VALUES (?,?,?,?,?,?,?)""",
            (work_id, sentence, provider, query_url, snippet, result_url, now),
        )
        conn.commit()
    finally:
        conn.close()


def update_last_checked(work_id: int) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn = _get_conn()
    try:
        conn.execute("UPDATE works SET last_checked=? WHERE id=?", (now, work_id))
        conn.commit()
    finally:
        conn.close()


def update_finding_status(finding_id: int, status: str) -> None:
    if status not in ("pending", "confirmed", "dismissed"):
        raise ValueError(f"Invalid status: {status!r}")
    conn = _get_conn()
    try:
        conn.execute("UPDATE findings SET status=? WHERE id=?", (status, finding_id))
        conn.commit()
    finally:
        conn.close()
