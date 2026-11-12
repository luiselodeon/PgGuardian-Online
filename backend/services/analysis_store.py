"""
PgGuardian — Persistencia de Análisis Históricos en app_db (RF-01.7 y RF-01.8)

Gestiona el almacenamiento permanente de reportes en app_db, desacoplado de
sandbox_db y TiendaDB. Nunca almacena credenciales de bases sandbox y aplica
filtrado obligatorio por user_id en consultas y borrados.
"""

from datetime import datetime, timedelta, timezone
import os
from uuid import UUID

import psycopg2
from psycopg2 import extras

SANDBOX_TTL_HOURS = 24

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_users_email_lowercase CHECK (email = LOWER(email))
);
ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sessions_user_active
    ON sessions (user_id, revoked_at, expires_at);

CREATE TABLE IF NOT EXISTS analyses (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    status VARCHAR(32) NOT NULL,
    message TEXT NOT NULL,
    file_count INTEGER NOT NULL,
    total_size_bytes BIGINT NOT NULL,
    files_json JSONB NOT NULL,
    sandbox_db_name VARCHAR(63) NOT NULL,
    sandbox_status VARCHAR(20) NOT NULL DEFAULT 'active',
    sandbox_expires_at TIMESTAMPTZ NOT NULL,
    sandbox_destroyed_at TIMESTAMPTZ,
    executed_statements INTEGER NOT NULL,
    execution_time_ms INTEGER NOT NULL,
    health_score INTEGER NOT NULL,
    total_findings INTEGER NOT NULL,
    scan_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'analyses'
          AND column_name = 'user_id'
          AND data_type <> 'uuid'
    ) THEN
        DELETE FROM analyses
        WHERE user_id NOT IN (SELECT id::text FROM users);

        ALTER TABLE analyses
            ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_analyses_user'
          AND conrelid = 'analyses'::regclass
    ) AND NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE confrelid = 'users'::regclass
          AND conrelid = 'analyses'::regclass
          AND contype = 'f'
    ) THEN
        DELETE FROM analyses a
        WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id = a.user_id);

        ALTER TABLE analyses
            ADD CONSTRAINT fk_analyses_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_analyses_user_created
    ON analyses (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analyses_sandbox_expiry
    ON analyses (sandbox_status, sandbox_expires_at)
    WHERE sandbox_status = 'active';
"""


def connect_app_db():
    """Conecta exclusivamente a app_db mediante variables APP_DB_*."""
    conn = psycopg2.connect(
        dbname=os.getenv("APP_DB_NAME", "pgguardian_app"),
        user=os.getenv("APP_DB_USER", "pgguardian_app_user"),
        password=os.getenv("APP_DB_PASSWORD", "pgguardian_app_pass"),
        host=os.getenv("APP_DB_HOST", "app_db"),
        port=int(os.getenv("APP_DB_PORT", "5432")),
        connect_timeout=10,
    )
    conn.autocommit = True
    return conn


_connect_app_db = connect_app_db


def init_app_db_schema() -> None:
    """Inicializa idempotentemente las tablas e índices de app_db."""
    conn = _connect_app_db()
    try:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA_DDL)
    finally:
        conn.close()


def insert_analysis(
    *,
    analysis_id: str,
    user_id: str,
    name: str,
    status: str,
    message: str,
    file_count: int,
    total_size_bytes: int,
    files: list[dict],
    sandbox_db_name: str,
    executed_statements: int,
    execution_time_ms: int,
    scan: dict,
    created_at: datetime,
) -> dict:
    """Registra un análisis y la fecha de expiración (24 h) de su sandbox en app_db."""
    expires_at = created_at.astimezone(timezone.utc) + timedelta(hours=SANDBOX_TTL_HOURS)
    query = """
    INSERT INTO analyses (
        id, user_id, name, status, message, file_count, total_size_bytes,
        files_json, sandbox_db_name, sandbox_status, sandbox_expires_at,
        executed_statements, execution_time_ms, health_score, total_findings,
        scan_json, created_at
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s,
        %s, %s, 'active', %s,
        %s, %s, %s, %s,
        %s, %s
    )
    RETURNING id::text, user_id::text, name, status, message, file_count, total_size_bytes,
              files_json AS files, sandbox_db_name, sandbox_status, sandbox_expires_at,
              sandbox_destroyed_at, executed_statements, execution_time_ms,
              health_score, total_findings, scan_json AS scan, created_at;
    """
    conn = _connect_app_db()
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(
                query,
                (
                    analysis_id,
                    user_id,
                    name,
                    status,
                    message,
                    file_count,
                    total_size_bytes,
                    extras.Json(files),
                    sandbox_db_name,
                    expires_at,
                    executed_statements,
                    execution_time_ms,
                    scan["health_score"],
                    scan["total_findings"],
                    extras.Json(scan),
                    created_at,
                ),
            )
            return dict(cur.fetchone())
    finally:
        conn.close()


def list_analyses_for_user(user_id: str) -> list[dict]:
    """Devuelve únicamente el historial de análisis pertenecientes al usuario."""
    normalized_user_id = _parse_uuid_or_none(user_id)
    if normalized_user_id is None:
        return []

    query = """
    SELECT id::text, user_id::text, name, status, file_count, total_size_bytes,
           sandbox_db_name, sandbox_status, sandbox_expires_at,
           sandbox_destroyed_at, executed_statements, execution_time_ms,
           health_score, total_findings, created_at
    FROM analyses
    WHERE user_id = %s
    ORDER BY created_at DESC;
    """
    conn = _connect_app_db()
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(query, (normalized_user_id,))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _parse_uuid_or_none(value: str) -> str | None:
    try:
        return str(UUID(value))
    except (ValueError, TypeError):
        return None


def get_analysis_for_user(analysis_id: str, user_id: str) -> dict | None:
    """Obtiene el detalle de un análisis validando propiedad del usuario."""
    normalized_id = _parse_uuid_or_none(analysis_id)
    normalized_user_id = _parse_uuid_or_none(user_id)
    if normalized_id is None or normalized_user_id is None:
        return None

    query = """
    SELECT id::text, user_id::text, name, status, message, file_count, total_size_bytes,
           files_json AS files, sandbox_db_name, sandbox_status, sandbox_expires_at,
           sandbox_destroyed_at, executed_statements, execution_time_ms,
           health_score, total_findings, scan_json AS scan, created_at
    FROM analyses
    WHERE id = %s AND user_id = %s;
    """
    conn = _connect_app_db()
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(query, (normalized_id, normalized_user_id))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def delete_analysis_for_user(analysis_id: str, user_id: str) -> dict | None:
    """Elimina un análisis únicamente si pertenece al usuario autenticado."""
    normalized_id = _parse_uuid_or_none(analysis_id)
    normalized_user_id = _parse_uuid_or_none(user_id)
    if normalized_id is None or normalized_user_id is None:
        return None

    query = """
    DELETE FROM analyses
    WHERE id = %s AND user_id = %s
    RETURNING id::text, sandbox_db_name, sandbox_status;
    """
    conn = _connect_app_db()
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(query, (normalized_id, normalized_user_id))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def find_expired_active_sandboxes(limit: int = 50) -> list[dict]:
    """Lista bases sandbox activas cuyo periodo de retención de 24 h venció."""
    query = """
    SELECT id::text, sandbox_db_name
    FROM analyses
    WHERE sandbox_status = 'active'
      AND sandbox_expires_at <= NOW()
    ORDER BY sandbox_expires_at ASC
    LIMIT %s;
    """
    conn = _connect_app_db()
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(query, (limit,))
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def mark_sandbox_destroyed(analysis_id: str) -> None:
    """Actualiza el estado del sandbox a 'destroyed' conservando el reporte histórico."""
    query = """
    UPDATE analyses
    SET sandbox_status = 'destroyed',
        sandbox_destroyed_at = NOW()
    WHERE id = %s AND sandbox_status = 'active';
    """
    conn = _connect_app_db()
    try:
        with conn.cursor() as cur:
            cur.execute(query, (analysis_id,))
    finally:
        conn.close()

