from datetime import datetime, timezone
import io
import unittest
from unittest.mock import patch

from fastapi import HTTPException, UploadFile

from api.routers.analyses import (
    MAX_FILE_SIZE_BYTES,
    MAX_TOTAL_SIZE_BYTES,
    create_analysis,
)
from api.schemas import FullScanResponse
from services.sandbox_runner import SandboxExecutionError, SandboxResult


def _upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(content))


def _fake_sandbox_result(parsed_scripts):
    total_stmts = sum(len(stmts) for _, stmts in parsed_scripts)
    return SandboxResult(
        sandbox_db_name="sandbox_test1234567890",
        executed_scripts=len(parsed_scripts),
        executed_statements=total_stmts,
        execution_time_ms=12,
    )


def _fake_scan_report(_sandbox_db_name):
    return FullScanResponse(
        health_score=85,
        total_findings=1,
        categories={},
        executed_at=datetime.now(timezone.utc),
        is_sandbox=True,
        evaluated_detectors=13,
        not_applicable_detectors=9,
    )


class AnalysesEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_single_sql_file(self):
        with (
            patch("api.routers.analyses.execute_in_sandbox", side_effect=_fake_sandbox_result) as mock_exec,
            patch("api.routers.analyses._scan_sandbox", side_effect=_fake_scan_report) as mock_scan,
        ):
            res = await create_analysis(
                files=[_upload("01_schema.sql", "-- Esquema con acentos áéíóúñ\nCREATE TABLE t(id int);\n".encode("utf-8"))],
                order=None,
            )
        self.assertEqual(res.status, "completado")
        self.assertEqual(res.file_count, 1)
        self.assertEqual(res.sandbox_db_name, "sandbox_test1234567890")
        self.assertEqual(res.executed_statements, 1)
        self.assertEqual(res.scan.health_score, 85)
        self.assertTrue(res.scan.is_sandbox)
        self.assertEqual(res.files[0].order, 1)
        self.assertEqual(res.files[0].filename, "01_schema.sql")
        self.assertEqual(res.files[0].encoding, "utf-8")
        self.assertEqual(res.files[0].line_count, 2)
        mock_exec.assert_called_once()
        mock_scan.assert_called_once_with("sandbox_test1234567890")

    async def test_valid_reordered_multiple_files(self):
        files = [
            _upload("02_seed.sql", b"INSERT INTO t VALUES (1);"),
            _upload("03_idx.sql", b"CREATE INDEX idx_t ON t(id);"),
            _upload("01_schema.sql", b"CREATE TABLE t(id int);"),
        ]
        with (
            patch("api.routers.analyses.execute_in_sandbox", side_effect=_fake_sandbox_result) as mock_exec,
            patch("api.routers.analyses._scan_sandbox", side_effect=_fake_scan_report),
        ):
            res = await create_analysis(files=files, order="[2, 0, 1]")
        self.assertEqual(res.file_count, 3)
        self.assertEqual(res.executed_statements, 3)
        self.assertEqual(
            [(f.order, f.filename) for f in res.files],
            [(1, "01_schema.sql"), (2, "02_seed.sql"), (3, "03_idx.sql")],
        )
        passed_names = [name for name, _ in mock_exec.call_args.args[0]]
        self.assertEqual(passed_names, ["01_schema.sql", "02_seed.sql", "03_idx.sql"])

    async def test_rejects_ast_blocked_statement_before_sandbox(self):
        with patch("api.routers.analyses.execute_in_sandbox") as mock_exec:
            with self.assertRaises(HTTPException) as ctx:
                await create_analysis(
                    files=[_upload("evil.sql", b"CREATE TABLE t(id int);\nALTER SYSTEM SET work_mem = '1GB';")],
                    order=None,
                )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail["code"], "SQL_AST_BLOCKED")
        self.assertEqual(ctx.exception.detail["filename"], "evil.sql")
        self.assertEqual(ctx.exception.detail["line"], 2)
        mock_exec.assert_not_called()

    async def test_propagates_sandbox_execution_error(self):
        err = SandboxExecutionError(
            code="SANDBOX_EXECUTION_ERROR",
            filename="broken.sql",
            line=3,
            statement="INSERT INTO missing VALUES (1)",
            pgcode="42P01",
            pg_error='relation "missing" does not exist',
            message="Error al ejecutar 'broken.sql' en la línea 3.",
        )
        with patch("api.routers.analyses.execute_in_sandbox", side_effect=err):
            with self.assertRaises(HTTPException) as ctx:
                await create_analysis(files=[_upload("broken.sql", b"SELECT 1;")], order=None)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail["filename"], "broken.sql")
        self.assertEqual(ctx.exception.detail["line"], 3)

    async def test_rejects_empty_file_list(self):
        with self.assertRaises(HTTPException) as ctx:
            await create_analysis(files=[], order=None)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_rejects_more_than_five_files(self):
        files = [_upload(f"s{i}.sql", b"SELECT 1;") for i in range(6)]
        with self.assertRaises(HTTPException) as ctx:
            await create_analysis(files=files, order=None)
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_rejects_invalid_extensions(self):
        for bad_name in ("script.txt", "schema.sql.bak", ".sql"):
            with self.assertRaises(HTTPException) as ctx:
                await create_analysis(files=[_upload(bad_name, b"SELECT 1;")], order=None)
            self.assertEqual(ctx.exception.status_code, 422)

    async def test_rejects_invalid_utf8(self):
        with self.assertRaises(HTTPException) as ctx:
            await create_analysis(files=[_upload("latin1.sql", b"SELECT '\xff\xfe';")], order=None)
        self.assertEqual(ctx.exception.status_code, 422)

    async def test_rejects_single_file_over_10mb(self):
        oversized = b"a" * (MAX_FILE_SIZE_BYTES + 1)
        with self.assertRaises(HTTPException) as ctx:
            await create_analysis(files=[_upload("big.sql", oversized)], order=None)
        self.assertEqual(ctx.exception.status_code, 413)

    async def test_rejects_combined_size_over_25mb(self):
        nine_mb = b"a" * (9 * 1024 * 1024)
        files = [_upload(f"p{i}.sql", nine_mb) for i in range(3)]  # 27 MB total
        self.assertGreater(len(files) * len(nine_mb), MAX_TOTAL_SIZE_BYTES)
        with self.assertRaises(HTTPException) as ctx:
            await create_analysis(files=files, order=None)
        self.assertEqual(ctx.exception.status_code, 413)

    async def test_rejects_invalid_order_parameter(self):
        files = [_upload("a.sql", b"SELECT 1;"), _upload("b.sql", b"SELECT 2;")]
        for bad_order in ("not-json", "[0]", "[0, 0]", "[0, 2]", "[true, false]"):
            with self.assertRaises(HTTPException) as ctx:
                await create_analysis(files=files, order=bad_order)
            self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
