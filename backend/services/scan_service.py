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


def _not_applicable_detector(label: str) -> dict[str, Any]:
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
                "title": "No aplica en entorno sandbox",
                "severity": "NO_APLICA",
                "evidence": NOT_APPLICABLE_REASON,
                "recommendation": (
                    "Ejecuta esta evaluación sobre una base con tráfico real para "
                    "recopilar estadísticas en PostgreSQL."
                ),
            }
        ],
    }


def _evaluated_detector(label: str, data: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "label": label,
        "status": "warning" if len(data) > 0 else "ok",
        "count": len(data),
        "data": data,
    }


def _run_or_na(
    key: str,
    label: str,
    func,
    conn,
    *,
    is_sandbox: bool,
    serialize: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if is_sandbox and key in SANDBOX_NOT_APPLICABLE_DETECTORS:
        return _not_applicable_detector(label), []
    data = _safe_run(func, conn, serialize=serialize)
    return _evaluated_detector(label, data), data


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
        "table_bloat", "Bloat en Tablas", check_table_bloat, conn, is_sandbox=is_sandbox
    )
    disabled_autovacuum_entry, disabled_autovacuum = _run_or_na(
        "disabled_autovacuum", "Autovacuum Desactivado", check_disabled_autovacuum, conn, is_sandbox=is_sandbox
    )
    dead_tuples_entry, dead_tuples = _run_or_na(
        "dead_tuples", "Dead Tuples", check_dead_tuples, conn, is_sandbox=is_sandbox
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
        is_sandbox=is_sandbox,
    )
    idle_entry, idle_in_transaction = _run_or_na(
        "idle_in_transaction",
        "Idle In Transaction",
        check_idle_in_transaction,
        conn,
        is_sandbox=is_sandbox,
    )

    # Indexes
    missing_partial_entry, missing_partial = _run_or_na(
        "missing_partial",
        "Índices Parciales Faltantes",
        check_missing_partial_indexes,
        conn,
        is_sandbox=is_sandbox,
    )
    missing_indexes_entry, missing_indexes = _run_or_na(
        "missing_indexes",
        "FK Sin Índice",
        check_missing_indexes,
        conn,
        is_sandbox=is_sandbox,
    )
    duplicate_indexes_entry, duplicate_indexes = _run_or_na(
        "duplicate_indexes",
        "Índices Duplicados",
        check_duplicate_indexes,
        conn,
        is_sandbox=is_sandbox,
    )
    unused_indexes_entry, unused_indexes = _run_or_na(
        "unused_indexes",
        "Índices No Usados",
        check_unused_indexes,
        conn,
        is_sandbox=is_sandbox,
    )
    covering_entry, covering_candidates = _run_or_na(
        "covering_candidates",
        "Candidatos a Covering Index",
        check_covering_index_candidates,
        conn,
        is_sandbox=is_sandbox,
    )
    obsolete_stats_entry, obsolete_stats = _run_or_na(
        "obsolete_stats",
        "Estadísticas Obsoletas",
        check_obsolete_stats,
        conn,
        is_sandbox=is_sandbox,
    )
    wildcard_entry, wildcard_searches = _run_or_na(
        "wildcard_searches",
        "Búsquedas con Wildcard",
        check_leading_wildcard_searches,
        conn,
        is_sandbox=is_sandbox,
    )

    # Queries
    pg_stat_enabled = check_pg_stat_statements(conn)
    temp_spills_entry, temp_spills = _run_or_na(
        "temp_spills",
        "Temp Spills",
        evaluate_temp_spills,
        conn,
        is_sandbox=is_sandbox,
        serialize=False,
    )
    seq_scans_entry, seq_scans = _run_or_na(
        "seq_scans",
        "Sequential Scans",
        detect_seq_scan_queries,
        conn,
        is_sandbox=is_sandbox,
        serialize=False,
    )
    top_time_entry, top_time_queries = _run_or_na(
        "top_time_queries",
        "Queries Más Lentas",
        evaluate_top_time_queries,
        conn,
        is_sandbox=is_sandbox,
        serialize=False,
    )
    db_temp_entry, db_temp_usage = _run_or_na(
        "db_temp_usage",
        "Uso Temporal en BD",
        evaluate_database_temp_usage,
        conn,
        is_sandbox=is_sandbox,
        serialize=False,
    )
    explain_entry, explain_spills = _run_or_na(
        "explain_spills",
        "Spills por EXPLAIN",
        evaluate_explain_spills,
        conn,
        is_sandbox=is_sandbox,
        serialize=False,
    )

    categories = {
        "bloat": {
            "label": "Bloat y Mantenimiento",
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
                    "label": "Work Mem Actual",
                    "count": len(work_mem_data),
                    "data": work_mem_data,
                },
                "work_mem_evaluation": _evaluated_detector("Evaluación Work Mem", work_mem_eval),
                "shared_buffers": {
                    "label": "Shared Buffers Actual",
                    "count": len(shared_buffers_data),
                    "data": shared_buffers_data,
                },
                "shared_buffers_evaluation": _evaluated_detector(
                    "Evaluación Shared Buffers", shared_buffers_eval
                ),
                "pg_stat_max_evaluation": _evaluated_detector(
                    "Evaluación pg_stat_statements.max", pg_stat_max_eval
                ),
                "pg_stat_limit": _evaluated_detector(
                    "Límite de Tracking de Queries", pg_stat_limit
                ),
                "slow_query_logging": _evaluated_detector(
                    "Logging de Queries Lentas", slow_query_logging
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
            "label": "Queries Problemáticas",
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

