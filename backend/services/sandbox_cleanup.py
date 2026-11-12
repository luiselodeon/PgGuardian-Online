"""
PgGuardian — Limpieza Programada de Bases Sandbox (RF-01.7)

Ejecuta periódicamente en segundo plano la purga de bases sandbox que
superaron las 24 horas desde su creación, conservando intactos los
reportes históricos en app_db.
"""

import asyncio
import logging
import os

from starlette.concurrency import run_in_threadpool

from services.analysis_store import (
    find_expired_active_sandboxes,
    mark_sandbox_destroyed,
)
from services.sandbox_runner import drop_sandbox_db

logger = logging.getLogger("pgguardian.sandbox_cleanup")

DEFAULT_CLEANUP_INTERVAL_SECONDS = 300


def cleanup_expired_sandboxes(limit: int = 50) -> int:
    """Elimina en sandbox_db las bases vencidas (>= 24 h) y marca su estado en app_db."""
    expired = find_expired_active_sandboxes(limit=limit)
    destroyed_count = 0
    for item in expired:
        db_name = item["sandbox_db_name"]
        if drop_sandbox_db(db_name):
            mark_sandbox_destroyed(item["id"])
            destroyed_count += 1
        else:
            logger.warning("No se pudo purgar el sandbox expirado '%s'.", db_name)
    return destroyed_count


async def sandbox_cleanup_loop(stop_event: asyncio.Event, interval_seconds: int | None = None) -> None:
    """Ciclo ligero en segundo plano dentro del lifespan de FastAPI."""
    interval = interval_seconds or int(
        os.getenv("SANDBOX_CLEANUP_INTERVAL_SECONDS", str(DEFAULT_CLEANUP_INTERVAL_SECONDS))
    )
    while not stop_event.is_set():
        try:
            purged = await run_in_threadpool(cleanup_expired_sandboxes)
            if purged > 0:
                logger.info("Limpieza programada completada: %d sandbox(es) purgados.", purged)
        except Exception as exc:
            logger.warning("Error durante limpieza programada de sandboxes: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue

