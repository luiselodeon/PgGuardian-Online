"""
PgGuardian — Schemas de respuesta genéricos

Modelos Pydantic que envuelven la metadata de cada respuesta
sin acoplar la estructura interna de los datos.
Usa dict[str, Any] para ser compatible con cualquier base de datos PostgreSQL.
"""

from datetime import datetime
from typing import Any
from pydantic import BaseModel


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

