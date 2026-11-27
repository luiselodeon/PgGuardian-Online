"""
PgGuardian API — Punto de Entrada

Aplicación FastAPI que expone todos los detectores de salud de PostgreSQL
a través de endpoints REST agrupados por categoría.

Incluye:
- CORS configurado para el frontend
- Routers para cada módulo detector
- Endpoint /api/full-scan que ejecuta todos los detectores
- Endpoint /api/health-check para verificar conectividad

Nota: Todos los routers bajo la carpeta de /routers, así como los archivos 
bajo la carpeta de /api fueron normalizados con ayuda de la Inteligencia Artificial.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os

from fastapi import FastAPI, Depends, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from api.auth import get_current_user
from api.database import get_connection
from api.schemas import FullScanResponse
from security.rate_limit import auth_rate_limiter, extract_client_ip
from services.analysis_store import connect_app_db, init_app_db_schema
from services.sandbox_cleanup import sandbox_cleanup_loop
from services.scan_service import run_full_scan

# Importar routers
from api.routers import analyses as analyses_router
from api.routers import auth as auth_router
from api.routers import bloat as bloat_router
from api.routers import config as config_router
from api.routers import health as health_router
from api.routers import indexes as indexes_router
from api.routers import queries as queries_router

logger = logging.getLogger("pgguardian.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el esquema de app_db y el ciclo de limpieza sandbox (24 h)."""
    await run_in_threadpool(init_app_db_schema)
    stop_event = asyncio.Event()
    cleanup_task = asyncio.create_task(sandbox_cleanup_loop(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        await cleanup_task


app = FastAPI(
    title="PgGuardian API",
    description="API de diagnóstico de salud para PostgreSQL",
    version="1.0.0",
    lifespan=lifespan,
)

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",    # Para seguir probando localmente
    "http://127.0.0.1:5173",
    "https://pgguardian-frontend.onrender.com",
]


def _get_cors_origins() -> list[str]:
    """Lee CORS_ORIGINS separado por comas (RF-03.5) o usa los orígenes locales."""
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if not raw:
        return list(_DEFAULT_CORS_ORIGINS)
    parsed = [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
    return parsed or list(_DEFAULT_CORS_ORIGINS)


origins = _get_cors_origins()

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_RATE_LIMITED_AUTH_PATHS = frozenset({"/api/auth/login", "/api/auth/register"})
_VALIDATION_MSG_ES = {
    "missing": "Este campo es obligatorio.",
    "json_invalid": "El cuerpo JSON de la petición no es válido.",
    "string_type": "El valor debe ser una cadena de texto.",
    "int_parsing": "El valor debe ser un número entero válido.",
    "int_type": "El valor debe ser un número entero.",
    "bool_parsing": "El valor debe ser booleano.",
}


@app.middleware("http")
async def enforce_auth_rate_limit(request: Request, call_next):
    """Limita login y registro a 10 peticiones por minuto por IP (RNF-02)."""
    if request.method == "POST" and request.url.path in _RATE_LIMITED_AUTH_PATHS:
        client_ip = extract_client_ip(request)
        allowed, retry_after = auth_rate_limiter.check(request.url.path, client_ip)
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after)},
                content={
                    "detail": (
                        "Demasiadas peticiones desde tu dirección IP. "
                        f"Máximo 10 solicitudes por minuto; intenta en {retry_after} s."
                    )
                },
            )
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def spanish_validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
):
    """Normaliza errores de validación FastAPI/Pydantic al español (RNF-04)."""
    translated = []
    for err in exc.errors():
        item = dict(err)
        err_type = item.get("type", "")
        raw_msg = str(item.get("msg", ""))
        if err_type in _VALIDATION_MSG_ES:
            item["msg"] = _VALIDATION_MSG_ES[err_type]
        elif raw_msg.startswith("Value error, "):
            item["msg"] = raw_msg[len("Value error, "):]
        item.pop("ctx", None)
        translated.append(item)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": translated},
    )

# Registrar routers (RF-02.5: detectores y análisis protegidos por sesión)
protected = [Depends(get_current_user)]
app.include_router(analyses_router.router)
app.include_router(auth_router.router)
app.include_router(bloat_router.router, dependencies=protected)
app.include_router(config_router.router, dependencies=protected)
app.include_router(health_router.router, dependencies=protected)
app.include_router(indexes_router.router, dependencies=protected)
app.include_router(queries_router.router, dependencies=protected)


@app.get("/api/health-check")
def health_check():
    """Verifica conectividad con PostgreSQL sin filtrar detalles internos (RF-04.6).

    Local (DB_HOST definida): TiendaDB vía get_connection().
    Producción (DB_HOST no definida): app_db con connect_timeout=2.
    La respuesta contiene únicamente la clave `status`; el detalle del error
    va solo al log del servidor.
    """
    conn_gen = None
    conn = None
    try:
        if os.getenv("DB_HOST"):
            conn_gen = get_connection()
            conn = next(conn_gen)
        else:
            conn = connect_app_db(connect_timeout=2)
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return {"status": "ok"}
    except Exception as exc:
        logger.error(
            "health-check falló [%s]: %s: %s",
            datetime.now(timezone.utc).isoformat(),
            type(exc).__name__,
            exc,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error"},
        )
    finally:
        if conn_gen is not None:
            conn_gen.close()
        elif conn is not None:
            conn.close()


@app.get("/api/full-scan", response_model=FullScanResponse, dependencies=[Depends(get_current_user)])
def full_scan(
    conn=Depends(get_connection),
):
    """
    Ejecuta TODOS los detectores sobre la conexión fija local (TiendaDB)
    y devuelve un reporte consolidado con health score calculado.
    """
    return run_full_scan(conn, is_sandbox=False)
