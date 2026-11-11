"""
PgGuardian — Gestor de aislamiento y ejecución en sandbox_db (RF-01.4)

Provisiona una base de datos temporal única por análisis en sandbox_db,
ejecuta scripts SQL con un rol sin privilegios de superusuario bajo un
límite global estricto de 120 segundos y aplica limpieza fail-fast.
"""

from dataclasses import dataclass
import os
import time
from uuid import uuid4

import psycopg2
from psycopg2 import errors as pg_errors
from psycopg2 import sql

from services.sql_validator import ParsedStatement

SANDBOX_TIMEOUT_SECONDS = 120

_PG_CODE_HINTS_ES = {
    "42P01": "Tabla o relación inexistente",
    "42703": "Columna inexistente",
    "42601": "Error de sintaxis SQL",
    "42P07": "La relación o tabla ya existe",
    "42710": "El objeto ya existe",
    "42704": "Objeto o tipo de dato inexistente",
    "42883": "Función u operador inexistente",
    "42804": "Incompatibilidad de tipos de datos",
    "42501": "Permiso insuficiente para el rol restringido del sandbox",
    "23505": "Violación de restricción única",
    "23503": "Violación de llave foránea",
    "23502": "Violación de restricción NOT NULL",
    "23514": "Violación de restricción CHECK",
    "22P02": "Formato de dato inválido",
    "57014": "Tiempo límite de ejecución excedido (120 s)",
}


@dataclass(frozen=True)
class SandboxConfig:
    host: str
    port: int
    admin_db: str
    admin_user: str
    admin_password: str
    exec_user: str
    exec_password: str


@dataclass(frozen=True)
class SandboxResult:
    sandbox_db_name: str
    executed_scripts: int
    executed_statements: int
    execution_time_ms: int


class SandboxExecutionError(Exception):
    """Error estructurado de ejecución o timeout en sandbox_db."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        filename: str | None = None,
        line: int | None = None,
        statement: str | None = None,
        pgcode: str | None = None,
        pg_error: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.filename = filename
        self.line = line
        self.statement = statement
        self.pgcode = pgcode
        self.pg_error = pg_error

    def to_dict(self) -> dict:
        payload = {
            "code": self.code,
            "message": self.message,
        }
        if self.filename is not None:
            payload["filename"] = self.filename
        if self.line is not None:
            payload["line"] = self.line
        if self.statement is not None:
            payload["statement"] = self.statement
        if self.pgcode is not None:
            payload["pgcode"] = self.pgcode
        if self.pg_error is not None:
            payload["pg_error"] = self.pg_error
        return payload


def _get_sandbox_config() -> SandboxConfig:
    """Lee credenciales exclusivas de sandbox_db; nunca reutiliza app_db/TiendaDB."""
    return SandboxConfig(
        host=os.getenv("SANDBOX_DB_HOST", "sandbox_db"),
        port=int(os.getenv("SANDBOX_DB_PORT", "5432")),
        admin_db=os.getenv("SANDBOX_DB_NAME", "postgres"),
        admin_user=os.getenv("SANDBOX_DB_ADMIN_USER", "sandbox_admin"),
        admin_password=os.getenv("SANDBOX_DB_ADMIN_PASSWORD", "sandbox_admin_pass"),
        exec_user=os.getenv("SANDBOX_DB_EXEC_USER", "sandbox_runner"),
        exec_password=os.getenv("SANDBOX_DB_EXEC_PASSWORD", "sandbox_runner_pass"),
    )


def _connect(cfg: SandboxConfig, *, dbname: str, user: str, password: str):
    conn = psycopg2.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=cfg.host,
        port=cfg.port,
        connect_timeout=10,
    )
    conn.autocommit = True
    return conn


def connect_sandbox_db(sandbox_db_name: str):
    """Abre una conexión sin privilegios hacia una base sandbox específica."""
    cfg = _get_sandbox_config()
    return _connect(
        cfg,
        dbname=sandbox_db_name,
        user=cfg.exec_user,
        password=cfg.exec_password,
    )


def _ensure_unprivileged_role(admin_cur, exec_user: str, exec_password: str) -> None:
    """Asegura que el rol ejecutor exista sin privilegios administrativos."""
    role_ident = sql.Identifier(exec_user)
    admin_cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s;", (exec_user,))
    exists = admin_cur.fetchone() is not None
    if not exists:
        try:
            admin_cur.execute(
                sql.SQL(
                    "CREATE ROLE {} WITH LOGIN PASSWORD %s "
                    "NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION;"
                ).format(role_ident),
                (exec_password,),
            )
            return
        except pg_errors.DuplicateObject:
            pass

    admin_cur.execute(
        sql.SQL(
            "ALTER ROLE {} WITH LOGIN PASSWORD %s "
            "NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION;"
        ).format(role_ident),
        (exec_password,),
    )


def _provision_sandbox_db(cfg: SandboxConfig, db_name: str) -> None:
    """Crea la base sandbox temporal y delega el esquema public al rol sin privilegios."""
    admin_conn = None
    sandbox_admin_conn = None
    try:
        admin_conn = _connect(
            cfg,
            dbname=cfg.admin_db,
            user=cfg.admin_user,
            password=cfg.admin_password,
        )
        with admin_conn.cursor() as cur:
            _ensure_unprivileged_role(cur, cfg.exec_user, cfg.exec_password)
            cur.execute(
                sql.SQL("CREATE DATABASE {} OWNER {};").format(
                    sql.Identifier(db_name),
                    sql.Identifier(cfg.exec_user),
                )
            )
            cur.execute(
                sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC;").format(
                    sql.Identifier(db_name)
                )
            )

        # PostgreSQL 15+ restringe CREATE en el esquema public salvo al dueño del esquema.
        sandbox_admin_conn = _connect(
            cfg,
            dbname=db_name,
            user=cfg.admin_user,
            password=cfg.admin_password,
        )
        with sandbox_admin_conn.cursor() as cur:
            cur.execute(
                sql.SQL("ALTER SCHEMA public OWNER TO {};").format(
                    sql.Identifier(cfg.exec_user)
                )
            )
            cur.execute(
                sql.SQL("GRANT ALL ON SCHEMA public TO {};").format(
                    sql.Identifier(cfg.exec_user)
                )
            )
    finally:
        if sandbox_admin_conn:
            sandbox_admin_conn.close()
        if admin_conn:
            admin_conn.close()


def _drop_sandbox_db(cfg: SandboxConfig, db_name: str) -> bool:
    """Elimina la base sandbox temporal cerrando conexiones activas."""
    admin_conn = None
    try:
        admin_conn = _connect(
            cfg,
            dbname=cfg.admin_db,
            user=cfg.admin_user,
            password=cfg.admin_password,
        )
        with admin_conn.cursor() as cur:
            cur.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE);").format(
                    sql.Identifier(db_name)
                )
            )
        return True
    except Exception:
        return False
    finally:
        if admin_conn:
            admin_conn.close()


def drop_sandbox_db(db_name: str) -> bool:
    """Elimina una base sandbox expirada o borrada manualmente usando SANDBOX_DB_*."""
    if not db_name or not db_name.startswith("sandbox_"):
        return False
    return _drop_sandbox_db(_get_sandbox_config(), db_name)


def _translate_pg_error(pgcode: str | None, primary_msg: str) -> str:
    hint = _PG_CODE_HINTS_ES.get(pgcode or "")
    if hint:
        return f"{hint}: {primary_msg}"
    return f"Error de PostgreSQL: {primary_msg}"


def _truncate_sql(stmt: str, limit: int = 240) -> str:
    compact = " ".join(stmt.split())
    return compact if len(compact) <= limit else f"{compact[:limit]}..."


def execute_in_sandbox(
    parsed_scripts: list[tuple[str, list[ParsedStatement]]],
    *,
    timeout_seconds: int = SANDBOX_TIMEOUT_SECONDS,
) -> SandboxResult:
    """
    Crea un sandbox temporal aislado y ejecuta secuencialmente los scripts validados.
    Detiene la ejecución al primer error y elimina el sandbox fallido.
    """
    cfg = _get_sandbox_config()
    db_name = f"sandbox_{uuid4().hex}"
    db_created = False
    exec_conn = None
    start_time = time.monotonic()
    deadline = start_time + timeout_seconds
    executed_statements = 0

    try:
        try:
            _provision_sandbox_db(cfg, db_name)
            db_created = True
        except psycopg2.Error as exc:
            raise SandboxExecutionError(
                code="SANDBOX_CONNECTION_ERROR",
                message="No se pudo aprovisionar la base temporal en sandbox_db.",
                pgcode=exc.pgcode,
                pg_error=str(exc).strip(),
            ) from exc

        try:
            exec_conn = _connect(
                cfg,
                dbname=db_name,
                user=cfg.exec_user,
                password=cfg.exec_password,
            )
        except psycopg2.Error as exc:
            raise SandboxExecutionError(
                code="SANDBOX_CONNECTION_ERROR",
                message="No se pudo conectar al sandbox temporal con el rol restringido.",
                pgcode=exc.pgcode,
                pg_error=str(exc).strip(),
            ) from exc

        with exec_conn.cursor() as cur:
            for filename, statements in parsed_scripts:
                for stmt in statements:
                    remaining_ms = int((deadline - time.monotonic()) * 1000)
                    if remaining_ms <= 0:
                        raise SandboxExecutionError(
                            code="SANDBOX_TIMEOUT",
                            filename=filename,
                            line=stmt.line,
                            statement=_truncate_sql(stmt.sql),
                            pgcode="57014",
                            message=(
                                f"Tiempo límite excedido ({timeout_seconds} s) antes de ejecutar "
                                f"'{filename}' en la línea {stmt.line}."
                            ),
                        )

                    try:
                        # Reafirma el timeout global en cada sentencia para evitar evasiones con SET statement_timeout = 0.
                        cur.execute("SET statement_timeout = %s;", (remaining_ms,))
                        cur.execute(stmt.sql)
                        executed_statements += 1
                    except psycopg2.Error as exc:
                        pos_raw = getattr(exc.diag, "statement_position", None)
                        pos = int(pos_raw) if pos_raw and pos_raw.isdigit() else 0
                        exact_line = stmt.line + (
                            stmt.sql[: max(0, pos - 1)].count("\n") if pos > 0 else 0
                        )
                        raw_pg_msg = (
                            getattr(exc.diag, "message_primary", None) or str(exc)
                        ).strip()

                        if exc.pgcode == "57014" or time.monotonic() >= deadline:
                            raise SandboxExecutionError(
                                code="SANDBOX_TIMEOUT",
                                filename=filename,
                                line=exact_line,
                                statement=_truncate_sql(stmt.sql),
                                pgcode=exc.pgcode or "57014",
                                pg_error=raw_pg_msg,
                                message=(
                                    f"Ejecución cancelada por superar el límite de {timeout_seconds} s "
                                    f"en '{filename}' (línea {exact_line}): {raw_pg_msg}"
                                ),
                            ) from exc

                        translated = _translate_pg_error(exc.pgcode, raw_pg_msg)
                        raise SandboxExecutionError(
                            code="SANDBOX_EXECUTION_ERROR",
                            filename=filename,
                            line=exact_line,
                            statement=_truncate_sql(stmt.sql),
                            pgcode=exc.pgcode,
                            pg_error=raw_pg_msg,
                            message=(
                                f"Error al ejecutar '{filename}' en la línea {exact_line}: "
                                f"{translated}"
                            ),
                        ) from exc

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        return SandboxResult(
            sandbox_db_name=db_name,
            executed_scripts=len(parsed_scripts),
            executed_statements=executed_statements,
            execution_time_ms=elapsed_ms,
        )
    except Exception:
        if exec_conn:
            exec_conn.close()
            exec_conn = None
        if db_created:
            _drop_sandbox_db(cfg, db_name)
        raise
    finally:
        if exec_conn:
            exec_conn.close()

