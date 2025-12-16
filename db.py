import hashlib
import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_DIR = Path("data")
DB_DIR.mkdir(exist_ok=True)

DB_PATH = DB_DIR / "recruiter.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resume_text TEXT NOT NULL,
            job_description TEXT NOT NULL,

            score INTEGER,
            pros TEXT,
            cons TEXT,
            rationale TEXT,

            recommendation TEXT,
            confidence REAL,
            decision_reason TEXT,

            created_at TEXT
        )
        """
    )

    conn.commit()
    conn.close()


def insert_candidate(
    resume_text: str,
    job_description: str,
    evaluation: dict,
    decision: dict,
    fingerprint: str
) -> int:

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
    """
    INSERT INTO candidates (
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
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
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
def find_candidate_by_fingerprint(fingerprint: str) -> int | None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM candidates WHERE fingerprint = ?",
        (fingerprint,)
    )

    row = cursor.fetchone()
    conn.close()

    return row[0] if row else None



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
        "pros": json.loads(row[4]),
        "cons": json.loads(row[5]),
        "rationale": row[6],
        "recommendation": row[7],
        "confidence": row[8],
        "decision_reason": row[9],
        "created_at": row[10]
    }
def make_fingerprint(resume_text: str, job_description: str) -> str:
    h = hashlib.sha256()
    h.update((resume_text + job_description).encode("utf-8"))
    return h.hexdigest()
def list_candidates(limit=50):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id, score, recommendation, confidence, created_at
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
            "score": r[1],
            "recommendation": r[2],
            "confidence": r[3],
            "created_at": r[4]
        }
        for r in rows
    ]

