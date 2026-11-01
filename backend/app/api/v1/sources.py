import hashlib
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import get_session
from app.core.exceptions import ApiError
from app.engine.pipeline import parse_source_bytes, profile_records
from app.models import SourceFile
from app.schemas import SourceListResponse, SourceUploadResponse

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("/upload", response_model=SourceUploadResponse, status_code=201)
async def upload_source(
    request: Request, file: UploadFile = File(...), session: Session = Depends(get_session)
):
    settings: Settings = request.app.state.settings
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.casefold()
    if suffix not in {".csv", ".json", ".jsonl", ".ndjson", ".xlsx", ".xlsm"}:
        raise ApiError(
            415,
            "unsupported_file_type",
            "Supported formats are UTF-8 CSV, JSON arrays/objects, JSON Lines, and Excel workbooks.",
        )
    content = await file.read(settings.max_upload_bytes + 1)
    await file.close()
    if len(content) > settings.max_upload_bytes:
        raise ApiError(
            413, "file_too_large", f"Uploads are limited to {settings.max_upload_bytes} bytes."
        )
    try:
        columns, records = parse_source_bytes(content, filename)
    except ValueError as exc:
        error_code = (
            "invalid_json"
            if suffix in {".json", ".jsonl", ".ndjson"}
            else "invalid_excel"
            if suffix in {".xlsx", ".xlsm"}
            else "invalid_csv"
        )
        raise ApiError(422, error_code, str(exc)) from exc
    if len(records) > settings.max_processing_rows:
        raise ApiError(
            413,
            "too_many_rows",
            f"Datasets are limited to {settings.max_processing_rows:,} data rows.",
        )
    profile = profile_records(columns, records, sample_size=settings.profile_sample_size)
    checksum = hashlib.sha256(content).hexdigest()
    existing = session.scalar(select(SourceFile).where(SourceFile.checksum == checksum))
    if existing:
        return existing
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    source_file_id = f"src_{checksum[:32]}"
    destination = settings.storage_dir / f"{checksum}{suffix}"
    if not destination.exists():
        with tempfile.NamedTemporaryFile(
            prefix=".upload-", suffix=".tmp", dir=settings.storage_dir, delete=False
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(content)
        os.replace(temp_path, destination)
    source = SourceFile(
        source_file_id=source_file_id,
        checksum=checksum,
        original_filename=filename[:255],
        storage_path=str(destination),
        size_bytes=len(content),
        columns=columns,
        profile=profile,
        schema_fingerprint=profile["schema_fingerprint"],
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


@router.get("", response_model=SourceListResponse)
def list_sources(session: Session = Depends(get_session)):
    items = session.scalars(select(SourceFile).order_by(SourceFile.uploaded_at.desc())).all()
    return {"items": items, "total": len(items)}
