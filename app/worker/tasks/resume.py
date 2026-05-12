from __future__ import annotations

from loguru import logger


async def process_resume(ctx: dict[str, object], *, resume_id: int, file_bytes: bytes) -> None:
    logger.info(
        "Queued resume processing placeholder invoked for resume_id={} with {} bytes",
        resume_id,
        len(file_bytes),
    )
