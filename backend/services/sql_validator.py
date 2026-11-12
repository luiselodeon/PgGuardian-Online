"""
PgGuardian — Validador estático AST para scripts SQL (RF-01.3)

Inspecciona el árbol sintáctico (AST) generado por pglast antes de provisionar
o ejecutar cualquier script en sandbox_db, bloqueando sentencias peligrosas
sin utilizar expresiones regulares.
"""

from dataclasses import dataclass

import pglast
from pglast import ast, enums, parser, visitors

ALLOWED_EXTENSIONS = frozenset({
    "uuid-ossp",
    "pgcrypto",
    "pg_trgm",
    "citext",
    "hstore",
    "unaccent",
    "btree_gin",
    "btree_gist",
})

ALLOWED_FUNCTION_LANGUAGES = frozenset({"sql", "plpgsql"})

_CRITICAL_OBJECT_TYPES = frozenset({
    enums.ObjectType.OBJECT_DATABASE,
    enums.ObjectType.OBJECT_TABLESPACE,
    enums.ObjectType.OBJECT_FDW,
    enums.ObjectType.OBJECT_FOREIGN_SERVER,
    enums.ObjectType.OBJECT_PARAMETER_ACL,
})

_COMMENT_OR_EMPTY_TOKENS = frozenset({"SQL_COMMENT", "C_COMMENT", "ASCII_59"})


@dataclass(frozen=True)
class ParsedStatement:
    """Sentencia SQL individual validada con su línea de inicio en el archivo."""
    line: int
    sql: str


class SqlValidationError(Exception):
    """Error estructurado emitido al detectar sintaxis inválida o sentencias prohibidas."""

    def __init__(
        self,
        *,
        code: str,
        filename: str,
        line: int,
        rule: str,
        statement: str,
        message: str,
    ):
        super().__init__(message)
        self.code = code
        self.filename = filename
        self.line = line
        self.rule = rule
        self.statement = statement
        self.message = message

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "filename": self.filename,
            "line": self.line,
            "rule": self.rule,
            "statement": self.statement,
        }


def _extract_language(options: tuple | None) -> str | None:
    if not options:
        return None
    for opt in options:
        if getattr(opt, "defname", None) == "language" and isinstance(opt.arg, ast.String):
            return (opt.arg.sval or "").strip().lower()
    return None


def _extract_object_names(objects: tuple | None) -> list[str]:
    names: list[str] = []
    if not objects:
        return names
    for obj in objects:
        if isinstance(obj, ast.String) and obj.sval:
            names.append(obj.sval.lower())
        elif isinstance(obj, tuple):
            for item in obj:
                if isinstance(item, ast.String) and item.sval:
                    names.append(item.sval.lower())
    return names


def _truncate_statement(stmt: str, limit: int = 240) -> str:
    compact = " ".join(stmt.split())
    return compact if len(compact) <= limit else f"{compact[:limit]}..."


class _SafetyVisitor(visitors.Visitor):
    """Recorre el AST de una sentencia y registra la primera infracción detectada."""

    def __init__(self):
        super().__init__()
        self.violation: tuple[str, str] | None = None

    def _reject(self, rule: str, message: str) -> None:
        if self.violation is None:
            self.violation = (rule, message)

    def visit_AlterSystemStmt(self, ancestors, node):
        self._reject(
            "alter_system",
            "Sentencia ALTER SYSTEM prohibida: no se permite modificar la configuración global del servidor.",
        )

    def visit_CopyStmt(self, ancestors, node):
        if node.is_program:
            self._reject(
                "copy_program",
                "Sentencia COPY ... PROGRAM prohibida: no se permite ejecutar programas del sistema operativo.",
            )
        elif node.filename is not None:
            self._reject(
                "copy_file",
                "Sentencia COPY con archivo prohibida: no se permite leer ni escribir archivos del servidor.",
            )

    def visit_CreateRoleStmt(self, ancestors, node):
        self._reject(
            "role_management",
            "Sentencia CREATE ROLE/USER/GROUP prohibida: no se permite crear roles en el sandbox.",
        )

    def visit_AlterRoleStmt(self, ancestors, node):
        self._reject(
            "role_management",
            "Sentencia ALTER ROLE/USER/GROUP prohibida: no se permite modificar roles ni privilegios.",
        )

    def visit_AlterRoleSetStmt(self, ancestors, node):
        self._reject(
            "role_management",
            "Sentencia ALTER ROLE ... SET prohibida: no se permite alterar configuración por rol.",
        )

    def visit_DropRoleStmt(self, ancestors, node):
        self._reject(
            "role_management",
            "Sentencia DROP ROLE/USER/GROUP prohibida: no se permite eliminar roles.",
        )

    def visit_GrantRoleStmt(self, ancestors, node):
        self._reject(
            "role_management",
            "Sentencia GRANT/REVOKE de rol prohibida: no se permite asignar ni revocar membresías de roles.",
        )

    def visit_VariableSetStmt(self, ancestors, node):
        name = (getattr(node, "name", "") or "").lower()
        if name in ("role", "session_authorization"):
            self._reject(
                "role_management",
                f"Sentencia SET {name.upper()} prohibida: no se permite cambiar el rol de sesión.",
            )

    def visit_GrantStmt(self, ancestors, node):
        if node.objtype in _CRITICAL_OBJECT_TYPES:
            self._reject(
                "critical_privilege",
                "Sentencia GRANT/REVOKE crítica prohibida sobre base de datos, tablespace, servidor externo o parámetro.",
            )
            return
        if node.objtype == enums.ObjectType.OBJECT_SCHEMA:
            for schema_name in _extract_object_names(node.objects):
                if schema_name.startswith("pg_") or schema_name == "information_schema":
                    self._reject(
                        "critical_privilege",
                        f"Sentencia GRANT/REVOKE prohibida sobre el esquema del sistema '{schema_name}'.",
                    )

    def visit_CreatedbStmt(self, ancestors, node):
        self._reject(
            "database_management",
            "Sentencia CREATE DATABASE prohibida: cada análisis se ejecuta en su propia base sandbox aislada.",
        )

    def visit_DropdbStmt(self, ancestors, node):
        self._reject(
            "database_management",
            "Sentencia DROP DATABASE prohibida: no se permite eliminar bases de datos.",
        )

    def visit_AlterDatabaseStmt(self, ancestors, node):
        self._reject(
            "database_management",
            "Sentencia ALTER DATABASE prohibida: no se permite modificar propiedades de bases de datos.",
        )

    def visit_AlterDatabaseSetStmt(self, ancestors, node):
        self._reject(
            "database_management",
            "Sentencia ALTER DATABASE ... SET prohibida: no se permite alterar parámetros de base de datos.",
        )

    def visit_AlterDatabaseRefreshCollStmt(self, ancestors, node):
        self._reject(
            "database_management",
            "Sentencia ALTER DATABASE prohibida.",
        )

    def visit_AlterOwnerStmt(self, ancestors, node):
        if node.objectType == enums.ObjectType.OBJECT_DATABASE:
            self._reject(
                "database_management",
                "Sentencia ALTER DATABASE ... OWNER TO prohibida.",
            )
        elif node.objectType in _CRITICAL_OBJECT_TYPES:
            self._reject(
                "critical_privilege",
                "Sentencia ALTER ... OWNER TO prohibida sobre objeto crítico del sistema.",
            )

    def visit_RenameStmt(self, ancestors, node):
        if node.renameType == enums.ObjectType.OBJECT_DATABASE:
            self._reject(
                "database_management",
                "Sentencia ALTER DATABASE ... RENAME TO prohibida.",
            )

    def visit_CreateTableSpaceStmt(self, ancestors, node):
        self._reject(
            "system_object_management",
            "Sentencia CREATE TABLESPACE prohibida: no se permite acceder al sistema de archivos del servidor.",
        )

    def visit_DropTableSpaceStmt(self, ancestors, node):
        self._reject(
            "system_object_management",
            "Sentencia DROP TABLESPACE prohibida.",
        )

    def visit_CreateFdwStmt(self, ancestors, node):
        self._reject(
            "system_object_management",
            "Sentencia CREATE FOREIGN DATA WRAPPER prohibida en el sandbox.",
        )

    def visit_AlterFdwStmt(self, ancestors, node):
        self._reject(
            "system_object_management",
            "Sentencia ALTER FOREIGN DATA WRAPPER prohibida en el sandbox.",
        )

    def visit_CreateForeignServerStmt(self, ancestors, node):
        self._reject(
            "system_object_management",
            "Sentencia CREATE SERVER prohibida en el sandbox.",
        )

    def visit_AlterForeignServerStmt(self, ancestors, node):
        self._reject(
            "system_object_management",
            "Sentencia ALTER SERVER prohibida en el sandbox.",
        )

    def visit_CreateUserMappingStmt(self, ancestors, node):
        self._reject(
            "system_object_management",
            "Sentencia CREATE USER MAPPING prohibida en el sandbox.",
        )

    def visit_CreateExtensionStmt(self, ancestors, node):
        extname = (node.extname or "").strip().lower()
        if extname not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
            self._reject(
                "disallowed_extension",
                f"Extensión '{extname}' no permitida. Extensiones autorizadas: {allowed}.",
            )

    def visit_AlterExtensionStmt(self, ancestors, node):
        extname = (node.extname or "").strip().lower()
        if extname not in ALLOWED_EXTENSIONS:
            self._reject(
                "disallowed_extension",
                f"Operación ALTER EXTENSION prohibida para la extensión no permitida '{extname}'.",
            )

    def visit_AlterExtensionContentsStmt(self, ancestors, node):
        extname = (node.extname or "").strip().lower()
        if extname not in ALLOWED_EXTENSIONS:
            self._reject(
                "disallowed_extension",
                f"Modificación de extensión no permitida '{extname}'.",
            )

    def visit_CreatePLangStmt(self, ancestors, node):
        plname = (node.plname or "").strip().lower()
        self._reject(
            "untrusted_language",
            f"Sentencia CREATE LANGUAGE '{plname}' prohibida: no se permite registrar lenguajes procedurales.",
        )

    def visit_CreateFunctionStmt(self, ancestors, node):
        lang = _extract_language(node.options)
        if lang and lang not in ALLOWED_FUNCTION_LANGUAGES:
            self._reject(
                "untrusted_language",
                f"Lenguaje procedural '{lang}' no permitido en función/procedimiento. Solo se permite: sql, plpgsql.",
            )

    def visit_DoStmt(self, ancestors, node):
        lang = _extract_language(node.args)
        if lang and lang not in ALLOWED_FUNCTION_LANGUAGES:
            self._reject(
                "untrusted_language",
                f"Lenguaje procedural '{lang}' no permitido en bloque DO. Solo se permite: sql, plpgsql.",
            )

    def visit_DropStmt(self, ancestors, node):
        if node.removeType in (
            enums.ObjectType.OBJECT_LANGUAGE,
            enums.ObjectType.OBJECT_FDW,
            enums.ObjectType.OBJECT_FOREIGN_SERVER,
        ):
            self._reject(
                "system_object_management",
                "Sentencia DROP prohibida sobre lenguaje procedural o servidor/wrapper externo.",
            )


def _locate_statement(
    sql_text: str,
    raw_stmt: ast.RawStmt,
    tokens: list,
    tok_idx: int,
    prev_pos: int,
    prev_line: int,
) -> tuple[int, str, int, int, int]:
    """Calcula línea e inicio de sentencia en O(1) amortizado usando cursores crecientes."""
    loc = raw_stmt.stmt_location
    end = loc + raw_stmt.stmt_len if raw_stmt.stmt_len > 0 else len(sql_text)
    n_tokens = len(tokens)
    while tok_idx < n_tokens and tokens[tok_idx].start < loc:
        tok_idx += 1

    start = loc
    scan_idx = tok_idx
    while scan_idx < n_tokens and tokens[scan_idx].start < end:
        if tokens[scan_idx].name not in _COMMENT_OR_EMPTY_TOKENS:
            start = tokens[scan_idx].start
            tok_idx = scan_idx
            break
        scan_idx += 1

    if start >= prev_pos:
        line = prev_line + sql_text.count("\n", prev_pos, start)
    else:
        line = sql_text.count("\n", 0, start) + 1
    stmt_sql = sql_text[start:end].strip()
    return line, stmt_sql, tok_idx, start, line


def validate_sql_script(filename: str, sql_text: str) -> list[ParsedStatement]:
    """Parsea y valida un script SQL completo vía AST antes de ejecutar en sandbox."""
    try:
        raw_tree = pglast.parse_sql(sql_text)
    except parser.ParseError as exc:
        msg = exc.args[0] if exc.args else str(exc)
        offset = exc.args[1] if len(exc.args) > 1 and isinstance(exc.args[1], int) else 0
        # pglast ParseError offset viene en bytes UTF-8
        utf8_prefix = sql_text.encode("utf-8")[:max(0, offset)].decode("utf-8", errors="ignore")
        line = utf8_prefix.count("\n") + 1
        raise SqlValidationError(
            code="SQL_SYNTAX_ERROR",
            filename=filename,
            line=line,
            rule="syntax_error",
            statement="",
            message=f"Error de sintaxis SQL en '{filename}' (línea {line}): {msg}.",
        ) from exc

    if not raw_tree:
        return []

    tokens = list(parser.scan(sql_text))
    statements: list[ParsedStatement] = []
    tok_idx = 0
    prev_pos = 0
    prev_line = 1

    for raw_stmt in raw_tree:
        line, stmt_sql, tok_idx, prev_pos, prev_line = _locate_statement(
            sql_text, raw_stmt, tokens, tok_idx, prev_pos, prev_line
        )
        visitor = _SafetyVisitor()
        visitor(raw_stmt.stmt)
        if visitor.violation is not None:
            rule, reason = visitor.violation
            snippet = _truncate_statement(stmt_sql)
            raise SqlValidationError(
                code="SQL_AST_BLOCKED",
                filename=filename,
                line=line,
                rule=rule,
                statement=snippet,
                message=(
                    f"Sentencia rechazada en '{filename}' (línea {line}, regla '{rule}'): "
                    f"{reason} Sentencia detectada: {snippet}"
                ),
            )
        if stmt_sql:
            statements.append(ParsedStatement(line=line, sql=stmt_sql))

    return statements


def validate_scripts(scripts: list[tuple[str, str]]) -> list[tuple[str, list[ParsedStatement]]]:
    """Valida todos los scripts ordenados; aborta antes de crear cualquier sandbox."""
    return [(filename, validate_sql_script(filename, sql_text)) for filename, sql_text in scripts]

