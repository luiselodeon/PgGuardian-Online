"""
PgGuardian — Dependencia de Autenticación y Sesión Activa (RF-02.5)

Valida el JWT recibido por cookie HttpOnly (pgguardian_session) o cabecera
Authorization Bearer y verifica que la sesión siga activa en app_db.
"""

from fastapi import Cookie, Depends, Header, HTTPException, status
import psycopg2

from security.sessions import SESSION_COOKIE_NAME, decode_access_token
from services.user_store import get_active_session_user

_AUTH_REQUIRED_DETAIL = "Sesión requerida o expirada. Inicia sesión para continuar."


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def get_current_user(
    session_cookie: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    authorization: str | None = Header(default=None),
) -> dict:
    """Exige una sesión válida en cookie o Bearer token; responde 401 si falta."""
    token = session_cookie or _extract_bearer_token(authorization)
    claims = decode_access_token(token) if token else None
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_AUTH_REQUIRED_DETAIL,
        )

    try:
        user = get_active_session_user(claims["sid"], claims["sub"])
    except psycopg2.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo validar la sesión en la base de datos.",
        ) from exc

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_AUTH_REQUIRED_DETAIL,
        )
    return user


def get_current_user_id(current_user: dict = Depends(get_current_user)) -> str:
    """Devuelve el UUID del usuario autenticado para aislamiento multitenant."""
    return current_user["id"]
