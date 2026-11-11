"""
PgGuardian — Dependencia de Identidad de Usuario (RF-01.8)

Extrae el identificador de usuario de la petición actual para aplicar
aislamiento multitenant sobre análisis mientras se integra el flujo completo
de autenticación y sesiones de RF-02.
"""

from fastapi import Cookie, Header, HTTPException, status


def get_current_user_id(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    session_user: str | None = Cookie(default=None, alias="pgguardian_user"),
) -> str:
    """
    Obtiene y valida el identificador del usuario propietario de la sesión.
    shortcut: lee cabecera X-User-Id o cookie pgguardian_user hasta integrar JWT/sessions en RF-02.
    """
    raw = (x_user_id or session_user or "").strip()
    if not raw or len(raw) > 128 or any(ord(ch) < 32 for ch in raw):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión requerida: autentícate o envía un identificador de usuario válido.",
        )
    return raw

