import unittest
from unittest.mock import MagicMock, patch

from api.routers.analyses import _scan_sandbox
from services import scan_service


def _patch_all_detectors(overrides=None):
    overrides = overrides or {}
    defaults = {
        "check_table_bloat": [],
        "check_disabled_autovacuum": [],
        "check_dead_tuples": [],
        "get_work_mem": ("work_mem", "65536", "kB"),
        "evaluate_work_mem": [],
        "get_shared_buffers": ("shared_buffers", "32768", "8kB"),
        "evaluate_shared_buffers": [],
        "evaluate_pg_stat_statements_max": [],
        "check_pg_stat_statements_limit": [],
        "check_slow_query_logging": [],
        "check_partitioning_candidates": [],
        "check_idle_in_transaction": [],
        "check_missing_partial_indexes": [],
        "check_missing_indexes": [],
        "check_duplicate_indexes": [],
        "check_unused_indexes": [],
        "check_covering_index_candidates": [],
        "check_obsolete_stats": [],
        "check_leading_wildcard_searches": [],
        "check_pg_stat_statements": False,
        "evaluate_temp_spills": [],
        "detect_seq_scan_queries": [],
        "evaluate_top_time_queries": [],
        "evaluate_database_temp_usage": [],
        "evaluate_explain_spills": [],
    }
    defaults.update(overrides)
    return {
        name: patch.object(scan_service, name, return_value=val)
        for name, val in defaults.items()
    }


class ScanServiceTests(unittest.TestCase):
    def test_sandbox_marks_traffic_detectors_no_aplica_and_skips_execution(self):
        patches = _patch_all_detectors()
        mocks = {name: p.start() for name, p in patches.items()}
        try:
            conn = MagicMock()
            res = scan_service.run_full_scan(conn, is_sandbox=True)
        finally:
            for p in patches.values():
                p.stop()

        self.assertTrue(res.is_sandbox)
        self.assertEqual(res.health_score, 100)
        self.assertEqual(res.total_findings, 0)
        self.assertEqual(res.evaluated_detectors, 13)
        self.assertEqual(res.not_applicable_detectors, 9)

        # Ningún detector de tráfico/estadísticas en vivo debe haberse ejecutado
        for skipped_fn in (
            "check_idle_in_transaction",
            "check_unused_indexes",
            "check_covering_index_candidates",
            "check_leading_wildcard_searches",
            "evaluate_temp_spills",
            "detect_seq_scan_queries",
            "evaluate_top_time_queries",
            "evaluate_database_temp_usage",
            "evaluate_explain_spills",
        ):
            mocks[skipped_fn].assert_not_called()

        # Todos los detectores excluidos deben reportar estado no_aplica y count 0
        na_paths = [
            ("health", "idle_in_transaction"),
            ("indexes", "unused_indexes"),
            ("indexes", "covering_candidates"),
            ("indexes", "wildcard_searches"),
            ("queries", "temp_spills"),
            ("queries", "seq_scans"),
            ("queries", "top_time_queries"),
            ("queries", "db_temp_usage"),
            ("queries", "explain_spills"),
        ]
        for cat, det in na_paths:
            entry = res.categories[cat]["detectors"][det]
            self.assertEqual(entry["status"], "no_aplica")
            self.assertEqual(entry["count"], 0)
            self.assertEqual(entry["data"][0]["severity"], "NO_APLICA")
            self.assertIn("recién creadas", entry["reason"])

    def test_sandbox_normalizes_score_over_active_detectors_only(self):
        # 2 llaves foráneas sin índice: peso 6 * 2 = 12 sobre peso activo 69 -> round(12 * 114 / 69) = 20 -> score 80
        patches = _patch_all_detectors(
            {"check_missing_indexes": [{"table_name": "orders"}, {"table_name": "items"}]}
        )
        for p in patches.values():
            p.start()
        try:
            res = scan_service.run_full_scan(MagicMock(), is_sandbox=True)
        finally:
            for p in patches.values():
                p.stop()

        self.assertEqual(res.total_findings, 2)
        self.assertEqual(res.health_score, 80)

    def test_production_mode_executes_all_detectors_without_scaling(self):
        # En TiendaDB (is_sandbox=False), peso total == peso activo -> score = 100 - (10 + 8) = 82
        patches = _patch_all_detectors(
            {
                "check_idle_in_transaction": [{"pid": 99}],  # 10 pts
                "evaluate_work_mem": [{"title": "low"}],    # 8 pts
                "check_pg_stat_statements": True,
            }
        )
        mocks = {name: p.start() for name, p in patches.items()}
        try:
            res = scan_service.run_full_scan(MagicMock(), is_sandbox=False)
        finally:
            for p in patches.values():
                p.stop()

        self.assertFalse(res.is_sandbox)
        self.assertEqual(res.evaluated_detectors, 22)
        self.assertEqual(res.not_applicable_detectors, 0)
        self.assertEqual(res.total_findings, 2)
        self.assertEqual(res.health_score, 82)
        mocks["check_idle_in_transaction"].assert_called_once()
        mocks["evaluate_temp_spills"].assert_called_once()

    def test_scan_sandbox_uses_connect_sandbox_db_and_closes_connection(self):
        fake_conn = MagicMock()
        with (
            patch("api.routers.analyses.connect_sandbox_db", return_value=fake_conn) as mock_connect,
            patch("api.routers.analyses.run_full_scan", return_value="ok_scan") as mock_scan,
        ):
            out = _scan_sandbox("sandbox_abc123")
        self.assertEqual(out, "ok_scan")
        mock_connect.assert_called_once_with("sandbox_abc123")
        mock_scan.assert_called_once_with(fake_conn, is_sandbox=True)
        fake_conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()

