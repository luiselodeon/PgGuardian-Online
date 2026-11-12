"""
PgGuardian — Utilidades de Sesión y JWT (RF-02.4, RF-02.5 y RF-02.6)

Genera y verifica tokens JWT firmados con HS256 almacenados en cookie HttpOnly
y respaldados por registros revocables en la tabla sessions de app_db.
"""

from datetime import datetime, timezone
import os

from fastapi import Response
import jwt

SESSION_COOKIE_NAME = "pgguardian_session"
SESSION_TTL_HOURS = 24
_JWT_ALGORITHM = "HS256"
# shortcut: fallback solo para pruebas unitarias locales cuando no se inyecta JWT_SECRET.
_DEV_FALLBACK_SECRET = "pgguardian-local-dev-jwt-secret-key-min-32bytes"


def _get_jwt_secret() -> str:
    return os.getenv("JWT_SECRET") or _DEV_FALLBACK_SECRET


def create_access_token(*, user_id: str, session_id: str, expires_at: datetime) -> str:
    """Firma un JWT HS256 asociado al usuario y al identificador de sesión."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "sid": session_id,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.astimezone(timezone.utc).timestamp()),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Valida firma y expiración del JWT; devuelve claims o None si es inválido."""
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=[_JWT_ALGORITHM],
            options={"require": ["sub", "sid", "exp"]},
        )
    except jwt.PyJWTError:
        return None
    if not isinstance(payload.get("sub"), str) or not isinstance(payload.get("sid"), str):
        return None
    return payload


def set_session_cookie(response: Response, token: str) -> None:
    """Escribe la cookie HttpOnly de sesión en la respuesta HTTP."""
    secure = os.getenv("COOKIE_SECURE", "").lower() == "true"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """Elimina la cookie de sesión al cerrar sesión."""
    secure = os.getenv("COOKIE_SECURE", "").lower() == "true"
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )

