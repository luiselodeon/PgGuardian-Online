"""
PgGuardian API — Router de Análisis de Scripts SQL (RF-01.1 y RF-01.2)

Recibe y valida la carga ordenada de hasta 5 archivos .sql en UTF-8 estricto,
respetando los límites de tamaño de 10 MB por archivo y 25 MB en total.
"""

from datetime import datetime, timezone
import json
from pathlib import PurePosixPath
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from api.schemas import AnalysisCreateResponse, AnalysisFileSummary

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
):
    """Valida hasta 5 scripts .sql en UTF-8 y devuelve el resumen ordenado en memoria."""
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

        ordered_summary = [
            AnalysisFileSummary(
                order=position,
                filename=validated_files[idx]["filename"],
                size_bytes=validated_files[idx]["size_bytes"],
                encoding="utf-8",
                line_count=validated_files[idx]["line_count"],
            )
            for position, idx in enumerate(execution_order, start=1)
        ]

        # shortcut: análisis validado en memoria sin persistencia ni ejecución en sandbox_db; actualizar en RF-01.4/RF-02.
        return AnalysisCreateResponse(
            id=str(uuid4()),
            status="validado",
            message="Scripts SQL validados correctamente y listos en el orden de ejecución.",
            file_count=len(ordered_summary),
            total_size_bytes=total_size,
            files=ordered_summary,
            created_at=datetime.now(timezone.utc),
        )
    finally:
        for upload in files:
            await upload.close()

