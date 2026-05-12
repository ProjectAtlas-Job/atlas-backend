from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from uuid import uuid4

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import HTTPException, status

from app.core.config import settings

MAX_RESUME_FILE_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "md"}
ALLOWED_MIME_TYPES: dict[str, set[str]] = {
    "pdf": {"application/pdf"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "doc": {
        "application/msword",
        "application/x-ole-storage",
        "application/CDFV2",
    },
    "txt": {"text/plain"},
    "md": {"text/markdown", "text/plain"},
}
STORAGE_CONTENT_TYPES: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "txt": "text/plain",
    "md": "text/markdown",
}


def normalize_resume_label(label: str | None) -> str | None:
    if label is None:
        return None
    normalized = " ".join(label.strip().split())
    return normalized or None


def get_resume_extension(filename: str | None) -> str:
    if not filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resume filename is required.")

    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported resume format. Allowed formats: pdf, docx, doc, txt, md.",
        )
    return extension


def validate_resume_upload(file_bytes: bytes, extension: str) -> None:
    try:
        import magic
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resume MIME validation is not configured on the server.",
        ) from exc

    if len(file_bytes) > MAX_RESUME_FILE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Resume file exceeds 10 MB.")

    detected_mime = magic.from_buffer(file_bytes, mime=True)
    allowed_mimes = ALLOWED_MIME_TYPES[extension]
    if detected_mime not in allowed_mimes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File content does not match .{extension} format.",
        )


def _get_supabase_client() -> Any:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resume storage is not configured.",
        )
    try:
        from supabase import create_client
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resume storage client is not configured on the server.",
        ) from exc
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


async def upload_resume_to_storage(*, user_id: int, extension: str, file_bytes: bytes) -> str:
    storage_path = f"resumes/{user_id}/{uuid4()}.{extension}"
    client = _get_supabase_client()
    try:
        await asyncio.to_thread(
            client.storage.from_(settings.SUPABASE_RESUMES_BUCKET).upload,
            storage_path,
            file_bytes,
            {"content-type": STORAGE_CONTENT_TYPES[extension], "upsert": "false"},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resume storage upload failed.",
        ) from exc
    return storage_path


async def enqueue_resume_processing(*, resume_id: int, file_bytes: bytes) -> None:
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    try:
        await redis.enqueue_job("process_resume", resume_id=resume_id, file_bytes=file_bytes)
    finally:
        await redis.close()
