from __future__ import annotations

from sqlalchemy import select

from app.db.models.resume import Resume
from app.db.session import AsyncSessionLocal
from app.services.resume.embedder import embed
from app.services.resume.parser import extract_text, normalise_text
from app.services.resume.scorer import semantic_score, structural_score
from loguru import logger


async def process_resume(ctx: dict[str, object], *, resume_id: int, file_bytes: bytes) -> None:
    del ctx
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Resume).where(Resume.id == resume_id))
        resume = result.scalar_one_or_none()
        if resume is None:
            logger.warning("Resume {} not found for processing", resume_id)
            return

        resume.status = "processing"
        await session.commit()

        try:
            raw_text = normalise_text(extract_text(file_bytes, resume.format))
            embedding = embed(raw_text)
            resume.raw_text = raw_text
            resume.embedding = embedding
            resume.structural_score = structural_score(raw_text)
            resume.semantic_score = semantic_score(raw_text, embedding)
            resume.status = "completed"
            await session.commit()
        except Exception:
            await session.rollback()
            resume.status = "error"
            await session.commit()
            logger.exception("Resume processing failed for resume_id={}", resume_id)
            raise
