"""
Feature 2: Evidence Manager - storage layer.

Two backends, chosen automatically at import time:
  - DATABASE_URL set (e.g. a Supabase Postgres connection string) -> Postgres.
    Use this for any real deployment: Render/Railway's local disk is wiped on
    every restart/redeploy, so SQLite would silently lose all data.
  - DATABASE_URL unset -> SQLite (original behavior). Zero setup, fine for
    local dev, but not durable across deploys.

All function signatures below are unchanged from the original SQLite-only
version, so nothing calling into this module (main.py) needs to change.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import blob_storage

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "storage", "app.db")
STORAGE_DIR = os.path.join(os.path.dirname(__file__), "..", "storage", "uploaded_files")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(STORAGE_DIR, exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras


class _PgCursorWrapper:
    """Makes a psycopg2 connection support the same `conn.execute(sql, params)`
    call the original SQLite code used, translating `?` placeholders to `%s`
    and returning dict-like rows via RealDictCursor."""
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql.replace("?", "%s"), params)
        return cur


@contextmanager
def get_conn():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        wrapper = _PgCursorWrapper(conn)
        try:
            yield wrapper
            conn.commit()
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db():
    id_type = "TEXT PRIMARY KEY"
    with get_conn() as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS evidence (
                id {id_type},
                complaint_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT,
                file_size INTEGER,
                upload_time TEXT,
                sha256 TEXT,
                extracted_entities_json TEXT
            )
        """)
        # Phase 4 (report history) uses this table
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS reports (
                id {id_type},
                complaint_id TEXT NOT NULL,
                crime_type TEXT,
                generated_date TEXT,
                status TEXT,
                format TEXT,
                filename TEXT,
                file_path TEXT
            )
        """)

    # Feature 13 (OCR pipeline): new columns added to the existing `evidence`
    # table via ALTER TABLE rather than changing the CREATE TABLE statement
    # above, so this stays a no-op on a fresh DB (columns already in place)
    # and a safe, additive migration on any existing app.db that predates
    # OCR support. Each column gets its OWN connection/transaction (not
    # reused from the block above) - critical for Postgres, where a failed
    # statement (e.g. "column already exists") aborts the entire transaction
    # and silently discards every other statement run on that same
    # connection until a rollback, which would otherwise make one already-
    # migrated column block the rest of the migration from ever applying.
    for column_def in (
        "ocr_text TEXT",
        "crime_prediction TEXT",
        "confidence REAL",
        "evidence_summary_json TEXT",
    ):
        try:
            with get_conn() as conn:
                conn.execute(f"ALTER TABLE evidence ADD COLUMN {column_def}")
        except Exception:
            pass  # column already exists - fine, this migration has already run before


def save_report_record(report_id, complaint_id, crime_type, status, format, filename, file_path):
    """Feature 12: Report History - records a generated report so it can be
    reopened/re-downloaded later without regenerating it."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO reports (id, complaint_id, crime_type, generated_date, status, format, filename, file_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (report_id, complaint_id, crime_type,
             datetime.now().isoformat(timespec="seconds"), status, format, filename, file_path),
        )


def list_reports(complaint_id: str = None) -> list:
    """Returns all reports, or only those for a given complaint_id if provided."""
    with get_conn() as conn:
        if complaint_id:
            rows = conn.execute(
                "SELECT * FROM reports WHERE complaint_id = ? ORDER BY generated_date DESC",
                (complaint_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM reports ORDER BY generated_date DESC").fetchall()
    return [dict(row) for row in rows]


def get_report(report_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    return dict(row) if row else None


def delete_report(report_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT file_path FROM reports WHERE id = ?", (report_id,)).fetchone()
        if row and row["file_path"]:
            blob_storage.delete_blob(row["file_path"])
        conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))


def save_evidence_record(evidence_id, complaint_id, filename, file_path, file_type,
                          file_size, sha256, extracted_entities: dict,
                          ocr_text: str = "", crime_prediction: str = None,
                          confidence: float = None, evidence_summary: dict = None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO evidence
               (id, complaint_id, filename, file_path, file_type, file_size,
                upload_time, sha256, extracted_entities_json,
                ocr_text, crime_prediction, confidence, evidence_summary_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (evidence_id, complaint_id, filename, file_path, file_type, file_size,
             datetime.now().isoformat(timespec="seconds"), sha256,
             json.dumps(extracted_entities), ocr_text, crime_prediction, confidence,
             json.dumps(evidence_summary or {})),
        )


def update_evidence_text(evidence_id: str, ocr_text: str, extracted_entities: dict,
                          evidence_summary: dict, crime_prediction: str = None,
                          confidence: float = None):
    """
    Feature 13: lets the user correct OCR text after upload (e.g. OCR
    misread a digit in a phone number) and have entities/classification
    recomputed against the corrected text - "edit extracted text before
    final submission". Returns the updated row, or None if the id doesn't exist.
    """
    with get_conn() as conn:
        conn.execute(
            """UPDATE evidence
               SET ocr_text = ?, extracted_entities_json = ?, evidence_summary_json = ?,
                   crime_prediction = ?, confidence = ?
               WHERE id = ?""",
            (ocr_text, json.dumps(extracted_entities), json.dumps(evidence_summary or {}),
             crime_prediction, confidence, evidence_id),
        )
        row = conn.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
    return dict(row) if row else None


def get_evidence(evidence_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
    return dict(row) if row else None


def list_evidence_for_complaint(complaint_id: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM evidence WHERE complaint_id = ? ORDER BY upload_time ASC",
            (complaint_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def merged_extracted_entities(complaint_id: str) -> dict:
    """Combines extracted entities across all evidence for a complaint into
    one dict of deduplicated lists - this is what pdf_report.py consumes."""
    merged = {}
    for row in list_evidence_for_complaint(complaint_id):
        entities = json.loads(row["extracted_entities_json"] or "{}")
        for key, values in entities.items():
            merged.setdefault(key, set()).update(values)
    return {k: sorted(v) for k, v in merged.items()}


def delete_evidence(evidence_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT file_path FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
        if row and row["file_path"]:
            blob_storage.delete_blob(row["file_path"])
        conn.execute("DELETE FROM evidence WHERE id = ?", (evidence_id,))


init_db()
