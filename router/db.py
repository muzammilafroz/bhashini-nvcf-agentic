import datetime
import logging
import os

try:
    import psycopg2
except ImportError:  # pragma: no cover - exercised only in minimal local envs
    psycopg2 = None

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
_initialized = False

def get_connection():
    if not DATABASE_URL:
        logger.info("DATABASE_URL is not set; deployment event logging is disabled")
        return None
    if psycopg2 is None:
        logger.warning("psycopg2 is not installed; deployment event logging is disabled")
        return None

    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Failed to connect to TimescaleDB: {e}")
        return None

def init_db():
    global _initialized
    if _initialized:
        return

    conn = get_connection()
    if not conn:
        return

    cursor = None
    try:
        cursor = conn.cursor()

        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
            conn.commit()
        except Exception as e:
            logger.info(f"TimescaleDB extension not available, using standard Postgres table: {e}")
            conn.rollback()

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
        conn.commit()

        # Attempt to convert to TimescaleDB hypertable if possible
        try:
            cursor.execute("""
                SELECT count(*) 
                FROM _timescaledb_catalog.hypertable 
                WHERE table_name = 'deployment_events'
            """)
            is_hypertable = cursor.fetchone()[0] > 0
            
            if not is_hypertable:
                cursor.execute("SELECT create_hypertable('deployment_events', 'ts', if_not_exists => TRUE)")
            conn.commit()
        except Exception as e:
            logger.info(f"TimescaleDB extension not available or active, falling back to standard Postgres table: {e}")
            conn.rollback()
        _initialized = True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
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
    init_db()

    conn = get_connection()
    if not conn:
        logger.warning("Skipping event logging due to missing DB connection")
        return

    cursor = None
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
        if cursor:
            cursor.close()
        if conn:
            conn.close()
