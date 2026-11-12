"""
PgGuardian API — Router de Análisis de Scripts SQL (RF-01.1 a RF-01.4)

Recibe y valida la carga ordenada de hasta 5 archivos .sql en UTF-8 estricto
(10 MB por archivo, 25 MB totales), valida su AST con pglast y los ejecuta en
una base temporal aislada dentro de sandbox_db.
"""

from datetime import datetime, timezone
import json
from pathlib import PurePosixPath
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from api.auth import get_current_user_id
from api.schemas import (
    AnalysisCreateResponse,
    AnalysisDeleteResponse,
    AnalysisFileSummary,
    AnalysisListResponse,
)
from services.analysis_store import (
    delete_analysis_for_user,
    get_analysis_for_user,
    insert_analysis,
    list_analyses_for_user,
)
from services.sandbox_runner import (
    SandboxExecutionError,
    connect_sandbox_db,
    drop_sandbox_db,
    execute_in_sandbox,
)
from services.scan_service import run_full_scan
from services.sql_validator import SqlValidationError, validate_scripts

router = APIRouter(prefix="/api/analyses", tags=["Análisis"])

MIN_FILES = 1
MAX_FILES = 5
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_SIZE_BYTES = 25 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024


def _parse_execution_order(order_raw: str | None, file_count: int) -> list[int]:
    """Valida y normaliza el orden secuencial de ejecución (índices base 0)."""
    if order_raw is None or not order_raw.strip():
        return list(range(file_count))

    raw = order_raw.strip()
    if len(raw) > 256:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El parámetro 'order' excede la longitud máxima permitida.",
        )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        try:
            parsed = [int(part.strip()) for part in raw.split(",") if part.strip() != ""]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El parámetro 'order' debe ser un arreglo JSON de índices enteros (ej. [0, 1]).",
            )

    if not isinstance(parsed, list) or any(
        isinstance(idx, bool) or not isinstance(idx, int) for idx in parsed
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El parámetro 'order' debe contener únicamente índices enteros.",
        )

    if len(parsed) != file_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"El parámetro 'order' debe incluir exactamente {file_count} índice(s) "
                "para coincidir con los archivos enviados."
            ),
        )

    if set(parsed) != set(range(file_count)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "El parámetro 'order' contiene índices inválidos o duplicados; "
                f"usa valores únicos entre 0 y {file_count - 1}."
            ),
        )

    return parsed


def _scan_sandbox(sandbox_db_name: str):
    """Ejecuta todos los detectores aplicables exclusivamente sobre el sandbox recién creado."""
    sandbox_conn = connect_sandbox_db(sandbox_db_name)
    try:
        return run_full_scan(sandbox_conn, is_sandbox=True)
    finally:
        sandbox_conn.close()


async def _read_and_validate_file(upload: UploadFile, current_total: int) -> dict:
    """Valida extensión, límites de peso y codificación UTF-8 de un archivo .sql."""
    filename = (upload.filename or "").replace("\\", "/").split("/")[-1].strip()
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes adjuntar al menos 1 archivo .sql con un nombre válido.",
        )

    if PurePosixPath(filename).suffix.lower() != ".sql":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"El archivo '{filename}' no es válido. Solo se permiten archivos con extensión .sql.",
        )

    chunks: list[bytes] = []
    file_size = 0
    while chunk := await upload.read(READ_CHUNK_BYTES):
        file_size += len(chunk)
        if file_size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"El archivo '{filename}' excede el límite máximo de 10 MB por archivo.",
            )
        if current_total + file_size > MAX_TOTAL_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="El tamaño combinado de los archivos excede el límite máximo de 25 MB por análisis.",
            )
        chunks.append(chunk)

    raw_bytes = b"".join(chunks)
    try:
        content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"El archivo '{filename}' no tiene una codificación UTF-8 válida.",
        )

    return {
        "filename": filename,
        "size_bytes": file_size,
        "line_count": len(content.splitlines()),
        "content": content,
    }


@router.post(
    "",
    response_model=AnalysisCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_analysis(
    files: list[UploadFile] = File(default=[]),
    order: str | None = Form(
        default=None,
        description="Arreglo JSON opcional con los índices base 0 que definen el orden de ejecución (ej. [1, 0]).",
    ),
    name: str | None = Form(
        default=None,
        description="Nombre descriptivo opcional para el reporte histórico.",
    ),
    user_id: str = Depends(get_current_user_id),
):
    """Valida, ejecuta en sandbox, audita y persiste el reporte en app_db para su dueño."""
    try:
        if len(files) < MIN_FILES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debes adjuntar al menos 1 archivo .sql para iniciar el análisis.",
            )

        if len(files) > MAX_FILES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Solo se permite cargar un máximo de {MAX_FILES} archivos .sql por análisis.",
            )

        execution_order = _parse_execution_order(order, len(files))

        validated_files: list[dict] = []
        total_size = 0
        for upload in files:
            meta = await _read_and_validate_file(upload, total_size)
            total_size += meta["size_bytes"]
            validated_files.append(meta)

        ordered_entries = [validated_files[idx] for idx in execution_order]

        try:
            parsed_scripts = validate_scripts(
                [(entry["filename"], entry["content"]) for entry in ordered_entries]
            )
        except SqlValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.to_dict(),
            ) from exc

        try:
            sandbox_res = await run_in_threadpool(execute_in_sandbox, parsed_scripts)
        except SandboxExecutionError as exc:
            if exc.code == "SANDBOX_TIMEOUT":
                err_status = status.HTTP_408_REQUEST_TIMEOUT
            elif exc.code == "SANDBOX_CONNECTION_ERROR":
                err_status = status.HTTP_503_SERVICE_UNAVAILABLE
            else:
                err_status = status.HTTP_422_UNPROCESSABLE_ENTITY
            raise HTTPException(status_code=err_status, detail=exc.to_dict()) from exc

        try:
            scan_report = await run_in_threadpool(_scan_sandbox, sandbox_res.sandbox_db_name)
        except Exception as exc:
            await run_in_threadpool(drop_sandbox_db, sandbox_res.sandbox_db_name)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al ejecutar los detectores sobre el sandbox.",
            ) from exc

        ordered_summary = [
            AnalysisFileSummary(
                order=position,
                filename=entry["filename"],
                size_bytes=entry["size_bytes"],
                encoding="utf-8",
                line_count=entry["line_count"],
            )
            for position, entry in enumerate(ordered_entries, start=1)
        ]

        analysis_id = str(uuid4())
        analysis_name = ((name or "").strip() or ordered_summary[0].filename)[:200]
        created_at = datetime.now(timezone.utc)
        files_payload = [item.model_dump() for item in ordered_summary]
        scan_payload = scan_report.model_dump(mode="json")

        try:
            stored = await run_in_threadpool(
                insert_analysis,
                analysis_id=analysis_id,
                user_id=user_id,
                name=analysis_name,
                status="completado",
                message="Scripts SQL validados, ejecutados y auditados correctamente en sandbox aislado.",
                file_count=len(ordered_summary),
                total_size_bytes=total_size,
                files=files_payload,
                sandbox_db_name=sandbox_res.sandbox_db_name,
                executed_statements=sandbox_res.executed_statements,
                execution_time_ms=sandbox_res.execution_time_ms,
                scan=scan_payload,
                created_at=created_at,
            )
        except Exception as exc:
            await run_in_threadpool(drop_sandbox_db, sandbox_res.sandbox_db_name)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo guardar el reporte del análisis en app_db.",
            ) from exc

        return AnalysisCreateResponse(**stored)
    finally:
        for upload in files:
            await upload.close()


@router.get("", response_model=AnalysisListResponse)
async def list_analyses(user_id: str = Depends(get_current_user_id)):
    """Lista únicamente los análisis pertenecientes al usuario autenticado."""
    rows = await run_in_threadpool(list_analyses_for_user, user_id)
    return AnalysisListResponse(items=rows, total=len(rows))


@router.get("/{analysis_id}", response_model=AnalysisCreateResponse)
async def get_analysis_detail(
    analysis_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Obtiene el reporte completo desde app_db aunque el sandbox ya haya expirado."""
    record = await run_in_threadpool(get_analysis_for_user, analysis_id, user_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análisis no encontrado.",
        )
    return AnalysisCreateResponse(**record)


@router.delete("/{analysis_id}", response_model=AnalysisDeleteResponse)
async def delete_analysis(
    analysis_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Elimina un análisis propio y purga su base sandbox si sigue activa."""
    deleted = await run_in_threadpool(delete_analysis_for_user, analysis_id, user_id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análisis no encontrado.",
        )

    if deleted["sandbox_status"] == "active":
        await run_in_threadpool(drop_sandbox_db, deleted["sandbox_db_name"])

    return AnalysisDeleteResponse(
        id=deleted["id"],
        message="Análisis eliminado correctamente.",
    )

