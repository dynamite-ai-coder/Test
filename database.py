import sqlite3
import os
import uuid
from datetime import datetime
from configuration import DATA_DIR


DB_PATH = os.path.join(DATA_DIR, "jobs.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            current_file TEXT,
            files_found INTEGER DEFAULT 0,
            files_uploaded INTEGER DEFAULT 0,
            files_failed INTEGER DEFAULT 0,
            error_message TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("[DATABASE] Initialized")


def create_job(user_id, channel):
    job_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()
    conn = get_connection()
    conn.execute(
        "INSERT INTO jobs (job_id, user_id, channel, status, created_at) VALUES (?, ?, ?, 'queued', ?)",
        (job_id, user_id, channel, now),
    )
    conn.commit()
    conn.close()
    print(f"[DATABASE] Created job {job_id} for {channel}")
    return job_id


def update_job(job_id, **kwargs):
    conn = get_connection()
    sets = []
    vals = []
    for k, v in kwargs.items():
        sets.append(f"{k} = ?")
        vals.append(v)
    vals.append(job_id)
    conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE job_id = ?", vals)
    conn.commit()
    conn.close()


def get_job(job_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_running_jobs():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM jobs WHERE status = 'running'").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_jobs(user_id, limit=10):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_recent_jobs(limit=10):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
