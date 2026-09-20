import psycopg
from psycopg.types.json import Json
from src.db import get_connection


def record_usage(tenant_id: str, usage_type: str, quantity: int, idempotency_key: str, metadata: dict = None):
    """
    Records a usage event idempotently. If (tenant_id, idempotency_key) already
    exists, returns the ORIGINAL event instead of creating a new one.
    Returns (event_dict, was_duplicate: bool).
    """
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM usage_events WHERE tenant_id = %s AND idempotency_key = %s",
            (tenant_id, idempotency_key),
        ).fetchone()

        if existing:
            conn.close()
            return existing, True

        row = conn.execute(
            """
            INSERT INTO usage_events (tenant_id, usage_type, quantity, idempotency_key, metadata)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (tenant_id, usage_type, quantity, idempotency_key, Json(metadata or {})),
        ).fetchone()
        conn.commit()
        conn.close()
        return row, False

    except psycopg.errors.UniqueViolation:
        conn.rollback()
        existing = conn.execute(
            "SELECT * FROM usage_events WHERE tenant_id = %s AND idempotency_key = %s",
            (tenant_id, idempotency_key),
        ).fetchone()
        conn.close()
        return existing, True


def get_monthly_usage(tenant_id: str, usage_type: str) -> int:
    """Sum this tenant's usage of a given type for the current calendar month."""
    conn = get_connection()
    row = conn.execute(
        """
        SELECT COALESCE(SUM(quantity), 0) AS total
        FROM usage_events
        WHERE tenant_id = %s
          AND usage_type = %s
          AND date_trunc('month', created_at) = date_trunc('month', now())
        """,
        (tenant_id, usage_type),
    ).fetchone()
    conn.close()
    return row["total"]