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

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from api.database import get_connection
from api.schemas import FullScanResponse
from services.analysis_store import init_app_db_schema
from services.sandbox_cleanup import sandbox_cleanup_loop
from services.scan_service import run_full_scan

# Importar routers
from api.routers import analyses as analyses_router
from api.routers import bloat as bloat_router
from api.routers import config as config_router
from api.routers import health as health_router
from api.routers import indexes as indexes_router
from api.routers import queries as queries_router


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

origins = [
    "http://localhost:5173",    # Para seguir probando localmente
    "https://pgguardian-frontend.onrender.com" 
]

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(analyses_router.router)
app.include_router(bloat_router.router)
app.include_router(config_router.router)
app.include_router(health_router.router)
app.include_router(indexes_router.router)
app.include_router(queries_router.router)


@app.get("/api/health-check")
def health_check(conn=Depends(get_connection)):
    """Verifica que la API puede conectarse a PostgreSQL."""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
        return {
            "status": "ok",
            "database": "connected",
            "pg_version": version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "status": "error",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/api/full-scan", response_model=FullScanResponse)
def full_scan(conn=Depends(get_connection)):
    """
    Ejecuta TODOS los detectores sobre la conexión fija local (TiendaDB)
    y devuelve un reporte consolidado con health score calculado.
    """
    return run_full_scan(conn, is_sandbox=False)
