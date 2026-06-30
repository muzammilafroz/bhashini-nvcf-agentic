import sqlite3
import datetime
from pathlib import Path

DB_PATH = Path("deployment_events.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deployment_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            model_name TEXT,
            git_sha TEXT,
            image_tag TEXT,
            fn_id TEXT,
            version_id TEXT,
            stage TEXT,
            traffic_pct INTEGER,
            rollback_reason TEXT,
            p95_latency_ms REAL,
            error_rate REAL,
            wer_delta REAL
        )
    """)
    conn.commit()
    conn.close()

def log_event(
    model_name: str,
    git_sha: str,
    image_tag: str,
    fn_id: str,
    version_id: str,
    stage: str,
    traffic_pct: int,
    rollback_reason: str | None = None,
    p95_latency_ms: float | None = None,
    error_rate: float | None = None,
    wer_delta: float | None = None
):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    ts = datetime.datetime.now(datetime.UTC).isoformat()
    
    cursor.execute("""
        INSERT INTO deployment_events 
        (ts, model_name, git_sha, image_tag, fn_id, version_id, stage, traffic_pct, rollback_reason, p95_latency_ms, error_rate, wer_delta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ts, model_name, git_sha, image_tag, fn_id, version_id, stage, traffic_pct, rollback_reason, p95_latency_ms, error_rate, wer_delta))
    
    conn.commit()
    conn.close()

# Initialize on import
init_db()
