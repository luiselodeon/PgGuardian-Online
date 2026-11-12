"""
PgGuardian — Orquestador de Escaneo Parametrizado (RF-01.5 y RF-01.6)

Ejecuta todos los detectores sobre cualquier conexión PostgreSQL inyectada
(TiendaDB o una base temporal en sandbox_db). Cuando is_sandbox=True,
marca los detectores dependientes de tráfico/estadísticas en vivo como
'no_aplica' y normaliza el health score únicamente sobre los detectores
evaluados.
"""

from datetime import datetime, timezone
from typing import Any

from api.schemas import FullScanResponse
from detectors.bloat import (
    check_dead_tuples,
    check_disabled_autovacuum,
    check_table_bloat,
)
from detectors.config import (
    check_pg_stat_statements_limit,
    check_slow_query_logging,
    evaluate_pg_stat_statements_max,
    evaluate_shared_buffers,
    evaluate_work_mem,
    get_shared_buffers,
    get_work_mem,
)
from detectors.health import (
    check_idle_in_transaction,
    check_partitioning_candidates,
)
from detectors.indexes import (
    check_covering_index_candidates,
    check_duplicate_indexes,
    check_leading_wildcard_searches,
    check_missing_indexes,
    check_missing_partial_indexes,
    check_obsolete_stats,
    check_unused_indexes,
)
from detectors.queries import (
    check_pg_stat_statements,
    detect_seq_scan_queries,
    evaluate_database_temp_usage,
    evaluate_explain_spills,
    evaluate_temp_spills,
    evaluate_top_time_queries,
)

NOT_APPLICABLE_REASON = (
    "No aplica en bases sandbox recién creadas porque no cuentan con "
    "estadísticas acumuladas ni métricas de tráfico en vivo."
)

# Detectores dependientes de estadísticas acumuladas o actividad en vivo (RF-01.6)
SANDBOX_NOT_APPLICABLE_DETECTORS = frozenset({
    "idle_in_transaction",
    "unused_indexes",
    "covering_candidates",
    "wildcard_searches",
    "temp_spills",
    "seq_scans",
    "top_time_queries",
    "db_temp_usage",
    "explain_spills",
})

# Pesos nominales por detector para normalización del score (0-100)
_DETECTOR_WEIGHTS = {
    "table_bloat": 5,
    "disabled_autovacuum": 10,
    "dead_tuples": 5,
    "work_mem_evaluation": 8,
    "shared_buffers_evaluation": 8,
    "pg_stat_max_evaluation": 5,
    "pg_stat_limit": 3,
    "slow_query_logging": 5,
    "partitioning_candidates": 2,
    "idle_in_transaction": 10,
    "missing_indexes": 6,
    "duplicate_indexes": 4,
    "unused_indexes": 3,
    "missing_partial": 3,
    "obsolete_stats": 5,
    "wildcard_searches": 3,
    "covering_candidates": 2,
    "temp_spills": 8,
    "seq_scans": 4,
    "top_time_queries": 4,
    "db_temp_usage": 5,
    "explain_spills": 6,
}


# Guía de remediación estándar en español por detector (RF / UX)
_REMEDIATION_CATALOG = {
    "table_bloat": {
        "title": "Bloat / fragmentación en tabla",
        "severity": "MEDIUM",
        "recommendation": "Recuperar páginas desperdiciadas y ajustar fillfactor o autovacuum si la tabla recibe muchos UPDATE/DELETE.",
        "steps": [
            "Ejecuta VACUUM (VERBOSE, ANALYZE) para liberar tuplas muertas sin bloqueo exclusivo.",
            "Si el bloat supera el 30-40% y requiere devolver espacio al disco, programa pg_repack o VACUUM FULL en ventana de mantenimiento.",
            "Revisa la frecuencia de autovacuum (autovacuum_vacuum_scale_factor) para tablas con alta rotación.",
        ],
    },
    "disabled_autovacuum": {
        "title": "Autovacuum desactivado en tabla",
        "severity": "HIGH",
        "recommendation": "Reactivar autovacuum inmediatamente para evitar acumulación de tuplas muertas, bloat severo y riesgo de transaction ID wraparound.",
        "steps": [
            "Restablece el parámetro con ALTER TABLE <tabla> RESET (autovacuum_enabled).",
            "Ejecuta VACUUM ANALYZE <tabla> después de habilitarlo para limpiar tuplas acumuladas.",
        ],
    },
    "dead_tuples": {
        "title": "Acumulación de filas muertas (dead tuples)",
        "severity": "MEDIUM",
        "recommendation": "Ejecutar mantenimiento VACUUM y validar que ninguna transacción larga ('idle in transaction') impida la limpieza.",
        "steps": [
            "Si el porcentaje supera 10%, ejecuta VACUUM ANALYZE sobre la tabla.",
            "Si supera 20%, evalúa VACUUM FULL ANALYZE o pg_repack en ventana controlada.",
            "Verifica que no existan sesiones largas bloqueando el horizonte de transacciones.",
        ],
    },
    "work_mem_evaluation": {
        "title": "work_mem insuficiente",
        "severity": "MEDIUM",
        "recommendation": "Aumentar work_mem de forma gradual (por sesión o global) considerando el número máximo de conexiones concurrentes.",
        "steps": [
            "Calcula la memoria disponible: RAM_disponible / (max_connections * 2).",
            "Prueba primero a nivel de sesión (SET work_mem = '32MB') en consultas pesadas antes de cambiar postgresql.conf.",
        ],
    },
    "shared_buffers_evaluation": {
        "title": "shared_buffers bajo",
        "severity": "MEDIUM",
        "recommendation": "Asignar aproximadamente 25% de la RAM del servidor dedicado a shared_buffers para reducir lecturas físicas desde disco.",
        "steps": [
            "Ajusta shared_buffers en postgresql.conf o mediante ALTER SYSTEM.",
            "Reinicia PostgreSQL para aplicar el cambio en memoria compartida.",
        ],
    },
    "pg_stat_max_evaluation": {
        "title": "pg_stat_statements.max bajo",
        "severity": "MEDIUM",
        "recommendation": "Incrementar pg_stat_statements.max (ej. 5000) para evitar pérdida de estadísticas por desalojo.",
        "steps": [
            "Configura pg_stat_statements.max = 5000 en postgresql.conf.",
            "Reinicia el servidor PostgreSQL para aplicar el nuevo tamaño de tabla hash.",
        ],
    },
    "pg_stat_limit": {
        "title": "Límite bajo de tracking en pg_stat_statements",
        "severity": "LOW",
        "recommendation": "Ampliar pg_stat_statements.max para conservar suficiente historial de consultas únicas.",
        "steps": [
            "Sube pg_stat_statements.max a 5000-10000 en postgresql.conf.",
            "Reinicia la instancia y valida que no haya eviction en pg_stat_statements_info.",
        ],
    },
    "slow_query_logging": {
        "title": "Registro de consultas lentas desactivado",
        "severity": "MEDIUM",
        "recommendation": "Habilitar log_min_duration_statement (ej. 500ms o 1000ms) para auditar consultas lentas en bitácora.",
        "steps": [
            "Define log_min_duration_statement = '1000ms' en postgresql.conf o ALTER SYSTEM.",
            "Ejecuta SELECT pg_reload_conf() para activar el registro sin reiniciar.",
        ],
    },
    "partitioning_candidates": {
        "title": "Tabla candidata a particionamiento o retención",
        "severity": "LOW",
        "recommendation": "Evaluar particionamiento por rango temporal y políticas de purga/archivado para tablas con crecimiento continuo.",
        "steps": [
            "Define una columna de particionamiento (por ejemplo created_at) según los filtros principales.",
            "Implementa particiones mensuales/anuales con retención automática para evitar escaneos masivos.",
        ],
    },
    "idle_in_transaction": {
        "title": "Sesión prolongada 'idle in transaction'",
        "severity": "HIGH",
        "recommendation": "Finalizar sesiones colgadas y configurar idle_in_transaction_session_timeout para evitar bloqueos y bloat.",
        "steps": [
            "Revisa la aplicación origen para asegurar COMMIT o ROLLBACK oportunos.",
            "Cancela la sesión problemática con pg_terminate_backend(<pid>) si bloquea recursos.",
            "Configura idle_in_transaction_session_timeout (ej. '5min') como protección preventiva.",
        ],
    },
    "missing_partial": {
        "title": "Oportunidad de índice parcial",
        "severity": "LOW",
        "recommendation": "Crear un índice parcial (WHERE columna != valor_dominante) para acelerar búsquedas sobre la minoría de filas y ahorrar espacio.",
        "steps": [
            "Confirma las consultas que filtran los valores minoritarios de la columna.",
            "Crea el índice usando CREATE INDEX CONCURRENTLY con cláusula WHERE selectiva.",
        ],
    },
    "missing_indexes": {
        "title": "Llave foránea sin índice",
        "severity": "HIGH",
        "recommendation": "Crear un índice B-Tree sobre la columna de llave foránea para acelerar JOINs y evitar bloqueos/escaneos secuenciales al borrar registros padre.",
        "steps": [
            "Ejecuta CREATE INDEX CONCURRENTLY sobre la columna referenciada para no bloquear escrituras.",
            "Ejecuta ANALYZE sobre la tabla y verifica con EXPLAIN que los JOINs usen Index Scan.",
        ],
    },
    "duplicate_indexes": {
        "title": "Índices duplicados en la misma columna",
        "severity": "MEDIUM",
        "recommendation": "Eliminar los índices redundantes conservando uno solo para reducir almacenamiento y sobrecarga en INSERT/UPDATE/DELETE.",
        "steps": [
            "Verifica que ninguno sirva una restricción UNIQUE distinta antes de borrar.",
            "Elimina los duplicados sin bloquear tráfico mediante DROP INDEX CONCURRENTLY.",
        ],
    },
    "unused_indexes": {
        "title": "Índice sin uso registrado",
        "severity": "LOW",
        "recommendation": "Validar en una ventana representativa de tráfico y eliminar índices con 0 lecturas para acelerar escrituras.",
        "steps": [
            "Confirma que no corresponda a una restricción UNIQUE ni a reportes mensuales.",
            "Ejecuta DROP INDEX CONCURRENTLY si sigue sin scans tras el ciclo completo.",
        ],
    },
    "covering_candidates": {
        "title": "Candidato a índice cubriente (INCLUDE)",
        "severity": "LOW",
        "recommendation": "Agregar columnas proyectadas con INCLUDE para habilitar Index-Only Scans y evitar accesos al heap.",
        "steps": [
            "Identifica las columnas del SELECT que no forman parte del filtro WHERE.",
            "Crea el índice con CREATE INDEX CONCURRENTLY ... ON tabla(filtro) INCLUDE(cols).",
        ],
    },
    "obsolete_stats": {
        "title": "Estadísticas obsoletas del optimizador",
        "severity": "MEDIUM",
        "recommendation": "Ejecutar ANALYZE sobre la tabla para sincronizar pg_class y permitir al planner elegir planes óptimos.",
        "steps": [
            "Ejecuta ANALYZE <esquema>.<tabla> inmediatamente.",
            "Si la tabla crece rápido, reduce autovacuum_analyze_scale_factor (ej. 0.05).",
        ],
    },
    "wildcard_searches": {
        "title": "Búsqueda LIKE/ILIKE con wildcard inicial",
        "severity": "MEDIUM",
        "recommendation": "Los patrones '%texto%' invalidan índices B-Tree; usa extensión pg_trgm con índice GIN o Full-Text Search.",
        "steps": [
            "Habilita la extensión pg_trgm (permitida en PgGuardian).",
            "Crea un índice GIN con operador gin_trgm_ops sobre la columna buscada.",
        ],
    },
    "temp_spills": {
        "title": "Derrames a disco temporal (temp spills)",
        "severity": "HIGH",
        "recommendation": "Optimizar ordenamientos/agrupaciones o incrementar work_mem para evitar escrituras lentas en disco.",
        "steps": [
            "Inspecciona la consulta con EXPLAIN (ANALYZE, BUFFERS).",
            "Agrega índices que eviten Sort en disco o ajusta work_mem por sesión.",
        ],
    },
    "seq_scans": {
        "title": "Sequential Scan frecuente en consulta",
        "severity": "MEDIUM",
        "recommendation": "Añadir un índice adecuado a las columnas de filtrado WHERE/JOIN para evitar leer toda la tabla.",
        "steps": [
            "Analiza el predicado WHERE de la consulta reportada con EXPLAIN.",
            "Crea el índice faltante con CREATE INDEX CONCURRENTLY y ejecuta ANALYZE.",
        ],
    },
    "top_time_queries": {
        "title": "Consulta con alto tiempo acumulado",
        "severity": "MEDIUM",
        "recommendation": "Revisar el plan de ejecución y frecuencia de llamada para reducir latencia o añadir caché/índices.",
        "steps": [
            "Ejecuta EXPLAIN (ANALYZE, BUFFERS) para detectar nodos costosos.",
            "Evalúa índices compuestos, paginación por cursor o reducción de columnas.",
        ],
    },
    "db_temp_usage": {
        "title": "Generación elevada de archivos temporales",
        "severity": "MEDIUM",
        "recommendation": "Identificar consultas con Sort/Hash grandes en pg_stat_statements y revisar work_mem.",
        "steps": [
            "Revisa las consultas con mayor temp_blks_written.",
            "Optimiza joins/agregaciones y ajusta work_mem de forma controlada.",
        ],
    },
    "explain_spills": {
        "title": "Sort o Hash en disco confirmado por EXPLAIN",
        "severity": "HIGH",
        "recommendation": "Reducir el volumen procesado antes del Sort/Hash mediante índices o aumentar work_mem.",
        "steps": [
            "Revisa los nodos 'external merge' o 'Batches > 1' en EXPLAIN.",
            "Crea índices alineados con ORDER BY / GROUP BY o incrementa work_mem.",
        ],
    },
}


def _resolve_severity(detector_key: str, row: dict[str, Any], default_severity: str) -> str:
    if row.get("severity"):
        sev = str(row["severity"]).upper()
        return "HIGH" if sev == "CRITICAL" else sev
    if row.get("stats_severity"):
        ss = str(row["stats_severity"]).upper()
        return {"CRITICAL": "HIGH", "WARNING": "MEDIUM"}.get(ss, ss)
    if detector_key == "table_bloat":
        pct = float(row.get("bloat_pct", 0) or 0)
        return "HIGH" if pct > 40 else ("MEDIUM" if pct > 20 else "OK")
    if detector_key == "dead_tuples":
        pct = float(row.get("dead_tuple_pct", 0) or 0)
        return "HIGH" if pct > 20 else ("MEDIUM" if pct > 10 else "OK")
    return default_severity


def _enrich_detector_rows(
    detector_key: str,
    category_label: str,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Garantiza título, categoría, severidad, recomendación y SQL uniforme por hallazgo."""
    meta = _REMEDIATION_CATALOG.get(detector_key)
    if not meta or not rows:
        return rows

    enriched: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict) or "error" in item:
            enriched.append(item)
            continue

        row = dict(item)
        row.setdefault("category", category_label)
        row.setdefault("title", row.get("finding_id") or meta["title"])
        severity = _resolve_severity(detector_key, row, meta["severity"])
        row["severity"] = severity

        if detector_key == "dead_tuples" and severity == "OK":
            row.setdefault(
                "recommendation",
                "La proporción de filas muertas está dentro del rango óptimo (≤ 10 %); mantener autovacuum activo.",
            )
            row.setdefault(
                "remediation_steps",
                ["Sin acción urgente requerida; monitorear periódicamente tras cargas masivas."],
            )
        else:
            row.setdefault("recommendation", meta["recommendation"])
            row.setdefault("remediation_steps", list(meta["steps"]))

        sql_snippet = (
            row.get("sql_remediation")
            or row.get("sql_recommendation")
            or row.get("sql_fix")
            or row.get("suggested_action")
        )
        if sql_snippet:
            row.setdefault("sql_remediation", sql_snippet)
        enriched.append(row)

    return enriched
def _serialize(rows: list) -> list[dict[str, Any]]:
    """Convierte RealDictRow a dict estándar para serialización JSON."""
    result = []
    for row in rows:
        item = {}
        for key, value in dict(row).items():
            if hasattr(value, "as_tuple"):
                item[key] = float(value)
            else:
                item[key] = value
        result.append(item)
    return result


def _safe_run(func, conn, serialize: bool = True) -> list[dict[str, Any]]:
    """Ejecuta un detector de forma segura, capturando excepciones."""
    try:
        result = func(conn)
        if result is None:
            return []
        if serialize and isinstance(result, list) and len(result) > 0:
            if hasattr(result[0], "items"):
                return _serialize(result)
        return result if isinstance(result, list) else [result]
    except Exception as exc:
        return [{"error": str(exc)}]


def _not_applicable_detector(label: str, category_label: str = "") -> dict[str, Any]:
    """Construye la entrada estándar 'no_aplica' retrocompatible para el frontend."""
    return {
        "label": label,
        "status": "no_aplica",
        "status_label": "No aplica",
        "reason": NOT_APPLICABLE_REASON,
        "count": 0,
        "data": [
            {
                "status": "no_aplica",
                "category": category_label or "Métricas en vivo",
                "title": "No aplica en entorno sandbox",
                "severity": "NO_APLICA",
                "evidence": NOT_APPLICABLE_REASON,
                "recommendation": (
                    "Ejecuta esta evaluación sobre una base con tráfico real para "
                    "recopilar estadísticas en PostgreSQL."
                ),
                "remediation_steps": [
                    "Evalúa este detector en producción o staging tras recibir consultas reales."
                ],
            }
        ],
    }


def _evaluated_detector(
    label: str,
    data: list[dict[str, Any]],
    *,
    detector_key: str = "",
    category_label: str = "",
) -> dict[str, Any]:
    enriched = _enrich_detector_rows(detector_key, category_label, data) if detector_key else data
    return {
        "label": label,
        "status": "warning" if len(enriched) > 0 else "ok",
        "count": len(enriched),
        "data": enriched,
    }


def _run_or_na(
    key: str,
    label: str,
    func,
    conn,
    *,
    category_label: str,
    is_sandbox: bool,
    serialize: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if is_sandbox and key in SANDBOX_NOT_APPLICABLE_DETECTORS:
        return _not_applicable_detector(label, category_label=category_label), []
    data = _safe_run(func, conn, serialize=serialize)
    entry = _evaluated_detector(label, data, detector_key=key, category_label=category_label)
    return entry, entry["data"]


def run_full_scan(conn, is_sandbox: bool = False) -> FullScanResponse:
    """
    Ejecuta el diagnóstico completo usando la conexión inyectada (`conn`).
    Cuando `is_sandbox=True`, excluye detectores de tráfico/actividad en vivo
    marcándolos como `no_aplica` y normaliza el health score sobre los activos.
    """
    now = datetime.now(timezone.utc)
    excluded = SANDBOX_NOT_APPLICABLE_DETECTORS if is_sandbox else frozenset()

    # Bloat
    table_bloat_entry, table_bloat = _run_or_na(
        "table_bloat", "Fragmentación (Bloat) en Tablas", check_table_bloat, conn,
        category_label="Bloat y Mantenimiento", is_sandbox=is_sandbox,
    )
    disabled_autovacuum_entry, disabled_autovacuum = _run_or_na(
        "disabled_autovacuum", "Autovacuum Desactivado", check_disabled_autovacuum, conn,
        category_label="Bloat y Mantenimiento", is_sandbox=is_sandbox,
    )
    dead_tuples_entry, dead_tuples = _run_or_na(
        "dead_tuples", "Tuplas Muertas", check_dead_tuples, conn,
        category_label="Bloat y Mantenimiento", is_sandbox=is_sandbox,
    )

    # Config (estática de pg_settings)
    work_mem_result = get_work_mem(conn)
    work_mem_data = (
        [{"name": work_mem_result[0], "setting": work_mem_result[1], "unit": work_mem_result[2]}]
        if work_mem_result
        else []
    )
    work_mem_eval = evaluate_work_mem(conn) or []

    shared_buffers_result = get_shared_buffers(conn)
    shared_buffers_data = (
        [{"name": shared_buffers_result[0], "setting": shared_buffers_result[1], "unit": shared_buffers_result[2]}]
        if shared_buffers_result
        else []
    )
    shared_buffers_eval = evaluate_shared_buffers(conn) or []

    pg_stat_max_eval = evaluate_pg_stat_statements_max(conn) or []
    pg_stat_limit = _safe_run(check_pg_stat_statements_limit, conn)
    slow_query_logging = _safe_run(check_slow_query_logging, conn)

    # Health
    partition_entry, partition_candidates = _run_or_na(
        "partitioning_candidates",
        "Candidatos a Particionamiento",
        check_partitioning_candidates,
        conn,
        category_label="Salud General",
        is_sandbox=is_sandbox,
    )
    idle_entry, idle_in_transaction = _run_or_na(
        "idle_in_transaction",
        "Sesiones Inactivas en Transacción",
        check_idle_in_transaction,
        conn,
        category_label="Salud General",
        is_sandbox=is_sandbox,
    )

    # Indexes
    missing_partial_entry, missing_partial = _run_or_na(
        "missing_partial",
        "Índices Parciales Faltantes",
        check_missing_partial_indexes,
        conn,
        category_label="Auditoría de Índices",
        is_sandbox=is_sandbox,
    )
    missing_indexes_entry, missing_indexes = _run_or_na(
        "missing_indexes",
        "FK Sin Índice",
        check_missing_indexes,
        conn,
        category_label="Auditoría de Índices",
        is_sandbox=is_sandbox,
    )
    duplicate_indexes_entry, duplicate_indexes = _run_or_na(
        "duplicate_indexes",
        "Índices Duplicados",
        check_duplicate_indexes,
        conn,
        category_label="Auditoría de Índices",
        is_sandbox=is_sandbox,
    )
    unused_indexes_entry, unused_indexes = _run_or_na(
        "unused_indexes",
        "Índices No Usados",
        check_unused_indexes,
        conn,
        category_label="Auditoría de Índices",
        is_sandbox=is_sandbox,
    )
    covering_entry, covering_candidates = _run_or_na(
        "covering_candidates",
        "Candidatos a Índice Cubriente",
        check_covering_index_candidates,
        conn,
        category_label="Auditoría de Índices",
        is_sandbox=is_sandbox,
    )
    obsolete_stats_entry, obsolete_stats = _run_or_na(
        "obsolete_stats",
        "Estadísticas Obsoletas",
        check_obsolete_stats,
        conn,
        category_label="Auditoría de Índices",
        is_sandbox=is_sandbox,
    )
    wildcard_entry, wildcard_searches = _run_or_na(
        "wildcard_searches",
        "Búsquedas con Comodín Inicial",
        check_leading_wildcard_searches,
        conn,
        category_label="Auditoría de Índices",
        is_sandbox=is_sandbox,
    )

    # Queries
    pg_stat_enabled = check_pg_stat_statements(conn)
    temp_spills_entry, temp_spills = _run_or_na(
        "temp_spills",
        "Derrames Temporales a Disco",
        evaluate_temp_spills,
        conn,
        category_label="Consultas Problemáticas",
        is_sandbox=is_sandbox,
        serialize=False,
    )
    seq_scans_entry, seq_scans = _run_or_na(
        "seq_scans",
        "Escaneos Secuenciales",
        detect_seq_scan_queries,
        conn,
        category_label="Consultas Problemáticas",
        is_sandbox=is_sandbox,
        serialize=False,
    )
    top_time_entry, top_time_queries = _run_or_na(
        "top_time_queries",
        "Consultas Más Lentas",
        evaluate_top_time_queries,
        conn,
        category_label="Consultas Problemáticas",
        is_sandbox=is_sandbox,
        serialize=False,
    )
    db_temp_entry, db_temp_usage = _run_or_na(
        "db_temp_usage",
        "Uso Temporal en BD",
        evaluate_database_temp_usage,
        conn,
        category_label="Consultas Problemáticas",
        is_sandbox=is_sandbox,
        serialize=False,
    )
    explain_entry, explain_spills = _run_or_na(
        "explain_spills",
        "Derrames Detectados por EXPLAIN",
        evaluate_explain_spills,
        conn,
        category_label="Consultas Problemáticas",
        is_sandbox=is_sandbox,
        serialize=False,
    )

    categories = {
        "bloat": {
            "label": "Fragmentación y Mantenimiento",
            "detectors": {
                "table_bloat": table_bloat_entry,
                "disabled_autovacuum": disabled_autovacuum_entry,
                "dead_tuples": dead_tuples_entry,
            },
        },
        "config": {
            "label": "Configuración",
            "detectors": {
                "work_mem": {
                    "label": "Valor Actual de work_mem",
                    "count": len(work_mem_data),
                    "data": work_mem_data,
                },
                "work_mem_evaluation": _evaluated_detector(
                    "Evaluación de work_mem", work_mem_eval,
                    detector_key="work_mem_evaluation", category_label="Configuración",
                ),
                "shared_buffers": {
                    "label": "Valor Actual de shared_buffers",
                    "count": len(shared_buffers_data),
                    "data": shared_buffers_data,
                },
                "shared_buffers_evaluation": _evaluated_detector(
                    "Evaluación de shared_buffers", shared_buffers_eval,
                    detector_key="shared_buffers_evaluation", category_label="Configuración",
                ),
                "pg_stat_max_evaluation": _evaluated_detector(
                    "Evaluación pg_stat_statements.max", pg_stat_max_eval,
                    detector_key="pg_stat_max_evaluation", category_label="Configuración",
                ),
                "pg_stat_limit": _evaluated_detector(
                    "Límite de Rastreo de Consultas", pg_stat_limit,
                    detector_key="pg_stat_limit", category_label="Configuración",
                ),
                "slow_query_logging": _evaluated_detector(
                    "Registro de Consultas Lentas", slow_query_logging,
                    detector_key="slow_query_logging", category_label="Configuración",
                ),
            },
        },
        "health": {
            "label": "Salud General",
            "detectors": {
                "partitioning_candidates": partition_entry,
                "idle_in_transaction": idle_entry,
            },
        },
        "indexes": {
            "label": "Auditoría de Índices",
            "detectors": {
                "missing_partial": missing_partial_entry,
                "missing_indexes": missing_indexes_entry,
                "duplicate_indexes": duplicate_indexes_entry,
                "unused_indexes": unused_indexes_entry,
                "covering_candidates": covering_entry,
                "obsolete_stats": obsolete_stats_entry,
                "wildcard_searches": wildcard_entry,
            },
        },
        "queries": {
            "label": "Consultas Problemáticas",
            "detectors": {
                "pg_stat_statements": {
                    "label": "pg_stat_statements",
                    "count": 1,
                    "data": [{"enabled": pg_stat_enabled}],
                },
                "temp_spills": temp_spills_entry,
                "seq_scans": seq_scans_entry,
                "top_time_queries": top_time_entry,
                "db_temp_usage": db_temp_entry,
                "explain_spills": explain_entry,
            },
        },
    }

    # --- Calcular Health Score normalizado sobre detectores ejecutados ---
    bloat_warnings = [
        r for r in table_bloat if not isinstance(r, dict) or r.get("bloat_pct", 0) > 20
    ]
    dead_warnings = [
        r for r in dead_tuples if isinstance(r, dict) and r.get("dead_tuple_pct", 0) > 10
    ]

    penalties_by_detector = {
        "table_bloat": len(bloat_warnings) * 5,
        "disabled_autovacuum": len(disabled_autovacuum) * 10,
        "dead_tuples": len(dead_warnings) * 5,
        "work_mem_evaluation": len(work_mem_eval) * 8,
        "shared_buffers_evaluation": len(shared_buffers_eval) * 8,
        "pg_stat_max_evaluation": len(pg_stat_max_eval) * 5,
        "pg_stat_limit": len(pg_stat_limit) * 3,
        "slow_query_logging": len(slow_query_logging) * 5,
        "partitioning_candidates": len(partition_candidates) * 2,
        "idle_in_transaction": len(idle_in_transaction) * 10,
        "missing_indexes": len(missing_indexes) * 6,
        "duplicate_indexes": len(duplicate_indexes) * 4,
        "unused_indexes": len(unused_indexes) * 3,
        "missing_partial": len(missing_partial) * 3,
        "obsolete_stats": len(obsolete_stats) * 5,
        "wildcard_searches": len(wildcard_searches) * 3,
        "covering_candidates": len(covering_candidates) * 2,
        "temp_spills": (
            len([s for s in temp_spills if isinstance(s, dict) and s.get("severity") == "HIGH"]) * 8
            + len([s for s in temp_spills if isinstance(s, dict) and s.get("severity") == "MEDIUM"]) * 5
        ),
        "seq_scans": len(seq_scans) * 4,
        "top_time_queries": len(top_time_queries) * 4,
        "db_temp_usage": len(db_temp_usage) * 5,
        "explain_spills": len(explain_spills) * 6,
    }

    active_penalty = sum(
        val for key, val in penalties_by_detector.items() if key not in excluded
    )
    total_weight = sum(_DETECTOR_WEIGHTS.values())
    active_weight = sum(
        weight for key, weight in _DETECTOR_WEIGHTS.items() if key not in excluded
    )

    if active_weight == 0:
        health_score = 100
    else:
        # En producción (excluded vacío), total_weight / active_weight == 1.0 (sin cambios para TiendaDB)
        normalized_penalty = round(active_penalty * (total_weight / active_weight))
        health_score = max(0, min(100, 100 - normalized_penalty))

    findings_counts = {
        "table_bloat": len(bloat_warnings),
        "disabled_autovacuum": len(disabled_autovacuum),
        "dead_tuples": len(dead_warnings),
        "work_mem_evaluation": len(work_mem_eval),
        "shared_buffers_evaluation": len(shared_buffers_eval),
        "pg_stat_max_evaluation": len(pg_stat_max_eval),
        "pg_stat_limit": len(pg_stat_limit),
        "slow_query_logging": len(slow_query_logging),
        "partitioning_candidates": len(partition_candidates),
        "idle_in_transaction": len(idle_in_transaction),
        "missing_partial": len(missing_partial),
        "missing_indexes": len(missing_indexes),
        "duplicate_indexes": len(duplicate_indexes),
        "unused_indexes": len(unused_indexes),
        "covering_candidates": len(covering_candidates),
        "obsolete_stats": len(obsolete_stats),
        "wildcard_searches": len(wildcard_searches),
        "temp_spills": len(temp_spills),
        "seq_scans": len(seq_scans),
        "top_time_queries": len(top_time_queries),
        "db_temp_usage": len(db_temp_usage),
        "explain_spills": len(explain_spills),
    }

    total_findings = sum(
        cnt for key, cnt in findings_counts.items() if key not in excluded
    )

    return FullScanResponse(
        health_score=health_score,
        total_findings=total_findings,
        categories=categories,
        executed_at=now,
        is_sandbox=is_sandbox,
        evaluated_detectors=len(_DETECTOR_WEIGHTS) - len(excluded),
        not_applicable_detectors=len(excluded),
    )

