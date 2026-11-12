"""
PgGuardian — Persistencia de Usuarios y Sesiones en app_db (RF-02.1 a RF-02.6)

Gestiona usuarios, bloqueo temporal por intentos fallidos, cambio de contraseña
y sesiones activas/revocadas exclusivamente en app_db.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from psycopg2 import errors, extras

from services.analysis_store import connect_app_db


class EmailAlreadyExistsError(Exception):
    """Error lanzado cuando el correo ya se encuentra registrado en app_db."""


def _valid_uuid(value: str) -> str | None:
    try:
        return str(UUID(value))
    except (ValueError, TypeError):
        return None


def get_user_by_email(email: str) -> dict | None:
    """Busca un usuario por correo normalizado en minúsculas."""
    normalized = email.strip().lower()
    query = """
    SELECT id::text, name, email, password_hash,
           failed_login_attempts, locked_until, created_at, updated_at
    FROM users
    WHERE email = %s;
    """
    conn = connect_app_db()
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(query, (normalized,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_user_with_hash_by_id(user_id: str) -> dict | None:
    """Obtiene el usuario y su hash actual para verificar cambio de contraseña."""
    uid = _valid_uuid(user_id)
    if uid is None:
        return None
    query = """
    SELECT id::text, name, email, password_hash
    FROM users
    WHERE id = %s;
    """
    conn = connect_app_db()
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(query, (uid,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def create_user(*, name: str, email: str, password_hash: str) -> dict:
    """Inserta un nuevo usuario en app_db sin exponer su hash en el resultado."""
    user_id = str(uuid4())
    normalized_email = email.strip().lower()
    clean_name = name.strip()
    now = datetime.now(timezone.utc)
    query = """
    INSERT INTO users (id, name, email, password_hash, created_at, updated_at)
    VALUES (%s, %s, %s, %s, %s, %s)
    RETURNING id::text, name, email, created_at, updated_at;
    """
    conn = connect_app_db()
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(
                query,
                (user_id, clean_name, normalized_email, password_hash, now, now),
            )
            return dict(cur.fetchone())
    except errors.UniqueViolation as exc:
        raise EmailAlreadyExistsError(
            "Este correo electrónico ya está registrado."
        ) from exc
    finally:
        conn.close()


def record_failed_login(
    user_id: str,
    *,
    max_attempts: int = 5,
    lock_minutes: int = 15,
) -> tuple[int, datetime | None]:
    """Incrementa intentos fallidos y bloquea la cuenta 15 min al llegar al límite."""
    query = """
    UPDATE users
    SET failed_login_attempts = CASE
            WHEN locked_until IS NOT NULL AND locked_until <= NOW() THEN 1
            ELSE failed_login_attempts + 1
        END,
        locked_until = CASE
            WHEN (
                CASE
                    WHEN locked_until IS NOT NULL AND locked_until <= NOW() THEN 1
                    ELSE failed_login_attempts + 1
                END
            ) >= %s THEN NOW() + (%s * INTERVAL '1 minute')
            ELSE NULL
        END,
        updated_at = NOW()
    WHERE id = %s
    RETURNING failed_login_attempts, locked_until;
    """
    conn = connect_app_db()
    try:
        with conn.cursor() as cur:
            cur.execute(query, (max_attempts, lock_minutes, user_id))
            attempts, locked_until = cur.fetchone()
            return int(attempts), locked_until
    finally:
        conn.close()


def reset_failed_logins(user_id: str) -> None:
    """Reinicia el contador de intentos fallidos tras autenticación exitosa."""
    query = """
    UPDATE users
    SET failed_login_attempts = 0,
        locked_until = NULL,
        updated_at = NOW()
    WHERE id = %s;
    """
    conn = connect_app_db()
    try:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
    finally:
        conn.close()


def update_user_password(user_id: str, new_password_hash: str) -> None:
    """Actualiza el hash Argon2id del usuario en app_db."""
    query = """
    UPDATE users
    SET password_hash = %s,
        updated_at = NOW()
    WHERE id = %s;
    """
    conn = connect_app_db()
    try:
        with conn.cursor() as cur:
            cur.execute(query, (new_password_hash, user_id))
    finally:
        conn.close()


def create_session(user_id: str, *, expires_at: datetime) -> dict:
    """Crea una nueva sesión persistida en app_db."""
    session_id = str(uuid4())
    query = """
    INSERT INTO sessions (id, user_id, expires_at)
    VALUES (%s, %s, %s)
    RETURNING id::text, user_id::text, expires_at, created_at;
    """
    conn = connect_app_db()
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(query, (session_id, user_id, expires_at))
            return dict(cur.fetchone())
    finally:
        conn.close()


def get_active_session_user(session_id: str, user_id: str) -> dict | None:
    """Devuelve el usuario autenticado si la sesión existe, no expiró ni fue revocada."""
    sid = _valid_uuid(session_id)
    uid = _valid_uuid(user_id)
    if sid is None or uid is None:
        return None
    query = """
    SELECT u.id::text AS id, u.name, u.email, s.id::text AS session_id
    FROM sessions s
    JOIN users u ON u.id = s.user_id
    WHERE s.id = %s
      AND s.user_id = %s
      AND s.revoked_at IS NULL
      AND s.expires_at > NOW();
    """
    conn = connect_app_db()
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(query, (sid, uid))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def revoke_session(session_id: str) -> None:
    """Revoca una sesión específica al cerrar sesión."""
    sid = _valid_uuid(session_id)
    if sid is None:
        return
    query = """
    UPDATE sessions
    SET revoked_at = NOW()
    WHERE id = %s AND revoked_at IS NULL;
    """
    conn = connect_app_db()
    try:
        with conn.cursor() as cur:
            cur.execute(query, (sid,))
    finally:
        conn.close()


def revoke_other_sessions(user_id: str, keep_session_id: str) -> int:
    """Revoca todas las demás sesiones activas del usuario (RF-02.6)."""
    uid = _valid_uuid(user_id)
    sid = _valid_uuid(keep_session_id)
    if uid is None or sid is None:
        return 0
    query = """
    UPDATE sessions
    SET revoked_at = NOW()
    WHERE user_id = %s
      AND id <> %s
      AND revoked_at IS NULL;
    """
    conn = connect_app_db()
    try:
        with conn.cursor() as cur:
            cur.execute(query, (uid, sid))
            return cur.rowcount
    finally:
        conn.close()
