"""
PgGuardian — Utilidades Criptográficas Argon2id (RF-02.3 / CA-04)

Configura PasswordHasher de argon2-cffi con los parámetros mínimos OWASP:
- Algoritmo: Argon2id (Type.ID)
- Memoria: 19 MiB (memory_cost=19456 KiB)
- Iteraciones: 2 (time_cost=2)
- Paralelismo: 1 (parallelism=1)
- Sal aleatoria criptográfica: 16 bytes (salt_len=16)
"""

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

ARGON2_TIME_COST = 2
ARGON2_MEMORY_COST = 19456
ARGON2_PARALLELISM = 1
ARGON2_SALT_LEN = 16
ARGON2_HASH_LEN = 32

PASSWORD_HASHER = PasswordHasher(
    time_cost=ARGON2_TIME_COST,
    memory_cost=ARGON2_MEMORY_COST,
    parallelism=ARGON2_PARALLELISM,
    hash_len=ARGON2_HASH_LEN,
    salt_len=ARGON2_SALT_LEN,
    type=Type.ID,
)


def hash_password(password: str) -> str:
    """Genera un hash Argon2id en formato PHC ($argon2id$...) sin texto plano."""
    if not isinstance(password, str) or not password:
        raise ValueError("La contraseña no puede estar vacía.")
    hashed = PASSWORD_HASHER.hash(password)
    if not hashed.startswith("$argon2id$"):
        raise RuntimeError("El hash generado no cumple el formato PHC Argon2id.")
    return hashed


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica en tiempo constante una contraseña contra su hash PHC Argon2id."""
    if not password or not password_hash or not password_hash.startswith("$argon2id$"):
        return False
    try:
        return bool(PASSWORD_HASHER.verify(password_hash, password))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False

