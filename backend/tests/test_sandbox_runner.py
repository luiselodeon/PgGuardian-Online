import os
import unittest
from unittest.mock import MagicMock, patch

import psycopg2

from services.sandbox_runner import (
    SandboxExecutionError,
    _get_sandbox_config,
    execute_in_sandbox,
)
from services.sql_validator import ParsedStatement


class _FakeDiag:
    def __init__(self, primary="error simulado", pos="15"):
        self.message_primary = primary
        self.statement_position = pos


class _FakePgError(psycopg2.Error):
    def __init__(self, pgcode="42P01", primary='relation "missing" does not exist', pos="1"):
        super().__init__(primary)
        self._pgcode = pgcode
        self._diag = _FakeDiag(primary=primary, pos=pos)

    @property
    def pgcode(self):
        return self._pgcode

    @property
    def diag(self):
        return self._diag


class SandboxRunnerTests(unittest.TestCase):
    def test_config_is_decoupled_from_app_db(self):
        env = {
            "DB_HOST": "app_db_should_be_ignored",
            "DB_USER": "app_user_should_be_ignored",
            "SANDBOX_DB_HOST": "sandbox_db",
            "SANDBOX_DB_PORT": "5432",
            "SANDBOX_DB_NAME": "postgres",
            "SANDBOX_DB_ADMIN_USER": "sandbox_admin",
            "SANDBOX_DB_ADMIN_PASSWORD": "secret",
            "SANDBOX_DB_EXEC_USER": "sandbox_runner",
            "SANDBOX_DB_EXEC_PASSWORD": "runner_secret",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = _get_sandbox_config()
        self.assertEqual(cfg.host, "sandbox_db")
        self.assertEqual(cfg.admin_user, "sandbox_admin")
        self.assertEqual(cfg.exec_user, "sandbox_runner")

    def test_fail_fast_drops_sandbox_and_reports_file_and_line(self):
        exec_cursor = MagicMock()
        # Primera sentencia (SET + CREATE TABLE) pasa; segunda falla en línea +1
        exec_cursor.execute.side_effect = [
            None,
            None,
            None,
            _FakePgError(pgcode="42P01", primary='relation "no_existe" does not exist', pos="15"),
        ]
        exec_conn = MagicMock()
        exec_conn.cursor.return_value.__enter__.return_value = exec_cursor

        scripts = [
            ("01_ok.sql", [ParsedStatement(line=1, sql="CREATE TABLE ok(id int);")]),
            ("02_fail.sql", [ParsedStatement(line=10, sql="SELECT *\nFROM no_existe;")]),
            ("03_never.sql", [ParsedStatement(line=1, sql="CREATE TABLE skipped(id int);")]),
        ]

        with (
            patch("services.sandbox_runner._provision_sandbox_db") as mock_prov,
            patch("services.sandbox_runner._connect", return_value=exec_conn),
            patch("services.sandbox_runner._drop_sandbox_db") as mock_drop,
        ):
            with self.assertRaises(SandboxExecutionError) as ctx:
                execute_in_sandbox(scripts)

        self.assertEqual(ctx.exception.code, "SANDBOX_EXECUTION_ERROR")
        self.assertEqual(ctx.exception.filename, "02_fail.sql")
        self.assertEqual(ctx.exception.line, 11)
        self.assertEqual(ctx.exception.pgcode, "42P01")
        mock_prov.assert_called_once()
        mock_drop.assert_called_once()
        exec_conn.close.assert_called()

    def test_timeout_triggers_cleanup_and_reports_timeout_code(self):
        exec_cursor = MagicMock()
        exec_cursor.execute.side_effect = [
            None,
            _FakePgError(pgcode="57014", primary="canceling statement due to statement timeout", pos="1"),
        ]
        exec_conn = MagicMock()
        exec_conn.cursor.return_value.__enter__.return_value = exec_cursor

        scripts = [("slow.sql", [ParsedStatement(line=4, sql="SELECT pg_sleep(200);")])]

        with (
            patch("services.sandbox_runner._provision_sandbox_db"),
            patch("services.sandbox_runner._connect", return_value=exec_conn),
            patch("services.sandbox_runner._drop_sandbox_db") as mock_drop,
        ):
            with self.assertRaises(SandboxExecutionError) as ctx:
                execute_in_sandbox(scripts, timeout_seconds=120)

        self.assertEqual(ctx.exception.code, "SANDBOX_TIMEOUT")
        self.assertEqual(ctx.exception.filename, "slow.sql")
        self.assertEqual(ctx.exception.line, 4)
        mock_drop.assert_called_once()


if __name__ == "__main__":
    unittest.main()

