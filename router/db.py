import os
import psycopg2
import datetime
import logging

logger = logging.getLogger(__name__)

# Default to the Droplet's PostgreSQL/TimescaleDB
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://kong:kong_pass@142.93.209.191:5432/kong")

def get_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Failed to connect to TimescaleDB: {e}")
        return None

def init_db():
    conn = get_connection()
    if not conn:
        return
        
    try:
        cursor = conn.cursor()
        # Create standard table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deployment_events (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMP WITH TIME ZONE NOT NULL,
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
        
        # Check if it's already a hypertable
        cursor.execute("""
            SELECT count(*) 
            FROM _timescaledb_catalog.hypertable 
            WHERE table_name = 'deployment_events'
        """)
        is_hypertable = cursor.fetchone()[0] > 0
        
        # Convert to TimescaleDB hypertable if not already
        if not is_hypertable:
            cursor.execute("SELECT create_hypertable('deployment_events', 'ts', if_not_exists => TRUE)")
            
        conn.commit()
    except Exception as e:
        logger.error(f"Error initializing TimescaleDB: {e}")
    finally:
        if conn:
            cursor.close()
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
    conn = get_connection()
    if not conn:
        logger.warning("Skipping event logging due to missing DB connection")
        return
        
    try:
        cursor = conn.cursor()
        ts = datetime.datetime.now(datetime.timezone.utc)
        
        cursor.execute("""
            INSERT INTO deployment_events 
            (ts, model_name, git_sha, image_tag, fn_id, version_id, stage, traffic_pct, rollback_reason, p95_latency_ms, error_rate, wer_delta)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (ts, model_name, git_sha, image_tag, fn_id, version_id, stage, traffic_pct, rollback_reason, p95_latency_ms, error_rate, wer_delta))
        
        conn.commit()
    except Exception as e:
        logger.error(f"Error logging event to TimescaleDB: {e}")
    finally:
        if conn:
            cursor.close()
            conn.close()

# Initialize on import
init_db()
