import hashlib
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

# ------------------------------
# Database location
# ------------------------------
DB_DIR = Path("data")
DB_DIR.mkdir(exist_ok=True)

DB_PATH = DB_DIR / "recruiter.db"


# ------------------------------
# Connection helper
# ------------------------------
def get_connection():
    return sqlite3.connect(DB_PATH)


# ------------------------------
# Initialize / migrate DB
# ------------------------------
def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Create table if not exists (fresh DB)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_name TEXT,
        resume_text TEXT NOT NULL,
        job_description TEXT NOT NULL,

        score INTEGER,
        pros TEXT,
        cons TEXT,
        rationale TEXT,

        recommendation TEXT,
        confidence REAL,
        decision_reason TEXT,

        fingerprint TEXT UNIQUE,
        created_at TEXT
    )
    """)

    # Lightweight migration: ensure candidate_name exists
    cursor.execute("PRAGMA table_info(candidates)")
    columns = {row[1] for row in cursor.fetchall()}

    if "candidate_name" not in columns:
        cursor.execute("ALTER TABLE candidates ADD COLUMN candidate_name TEXT")

    conn.commit()
    conn.close()


# ------------------------------
# Insert candidate
# ------------------------------
def insert_candidate(
    resume_text: str,
    job_description: str,
    evaluation: dict,
    decision: dict,
    fingerprint: str,
    candidate_name: Optional[str] = None
) -> int:

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO candidates (
            candidate_name,
            resume_text,
            job_description,
            score,
            pros,
            cons,
            rationale,
            recommendation,
            confidence,
            decision_reason,
            fingerprint,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_name,
            resume_text,
            job_description,
            evaluation.get("score"),
            json.dumps(evaluation.get("pros", [])),
            json.dumps(evaluation.get("cons", [])),
            evaluation.get("rationale"),
            decision.get("recommendation"),
            decision.get("confidence"),
            decision.get("reason"),
            fingerprint,
            datetime.utcnow().isoformat()
        )
    )

    candidate_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return candidate_id


# ------------------------------
# Duplicate detection
# ------------------------------
def make_fingerprint(resume_text: str, job_description: str) -> str:
    h = hashlib.sha256()
    h.update((resume_text + job_description).encode("utf-8"))
    return h.hexdigest()


def find_candidate_by_fingerprint(fingerprint: str) -> Optional[int]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM candidates WHERE fingerprint = ?",
        (fingerprint,)
    )

    row = cursor.fetchone()
    conn.close()

    return row[0] if row else None


# ------------------------------
# Fetch single candidate
# ------------------------------
def safe_json_loads(value):
    if not value:
        return []
    try:
        return json.loads(value)
    except Exception:
        return []


def get_candidate(candidate_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM candidates WHERE id = ?",
        (candidate_id,)
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "resume_text": row[1],
        "job_description": row[2],
        "score": row[3],
        "pros": safe_json_loads(row[4]),
        "cons": safe_json_loads(row[5]),
        "rationale": row[6],
        "recommendation": row[7],
        "confidence": row[8],
        "decision_reason": row[9],
        "created_at": row[10]
    }


# ------------------------------
# List candidates (dashboard)
# ------------------------------
def list_candidates(limit: int = 50):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            candidate_name,
            score,
            recommendation,
            confidence,
            created_at
        FROM candidates
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,)
    )

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "candidate_name": r[1],
            "score": r[2],
            "recommendation": r[3],
            "confidence": r[4],
            "created_at": r[5]
        }
        for r in rows
    ]
def delete_all_candidates():
    """Delete all candidates and reset ID counter."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Delete all candidates
    cursor.execute("DELETE FROM candidates")
    
    # Reset AUTOINCREMENT counter
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='candidates'")
    
    conn.commit()
    conn.close()

