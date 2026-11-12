import unittest

from services.sql_validator import SqlValidationError, validate_sql_script


class SqlAstValidatorTests(unittest.TestCase):
    def test_allows_valid_ddl_dml_and_trusted_extensions(self):
        sql = """
        -- Script válido con extensión permitida y función PL/pgSQL
        SET search_path = public;
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
        CREATE EXTENSION IF NOT EXISTS pg_trgm;
        CREATE TABLE clientes (
            id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
            nombre TEXT NOT NULL
        );
        CREATE FUNCTION contar_clientes() RETURNS BIGINT LANGUAGE sql AS $$
            SELECT count(*) FROM clientes;
        $$;
        DO $$ BEGIN RAISE NOTICE 'ok'; END $$;
        GRANT SELECT ON TABLE clientes TO PUBLIC;
        """
        stmts = validate_sql_script("valid.sql", sql)
        self.assertEqual(len(stmts), 7)

    def test_blocks_alter_system_with_exact_line_after_utf8_comments(self):
        sql = "-- Comentario con acentos áéíóúñ\nCREATE TABLE t(id int);\nALTER SYSTEM SET work_mem = '64MB';"
        with self.assertRaises(SqlValidationError) as ctx:
            validate_sql_script("sys.sql", sql)
        self.assertEqual(ctx.exception.rule, "alter_system")
        self.assertEqual(ctx.exception.line, 3)
        self.assertEqual(ctx.exception.filename, "sys.sql")

    def test_blocks_copy_file_and_program_but_allows_stdin(self):
        validate_sql_script("stdin.sql", "COPY t FROM STDIN;")
        for sql, expected_rule in (
            ("COPY t TO '/tmp/leak.csv';", "copy_file"),
            ("COPY t FROM '/etc/passwd';", "copy_file"),
            ("COPY t FROM PROGRAM 'cat /etc/passwd';", "copy_program"),
        ):
            with self.assertRaises(SqlValidationError) as ctx:
                validate_sql_script("copy.sql", sql)
            self.assertEqual(ctx.exception.rule, expected_rule)

    def test_blocks_role_and_critical_privilege_statements(self):
        for sql in (
            "CREATE ROLE evil SUPERUSER;",
            "CREATE USER hacker;",
            "ALTER ROLE tienda_user WITH SUPERUSER;",
            "ALTER ROLE runner SET work_mem = '1GB';",
            "DROP ROLE runner;",
            "GRANT pg_execute_server_program TO runner;",
            "SET ROLE postgres;",
            "GRANT ALL PRIVILEGES ON DATABASE postgres TO PUBLIC;",
            "GRANT USAGE ON SCHEMA pg_catalog TO PUBLIC;",
        ):
            with self.assertRaises(SqlValidationError) as ctx:
                validate_sql_script("roles.sql", sql)
            self.assertIn(ctx.exception.rule, ("role_management", "critical_privilege"))

    def test_blocks_database_management_statements(self):
        for sql in (
            "CREATE DATABASE otro;",
            "DROP DATABASE postgres;",
            "ALTER DATABASE app_db CONNECTION LIMIT 0;",
            "ALTER DATABASE app_db SET work_mem = '1GB';",
            "ALTER DATABASE app_db OWNER TO evil;",
            "ALTER DATABASE app_db RENAME TO hacked;",
        ):
            with self.assertRaises(SqlValidationError) as ctx:
                validate_sql_script("dbs.sql", sql)
            self.assertEqual(ctx.exception.rule, "database_management")

    def test_blocks_disallowed_extensions(self):
        for sql in (
            "CREATE EXTENSION dblink;",
            "CREATE EXTENSION IF NOT EXISTS file_fdw;",
            "CREATE EXTENSION pg_stat_statements;",
            "ALTER EXTENSION dblink UPDATE;",
        ):
            with self.assertRaises(SqlValidationError) as ctx:
                validate_sql_script("ext.sql", sql)
            self.assertEqual(ctx.exception.rule, "disallowed_extension")

    def test_blocks_untrusted_languages(self):
        for sql in (
            "CREATE PROCEDURAL LANGUAGE plpython3u HANDLER handler_fn;",
            "CREATE FUNCTION f() RETURNS void LANGUAGE plpython3u AS $$ pass $$;",
            "CREATE FUNCTION g() RETURNS void LANGUAGE c AS 'evil.so', 'fn';",
            "DO LANGUAGE plperlu $$ system('id'); $$;",
        ):
            with self.assertRaises(SqlValidationError) as ctx:
                validate_sql_script("lang.sql", sql)
            self.assertEqual(ctx.exception.rule, "untrusted_language")

    def test_reports_syntax_errors_before_sandbox(self):
        with self.assertRaises(SqlValidationError) as ctx:
            validate_sql_script("syntax.sql", "SELECT 1;\nCREAT TABL rota;")
        self.assertEqual(ctx.exception.code, "SQL_SYNTAX_ERROR")
        self.assertEqual(ctx.exception.line, 2)


if __name__ == "__main__":
    unittest.main()

