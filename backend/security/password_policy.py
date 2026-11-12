"""
PgGuardian — Políticas de Contraseñas y Validación de Credenciales (RF-02.1 y RF-02.2)

Centraliza la normalización de correo electrónico, la validación de longitud
estricta (12 a 128 caracteres), la verificación contra correo/parte local y el
bloqueo frente a la lista de contraseñas comunes (>= 10,000 entradas).
"""

from functools import lru_cache
from pathlib import Path
import re

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128
MAX_EMAIL_LENGTH = 255
MIN_COMMON_PASSWORD_ENTRIES = 10_000

_COMMON_PASSWORDS_FILE = Path(__file__).with_name("common_passwords.txt")
_EMAIL_RE = re.compile(
    r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+$"
)


def normalize_email(email: str) -> str:
    """Normaliza y valida el formato básico del correo electrónico."""
    if not isinstance(email, str):
        raise ValueError("Ingresa un correo electrónico válido.")
    cleaned = email.strip().lower()
    if (
        not cleaned
        or len(cleaned) > MAX_EMAIL_LENGTH
        or ".." in cleaned
        or not _EMAIL_RE.match(cleaned)
    ):
        raise ValueError("Ingresa un correo electrónico válido.")
    return cleaned


@lru_cache(maxsize=1)
def load_common_passwords() -> frozenset[str]:
    """Carga en memoria el conjunto de contraseñas comunes en minúsculas."""
    if not _COMMON_PASSWORDS_FILE.is_file():
        raise RuntimeError(
            f"No se encontró el catálogo de contraseñas comunes en {_COMMON_PASSWORDS_FILE}."
        )
    entries: set[str] = set()
    with _COMMON_PASSWORDS_FILE.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            item = line.strip().lower()
            if item:
                entries.add(item)
    if len(entries) < MIN_COMMON_PASSWORD_ENTRIES:
        raise RuntimeError(
            f"El catálogo de contraseñas comunes debe tener al menos {MIN_COMMON_PASSWORD_ENTRIES} entradas."
        )
    return frozenset(entries)


def is_common_password(password: str) -> bool:
    """Indica si la contraseña coincide (sin distinguir mayúsculas) con una común."""
    common = load_common_passwords()
    lowered = password.lower()
    return lowered in common or lowered.strip() in common


def validate_password_policy(
    password: str,
    *,
    email: str | None = None,
    password_confirm: str | None = None,
) -> None:
    """Valida las reglas RF-02.1 y RF-02.2 con mensajes de error en español."""
    if not isinstance(password, str):
        raise ValueError("La contraseña debe ser una cadena de texto válida.")

    if len(password) < MIN_PASSWORD_LENGTH or len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(
            f"La contraseña debe tener entre {MIN_PASSWORD_LENGTH} y {MAX_PASSWORD_LENGTH} caracteres."
        )

    if not password.strip():
        raise ValueError("La contraseña no puede estar compuesta solo por espacios.")

    if password_confirm is not None and password != password_confirm:
        raise ValueError("Las contraseñas no coinciden.")

    if email:
        normalized_email = email.strip().lower()
        local_part = normalized_email.split("@", 1)[0]
        pwd_lower = password.lower()
        if (normalized_email and normalized_email in pwd_lower) or (
            local_part and local_part in pwd_lower
        ):
            raise ValueError(
                "La contraseña no puede contener tu correo electrónico ni el nombre de usuario del correo."
            )

    if is_common_password(password):
        raise ValueError(
            "Esta contraseña es demasiado común. Elige una contraseña más segura."
        )
