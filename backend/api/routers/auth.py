"""
PgGuardian API — Router de Autenticación y Gestión de Sesiones (RF-02.1 a RF-02.6)

Expone registro, login con bloqueo de 15 min tras 5 fallos, consulta de sesión
activa (/me), cierre de sesión (/logout) y cambio de contraseña (/password).
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
import psycopg2

from api.auth import get_current_user
from api.schemas import (
    AuthUserSummary,
    PasswordChangeResponse,
    PasswordChangeRequest,
    UserLoginRequest,
    UserLoginResponse,
    UserLogoutResponse,
    UserRegisterRequest,
    UserRegisterResponse,
)
from security.hashing import hash_password, verify_password
from security.password_policy import validate_password_policy
from security.sessions import (
    SESSION_TTL_HOURS,
    clear_session_cookie,
    create_access_token,
    set_session_cookie,
)
from services.user_store import (
    EmailAlreadyExistsError,
    create_session,
    create_user,
    get_user_by_email,
    get_user_with_hash_by_id,
    record_failed_login,
    reset_failed_logins,
    revoke_other_sessions,
    revoke_session,
    update_user_password,
)

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])

MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
_INVALID_CREDENTIALS_MSG = "Credenciales inválidas."
# Hash Argon2id dummy (OWASP) para igualar tiempos ante correos inexistentes.
_DUMMY_ARGON2_HASH = (
    "$argon2id$v=19$m=19456,t=2,p=1$AAAAAAAAAAAAAAAAAAAAAA$"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)


def _issue_session(response: Response, user_id: str) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    session = create_session(user_id, expires_at=expires_at)
    token = create_access_token(
        user_id=user_id,
        session_id=session["id"],
        expires_at=expires_at,
    )
    set_session_cookie(response, token)


@router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(payload: UserRegisterRequest, response: Response):
    """Registra un usuario nuevo en app_db, crea sesión e inicia cookie HttpOnly."""
    try:
        if get_user_by_email(payload.email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este correo electrónico ya está registrado.",
            )
        password_hash = hash_password(payload.password)
        user = create_user(
            name=payload.name,
            email=payload.email,
            password_hash=password_hash,
        )
        _issue_session(response, user["id"])
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except psycopg2.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo completar el registro en la base de datos de usuarios.",
        ) from exc

    return UserRegisterResponse(
        id=user["id"],
        name=user["name"],
        email=user["email"],
        created_at=user["created_at"],
        message="Usuario registrado correctamente.",
    )


@router.post("/login", response_model=UserLoginResponse)
def login_user(payload: UserLoginRequest, response: Response):
    """Autentica por correo/contraseña y bloquea 15 min tras 5 intentos fallidos."""
    now = datetime.now(timezone.utc)
    try:
        user = get_user_by_email(payload.email)
    except psycopg2.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo verificar la cuenta en la base de datos de usuarios.",
        ) from exc

    if user and user.get("locked_until"):
        locked_until = user["locked_until"]
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            remaining_seconds = max(1, int((locked_until - now).total_seconds()))
            remaining_minutes = max(1, (remaining_seconds + 59) // 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Cuenta bloqueada temporalmente por demasiados intentos fallidos. "
                    f"Intenta nuevamente en {remaining_minutes} minuto(s)."
                ),
                headers={"Retry-After": str(remaining_seconds)},
            )

    if not user:
        verify_password(payload.password, _DUMMY_ARGON2_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS_MSG,
        )

    if not verify_password(payload.password, user["password_hash"]):
        try:
            record_failed_login(
                user["id"],
                max_attempts=MAX_FAILED_LOGIN_ATTEMPTS,
                lock_minutes=LOCKOUT_MINUTES,
            )
        except psycopg2.Error as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo actualizar el estado de autenticación.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS_MSG,
        )

    try:
        if user.get("failed_login_attempts", 0) > 0 or user.get("locked_until") is not None:
            reset_failed_logins(user["id"])
        _issue_session(response, user["id"])
    except psycopg2.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo iniciar la sesión en la base de datos.",
        ) from exc

    return UserLoginResponse(
        user=AuthUserSummary(id=user["id"], name=user["name"], email=user["email"]),
        message="Sesión iniciada correctamente.",
    )


@router.get("/me", response_model=AuthUserSummary)
def get_me(current_user: dict = Depends(get_current_user)):
    """Devuelve el usuario autenticado de la sesión activa."""
    return AuthUserSummary(
        id=current_user["id"],
        name=current_user["name"],
        email=current_user["email"],
    )


@router.post("/logout", response_model=UserLogoutResponse)
def logout_user(response: Response, current_user: dict = Depends(get_current_user)):
    """Revoca la sesión actual en app_db y limpia la cookie HttpOnly."""
    try:
        revoke_session(current_user["session_id"])
    except psycopg2.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo cerrar la sesión en la base de datos.",
        ) from exc
    clear_session_cookie(response)
    return UserLogoutResponse(message="Sesión cerrada correctamente.")


@router.post("/password", response_model=PasswordChangeResponse)
def change_password(
    payload: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Cambia la contraseña verificando la actual y revoca las demás sesiones."""
    try:
        user_record = get_user_with_hash_by_id(current_user["id"])
    except psycopg2.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo consultar el usuario en la base de datos.",
        ) from exc

    if not user_record or not verify_password(
        payload.current_password, user_record["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La contraseña actual es incorrecta.",
        )

    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La nueva contraseña debe ser diferente a la contraseña actual.",
        )

    try:
        validate_password_policy(
            payload.new_password,
            email=user_record["email"],
            password_confirm=payload.new_password_confirm,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    new_hash = hash_password(payload.new_password)
    try:
        update_user_password(user_record["id"], new_hash)
        revoked = revoke_other_sessions(user_record["id"], current_user["session_id"])
    except psycopg2.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo actualizar la contraseña en la base de datos.",
        ) from exc

    return PasswordChangeResponse(
        message="Contraseña actualizada correctamente. Se cerraron tus demás sesiones.",
        revoked_sessions=revoked,
    )
