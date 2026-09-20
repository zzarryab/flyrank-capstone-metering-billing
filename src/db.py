import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=False)


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free',
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            subscription_status TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            usage_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            idempotency_key TEXT NOT NULL,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, idempotency_key)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_webhook_events (
            stripe_event_id TEXT PRIMARY KEY,
            processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    conn.execute("""
        CREATE EXTENSION IF NOT EXISTS pgcrypto
    """)
    conn.commit()

    # Seed one demo tenant if none exist
    row = conn.execute("SELECT COUNT(*) AS c FROM tenants").fetchone()
    if row["c"] == 0:
        conn.execute(
            "INSERT INTO tenants (name, plan) VALUES (%s, %s)",
            ("Demo Tenant", "free"),
        )
        conn.commit()
    conn.close()