"""
PgGuardian — Schemas de respuesta genéricos

Modelos Pydantic que envuelven la metadata de cada respuesta
sin acoplar la estructura interna de los datos.
Usa dict[str, Any] para ser compatible con cualquier base de datos PostgreSQL.
"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, field_validator, model_validator

from security.password_policy import normalize_email, validate_password_policy


class DetectorResponse(BaseModel):
    """Respuesta estándar para cualquier detector individual."""
    status: str                     # "ok" | "warning" | "error"
    detector: str                   # Nombre del detector ejecutado
    count: int                      # Cantidad de resultados/hallazgos
    data: list[dict[str, Any]]      # Resultados crudos — estructura genérica
    executed_at: datetime


class FullScanResponse(BaseModel):
    """Respuesta del escaneo completo que agrupa todos los detectores."""
    health_score: int               # 0-100
    total_findings: int
    categories: dict[str, Any]      # Resultados agrupados por categoría
    executed_at: datetime
    is_sandbox: bool = False
    evaluated_detectors: int = 22
    not_applicable_detectors: int = 0


class AnalysisFileSummary(BaseModel):
    """Resumen de un archivo .sql validado para un análisis."""
    order: int
    filename: str
    size_bytes: int
    encoding: str
    line_count: int


class AnalysisCreateResponse(BaseModel):
    """Respuesta al validar, ejecutar en sandbox y registrar un análisis."""
    id: str
    user_id: str
    name: str
    status: str
    message: str
    file_count: int
    total_size_bytes: int
    sandbox_db_name: str
    sandbox_status: str
    sandbox_expires_at: datetime
    sandbox_destroyed_at: datetime | None = None
    executed_statements: int
    execution_time_ms: int
    files: list[AnalysisFileSummary]
    scan: FullScanResponse
    created_at: datetime


class AnalysisSummaryItem(BaseModel):
    """Resumen de un análisis para el listado del historial."""
    id: str
    user_id: str
    name: str
    status: str
    file_count: int
    total_size_bytes: int
    sandbox_db_name: str
    sandbox_status: str
    sandbox_expires_at: datetime
    sandbox_destroyed_at: datetime | None = None
    executed_statements: int
    execution_time_ms: int
    health_score: int
    total_findings: int
    created_at: datetime


class AnalysisListResponse(BaseModel):
    """Listado de análisis históricos filtrados por el usuario autenticado."""
    items: list[AnalysisSummaryItem]
    total: int


class AnalysisDeleteResponse(BaseModel):
    """Respuesta tras eliminar un análisis propio."""
    id: str
    message: str


class UserRegisterRequest(BaseModel):
    """Solicitud de registro de usuario (RF-02.1 y RF-02.2)."""
    name: str
    email: str
    password: str
    password_confirm: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("El nombre es obligatorio.")
        if len(clean) > 150:
            raise ValueError("El nombre no puede exceder los 150 caracteres.")
        return clean

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @model_validator(mode="after")
    def validate_passwords(self) -> "UserRegisterRequest":
        validate_password_policy(
            self.password,
            email=self.email,
            password_confirm=self.password_confirm,
        )
        return self


class UserRegisterResponse(BaseModel):
    """Respuesta segura tras registrar un usuario (sin exponer password_hash)."""
    id: str
    name: str
    email: str
    created_at: datetime
    message: str


class AuthUserSummary(BaseModel):
    """Datos públicos del usuario autenticado."""
    id: str
    name: str
    email: str


class UserLoginRequest(BaseModel):
    """Credenciales para iniciar sesión (RF-02.4)."""
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError("Ingresa tu contraseña.")
        return value


class UserLoginResponse(BaseModel):
    """Respuesta al iniciar sesión exitosamente."""
    user: AuthUserSummary
    message: str


class UserLogoutResponse(BaseModel):
    """Respuesta al cerrar sesión."""
    message: str


class PasswordChangeRequest(BaseModel):
    """Solicitud de cambio de contraseña con verificación de la actual (RF-02.6)."""
    current_password: str
    new_password: str
    new_password_confirm: str

    @field_validator("current_password")
    @classmethod
    def validate_current_password(cls, value: str) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError("Ingresa tu contraseña actual.")
        return value

    @model_validator(mode="after")
    def validate_new_passwords(self) -> "PasswordChangeRequest":
        validate_password_policy(
            self.new_password,
            password_confirm=self.new_password_confirm,
        )
        return self


class PasswordChangeResponse(BaseModel):
    """Respuesta tras actualizar la contraseña y revocar sesiones previas."""
    message: str
    revoked_sessions: int

